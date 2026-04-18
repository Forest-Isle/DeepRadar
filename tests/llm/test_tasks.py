import json
from unittest.mock import MagicMock

import pytest

from deepradar.llm.tasks import _parse_json, batch_summarize
from deepradar.processing.models import RawNewsItem, SourceType


def test_parse_json_plain():
    result = _parse_json('[{"key": "value"}]')
    assert result == [{"key": "value"}]


def test_parse_json_with_markdown_fences():
    text = '```json\n[{"key": "value"}]\n```'
    result = _parse_json(text)
    assert result == [{"key": "value"}]


def test_parse_json_with_bare_fences():
    text = '```\n[{"key": "value"}]\n```'
    result = _parse_json(text)
    assert result == [{"key": "value"}]


def _make_raw_item(title: str = "Test Item") -> RawNewsItem:
    return RawNewsItem(
        source=SourceType.HACKERNEWS,
        source_name="HN",
        title=title,
        url="https://example.com",
        content="Some content about AI",
    )


def _make_mock_client(response_json: list[dict]) -> MagicMock:
    client = MagicMock()
    client.complete.return_value = json.dumps(response_json)
    return client


@pytest.mark.asyncio
async def test_batch_summarize_returns_processed_items():
    items = [_make_raw_item("Item 1"), _make_raw_item("Item 2")]
    llm_response = [
        {
            "index": 0,
            "summary_en": "Summary 1",
            "summary_zh": "摘要 1",
            "category": "LLM",
            "importance_score": 8.0,
            "tags": ["ai"],
            "why_it_matters": "Important",
            "why_it_matters_zh": "很重要",
        },
        {
            "index": 1,
            "summary_en": "Summary 2",
            "summary_zh": "摘要 2",
            "category": "CV",
            "importance_score": 6.0,
            "tags": ["vision"],
            "why_it_matters": "Useful",
            "why_it_matters_zh": "有用",
        },
    ]
    client = _make_mock_client(llm_response)
    result = await batch_summarize(client, items, batch_size=12)
    assert len(result) == 2
    assert result[0].summary_en == "Summary 1"
    assert result[1].category == "CV"


@pytest.mark.asyncio
async def test_batch_summarize_fallback_on_error():
    items = [_make_raw_item()]
    client = MagicMock()
    client.complete.side_effect = RuntimeError("API down")
    result = await batch_summarize(client, items, batch_size=12)
    assert len(result) == 1
    assert result[0].summary_en == ""
    assert result[0].raw.title == "Test Item"
