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


class ChinaSourcesSource(BaseSource):
    """Chinese-language AI news (量子位 / 雷锋网 / InfoQ 中国 ...).

    Domestic models (DeepSeek, Qwen, Kimi, 智谱, MiniMax) often break here first,
    so this is the biggest information-asymmetry gap for a Chinese reader.
    """

    name = "china_sources"

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
        cfg = self.config.get("sources", {}).get("china_sources", {})
        if not cfg.get("enabled", True):
            return []

        feeds = cfg.get("feeds", [])
        lookback_hours = cfg.get("lookback_hours", 48)
        max_per_feed = cfg.get("max_items_per_feed", 8)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=30)
        headers = {"User-Agent": "Mozilla/5.0 (compatible; DeepRadar/1.0; +https://github.com/wuqisen/DeepRadar)"}

        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            for feed_info in feeds:
                feed_name = feed_info.get("name", "中文源")
                feed_url = feed_info.get("url", "")
                if not feed_url:
                    continue

                try:
                    text = await self._fetch_feed(session, feed_url)
                    feed = feedparser.parse(text)

                    kept = 0
                    for entry in feed.entries:
                        if kept >= max_per_feed:
                            break

                        published = None
                        for attr in ("published_parsed", "updated_parsed"):
                            parsed = getattr(entry, attr, None)
                            if parsed:
                                published = datetime(*parsed[:6], tzinfo=timezone.utc)
                                break
                        if published and published < cutoff:
                            continue

                        summary = strip_html(entry.get("summary", entry.get("description", "")))

                        items.append(
                            RawNewsItem(
                                source=SourceType.CHINA,
                                source_name=feed_name,
                                title=entry.get("title", "").strip(),
                                url=entry.get("link", ""),
                                content=summary[:1500],
                                published_at=published,
                                metadata={"feed_url": feed_url, "lang": "zh"},
                            )
                        )
                        kept += 1

                    self.logger.info(f"Fetched {kept} entries from {feed_name}")
                except Exception as e:
                    self.logger.warning(f"Failed to fetch China source {feed_name}: {e}")

        self.logger.info(f"Total China-source items: {len(items)}")
        return items
