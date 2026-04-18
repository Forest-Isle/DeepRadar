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
