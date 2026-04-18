from deepradar.processing.models import ProcessedNewsItem, RawNewsItem, SourceType
from deepradar.report.agent_report import generate_agent_report


def _make_agent_item(source: SourceType, title: str, score: float = 5.0) -> ProcessedNewsItem:
    return ProcessedNewsItem(
        raw=RawNewsItem(
            source=source,
            source_name=source.value,
            title=title,
            url="https://example.com",
        ),
        summary_en="English summary",
        summary_zh="中文摘要",
        importance_score=score,
        category="AI Agent",
        is_agent_related=True,
    )


def test_generate_agent_report_contains_header():
    items = [_make_agent_item(SourceType.ARXIV, "Multi-agent reasoning paper")]
    md = generate_agent_report(items, "2026-04-18")
    assert "AI Agent" in md
    assert "2026-04-18" in md


def test_generate_agent_report_sections():
    items = [
        _make_agent_item(SourceType.ARXIV, "Agent paper"),
        _make_agent_item(SourceType.RSS_BLOG, "LangChain release"),
        _make_agent_item(SourceType.REDDIT, "CrewAI discussion"),
    ]
    md = generate_agent_report(items, "2026-04-18")
    assert "论文与研究" in md or "Papers" in md
    assert "框架与工具" in md or "Frameworks" in md
    assert "产品与发布" in md or "Community" in md


def test_generate_agent_report_empty_items():
    md = generate_agent_report([], "2026-04-18")
    assert "AI Agent" in md
    assert "No agent-related items" in md or "暂无" in md


def test_generate_agent_report_all_items_listed():
    items = [_make_agent_item(SourceType.ARXIV, f"Paper {i}") for i in range(5)]
    md = generate_agent_report(items, "2026-04-18")
    for i in range(5):
        assert f"Paper {i}" in md
