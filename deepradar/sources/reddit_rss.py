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


class RedditRssSource(BaseSource):
    name = "reddit_rss"

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
        cfg = self.config.get("sources", {}).get("reddit_rss", {})
        if not cfg.get("enabled", True):
            return []

        subreddits = cfg.get("subreddits", ["MachineLearning"])
        user_agent = cfg.get("user_agent", "DeepRadar/1.0")
        lookback_hours = cfg.get("lookback_hours", 48)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {"User-Agent": user_agent}

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for sub in subreddits:
                url = f"https://www.reddit.com/r/{sub}/hot/.rss"
                try:
                    text = await self._fetch_feed(session, url)
                    feed = feedparser.parse(text)

                    for entry in feed.entries:
                        published = None
                        if hasattr(entry, "updated_parsed") and entry.updated_parsed:
                            published = datetime(*entry.updated_parsed[:6], tzinfo=timezone.utc)
                            if published < cutoff:
                                continue

                        content = entry.get("summary", "")
                        import re
                        if "<" in content:
                            content = re.sub(r"<[^>]+>", "", content).strip()

                        items.append(
                            RawNewsItem(
                                source=SourceType.REDDIT,
                                source_name=f"r/{sub}",
                                title=entry.get("title", "").strip(),
                                url=entry.get("link", ""),
                                content=content[:1000],
                                published_at=published,
                                metadata={"subreddit": sub},
                            )
                        )

                    self.logger.info(f"Fetched {len(feed.entries)} entries from r/{sub}")
                except Exception as e:
                    self.logger.warning(f"Failed to fetch r/{sub}: {e}")

        self.logger.info(f"Total Reddit items: {len(items)}")
        return items
