# Source Reliability Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix three recurring failures — Twitter/Nitter unreliable, YouTube RSS blocked, LLM returning malformed JSON.

**Architecture:** Replace TwitterRssSource with a new BlueskySource using the public Bluesky API; add Invidious fallback to YouTubeRssSource; enhance `_parse_json` with `json-repair` auto-fix and LLM retry.

**Tech Stack:** Python 3.11+, aiohttp, json-repair>=0.30.0, Bluesky public API (no auth), Invidious RSS

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `deepradar/sources/bluesky.py` | New BlueskySource replacing TwitterRssSource |
| Modify | `deepradar/processing/models.py` | Add `BLUESKY` to SourceType enum |
| Modify | `deepradar/main.py` | Swap TwitterRssSource → BlueskySource |
| Modify | `deepradar/sources/youtube_rss.py` | Add Invidious fallback, remove @retry |
| Modify | `deepradar/llm/tasks.py` | Enhance `_parse_json` + LLM retry |
| Modify | `config/sources.yaml` | Replace twitter_rss block, add bluesky + invidious_instances |
| Modify | `requirements.txt` | Add json-repair>=0.30.0 |
| Create | `tests/sources/__init__.py` | Test package init |
| Create | `tests/sources/test_bluesky.py` | Tests for BlueskySource |
| Create | `tests/sources/test_youtube_rss.py` | Tests for YouTube Invidious fallback |
| Modify | `tests/llm/test_tasks.py` | Add tests for repaired/retried JSON parsing |

---

## Task 1: Add BLUESKY to SourceType

**Files:**
- Modify: `deepradar/processing/models.py:10-17`

- [ ] **Step 1: Add enum value**

In `deepradar/processing/models.py`, change the `SourceType` class to:

```python
class SourceType(str, Enum):
    GITHUB = "github"
    HACKERNEWS = "hackernews"
    ARXIV = "arxiv"
    RSS_BLOG = "rss_blog"
    TWITTER = "twitter"
    BLUESKY = "bluesky"
    REDDIT = "reddit"
    YOUTUBE = "youtube"
```

- [ ] **Step 2: Verify no tests break**

```bash
cd /Users/wuqisen/dev/DeepRadar
python -m pytest tests/processing/test_models.py -v
```

Expected: all PASS (existing tests don't reference TWITTER/BLUESKY directly)

- [ ] **Step 3: Commit**

```bash
git add deepradar/processing/models.py
git commit -m "feat: add BLUESKY to SourceType enum"
```

---

## Task 2: Add json-repair dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add dependency**

In `requirements.txt`, append:

```
json-repair>=0.30.0
```

- [ ] **Step 2: Install**

```bash
pip install json-repair>=0.30.0
```

Expected: `Successfully installed json-repair-...`

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add json-repair dependency"
```

---

## Task 3: Enhance _parse_json with repair + LLM retry

**Files:**
- Modify: `deepradar/llm/tasks.py`
- Modify: `tests/llm/test_tasks.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/llm/test_tasks.py`:

```python
def test_parse_json_truncated_repaired():
    # Missing closing bracket — json-repair should fix it
    text = '[{"index": 0, "summary_en": "Hello"'
    result = _parse_json(text)
    assert isinstance(result, list)
    assert result[0]["summary_en"] == "Hello"


def test_parse_json_trailing_comma_repaired():
    text = '[{"index": 0, "summary_en": "Hello",}]'
    result = _parse_json(text)
    assert result[0]["summary_en"] == "Hello"


def test_parse_json_completely_invalid_raises():
    with pytest.raises(Exception):
        _parse_json("this is not json at all !@#$")


@pytest.mark.asyncio
async def test_batch_summarize_retries_on_bad_json():
    items = [_make_raw_item("Item 1")]
    client = MagicMock()
    good_response = json.dumps([{
        "index": 0,
        "summary_en": "Retry worked",
        "summary_zh": "重试成功",
        "category": "Other",
        "importance_score": 5.0,
        "tags": [],
        "why_it_matters": "ok",
        "why_it_matters_zh": "好",
    }])
    # First call returns invalid JSON, second call returns valid JSON
    client.complete.side_effect = ["not valid json !@#$", good_response]
    result = await batch_summarize(client, items, batch_size=12)
    assert len(result) == 1
    assert result[0].summary_en == "Retry worked"
    assert client.complete.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/llm/test_tasks.py::test_parse_json_truncated_repaired tests/llm/test_tasks.py::test_batch_summarize_retries_on_bad_json -v
```

Expected: FAIL — `json.loads` raises on truncated JSON, no retry logic exists

- [ ] **Step 3: Implement enhanced _parse_json and retry in _process_batch**

Replace the contents of `deepradar/llm/tasks.py` with:

```python
from __future__ import annotations

import json
import logging
from typing import Any

from json_repair import repair_json

from deepradar.llm.client import LLMClient
from deepradar.llm.prompts import (
    BATCH_SUMMARIZE_PROMPT,
    DAILY_HEADLINE_PROMPT,
    GITHUB_REPO_PROMPT,
    SYSTEM_PROMPT,
)
from deepradar.processing.models import ProcessedNewsItem, RawNewsItem, SourceType

logger = logging.getLogger(__name__)

_RETRY_SUFFIX = "\n\nIMPORTANT: Respond ONLY with a valid JSON array. No explanation, no markdown, no extra text."


def _parse_json(text: str) -> Any:
    """Try to parse JSON, stripping markdown fences. Falls back to json-repair."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    repaired = repair_json(text, return_objects=True)
    if repaired is not None and repaired != "" and repaired != [] and repaired != {}:
        return repaired

    raise ValueError(f"Could not parse JSON even after repair: {text[:200]!r}")


def _items_to_json(items: list[RawNewsItem]) -> str:
    entries = []
    for i, item in enumerate(items):
        entries.append({
            "index": i,
            "title": item.title,
            "source": item.source_name,
            "url": item.url,
            "content": item.content[:500],
        })
    return json.dumps(entries, ensure_ascii=False, indent=2)


async def batch_summarize(
    client: LLMClient,
    items: list[RawNewsItem],
    batch_size: int = 12,
    max_concurrent: int = 3,
) -> list[ProcessedNewsItem]:
    """Process items through LLM API in concurrent batches."""
    import asyncio

    sem = asyncio.Semaphore(max_concurrent)
    results: list[ProcessedNewsItem] = []
    lock = asyncio.Lock()

    async def _process_batch(batch: list[RawNewsItem], batch_num: int) -> None:
        async with sem:
            items_json = _items_to_json(batch)
            base_prompt = BATCH_SUMMARIZE_PROMPT.format(items_json=items_json)

            parsed = None
            last_exc: Exception | None = None

            for attempt in range(3):  # 1 initial + 2 retries
                prompt = base_prompt if attempt == 0 else base_prompt + _RETRY_SUFFIX
                try:
                    response = await asyncio.to_thread(client.complete, SYSTEM_PROMPT, prompt)
                    parsed = _parse_json(response)
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < 2:
                        logger.warning(f"Batch {batch_num} attempt {attempt + 1} failed: {exc}. Retrying...")

            if parsed is None:
                logger.error(f"LLM batch processing failed after 3 attempts: {last_exc}")
                async with lock:
                    for raw in batch:
                        results.append(ProcessedNewsItem(raw=raw))
                return

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

    tasks = []
    for i, batch_start in enumerate(range(0, len(items), batch_size)):
        batch = items[batch_start : batch_start + batch_size]
        tasks.append(_process_batch(batch, i + 1))

    await asyncio.gather(*tasks)
    return results


def generate_headline(client: LLMClient, top_items: list[ProcessedNewsItem]) -> dict[str, str]:
    """Generate daily headline and executive summary."""
    entries = []
    for item in top_items[:10]:
        entries.append({
            "title": item.raw.title,
            "summary": item.summary_en,
            "score": item.importance_score,
            "category": item.category,
        })
    top_json = json.dumps(entries, ensure_ascii=False, indent=2)
    prompt = DAILY_HEADLINE_PROMPT.format(top_items_json=top_json)

    try:
        response = client.complete(SYSTEM_PROMPT, prompt)
        return _parse_json(response)
    except Exception as e:
        logger.error(f"Failed to generate headline: {e}")
        return {
            "headline_en": "AI Daily Report",
            "headline_zh": "AI 每日报告",
            "summary_en": "Today's AI news digest.",
            "summary_zh": "今日 AI 新闻摘要。",
        }


def enrich_github_repos(client: LLMClient, items: list[ProcessedNewsItem]) -> None:
    """Add GitHub-specific 'why it matters' explanations in-place."""
    github_items = [it for it in items if it.raw.source == SourceType.GITHUB]
    if not github_items:
        return

    repos = []
    for i, it in enumerate(github_items):
        repos.append({
            "index": i,
            "name": it.raw.title,
            "description": it.raw.content,
            "stars_today": it.raw.metadata.get("stars_today", 0),
            "language": it.raw.metadata.get("language", ""),
        })
    repos_json = json.dumps(repos, ensure_ascii=False, indent=2)
    prompt = GITHUB_REPO_PROMPT.format(repos_json=repos_json)

    try:
        response = client.complete(SYSTEM_PROMPT, prompt)
        parsed = _parse_json(response)
        for entry in parsed:
            idx = entry.get("index", 0)
            if idx < len(github_items):
                github_items[idx].why_it_matters = entry.get("why_en", github_items[idx].why_it_matters)
                github_items[idx].why_it_matters_zh = entry.get("why_zh", github_items[idx].why_it_matters_zh)
    except Exception as e:
        logger.error(f"Failed to enrich GitHub repos: {e}")
```

- [ ] **Step 4: Run all LLM tests**

```bash
python -m pytest tests/llm/ -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add deepradar/llm/tasks.py tests/llm/test_tasks.py
git commit -m "feat: enhance JSON parsing with json-repair and LLM retry"
```

---

## Task 4: Replace TwitterRssSource with BlueskySource

**Files:**
- Create: `deepradar/sources/bluesky.py`
- Create: `tests/sources/__init__.py`
- Create: `tests/sources/test_bluesky.py`

- [ ] **Step 1: Write failing tests**

Create `tests/sources/__init__.py` (empty file).

Create `tests/sources/test_bluesky.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

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

    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/sources/test_bluesky.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'deepradar.sources.bluesky'`

- [ ] **Step 3: Implement BlueskySource**

Create `deepradar/sources/bluesky.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiohttp

from deepradar.processing.models import RawNewsItem, SourceType
from deepradar.sources.base import BaseSource

_API_BASE = "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"


class BlueskySource(BaseSource):
    name = "bluesky"

    async def fetch(self) -> list[RawNewsItem]:
        cfg = self.config.get("sources", {}).get("bluesky", {})
        if not cfg.get("enabled", True):
            return []

        accounts = cfg.get("accounts", [])
        lookback_hours = cfg.get("lookback_hours", 48)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for handle in accounts:
                try:
                    url = f"{_API_BASE}?actor={handle}&limit=20"
                    async with session.get(url) as resp:
                        if resp.status != 200:
                            self.logger.warning(f"Bluesky API returned {resp.status} for @{handle}")
                            continue
                        data = await resp.json()

                    for feed_item in data.get("feed", []):
                        post = feed_item.get("post", {})
                        record = post.get("record", {})
                        text = record.get("text", "").strip()
                        if not text:
                            continue

                        created_at_str = record.get("createdAt") or post.get("indexedAt", "")
                        published = None
                        if created_at_str:
                            try:
                                published = datetime.fromisoformat(
                                    created_at_str.replace("Z", "+00:00")
                                )
                            except ValueError:
                                pass

                        if published and published < cutoff:
                            continue

                        post_uri = post.get("uri", "")
                        rkey = post_uri.split("/")[-1] if "/" in post_uri else ""
                        url_link = (
                            f"https://bsky.app/profile/{handle}/post/{rkey}" if rkey else ""
                        )

                        items.append(
                            RawNewsItem(
                                source=SourceType.BLUESKY,
                                source_name=f"@{handle}",
                                title=text[:120],
                                url=url_link,
                                content=text,
                                published_at=published,
                                metadata={"handle": handle, "cid": post.get("cid", "")},
                            )
                        )

                except Exception as exc:
                    self.logger.warning(f"Failed to fetch Bluesky posts for @{handle}: {exc}")

        self.logger.info(f"Total Bluesky items: {len(items)}")
        return items
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/sources/test_bluesky.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add deepradar/sources/bluesky.py tests/sources/__init__.py tests/sources/test_bluesky.py
git commit -m "feat: add BlueskySource replacing TwitterRssSource"
```

---

## Task 5: Wire BlueskySource into main.py + update config

**Files:**
- Modify: `deepradar/main.py:24,49`
- Modify: `config/sources.yaml`

- [ ] **Step 1: Update main.py**

In `deepradar/main.py`, replace:

```python
from deepradar.sources.twitter_rss import TwitterRssSource
```

with:

```python
from deepradar.sources.bluesky import BlueskySource
```

And in `_init_sources`, replace `TwitterRssSource` with `BlueskySource`:

```python
def _init_sources(config: dict[str, Any]) -> list:
    """Initialize all enabled source instances."""
    source_classes = [
        HackerNewsSource,
        ArxivSource,
        RssBlogsSource,
        GitHubTrendingSource,
        RedditRssSource,
        YouTubeRssSource,
        BlueskySource,
    ]
    sources = []
    for cls in source_classes:
        src = cls(config)
        src_cfg = config.get("sources", {}).get(src.name, {})
        if src_cfg.get("enabled", True):
            sources.append(src)
        else:
            logger.info(f"Source {src.name} is disabled, skipping")
    return sources
```

- [ ] **Step 2: Update config/sources.yaml**

Remove the `twitter_rss` block entirely and add `bluesky` block in its place:

```yaml
bluesky:
  enabled: true
  accounts:
    - "openai.com"
    - "anthropic.com"
    - "ylecun.bsky.social"
    - "karpathy.bsky.social"
    - "goodside.bsky.social"
  lookback_hours: 48
```

- [ ] **Step 3: Verify import works**

```bash
python -c "from deepradar.main import _init_sources; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add deepradar/main.py config/sources.yaml
git commit -m "feat: wire BlueskySource into main pipeline, replace twitter_rss config"
```

---

## Task 6: Add Invidious fallback to YouTubeRssSource

**Files:**
- Modify: `deepradar/sources/youtube_rss.py`
- Modify: `config/sources.yaml`
- Create: `tests/sources/test_youtube_rss.py`

- [ ] **Step 1: Write failing tests**

Create `tests/sources/test_youtube_rss.py`:

```python
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
    resp.raise_for_status = AsyncMock(
        side_effect=None if status == 200 else Exception(f"HTTP {status}")
    )
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
    # Should only call YouTube, not Invidious
    call_urls = [str(c.args[0]) for c in mock_session.get.call_args_list]
    assert any("youtube.com" in u for u in call_urls)
    assert not any("inv.nadeko.net" in u for u in call_urls)


@pytest.mark.asyncio
async def test_fetch_falls_back_to_invidious():
    config = _make_config(invidious_instances=["https://inv.nadeko.net"])
    source = YouTubeRssSource(config)

    call_count = 0

    async def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/sources/test_youtube_rss.py -v
```

Expected: FAIL — current code has no Invidious fallback

- [ ] **Step 3: Rewrite YouTubeRssSource with fallback**

Replace `deepradar/sources/youtube_rss.py` entirely:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import aiohttp
import feedparser

from deepradar.processing.models import RawNewsItem, SourceType
from deepradar.sources.base import BaseSource


class YouTubeRssSource(BaseSource):
    name = "youtube_rss"

    async def _fetch_channel_feed(
        self,
        session: aiohttp.ClientSession,
        channel_id: str,
        invidious_instances: list[str],
    ) -> str | None:
        """Try YouTube primary, then each Invidious instance. Returns feed text or None."""
        primary_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
        try:
            async with session.get(primary_url) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception:
            pass

        for instance in invidious_instances:
            url = f"{instance.rstrip('/')}/feed/channel/{channel_id}"
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        return await resp.text()
            except Exception:
                pass

        return None

    async def fetch(self) -> list[RawNewsItem]:
        cfg = self.config.get("sources", {}).get("youtube_rss", {})
        if not cfg.get("enabled", True):
            return []

        channels = cfg.get("channels", [])
        lookback_hours = cfg.get("lookback_hours", 48)
        invidious_instances = cfg.get("invidious_instances", [])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)

        items: list[RawNewsItem] = []
        timeout = aiohttp.ClientTimeout(total=30)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            for ch in channels:
                ch_name = ch.get("name", "Unknown")
                ch_id = ch.get("channel_id", "")
                if not ch_id:
                    continue

                text = await self._fetch_channel_feed(session, ch_id, invidious_instances)
                if text is None:
                    self.logger.warning(f"All sources failed for YouTube channel {ch_name}")
                    continue

                feed = feedparser.parse(text)
                for entry in feed.entries:
                    published = None
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        published = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        if published < cutoff:
                            continue

                    video_id = entry.get("yt_videoid", "")
                    thumbnail = (
                        f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg"
                        if video_id
                        else ""
                    )

                    items.append(
                        RawNewsItem(
                            source=SourceType.YOUTUBE,
                            source_name=ch_name,
                            title=entry.get("title", "").strip(),
                            url=entry.get("link", ""),
                            content=entry.get("summary", "").strip()[:500],
                            published_at=published,
                            metadata={
                                "channel_name": ch_name,
                                "channel_id": ch_id,
                                "video_id": video_id,
                                "thumbnail": thumbnail,
                            },
                        )
                    )

                self.logger.info(f"Fetched {len(feed.entries)} videos from {ch_name}")

        self.logger.info(f"Total YouTube items: {len(items)}")
        return items
```

- [ ] **Step 4: Update config/sources.yaml — add invidious_instances**

In `config/sources.yaml`, update the `youtube_rss` block to add `invidious_instances`:

```yaml
youtube_rss:
  enabled: true
  invidious_instances:
    - "https://inv.nadeko.net"
    - "https://invidious.io.lol"
    - "https://yt.cdaut.de"
  channels:
    - name: "Two Minute Papers"
      channel_id: "UCbfYPyITQ-7l4upoX8nvctg"
    - name: "Yannic Kilcher"
      channel_id: "UCZHmQk67mSJgfCCTn7xBfew"
    - name: "AI Explained"
      channel_id: "UCNJ1Ymd5yFuUPtn21xtRbbw"
    - name: "Matt Wolfe"
      channel_id: "UCJMuGG_MrFz2IG9lQG5y7WQ"
  lookback_hours: 48
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/sources/test_youtube_rss.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add deepradar/sources/youtube_rss.py config/sources.yaml tests/sources/test_youtube_rss.py
git commit -m "feat: add Invidious fallback to YouTubeRssSource, remove @retry"
```

---

## Task 7: Full test suite verification

- [ ] **Step 1: Run full test suite**

```bash
python -m pytest tests/ -v
```

Expected: all PASS

- [ ] **Step 2: Smoke test import chain**

```bash
python -c "
from deepradar.sources.bluesky import BlueskySource
from deepradar.sources.youtube_rss import YouTubeRssSource
from deepradar.llm.tasks import _parse_json, batch_summarize
from deepradar.processing.models import SourceType
assert SourceType.BLUESKY == 'bluesky'
print('All imports OK')
"
```

Expected: `All imports OK`

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "chore: verify all source reliability fixes pass full test suite"
```
