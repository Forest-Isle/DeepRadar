from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Any

from deepradar.processing.models import RawNewsItem

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4096)
def _kw_pattern(keyword: str) -> re.Pattern[str]:
    """Compile a word-boundary matcher so 'ai' doesn't match 'said' or 'gpt' 'gpts'."""
    return re.compile(r"\b" + re.escape(keyword) + r"\b")


def _has_keyword(text: str, keyword: str) -> bool:
    # CJK has no word boundaries, so \b would never match inside Chinese text.
    if not keyword.isascii():
        return keyword in text
    return _kw_pattern(keyword).search(text) is not None


def _compute_relevance_score(
    item: RawNewsItem,
    categories_cfg: dict[str, Any],
    credibility_cfg: dict[str, float],
) -> float:
    """Compute keyword-based relevance score for an item."""
    text = f"{item.title} {item.content}".lower()
    score = 0.0

    # Check AI relevance keywords
    kw_cfg = categories_cfg.get("ai_relevance_keywords", {})
    for kw in kw_cfg.get("high", []):
        if _has_keyword(text, kw):
            score += 3.0
    for kw in kw_cfg.get("medium", []):
        if _has_keyword(text, kw):
            score += 1.5
    for kw in kw_cfg.get("low", []):
        if _has_keyword(text, kw):
            score += 0.5

    # Check category keywords with weights
    for cat in categories_cfg.get("categories", []):
        weight = cat.get("weight", 1.0)
        for kw in cat.get("keywords", []):
            if _has_keyword(text, kw):
                score += 1.0 * weight

    # Boost based on engagement metadata
    meta = item.metadata
    if "score" in meta:  # HN or Reddit score
        if meta["score"] > 200:
            score += 3.0
        elif meta["score"] > 100:
            score += 2.0
        elif meta["score"] > 50:
            score += 1.0
    if "stars_today" in meta:
        if meta["stars_today"] > 100:
            score += 3.0
        elif meta["stars_today"] > 50:
            score += 2.0
    if "upvotes" in meta:  # HF Daily Papers community votes
        if meta["upvotes"] > 100:
            score += 3.0
        elif meta["upvotes"] > 30:
            score += 2.0
        elif meta["upvotes"] > 10:
            score += 1.0

    # Boost if appeared on multiple sources
    also_on = meta.get("also_on", [])
    score += len(also_on) * 2.0

    # Source credibility: official blogs / curated newsletters outrank raw community chatter
    score += credibility_cfg.get(item.source.value, 0.0)

    return score


def _is_agent_related(item: RawNewsItem, categories_cfg: dict[str, Any]) -> bool:
    """Return True if item matches any keyword in the AI Agent category."""
    text = f"{item.title} {item.content}".lower()
    for cat in categories_cfg.get("categories", []):
        if cat.get("name") == "AI Agent":
            for kw in cat.get("keywords", []):
                if _has_keyword(text, kw):
                    return True
    return False


def filter_relevant(
    items: list[RawNewsItem],
    config: dict[str, Any],
    min_score: float = 2.0,
) -> list[RawNewsItem]:
    """Filter items by relevance score and recency."""
    categories_cfg = config.get("categories", {})
    credibility_cfg = config.get("settings", {}).get("source_credibility", {})

    scored: list[tuple[float, RawNewsItem]] = []
    for item in items:
        rel_score = _compute_relevance_score(item, categories_cfg, credibility_cfg)
        if rel_score >= min_score:
            item.metadata["relevance_score"] = rel_score
            item.metadata["is_agent_related"] = _is_agent_related(item, categories_cfg)
            scored.append((rel_score, item))

    # Sort by relevance score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    result = [item for _, item in scored]

    logger.info(f"Filter: {len(items)} -> {len(result)} items (min_score={min_score})")
    return result
