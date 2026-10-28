# 研途 ResearchLoop

2026 OceanBase × Qoder 生态挑战赛 03 题（学习科研提效方向）作品。把「带出处的资料检索」和「带负责人、截止日期、状态的行动项」放进同一个中文工作台，周报直接读取同一张任务表，条目保留原始出处。

核心应用**完全在本机运行**，业务数据全部落在真实 seekdb 数据库里；Qoder Sites 上发布的是作品介绍与验收入口静态站（见 `site/`）。赛题指定的数据库能力由 seekdb 真实实现，不使用其他数据库或内存示例结果冒充。

## 功能闭环

1. **导入资料**：粘贴或选择 Markdown / TXT，按 500 字符窗口、60 字符重叠分块，保留「文件名 · 第 N 块 · 版本 R」作为出处。
2. **带出处的检索**：中文问题按二元切分生成检索词，由 seekdb 的 ngram 全文索引在库内过滤并给出相关度分数；页面只展示数据库返回的原文片段与出处。
3. **行动项**：从任一条命中结果作为出处新建任务（标题 / 负责人 / 截止日期 / 状态），出处锁定资料版本号；同幂等键重试不产生第二条。
4. **周报**：按「本周完成 / 待解决问题 / 下周计划」生成可复制纯文本，条目带出处与逾期标记，并明确标注由模板规则生成（不声称 AI 生成）。

另有：工作空间隔离、空态提示、失败提示与重试、窄屏单列布局。

## 运行环境

- Node `^22.13.0 || >=24.0.0`（本机实测 v22.20.0），npm 随附版本。
- seekdb 1.4.0（Linux 版，运行在 WSL Ubuntu 内，监听 `127.0.0.1:2881`）。
- 端口约定：seekdb `2881` · 核心服务 `8788` · 前端 `5173` · 介绍页本地预览 `4174`。

## 运行步骤

### 1. 启动 seekdb（WSL）

```sh
# 一次性安装：官方镜像下载 → 校验 SHA-256 → 解包，不注册系统服务、不删除任何目录
wsl -d Ubuntu -- bash /mnt/e/project/oceanbase-ecosystem-2026/stepfun/scripts/install-seekdb-wsl.sh

# 启动（保持前台，数据目录在 WSL 原生文件系统）
wsl -d Ubuntu -- bash /mnt/e/project/oceanbase-ecosystem-2026/stepfun/scripts/start-seekdb-wsl.sh
```

Windows 侧确认可达：`netstat -ano | findstr 2881` 出现 `LISTENING`。

### 2. 启动核心服务

```sh
cd server
npm ci
npm start          # http://127.0.0.1:8788
```

首次启动会执行 `ensureSeekdbSchema()`：建库建表，并为已有表**增量补齐**版本管理列（`ALTER TABLE … ADD COLUMN`），不删除任何数据。

连接参数只用环境变量传入（服务不读取 `.env` 文件，也不会把密码写进代码）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `RESEARCHLOOP_HOST` | `127.0.0.1` | 核心服务监听地址 |
| `RESEARCHLOOP_PORT` | `8788` | 核心服务端口 |
| `SEEKDB_HOST` / `SEEKDB_PORT` | `127.0.0.1` / `2881` | seekdb 地址 |
| `SEEKDB_USER` / `SEEKDB_PASSWORD` | `root` / 空 | 本机开发实例账号；若自行设置密码，只放在启动命令的环境变量里 |
| `SEEKDB_DATABASE` | `test` | 连接库；业务表固定写在 schema `researchloop` |

示例：`SEEKDB_PORT=2881 npm start`（Git Bash）或 `$env:SEEKDB_PORT='2881'; npm start`（PowerShell）。

冒烟检查：

```sh
curl http://127.0.0.1:8788/api/health
# {"ok":true,"backend":"seekdb","label":"seekdb 1.4.0 · 库内 ngram 全文检索","today":"…"}
```

### 3. 启动前端工作台

```sh
npm ci
npm run dev        # Vite 输出 http://127.0.0.1:5173，/api 代理到 8788
```

打开该地址 → 「资料库」→「导入 5 份公开示例资料」→「资料检索」问「怎样保证实验可以复现」→ 用某条结果作为出处新建行动项 → 标记完成 → 到「周报」查看并复制。

### 4. 端到端验收（真实 HTTP + 真实 seekdb）

```sh
npm run verify     # 或 cd server && npm run verify
```

`server/verify-flow.ts` 逐项断言 30 条，结果写入 `results/seekdb-verify.json`（含每条响应体）。期望末行 `全部通过：30/30`。验收会在 `verify`、`verify-large`、`verify-version-*` 空间累积记录，与演示空间隔离。

### 5. 本地预览作品展示站

```sh
npm run serve:site # http://127.0.0.1:4174
```

### 生产构建

```sh
npm run build      # tsc --noEmit 类型检查 + Vite 构建，输出 dist/
```

## 目录结构

```
researchloop/
├─ functions/core/      业务核心（一份，浏览器端与 Node 服务共用）
│  ├─ api.ts            HTTP 路由、请求体限长、输入校验、错误语义
│  ├─ chunk.ts          分块与出处、容量上限显式拒绝、SHA-256 标识
│  ├─ keywords.ts       中文二元切分检索词
│  ├─ report.ts         周区间与三段周报模板
│  ├─ samples.ts        5 份公开示例资料（虚构整理材料）
│  ├─ store.ts          存储适配器接口
│  └─ validate.ts       字段校验与中文错误消息
├─ server/              Node 核心服务 + seekdb 适配器 + 验收脚本（独立 npm 包）
├─ src/                 React 前端（中文主界面：检索 / 资料库 / 行动项 / 周报 / 关于本站）
├─ site/                Qoder Sites 静态作品展示站（index.html、styles.css、screenshots/）
├─ results/             真实验收证据 seekdb-verify.json
└─ scripts/             构建、静态预览、运行时检查
```

## 数据模型（seekdb · schema `researchloop`）

| 表 | 作用 | 关键列 |
| --- | --- | --- |
| `rl_sources` | 一份资料及其当前版本 | `id`、`workspace_id`、`name`、`chunk_count`、`revision` |
| `rl_material_chunks` | 分块正文与版本状态 | `id`（`SHA-256(工作空间\|资料名\|块号\|内容)`）、`content`、`chunk_no`、`revision`、`retired_at`、`FULLTEXT INDEX ft_chunk(content) WITH PARSER ngram` |
| `rl_actions` | 行动项与出处引用 | `id`（`SHA-256(工作空间\|幂等键)`）、`title`、`owner_name`、`due_date`、`status`、`ref_chunk_id`、`ref_chunk_no`、`ref_chunk_revision` |

版本策略：同名资料内容变化 → `revision + 1`、新分块入库、被替换的旧分块置 `retired_at` 退休（保留、不删除）。检索与列表只作用于 `retired_at IS NULL`；已有引用凭原始分块标识仍可解析，周报出处显示锁定的版本号。

## HTTP 接口

`GET /api/health` · `GET /api/state?workspace=` · `GET /api/search?workspace=&q=&limit=` · `GET /api/chunks?workspace=&sourceId=&limit=` · `POST /api/sources` · `GET /api/actions?workspace=&status=` · `POST /api/actions` · `PATCH /api/actions/{id}` · `GET /api/report?workspace=&week=`

失败语义：输入问题返回 400 与中文说明；后端不可用返回 503 `backend_unavailable` 并声明不会用示例结果替代真实检索。

## 实测结果摘要（本轮）

- 端到端断言 **30 / 30 全部通过**（`results/seekdb-verify.json`）。
- 检索在库内排序：`retrieval = database-fulltext-ranked`，`tookMs ≈ 4–7`，首位命中相关度 0.3441。
- 长文本不截断：182,429 字符 → **415 块**全部入库（旧实现在 400 块处静默丢尾），检索「尾部校验标记」命中第 415 块。
- 超长显式拒绝：200,010 字符 → 400 `material_too_large`。
- 版本与引用稳定性：改版后 `revision = 2`、`retired = 1`；退休分块不再被检索到；引用旧分块仍可创建行动项并锁定「版本 1」，周报出处显示「版本 1」。

## 边界

- 公开示例资料为参赛者整理的虚构学习科研材料，不含真实个人数据、凭据或未公开实验结果。
- 单份资料上限 200,000 字符、最多 460 块；超出即拒绝，不静默截断。
- 退休分块与验收记录只标记、不批量删除；本作品不提供删除接口。
- 发布的展示站为静态页面，不含业务后端；核心应用需按上文步骤在本机运行。

## 开发记录

`DEVLOG.md` 按实际推进顺序记录本轮开发轨迹（能力核查、检索实测、评审问题修复、验收、截图归档与发布）。模板来源见 `PROVENANCE.md`。作品介绍页已发布为公开站点：<https://yantu-researchloop-lr92v5hwg45.qoder.website>。截图说明见 `SCREENSHOTS.md`，图片位于 `site/screenshots/`（01–04，JPG）。
