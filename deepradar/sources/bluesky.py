from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiohttp

from deepradar.processing.models import RawNewsItem, SourceType
from deepradar.sources.base import BaseSource

_API_BASE = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"


class BlueskySource(BaseSource):
    name = "bluesky"

    async def fetch(self) -> list[RawNewsItem]:
        cfg = self.config.get("sources", {}).get("bluesky", {})
        if not cfg.get("enabled", True):
            return []

        accounts = cfg.get("accounts", [])
        lookback_hours = cfg.get("lookback_hours", 48)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for handle in accounts:
                try:
                    url = f"{_API_BASE}?actor={handle}&limit=20"
                    resp = await session.get(url)
                    if resp.status != 200:
                        self.logger.warning(f"Bluesky API returned {resp.status} for @{handle}")
                        continue
                    data = await resp.json()

                    for feed_item in data.get("feed", []):
                        post = feed_item.get("post", {})
                        record = post.get("record", {})
                        text = record.get("text", "").strip()
                        if not text:
                            continue

                        created_at_str = record.get("createdAt") or post.get("indexedAt", "")
                        published = None
                        if created_at_str:
                            try:
                                published = datetime.fromisoformat(
                                    created_at_str.replace("Z", "+00:00")
                                )
                            except ValueError:
                                pass

                        if published and published < cutoff:
                            continue

                        post_uri = post.get("uri", "")
                        rkey = post_uri.split("/")[-1] if "/" in post_uri else ""
                        url_link = (
                            f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else ""
                        )

                        items.append(
                            RawNewsItem(
                                source=SourceType.BLUESKY,
                                source_name=f"@{handle}",
                                title=text[:120],
                                url=url_link,
                                content=text,
                                published_at=published,
                                metadata={"handle": handle, "cid": post.get("cid", "")},
                            )
                        )

                except Exception as exc:
                    self.logger.warning(f"Failed to fetch Bluesky posts for @{handle}: {exc}")

        self.logger.info(f"Total Bluesky items: {len(items)}")
        return items
