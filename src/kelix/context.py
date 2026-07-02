"""Relevance scoring for prompt context selection (stdlib only)."""

from __future__ import annotations

import math
import re

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


def _build_idf(documents: list[str]) -> dict[str, float]:
    n = len(documents)
    if n == 0:
        return {}
    df: dict[str, int] = {}
    for doc in documents:
        for tok in set(_tokenize(doc)):
            df[tok] = df.get(tok, 0) + 1
    return {tok: math.log(n / count) + 1.0 for tok, count in df.items()}


def score(text: str, query: str, idf: dict[str, float] | None = None) -> float:
    """Token overlap between *text* and *query*, weighted by inverse frequency."""
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    text_tokens = set(_tokenize(text))
    weights = idf if idf is not None else _build_idf([text, query])
    total = 0.0
    for tok in query_tokens:
        if tok in text_tokens:
            total += weights.get(tok, 1.0)
    return total


def select(
    candidates: list[str],
    query: str,
    budget_chars: int,
) -> list[str]:
    """Return highest-scoring *candidates* until *budget_chars*; ties by recency.

    Later items in *candidates* are treated as more recent. With an empty
    *query*, selection falls back to recency (most recent first) until budget.
    """
    if not candidates:
        return []
    if budget_chars <= 0:
        return []

    if not query.strip():
        chosen: list[str] = []
        used = 0
        for text in reversed(candidates):
            extra = len(text) + (1 if chosen else 0)
            if used + extra > budget_chars and chosen:
                break
            chosen.append(text)
            used += extra
        chosen.reverse()
        return chosen

    idf = _build_idf(candidates + [query])
    ranked = sorted(
        enumerate(candidates),
        key=lambda item: (-score(item[1], query, idf), -item[0]),
    )
    chosen = []
    used = 0
    for _, text in ranked:
        extra = len(text) + (1 if chosen else 0)
        if used + extra > budget_chars and chosen:
            continue
        chosen.append(text)
        used += extra
    return chosen


def select_scored(
    candidates: list[str],
    query: str,
    budget_chars: int,
) -> list[tuple[str, float]]:
    """Like :func:`select`, but each chosen item includes its relevance score."""
    if not candidates:
        return []
    if budget_chars <= 0:
        return []

    if not query.strip():
        chosen: list[tuple[str, float]] = []
        used = 0
        for text in reversed(candidates):
            extra = len(text) + (1 if chosen else 0)
            if used + extra > budget_chars and chosen:
                break
            chosen.append((text, 0.0))
            used += extra
        chosen.reverse()
        return chosen

    idf = _build_idf(candidates + [query])
    ranked = sorted(
        enumerate(candidates),
        key=lambda item: (-score(item[1], query, idf), -item[0]),
    )
    chosen: list[tuple[str, float]] = []
    used = 0
    for _, text in ranked:
        sc = score(text, query, idf)
        extra = len(text) + (1 if chosen else 0)
        if used + extra > budget_chars and chosen:
            continue
        chosen.append((text, sc))
        used += extra
    return chosen
