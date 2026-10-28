/// <reference lib="webworker" />
import { env, pipeline } from '@huggingface/transformers';
import { MODEL, type BackendPreference, type InferenceInfo, type Precision } from './shared';
env.allowRemoteModels = false;
env.allowLocalModels = true;
env.localModelPath = '/models/';
env.useBrowserCache = true;
// Served by Vite from node_modules; the production build includes the runtime assets.
if (env.backends.onnx.wasm) {
  env.backends.onnx.wasm.numThreads = 1;
  env.backends.onnx.wasm.wasmPaths = '/ort/';
}
let extractor: any;
let loadedKey = '';
let info: InferenceInfo;
async function load(dtype: Precision, backend: BackendPreference) {
  const key = `${dtype}:${backend}`;
  if (extractor && key === loadedKey) return info;
  await extractor?.dispose(); extractor = undefined; loadedKey = '';
  const started = performance.now();
  let consistency: InferenceInfo['consistency'];
  let reason = backend === 'wasm' ? '已显式选择 WASM，用于降级验证/基线比较' : '';
  const options = { dtype, local_files_only: true, revision: MODEL.revision,
    progress_callback: (progress: unknown) => self.postMessage({ type: 'progress', progress }) };
  if (backend !== 'wasm' && 'gpu' in navigator) {
    let reference: any;
    try {
      const adapter = await (navigator as any).gpu.requestAdapter();
      if (!adapter) throw new Error('未取得 GPU 适配器');
      extractor = await pipeline('feature-extraction', MODEL.id, { ...options, device: 'webgpu' });
      // Fixed, public calibration sentences detect gross backend numeric disagreement.
      // This is a startup smoke check; retrieval quality still needs labeled evaluation.
      const calibration = ['query: 如何保证机器学习实验可以复现？',
        'query: Hybrid retrieval combines keyword and semantic search.',
        'passage: 模型量化后的检索质量需要在同一语料上评估。'];
      reference = await pipeline('feature-extraction', MODEL.id, { ...options, device: 'wasm' });
      const gpuOutput = await extractor(calibration, { pooling: 'mean', normalize: true });
      const cpuOutput = await reference(calibration, { pooling: 'mean', normalize: true });
      const gpu = gpuOutput.tolist() as number[][], cpu = cpuOutput.tolist() as number[][];
      const cosines = gpu.map((v, i) => {
        const w = cpu[i];
        return v.reduce((sum, x, j) => sum + x * w[j], 0) /
          Math.sqrt(v.reduce((sum, x) => sum + x * x, 0) * w.reduce((sum, x) => sum + x * x, 0));
      });
      gpuOutput.dispose?.(); cpuOutput.dispose?.();
      const minimumCosine = Math.min(...cosines), threshold = 0.99;
      consistency = { minimumCosine, threshold, samples: calibration.length };
      if (!Number.isFinite(minimumCosine) || minimumCosine < threshold)
        throw new Error(`后端一致性检查未通过（最小余弦 ${minimumCosine.toFixed(4)} < ${threshold}）`);
      info = { device: 'webgpu', dtype, reason: '本地 WebGPU 推理，已通过后端一致性检查', consistency, loadMs: performance.now() - started, model: MODEL.id, revision: MODEL.revision };
    } catch (e) {
      await extractor?.dispose(); extractor = undefined;
      reason = `WebGPU 不可用，自动降级 WASM：${String(e).slice(0, 180)}`;
    } finally { await reference?.dispose(); }
  } else if (backend !== 'wasm') reason = '此浏览器未提供 WebGPU，自动使用 WASM';
  if (!extractor) {
    extractor = await pipeline('feature-extraction', MODEL.id, { ...options, device: 'wasm' });
    info = { device: 'wasm', dtype, reason, consistency, loadMs: performance.now() - started, model: MODEL.id, revision: MODEL.revision };
  }
  loadedKey = key;
  return info;
}
async function embed(texts: string[], kind: 'query' | 'passage') {
  const result = await extractor(texts.map(text => `${kind}: ${text}`), { pooling: 'mean', normalize: true });
  return result.tolist() as number[][];
}
// One worker queue prevents switching/disposal in the middle of a batch.
let queue = Promise.resolve();
self.onmessage = event => {
  const message = event.data;
  queue = queue.catch(() => {}).then(async () => {
    try {
      const inference = await load(message.dtype, message.backend);
      const started = performance.now();
      let vectors: number[][] = [];
      if (message.texts?.length) {
        try { vectors = await embed(message.texts, message.kind); }
        catch (e) {
          if (inference.device !== 'webgpu') throw e;
          // A backend may initialize successfully but fail on its first real graph execution.
          const failure = String(e).slice(0, 160);
          await load(message.dtype, 'wasm');
          info.reason = `WebGPU 图执行失败，自动改用 WASM：${failure}`;
          loadedKey = `${message.dtype}:${message.backend}`;
          vectors = await embed(message.texts, message.kind);
        }
      }
      self.postMessage({ id: message.id, type: 'result', info, vectors, inferenceMs: performance.now() - started });
    } catch (e) { self.postMessage({ id: message.id, type: 'error', error: String(e) }); }
  });
};
