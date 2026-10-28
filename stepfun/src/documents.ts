import type { DocumentChunk } from './shared';
export function splitText(text: string, maxChars = 500, overlap = 60): string[] {
  if (!Number.isInteger(maxChars) || maxChars < 1 || !Number.isInteger(overlap) || overlap < 0 || overlap >= maxChars)
    throw new Error('分块参数无效');
  const clean = text.replace(/\r\n/g, '\n').trim();
  const chunks: string[] = [];
  for (let start = 0; start < clean.length; start += maxChars - overlap) {
    const chunk = clean.slice(start, start + maxChars).trim();
    if (chunk) chunks.push(chunk);
    if (start + maxChars >= clean.length) break;
  }
  return chunks;
}
export async function toChunks(text: string, source: string): Promise<DocumentChunk[]> {
  return Promise.all(splitText(text).map(async (part, chunk) => {
    const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(`${source}\0${chunk}\0${part}`));
    const id = Array.from(new Uint8Array(bytes), x => x.toString(16).padStart(2, '0')).join('');
    return { id, text: part, source, chunk };
  }));
}
