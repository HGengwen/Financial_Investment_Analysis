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

### 美股（PDD、腾讯ADR、网易ADR等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **macrotrends** | macrotrends.net/stocks/charts/{ticker} | 直接访问，无需注册 |
| 2（副） | **stockanalysis** | stockanalysis.com/stocks/{ticker}/financials | 直接访问，无需注册 |
| 原始一手 | SEC EDGAR | sec.gov/cgi-bin/browse-edgar | 10-K / 10-Q 原文 |

### 港股（腾讯0700、网易9999、美团3690等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **aastocks** | aastocks.com/tc/stocks/analysis/company-fundamental | 直接访问 |
| 2（副） | **macrotrends**（ADR代码） | 腾讯用TCEHY，网易用NTES | 直接访问 |
| 原始一手 | HKEX披露易 | hkexnews.hk | 年报PDF |

### A股（三七互娱、吉比特等）

| 优先级 | 来源 | URL | 获取方式 |
|--------|------|-----|---------|
| 1（主） | **东方财富** | eastmoney.com → 搜股票代码 → 财务报表 | 直接访问 |
| 2（副） | **巨潮资讯** | cninfo.com.cn | 原始年报/季报PDF |

**注意**：由于网络限制，WebSearch/WebFetch 在中国大陆不可用，需使用替代工具。

---

## 执行流程

### 第一步：确认上市地点与股票代码

首先确认公司的上市情况：
- **仅A股**：使用 `tools/a_share/stock_info.py` 和 `tools/a_share/stock_financial.py`
- **仅港股**：使用 `tools/hk_stock/stock_info.py`
- **A+H股**：同时使用A股和港股工具
- **美股**：通过浏览器手动访问 macrotrends/stockanalysis

### 第二步：获取财务数据

根据上市地点，使用相应的本地工具：

#### A股数据获取

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/a_share/stock_info.py` | A股信息查询 | `python tools/a_share/stock_info.py --search 紫金矿业` |
| `tools/a_share/stock_financial.py` | A股财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 601899` |
| `tools/a_share/stock_quote.py` | A股历史股价 | `python tools/a_share/stock_quote.py --code 601899` |
| `tools/a_share/stock_equity.py` | 股权结构与年报下载 | `python tools/a_share/stock_equity.py --code 601899` |

**Python路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

**数据源**：东方财富、新浪财经、巨潮资讯

#### 港股数据获取

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/hk_stock/stock_financial.py` | 港股信息查询、财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| `tools/hk_stock/stock_quote.py` | 港股历史K线 | `python tools/hk_stock/stock_quote.py --code 00700` |
| `tools/hk_stock/stock_screen.py` | 港股质量筛选 | `python tools/hk_stock/stock_screen.py --code 00700` |

**数据源**：东方财富、新浪财经

#### 美股数据获取

由于 WebSearch/WebFetch 不可用，需通过浏览器手动访问：
- **主数据源**：macrotrends.net/stocks/charts/{ticker}
- **副数据源**：stockanalysis.com/stocks/{ticker}/financials
- **原始财报**：sec.gov/cgi-bin/browse-edgar（10-K/10-Q）

### 第三步：误差计算与标记

对每个财务指标（收入、净利润、毛利率、经营现金流、资产负债率等），分别从**来源1**和**来源2**取数。

```
误差率 = |来源1数值 - 来源2数值| / 来源1数值 × 100%
```

| 误差 | 处理方式 |
|------|---------|
| ≤ 1% | ✅ 一致，取来源1数值，标注两个来源 |
| 1% ~ 5% | ⚠️ 标记"数据存在差异"，注明两个数值，说明可能原因（汇率/会计口径） |
| > 5% | ❌ 标记"数据存在重大差异"，必须查原始财报核实，不得直接使用 |

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

| 原因 | 说明 |
|------|------|
| GAAP vs Non-GAAP | 最常见，尤其是利润类数据 |
| 汇率换算 | 港币/人民币/美元换算时间点不同 |
| 财年定义 | 自然年 vs 财年（如苹果财年10月结束） |
| 合并口径 | 是否含少数股东权益 |
| 数据更新滞后 | 某平台尚未更新最新一期财报 |

---

## 股价与复权（历史序列必读）

价格有三种口径，混用会让历史股价位置、长期涨幅、历史估值分位全部失真：

| 口径 | 含义 | 用途 |
|------|------|------|
| 不复权 | 实际成交价，除权除息日跳空 | 仅用于"当前时点"快照 |
| 前复权 | 以最新价为基准回调历史价 | 历史股价对比、N年涨幅、历史PE band 一律用它 |
| 后复权 | 以上市首日为基准前推 | 计算历史总回报/年化收益 |

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

详细使用说明请参考：
- **A股工具**：[docs/A股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/A股工具使用指南.md)
- **港股工具**：[docs/港股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/港股工具使用指南.md)

### PDF文档内容提取（使用 Poppler 工具集）

下载的财报PDF可以使用 **Poppler 工具集** 进行内容提取和分析。

#### Poppler 工具集介绍

Poppler 是一个开源的 PDF 渲染库，提供以下命令行工具：

| 工具 | 功能 | 主要用途 |
|------|------|---------|
| `pdftotext` | 将PDF转换为纯文本 | 提取年报中的文字内容 |
| `pdfinfo` | 获取PDF文档信息 | 查看页数、标题、作者等元数据 |
| `pdftoppm` | 将PDF页面渲染为图像 | 处理扫描版PDF、提取图表 |

#### pdftotext：提取文本内容

```bash
# 基本用法：将PDF转换为文本文件
pdftotext 601899_2025年报.pdf 601899_2025年报.txt

# 保持原始布局（推荐）
pdftotext -layout 601899_2025年报.pdf 601899_2025年报.txt

# 指定页面范围（只提取第10-20页）
pdftotext -f 10 -l 20 -layout 601899_2025年报.pdf 601899_2025年报_部分.txt

# 输出到控制台（便于快速查看）
pdftotext -layout 601899_2025年报.pdf -
```

**在财务数据验证中的应用**：
- **提取财务报表**：从年报中提取资产负债表、利润表、现金流量表
- **查找关键数据**：搜索"净利润"、"营业收入"、"毛利率"等关键词
- **验证数据来源**：与第三方数据源进行交叉验证

#### pdfinfo：获取文档信息

```bash
# 查看PDF基本信息
pdfinfo 601899_2025年报.pdf

# 输出示例：
# Title:          紫金矿业2025年年度报告
# Author:         紫金矿业集团股份有限公司
# Creator:        Microsoft Word
# Producer:       Acrobat Distiller
# CreationDate:   2026-03-15
# Pages:          256
# ...
```

**在财务数据验证中的应用**：
- **确认报告年份**：通过创建日期判断报告是否为最新版
- **预估数据量**：根据页数规划提取工作量

#### pdftoppm：处理扫描版PDF

**重要**：A股年报常为扫描版PDF（图像格式），无法直接用 pdftotext 提取文本，需要使用 pdftoppm 渲染为图像。

```bash
# 将PDF页面渲染为高分辨率PNG图像
pdftoppm -png -r 300 601899_2025年报.pdf output/page

# 渲染指定页面（第50-60页）
pdftoppm -png -r 300 -f 50 -l 60 601899_2025年报.pdf output/page

# 超高分辨率（用于提取图表）
pdftoppm -png -r 600 601899_2025年报.pdf output/page
```

**在财务数据验证中的应用**：
- **处理扫描版年报**：将扫描版PDF转为图像，便于视觉检查
- **提取财务图表**：高分辨率渲染年报中的财务图表、数据表格
- **人工核对**：对关键数据进行人工验证

#### 完整的年报数据提取工作流

```bash
# 步骤1：下载年报PDF
python tools/a_share/stock_equity.py --code 601899 --download-report

# 步骤2：检查PDF类型（文本版 vs 扫描版）
pdftotext -layout 601899_2025年报.pdf - | head -100

# 如果能正常输出文本 → 文本版PDF
# 如果输出乱码或空白 → 扫描版PDF，需要使用 pdftoppm

# 步骤3A（文本版PDF）：提取文本内容
pdftotext -layout 601899_2025年报.pdf 601899_2025年报.txt

# 步骤3B（扫描版PDF）：渲染为图像
mkdir output
pdftoppm -png -r 300 601899_2025年报.pdf output/page

# 步骤4：搜索关键财务数据（文本版）
grep -n "净利润\|营业收入\|毛利率\|ROE" 601899_2025年报.txt

# 步骤5：数据交叉验证
# 将提取的数据与其他来源（东方财富、巨潮资讯）进行对比
```

#### 使用 Poppler 的注意事项

1. **扫描版PDF限制**：
   - 扫描版PDF无法直接提取文本，必须使用 pdftoppm 转为图像
   - 转换后的图像可以用 OCR 工具进一步处理（如 tesseract）

2. **文件大小**：
   - 高分辨率渲染会生成大量图像文件（每页1-5MB）
   - 建议先用低分辨率预览，确定需要的页面后再高分辨率渲染

3. **内容完整性**：
   - 扫描版PDF可能存在字迹模糊、页面倾斜等问题
   - 重要数据建议人工复核，不要完全依赖工具提取

4. **工具可用性**：
   - Poppler 是开源工具，Windows 用户需要安装 Poppler for Windows
   - Linux/macOS 系统通常已预装 Poppler 工具

5. **数据验证原则**：
   - 从PDF提取的数据必须与其他来源进行交叉验证
   - 特别关注数字、单位、小数点位置的准确性

#### 扫描版PDF的替代方案

如果 Poppler 无法满足需求，可以考虑：

1. **OCR工具**：tesseract（开源）、ABBYY FineReader（商业）
2. **在线工具**：Adobe Acrobat Online、Smallpdf
3. **手动处理**：对于关键页面，手动输入数据（确保准确性）

**重要提醒**：无论使用何种工具，提取的数据都需要人工验证，特别是财务数字、百分比等关键信息。

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |

### 网络搜索工具

由于官方 WebSearch/WebFetch 在中国大陆不可用，请使用本地网络搜索工具：

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/web_search.py` | 网络信息搜索（阿里云百炼） | `python tools/common/web_search.py "紫金矿业 2025年净利润"` |

---

## 局限性

1. **网络限制**：WebSearch/WebFetch 在中国大陆不可用，美股数据需通过浏览器手动获取
2. **数据源覆盖**：本地工具主要覆盖A股和港股，美股数据源较少
3. **实时性**：本地工具数据可能滞后1-2天，最新财报建议查原始来源
4. **港股接口稳定性**：东方财富港股接口在中国大陆网络连接不稳定（非地理封锁），工具已内置重试机制

---

## 快速索引

| 场景 | 主要来源 | 备用来源 |
|------|---------|---------|
| PDD / 拼多多 | macrotrends.net/stocks/charts/PDD | stockanalysis.com/stocks/pdd |
| 腾讯 | macrotrends.net/stocks/charts/TCEHY | aastocks（0700.HK） |
| 网易 | macrotrends.net/stocks/charts/NTES | aastocks（9999.HK） |
| 三七互娱 | eastmoney.com（002555） | cninfo.com.cn |
| 吉比特 | eastmoney.com（603444） | cninfo.com.cn |
| Nintendo | macrotrends.net/stocks/charts/NTDOY | stockanalysis.com/stocks/ntdoy |
| Capcom | macrotrends（CCOEY） | stockanalysis（CCOEY） |