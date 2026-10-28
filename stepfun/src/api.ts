import type { Precision } from './shared';
export interface Target { namespace: string; collection: string; dtype: Precision }
export async function api<T = any>(url: string, payload?: unknown): Promise<T> {
  const response = await fetch(`/api/${url}`, payload === undefined ? undefined : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  const body = await response.json();
  if (!response.ok) throw new Error(body.error ?? `请求失败：${response.status}`);
  return body as T;
}
