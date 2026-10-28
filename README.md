# 2026 生态赛：03 / 04 / 06

本项目基于官方 `oceanbase/powercontext` 的 `2026-competition-ecosystem` 分支，保留官方初始提交。各题使用独立目录，在 `feature/*` 分支提测。

| 题目 | 源码 / 材料 | 当前进展 |
| --- | --- | --- |
| 03 Qoder 提效项目「研途」 | [运行与验收](qoder/researchloop/README.md) · [公开作品站](https://yantu-researchloop-lr92v5hwg45.qoder.website) | Qoder 主体开发已完成，真实 seekdb 验收 30/30；已独立提测，等待平台执行 |
| 04 端侧 AI 与 seekdb「知页」 | [运行说明](stepfun/README.md) · [一页报告](stepfun/output/pdf/technical-report.pdf) | 已独立提测，平台 20.000 / 20 分 |
| 06 高德附近推荐 | [SKILL.md](gaode/SKILL.md) | 已独立提测，平台 20.000 / 20 分 |

04 的浏览器端和查询端均在本机向量化，seekdb-js 负责真实数据库内混合检索。INT8 在小样例上保持质量；本机 WebGPU 数值检查不通过时自动回退 WASM，详见报告的实际数据和限制。

## 浏览器工具准备

本机已安装微软官方 `@playwright/mcp@0.0.83` 到 `E:\tools\browser-mcp`。浏览器扩展来自 [微软官方安装说明](https://github.com/microsoft/playwright/tree/main/packages/extension#readme) 中链接的 [Playwright Extension 商店页](https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm)。扩展需安装到你要使用的 Edge 配置中，并在首次连接页面选择允许控制的比赛标签页。不能把 MCP 服务端安装成功当成浏览器已连接成功。

04 本地网站：`http://127.0.0.1:8787`；运行前按 stepfun README 启动 WSL 数据库与 API。模型权重、依赖、数据库、密码和浏览器状态均不进 Git。

私有备份仓库已创建。04、06 的评测代码已同步到报名登记的团队仓库 `sleepz1/powercontext` 的 `feature/ecosystem-ae04-ae06` 分支并分别通过测试。分题回执与状态见 [SUBMISSIONS.md](SUBMISSIONS.md)。
