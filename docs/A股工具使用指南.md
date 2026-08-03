# A股数据工具使用指南

本文档介绍如何使用独立的A股数据工具获取A股市场数据。

> **重构说明**：A股数据工具已重构到 `tools/a_share/` 目录下，辅助工具（精确金融计算、报告审核）重构到 `tools/common/` 目录下。请按本文档中的最新路径调用工具。

---

## 工具列表

### 核心数据工具

| 工具文件 | 功能 | 命令示例 |
|---------|------|---------|
| `stock_info.py` | A股信息查询 | `python tools/a_share/stock_info.py --search 新易盛` |
| `stock_quote.py` | A股行情数据 | `python tools/a_share/stock_quote.py --code 300502` |
| `stock_financial.py` | A股财务指标 | `python tools/a_share/stock_financial.py --code 300502` |
| `stock_screen.py` | 质量筛选7条指标 | `python tools/a_share/stock_screen.py --code 300502` |
| `stock_equity.py` | 股权结构与财报下载 | `python tools/a_share/stock_equity.py --code 601899` |

### 辅助计算工具

| 工具文件 | 功能 | 命令示例 |
|---------|------|---------|
| `financial_rigor.py` | 精确金融计算（PE、ROE、市值校验） | `python tools/common/financial_rigor.py verify-valuation --help` |
| `report_audit.py` | 研究报告审核 | `python tools/common/report_audit.py --help` |

### 大宗商品数据工具

| 工具文件 | 功能 | 命令示例 |
|---------|------|---------|
| `commodity_price.py` | 大宗商品价格数据获取（Akshare 优先，yfinance 回退） | `python tools/common/commodity_price.py --code cu,GC,CL` |

### 网络搜索工具

| 工具文件 | 功能 | 命令示例 |
|---------|------|---------|
| `doubao_search.py` | 豆包搜索（火山引擎 SearchInfinity，AK/SK 鉴权） | `python tools/common/doubao_search.py "紫金矿业 财报"` |
| `web_search.py` | 阿里云百炼 WebSearch MCP（替代被地域封锁的 Anthropic WebSearch） | `python tools/common/web_search.py "腾讯控股 股价"` |
| `tavily_search.py` | Tavily 搜索（阿里云百炼 MCP，返回 title/url/content） | `python tools/common/tavily_search.py "紫金矿业 2025年报"` |

---

## 一、stock_info.py - A股信息查询

### 功能说明

获取A股上市公司的代码、名称、上市信息等基本信息。

### 使用方法

#### 1. 列出全部A股

```bash
python tools/a_share/stock_info.py --list
```

**输出示例**:
```json
{
  "success": true,
  "data": [
    {"code": "000001", "name": "平安银行"},
    {"code": "000002", "name": "万科A"},
    ...
  ],
  "meta": {
    "tool": "stock_info",
    "command": "list",
    "market": "a",
    "count": 5462,
    "timestamp": "2026-07-13T23:00:00"
  }
}
```

#### 2. 搜索A股

```bash
python tools/a_share/stock_info.py --search 新易盛
```

**输出示例**:
```json
{
  "success": true,
  "data": [
    {
      "code": "300502",
      "name": "新易盛",
      "market": "a",
      "price": 85.20,
      "change_pct": 3.25,
      "volume": 12345678,
      ...
    }
  ],
  "meta": {
    "tool": "stock_info",
    "command": "search",
    "keyword": "新易盛",
    "count": 1
  }
}
```

#### 3. 查询单只A股

```bash
python tools/a_share/stock_info.py --code 300502
```

**输出字段说明**:
- `code`: A股代码（6位数字）
- `name`: 公司名称
- `market`: 市场标识（"a"）
- `price`: 最新价
- `change_pct`: 涨跌幅（%）
- `change`: 涨跌额
- `volume`: 成交量
- `amount`: 成交额
- `high`: 最高价
- `low`: 最低价
- `open`: 今开
- `pre_close`: 昨收

#### 4. 按行业筛选

```bash
python tools/a_share/stock_info.py --industry 光模块
```

**说明**: 仅支持A股行业筛选，港股暂不支持。

---

## 二、stock_quote.py - A股行情数据

### 功能说明

获取A股历史K线数据，支持日/周/月线、前/后复权、多数据源。

### 使用方法

#### 1. 获取最近30天数据

```bash
python tools/a_share/stock_quote.py --code 300502
```

#### 2. 指定日期范围

```bash
python tools/a_share/stock_quote.py --code 300502 --start 20260101 --end 20260710
```

#### 3. 选择复权方式

```bash
# 未复权（默认）
python tools/a_share/stock_quote.py --code 300502 --adjust ""

# 前复权
python tools/a_share/stock_quote.py --code 300502 --adjust qfq

# 后复权
python tools/a_share/stock_quote.py --code 300502 --adjust hfq
```

#### 4. 选择数据源

```bash
# 东方财富（默认）
python tools/a_share/stock_quote.py --code 300502 --source eastmoney

# 新浪（国内可达）
python tools/a_share/stock_quote.py --code 300502 --source sina
```

**输出示例**:
```json
{
  "success": true,
  "data": {
    "code": "300502",
    "start_date": "20260613",
    "end_date": "20260713",
    "adjust": "",
    "source": "eastmoney",
    "count": 22,
    "data": [
      {
        "date": "20260713",
        "open": 83.0,
        "high": 87.5,
        "low": 82.0,
        "close": 85.2,
        "volume": 12345678,
        "amount": 1040000000,
        "change_pct": 3.25,
        "change": 2.68,
        "turnover": 2.15
      },
      ...
    ]
  },
  "meta": {
    "tool": "stock_quote",
    "command": "code",
    "code": "300502",
    "market": "a"
  }
}
```

---

## 三、stock_financial.py - A股财务指标

### 功能说明

获取A股上市公司的财务指标数据，包括ROE、毛利率、净利率等关键指标。

### 使用方法

#### 1. 获取关键财务指标

```bash
python tools/a_share/stock_financial.py --code 300502
```

**返回的关键指标**:
- ROE（净资产收益率）
- 毛利率
- 净利率
- 经营现金流
- 净利润
- 资产负债率
- 基本每股收益
- 每股经营现金流
- 每股净资产
- 期间费用率

#### 2. 查询单个指标

```bash
python tools/a_share/stock_financial.py --code 300502 --indicator ROE
```

#### 3. 查询多个指标

```bash
python tools/a_share/stock_financial.py --code 300502 --indicator 毛利率,净利率
```

#### 4. 查询全部原始指标

```bash
python tools/a_share/stock_financial.py --code 300502 --indicator all
```

**输出示例**:
```json
{
  "success": true,
  "data": {
    "code": "300502",
    "name": "新易盛",
    "indicator": "ROE",
    "data": {
      "2025": 24.5,
      "2024": 22.3,
      "2023": 20.1,
      ...
    }
  },
  "meta": {
    "tool": "stock_financial",
    "command": "indicator",
    "code": "300502",
    "market": "a"
  }
}
```

---

## 四、stock_screen.py - 质量筛选工具

### 功能说明

对A股上市公司执行7条去劣指标筛选，快速排除不符合一流公司标准的标的。

### 使用方法

#### 1. 单只股票筛选

```bash
python tools/a_share/stock_screen.py --code 300502
```

#### 2. 多只股票筛选

```bash
python tools/a_share/stock_screen.py --code 300502,600519,000858
```

### 7条去劣指标

| # | 指标 | 排除条件 | 衡量的是什么 |
|---|------|---------|-------------|
| 1 | 10年平均ROE | < 8% | 资本效率 |
| 2 | 5年累计自由现金流 | 为负 | 利润质量 |
| 3 | 利息覆盖倍数 | < 2倍 | 偿债安全 |
| 4 | 长期毛利率 | < 15% | 定价权 |
| 5 | 经营现金流/净利润 | < 0.7 | 利润质量 |
| 6 | 长期净利率 | < 5% | 抗风险能力 |
| 7 | 5年总股本膨胀 | > 20% | 股东利益 |

**输出示例**:
```json
{
  "success": true,
  "data": {
    "code": "300502",
    "name": "新易盛",
    "result": {
      "roe_avg": {"value": 24.0, "pass": true},
      "fcf_cumulative": {"value": "正", "pass": true},
      "interest_coverage": {"value": 45.2, "pass": true},
      "gross_margin_avg": {"value": 34.5, "pass": true},
      "ocf_to_ni_avg": {"value": 1.15, "pass": true},
      "net_margin_avg": {"value": 18.2, "pass": true},
      "share_dilution": {"value": -5.3, "pass": true},
      "overall": "通过"
    }
  },
  "meta": {
    "tool": "stock_screen",
    "command": "screen",
    "code": "300502",
    "market": "a"
  }
}
```

---

## 五、stock_equity.py - 股权结构与财报下载

### 功能说明

获取A股上市公司的股权结构信息，并支持从巨潮资讯网下载最新财报PDF（年报、半年报、季报）。

### 使用方法

#### 1. 获取股权结构数据

```bash
python tools/a_share/stock_equity.py --code 601899
```

**返回的数据**:
- 前十大股东（总股本口径）
- 前十大流通股东（流通股本口径）
- 股本结构历史变动
- 公司基础信息

#### 2. 导出为Excel文件

```bash
python tools/a_share/stock_equity.py --code 601899 --export
```

#### 3. JSON格式输出

```bash
python tools/a_share/stock_equity.py --code 601899 --json
```

#### 4. 下载最新年报PDF

```bash
python tools/a_share/stock_equity.py --code 601899 --download-report
```

#### 5. 下载最新半年报PDF

```bash
python tools/a_share/stock_equity.py --code 601899 --download-report --report-type semiannual
```

#### 6. 下载最新季报PDF

```bash
python tools/a_share/stock_equity.py --code 601899 --download-report --report-type quarterly
```

#### 7. 指定财报保存目录

```bash
python tools/a_share/stock_equity.py --code 601899 --download-report --report-dir ./reports
```

### 输出示例

**股权结构数据**:
```json
{
  "success": true,
  "data": {
    "code": "601899",
    "exchange": "沪",
    "report_date": "20251231",
    "top10_holders": {
      "success": true,
      "count": 10,
      "data": [
        {
          "股东名称": "闽西兴杭国有资产投资经营有限公司",
          "持股数量": "1743551234",
          "占总股本持股比例": "22.88"
        },
        ...
      ]
    },
    "top10_free_holders": {...},
    "share_structure": {...},
    "company_info": {...}
  }
}
```

**财报下载结果**:
```
✅ 年报下载成功：./cninfo_reports\601899_2025年报.pdf
   文件大小：78123.45 KB
```

### 文件命名规则

| 报告类型 | 文件名格式 | 示例 |
|---------|-----------|------|
| 年报 | `{股票代码}_{年份}年报.pdf` | `601899_2025年报.pdf` |
| 半年报 | `{股票代码}_{年份}半年报.pdf` | `601899_2026半年报.pdf` |
| 季报 | `{股票代码}_{年份}{季度}季报.pdf` | `601899_2026Q1季报.pdf` |

### 数据来源

- **股权结构数据**: 东方财富、巨潮资讯（通过akshare接口）
- **财报PDF**: 巨潮资讯网

### 注意事项

1. **数据延迟**: 免费接口数据可能有数分钟延迟
2. **文件大小**: 年报通常较大（1-80MB），半年报和季报较小（100-500KB）
3. **下载延迟**: 为避免频繁请求，下载后会自动延迟1.2秒
4. **报告可得性**: 部分公司可能未发布半年报，这是正常现象

---

## 六、financial_rigor.py - 精确金融计算

### 功能说明

提供精确的金融计算功能，包括PE、ROE、市值校验、三情景估值等。所有计算结果经过精确算术验证，避免LLM心算错误。

### 使用方法

#### 1. 验证估值数据

```bash
python tools/common/financial_rigor.py verify-valuation \
  --price 420.5 \
  --eps 23.36 \
  --bvps 105.3 \
  --fcf-per-share 15.6
```

#### 2. 验证市值计算

```bash
python tools/common/financial_rigor.py verify-market-cap \
  --price 420.5 \
  --shares 95.2 \
  --reported 40000 \
  --currency HKD
```

#### 3. 数据交叉验证

```bash
python tools/common/financial_rigor.py cross-validate \
  --field ROE \
  --values '{"东方财富": 25.06, "新浪": 24.8}' \
  --unit '%'
```

#### 4. 三情景估值

```bash
python tools/common/financial_rigor.py three-scenario \
  --price 420.5 \
  --eps 23.36 \
  --shares 95.2 \
  --growth 15 10 5 \
  --pe 25 20 15
```

#### 5. 精确计算

```bash
python tools/common/financial_rigor.py calc --expr "420.5 / 23.36"
```

### 应用场景

- 估值数据验证
- 市值计算校验
- 多数据源交叉验证
- 三情景估值分析
- 精确算术计算

---

## 七、report_audit.py - 研究报告审核

### 功能说明

对研究报告进行数据审核，检查数据准确性、来源标注、估值计算等。

### 使用方法

#### 1. 审核报告文件

```bash
python tools/common/report_audit.py --file reports/腾讯-20260722.md
```

#### 2. 指定采样数量

```bash
python tools/common/report_audit.py --file reports/腾讯-20260722.md --sample 10
```

### 审核内容

1. **数据准确性**: 验证财务数据的准确性
2. **来源标注**: 检查数据来源是否标注
3. **估值计算**: 验证估值数据的计算过程
4. **偏差分析**: 分析不同数据源之间的偏差

---

## 八、doubao_search.py - 豆包搜索

### 功能说明

通过火山引擎联网搜索 API（豆包搜索 SearchInfinity）实现网络信息搜索，返回结构化搜索结果。

**核心特性**:
- 使用火山引擎 TOP 网关 AK/SK 鉴权（SignatureV4 签名）
- 支持 Web 搜索、时间范围过滤、站点过滤、行业类型搜索
- 返回结构化数据：标题、链接、摘要、正文、权威度等
- 内置客户端 QPS 限流（默认 5 QPS，账号维度限流）
- 支持导出 Markdown 格式搜索报告

### 依赖与配置

**依赖库**:
```bash
pip install volcengine python-dotenv requests
```

**环境变量**（在项目根目录 `.env` 文件中配置）:
```
VOLC_AK=你的AccessKeyID
VOLC_SK=你的SecretAccessKey
VOLC_QPS=5  # 可选，QPS 限流
```

### 使用方法

#### 1. 基本搜索

```bash
python tools/common/doubao_search.py "紫金矿业 财报"
```

#### 2. 指定返回条数

```bash
python tools/common/doubao_search.py "黄金价格走势 2026" --count 10
```

#### 3. 时间范围过滤

```bash
# 可选: day / week / month / year
python tools/common/doubao_search.py "新规" --time-range month
```

#### 4. 站点过滤

```bash
# 仅搜索指定站点（多个用 | 分隔）
python tools/common/doubao_search.py "A股 半年报" --sites gov.cn|sse.com.cn
# 屏蔽指定站点
python tools/common/doubao_search.py "A股 分析" --block-hosts some-bad-site.com
```

#### 5. 财经定向搜索快捷选项

等同于 `--industry finance --auth-level 1`（金融行业 + 仅非常权威信源）:

```bash
python tools/common/doubao_search.py "紫金矿业 半年报" --finance
```

#### 6. 行业类型搜索

```bash
# 可选: finance / game / gov
python tools/common/doubao_search.py "新规" --industry gov
```

#### 7. 仅返回有正文的结果

```bash
python tools/common/doubao_search.py "腾讯控股 年报" --need-content
```

#### 8. 正文格式选择

```bash
# 可选: text / markdown（默认 markdown）
python tools/common/doubao_search.py "腾讯控股 年报" --content-format text
```

#### 9. JSON 格式输出

```bash
python tools/common/doubao_search.py "腾讯控股" --json
```

#### 10. 导出 Markdown 报告

```bash
# 导出到 reports/ 目录（默认命名规则）
python tools/common/doubao_search.py "A股 半年报" --finance --export
# 自定义导出路径
python tools/common/doubao_search.py "紫金矿业" --export --export-path reports/my_report.md
```

#### 11. 命令行覆盖凭证

```bash
python tools/common/doubao_search.py "紫金矿业" --ak AKLTY... --sk TW1N...
```

### 模块导入接口

```python
from tools.common.doubao_search import doubao_search

# 基本调用
results = doubao_search("黄金价格", count=5)

# 财经定向搜索
results = doubao_search(
    "紫金矿业 财报",
    count=10,
    industry="finance",
    auth_info_level=1,
    time_range="month",
    need_content=True,
)

for r in results:
    print(f"标题: {r['title']}")
    print(f"链接: {r['url']}")
    print(f"来源: {r['site_name']}")
    print(f"权威度: {r['auth_des']}（等级 {r['auth_level']}）")
    print(f"摘要: {r['summary'][:100]}...")
```

### 返回字段说明

每条搜索结果包含以下字段:

| 字段 | 类型 | 说明 |
|------|------|------|
| `title` | str | 标题 |
| `url` | str | 链接 |
| `site_name` | str | 来源站点名 |
| `publish_time` | str | 发布时间（ISO 8601） |
| `summary` | str | 摘要（500~1000 字，适合大模型场景） |
| `snippet` | str | 简短片段 |
| `content` | str | 正文内容（需 `need_content=True`） |
| `auth_level` | int | 权威度等级（1=非常权威, 2=正常权威, 3=一般权威, 4=一般不权威） |
| `auth_des` | str | 权威度中文描述 |
| `rank_score` | float | 相关性评分 |

### 注意事项

1. **AK/SK 申请**: 需在火山引擎控制台开通联网搜索服务并创建 IAM 访问密钥
2. **QPS 限流**: 账号维度默认 5 QPS，需扩容可提工单；客户端已内置限流
3. **关键词长度**: 1~100 字符，过长会自动截断
4. **结果条数**: 1~50 条，默认 10 条
5. **正文获取**: 默认不返回正文，需 `--need-content` 开启

---

## 九、web_search.py - 阿里云百炼 WebSearch

### 功能说明

通过阿里云百炼 WebSearch MCP 服务实现网络信息搜索，替代被地域封锁的 Anthropic WebSearch 服务。

**核心特性**:
- 使用 MCP 协议连接阿里云百炼 WebSearch 服务
- 通过 SSE 协议流式获取结果
- 返回标准化字段：title、link、snippet
- 与阿里云通义千问生态深度集成

### 依赖与配置

**依赖库**:
```bash
pip install mcp python-dotenv
```

**环境变量**（在项目根目录 `.env` 文件中配置）:
```
DASHSCOPE_API_KEY=your_api_key_here
WebSearch_MCP_BASE_URL=https://dashscope.aliyuncs.com/api/v1/mcps/WebSearch/sse  # 可选
```

### 使用方法

#### 1. 基本搜索

```bash
python tools/common/web_search.py "腾讯控股 股价"
```

#### 2. 指定结果数量

```bash
python tools/common/web_search.py "中际旭创 ROE" --num 10
```

#### 3. JSON 格式输出

```bash
python tools/common/web_search.py "贵州茅台 年报 2024" --json
```

#### 4. 命令行覆盖 API Key

```bash
python tools/common/web_search.py "腾讯控股" --api-key sk-your-api-key
```

### 模块导入接口

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
    for item in result["results"]:
        print(f"标题: {item['title']}")
        print(f"链接: {item['link']}")

asyncio.run(main())
```

### 注意事项

1. **API Key 申请**: 需在阿里云百炼控制台开通 WebSearch MCP 服务
2. **异步调用**: 使用 MCP 协议（SSE），需在异步环境中运行
3. **Windows 兼容**: 已自动设置 `WindowsSelectorEventLoopPolicy`
4. **字段简化**: 仅返回 title、link、snippet、hostname 四个字段

---

## 十、搜索工具选型对比

### 选型决策表

下表综合"海内外财经检索选型结论"，明确 `doubao_search.py` 与 `web_search.py` 的优先选用场合:

| 维度 | `doubao_search.py`（火山引擎豆包搜索） | `web_search.py`（阿里云百炼 WebSearch） |
|------|--------------------------------|--------------------------------|
| **鉴权方式** | AK/SK（SignatureV4 签名） | Bearer Token（DASHSCOPE_API_KEY） |
| **接入协议** | HTTP REST + 签名 | MCP（SSE 流式） |
| **返回字段丰富度** | 高（10+ 字段，含权威度、相关性、摘要、正文） | 中（4 字段：title/link/snippet/hostname） |
| **正文能力** | 支持（`--need-content` + markdown/text 格式） | 不支持 |
| **行业定向** | 支持（finance/game/gov） | 不支持 |
| **权威度筛选** | 支持（仅非常权威信源） | 不支持 |
| **站点过滤** | 支持（`--sites` / `--block-hosts`） | 不支持 |
| **限流机制** | 客户端 QPS 限流（线程安全） | 无（依赖服务端） |
| **Markdown 报告导出** | 内置（`--export`） | 不支持 |
| **模型生态绑定** | 中立无绑定（适配通义千问/Claude/本地 LLM 等多模型架构） | 与阿里云通义千问生态深度绑定 |
| **免费额度** | 每月 500 次免费（个人/小团队高频资讯监控） | 按阿里云百炼计费策略 |

### 优先选择 `doubao_search.py` 的场景

1. **跨市场综合检索**: 同时检索 A 股 / 港股 / 美股 / 中概股、海外央行政策、境外投行研报、SEC 公告
2. **投研报告自动化**: 需要抓取公告、研报全文做大模型二次拆解、自动生成投研报告（依赖 `--need-content` 正文能力 + `--export` 报告导出）
3. **多模型混合架构**: 接入多模型（通义千问、本地开源 LLM、Claude 等），要求检索底座中立无绑定
4. **权威信源筛选**: 财经定向搜索场景需 `--finance` 快捷选项（金融行业 + 仅非常权威信源）
5. **个人/小团队高频监控**: 利用每月 500 次免费额度进行高频资讯监控
6. **行业垂直搜索**: 需要 `--industry finance/game/gov` 进行行业类型搜索
7. **站点白名单/黑名单**: 需要限定搜索站点范围或屏蔽特定站点

### 仅选择 `web_search.py` 的场景

1. **阿里云全栈部署**: 企业全栈部署在阿里云，主力模型仅使用通义千问
2. **A股量化基本面**: 仅做 A 股量化基本面分析，依赖百炼金融专项 MCP 插件获取行情、持仓数据
3. **持牌金融机构合规需求**: 持牌金融机构需要私有化部署、全链路审计、等保合规交付
4. **轻量级场景**: 仅需快速获取 title/link/snippet，不需要正文、权威度、报告导出等高级能力
5. **已有阿里云百炼生态**: 已开通 DASHSCOPE_API_KEY，希望复用现有凭证，避免额外开通火山引擎服务

### 选型决策流程图

```
开始
  │
  ├─ 是否需要跨市场检索（A/港/美/中概股）或海外信源？
  │   ├─ 是 → 优先 doubao_search.py
  │   └─ 否 ↓
  │
  ├─ 是否需要正文/权威度/行业定向/报告导出？
  │   ├─ 是 → 优先 doubao_search.py
  │   └─ 否 ↓
  │
  ├─ 是否已全栈部署阿里云 + 仅用通义千问？
  │   ├─ 是 → 选择 web_search.py
  │   └─ 否 ↓
  │
  ├─ 是否需要等保合规/全链路审计（持牌金融机构）？
  │   ├─ 是 → 选择 web_search.py
  │   └─ 否 ↓
  │
  └─ 默认推荐 doubao_search.py（功能更丰富，中立无绑定）
```

### 实战推荐

| 使用场景 | 推荐工具 | 理由 |
|---------|---------|------|
| 海外投行研报检索 | `doubao_search.py` | 海外信源覆盖更广，正文能力强 |
| A股财报数据交叉验证 | `doubao_search.py --finance` | 权威度筛选 + 行业定向 |
| 美股 SEC 公告抓取 | `doubao_search.py --need-content` | 支持正文返回与 Markdown 导出 |
| 跨市场金融资讯监控 | `doubao_search.py` | 中立无绑定，适配多模型架构 |
| 通义千问 RAG 检索增强 | `web_search.py` | 与阿里云生态深度集成 |
| 阿里云全栈企业部署 | `web_search.py` | 复用 DASHSCOPE_API_KEY，统一计费 |
| 持牌金融机构合规交付 | `web_search.py` | 私有化部署 + 全链路审计 |
| 快速验证某个关键词 | 任一均可 | 视已配置凭证而定 |

### 配套测试

两个工具均配套测试软件:

- `doubao_search.py` 测试: `python tests/common/test_doubao_search.py [--skip-live]`
- `web_search.py` 测试: `python tests/common/test_web_search.py`

`--skip-live` 参数可跳过需要真实凭证的在线测试，适合在 CI/CD 等无凭证环境运行。

---

## 十一、commodity_price.py - 大宗商品价格数据

### 功能说明

获取大宗商品价格数据，支持 18 个品种（有色金属、贵金属、能源化工、新能源小金属四大类别）。采用 Akshare 优先、yfinance 回退的双数据源策略。

**支持品种**：
- **有色金属（6个）**：沪铜(cu)、沪铝(al)、沪锌(zn)、沪铅(pb)、沪镍(ni)、沪锡(sn)
- **贵金属（6个）**：沪金(au)、沪银(ag)、COMEX黄金(GC)、COMEX白银(SI)、铂金(PL)、钯金(PA)
- **能源化工（4个）**：上海原油(sc)、WTI原油(CL)、布伦特原油(BZ)、天然气(NG)
- **新能源小金属（2个）**：碳酸锂(lc)、工业硅(si)

**限流保护**：
- 单次获取最多返回 10 条记录
- 批量获取最多 10 个品种
- yfinance 请求间隔至少 2 秒
- 批量获取品种间间隔 1 秒

### 使用方法

#### 1. 列出所有支持品种

```bash
python tools/common/commodity_price.py --list
```

**输出示例**：
```json
{
  "success": true,
  "data": [
    {
      "category": "有色金属",
      "commodities": [
        {"code": "cu", "name": "沪铜", "currency": "CNY", "exchange": "SHFE"},
        ...
      ]
    },
    ...
  ],
  "meta": {"total_count": 18}
}
```

#### 2. 获取单个品种

```bash
python tools/common/commodity_price.py --code cu
```

**输出示例**：
```json
{
  "success": true,
  "data": {
    "code": "cu",
    "name": "沪铜",
    "source": "akshare",
    "records": [
      {
        "date": "2026-01-15",
        "open": 105000.0,
        "high": 105500.0,
        "low": 104800.0,
        "close": 105050.0,
        "volume": 123456
      },
      ...
    ],
    "record_count": 10
  }
}
```

#### 3. 批量获取多个品种

```bash
python tools/common/commodity_price.py --code cu,GC,CL
```

#### 4. 指定日期范围

```bash
python tools/common/commodity_price.py --code cu --start 2025-01-01 --end 2025-07-31
```

#### 5. 限制返回记录数

```bash
python tools/common/commodity_price.py --code cu --max-records 5
```

### 数据源策略

| 品种类型 | 主数据源 | 回退数据源 |
|---------|---------|-----------|
| 国内品种（上期所/广期所） | Akshare | 无（仅 Akshare 支持） |
| 外盘品种（COMEX/WTI/布伦特等） | Akshare | yfinance |
| 铂金/钯金 | 无（Akshare 无稳定接口） | yfinance |

### 注意事项

1. **限流保护**：单次获取最多 10 条记录，批量获取最多 10 个品种
2. **默认时间窗口**：14 天（约 10 个交易日）
3. **yfinance 代理**：在中国大陆使用 yfinance 可能需要配置代理
4. **数据延迟**：免费接口数据可能有数分钟延迟
5. **测试文件**：单元测试 `tests/common/test_commodity_price.py`，集成测试 `tests/common/test_commodity_price_integration.py`

---

## 十二、A股代码格式说明

A股代码统一使用**6位数字字符串**:

| 代码前缀 | 交易所 | 板块 |
|---------|--------|------|
| 60xxxx | 上海证券交易所 | 主板 |
| 00xxxx | 深圳证券交易所 | 主板（含原中小板002xxx） |
| 30xxxx | 深圳证券交易所 | 创业板 |
| 688xxx | 上海证券交易所 | 科创板 |

**示例**:
| 公司 | 代码 | 板块 |
|------|------|------|
| 中国平安 | 601318 | 上交所主板 |
| 万科A | 000002 | 深交所主板 |
| 新易盛 | 300502 | 深交所创业板 |
| 中芯国际 | 688981 | 上交所科创板 |

---

## 十三、数据源说明

### stock_info_a_code_name()

- 来源：东方财富
- 字段：代码、名称
- 特点：数据全面、覆盖全部A股
- 用途：`stock_info.py` 获取A股代码和名称

### stock_yjbb_em()

- 来源：东方财富
- 字段：代码、名称、价格、涨跌幅、成交量等
- 特点：数据实时、字段丰富
- 用途：`stock_info.py`, `stock_financial.py`, `stock_screen.py` 获取实时行情和业绩数据

### stock_zh_a_hist()

- 来源：东方财富
- 参数：代码、开始日期、结束日期、复权方式、周期
- 特点：支持自定义日期范围、多种复权方式
- 用途：`stock_quote.py` 获取A股历史K线数据（默认数据源）

### stock_zh_a_daily()

- 来源：新浪财经
- 参数：代码、复权方式
- 特点：网络连接稳定、历史数据长
- 用途：`stock_quote.py` 获取A股历史K线数据（备用数据源）

### stock_financial_abstract()

- 来源：东方财富
- 字段：ROE、毛利率、净利率、经营现金流等
- 特点：数据全面、覆盖近10年
- 用途：`stock_financial.py`, `stock_screen.py` 获取A股财务指标

### stock_financial_report_sina()

- 来源：新浪财经
- 字段：利润表、资产负债表、现金流量表
- 特点：数据详细、支持三大报表
- 用途：`stock_screen.py` 获取财务报表数据

### stock_ipo_info()

- 来源：东方财富
- 字段：上市日期、发行价、总股本等
- 特点：数据准确、覆盖全部A股
- 用途：`stock_screen.py` 获取上市信息

### stock_gdfx_top_10_em()

- 来源：东方财富
- 字段：股东名称、持股数量、持股比例等
- 特点：数据准确、覆盖全部A股、支持指定报告期
- 用途：`stock_equity.py` 获取前十大股东（总股本口径）

### stock_gdfx_free_top_10_em()

- 来源：东方财富
- 字段：股东名称、持股数量、持股比例等
- 特点：数据准确、覆盖全部A股、支持指定报告期
- 用途：`stock_equity.py` 获取前十大流通股东（流通股本口径）

### stock_share_change_cninfo()

- 来源：巨潮资讯
- 字段：变动日期、变动原因、总股本、流通股本等
- 特点：数据权威、覆盖历史变动记录
- 用途：`stock_equity.py` 获取股本结构历史变动

### stock_profile_cninfo()

- 来源：巨潮资讯
- 字段：公司名称、英文名称、行业、主营业务等
- 特点：数据权威、信息全面
- 用途：`stock_equity.py` 获取公司基础信息

### 巨潮资讯网API

- 来源：巨潮资讯网
- 接口：全文搜索API
- 字段：公告标题、PDF链接、公告日期等
- 特点：数据权威、支持搜索、免费使用
- 用途：`stock_equity.py` 查询和下载财报PDF（年报、半年报、季报）
- API端点：`https://www.cninfo.com.cn/new/fulltextSearch/full`

### 数据源对比总结

| 数据源 | 主要特点 | 适用场景 | 使用工具 |
|--------|---------|---------|---------|
| 东方财富 | 数据实时、字段丰富、覆盖全面 | 实时行情、财务数据、股权结构 | stock_info.py, stock_quote.py, stock_financial.py, stock_screen.py, stock_equity.py |
| 新浪财经 | 网络稳定、历史数据长 | 历史行情、财务报表 | stock_quote.py, stock_screen.py |
| 巨潮资讯 | 数据权威、官方来源 | 股本变动、公司信息、财报PDF | stock_equity.py |

---

## 十四、注意事项

### 1. 代码格式

A股代码必须为6位数字字符串，如 `300502`，不要添加 `.SH` 或 `.SZ` 后缀。

### 2. 数据延迟

免费接口数据可能有数分钟延迟，不适合高频交易。

### 3. 访问限制

高频请求可能触发风控，建议增加延时、分批请求。

### 4. 字段差异

不同接口的字段名可能不同（中文/英文），工具已做适配。

### 5. 数据源选择

**东方财富接口**:
- 优点：数据实时、字段丰富、支持自定义日期范围
- 缺点：高峰时段可能响应较慢

**新浪接口**:
- 优点：网络连接稳定、历史数据长
- 缺点：字段较少、不支持自定义日期范围

**建议**:
- 实时数据：优先使用东方财富接口
- 历史数据：可使用新浪接口（`--source sina`）
- 高峰时段：建议使用新浪接口避免超时

---

## 十五、与港股/美股工具的区别

| 特性 | A股工具 | 港股工具 | 美股工具 |
|------|---------|---------|---------|
| 代码长度 | 6位 | 5位 | 标准格式（如AAPL） |
| 市场标识 | "a" | "hk" | "us" |
| 行业筛选 | 支持 | 暂不支持 | 暂不支持 |
| 财务指标 | 支持 | 支持 | 支持（yfinance） |
| 质量筛选 | 支持 | 支持 | 暂不支持 |
| 股权结构 | 支持 | 暂不支持 | 暂不支持 |
| 财报下载 | 支持 | 暂不支持 | 暂不支持 |
| 数据源 | 东方财富、新浪、巨潮 | 东方财富、新浪 | Yahoo Finance |

---

## 十六、Python路径

```bash
F:\Anaconda3\envs\Python_3_12_3\python.exe
```

---

## 十六、常见使用场景

### 场景1: 快速查询公司信息

```bash
# 搜索公司
python tools/a_share/stock_info.py --search 新易盛

# 查询单只股票
python tools/a_share/stock_info.py --code 300502
```

### 场景2: 获取历史行情

```bash
# 最近30天行情
python tools/a_share/stock_quote.py --code 300502

# 指定日期范围（前复权）
python tools/a_share/stock_quote.py --code 300502 --start 20250101 --end 20260710 --adjust qfq
```

### 场景3: 查询财务指标

```bash
# 全部关键指标
python tools/a_share/stock_financial.py --code 300502

# 单个指标
python tools/a_share/stock_financial.py --code 300502 --indicator ROE
```

### 场景4: 执行质量筛选

```bash
# 单只股票筛选
python tools/a_share/stock_screen.py --code 300502

# 多只股票对比筛选
python tools/a_share/stock_screen.py --code 300502,600519,000858
```

### 场景5: 获取股权结构数据

```bash
# 获取股权结构数据
python tools/a_share/stock_equity.py --code 601899

# 导出为Excel文件
python tools/a_share/stock_equity.py --code 601899 --export
```

### 场景6: 下载财报PDF

```bash
# 下载最新年报
python tools/a_share/stock_equity.py --code 601899 --download-report

# 下载最新半年报
python tools/a_share/stock_equity.py --code 601899 --download-report --report-type semiannual

# 下载最新季报
python tools/a_share/stock_equity.py --code 601899 --download-report --report-type quarterly
```

### 场景7: 获取大宗商品价格

```bash
# 列出所有支持的大宗商品品种
python tools/common/commodity_price.py --list

# 获取沪铜价格（默认最近14天，最多10条）
python tools/common/commodity_price.py --code cu

# 批量获取多个品种
python tools/common/commodity_price.py --code cu,GC,CL

# 指定日期范围
python tools/common/commodity_price.py --code cu --start 2025-01-01 --end 2025-07-31

# 限制返回记录数
python tools/common/commodity_price.py --code cu --max-records 5
```

---

## 十七、局限性说明

1. **数据窗口**：部分公司上市时间较短，财务数据可能不足10年
2. **周期性行业**：周期性行业需用完整周期平均值判断，避免单一年份误导
3. **数据准确性**：免费接口数据可能存在延迟或误差，重要决策需交叉验证
4. **财务报表**：部分公司财务报表数据可能缺失特定字段

---

**文档版本**: v2.1
**更新日期**: 2026-08-01
**变更记录**:
- v2.1 (2026-08-01): 新增 doubao_search.py、web_search.py 工具说明章节与搜索工具选型对比
- v2.0 (2026-07-29): 工具重构到 tools/a_share/ 和 tools/common/ 目录，更新所有路径引用
