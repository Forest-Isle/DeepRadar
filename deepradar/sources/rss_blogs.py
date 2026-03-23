from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp
import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from deepradar.processing.models import RawNewsItem, SourceType
from deepradar.sources.base import BaseSource

logger = logging.getLogger(__name__)


class RssBlogsSource(BaseSource):
    name = "rss_blogs"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((aiohttp.ClientError,)),
    )
    async def _fetch_feed(self, session: aiohttp.ClientSession, url: str) -> str:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def fetch(self) -> list[RawNewsItem]:
        cfg = self.config.get("sources", {}).get("rss_blogs", {})
        if not cfg.get("enabled", True):
            return []

        feeds = cfg.get("feeds", [])
        lookback_hours = cfg.get("lookback_hours", 48)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for feed_info in feeds:
                feed_name = feed_info.get("name", "Unknown Blog")
                feed_url = feed_info.get("url", "")
                if not feed_url:
                    continue

                try:
                    text = await self._fetch_feed(session, feed_url)
                    feed = feedparser.parse(text)

                    for entry in feed.entries:
                        published = None
                        for attr in ("published_parsed", "updated_parsed"):
                            parsed = getattr(entry, attr, None)
                            if parsed:
                                published = datetime(*parsed[:6], tzinfo=timezone.utc)
                                break

                        if published and published < cutoff:
                            continue

                        summary = entry.get("summary", entry.get("description", ""))
                        # Strip HTML tags simply
                        if "<" in summary:
                            import re
                            summary = re.sub(r"<[^>]+>", "", summary).strip()

                        items.append(
                            RawNewsItem(
                                source=SourceType.RSS_BLOG,
                                source_name=feed_name,
                                title=entry.get("title", "").strip(),
                                url=entry.get("link", ""),
                                content=summary[:1000],
                                published_at=published,
                                metadata={"feed_url": feed_url},
                            )
                        )

                    self.logger.info(f"Fetched {len(feed.entries)} entries from {feed_name}")
                except Exception as e:
                    self.logger.warning(f"Failed to fetch RSS feed {feed_name}: {e}")

        self.logger.info(f"Total RSS blog items: {len(items)}")
        return items
