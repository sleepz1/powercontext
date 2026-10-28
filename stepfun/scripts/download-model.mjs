import { mkdir, writeFile, rename, readFile, stat } from 'node:fs/promises';
import { createWriteStream, createReadStream } from 'node:fs';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { createHash } from 'node:crypto';
const id = 'Xenova/multilingual-e5-small';
const revision = '761b726dd34fb83930e26aab4e9ac3899aa1fa78';
const origin = process.env.MODEL_SOURCE || 'https://hf-mirror.com';
const modelDir = `public/models/${id}`;
const files = ['config.json', 'tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json', 'onnx/model.onnx', 'onnx/model_quantized.onnx'];
await mkdir(`${modelDir}/onnx`, { recursive: true });
async function sha256(path) { const hash = createHash('sha256'); for await (const part of createReadStream(path)) hash.update(part); return hash.digest('hex'); }
let old; try { old = JSON.parse(await readFile('public/models/manifest.json', 'utf8')); } catch {}
const entries = [];
for (const file of files) {
  const dest = `${modelDir}/${file}`;
  const previous = old?.files?.find(x => x.file === file);
  let reusable = false;
  try { reusable = old.revision === revision && previous?.sha256 === await sha256(dest); } catch {}
  if (!reusable) {
    const url = `${origin}/${id}/resolve/${revision}/${file}`;
    console.log(`下载 ${file}`);
    const response = await fetch(url, { signal: AbortSignal.timeout(600000) });
    if (!response.ok || !response.body) throw new Error(`${response.status}: ${url}`);
    await pipeline(Readable.fromWeb(response.body), createWriteStream(`${dest}.part`));
    await rename(`${dest}.part`, dest);
  }
  const bytes = (await stat(dest)).size;
  entries.push({ file, bytes, sha256: await sha256(dest) });
  console.log(`${file}: ${bytes} bytes`);
}
const fp32 = entries.find(x => x.file === 'onnx/model.onnx').bytes;
const int8 = entries.find(x => x.file === 'onnx/model_quantized.onnx').bytes;
const manifest = { id, revision, source: origin, measuredAt: new Date().toISOString(), files: entries,
  fp32Bytes: fp32, int8Bytes: int8, compressionRatio: fp32 / int8,
  accounting: 'ONNX 权重文件大小；公共 tokenizer/config 文件单独列出，精度共享' };
await writeFile('public/models/manifest.json', JSON.stringify(manifest, null, 2));
console.log(`模型已就绪，ONNX 文件压缩比 ${(fp32 / int8).toFixed(3)}×`);
