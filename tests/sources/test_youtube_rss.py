from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from deepradar.sources.youtube_rss import YouTubeRssSource

_SAMPLE_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015">
  <entry>
    <title>Amazing AI Video</title>
    <link href="https://www.youtube.com/watch?v=abc123"/>
    <yt:videoId>abc123</yt:videoId>
    <published>2026-04-18T05:00:00+00:00</published>
    <summary>Great summary</summary>
  </entry>
</feed>"""


def _make_config(invidious_instances=None):
    return {
        "sources": {
            "youtube_rss": {
                "enabled": True,
                "channels": [{"name": "Test Channel", "channel_id": "UCabc123"}],
                "lookback_hours": 48,
                "invidious_instances": invidious_instances or ["https://inv.nadeko.net"],
            }
        }
    }


def _mock_resp(status, text):
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


@pytest.mark.asyncio
async def test_fetch_from_youtube_primary():
    config = _make_config()
    source = YouTubeRssSource(config)

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.get.return_value = _mock_resp(200, _SAMPLE_FEED)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        items = await source.fetch()

    assert len(items) == 1
    assert items[0].title == "Amazing AI Video"
    call_urls = [str(c.args[0]) for c in mock_session.get.call_args_list]
    assert any("youtube.com" in u for u in call_urls)
    assert not any("inv.nadeko.net" in u for u in call_urls)


@pytest.mark.asyncio
async def test_fetch_falls_back_to_invidious():
    config = _make_config(invidious_instances=["https://inv.nadeko.net"])
    source = YouTubeRssSource(config)

    async def mock_get(url, **kwargs):
        if "youtube.com" in url:
            return _mock_resp(403, "")
        return _mock_resp(200, _SAMPLE_FEED)

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.get.side_effect = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        items = await source.fetch()

    assert len(items) == 1
    assert items[0].title == "Amazing AI Video"


@pytest.mark.asyncio
async def test_fetch_all_fail_returns_empty():
    config = _make_config(invidious_instances=["https://inv.nadeko.net"])
    source = YouTubeRssSource(config)

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.get.return_value = _mock_resp(403, "")
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        items = await source.fetch()

    assert items == []
