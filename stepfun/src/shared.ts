export const MODEL = {
  id: 'Xenova/multilingual-e5-small',
  revision: '761b726dd34fb83930e26aab4e9ac3899aa1fa78',
  dimension: 384,
  pooling: 'mean', normalize: true,
} as const;
export type Precision = 'q8' | 'fp32';
export type BackendPreference = 'auto' | 'wasm';
export interface DocumentChunk { id: string; text: string; source: string; chunk: number }
export interface SearchHit { id: string; text: string; source: string; distance: number | null }
export interface InferenceInfo {
  device: 'webgpu' | 'wasm'; dtype: Precision; reason: string;
  loadMs: number; model: string; revision: string;
  consistency?: { minimumCosine: number; threshold: number; samples: number };
}
export interface Measurement {
  at: string; stage: string; ms: number; count?: number;
  device?: string; dtype?: string; batch?: number; detail?: string;
}
export const namespacePattern = /^[a-f0-9]{24}$/;
export function validCollection(name: unknown): name is string {
  return typeof name === 'string' && /^[a-z][a-z0-9_]{0,30}$/.test(name);
}
export function validateVector(v: unknown): v is number[] {
  return Array.isArray(v) && v.length === MODEL.dimension && v.every(x => typeof x === 'number' && Number.isFinite(x))
    && v.some(x => x !== 0);
}
export function median(values: number[]): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b), m = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[m] : (sorted[m - 1] + sorted[m]) / 2;
}
