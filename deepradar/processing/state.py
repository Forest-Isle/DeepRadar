from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any

import aiohttp

from deepradar.processing.dedup import _normalize_url
from deepradar.processing.models import ProcessedNewsItem, RawNewsItem

logger = logging.getLogger(__name__)

STATE_PATH = "state/seen.json"
_SCHEMA_VERSION = 1


def fingerprint(raw: RawNewsItem) -> str:
    """Stable cross-day key for an item: its normalized URL."""
    return _normalize_url(raw.url)


def _engagement(raw: RawNewsItem) -> int:
    """Single engagement number used to detect escalation across days."""
    meta = raw.metadata
    for key in ("score", "stars_today", "comment_count"):
        value = meta.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return 0


def _safe_date(value: Any) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return date.min


class SeenStore:
    """Records which items were already reported, so recurring events can be
    demoted instead of re-surfaced at full weight on subsequent days."""

    def __init__(self, entries: dict[str, dict[str, Any]] | None = None) -> None:
        self.entries = entries or {}

    @classmethod
    def from_json(cls, text: str) -> "SeenStore":
        try:
            data = json.loads(text)
            entries = data.get("entries", {})
            if not isinstance(entries, dict):
                raise ValueError("entries is not an object")
            return cls(entries)
        except (json.JSONDecodeError, AttributeError, ValueError) as exc:
            logger.warning(f"Could not parse seen state ({exc}); starting empty")
            return cls({})

    def check(self, raw: RawNewsItem) -> dict[str, Any] | None:
        """Return the prior record for this item, or None if never seen."""
        return self.entries.get(fingerprint(raw))

    def mark(self, items: list[ProcessedNewsItem], today: str) -> None:
        """Record every considered item as seen on `today`."""
        for it in items:
            raw = it.raw
            fp = fingerprint(raw)
            eng = _engagement(raw)
            rec = self.entries.get(fp)
            if rec:
                rec["last_seen"] = today
                rec["times_seen"] = rec.get("times_seen", 1) + 1
                rec["last_engagement"] = max(eng, rec.get("last_engagement", 0))
            else:
                self.entries[fp] = {
                    "first_seen": today,
                    "last_seen": today,
                    "times_seen": 1,
                    "last_engagement": eng,
                    "title": raw.title[:200],
                }

    def prune(self, today: str, ttl_days: int) -> None:
        cutoff = _safe_date(today) - timedelta(days=ttl_days)
        if cutoff == date.min:
            return
        self.entries = {
            fp: rec for fp, rec in self.entries.items()
            if _safe_date(rec.get("last_seen")) >= cutoff
        }

    def dumps(self) -> str:
        return json.dumps(
            {"version": _SCHEMA_VERSION, "entries": self.entries},
            ensure_ascii=False,
            indent=1,
            sort_keys=True,
        )


def apply_recurrence(
    items: list[ProcessedNewsItem],
    store: SeenStore,
    config: dict[str, Any],
    today: str,
) -> None:
    """Tag and demote items already reported on a prior day.

    Escalating stories (engagement jumped) keep full weight and get a hotter
    badge; flat reruns are demoted so fresh items rank above them.
    """
    cfg = config.get("settings", {}).get("dedup_state", {})
    if not cfg.get("enabled", True):
        return
    demote = cfg.get("demote_factor", 0.4)
    esc_factor = cfg.get("escalation_factor", 1.5)
    esc_min_delta = cfg.get("escalation_min_delta", 50)

    for it in items:
        rec = store.check(it.raw)
        if not rec:
            continue
        days = (_safe_date(today) - _safe_date(rec.get("first_seen"))).days
        prev_eng = rec.get("last_engagement", 0)
        cur_eng = _engagement(it.raw)
        escalated = cur_eng >= prev_eng * esc_factor and (cur_eng - prev_eng) >= esc_min_delta
        it.raw.metadata["recurring"] = {"days": max(days, 1), "escalated": escalated}
        if not escalated:
            it.importance_score *= demote


async def load_seen_store(config: dict[str, Any]) -> SeenStore:
    """Load prior seen state from the reports repo via the GitHub contents API.

    Returns an empty store when no repo is configured or the file is absent.
    """
    settings = config.get("settings", {})
    repo = settings.get("reports_repo", "")
    if not repo:
        return SeenStore({})
    token = settings.get("reports_repo_token", "")
    branch = settings.get("publishing", {}).get("branch", "main")
    url = f"https://api.github.com/repos/{repo}/contents/{STATE_PATH}?ref={branch}"
    headers = {"Accept": "application/vnd.github.raw+json"}
    if token:
        headers["Authorization"] = f"token {token}"

    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status == 404:
                    logger.info("No prior seen state (404); starting fresh")
                    return SeenStore({})
                resp.raise_for_status()
                text = await resp.text()
        store = SeenStore.from_json(text)
        logger.info(f"Loaded seen state: {len(store.entries)} entries")
        return store
    except Exception as exc:
        logger.warning(f"Failed to load seen state: {exc}; starting fresh")
        return SeenStore({})
