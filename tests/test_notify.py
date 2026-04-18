from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from deepradar.notify import send_notification


@pytest.mark.asyncio
async def test_send_notification_returns_false_on_empty_url():
    result = await send_notification("", {"data": "test"})
    assert result is False


@pytest.mark.asyncio
async def test_send_notification_returns_false_on_error():
    with patch("deepradar.notify.aiohttp.ClientSession") as MockSession:
        mock_session = AsyncMock()
        mock_session.post.side_effect = Exception("network error")
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=False)

        result = await send_notification("https://hooks.example.com/test", {"data": "test"})
        assert result is False


@pytest.mark.asyncio
async def test_send_notification_posts_json():
    mock_resp = AsyncMock()
    mock_resp.status = 200

    mock_post_ctx = AsyncMock()
    mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_post_ctx.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post.return_value = mock_post_ctx

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("deepradar.notify.aiohttp.ClientSession", return_value=mock_session_ctx):
        payload = {"date": "2026-04-18", "total_items": 42}
        result = await send_notification("https://hooks.example.com/test", payload)
        assert result is True
