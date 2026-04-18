from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import date
from typing import Any

from deepradar.config import load_config
from deepradar.notify import send_notification
from deepradar.llm.client import LLMClient
from deepradar.llm.tasks import batch_summarize, enrich_github_repos, generate_headline
from deepradar.processing.dedup import deduplicate
from deepradar.processing.filter import filter_relevant
from deepradar.processing.models import RawNewsItem, SourceResult
from deepradar.publish.github_publisher import publish_report
from deepradar.report.generator import generate_report
from deepradar.sources.arxiv_papers import ArxivSource
from deepradar.sources.github_trending import GitHubTrendingSource
from deepradar.sources.hackernews import HackerNewsSource
from deepradar.sources.reddit_rss import RedditRssSource
from deepradar.sources.rss_blogs import RssBlogsSource
from deepradar.sources.bluesky import BlueskySource
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
        BlueskySource,
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


async def _collect_all(sources: list) -> tuple[list[RawNewsItem], list[SourceResult]]:
    """Fetch from all sources concurrently. Returns items and per-source results."""
    tasks = [src.fetch() for src in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: list[RawNewsItem] = []
    source_results: list[SourceResult] = []

    for src, result in zip(sources, results):
        if isinstance(result, Exception):
            logger.error(f"Source {src.name} raised exception: {result}")
            source_results.append(SourceResult(name=src.name, error=str(result)))
        elif result:
            all_items.extend(result)
            source_results.append(SourceResult(name=src.name, item_count=len(result)))
        else:
            source_results.append(SourceResult(name=src.name, item_count=0))

    return all_items, source_results


async def run(args: argparse.Namespace | None = None) -> None:
    if args and args.config_dir:
        from pathlib import Path
        from deepradar.config import reset_config
        reset_config()
        config = load_config(Path(args.config_dir))
    else:
        config = load_config()

    if args:
        _apply_cli_overrides(config, args)

    _setup_logging(config)

    today = args.date if (args and args.date) else date.today().isoformat()
    logger.info(f"=== DeepRadar Daily Report: {today} ===")

    # Step 1: Collect from all sources
    sources = _init_sources(config)
    logger.info(f"Initialized {len(sources)} sources")

    raw_items, source_results = await _collect_all(sources)
    total_collected = len(raw_items)
    sources_active = sum(1 for r in source_results if r.error is None)
    logger.info(f"Collected {total_collected} raw items from {sources_active}/{len(sources)} sources")

    if not raw_items:
        logger.warning("No items collected. Aborting report generation.")
        return

    # Step 2: Deduplicate and filter
    deduped = deduplicate(raw_items)
    min_score = config.get("settings", {}).get("report", {}).get("min_importance_score", 2.0)
    filtered = filter_relevant(deduped, config, min_score=min_score)
    logger.info(f"After processing: {len(filtered)} items")

    # Step 3: LLM enrichment
    api_key = config.get("settings", {}).get("anthropic_api_key", "")
    if api_key:
        logger.info("Starting LLM processing...")
        client = LLMClient(config)
        batch_size = config.get("settings", {}).get("llm", {}).get("batch_size", 12)
        max_concurrent = config.get("settings", {}).get("llm", {}).get("max_concurrent_batches", 3)
        processed = await batch_summarize(client, filtered, batch_size=batch_size, max_concurrent=max_concurrent)
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
        "source_results": source_results,
    }
    report_md = generate_report(processed, today, headline, stats, config)
    logger.info(f"Report generated: {len(report_md)} characters")

    # Step 5: Publish
    publish_report(report_md, today, config)

    # Step 6: Notify
    webhook_url = config.get("settings", {}).get("webhook_url", "")
    if webhook_url:
        notif_cfg = config.get("settings", {}).get("notifications", {})
        should_notify = notif_cfg.get("on_success", True)
        if should_notify:
            await send_notification(webhook_url, {
                "date": today,
                "status": "success",
                "total_collected": total_collected,
                "items_in_report": len(processed),
                "sources": [r.model_dump() for r in source_results],
            })

    logger.info("=== Done ===")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="deepradar",
        description="DeepRadar — AI News Sniffer. Generate daily AI news reports.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Save report locally only, don't publish")
    parser.add_argument("--sources", type=str, default="", help="Comma-separated source names to enable (e.g. hackernews,arxiv)")
    parser.add_argument("--date", type=str, default="", help="Override report date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", type=str, default="", help="Override output directory")
    parser.add_argument("--config-dir", type=str, default="", help="Override config directory")
    parser.add_argument("--verbose", action="store_true", help="Set log level to DEBUG")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM enrichment")
    return parser.parse_args()


def _apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> None:
    """Apply CLI argument overrides to the loaded config."""
    if args.dry_run:
        config["settings"]["reports_repo"] = ""

    if args.sources:
        enabled_names = {s.strip() for s in args.sources.split(",")}
        for src_name, src_cfg in config.get("sources", {}).items():
            if isinstance(src_cfg, dict):
                src_cfg["enabled"] = src_name in enabled_names

    if args.verbose:
        config.setdefault("settings", {}).setdefault("general", {})["log_level"] = "DEBUG"

    if args.no_llm:
        config["settings"]["anthropic_api_key"] = ""

    if args.output_dir:
        config["settings"]["output_dir"] = args.output_dir


def main() -> None:
    args = _parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
