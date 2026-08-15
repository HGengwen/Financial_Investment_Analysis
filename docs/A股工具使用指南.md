# A股数据工具使用指南

本文档介绍如何使用独立的A股数据工具获取A股市场数据。

> **重构说明**：A股数据工具已重构到 `tools/a_share/` 目录下，通用工具（精确金融计算、报告审核、网络搜索等）重构到 `tools/common/` 目录下。请按本文档中的最新路径调用工具。

---

## 工具列表

### 核心数据工具

| 工具文件                      | 功能                     | 命令示例                                                     |
| ----------------------------- | ------------------------ | ------------------------------------------------------------ |
| `stock_info.py`             | A股信息查询              | `python tools/a_share/stock_info.py --search 新易盛`       |
| `stock_quote.py`            | A股行情数据              | `python tools/a_share/stock_quote.py --code 300502`        |
| `stock_financial.py`        | A股财务指标              | `python tools/a_share/stock_financial.py --code 300502`    |
| `stock_financial_batch.ps1` | 批量查询多只股票财务指标 | `powershell -File tools/a_share/stock_financial_batch.ps1` |
| `stock_screen.py`           | 质量筛选7条指标          | `python tools/a_share/stock_screen.py --code 300502`       |
| `stock_equity.py`           | 股权结构与财报下载       | `python tools/a_share/stock_equity.py --code 601899`       |

### 辅助计算工具

| 工具文件               | 功能                              | 命令示例                                                           |
| ---------------------- | --------------------------------- | ------------------------------------------------------------------ |
| `financial_rigor.py` | 精确金融计算（PE、ROE、市值校验） | `python tools/common/financial_rigor.py verify-valuation --help` |
| `report_audit.py`    | 研究报告审核                      | `python tools/common/report_audit.py --help`                     |

### 大宗商品数据工具

| 工具文件               | 功能                                                | 命令示例                                                   |
| ---------------------- | --------------------------------------------------- | ---------------------------------------------------------- |
| `commodity_price.py` | 大宗商品价格数据获取（Akshare 优先，yfinance 回退） | `python tools/common/commodity_price.py --code cu,GC,CL` |

### 汇率数据工具

| 工具文件       | 功能                                                | 命令示例                                         |
| -------------- | --------------------------------------------------- | ------------------------------------------------ |
| `fx_rate.py` | 国际主要货币汇率获取（Akshare 优先，yfinance 回退） | `python tools/common/fx_rate.py --code USDCNY` |

### PDF 文档处理工具

| 工具文件           | 功能                                                        | 命令示例                                                            |
| ------------------ | ----------------------------------------------------------- | ------------------------------------------------------------------- |
| `pdf_extract.py` | PDF 文字与表格提取（基于 pdf-inspector，面向财报/年报附表） | `python tools/common/pdf_extract.py markdown 601899_2025年报.pdf` |

### 网络搜索工具

按工具重要性排序（角色定位详见第十三章选型对比）:

| 工具文件             | 功能（角色定位）                                                       | 命令示例                                                           |
| -------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------ |
| `anysearch.py`     | AnySearch 全域结构化搜索（**A股投研首选**，23 大垂直领域数据库） | `python tools/common/anysearch.py "紫金矿业 财报" --tag finance` |
| `doubao_search.py` | 豆包搜索（**实时资讯/舆情首选**，火山引擎 SearchInfinity）       | `python tools/common/doubao_search.py "紫金矿业 财报"`           |
| `exa_search.py`    | Exa 语义搜索（**美股深度研究首选**，AI 原生检索，支持深度档位）  | `python tools/common/exa_search.py "煤化工行业报告"`             |
| `tavily_search.py` | Tavily 搜索（**港美股深度内容辅源**，阿里云百炼 MCP）            | `python tools/common/tavily_search.py "紫金矿业 2025年报"`       |
| `web_search.py`    | 阿里云百炼 WebSearch MCP（**仅阿里云生态/轻量验证兜底**）        | `python tools/common/web_search.py "腾讯控股 股价"`              |

---

## 一、stock_info.py - A股信息查询

### 功能说明

获取A股上市公司的代码、名称、行业、ROE、毛利率、每股收益等基本信息。

**数据缓存机制**（`tools/common/a_stock_cache.py`）：
- 代码/名称与最新季度行业数据优先从本地缓存 `data/a_share/`（CSV 文件）读取，
  避免每次查询都调用 akshare 拉取全量数据（约 5500 行），降低限流风险；
- 缓存有效期默认 7 天（`.env` 的 `STOCK_CACHE_TTL_DAYS` 可配置），到期后任意
  查询自动刷新（退市股/改名股最迟 7 天自愈）；
- 本地查不到时触发 miss 刷新：强制刷新一次缓存后再查（新 IPO/改名股自愈）；
- 输出 meta 的 `cache` 字段标识缓存状态：
  `hit`（缓存命中，零 API 调用）/ `refresh`（本次拉取刷新）/ `stale`（刷新失败降级使用旧缓存）；
- 强制刷新缓存：使用 `--refresh` 参数（见下方第 5 节）。

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
    "count": 5543,
    "cache": "hit",
    "timestamp": "2026-08-15T17:00:00"
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
      "industry": "通信设备",
      "roe": 28.5,
      "gross_margin": 35.2,
      "eps": 1.85
    }
  ],
  "meta": {
    "tool": "stock_info",
    "command": "search",
    "keyword": "新易盛",
    "count": 1,
    "cache": "hit"
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
- `industry`: 所处行业（来自最新季度业绩报表，未披露时为空）
- `roe`: 净资产收益率（%）
- `gross_margin`: 销售毛利率（%）
- `eps`: 每股收益（元）
- 注：meta 的 `cache` 字段标识缓存状态；本地查不到时工具会自动强制刷新一次缓存后再查

> 说明：`--code` 返回的是基本信息与最新季度业绩字段，行情类字段（价格、涨跌幅、成交量等）请使用 `stock_quote.py` 获取。

#### 4. 按行业筛选

```bash
python tools/a_share/stock_info.py --industry 光模块
```

**说明**: 仅支持A股行业筛选，港股暂不支持。

#### 5. 强制刷新缓存

```bash
python tools/a_share/stock_info.py --refresh
```

**说明**: 强制从 akshare 拉取全量代码/名称与最新季度行业数据，覆写本地缓存
`data/a_share/stock_code.csv` 与 `data/a_share/stock_industry.csv`，并输出缓存文件路径与记录数。

**输出示例**:

```json
{
  "success": true,
  "data": {
    "stock_code": {"count": 5543, "cache_file": "F:/Financial_Investment_Analysis/data/a_share/stock_code.csv"},
    "stock_industry": {"count": 1123, "cache_file": "F:/Financial_Investment_Analysis/data/a_share/stock_industry.csv"}
  },
  "meta": {
    "tool": "stock_info",
    "command": "refresh",
    "market": "a",
    "elapsed_seconds": 13.2,
    "timestamp": "2026-08-15T17:30:00"
  }
}
```

**注意**: 行业数据条数可能少于代码列表——`stock_yjbb_em` 仅返回已披露当季业绩的公司
（如 8 月中旬 2026 半年报未披露完时约 1100 条），属正常现象；缓存目录 `data/` 已被
`.gitignore` 忽略，不会进入版本库。

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

**数据缓存**（`tools/common/a_stock_cache.py`）：财务摘要与利润表按股票分文件缓存于
`data/a_share/financial/`（TTL 默认 7 天，`.env` 的 `A_FINANCIAL_TTL_DAYS` 可配置）；
IPO 信息缓存 90 天（`A_IPO_TTL_DAYS`，上市后几乎不变）。命中缓存零 API 调用，仅
缓存缺失/过期才调用 akshare；刷新失败时降级返回旧缓存（`meta.cache = "stale"`）。

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

**输出示例**（所有模式的输出结构统一为 `data.indicators`，键为报告期如 `20251231`）:

```json
{
  "success": true,
  "data": {
    "indicators": {
      "ROE": {
        "20251231": 24.5,
        "20250930": 18.2,
        "20250630": 12.1,
        ...
      },
      "毛利率": {
        "20251231": 35.6,
        ...
      }
    }
  },
  "meta": {
    "tool": "stock_financial",
    "code": "300502",
    "indicator": "ROE",
    "timestamp": "2026-08-05T15:00:00"
  }
}
```

**解析方式**（使用 `d['data']['indicators']` 访问指标数据）:

```python
import sys, json
d = json.loads(sys.stdin.buffer.read().decode('utf-8-sig'))
ind = d['data']['indicators']
print(ind['ROE'])
```

### 批量查询脚本 stock_financial_batch.ps1

批量调用 `stock_financial.py`，一次查询多只股票的指定财务指标，输出每只股票最近 N 期数据。已内置统一输出结构（`d['data']['indicators']`）的解析逻辑，并在 Python 内用 `subprocess` 直接捕获工具 stdout 解析，避免 PowerShell 管道重编码导致的 JSON 解码失败。

**使用方法**（PowerShell 7 环境）:

```powershell
# 默认参数（4只股票 × 6个核心指标 × 近5期）
& "F:/Financial_Investment_Analysis/tools/a_share/stock_financial_batch.ps1"

# 自定义股票代码和指标
& "F:/Financial_Investment_Analysis/tools/a_share/stock_financial_batch.ps1" -codes "601899,000960" -indicators "ROE,毛利率"

# 指定期数
& "F:/Financial_Investment_Analysis/tools/a_share/stock_financial_batch.ps1" -codes "601899" -periods 3
```

**参数说明**:

| 参数            | 默认值                                                       | 说明                 |
| --------------- | ------------------------------------------------------------ | -------------------- |
| `-codes`      | `000960,000962,000426,002155`                              | 股票代码（逗号分隔） |
| `-indicators` | `营业总收入,归母净利润,基本每股收益,ROE,毛利率,资产负债率` | 财务指标（逗号分隔） |
| `-periods`    | `5`                                                        | 输出最近几期数据     |
| `-python`     | `F:/Anaconda3/envs/Python_3_12_3/python.exe`               | Python 路径          |

**输出示例**:

```
===== 000960 =====
ROE {'20250930': 8.75, '20251231': 9.77, '20260331': 4.24}
毛利率 {'20250930': 11.3893, '20251231': 11.3748, '20260331': 10.044}
===== 000962 =====
ROE {'20250930': 7.75, '20251231': 9.62, '20260331': 1.7}
毛利率 {'20250930': 18.1065, '20251231': 18.4334, '20260331': 14.8854}
```

**注意**：

- 需使用 **PowerShell 7**（`pwsh`/终端）运行；Windows PowerShell 5.1 会因 ANSI 编码导致中文指标乱码
- 脚本通过 `$MyInvocation.MyCommand.Path` 自适应工作目录，可在任意位置调用

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

| # | 指标              | 排除条件 | 衡量的是什么 |
| - | ----------------- | -------- | ------------ |
| 1 | 10年平均ROE       | < 8%     | 资本效率     |
| 2 | 5年累计自由现金流 | 为负     | 利润质量     |
| 3 | 利息覆盖倍数      | < 2倍    | 偿债安全     |
| 4 | 长期毛利率        | < 15%    | 定价权       |
| 5 | 经营现金流/净利润 | < 0.7    | 利润质量     |
| 6 | 长期净利率        | < 5%     | 抗风险能力   |
| 7 | 5年总股本膨胀     | > 20%    | 股东利益     |

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

| 报告类型 | 文件名格式                          | 示例                      |
| -------- | ----------------------------------- | ------------------------- |
| 年报     | `{股票代码}_{年份}年报.pdf`       | `601899_2025年报.pdf`   |
| 半年报   | `{股票代码}_{年份}半年报.pdf`     | `601899_2026半年报.pdf` |
| 季报     | `{股票代码}_{年份}{季度}季报.pdf` | `601899_2026Q1季报.pdf` |

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

## 八、anysearch.py - AnySearch 全域结构化搜索

### 功能说明

**角色定位**：A股投研首选。

通过 AnySearch 全域结构化搜索 API 实现网络信息搜索，专为 AI Agent/大模型打造，自动意图路由、多垂直数据库聚合、自动清洗广告冗余，输出轻量化结构化内容，大幅降低 Token 消耗，抑制 AI 幻觉。

**核心能力**：

- **23 大垂直领域专属数据库**: 学术、法律、金融、代码、专利、医疗、安全漏洞、航空出行、农业、舆情自媒体等，支持精准定向检索（`tag` 分层）
- **多源智能融合**: 自动识别查询意图，并行调取通用网页 + 行业私有索引，交叉校验去重
- **轻量化结构化输出**: 支持 JSON/Markdown 两种格式，自动剔除广告、导航垃圾内容，比传统搜索 API 节省 60%~70% Token
- **国内专属低延迟节点**: 大陆直连无跨境网络问题，平均响应 0.4s
- **QPS 限流**: 内置线程安全限速器，默认 20 QPS，避免触发服务端 429

**免费额度政策（2026 最新）**：

- 匿名 IP 调用（无 API Key）：按 IP 限流，额度极少，仅临时测试
- 注册普通用户（免费永久）：每日 1000 次搜索额度，0 点自动重置，全功能无阉割
- 学生/开源开发者认证：每日额度提升至 2000 次

### 依赖与配置

依赖库：`pip install requests python-dotenv`

在项目根目录 `.env` 文件配置（不填则匿名调用，额度极少）：

```bash
# AnySearch API Key（申请: https://anysearch.com/console/api-keys）
ANYSEARCH_API_KEY=sk-your-api-key
ANYSEARCH_BASE_URL=https://api.anysearch.com   # API 基础 URL，默认即可
ANYSEARCH_MAX_QPS=20                            # QPS 限流（默认 20）
ANYSEARCH_DEFAULT_MAX_RESULTS=10                # 默认返回结果数
ANYSEARCH_DEFAULT_ZONE=cn                       # 默认区域（cn/intl）
ANYSEARCH_DEFAULT_LANGUAGE=zh-CN                # 默认语言（zh-CN/en）
ANYSEARCH_DEFAULT_FORMAT=json                   # 默认格式（json/markdown）
ANYSEARCH_REQUEST_TIMEOUT=30                    # 请求超时秒数
```

### 使用方法

#### 1. 基本搜索

```bash
python tools/common/anysearch.py "紫金矿业 财报"
```

#### 2. 指定返回条数

```bash
# 返回 1-20 条结果（默认 10 条）
python tools/common/anysearch.py "黄金价格走势 2026" --count 10
```

#### 3. 垂直领域定向搜索（tag）

```bash
# 金融财务领域（财务报表）
python tools/common/anysearch.py "A股 半年报 业绩" --tag finance.fundamental
# 法律判例
python tools/common/anysearch.py "民法典 民间借贷 利率" --tag legal.case
# 代码文档
python tools/common/anysearch.py "FastAPI 教程" --tag code.doc --zone intl
# 学术论文
python tools/common/anysearch.py "carbon capture" --tag academic.search --zone intl
```

`--tag` 支持快捷别名（自动映射为官方 tag），常用别名：

| 别名                          | 官方 tag                | 领域         |
| ----------------------------- | ----------------------- | ------------ |
| `general`                   | `general.general`     | 通用全网搜索 |
| `code` / `doc`            | `code.doc`            | 开发文档     |
| `github` / `snippet`      | `code.snippet`        | GitHub 代码  |
| `finance` / `fundamental` | `finance.fundamental` | 财务报表     |
| `stock` / `quote`         | `finance.quote`       | 实时行情     |
| `calendar`                  | `finance.calendar`    | 财报日程     |
| `macro`                     | `finance.macro`       | 宏观经济     |
| `legal` / `case`          | `legal.case`          | 法律判例     |
| `statute`                   | `legal.statute`       | 法规         |
| `patent` / `ip`           | `ip.global`           | 全球专利     |
| `vuln` / `cve`            | `security.vuln`       | CVE 漏洞     |
| `paper` / `academic`      | `academic.search`     | 学术论文     |

**垂直领域 Tag 完整分类**（官方 tag 体系，格式统一为 `大类.细分域`，填入 API `tag` 参数即可定向调取专业数据库）：

1. **academic（学术）**：`biomedical` 生物医药、`citation` 引用、`dataset` 数据集、`preprint` 预印本、`search` 综合论文
2. **code（开发）**：`doc` 开发文档、`snippet` GitHub 代码片段
3. **finance（金融）**：`calendar` 财报日程、`fundamental` 财务报表、`macro` 宏观经济、`quote` 实时行情
4. **legal（法律）**：`case` 判例、`statute` 法规、`legislation` 法案
5. **ip（专利）**：`global` 全球专利检索
6. **security（安全）**：`vuln` CVE 漏洞、`intel` 威胁情报
7. **general.general**：通用全网搜索（默认）
8. **其余领域**：`agriculture` 农业、`energy` 能源、`health` 医疗、`travel` 航班、`social_media` 自媒体、`gaming` 游戏等

#### 4. 扩展筛选参数（params）

```bash
# 指定代码库（code 领域）
python tools/common/anysearch.py "Go 1.26" --tag code --params '{"library":"golang"}'
# 指定股票代码（quote 领域）
python tools/common/anysearch.py "AAPL 股价" --tag quote --params '{"ticker":"AAPL"}'
```

#### 5. 区域与语言切换

```bash
# 国际区域（海外资讯收录质量更高）
python tools/common/anysearch.py "Fed rate decision" --zone intl --language en
# 国内区域（默认）
python tools/common/anysearch.py "A股 政策" --zone cn --language zh-CN
```

#### 6. JSON 格式输出

```bash
python tools/common/anysearch.py "腾讯控股" --json
```

#### 7. 导出 Markdown 报告

```bash
# 导出到 reports/ 目录（默认命名规则）
python tools/common/anysearch.py "紫金矿业" --export
# 自定义导出路径
python tools/common/anysearch.py "紫金矿业" --export --export-path reports/my_report.md
```

### 模块导入接口

```python
from tools.common.anysearch import anysearch

# 基本调用
results = anysearch("黄金价格", max_results=5)

# 垂直领域定向搜索
results = anysearch(
    "紫金矿业 财报",
    tag="finance",            # 支持快捷别名
    max_results=5,
)

for item in results:
    print(f"标题: {item['title']}")
    print(f"链接: {item['url']}")
    print(f"摘要: {item['snippet'][:100]}...")
```

返回值每项包含 4 个字段：`title`（标题）、`url`（链接）、`snippet`（简短摘要）、`content`（清洗后的完整正文，专供 LLM 读取）。

### 注意事项

1. **API Key 申请**: 需在 https://anysearch.com/console/api-keys 注册获取（免费每日 1000 次）
2. **匿名模式**: 未配置 `ANYSEARCH_API_KEY` 时自动匿名调用，但额度极少，正式开发强烈建议注册
3. **query 长度**: 单条 query 建议不超过 300 字符，批量多关键词请拆分多次请求
4. **额度管理**: 402 额度耗尽需等待次日 0 点重置；429 限流请增加重试间隔
5. **tag 优先**: 优先使用 `--tag` 垂直检索，避免通用全网搜索，减少无关结果与 Token 消耗
6. **返回字段**: 每项含 title、url、snippet、content 四个字段

---

## 九、doubao_search.py - 豆包搜索

### 功能说明

**角色定位**：实时资讯/舆情首选。

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

| 字段             | 类型  | 说明                                                           |
| ---------------- | ----- | -------------------------------------------------------------- |
| `title`        | str   | 标题                                                           |
| `url`          | str   | 链接                                                           |
| `site_name`    | str   | 来源站点名                                                     |
| `publish_time` | str   | 发布时间（ISO 8601）                                           |
| `summary`      | str   | 摘要（500~1000 字，适合大模型场景）                            |
| `snippet`      | str   | 简短片段                                                       |
| `content`      | str   | 正文内容（需`need_content=True`）                            |
| `auth_level`   | int   | 权威度等级（1=非常权威, 2=正常权威, 3=一般权威, 4=一般不权威） |
| `auth_des`     | str   | 权威度中文描述                                                 |
| `rank_score`   | float | 相关性评分                                                     |

### 注意事项

1. **AK/SK 申请**: 需在火山引擎控制台开通联网搜索服务并创建 IAM 访问密钥
2. **QPS 限流**: 账号维度默认 5 QPS，需扩容可提工单；客户端已内置限流
3. **关键词长度**: 1~100 字符，过长会自动截断
4. **结果条数**: 1~50 条，默认 10 条
5. **正文获取**: 默认不返回正文，需 `--need-content` 开启

---

## 十、exa_search.py - Exa 语义搜索

### 功能说明

**角色定位**：美股深度研究首选。

通过 Exa.ai（原 Metaphor Search）语义搜索引擎 API 实现网络信息搜索。Exa 是原生为大模型/AI 智能体打造的自研语义搜索引擎，无广告排序干扰，擅长长文本、研究型、专业领域查询（学术、财报、代码、法律、医疗）。

**核心特性**:

- 使用 HTTP API 调用（`x-api-key` 认证），无需 SDK
- 语义向量检索：直接理解自然语言长问句，支持中英文
- 检索速度档位：instant/fast/auto/deep-lite/deep（deep 档适合深度调研）
- Autoprompt 自动优化查询词，提升冷门资料命中率
- 两种内容模式：text 全文提取 / highlights 高亮摘要（Token 节约 90%）
- 返回结构化数据：title、url、published_date、content

### 依赖与配置

**依赖库**:

```bash
pip install requests python-dotenv
```

**环境变量**（在项目根目录 `.env` 文件中配置）:

```
EXA_API_KEY=your_exa_api_key
```

API Key 申请地址：https://dashboard.exa.ai/api-keys（免费层每月 1000 次搜索）

### 使用方法

#### 1. 基本搜索

```bash
python tools/common/exa_search.py "煤化工行业报告"
```

#### 2. 指定结果数量

```bash
python tools/common/exa_search.py "紫金矿业 2025年报" --max-results 8
```

#### 3. 深度调研（deep 档，耗时 4-40 秒）

```bash
python tools/common/exa_search.py "A股 磷化工 产业链 深度报告" --type deep
```

#### 4. Token 节约模式（highlights 高亮摘要）

```bash
python tools/common/exa_search.py "黄金价格走势" --highlights --json
```

#### 5. 关闭 Autoprompt / 指定内容字符数

```bash
python tools/common/exa_search.py "紫金矿业" --no-autoprompt --max-characters 3000
```

### 参数说明

| 参数                 | 默认值   | 说明                                       |
| -------------------- | -------- | ------------------------------------------ |
| `query`            | 必填     | 搜索关键词                                 |
| `--max-results`    | 5        | 返回结果数量                               |
| `--type`           | auto     | 检索档位：instant/fast/auto/deep-lite/deep |
| `--no-autoprompt`  | 开启     | 关闭查询词自动优化                         |
| `--max-characters` | 2000     | 内容提取最大字符数                         |
| `--highlights`     | 关闭     | 使用高亮摘要模式（Token 更省）             |
| `--json`           | 关闭     | JSON 格式输出                              |
| `--api-key`        | 环境变量 | 命令行覆盖 API Key                         |

### 模块导入接口

```python
from tools.common.exa_search import exa_search

results = exa_search("黄金价格走势", max_results=3, search_type="fast")
for item in results:
    print(f"标题: {item['title']}")
    print(f"链接: {item['url']}")
    print(f"发布时间: {item['published_date']}")
    print(f"内容: {item['content'][:100]}...")
```

### 注意事项

1. **API Key 申请**: 需在 https://dashboard.exa.ai/api-keys 申请（免费层每月 1000 次）
2. **深度档位耗时**: `deep`/`deep-lite` 档位耗时较长（4-40 秒），工具已设置 60 秒超时
3. **检索档位选择**: 常规问答用 `auto`，实时场景用 `instant`/`fast`，深度调研用 `deep`
4. **Token 控制**: 追求上下文成本节约时使用 `--highlights`（只返回相关段落）
5. **返回字段**: 每项含 title、url、published_date、content 四个字段

---

## 十一、tavily_search.py - Tavily 搜索

### 功能说明

**角色定位**：港美股深度内容辅源，中文弱、国内网络不稳，不作主源。

通过阿里云百炼 Tavily MCP 服务实现网络信息搜索，返回标题、URL、内容三个字段。主要面向港股/美股深度内容检索的辅助验证场景（如管理层讨论、分析师点评），不作为主搜索源。

**核心特性**:

- 使用 MCP 协议（SSE 流式）连接阿里云百炼 Tavily 服务
- 搜索参数固定为 `search_depth=advanced`（高级搜索档）+ `include_raw_content=True`（开启正文），内容质量较高
- 返回结构化数据：title、url、content
- 支持命令行调用和模块导入
- 从项目根目录 `.env` 文件读取 API Key

### 依赖与配置

**依赖库**:

```bash
pip install mcp python-dotenv
```

**环境变量**（在项目根目录 `.env` 文件中配置）:

```
DASHSCOPE_API_KEY=your_api_key_here
Tavily_MCP_BASE_URL=https://dashscope.aliyuncs.com/api/v1/mcps/tavily-ai/sse  # 可选
```

### 使用方法

#### 1. 基本搜索

```bash
python tools/common/tavily_search.py "紫金矿业 2025年报"
```

#### 2. 指定结果数量

```bash
python tools/common/tavily_search.py "腾讯控股 年报" --max-results 10
```

#### 3. JSON 格式输出

```bash
python tools/common/tavily_search.py "紫金矿业 ROE" --json
```

#### 4. 命令行覆盖 API Key

```bash
python tools/common/tavily_search.py "腾讯控股" --api-key sk-your-api-key
```

### 参数说明

| 参数              | 默认值   | 说明                                |
| ----------------- | -------- | ----------------------------------- |
| `query`         | 必填     | 搜索关键词                          |
| `--max-results` | 5        | 返回结果数量（传入 MCP 服务的参数） |
| `--json`        | 关闭     | JSON 格式输出                       |
| `--api-key`     | 环境变量 | 命令行覆盖 DASHSCOPE_API_KEY        |

### 模块导入接口

```python
import asyncio
from tools.common.tavily_search import tavily_search

async def main():
    results = await tavily_search("黄金价格走势", max_results=3)
    for r in results:
        print(f"标题: {r['title']}")
        print(f"链接: {r['url']}")
        print(f"内容: {r['content'][:100]}...")

asyncio.run(main())
```

### 返回字段说明

每条搜索结果包含以下字段:

| 字段        | 类型 | 说明                                       |
| ----------- | ---- | ------------------------------------------ |
| `title`   | str  | 标题                                       |
| `url`     | str  | 链接                                       |
| `content` | str  | 正文内容（含 raw_content，由工具解析拼接） |

### 注意事项

1. **API Key 申请**: 需在阿里云百炼控制台开通 Tavily MCP 服务（复用 `DASHSCOPE_API_KEY`）
2. **异步调用**: 使用 MCP 协议（SSE），需在异步环境中运行
3. **Windows 兼容**: 已自动设置 `WindowsSelectorEventLoopPolicy`
4. **搜索深度固定**: 工具内部固定 `search_depth=advanced` + `include_raw_content=True`，CLI 不支持切换搜索档位
5. **角色定位**: 中文检索能力较弱、国内网络波动较大，仅作为港美股深度内容辅源，不作主源；详见第十三章选型对比

---

## 十二、web_search.py - 阿里云百炼 WebSearch

### 功能说明

**角色定位**：仅阿里云生态/轻量验证兜底，移出默认组合。

通过阿里云百炼 WebSearch MCP 服务实现网络信息搜索，作为阿里云通义千问生态内的轻量检索手段，仅用于已有阿里云生态的快速关键词验证场景。

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
5. **角色定位**: 无垂直深库、无正文/权威度/报告导出能力，仅作为阿里云生态内的轻量验证兜底，移出默认搜索组合；详见第十三章选型对比

---

## 十三、搜索工具选型对比

本章为五工具 × 市场选型矩阵，依据《搜索服务选择策略重构方案 v2.0》定稿。

### 13.1 五工具角色定位总览

| 工具                 | 角色定位                                           | 报告依据             | 实测验证状态                                                                                                        |
| -------------------- | -------------------------------------------------- | -------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `anysearch.py`     | A股投研首选（23 类垂直库、多源交叉、国内直连）     | 报告 5.2.1、5.3、7.5 | ✅ 港股通用搜索覆盖通过；✅ 美股`--zone intl` 覆盖通过；⚠️ `--tag finance` 垂直库需额外参数，港股适用性待验证 |
| `doubao_search.py` | 实时资讯/舆情首选（权威信源、跨市场、正文/导出）   | 报告 5.2.2、5.3      | ✅ 豆包搜索测试正常                                                                                                 |
| `exa_search.py`    | 美股深度研究首选（SEC filings、27K 美股、deep 档） | 报告 5.2.4、5.3      | ✅ "AAPL 10-K" 直接命中 SEC.gov 原文 + Apple IR + EDGAR，5 条结果全部高质量                                         |
| `tavily_search.py` | 港美股深度内容辅源（管理层讨论/分析师点评）        | 报告 3.4             | 未单独实测，沿用报告结论；中文弱、国内网络不稳，不作主源                                                            |
| `web_search.py`    | 仅阿里云生态/轻量验证兜底（2000 次一次性额度）     | 报告 3.3             | 未单独实测，沿用报告结论；移出默认组合                                                                              |

### 13.2 各工具核心参数速查

| 工具                 | 关键参数                                                                                       | 免费额度                 | 国内稳定性   |
| -------------------- | ---------------------------------------------------------------------------------------------- | ------------------------ | ------------ |
| `anysearch.py`     | `--tag finance/legal/patent/paper`、`--zone cn/intl`、`--language zh-CN/en`              | 每日 1000 次（0 点重置） | 直连 0.4s    |
| `doubao_search.py` | `--finance`、`--sites`、`--need-content`、`--export`、`--time-range`、`--industry` | 每月 500 次              | 直连 0.45s   |
| `tavily_search.py` | `--max-results`、搜索深度（固定 advanced）                                                   | 每月 1000 次             | 海外，波动大 |
| `exa_search.py`    | `--type deep`、`--highlights`、`--max-results`                                           | 注册 $20 + 月赠 $10      | 海外，波动大 |
| `web_search.py`    | 无高级参数                                                                                     | 前 2000 次一次性         | 国内节点稳定 |

### 13.3 市场 × 场景选型矩阵（定稿）

#### A股 —— 双主组合

| 场景                         | 主搜索                                       | 辅/验证                     |
| ---------------------------- | -------------------------------------------- | --------------------------- |
| 财报/研报/公告/判例/专利深查 | `anysearch --tag finance/legal`            | `doubao --finance`        |
| 实时新闻/舆情/热点资讯       | `doubao --finance`                         | `anysearch`               |
| 精确数值核验                 | `financial_rigor.py`（专用工具，不属搜索） | —                          |
| 多源交叉验证                 | `anysearch` + `doubao` 双主              | `web_search` 兜底（手动） |

#### 港股

| 场景                   | 主搜索                         | 辅/验证                                             |
| ---------------------- | ------------------------------ | --------------------------------------------------- |
| 港交所披露易/公告/回购 | `doubao --sites hkexnews.hk` | `tavily`                                          |
| 管理层讨论/分析师点评  | `tavily`                     | `doubao`                                          |
| 财报/研报深度检索      | `doubao --need-content`      | `anysearch`（通用搜索，**已验证港股覆盖**） |
| 双源验证               | `doubao` + `tavily`        | —                                                  |

#### 美股

| 场景                           | 主搜索               | 辅/验证                   |
| ------------------------------ | -------------------- | ------------------------- |
| SEC filings/财报/MD&A 深度检索 | `exa --type deep`  | `tavily`                |
| 美股新闻/舆情/跨市场对比       | `doubao`           | `anysearch --zone intl` |
| 双源验证                       | `exa` + `doubao` | —                        |

### 13.4 通用规范（全市场适用）

1. 使用 `--time-range day/week/month` 限制时间范围，优先获取最新信息
2. 搜索结果必须包含数据来源日期；过时数据须标注时效性说明
3. 非境内上市公司关键信息须双源验证（港股：doubao+tavily；美股：exa+doubao）
4. 关键信息缺失时标注"信息不足"，不得用推测填充
5. 中概股双重上市（A+H / A+美股）用 `doubao` 跨市场综合检索，无需切换工具

### 13.5 实测验证结论

- **anysearch 港股通用搜索覆盖通过**：腾讯 00700 返回 5 条权威财经媒体结果含精确财务数据；港交所 00388 返回 3 条含精确业绩数据
- **anysearch 美股 `--zone intl` 覆盖通过**：NVDA 返回 $130.5B revenue, $2.94 EPS
- **exa 美股 SEC filings 实测通过**：搜索 "AAPL 10-K" 直接命中 SEC.gov 原文（aapl-20240928.htm）+ Apple IR + EDGAR，5 条结果全部高质量
- **doubao 搜索测试正常**
- ⚠️ **警告**：`anysearch --tag finance` 垂直库需额外参数（symbol/type/cn_code）；港股财报/研报深度检索以 `doubao --need-content` 为主、`anysearch` 通用搜索为辅

### 13.6 选型决策流程图

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

### 13.7 实战推荐表

按市场分组，每行含"使用场景 | 推荐工具 | 命令示例 | 理由"。

#### A股

| 使用场景                   | 推荐工具                            | 命令示例                                                           | 理由                         |
| -------------------------- | ----------------------------------- | ------------------------------------------------------------------ | ---------------------------- |
| A股财报/研报/公告深查      | `anysearch.py --tag finance`      | `python tools/common/anysearch.py "紫金矿业 财报" --tag finance` | 23 类垂直库定向，省 Token    |
| A股实时新闻/舆情监控       | `doubao_search.py --finance`      | `python tools/common/doubao_search.py "紫金矿业" --finance`      | 权威信源筛选 + 行业定向      |
| 法律判例/专利/学术论文检索 | `anysearch.py --tag legal/patent` | `python tools/common/anysearch.py "民法典" --tag legal`          | 独家垂直数据库，其他工具缺失 |
| 多源交叉验证               | `anysearch` + `doubao` 双主     | 两次调用后对比                                                     | 国内直连稳定，免费额度充足   |
| 精确数值核验               | `financial_rigor.py`              | `python tools/common/financial_rigor.py verify-valuation ...`    | 专用工具，不属搜索           |

#### 港股

| 使用场景               | 推荐工具                            | 命令示例                                                                 | 理由                     |
| ---------------------- | ----------------------------------- | ------------------------------------------------------------------------ | ------------------------ |
| 港交所披露易/公告/回购 | `doubao_search.py --sites`        | `python tools/common/doubao_search.py "腾讯 回购" --sites hkexnews.hk` | 站点白名单定向           |
| 管理层讨论/分析师点评  | `tavily_search.py`                | `python tools/common/tavily_search.py "Tencent management discussion"` | 深度内容辅源             |
| 财报/研报深度检索      | `doubao_search.py --need-content` | `python tools/common/doubao_search.py "腾讯控股 年报" --need-content`  | 正文返回 + Markdown 导出 |
| 双源验证               | `doubao` + `tavily`             | 两次调用后对比                                                           | 非境内上市公司须双源验证 |

#### 美股

| 使用场景                       | 推荐工具                      | 命令示例                                                                       | 理由                     |
| ------------------------------ | ----------------------------- | ------------------------------------------------------------------------------ | ------------------------ |
| SEC filings/财报/MD&A 深度检索 | `exa_search.py --type deep` | `python tools/common/exa_search.py "AAPL 10-K" --type deep`                  | 直接命中 SEC.gov 原文    |
| 美股新闻/舆情/跨市场对比       | `doubao_search.py`          | `python tools/common/doubao_search.py "NVDA earnings"`                       | 跨市场综合检索           |
| 美股辅搜/海外资讯              | `anysearch.py --zone intl`  | `python tools/common/anysearch.py "NVDA earnings" --zone intl --language en` | 已验证返回精确财务数据   |
| 双源验证                       | `exa` + `doubao`          | 两次调用后对比                                                                 | 非境内上市公司须双源验证 |

#### 通用

| 使用场景           | 推荐工具          | 命令示例                                       | 理由                       |
| ------------------ | ----------------- | ---------------------------------------------- | -------------------------- |
| 高频免费检索       | `anysearch.py`  | `python tools/common/anysearch.py "关键词"`  | 每日 1000 次免费，0 点重置 |
| 阿里云全栈部署     | `web_search.py` | `python tools/common/web_search.py "关键词"` | 复用 DASHSCOPE_API_KEY     |
| 快速验证某个关键词 | 任一均可          | 视已配置凭证而定                               | 轻量场景                   |

### 13.8 配套测试

各工具均配套测试软件:

- `anysearch.py` 测试: `python tests/common/test_anysearch.py [--skip-live]`
- `doubao_search.py` 测试: `python tests/common/test_doubao_search.py [--skip-live]`
- `exa_search.py` 测试: `python tests/common/test_exa_search.py [--test unit|all]`
- `tavily_search.py` 测试: `python tests/common/test_tavily_search.py`
- `web_search.py` 测试: `python tests/common/test_web_search.py`

`--skip-live` 参数可跳过需要真实凭证的在线测试，适合在 CI/CD 等无凭证环境运行。
`test_exa_search.py` 默认运行 `unit`（mock 无网络依赖），配置 `EXA_API_KEY` 后可运行 `--test all` 执行网络集成测试。
`test_anysearch.py` 默认运行 22 项测试，配置 `ANYSEARCH_API_KEY` 后运行在线搜索测试；`--skip-live` 跳过在线测试。

---

## 十四、commodity_price.py - 大宗商品价格数据

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

| 品种类型                       | 主数据源                 | 回退数据源            |
| ------------------------------ | ------------------------ | --------------------- |
| 国内品种（上期所/广期所）      | Akshare                  | 无（仅 Akshare 支持） |
| 外盘品种（COMEX/WTI/布伦特等） | Akshare                  | yfinance              |
| 铂金/钯金                      | 无（Akshare 无稳定接口） | yfinance              |

### 注意事项

1. **限流保护**：单次获取最多 10 条记录，批量获取最多 10 个品种
2. **默认时间窗口**：14 天（约 10 个交易日）
3. **yfinance 代理**：在中国大陆使用 yfinance 可能需要配置代理
4. **数据延迟**：免费接口数据可能有数分钟延迟
5. **测试文件**：单元测试 `tests/common/test_commodity_price.py`，集成测试 `tests/common/test_commodity_price_integration.py`

---

## 十五、fx_rate.py - 国际主要货币汇率

### 功能说明

获取国际主要货币汇率数据，支持 19 个货币对（美元兑主要货币、人民币兑主要货币、人民币与港币双向）。采用 **Akshare 优先、yfinance 回退** 的双数据源策略，获取的是**市场浮动汇率（收盘价）**（盘面K线），非央行中间价。

> **关联用途**：结合 `commodity_price.py` 获取的大宗商品价格，可支撑有色金属等大宗商品的人民币成本核算；结合 `stock_quote.py` 可折算港股/美股行情的人民币口径。

**支持货币对（19 个）**：

- **美元兑主要货币（9个）**：USDCNY、USDCNH、EURUSD、GBPUSD、USDJPY、AUDUSD、USDCAD、USDCHF、USDHKD
- **人民币兑主要货币（8个，1外币=x人民币）**：EURCNY、GBPCNY、JPYCNY、AUDCNY、CADCNY、CHFCNY、NZDCNY、SGDCNY
- **人民币与港币（2个，双向）**：CNYHKD（1人民币=x港币）、HKDCNY（1港币=x人民币）

**限流保护**（严格限制记录数，避免触发数据源限流）：

- 单次获取默认最多返回 10 条记录，阈值上限 50 条（`--max-records`自动裁到阈值）
- Akshare 主路径采用**直连东方财富极小请求**：仅取「日期+收盘价」2 字段、最近 10 个交易日，代替 akshare 原生 `lmt=50000` 的批量大请求
- 任意两次 API 调用间隔至少 0.5 秒（模块级限流器）
- 批量获取最多 5 个货币对，货币对间间隔至少 1 秒
- 瞬时网络异常指数退避重试（3 次，1/2/4 秒）；**服务端封禁信号（如东方财富 RemoteDisconnected）自动识别并立即放弃重试**，快速回退 yfinance，避免封禁期间反复请求延长封禁

### 使用方法

#### 1. 列出所有支持货币对

```bash
python tools/common/fx_rate.py --list
```

**输出示例**：

```json
{
  "success": true,
  "data": [
    {"symbol": "USDCNY", "akshare_code": "USDCNH", "yfinance_ticker": "CNY=X"},
    {"symbol": "EURCNY", "akshare_code": "EURCNH", "yfinance_ticker": "EURCNY=X"},
    ...
  ],
  "meta": {"tool": "fx_rate", "command": "list", "total_count": 19}
}
```

#### 2. 获取单个货币对（默认最近 10 条）

```bash
python tools/common/fx_rate.py --code USDCNY
```

**输出示例**：

```json
{
  "success": true,
  "data": {
    "symbol": "USDCNY",
    "source": "yfinance",
    "success": true,
    "error": null,
    "fetch_time": "2026-08-07 11:22:06",
    "record_count": 10,
    "records": [
      {"date": "2026-07-24", "close": 6.7725},
      {"date": "2026-07-27", "close": 6.7718},
      ...
    ]
  },
  "meta": {
    "tool": "fx_rate",
    "command": "fetch",
    "symbol": "USDCNY",
    "limit": {"max_records": 10, "hard_limit": 50}
  }
}
```

#### 3. 批量获取多个货币对（最多 5 个）

```bash
python tools/common/fx_rate.py --code USDCNY,EURUSD,GBPUSD
```

#### 4. 指定日期范围

```bash
python tools/common/fx_rate.py --code USDCNY --start 2026-07-20 --end 2026-08-01
```

#### 5. 限制返回记录数

```bash
# 调整记录数（默认 10，上限 50）
python tools/common/fx_rate.py --code USDCNY --max-records 20

# 超过硬上限 50 会被拒绝
python tools/common/fx_rate.py --code USDCNY --max-records 100
# {"success": false, "error": "max_records 超过硬上限 50，当前: 100；为避免触发数据源限流，请分批获取"}
```

### 货币对代码说明

| 货币对 | 报价方向          | akshare 代码       | yfinance ticker |
| ------ | ----------------- | ------------------ | --------------- |
| USDCNY | 1美元=x人民币     | USDCNH（离岸代理） | CNY=X           |
| USDCNH | 1美元=x离岸人民币 | USDCNH             | CNH=X           |
| EURUSD | 1欧元=x美元       | EURUSD             | EURUSD=X        |
| USDJPY | 1美元=x日元       | USDJPY             | JPY=X           |
| EURCNY | 1欧元=x人民币     | EURCNH             | EURCNY=X        |
| GBPCNY | 1英镑=x人民币     | GBPCNH             | GBPCNY=X        |
| JPYCNY | 1日元=x人民币     | JPYCNH             | JPYCNY=X        |
| CNYHKD | 1人民币=x港币     | CNHHKD             | CNYHKD=X        |
| HKDCNY | 1港币=x人民币     | HKDCNH             | HKDCNY=X        |

> 完整 19 个货币对代码可通过 `--list` 查看。

### 数据源策略与回退机制

| 环节         | 说明                                                             |
| ------------ | ---------------------------------------------------------------- |
| 主数据源     | Akshare（直连东方财富极小请求，仅 2 字段 × 10 条）              |
| 回退数据源   | yfinance（Akshare 异常/空数据/区间无数据时自动切换）             |
| 封禁信号识别 | 东方财富`RemoteDisconnected`、HTTP 403 → 立即放弃重试直接回退 |
| 全失败处理   | 返回规范错误 JSON（`success: false`），绝不抛异常崩溃          |

### 注意事项

1. **汇率口径**：本工具获取的是市场浮动汇率（盘面K线），不适合直接做财报折算；会计准则认可的央行中间价请用 `ak.currency_safe()` 等接口单独获取
2. **USDCNY 口径**：东方财富代码表无在岸 USDCNY，以离岸 USDCNH 作为市场汇率代理（yfinance 的 CNY=X 同为离岸口径），两者数值一致
3. **东方财富 IP 封禁**：短时间内高频调用会被临时封禁（表现为 RemoteDisconnected），封禁期间切勿反复重试；本工具会自动识别并快速回退 yfinance，待冷却（数十分钟至数小时）后自动恢复
4. **yfinance 网络**：在中国大陆使用 yfinance 可能超时或被限流，这正是设计双数据源的原因
5. **测试文件**：单元测试 `tests/common/test_fx_rate.py`（61 个用例，mock 数据源），集成测试 `tests/common/test_fx_rate_integration.py`（默认跳过，`FX_RUN_INTEGRATION=1` 启用）

---

## 十六、pdf_extract.py - PDF 文字与表格提取

### 功能说明

基于 Firecrawl 开源的 **pdf-inspector** 库（底层 Rust，Python 绑定，预编译二进制），从 PDF 格式文档中提取文字与表格，专门面向财报/年报等含复杂附表的文档场景。配合 `stock_equity.py --download-report` 下载的财报 PDF 使用，可完成"下载 → 提取 → 分析"的自动化流程。

**核心能力**:

- `detect` 分类检测：快速判断 PDF 类型（`text_based`/`scanned`/`mixed`），并返回需 OCR 的页码
- `text` 纯文本提取：提取扁平化纯文本（不含表格排版信息）
- `markdown` 含表格的 Markdown 提取：自动完成类型检测 + 文字提取 + 表格识别 + 多栏重排，输出含财务附表的 Markdown
- `all` 全流程：依次执行 分类 + 纯文本 + Markdown

**扫描格式检测**：当检测到 PDF 为扫描格式（`scanned`/`mixed` 或含需 OCR 页面）时，`data` 中返回 `"scanned": {"scanned": true, "note": "..."}` 标志，提示调用方需走 OCR 流程，避免对无法提取的文档做无效处理。

> **命名说明**：本工具命名为 `pdf_extract.py`（而非 `pdf_inspector.py`），是为了避免与库模块 `pdf_inspector` 同名导致 `import pdf_inspector` 解析到工具自身（同名模块遮蔽问题）。

### 使用方法

#### 1. 分类检测

```bash
python tools/common/pdf_extract.py detect 601899_2025年报.pdf
```

**输出示例**:

```json
{
  "success": true,
  "data": {
    "pdf_type": "text_based",
    "page_count": 352,
    "pages_needing_ocr": [],
    "confidence": 1.0,
    "scanned": {"scanned": false}
  },
  "meta": {"tool": "pdf_extract", "command": "detect", "pdf": "601899_2025年报.pdf"}
}
```

#### 2. 提取纯文本

```bash
python tools/common/pdf_extract.py text 601899_2026半年报.pdf
```

**说明**：纯文本不写 txt 文件，仅放入 JSON 的 `data.content` 字段。

**输出示例**:

```json
{
  "success": true,
  "data": {
    "scanned": {"scanned": false},
    "length": 2384,
    "content": "紫金矿业集团股份有限公司 ..."
  },
  "meta": {"tool": "pdf_extract", "command": "text"}
}
```

#### 3. 提取含表格的 Markdown

```bash
# 提取全部页
python tools/common/pdf_extract.py markdown 601899_2026半年报.pdf

# 仅提取指定页（0 索引，逗号分隔）
python tools/common/pdf_extract.py markdown 601899_2025年报.pdf --pages 0,1

# 将 Markdown 写盘为 md 文件
python tools/common/pdf_extract.py markdown 601899_2026半年报.pdf --save-md

# 指定 md 输出目录（默认 reports/pdf）
python tools/common/pdf_extract.py markdown 601899_2026半年报.pdf --save-md --out-dir reports/pdf
```

**输出示例**:

```json
{
  "success": true,
  "data": {
    "scanned": {"scanned": false},
    "title": "601899_2026半年报",
    "pages_with_tables": [2],
    "pages_with_columns": [],
    "processing_time_ms": 950,
    "length": 3210,
    "content": "| 项目 | 本期 | 上期 |\n|---|---|---|\n| ... |",
    "file": null
  },
  "meta": {"tool": "pdf_extract", "command": "markdown"}
}
```

#### 4. 全流程

```bash
# 全流程（分类 + 纯文本 + Markdown），Markdown 写盘
python tools/common/pdf_extract.py all 601899_2026半年报.pdf --save-md
```

**输出示例**（`data` 含 `classify`/`text`/`markdown` 三个子块）:

```json
{
  "success": true,
  "data": {
    "classify": {"pdf_type": "text_based", "page_count": 3, "pages_needing_ocr": [], "confidence": 1.0},
    "text": {"length": 2384, "content": "..."},
    "markdown": {"title": "601899_2026半年报", "pages_with_tables": [2], "pages_with_columns": [], "processing_time_ms": 950, "length": 3210, "content": "..."}
  },
  "meta": {"tool": "pdf_extract", "command": "all"}
}
```

### 参数说明

| 参数          | 适用子命令     | 默认值          | 说明                                          |
| ------------- | -------------- | --------------- | --------------------------------------------- |
| `<pdf>`     | 全部           | 必填            | PDF 文件路径                                  |
| `--pages`   | markdown / all | 全部页          | 仅提取指定页（0 索引，逗号分隔，如`0,1,2`） |
| `--save-md` | markdown / all | 关闭            | 是否将 Markdown 写盘为 md 文件                |
| `--out-dir` | markdown / all | `reports/pdf` | md 文件输出目录                               |

### 扫描格式处理

当 `detect` 判定 PDF 为扫描格式（`scanned`/`mixed`）或存在需 OCR 页面时，各子命令会返回 `data.scanned.scanned = true` 且 `content` 为空。此时应转交 OCR 流程处理，而非继续做文本/表格提取。

**扫描件输出示例**:

```json
{
  "success": true,
  "data": {
    "scanned": {
      "scanned": true,
      "note": "检测到扫描格式或含需 OCR 的页面，无法直接提取文本/表格，请使用 OCR 流程处理（需要 OCR 的页码: [0, 1]）。"
    },
    "length": 0,
    "content": ""
  },
  "meta": {"tool": "pdf_extract", "command": "text"}
}
```

### 与财报下载工具配合

```bash
# 1. 下载财报 PDF（见"五、stock_equity.py"）
python tools/a_share/stock_equity.py --code 601899 --download-report

# 2. 提取财报中的财务附表
python tools/common/pdf_extract.py markdown cninfo_reports/601899_2025年报.pdf --save-md --out-dir reports/pdf
```

### 注意事项

1. **依赖库**：`pip install pdf-inspector`，当前环境已安装
2. **扫描件**：扫描格式 PDF 无法直接提取文字/表格，需 OCR 流程；工具会返回 `scanned` 标志提示
3. **年报体积**：A股年报通常 300+ 页，`markdown`/`all` 全文提取较耗时，可用 `--pages` 限定关键页
4. **测试软件**：单元测试 `tests/common/test_pdf_extract.py`，集成测试 `tests/common/test_pdf_extract_integration.py`

---

## 十七、A股代码格式说明

A股代码统一使用**6位数字字符串**:

| 代码前缀 | 交易所                 | 板块                     |
| -------- | ---------------------- | ------------------------ |
| 60xxxx   | 上海证券交易所         | 主板                     |
| 00xxxx   | 深圳证券交易所         | 主板（含原中小板002xxx） |
| 30xxxx   | 深圳证券交易所         | 创业板                   |
| 688xxx   | 上海证券交易所         | 科创板                   |
| 8xxxxx   | 北京证券交易所         | 北交所（原新三板精选层平移，83/87/88 开头） |
| 920xxx   | 北京证券交易所         | 北交所（2024年启用新代码段，新上市公司）   |

**北交所代码说明**：

- **8xxxxx**：原新三板精选层平移至北交所的存量股票，常见前缀 `83`、`87`、`88`（如 `830799`）。
- **920xxx**：2024 年起北交所启用独立新代码段，新上市公司统一使用 `920` 开头（如 `920018`），与存量 `8` 开头代码并存。
- 北交所整体代码均为 **6 位数字字符串**，与其他交易所代码格式一致，工具传入方式相同。
- 注意：`8` 开头的 6 位代码同时存在于新三板（如 `83xxxx`/`87xxxx`/`88xxxx` 的部分未平移公司），使用 akshare 工具时需通过 `stock_info.py` 确认目标公司是否确为北交所上市公司，避免与新三板挂牌公司混淆。

**示例**:

| 公司     | 代码   | 板块           |
| -------- | ------ | -------------- |
| 中国平安 | 601318 | 上交所主板     |
| 万科A    | 000002 | 深交所主板     |
| 新易盛   | 300502 | 深交所创业板   |
| 中芯国际 | 688981 | 上交所科创板   |
| 贝特瑞   | 835185 | 北交所         |
| 万达轴承 | 920002 | 北交所（新代码段） |

---

## 十八、数据源说明

### stock_info_a_code_name()

- 来源：东方财富
- 字段：代码、名称
- 特点：数据全面、覆盖全部A股
- 用途：`stock_info.py` 获取A股代码和名称（经 `tools/common/a_stock_cache.py` 本地缓存，仅缓存缺失/过期时调用）

### stock_yjbb_em()

- 来源：东方财富
- 字段：代码、名称、所处行业、净资产收益率、销售毛利率、每股收益等
- 特点：按季度披露，季度内数据稳定
- 用途：`stock_info.py`, `stock_financial.py`, `stock_screen.py` 获取业绩与行业数据（经 `tools/common/a_stock_cache.py` 本地缓存，按季度缓存，仅缓存缺失/过期时调用）

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

| 数据源   | 主要特点                     | 适用场景                     | 使用工具                                                                            |
| -------- | ---------------------------- | ---------------------------- | ----------------------------------------------------------------------------------- |
| 东方财富 | 数据实时、字段丰富、覆盖全面 | 实时行情、财务数据、股权结构 | stock_info.py, stock_quote.py, stock_financial.py, stock_screen.py, stock_equity.py |
| 新浪财经 | 网络稳定、历史数据长         | 历史行情、财务报表           | stock_quote.py, stock_screen.py                                                     |
| 巨潮资讯 | 数据权威、官方来源           | 股本变动、公司信息、财报PDF  | stock_equity.py                                                                     |

---

## 十九、注意事项

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

## 二十、与港股/美股工具的区别

| 特性     | A股工具              | 港股工具       | 美股工具           |
| -------- | -------------------- | -------------- | ------------------ |
| 代码长度 | 6位                  | 5位            | 标准格式（如AAPL） |
| 市场标识 | "a"                  | "hk"           | "us"               |
| 行业筛选 | 支持                 | 暂不支持       | 暂不支持           |
| 财务指标 | 支持                 | 支持           | 支持（yfinance）   |
| 质量筛选 | 支持                 | 支持           | 暂不支持           |
| 股权结构 | 支持                 | 暂不支持       | 暂不支持           |
| 财报下载 | 支持                 | 暂不支持       | 暂不支持           |
| 数据源   | 东方财富、新浪、巨潮 | 东方财富、新浪 | Yahoo Finance      |

---

## 二十一、Python路径

```bash
F:\Anaconda3\envs\Python_3_12_3\python.exe
```

---

## 二十二、常见使用场景

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

### 场景8: 提取财报PDF文字与附表

```bash
# 下载财报 PDF（见"五、stock_equity.py"）
python tools/a_share/stock_equity.py --code 601899 --download-report

# 分类检测（判断是否扫描件、总页数）
python tools/common/pdf_extract.py detect cninfo_reports/601899_2025年报.pdf

# 提取含财务附表的 Markdown 并写盘
python tools/common/pdf_extract.py markdown cninfo_reports/601899_2026半年报.pdf --save-md --out-dir reports/pdf

# 全流程（分类 + 纯文本 + Markdown）
python tools/common/pdf_extract.py all cninfo_reports/601899_2026半年报.pdf --save-md
```

### 场景9: 获取国际货币汇率

```bash
# 列出所有支持的货币对（19个）
python tools/common/fx_rate.py --list

# 获取美元/人民币汇率（默认最近10条）
python tools/common/fx_rate.py --code USDCNY

# 获取欧元/人民币汇率
python tools/common/fx_rate.py --code EURCNY

# 批量获取多个货币对（最多5个）
python tools/common/fx_rate.py --code USDCNY,EURUSD,GBPUSD

# 指定日期范围和记录数（上限50）
python tools/common/fx_rate.py --code USDCNY --start 2026-07-20 --end 2026-08-01 --max-records 20
```

---

## 二十三、局限性说明

1. **数据窗口**：部分公司上市时间较短，财务数据可能不足10年
2. **周期性行业**：周期性行业需用完整周期平均值判断，避免单一年份误导
3. **数据准确性**：免费接口数据可能存在延迟或误差，重要决策需交叉验证
4. **财务报表**：部分公司财务报表数据可能缺失特定字段

---

**文档版本**: v2.5
**更新日期**: 2026-08-10
**变更记录**:

- v2.5 (2026-08-10): 搜索工具章节按重要性重排（anysearch 升首、doubao 第二、exa 第三、tavily 新增专章、web_search 降级兜底）；第13章选型对比全量重写为 5 工具 × 市场矩阵（含角色定位总览、参数速查、市场 × 场景矩阵、通用规范、实测结论、决策流程图、实战推荐表）；网络搜索工具表格更新角色定位；原 13~22 章节顺延为 14~23
- v2.4 (2026-08-09): 新增 anysearch.py 工具说明章节（AnySearch 全域结构化搜索，23 大垂直数据库 + tag 定向），更新网络搜索工具表格与搜索工具选型对比；原十一~二十一章节顺延为十二~二十二
- v2.3 (2026-08-07): 新增 fx_rate.py 汇率工具说明章节（国际主要货币汇率，Akshare优先/yfinance回退），新增常见使用场景9；原十四~二十章节顺延为十五~二十一
- v2.2 (2026-08-06): 新增 pdf_extract.py 工具说明章节（PDF 文字与表格提取），原十三~十九章节顺延为十四~二十
- v2.1 (2026-08-01): 新增 doubao_search.py、web_search.py 工具说明章节与搜索工具选型对比
- v2.0 (2026-07-29): 工具重构到 tools/a_share/ 和 tools/common/ 目录，更新所有路径引用
