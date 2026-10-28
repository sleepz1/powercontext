// Real database plumbing check. Fixture vectors are NOT inference/quality evidence.
import assert from 'node:assert/strict';
import { randomBytes, createHash } from 'node:crypto';
const base = process.env.APP_API ?? 'http://127.0.0.1:8787/api';
async function request(route: string, data?: unknown) {
  const r = await fetch(`${base}/${route}`, data === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data),
  });
  const value = await r.json() as any;
  if (!r.ok) throw new Error(JSON.stringify(value));
  return value;
}
const target = { namespace: randomBytes(12).toString('hex'), collection: 'dbcheck', dtype: 'q8' };
const vector = Array.from({ length: 384 }, (_, i) => i === 0 ? 1 : 0);
function record(text: string) { return { id: createHash('sha256').update(text).digest('hex'), source: 'db-fixture.md', chunk: 0, text, embedding: vector }; }
console.log('health', await request('health'));
assert.equal((await request('collections', target)).count, 0);
const first = record('数据库增量索引刷新测试');
assert.equal((await request('import', { ...target, records: [first] })).count, 1);
assert.equal((await request('import', { ...target, records: [first] })).count, 1);
assert.equal((await request('import', { ...target, records: [record('新增文档应立即可检索')] })).count, 2);
const found = await request('search', { ...target, query: '新增文档', vector, limit: 5 });
assert.ok(found.hits.some((x: any) => x.text.includes('新增文档')));
const second = { ...target, collection: 'isolated' };
assert.equal((await request('collections', second)).count, 0);
assert.equal((await request('search', { ...second, query: '新增文档', vector })).hits.length, 0);
assert.equal((await request('collections', { ...target, dtype: 'fp32' })).count, 0);
const otherSession = { ...target, namespace: randomBytes(12).toString('hex') };
assert.equal((await request('collections', otherSession)).count, 0);
const invalid = await fetch(`${base}/import`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...target, records: [{ ...first, embedding: [1] }] }) });
assert.equal(invalid.status, 400);
console.log('PASS: real seekdb write / refresh / repeat import / incremental visibility / collection, precision and session isolation / invalid-vector rejection');
console.log('Retained test namespace (no automatic deletion):', target.namespace);
