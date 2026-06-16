from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from deepradar.processing.models import SourceType
from deepradar.sources.newsletters import NewslettersSource


def _rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _feed_xml(pubdate: str) -> str:
    return f"""<?xml version="1.0"?><rss version="2.0"><channel>
<item>
  <title>GPT-5 launch roundup</title>
  <link>https://news.smol.ai/p/1</link>
  <description>Big AI news: model release and agent benchmarks.</description>
  <pubDate>{pubdate}</pubDate>
</item>
</channel></rss>"""


def _cfg(enabled=True):
    return {
        "sources": {
            "newsletters": {
                "enabled": enabled,
                "feeds": [{"name": "AI News (smol.ai)", "url": "https://news.smol.ai/rss.xml"}],
                "lookback_hours": 72,
                "max_items_per_feed": 5,
            }
        }
    }


@pytest.mark.asyncio
async def test_fetch_parses_curated_items(monkeypatch):
    source = NewslettersSource(_cfg())

    async def fake_feed(session, url):
        return _feed_xml(_rfc822(datetime.now(timezone.utc) - timedelta(hours=2)))

    monkeypatch.setattr(source, "_fetch_feed", fake_feed)
    items = await source.fetch()

    assert len(items) == 1
    assert items[0].source == SourceType.NEWSLETTER
    assert items[0].source_name == "AI News (smol.ai)"
    assert items[0].metadata["curated"] is True


@pytest.mark.asyncio
async def test_old_items_filtered(monkeypatch):
    source = NewslettersSource(_cfg())

    async def fake_feed(session, url):
        return _feed_xml(_rfc822(datetime.now(timezone.utc) - timedelta(days=30)))

    monkeypatch.setattr(source, "_fetch_feed", fake_feed)
    assert await source.fetch() == []


@pytest.mark.asyncio
async def test_disabled_returns_empty():
    source = NewslettersSource(_cfg(enabled=False))
    assert await source.fetch() == []
