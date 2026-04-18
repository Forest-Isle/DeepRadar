from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiohttp
import feedparser

from deepradar.processing.models import RawNewsItem, SourceType
from deepradar.sources.base import BaseSource


class YouTubeRssSource(BaseSource):
    name = "youtube_rss"

    async def _fetch_channel_feed(
        self,
        session: aiohttp.ClientSession,
        channel_id: str,
        invidious_instances: list[str],
    ) -> str | None:
        """Try YouTube primary, then each Invidious instance. Returns feed text or None."""
        primary_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            resp = await session.get(primary_url)
            if resp.status == 200:
                return await resp.text()
        except Exception:
            pass

        for instance in invidious_instances:
            url = f"{instance.rstrip('/')}/feed/channel/{channel_id}"
            try:
                resp = await session.get(url)
                if resp.status == 200:
                    return await resp.text()
            except Exception:
                pass

        return None

    async def fetch(self) -> list[RawNewsItem]:
        cfg = self.config.get("sources", {}).get("youtube_rss", {})
        if not cfg.get("enabled", True):
            return []

        channels = cfg.get("channels", [])
        lookback_hours = cfg.get("lookback_hours", 48)
        invidious_instances = cfg.get("invidious_instances", [])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for ch in channels:
                ch_name = ch.get("name", "Unknown")
                ch_id = ch.get("channel_id", "")
                if not ch_id:
                    continue

                text = await self._fetch_channel_feed(session, ch_id, invidious_instances)
                if text is None:
                    self.logger.warning(f"All sources failed for YouTube channel {ch_name}")
                    continue

                feed = feedparser.parse(text)
                for entry in feed.entries:
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        if published < cutoff:
                            continue

                    video_id = entry.get("yt_videoid", "")
                    thumbnail = (
                        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                        if video_id
                        else ""
                    )

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

        self.logger.info(f"Total YouTube items: {len(items)}")
        return items
