from __future__ import annotations

from deepradar.processing.models import ProcessedNewsItem, SourceType


_BLOG_SOURCES = {SourceType.RSS_BLOG, SourceType.TWITTER, SourceType.YOUTUBE}
_COMMUNITY_SOURCES = {SourceType.HACKERNEWS, SourceType.REDDIT}


def generate_agent_report(items: list[ProcessedNewsItem], date_str: str) -> str:
    """Generate a standalone AI Agent digest report in Markdown."""
    agent_items = [i for i in items if i.is_agent_related]
    agent_items.sort(key=lambda x: x.importance_score, reverse=True)

    md = f"# 🤖 AI Agent Daily Digest — {date_str}\n\n"
    md += "> 专注 AI Agent 领域的技术进展与生态动态\n\n---\n\n"

    if not agent_items:
        md += "暂无 agent 相关内容。\n"
        return md

    # Executive Summary
    md += "## 📋 Executive Summary\n\n"
    top = agent_items[:3]
    for item in top:
        summary = item.summary_zh or item.summary_en or item.raw.title
        md += f"- **[{item.raw.title}]({item.raw.url})**: {summary}\n"
    md += "\n---\n\n"

    # 框架与工具动态 (Blog / GitHub / Twitter / YouTube)
    framework_items = [i for i in agent_items if i.raw.source in _BLOG_SOURCES or i.raw.source == SourceType.GITHUB]
    if framework_items:
        md += "## 🔧 框架与工具动态 / Frameworks & Tools\n\n"
        for item in framework_items:
            md += f"### [{item.raw.title}]({item.raw.url})\n"
            md += f"**来源**: {item.raw.source_name}\n\n"
            if item.summary_en:
                md += f"{item.summary_en}\n\n"
            if item.summary_zh:
                md += f"{item.summary_zh}\n\n"
        md += "---\n\n"

    # 论文与研究 (arXiv)
    paper_items = [i for i in agent_items if i.raw.source == SourceType.ARXIV]
    if paper_items:
        md += "## 📄 论文与研究 / Papers & Research\n\n"
        for item in paper_items:
            authors = item.raw.metadata.get("authors", "")
            md += f"### [{item.raw.title}]({item.raw.url})\n"
            if authors:
                md += f"**Authors**: {authors}\n\n"
            if item.summary_en:
                md += f"{item.summary_en}\n\n"
            if item.summary_zh:
                md += f"{item.summary_zh}\n\n"
        md += "---\n\n"

    # 产品与发布 (HN / Reddit / Community)
    community_items = [i for i in agent_items if i.raw.source in _COMMUNITY_SOURCES]
    if community_items:
        md += "## 🚀 产品与发布 / Community & Products\n\n"
        for item in community_items:
            md += f"- **[{item.raw.title}]({item.raw.url})** ({item.raw.source_name})"
            summary = item.summary_zh or item.summary_en
            if summary:
                md += f" — {summary}"
            md += "\n"
        md += "\n---\n\n"

    # 原始条目列表
    md += "## 📑 全量条目 / All Items\n\n"
    for idx, item in enumerate(agent_items, 1):
        md += f"{idx}. [{item.raw.title}]({item.raw.url}) ({item.raw.source_name}, score={item.importance_score:.1f})\n"

    return md
