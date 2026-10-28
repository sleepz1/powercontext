import { createHash } from 'node:crypto';
import { SeekdbClient, Schema, VectorIndexConfig, FulltextIndexConfig } from 'seekdb';
import { MODEL, namespacePattern, validCollection, validateVector, type Precision, type DocumentChunk } from '../src/shared';

export const client = new SeekdbClient({
  host: process.env.SEEKDB_HOST ?? '127.0.0.1', port: Number(process.env.SEEKDB_PORT ?? 2881),
  user: process.env.SEEKDB_USER ?? 'root', password: process.env.SEEKDB_PASSWORD ?? '',
  database: process.env.SEEKDB_DATABASE ?? 'test',
});
const pending = new Map<string, Promise<unknown>>();
const dirty = new Set<string>();
export interface Target { namespace: string; collection: string; dtype: Precision }
export function target(input: Record<string, unknown>): Target {
  if (typeof input.namespace !== 'string' || !namespacePattern.test(input.namespace)) throw new Error('会话标识无效');
  if (!validCollection(input.collection)) throw new Error('集合名需以小写字母开头，且仅含小写字母、数字、下划线，最长 31 字符');
  if (input.dtype !== 'q8' && input.dtype !== 'fp32') throw new Error('模型精度无效');
  return { namespace: input.namespace, collection: input.collection, dtype: input.dtype };
}
export function dbName(t: Target): string {
  const fingerprint = createHash('sha256').update(`${t.namespace}|${MODEL.id}|${MODEL.revision}|${t.dtype}`).digest('hex').slice(0, 16);
  return `lf_${fingerprint}_${t.collection}`;
}
export async function serial<T>(name: string, fn: () => Promise<T>): Promise<T> {
  const previous = pending.get(name) ?? Promise.resolve();
  const next = previous.catch(() => {}).then(fn);
  pending.set(name, next);
  try { return await next; } finally { if (pending.get(name) === next) pending.delete(name); }
}
export async function getCollection(t: Target) {
  return client.getCollection({ name: dbName(t), embeddingFunction: null });
}
export async function ensureCollection(t: Target) {
  return client.getOrCreateCollection({
    name: dbName(t), embeddingFunction: null,
    schema: new Schema({
      fulltextIndex: new FulltextIndexConfig('ngram', { ngram_token_size: 2 }),
      vectorIndex: new VectorIndexConfig({ hnsw: { dimension: MODEL.dimension, distance: 'cosine' }, embeddingFunction: null }),
    }),
  });
}
export function records(input: unknown): (DocumentChunk & { embedding: number[] })[] {
  if (!Array.isArray(input) || !input.length || input.length > 64) throw new Error('单批须包含 1–64 个分块');
  return input.map(r => {
    if (!r || typeof r.id !== 'string' || !/^[a-f0-9]{64}$/.test(r.id) || typeof r.text !== 'string' || !r.text.trim() || r.text.length > 2000
      || typeof r.source !== 'string' || !r.source || r.source.length > 240 || !Number.isInteger(r.chunk) || r.chunk < 0 || !validateVector(r.embedding))
      throw new Error('文档或 384 维向量无效；服务端不会代算 embedding');
    return r;
  });
}
export async function importRecords(t: Target, rows: ReturnType<typeof records>) {
  const name = dbName(t);
  return serial(name, async () => {
    const collection = await ensureCollection(t);
    dirty.add(name);
    const started = performance.now();
    await collection.upsert({ ids: rows.map(x => x.id), documents: rows.map(x => x.text),
      metadatas: rows.map(x => ({ source: x.source, chunk: x.chunk, model: MODEL.id, revision: MODEL.revision, dtype: t.dtype })),
      embeddings: rows.map(x => x.embedding) });
    const written = performance.now();
    await collection.refresh_index();
    dirty.delete(name);
    return { count: await collection.count(), writeMs: written - started, refreshMs: performance.now() - written };
  });
}
export async function refresh(t: Target) {
  return serial(dbName(t), async () => {
    const collection = await getCollection(t);
    const start = performance.now();
    await collection.refresh_index(); dirty.delete(dbName(t));
    return { count: await collection.count(), refreshMs: performance.now() - start };
  });
}
export async function search(t: Target, query: string, vector: number[], limit: number) {
  return serial(dbName(t), async () => {
    if (dirty.has(dbName(t))) throw new Error('上一批写入尚未成功刷新索引，请点击刷新后重试');
    const collection = await getCollection(t);
    const started = performance.now();
    // Both retrieval branches and RRF execute inside seekdb through DBMS_HYBRID_SEARCH.
    const results = await collection.hybridSearch({
      query: { whereDocument: { $contains: query }, nResults: 30 },
      knn: { queryEmbeddings: [vector], nResults: 30 },
      rank: { rrf: { rankWindowSize: 30, rankConstant: 60 } }, nResults: limit,
      include: ['documents', 'metadatas', 'distances'],
    });
    return { searchMs: performance.now() - started, hits: (results.ids[0] ?? []).map((id, i) => ({
      id, text: results.documents?.[0]?.[i] ?? '', source: results.metadatas?.[0]?.[i]?.source ?? '',
      distance: results.distances?.[0]?.[i] ?? null,
    })) };
  });
}
