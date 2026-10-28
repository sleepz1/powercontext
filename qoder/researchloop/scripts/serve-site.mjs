import './check-node.mjs';
import { createServer } from 'node:http';
import { extname, posix } from 'node:path';
import { createReadStream, statSync } from 'node:fs';

const root = new URL('../site/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1');
const host = process.env.SITE_HOST ?? '127.0.0.1';
const port = Number(process.env.SITE_PORT ?? 4174);

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
};

createServer((request, response) => {
  const { pathname } = new URL(request.url, `http://${host}:${port}`);
  const relative = posix.normalize(pathname === '/' ? '/index.html' : pathname).replace(/^\/+/, '');
  if (relative.includes('..') || /[^\w./-]/.test(relative)) {
    response.writeHead(400, { 'content-type': 'text/plain; charset=utf-8' });
    response.end('请求路径不被允许。');
    return;
  }
  const target = `${root}/${relative}`;
  let info;
  try {
    info = statSync(target);
  } catch {
    response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
    response.end('文件不存在。');
    return;
  }
  if (info.isDirectory()) {
    response.writeHead(403, { 'content-type': 'text/plain; charset=utf-8' });
    response.end('不提供目录列表。');
    return;
  }
  response.writeHead(200, {
    'content-type': TYPES[extname(target).toLowerCase()] ?? 'application/octet-stream',
    'content-length': String(info.size),
    'cache-control': 'no-store',
  });
  createReadStream(target).pipe(response);
}).listen(port, host, () => {
  console.log(`作品展示站本地预览：http://${host}:${port}`);
});
