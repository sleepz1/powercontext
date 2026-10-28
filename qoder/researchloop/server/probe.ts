// Temporary capability probe for the local seekdb instance. Run:
// node --experimental-strip-types dev/seekdb-probe.ts
import { SeekdbClient, Schema, FulltextIndexConfig } from 'seekdb';

const client = new SeekdbClient({
  host: process.env.SEEKDB_HOST ?? '127.0.0.1',
  port: Number(process.env.SEEKDB_PORT ?? 2881),
  user: process.env.SEEKDB_USER ?? 'root',
  password: process.env.SEEKDB_PASSWORD ?? '',
  database: process.env.SEEKDB_DATABASE ?? 'test',
});

const note = (label: string, ok: boolean, detail: unknown) => {
  console.log(`[${ok ? 'OK' : 'FAIL'}] ${label}`, typeof detail === 'string' ? detail : JSON.stringify(detail).slice(0, 400));
};

// 1. Raw SQL round trip.
try {
  const rows = await client.execute('SELECT 1 AS one');
  note('execute SELECT 1', true, rows);
} catch (error) { note('execute SELECT 1', false, (error as Error).message); }

// 2. Application tables in a dedicated database.
for (const sql of [
  'CREATE DATABASE IF NOT EXISTS researchloop',
  'CREATE TABLE IF NOT EXISTS researchloop.rl_actions (' +
    'id varchar(64) PRIMARY KEY, workspace_id varchar(64) NOT NULL, title varchar(300) NOT NULL, ' +
    'owner_name varchar(80) NOT NULL, due_date varchar(10) NOT NULL, status varchar(16) NOT NULL, ' +
    'ref_chunk_id varchar(64) NOT NULL, ref_source_name varchar(240) NOT NULL, ref_chunk_no int NOT NULL, ' +
    'created_at varchar(40) NOT NULL, updated_at varchar(40) NOT NULL, completed_at varchar(40) NULL)',
  'CREATE TABLE IF NOT EXISTS researchloop.rl_chunks (' +
    'id varchar(64) PRIMARY KEY, workspace_id varchar(64) NOT NULL, source_name varchar(240) NOT NULL, ' +
    'chunk_no int NOT NULL, content text NOT NULL, FULLTEXT INDEX ft_chunk(content))',
]) {
  try { await client.execute(sql); note('ddl', true, sql.slice(0, 60)); }
  catch (error) { note(`ddl: ${sql.slice(0, 40)}`, false, (error as Error).message); }
}

// 3. Chinese fulltext search inside the database.
try {
  await client.execute("DELETE FROM researchloop.rl_chunks WHERE workspace_id='probe'");
} catch (error) { note('probe cleanup', false, (error as Error).message); }
try {
  await client.execute(
    "INSERT INTO researchloop.rl_chunks (id, workspace_id, source_name, chunk_no, content) VALUES ('p1','probe','实验.md',0,?)",
    ['复现实验时必须固定依赖版本与随机种子，否则结果无法对齐。'],
  );
  await client.execute(
    "INSERT INTO researchloop.rl_chunks (id, workspace_id, source_name, chunk_no, content) VALUES ('p2','probe','论文阅读.md',1,?)",
    ['阅读论文先记录问题与结论，再摘录证据段落并注明页码。'],
  );
  const hit = await client.execute(
    "SELECT id, source_name, chunk_no, MATCH(content) AGAINST(?) AS score FROM researchloop.rl_chunks " +
      "WHERE MATCH(content) AGAINST('实验 复现 版本') ORDER BY score DESC LIMIT 5",
    ['实验 复现 版本'],
  );
  note('sql fulltext MATCH AGAINST', true, hit);
} catch (error) { note('sql fulltext MATCH AGAINST', false, (error as Error).message); }

// 4. Structured query used by the weekly report.
try {
  const joined = await client.execute(
    'SELECT a.id, a.title, a.status, c.source_name, c.chunk_no FROM researchloop.rl_actions a ' +
      'LEFT JOIN researchloop.rl_chunks c ON c.id = a.ref_chunk_id WHERE a.workspace_id=? LIMIT 5',
    ['probe'],
  );
  note('sql join actions->chunks', true, joined);
} catch (error) { note('sql join actions->chunks', false, (error as Error).message); }

// 5. Collection API without a vector index (fulltext only).
try {
  const exists = await client.hasCollection({ name: 'rl_probe' });
  if (exists) await client.deleteCollection('rl_probe');
  const collection = await client.createCollection({
    name: 'rl_probe',
    embeddingFunction: null,
    schema: new Schema({ fulltextIndex: new FulltextIndexConfig('ngram', { ngram_token_size: 2 }) }),
  });
  await collection.upsert({
    ids: ['c1'],
    documents: ['补齐实验依赖版本，保证第三方实验可以复现。'],
    metadatas: [{ source: '实验.md', chunk: 0 }],
  });
  await collection.refresh_index();
  const found = await collection.query({ queryTexts: ['怎样保证实验可以复现'], nResults: 3 });
  note('collection query without embeddings', true, {
    ids: found.ids, documents: found.documents, metadatas: found.metadatas,
  });
  const byId = await collection.getMaxTextLen?.();
  note('collection helper present', true, typeof byId);
} catch (error) { note('collection query without embeddings', false, (error as Error).message); }

await client.close();
