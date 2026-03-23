from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


_config: dict[str, Any] | None = None


def _find_config_dir() -> Path:
    """Find the config directory relative to the project root."""
    # Try env var first, then relative to this file
    if env := os.environ.get("DEEPRADAR_CONFIG_DIR"):
        return Path(env)
    return Path(__file__).resolve().parent.parent / "config"


def load_config(config_dir: Path | None = None) -> dict[str, Any]:
    """Load and merge all YAML config files. Cached after first call."""
    global _config
    if _config is not None:
        return _config

    config_dir = config_dir or _find_config_dir()
    cfg: dict[str, Any] = {}
    for name in ("settings", "sources", "categories"):
        path = config_dir / f"{name}.yaml"
        if path.exists():
            with open(path) as f:
                cfg[name] = yaml.safe_load(f) or {}

    # Environment variable overrides
    cfg.setdefault("settings", {})
    cfg["settings"]["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")
    cfg["settings"]["reports_repo"] = os.environ.get(
        "REPORTS_REPO",
        cfg["settings"].get("publishing", {}).get("reports_repo", ""),
    )
    cfg["settings"]["reports_repo_token"] = os.environ.get("REPORTS_REPO_TOKEN", os.environ.get("GITHUB_TOKEN", ""))

    _config = cfg
    return cfg


def reset_config() -> None:
    """Reset cached config (for testing)."""
    global _config
    _config = None
