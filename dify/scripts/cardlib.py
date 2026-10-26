"""Deck rules for the OB meme trivia card machine.

`rewrite_main` and `pick_main` are copied into the Dify code nodes by
`render_dsl.py`. Keep them self-contained: no module globals, no imports.
"""

from __future__ import annotations

import inspect
from pathlib import Path


def rewrite_main(query, last_theme):
    def is_redraw(text):
        keys = ("再来一张卡", "再来一张", "换一张", "再抽一张", "下一张", "再抽", "再来")
        return any(key in text for key in keys)

    def detect_rarity(text):
        upper = text.upper()
        if "SSR" in upper:
            return "SSR"
        if "SR" in upper:
            return "SR"
        padded = " " + upper + " "
        if " R " in padded or (upper.endswith("R") and not upper.endswith("SR")):
            return "R"
        return ""

    def is_generic(text, rarity):
        keys = (
            "再来一张卡",
            "再来一张",
            "换一张",
            "再抽一张",
            "下一张",
            "再抽",
            "再来",
            "随机来一张",
            "抽一张",
            "抽卡",
            "来一张",
            "随机",
            "抽",
        )
        cleaned = text
        for key in keys:
            cleaned = cleaned.replace(key, " ")
        if rarity:
            cleaned = cleaned.replace(rarity, " ")
            cleaned = cleaned.replace(rarity.lower(), " ")
        leftover = []
        for ch in cleaned:
            if ch.isspace() or ch in "，。！？、~～!?,.":
                continue
            leftover.append(ch)
        return "".join(leftover) == ""

    text = (query or "").strip()
    rarity = detect_rarity(text)
    redraw = "yes" if is_redraw(text) else "no"
    generic = is_generic(text, rarity)
    theme = (last_theme or "").strip()
    if redraw == "yes" and generic and theme:
        search = theme
    elif generic or text == "":
        search = "OceanBase seekdb Dify 冷知识"
    else:
        search = text
    return {"search_query": search, "redraw": redraw, "rarity": rarity}


def pick_main(query, chunks, last_card_id, last_theme, draw_count, redraw, rarity, search_query):
    def as_list(value):
        if value is None:
            return []
        if isinstance(value, list):
            return value
        if isinstance(value, tuple):
            return list(value)
        return [value]

    def chunk_text(item):
        if item is None:
            return ""
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            for key in ("content", "page_content", "text", "sign_content"):
                found = item.get(key)
                if found:
                    return str(found)
        return str(item)

    def chunk_semantic(item):
        if isinstance(item, dict):
            meta = item.get("metadata") or {}
            if isinstance(meta, dict):
                raw = meta.get("score", 0)
                try:
                    return float(raw)
                except Exception:
                    return 0.0
        return 0.0

    def parse_card(text):
        if "card_id:" not in text:
            return None
        fields = {}
        for line in text.splitlines():
            if line.startswith("# "):
                break
            if line.startswith("---") or ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
        card_id = fields.get("card_id", "")
        if not card_id.startswith("OB-"):
            return None
        title = ""
        for line in text.splitlines():
            if line.startswith("# "):
                title = line[2:].strip()
                break

        def section(name):
            marker = "## " + name
            start = text.find(marker)
            if start < 0:
                return ""
            rest = text[start + len(marker) :].lstrip("\n")
            nxt = rest.find("\n## ")
            if nxt >= 0:
                rest = rest[:nxt]
            return rest.strip()

        keywords = []
        for item in fields.get("keywords", "").split(","):
            word = item.strip()
            if word:
                keywords.append(word)
        return {
            "card_id": card_id,
            "rarity": fields.get("rarity", ""),
            "theme": fields.get("theme", ""),
            "keywords": keywords,
            "source_title": fields.get("source_title", ""),
            "source_url": fields.get("source_url", ""),
            "title": title,
            "fact": section("冷知识"),
            "meme": section("梗图"),
        }

    def is_generic(text, rarity_token):
        keys = (
            "再来一张卡",
            "再来一张",
            "换一张",
            "再抽一张",
            "下一张",
            "再抽",
            "再来",
            "随机来一张",
            "抽一张",
            "抽卡",
            "来一张",
            "随机",
            "抽",
        )
        cleaned = text
        for key in keys:
            cleaned = cleaned.replace(key, " ")
        if rarity_token:
            cleaned = cleaned.replace(rarity_token, " ")
            cleaned = cleaned.replace(rarity_token.lower(), " ")
        leftover = []
        for ch in cleaned:
            if ch.isspace() or ch in "，。！？、~～!?,.":
                continue
            leftover.append(ch)
        return "".join(leftover) == ""

    def score_card(card, text):
        blob = (text or "").lower()
        if not blob.strip():
            return 0
        hits = 0
        for keyword in card["keywords"]:
            if keyword.lower() in blob:
                hits += 1
        if card["theme"].lower() in blob:
            hits += 1
        if card["card_id"].lower() in blob:
            hits += 1
        return hits

    def current_draw(value):
        try:
            return int(value)
        except Exception:
            return 0

    def miss_face(reason):
        return "\n".join(
            [
                "🃏 OB梗图冷知识抽卡机",
                "━━━━━━━━━━━━━━━━",
                "这局没摸到牌。",
                "",
                reason,
                "",
                "试试：抽一张 seekdb 混合检索 / 来一张 SSR / 再来一张",
                "━━━━━━━━━━━━━━━━",
            ]
        )

    def format_face(card, draw_n, search, note, repeated):
        lines = [
            "🃏 OB梗图冷知识抽卡机",
            "━━━━━━━━━━━━━━━━",
            card["card_id"] + " · " + card["rarity"] + " · " + card["theme"],
            card["title"],
            "",
            "【梗图】",
            card["meme"].strip(),
            "",
            "【冷知识】",
            card["fact"].strip(),
            "",
            "【出处】",
            card["source_title"],
            card["source_url"],
            "",
            "【本局】第 " + str(draw_n) + " 抽 · 检索「" + (search or "") + "」",
        ]
        if note:
            lines.append(note)
        if repeated:
            lines.append("召回里能出的就剩这一张，本抽与上一张相同。")
        lines.append("━━━━━━━━━━━━━━━━")
        return "\n".join(lines)

    def empty(reason, theme, draw_n):
        return {
            "card_id": "",
            "theme": theme or "",
            "rarity": "",
            "card_face": miss_face(reason),
            "host_brief": "没摸到牌。不要编造冷知识。",
            "picked": "no",
            "source_url": "",
            "next_draw_count": draw_n,
        }

    text = (query or "").strip()
    theme = (last_theme or "").strip()
    rarity_token = (rarity or "").strip()
    search = search_query or ""
    draw_n = current_draw(draw_count)
    parsed = []
    for index, item in enumerate(as_list(chunks)):
        card = parse_card(chunk_text(item))
        if not card:
            continue
        card["semantic"] = chunk_semantic(item)
        card["order"] = index
        parsed.append(card)
    if not parsed:
        return empty("召回片段里没有 card_id。请把知识库调成一文件一块后再抽。", theme, draw_n)

    redraw_yes = redraw == "yes"
    generic = is_generic(text, rarity_token)
    note = ""
    pool = parsed
    if redraw_yes and generic and theme:
        themed = [card for card in pool if card["theme"] == theme]
        if themed:
            pool = sorted(themed, key=lambda card: card["card_id"])
        else:
            pool = sorted(pool, key=lambda card: card["card_id"])
            note = "这一轮召回里没有上一主题的牌，改从召回结果里抽。"
    elif generic:
        pool = sorted(pool, key=lambda card: card["card_id"])
    else:
        matched = [card for card in pool if score_card(card, text) > 0]
        if not matched:
            return empty("牌库只有 OceanBase、seekdb、Dify 和这届比赛。这句话对不上任何一张。", theme, draw_n)
        matched.sort(key=lambda card: (-score_card(card, text), -card["semantic"], card["card_id"]))
        pool = matched

    if rarity_token:
        rare = [card for card in pool if card["rarity"] == rarity_token]
        if rare:
            pool = rare
        else:
            note = "牌库里没有这个稀有度，改发召回里最接近的一张。"

    last_id = (last_card_id or "").strip()
    if last_id:
        rest = [card for card in pool if card["card_id"] != last_id]
        if rest:
            pool = rest
    chosen = pool[0]
    repeated = chosen["card_id"] == last_id
    face = format_face(chosen, draw_n + 1, search, note, repeated)
    return {
        "card_id": chosen["card_id"],
        "theme": chosen["theme"],
        "rarity": chosen["rarity"],
        "card_face": face,
        "host_brief": "卡面已印好。只写吐槽，不要改数字、版本或出处。",
        "picked": "yes",
        "source_url": chosen["source_url"],
        "next_draw_count": draw_n + 1,
    }


def node_source(*functions):
    parts = [inspect.getsource(fn).rstrip() for fn in functions]
    return "\n\n".join(parts) + "\n"


def rewrite_node_code():
    return node_source(rewrite_main) + (
        "\n\ndef main(query, last_theme):\n    return rewrite_main(query, last_theme)\n"
    )


def pick_node_code():
    return node_source(pick_main) + (
        "\n\ndef main(query, chunks, last_card_id, last_theme, draw_count, redraw, rarity, search_query):\n"
        "    return pick_main(query, chunks, last_card_id, last_theme, draw_count, redraw, rarity, search_query)\n"
    )


def deck_dir():
    return Path(__file__).resolve().parents[1] / "knowledge" / "cards"


def load_chunks(cards_dir=None):
    root = Path(cards_dir) if cards_dir else deck_dir()
    chunks = []
    for path in sorted(root.glob("OB-*.md")):
        chunks.append({"content": path.read_text(encoding="utf-8"), "metadata": {"score": 0.0}})
    return chunks


def draw(query, last_card_id="", last_theme="", draw_count=0, chunks=None):
    info = rewrite_main(query, last_theme)
    result = pick_main(
        query,
        load_chunks() if chunks is None else chunks,
        last_card_id,
        last_theme,
        draw_count,
        info["redraw"],
        info["rarity"],
        info["search_query"],
    )
    return result, info
