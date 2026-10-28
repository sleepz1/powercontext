import { createServer } from 'node:http';
import { Readable } from 'node:stream';
import type { IncomingMessage, ServerResponse } from 'node:http';
import { SeekdbClient } from 'seekdb';
import { application } from '../functions/core/api.ts';
import { ensureSeekdbSchema, seekdbStore } from './seekdb-store.ts';

const host = process.env.RESEARCHLOOP_HOST ?? '127.0.0.1';
const port = Number(process.env.RESEARCHLOOP_PORT ?? 8788);

const client = new SeekdbClient({
  host: process.env.SEEKDB_HOST ?? '127.0.0.1',
  port: Number(process.env.SEEKDB_PORT ?? 2881),
  user: process.env.SEEKDB_USER ?? 'root',
  password: process.env.SEEKDB_PASSWORD ?? '',
  database: process.env.SEEKDB_DATABASE ?? 'test',
});

const store = seekdbStore(client);
const handle = application(store);

const toWebRequest = (request: IncomingMessage): Request => {
  const url = `http://${host}:${port}${request.url ?? '/'}`;
  const headers = new Headers();
  for (const [key, value] of Object.entries(request.headers)) {
    if (typeof value === 'string') headers.append(key, value);
    else if (Array.isArray(value)) for (const item of value) headers.append(key, item);
  }
  const method = request.method ?? 'GET';
  return new Request(url, {
    method,
    headers,
    body: method === 'GET' || method === 'HEAD' ? null : Readable.toWeb(request) as ReadableStream,
    duplex: 'half',
  } as RequestInit);
};

const server = createServer((request: IncomingMessage, response: ServerResponse) => {
  void (async () => {
    try {
      const result = await handle(toWebRequest(request));
      response.writeHead(result.status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store', ...Object.fromEntries(result.headers) });
      response.end(Buffer.from(await result.arrayBuffer()));
    } catch (error) {
      response.writeHead(500, { 'content-type': 'application/json; charset=utf-8' });
      response.end(JSON.stringify({ ok: false, error: 'server_error', message: error instanceof Error ? error.message : 'unknown' }));
    }
  })();
});

const applied = await ensureSeekdbSchema(client);
console.log('seekdb schema ready: researchloop.rl_sources / rl_material_chunks / rl_actions');
if (applied.length) console.log(`补齐版本管理列：${applied.join(', ')}`);

server.listen(port, host, () => {
  console.log(`研途核心服务（seekdb 后端）监听 http://${host}:${port}`);
});

const shutdown = () => {
  server.close(() => { void client.close().finally(() => process.exit(0)); });
};
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
