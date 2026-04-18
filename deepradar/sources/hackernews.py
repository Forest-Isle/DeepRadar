from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from deepradar.processing.keywords import is_ai_related
from deepradar.processing.models import RawNewsItem, SourceType
from deepradar.sources.base import BaseSource

logger = logging.getLogger(__name__)


class HackerNewsSource(BaseSource):
    name = "hackernews"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
    )
    async def _get_json(self, session: aiohttp.ClientSession, url: str) -> Any:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def fetch(self) -> list[RawNewsItem]:
        cfg = self.config.get("sources", {}).get("hackernews", {})
        if not cfg.get("enabled", True):
            return []

        top_url = cfg.get("top_stories_url", "https://hacker-news.firebaseio.com/v0/topstories.json")
        item_tpl = cfg.get("item_url_template", "https://hacker-news.firebaseio.com/v0/item/{id}.json")
        max_stories = cfg.get("max_stories_to_check", 200)
        min_score = cfg.get("min_score", 30)

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                story_ids = await self._get_json(session, top_url)
                story_ids = story_ids[:max_stories]

                sem = asyncio.Semaphore(50)

                async def fetch_item(sid: int) -> dict | None:
                    async with sem:
                        try:
                            return await self._get_json(session, item_tpl.format(id=sid))
                        except Exception:
                            return None

                results = await asyncio.gather(*(fetch_item(sid) for sid in story_ids))

                for story in results:
                    if not story or story.get("type") != "story":
                        continue
                    score = story.get("score", 0)
                    title = story.get("title", "")
                    if score < min_score:
                        continue
                    if not is_ai_related(title, "", self.config):
                        continue

                    url = story.get("url", f"https://news.ycombinator.com/item?id={story['id']}")
                    items.append(
                        RawNewsItem(
                            source=SourceType.HACKERNEWS,
                            source_name="Hacker News",
                            title=title,
                            url=url,
                            published_at=None,
                            metadata={
                                "score": score,
                                "comment_count": story.get("descendants", 0),
                                "author": story.get("by", ""),
                                "hn_id": story.get("id"),
                            },
                        )
                    )

            self.logger.info(f"Fetched {len(items)} AI-related stories from HN")
        except Exception as e:
            self.logger.error(f"Failed to fetch from HN: {e}")

        return items
