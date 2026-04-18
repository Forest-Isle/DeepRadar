# DeepRadar Hardening & Usability — Design Spec

## Goal

Make DeepRadar correct, testable, and usable as a daily tool by fixing config gaps, adding tests, improving robustness, and providing CLI control.

## Scope

This covers a single iteration of improvements. It does **not** add new data sources, change the LLM provider, or add a web UI. Specifically:

1. **Fix config wiring** — unused settings become functional
2. **Code quality** — eliminate duplication, fix inline imports
3. **Robustness** — better error handling, source failure summaries, notification webhook
4. **Tests** — unit tests for processing, mock-based tests for sources and LLM
5. **CLI** — argparse-based command-line interface

---

## 1. Fix Config Wiring

### Problem

Two settings in `config/settings.yaml` are declared but never used:

- `report.min_importance_score: 3.0` — `filter_relevant()` uses a hardcoded default of `2.0`, and `main.py` never passes the config value.
- `llm.max_concurrent_batches: 3` — `batch_summarize()` processes batches sequentially.

### Design

**`min_importance_score`**: In `main.py`, read `config["settings"]["report"]["min_importance_score"]` and pass it to `filter_relevant()` as the `min_score` argument. The function signature already accepts this parameter — it just needs to receive the configured value.

**`max_concurrent_batches`**: In `tasks.py`, make `batch_summarize` an `async` function. Each batch call runs `client.complete()` (synchronous Anthropic SDK) inside `asyncio.to_thread()`. An `asyncio.Semaphore(max_concurrent_batches)` gates how many batch calls run concurrently. The call site in `main.py` already uses `await` for the pipeline, so this fits naturally. The `LLMClient` class itself remains synchronous — only the orchestration layer becomes async.

---

## 2. Code Quality — Deduplicate Shared Logic

### Problem

- `AI_KEYWORDS` is hardcoded in `hackernews.py` and imported by `github_trending.py`. This duplicates the keyword list in `categories.yaml`.
- HTML stripping (`re.sub(r"<[^>]+>", "", text)`) is copy-pasted in `reddit_rss.py`, `twitter_rss.py`, and `rss_blogs.py`.
- `import re` appears inside function bodies/loops in three source files.

### Design

**Shared AI keyword matching**: Create `deepradar/processing/keywords.py` with `is_ai_related(title: str, text: str, config: dict) -> bool`. It extracts keywords from `config["categories"]["ai_relevance_keywords"]` and `config["categories"]["categories"][*]["keywords"]`, merging them into a single set for matching. Source modules (`hackernews.py`, `github_trending.py`) call this instead of using the hardcoded `AI_KEYWORDS` set. The `AI_KEYWORDS` constant and `_is_ai_related()` function in `hackernews.py` are removed entirely.

**Shared HTML stripping**: Add `strip_html(text: str) -> str` to `deepradar/processing/utils.py`. All three RSS sources import and call this.

**Inline imports**: Move `import re` to the top of each file.

---

## 3. Robustness — Error Reporting & Source Failure Summary

### Problem

When sources fail, errors are logged but there's no aggregate summary. The user doesn't know which sources succeeded or failed without reading all logs.

### Design

**Source result tracking**: `_collect_all()` in `main.py` already tracks exceptions. Extend it to return a structured result. Add `SourceResult` to `deepradar/processing/models.py`:

```python
class SourceResult(BaseModel):
    name: str
    item_count: int
    error: str | None = None
```

`_collect_all()` returns `tuple[list[RawNewsItem], list[SourceResult]]` instead of `tuple[list[RawNewsItem], int]`. Pass the `SourceResult` list through to `generate_report()` so the footer includes per-source status (e.g., "hackernews: 12 items, github_trending: ERROR — timeout").

**Notification webhook**: Add a new `deepradar/notify.py` module with a single function `send_webhook(url, payload)`. Called at the end of `main.py` with a summary JSON (date, items collected, sources status, report path). Configured via `settings.yaml`:

```yaml
notifications:
  webhook_url: ""  # Set via DEEPRADAR_WEBHOOK_URL env var
  on_success: true
  on_failure: true
```

The webhook sends a POST with JSON body. Compatible with Slack incoming webhooks, Feishu bots, Discord webhooks, or any custom endpoint.

The env var `DEEPRADAR_WEBHOOK_URL` is wired in `config.py` alongside the other env overrides (`ANTHROPIC_API_KEY`, `REPORTS_REPO`, etc.).

---

## 4. Tests

### Problem

No tests exist despite pytest being in dev dependencies.

### Design

**Test structure:**

```
tests/
├── conftest.py              # Shared fixtures (sample config, sample items)
├── processing/
│   ├── test_dedup.py        # URL normalization, title fuzzy matching
│   ├── test_filter.py       # Relevance scoring, min_score filtering
│   ├── test_keywords.py     # AI keyword matching (new module)
│   └── test_utils.py        # HTML stripping (new module)
├── llm/
│   ├── test_tasks.py        # JSON parsing, batch summarize with mocked client
│   └── test_client.py       # Token tracking, retry behavior
├── sources/
│   ├── test_hackernews.py   # Mock HN API responses
│   ├── test_github_trending.py  # Mock HTML pages
│   ├── test_rss_blogs.py    # Mock RSS feeds
│   └── test_reddit_rss.py   # Mock Reddit RSS
├── report/
│   └── test_generator.py    # Report structure, section rendering
├── test_config.py           # Config loading, env overrides
└── test_notify.py           # Webhook sending
```

**Test approach:**
- Processing tests are pure unit tests (no mocking needed)
- Source tests use `aioresponses` to mock HTTP
- LLM tests mock `LLMClient.complete()` to return canned JSON
- Report tests verify Markdown structure with known inputs

**What we test:**
- `dedup.py`: URL normalization edge cases, title fuzzy matching threshold, also_on merging
- `filter.py`: Score computation with various keyword combos, engagement boosts, min_score cutoff
- `tasks.py`: JSON parsing with/without markdown fences, batch fallback on error, headline generation
- `generator.py`: Section rendering with empty/populated data, max item limits
- `config.py`: YAML loading, env var overrides, `reset_config()`

---

## 5. CLI

### Problem

The only way to run is `python -m deepradar.main` with no arguments. No way to do a dry run, select sources, or override the date.

### Design

Add `argparse` to `main.py`:

```
python -m deepradar.main [options]

Options:
  --dry-run           Generate report but don't publish (save to output/ only)
  --sources SRC,...   Comma-separated list of sources to enable (overrides config)
  --date YYYY-MM-DD   Override report date (default: today)
  --output-dir DIR    Override output directory (default: output/)
  --config-dir DIR    Override config directory (default: config/)
  --verbose           Set log level to DEBUG
  --no-llm            Skip LLM enrichment (useful for testing)
```

These are applied as overrides on top of the loaded config. `--dry-run` sets `reports_repo` to empty string, forcing local-only output. `--sources` accepts the source `name` attributes (`hackernews`, `arxiv`, `rss_blogs`, `github_trending`, `reddit_rss`, `youtube_rss`, `twitter_rss`) and disables all sources not in the list. `--no-llm` skips the LLM step entirely (same behavior as missing API key, but intentional).

---

## Out of Scope

- New data sources
- Replacing Nitter with a different Twitter scraping approach
- Web UI or dashboard
- Historical report comparison / trending analysis
- Replacing the Anthropic SDK with a multi-provider LLM layer
- Pydantic Settings refactor (config remains dict-based for now)

---

## Success Criteria

1. `python -m deepradar.main --dry-run --no-llm` runs without errors and produces a valid Markdown file
2. `pytest` passes with >80% coverage on processing, LLM tasks, and report modules
3. `min_importance_score` and `max_concurrent_batches` from config are functional
4. Run summary shows per-source status in report footer
5. Webhook notification fires on run completion (when configured)
