---
name: web-search-tools
description: "网络信息搜索工具：提供豆包搜索（火山引擎，推荐）、Tavily、阿里云百炼 WebSearch 三个本地搜索工具的选用规范，禁止使用Anthropic官方WebSearch/WebFetch。"
disable-model-invocation: true
---

# 网络信息搜索工具

**重要约束**：禁止使用 Anthropic 官方 WebSearch 和 WebFetch 工具（中国大陆地区不可用），所有网络信息必须使用以下本地工具。

---

## 工具选型决策

三个本地搜索工具的完整使用说明、参数详解、模块导入接口、返回字段、依赖配置、选型决策表与流程图，详见 [docs/A股工具使用指南.md](../../../docs/A股工具使用指南.md) 第八章~第十章。本技能仅提供关键决策摘要与命令速查。

### 选型决策摘要

| 维度 | `doubao_search.py` | `tavily_search.py` | `web_search.py` |
|------|--------------------|---------------------|------------------|
| 鉴权 | 火山引擎 AK/SK | DASHSCOPE_API_KEY | DASHSCOPE_API_KEY |
| 协议 | HTTP REST + SignatureV4 | MCP（SSE） | MCP（SSE） |
| 正文能力 | ✅ `--need-content` | ✅ `raw_content` | ❌ |
| 权威度筛选 | ✅ `--finance`（仅非常权威信源） | ❌ | ❌ |
| 站点过滤 | ✅ `--sites` / `--block-hosts` | ❌ | ❌ |
| 报告导出 | ✅ `--export` Markdown | ❌ | ❌ |
| QPS 限流 | ✅ 客户端线程安全 | ❌ | ❌ |
| 模型生态 | 中立无绑定 | 阿里云通义千问 | 阿里云通义千问 |
| 免费额度 | 500 次/月 | 按百炼计费 | 按百炼计费 |

### 推荐场景

| 场景 | 推荐工具 |
|------|---------|
| 跨市场检索（A/港/美/中概股）、海外央行政策、SEC 公告 | `doubao_search.py` |
| 投研报告自动化（公告/研报全文 + Markdown 导出） | `doubao_search.py --need-content --export` |
| 财经定向搜索（金融行业 + 仅非常权威信源） | `doubao_search.py --finance` |
| 多模型混合架构（通义千问/Claude/本地 LLM） | `doubao_search.py`（中立无绑定） |
| 个人/小团队高频监控（500 次免费额度） | `doubao_search.py` |
| 阿里云全栈 + 仅用通义千问 | `web_search.py` |
| A股量化基本面 + 百炼金融专项 MCP | `web_search.py` |
| 持牌金融机构私有化/等保合规 | `web_search.py` |
| 内容深度搜索（MD&A、分析师点评） | `tavily_search.py` |

完整选型决策流程图与实战推荐参见 [A股工具使用指南.md#十搜索工具选型对比](../../../docs/A股工具使用指南.md#十搜索工具选型对比)。

---

## 命令速查

### 豆包搜索（火山引擎，推荐）

```bash
# 基本搜索
python tools/common/doubao_search.py "{搜索关键词}"

# 财经定向搜索（金融行业 + 仅非常权威信源）
python tools/common/doubao_search.py "紫金矿业 半年报" --finance

# 抓取正文做大模型拆解 + 导出 Markdown 报告
python tools/common/doubao_search.py "腾讯控股 2025年报" --need-content --export

# 站点过滤（仅 SEC EDGAR / 港交所披露易）
python tools/common/doubao_search.py "AAPL 10-K" --sites sec.gov
python tools/common/doubao_search.py "腾讯 回购" --sites hkexnews.hk

# 时间范围（day/week/month/year）
python tools/common/doubao_search.py "美联储 加息" --time-range week

# 指定返回条数
python tools/common/doubao_search.py "{关键词}" --count 10

# JSON 格式输出
python tools/common/doubao_search.py "{关键词}" --json
```

**依赖**：`pip install volcengine python-dotenv requests`
**配置**：在项目根目录 `.env` 文件中配置
```
VOLC_AK=你的AccessKeyID
VOLC_SK=你的SecretAccessKey
VOLC_QPS=5  # 可选
```

### Tavily 搜索（深度内容）

```bash
python tools/common/tavily_search.py "{搜索关键词}" --max-results 5
# 返回 title、url、content 三个字段
# 支持高级搜索（search_depth="advanced"）
```

### WebSearch 搜索（阿里云百炼）

```bash
python tools/common/web_search.py "{搜索关键词}"
# 返回 title、link、snippet、hostname
```

**依赖**：`pip install mcp python-dotenv`
**配置**：在 `.env` 文件中配置 `DASHSCOPE_API_KEY`

---

## 重要内容多源验证（推荐）

对于重要分析（如财报研究、行业格局分析），建议**同时调用 2~3 个工具**，互为补充：

```bash
# 优先豆包搜索（正文 + 权威度 + 报告导出）
python tools/common/doubao_search.py "核电行业 全球竞争格局" --need-content --export

# 补充 Tavily（深度内容）+ WebSearch（多源视角）
python tools/common/tavily_search.py "核电行业 全球竞争格局 主要玩家"
python tools/common/web_search.py "核电行业 全球竞争格局 主要玩家"
```

- `doubao_search.py`：权威信源 + 正文能力，适合投研报告自动化
- `tavily_search.py`：内容深度高，适合管理层讨论、分析师点评
- `web_search.py`：多源视角，适合交叉验证

---

## 按市场分类的推荐工具

### A 股公司

| 场景 | 推荐工具 |
|------|---------|
| 财报交叉验证、投研报告自动化 | `doubao_search.py --finance --need-content --export` |
| 快速验证、关键词检索 | `web_search.py` 或 `tavily_search.py` 均可 |

### 港股/美股/中概股

| 场景 | 推荐工具 |
|------|---------|
| 港交所披露易 / SEC EDGAR 公告定向检索 | `doubao_search.py --sites hkexnews.hk` 或 `--sites sec.gov` |
| 跨市场对比（A+H+中概股） | `doubao_search.py` |
| 管理层讨论（MD&A）深度搜索 | `tavily_search.py` |
| 行业新闻与多源视角 | `web_search.py` |

---

## 模块导入接口

### 豆包搜索

```python
from tools.common.doubao_search import doubao_search

# 财经定向搜索
results = doubao_search(
    "紫金矿业 财报",
    count=10,
    industry="finance",
    auth_info_level=1,
    need_content=True,
)

for r in results:
    print(f"标题: {r['title']}")
    print(f"链接: {r['url']}")
    print(f"权威度: {r['auth_des']}（等级 {r['auth_level']}）")
```

### WebSearch

```python
import asyncio
from tools.common.web_search import search_web

async def main():
    result = await search_web(
        api_key="sk-xxx",
        mcp_url="https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/sse",
        query="黄金价格走势",
        num_results=5,
    )

asyncio.run(main())
```

---

## 相关技能

- [A股数据获取](./a-share-data.md)
- [港股数据获取](./hk-share-data.md)
- [公共工具索引](./common-tools-guide.md)
- [完整选型决策流程](../../../docs/A股工具使用指南.md#十搜索工具选型对比)

---

## 版本信息

- **版本**：2.0.0（新增豆包搜索，重构选型决策）
- **创建日期**：2026-07-31
- **最后更新**：2026-08-01
- **维护状态**：活跃维护
