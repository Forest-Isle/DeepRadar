# AI Agent 信息收集 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有 DeepRadar pipeline 上增加 AI Agent 专项信息收集能力，输出日报 Agent 专题板块 + 独立 agent 报告文件。

**Architecture:** 配置层新增 `AI Agent` 关键词类目 + 专属 RSS 源；处理层在 `ProcessedNewsItem` 上打 `is_agent_related` 标记；报告层新增 `agent_report.py` 模块生成独立报告，同时在现有日报末尾追加 Agent 专题板块。

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, pytest

---

## File Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `config/categories.yaml` | 修改 | 新增 `AI Agent` 类目及关键词列表 |
| `config/sources.yaml` | 修改 | 新增 LangChain/AutoGen RSS；arXiv 加 `cs.MA` |
| `deepradar/processing/models.py` | 修改 | `ProcessedNewsItem` 新增 `is_agent_related: bool` |
| `deepradar/processing/filter.py` | 修改 | 在 `filter_relevant` 返回前填充 `is_agent_related` |
| `deepradar/report/agent_report.py` | 新建 | 独立 agent 报告生成器 |
| `deepradar/report/generator.py` | 修改 | 日报末尾追加 Agent 专题板块 |
| `deepradar/main.py` | 修改 | 主流程调用独立 agent 报告生成并写文件 |
| `tests/processing/test_filter.py` | 修改 | 新增 `is_agent_related` 标记测试 |
| `tests/report/test_agent_report.py` | 新建 | agent_report 模块测试 |
| `tests/report/test_generator.py` | 修改 | 新增日报 Agent 专题板块测试 |

---

## Task 1: 新增 AI Agent 配置

**Files:**
- Modify: `config/categories.yaml`
- Modify: `config/sources.yaml`

- [ ] **Step 1: 在 categories.yaml 末尾追加 AI Agent 类目**

打开 `config/categories.yaml`，在 `categories:` 列表末尾追加：

```yaml
  - name: "AI Agent"
    keywords:
      - "agent"
      - "multi-agent"
      - "agentic"
      - "autonomous agent"
      - "tool use"
      - "tool calling"
      - "function calling"
      - "langchain"
      - "langgraph"
      - "autogpt"
      - "crewai"
      - "autogen"
      - "memory"
      - "planning"
      - "reflection"
      - "mcp"
      - "model context protocol"
      - "agent framework"
      - "agent benchmark"
      - "agentbench"
    weight: 1.5
```

- [ ] **Step 2: 在 sources.yaml 追加 RSS 源并扩展 arXiv 类目**

在 `rss_blogs.feeds` 列表末尾追加两条：

```yaml
    - name: "LangChain Blog"
      url: "https://blog.langchain.dev/rss/"
    - name: "AutoGen Blog"
      url: "https://microsoft.github.io/autogen/blog/rss.xml"
```

将 `arxiv.categories` 改为：

```yaml
  categories: ["cs.AI", "cs.CL", "cs.LG", "cs.CV", "cs.MA"]
```

- [ ] **Step 3: Commit**

```bash
git add config/categories.yaml config/sources.yaml
git commit -m "feat: add AI Agent category and dedicated RSS sources"
```

---

## Task 2: ProcessedNewsItem 增加 is_agent_related 字段

**Files:**
- Modify: `deepradar/processing/models.py`
- Modify: `tests/processing/test_models.py`

- [ ] **Step 1: 写失败测试**

在 `tests/processing/test_models.py` 末尾追加：

```python
def test_processed_news_item_has_is_agent_related():
    from deepradar.processing.models import ProcessedNewsItem, RawNewsItem, SourceType
    item = ProcessedNewsItem(
        raw=RawNewsItem(
            source=SourceType.ARXIV,
            source_name="arxiv",
            title="Test",
            url="https://example.com",
        )
    )
    assert item.is_agent_related is False

def test_processed_news_item_is_agent_related_can_be_true():
    from deepradar.processing.models import ProcessedNewsItem, RawNewsItem, SourceType
    item = ProcessedNewsItem(
        raw=RawNewsItem(
            source=SourceType.ARXIV,
            source_name="arxiv",
            title="Test",
            url="https://example.com",
        ),
        is_agent_related=True,
    )
    assert item.is_agent_related is True
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/processing/test_models.py::test_processed_news_item_has_is_agent_related -v
```

Expected: `FAILED` — `ProcessedNewsItem` 无 `is_agent_related` 字段。

- [ ] **Step 3: 在 ProcessedNewsItem 添加字段**

在 `deepradar/processing/models.py` 的 `ProcessedNewsItem` 类中，在 `why_it_matters_zh` 字段后追加：

```python
    is_agent_related: bool = False
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/processing/test_models.py -v
```

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add deepradar/processing/models.py tests/processing/test_models.py
git commit -m "feat: add is_agent_related field to ProcessedNewsItem"
```

---

## Task 3: filter_relevant 填充 is_agent_related 标记

**Files:**
- Modify: `deepradar/processing/filter.py`
- Modify: `tests/processing/test_filter.py`

- [ ] **Step 1: 写失败测试**

在 `tests/processing/test_filter.py` 末尾追加：

```python
def test_filter_marks_agent_items(sample_config):
    from deepradar.processing.filter import filter_relevant
    from deepradar.processing.models import RawNewsItem, SourceType

    agent_item = RawNewsItem(
        source=SourceType.RSS_BLOG,
        source_name="blog",
        title="LangChain introduces new agent framework",
        url="https://example.com/1",
        content="langchain autogen multi-agent tool calling",
    )
    non_agent_item = RawNewsItem(
        source=SourceType.RSS_BLOG,
        source_name="blog",
        title="GPT-4 training breakthrough",
        url="https://example.com/2",
        content="large language model training gpu",
    )

    # sample_config must have categories with AI Agent entry and weight 1.5
    config_with_agent = dict(sample_config)
    cats = config_with_agent.get("categories", {})
    categories_list = cats.get("categories", [])
    categories_list.append({
        "name": "AI Agent",
        "keywords": ["langchain", "autogen", "multi-agent", "agent", "tool calling"],
        "weight": 1.5,
    })

    result = filter_relevant([agent_item, non_agent_item], config_with_agent, min_score=0.0)
    agent_result = next((r for r in result if "LangChain" in r.raw.title), None)
    assert agent_result is not None
    assert agent_result.is_agent_related is True

    non_agent_result = next((r for r in result if "GPT-4" in r.raw.title), None)
    assert non_agent_result is not None
    assert non_agent_result.is_agent_related is False
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/processing/test_filter.py::test_filter_marks_agent_items -v
```

Expected: `FAILED` — `filter_relevant` 返回 `RawNewsItem`，不含 `is_agent_related`。

- [ ] **Step 3: 修改 filter_relevant 填充标记**

`filter_relevant` 当前返回 `list[RawNewsItem]`，但实际上应在 `main.py` 中 LLM enrichment 之前标记。  
由于 `is_agent_related` 属于 `ProcessedNewsItem`，需要调整方案：在 `filter_relevant` 内部通过 metadata 传递标记，再在 `main.py` 的 `ProcessedNewsItem` 构建时使用。

**更简洁方案**：在 `filter_relevant` 中将命中 `AI Agent` 类目的 item 的 `metadata["is_agent_related"] = True`，然后在 `main.py` 构建 `ProcessedNewsItem` 时读取该 metadata 字段。

修改 `deepradar/processing/filter.py`，在 `_compute_relevance_score` 同级别添加辅助函数，并在 `filter_relevant` 的 scored 循环中标记：

```python
def _is_agent_related(item: RawNewsItem, categories_cfg: dict[str, Any]) -> bool:
    """Return True if item matches any keyword in the AI Agent category."""
    text = f"{item.title} {item.content}".lower()
    for cat in categories_cfg.get("categories", []):
        if cat.get("name") == "AI Agent":
            for kw in cat.get("keywords", []):
                if kw in text:
                    return True
    return False
```

在 `filter_relevant` 的 for 循环中，紧跟 `item.metadata["relevance_score"] = rel_score` 之后追加：

```python
            item.metadata["is_agent_related"] = _is_agent_related(item, categories_cfg)
```

完整修改后的 `filter_relevant` 循环部分：

```python
    for item in items:
        rel_score = _compute_relevance_score(item, categories_cfg)
        if rel_score >= min_score:
            item.metadata["relevance_score"] = rel_score
            item.metadata["is_agent_related"] = _is_agent_related(item, categories_cfg)
            scored.append((rel_score, item))
```

- [ ] **Step 4: 更新测试以匹配 metadata 方案**

将 `tests/processing/test_filter.py` 中刚才新增的测试的断言改为检查 metadata：

```python
    agent_result = next((r for r in result if "LangChain" in r.raw.title), None)
    assert agent_result is not None
    assert agent_result.metadata.get("is_agent_related") is True

    non_agent_result = next((r for r in result if "GPT-4" in r.raw.title), None)
    assert non_agent_result is not None
    assert non_agent_result.metadata.get("is_agent_related") is not True
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
pytest tests/processing/test_filter.py -v
```

Expected: 全部 PASS。

- [ ] **Step 6: Commit**

```bash
git add deepradar/processing/filter.py tests/processing/test_filter.py
git commit -m "feat: mark agent-related items via metadata in filter_relevant"
```

---

## Task 4: main.py 将 metadata 标记传入 ProcessedNewsItem

**Files:**
- Modify: `deepradar/main.py`

- [ ] **Step 1: 在无 LLM 分支中传递 is_agent_related**

在 `main.py` 的 `else` 分支（无 API KEY 时）：

当前：
```python
        processed = [ProcessedNewsItem(raw=item) for item in filtered]
```

改为：
```python
        processed = [
            ProcessedNewsItem(
                raw=item,
                is_agent_related=item.metadata.get("is_agent_related", False),
            )
            for item in filtered
        ]
```

- [ ] **Step 2: 在有 LLM 分支中传递 is_agent_related**

`batch_summarize` 在 `deepradar/llm/tasks.py` 中构建 `ProcessedNewsItem`，需要将 metadata 中的标记传入。
打开 `deepradar/llm/tasks.py`，找到构建 `ProcessedNewsItem` 的位置（搜索 `ProcessedNewsItem(`），在构建时追加：

```python
is_agent_related=item.metadata.get("is_agent_related", False),
```

> **Note:** 若 `batch_summarize` 内部已有完整的 `ProcessedNewsItem` 构建逻辑，直接在那里加字段即可；如果它只是 enrichment（在已有 item 上更新字段），则在 `main.py` 的有 LLM 分支末尾补一次赋值：
> ```python
> for p_item in processed:
>     p_item.is_agent_related = p_item.raw.metadata.get("is_agent_related", False)
> ```

- [ ] **Step 3: 运行现有测试，确认没有回归**

```bash
pytest tests/ -v
```

Expected: 全部 PASS。

- [ ] **Step 4: Commit**

```bash
git add deepradar/main.py deepradar/llm/tasks.py
git commit -m "feat: propagate is_agent_related from metadata into ProcessedNewsItem"
```

---

## Task 5: 新建独立 Agent 报告生成器

**Files:**
- Create: `deepradar/report/agent_report.py`
- Create: `tests/report/test_agent_report.py`

- [ ] **Step 1: 写失败测试**

新建 `tests/report/test_agent_report.py`：

```python
from deepradar.processing.models import ProcessedNewsItem, RawNewsItem, SourceType
from deepradar.report.agent_report import generate_agent_report


def _make_agent_item(source: SourceType, title: str, score: float = 5.0) -> ProcessedNewsItem:
    return ProcessedNewsItem(
        raw=RawNewsItem(
            source=source,
            source_name=source.value,
            title=title,
            url="https://example.com",
        ),
        summary_en="English summary",
        summary_zh="中文摘要",
        importance_score=score,
        category="AI Agent",
        is_agent_related=True,
    )


def test_generate_agent_report_contains_header():
    items = [_make_agent_item(SourceType.ARXIV, "Multi-agent reasoning paper")]
    md = generate_agent_report(items, "2026-04-18")
    assert "AI Agent" in md
    assert "2026-04-18" in md


def test_generate_agent_report_sections():
    items = [
        _make_agent_item(SourceType.ARXIV, "Agent paper"),
        _make_agent_item(SourceType.RSS_BLOG, "LangChain release"),
        _make_agent_item(SourceType.REDDIT, "CrewAI discussion"),
    ]
    md = generate_agent_report(items, "2026-04-18")
    assert "论文与研究" in md or "Papers" in md
    assert "框架与工具" in md or "Frameworks" in md
    assert "产品与发布" in md or "Community" in md


def test_generate_agent_report_empty_items():
    md = generate_agent_report([], "2026-04-18")
    assert "AI Agent" in md
    assert "No agent-related items" in md or "暂无" in md


def test_generate_agent_report_all_items_listed():
    items = [_make_agent_item(SourceType.ARXIV, f"Paper {i}") for i in range(5)]
    md = generate_agent_report(items, "2026-04-18")
    for i in range(5):
        assert f"Paper {i}" in md
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/report/test_agent_report.py -v
```

Expected: `FAILED` — `generate_agent_report` 不存在。

- [ ] **Step 3: 实现 agent_report.py**

新建 `deepradar/report/agent_report.py`：

```python
from __future__ import annotations

from deepradar.processing.models import ProcessedNewsItem, SourceType


_BLOG_SOURCES = {SourceType.RSS_BLOG, SourceType.TWITTER, SourceType.YOUTUBE}
_COMMUNITY_SOURCES = {SourceType.HACKERNEWS, SourceType.REDDIT}


def generate_agent_report(items: list[ProcessedNewsItem], date_str: str) -> str:
    """Generate a standalone AI Agent digest report in Markdown."""
    agent_items = [i for i in items if i.is_agent_related]
    agent_items.sort(key=lambda x: x.importance_score, reverse=True)

    md = f"# 🤖 AI Agent Daily Digest — {date_str}\n\n"
    md += "> 专注 AI Agent 领域的技术进展与生态动态\n\n---\n\n"

    if not agent_items:
        md += "暂无 agent 相关内容。\n"
        return md

    # Executive Summary
    md += "## 📋 Executive Summary\n\n"
    top = agent_items[:3]
    for item in top:
        summary = item.summary_zh or item.summary_en or item.raw.title
        md += f"- **[{item.raw.title}]({item.raw.url})**: {summary}\n"
    md += "\n---\n\n"

    # 框架与工具动态 (Blog / GitHub / Twitter / YouTube)
    framework_items = [i for i in agent_items if i.raw.source in _BLOG_SOURCES or i.raw.source == SourceType.GITHUB]
    if framework_items:
        md += "## 🔧 框架与工具动态 / Frameworks & Tools\n\n"
        for item in framework_items:
            md += f"### [{item.raw.title}]({item.raw.url})\n"
            md += f"**来源**: {item.raw.source_name}\n\n"
            if item.summary_en:
                md += f"{item.summary_en}\n\n"
            if item.summary_zh:
                md += f"{item.summary_zh}\n\n"
        md += "---\n\n"

    # 论文与研究 (arXiv)
    paper_items = [i for i in agent_items if i.raw.source == SourceType.ARXIV]
    if paper_items:
        md += "## 📄 论文与研究 / Papers & Research\n\n"
        for item in paper_items:
            authors = item.raw.metadata.get("authors", "")
            md += f"### [{item.raw.title}]({item.raw.url})\n"
            if authors:
                md += f"**Authors**: {authors}\n\n"
            if item.summary_en:
                md += f"{item.summary_en}\n\n"
            if item.summary_zh:
                md += f"{item.summary_zh}\n\n"
        md += "---\n\n"

    # 产品与发布 (HN / Reddit / Community)
    community_items = [i for i in agent_items if i.raw.source in _COMMUNITY_SOURCES]
    if community_items:
        md += "## 🚀 产品与发布 / Community & Products\n\n"
        for item in community_items:
            md += f"- **[{item.raw.title}]({item.raw.url})** ({item.raw.source_name})"
            summary = item.summary_zh or item.summary_en
            if summary:
                md += f" — {summary}"
            md += "\n"
        md += "\n---\n\n"

    # 原始条目列表
    md += "## 📑 全量条目 / All Items\n\n"
    for idx, item in enumerate(agent_items, 1):
        md += f"{idx}. [{item.raw.title}]({item.raw.url}) ({item.raw.source_name}, score={item.importance_score:.1f})\n"

    return md
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/report/test_agent_report.py -v
```

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add deepradar/report/agent_report.py tests/report/test_agent_report.py
git commit -m "feat: add standalone AI Agent report generator"
```

---

## Task 6: 日报追加 Agent 专题板块

**Files:**
- Modify: `deepradar/report/generator.py`
- Modify: `tests/report/test_generator.py`

- [ ] **Step 1: 写失败测试**

在 `tests/report/test_generator.py` 末尾追加：

```python
def test_report_contains_agent_section_when_agent_items_present():
    from deepradar.processing.models import ProcessedNewsItem, RawNewsItem, SourceType
    items = []
    for i in range(3):
        item = ProcessedNewsItem(
            raw=RawNewsItem(
                source=SourceType.RSS_BLOG,
                source_name="blog",
                title=f"Agent item {i}",
                url="https://example.com",
            ),
            summary_en=f"Summary {i}",
            summary_zh=f"摘要 {i}",
            importance_score=float(5 - i),
            category="AI Agent",
            is_agent_related=True,
        )
        items.append(item)
    md = generate_report(items, "2026-04-18", HEADLINE, {}, MINIMAL_CONFIG)
    assert "AI Agent 专题" in md
    assert "Agent item 0" in md


def test_report_no_agent_section_when_no_agent_items():
    md = generate_report([], "2026-04-18", HEADLINE, {}, MINIMAL_CONFIG)
    assert "AI Agent 专题" not in md
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
pytest tests/report/test_generator.py::test_report_contains_agent_section_when_agent_items_present -v
```

Expected: `FAILED` — 报告中无 `AI Agent 专题` 板块。

- [ ] **Step 3: 修改 generator.py 追加 Agent 专题板块**

在 `generate_report` 函数中，在 `# Footer` 注释之前追加以下代码：

```python
    # AI Agent 专题板块
    agent_items = _sort_by_importance([i for i in items if i.is_agent_related])
    if agent_items:
        md += "\n---\n\n## 🤖 AI Agent 专题 / Agent Focus\n\n"
        for item in agent_items[:10]:
            source = item.raw.source_name
            summary = item.summary_zh or item.summary_en or ""
            md += f"- **[{item.raw.title}]({item.raw.url})** ({source})"
            if summary:
                md += f" — {summary}"
            md += "\n"
        md += "\n"
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
pytest tests/report/test_generator.py -v
```

Expected: 全部 PASS。

- [ ] **Step 5: Commit**

```bash
git add deepradar/report/generator.py tests/report/test_generator.py
git commit -m "feat: append AI Agent section to daily report"
```

---

## Task 7: main.py 集成独立 Agent 报告写文件

**Files:**
- Modify: `deepradar/main.py`

- [ ] **Step 1: 在 main.py 中导入并调用 generate_agent_report**

在 `deepradar/main.py` 顶部导入区追加：

```python
from deepradar.report.agent_report import generate_agent_report
```

在 `run` 函数的 `# Step 4: Generate report` 块中，紧跟 `report_md = generate_report(...)` 之后追加：

```python
    agent_report_md = generate_agent_report(processed, today)
```

- [ ] **Step 2: 将 agent report 写入文件**

在 `publish_report(report_md, today, config)` 之后追加：

```python
    # Write standalone agent report
    from pathlib import Path
    output_dir = Path(config.get("settings", {}).get("output_dir", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    agent_report_path = output_dir / f"agent-{today}.md"
    agent_report_path.write_text(agent_report_md, encoding="utf-8")
    logger.info(f"Agent report written to {agent_report_path}")
```

- [ ] **Step 3: 运行完整测试套件，确认没有回归**

```bash
pytest tests/ -v
```

Expected: 全部 PASS。

- [ ] **Step 4: Commit**

```bash
git add deepradar/main.py
git commit -m "feat: generate and write standalone agent report in main pipeline"
```

---

## Task 8: 全流程验证

**Files:**
- 只读验证，无文件修改

- [ ] **Step 1: 以 --no-llm --dry-run 模式跑一次完整 pipeline**

```bash
python -m deepradar --no-llm --dry-run --sources hackernews,arxiv
```

Expected: 控制台输出 `Agent report written to output/agent-YYYY-MM-DD.md`，无异常。

- [ ] **Step 2: 确认两份报告文件存在且包含预期内容**

```bash
ls output/
grep "AI Agent 专题" output/$(date +%Y-%m-%d).md
grep "AI Agent Daily Digest" output/agent-$(date +%Y-%m-%d).md
```

Expected: 两个 grep 均有输出。

- [ ] **Step 3: 运行完整测试套件**

```bash
pytest tests/ -v --tb=short
```

Expected: 全部 PASS，无 WARNING。

- [ ] **Step 4: 最终 Commit**

```bash
git add .
git commit -m "feat: AI agent collection - full pipeline integration complete"
```
