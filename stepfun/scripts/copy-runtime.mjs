import { createRequire } from 'node:module';
import { dirname, join } from 'node:path';
import { mkdir, readdir, copyFile } from 'node:fs/promises';
const require = createRequire(import.meta.url);
const entry = require.resolve('onnxruntime-web');
const dist = dirname(entry);
await mkdir('public/ort', { recursive: true });
let copied = 0;
for (const file of await readdir(dist)) {
  if (/\.wasm$|\.mjs$/.test(file)) { await copyFile(join(dist, file), join('public/ort', file)); copied++; }
}
if (!copied) throw new Error(`未找到 ONNX Web runtime: ${dist}`);
console.log(`已复制 ${copied} 个本地 ONNX 运行时文件`);
