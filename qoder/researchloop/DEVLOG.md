# 开发记录（DEVLOG）

按实际推进顺序追加，不回溯改写既有条目。工具：Qoder CLI（会话内开发），赛题 03 · 学习科研提效。

## 2026-10-28 · 规则复核与路线确定

- 重新核对 03 题公开规则后确认：项目网站是作品展示与评审入口，项目本身可按说明本地运行，**不要求云端 seekdb**。
- 路线据此改为「本机 seekdb 承担全部业务数据的核心应用 + Qoder Sites 静态作品展示站」。放弃把站点自带数据库当核心的方案：它不是赛题指定的数据库，会构成冒充指定技术。
- 核查 Qoder Sites 能力（宿主 CLI 32 个操作）：站点内容 = `webDirectory` 里的静态文件；服务端 = 单个 `app` Edge Function；数据库迁移仅支持 `CREATE TABLE app.<t>` / `ADD COLUMN` / 普通索引，列类型限定在 boolean、integer、bigint、text、uuid、timestamptz、jsonb（无 `date`、无 `varchar(n)`、无 CHECK/生成列）；没有任何通往云端 seekdb 或 PowerContext 的通道。结论写入方案，作为路线调整依据。
- 核实 PowerContext 官方形态：OceanBase 开源的 Agent 上下文服务（HTTP / MCP / SDK / CLI），**自托管**，无官方托管实例；比赛分支仅为目录脚手架。因此不把它作为发布站点的在线依赖。

## 2026-10-28 · seekdb 能力实测（先测后设计）

- 用 `server/probe.ts` 确认 npm `seekdb@1.4.0` 是 MySQL 协议客户端，`client.execute(sql, params)` 支持参数化原始 SQL。
- 尝试 collection 路线失败：写入文档时必须提供 embedding 或 embedding function，空 embedding 被拒绝（`Documents provided but no embeddings and no embedding function`）。改走关系表 + 库内全文索引。
- 用 `server/probe-fulltext.ts` 实测中文检索：默认解析器对中文查询返回空结果；`FULLTEXT INDEX … WITH PARSER ngram`（索引词长 2）可用，且 `MATCH(content) AGAINST(?)` 直接在库里给出相关度分数。据此把检索下推进单条 SQL，前端与 Node 服务都不做内存检索。
- 踩坑记录：早期遗留表使 `CREATE TABLE IF NOT EXISTS` 不生效，出现 `Unknown column 'source_id'`；端口 8787 已被 04 题占用，本项目改用 8788；`npm install seekdb` 因 `@seekdb/default-embed` 的 `workspace:*` peer 依赖报 EUNSUPPORTEDPROTOCOL，服务端独立成 `server/` 包并用 `.npmrc` 的 `legacy-peer-deps=true` 绕过。
- 首轮端到端验收 18 项断言全部通过，证据写入 `results/seekdb-verify.json`。

## 2026-10-28 · 按评审笔记修复真实缺陷

对照 `E:/tools/contest-setup/qoder-review-notes.md` 逐条核实：

1. **createAction 占位符数不匹配**（13 个 `?` 对 12 列）：已确认并修正为列数一致，随后被真实创建请求验证。
2. **长文本静默截断**：原 `chunkText` 在 400 块处 `break`，而导入上限允许 200,000 字符（约 455 块），尾部内容会无声消失。改为先按窗口/步长算出需要的块数，超出容量直接抛 `material_too_large` 并说明需要多少块；`maxChunksPerSource` 调到 460 与字符上限自洽。回归断言：182,429 字符资料完整入库 415 块（旧实现此处会丢尾），检索「尾部校验标记」命中第 415 块；200,010 字符资料返回 400。
3. **同名变更资料的版本与引用稳定性**：原实现保留 sourceId 但插入新分块、不退休旧块，导致同序号重复与陈旧内容混在检索结果里。新增列 `rl_sources.revision`、`rl_material_chunks.revision/retired_at`、`rl_actions.ref_chunk_revision`；导入策略改为「内容相同幂等返回，不变动版本」/「内容变化则版本 +1、新分块入库、旧分块退休并保留」；检索与列表只作用于 `retired_at IS NULL`，而按分块标识取原文仍可解析历史版本，因此旧引用不会被断链。为已有安装用 `ensureSeekdbSchema()`（读 `information_schema.COLUMNS` 后 `ALTER TABLE … ADD COLUMN`）增量补列，不删除任何数据。
4. **架构与发布路线**（笔记 4）：按上文「规则复核」执行。
5. **端口与分支**（笔记 5、6）：8788、`feature/researchloop-qoder`，不推送凭据，不回退 04 的 WSL 启动脚本。

## 2026-10-28 · 验收扩展与界面同步

- `server/verify-flow.ts` 从 18 项扩到 30 项：新增长文本 3 项、版本与引用 8 项，并加强幂等断言（重复导入必须 `retired = 0` 且版本不变）、出处版本一致性断言（行动项 `ref_chunk_revision` 等于命中分块版本）。版本用例改用随运行编号的空间，避免重复执行时版本算术失真。
- 首轮全绿：30 / 30。
- 界面与代码同步：分块列表与资料清单显示版本号，导入提示区分「新增 / 跳过 / 退休旧分块 / 当前版本」，行动项与周报出处带锁定版本；「关于本站」重写为本地 seekdb 核心 + Sites 静态展示站的真实说明，并补上版本策略一节。
- 端点简化：前端改走同源 `/api`（Vite dev/preview 代理到 8788），删除 Deno 模板入口 `functions/index.ts`、`functions/handler.ts`、`dev/function-local.ts` 与站点数据库分支类型；核心服务不再输出堆栈的调试响应分支一并移除。
- `npm run build`（`tsc --noEmit` + Vite）通过；本回合修复了 `@/views`、`@/api`、`@/format` 三个别名导入（`@` 映射到工程根，同级模块改为相对路径）。
- 新增 `site/`：作品介绍与验收入口静态页（问题、功能、架构、真实结果、截图位、本地运行步骤、开发记录、边界说明）与 `scripts/serve-site.mjs` 本地预览（`http://127.0.0.1:4174`）。截图路径以 `site/screenshots/README.md` 约定，图片缺失时页面显示待补充说明。

## 2026-10-28 · 截图归档与 Qoder Sites 发布

- 浏览器真实验收已完成：导入 → 库内检索 → 行动项 → 完成 → 周报全链路走通，30 项真实数据库断言通过，前端生产构建通过。
- 四张真实界面截图写入 `site/screenshots/`（01-workbench、02-library-versions、03-actions、04-report，均为 JPG）。介绍页图片路径改为 JPG，移除「截图待补充」与 05-mobile 占位；移动端视口工具无效，未声称已测。
- 资料库配图说明按画面实际内容改写：5 份资料、6 个分块，逐份列出「块数 · 版本 1」；检索、行动项、周报的配图说明同步改为截图中的实测数字（13 ms、分值 4.1054、2 项已完成、区间 2026-10-26 ~ 2026-11-01）。
- 保留根代理 `chunkText` 的终点 `break` 修复：窗口覆盖文本终点时立即结束，避免多余尾块。
- Qoder Sites 首次建站并发布：`researchloop/site` 作为 `webDirectory`，公开地址 <https://yantu-researchloop-lr92v5hwg45.qoder.website>。发布后匿名请求首页、`styles.css` 与四张截图均返回 200；访问范围设为 public。
- 发布过程：`prepare_site` 创建草稿（artifactReady、dependenciesReady、canPublish 均为 true）→ `publish_site` → `get_publish_status` 返回 published=true、committed=true。本地 `.qoder.site` 描述文件在首次准备时 pending，按同一 action 与相同输入重试 `prepare_site` 后写入成功。

## 当前遗留

- 验收在数据库中留下的测试空间（`verify`、`verify-large`、`verify-version-*`）不做清理：本作品不提供批量删除。
- 检索词生成目前只做中文二元切分 + 整段短语，没有同义词表；短查询的召回依赖库里 ngram 命中。
- 行动项没有删除/归档接口；演示身份由前端空间选择器决定，本回合不做多用户鉴权。
