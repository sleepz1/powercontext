# DSL

只导入这一个文件：

1. `ob-meme-card.yml`

没有第二个文件，也没有导入顺序。形式是 Dify Chatflow（`kind: app`，`mode: advanced-chat`，`version: 0.6.0`）。目标运行时是 Dify 1.10.1 自托管；1.11.2 与 1.13.0 的 compose 仍包含 `seekdb` profile，但本文件里的表名和列说明按 1.10.1 的 `OceanBaseVector` 阅读。

它由 `../scripts/render_dsl.py` 从 `../scripts/cardlib.py` 生成，不是某次 Dify 工作室的导出件。若某个 Dify 版本拒绝导入，按 `../docs/CARD-RULES.md` 在工作室里搭同样的九个节点，代码仍以 `cardlib.py` 为准。重新生成：

```bash
python3 dify/scripts/render_dsl.py
python3 dify/scripts/check_deck.py
```

## 导入后必做

1. 打开节点「牌库检索」，去掉占位数据集 `00000000-0000-4000-8000-00000000ae05`，改选知识库 `ob-meme-cards`。
2. 打开节点「主持人吐槽」，把 `REPLACE_WITH_YOUR_CHAT_MODEL` 换成工作室里已配置的对话模型。供应商占位是 `langgenius/openai_api_compatible/openai_api_compatible`。若该插件未安装，直接改成你已安装的供应商。
3. 保存并发布。应用入口用 Dify 自带的对话页即可，不需要另做前端。

占位符留在仓库里是为了让导入动作有一个明确的重绑点。不要在 YAML 里写入数据集的真实访问密钥；Dify 的数据集密钥不属于这个文件。

## 节点

开场 → 改写检索词 → 牌库检索 → 抽一张 → 摸到牌了吗。摸到则记下会话变量，再请主持人吐槽并出牌。没摸到则只回代码节点印好的拒答，不调用模型。

`top_k` 为 8，关闭重排，不设分数阈值。
