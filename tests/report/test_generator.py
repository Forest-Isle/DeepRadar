from deepradar.processing.models import (
    ProcessedNewsItem,
    RawNewsItem,
    SourceResult,
    SourceType,
)
from deepradar.report.generator import generate_report


MINIMAL_CONFIG = {
    "settings": {
        "report": {
            "max_github_repos": 10,
            "max_news_items": 15,
            "max_papers": 10,
            "max_social_items": 10,
        }
    }
}

HEADLINE = {
    "headline_en": "Test Headline",
    "headline_zh": "测试标题",
    "summary_en": "Test summary.",
    "summary_zh": "测试摘要。",
}


def _make_processed(source: SourceType, title: str, score: float = 5.0) -> ProcessedNewsItem:
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
        category="LLM",
    )


def test_report_contains_header():
    md = generate_report([], "2026-04-18", HEADLINE, {}, MINIMAL_CONFIG)
    assert "DeepRadar AI Daily" in md
    assert "Test Headline" in md


def test_report_contains_github_section():
    items = [_make_processed(SourceType.GITHUB, "cool/repo")]
    items[0].raw.metadata = {"stars_today": 50, "total_stars": 1000, "language": "Python"}
    md = generate_report(items, "2026-04-18", HEADLINE, {}, MINIMAL_CONFIG)
    assert "Hot GitHub Repos" in md
    assert "cool/repo" in md


def test_report_footer_shows_source_status():
    source_results = [
        SourceResult(name="hackernews", item_count=12),
        SourceResult(name="arxiv", item_count=5),
        SourceResult(name="twitter_rss", item_count=0, error="Connection timeout"),
    ]
    stats = {
        "total_collected": 17,
        "sources_active": 2,
        "sources_total": 3,
        "items_filtered": 10,
        "tokens_used": 500,
        "source_results": source_results,
    }
    md = generate_report([], "2026-04-18", HEADLINE, stats, MINIMAL_CONFIG)
    assert "hackernews: 12 items" in md
    assert "twitter_rss: ERROR" in md


def test_report_respects_max_items():
    items = [_make_processed(SourceType.HACKERNEWS, f"Item {i}") for i in range(20)]
    config = {
        "settings": {
            "report": {
                "max_github_repos": 10,
                "max_news_items": 5,
                "max_papers": 10,
                "max_social_items": 10,
            }
        }
    }
    md = generate_report(items, "2026-04-18", HEADLINE, {}, config)
    assert md.count("###") <= 6
