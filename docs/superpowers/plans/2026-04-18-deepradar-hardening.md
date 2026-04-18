# DeepRadar Hardening & Usability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DeepRadar correct, testable, and usable as a daily tool by fixing config gaps, adding tests, improving robustness, and providing CLI control.

**Architecture:** Incremental improvements to the existing pipeline. New shared utility modules (`processing/utils.py`, `processing/keywords.py`, `notify.py`) extract duplicated logic. Config wiring connects declared-but-unused settings. CLI wraps the existing `run()` function with argument overrides. Tests mirror the source tree under `tests/`.

**Tech Stack:** Python 3.10+, pytest, pytest-asyncio, aioresponses, aiohttp, pydantic

---

## File Structure

**New files to create:**

| File | Responsibility |
|------|---------------|
| `deepradar/processing/utils.py` | Shared `strip_html()` utility |
| `deepradar/processing/keywords.py` | Config-driven `is_ai_related()` |
| `deepradar/notify.py` | Webhook notification on run completion |
| `tests/conftest.py` | Shared fixtures: sample config, sample items |
| `tests/processing/test_utils.py` | Tests for `strip_html` |
| `tests/processing/test_keywords.py` | Tests for `is_ai_related` |
| `tests/processing/test_dedup.py` | Tests for URL normalization, fuzzy title dedup |
| `tests/processing/test_filter.py` | Tests for relevance scoring, min_score |
| `tests/llm/test_tasks.py` | Tests for JSON parsing, batch summarize |
| `tests/report/test_generator.py` | Tests for report section rendering |
| `tests/test_config.py` | Tests for config loading, env overrides |
| `tests/test_notify.py` | Tests for webhook sending |

**Files to modify:**

| File | Changes |
|------|---------|
| `deepradar/processing/models.py` | Add `SourceResult` model |
| `deepradar/sources/hackernews.py` | Remove `AI_KEYWORDS`, use `keywords.py` |
| `deepradar/sources/github_trending.py` | Use `keywords.py` instead of importing from hackernews |
| `deepradar/sources/rss_blogs.py` | Use `utils.strip_html`, fix inline import |
| `deepradar/sources/reddit_rss.py` | Use `utils.strip_html`, fix inline import |
| `deepradar/sources/twitter_rss.py` | Use `utils.strip_html`, fix inline import |
| `deepradar/llm/tasks.py` | Make `batch_summarize` async with concurrency |
| `deepradar/config.py` | Add webhook URL env var |
| `deepradar/main.py` | CLI args, wire config values, SourceResult, notification |
| `deepradar/report/generator.py` | Accept source_results, render per-source status |
| `deepradar/report/templates.py` | Add `SOURCE_STATUS_ITEM` template |
| `config/settings.yaml` | Add `notifications` section |

---

### Task 1: Create `processing/utils.py` with `strip_html`

**Files:**
- Create: `tests/processing/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/processing/test_utils.py`
- Create: `deepradar/processing/utils.py`

- [ ] **Step 1: Create test directory structure and write the failing test**

Create empty `__init__.py` files and the test:

```python
# tests/__init__.py — empty

# tests/processing/__init__.py — empty
```

```python
# tests/processing/test_utils.py
from deepradar.processing.utils import strip_html


def test_strip_html_removes_tags():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_handles_plain_text():
    assert strip_html("no tags here") == "no tags here"


def test_strip_html_handles_empty_string():
    assert strip_html("") == ""


def test_strip_html_strips_whitespace():
    assert strip_html("  <p>  spaced  </p>  ") == "spaced"


def test_strip_html_handles_nested_tags():
    assert strip_html("<div><p>nested <a href='#'>link</a></p></div>") == "nested link"


def test_strip_html_preserves_entities():
    assert strip_html("&amp; &lt; &gt;") == "& < >"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/processing/test_utils.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'deepradar.processing.utils'`

- [ ] **Step 3: Write minimal implementation**

```python
# deepradar/processing/utils.py
from __future__ import annotations

import html
import re

_TAG_RE = re.compile(r"<[^>]+>")


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities."""
    if not text:
        return ""
    cleaned = _TAG_RE.sub("", text)
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/processing/test_utils.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/__init__.py tests/processing/__init__.py tests/processing/test_utils.py deepradar/processing/utils.py
git commit -m "feat: add strip_html utility with tests"
```

---

### Task 2: Create `processing/keywords.py` with `is_ai_related`

**Files:**
- Create: `tests/processing/test_keywords.py`
- Create: `deepradar/processing/keywords.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/processing/test_keywords.py
from deepradar.processing.keywords import is_ai_related


SAMPLE_CONFIG = {
    "categories": {
        "ai_relevance_keywords": {
            "high": ["ai", "machine learning", "llm"],
            "medium": ["transformer", "embedding"],
            "low": ["automation"],
        },
        "categories": [
            {"name": "LLM", "keywords": ["gpt", "claude"], "weight": 1.2},
            {"name": "CV", "keywords": ["computer vision", "diffusion"], "weight": 1.0},
        ],
    }
}


def test_matches_high_keyword():
    assert is_ai_related("New AI model released", "", SAMPLE_CONFIG) is True


def test_matches_category_keyword():
    assert is_ai_related("GPT-5 announced", "", SAMPLE_CONFIG) is True


def test_no_match():
    assert is_ai_related("Cooking recipes today", "best pasta ever", SAMPLE_CONFIG) is False


def test_matches_in_text_body():
    assert is_ai_related("Untitled", "uses machine learning for predictions", SAMPLE_CONFIG) is True


def test_case_insensitive():
    assert is_ai_related("NEW LLM BENCHMARK", "", SAMPLE_CONFIG) is True


def test_empty_config_returns_false():
    assert is_ai_related("anything", "", {"categories": {}}) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/processing/test_keywords.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'deepradar.processing.keywords'`

- [ ] **Step 3: Write minimal implementation**

```python
# deepradar/processing/keywords.py
from __future__ import annotations

from typing import Any


def _collect_keywords(config: dict[str, Any]) -> set[str]:
    """Extract all AI-related keywords from categories config into a single set."""
    categories_cfg = config.get("categories", {})
    keywords: set[str] = set()

    kw_cfg = categories_cfg.get("ai_relevance_keywords", {})
    for level in ("high", "medium", "low"):
        for kw in kw_cfg.get(level, []):
            keywords.add(kw.lower())

    for cat in categories_cfg.get("categories", []):
        for kw in cat.get("keywords", []):
            keywords.add(kw.lower())

    return keywords


def is_ai_related(title: str, text: str, config: dict[str, Any]) -> bool:
    """Check if title+text contains any AI-related keyword from config."""
    keywords = _collect_keywords(config)
    if not keywords:
        return False
    combined = f"{title} {text}".lower()
    return any(kw in combined for kw in keywords)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/processing/test_keywords.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add tests/processing/test_keywords.py deepradar/processing/keywords.py
git commit -m "feat: add config-driven is_ai_related with tests"
```

---

### Task 3: Add `SourceResult` to `processing/models.py`

**Files:**
- Modify: `deepradar/processing/models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/processing/test_models.py
from deepradar.processing.models import SourceResult


def test_source_result_success():
    r = SourceResult(name="hackernews", item_count=12)
    assert r.name == "hackernews"
    assert r.item_count == 12
    assert r.error is None


def test_source_result_error():
    r = SourceResult(name="twitter_rss", item_count=0, error="Connection timeout")
    assert r.error == "Connection timeout"
    assert r.item_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/processing/test_models.py -v`
Expected: FAIL with `ImportError: cannot import name 'SourceResult'`

- [ ] **Step 3: Add SourceResult to models.py**

Add at the end of `deepradar/processing/models.py`:

```python
class SourceResult(BaseModel):
    """Result of a single source fetch — used for run summary."""

    name: str
    item_count: int = 0
    error: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/processing/test_models.py -v`
Expected: All 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add deepradar/processing/models.py tests/processing/test_models.py
git commit -m "feat: add SourceResult model"
```

---

### Task 4: Update RSS sources to use shared `strip_html`

**Files:**
- Modify: `deepradar/sources/rss_blogs.py`
- Modify: `deepradar/sources/reddit_rss.py`
- Modify: `deepradar/sources/twitter_rss.py`

- [ ] **Step 1: Update `rss_blogs.py`**

In `deepradar/sources/rss_blogs.py`:

Add import at top of file (after the existing imports):
```python
from deepradar.processing.utils import strip_html
```

Replace the inline HTML stripping block (lines 66-68):
```python
                        # Strip HTML tags simply
                        if "<" in summary:
                            import re
                            summary = re.sub(r"<[^>]+>", "", summary).strip()
```
With:
```python
                        summary = strip_html(summary)
```

- [ ] **Step 2: Update `reddit_rss.py`**

In `deepradar/sources/reddit_rss.py`:

Add import at top of file (after the existing imports):
```python
from deepradar.processing.utils import strip_html
```

Replace the inline HTML stripping block (lines 59-61):
```python
                        content = entry.get("summary", "")
                        import re
                        if "<" in content:
                            content = re.sub(r"<[^>]+>", "", content).strip()
```
With:
```python
                        content = strip_html(entry.get("summary", ""))
```

- [ ] **Step 3: Update `twitter_rss.py`**

In `deepradar/sources/twitter_rss.py`:

Add import at top of file (after the existing imports):
```python
from deepradar.processing.utils import strip_html
```

Replace the inline HTML stripping block (lines 65-68):
```python
                        content = entry.get("summary", entry.get("title", ""))
                        import re
                        if "<" in content:
                            content = re.sub(r"<[^>]+>", "", content).strip()
```
With:
```python
                        content = strip_html(entry.get("summary", entry.get("title", "")))
```

- [ ] **Step 4: Run existing tests to verify nothing broke**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add deepradar/sources/rss_blogs.py deepradar/sources/reddit_rss.py deepradar/sources/twitter_rss.py
git commit -m "refactor: use shared strip_html in RSS sources"
```

---

### Task 5: Update HN and GitHub Trending to use shared keywords

**Files:**
- Modify: `deepradar/sources/hackernews.py`
- Modify: `deepradar/sources/github_trending.py`

- [ ] **Step 1: Update `hackernews.py`**

In `deepradar/sources/hackernews.py`:

Remove the `AI_KEYWORDS` set (lines 15-25) and `_is_ai_related` function (lines 28-30).

Add import at top:
```python
from deepradar.processing.keywords import is_ai_related
```

Replace `_is_ai_related(title)` call on line 82:
```python
                    if not _is_ai_related(title):
                        continue
```
With:
```python
                    if not is_ai_related(title, "", self.config):
                        continue
```

- [ ] **Step 2: Update `github_trending.py`**

In `deepradar/sources/github_trending.py`:

Remove the import from hackernews (line 13):
```python
from deepradar.sources.hackernews import AI_KEYWORDS, _is_ai_related
```

Add import:
```python
from deepradar.processing.keywords import is_ai_related
```

Replace `_is_ai_related(repo_path, description)` call on line 98:
```python
                if not _is_ai_related(repo_path, description):
                    continue
```
With:
```python
                if not is_ai_related(repo_path, description, self.config):
                    continue
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add deepradar/sources/hackernews.py deepradar/sources/github_trending.py
git commit -m "refactor: use config-driven keywords instead of hardcoded AI_KEYWORDS"
```

---

### Task 6: Wire `min_importance_score` from config

**Files:**
- Modify: `deepradar/main.py:99-100`
- Create: `tests/processing/test_filter.py`

- [ ] **Step 1: Write test for filter with configurable min_score**

```python
# tests/processing/test_filter.py
from deepradar.processing.filter import filter_relevant
from deepradar.processing.models import RawNewsItem, SourceType


def _make_item(title: str, score: int = 0) -> RawNewsItem:
    return RawNewsItem(
        source=SourceType.HACKERNEWS,
        source_name="HN",
        title=title,
        url="https://example.com",
        metadata={"score": score},
    )


SAMPLE_CONFIG = {
    "categories": {
        "ai_relevance_keywords": {
            "high": ["ai", "llm"],
            "medium": ["model"],
            "low": [],
        },
        "categories": [],
    }
}


def test_filter_with_default_min_score():
    items = [_make_item("New AI model", score=50)]
    result = filter_relevant(items, SAMPLE_CONFIG)
    assert len(result) == 1


def test_filter_with_high_min_score_excludes_low_relevance():
    items = [_make_item("Random topic")]
    result = filter_relevant(items, SAMPLE_CONFIG, min_score=100.0)
    assert len(result) == 0


def test_filter_sorts_by_relevance():
    items = [
        _make_item("Just a model"),
        _make_item("AI and LLM breakthrough", score=200),
    ]
    result = filter_relevant(items, SAMPLE_CONFIG)
    assert result[0].title == "AI and LLM breakthrough"


def test_engagement_boost():
    item = _make_item("AI news", score=250)
    result = filter_relevant([item], SAMPLE_CONFIG)
    assert len(result) == 1
    assert result[0].metadata["relevance_score"] > 5.0
```

- [ ] **Step 2: Run test to verify it passes (these test existing behavior)**

Run: `pytest tests/processing/test_filter.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Wire config value in `main.py`**

In `deepradar/main.py`, replace line 100:
```python
    filtered = filter_relevant(deduped, config)
```
With:
```python
    min_score = config.get("settings", {}).get("report", {}).get("min_importance_score", 2.0)
    filtered = filter_relevant(deduped, config, min_score=min_score)
```

- [ ] **Step 4: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add deepradar/main.py tests/processing/test_filter.py
git commit -m "feat: wire min_importance_score from config to filter_relevant"
```

---

### Task 7: Make `batch_summarize` async with concurrency control

**Files:**
- Modify: `deepradar/llm/tasks.py`
- Modify: `deepradar/main.py`
- Create: `tests/llm/__init__.py`
- Create: `tests/llm/test_tasks.py`

- [ ] **Step 1: Write tests for batch_summarize and JSON parsing**

```python
# tests/llm/__init__.py — empty

# tests/llm/test_tasks.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/llm/test_tasks.py -v`
Expected: FAIL because `batch_summarize` is not async yet

- [ ] **Step 3: Make `batch_summarize` async in `tasks.py`**

Replace the `batch_summarize` function in `deepradar/llm/tasks.py` with:

```python
async def batch_summarize(
    client: LLMClient,
    items: list[RawNewsItem],
    batch_size: int = 12,
    max_concurrent: int = 3,
) -> list[ProcessedNewsItem]:
    """Process items through Claude API in concurrent batches."""
    import asyncio

    sem = asyncio.Semaphore(max_concurrent)
    results: list[ProcessedNewsItem] = []
    lock = asyncio.Lock()

    async def _process_batch(batch: list[RawNewsItem], batch_num: int) -> None:
        async with sem:
            items_json = _items_to_json(batch)
            prompt = BATCH_SUMMARIZE_PROMPT.format(items_json=items_json)

            try:
                response = await asyncio.to_thread(client.complete, SYSTEM_PROMPT, prompt)
                parsed = _parse_json(response)

                batch_results = []
                for entry in parsed:
                    idx = entry.get("index", 0)
                    if idx >= len(batch):
                        continue
                    raw = batch[idx]
                    batch_results.append(
                        ProcessedNewsItem(
                            raw=raw,
                            summary_en=entry.get("summary_en", ""),
                            summary_zh=entry.get("summary_zh", ""),
                            category=entry.get("category", "Other"),
                            importance_score=float(entry.get("importance_score", 5.0)),
                            tags=entry.get("tags", []),
                            why_it_matters=entry.get("why_it_matters", ""),
                            why_it_matters_zh=entry.get("why_it_matters_zh", ""),
                        )
                    )
                logger.info(f"Batch {batch_num}: processed {len(parsed)} items")
                async with lock:
                    results.extend(batch_results)
            except Exception as e:
                logger.error(f"LLM batch processing failed: {e}")
                async with lock:
                    for raw in batch:
                        results.append(ProcessedNewsItem(raw=raw))

    tasks = []
    for i, batch_start in enumerate(range(0, len(items), batch_size)):
        batch = items[batch_start : batch_start + batch_size]
        tasks.append(_process_batch(batch, i + 1))

    await asyncio.gather(*tasks)
    return results
```

- [ ] **Step 4: Update call site in `main.py`**

In `deepradar/main.py`, replace line 109:
```python
        processed = batch_summarize(client, filtered, batch_size=batch_size)
```
With:
```python
        max_concurrent = config.get("settings", {}).get("llm", {}).get("max_concurrent_batches", 3)
        processed = await batch_summarize(client, filtered, batch_size=batch_size, max_concurrent=max_concurrent)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/llm/test_tasks.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add deepradar/llm/tasks.py deepradar/main.py tests/llm/__init__.py tests/llm/test_tasks.py
git commit -m "feat: make batch_summarize async with configurable concurrency"
```

---

### Task 8: Update `_collect_all` to return `SourceResult` list

**Files:**
- Modify: `deepradar/main.py:60-76`

- [ ] **Step 1: Rewrite `_collect_all` to return SourceResult**

In `deepradar/main.py`, add to imports:
```python
from deepradar.processing.models import RawNewsItem, SourceResult
```
(Replace the existing `from deepradar.processing.models import RawNewsItem` line.)

Replace the `_collect_all` function:
```python
async def _collect_all(sources: list) -> tuple[list[RawNewsItem], list[SourceResult]]:
    """Fetch from all sources concurrently. Returns items and per-source results."""
    tasks = [src.fetch() for src in sources]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_items: list[RawNewsItem] = []
    source_results: list[SourceResult] = []

    for src, result in zip(sources, results):
        if isinstance(result, Exception):
            logger.error(f"Source {src.name} raised exception: {result}")
            source_results.append(SourceResult(name=src.name, error=str(result)))
        elif result:
            all_items.extend(result)
            source_results.append(SourceResult(name=src.name, item_count=len(result)))
        else:
            source_results.append(SourceResult(name=src.name, item_count=0))

    return all_items, source_results
```

- [ ] **Step 2: Update callers in `run()`**

Replace lines that unpack the old tuple:
```python
    raw_items, sources_active = await _collect_all(sources)
    total_collected = len(raw_items)
    logger.info(f"Collected {total_collected} raw items from {sources_active}/{len(sources)} sources")
```
With:
```python
    raw_items, source_results = await _collect_all(sources)
    total_collected = len(raw_items)
    sources_active = sum(1 for r in source_results if r.error is None)
    logger.info(f"Collected {total_collected} raw items from {sources_active}/{len(sources)} sources")
```

Also update the `stats` dict to include `source_results`:
```python
    stats = {
        "total_collected": total_collected,
        "sources_active": sources_active,
        "sources_total": len(sources),
        "items_filtered": len(filtered),
        "tokens_used": usage.get("total_tokens", 0),
        "source_results": source_results,
    }
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add deepradar/main.py
git commit -m "feat: collect_all returns SourceResult list for per-source tracking"
```

---

### Task 9: Update report footer with per-source status

**Files:**
- Modify: `deepradar/report/templates.py`
- Modify: `deepradar/report/generator.py`
- Create: `tests/report/__init__.py`
- Create: `tests/report/test_generator.py`

- [ ] **Step 1: Write the test**

```python
# tests/report/__init__.py — empty

# tests/report/test_generator.py
from deepradar.processing.models import (
    ProcessedNewsItem,
    RawNewsItem,
    SourceResult,
    SourceType,
)
from deepradar.report.generator import generate_report


MINIMAL_CONFIG = {
    "settings": {
        "report": {
            "max_github_repos": 10,
            "max_news_items": 15,
            "max_papers": 10,
            "max_social_items": 10,
        }
    }
}

HEADLINE = {
    "headline_en": "Test Headline",
    "headline_zh": "测试标题",
    "summary_en": "Test summary.",
    "summary_zh": "测试摘要。",
}


def _make_processed(source: SourceType, title: str, score: float = 5.0) -> ProcessedNewsItem:
    return ProcessedNewsItem(
        raw=RawNewsItem(
            source=source,
            source_name=source.value,
            title=title,
            url="https://example.com",
        ),
        summary_en="English summary",
        summary_zh="中文摘要",
        importance_score=score,
        category="LLM",
    )


def test_report_contains_header():
    md = generate_report([], "2026-04-18", HEADLINE, {}, MINIMAL_CONFIG)
    assert "DeepRadar AI Daily" in md
    assert "Test Headline" in md


def test_report_contains_github_section():
    items = [_make_processed(SourceType.GITHUB, "cool/repo")]
    items[0].raw.metadata = {"stars_today": 50, "total_stars": 1000, "language": "Python"}
    md = generate_report(items, "2026-04-18", HEADLINE, {}, MINIMAL_CONFIG)
    assert "Hot GitHub Repos" in md
    assert "cool/repo" in md


def test_report_footer_shows_source_status():
    source_results = [
        SourceResult(name="hackernews", item_count=12),
        SourceResult(name="arxiv", item_count=5),
        SourceResult(name="twitter_rss", item_count=0, error="Connection timeout"),
    ]
    stats = {
        "total_collected": 17,
        "sources_active": 2,
        "sources_total": 3,
        "items_filtered": 10,
        "tokens_used": 500,
        "source_results": source_results,
    }
    md = generate_report([], "2026-04-18", HEADLINE, stats, MINIMAL_CONFIG)
    assert "hackernews: 12 items" in md
    assert "twitter_rss: ERROR" in md


def test_report_respects_max_items():
    items = [_make_processed(SourceType.HACKERNEWS, f"Item {i}") for i in range(20)]
    config = {
        "settings": {
            "report": {
                "max_github_repos": 10,
                "max_news_items": 5,
                "max_papers": 10,
                "max_social_items": 10,
            }
        }
    }
    md = generate_report(items, "2026-04-18", HEADLINE, {}, config)
    assert md.count("###") <= 6  # header + up to 5 items
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/report/test_generator.py -v`
Expected: `test_report_footer_shows_source_status` FAILS (source status not rendered yet)

- [ ] **Step 3: Add source status template**

In `deepradar/report/templates.py`, replace `REPORT_FOOTER`:

```python
SOURCE_STATUS_ITEM = "- {name}: {status}\n"

REPORT_FOOTER = """
---

## 📊 Statistics / 统计

- Total items collected: {total_collected}
- Sources active: {sources_active}/{sources_total}
- Items after dedup & filter: {items_filtered}
- Items in report: {items_in_report}
- LLM tokens used: {tokens_used}

### Source Status / 数据源状态
{source_status}
- Report generated at: {timestamp} UTC

---

*Generated by [DeepRadar](https://github.com/wuqisen/DeepRadar) — AI News Sniffer*
*Powered by Claude API*
"""
```

- [ ] **Step 4: Update `generator.py` to render source status**

In `deepradar/report/generator.py`, add `SOURCE_STATUS_ITEM` to imports:
```python
from deepradar.report.templates import (
    # ... existing imports ...
    SOURCE_STATUS_ITEM,
)
```

Also add `SourceResult` to model imports:
```python
from deepradar.processing.models import ProcessedNewsItem, SourceResult, SourceType
```

Replace the footer rendering block at the end of `generate_report`:
```python
    # Footer
    source_results: list[SourceResult] = stats.get("source_results", [])
    source_status = ""
    for sr in source_results:
        if sr.error:
            source_status += SOURCE_STATUS_ITEM.format(name=sr.name, status=f"ERROR — {sr.error}")
        else:
            source_status += SOURCE_STATUS_ITEM.format(name=sr.name, status=f"{sr.item_count} items")

    md += REPORT_FOOTER.format(
        total_collected=stats.get("total_collected", 0),
        sources_active=stats.get("sources_active", 0),
        sources_total=stats.get("sources_total", 7),
        items_filtered=stats.get("items_filtered", 0),
        items_in_report=len(items),
        tokens_used=stats.get("tokens_used", 0),
        source_status=source_status or "- No source data available\n",
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
    )
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/report/test_generator.py -v`
Expected: All 4 tests PASS

- [ ] **Step 6: Commit**

```bash
git add deepradar/report/templates.py deepradar/report/generator.py tests/report/__init__.py tests/report/test_generator.py
git commit -m "feat: add per-source status to report footer"
```

---

### Task 10: Create `notify.py` webhook module

**Files:**
- Create: `deepradar/notify.py`
- Create: `tests/test_notify.py`
- Modify: `config/settings.yaml`

- [ ] **Step 1: Write the test**

```python
# tests/test_notify.py
import json
from unittest.mock import AsyncMock, patch

import pytest

from deepradar.notify import send_notification


@pytest.mark.asyncio
async def test_send_notification_posts_json():
    with patch("deepradar.notify.aiohttp.ClientSession") as MockSession:
        mock_resp = AsyncMock()
        mock_resp.status = 200
        mock_session = AsyncMock()
        mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_session.post.return_value.__aexit__ = AsyncMock(return_value=False)
        MockSession.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        MockSession.return_value.__aexit__ = AsyncMock(return_value=False)

        payload = {"date": "2026-04-18", "total_items": 42}
        result = await send_notification("https://hooks.example.com/test", payload)
        assert result is True
        mock_session.post.assert_called_once()


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_notify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'deepradar.notify'`

- [ ] **Step 3: Implement `notify.py`**

```python
# deepradar/notify.py
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
```

- [ ] **Step 4: Add notifications section to `config/settings.yaml`**

Append to `config/settings.yaml`:
```yaml

notifications:
  webhook_url: ""  # Override via DEEPRADAR_WEBHOOK_URL env var
  on_success: true
  on_failure: true
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_notify.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add deepradar/notify.py tests/test_notify.py config/settings.yaml
git commit -m "feat: add webhook notification module"
```

---

### Task 11: Wire notification in `config.py` and `main.py`

**Files:**
- Modify: `deepradar/config.py`
- Modify: `deepradar/main.py`

- [ ] **Step 1: Add webhook URL env var to `config.py`**

In `deepradar/config.py`, after the `reports_repo_token` line (line 42), add:
```python
    cfg["settings"]["webhook_url"] = os.environ.get(
        "DEEPRADAR_WEBHOOK_URL",
        cfg["settings"].get("notifications", {}).get("webhook_url", ""),
    )
```

- [ ] **Step 2: Add notification call to `main.py`**

In `deepradar/main.py`, add import:
```python
from deepradar.notify import send_notification
```

At the end of `run()`, after `publish_report(...)` and before `logger.info("=== Done ===")`, add:
```python
    # Step 6: Notify
    webhook_url = config.get("settings", {}).get("webhook_url", "")
    if webhook_url:
        notif_cfg = config.get("settings", {}).get("notifications", {})
        is_success = True  # If we reached here, the run succeeded
        should_notify = (is_success and notif_cfg.get("on_success", True)) or (
            not is_success and notif_cfg.get("on_failure", True)
        )
        if should_notify:
            await send_notification(webhook_url, {
                "date": today,
                "status": "success",
                "total_collected": total_collected,
                "items_in_report": len(processed),
                "sources": [r.model_dump() for r in source_results],
            })
```

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add deepradar/config.py deepradar/main.py
git commit -m "feat: wire webhook notification into config and main pipeline"
```

---

### Task 12: Add CLI arguments

**Files:**
- Modify: `deepradar/main.py`

- [ ] **Step 1: Add argparse to `main.py`**

Add `import argparse` to imports.

Replace the `main()` function and add a `_parse_args` function:

```python
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="deepradar",
        description="DeepRadar — AI News Sniffer. Generate daily AI news reports.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Save report locally only, don't publish")
    parser.add_argument("--sources", type=str, default="", help="Comma-separated source names to enable (e.g. hackernews,arxiv)")
    parser.add_argument("--date", type=str, default="", help="Override report date (YYYY-MM-DD)")
    parser.add_argument("--output-dir", type=str, default="", help="Override output directory")
    parser.add_argument("--config-dir", type=str, default="", help="Override config directory")
    parser.add_argument("--verbose", action="store_true", help="Set log level to DEBUG")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM enrichment")
    return parser.parse_args()


def _apply_cli_overrides(config: dict[str, Any], args: argparse.Namespace) -> None:
    """Apply CLI argument overrides to the loaded config."""
    if args.dry_run:
        config["settings"]["reports_repo"] = ""

    if args.sources:
        enabled_names = {s.strip() for s in args.sources.split(",")}
        for src_name, src_cfg in config.get("sources", {}).items():
            if isinstance(src_cfg, dict):
                src_cfg["enabled"] = src_name in enabled_names

    if args.verbose:
        config.setdefault("settings", {}).setdefault("general", {})["log_level"] = "DEBUG"

    if args.no_llm:
        config["settings"]["anthropic_api_key"] = ""

    if args.output_dir:
        config["settings"]["output_dir"] = args.output_dir


def main() -> None:
    args = _parse_args()
    asyncio.run(run(args))
```

- [ ] **Step 2: Update `run()` signature to accept args**

Change `run()` to accept args:
```python
async def run(args: argparse.Namespace | None = None) -> None:
    if args and args.config_dir:
        from pathlib import Path
        from deepradar.config import reset_config
        reset_config()
        config = load_config(Path(args.config_dir))
    else:
        config = load_config()

    if args:
        _apply_cli_overrides(config, args)

    _setup_logging(config)

    today = args.date if (args and args.date) else date.today().isoformat()
```

The rest of `run()` stays the same.

- [ ] **Step 3: Update publish call to respect `output_dir`**

In `deepradar/main.py`, before the publish call, add:
```python
    if config.get("settings", {}).get("output_dir"):
        config["settings"]["_output_dir_override"] = config["settings"]["output_dir"]
```

In `deepradar/publish/github_publisher.py`, update the local fallback paths to check for override:
```python
        output_dir = Path(config.get("settings", {}).get("output_dir", "output"))
```
(Apply this change in both the "no reports_repo" block and the exception fallback block.)

- [ ] **Step 4: Test the CLI manually**

Run: `python -m deepradar.main --help`
Expected: Help message with all options shown

Run: `python -m deepradar.main --dry-run --no-llm --date 2026-04-18 --verbose`
Expected: Runs without error, saves report to `output/2026-04-18.md`, DEBUG-level logs visible

- [ ] **Step 5: Commit**

```bash
git add deepradar/main.py deepradar/publish/github_publisher.py
git commit -m "feat: add CLI arguments (--dry-run, --sources, --date, --no-llm, --verbose)"
```

---

### Task 13: Tests for dedup module

**Files:**
- Create: `tests/processing/test_dedup.py`

- [ ] **Step 1: Write tests**

```python
# tests/processing/test_dedup.py
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
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/processing/test_dedup.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/processing/test_dedup.py
git commit -m "test: add dedup module tests"
```

---

### Task 14: Tests for config module

**Files:**
- Create: `tests/test_config.py`

- [ ] **Step 1: Write tests**

```python
# tests/test_config.py
import os
import tempfile
from pathlib import Path

import yaml

from deepradar.config import load_config, reset_config


def _write_yaml(dir_path: Path, name: str, data: dict) -> None:
    with open(dir_path / f"{name}.yaml", "w") as f:
        yaml.dump(data, f)


def test_load_config_reads_yaml_files():
    reset_config()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_yaml(tmp_path, "settings", {"llm": {"model": "test-model"}})
        _write_yaml(tmp_path, "sources", {"hackernews": {"enabled": True}})
        _write_yaml(tmp_path, "categories", {"ai_relevance_keywords": {"high": ["ai"]}})

        cfg = load_config(tmp_path)
        assert cfg["settings"]["llm"]["model"] == "test-model"
        assert cfg["sources"]["hackernews"]["enabled"] is True
        assert "ai" in cfg["categories"]["ai_relevance_keywords"]["high"]
    reset_config()


def test_env_var_overrides(monkeypatch):
    reset_config()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key-123")
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_yaml(tmp_path, "settings", {})
        _write_yaml(tmp_path, "sources", {})
        _write_yaml(tmp_path, "categories", {})

        cfg = load_config(tmp_path)
        assert cfg["settings"]["anthropic_api_key"] == "test-key-123"
    reset_config()


def test_missing_yaml_files_handled():
    reset_config()
    with tempfile.TemporaryDirectory() as tmp:
        cfg = load_config(Path(tmp))
        assert "settings" in cfg
    reset_config()


def test_reset_config():
    reset_config()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_yaml(tmp_path, "settings", {"key": "value1"})
        _write_yaml(tmp_path, "sources", {})
        _write_yaml(tmp_path, "categories", {})
        cfg1 = load_config(tmp_path)

    reset_config()
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _write_yaml(tmp_path, "settings", {"key": "value2"})
        _write_yaml(tmp_path, "sources", {})
        _write_yaml(tmp_path, "categories", {})
        cfg2 = load_config(tmp_path)

    assert cfg1["settings"]["key"] == "value1"
    assert cfg2["settings"]["key"] == "value2"
    reset_config()
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/test_config.py -v`
Expected: All 4 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_config.py
git commit -m "test: add config loading tests"
```

---

### Task 15: Create shared test fixtures in `conftest.py`

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write conftest with shared fixtures**

```python
# tests/conftest.py
import pytest

from deepradar.processing.models import (
    ProcessedNewsItem,
    RawNewsItem,
    SourceResult,
    SourceType,
)


@pytest.fixture
def sample_config():
    return {
        "settings": {
            "llm": {
                "model": "claude-sonnet-4-20250514",
                "max_tokens_per_request": 4096,
                "batch_size": 12,
                "max_concurrent_batches": 3,
                "temperature": 0.3,
            },
            "report": {
                "max_github_repos": 10,
                "max_news_items": 15,
                "max_papers": 10,
                "max_social_items": 10,
                "min_importance_score": 3.0,
            },
            "anthropic_api_key": "",
            "reports_repo": "",
        },
        "sources": {
            "hackernews": {"enabled": True},
            "arxiv": {"enabled": True},
            "github_trending": {"enabled": True},
        },
        "categories": {
            "ai_relevance_keywords": {
                "high": ["ai", "artificial intelligence", "machine learning", "llm"],
                "medium": ["model", "transformer", "embedding"],
                "low": ["automation"],
            },
            "categories": [
                {"name": "LLM", "keywords": ["gpt", "claude", "llama"], "weight": 1.2},
                {"name": "CV", "keywords": ["computer vision", "diffusion"], "weight": 1.0},
            ],
        },
    }


@pytest.fixture
def sample_raw_item():
    return RawNewsItem(
        source=SourceType.HACKERNEWS,
        source_name="Hacker News",
        title="New AI Model Breaks Records",
        url="https://example.com/ai-model",
        content="A new AI model has achieved SOTA results.",
        metadata={"score": 150, "comment_count": 45},
    )


@pytest.fixture
def sample_processed_item(sample_raw_item):
    return ProcessedNewsItem(
        raw=sample_raw_item,
        summary_en="A new AI model achieved state-of-the-art results.",
        summary_zh="一个新的 AI 模型达到了最先进的结果。",
        category="LLM / Foundation Models",
        importance_score=8.5,
        tags=["ai", "benchmark", "llm"],
        why_it_matters="Sets new performance records on key benchmarks.",
        why_it_matters_zh="在关键基准测试上创造了新的性能记录。",
    )


@pytest.fixture
def sample_source_results():
    return [
        SourceResult(name="hackernews", item_count=12),
        SourceResult(name="arxiv", item_count=25),
        SourceResult(name="github_trending", item_count=8),
        SourceResult(name="twitter_rss", item_count=0, error="All Nitter instances failed"),
    ]
```

- [ ] **Step 2: Verify conftest loads correctly**

Run: `pytest tests/ -v --collect-only`
Expected: All tests discovered, no import errors

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add shared test fixtures"
```

---

### Task 16: Final integration — run full test suite and dry-run

**Files:** None new (verification only)

- [ ] **Step 1: Run complete test suite**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run dry-run smoke test**

Run: `python -m deepradar.main --dry-run --no-llm --verbose`
Expected: Report saved to `output/` directory, DEBUG-level logs, no errors

- [ ] **Step 3: Verify report output is valid**

Run: `cat output/$(date +%Y-%m-%d).md | head -30`
Expected: Markdown with header, sections, footer with "Source Status" section

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and integration verification"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Fix `min_importance_score` wiring → Task 6
- [x] Fix `max_concurrent_batches` wiring → Task 7
- [x] Shared `strip_html` → Task 1, Task 4
- [x] Shared `is_ai_related` from config → Task 2, Task 5
- [x] Fix inline imports → Task 4
- [x] `SourceResult` model → Task 3
- [x] Per-source status in report → Task 8, Task 9
- [x] Notification webhook → Task 10, Task 11
- [x] CLI arguments → Task 12
- [x] Tests for processing → Task 6, Task 13
- [x] Tests for LLM tasks → Task 7
- [x] Tests for report → Task 9
- [x] Tests for config → Task 14

**Placeholder scan:** No TBD/TODO items. All steps have code.

**Type consistency:** `SourceResult` used consistently in models.py, main.py, generator.py, and conftest.py. `is_ai_related` signature matches across keywords.py, hackernews.py, and github_trending.py. `batch_summarize` is async in tasks.py and awaited in main.py.
