import { test } from 'node:test';
import assert from 'node:assert/strict';
import { splitText, toChunks } from '../src/documents';
import { validateVector, MODEL, median, validCollection } from '../src/shared';
import { qualityMetrics } from '../src/evaluation';
test('overlapping chunks terminate and preserve all non-whitespace content', () => {
  const source = 'abcdefghijklmnopqrstuvwxyz';
  assert.deepEqual(splitText(source, 10, 3), ['abcdefghij', 'hijklmnopq', 'opqrstuvwx', 'vwxyz']);
  assert.deepEqual(splitText('  \r\n '), []);
  assert.throws(() => splitText(source, 10, 10));
});
test('repeat imports have stable IDs; changed content or source has different IDs', async () => {
  const first = await toChunks('same document', 'source.md');
  assert.deepEqual(first, await toChunks('same document', 'source.md'));
  assert.notEqual(first[0].id, (await toChunks('new document', 'source.md'))[0].id);
  assert.notEqual(first[0].id, (await toChunks('same document', 'another.md'))[0].id);
});
test('invalid vectors cannot reach seekdb', () => {
  assert.equal(validateVector(Array(MODEL.dimension).fill(0.1)), true);
  assert.equal(validateVector(Array(383).fill(0.1)), false);
  assert.equal(validateVector(Array(384).fill(0)), false);
  assert.equal(validateVector([NaN, ...Array(383).fill(1)]), false);
  assert.equal(validCollection('notes; DROP TABLE x'), false);
});
test('quality counts distinct relevant sources and penalizes ranking errors', () => {
  assert.deepEqual(qualityMetrics(['a','a','b'], ['a','b']), { recall: 1, ndcg: 1 });
  const partial = qualityMetrics(['wrong','a'], ['a','b']);
  assert.equal(partial.recall, 0.5); assert.ok(partial.ndcg < 0.5);
  assert.equal(median([5, 1, 3, 9]), 4); assert.equal(median([]), null);
});
