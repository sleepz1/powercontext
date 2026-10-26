# Copyright (c) 2026 OceanBase.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Offline lexical ranking of stored PDF page texts.

Financial questions often ask for a metric whose evidence page does not repeat the
question wording. Primary statements, segment tables, customer concentration, and
litigation notes are detected from the page itself and preferred when the question
asks for that kind of evidence.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset([
    "a",
    "an",
    "the",
    "and",
    "or",
    "for",
    "of",
    "to",
    "in",
    "on",
    "at",
    "by",
    "from",
    "with",
    "as",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "what",
    "which",
    "who",
    "how",
    "why",
    "when",
    "where",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "i",
    "we",
    "you",
    "it",
    "its",
    "our",
    "your",
    "this",
    "that",
    "these",
    "those",
    "please",
    "has",
    "have",
    "had",
    "any",
    "not",
    "if",
    "then",
    "than",
    "per",
    "about",
    "into",
    "over",
    "under",
    "such",
    "their",
    "there",
    "also",
    "other",
    "more",
    "most",
    "may",
    "will",
    "just",
])
_BOILER = frozenset([
    "answer",
    "question",
    "respond",
    "response",
    "calculate",
    "calculated",
    "calculation",
    "using",
    "shown",
    "detail",
    "details",
    "assume",
    "assuming",
    "assumption",
    "perspective",
    "analyst",
    "define",
    "defined",
    "definition",
    "only",
    "use",
    "within",
    "give",
    "relying",
    "investment",
    "million",
    "millions",
    "usd",
    "fy",
    "please",
    "state",
    "whether",
    "explain",
    "describe",
    "provide",
    "following",
    "based",
    "including",
    "include",
    "primarily",
    "profile",
    "useful",
    "metric",
    "company",
    "like",
    "then",
])
_INCOME_TITLES = (
    "consolidatedstatementofincome",
    "consolidatedstatementsofincome",
    "consolidatedstatementofoperations",
    "consolidatedstatementsofoperations",
    "consolidatedstatementofearnings",
    "consolidatedstatementsofearnings",
    "consolidatedincomestatement",
    "consolidatedstatementsofprofit",
)
_CASH_TITLES = (
    "consolidatedstatementofcashflow",
    "consolidatedstatementsofcashflow",
)
_BALANCE_TITLES = (
    "consolidatedbalancesheet",
    "consolidatedbalancesheets",
    "consolidatedstatementoffinancialposition",
    "consolidatedstatementsoffinancialposition",
)
_TITLE_TAILS = (
    "year",
    "ended",
    "december",
    "fiscal",
    "million",
    "dollar",
    "atdec",
    "except",
    "january",
    "september",
    "june",
    "march",
)
_AMOUNTS = re.compile(r"\d{1,3}(?:,\d{3})+|\(\d[\d,]*\)")
_REGION = re.compile(
    r"north america|latin america|south america|united states|europe|asia pacific|middle east|africa|china|australia|new zealand",
    re.IGNORECASE,
)
_REVENUE_SHARE = re.compile(
    r"\d+\s*% of (?:our )?(?:consolidated )?(?:net )?(?:total )?(?:revenue|revenues)",
    re.IGNORECASE,
)
_MA = re.compile(r"m\s*&\s*a\b", re.IGNORECASE)
_DA = re.compile(r"d\s*&\s*a\b", re.IGNORECASE)
_CAPEX = re.compile(r"\bcapex\b", re.IGNORECASE)
_PL = re.compile(r"\bp&l\b", re.IGNORECASE)
_INCOME_INTENT = re.compile(
    r"income statement|statements of income|statement of income|statement of operations|"
    r"statements of operations|statements of earnings|p&l|profit and loss|operating income|"
    r"operating profit|\bebitda\b|gross profit|gross margin|operating margin|profit margin|"
    r"net margin|effective tax",
    re.IGNORECASE,
)
_CASH_INTENT = re.compile(
    r"cash flow|depreciation|amortiz|d&a|\bcapex\b|capital expenditure|capital spending|purchases of property",
    re.IGNORECASE,
)
_BALANCE_INTENT = re.compile(
    r"balance sheet|financial position|working capital|total assets|current assets|"
    r"stockholders|shareholders. equity|quick ratio|current ratio|liquidity",
    re.IGNORECASE,
)
_CAPITAL_INTENSITY = re.compile(r"capital-intensive|capital intensive|fixed asset", re.IGNORECASE)
_LEGAL_INTENT = re.compile(r"\blegal\b|litigation|lawsuit|legal proceeding", re.IGNORECASE)
_GEO_INTENT = re.compile(r"geograph|regions?|primarily operates|operates in", re.IGNORECASE)
_RESTRUCT_INTENT = re.compile(r"restructur", re.IGNORECASE)
_SEGMENT_INTENT = re.compile(
    r"\bsegment\b|product categor|service categor|organic sale|organic sales|m\s*&\s*a\b",
    re.IGNORECASE,
)
_CUSTOMER_INTENT = re.compile(r"\bcustomer", re.IGNORECASE)
_INVENTORY_INTENT = re.compile(r"inventory turnover|sold its inventory|inventory management", re.IGNORECASE)
_MARGIN_INTENT = re.compile(r"\bmargin\b|gross profit", re.IGNORECASE)
_GROWTH_INTENT = re.compile(r"\bgrowth\b", re.IGNORECASE)
_FINANCIAL_INTENT = re.compile(r"financial", re.IGNORECASE)
_DEBT_INTENT = re.compile(r"\bdebt\b", re.IGNORECASE)
_ACQUISITION_INTENT = re.compile(r"\bacquisition|\bacquire", re.IGNORECASE)
_DRIVER_INTENT = re.compile(
    r"\b(?:drove|driven)\b.{0,48}\b(?:revenue|sales)\b|\b(?:revenue|sales)\b.{0,48}\b(?:drove|driven)\b",
    re.IGNORECASE,
)
_SYNONYMS = {
    "battle": ("litigation", "lawsuit", "proceeding"),
    "jnj": ("johnson",),
    "lawsuit": ("litigation", "proceeding"),
    "retain": ("retention",),
    "geograph": ("region",),
    "geography": ("region",),
}


@dataclass(frozen=True, slots=True)
class _PageView:
    index: int
    low: str
    terms: frozenset[str]
    kinds: frozenset[str]
    legal: int
    segment: bool
    customer: float
    regions: int
    debt: bool
    margin_note: bool
    growth_note: bool
    acquisition: float
    amounts: int
    revenue_driver: bool
    head_terms: frozenset[str]


def rank_page_texts(question: str, texts: Sequence[str], limit: int) -> tuple[int, ...]:
    """Return indexes of the best matching page texts, highest score first."""

    if limit < 1 or not isinstance(question, str) or question.strip() == "":
        return ()
    pages = tuple(_page_view(index, text) for index, text in enumerate(texts))
    if not pages:
        return ()
    return _ordered_indexes(pages, question, limit)


def _page_view(index: int, text: object) -> _PageView:
    body = text if isinstance(text, str) else ""
    low = body.lower()
    amounts = len(_AMOUNTS.findall(body))
    return _PageView(
        index=index,
        low=low,
        terms=frozenset(_tokens(body)),
        kinds=frozenset(_statement_kinds(body, amounts)),
        legal=_legal_strength(low),
        segment=_segment_table(low, body),
        customer=_customer_signal(low),
        regions=len({match.group(0).lower() for match in _REGION.finditer(body)}),
        debt=_debt_table(low, body),
        margin_note=_margin_note(low),
        growth_note=_growth_note(low),
        acquisition=_acquisition_note(low),
        amounts=amounts,
        revenue_driver=_revenue_driver(low),
        head_terms=frozenset(_tokens(body.split("\n", 1)[0])),
    )


def _ordered_indexes(pages: Sequence[_PageView], question: str, limit: int) -> tuple[int, ...]:
    terms = _query_terms(question)
    pages = _pages_for_document(pages, _anchor_terms(question, terms))
    idf, corpus_size = _idf(pages)
    intents = _intents(question)
    phrases = _phrase_words(question)
    scored = sorted(
        ((_score(page, terms, phrases, idf, corpus_size, intents), page) for page in pages),
        key=lambda item: (-item[0], item[1].low),
    )
    pinned = _pinned(scored, intents)
    ordered = list(pinned)
    for _, page in scored:
        if page.index in pinned:
            continue
        ordered.append(page.index)
        if len(ordered) >= limit:
            break
    return tuple(ordered[:limit])


def _anchor_terms(question: str, terms: Sequence[str]) -> tuple[str, ...]:
    """Add concatenated company names such as ``american`` + ``express``."""

    raw = [
        token
        for token in _TOKEN.findall(question.lower())
        if token not in _STOP and token not in _BOILER and len(token) > 1 and not token.isdigit()
    ]
    joined = [_stem("".join(raw[start : start + size])) for size in (2, 3, 4) for start in range(len(raw) - size + 1)]
    return tuple(dict.fromkeys((*terms, *joined)))


def _pages_for_document(pages: Sequence[_PageView], terms: Sequence[str]) -> Sequence[_PageView]:
    """Keep pages from the filing named in the question when several filings share a scope.

    Stored page text starts with the document id. A token that is present in some of
    those ids and absent from others identifies the filing. Ranking then matches the
    single-filing order. A scope that holds one filing shares one id, so nothing is
    dropped.
    """

    if len(pages) < 2 or not terms:
        return pages
    frequency: Counter[str] = Counter()
    for page in pages:
        frequency.update(term for term in terms if term in page.head_terms)
    candidates = [term for term in terms if 0 < frequency[term] < len(pages)]
    if not candidates:
        return pages
    anchor = min(candidates, key=lambda term: (frequency[term], len(term), term))
    chosen = tuple(page for page in pages if anchor in page.head_terms)
    return chosen or pages


def _pinned(scored: Sequence[tuple[float, _PageView]], intents: frozenset[str]) -> tuple[int, ...]:
    chosen: list[int] = []
    for kind in ("income", "cash", "balance"):
        if kind not in intents:
            continue
        matches = sorted(
            (page for _, page in scored if kind in page.kinds),
            key=lambda page: (-page.amounts, page.low),
        )
        for page in matches[:2]:
            if page.index not in chosen:
                chosen.append(page.index)
    if "legal" in intents:
        legal_pages = sorted(
            (page for _, page in scored if page.legal > 0),
            key=lambda page: (-page.legal, page.low),
        )
        for page in legal_pages[:2]:
            if page.index not in chosen:
                chosen.append(page.index)
    return tuple(chosen)


def _score(
    page: _PageView,
    terms: Sequence[str],
    phrases: Sequence[str],
    idf: dict[str, float],
    corpus_size: int,
    intents: frozenset[str],
) -> float:
    return _lexical_score(page, terms, idf, corpus_size) + _bigram_score(page.low, phrases) + _cue_score(page, intents)


def _lexical_score(page: _PageView, terms: Sequence[str], idf: dict[str, float], corpus_size: int) -> float:
    unseen = math.log(1 + (corpus_size + 0.5) / 0.5)
    score = 0.0
    for term in terms:
        if _matches(term, page.terms):
            weight = idf.get(term, unseen)
            score += weight * weight
    return score


def _bigram_score(low: str, words: Sequence[str]) -> float:
    score = 0.0
    for left, right in pairwise(words):
        if f"{left} {right}" in low or f"{left} {right}s" in low:
            score += 2.2
    return score


def _cue_score(page: _PageView, intents: frozenset[str]) -> float:
    score = 0.0
    if "legal" in intents:
        score += min(page.legal, 12) * 0.8
    if "geo" in intents:
        score += 1.6 * page.regions
    if "customer" in intents:
        score += page.customer
    if "acquire" in intents:
        score += page.acquisition
    if "restruct" in intents and "restructuring" in page.low:
        score += 4
    for name, enabled, weight in (
        ("segment", page.segment, 9),
        ("margin", page.margin_note, 7),
        ("growth", page.growth_note, 8),
        ("debt", page.debt, 9),
        ("driver", page.revenue_driver, 8),
    ):
        if name in intents and enabled:
            score += weight
    return score


def _idf(pages: Sequence[_PageView]) -> tuple[dict[str, float], int]:
    counts: Counter[str] = Counter()
    for page in pages:
        counts.update(page.terms)
    corpus_size = len(pages)
    return {
        term: math.log(1 + (corpus_size - count + 0.5) / (count + 0.5)) for term, count in counts.items()
    }, corpus_size


def _query_terms(question: str) -> tuple[str, ...]:
    terms = _content_tokens(_expand_question(question))
    extra = [_stem(synonym) for term in terms for synonym in _SYNONYMS.get(term, ())]
    return tuple(dict.fromkeys((*terms, *extra)))


def _phrase_words(question: str) -> tuple[str, ...]:
    return tuple(
        _stem(token)
        for token in _TOKEN.findall(_expand_question(question).lower())
        if token not in _STOP and token not in _BOILER and len(token) > 2 and not (token.isdigit() and len(token) <= 3)
    )


def _expand_question(question: str) -> str:
    text = _MA.sub(" acquisition divestiture ", question)
    text = _DA.sub(" depreciation amortization ", text)
    text = _CAPEX.sub(" capital expenditure ", text)
    return _PL.sub(" income statement ", text)


_INTENT_RULES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (_INCOME_INTENT, ("income",)),
    (_CASH_INTENT, ("cash",)),
    (_BALANCE_INTENT, ("balance",)),
    (_CAPITAL_INTENSITY, ("income", "cash", "balance")),
    (_LEGAL_INTENT, ("legal",)),
    (_GEO_INTENT, ("geo",)),
    (_RESTRUCT_INTENT, ("restruct",)),
    (_SEGMENT_INTENT, ("segment",)),
    (_CUSTOMER_INTENT, ("customer",)),
    (_INVENTORY_INTENT, ("income", "balance")),
    (_MARGIN_INTENT, ("margin",)),
    (_DEBT_INTENT, ("debt",)),
    (_ACQUISITION_INTENT, ("acquire",)),
    (_DRIVER_INTENT, ("driver",)),
)


def _intents(question: str) -> frozenset[str]:
    found: set[str] = set()
    for pattern, labels in _INTENT_RULES:
        if pattern.search(question):
            found.update(labels)
    if _GROWTH_INTENT.search(question) and _FINANCIAL_INTENT.search(question):
        found.add("growth")
    return frozenset(found)


def _content_tokens(text: str) -> tuple[str, ...]:
    return tuple(
        _stem(token)
        for token in _TOKEN.findall(text.lower())
        if token not in _STOP and token not in _BOILER and len(token) > 1 and not (token.isdigit() and len(token) <= 3)
    )


def _tokens(text: str) -> tuple[str, ...]:
    return _content_tokens(text)


def _stem(token: str) -> str:
    """Strip a trailing plural so short morphological variants share a term."""

    if len(token) > 5 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 4 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _matches(query_term: str, page_terms: frozenset[str]) -> bool:
    if query_term in page_terms:
        return True
    if len(query_term) < 6:
        return False
    for term in page_terms:
        if len(term) < 6:
            continue
        shared = 0
        limit = min(len(query_term), len(term))
        while shared < limit and query_term[shared] == term[shared]:
            shared += 1
        if shared >= 6:
            return True
    return False


def _statement_kinds(text: str, amounts: int) -> set[str]:
    if amounts < 12:
        return set()
    head = _letters(text).removeprefix("tableofcontents")[:180]
    found: set[str] = set()
    if _titled(head, _INCOME_TITLES) and not head.startswith("consolidatedstatementofcomprehensive"):
        found.add("income")
    if _titled(head, _CASH_TITLES):
        found.add("cash")
    if _titled(head, _BALANCE_TITLES):
        found.add("balance")
    return found


def _titled(head: str, titles: tuple[str, ...]) -> bool:
    return any(_title_continues(head, title) for title in titles)


def _title_continues(head: str, title: str) -> bool:
    index = head.find(title)
    if index < 0:
        return False
    tail = head[index + len(title) : index + len(title) + 56]
    return any(marker in tail for marker in _TITLE_TAILS)


def _letters(text: str) -> str:
    return re.sub(r"[^a-z]", "", text.lower())


def _legal_strength(low: str) -> int:
    return (
        3 * low.count("lawsuit")
        + 3 * low.count("litigation")
        + 2 * low.count("legal action")
        + 2 * low.count("legal proceeding")
    )


def _segment_table(low: str, text: str) -> bool:
    if len(_AMOUNTS.findall(text)) < 8 or "segment" not in low:
        return False
    if not any(word in low for word in ("revenue", "revenues", "net sales", "sales")):
        return False
    return any(phrase in low for phrase in ("business segment", "by segment", "segment data", "organic sale"))


def _debt_table(low: str, text: str) -> bool:
    if len(_AMOUNTS.findall(text)) < 8:
        return False
    if "long-term debt" in low:
        return True
    return "outstanding" in low and "debt" in low and "interest rate" in low


def _margin_note(low: str) -> bool:
    return "percent to sales" in low or "as a percent of sales" in low or "as a percentage of sales" in low


def _growth_note(low: str) -> bool:
    if "results of operations" not in low or "sales" not in low:
        return False
    return any(phrase in low for phrase in ("sales increased", "sales decreased", "sales grew", "sales declined"))


def _acquisition_note(low: str) -> float:
    mentions = low.count("acquisition") + low.count("acquired")
    if mentions < 8:
        return 0.0
    if "acquisitions and divestitures" not in low[:600] and "business combination" not in low[:600]:
        return 0.0
    score = float(min(mentions, 18))
    if "purchase consideration" in low or "equity interest" in low:
        score += 4
    return score


def _revenue_driver(low: str) -> bool:
    if "results of operations" not in low:
        return False
    if "net revenue" not in low and "net sales" not in low:
        return False
    return "driven" in low or "increase" in low or "decrease" in low


def _customer_signal(low: str) -> float:
    score = 0.0
    if "customer accounted for" in low:
        score += 8
    if "portion of our revenue" in low:
        score += 7
    if _REVENUE_SHARE.search(low):
        score += 5
    if "major customer" in low:
        score += 3
    if "limited number of" in low and any(word in low for word in ("customer", "airline", "revenue")):
        score += 4
    if "concentration" in low and "customer" in low:
        score += 4
    return score


__all__ = ["rank_page_texts"]
