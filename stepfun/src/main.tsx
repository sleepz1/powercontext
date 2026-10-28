import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { EmbeddingEngine } from './embedding';
import { api, type Target } from './api';
import { toChunks } from './documents';
import { benchmark } from './benchmark';
import { MODEL, median, validCollection, type Precision, type BackendPreference, type InferenceInfo, type Measurement, type SearchHit } from './shared';
import './style.css';

const namespaceKey = 'localfolio.namespace';
let namespace = localStorage.getItem(namespaceKey);
if (!namespace || !/^[a-f0-9]{24}$/.test(namespace)) {
  namespace = Array.from(crypto.getRandomValues(new Uint8Array(12)), x => x.toString(16).padStart(2, '0')).join('');
  localStorage.setItem(namespaceKey, namespace);
}
const ns = namespace;
const initialCollections = (() => { try { const c = JSON.parse(localStorage.getItem(`localfolio.collections.${ns}`) ?? '["notes"]'); return Array.isArray(c) && c.length && c.every(validCollection) ? c : ['notes']; } catch { return ['notes']; } })();
const engine = new EmbeddingEngine();
const fmt = (ms: number | null) => ms === null ? '—' : ms < 1000 ? `${ms.toFixed(0)} ms` : `${(ms / 1000).toFixed(2)} s`;
function download(name: string, value: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: 'application/json' }));
  const a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url);
}
function App() {
  const [collections, setCollections] = useState<string[]>(initialCollections);
  const [collection, setCollection] = useState(initialCollections[0]);
  const [newName, setNewName] = useState('');
  const [dtype, setDtype] = useState<Precision>('q8');
  const [backend, setBackend] = useState<BackendPreference>(new URLSearchParams(location.search).get('backend') === 'wasm' ? 'wasm' : 'auto');
  const [batch, setBatch] = useState(1);
  const [health, setHealth] = useState('正在连接');
  const [count, setCount] = useState(0);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('导入一份笔记，或使用示例资料开始。');
  const [info, setInfo] = useState<InferenceInfo | null>(null);
  const [error, setError] = useState('');
  const [query, setQuery] = useState('');
  const [hits, setHits] = useState<SearchHit[] | null>(null);
  const [metrics, setMetrics] = useState<Measurement[]>([]);
  const [report, setReport] = useState<any>(null);
  const [tab, setTab] = useState<'library' | 'performance'>('library');
  const [renderLatency, setRenderLatency] = useState<number | null>(null);
  const generation = useRef(0);
  const snapshot = useRef<any>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const target: Target = { namespace: ns, collection, dtype };
  const add = (stage: string, ms: number, extra: Partial<Measurement> = {}) => setMetrics(prev => [...prev, { at: new Date().toISOString(), stage, ms, ...extra }]);
  useEffect(() => {
    engine.onProgress = setStatus;
    api('health').then(() => setHealth('seekdb 已连接')).catch(e => { setHealth('seekdb 未连接'); setError(e.message); });
  }, []);
  useEffect(() => {
    const current = ++generation.current;
    setHits(null); setCount(0); setError(''); setBusy(true);
    api('collections', { namespace: ns, collection, dtype }).then(r => {
      if (generation.current === current) { setCount(r.count); setHealth('seekdb 已连接'); setStatus(`已打开 ${collection} · ${dtype}，${r.count} 个分块。`); }
    }).catch(e => { if (generation.current === current) setError(e.message); })
      .finally(() => { if (generation.current === current) setBusy(false); });
  }, [collection, dtype]);
  useEffect(() => { snapshot.current = { metrics, report, info, count, collection, dtype, hits }; }, [metrics, report, info, count, collection, dtype, hits]);
  useEffect(() => {
    (window as any).localfolio = { snapshot: () => snapshot.current, benchmark: (selected?: any) => benchmark(ns, setStatus, selected) };
  }, []);
  async function importDocuments(documents: { source: string; text: string }[]) {
    setBusy(true); setError(''); setHits(null); const current = generation.current;
    try {
      const chunks = (await Promise.all(documents.map(x => toChunks(x.text, x.source)))).flat();
      if (!chunks.length || chunks.length > 1000) throw new Error('请导入 1–1000 个分块的文本文档。');
      const started = performance.now();
      const loaded = await engine.run([], 'passage', dtype, backend); setInfo(loaded.info);
      add('model_load_or_reuse', performance.now() - started, { device: loaded.info.device, dtype });
      // Embed in configurable micro-batches; commit and refresh each 64-record write batch.
      for (let offset = 0; offset < chunks.length; offset += 64) {
        const records = [];
        for (let j = offset; j < Math.min(offset + 64, chunks.length); j += batch) {
          const group = chunks.slice(j, Math.min(j + batch, offset + 64, chunks.length));
          setStatus(`本地向量化 ${Math.min(j + group.length, chunks.length)} / ${chunks.length}`);
          const embedded = await engine.run(group.map(x => x.text), 'passage', dtype, backend); setInfo(embedded.info);
          add('document_embedding', embedded.inferenceMs, { count: group.length, dtype, batch, device: embedded.info.device });
          records.push(...group.map((x, i) => ({ ...x, embedding: embedded.vectors[i] })));
        }
        setStatus('写入 seekdb 并刷新索引…');
        const result = await api('import', { ...target, records });
        if (generation.current !== current) return;
        setCount(result.count); add('database_write', result.writeMs, { count: records.length }); add('index_refresh', result.refreshMs);
      }
      setStatus(`导入完成，${chunks.length} 个分块已写入并刷新。可开始检索。`);
    } catch (e) { setError(String(e)); setStatus('导入未完成；已提交的批次保留，可重试或刷新索引。'); }
    finally { setBusy(false); }
  }
  async function sample() { try { await importDocuments(await (await fetch('/sample.json')).json()); } catch (e) { setError(String(e)); } }
  async function files(list: FileList | null) {
    if (!list?.length) return;
    try {
      const items = [];
      for (const file of Array.from(list)) {
        if (!/\.(txt|md)$/i.test(file.name) || file.size > 2 * 1024 * 1024) throw new Error('仅支持每份不超过 2 MB 的 .txt / .md 文本');
        items.push({ source: file.name, text: await file.text() });
      }
      await importDocuments(items);
    } catch (e) { setError(String(e)); }
    if (fileInput.current) fileInput.current.value = '';
  }
  async function search(event: React.FormEvent) {
    event.preventDefault(); if (!query.trim()) return;
    setBusy(true); setError(''); setHits(null); setRenderLatency(null); const current = generation.current, start = performance.now();
    try {
      const embedded = await engine.run([query.trim()], 'query', dtype, backend); setInfo(embedded.info);
      add('query_embedding', embedded.inferenceMs, { dtype, device: embedded.info.device });
      const result = await api('search', { ...target, query: query.trim(), vector: embedded.vectors[0], limit: 5 });
      if (generation.current !== current) return;
      setHits(result.hits); add('database_search', result.searchMs);
      // Two animation frames include the UI commit and first paint in interactive latency.
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const ms = performance.now() - start; setRenderLatency(ms); add('query_to_paint', ms);
      }));
      setStatus(`已完成数据库混合检索，返回 ${result.hits.length} 个结果。`);
    } catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  async function refresh() {
    setBusy(true); setError(''); try { const r = await api('refresh', target); setCount(r.count); add('index_refresh', r.refreshMs); setStatus('索引刷新完成。'); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  function createCollection() {
    const name = newName.trim(); if (!validCollection(name)) { setError('集合名以小写字母开头，可用小写字母、数字、下划线，最长 31 字符'); return; }
    const next = [...new Set([...collections, name])]; setCollections(next); localStorage.setItem(`localfolio.collections.${ns}`, JSON.stringify(next)); setCollection(name); setNewName('');
  }
  async function measure() {
    setBusy(true); setError(''); setReport(null);
    try { setReport(await benchmark(ns, setStatus)); setStatus('四组对照完成。可导出原始数据，核对实际后端和质量。'); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  }
  const latestSearch = median(metrics.filter(x => x.stage === 'database_search').map(x => x.ms));
  return <div className="shell">
    <aside className="sidebar">
      <a className="brand" href="/"><span className="logo">知</span><span>知页<small>LOCALFOLIO</small></span></a>
      <div className="workspace-label">个人工作台 <span>LOCAL</span></div>
      <nav><button className={tab === 'library' ? 'nav active' : 'nav'} onClick={() => setTab('library')}>▤ <span>我的知识库</span><b>{collections.length}</b></button>
        <button className={tab === 'performance' ? 'nav active' : 'nav'} onClick={() => setTab('performance')}>◷ <span>性能与实验</span></button></nav>
      <section className="collection-list"><h3>知识集合</h3>{collections.map(name => <button disabled={busy} className={collection === name ? 'collection selected' : 'collection'} key={name} onClick={() => { setCollection(name); setTab('library'); }}>▧ <span>{name}</span>{collection === name && <i/>}</button>)}
        <div className="new-collection"><input aria-label="新集合名称" value={newName} placeholder="新集合（英文名）" disabled={busy} onChange={e => setNewName(e.target.value)}/><button aria-label="创建集合" disabled={busy} onClick={createCollection}>＋</button></div>
      </section>
      <div className="local-card"><span className="local-icon">⌘</span><strong>向量计算，留在本机</strong><p>文档和查询由浏览器处理。文本与向量写入你配置的本地 seekdb。</p></div>
      <div className="sidebar-footer"><span className={health.includes('已连接') ? 'dot' : 'dot offline'}/>{health}<small>seekdb-js 1.4.0</small></div>
    </aside>
    <main>
      <header><span>工作台 <b>/</b> {tab === 'library' ? '我的知识库' : '性能与实验'}</span><div className="header-right"><span className="chip">本地优先</span><span className="avatar">我</span></div></header>
      <div className="page">
        <div className="page-title"><div><div className="eyebrow">YOUR IDEAS, WITH CONTEXT</div><h1>{tab === 'library' ? '让知识，重新连接。' : '每一次优化，都有依据。'}</h1><p>{tab === 'library' ? '整理散落的笔记和研究资料，用自己的话找到需要的内容。' : '固定语料、模型版本与设备，比较量化、批处理和推理后端。'}</p></div><span className="page-mark">✳</span></div>
        <div className="stats"><div><span>当前集合的分块</span><strong data-testid="chunk-count">{count.toString().padStart(2, '0')}<em>chunks</em></strong></div><div><span>本地推理后端</span><strong>{info?.device === 'webgpu' ? 'WebGPU' : info?.device === 'wasm' ? 'WASM' : '待加载'}<em>{dtype === 'q8' ? 'INT8' : 'FP32'}</em></strong></div><div><span>数据库检索中位耗时</span><strong>{fmt(latestSearch)}<em>seekdb</em></strong></div></div>
        <div className="settings"><label>模型精度<select aria-label="模型精度" disabled={busy} value={dtype} onChange={e => setDtype(e.target.value as Precision)}><option value="q8">INT8 · 量化模型</option><option value="fp32">FP32 · 对照基线</option></select></label><label>推理后端<select aria-label="推理后端" disabled={busy} value={backend} onChange={e => { setBackend(e.target.value as BackendPreference); setInfo(null); }}><option value="auto">优先 WebGPU · 自动降级</option><option value="wasm">强制 WASM · 验证降级</option></select></label><label>批大小<select aria-label="批大小" disabled={busy} value={batch} onChange={e => setBatch(Number(e.target.value))}>{[1, 4, 8, 16].map(n => <option key={n}>{n}</option>)}</select></label></div>
        {info && <p className="backend-note" data-testid="backend-note">● {info.reason} · {MODEL.id} · 384 维</p>}
        {error && <div className="error" role="alert">{error}</div>}
        {tab === 'library' ? <>
          <section className="panel import-panel"><div className="section-heading"><div><h2>把资料放进来 <span>01</span></h2><p>支持 TXT、Markdown；连续导入保留已有内容。</p></div><button className="text-button" disabled={busy} onClick={sample}>试用 12 份示例资料 ↗</button></div>
            <input ref={fileInput} type="file" accept=".txt,.md" multiple hidden data-testid="file-input" onChange={e => void files(e.target.files)}/>
            <button className="dropzone" disabled={busy} onClick={() => fileInput.current?.click()}><span className="upload-icon">↥</span><strong>选择你想整理的文档</strong><span>TXT / Markdown · 每份最多 2 MB</span><span className="pill-button">选择文件 ＋</span></button>
            <div className="import-footer"><span className={busy ? 'spinner' : 'dot'}/><span role="status">{status}</span><button disabled={busy} className="text-button" onClick={refresh}>刷新索引 ↻</button></div>
          </section>
          <section className="panel search-panel"><div className="section-heading"><div><h2>从一个问题开始 <span>02</span></h2><p>语义理解 × 全文关键词，在 seekdb 中合并排序。</p></div><span className="subtle-chip">混合检索</span></div>
            <form onSubmit={search}><div className="searchbox"><span>⌕</span><input aria-label="检索问题" placeholder="比如：如何保证机器学习实验可以复现？" value={query} onChange={e => setQuery(e.target.value)}/><button type="submit" disabled={busy || !count || !query.trim()}>检索 <span>↗</span></button></div></form>
            <div className="suggestions">试着问{['浏览器没有 WebGPU 时怎么办？', '模型量化后的质量怎样评估？'].map(q => <button key={q} disabled={busy} onClick={() => setQuery(q)}>{q} ↗</button>)}</div>
            {hits === null ? <div className="empty"><span>⌕</span><h3>答案，藏在你读过的资料里</h3><p>导入资料后开始搜索，结果会保留原文与出处。</p></div> : <div className="results"><div className="results-label">找到 {hits.length} 条相关内容 <span>{renderLatency !== null && `查询到展示 ${fmt(renderLatency)}`}</span></div>{hits.length === 0 && <p>当前集合没有检索结果，请检查资料内容或换一个问题。</p>}{hits.map((hit, i) => <article className="result" key={hit.id}><div className="result-heading"><span className="rank">{i + 1}</span><h3>{hit.source}</h3><span className="subtle-chip">原文片段</span></div><p>{hit.text}</p><small>来源：{hit.source} · {hit.id.slice(0, 12)}</small></article>)}</div>}
          </section>
        </> : <section className="panel performance-panel"><div className="section-heading"><div><h2>固定条件对照实验</h2><p>FP32/WASM、INT8/WASM（batch 1/8）、INT8/优先 WebGPU。每组重复三轮。</p></div><button className="primary" disabled={busy} onClick={measure}>运行完整对照</button></div>
          <p className="notice">首次运行需加载两个精度的模型，可能耗时数分钟。实际后端和降级原因会随数据导出。性能并不保证提升，以测量结果为准。</p><p role="status">{status}</p>
          {report && <><div className="table-wrap"><table><thead><tr><th>配置</th><th>实际后端</th><th>分块/秒</th><th>检索中位数</th><th>端到端中位数</th><th>Recall@5</th><th>nDCG@5</th></tr></thead><tbody>{report.runs.map((r: any) => <tr key={r.config.label}><td>{r.config.label}</td><td>{r.actualBackend.device}</td><td>{r.documentsPerSecond.toFixed(2)}</td><td>{fmt(r.medianSearchMs)}</td><td>{fmt(r.medianEndToEndMs)}</td><td>{r.recallAt5.toFixed(3)}</td><td>{r.ndcgAt5.toFixed(3)}</td></tr>)}</tbody></table></div><button className="primary" onClick={() => download('localfolio-benchmark.json', report)}>导出完整对照数据 ↓</button></>}
          <div className="divider"/><h3>交互原始计时</h3><p>记录模型加载/复用、文档向量化、写入、刷新、查询向量化、数据库检索和查询到绘制。共 {metrics.length} 条。</p><button className="secondary" onClick={() => download('localfolio-interaction.json', { model: MODEL, userAgent: navigator.userAgent, info, metrics })}>导出本次交互计时 ↓</button>
        </section>}
        <footer><span>知页 LOCALFOLIO</span><span>浏览器向量化 · 本地 seekdb 存储与检索</span><span>{collection} / {dtype}</span></footer>
      </div>
    </main>
  </div>;
}
createRoot(document.getElementById('root')!).render(<App/>);
