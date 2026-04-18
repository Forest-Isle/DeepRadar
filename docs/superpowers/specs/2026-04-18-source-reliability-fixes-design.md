# DeepRadar Source Reliability Fixes — Design Spec

Date: 2026-04-18

## Problem Summary

Three recurring failures degrade daily report quality:

1. **Twitter/Nitter**: All Nitter instances fail — service is unreliable, returning 0 Twitter items
2. **YouTube RSS**: `youtube.com/feeds/videos.xml` is rate-limited/blocked — RetryError noise in logs, 0 YouTube items
3. **LLM JSON parse errors**: LLM occasionally returns truncated or malformed JSON — entire batch degrades to no-summary items

---

## Fix 1: Twitter → Bluesky

**File**: `deepradar/sources/bluesky.py` (new), `deepradar/sources/__init__.py` (update), `config/sources.yaml` (update)

- Replace `TwitterRssSource` with new `BlueskySource`
- Call Bluesky public API: `https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=<handle>&limit=20`
  - No authentication required
  - Returns structured JSON (no HTML scraping)
- Config key: `bluesky` in `sources.yaml`, with `accounts` list of Bluesky handles (e.g. `ylecun.bsky.social`)
- `SourceType`: add `BLUESKY` enum value in `processing/models.py`
- Error handling: skip failed handles silently, log single warning per handle

**Config change**:
```yaml
bluesky:
  enabled: true
  accounts:
    - "openai.com"
    - "anthropic.com"
    - "ylecun.bsky.social"
    - "karpathy.bsky.social"
  lookback_hours: 48
```

---

## Fix 2: YouTube → Invidious Fallback

**File**: `deepradar/sources/youtube_rss.py` (modify), `config/sources.yaml` (update)

- Primary: `https://www.youtube.com/feeds/videos.xml?channel_id=<id>`
- Fallback: iterate `invidious_instances` list, try `<instance>/feed/channel/<id>` until one succeeds
- Remove `@retry` decorator — replace with manual try/fallback logic inside `_fetch_feed`
- Each channel logs at most one warning if all sources fail
- No RetryError propagated to caller

**Config addition**:
```yaml
youtube_rss:
  invidious_instances:
    - "https://inv.nadeko.net"
    - "https://invidious.io.lol"
    - "https://yt.cdaut.de"
```

---

## Fix 3: LLM JSON Robustness

**File**: `deepradar/llm/tasks.py` (modify), `requirements.txt` (add `json-repair`)

- Enhance `_parse_json`:
  1. Strip markdown fences (existing)
  2. Try `json.loads` — success → return
  3. Try `json_repair.repair_json` — success → return
  4. Raise exception (triggers retry at caller)
- In `_process_batch`, on parse failure: retry LLM call up to 2 times with strengthened prompt suffix
- Retry prompt suffix: `"\n\nIMPORTANT: Respond ONLY with a valid JSON array. No explanation, no markdown, no extra text."`
- Only after all retries fail: log error and degrade to empty ProcessedNewsItems

**Dependency**: `json-repair>=0.30.0`

---

## Testing

- Unit test `_parse_json` with truncated JSON, JSON with illegal chars, JSON in markdown fences
- Unit test `BlueskySource.fetch` with mocked HTTP responses
- Unit test YouTube fallback logic with mocked primary failure + Invidious success

---

## Out of Scope

- Replacing rss_blogs sources that 404 (Anthropic/Meta/Microsoft) — separate issue
- Twitter OAuth integration
