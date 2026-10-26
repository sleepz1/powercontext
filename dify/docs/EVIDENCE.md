# 证据

核对日期：2026-10-26。未官方提测。

| # | 证据 | 状态 | 在哪里 |
| --- | --- | --- | --- |
| 1 | 语雀题面摘录 | 已收入 | `docs/YUQUE-Dify.md` |
| 2 | questionId / subQuestionId | 按任务指定记为 `600076` / `800513` | `README.md`。没有题板登录截图 |
| 3 | Dify DSL | 已生成可导入的 Chatflow 文本，尚未从线上工作室导出 | `dsl/ob-meme-card.yml` |
| 4 | 运行说明 | 已写 | `README.md`、`docs/seekdb.env.example` |
| 5 | 验证样例 | 步骤和本地期望已写。Dify 与 seekdb 的运行截图、节点日志不在本提交里 | `scripts/smoke.md` |
| 6 | 牌库 | 16 张，每张有出处 | `knowledge/cards/` |
| 7 | 规则自测 | `python3 dify/scripts/check_deck.py` 覆盖全牌库与 DSL 内代码 | 本地运行，不代替 seekdb |
| 8 | seekdb 读写 | 核对 SQL 已写，本提交没有执行结果 | `scripts/smoke.md` 样例 D |
| 9 | 公开体验 URL | 无 | |
| 10 | 官方 TestRecord | 未提测 | |

密钥不入库。运行 seekdb 之后得到的密码、Cookie 和模型 Key 只留在本地 Dify 与 shell 环境。
