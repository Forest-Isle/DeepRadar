from __future__ import annotations

from typing import Any


def _collect_keywords(config: dict[str, Any]) -> set[str]:
    """Extract all AI-related keywords from categories config into a single set."""
    categories_cfg = config.get("categories", {})
    keywords: set[str] = set()

    kw_cfg = categories_cfg.get("ai_relevance_keywords", {})
    for level in ("high", "medium", "low"):
        for kw in kw_cfg.get(level, []):
            keywords.add(kw.lower())

    for cat in categories_cfg.get("categories", []):
        for kw in cat.get("keywords", []):
            keywords.add(kw.lower())

    return keywords


def is_ai_related(title: str, text: str, config: dict[str, Any]) -> bool:
    """Check if title+text contains any AI-related keyword from config."""
    keywords = _collect_keywords(config)
    if not keywords:
        return False
    combined = f"{title} {text}".lower()
    return any(kw in combined for kw in keywords)
