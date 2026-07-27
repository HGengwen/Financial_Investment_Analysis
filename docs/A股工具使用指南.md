# A股数据工具使用指南

本文档介绍如何使用独立的A股数据工具获取A股市场数据。

---

## 工具列表

| 工具文件 | 功能 | 命令示例 |
|---------|------|---------|
| `stock_info.py` | A股信息查询 | `python tools/stock_info.py --search 新易盛` |
| `stock_quote.py` | A股行情数据 | `python tools/stock_quote.py --code 300502` |
| `stock_financial.py` | A股财务指标 | `python tools/stock_financial.py --code 300502` |
| `stock_screen.py` | 质量筛选7条指标 | `python tools/stock_screen.py --code 300502` |
| `stock_equity.py` | 股权结构与财报下载 | `python tools/stock_equity.py --code 601899` |

---

## 一、stock_info.py - A股信息查询

### 功能说明

获取A股上市公司的代码、名称、上市信息等基本信息。

### 使用方法

#### 1. 列出全部A股

```bash
python tools/stock_info.py --list
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
python tools/stock_info.py --search 新易盛
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
python tools/stock_info.py --code 300502
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
python tools/stock_info.py --industry 光模块
```

**说明**: 仅支持A股行业筛选，港股暂不支持。

---

## 二、stock_quote.py - A股行情数据

### 功能说明

获取A股历史K线数据，支持日/周/月线、前/后复权、多数据源。

### 使用方法

#### 1. 获取最近30天数据

```bash
python tools/stock_quote.py --code 300502
```

#### 2. 指定日期范围

```bash
python tools/stock_quote.py --code 300502 --start 20260101 --end 20260710
```

#### 3. 选择复权方式

```bash
# 未复权（默认）
python tools/stock_quote.py --code 300502 --adjust ""

# 前复权
python tools/stock_quote.py --code 300502 --adjust qfq

# 后复权
python tools/stock_quote.py --code 300502 --adjust hfq
```

#### 4. 选择数据源

```bash
# 东方财富（默认）
python tools/stock_quote.py --code 300502 --source eastmoney

# 新浪（国内可达）
python tools/stock_quote.py --code 300502 --source sina
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
python tools/stock_financial.py --code 300502
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
python tools/stock_financial.py --code 300502 --indicator ROE
```

#### 3. 查询多个指标

```bash
python tools/stock_financial.py --code 300502 --indicator 毛利率,净利率
```

#### 4. 查询全部原始指标

```bash
python tools/stock_financial.py --code 300502 --indicator all
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
python tools/stock_screen.py --code 300502
```

#### 2. 多只股票筛选

```bash
python tools/stock_screen.py --code 300502,600519,000858
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
python tools/stock_equity.py --code 601899
```

**返回的数据**:
- 前十大股东（总股本口径）
- 前十大流通股东（流通股本口径）
- 股本结构历史变动
- 公司基础信息

#### 2. 导出为Excel文件

```bash
python tools/stock_equity.py --code 601899 --export
```

#### 3. JSON格式输出

```bash
python tools/stock_equity.py --code 601899 --json
```

#### 4. 下载最新年报PDF

```bash
python tools/stock_equity.py --code 601899 --download-report
```

#### 5. 下载最新半年报PDF

```bash
python tools/stock_equity.py --code 601899 --download-report --report-type semiannual
```

#### 6. 下载最新季报PDF

```bash
python tools/stock_equity.py --code 601899 --download-report --report-type quarterly
```

#### 7. 指定财报保存目录

```bash
python tools/stock_equity.py --code 601899 --download-report --report-dir ./reports
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

## 六、A股代码格式说明

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

## 七、数据源说明

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

## 八、注意事项

### 1. 代码格式

A股代码必须为6位数字字符串，如 `300502`，不要添加 `.SH` 或 `.SZ` 后缀。

### 2. 数据延迟

免费接口数据可能有数分钟延迟，不适合高频交易。

### 3. 访问限制

高频请求可能触发风控，建议增加延时、分批请求。

### 4. 字段差异

不同接口的字段名可能不同（中文/英文），工具已做适配。

### 5. **数据源选择（重要）**

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

## 九、与港股工具的区别

| 特性 | A股工具 | 港股工具 |
|------|---------|---------|
| 代码长度 | 6位 | 5位 |
| 市场标识 | "a" | "hk" |
| 行业筛选 | 支持 | 暂不支持 |
| 财务指标 | 支持（stock_financial.py） | 支持（stock_info_hk.py --financial） |
| 质量筛选 | 支持（stock_screen.py） | 待开发 |
| 股权结构 | 支持（stock_equity.py） | 待开发 |
| 财报下载 | 支持（stock_equity.py） | 待开发 |
| 数据源 | 东方财富、新浪 | 东方财富、新浪 |
| 网络稳定性 | 稳定 | 东方财富接口需重试机制 |

---

## 十、Python路径

```bash
F:\Anaconda3\envs\Python_3_12_3\python.exe
```

---

## 十一、常见使用场景

### 场景1: 快速查询公司信息

```bash
# 搜索公司
python tools/stock_info.py --search 新易盛

# 查询单只股票
python tools/stock_info.py --code 300502
```

### 场景2: 获取历史行情

```bash
# 最近30天行情
python tools/stock_quote.py --code 300502

# 指定日期范围（前复权）
python tools/stock_quote.py --code 300502 --start 20250101 --end 20260710 --adjust qfq
```

### 场景3: 查询财务指标

```bash
# 全部关键指标
python tools/stock_financial.py --code 300502

# 单个指标
python tools/stock_financial.py --code 300502 --indicator ROE
```

### 场景4: 执行质量筛选

```bash
# 单只股票筛选
python tools/stock_screen.py --code 300502

# 多只股票对比筛选
python tools/stock_screen.py --code 300502,600519,000858
```

### 场景5: 获取股权结构数据

```bash
# 获取股权结构数据
python tools/stock_equity.py --code 601899

# 导出为Excel文件
python tools/stock_equity.py --code 601899 --export
```

### 场景6: 下载财报PDF

```bash
# 下载最新年报
python tools/stock_equity.py --code 601899 --download-report

# 下载最新半年报
python tools/stock_equity.py --code 601899 --download-report --report-type semiannual

# 下载最新季报
python tools/stock_equity.py --code 601899 --download-report --report-type quarterly
```

---

## 十二、局限性说明

1. **数据窗口**：部分公司上市时间较短，财务数据可能不足10年
2. **周期性行业**：周期性行业需用完整周期平均值判断，避免单一年份误导
3. **数据准确性**：免费接口数据可能存在延迟或误差，重要决策需交叉验证
4. **财务报表**：部分公司财务报表数据可能缺失特定字段

---

**文档版本**: v1.0
**更新日期**: 2026-07-13