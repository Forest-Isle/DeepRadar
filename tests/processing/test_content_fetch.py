import pytest

from deepradar.processing import content_fetch
from deepradar.processing.content_fetch import _should_fetch, enrich_content
from deepradar.processing.models import RawNewsItem, SourceType


def _item(source: SourceType, url: str, content: str = "") -> RawNewsItem:
    return RawNewsItem(source=source, source_name="src", title="t", url=url, content=content)


_CFG = {"settings": {"content_fetch": {"enabled": True, "top_n": 25, "min_existing_chars": 600}}}


class TestShouldFetch:
    def test_external_hn_link_fetched(self):
        assert _should_fetch(_item(SourceType.HACKERNEWS, "https://blog.com/post"), 600)

    def test_long_content_skipped(self):
        assert not _should_fetch(_item(SourceType.HACKERNEWS, "https://blog.com/post", "x" * 700), 600)

    def test_github_source_skipped(self):
        assert not _should_fetch(_item(SourceType.GITHUB, "https://github.com/a/b"), 600)

    def test_platform_self_link_skipped(self):
        assert not _should_fetch(_item(SourceType.REDDIT, "https://reddit.com/r/x/abc"), 600)

    def test_pdf_skipped(self):
        assert not _should_fetch(_item(SourceType.RSS_BLOG, "https://x.com/paper.pdf"), 600)


@pytest.mark.asyncio
async def test_enrich_replaces_content_on_success(monkeypatch):
    async def fake_fetch(session, url):
        return "<html>full</html>"

    monkeypatch.setattr(content_fetch, "_fetch_html", fake_fetch)
    monkeypatch.setattr(content_fetch, "_extract", lambda html, url: "extracted article body " * 20)
    item = _item(SourceType.HACKERNEWS, "https://blog.com/post", "thin")
    await enrich_content([item], _CFG)
    assert item.metadata.get("content_fetched") is True
    assert "extracted article body" in item.content


@pytest.mark.asyncio
async def test_enrich_keeps_original_on_fetch_failure(monkeypatch):
    async def fake_fetch(session, url):
        return None

    monkeypatch.setattr(content_fetch, "_fetch_html", fake_fetch)
    monkeypatch.setattr(content_fetch, "_extract", lambda html, url: "should not be used")
    item = _item(SourceType.HACKERNEWS, "https://blog.com/post", "thin")
    await enrich_content([item], _CFG)
    assert item.content == "thin"
    assert "content_fetched" not in item.metadata


@pytest.mark.asyncio
async def test_enrich_disabled_is_noop():
    item = _item(SourceType.HACKERNEWS, "https://blog.com/post", "thin")
    await enrich_content([item], {"settings": {"content_fetch": {"enabled": False}}})
    assert item.content == "thin"
