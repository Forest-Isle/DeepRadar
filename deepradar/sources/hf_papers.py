from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from deepradar.processing.models import RawNewsItem, SourceType
from deepradar.sources.base import BaseSource

logger = logging.getLogger(__name__)


class HFPapersSource(BaseSource):
    """Hugging Face Daily Papers — community-curated and upvote-ranked, far
    higher signal than the raw arXiv firehose."""

    name = "hf_papers"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((aiohttp.ClientError,)),
    )
    async def _fetch_json(self, session: aiohttp.ClientSession, url: str) -> Any:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.json()

    async def fetch(self) -> list[RawNewsItem]:
        cfg = self.config.get("sources", {}).get("hf_papers", {})
        if not cfg.get("enabled", True):
            return []

        api_url = cfg.get("api_url", "https://huggingface.co/api/daily_papers")
        max_results = cfg.get("max_results", 30)
        min_upvotes = cfg.get("min_upvotes", 3)

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                data = await self._fetch_json(session, api_url)
        except Exception as e:
            self.logger.error(f"Failed to fetch HF daily papers: {e}")
            return []

        for entry in data[:max_results] if isinstance(data, list) else []:
            paper = entry.get("paper", {})
            upvotes = paper.get("upvotes", 0) or 0
            if upvotes < min_upvotes:
                continue

            paper_id = paper.get("id", "")
            title = (paper.get("title") or entry.get("title", "")).replace("\n", " ").strip()
            if not paper_id or not title:
                continue

            author_names = [a.get("name", "") for a in paper.get("authors", [])]
            authors = ", ".join(author_names[:6])
            if len(author_names) > 6:
                authors += ", et al."
            published = None
            pub_str = entry.get("publishedAt") or paper.get("publishedAt", "")
            if pub_str:
                try:
                    published = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
                except ValueError:
                    pass

            items.append(
                RawNewsItem(
                    source=SourceType.HF_PAPER,
                    source_name="HF Daily Papers",
                    title=title,
                    url=f"https://huggingface.co/papers/{paper_id}",
                    content=(paper.get("summary", "") or "").replace("\n", " ").strip(),
                    published_at=published or datetime.now(timezone.utc),
                    metadata={
                        "authors": authors,
                        "categories": [f"🤗 HF ▲{upvotes}"],
                        "arxiv_id": paper_id,
                        "upvotes": upvotes,
                    },
                )
            )

        self.logger.info(f"Fetched {len(items)} papers from HF Daily Papers")
        return items
