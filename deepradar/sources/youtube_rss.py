from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import aiohttp
import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from deepradar.processing.models import RawNewsItem, SourceType
from deepradar.sources.base import BaseSource

logger = logging.getLogger(__name__)


class YouTubeRssSource(BaseSource):
    name = "youtube_rss"

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
        cfg = self.config.get("sources", {}).get("youtube_rss", {})
        if not cfg.get("enabled", True):
            return []

        channels = cfg.get("channels", [])
        lookback_hours = cfg.get("lookback_hours", 48)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for ch in channels:
                ch_name = ch.get("name", "Unknown")
                ch_id = ch.get("channel_id", "")
                if not ch_id:
                    continue

                url = f"https://www.youtube.com/feeds/videos.xml?channel_id={ch_id}"
                try:
                    text = await self._fetch_feed(session, url)
                    feed = feedparser.parse(text)

                    for entry in feed.entries:
                        published = None
                        if hasattr(entry, "published_parsed") and entry.published_parsed:
                            published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                            if published < cutoff:
                                continue

                        video_id = entry.get("yt_videoid", "")
                        thumbnail = f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg" if video_id else ""

                        items.append(
                            RawNewsItem(
                                source=SourceType.YOUTUBE,
                                source_name=ch_name,
                                title=entry.get("title", "").strip(),
                                url=entry.get("link", ""),
                                content=entry.get("summary", "").strip()[:500],
                                published_at=published,
                                metadata={
                                    "channel_name": ch_name,
                                    "channel_id": ch_id,
                                    "video_id": video_id,
                                    "thumbnail": thumbnail,
                                },
                            )
                        )

                    self.logger.info(f"Fetched {len(feed.entries)} videos from {ch_name}")
                except Exception as e:
                    self.logger.warning(f"Failed to fetch YouTube channel {ch_name}: {e}")

        self.logger.info(f"Total YouTube items: {len(items)}")
        return items
