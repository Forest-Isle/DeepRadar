from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from deepradar.processing.models import RawNewsItem

logger = logging.getLogger(__name__)


def _compute_relevance_score(item: RawNewsItem, categories_cfg: dict[str, Any]) -> float:
    """Compute keyword-based relevance score for an item."""
    text = f"{item.title} {item.content}".lower()
    score = 0.0

    # Check AI relevance keywords
    kw_cfg = categories_cfg.get("ai_relevance_keywords", {})
    for kw in kw_cfg.get("high", []):
        if kw in text:
            score += 3.0
    for kw in kw_cfg.get("medium", []):
        if kw in text:
            score += 1.5
    for kw in kw_cfg.get("low", []):
        if kw in text:
            score += 0.5

    # Check category keywords with weights
    for cat in categories_cfg.get("categories", []):
        weight = cat.get("weight", 1.0)
        for kw in cat.get("keywords", []):
            if kw in text:
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

    # Boost if appeared on multiple sources
    also_on = meta.get("also_on", [])
    score += len(also_on) * 2.0

    return score


def filter_relevant(
    items: list[RawNewsItem],
    config: dict[str, Any],
    min_score: float = 2.0,
) -> list[RawNewsItem]:
    """Filter items by relevance score and recency."""
    categories_cfg = config.get("categories", {})

    scored: list[tuple[float, RawNewsItem]] = []
    for item in items:
        rel_score = _compute_relevance_score(item, categories_cfg)
        if rel_score >= min_score:
            item.metadata["relevance_score"] = rel_score
            scored.append((rel_score, item))

    # Sort by relevance score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    result = [item for _, item in scored]

    logger.info(f"Filter: {len(items)} -> {len(result)} items (min_score={min_score})")
    return result
