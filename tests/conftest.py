import pytest

from deepradar.processing.models import (
    ProcessedNewsItem,
    RawNewsItem,
    SourceResult,
    SourceType,
)


@pytest.fixture
def sample_config():
    return {
        "settings": {
            "llm": {
                "model": "claude-sonnet-4-20250514",
                "max_tokens_per_request": 4096,
                "batch_size": 12,
                "max_concurrent_batches": 3,
                "temperature": 0.3,
            },
            "report": {
                "max_github_repos": 10,
                "max_news_items": 15,
                "max_papers": 10,
                "max_social_items": 10,
                "min_importance_score": 3.0,
            },
            "anthropic_api_key": "",
            "reports_repo": "",
        },
        "sources": {
            "hackernews": {"enabled": True},
            "arxiv": {"enabled": True},
            "github_trending": {"enabled": True},
        },
        "categories": {
            "ai_relevance_keywords": {
                "high": ["ai", "artificial intelligence", "machine learning", "llm"],
                "medium": ["model", "transformer", "embedding"],
                "low": ["automation"],
            },
            "categories": [
                {"name": "LLM", "keywords": ["gpt", "claude", "llama"], "weight": 1.2},
                {"name": "CV", "keywords": ["computer vision", "diffusion"], "weight": 1.0},
            ],
        },
    }


@pytest.fixture
def sample_raw_item():
    return RawNewsItem(
        source=SourceType.HACKERNEWS,
        source_name="Hacker News",
        title="New AI Model Breaks Records",
        url="https://example.com/ai-model",
        content="A new AI model has achieved SOTA results.",
        metadata={"score": 150, "comment_count": 45},
    )


@pytest.fixture
def sample_processed_item(sample_raw_item):
    return ProcessedNewsItem(
        raw=sample_raw_item,
        summary_en="A new AI model achieved state-of-the-art results.",
        summary_zh="一个新的 AI 模型达到了最先进的结果。",
        category="LLM / Foundation Models",
        importance_score=8.5,
        tags=["ai", "benchmark", "llm"],
        why_it_matters="Sets new performance records on key benchmarks.",
        why_it_matters_zh="在关键基准测试上创造了新的性能记录。",
    )


@pytest.fixture
def sample_source_results():
    return [
        SourceResult(name="hackernews", item_count=12),
        SourceResult(name="arxiv", item_count=25),
        SourceResult(name="github_trending", item_count=8),
        SourceResult(name="twitter_rss", item_count=0, error="All Nitter instances failed"),
    ]
