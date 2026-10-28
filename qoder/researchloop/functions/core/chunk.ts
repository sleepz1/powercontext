import { LIMITS } from './domain.ts';
import { InputError } from './validate.ts';

export const CHUNK_SIZE = 500;
export const CHUNK_OVERLAP = 60;

export function chunkText(text: string): string[] {
  const normalized = text.replace(/\r\n?/g, '\n').trim();
  if (!normalized) return [];
  if (normalized.length <= CHUNK_SIZE) return [normalized];

  const step = CHUNK_SIZE - CHUNK_OVERLAP;
  const required = Math.ceil((normalized.length - CHUNK_SIZE) / step) + 1;
  if (required > LIMITS.maxChunksPerSource) {
    throw new InputError(
      'material_too_large',
      `资料过长：按 ${CHUNK_SIZE} 字符窗口、${CHUNK_OVERLAP} 字符重叠需要 ${required} 个分块，超过单次上限 ${LIMITS.maxChunksPerSource}。请拆成多份资料导入，未导入的内容不会被静默丢弃。`,
    );
  }

  const pieces: string[] = [];
  for (let start = 0; start < normalized.length; start += step) {
    const slice = normalized.slice(start, start + CHUNK_SIZE).trim();
    if (slice) pieces.push(slice);
    if (start + CHUNK_SIZE >= normalized.length) break;
  }
  return pieces;
}

async function sha256Hex(input: string): Promise<string> {
  const bytes = new TextEncoder().encode(input);
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
}

export function chunkFingerprint(workspaceId: string, sourceName: string, chunkNo: number, content: string): string {
  return `${workspaceId}|${sourceName}|${chunkNo}|${content}`;
}

export async function chunkIdOf(fingerprint: string): Promise<string> {
  return sha256Hex(fingerprint);
}

export async function idFromFingerprint(fingerprint: string): Promise<string> {
  return sha256Hex(fingerprint);
}

export function provenance(chunk: { sourceName: string; chunkNo: number; revision?: number }): string {
  const revision = chunk.revision === undefined ? '' : ` · 版本 ${chunk.revision}`;
  return `${chunk.sourceName} · 第 ${chunk.chunkNo + 1} 块${revision}`;
}
