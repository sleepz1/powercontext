# 实施方案

作品：OB梗图冷知识抽卡机。赛题 Just for Fun，满分 20。questionId `600076`，subQuestionId `800513`。

## 玩法

玩家说主题、稀有度或「再来一张」。Chatflow 从知识库召回牌面，代码节点按牌库原文印出梗图和冷知识，对话模型只追加两行吐槽。对不上牌库的话直接说没摸到，不生成一条新的「冷知识」。

## 分工

| 组件 | 做什么 | 不做什么 |
| --- | --- | --- |
| Dify Chatflow | 改写检索词、知识库召回、条件分支、会话变量、主持人吐槽、回复 | 不保存牌库正文 |
| seekdb | Dify 的向量库。牌的向量和原文写入 `id` / `vector` / `text` / `metadata` | 不做元数据库 |
| PostgreSQL | Dify 1.10.1 默认元数据库 | 不存放牌面向量 |
| 会话变量 | 同一会话的上一张卡号、主题和已抽次数 | 不跨会话。本作品不接 PowerContext |

元数据库保持 PostgreSQL，是为了避开 seekdb 同时做元数据库和向量库时社区报告过的 “Dataset not found”（[langgenius/dify#28992](https://github.com/langgenius/dify/issues/28992)、[langgenius/dify#31025](https://github.com/langgenius/dify/issues/31025)）。题面允许 seekdb 只承担向量存储。

## 交付

- `dsl/ob-meme-card.yml`：Chatflow。数据集 id 和模型名是占位，导入后重绑。
- `knowledge/cards/`：16 张牌，一文件一张。
- `docs/seekdb.env.example`：向量库连到 seekdb 容器的环境变量增量。
- `scripts/check_deck.py`：校验牌面，并执行 DSL 里的代码节点。
- `scripts/draw_card.py`：对全牌库做一次本地抽卡。
- `scripts/smoke.md`：给评审走的样例。

## 风险

| 风险 | 处理 |
| --- | --- |
| DSL 不是某次工作室导出 | 结构按 Dify `kind: app` / `advanced-chat` 写，代码节点与 `cardlib.py` 同源。导入后重绑知识库和模型 |
| seekdb 镜像标签是上游 compose 里的 `latest` | 跑起来后把镜像 digest 记在本地证据里，不写进仓库 |
| `OceanBaseVector` 会读 `ob_vector_memory_limit_percentage` | 索引失败就把 api 与 worker 日志留在本地，不要把没建成的表说成已经写入 |
| 混合检索要求 OceanBase ≥ 4.3.5.1 | 默认关闭 |
| 没有对话模型 | 没摸到牌的分支不调用模型。出牌分支可暂时只回卡面，用来先确认检索 |

## 不做

- 不官方提测，不写 TestRecord。
- 不把 API Key、数据库密码或 Token 放进 git。
- 不接一个会失败的 PowerContext HTTP 节点来凑第二种技术。
- 不把上游示例密码写进配置。
