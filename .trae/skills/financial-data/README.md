# 财务数据获取与交叉验证 (Financial Data)

每个关键数据必须来自两个独立来源，误差>1%须标记

---

## 快速开始

### 基本调用方式

```
/financial-data {公司名或股票代码}
```

例如：
- `/financial-data 紫金矿业`
- `/financial-data 00700`（港股腾讯）
- `/financial-data PDD`（美股拼多多）

---

## 核心功能

为所有涉及企业财务数据的研究提供**数据获取标准流程**，确保数据准确性。本Skill是其他投研Skill的基础规范，提供数据源优先级、误差标记规则、股价复权规范等标准。

### 四步执行流程

1. **确认上市地点与股票代码** — A股/港股/美股/A+H股分流
2. **获取财务数据** — 使用对应市场的本地工具
3. **误差计算与标记** — 两源对比，≤1%一致 / 1-5%标记差异 / >5%重大差异
4. **数据呈现格式** — 每个关键数据标注两个来源+误差率

### 数据源优先级

**核心原则**：优先使用本地工具（基于 yfinance / akshare 库）获取数据，浏览器手动访问作为补充，原始财报作为最终核对依据。

| 市场 | 主数据源（本地工具） | 副数据源（浏览器） | 原始一手来源 |
|------|---------------------|-------------------|-------------|
| 美股 | `tools/us_stock/stock_financial.py`（yfinance） | macrotrends.net / stockanalysis.com | SEC EDGAR（10-K/10-Q） |
| 港股 | `tools/hk_stock/stock_financial.py`（东方财富/新浪） | aastocks.com / macrotrends（ADR） | HKEX披露易（年报PDF） |
| A股 | `tools/a_share/stock_financial.py`（akshare） | eastmoney.com | 巨潮资讯（年报PDF，通过 `stock_equity.py --download-report` 下载） |

---

## 使用示例

### 示例1：获取A股财务数据
```
/financial-data 紫金矿业
```
 使用 `stock_info.py` 查询股票代码，`stock_financial.py` 获取财务指标，与东方财富/巨潮资讯交叉验证

### 示例2：获取港股财务数据
```
/financial-data 00700
```
 使用 `tools/hk_stock/stock_financial.py --financial 00700` 获取腾讯财务指标，与 aastocks 交叉验证

### 示例3：获取美股财务数据
```
/financial-data PDD
```
 使用 `tools/us_stock/stock_financial.py --code PDD`（yfinance）获取数据，或通过浏览器手动访问 macrotrends/stockanalysis，与 SEC EDGAR 原始财报交叉验证

---

## 输出报告

本技能为**基础数据规范型技能**，本身不生成独立报告文件，但其规范适用于所有投研Skill的财务数据呈现。

### 数据呈现格式标准

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

## 验证标准

### 误差处理规则

| 误差率 | 处理方式 |
|--------|---------|
| ≤ 1% | ✅ 一致，取来源1数值，标注两个来源 |
| 1% ~ 5% | ⚠️ 标记"数据存在差异"，注明两个数值，说明可能原因 |
| > 5% | ❌ 标记"数据存在重大差异"，必须查原始财报核实，不得直接使用 |

### 常见差异原因（不一定是数据错误）

| 原因 | 说明 |
|------|------|
| GAAP vs Non-GAAP | 最常见，尤其是利润类数据 |
| 汇率换算 | 港币/人民币/美元换算时间点不同 |
| 财年定义 | 自然年 vs 财年（如苹果财年10月结束） |
| 合并口径 | 是否含少数股东权益 |
| 数据更新滞后 | 某平台尚未更新最新一期财报 |

### 股价与复权规范

| 口径 | 含义 | 用途 |
|------|------|------|
| 不复权 | 实际成交价，除权除息日跳空 | 仅用于"当前时点"快照 |
| 前复权 | 以最新价为基准回调历史价 | 历史股价对比、N年涨幅、历史PE band 一律用它 |
| 后复权 | 以上市首日为基准前推 | 计算历史总回报/年化收益 |

**复权规则**：
1. 涉及历史价格的分析统一用**前复权**，同一分析内不得混用复权口径
2. 当前市值/当前PE 用当前实际股价 × 当前总股本即可
3. 跨越拆股/大比例送转的每股指标，必须复权还原后再同比
4. 总回报/年化收益需计入分红（后复权已含）
5. 增发/回购后市值验算以最新总股本为准

### 特别规则

1. **未上市公司**（米哈游、莉莉丝等）：只有一手数据来源时，数据前标记 `[估计]`，不执行交叉验证
2. **季度数据 vs 年度数据**：优先使用年度数据做交叉验证，季度数据部分来源可能有滞后
3. **原始财报优先**：若两个来源均与原始财报（10-K/年报PDF）不符，以原始财报为准，标记来源错误

---

## 工具依赖

### 本地数据获取工具

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票信息查询 | `python tools/a_share/stock_info.py --search 紫金矿业` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 601899` |
| A股 | `tools/a_share/stock_quote.py` | 历史股价与实时行情 | `python tools/a_share/stock_quote.py --code 601899` |
| A股 | `tools/a_share/stock_equity.py` | 股权结构与财报下载 | `python tools/a_share/stock_equity.py --code 601899` |
| 港股 | `tools/hk_stock/stock_financial.py` | 港股信息与财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| 港股 | `tools/hk_stock/stock_quote.py` | 港股历史K线 | `python tools/hk_stock/stock_quote.py --code 00700` |
| 港股 | `tools/hk_stock/stock_screen.py` | 港股质量筛选 | `python tools/hk_stock/stock_screen.py --code 00700` |
| 美股 | `tools/us_stock/stock_info.py` | 美股信息查询 | `python tools/us_stock/stock_info.py --search Apple` |
| 美股 | `tools/us_stock/stock_financial.py` | 美股财务指标 | `python tools/us_stock/stock_financial.py --code AAPL` |
| 美股 | `tools/us_stock/stock_quote.py` | 美股行情数据 | `python tools/us_stock/stock_quote.py --code AAPL` |

**Python路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

**数据源**：东方财富、新浪财经、巨潮资讯（A股）；东方财富、新浪财经（港股）；yfinance（美股）

详细使用说明请参考：
- **A股工具**：[docs/A股工具使用指南.md](../../docs/A股工具使用指南.md)
- **港股工具**：[docs/港股工具使用指南.md](../../docs/港股工具使用指南.md)
- **美股工具**：[docs/美股工具使用指南.md](../../docs/美股工具使用指南.md)

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |

### 网络搜索工具

由于官方 WebSearch/WebFetch 在中国大陆不可用，请使用本地网络搜索工具。

**工具优先级**（基于上市地点）：

| 上市地点 | 主搜索工具 | 辅助搜索工具 | 说明 |
|---------|-----------|------------|------|
| A股 | `tools/common/doubao_search.py` | `tools/common/web_search.py` | 豆包搜索为推荐首选 |
| 港股/美股 | `tools/common/doubao_search.py` | `tools/common/tavily_search.py` + `tools/common/web_search.py` | 非境内上市需双源验证 |

**搜索规范**：
- 使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 搜索结果必须包含数据来源日期；过时数据须标注时效性说明
- 非境内上市公司须 Doubao + Tavily 双源验证
- 关键信息缺失时标注"信息不足"，不得用推测填充

### PDF文档内容提取（首选 pdf_extract.py）

A股年报/半年报/季报PDF通过 `tools/a_share/stock_equity.py --download-report` 下载：

```bash
# 下载年报/半年报/季报 PDF
python tools/a_share/stock_equity.py --code 601899 --download-report --report-type annual      # 年报
python tools/a_share/stock_equity.py --code 601899 --download-report --report-type semiannual   # 半年报
python tools/a_share/stock_equity.py --code 601899 --download-report --report-type quarterly    # 季报
```

下载的PDF保存于 `cninfo_reports/` 目录，命名格式：`{股票代码}_{年份}年报.pdf`。提取文字与表格**首选** `pdf_extract.py`，返回失败（退出码非0 / success=false / 扫描件）时才回退 Poppler 工具集：

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `pdf_extract.py` | PDF文字与表格提取（首选） | `python tools/common/pdf_extract.py markdown 601899_2025年报.pdf --save-md` |
| `pdftotext` | 将PDF转换为纯文本（回退） | `pdftotext -layout 601899_2025年报.pdf output.txt` |
| `pdfinfo` | 获取PDF文档信息（回退） | `pdfinfo 601899_2025年报.pdf` |
| `pdftoppm` | 将PDF页面渲染为图像（回退） | `pdftoppm -png -r 300 601899_2025年报.pdf output/page` |

**关键提示**：
- 首选 `pdf_extract.py` 提取文字与表格；返回失败时才回退 Poppler 工具集（详见 [PDF文档内容提取技能](../tools-scripts/pdf-extraction.md)）
- 扫描版PDF无法用 `pdftotext` 提取文本，须用 `pdftoppm` 渲染为图像后人工核对
- 从PDF提取的数据必须与其他来源交叉验证
- 详细工作流见 [SKILL.md](./SKILL.md) "PDF文档内容提取"章节

### 美股数据补充获取（浏览器手动）

当本地工具无法获取完整数据时，可通过浏览器手动访问：
- **主数据源**：macrotrends.net/stocks/charts/{ticker}
- **副数据源**：stockanalysis.com/stocks/{ticker}/financials
- **原始财报**：sec.gov/cgi-bin/browse-edgar（10-K/10-Q）

**重要约束**：
- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- A股、港股、美股数据优先使用本地工具获取
- 美股数据可通过浏览器手动访问作为补充
- 港股/美股公司须 Doubao + Tavily 双源验证
- 网络搜索须使用 `--time-range month/week` 限制时间范围

---

## 核心原则

1. **每个关键数据必须来自两个独立来源** — 交叉验证是投资研究的基本功
2. **误差>1%须标记** — 数据误差5%看似不大，但乘上市值就是几十亿偏差
3. **原始财报优先** — 若两个来源均与原始财报不符，以原始财报为准
4. **不虚构数据** — 搜不到就标注"估计"或"数据不足"
5. **数据源标注透明** — 每个数据必须标注来源和误差率
6. **会计口径明确** — 区分 GAAP vs Non-GAAP，注明口径差异原因

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- A股、港股、美股数据优先使用本地工具获取（akshare / 东方财富+新浪 / yfinance）
- 每个关键数据必须来自两个独立来源，误差>1%须标记
- 涉及历史价格的分析统一用前复权，同一分析内不得混用复权口径
- 当前市值/当前PE 用当前实际股价 × 当前总股本即可，与复权无关
- 未上市公司数据前标记 `[估计]`，不执行交叉验证
- 港股/美股公司须 Doubao + Tavily 双源验证
- 网络搜索须使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 扫描版PDF无法直接提取文本，须用 `pdftoppm` 渲染为图像后人工核对
- 从PDF提取的数据必须与其他来源交叉验证
- 关键财务数据须使用 `financial_rigor.py` 验算，禁止 LLM 心算

---

## 局限性说明

- **网络限制**：WebSearch/WebFetch 在中国大陆不可用，美股数据需通过浏览器手动获取
- **数据源覆盖**：本地工具主要覆盖A股和港股，美股数据源较少
- **实时性**：本地工具数据可能滞后1-2天，最新财报建议查原始来源
- **港股接口稳定性**：东方财富港股接口在中国大陆网络连接不稳定（非地理封锁），工具已内置重试机制
- **扫描版PDF限制**：A股年报常为扫描版PDF，可能无法提取文本内容
- 不构成投资建议，仅供学习研究参考

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

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [A股工具使用指南](../../docs/A股工具使用指南.md) — A股工具详细说明
- [港股工具使用指南](../../docs/港股工具使用指南.md) — 港股工具详细说明
- [财报精读](../earnings-review/README.md) — 财报一手资料深度解读
- [财报精读团队](../earnings-team/README.md) — 六Agent团队财报精读

---

## 版本信息

- **版本**：1.1.0
- **创建日期**：2026-07-22
- **最后更新**：2026-08-06（PDF 文档提取首选 `pdf_extract.py`，Poppler 作为失败回退）
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。
