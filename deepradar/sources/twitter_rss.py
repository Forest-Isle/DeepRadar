from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import aiohttp
import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from deepradar.processing.models import RawNewsItem, SourceType
from deepradar.processing.utils import strip_html
from deepradar.sources.base import BaseSource

logger = logging.getLogger(__name__)


class TwitterRssSource(BaseSource):
    name = "twitter_rss"

    async def _try_fetch(self, session: aiohttp.ClientSession, url: str) -> str | None:
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception:
            pass
        return None

    async def fetch(self) -> list[RawNewsItem]:
        cfg = self.config.get("sources", {}).get("twitter_rss", {})
        if not cfg.get("enabled", True):
            return []

        instances = cfg.get("nitter_instances", [])
        accounts = cfg.get("accounts", [])
        lookback_hours = cfg.get("lookback_hours", 48)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        if not instances or not accounts:
            self.logger.warning("No Nitter instances or accounts configured")
            return []

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for account in accounts:
                fetched = False
                for instance in instances:
                    url = f"{instance.rstrip('/')}/{account}/rss"
                    text = await self._try_fetch(session, url)
                    if not text:
                        continue

                    feed = feedparser.parse(text)
                    if not feed.entries:
                        continue

                    for entry in feed.entries:
                        published = None
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                            if published < cutoff:
                                continue

                        content = strip_html(entry.get("summary", entry.get("title", "")))

                        items.append(
                            RawNewsItem(
                                source=SourceType.TWITTER,
                                source_name=f"@{account}",
                                title=content[:120],
                                url=entry.get("link", ""),
                                content=content,
                                published_at=published,
                                metadata={"account": account, "nitter_instance": instance},
                            )
                        )

                    fetched = True
                    self.logger.info(f"Fetched tweets from @{account} via {instance}")
                    break

                if not fetched:
                    self.logger.warning(f"All Nitter instances failed for @{account}")

        self.logger.info(f"Total Twitter items: {len(items)}")
        return items
