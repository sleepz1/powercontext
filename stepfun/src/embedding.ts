import type { BackendPreference, InferenceInfo, Precision } from './shared';
export interface EmbedResult { vectors: number[][]; info: InferenceInfo; inferenceMs: number }
export class EmbeddingEngine {
  private worker = new Worker(new URL('./embedding.worker.ts', import.meta.url), { type: 'module' });
  private seq = 0;
  private requests = new Map<number, { resolve: (value: EmbedResult) => void; reject: (error: Error) => void }>();
  onProgress: (message: string) => void = () => {};
  dispose() { this.worker.terminate(); for (const r of this.requests.values()) r.reject(new Error('推理已终止')); this.requests.clear(); }
  constructor() {
    this.worker.onmessage = ({ data }) => {
      if (data.type === 'progress') { this.onProgress(`${data.progress.status ?? ''} ${data.progress.file ?? ''} ${Math.round(data.progress.progress ?? 0)}%`); return; }
      const request = this.requests.get(data.id); if (!request) return;
      this.requests.delete(data.id);
      data.type === 'error' ? request.reject(new Error(data.error)) : request.resolve(data);
    };
    this.worker.onerror = e => { for (const r of this.requests.values()) r.reject(new Error(e.message)); this.requests.clear(); };
  }
  run(texts: string[], kind: 'query' | 'passage', dtype: Precision, backend: BackendPreference): Promise<EmbedResult> {
    const id = ++this.seq;
    return new Promise((resolve, reject) => { this.requests.set(id, { resolve, reject }); this.worker.postMessage({ id, texts, kind, dtype, backend }); });
  }
}
