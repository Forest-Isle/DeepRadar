from __future__ import annotations

import asyncio
import logging
from typing import Any
from urllib.parse import urlparse

import aiohttp

from deepradar.processing.models import RawNewsItem, SourceType

logger = logging.getLogger(__name__)

# Sources whose items link to a real article worth fetching. GitHub repos,
# arXiv (abstract already in content), and video sources are excluded.
_FETCH_SOURCES = {SourceType.HACKERNEWS, SourceType.REDDIT, SourceType.RSS_BLOG}

# Platform hosts where the URL is the post itself, not an external article.
_SKIP_HOSTS = {
    "news.ycombinator.com",
    "reddit.com",
    "old.reddit.com",
    "twitter.com",
    "x.com",
    "youtube.com",
    "youtu.be",
}

_SKIP_SUFFIXES = (".pdf", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".mp4")


def _should_fetch(item: RawNewsItem, min_existing_chars: int) -> bool:
    if item.source not in _FETCH_SOURCES:
        return False
    if len(item.content or "") >= min_existing_chars:
        return False
    parsed = urlparse(item.url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    if host in _SKIP_HOSTS:
        return False
    if parsed.path.lower().endswith(_SKIP_SUFFIXES):
        return False
    return True


def _extract(html: str, url: str) -> str:
    import trafilatura

    return trafilatura.extract(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
    ) or ""


async def _fetch_html(session: aiohttp.ClientSession, url: str) -> str | None:
    async with session.get(url) as resp:
        if resp.status != 200:
            return None
        if "html" not in resp.headers.get("Content-Type", "").lower():
            return None
        raw = await resp.read()
    return raw.decode("utf-8", "ignore")


async def enrich_content(items: list[RawNewsItem], config: dict[str, Any]) -> None:
    """Fetch and extract article bodies for the top items in-place.

    Replaces each item's thin RSS/title content with the extracted main text so
    the LLM summarizes the actual article. Failures leave the item untouched.
    """
    cfg = config.get("settings", {}).get("content_fetch", {})
    if not cfg.get("enabled", True):
        return
    top_n = cfg.get("top_n", 25)
    min_existing = cfg.get("min_existing_chars", 600)
    max_chars = cfg.get("max_chars", 4000)
    timeout_s = cfg.get("timeout", 15)
    concurrency = cfg.get("concurrency", 8)

    targets = [it for it in items[:top_n] if _should_fetch(it, min_existing)]
    if not targets:
        return

    sem = asyncio.Semaphore(concurrency)
    timeout = aiohttp.ClientTimeout(total=timeout_s)
    headers = {"User-Agent": "DeepRadar/1.0 (+https://github.com/wuqisen/DeepRadar)"}
    fetched = 0

    async def _one(session: aiohttp.ClientSession, item: RawNewsItem) -> None:
        nonlocal fetched
        async with sem:
            try:
                html = await _fetch_html(session, item.url)
                if not html:
                    return
                body = await asyncio.to_thread(_extract, html, item.url)
                if body and len(body) > len(item.content or ""):
                    item.content = body[:max_chars]
                    item.metadata["content_fetched"] = True
                    fetched += 1
            except Exception as exc:
                logger.debug(f"content fetch failed for {item.url}: {exc}")

    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        await asyncio.gather(*(_one(session, it) for it in targets))

    logger.info(f"Content fetch: enriched {fetched}/{len(targets)} items")
