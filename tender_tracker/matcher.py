from __future__ import annotations

import math
import re
from collections import Counter

import pandas as pd


STOPWORDS = {
    "a",
    "about",
    "above",
    "after",
    "all",
    "along",
    "an",
    "and",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "with",
}

TOKEN_PATTERN = re.compile(r"[a-z0-9]{2,}")


def normalize_text(text: str | None) -> str:
    if text is None:
        return ""
    return " ".join(str(text).strip().lower().split())


def tokenize(text: str | None) -> list[str]:
    normalized = normalize_text(text)
    return [
        token
        for token in TOKEN_PATTERN.findall(normalized)
        if token not in STOPWORDS
    ]


def _vectorize(tokens: list[str]) -> Counter:
    return Counter(tokens)


def _cosine_similarity(left: Counter, right: Counter) -> float:
    if not left or not right:
        return 0.0

    dot_product = sum(left[token] * right[token] for token in left.keys() & right.keys())
    left_norm = math.sqrt(sum(value * value for value in left.values()))
    right_norm = math.sqrt(sum(value * value for value in right.values()))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _shared_keywords(profile_tokens: list[str], tender_tokens: list[str]) -> str:
    overlap = sorted(set(profile_tokens) & set(tender_tokens))
    return ", ".join(overlap[:8])


def rank_tenders(
    profile_text: str,
    tenders_dataframe: pd.DataFrame,
    *,
    minimum_score: float = 0.0,
) -> pd.DataFrame:
    if tenders_dataframe.empty:
        empty = tenders_dataframe.copy()
        empty["match_score"] = pd.Series(dtype="float64")
        empty["shared_keywords"] = pd.Series(dtype="object")
        return empty

    profile_tokens = tokenize(profile_text)
    profile_vector = _vectorize(profile_tokens)

    scores: list[float] = []
    keywords: list[str] = []

    for row in tenders_dataframe.itertuples(index=False):
        tender_text = " ".join(
            [
                str(getattr(row, "title", "") or ""),
                str(getattr(row, "description", "") or ""),
                str(getattr(row, "reference_no", "") or ""),
                str(getattr(row, "department", "") or ""),
                str(getattr(row, "location", "") or ""),
            ]
        )
        tender_tokens = tokenize(tender_text)
        tender_vector = _vectorize(tender_tokens)
        scores.append(round(_cosine_similarity(profile_vector, tender_vector), 6))
        keywords.append(_shared_keywords(profile_tokens, tender_tokens))

    ranked = tenders_dataframe.copy()
    ranked["match_score"] = scores
    ranked["shared_keywords"] = keywords
    ranked = ranked.sort_values(
        by=["match_score", "closing_date_sort", "updated_at"],
        ascending=[False, True, False],
        na_position="last",
    )
    if minimum_score > 0:
        ranked = ranked[ranked["match_score"] >= minimum_score]
    return ranked
