# 验证样例

本地命令只证明牌面规则。它不连接 Dify，也不连接 seekdb。Dify 路径以本节后半的期望为准。

重置线上状态：新开一个对话。会话变量 `last_card_id`、`last_theme`、`draw_count` 回到空和 0。不要在旧对话里重放样例 A。

先跑规则检查：

```bash
python3 dify/scripts/check_deck.py
```

期望输出以 `deck ok: 16 cards` 开头，退出码 0。

## 样例 A：主题抽卡

初始：新会话，知识库 16 张牌均已索引。

输入：`抽一张 seekdb 混合检索`

本地全牌库结果：

```text
🃏 OB梗图冷知识抽卡机
━━━━━━━━━━━━━━━━
OB-001 · SSR · seekdb
一条 SQL，四种检索一口锅

【梗图】
画面：向量、全文、标量和 SQL 四根箭头插进同一口锅。
台词：别人的 RAG 是拼盘，这口锅一锅出。

【冷知识】
seekdb README 把混合检索写成一条 SQL。示例同时用 `l2_distance`、`MATCH(content) AGAINST(...)`，再加上 `author_id`、`created_at` 这类标量条件，放进同一个执行计划，不在客户端做 N+1 归并。那是示例查询，不是仓库里预置的一张 `docs` 表。

【出处】
oceanbase/seekdb README
https://github.com/oceanbase/seekdb

【本局】第 1 抽 · 检索「抽一张 seekdb 混合检索」
━━━━━━━━━━━━━━━━
```

本地命令：

```bash
python3 dify/scripts/draw_card.py "抽一张 seekdb 混合检索"
```

Dify 期望：

- 卡面含 `OB-001`、`SSR`、`seekdb`，冷知识出现 `l2_distance` 与 `MATCH`，出处 URL 为 `https://github.com/oceanbase/seekdb`。
- 卡面下方另有主持人两行，且没有新的 tpmC、版本号或协议名。
- 节点「牌库检索」的结果非空，片段内能看到 `card_id: OB-001`。
- 引用开关开着，回复可以展开召回片段。

若召回的前 8 段里没有 OB-001，先确认分段没有把 `card_id` 和正文拆开，再把该节点的 `top_k` 调到 16 后重试。

## 样例 B：再来一张

紧接样例 A，不新开对话。

输入：`再来一张`

本地命令与期望：

```bash
python3 dify/scripts/draw_card.py "再来一张" --last-card-id OB-001 --last-theme seekdb --draw-count 1
```

本地全牌库抽到 `OB-002`，卡面含「第 2 抽」，主题仍是 `seekdb`。

Dify 期望：`card_id` 不是 `OB-001`，`theme` 仍是 `seekdb`，冷知识与对应牌文件一致。卡号可以不是 `OB-002`，因为线上只在本次召回的牌里按卡号取下一张。若又打出 OB-001，说明召回里没有第二张 `theme: seekdb` 的牌，按样例 A 的分段和 `top_k` 处理。

## 样例 C：牌库之外

新会话或旧会话都可以。

输入：`午饭吃什么`

本地与 Dify 都期望卡面以「这局没摸到牌」开头，不出现 `tpmC`、`707` 或任何牌的出处 URL。此分支不应出现模型生成的冷知识。本地主题和卡号为空。

```bash
python3 dify/scripts/draw_card.py "午饭吃什么"
```

## 样例 D：seekdb 里真有这些牌

在 Dify 把 16 个文件索引完成之后做。密码用交互提示输入，不要写进命令行，也不要写回仓库。

```bash
mysql -h127.0.0.1 -P2881 -uroot -p
```

```sql
USE dify_cards;
SHOW TABLES LIKE 'vector_index_%';
SELECT COUNT(*) FROM vector_index_替换成实际表名_node;
SELECT id, LEFT(text, 160) FROM vector_index_替换成实际表名_node LIMIT 3;
```

期望：

- 库 `dify_cards` 存在。这是 `OCEANBASE_VECTOR_DATABASE`，不是元数据库。
- 至少一张表匹配 `vector_index_%_node`。首次建库时，表名是 `vector_index_` 加上数据集 UUID 去掉横线、再加 `_node`。
- `COUNT(*)` 不小于分段数。一文件一段时就是 16。
- `text` 前 160 个字符里能看到某张牌的 `card_id`。

容器尚未写入时，`SHOW TABLES` 没有这张表。把 api 与 worker 里创建集合的报错留在本地。常见的一处是 `ob_vector_memory_limit_percentage` 读不到或无权修改；出现这条时，向量库还没有承担存储。

可选的混合检索不要在这次验收里打开。`OCEANBASE_ENABLE_HYBRID_SEARCH` 保持 `false`。

## 样例 E：建议问题里的另外两句

新会话输入 `来一张 SSR`。本地抽到 OB-001，检索词是「OceanBase seekdb Dify 冷知识」。Dify 期望打出一张 `rarity: SSR` 的牌，卡面与该文件一致。三张 SSR 是 OB-001、OB-007、OB-013。

`来一张 R` 在本地抽到 OB-004。Dify 期望 `rarity` 为 `R`。
