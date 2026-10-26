"""Draw against the on-disk deck. This checks the rules; it does not talk to seekdb."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cardlib import draw


def main():
    parser = argparse.ArgumentParser(description="Draw one OB meme trivia card from the local deck.")
    parser.add_argument("query", help="Player text, for example: 抽一张 seekdb 混合检索")
    parser.add_argument("--last-card-id", default="")
    parser.add_argument("--last-theme", default="")
    parser.add_argument("--draw-count", type=int, default=0)
    args = parser.parse_args()
    result, info = draw(
        args.query,
        last_card_id=args.last_card_id,
        last_theme=args.last_theme,
        draw_count=args.draw_count,
    )
    print(result["card_face"])
    print("---")
    print(
        "picked={picked} card_id={card_id} theme={theme} rarity={rarity} "
        "search={search} redraw={redraw}".format(
            picked=result["picked"],
            card_id=result["card_id"] or "-",
            theme=result["theme"] or "-",
            rarity=result["rarity"] or "-",
            search=info["search_query"],
            redraw=info["redraw"],
        )
    )
    return 0 if result["card_face"] else 1


if __name__ == "__main__":
    sys.exit(main())
