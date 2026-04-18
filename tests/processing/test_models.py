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
