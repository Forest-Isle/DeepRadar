from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from deepradar.processing.models import ProcessedNewsItem, SourceResult, SourceType
from deepradar.report.templates import (
    BLOG_ITEM,
    BLOG_SECTION_HEADER,
    CHINA_SECTION_HEADER,
    CURATED_SECTION_HEADER,
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
    THREAD_ITEM,
    THREADS_SECTION,
    TLDR_ROW,
    TLDR_SECTION,
)

logger = logging.getLogger(__name__)


def _sort_by_importance(items: list[ProcessedNewsItem]) -> list[ProcessedNewsItem]:
    return sorted(items, key=lambda x: x.importance_score, reverse=True)


def _recurrence_badge(item: ProcessedNewsItem) -> str:
    """Badge marking an item already reported on a prior day."""
    rec = item.raw.metadata.get("recurring")
    if not rec:
        return ""
    days = rec.get("days", 1)
    if rec.get("escalated"):
        return f" 🔥 持续热点↑ {days}天"
    return f" 🔁 持续 {days}天"


def _cell(text: str, limit: int) -> str:
    """Sanitize text for a Markdown table cell."""
    text = (text or "").replace("\n", " ").replace("|", "/").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _render_threads(themes: list[dict[str, str]]) -> str:
    if not themes:
        return ""
    rows = ""
    for idx, t in enumerate(themes, 1):
        rows += THREAD_ITEM.format(
            idx=idx,
            title_zh=t.get("title_zh", ""),
            title_en=t.get("title_en", ""),
            summary_zh=t.get("summary_zh", ""),
        )
    return THREADS_SECTION.format(threads=rows)


def _render_tldr(items: list[ProcessedNewsItem], limit: int = 12) -> str:
    top = _sort_by_importance(items)[:limit]
    if not top:
        return ""
    rows = ""
    for idx, item in enumerate(top, 1):
        oneliner = item.summary_zh or item.why_it_matters_zh or item.raw.content
        rows += TLDR_ROW.format(
            idx=idx,
            title=_cell(item.raw.title, 60),
            url=item.raw.url,
            oneliner=_cell(oneliner, 44),
            source=_cell(item.raw.source_name, 18),
            score=f"{item.importance_score:.1f}",
        )
    return TLDR_SECTION.format(rows=rows)


def generate_report(
    items: list[ProcessedNewsItem],
    date_str: str,
    headline: dict[str, str],
    stats: dict[str, Any],
    config: dict[str, Any],
    themes: list[dict[str, str]] | None = None,
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
    arxiv_items = _sort_by_importance(
        [i for i in items if i.raw.source in (SourceType.ARXIV, SourceType.HF_PAPER)]
    )
    blog_items = _sort_by_importance([i for i in items if i.raw.source == SourceType.RSS_BLOG])
    newsletter_items = _sort_by_importance([i for i in items if i.raw.source == SourceType.NEWSLETTER])
    china_items = _sort_by_importance([i for i in items if i.raw.source == SourceType.CHINA])
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

    # Narrative threads + TL;DR table (high-density top-of-report)
    md += _render_threads(themes or [])
    md += _render_tldr(items)

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
            source_label += _recurrence_badge(item)

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
                title=item.raw.title + _recurrence_badge(item),
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

    # Curated Digests (newsletters)
    if newsletter_items:
        md += CURATED_SECTION_HEADER
        for item in newsletter_items:
            md += BLOG_ITEM.format(
                title=item.raw.title + _recurrence_badge(item),
                url=item.raw.url,
                source=item.raw.source_name,
                summary_en=item.summary_en,
                summary_zh=item.summary_zh,
            )

    # China AI (Chinese-language sources)
    if china_items:
        md += CHINA_SECTION_HEADER
        for item in china_items:
            md += BLOG_ITEM.format(
                title=item.raw.title + _recurrence_badge(item),
                url=item.raw.url,
                source=item.raw.source_name,
                summary_en=item.summary_zh or item.summary_en,
                summary_zh="",
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
            md += f"- **[{item.raw.title}]({item.raw.url})** ({source}){_recurrence_badge(item)}"
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
