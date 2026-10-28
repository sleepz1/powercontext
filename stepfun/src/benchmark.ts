import { EmbeddingEngine } from './embedding';
import { api, type Target } from './api';
import { toChunks } from './documents';
import { qualityMetrics } from './evaluation';
import { MODEL, median, type Precision, type BackendPreference, type SearchHit } from './shared';
export interface Profile { label: string; dtype: Precision; backend: BackendPreference; batch: number }
export const profiles: Profile[] = [
  { label: 'FP32 / WASM / batch 1', dtype: 'fp32', backend: 'wasm', batch: 1 },
  { label: 'INT8 / WASM / batch 1', dtype: 'q8', backend: 'wasm', batch: 1 },
  { label: 'INT8 / WASM / batch 8', dtype: 'q8', backend: 'wasm', batch: 8 },
  { label: 'INT8 / Auto WebGPU / batch 8', dtype: 'q8', backend: 'auto', batch: 8 },
];
export async function benchmark(namespace: string, progress: (message: string) => void, selected = profiles) {
  const documents = await (await fetch('/sample.json')).json() as { source: string; text: string }[];
  const queries = await (await fetch('/queries.json')).json() as { query: string; relevant: string[] }[];
  const chunks = (await Promise.all(documents.map(x => toChunks(x.text, x.source)))).flat();
  const manifest = await api('model-manifest');
  const runs: any[] = [];
  const benchmarkId = Date.now().toString(36);
  for (const [index, config] of selected.entries()) {
    const engine = new EmbeddingEngine(); engine.onProgress = progress;
    const t: Target = { namespace, collection: `bench_${benchmarkId}_${index}`, dtype: config.dtype };
    try {
      progress(`加载 ${config.label}`);
      const coldStarted = performance.now();
      const loaded = await engine.run([], 'query', config.dtype, config.backend);
      const loadMs = performance.now() - coldStarted;
      await api('collections', t);
      const inferenceRuns: number[] = [];
      let written: any;
      // Three measured passes over the same corpus, with identical write/refresh boundaries.
      for (let repeat = 0; repeat < 3; repeat++) {
        const records: any[] = []; let inferenceMs = 0;
        for (let i = 0; i < chunks.length; i += config.batch) {
          const group = chunks.slice(i, i + config.batch);
          const embedding = await engine.run(group.map(x => x.text), 'passage', config.dtype, config.backend);
          inferenceMs += embedding.inferenceMs;
          records.push(...group.map((chunk, j) => ({ ...chunk, embedding: embedding.vectors[j] })));
        }
        written = await api('import', { ...t, records });
        inferenceRuns.push(inferenceMs);
      }
      // Cold/first execution is retained separately; warmed queries are measured below.
      const firstStart = performance.now();
      const firstVector = await engine.run([queries[0].query], 'query', config.dtype, config.backend);
      await api('search', { ...t, query: queries[0].query, vector: firstVector.vectors[0], limit: 5 });
      const firstQueryMs = performance.now() - firstStart;
      const raw: any[] = [];
      for (let repeat = 0; repeat < 3; repeat++) for (const q of queries) {
        progress(`${config.label} · 查询 ${repeat + 1}/3 · ${q.query}`);
        const start = performance.now();
        const embedding = await engine.run([q.query], 'query', config.dtype, config.backend);
        const result = await api<{ hits: SearchHit[]; searchMs: number }>('search', { ...t, query: q.query, vector: embedding.vectors[0], limit: 5 });
        raw.push({ repeat, query: q.query, relevant: q.relevant, hits: result.hits, inferenceMs: embedding.inferenceMs,
          searchMs: result.searchMs, endToEndMs: performance.now() - start,
          ...qualityMetrics(result.hits.map(x => x.source), q.relevant), actualDevice: embedding.info.device });
      }
      runs.push({ config, actualBackend: firstVector.info, loadMs, firstQueryMs, corpusEmbeddingMs: inferenceRuns,
        documentsPerSecond: chunks.length / (median(inferenceRuns)! / 1000), lastWrite: written, raw,
        medianSearchMs: median(raw.map(x => x.searchMs)), medianEndToEndMs: median(raw.map(x => x.endToEndMs)),
        recallAt5: raw.reduce((s, x) => s + x.recall, 0) / raw.length,
        ndcgAt5: raw.reduce((s, x) => s + x.ndcg, 0) / raw.length });
    } finally { engine.dispose(); }
  }
  return { recordedAt: new Date().toISOString(), model: MODEL, manifest, userAgent: navigator.userAgent,
    hardwareConcurrency: navigator.hardwareConcurrency, corpusChunks: chunks.length, queryCount: queries.length,
    method: '原始计时含 3 次语料向量化及 3 轮查询；首次模型加载独立记录；热查询含 Worker 与本地 API 往返，不含 UI 绘制。样例集质量仅代表该集。',
    runs };
}
