// Temporary probe: how to make Chinese retrieval run inside seekdb.
// node probe-fulltext.ts
import { SeekdbClient } from 'seekdb';

const client = new SeekdbClient({
  host: '127.0.0.1', port: 2881, user: 'root', password: '', database: 'test',
});
const say = (label: string, rows: unknown) =>
  console.log(`--- ${label}:`, JSON.stringify(rows).slice(0, 500));

await client.execute('CREATE DATABASE IF NOT EXISTS researchloop');
await client.execute("DELETE FROM researchloop.rl_chunks WHERE workspace_id='probe2'");
try { await client.execute('DROP TABLE researchloop.rl_ft_probe'); } catch { /* first run */ }
await client.execute(
  'CREATE TABLE researchloop.rl_ft_probe (id varchar(64) PRIMARY KEY, content text NOT NULL, ' +
    "FULLTEXT INDEX ft_probe(content) WITH PARSER ngram)",
);
for (const [id, text] of [
  ['p1', '复现实验时必须固定依赖版本与随机种子，否则结果无法对齐。'],
  ['p2', '阅读论文先记录问题与结论，再摘录证据段落并注明页码。'],
] as [string, string][]) {
  await client.execute('INSERT INTO researchloop.rl_ft_probe (id, content) VALUES (?,?)', [id, text]);
}
for (const wait of [0, 3000]) {
  if (wait) await new Promise(r => setTimeout(r, wait));
  try {
    say(`MATCH ngram after ${wait}ms`, await client.execute(
      "SELECT id, MATCH(content) AGAINST('实验 版本') AS score FROM researchloop.rl_ft_probe " +
        "WHERE MATCH(content) AGAINST('实验 版本') ORDER BY score DESC",
    ));
  } catch (error) { console.log('FAIL MATCH ngram:', (error as Error).message.slice(0, 200)); }
}
try {
  say('MATCH default parser space', await client.execute(
    "SELECT id, MATCH(content) AGAINST('复现') FROM researchloop.rl_chunks WHERE MATCH(content) AGAINST('复现')",
  ));
} catch (error) { console.log('FAIL space:', (error as Error).message.slice(0, 200)); }
try {
  say('LIKE based retrieval ranked in SQL', await client.execute(
    "SELECT id, source_name, chunk_no, " +
      "((content LIKE '%实验%') + (content LIKE '%复现%') + (content LIKE '%版本%')) AS hits " +
      "FROM researchloop.rl_chunks WHERE workspace_id='probe' AND " +
      "(content LIKE '%实验%' OR content LIKE '%复现%' OR content LIKE '%版本%') " +
      'ORDER BY hits DESC LIMIT 5',
  ));
} catch (error) { console.log('FAIL like:', (error as Error).message.slice(0, 200)); }
await client.close();
