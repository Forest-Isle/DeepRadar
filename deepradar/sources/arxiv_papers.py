from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote

import aiohttp
import feedparser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from deepradar.processing.models import RawNewsItem, SourceType
from deepradar.sources.base import BaseSource

logger = logging.getLogger(__name__)


class ArxivSource(BaseSource):
    name = "arxiv"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=3, min=3, max=15),
        retry=retry_if_exception_type((aiohttp.ClientError,)),
    )
    async def _fetch_feed(self, session: aiohttp.ClientSession, url: str) -> str:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.text()

    async def fetch(self) -> list[RawNewsItem]:
        cfg = self.config.get("sources", {}).get("arxiv", {})
        if not cfg.get("enabled", True):
            return []

        base_url = cfg.get("base_url", "http://export.arxiv.org/api/query")
        categories = cfg.get("categories", ["cs.AI", "cs.CL", "cs.LG", "cs.CV"])
        max_results = cfg.get("max_results", 100)
        lookback_hours = cfg.get("lookback_hours", 48)

        cat_query = "+OR+".join(f"cat:{c}" for c in categories)
        url = f"{base_url}?search_query={quote(cat_query, safe='+:')}&sortBy=submittedDate&sortOrder=descending&max_results={max_results}"

        items: list[RawNewsItem] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        try:
            timeout = aiohttp.ClientTimeout(total=60)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                text = await self._fetch_feed(session, url)

            feed = feedparser.parse(text)
            for entry in feed.entries:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                    if published < cutoff:
                        continue

                authors = ", ".join(a.get("name", "") for a in getattr(entry, "authors", []))
                cats = [t.get("term", "") for t in getattr(entry, "tags", [])]
                arxiv_id = entry.get("id", "").split("/abs/")[-1] if "/abs/" in entry.get("id", "") else ""

                pdf_url = ""
                for link in getattr(entry, "links", []):
                    if link.get("type") == "application/pdf":
                        pdf_url = link.get("href", "")
                        break

                items.append(
                    RawNewsItem(
                        source=SourceType.ARXIV,
                        source_name="arXiv",
                        title=entry.get("title", "").replace("\n", " ").strip(),
                        url=entry.get("link", entry.get("id", "")),
                        content=entry.get("summary", "").replace("\n", " ").strip(),
                        published_at=published,
                        metadata={
                            "authors": authors,
                            "categories": cats,
                            "arxiv_id": arxiv_id,
                            "pdf_url": pdf_url,
                        },
                    )
                )

            self.logger.info(f"Fetched {len(items)} papers from arXiv")
        except Exception as e:
            self.logger.error(f"Failed to fetch from arXiv: {e}")

        return items
