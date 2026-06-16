from deepradar.processing.models import ProcessedNewsItem, RawNewsItem, SourceType
from deepradar.processing.state import (
    SeenStore,
    apply_recurrence,
    fingerprint,
    load_seen_store,
)

import pytest


def _make(url: str, score: int = 100, importance: float = 8.0, title: str = "Item") -> ProcessedNewsItem:
    return ProcessedNewsItem(
        raw=RawNewsItem(
            source=SourceType.HACKERNEWS,
            source_name="Hacker News",
            title=title,
            url=url,
            metadata={"score": score},
        ),
        importance_score=importance,
    )


_CFG = {"settings": {"dedup_state": {"enabled": True}}}


class TestSeenStore:
    def test_roundtrip_through_json(self):
        store = SeenStore()
        store.mark([_make("https://a.com/1")], "2026-06-16")
        loaded = SeenStore.from_json(store.dumps())
        assert loaded.entries == store.entries

    def test_from_json_garbage_starts_empty(self):
        assert SeenStore.from_json("not json").entries == {}

    def test_check_unseen_returns_none(self):
        assert SeenStore().check(_make("https://a.com/1").raw) is None

    def test_mark_creates_then_increments(self):
        store = SeenStore()
        item = _make("https://a.com/1", score=100)
        store.mark([item], "2026-06-15")
        store.mark([item], "2026-06-16")
        rec = store.check(item.raw)
        assert rec["times_seen"] == 2
        assert rec["first_seen"] == "2026-06-15"
        assert rec["last_seen"] == "2026-06-16"

    def test_mark_keeps_peak_engagement(self):
        store = SeenStore()
        store.mark([_make("https://a.com/1", score=300)], "2026-06-15")
        store.mark([_make("https://a.com/1", score=100)], "2026-06-16")
        assert store.entries[fingerprint(_make("https://a.com/1").raw)]["last_engagement"] == 300

    def test_prune_drops_stale_entries(self):
        store = SeenStore()
        store.mark([_make("https://old.com/1")], "2026-05-01")
        store.mark([_make("https://new.com/1")], "2026-06-15")
        store.prune("2026-06-16", ttl_days=30)
        assert fingerprint(_make("https://new.com/1").raw) in store.entries
        assert fingerprint(_make("https://old.com/1").raw) not in store.entries


class TestApplyRecurrence:
    def test_unseen_item_untouched(self):
        item = _make("https://a.com/1", importance=8.0)
        apply_recurrence([item], SeenStore(), _CFG, "2026-06-16")
        assert item.importance_score == 8.0
        assert "recurring" not in item.raw.metadata

    def test_flat_rerun_demoted_and_tagged(self):
        item = _make("https://a.com/1", score=100, importance=8.0)
        store = SeenStore()
        store.mark([_make("https://a.com/1", score=100)], "2026-06-14")
        apply_recurrence([item], store, _CFG, "2026-06-16")
        assert item.importance_score == pytest.approx(8.0 * 0.4)
        assert item.raw.metadata["recurring"] == {"days": 2, "escalated": False}

    def test_escalating_story_keeps_weight(self):
        item = _make("https://a.com/1", score=400, importance=8.0)
        store = SeenStore()
        store.mark([_make("https://a.com/1", score=100)], "2026-06-15")
        apply_recurrence([item], store, _CFG, "2026-06-16")
        assert item.importance_score == 8.0
        assert item.raw.metadata["recurring"]["escalated"] is True

    def test_disabled_is_noop(self):
        item = _make("https://a.com/1", importance=8.0)
        store = SeenStore()
        store.mark([_make("https://a.com/1")], "2026-06-14")
        apply_recurrence([item], store, {"settings": {"dedup_state": {"enabled": False}}}, "2026-06-16")
        assert item.importance_score == 8.0


@pytest.mark.asyncio
async def test_load_seen_store_no_repo_returns_empty():
    store = await load_seen_store({"settings": {"reports_repo": ""}})
    assert store.entries == {}
