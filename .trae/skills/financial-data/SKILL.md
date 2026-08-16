---
name: financial-data
description: "财务数据获取与交叉验证规范：每个关键数据必须来自两个独立来源，误差>1%须标记。适用于所有涉及企业财务数据的研究。"
disable-model-invocation: true
---
# 财务数据获取与交叉验证规范

本规范适用于所有涉及企业财务数据的研究。**每个关键数据必须来自两个独立来源，误差>1%须标记。**

> "永远不要相信单一数据源。交叉验证是投资研究的基本功。" —— 巴菲特

> "数据误差5%看似不大，但乘上市值就是几十亿的偏差。" —— 李录

## 设计理念

财务数据是投资研究的基石，但数据源之间存在误差：

- **GAAP vs Non-GAAP**：利润数据口径不同
- **汇率换算**：港币/人民币/美元换算时间点不同
- **财年定义**：自然年 vs 财年（如苹果财年10月结束）
- **数据更新滞后**：某平台尚未更新最新一期财报

本Skill为所有投研Skill提供**数据获取标准流程**，确保数据准确性。

---

## 数据源优先级

**核心原则**：优先使用本地工具（基于 yfinance / akshare 库）获取数据，浏览器手动访问作为补充，原始财报作为最终核对依据。

### 美股（PDD、腾讯ADR、网易ADR等）

| 优先级   | 来源                              | URL/命令                                                    | 获取方式                |
| -------- | --------------------------------- | ----------------------------------------------------------- | ----------------------- |
| 1（主）  | **本地工具（yfinance）**    | `python tools/us_stock/stock_financial.py --code AAPL`     | 本地工具，数据源 yfinance |
| 2（副）  | **macrotrends**             | macrotrends.net/stocks/charts/{ticker}                      | 浏览器手动访问          |
| 3（辅）  | **stockanalysis**           | stockanalysis.com/stocks/{ticker}/financials                | 浏览器手动访问          |
| 原始一手 | SEC EDGAR                         | sec.gov/cgi-bin/browse-edgar                                | 10-K / 10-Q 原文        |

### 港股（腾讯0700、网易9999、美团3690等）

| 优先级   | 来源                              | URL/命令                                                    | 获取方式                |
| -------- | --------------------------------- | ----------------------------------------------------------- | ----------------------- |
| 1（主）  | **本地工具**                | `python tools/hk_stock/stock_financial.py --financial 00700` | 本地工具，数据源东方财富/新浪 |
| 2（副）  | **aastocks**                | aastocks.com/tc/stocks/analysis/company-fundamental         | 浏览器手动访问          |
| 3（辅）  | **macrotrends**（ADR代码）  | 腾讯用TCEHY，网易用NTES                                     | 浏览器手动访问          |
| 原始一手 | HKEX披露易                        | hkexnews.hk                                                 | 年报PDF                 |

### A股（三七互娱、吉比特等）

| 优先级   | 来源                              | URL/命令                                                    | 获取方式                |
| -------- | --------------------------------- | ----------------------------------------------------------- | ----------------------- |
| 1（主）  | **本地工具（akshare）**     | `python tools/a_share/stock_financial.py --code 601899`    | 本地工具，数据源 akshare  |
| 2（副）  | **东方财富**                | eastmoney.com → 搜股票代码 → 财务报表                       | 浏览器手动访问          |
| 原始一手 | **巨潮资讯**                | cninfo.com.cn                                               | 通过 `tools/a_share/stock_equity.py --download-report` 下载原始年报/季报PDF |

**原始财报PDF获取与阅读**：

```bash
# 使用 stock_equity.py 下载年报/半年报/季报 PDF
python tools/a_share/stock_equity.py --code 601899 --download-report --report-type annual      # 年报
python tools/a_share/stock_equity.py --code 601899 --download-report --report-type semiannual   # 半年报
python tools/a_share/stock_equity.py --code 601899 --download-report --report-type quarterly    # 季报
```

下载的PDF保存于 `cninfo_reports/` 目录，命名格式：`{股票代码}_{年份}年报.pdf`、`{股票代码}_{年份}半年报.pdf`、`{股票代码}_{年份}{季度}季报.pdf`。

**PDF文档阅读工具（首选 pdf_extract.py）**：

提取 PDF 文字与表格**首选** `tools/common/pdf_extract.py`（基于 pdf-inspector 库，能自动还原财务附表），支持自动乱码检测 + OCR 回退；仅当返回失败（退出码非0 / success=false / 扫描件）时回退 Poppler 工具集。

| 工具 | 功能 | 命令示例 |
| ---- | ---- | -------- |
| `pdf_extract.py` | PDF文字与表格提取（首选） | `python tools/common/pdf_extract.py markdown cninfo_reports/601899_2025年报.pdf --save-md` |
| `pdf_extract.py --force-ocr` | 强制 OCR 提取（Adobe-CNS1 乱码时） | `python tools/common/pdf_extract.py text cninfo_reports/688235_2025年报.pdf --force-ocr --ocr-langs chi_tra+eng` |
| `pdftotext` | 将PDF转换为纯文本（回退） | `pdftotext -layout cninfo_reports/601899_2025年报.pdf 601899_2025年报.txt` |
| `pdfinfo` | 获取PDF文档信息（回退） | `pdfinfo cninfo_reports/601899_2025年报.pdf` |
| `pdftoppm` | 将PDF渲染为图像（回退） | `pdftoppm -png -r 300 cninfo_reports/601899_2025年报.pdf output/page` |

**注意**：
- 首选 `pdf_extract.py` 提取文字与表格；返回失败时才回退 Poppler 工具集（详见 [PDF文档内容提取技能](../tools-scripts/pdf-extraction.md)）
- `pdf_extract.py` 内置自动乱码检测，当 pdf-inspector 提取文本出现乱码（如 Adobe-CNS1 字体编码问题）且 tesseract OCR 可用时，自动触发 OCR 回退
- **繁体中文 PDF**（如百济神州）需使用 `--force-ocr --ocr-langs chi_tra+eng` 指定繁体中文语言包
- 扫描版PDF无法用 pdftotext 提取文本，须用 pdftoppm 渲染为图像后人工核对
- 详细使用指南见下方"工具使用指南 → PDF文档内容提取"章节

**其他说明**：网络搜索禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合（anysearch/doubao/exa/tavily/web_search），详见 [web-search-tools](../tools-scripts/web-search-tools.md)。美股本地工具基于 yfinance 库，A股本地工具基于 akshare 库，港股本地工具基于东方财富/新浪财经接口。

---

## 执行流程

### 第一步：确认上市地点与股票代码

首先确认公司的上市情况：

- **仅A股**：使用 `tools/a_share/stock_info.py` 和 `tools/a_share/stock_financial.py`
- **仅港股**：使用 `tools/hk_stock/stock_financial.py`
- **A+H股**：同时使用A股和港股工具
- **美股**：使用 `tools/us_stock/stock_financial.py`，或通过浏览器手动访问 macrotrends/stockanalysis

### 第二步：获取财务数据

根据上市地点，使用相应的本地工具：

#### A股数据获取

| 工具                                 | 功能                         | 命令示例                                                  |
| ------------------------------------ | ---------------------------- | --------------------------------------------------------- |
| `tools/a_share/stock_info.py`      | A股信息查询                  | `python tools/a_share/stock_info.py --search 紫金矿业`  |
| `tools/a_share/stock_financial.py` | A股财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 601899` |
| `tools/a_share/stock_quote.py`     | A股历史股价                  | `python tools/a_share/stock_quote.py --code 601899`     |
| `tools/a_share/stock_equity.py`    | 股权结构与年报下载           | `python tools/a_share/stock_equity.py --code 601899`    |

**Python路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

**数据源**：东方财富、新浪财经、巨潮资讯

#### 港股数据获取

| 工具                                  | 功能                   | 命令示例                                                       |
| ------------------------------------- | ---------------------- | -------------------------------------------------------------- |
| `tools/hk_stock/stock_financial.py` | 港股信息查询、财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| `tools/hk_stock/stock_quote.py`     | 港股历史K线            | `python tools/hk_stock/stock_quote.py --code 00700`          |
| `tools/hk_stock/stock_screen.py`    | 港股质量筛选           | `python tools/hk_stock/stock_screen.py --code 00700`         |

**数据源**：东方财富、新浪财经

#### 美股数据获取

可使用本地工具，或通过浏览器手动访问：

- **本地工具（推荐）**：`tools/us_stock/stock_financial.py`、`tools/us_stock/stock_info.py`、`tools/us_stock/stock_quote.py`
- **主数据源**：macrotrends.net/stocks/charts/{ticker}
- **副数据源**：stockanalysis.com/stocks/{ticker}/financials
- **原始财报**：sec.gov/cgi-bin/browse-edgar（10-K/10-Q）

| 工具                                  | 功能         | 命令示例                                                 |
| ------------------------------------- | ------------ | -------------------------------------------------------- |
| `tools/us_stock/stock_info.py`      | 美股信息查询 | `python tools/us_stock/stock_info.py --search Apple`   |
| `tools/us_stock/stock_financial.py` | 美股财务指标 | `python tools/us_stock/stock_financial.py --code AAPL` |
| `tools/us_stock/stock_quote.py`     | 美股行情数据 | `python tools/us_stock/stock_quote.py --code AAPL`     |

**数据源**：yfinance

### 第三步：误差计算与标记

对每个财务指标（收入、净利润、毛利率、经营现金流、资产负债率等），分别从**来源1**和**来源2**取数。

```
误差率 = |来源1数值 - 来源2数值| / 来源1数值 × 100%
```

| 误差    | 处理方式                                                             |
| ------- | -------------------------------------------------------------------- |
| ≤ 1%   | ✅ 一致，取来源1数值，标注两个来源                                   |
| 1% ~ 5% | ⚠️ 标记"数据存在差异"，注明两个数值，说明可能原因（汇率/会计口径） |
| > 5%    | ❌ 标记"数据存在重大差异"，必须查原始财报核实，不得直接使用          |

### 第四步：数据呈现格式

每个关键数据必须按以下格式标注：

```
收入：1,239亿元 ✅
  - macrotrends: 1,241亿元
  - stockanalysis: 1,237亿元
  - 误差: 0.3%
```

差异示例：

```
净利润：245亿元 ⚠️ 数据存在差异
  - macrotrends: 245亿元（GAAP）
  - stockanalysis: 278亿元（Non-GAAP）
  - 误差: 13.5% — 原因：会计口径不同（GAAP vs Non-GAAP）
```

---

## 常见差异原因（不一定是数据错误）

| 原因             | 说明                                 |
| ---------------- | ------------------------------------ |
| GAAP vs Non-GAAP | 最常见，尤其是利润类数据             |
| 汇率换算         | 港币/人民币/美元换算时间点不同       |
| 财年定义         | 自然年 vs 财年（如苹果财年10月结束） |
| 合并口径         | 是否含少数股东权益                   |
| 数据更新滞后     | 某平台尚未更新最新一期财报           |

---

## 股价与复权（历史序列必读）

价格有三种口径，混用会让历史股价位置、长期涨幅、历史估值分位全部失真：

| 口径   | 含义                       | 用途                                        |
| ------ | -------------------------- | ------------------------------------------- |
| 不复权 | 实际成交价，除权除息日跳空 | 仅用于"当前时点"快照                        |
| 前复权 | 以最新价为基准回调历史价   | 历史股价对比、N年涨幅、历史PE band 一律用它 |
| 后复权 | 以上市首日为基准前推       | 计算历史总回报/年化收益                     |

**规则**：

1. 涉及历史价格的分析统一用**前复权**，且同一分析内**不得混用**复权与不复权来源。
2. 当前市值/当前PE 用**当前实际股价 × 当前总股本**即可，与复权无关——复权只影响历史序列。
3. 跨越拆股/大比例送转的每股指标（历史EPS、历史股价），必须复权还原后再同比。
4. 总回报/年化收益需计入分红（后复权已含），只看价格涨幅会低估。
5. 增发/回购后市值验算以最新总股本为准（`financial_rigor.py verify-market-cap` 偏差>5% 会提示核对）。

---

## 特别规则

1. **未上市公司**（米哈游、莉莉丝等）：只有一手数据来源时，数据前标记 `[估计]`，不执行交叉验证
2. **季度数据 vs 年度数据**：优先使用年度数据做交叉验证，季度数据部分来源可能有滞后
3. **原始财报优先**：若两个来源均与原始财报（10-K/年报PDF）不符，以原始财报为准，标记来源错误

---

## 工具使用指南

### 本地工具（推荐）

根据上市地点选择相应的工具：

| 市场 | 工具                                  | 功能                      | 命令示例                                                       |
| ---- | ------------------------------------- | ------------------------- | -------------------------------------------------------------- |
| A股  | `tools/a_share/stock_info.py`       | 股票信息查询              | `python tools/a_share/stock_info.py --search 紫金矿业`       |
| A股  | `tools/a_share/stock_financial.py`  | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 601899`      |
| A股  | `tools/a_share/stock_quote.py`      | 历史股价与实时行情        | `python tools/a_share/stock_quote.py --code 601899`          |
| A股  | `tools/a_share/stock_equity.py`     | 股权结构与财报下载        | `python tools/a_share/stock_equity.py --code 601899`         |
| 港股 | `tools/hk_stock/stock_financial.py` | 港股信息与财务指标        | `python tools/hk_stock/stock_financial.py --financial 00700` |
| 港股 | `tools/hk_stock/stock_quote.py`     | 港股历史K线               | `python tools/hk_stock/stock_quote.py --code 00700`          |
| 港股 | `tools/hk_stock/stock_screen.py`    | 港股质量筛选              | `python tools/hk_stock/stock_screen.py --code 00700`         |
| 美股 | `tools/us_stock/stock_info.py`      | 美股信息查询              | `python tools/us_stock/stock_info.py --search Apple`         |
| 美股 | `tools/us_stock/stock_financial.py` | 美股财务指标              | `python tools/us_stock/stock_financial.py --code AAPL`       |
| 美股 | `tools/us_stock/stock_quote.py`     | 美股行情数据              | `python tools/us_stock/stock_quote.py --code AAPL`           |

**Python路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

**数据源**：东方财富、新浪财经、巨潮资讯（A股）；东方财富、新浪财经（港股）；yfinance（美股）

详细使用说明请参考：

- **A股工具**：[docs/A股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/A股工具使用指南.md)
- **港股工具**：[docs/港股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/港股工具使用指南.md)
- **美股工具**：[docs/美股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/美股工具使用指南.md)

### PDF文档内容提取（首选 pdf_extract.py）

下载的财报PDF提取文字与表格**首选** `tools/common/pdf_extract.py`（基于 pdf-inspector 库，支持自动乱码检测 + OCR 回退），仅当返回失败（退出码非0 / success=false / 扫描件）时才回退 Poppler 工具集。完整规范见 [PDF文档内容提取技能](../tools-scripts/pdf-extraction.md)。

#### 年报数据提取工作流

```bash
# 步骤1：下载年报PDF
python tools/a_share/stock_equity.py --code 601899 --download-report

# 步骤2（首选）：用 pdf_extract.py 分类检测 PDF 类型
python tools/common/pdf_extract.py detect 601899_2025年报.pdf
# text_based → 文本版PDF；scanned/mixed 或 scanned=true → 扫描版PDF

# 步骤3（首选）：提取含财务附表的 Markdown 并写盘
python tools/common/pdf_extract.py markdown 601899_2025年报.pdf --save-md --out-dir reports/pdf

# 步骤3（OCR 回退）：若 pdf-inspector 提取乱码，自动触发 OCR 回退
# 也可手动强制 OCR（适用于繁体中文 PDF 如百济神州）
python tools/common/pdf_extract.py text 688235_2025年报.pdf --force-ocr --ocr-langs chi_tra+eng

# 步骤3回退：若 pdf_extract.py 返回失败，回退 Poppler
pdftotext -layout 601899_2025年报.pdf 601899_2025年报.txt   # 文本版
grep -n "净利润\|营业收入\|毛利率\|ROE" 601899_2025年报.txt
pdftoppm -png -r 300 601899_2025年报.pdf output/page          # 扫描版

# 步骤4：与其他来源（东方财富、巨潮资讯）交叉验证
```

#### 注意事项

- **首选** `pdf_extract.py` 提取文字与表格；返回失败（退出码非0 / success=false / 扫描件）时回退 Poppler 工具集
- **自动乱码回退**：`pdf_extract.py` 内置 CJK 占比检测，低于 30% 时自动触发 OCR 回退（需安装 tesseract）
- **繁体中文 PDF**（如百济神州）：建议使用 `--force-ocr --ocr-langs chi_tra+eng` 指定繁体中文语言包
- **扫描版PDF**：`pdf_extract.py` 会返回 scanned 标志；回退 Poppler 后无法用 `pdftotext` 提取文本，须用 `pdftoppm` 渲染为图像后人工核对（或配合 OCR 工具如 tesseract）
- **工具安装**：首选需 `pip install pdf-inspector`；OCR 回退需安装 tesseract + pytesseract + pymupdf；回退需安装 Poppler
- **数据验证**：从PDF提取的数据必须与其他来源交叉验证，特别关注数字、单位、小数点位置
- **文件大小**：高分辨率渲染会生成大量图像（每页1-5MB），建议先低分辨率预览定位页面后再高分辨率渲染

### 精确计算工具

| 工具                                | 功能                              | 命令示例                                                                         |
| ----------------------------------- | --------------------------------- | -------------------------------------------------------------------------------- |
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |

### 国际货币汇率获取

跨市场（A股/港股/美股）估值对比、市值统一口径、财务数据折算时，使用 `tools/common/fx_rate.py` 获取实时汇率（**Akshare 优先，yfinance 回退**，支持 19 个货币对）。

```bash
# 列出所有支持货币对
python tools/common/fx_rate.py --list

# 获取美元/人民币汇率（默认最近 10 条）
python tools/common/fx_rate.py --code USDCNY

# 获取港币/人民币、美元/港币（港股折算到人民币/美元口径）
python tools/common/fx_rate.py --code HKDCNY,USDHKD

# 指定日期范围并限制记录数（超硬上限自动裁剪）
python tools/common/fx_rate.py --code USDCNY --start 2026-07-20 --end 2026-08-01 --max-records 20
```

**汇率换算规范**：

- 跨币种数据（收入/净利润/市值）折算必须用**同一时间点汇率**，避免换算误差
- 港币/人民币/美元换算时，用 `fx_rate.py` 获取当日实时汇率，**不得**使用训练数据中的固定汇率
- 港股 → 人民币用 `HKDCNY`；美元 → 人民币用 `USDCNY`；跨市场对比时统一折算到同一货币口径
- 完整货币对说明见 [A股工具使用指南.md 汇率章节](file:///f:/Financial_Investment_Analysis/docs/A股工具使用指南.md)

### 网络搜索工具

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。完整角色定位、市场×场景选型矩阵、命令速查、多源验证示例见 [web-search-tools](../tools-scripts/web-search-tools.md)。

**财务数据验证场景下的搜索选型**：
- A股：`anysearch --tag finance` 主 + `doubao --finance` 辅
- 港股：`doubao --sites hkexnews.hk` 主 + `tavily` 辅；双源 doubao+tavily
- 美股：`exa --type deep` 主 + `doubao` 辅；双源 exa+doubao

**搜索规范**：

- 使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 搜索结果必须包含数据来源日期；过时数据须标注时效性说明
- 非境内上市须按市场双源验证（港股 doubao+tavily；美股 exa+doubao）
- 关键信息缺失时标注"信息不足"，不得用推测填充

---

## 局限性

1. **网络限制**：网络搜索须使用本地五工具组合（详见 web-search-tools.md），美股数据需通过浏览器手动获取
2. **数据源覆盖**：本地工具主要覆盖A股和港股，美股数据源较少
3. **实时性**：本地工具数据可能滞后1-2天，最新财报建议查原始来源
4. **港股接口稳定性**：东方财富港股接口在中国大陆网络连接不稳定（非地理封锁），工具已内置重试机制

---

## 快速索引

| 场景         | 主要来源                            | 备用来源                       |
| ------------ | ----------------------------------- | ------------------------------ |
| PDD / 拼多多 | macrotrends.net/stocks/charts/PDD   | stockanalysis.com/stocks/pdd   |
| 腾讯         | macrotrends.net/stocks/charts/TCEHY | aastocks（0700.HK）            |
| 网易         | macrotrends.net/stocks/charts/NTES  | aastocks（9999.HK）            |
| 三七互娱     | eastmoney.com（002555）             | cninfo.com.cn                  |
| 吉比特       | eastmoney.com（603444）             | cninfo.com.cn                  |
| Nintendo     | macrotrends.net/stocks/charts/NTDOY | stockanalysis.com/stocks/ntdoy |
| Capcom       | macrotrends（CCOEY）                | stockanalysis（CCOEY）         |
