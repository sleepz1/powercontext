# 牌库

dataset 名称：`ob-meme-cards`。把 `cards/` 下 16 个文件一次导入。不要把本 README 导入知识库。

分段：自定义。分隔符使用三个换行 `\n\n\n`，最大长度 2000，重叠 0。每张牌应是 1 个分段。分段多于 1 时加大最大长度，直到 `card_id` 和「冷知识」出现在同一段。

Embedding 使用工作室里已有、能处理中文的模型。维度由该模型的第一条向量决定。更换 Embedding 后重建这个知识库。

索引完成前，Dify 文档状态应变为可用。索引由 worker 执行，只看 api 容器健康不够。

| 卡号 | 稀有度 | 主题 | 标题 |
| --- | --- | --- | --- |
| OB-001 | SSR | seekdb | 一条 SQL，四种检索一口锅 |
| OB-002 | SR | seekdb | MySQL 协议，但是能嵌进进程 |
| OB-003 | SR | seekdb | 实验砸了，就丢掉那一叉 |
| OB-004 | R | seekdb | 1523 这个数字，别当成你自己跑出来的 |
| OB-005 | SR | seekdb | 写入先回家，索引在后面追 |
| OB-006 | R | seekdb | 一条 pip，或者一杯 7 天的云 |
| OB-007 | SSR | oceanbase | 七亿后面还有六位数 |
| OB-008 | SR | oceanbase | 开源日是六月一日，协议不是 Apache |
| OB-009 | R | oceanbase | 50% 和 10 倍，是发布会的句子 |
| OB-010 | SR | oceanbase | 社区版是子集，不是换皮 |
| OB-011 | SR | dify | 元数据库终于能说 MySQL 了 |
| OB-012 | SR | dify | profile 叫 seekdb，驱动仍叫 oceanbase |
| OB-013 | SSR | dify | 牌进库之后，表名是可以算出来的 |
| OB-014 | R | contest | 满分二十，DSL 里却没有牌 |
| OB-015 | SR | dify | 向量库已经在干活，就不必再画一个节点 |
| OB-016 | R | contest | 五百九十美元是奖品，不是分数 |

规则见 `../docs/CARD-RULES.md`。
