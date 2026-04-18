from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


async def send_notification(webhook_url: str, payload: dict[str, Any]) -> bool:
    """Send a JSON POST to the configured webhook URL. Returns True on success."""
    if not webhook_url:
        return False

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status < 300:
                    logger.info(f"Notification sent (status {resp.status})")
                    return True
                else:
                    logger.warning(f"Notification failed with status {resp.status}")
                    return False
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False
