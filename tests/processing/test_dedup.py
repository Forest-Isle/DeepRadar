from deepradar.processing.dedup import _normalize_url, _normalize_title, deduplicate
from deepradar.processing.models import RawNewsItem, SourceType


def _make_item(title: str, url: str, source_name: str = "HN") -> RawNewsItem:
    return RawNewsItem(
        source=SourceType.HACKERNEWS,
        source_name=source_name,
        title=title,
        url=url,
    )


class TestNormalizeUrl:
    def test_strips_www(self):
        assert "example.com" in _normalize_url("https://www.example.com/page")

    def test_strips_tracking_params(self):
        result = _normalize_url("https://example.com/page?utm_source=twitter&id=1")
        assert "utm_source" not in result
        assert "id=1" in result

    def test_strips_trailing_slash(self):
        a = _normalize_url("https://example.com/page/")
        b = _normalize_url("https://example.com/page")
        assert a == b

    def test_lowercases_host(self):
        result = _normalize_url("https://EXAMPLE.COM/Page")
        assert "example.com" in result


class TestNormalizeTitle:
    def test_lowercases_and_strips(self):
        assert _normalize_title("  Hello  World  ") == "hello world"


class TestDeduplicate:
    def test_url_dedup(self):
        items = [
            _make_item("Article A", "https://example.com/post", "HN"),
            _make_item("Article A", "https://example.com/post", "Reddit"),
        ]
        result = deduplicate(items)
        assert len(result) == 1
        assert "Reddit" in result[0].metadata.get("also_on", [])

    def test_title_fuzzy_dedup(self):
        items = [
            _make_item("OpenAI Releases GPT-5", "https://a.com/1"),
            _make_item("OpenAI releases GPT-5 today", "https://b.com/2"),
        ]
        result = deduplicate(items)
        assert len(result) == 1

    def test_different_articles_kept(self):
        items = [
            _make_item("Completely different topic A", "https://a.com/1"),
            _make_item("Unrelated article B", "https://b.com/2"),
        ]
        result = deduplicate(items)
        assert len(result) == 2

    def test_empty_input(self):
        assert deduplicate([]) == []
