from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class SourceType(str, Enum):
    GITHUB = "github"
    HACKERNEWS = "hackernews"
    ARXIV = "arxiv"
    RSS_BLOG = "rss_blog"
    TWITTER = "twitter"
    BLUESKY = "bluesky"
    REDDIT = "reddit"
    YOUTUBE = "youtube"


class RawNewsItem(BaseModel):
    """Raw item as fetched from a source, before LLM processing."""

    source: SourceType
    source_name: str
    title: str
    url: str
    content: str = ""
    published_at: Optional[datetime] = None
    metadata: dict = Field(default_factory=dict)


class ProcessedNewsItem(BaseModel):
    """Item after LLM processing — enriched with AI-generated fields."""

    raw: RawNewsItem
    summary_en: str = ""
    summary_zh: str = ""
    category: str = ""
    importance_score: float = 0.0
    tags: list[str] = Field(default_factory=list)
    why_it_matters: str = ""
    why_it_matters_zh: str = ""


class SourceResult(BaseModel):
    """Result of a single source fetch — used for run summary."""

    name: str
    item_count: int = 0
    error: str | None = None
