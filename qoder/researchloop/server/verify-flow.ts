// End-to-end acceptance run against the local seekdb-backed core service.
// Requires: seekdb running and `npm start` in this directory.
// node --experimental-strip-types --no-warnings verify-flow.ts
import { mkdir, writeFile } from 'node:fs/promises';
import { chunkText } from '../functions/core/chunk.ts';
import { SAMPLE_MATERIALS } from '../functions/core/samples.ts';

const base = process.env.VERIFY_BASE ?? 'http://127.0.0.1:8788';
const evidencePath = new URL('../results/seekdb-verify.json', import.meta.url);
const evidence: Record<string, unknown> = { startedAt: new Date().toISOString(), base, steps: [] as string[], checks: [] as { name: string; pass: boolean; detail: unknown }[] };

const writeEvidence = async (): Promise<void> => {
  evidence.finishedAt = new Date().toISOString();
  evidence.allPassed = evidence.checks.every(check => check.pass);
  await mkdir(new URL('../results', import.meta.url), { recursive: true });
  await writeFile(evidencePath, JSON.stringify(evidence, null, 2), 'utf8');
};

const record = (name: string, pass: boolean, detail: unknown) => {
  evidence.checks.push({ name, pass, detail });
  console.log(`${pass ? 'PASS' : 'FAIL'} ${name} :: ${JSON.stringify(detail).slice(0, 260)}`);
};

async function call(path: string, init?: RequestInit): Promise<{ status: number; json: any }> {
  const response = await fetch(base + path, init);
  const json = await response.json();
  return { status: response.status, json };
}

const post = (path: string, payload: unknown, headers: Record<string, string> = {}) =>
  call(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json', ...headers },
    body: JSON.stringify(payload),
  });

// 1. Backend identity must be the real seekdb service, not a fixture.
const health = await call('/api/health');
record('health.reports-seekdb', health.json.backend === 'seekdb', health.json);

// 2. Import the public sample materials (workspace `verify` is used twice to prove idempotency).
const importWorkspace = 'verify';
let firstCreated = 0;
for (const material of SAMPLE_MATERIALS) {
  const result = await post('/api/sources', { workspace: importWorkspace, name: material.name, text: material.text });
  if (result.status !== 201) { record(`import.${material.name}`, false, result.json); continue; }
  firstCreated += result.json.created;
  record(`import.${material.name}`, true, { chunks: result.json.source.chunkCount, created: result.json.created, skipped: result.json.skipped, revision: result.json.revision });
}
const again = await post('/api/sources', { workspace: importWorkspace, name: SAMPLE_MATERIALS[0].name, text: SAMPLE_MATERIALS[0].text });
record('import.idempotent-reimport', again.json.created === 0 && again.json.skipped > 0 && again.json.retired === 0,
  { created: again.json.created, skipped: again.json.skipped, retired: again.json.retired, revision: again.json.revision });

// 3. Real retrieval with provenance.
const search = await call(`/api/search?workspace=${importWorkspace}&q=${encodeURIComponent('怎样保证实验可以复现')}&limit=5`);
const topHit = search.json.hits?.[0];
record('search.returns-ranked-hits', search.json.ok === true && search.json.hits.length > 0, {
  retrieval: search.json.retrieval, terms: search.json.terms, tookMs: search.json.tookMs,
  top: topHit ? { source: topHit.chunk.sourceName, chunk: topHit.chunk.chunkNo, dbScore: topHit.dbScore, provenance: topHit.provenance } : null,
});
record('search.hit-has-provenance', !!topHit?.chunk?.content && !!topHit?.provenance, { provenance: topHit?.provenance, excerpt: topHit?.chunk?.content?.slice(0, 60) });
if (!topHit) {
  await writeEvidence();
  console.error('检索没有返回结果，后续步骤无法继续。');
  process.exit(1);
}

// 4. Collection isolation: another workspace sees nothing.
const isolated = await call(`/api/search?workspace=verify-isolated&q=${encodeURIComponent('实验复现')}&limit=5`);
record('search.workspace-isolation', isolated.json.hits?.length === 0, { hitsInOtherWorkspace: isolated.json.hits?.length });

// 5. Action item bound to the retrieved chunk.
const key = crypto.randomUUID();
const created = await post('/api/actions', {
  workspace: importWorkspace, title: '补齐实验依赖版本并输出锁文件', ownerName: '陈同学',
  dueDate: new Date(Date.now() + 3 * 86400000).toISOString().slice(0, 10), status: 'open',
  refChunkId: topHit.chunk.id, idempotencyKey: key,
});
record('action.create-with-provenance', created.status === 201 && created.json.action?.refSourceName?.length > 0
  && created.json.action?.refChunkRevision === topHit.chunk.revision, created.json);
if (!created.json.action) {
  await writeEvidence();
  console.error('行动项创建失败，后续步骤无法继续。');
  process.exit(1);
}

const retry = await post('/api/actions', {
  workspace: importWorkspace, title: '补齐实验依赖版本并输出锁文件', ownerName: '陈同学',
  dueDate: created.json.action.dueDate, status: 'open', refChunkId: topHit.chunk.id, idempotencyKey: key,
});
record('action.idempotent-retry', retry.json.action?.id === created.json.action?.id, { status: retry.status, sameId: retry.json.action?.id === created.json.action?.id });

const patched = await call(`/api/actions/${created.json.action.id}`, {
  method: 'PATCH', headers: { 'content-type': 'application/json' },
  body: JSON.stringify({ workspace: importWorkspace, status: 'done' }),
});
record('action.complete', patched.json.action?.status === 'done' && !!patched.json.action?.completedAt, { status: patched.json.action?.status, completedAt: patched.json.action?.completedAt });

// 6. Weekly report includes the finished task and its provenance.
const report = await call(`/api/report?workspace=${importWorkspace}`);
const text = report.json.text as string;
record('report.contains-completed-action', text.includes('补齐实验依赖版本') && text.includes('出处：'), { range: report.json.range, excerpt: text.slice(0, 300) });
record('report.declares-template-rule', report.json.rule === 'template' && report.json.completed.length > 0, { rule: report.json.rule, completed: report.json.completed.length, pending: report.json.pending.length });

// 7. Persistence across a fresh read (no in-memory cache in the service).
const state = await call(`/api/state?workspace=${importWorkspace}`);
record('state.persisted-in-seekdb', state.json.counters.chunks > 0 && state.json.counters.sources === SAMPLE_MATERIALS.length && state.json.actions.length > 0, state.json.counters);

const badSearch = await call(`/api/search?workspace=${importWorkspace}&q=`);
record('search.empty-query-rejected', badSearch.status === 400, badSearch.json);
const unknownRoute = await call('/api/nope');
record('route.unknown-404', unknownRoute.status === 404, unknownRoute.json);

// 8. Long material: every character must reach the database, never a silent tail cut.
// 182k characters needs 415 chunks, which is beyond the 400-chunk window a previous
// build capped at: the tail used to be dropped without a word.
const largeWorkspace = 'verify-large';
const largeBody = '这一段资料用于验证长文本分块容量上限的处理方式。'.repeat(7600);
const largeTail = '尾部校验标记：最后一段内容不得被丢弃，用于证明分块完整。';
const largeText = `${largeBody}\n${largeTail}`;
const largeImport = await post('/api/sources', { workspace: largeWorkspace, name: '长文本完整性校验.txt', text: largeText });
const expectedChunks = chunkText(largeText).length;
record('import.long-material-all-chunks', largeImport.status === 201 && largeImport.json.source.chunkCount === expectedChunks, {
  characters: largeText.length, storedChunks: largeImport.json.source?.chunkCount, expectedChunks,
});
const overLimit = '超出上限的资料片段。'.repeat(20_001);
const oversized = await post('/api/sources', { workspace: largeWorkspace, name: '超长度资料.txt', text: overLimit });
record('import.over-length-rejected', oversized.status === 400 && oversized.json.error === 'material_too_large', {
  characters: overLimit.length, status: oversized.status, error: oversized.json.error, message: oversized.json.message,
});
const tailSearch = await call(`/api/search?workspace=${largeWorkspace}&q=${encodeURIComponent('尾部校验标记')}&limit=20`);
const tailHit = (tailSearch.json.hits ?? []).find((hit: any) => String(hit.chunk?.content ?? '').includes('尾部校验标记'));
record('import.long-material-tail-searchable', !!tailHit, {
  hits: tailSearch.json.hits?.length, chunkNo: tailHit?.chunk?.chunkNo, expectedLastChunkNo: expectedChunks - 1,
});

// 9. Same-name re-import: new revision, old chunks retired but still citable.
// A run-scoped workspace keeps the revision arithmetic meaningful across repeated runs.
const versionWorkspace = `verify-version-${Date.now().toString(36)}`;
const versionName = '组会纪要-版本策略.md';
const v1 = await post('/api/sources', {
  workspace: versionWorkspace, name: versionName,
  text: '# 组会纪要（第一版）\n\n第一版独有内容：本周确定基线实验范围，负责人陈同学。\n',
});
record('version.first-revision', v1.status === 201 && v1.json.revision === 1 && v1.json.retired === 0, {
  revision: v1.json.revision, created: v1.json.created, retired: v1.json.retired,
});
const v1Chunks = await call(`/api/chunks?workspace=${versionWorkspace}&sourceId=${encodeURIComponent(v1.json.source.id)}&limit=20`);
const firstGeneration = v1Chunks.json.chunks as any[];
const historicalChunkId = firstGeneration[0]?.id;
record('version.first-generation-read', firstGeneration.length > 0 && firstGeneration.every(c => c.revision === 1), {
  chunkCount: firstGeneration.length, chunkIds: firstGeneration.map(c => c.id.slice(0, 8)),
});
const v2 = await post('/api/sources', {
  workspace: versionWorkspace, name: versionName,
  text: '# 组会纪要（第二版）\n\n第二版独有内容：基线范围扩大到两组数据集，负责人改为李同学。\n',
});
record('version.bump-retires-previous-chunks', v2.json.revision === 2 && v2.json.retired === firstGeneration.length, {
  revision: v2.json.revision, created: v2.json.created, retired: v2.json.retired, chunkCount: v2.json.source.chunkCount,
});
const staleSearch = await call(`/api/search?workspace=${versionWorkspace}&q=${encodeURIComponent('第一版独有内容')}&limit=10`);
const staleHits = (staleSearch.json.hits ?? []) as any[];
// Full-text matching legitimately returns partially related current chunks; the
// invariant is that a retired chunk never surfaces again.
record('version.retired-content-not-searchable', staleHits.every(hit => hit.chunk.id !== historicalChunkId)
  && staleHits.every(hit => !String(hit.chunk.content).includes('第一版独有内容')), {
  hits: staleHits.length, returned: staleHits.map(hit => `${hit.provenance}`),
});
const freshSearch = await call(`/api/search?workspace=${versionWorkspace}&q=${encodeURIComponent('第二版独有内容')}&limit=10`);
record('version.current-content-searchable', (freshSearch.json.hits ?? []).length > 0, {
  hits: freshSearch.json.hits?.length, topProvenance: freshSearch.json.hits?.[0]?.provenance,
});
const v2Chunks = await call(`/api/chunks?workspace=${versionWorkspace}&sourceId=${encodeURIComponent(v2.json.source.id)}&limit=20`);
const currentGeneration = v2Chunks.json.chunks as any[];
record('version.active-generation-unique', currentGeneration.every(c => c.revision === 2)
  && new Set(currentGeneration.map(c => c.chunkNo)).size === currentGeneration.length, {
  active: currentGeneration.map(c => ({ no: c.chunkNo, revision: c.revision })),
});
const historicalAction = await post('/api/actions', {
  workspace: versionWorkspace, title: '按第一版纪要核对负责人变更', ownerName: '李同学',
  dueDate: new Date(Date.now() + 2 * 86400000).toISOString().slice(0, 10), status: 'open',
  refChunkId: historicalChunkId, idempotencyKey: crypto.randomUUID(),
});
record('version.historical-citation-still-resolves', historicalAction.status === 201
  && historicalAction.json.action?.refChunkRevision === 1 && !!historicalAction.json.action?.refSourceName, {
  status: historicalAction.status, revision: historicalAction.json.action?.refChunkRevision,
  source: historicalAction.json.action?.refSourceName, chunkNo: historicalAction.json.action?.refChunkNo,
});
const versionState = await call(`/api/state?workspace=${versionWorkspace}`);
record('version.source-row-current-revision', versionState.json.sources?.[0]?.revision === 2
  && versionState.json.counters.chunks === currentGeneration.length, {
  sourceRevision: versionState.json.sources?.[0]?.revision, activeChunks: versionState.json.counters.chunks,
});
const versionReport = await call(`/api/report?workspace=${versionWorkspace}`);
record('version.report-quotes-locked-revision', String(versionReport.json.text ?? '').includes('版本 1'), {
  excerpt: String(versionReport.json.text ?? '').split('\n').find(line => line.includes('按第一版纪要')) ?? '',
});

await writeEvidence();
console.log(`\n${evidence.allPassed ? '全部通过' : '存在失败'}：${evidence.checks.filter(c => c.pass).length}/${evidence.checks.length}，证据写入 results/seekdb-verify.json`);
process.exitCode = evidence.allPassed ? 0 : 1;
