from deepradar.processing.filter import filter_relevant
from deepradar.processing.models import RawNewsItem, SourceType


def _make_item(title: str, score: int = 0) -> RawNewsItem:
    return RawNewsItem(
        source=SourceType.HACKERNEWS,
        source_name="HN",
        title=title,
        url="https://example.com",
        metadata={"score": score},
    )


SAMPLE_CONFIG = {
    "categories": {
        "ai_relevance_keywords": {
            "high": ["ai", "llm"],
            "medium": ["model"],
            "low": [],
        },
        "categories": [],
    }
}


def test_filter_with_default_min_score():
    items = [_make_item("New AI model", score=50)]
    result = filter_relevant(items, SAMPLE_CONFIG)
    assert len(result) == 1


def test_filter_with_high_min_score_excludes_low_relevance():
    items = [_make_item("Random topic")]
    result = filter_relevant(items, SAMPLE_CONFIG, min_score=100.0)
    assert len(result) == 0


def test_filter_sorts_by_relevance():
    items = [
        _make_item("Just a model"),
        _make_item("AI and LLM breakthrough", score=200),
    ]
    result = filter_relevant(items, SAMPLE_CONFIG)
    assert result[0].title == "AI and LLM breakthrough"


def test_engagement_boost():
    item = _make_item("AI news", score=250)
    result = filter_relevant([item], SAMPLE_CONFIG)
    assert len(result) == 1
    assert result[0].metadata["relevance_score"] > 5.0
