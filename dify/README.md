# OB梗图冷知识抽卡机

OceanBase 第六届 AI 生态 · Just for Fun · Dify。满分 20。questionId `600076`，subQuestionId `800513`。

玩家丢一句主题，机器打出一张文字梗图，梗图下面是一条能打开出处核对的冷知识。再说「再来一张」，同一会话里换一张。句子对不上牌库时，它说没摸到，不现编。

| 项 | 值 |
| --- | --- |
| 应用 | Dify Chatflow，入口用工作室自带对话页 |
| 必选 | Dify 负责改写、召回、分支、会话变量和吐槽 |
| 技术结合 | seekdb 做知识库向量存储。元数据库仍是 PostgreSQL |
| 不用 | 抽卡机不调用 PowerContext。同目录的插件骨架也不联网 |
| 提测 | 材料放在本目录。本提交没有官方提测 |

题面摘录在 `docs/YUQUE-Dify.md`。验收对照在 `docs/ACCEPTANCE.md`。

## 怎么玩

- `抽一张 seekdb 混合检索`：按原话检索。
- `来一张 SSR` 或 `来一张 R`：不限主题，只限稀有度。`SSR` 优先于 `SR`。
- `再来一张`：沿用上一张的主题，并排除上一张卡号。
- `换一张 TPC-C`：按新主题抽，同时排除上一张。
- `午饭吃什么`：拒答。

卡面固定含卡号、稀有度、主题、梗图、冷知识、出处和本局第几抽。主持人只在卡面下面加两行，不能改数字和出处。

## 分工

牌的原文和向量在 seekdb。Dify 1.10.1 的向量类型名叫 `oceanbase`，compose 里的服务器是 profile `seekdb`、镜像 `oceanbase/seekdb:latest`、端口 2881。Chatflow 没有单独的 seekdb 节点；「牌库检索」的结果就是 seekdb 里的 `text`。题面允许这种用法，见 `knowledge/cards/OB-015.md`。

同一会话的防重复放在 Dify 会话变量 `last_card_id`、`last_theme`、`draw_count`。新对话会忘记上一张，这是当前边界，不是跨会话记忆。

元数据库不要改到 seekdb。社区问题 [langgenius/dify#28992](https://github.com/langgenius/dify/issues/28992) 和 [langgenius/dify#31025](https://github.com/langgenius/dify/issues/31025) 报告过两边同时指向 seekdb 时出现 “Dataset not found”。

## 目录

```text
README.md                 本运行说明
docs/YUQUE-Dify.md        题面摘录
docs/PLAN.md              方案与风险
docs/ACCEPTANCE.md        验收对照
docs/CARD-RULES.md        牌面与抽卡规则
docs/EVIDENCE.md          哪些证据已在仓库，哪些要运行后才有
docs/seekdb.env.example   向量库环境变量增量
knowledge/cards/OB-*.md   16 张牌
dsl/ob-meme-card.yml      唯一的 Chatflow
scripts/check_deck.py     牌库与 DSL 代码检查
scripts/draw_card.py      全牌库本地抽卡
scripts/smoke.md          验证样例
```

## 环境

| 软件 | 版本 |
| --- | --- |
| Dify | 1.10.1。文档中的建表列、HNSW 参数和集合名按这个 tag 的 `OceanBaseVector` |
| compose 中的 seekdb | 上游写成 `oceanbase/seekdb:latest`，不在这里钉 digest |
| 元数据库 | compose 自带的 PostgreSQL 15，profile `postgresql` |
| 向量连接 | 主机 `seekdb`，端口 `2881`，用户 `root`，库 `dify_cards` |
| Embedding | 工作室里任意能处理中文的 Embedding。换模型后重建知识库 |
| 对话模型 | 任意已配置的聊天模型。只负责吐槽 |
| 重排 | 不需要 |
| Python | 3.11+，仅用于本目录的检查脚本。需要 PyYAML |

对话模型若走 MiniMax 的 OpenAI 兼容接口，基址以 MiniMax 控制台当前文档为准，常见写法是 `https://api.minimaxi.com/v1`。Key 只填在 Dify 的模型供应商里。

已知限制：

- DSL 里的数据集 id `00000000-0000-4000-8000-00000000ae05` 和模型名 `REPLACE_WITH_YOUR_CHAT_MODEL` 必须在导入后重绑。
- 本提交没有 Dify 运行截图、seekdb 查询结果或官方 TestRecord。
- 梗图是原文里的「画面 / 台词」，不是图片文件。
- seekdb 容器内存沿用 `SEEKDB_MEMORY_LIMIT=2G`。混合检索保持关闭。
- Dify 1.10.1 的 `OceanBaseVector` 在建表时会查看 `ob_vector_memory_limit_percentage`。这个参数不存在或无权修改时，索引会失败，样例 D 不应被算作通过。

## 从空环境到能玩

1. 取 Dify 1.10.1 源码，进入 `docker/`，用上游 `.env.example` 生成 `.env`。
2. 按 `docs/seekdb.env.example` 覆盖其中列出的键。把 `CHANGE_ME` 换成只存在于这台机器上的密码。
3. 启动：

   ```bash
   docker compose up -d
   ```

   `COMPOSE_PROFILES=seekdb,postgresql` 会拉起 seekdb 和 PostgreSQL，不会拉起 `oceanbase-ce`。两套服务都绑定 2881，不要一起开。

4. 等 seekdb 健康后建库。密码用客户端提示输入：

   ```bash
   mysql -h127.0.0.1 -P2881 -uroot -p
   ```

   ```sql
   CREATE DATABASE IF NOT EXISTS dify_cards;
   ```

5. 打开 Dify 控制台，配好 Embedding 和对话模型。不要把 Key 写进本仓库。
6. 新建知识库 `ob-meme-cards`，导入 `knowledge/cards/` 的 16 个文件。分段见 `knowledge/README.md`。等文档状态变为可用。
7. 导入 `dsl/ob-meme-card.yml`。在「牌库检索」里换成这个知识库，在「主持人吐槽」里换成对话模型，然后发布。
8. 用工作室对话页按 `scripts/smoke.md` 走样例 A 到 E。样例 D 确认 seekdb 里能读到牌的 `text`。

还没有对话模型、只想先看检索时：把「出牌」节点的回复暂时改成只含 `{{#6000765001.card_face#}}`。确认样例 A 的卡面后，把主持人那行加回去。没摸到的分支本来就不调用模型。

## 本地检查

```bash
python3 dify/scripts/check_deck.py
python3 dify/scripts/draw_card.py "抽一张 seekdb 混合检索"
```

第一条通过，只说明 16 张牌和 DSL 里的抽卡代码一致。它不能代替样例 D。


## 同目录的插件骨架

`manifest.yaml`、`main.py`、`provider/` 和 `tools/pc_ping.py` 是一份单独的 PowerContext Dify 插件骨架，不是这台抽卡机。`pc_ping` 只返回固定文本，不连接 PowerContext，也不读写 seekdb。抽卡机的入口是 `dsl/ob-meme-card.yml`。插件的安装与打包说明在 `docs/PLUGIN.md`。

## 密钥

配置示例只用 `CHANGE_ME` 和 `REPLACE_WITH_YOUR_CHAT_MODEL`。仓库不提供、也不接受真实 API Key、数据库密码或 Token。上游 Dify `.env.example` 里的默认口令不要抄进本目录。
