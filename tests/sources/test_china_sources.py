from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from deepradar.processing.models import SourceType
from deepradar.sources.china_sources import ChinaSourcesSource


def _rfc822(dt: datetime) -> str:
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _feed_xml(pubdate: str) -> str:
    return f"""<?xml version="1.0"?><rss version="2.0"><channel>
<item>
  <title>阿里发布首个具身大模型 Qwen-Robot 系列</title>
  <link>https://www.qbitai.com/p/1</link>
  <description>大模型与智能体的新进展</description>
  <pubDate>{pubdate}</pubDate>
</item>
</channel></rss>"""


def _cfg(enabled=True):
    return {
        "sources": {
            "china_sources": {
                "enabled": enabled,
                "feeds": [{"name": "量子位", "url": "https://www.qbitai.com/feed"}],
                "lookback_hours": 48,
                "max_items_per_feed": 8,
            }
        }
    }


@pytest.mark.asyncio
async def test_fetch_chinese_items(monkeypatch):
    source = ChinaSourcesSource(_cfg())

    async def fake_feed(session, url):
        return _feed_xml(_rfc822(datetime.now(timezone.utc) - timedelta(hours=2)))

    monkeypatch.setattr(source, "_fetch_feed", fake_feed)
    items = await source.fetch()

    assert len(items) == 1
    assert items[0].source == SourceType.CHINA
    assert items[0].source_name == "量子位"
    assert items[0].metadata["lang"] == "zh"
    assert "Qwen-Robot" in items[0].title


@pytest.mark.asyncio
async def test_disabled_returns_empty():
    source = ChinaSourcesSource(_cfg(enabled=False))
    assert await source.fetch() == []
