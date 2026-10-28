# 研途：安装与 Qoder 开发入口

项目方案见 [PLAN.md](PLAN.md)，开发任务见 [QODER_PROMPT.md](QODER_PROMPT.md)。

已安装官方 npm 包 `@qoder-ai/qodercli@1.1.80`，不需要重新安装。PowerShell 中运行：

```powershell
& 'E:\tools\qoder\node_modules\.bin\qoder.cmd' --version
& 'E:\tools\qoder\node_modules\.bin\qoder.cmd' login
& 'E:\tools\qoder\node_modules\.bin\qoder.cmd' status -o json
```

`login` 会生成一次性网页登录链接，由账号本人完成登录；链接超时后重新运行。无需向任何人提供密码或验证码。

登录后打开 Qoder CLI：

```powershell
& 'E:\tools\qoder\node_modules\.bin\qoder.cmd' -w 'E:\project\oceanbase-ecosystem-2026\qoder'
```

将 `QODER_PROMPT.md` 的任务交给 Qoder。用 Qoder 对话开发主体功能，并保存真实记录、Qoder UID、演示截图与验证过程。03 题规则复核后的路线是：**核心应用在本机跑真实 seekdb，Qoder Sites 只发布作品介绍与验收入口的静态站点**；首次建站时明确要求“为当前账号新建研途作品展示站”，不接入站点数据库冒充指定技术。先核查真实托管能力与服务端连接方案，再部署。不要手写 `.qoder.site` 文件，也不要填写虚构 URL。

如需从零安装同版本（当前机器已完成）：

```powershell
npm.cmd install --prefix E:\tools\qoder --cache E:\tools\npm-cache --registry https://registry.npmjs.org @qoder-ai/qodercli@1.1.80
```

官方文档：[CLI 入门](https://docs.qoder.com/cli/quickstart)。赛题：[Qoder 项目要求](https://oceanbase.yuque.com/org-wiki-obtech-vh7w9r/hc3pio/uygu3273xzlrcmrm)。

主体开发已在 `researchloop/` 完成并由 Qoder 会话记录：中文工作台、真实 seekdb 检索与行动项闭环、周报生成、端到端验收 30/30。运行与验收步骤见 [researchloop/README.md](researchloop/README.md)，开发轨迹见 [researchloop/DEVLOG.md](researchloop/DEVLOG.md)。作品介绍静态站位于 `researchloop/site/`，已发布为公开站点：<https://yantu-researchloop-lr92v5hwg45.qoder.website>；四张真实界面截图位于 `researchloop/site/screenshots/`。
