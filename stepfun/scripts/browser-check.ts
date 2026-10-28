import { chromium } from 'playwright';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
const base = process.env.APP_URL ?? 'http://127.0.0.1:5173';
await mkdir('test-results', { recursive: true });
const browser = await chromium.launch({ channel: 'msedge', headless: true });
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } });
const page = await context.newPage();
const errors: string[] = [], external: string[] = [];
page.on('pageerror', e => errors.push(e.message));
context.on('request', r => { if (/^https?:/.test(r.url()) && !r.url().startsWith(base) && !r.url().startsWith('http://127.0.0.1:8787')) external.push(r.url()); });
page.on('console', m => { if (m.type() === 'error') console.log('browser:', m.text().slice(0, 500)); });
async function ready() { await page.getByRole('button', { name: '试用 12 份示例资料' }).waitFor(); await page.waitForFunction(() => !(document.querySelector('.text-button') as HTMLButtonElement)?.disabled, null, { timeout: 180000 }); }
async function finished() { await page.waitForFunction(() => !(document.querySelector('.dropzone') as HTMLButtonElement)?.disabled, null, { timeout: 600000 }); const error = await page.getByRole('alert').allTextContents(); assert.deepEqual(error, []); }
async function snapshot() { return page.evaluate(() => (window as any).localfolio.snapshot()); }
async function imported(count: number) {
  await page.waitForFunction(n => (window as any).localfolio.snapshot()?.count === n || !!document.querySelector('[role=alert]'), count, { timeout: 600000 });
  await finished(); assert.equal((await snapshot()).count, count);
}
try {
  await page.goto(`${base}/?backend=wasm`); await ready();
  await page.getByRole('button', { name: '试用 12 份示例资料' }).click(); await imported(12);
  const first = await snapshot(); assert.equal(first.count, 12); assert.equal(first.info.device, 'wasm');
  const repeatedWrite = page.waitForResponse(r => r.url().endsWith('/api/import'), { timeout: 600000 });
  await page.getByRole('button', { name: '试用 12 份示例资料' }).click(); await repeatedWrite; await finished();
  assert.equal((await snapshot()).count, 12);
  await page.getByTestId('file-input').setInputFiles({ name: '增量验证.md', mimeType: 'text/markdown', buffer: Buffer.from('星河项目验收日为十一月二十日，负责人是林同学，新增资料需立即检索。') });
  await imported(13);
  await page.getByLabel('检索问题').fill('星河项目验收负责人是谁？');
  await page.getByRole('button', { name: '检索 ↗', exact: true }).click(); await finished();
  const searched = await snapshot(); assert.ok(searched.hits.some((h: any) => h.source === '增量验证.md'));
  await page.screenshot({ path: 'test-results/desktop.png', fullPage: true });
  await page.getByLabel('新集合名称').fill('isolated'); await page.getByLabel('创建集合').click(); await finished();
  await page.waitForFunction(() => { const s = (window as any).localfolio.snapshot(); return s?.collection === 'isolated' && s.count === 0; });
  await finished();
  assert.equal((await snapshot()).count, 0);
  await page.getByRole('button', { name: '▧ notes', exact: true }).click();
  await page.waitForFunction(() => { const s = (window as any).localfolio.snapshot(); return s?.collection === 'notes' && s.count === 13; });
  await finished();
  await page.getByLabel('推理后端').selectOption('auto');
  await page.getByLabel('检索问题').fill('模型量化后的检索质量怎样评估？');
  await page.getByRole('button', { name: '检索 ↗', exact: true }).click(); await finished();
  const auto = await snapshot(); assert.ok(['wasm', 'webgpu'].includes(auto.info.device));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: 'test-results/mobile.png', fullPage: true });
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1));
  assert.deepEqual(errors, []); assert.deepEqual(external, []);
  await writeFile('test-results/interaction.json', JSON.stringify({ at: new Date().toISOString(), first, searched, auto, errors, external }, null, 2));
  await mkdir('results', { recursive: true });
  await writeFile('results/verification.json', JSON.stringify({ at: new Date().toISOString(), appUrl: base,
    checks: ['real browser WASM embedding', 'repeat import: 12 -> 12', 'incremental import: 12 -> 13',
      'new document appears in hybrid query', 'empty isolated collection', 'auto backend with numeric guard',
      '390px responsive viewport without horizontal overflow', 'no external HTTP requests'],
    firstInitializationInFreshBrowserContext: { info: first.info, measurements: first.metrics },
    warmedInteractiveQuery: { measurements: searched.metrics, topSource: searched.hits[0]?.source },
    autoBackend: auto.info, errors, externalRequests: external,
    note: 'Fresh isolated browser context; server files and OS caches may already be warm. Initialization is not an internet download benchmark.' }, null, 2));
  console.log('PASS: real browser WASM embedding, incremental write, repeat import, hybrid query, isolated collection, auto backend, responsive layout, no external HTTP requests');
  if (process.argv.includes('--benchmark')) {
    console.log('Running four real benchmark profiles; this may take several minutes.');
    const report = await page.evaluate(async () => (window as any).localfolio.benchmark());
    await mkdir('results', { recursive: true });
    await writeFile('results/benchmark.json', JSON.stringify(report, null, 2));
    console.log(JSON.stringify(report.runs.map((r: any) => ({ label: r.config.label, actual: r.actualBackend.device, docsPerSec: r.documentsPerSecond, e2eMs: r.medianEndToEndMs, recall: r.recallAt5, ndcg: r.ndcgAt5 })), null, 2));
  }
} finally { await browser.close(); }
