from __future__ import annotations

import pytest

from deepradar.processing.models import SourceType
from deepradar.sources.hf_papers import HFPapersSource


def _cfg(enabled=True, min_upvotes=3):
    return {
        "sources": {
            "hf_papers": {
                "enabled": enabled,
                "api_url": "https://huggingface.co/api/daily_papers",
                "max_results": 30,
                "min_upvotes": min_upvotes,
            }
        }
    }


_DATA = [
    {
        "paper": {
            "id": "2406.00001",
            "title": "Great Agent Paper",
            "summary": "agentic reasoning breakthrough",
            "upvotes": 42,
            "authors": [{"name": "Alice"}, {"name": "Bob"}],
            "publishedAt": "2026-06-15T00:00:00.000Z",
        }
    },
    {"paper": {"id": "2406.00002", "title": "Low Signal Paper", "summary": "x", "upvotes": 1, "authors": []}},
]


@pytest.mark.asyncio
async def test_fetch_filters_by_upvotes(monkeypatch):
    source = HFPapersSource(_cfg())

    async def fake_json(session, url):
        return _DATA

    monkeypatch.setattr(source, "_fetch_json", fake_json)
    items = await source.fetch()

    assert len(items) == 1
    item = items[0]
    assert item.source == SourceType.HF_PAPER
    assert item.url == "https://huggingface.co/papers/2406.00001"
    assert item.metadata["upvotes"] == 42
    assert "▲42" in item.metadata["categories"][0]
    assert item.metadata["authors"] == "Alice, Bob"


@pytest.mark.asyncio
async def test_disabled_returns_empty():
    source = HFPapersSource(_cfg(enabled=False))
    assert await source.fetch() == []
