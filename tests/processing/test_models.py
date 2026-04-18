from deepradar.processing.models import SourceResult


def test_source_result_success():
    r = SourceResult(name="hackernews", item_count=12)
    assert r.name == "hackernews"
    assert r.item_count == 12
    assert r.error is None


def test_source_result_error():
    r = SourceResult(name="twitter_rss", item_count=0, error="Connection timeout")
    assert r.error == "Connection timeout"
    assert r.item_count == 0


def test_processed_news_item_has_is_agent_related():
    from deepradar.processing.models import ProcessedNewsItem, RawNewsItem, SourceType
    item = ProcessedNewsItem(
        raw=RawNewsItem(
            source=SourceType.ARXIV,
            source_name="arxiv",
            title="Test",
            url="https://example.com",
        )
    )
    assert item.is_agent_related is False


def test_processed_news_item_is_agent_related_can_be_true():
    from deepradar.processing.models import ProcessedNewsItem, RawNewsItem, SourceType
    item = ProcessedNewsItem(
        raw=RawNewsItem(
            source=SourceType.ARXIV,
            source_name="arxiv",
            title="Test",
            url="https://example.com",
        ),
        is_agent_related=True,
    )
    assert item.is_agent_related is True
