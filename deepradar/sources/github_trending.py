from __future__ import annotations

import logging
import re
from typing import Any

import aiohttp
from bs4 import BeautifulSoup
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from deepradar.processing.keywords import is_ai_related
from deepradar.processing.models import RawNewsItem, SourceType
from deepradar.sources.base import BaseSource

logger = logging.getLogger(__name__)


class GitHubTrendingSource(BaseSource):
    name = "github_trending"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((aiohttp.ClientError,)),
    )
    async def _fetch_page(self, session: aiohttp.ClientSession, url: str) -> str:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "text/html",
        }
        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.text()

    def _parse_stars(self, text: str) -> int:
        text = text.strip().replace(",", "")
        if not text:
            return 0
        try:
            return int(text)
        except ValueError:
            return 0

    async def fetch(self) -> list[RawNewsItem]:
        cfg = self.config.get("sources", {}).get("github_trending", {})
        if not cfg.get("enabled", True):
            return []

        base_url = cfg.get("url", "https://github.com/trending")
        min_stars_today = cfg.get("min_stars_today", 10)

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=30)

        try:
            async with aiohttp.ClientSession(timeout=timeout) as session:
                html = await self._fetch_page(session, f"{base_url}?since=daily")

            soup = BeautifulSoup(html, "lxml")
            repo_list = soup.select("article.Box-row")

            for article in repo_list:
                # Repo name
                h2 = article.select_one("h2 a")
                if not h2:
                    continue
                repo_path = h2.get("href", "").strip("/")
                if not repo_path:
                    continue
                repo_url = f"https://github.com/{repo_path}"

                # Description
                p = article.select_one("p")
                description = p.get_text(strip=True) if p else ""

                # Language
                lang_span = article.select_one("[itemprop='programmingLanguage']")
                language = lang_span.get_text(strip=True) if lang_span else ""

                # Stars today
                stars_today_elem = article.select_one("span.d-inline-block.float-sm-right")
                stars_today_text = stars_today_elem.get_text(strip=True) if stars_today_elem else "0"
                stars_today_match = re.search(r"([\d,]+)", stars_today_text)
                stars_today = self._parse_stars(stars_today_match.group(1)) if stars_today_match else 0

                # Total stars
                star_links = article.select("a.Link--muted")
                total_stars = 0
                for link in star_links:
                    href = link.get("href", "")
                    if "/stargazers" in href:
                        total_stars = self._parse_stars(link.get_text(strip=True))
                        break

                # Filter
                if stars_today < min_stars_today:
                    continue
                if not is_ai_related(repo_path, description, self.config):
                    continue

                items.append(
                    RawNewsItem(
                        source=SourceType.GITHUB,
                        source_name="GitHub Trending",
                        title=repo_path,
                        url=repo_url,
                        content=description,
                        metadata={
                            "stars_today": stars_today,
                            "total_stars": total_stars,
                            "language": language,
                        },
                    )
                )

            self.logger.info(f"Fetched {len(items)} AI repos from GitHub Trending")
        except Exception as e:
            self.logger.error(f"Failed to fetch GitHub Trending: {e}")

        return items
