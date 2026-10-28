# 分题交付状态

代码基线：`oceanbase/powercontext` 的 `2026-competition-ecosystem`，提交 `d647275c308e09b7b623f322a26f5c4e85734fb0`。
本地工作分支：`codex/ecosystem-03-04-06`。三题使用各自官方目录，分别提交材料。

| 题目 | 材料位置 | 当前状态 |
| --- | --- | --- |
| 03 Qoder 提效项目 | qoder/PLAN.md、README.md、QODER_PROMPT.md | CLI 已安装；等待本人账号授权后由 Qoder 进行主体开发、保存记录、发布 Sites |
| 04 端侧推理 + 混合检索 | stepfun/ 全部源码、README、output/pdf/technical-report.pdf、results/ | 已实现并通过真实数据库、浏览器与生产构建验证；有完整原始实测数据 |
| 06 高德周边 Skill | gaode/SKILL.md | 单文件已完成、通过 Skill 格式校验；评测环境负责提供高德 MCP 与 Key |

04 源码不包含 node_modules、模型权重、ONNX 运行时、数据库或密码；按 README 安装依赖和下载固定模型即可复现。06 上传单独的 SKILL.md，不上传项目 ZIP 代替该文件。

04 的 WebGPU 一致性检查在本机发现偏差并回退 WASM，报告中没有把回退后的性能称为 GPU 加速。03 的准备材料不能替代 Qoder 真实开发证据。

私有目标仓库：`https://github.com/geshanchang-create/powercontext-2026`，当前成果已推送至工作分支。官方基线分支单独保留。

**尚未上传到比赛平台、未获得官方测试结果或分数。03 仍需验证本机 Qoder CLI 授权，再完成主要开发、记录和 Sites 发布。**
