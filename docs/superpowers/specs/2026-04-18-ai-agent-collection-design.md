# AI Agent 信息收集功能设计

**日期**: 2026-04-18  
**状态**: 待实现

## 目标

在现有 DeepRadar AI 资讯聚合 pipeline 基础上，专项增强对 AI agent 领域信息的覆盖与输出，包括技术进展（框架、论文、架构）和生态产品（发布、基准、工具）两个维度。

## 方案选择

采用**方案 A：关键词增强 + Agent 专属类目 + 独立报告模块**，完全复用现有 pipeline，改动集中在配置和报告层。

## 设计

### 1. 配置层变更

#### `config/categories.yaml`

新增 `AI Agent` 类目：

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

权重设为 1.5，高于其他类目，确保 agent 相关内容优先出现在报告中。

#### `config/sources.yaml`

新增专属 RSS 源（`rss_blogs.feeds` 下追加）：

| 名称 | URL |
|------|-----|
| LangChain Blog | `https://blog.langchain.dev/rss/` |
| AutoGen Blog | `https://microsoft.github.io/autogen/blog/rss.xml` |

arXiv 类目追加 `cs.MA`（多智能体系统）：

```yaml
arxiv:
  categories: ["cs.AI", "cs.CL", "cs.LG", "cs.CV", "cs.MA"]
```

### 2. 数据处理层

#### `deepradar/processing/models.py`

在 `ProcessedItem` 上新增字段：

```python
is_agent_related: bool = False
```

填充逻辑：若条目命中 `AI Agent` 类目关键词，则置为 `True`。由现有关键词匹配流程驱动，无需额外 LLM 调用，不增加运行成本。

#### `deepradar/processing/filter.py`（或 `keywords.py`）

在分类打标后，检查是否命中 `AI Agent` 类目，若是则设置 `item.is_agent_related = True`。

### 3. 报告层

#### 日报扩展（`deepradar/report/generator.py`）

在现有日报 `output/YYYY-MM-DD.md` 末尾追加 `## AI Agent 专题` 板块：
- 来源：当日 `is_agent_related=True` 的条目
- 最多展示 10 条，按权重评分降序排列
- 每条格式：标题 + 来源 + 一句话摘要

#### 独立 Agent 报告（新增 `deepradar/report/agent_report.py`）

输出路径：`output/agent-YYYY-MM-DD.md`

报告结构：
1. **Executive Summary** — 当日 agent 领域核心动态（3-5 句）
2. **框架与工具动态** — 来自 Blog/GitHub 的条目
3. **论文与研究** — 来自 arXiv 的条目
4. **产品与发布** — 来自社区/新闻的条目
5. **原始条目列表** — 全量 agent 相关条目

分组方式：按来源类型（arXiv / Blog / 社区）自然分组，为后续细分子类预留扩展点。

两份报告共用同一批 `is_agent_related` 条目，无重复过滤处理。

#### `deepradar/main.py`

在主流程末端添加独立 agent 报告的生成调用。

## 数据流

```
Sources (新增 LangChain/AutoGen RSS + cs.MA arXiv)
  ↓
现有采集 pipeline（无变化）
  ↓
关键词分类（新增 AI Agent 类目 → is_agent_related 标记）
  ↓
┌─────────────────────┬──────────────────────────┐
│  现有日报            │  新增独立 Agent 报告       │
│  + AI Agent 专题板块 │  output/agent-YYYY-MM-DD.md│
└─────────────────────┴──────────────────────────┘
```

## 扩展点

- **子类细分**：后续可将 `AI Agent` 拆分为"框架与工具 / 多智能体系统 / Agent 评测 / 商业产品 / 安全对齐"等子类
- **LLM 二次分类**：在关键词召回基础上叠加 LLM 精排，提升准确率
- **新增来源**：CrewAI、AgentBench、Papers With Code agent 榜单等

## 改动文件清单

| 文件 | 改动类型 |
|------|---------|
| `config/categories.yaml` | 新增 AI Agent 类目 |
| `config/sources.yaml` | 新增 RSS 源，arXiv 加 cs.MA |
| `deepradar/processing/models.py` | 新增 `is_agent_related` 字段 |
| `deepradar/processing/filter.py` 或 `keywords.py` | 填充 `is_agent_related` 标记 |
| `deepradar/report/generator.py` | 日报末尾追加 Agent 专题板块 |
| `deepradar/report/agent_report.py` | 新增文件：独立 agent 报告生成器 |
| `deepradar/main.py` | 调用独立 agent 报告生成 |
