# 2026 生态赛：03 / 04 / 06

此私有仓库基于官方 `oceanbase/powercontext` 的 `2026-competition-ecosystem` 分支，保留官方初始提交。工作分支为 `codex/ecosystem-03-04-06`，每题使用自己的目录和提交材料。

| 题目 | 源码 / 材料 | 当前进展 |
| --- | --- | --- |
| 03 Qoder 提效项目「研途」 | [方案与开发入口](qoder/README.md) | CLI 已安装；本机 CLI 授权尚未验证成功，主体开发及 Sites 发布待完成 |
| 04 端侧 AI 与 seekdb「知页」 | [运行说明](stepfun/README.md) · [一页报告](stepfun/output/pdf/technical-report.pdf) | 已完成真实数据库、浏览器和生产构建验证；包含完整原始实测数据 |
| 06 高德附近推荐 | [SKILL.md](gaode/SKILL.md) | 单文件已完成并通过格式校验，比赛环境提供 MCP 与 Key |

04 的浏览器端和查询端均在本机向量化，seekdb-js 负责真实数据库内混合检索。INT8 在小样例上保持质量；本机 WebGPU 数值检查不通过时自动回退 WASM，详见报告的实际数据和限制。

## 浏览器工具准备

本机已安装微软官方 `@playwright/mcp@0.0.83` 到 `E:\tools\browser-mcp`。浏览器扩展来自 [微软官方安装说明](https://github.com/microsoft/playwright/tree/main/packages/extension#readme) 中链接的 [Playwright Extension 商店页](https://chromewebstore.google.com/detail/playwright-extension/mmlmfjhmonkocbjadbfplnigmagldckm)。扩展需安装到你要使用的 Edge 配置中，并在首次连接页面选择允许控制的比赛标签页。不能把 MCP 服务端安装成功当成浏览器已连接成功。

04 本地网站：`http://127.0.0.1:8787`；运行前按 stepfun README 启动 WSL 数据库与 API。模型权重、依赖、数据库、密码和浏览器状态均不进 Git。

私有仓库已创建，03、04、06 当前材料已推送。**尚未在比赛平台正式提交，暂无官方得分。** 分题状态见 [SUBMISSIONS.md](SUBMISSIONS.md)。
