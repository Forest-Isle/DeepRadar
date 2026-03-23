# DeepRadar — AI News Sniffer

每日自动追踪最前沿的 AI 资讯和 GitHub 项目，生成中英双语日报。

## Features

- **7 大数据源**: GitHub Trending, Hacker News, arXiv, RSS 博客, Twitter/X, Reddit, YouTube
- **AI 智能处理**: Claude API 自动摘要、分类、评分、中英双语翻译
- **自动化运行**: GitHub Actions 每日定时执行
- **精美报告**: 结构化 Markdown 日报，自动推送到独立仓库

## Quick Start

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
export ANTHROPIC_API_KEY="your-api-key"
export REPORTS_REPO="your-username/DeepRadar-Reports"  # 可选
export REPORTS_REPO_TOKEN="your-github-pat"             # 可选
```

### 3. 本地运行

```bash
python -m deepradar.main
```

报告会保存到 `output/YYYY-MM-DD.md`（未配置远程仓库时）。

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

### 手动触发

在 Actions 页面点击 "Run workflow" 可手动触发一次运行。

## 配置

所有配置文件在 `config/` 目录:

- `sources.yaml` — 数据源 URL、参数
- `categories.yaml` — AI 分类关键词
- `settings.yaml` — LLM 模型、报告参数

## 项目结构

```
deepradar/
├── main.py              # 主编排器
├── config.py            # 配置加载
├── sources/             # 7 个数据源采集模块
├── processing/          # 去重、过滤
├── llm/                 # Claude API 集成
├── report/              # Markdown 报告生成
└── publish/             # GitHub 发布
```

## 成本

使用 Claude Sonnet API，每日运行成本约 $0.10-0.20。

## License

MIT
