import { useEffect, useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { api, describeError, sampleMaterials, type Health, type ReportOutput, type SearchOutput } from "./api";
import { STATUS_LABELS, type ActionRecord, ActionStatus, type ChunkRecord, type SourceRecord, type WorkspaceCounters } from "@/functions/core/domain.ts";
import { todayLabel } from "./format";

export interface Common {
  workspace: string;
  counters: WorkspaceCounters;
  sources: SourceRecord[];
  actions: ActionRecord[];
  reload: () => void;
  health: Health | null;
}

function Panel({ title, description, children, aside }: { title: string; description?: string; children: React.ReactNode; aside?: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-border bg-card p-4 shadow-xs sm:p-5">
      <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold tracking-tight sm:text-lg">{title}</h2>
          {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
        </div>
        {aside}
      </header>
      {children}
    </section>
  );
}

function Notice({ tone, children }: { tone: "error" | "empty" | "info"; children: React.ReactNode }) {
  const styles = tone === "error"
    ? "border-destructive/40 bg-destructive/5 text-destructive"
    : tone === "empty"
      ? "border-dashed border-border bg-muted/40 text-muted-foreground"
      : "border-border bg-muted/40 text-foreground";
  return <p role="status" className={`rounded-md border px-3 py-2 text-sm ${styles}`}>{children}</p>;
}

function Provenance({ chunk }: { chunk: { sourceName: string; chunkNo: number; revision?: number | null } }) {
  return (
    <p className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
      <Badge variant="secondary" className="rounded-sm font-normal">出处</Badge>
      <span className="font-medium text-foreground">{chunk.sourceName}</span>
      <span>· 第 {chunk.chunkNo + 1} 块</span>
      {chunk.revision ? <span>· 版本 {chunk.revision}</span> : null}
    </p>
  );
}

const SUGGESTIONS = ["怎样保证实验可以复现", "文文摘录为什么要带出处", "组会决定了哪些行动项", "中文全文检索需要哪种索引"];

export function Workbench({ workspace, reload }: Common) {
  const [query, setQuery] = useState(SUGGESTIONS[0]);
  const [result, setResult] = useState<SearchOutput | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const [draft, setDraft] = useState<ChunkRecord | null>(null);

  const run = async (text: string) => {
    if (!text.trim()) { setError("请输入检索问题。"); return; }
    setPending(true); setError(null);
    try {
      setResult(await api.search(workspace, text, 6));
    } catch (cause) {
      setError(describeError(cause));
      setResult(null);
    } finally {
      setPending(false);
    }
  };

  useEffect(() => { setResult(null); setError(null); setOpen(null); }, [workspace]);

  return (
    <div className="flex flex-col gap-4">
      <Panel
        title="带出处的资料检索"
        description="问题在数据服务里拆成检索词，由数据库完成匹配与排序；结果展示原文与出处，不生成没有来源的结论。"
      >
        <form
          className="flex flex-col gap-3 sm:flex-row"
          onSubmit={(event) => { event.preventDefault(); void run(query); }}
        >
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如：怎样保证实验可以复现"
            aria-label="检索问题"
            className="sm:flex-1"
          />
          <Button type="submit" disabled={pending}>{pending ? "检索中" : "检索"}</Button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          {SUGGESTIONS.map(item => (
            <Button key={item} type="button" variant="outline" size="sm" onClick={() => { setQuery(item); void run(item); }}>
              {item}
            </Button>
          ))}
        </div>
        {error ? <div className="mt-4"><Notice tone="error">{error} <Button variant="link" size="sm" className="h-auto p-0" onClick={() => void run(query)}>重试</Button></Notice></div> : null}
        {pending ? <div className="mt-4"><Notice tone="info">正在向数据服务请求结果…</Notice></div> : null}
        {result && !pending ? (
          <div className="mt-4 flex flex-col gap-3">
            <p className="text-xs text-muted-foreground">
              引擎：{result.engine}｜方式：{result.retrieval === "database-fulltext-ranked" ? "数据库内全文相关度排序" : "数据库侧关键词条件过滤"}｜用时 {result.tookMs} ms｜检索词 {result.terms.join(" / ")}
            </p>
            {result.hits.length === 0 ? (
              <Notice tone="empty">没有命中资料。可先在「资料库」导入内容，或换一个更具体的问题。</Notice>
            ) : result.hits.map(hit => (
              <article key={hit.chunk.id} className="rounded-md border border-border bg-background p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium">{hit.chunk.sourceName}</p>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    {hit.dbScore !== null ? <span>库内分值 {hit.dbScore.toFixed(4)}</span> : <span>命中 {hit.matched.length} 个检索词</span>}
                    <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(open === hit.chunk.id ? null : hit.chunk.id)}>
                      {open === hit.chunk.id ? "收起原文" : "回看原文"}
                    </Button>
                  </div>
                </div>
                <p className={`mt-2 whitespace-pre-wrap text-sm leading-6 ${open === hit.chunk.id ? "" : "line-clamp-3"}`}>{hit.chunk.content}</p>
                <Provenance chunk={hit.chunk} />
                <div className="mt-3">
                  <Button type="button" size="sm" variant="secondary" onClick={() => setDraft(hit.chunk)}>以此为出处新建行动项</Button>
                </div>
              </article>
            ))}
          </div>
        ) : null}
        {draft ? <DraftCard chunk={draft} onDone={() => { setDraft(null); reload(); }} /> : null}
      </Panel>
    </div>
  );
}

function DraftCard({ chunk, onDone }: { chunk: ChunkRecord; onDone: () => void }) {
  const [title, setTitle] = useState("");
  const [owner, setOwner] = useState("");
  const [due, setDue] = useState(todayLabel(7));
  const [status, setStatus] = useState<ActionStatus>("open");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const key = useRef(crypto.randomUUID());

  const submit = async () => {
    setBusy(true); setMessage(null);
    try {
      await api.createAction({
        workspace: chunk.workspaceId, title, ownerName: owner, dueDate: due, status, refChunkId: chunk.id, idempotencyKey: key.current,
      });
      key.current = crypto.randomUUID();
      setTitle(""); setOwner("");
      onDone();
      setMessage("已写入数据服务，可在「行动项」查看。");
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-md border border-primary/30 bg-primary/5 p-3">
      <p className="text-sm font-medium">从出处新建行动项</p>
      <p className="mt-1 text-xs text-muted-foreground">
        关联 {chunk.sourceName} · 第 {chunk.chunkNo + 1} 块{chunk.revision ? ` · 版本 ${chunk.revision}` : ""}
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <Input value={title} onChange={e => setTitle(e.target.value)} placeholder="行动项标题，如：补齐实验依赖版本" aria-label="行动项标题" />
        <Input value={owner} onChange={e => setOwner(e.target.value)} placeholder="负责人" aria-label="负责人" />
        <Input type="date" value={due} onChange={e => setDue(e.target.value)} aria-label="截止日期" />
        <select
          className="h-9 rounded-md border border-input bg-background px-2 text-sm"
          value={status}
          onChange={e => setStatus(e.target.value as ActionStatus)}
          aria-label="状态"
        >
          {(["open", "doing", "done"] as ActionStatus[]).map(value => <option key={value} value={value}>{STATUS_LABELS[value]}</option>)}
        </select>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <Button size="sm" onClick={() => void submit()} disabled={busy || !title.trim() || !owner.trim()}>{busy ? "保存中" : "保存行动项"}</Button>
        <Button size="sm" variant="ghost" onClick={onDone}>关闭</Button>
      </div>
      {message ? <p role="status" className="mt-2 text-xs text-muted-foreground">{message}</p> : null}
    </div>
  );
}

export function Library({ workspace, sources, counters, reload }: Common) {
  const [name, setName] = useState("");
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [chunks, setChunks] = useState<ChunkRecord[]>([]);

  const send = async (payload: { name: string; text: string }) => {
    setBusy(true); setMessage(null);
    try {
      const result = await api.importSource(workspace, payload.name, payload.text);
      setMessage(
        `已写入 ${result.source.chunkCount} 个分块，新增 ${result.created}，重复跳过 ${result.skipped}，当前版本 ${result.revision}`
        + (result.retired > 0 ? `，退休旧分块 ${result.retired}（保留供历史出处解析）` : "")
        + "。",
      );
      setName(""); setText("");
      reload();
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(false);
    }
  };

  const openChunks = async (source: SourceRecord) => {
    if (expanded === source.id) { setExpanded(null); return; }
    setExpanded(source.id);
    try {
      setChunks((await api.chunks(workspace, source.id, 20)).chunks);
    } catch (error) {
      setMessage(describeError(error));
    }
  };

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > 1_000_000) { setMessage("文件超过 1 MB，请拆分后导入。"); return; }
    setName(file.name);
    setText(await file.text());
  };

  return (
    <div className="flex flex-col gap-4">
      <Panel
        title="导入学习资料"
        description="按 500 字符窗口、60 字符重叠分块，保留文件名与分块序号作为出处。同名资料内容变化时递增版本、旧分块退休留存，内容超出容量上限会明确拒绝而不是静默截断。"
        aside={<Badge variant="outline">资料 {counters.sources} 份 · 分块 {counters.chunks} 块</Badge>}
      >
        <div className="flex flex-col gap-3">
          <Input value={name} onChange={e => setName(e.target.value)} placeholder="资料名，例如 实验复现清单.md" aria-label="资料名" />
          <textarea
            className="min-h-40 w-full rounded-md border border-input bg-background p-3 text-sm leading-6"
            value={text}
            onChange={e => setText(e.target.value)}
            placeholder="粘贴 Markdown / TXT 内容"
            aria-label="资料内容"
          />
          <div className="flex flex-wrap items-center gap-2">
            <input
              type="file"
              accept=".md,.markdown,.txt,text/plain"
              className="text-sm"
              onChange={e => void onFile(e.target.files?.[0])}
              aria-label="选择文件"
            />
            <Button size="sm" onClick={() => void send({ name, text })} disabled={busy || !name.trim() || !text.trim()}>
              {busy ? "写入中" : "导入当前内容"}
            </Button>
            <Button
              size="sm"
              variant="secondary"
              disabled={busy}
              onClick={() => void (async () => {
                setBusy(true); setMessage(null);
                try {
                  let created = 0;
                  for (const material of sampleMaterials) {
                    const result = await api.importSource(workspace, material.name, material.text);
                    created += result.created;
                  }
                  setMessage(`公开示例资料导入完成，新增 ${created} 个分块。示例内容为虚构整理材料，用于验证流程。`);
                  reload();
                } catch (error) {
                  setMessage(describeError(error));
                } finally {
                  setBusy(false);
                }
              })()}
            >
              导入 5 份公开示例资料
            </Button>
          </div>
          {message ? <Notice tone={message.startsWith("已") || message.startsWith("公开") ? "info" : "error"}>{message}</Notice> : null}
        </div>
      </Panel>

      <Panel title="资料清单" description="点击一份资料可回看当前版本的分块原文与序号；被替换的旧版本仍可凭出处标识解析。">
        {sources.length === 0 ? (
          <Notice tone="empty">当前空间还没有资料。导入公开示例或粘贴自己的笔记后，这里会出现条目。</Notice>
        ) : (
          <ul className="flex flex-col gap-2">
            {sources.map(source => (
              <li key={source.id} className="rounded-md border border-border bg-background p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium">{source.name}</p>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{source.chunkCount} 块</span>
                    <Badge variant="outline">版本 {source.revision}</Badge>
                    <Button size="sm" variant="ghost" onClick={() => void openChunks(source)}>
                      {expanded === source.id ? "收起" : "查看分块"}
                    </Button>
                  </div>
                </div>
                {expanded === source.id ? (
                  <ul className="mt-3 flex flex-col gap-2">
                    {chunks.filter(chunk => chunk.sourceId === source.id).map(chunk => (
                      <li key={chunk.id} className="rounded-sm bg-muted/40 p-2">
                        <p className="whitespace-pre-wrap text-xs leading-5">{chunk.content}</p>
                        <p className="mt-1 text-[11px] text-muted-foreground">
                          第 {chunk.chunkNo + 1} 块 · 版本 {chunk.revision} · {chunk.id.slice(0, 8)}
                        </p>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

export function Actions({ workspace, actions, counters, reload }: Common) {
  const [filter, setFilter] = useState<ActionStatus | "all">("all");
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const today = useMemo(() => new Date(Date.now() + 8 * 3600 * 1000).toISOString().slice(0, 10), []);
  const visible = filter === "all" ? actions : actions.filter(action => action.status === filter);

  const patch = async (action: ActionRecord, next: ActionStatus) => {
    setBusy(true); setMessage(null);
    try {
      await api.patchAction(workspace, action.id, { status: next });
      reload();
    } catch (error) {
      setMessage(describeError(error));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel
      title="行动项"
      description="负责人、截止日期、状态和关联出处都保存在数据服务的任务表里，周报直接读取同一张表。"
      aside={<Badge variant="outline">共 {counters.actions} 项 · 未完成 {counters.openActions} 项</Badge>}
    >
      <div className="flex flex-wrap gap-2">
        {(["all", "open", "doing", "done"] as const).map(value => (
          <Button key={value} size="sm" variant={filter === value ? "default" : "outline"} onClick={() => setFilter(value)}>
            {value === "all" ? "全部" : STATUS_LABELS[value]}
          </Button>
        ))}
      </div>
      {message ? <div className="mt-3"><Notice tone="error">{message}</Notice></div> : null}
      <div className="mt-4 flex flex-col gap-2">
        {visible.length === 0 ? (
          <Notice tone="empty">没有符合条件的行动项。可在「带出处的资料检索」里选中一段原文，用它作为出处新建一条。</Notice>
        ) : visible.map(action => (
          <article key={action.id} className="rounded-md border border-border bg-background p-3">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="text-sm font-medium">{action.title}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {action.ownerName}｜截止 {action.dueDate}
                  {action.status !== "done" && action.dueDate < today ? <span className="ml-1 text-destructive">已逾期</span> : null}
                  {action.completedAt ? <span className="ml-1">完成于 {action.completedAt}</span> : null}
                </p>
                {action.refChunkId ? <Provenance chunk={{ sourceName: action.refSourceName, chunkNo: action.refChunkNo ?? 0, revision: action.refChunkRevision }} /> : (
                  <p className="mt-2 text-xs text-muted-foreground">未关联出处</p>
                )}
              </div>
              <Badge variant={action.status === "done" ? "secondary" : "default"}>{STATUS_LABELS[action.status]}</Badge>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {(["open", "doing", "done"] as ActionStatus[]).filter(status => status !== action.status).map(status => (
                <Button key={status} size="xs" variant="outline" disabled={busy} onClick={() => void patch(action, status)}>
                  标记为{STATUS_LABELS[status]}
                </Button>
              ))}
            </div>
          </article>
        ))}
      </div>
    </Panel>
  );
}

export function ReportView({ workspace, health }: Common) {
  const [week, setWeek] = useState(health?.today ?? "");
  const [report, setReport] = useState<ReportOutput | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = async (value: string) => {
    setError(null);
    try {
      setReport(await api.report(workspace, value || undefined));
    } catch (cause) {
      setError(describeError(cause));
      setReport(null);
    }
  };

  useEffect(() => { if (week) void load(week); }, [workspace, week]);

  const copy = async () => {
    if (!report) return;
    try {
      await navigator.clipboard.writeText(report.text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError("浏览器拒绝了剪贴板访问，请手动全选下方文本复制。");
    }
  };

  return (
    <Panel
      title="本周周报"
      description="按“本周完成 / 待解决问题 / 下周计划”三个区间从任务表整理，条目自带出处。规则是模板化的时间区间判断，不是 AI 生成。"
      aside={
        <div className="flex flex-wrap items-center gap-2">
          <Input type="date" value={week} onChange={e => setWeek(e.target.value)} className="h-8 w-auto" aria-label="周内日期" />
          <Button size="sm" variant="secondary" onClick={() => void load(week)}>重新整理</Button>
          <Button size="sm" onClick={() => void copy()} disabled={!report}>复制文本</Button>
        </div>
      }
    >
      {copied ? <Notice tone="info">周报文本已复制到剪贴板。</Notice> : null}
      {error ? <Notice tone="error">{error} <Button variant="link" size="sm" className="h-auto p-0" onClick={() => void load(week)}>重试</Button></Notice> : null}
      {report ? (
        <div className="flex flex-col gap-4">
          <p className="text-xs text-muted-foreground">区间 {report.range.start} ~ {report.range.end}｜下周 {report.range.nextStart} ~ {report.range.nextEnd}｜服务器日期 {report.today}</p>
          <div className="grid gap-3 sm:grid-cols-3">
            {([["本周完成", report.completed], ["待解决问题", report.pending], ["下周计划", report.nextWeek]] as const).map(([title, items]) => (
              <div key={title} className="rounded-md border border-border bg-background p-3">
                <p className="text-sm font-medium">{title}<span className="ml-1 text-xs text-muted-foreground">{items.length}</span></p>
                <ul className="mt-2 flex flex-col gap-2">
                  {items.length === 0 ? <li className="text-xs text-muted-foreground">暂无条目</li> : items.map(item => (
                    <li key={item.id} className="text-xs leading-5">
                      <p>{item.title}</p>
                      <p className="text-muted-foreground">{item.ownerName}｜{item.statusLabel}｜截止 {item.dueDate}{item.overdue ? "（逾期）" : ""}</p>
                      <p className="text-muted-foreground">出处：{item.provenance}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
          <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border border-border bg-muted/40 p-3 text-xs leading-5">{report.text}</pre>
        </div>
      ) : null}
    </Panel>
  );
}
