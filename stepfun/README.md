# 知页 LOCALFOLIO · 04 端侧推理与 seekdb 混合检索

TXT / Markdown 导入 → 浏览器 Worker 内 E5 embedding → seekdb-js 写入并刷新索引 → seekdb 数据库内全文+向量 RRF → 带出处的检索结果。文档与查询都在浏览器向量化，服务端没有 embedding 模型。自动优先 WebGPU，初始化、后端一致性检查或执行失败时降级 WASM，页面展示实际后端与原因。

## 本机环境与启动

Node.js 22、WSL2 Ubuntu 24.04 已可用。项目、npm 缓存、Qoder CLI、模型和官方 seekdb 安装文件都在 E 盘。数据库运行目录使用 WSL 原生文件系统 `/home/geshanchang/seekdb-contest-runtime2`，对应现有 Ubuntu 的 C 盘虚拟磁盘；本机 E 盘 NTFS 挂载的直接 I/O 初始化失败。没有移动或重装用户现有 WSL。

### 1. 数据库

此机器已将官方 seekdb 1.4.0 DEB 解包到 `E:\tools\seekdb-linux\1.4.0`，并在相同目录解包 Ubuntu `libaio1t64`，补齐本地 `libaio.so.1` 链接。安装包来源、哈希见技术报告。使用 WSL 原生目录持久化，日志盘至少 2 GB。

同目录布局下如需重新安装，可运行 `wsl -d Ubuntu -- bash /mnt/e/project/oceanbase-ecosystem-2026/stepfun/scripts/install-seekdb-wsl.sh`。脚本从官方镜像下载、校验 SHA-256 并解包，不注册系统服务、不删除目录。

```powershell
wsl -d Ubuntu -- bash /mnt/e/project/oceanbase-ecosystem-2026/stepfun/scripts/start-seekdb-wsl.sh
```

保留这个数据库终端；脚本以前台模式运行，避免 WSL 随启动命令退出而停止数据库。API 和前端在另外的终端启动。

其他机器使用 [官方 seekdb 部署方式](https://docs.seekdb.ai/seekdb/deploy-by-systemd/)，启动 MySQL 协议端口 2881 并创建 `test` 数据库。运行本项目需要支持 collection 全文索引、向量索引、`refresh_index()` 与数据库混合检索的服务版本。

### 2. 安装依赖和固定模型

```powershell
Set-Location E:\project\oceanbase-ecosystem-2026\stepfun
npm.cmd ci --cache E:\tools\npm-cache
npm.cmd run models
```

模型固定 `Xenova/multilingual-e5-small` 的提交 `761b726dd34fb83930e26aab4e9ac3899aa1fa78`，384 维、mean pooling、归一化，E5 `passage:` / `query:` 前缀。下载脚本默认 `https://hf-mirror.com`，可在下载前设置 `MODEL_SOURCE=https://huggingface.co`。两份 ONNX 权重合计约 589 MB（十进制），另有共享 tokenizer；本机已下载，可直接启动。清单记录每个文件的字节数和 SHA-256，重复运行会校验复用。首次推理从 localhost 读取本地权重，无云端推理请求。沿用原模型的 MIT 许可，参见 [模型卡](https://huggingface.co/Xenova/multilingual-e5-small)。

### 3. 两个终端分别运行

```powershell
# 终端 A：API，默认 root / 无密码 / test，仅限本地开发。
# 不同数据库配置请先设置 .env.example 中列出的环境变量。
npm.cmd run server
```

```powershell
# 终端 B：前端
npm.cmd run dev
```

访问 <http://127.0.0.1:5173>。生产本地运行可执行 `npm run build` 后运行 `npm run server`，访问 <http://127.0.0.1:8787>；需保留 `public/models`、`public/ort` 和 `dist`。不要把此无登录的本地开发 API 直接暴露到公网。`.env` 不会自动加载，须通过 shell / 进程环境设置参数。

## 使用与验收

1. 点击“试用 12 份示例资料”，观察实际后端、量化精度、导入进度和分块数。
2. 搜索“怎样让刚导入的文档立即可检索”，核对结果源文件和原文片段。
3. 再导入相同文件，分块数不应增加；导入新的 TXT / MD，写入后刷新，新增内容应立即可检索。
4. 创建另一集合，内容独立；切换 FP32 / INT8 时使用不同集合，避免混入不同精度向量。不同浏览器会话命名空间也不同。
5. 选择“强制 WASM”检索，再切换自动后端验证实际 GPU 或降级信息。自动模式对三个固定公开句子与同精度 WASM 输出比较，最小余弦低于 0.99 时降级；这只是数值冒烟检查，不能代替带标签的质量评估。本机实测会触发此降级，不能宣称取得 GPU 加速。
6. 性能页运行四组对照，导出原始 JSON；每组 3 次语料向量化、3 轮 6 条查询，质量标签见 `public/queries.json`。

源文件按 500 字符、60 字符重叠分块，模型自身 token 上限仍可能截断长片段。ID 是“来源+分块序号+内容”的 SHA-256：相同内容重复导入幂等，修改内容会追加新版本，当前没有自动删除旧版本功能。输入限制每文件 2 MB、单次最多 1000 个分块、单批写入最多 64 个。批处理后统一刷新。刷新失败会禁止该集合检索并提示重试，防止把未刷新结果报告为成功。

## 数据库执行方式

`server/database.ts` 使用 `seekdb@1.4.0`：`embeddingFunction: null` 禁用服务端自动向量化，创建 384 维 cosine HNSW 与 ngram 全文索引；通过 SDK `hybridSearch()` 将全文与向量两路及 RRF 排序交给数据库执行。浏览器只渲染返回结果，不拼接两路检索结果。会话和精度进入集合指纹，数据库凭据只存在服务端环境中。

## 复现与数据

```powershell
npm.cmd test
npm.cmd run build
npm.cmd run test:db
npm.cmd run test:browser
npm.cmd run test:browser -- --benchmark
```

数据库检查使用明确标注的合成向量，只验证写入/刷新/隔离等链路；检索质量和推理性能只来自真实浏览器模型执行。浏览器测试使用已安装 Edge 的独立无头会话，不读取用户浏览器账号。截图和交互数据位于忽略的 `test-results/`；完整对照保存至 `results/benchmark.json`。测试会创建独立集合并保留数据，不自动批量删除。

首次“模型加载”计时包括读取/解析与会话初始化；浏览器或操作系统可能已有缓存，不等同于全新网络下载。首次查询发生在语料导入之后，属于查询首轮而非模型首次执行。热查询端到端计时包含 Worker 和本地 API 往返、不含页面绘制；交互模式额外记录双动画帧近似的查询到绘制时间。12 份人工示例与 6 条标签仅用于复现和冒烟评估，不能代表大规模或真实生产检索质量。

一页可提交报告：[technical-report.pdf](output/pdf/technical-report.pdf)，文字说明、实际版本与限制见 [TECHNICAL.md](TECHNICAL.md)。报告可用安装了 reportlab/pypdf 的 Python 运行 `scripts/make-report.py` 重新生成。最终生产构建原始测量见 `results/benchmark.json`，新浏览器上下文初始化与交互记录见 `results/verification.json`。最初未启用后端一致性检查时的实验留在 `results/initial-webgpu-unchecked.json`，仅用于说明发现并修复的数值问题，不能当作最终应用表现。本项目属于 04，06 使用独立 `gaode/SKILL.md`；03 的 Qoder 开发与 Sites 发布单独交付。
