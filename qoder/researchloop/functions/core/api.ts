import { idFromFingerprint, provenance } from './chunk.ts';
import { keywords } from './keywords.ts';
import { buildWeeklyReport, weekRange } from './report.ts';
import { InputError } from './validate.ts';
import * as rules from './validate.ts';
import { LIMITS, type ActionRecord } from './domain.ts';
import type { ActionPatch, Store } from './store.ts';

export class ApiError extends Error {
  status: number;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' },
  });

const MAX_BODY = 1_000_000;

async function body(request: Request): Promise<Record<string, unknown>> {
  const type = request.headers.get('content-type') ?? '';
  if (!type.startsWith('application/json')) throw new ApiError(400, 'invalid_content_type', '请求体需为 JSON。');
  const reader = request.body?.getReader();
  if (!reader) throw new ApiError(400, 'empty_body', '请求体为空。');
  const chunks: Uint8Array[] = [];
  let size = 0;
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > MAX_BODY) { await reader.cancel(); throw new ApiError(413, 'payload_too_large', `请求体超过 ${MAX_BODY} 字节。`); }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const bytes = new Uint8Array(size);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.length; }
  try {
    return JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes)) as Record<string, unknown>;
  } catch {
    throw new ApiError(400, 'invalid_json', '请求体不是有效 JSON。');
  }
}

// Node and Deno both report UTC; the demo workspace is used by Chinese study teams.
const serverDay = (): string => new Date(Date.now() + 8 * 60 * 60 * 1000).toISOString().slice(0, 10);

const route = (pathname: string): string => {
  const match = pathname.match(/^\/(?:functions\/v1\/)?(?:app|app-d[0-9a-f]{32})(\/.*)?$/);
  if (match) return match[1] || '/';
  return pathname;
};

export function application(store: Store) {
  return async (request: Request): Promise<Response> => {
    const url = new URL(request.url);
    const path = route(url.pathname);
    const method = request.method.toUpperCase();
    try {
      if (path === '/api/health' && method === 'GET') {
        return json({ ok: true, backend: store.backend, label: store.label, today: serverDay() });
      }

      if (path === '/api/state' && method === 'GET') {
        const workspace = rules.workspaceId(url.searchParams.get('workspace'));
        const [counters, sources, actions] = await Promise.all([
          store.counters(workspace),
          store.listSources(workspace, 50),
          store.listActions(workspace, 'all'),
        ]);
        return json({ ok: true, workspace, counters, sources, actions });
      }

      if (path === '/api/search' && method === 'GET') {
        const workspace = rules.workspaceId(url.searchParams.get('workspace'));
        const query = rules.queryText(url.searchParams.get('q'));
        const limit = rules.resultLimit(url.searchParams.get('limit'), 6);
        const terms = keywords(query);
        if (!terms.length) throw new ApiError(400, 'no_keywords', '请输入包含实词的问题。');
        const started = Date.now();
        const candidates = await store.searchChunks(workspace, terms, Math.min(LIMITS.resultLimit * 4, 80));
        const scored = candidates
          .map(candidate => ({
            chunk: candidate.chunk,
            dbScore: candidate.dbScore,
            matched: terms.filter(term => candidate.chunk.content.toLowerCase().includes(term.toLowerCase())),
          }))
          .filter(row => row.matched.length > 0 || (row.dbScore !== null && row.dbScore > 0));
        const ordered = scored.sort((a, b) => (b.dbScore ?? 0) - (a.dbScore ?? 0) || b.matched.length - a.matched.length
          || a.chunk.sourceName.localeCompare(b.chunk.sourceName, 'zh-Hans-CN')
          || a.chunk.chunkNo - b.chunk.chunkNo);
        const hits = ordered.slice(0, limit).map(hit => ({ ...hit, provenance: provenance(hit.chunk) }));
        return json({
          ok: true, workspace, query, terms, engine: store.label,
          retrieval: 'database-fulltext-ranked',
          tookMs: Date.now() - started, hits,
        });
      }

      if (path === '/api/chunks' && method === 'GET') {
        const workspace = rules.workspaceId(url.searchParams.get('workspace'));
        const sourceId = rules.chunkId(url.searchParams.get('sourceId'));
        if (!sourceId) throw new ApiError(400, 'invalid_source_id', '缺少资料标识。');
        const limit = rules.resultLimit(url.searchParams.get('limit'), 20);
        return json({ ok: true, chunks: await store.listChunks(workspace, sourceId, limit) });
      }

      if (path === '/api/sources' && method === 'POST') {
        const input = await body(request);
        const workspace = rules.workspaceId(input.workspace);
        const name = rules.sourceName(input.name);
        const text = rules.importText(input.text);
        const result = await store.importSource({ workspaceId: workspace, name, text });
        return json({ ok: true, ...result }, 201);
      }

      if (path === '/api/actions' && method === 'GET') {
        const workspace = rules.workspaceId(url.searchParams.get('workspace'));
        const statusParam = url.searchParams.get('status') ?? 'all';
        const status = statusParam === 'all' ? 'all' : rules.statusValue(statusParam);
        return json({ ok: true, actions: await store.listActions(workspace, status) });
      }

      if (path === '/api/actions' && method === 'POST') {
        const input = await body(request);
        const workspace = rules.workspaceId(input.workspace);
        const title = rules.actionTitle(input.title);
        const owner = rules.ownerName(input.ownerName);
        const due = rules.dueDate(input.dueDate);
        const status = rules.statusValue(input.status ?? 'open');
        const refChunkId = rules.chunkId(input.refChunkId);
        const key = typeof input.idempotencyKey === 'string' ? input.idempotencyKey.trim() : '';
        if (!/^[a-f0-9-]{36}$/.test(key)) throw new ApiError(400, 'invalid_idempotency_key', '缺少有效的幂等键，请刷新页面重试。');
        const createdAt = new Date().toISOString();
        let reference: ActionRecord['refSourceName'] = '';
        let refChunkNo: number | null = null;
        let refChunkRevision: number | null = null;
        if (refChunkId) {
          const chunk = await store.chunkById(workspace, refChunkId);
          if (!chunk) throw new ApiError(404, 'chunk_not_found', '关联出处不在当前工作区，请重新选择。');
          reference = chunk.sourceName;
          refChunkNo = chunk.chunkNo;
          refChunkRevision = chunk.revision;
        }
        const id = await idFromFingerprint(`${workspace}|${key}`);
        const created = await store.createAction({
          id, workspaceId: workspace, title, ownerName: owner, dueDate: due, status,
          refChunkId, refSourceName: reference, refChunkNo, refChunkRevision,
          createdAt, updatedAt: createdAt, completedAt: status === 'done' ? createdAt.slice(0, 10) : null,
        });
        return json({ ok: true, action: created }, 201);
      }

      const actionPath = path.match(/^\/api\/actions\/([a-f0-9]{64})$/);
      if (actionPath && method === 'PATCH') {
        const input = await body(request);
        const workspace = rules.workspaceId(input.workspace);
        const patch: ActionPatch = { updatedAt: new Date().toISOString() };
        if (input.title !== undefined) patch.title = rules.actionTitle(input.title);
        if (input.ownerName !== undefined) patch.ownerName = rules.ownerName(input.ownerName);
        if (input.dueDate !== undefined) patch.dueDate = rules.dueDate(input.dueDate);
        if (input.status !== undefined) {
          patch.status = rules.statusValue(input.status);
          patch.completedAt = patch.status === 'done' ? serverDay() : null;
        }
        const updated = await store.updateAction(workspace, actionPath[1], patch);
        if (!updated) throw new ApiError(404, 'action_not_found', '行动项不存在或不属于当前工作区。');
        return json({ ok: true, action: updated });
      }

      if (path === '/api/report' && method === 'GET') {
        const workspace = rules.workspaceId(url.searchParams.get('workspace'));
        const week = url.searchParams.get('week');
        const today = serverDay();
        const anchor = week ? rules.isoDate(week) : today;
        const range = weekRange(anchor);
        const actions = await store.listActions(workspace, 'all');
        const report = buildWeeklyReport(actions, anchor, range, today);
        return json({ ok: true, workspace, today, ...report });
      }

      if (path === '/' && method === 'GET') {
        return json({ ok: true, service: 'researchloop', endpoints: ['/api/health', '/api/state', '/api/search', '/api/sources', '/api/actions', '/api/report'] });
      }

      throw new ApiError(404, 'not_found', '接口不存在。');
    } catch (error) {
      if (error instanceof InputError) return json({ ok: false, error: error.code, message: error.message }, 400);
      if (error instanceof ApiError) return json({ ok: false, error: error.code, message: error.message }, error.status);
      const detail = error instanceof Error ? error.message : 'unknown';
      const notReady = /not connect|ECONNREFUSED|ETIMEDOUT|getaddrinfo|ENOTFOUND|EHOSTUNREACH/i;
      if (notReady.test(detail)) {
        return json({ ok: false, error: 'backend_unavailable', message: '后端数据服务当前不可用，页面不会用示例结果替代真实检索。' }, 503);
      }
      return json({ ok: false, error: 'internal_error', message: '服务处理失败，请稍后重试。' }, 500);
    }
  };
}
