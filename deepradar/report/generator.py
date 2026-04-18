from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from deepradar.processing.models import ProcessedNewsItem, SourceResult, SourceType
from deepradar.report.templates import (
    BLOG_ITEM,
    BLOG_SECTION_HEADER,
    GITHUB_DETAIL,
    GITHUB_SECTION_HEADER,
    GITHUB_TABLE_ROW,
    NEWS_ITEM,
    NEWS_SECTION_HEADER,
    PAPER_ITEM,
    PAPERS_SECTION_HEADER,
    REPORT_FOOTER,
    REPORT_HEADER,
    SOCIAL_ITEM,
    SOCIAL_REDDIT_HEADER,
    SOCIAL_SECTION_HEADER,
    SOCIAL_TWITTER_HEADER,
    SOCIAL_YOUTUBE_HEADER,
    SOURCE_STATUS_ITEM,
)

logger = logging.getLogger(__name__)


def _sort_by_importance(items: list[ProcessedNewsItem]) -> list[ProcessedNewsItem]:
    return sorted(items, key=lambda x: x.importance_score, reverse=True)


def generate_report(
    items: list[ProcessedNewsItem],
    date_str: str,
    headline: dict[str, str],
    stats: dict[str, Any],
    config: dict[str, Any],
) -> str:
    """Generate the full Markdown report."""
    report_cfg = config.get("settings", {}).get("report", {})
    max_repos = report_cfg.get("max_github_repos", 10)
    max_news = report_cfg.get("max_news_items", 15)
    max_papers = report_cfg.get("max_papers", 10)
    max_social = report_cfg.get("max_social_items", 10)

    # Group items by source type
    github_items = _sort_by_importance([i for i in items if i.raw.source == SourceType.GITHUB])
    hn_items = _sort_by_importance([i for i in items if i.raw.source == SourceType.HACKERNEWS])
    arxiv_items = _sort_by_importance([i for i in items if i.raw.source == SourceType.ARXIV])
    blog_items = _sort_by_importance([i for i in items if i.raw.source == SourceType.RSS_BLOG])
    twitter_items = _sort_by_importance([i for i in items if i.raw.source == SourceType.TWITTER])
    reddit_items = _sort_by_importance([i for i in items if i.raw.source == SourceType.REDDIT])
    youtube_items = _sort_by_importance([i for i in items if i.raw.source == SourceType.YOUTUBE])

    md = ""

    # Header
    md += REPORT_HEADER.format(
        date=date_str,
        headline_en=headline.get("headline_en", "AI Daily Report"),
        headline_zh=headline.get("headline_zh", "AI 每日报告"),
        summary_en=headline.get("summary_en", ""),
        summary_zh=headline.get("summary_zh", ""),
    )

    # GitHub Repos
    if github_items:
        md += GITHUB_SECTION_HEADER
        for idx, item in enumerate(github_items[:max_repos], 1):
            md += GITHUB_TABLE_ROW.format(
                idx=idx,
                name=item.raw.title,
                url=item.raw.url,
                stars_today=item.raw.metadata.get("stars_today", 0),
                total_stars=item.raw.metadata.get("total_stars", 0),
                language=item.raw.metadata.get("language", "—"),
                category=item.category or "—",
            )
        md += "\n"
        for item in github_items[:max_repos]:
            md += GITHUB_DETAIL.format(
                name=item.raw.title,
                url=item.raw.url,
                why_en=item.why_it_matters or item.summary_en,
                why_zh=item.why_it_matters_zh or item.summary_zh,
                summary_en=item.summary_en,
                summary_zh=item.summary_zh,
            )

    # Top AI News (HN + cross-source high-importance items)
    news_items = _sort_by_importance(hn_items + reddit_items)
    if news_items:
        md += NEWS_SECTION_HEADER
        for idx, item in enumerate(news_items[:max_news], 1):
            also_on = item.raw.metadata.get("also_on", [])
            source_label = item.raw.source_name
            if also_on:
                source_label += f" (also on {', '.join(also_on)})"

            md += NEWS_ITEM.format(
                idx=idx,
                title=item.raw.title,
                url=item.raw.url,
                source=source_label,
                score=f"{item.importance_score:.1f}",
                category=item.category or "—",
                summary_en=item.summary_en,
                summary_zh=item.summary_zh,
                why_en=item.why_it_matters,
                why_zh=item.why_it_matters_zh,
            )

    # Notable Papers
    if arxiv_items:
        md += PAPERS_SECTION_HEADER
        for idx, item in enumerate(arxiv_items[:max_papers], 1):
            md += PAPER_ITEM.format(
                idx=idx,
                title=item.raw.title,
                url=item.raw.url,
                authors=item.raw.metadata.get("authors", "—"),
                categories=", ".join(item.raw.metadata.get("categories", [])),
                summary_en=item.summary_en,
                summary_zh=item.summary_zh,
            )

    # Industry Updates (Blog posts)
    if blog_items:
        md += BLOG_SECTION_HEADER
        for item in blog_items:
            md += BLOG_ITEM.format(
                title=item.raw.title,
                url=item.raw.url,
                source=item.raw.source_name,
                summary_en=item.summary_en,
                summary_zh=item.summary_zh,
            )

    # Social Media Highlights
    has_social = twitter_items or youtube_items
    if has_social:
        md += SOCIAL_SECTION_HEADER

        if twitter_items:
            md += SOCIAL_TWITTER_HEADER
            for item in twitter_items[:max_social]:
                md += SOCIAL_ITEM.format(
                    source=item.raw.source_name,
                    title=item.raw.title[:100],
                    url=item.raw.url,
                    summary=item.summary_en or item.raw.content[:100],
                )
            md += "\n"

        if youtube_items:
            md += SOCIAL_YOUTUBE_HEADER
            for item in youtube_items[:max_social]:
                md += SOCIAL_ITEM.format(
                    source=item.raw.source_name,
                    title=item.raw.title,
                    url=item.raw.url,
                    summary=item.summary_en or item.raw.content[:100],
                )
            md += "\n"

    # AI Agent 专题板块
    agent_items = _sort_by_importance([i for i in items if i.is_agent_related])
    if agent_items:
        md += "\n---\n\n## 🤖 AI Agent 专题 / Agent Focus\n\n"
        for item in agent_items[:10]:
            source = item.raw.source_name
            summary = item.summary_zh or item.summary_en or ""
            md += f"- **[{item.raw.title}]({item.raw.url})** ({source})"
            if summary:
                md += f" — {summary}"
            md += "\n"
        md += "\n"

    # Footer
    source_results: list[SourceResult] = stats.get("source_results", [])
    source_status = ""
    for sr in source_results:
        if sr.error:
            source_status += SOURCE_STATUS_ITEM.format(name=sr.name, status=f"ERROR — {sr.error}")
        else:
            source_status += SOURCE_STATUS_ITEM.format(name=sr.name, status=f"{sr.item_count} items")

    md += REPORT_FOOTER.format(
        total_collected=stats.get("total_collected", 0),
        sources_active=stats.get("sources_active", 0),
        sources_total=stats.get("sources_total", 7),
        items_filtered=stats.get("items_filtered", 0),
        items_in_report=len(items),
        tokens_used=stats.get("tokens_used", 0),
        source_status=source_status or "- No source data available\n",
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )

    return md
