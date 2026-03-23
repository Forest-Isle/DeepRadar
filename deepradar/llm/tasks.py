from __future__ import annotations

import json
import logging
from typing import Any

from deepradar.llm.client import LLMClient
from deepradar.llm.prompts import (
    BATCH_SUMMARIZE_PROMPT,
    DAILY_HEADLINE_PROMPT,
    GITHUB_REPO_PROMPT,
    SYSTEM_PROMPT,
)
from deepradar.processing.models import ProcessedNewsItem, RawNewsItem, SourceType

logger = logging.getLogger(__name__)


def _parse_json(text: str) -> Any:
    """Try to parse JSON, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return json.loads(text)


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


def batch_summarize(
    client: LLMClient,
    items: list[RawNewsItem],
    batch_size: int = 12,
) -> list[ProcessedNewsItem]:
    """Process items through Claude API in batches to get summaries, categories, scores."""
    results: list[ProcessedNewsItem] = []

    for batch_start in range(0, len(items), batch_size):
        batch = items[batch_start : batch_start + batch_size]
        items_json = _items_to_json(batch)
        prompt = BATCH_SUMMARIZE_PROMPT.format(items_json=items_json)

        try:
            response = client.complete(SYSTEM_PROMPT, prompt)
            parsed = _parse_json(response)

            for entry in parsed:
                idx = entry.get("index", 0)
                if idx >= len(batch):
                    continue
                raw = batch[idx]
                results.append(
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
            logger.info(f"Batch {batch_start // batch_size + 1}: processed {len(parsed)} items")
        except Exception as e:
            logger.error(f"LLM batch processing failed: {e}")
            # Fallback: create items without LLM enrichment
            for raw in batch:
                results.append(ProcessedNewsItem(raw=raw))

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
