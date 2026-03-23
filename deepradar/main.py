from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date
from typing import Any

from deepradar.config import load_config
from deepradar.llm.client import LLMClient
from deepradar.llm.tasks import batch_summarize, enrich_github_repos, generate_headline
from deepradar.processing.dedup import deduplicate
from deepradar.processing.filter import filter_relevant
from deepradar.processing.models import RawNewsItem
from deepradar.publish.github_publisher import publish_report
from deepradar.report.generator import generate_report
from deepradar.sources.arxiv_papers import ArxivSource
from deepradar.sources.github_trending import GitHubTrendingSource
from deepradar.sources.hackernews import HackerNewsSource
from deepradar.sources.reddit_rss import RedditRssSource
from deepradar.sources.rss_blogs import RssBlogsSource
from deepradar.sources.twitter_rss import TwitterRssSource
from deepradar.sources.youtube_rss import YouTubeRssSource

logger = logging.getLogger("deepradar")


def _setup_logging(config: dict[str, Any]) -> None:
    level_name = config.get("settings", {}).get("general", {}).get("log_level", "INFO")
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _init_sources(config: dict[str, Any]) -> list:
    """Initialize all enabled source instances."""
    source_classes = [
        HackerNewsSource,
        ArxivSource,
        RssBlogsSource,
        GitHubTrendingSource,
        RedditRssSource,
        YouTubeRssSource,
        TwitterRssSource,
    ]
    sources = []
    for cls in source_classes:
        src = cls(config)
        src_cfg = config.get("sources", {}).get(src.name, {})
        if src_cfg.get("enabled", True):
            sources.append(src)
        else:
            logger.info(f"Source {src.name} is disabled, skipping")
    return sources


async def _collect_all(sources: list) -> tuple[list[RawNewsItem], int]:
    """Fetch from all sources concurrently. Returns items and active source count."""
    tasks = [src.fetch() for src in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: list[RawNewsItem] = []
    active = 0
    for src, result in zip(sources, results):
        if isinstance(result, Exception):
            logger.error(f"Source {src.name} raised exception: {result}")
        elif result:
            all_items.extend(result)
            active += 1
        else:
            active += 1  # Returned empty but didn't fail

    return all_items, active


async def run() -> None:
    config = load_config()
    _setup_logging(config)

    today = date.today().isoformat()
    logger.info(f"=== DeepRadar Daily Report: {today} ===")

    # Step 1: Collect from all sources
    sources = _init_sources(config)
    logger.info(f"Initialized {len(sources)} sources")

    raw_items, sources_active = await _collect_all(sources)
    total_collected = len(raw_items)
    logger.info(f"Collected {total_collected} raw items from {sources_active}/{len(sources)} sources")

    if not raw_items:
        logger.warning("No items collected. Aborting report generation.")
        return

    # Step 2: Deduplicate and filter
    deduped = deduplicate(raw_items)
    filtered = filter_relevant(deduped, config)
    logger.info(f"After processing: {len(filtered)} items")

    # Step 3: LLM enrichment
    api_key = config.get("settings", {}).get("anthropic_api_key", "")
    if api_key:
        logger.info("Starting LLM processing...")
        client = LLMClient(config)
        batch_size = config.get("settings", {}).get("llm", {}).get("batch_size", 12)
        processed = batch_summarize(client, filtered, batch_size=batch_size)
        enrich_github_repos(client, processed)
        headline = generate_headline(client, processed)
        usage = client.get_usage_stats()
        logger.info(f"LLM usage: {usage}")
    else:
        logger.warning("No ANTHROPIC_API_KEY set. Generating report without LLM enrichment.")
        from deepradar.processing.models import ProcessedNewsItem
        processed = [ProcessedNewsItem(raw=item) for item in filtered]
        headline = {
            "headline_en": "AI Daily Report",
            "headline_zh": "AI 每日报告",
            "summary_en": "Today's AI news digest.",
            "summary_zh": "今日 AI 新闻摘要。",
        }
        usage = {"total_tokens": 0}

    # Step 4: Generate report
    stats = {
        "total_collected": total_collected,
        "sources_active": sources_active,
        "sources_total": len(sources),
        "items_filtered": len(filtered),
        "tokens_used": usage.get("total_tokens", 0),
    }
    report_md = generate_report(processed, today, headline, stats, config)
    logger.info(f"Report generated: {len(report_md)} characters")

    # Step 5: Publish
    publish_report(report_md, today, config)
    logger.info("=== Done ===")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
