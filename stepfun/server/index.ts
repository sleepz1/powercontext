import express from 'express';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { MODEL, validateVector } from '../src/shared';
import { client, target, serial, dbName, ensureCollection, records, importRecords, refresh, search } from './database';
const app = express();
app.disable('x-powered-by');
app.use((req, res, next) => {
  const origin = req.get('origin');
  if (origin && !['http://127.0.0.1:5173', 'http://localhost:5173', 'http://127.0.0.1:8787', 'http://localhost:8787'].includes(origin)) {
    res.status(403).json({ error: '仅允许本地应用访问' }); return;
  }
  next();
});
app.use(express.json({ limit: '12mb' }));
app.get('/api/health', async (_req, res) => {
  try { const version = await client.execute('SELECT VERSION() AS version'); res.json({ ok: true, version, model: MODEL }); }
  catch { res.status(503).json({ error: 'seekdb 未连接。请启动本地数据库并检查 SEEKDB_* 配置。' }); }
});
app.get('/api/model-manifest', async (_req, res) => {
  try { res.sendFile(path.resolve('public/models/manifest.json')); }
  catch { res.status(404).json({ error: '请先执行 npm run models 下载固定版本模型' }); }
});
app.post('/api/collections', async (req, res) => {
  const t = target(req.body);
  const result = await serial(dbName(t), async () => { const c = await ensureCollection(t); await c.refresh_index(); return { name: t.collection, count: await c.count() }; });
  res.json(result);
});
app.post('/api/import', async (req, res) => {
  const t = target(req.body), rows = records(req.body.records);
  res.json(await importRecords(t, rows));
});
app.post('/api/refresh', async (req, res) => { res.json(await refresh(target(req.body))); });
app.post('/api/search', async (req, res) => {
  const t = target(req.body), { query, vector, limit = 5 } = req.body;
  if (typeof query !== 'string' || !query.trim() || query.length > 1000 || !validateVector(vector) || !Number.isInteger(limit) || limit < 1 || limit > 20)
    throw new Error('检索文本、结果数或向量无效');
  res.json(await search(t, query, vector, limit));
});
app.use(express.static(fileURLToPath(new URL('../dist', import.meta.url))));
app.use(express.static(fileURLToPath(new URL('../public', import.meta.url))));
app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error(err.name, err.message);
  res.status(400).json({ error: err.message.slice(0, 500) });
});
app.listen(8787, '127.0.0.1', () => console.log('知页 API http://127.0.0.1:8787 (seekdb-js, no server embedding)'));
