"""Validate the deck and the committed DSL. Exit 0 when the package is consistent."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cardlib import deck_dir, draw
from render_dsl import DSL_PATH, render

ROOT = Path(__file__).resolve().parents[1]
DATASET_TOKEN = "00000000-0000-4000-8000-00000000ae05"


def exec_committed_nodes(text):
    import yaml

    from cardlib import load_chunks

    doc = yaml.safe_load(text)
    nodes = {node["id"]: node["data"] for node in doc["workflow"]["graph"]["nodes"]}
    rewrite_ns = {}
    pick_ns = {}
    exec(nodes["6000762001"]["code"], rewrite_ns, rewrite_ns)
    exec(nodes["6000765001"]["code"], pick_ns, pick_ns)
    chunks = load_chunks()
    info = rewrite_ns["main"]("抽一张 seekdb 混合检索", "")
    result = pick_ns["main"](
        "抽一张 seekdb 混合检索",
        chunks,
        "",
        "",
        0,
        info["redraw"],
        info["rarity"],
        info["search_query"],
    )
    if result["card_id"] != "OB-001":
        return [f"DSL code node drew {result['card_id']}"]
    return []
BANNED = (
    "difyai" + "123456",
    "sk" + "-",
    "AK" + "IA",
    "BEGIN " + "PRIVATE",
    "BEGIN " + "RSA",
    "BEGIN " + "OPENSSH",
    "xoxb" + "-",
    "gh" + "p_",
)


def parse_file(text):
    fields = {}
    for line in text.splitlines():
        if line.startswith("# "):
            break
        if line.startswith("---") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
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

    card_id = fields.get("card_id", "")
    if not card_id.startswith("OB-"):
        return None
    keywords = [item.strip() for item in fields.get("keywords", "").split(",") if item.strip()]
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


def main():
    errors = []
    cards = []
    paths = sorted(deck_dir().glob("OB-*.md"))
    if len(paths) < 12:
        errors.append(f"need at least 12 cards, found {len(paths)}")
    seen = set()
    for path in paths:
        text = path.read_text(encoding="utf-8")
        if "\n\n\n" in text:
            errors.append(f"{path.name} has a blank-line run; keep one file one chunk")
        card = parse_file(text)
        if card is None:
            errors.append(f"{path.name} did not parse")
            continue
        if path.stem != card["card_id"]:
            errors.append(f"{path.name} card_id is {card['card_id']}")
        if card["card_id"] in seen:
            errors.append(f"duplicate {card['card_id']}")
        seen.add(card["card_id"])
        if card["rarity"] not in {"R", "SR", "SSR"}:
            errors.append(f"{card['card_id']} rarity {card['rarity']}")
        if not card["theme"] or not card["keywords"] or not card["title"]:
            errors.append(f"{card['card_id']} missing theme, keywords, or title")
        if not card["fact"] or "画面" not in card["meme"] or "台词" not in card["meme"]:
            errors.append(f"{card['card_id']} fact or meme section is incomplete")
        if not card["source_url"].startswith("https://") or not card["source_title"]:
            errors.append(f"{card['card_id']} source is incomplete")
        cards.append(card)

    expected = {
        "抽一张 seekdb 混合检索": "OB-001",
        "来一张 SSR": "OB-001",
        "来一张 R": "OB-004",
    }
    for query, card_id in expected.items():
        result, _info = draw(query)
        if result["picked"] != "yes" or result["card_id"] != card_id:
            errors.append(f"{query!r} -> {result['card_id']} picked={result['picked']}, want {card_id}")
        if card_id == "OB-001" and "707,351,007" in result["card_face"]:
            errors.append("OB-001 face leaked the TPC-C figure")

    redraw, info = draw("再来一张", last_card_id="OB-001", last_theme="seekdb", draw_count=1)
    if redraw["card_id"] != "OB-002" or "第 2 抽" not in redraw["card_face"]:
        errors.append(f"redraw -> {redraw['card_id']} search={info['search_query']}")
    if redraw["theme"] != "seekdb":
        errors.append("redraw left the seekdb theme")

    switched, _info = draw("换一张 TPC-C", last_card_id="OB-001", last_theme="seekdb", draw_count=1)
    if switched["card_id"] != "OB-007":
        errors.append(f"theme switch -> {switched['card_id']}")

    missed, _info = draw("午饭吃什么")
    if missed["picked"] != "no" or missed["card_id"]:
        errors.append("off-deck query should miss")
    if "707" in missed["card_face"] or "tpmC" in missed["card_face"]:
        errors.append("miss path invented a fact")

    ssr = [card["card_id"] for card in cards if card["rarity"] == "SSR"]
    if ssr != ["OB-001", "OB-007", "OB-013"]:
        errors.append(f"SSR set changed: {ssr}")

    rendered = render()
    committed = DSL_PATH.read_text(encoding="utf-8") if DSL_PATH.exists() else ""
    if committed != rendered:
        errors.append("dsl/ob-meme-card.yml is stale; run python3 dify/scripts/render_dsl.py")
    else:
        errors.extend(exec_committed_nodes(committed))
    for token in ("kind: app", "advanced-chat", "knowledge-retrieval", "REPLACE_WITH_YOUR_CHAT_MODEL", DATASET_TOKEN):
        if token not in committed:
            errors.append(f"DSL missing {token}")

    blob_parts = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        blob_parts.append(path.read_text(encoding="utf-8"))
    blob = "\n".join(blob_parts)
    for token in BANNED:
        if token in blob:
            errors.append(f"banned token present: {token}")

    if errors:
        print("\n".join(errors))
        return 1
    print(f"deck ok: {len(cards)} cards, dsl matches cardlib")
    return 0


if __name__ == "__main__":
    sys.exit(main())
