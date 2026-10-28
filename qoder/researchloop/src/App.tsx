import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Actions, Library, ReportView, Workbench, type Common } from "./views";
import { api, describeError, WORKSPACES, type Health, type StateOutput } from "./api";
import { backendTitle } from "./format";

const TABS = [
  { id: "workbench", label: "资料检索" },
  { id: "library", label: "资料库" },
  { id: "actions", label: "行动项" },
  { id: "report", label: "周报" },
  { id: "about", label: "关于本站" },
] as const;

type TabId = (typeof TABS)[number]["id"];

const REPO_URL = "https://github.com/sleepz1/powercontext/tree/feature/researchloop-qoder/qoder/researchloop";

export default function App() {
  const [tab, setTab] = useState<TabId>("workbench");
  const [workspace, setWorkspace] = useState(WORKSPACES[0].id);
  const [health, setHealth] = useState<Health | null>(null);
  const [state, setState] = useState<StateOutput | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [nextHealth, nextState] = await Promise.all([api.health(), api.state(workspace)]);
      setHealth(nextHealth);
      setState(nextState);
    } catch (cause) {
      setError(describeError(cause));
      setHealth(prev => prev);
      setState(null);
    } finally {
      setLoading(false);
    }
  }, [workspace]);

  useEffect(() => { void reload(); }, [reload]);

  const common: Common = {
    workspace,
    counters: state?.counters ?? { sources: 0, chunks: 0, actions: 0, openActions: 0 },
    sources: state?.sources ?? [],
    actions: state?.actions ?? [],
    reload: () => void reload(),
    health,
  };

  return (
    <div className="min-h-dvh bg-background text-foreground">
      <header className="border-b border-border bg-card/70">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold tracking-tight sm:text-2xl">研途 ResearchLoop</h1>
              <p className="mt-1 text-sm text-muted-foreground">资料检索与任务推进放在一起的学习科研工作台</p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant={health ? "default" : "destructive"} className="rounded-sm">
                {health ? backendTitle(health.backend) : "后端未就绪"}
              </Badge>
              <label className="flex items-center gap-2 text-xs text-muted-foreground">
                空间
                <select
                  className="h-8 rounded-md border border-input bg-background px-2 text-xs text-foreground"
                  value={workspace}
                  onChange={event => setWorkspace(event.target.value)}
                  aria-label="选择工作空间"
                >
                  {WORKSPACES.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
                </select>
              </label>
              <Button size="sm" variant="outline" onClick={() => void reload()} disabled={loading}>{loading ? "读取中" : "刷新"}</Button>
            </div>
          </div>
          <nav className="scrollbar-none -mx-1 overflow-x-auto px-1" aria-label="主导航">
            <ul className="flex gap-1">
              {TABS.map(item => (
                <li key={item.id}>
                  <Button
                    size="sm"
                    variant={tab === item.id ? "secondary" : "ghost"}
                    onClick={() => setTab(item.id)}
                    aria-current={tab === item.id ? "page" : undefined}
                  >
                    {item.label}
                  </Button>
                </li>
              ))}
            </ul>
          </nav>
        </div>
      </header>

      <main className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-5 sm:px-6 sm:py-6">
        {error ? (
          <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive" role="status">
            {error}
            <span className="ml-2 text-muted-foreground">页面不会用内存示例数据代替真实检索。</span>
            <Button size="sm" variant="outline" className="ml-3" onClick={() => void reload()}>重试</Button>
          </div>
        ) : null}
        {tab === "workbench" ? <Workbench {...common} /> : null}
        {tab === "library" ? <Library {...common} /> : null}
        {tab === "actions" ? <Actions {...common} /> : null}
        {tab === "report" ? <ReportView {...common} /> : null}
        {tab === "about" ? <About health={health} workspace={workspace} repo={REPO_URL} /> : null}
      </main>

      <footer className="border-t border-border px-4 py-5 text-xs text-muted-foreground sm:px-6">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-2">
          <p>研途 ResearchLoop · 2026 OceanBase × Qoder 生态赛 03 作品</p>
          <p>核心应用在本机跑真实 seekdb；作品介绍与验收入口通过 Qoder Sites 静态站点发布</p>
        </div>
      </footer>
    </div>
  );
}

function About({ health, workspace, repo }: { health: Health | null; workspace: string; repo: string }) {
  return (
    <div className="flex flex-col gap-4">
      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <h2 className="text-base font-semibold sm:text-lg">项目要解决的问题</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          论文摘录、实验记录和组会行动项散落在不同文件里：查资料找不到出处，写周报要重新把任务拼一遍。
          研途把「带出处的资料检索」和「带负责人与截止日期的行动项」放进同一个工作台，
          周报直接读取同一张任务表，条目保留原始出处。
        </p>
      </section>

      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <h2 className="text-base font-semibold sm:text-lg">核心功能</h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-muted-foreground">
          <li>导入 Markdown / TXT 资料，按 500 字符窗口、60 字符重叠分块，保留文件名与分块序号作为出处。</li>
          <li>用一句话检索资料，结果返回原文片段、数据库相关度分数与出处；不生成无出处结论。</li>
          <li>从任意检索结果新建行动项，设置负责人、截止日期、状态与关联出处（出处锁定资料版本号）。</li>
          <li>按「本周完成 / 待解决问题 / 下周计划」输出可复制周报，条目自带出处；明确标注模板规则生成。</li>
          <li>空间隔离：不同工作空间的资料与任务互不可见，数据全部落在真实 seekdb 里。</li>
          <li>同名资料改版不丢历史：新版本生效、旧分块退休留存、历史出处仍可解析。</li>
        </ul>
      </section>

      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <h2 className="text-base font-semibold sm:text-lg">架构与数据库分工</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          业务逻辑只有一份，位于 <code>functions/core/</code>：分块、检索词、校验、版本策略、周报规则与 HTTP 路由。
          这个页面通过本地开发代理调用本机核心服务，所有资料与任务都读写真实数据库。
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div className="rounded-md border border-border bg-background p-3">
            <p className="text-sm font-medium">seekdb 1.4.0 · 唯一承担业务数据的核心</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              Node 服务用 <code>seekdb</code> npm SDK 连接本机 seekdb。资料分块与行动项存放在
              <code>researchloop.rl_*</code> 三张表里；中文检索使用
              <code>FULLTEXT INDEX ... WITH PARSER ngram</code>，由
              <code>MATCH(content) AGAINST(?)</code> 在数据库内完成过滤与相关度排序，应用层只渲染结果。
            </p>
          </div>
          <div className="rounded-md border border-border bg-background p-3">
            <p className="text-sm font-medium">Qoder Sites · 静态作品展示站</p>
            <p className="mt-1 text-xs leading-5 text-muted-foreground">
              发布的站点是作品介绍与评审入口：问题、功能、架构、真实验收结果、截图与本地运行步骤。
              赛题指定的数据库能力由本地 seekdb 真实实现，展示站不使用其他数据库冒充指定技术，
              也不放内存示例结果。
            </p>
          </div>
        </div>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          核心服务不可用时，页面显示明确的失败状态并提供重试，不会用内存数组或静态结果冒充数据库返回。
        </p>
      </section>

      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <h2 className="text-base font-semibold sm:text-lg">资料版本与出处稳定性</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          同名资料再次导入且内容有变化时：资料版本号递增，新分块写入，被替换的旧分块标记为退休并保留在库里
          （不批量删除）。检索与列表只返回当前版本；已有引用凭原始分块标识仍能解析到当时看到的内容，
          周报里的出处会标注锁定的版本号。内容长度超过分块容量上限时直接报错并说明原因，不静默丢弃尾部。
        </p>
      </section>

      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <h2 className="text-base font-semibold sm:text-lg">评审验收步骤</h2>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm leading-6 text-muted-foreground">
          <li>在「资料库」点击「导入 5 份公开示例资料」（可重复点击，相同内容会幂等跳过并提示版本不变）。</li>
          <li>在「资料检索」输入「怎样保证实验可以复现」，打开命中结果的原文，核对出处文件名、分块序号与版本。</li>
          <li>点「以此为出处新建行动项」，填「补齐实验依赖版本」等标题、负责人和截止日期后保存。</li>
          <li>在「行动项」把它标记为已完成，回到「周报」查看该条目与出处，并复制文本。</li>
          <li>回到「资料库」用同一个资料名导入改过一句的内容：版本号 +1、提示退休旧分块；行动项出处仍锁定版本 1。</li>
          <li>刷新页面或重启前端，数据仍然存在（都在 seekdb 里）；切换到「我的空间」可验证空间隔离。</li>
        </ol>
        <p className="mt-3 text-xs leading-5 text-muted-foreground">
          这套流程同样由 <code>server/verify-flow.ts</code> 以真实 HTTP 请求逐项断言，最近一次结果见
          <code> results/seekdb-verify.json</code>。
          当前空间：<code>{workspace}</code>；数据后端：{health ? `${backendTitle(health.backend)} · ${health.label}` : "未就绪"}。
          公开示例内容为参赛者整理的虚构学习科研材料，不含真实个人数据。
        </p>
      </section>

      <section className="rounded-lg border border-border bg-card p-4 sm:p-5">
        <h2 className="text-base font-semibold sm:text-lg">Qoder 开发记录与代码</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">
          主体实现由 Qoder CLI 在一次会话中完成：能力核查、seekdb 检索方案实测、核心逻辑、双适配器、前端与端到端验证。
          开发过程中的实测数据保存在仓库 <code>qoder/researchloop/results/</code>。
          分块与「检索下推进数据库」的思路复用了同仓库 <code>stepfun</code>（04 题）的实测结论，
          研究任务与周报功能为本赛题新实现。
        </p>
        <p className="mt-3 text-sm">
          <a className="text-primary underline underline-offset-4" href={repo} target="_blank" rel="noreferrer">代码仓库（题目录 qoder/）</a>
        </p>
      </section>
    </div>
  );
}
