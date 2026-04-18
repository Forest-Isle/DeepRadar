# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.3.0] - 2026-04-18

### Added
- Support for custom Anthropic API base URL via `ANTHROPIC_BASE_URL` env var or `llm.base_url` in `settings.yaml` — enables using relay/proxy API endpoints
- `python-dotenv` dependency for automatic `.env` file loading

## [0.2.0] - 2026-04-17

### Added
- CLI arguments: `--dry-run`, `--sources`, `--date`, `--output-dir`, `--config-dir`, `--verbose`, `--no-llm`
- Webhook notifications (Slack / 飞书 / Discord) via `DEEPRADAR_WEBHOOK_URL`
- 43 unit tests covering dedup, filter, keywords, LLM tasks, report generation, config loading, and notifications

## [0.1.0] - 2026-04-01

### Added
- Initial release with 7 data sources: GitHub Trending, Hacker News, arXiv, RSS Blogs, Twitter/X, Reddit, YouTube
- Claude API integration for summarization, categorization, scoring, and bilingual translation
- GitHub Actions workflow for daily automated runs
- Markdown report generation with auto-publish to a separate GitHub repo
