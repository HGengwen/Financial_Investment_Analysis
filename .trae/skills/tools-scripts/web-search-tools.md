---
name: web-search-tools
description: "网络信息搜索工具（v3.0 五工具）：AnySearch（A股投研首选）、豆包搜索（实时资讯首选）、Exa（美股深度研究首选）、Tavily（港美股深度内容辅源）、阿里云百炼 WebSearch（仅兜底）。提供市场×场景选型矩阵与命令速查，禁止使用 Anthropic 官方 WebSearch/WebFetch。"
disable-model-invocation: true
---
# 网络信息搜索工具（v3.0 五工具）

**重要约束**：禁止使用 Anthropic 官方 WebSearch 和 WebFetch 工具（中国大陆地区不可用），所有网络信息必须使用以下本地工具。

本文件为**技能文件统一引用入口**，提供五工具的角色定位、选型矩阵与命令速查。各工具的完整使用说明、参数详解、模块导入接口、返回字段、依赖配置，详见 [docs/A股工具使用指南.md](../../../docs/A股工具使用指南.md) 第八章~第十二章。

---

## 一、五工具角色定位

依据《搜索服务选择策略重构方案 v2.0》与对比报告结论：

| 工具                 | 角色定位                            | 关键能力                                                                                             | 免费额度                 | 国内稳定性   |
| -------------------- | ----------------------------------- | ---------------------------------------------------------------------------------------------------- | ------------------------ | ------------ |
| `anysearch.py`     | **A股投研首选**               | 23 类垂直数据库（财报/研报/公告/判例/专利）、多源交叉验证、tag 定向                                  | 每日 1000 次（0 点重置） | 直连 0.4s    |
| `doubao_search.py` | **实时资讯/舆情首选**         | `--finance` 权威信源、`--sites` 定向、`--need-content` 正文、`--export` 导出、跨市场综合检索 | 每月 500 次              | 直连 0.45s   |
| `exa_search.py`    | **美股深度研究首选**          | SEC filings、27K+ 美股全栈数据、外文论文、`--type deep` 深度档                                     | 注册 $20 + 月赠 $10      | 海外，波动大 |
| `tavily_search.py` | **港美股深度内容辅源**        | 管理层讨论、分析师点评（中文弱、国内网络不稳，不作主源）                                             | 每月 1000 次             | 海外，波动大 |
| `web_search.py`    | **仅阿里云生态/轻量验证兜底** | 2000 次一次性额度、无垂直深库、仅限百炼生态，移出默认组合                                            | 前 2000 次一次性         | 国内节点稳定 |

### 各工具核心参数速查

| 工具                 | 关键参数                                                                                                                       |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `anysearch.py`     | `--tag finance/legal/patent/paper`、`--zone cn/intl`、`--language zh-CN/en`、`--count`、`--export`                   |
| `doubao_search.py` | `--finance`、`--sites`、`--block-hosts`、`--need-content`、`--export`、`--time-range`、`--industry`、`--count` |
| `exa_search.py`    | `--type instant/fast/auto/deep-lite/deep`、`--highlights`、`--max-results`、`--max-characters`、`--no-autoprompt`    |
| `tavily_search.py` | `--max-results`（1-20）、搜索深度（advanced）、`--json`                                                                    |
| `web_search.py`    | `--num`、`--json`、`--api-key`                                                                                           |

---

## 二、市场 × 场景选型矩阵（定稿）

### A股 —— 双主组合

| 场景                         | 主搜索                                       | 辅/验证                     |
| ---------------------------- | -------------------------------------------- | --------------------------- |
| 财报/研报/公告/判例/专利深查 | `anysearch --tag finance/legal`            | `doubao --finance`        |
| 实时新闻/舆情/热点资讯       | `doubao --finance`                         | `anysearch`               |
| 精确数值核验                 | `financial_rigor.py`（专用工具，不属搜索） | —                          |
| 多源交叉验证                 | `anysearch` + `doubao` 双主              | `web_search` 兜底（手动） |

### 港股

| 场景                   | 主搜索                         | 辅/验证                                             |
| ---------------------- | ------------------------------ | --------------------------------------------------- |
| 港交所披露易/公告/回购 | `doubao --sites hkexnews.hk` | `tavily`                                          |
| 管理层讨论/分析师点评  | `tavily`                     | `doubao`                                          |
| 财报/研报深度检索      | `doubao --need-content`      | `anysearch`（通用搜索，**已验证港股覆盖**） |
| 双源验证               | `doubao` + `tavily`        | —                                                  |

### 美股

| 场景                           | 主搜索               | 辅/验证                   |
| ------------------------------ | -------------------- | ------------------------- |
| SEC filings/财报/MD&A 深度检索 | `exa --type deep`  | `tavily`                |
| 美股新闻/舆情/跨市场对比       | `doubao`           | `anysearch --zone intl` |
| 双源验证                       | `exa` + `doubao` | —                        |

### 通用规范（全市场适用）

1. 使用 `--time-range day/week/month` 限制时间范围，优先获取最新信息
2. 搜索结果必须包含数据来源日期；过时数据须标注时效性说明
3. 非境内上市公司关键信息须双源验证（港股：doubao+tavily；美股：exa+doubao）
4. 关键信息缺失时标注"信息不足"，不得用推测填充
5. 中概股双重上市（A+H / A+美股）用 `doubao` 跨市场综合检索，无需切换工具

### 实测验证结论

- **anysearch 港股覆盖**：通用搜索模式已实测通过（腾讯 00700 返回 5 条权威财经媒体结果含精确财务数据；港交所 00388 返回 3 条含精确业绩数据）
- **anysearch 美股覆盖**：`--zone intl --language en` 已实测通过（NVDA 返回 $130.5B revenue, $2.94 EPS）
- **anysearch 垂直库警告**：`--tag finance` 垂直库需额外参数（symbol/type/cn_code）
- **exa SEC filings**：搜索 "AAPL 10-K" 直接命中 SEC.gov 原文（aapl-20240928.htm）+ Apple IR + EDGAR，5 条结果全部高质量
- **doubao**：实测正常

> 美股/海外检索使用英文关键词（`10-K`、`earnings call`、`guidance`）命中率更高；anysearch 检索海外建议加 `--zone intl --language en`。

---

## 三、选型决策流程图

```
开始
  │
  ├─ 哪个市场？
  │   ├─ A股 ↓
  │   │   ├─ 财报/研报/公告/判例/专利深查？ → anysearch --tag 主 + doubao --finance 辅
  │   │   ├─ 实时新闻/舆情/热点？ → doubao --finance 主 + anysearch 辅
  │   │   └─ 精确数值核验？ → financial_rigor.py（专用工具，不属搜索）
  │   ├─ 港股 ↓
  │   │   ├─ 披露易/公告/回购？ → doubao --sites hkexnews.hk 主 + tavily 辅
  │   │   ├─ 管理层讨论/分析师点评？ → tavily 主 + doubao 辅
  │   │   └─ 财报/研报深度检索？ → doubao --need-content 主 + anysearch 辅
  │   └─ 美股 ↓
  │       ├─ SEC filings/财报/MD&A？ → exa --type deep 主 + tavily 辅
  │       ├─ 新闻/舆情/跨市场？ → doubao 主 + anysearch --zone intl 辅
  │       └─ 双源验证 → exa + doubao
  │
  └─ 通用规范：--time-range 限时效 / 结果标注来源日期 / 双源验证 / 信息不足禁止推测
```

完整选型决策表与实战推荐参见 [A股工具使用指南.md 搜索工具选型对比章节](../../../docs/A股工具使用指南.md#十三搜索工具选型对比)。

---

## 四、命令速查

### AnySearch（A股投研首选）

```bash
# 基本搜索
python tools/common/anysearch.py "紫金矿业 财报"

# 垂直领域定向搜索（tag）
python tools/common/anysearch.py "A股 半年报 业绩" --tag finance
python tools/common/anysearch.py "民法典 民间借贷 利率" --tag legal
python tools/common/anysearch.py "carbon capture" --tag paper --zone intl

# 国际区域（美股/海外检索）
python tools/common/anysearch.py "NVDA earnings" --zone intl --language en

# 指定返回条数 + JSON 输出
python tools/common/anysearch.py "黄金价格走势 2026" --count 10 --json

# 导出 Markdown 报告
python tools/common/anysearch.py "紫金矿业" --export
```

**依赖**：`pip install requests python-dotenv`
**配置**：在 `.env` 中配置 `ANYSEARCH_API_KEY`（申请：https://anysearch.com/console/api-keys，免费每日 1000 次）

### 豆包搜索（实时资讯/舆情首选）

```bash
# 基本搜索
python tools/common/doubao_search.py "紫金矿业 财报"

# 财经定向搜索（金融行业 + 仅非常权威信源）
python tools/common/doubao_search.py "紫金矿业 半年报" --finance

# 抓取正文做大模型拆解 + 导出 Markdown 报告
python tools/common/doubao_search.py "腾讯控股 2025年报" --need-content --export

# 站点过滤（港交所披露易 / SEC EDGAR）
python tools/common/doubao_search.py "腾讯 回购" --sites hkexnews.hk
python tools/common/doubao_search.py "AAPL 10-K" --sites sec.gov

# 时间范围（day/week/month/year）
python tools/common/doubao_search.py "美联储 加息" --time-range week

# 指定返回条数 + JSON 输出
python tools/common/doubao_search.py "{关键词}" --count 10 --json
```

**依赖**：`pip install volcengine python-dotenv requests`
**配置**：在 `.env` 中配置

```
VOLC_AK=你的AccessKeyID
VOLC_SK=你的SecretAccessKey
VOLC_QPS=5  # 可选
```

### Exa（美股深度研究首选）

```bash
# 基本搜索
python tools/common/exa_search.py "AAPL 10-K 2025"

# 深度调研（deep 档，耗时 4-40 秒，直接命中 SEC.gov 原文）
python tools/common/exa_search.py "AAPL 10-K" --type deep

# 指定结果数量
python tools/common/exa_search.py "NVDA earnings call" --max-results 8

# Token 节约模式（highlights 高亮摘要，只返回相关段落）
python tools/common/exa_search.py "AI semiconductor industry" --highlights --json

# 返回 title、url、published_date、content 四个字段
```

**依赖**：`pip install requests python-dotenv`
**配置**：在 `.env` 中配置 `EXA_API_KEY`（申请：https://dashboard.exa.ai/api-keys，免费层 1000 次/月）

### Tavily（港美股深度内容辅源）

```bash
# 基本搜索
python tools/common/tavily_search.py "腾讯 2025Q4 管理层讨论" --max-results 10

# JSON 格式输出
python tools/common/tavily_search.py "紫金矿业 ROE" --json

# 返回 title、url、content 三个字段
# 支持高级搜索（search_depth="advanced"）
```

**依赖**：`pip install mcp python-dotenv`
**配置**：在 `.env` 中配置 `DASHSCOPE_API_KEY`

### WebSearch（仅阿里云生态/轻量验证兜底）

```bash
python tools/common/web_search.py "腾讯控股 股价"
# 返回 title、link、snippet、hostname
```

**依赖**：`pip install mcp python-dotenv`
**配置**：在 `.env` 中配置 `DASHSCOPE_API_KEY`

---

## 五、重要内容多源验证（推荐）

对于重要分析（如财报研究、行业格局分析），建议**同时调用 2~3 个工具**，互为补充。

### A股双主验证

```bash
# anysearch 垂直检索（财报/研报）+ doubao 财经定向（权威信源 + 正文）
python tools/common/anysearch.py "紫金矿业 财报" --tag finance
python tools/common/doubao_search.py "紫金矿业 2025年报" --finance --need-content --export
```

### 港股双源验证（doubao + tavily）

```bash
# 优先豆包搜索（披露易定向 + 正文 + 权威度筛选）
python tools/common/doubao_search.py "腾讯控股 2025Q4 财报" --finance --sites hkexnews.hk --need-content --export

# 补充 Tavily（管理层讨论深度内容）
python tools/common/tavily_search.py "腾讯 2025Q4 管理层讨论"

# 如需财务数据交叉验证，补充 AnySearch 通用搜索
python tools/common/anysearch.py "腾讯控股 财报"
```

### 美股双源验证（exa + doubao）

```bash
# 优先 Exa（SEC filings 深度检索，直接命中原文）
python tools/common/exa_search.py "AAPL 10-K 2025" --type deep --max-results 10

# 补充 Doubao（新闻/舆情/分析师点评 + 跨市场视角）
python tools/common/doubao_search.py "AAPL Q3 2026 earnings analyst reactions" --finance --need-content

# 如需 MD&A 深度内容，补充 Tavily
python tools/common/tavily_search.py "AAPL management discussion Q3 2026"
```

### 各工具角色定位说明

- `anysearch.py`：A股投研首选，垂直数据库定向 + 每日 1000 次免费，适合财报/研报/判例/专利检索
- `doubao_search.py`：实时资讯/舆情首选，权威信源 + 正文能力 + 跨市场综合检索
- `exa_search.py`：美股深度研究首选，SEC filings 直接命中原文，适合研究型长文与专业领域查询
- `tavily_search.py`：港美股深度内容辅源，适合管理层讨论、分析师点评（中文弱、国内网络不稳，不作主源）
- `web_search.py`：仅阿里云生态/轻量验证兜底，移出默认组合

---

## 六、模块导入接口

### AnySearch

```python
from tools.common.anysearch import anysearch

# 基本调用
results = anysearch("黄金价格", max_results=5)

# 垂直领域定向搜索
results = anysearch("紫金矿业 财报", tag="finance", max_results=5)

for item in results:
    print(f"标题: {item['title']}")
    print(f"链接: {item['url']}")
    print(f"摘要: {item['snippet'][:100]}")
```

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

### Exa

```python
from tools.common.exa_search import exa_search

results = exa_search("黄金价格走势", max_results=3, search_type="fast")
for item in results:
    print(f"标题: {item['title']}")
    print(f"链接: {item['url']}")
    print(f"发布时间: {item['published_date']}")
```

### Tavily

```python
import asyncio
from tools.common.tavily_search import tavily_search

async def main():
    results = await tavily_search("黄金价格走势", max_results=5)
    for r in results:
        print(f"标题: {r['title']}")
        print(f"链接: {r['url']}")
        print(f"内容: {r['content'][:100]}")

asyncio.run(main())
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

## 七、配套测试

各工具均配套测试软件：

- `anysearch.py` 测试：`python tests/common/test_anysearch.py [--skip-live]`
- `doubao_search.py` 测试：`python tests/common/test_doubao_search.py [--skip-live]`
- `tavily_search.py` 测试：`python tests/common/test_tavily_search.py`
- `exa_search.py` 测试：`python tests/common/test_exa_search.py [--test unit|all]`
- `web_search.py` 测试：`python tests/common/test_web_search.py`

`--skip-live` 参数可跳过需要真实凭证的在线测试，适合在 CI/CD 等无凭证环境运行。

---

## 八、相关技能

- [A股数据获取](./a-share-data.md)
- [港股数据获取](./hk-share-data.md)
- [公共工具索引](./common-tools-guide.md)
- [完整选型决策流程](../../../docs/A股工具使用指南.md#十三搜索工具选型对比)

---

## 版本信息

- **版本**：3.0.0（五工具全量重写，新增 AnySearch 为 A股投研首选，Exa 升为美股深度研究首选，Tavily 定位为港美股深度内容辅源，WebSearch 降级为仅兜底）
- **创建日期**：2026-07-31
- **最后更新**：2026-08-10
- **维护状态**：活跃维护
- **策略依据**：[搜索服务选择策略重构方案 v2.0](../../../docs/搜索服务选择策略重构方案.md)
