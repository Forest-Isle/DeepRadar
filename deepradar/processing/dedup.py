from __future__ import annotations

import difflib
import logging
import re
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from deepradar.processing.models import RawNewsItem

logger = logging.getLogger(__name__)

# Tracking parameters to strip from URLs
_TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "ref", "source"}


def _normalize_url(url: str) -> str:
    """Normalize a URL for deduplication: strip tracking params, trailing slash, www."""
    try:
        parsed = urlparse(url)
        # Remove www prefix
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        # Strip tracking params
        params = parse_qs(parsed.query, keep_blank_values=False)
        clean_params = {k: v for k, v in params.items() if k.lower() not in _TRACKING_PARAMS}
        query = urlencode(clean_params, doseq=True)
        # Rebuild
        path = parsed.path.rstrip("/")
        return urlunparse(("", host, path, parsed.params, query, ""))
    except Exception:
        return url.lower().rstrip("/")


def _normalize_title(title: str) -> str:
    """Normalize title for fuzzy comparison."""
    return re.sub(r"\s+", " ", title.lower().strip())


def deduplicate(items: list[RawNewsItem]) -> list[RawNewsItem]:
    """Remove duplicate items by URL and fuzzy title matching.

    When duplicates are found, keep the item with the richest metadata
    and note all sources it appeared in.
    """
    seen_urls: dict[str, int] = {}  # normalized_url -> index in result
    result: list[RawNewsItem] = []

    # Phase 1: URL-based dedup
    for item in items:
        norm = _normalize_url(item.url)
        if norm in seen_urls:
            idx = seen_urls[norm]
            existing = result[idx]
            # Merge: add source info to metadata
            sources = existing.metadata.get("also_on", [])
            sources.append(item.source_name)
            existing.metadata["also_on"] = sources
        else:
            seen_urls[norm] = len(result)
            result.append(item.model_copy(deep=True))

    # Phase 2: Title-based fuzzy dedup
    deduped: list[RawNewsItem] = []
    titles: list[str] = []

    for item in result:
        norm_title = _normalize_title(item.title)
        is_dup = False
        for i, existing_title in enumerate(titles):
            ratio = difflib.SequenceMatcher(None, norm_title, existing_title).ratio()
            if ratio > 0.85:
                # Merge into existing
                sources = deduped[i].metadata.get("also_on", [])
                sources.append(item.source_name)
                deduped[i].metadata["also_on"] = sources
                is_dup = True
                break

        if not is_dup:
            deduped.append(item)
            titles.append(norm_title)

    logger.info(f"Dedup: {len(items)} -> {len(deduped)} items")
    return deduped
