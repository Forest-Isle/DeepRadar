# DeepRadar — AI News Sniffer

每日自动追踪最前沿的 AI 资讯和 GitHub 项目，生成中英双语日报。

## Features

- **7 大数据源**: GitHub Trending, Hacker News, arXiv, RSS 博客, Twitter/X, Reddit, YouTube
- **AI 智能处理**: Claude API 自动摘要、分类、评分、中英双语翻译
- **自动化运行**: GitHub Actions 每日定时执行
- **精美报告**: 结构化 Markdown 日报，自动推送到独立仓库
- **灵活 CLI**: 支持 `--dry-run`、`--no-llm`、`--sources` 等参数，方便调试和定制
- **Webhook 通知**: 运行完成后可推送 Slack / 飞书 / Discord 等通知
- **完善测试**: 43 个单元测试覆盖核心模块

## Quick Start

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写，或直接 export：

```bash
export ANTHROPIC_API_KEY="your-api-key"
export ANTHROPIC_BASE_URL="https://your-relay.example.com"  # 可选，使用中转站时设置
export REPORTS_REPO="your-username/DeepRadar-Reports"        # 可选
export REPORTS_REPO_TOKEN="your-github-pat"                  # 可选
export DEEPRADAR_WEBHOOK_URL="https://hooks.example.com/..."  # 可选
```

### 3. 本地运行

```bash
# 完整运行（需要 ANTHROPIC_API_KEY）
python -m deepradar.main

# 仅测试采集管道，不调用 LLM
python -m deepradar.main --dry-run --no-llm

# 只抓取指定数据源
python -m deepradar.main --dry-run --no-llm --sources hackernews,arxiv
```

报告会保存到 `output/YYYY-MM-DD.md`（未配置远程仓库或使用 `--dry-run` 时）。

## CLI 参数

```
python -m deepradar.main [options]

Options:
  --dry-run             仅保存到本地，不推送到远程仓库
  --sources SRC,...     指定启用的数据源（逗号分隔）
  --date YYYY-MM-DD     覆盖报告日期（默认今天）
  --output-dir DIR      覆盖输出目录（默认 output/）
  --config-dir DIR      覆盖配置目录（默认 config/）
  --verbose             开启 DEBUG 日志
  --no-llm              跳过 LLM 处理（用于测试）
```

可用数据源名称: `hackernews`, `arxiv`, `rss_blogs`, `github_trending`, `reddit_rss`, `youtube_rss`, `twitter_rss`

## GitHub Actions 自动化

### 所需 Secrets

在 DeepRadar 仓库的 Settings > Secrets 中添加:

| Secret | 说明 |
|--------|------|
| `ANTHROPIC_API_KEY` | Claude API 密钥 |
| `REPORTS_REPO_TOKEN` | GitHub PAT (需要 `repo` 权限) |

### 所需 Variables

| Variable | 说明 | 示例 |
|----------|------|------|
| `REPORTS_REPO` | 报告输出仓库 | `username/DeepRadar-Reports` |
| `ANTHROPIC_BASE_URL` | LLM 请求端点（可选，使用中转站或兼容 API 时设置） | `https://your-relay.example.com` |

### 手动触发

在 Actions 页面点击 "Run workflow" 可手动触发一次运行。

## 配置

所有配置文件在 `config/` 目录:

| 文件 | 说明 |
|------|------|
| `settings.yaml` | LLM 模型、报告参数、通知配置 |
| `sources.yaml` | 数据源 URL、参数、开关 |
| `categories.yaml` | AI 分类关键词、权重 |

### 关键配置项

```yaml
# settings.yaml
llm:
  model: "claude-sonnet-4-20250514"
  base_url: ""                 # 可选，留空使用官方 API；或通过 ANTHROPIC_BASE_URL 环境变量设置
  batch_size: 12
  max_concurrent_batches: 3    # LLM 并发批次数

report:
  min_importance_score: 3.0    # 最低相关性分数阈值
  max_news_items: 15

notifications:
  webhook_url: ""              # 或通过 DEEPRADAR_WEBHOOK_URL 环境变量设置
  on_success: true
  on_failure: true
```

## 项目结构

```
deepradar/
├── main.py              # 主编排器 + CLI
├── config.py            # 配置加载 + 环境变量
├── notify.py            # Webhook 通知
├── sources/             # 7 个数据源采集模块
│   ├── base.py          # 数据源基类
│   ├── hackernews.py
│   ├── arxiv_papers.py
│   ├── github_trending.py
│   ├── rss_blogs.py
│   ├── reddit_rss.py
│   ├── twitter_rss.py
│   └── youtube_rss.py
├── processing/          # 数据处理
│   ├── models.py        # 数据模型 (RawNewsItem, ProcessedNewsItem, SourceResult)
│   ├── dedup.py         # URL + 标题模糊去重
│   ├── filter.py        # 相关性评分 + 过滤
│   ├── keywords.py      # 配置驱动的 AI 关键词匹配
│   └── utils.py         # 共享工具 (strip_html)
├── llm/                 # Claude API 集成
│   ├── client.py        # API 客户端 + 重试 + token 追踪
│   ├── tasks.py         # 异步批量摘要、标题生成、GitHub 项目解读
│   └── prompts.py       # Prompt 模板
├── report/              # Markdown 报告生成
│   ├── generator.py     # 报告组装（含数据源状态追踪）
│   └── templates.py     # 报告模板
└── publish/             # GitHub 发布
    └── github_publisher.py
```

## 测试

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v
```

测试覆盖: 去重、过滤、关键词匹配、HTML 清理、LLM 任务解析、报告生成、配置加载、Webhook 通知。

## 成本

使用 Claude Sonnet API，每日运行成本约 $0.10-0.20。使用 `--no-llm` 可零成本测试采集管道。

## License

MIT
