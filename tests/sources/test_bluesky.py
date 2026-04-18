from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from deepradar.sources.bluesky import BlueskySource
from deepradar.processing.models import SourceType


def _make_config(accounts=None, enabled=True):
    return {
        "sources": {
            "bluesky": {
                "enabled": enabled,
                "accounts": accounts or ["ylecun.bsky.social"],
                "lookback_hours": 48,
            }
        }
    }


def _make_post(text="Hello AI world", created_at=None):
    if created_at is None:
        created_at = "2026-04-18T06:00:00.000Z"
    return {
        "post": {
            "uri": "at://did:plc:abc/app.bsky.feed.post/123",
            "cid": "abc123",
            "author": {"handle": "ylecun.bsky.social", "displayName": "Yann LeCun"},
            "record": {"text": text, "createdAt": created_at},
            "indexedAt": created_at,
        }
    }


@pytest.mark.asyncio
async def test_fetch_returns_items():
    config = _make_config()
    source = BlueskySource(config)

    mock_response = {"feed": [_make_post("Exciting AI news!")]}

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get.return_value = mock_resp
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        items = await source.fetch()

    assert len(items) == 1
    assert items[0].source == SourceType.BLUESKY
    assert items[0].source_name == "@ylecun.bsky.social"
    assert "Exciting AI news!" in items[0].content


@pytest.mark.asyncio
async def test_fetch_skips_failed_handle():
    config = _make_config(accounts=["ylecun.bsky.social", "broken.bsky.social"])
    source = BlueskySource(config)

    good_response = {"feed": [_make_post("Good post")]}

    async def mock_get(url, **kwargs):
        mock_resp = AsyncMock()
        if "ylecun" in url:
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=good_response)
        else:
            mock_resp.status = 404
            mock_resp.json = AsyncMock(return_value={})
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        return mock_resp

    with patch("aiohttp.ClientSession") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.get.side_effect = mock_get
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        items = await source.fetch()

    assert len(items) == 1
    assert items[0].source_name == "@ylecun.bsky.social"


@pytest.mark.asyncio
async def test_fetch_disabled_returns_empty():
    config = _make_config(enabled=False)
    source = BlueskySource(config)
    items = await source.fetch()
    assert items == []
