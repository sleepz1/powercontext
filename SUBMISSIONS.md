# 分题交付状态

代码基线：`oceanbase/powercontext` 的 `2026-competition-ecosystem`，提交 `d647275c308e09b7b623f322a26f5c4e85734fb0`。
本地工作分支：04/06 在 `codex/ecosystem-03-04-06`，03 在 `feature/researchloop-qoder`。三题使用各自官方目录，分别提交材料。

| 题目 | 材料位置 | 当前状态 |
| --- | --- | --- |
| 03 Qoder 提效项目 | qoder/researchloop/（README、DEVLOG、functions、server、src、site、results/seekdb-verify.json） | 核心应用已完成并在本机跑通真实 seekdb：30/30 端到端断言通过、生产构建通过；作品介绍静态站已公开（https://yantu-researchloop-lr92v5hwg45.qoder.website），四张真实界面截图已补入 site/screenshots/ |
| 04 端侧推理 + 混合检索 | stepfun/ 全部源码、README、output/pdf/technical-report.pdf、results/ | 2026-10-28 22:06 独立提测；平台执行成功，20.000 / 20 分 |
| 06 高德周边 Skill | gaode/SKILL.md | 2026-10-28 22:04 独立提测；平台执行成功，20.000 / 20 分 |

04 源码不包含 node_modules、模型权重、ONNX 运行时、数据库或密码；按 README 安装依赖和下载固定模型即可复现。06 上传单独的 SKILL.md，不上传项目 ZIP 代替该文件。

04 的 WebGPU 一致性检查在本机发现偏差并回退 WASM，报告中没有把回退后的性能称为 GPU 加速。03 的准备材料不能替代 Qoder 真实开发证据。

私有目标仓库：`https://github.com/geshanchang-create/powercontext-2026`，当前成果已推送至工作分支。官方基线分支单独保留。

04、06 实际提测入口使用报名登记的团队仓库 `https://github.com/sleepz1/powercontext`，分支 `feature/ecosystem-ae04-ae06`，Commit `ba9e23480278638b9d4b393fb78d7d087313dde2`。其文件树与本地 `69ecb48` 完全一致；未修改主分支。两题分别进入各自题目详情页提测，各 1 次。

记录页：[04](https://open.oceanbase.com/train/TestRecord?questionId=600073) · [06](https://open.oceanbase.com/train/TestRecord?questionId=600074)。截图保存在本机提交材料目录 `E:/project/submissions/ecosystem-03-04-06/receipts/`。

03 尚未提测；主体开发、真实数据库验收、桌面浏览器操作与公开站点发布已完成。
