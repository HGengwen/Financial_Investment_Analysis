---
name: common-tools-guide
description: "公共工具索引：为所有投研技能提供工具使用规范的总入口，按单一职责拆分为A股数据、港股数据、财务计算、网络搜索、报告审核、全局约束等独立技能文件。"
disable-model-invocation: true
---

# 公共工具使用指南（索引）

本文件为所有投研技能提供**工具使用规范的总入口**。按单一职责原则，工具指南已拆分为以下独立技能文件，其他技能按需引用对应文件。

---

## 工具技能清单

| 技能文件 | 职责 | 核心工具 |
|---------|------|---------|
| [a-share-data.md](./a-share-data.md) | A股数据获取 | `stock_info.py`（含 `--profile`）、`stock_financial.py`（含 `--advanced`）、`stock_quote.py`（含 `--momentum`/`--auto-peers`）、`stock_screen.py`、`stock_equity.py` |
| [hk-share-data.md](./hk-share-data.md) | 港股数据获取 | `stock_financial.py`（含 `--advanced`）、`stock_quote.py`、`stock_screen.py` |
| [financial-calc.md](./financial-calc.md) | 财务计算与验证 | `financial_rigor.py`（市值验算、交叉验证、估值验算、三情景估值、五维估值 peg/ps-g/pe-percentile/implied-growth） |
| [web-search-tools.md](./web-search-tools.md) | 网络信息搜索（v3.0 五工具） | `anysearch.py`（A股投研首选）、`doubao_search.py`（实时资讯首选）、`exa_search.py`（美股深度研究首选）、`tavily_search.py`（港美股辅源）、`web_search.py`（仅兜底） |
| [report-audit.md](./report-audit.md) | 报告审核与抽检 | `report_audit.py`（15%随机抽样、准出/打回判决） |
| [global-constraints.md](./global-constraints.md) | 全局约束规范 | 误差处理规则、股价复权规范、七条核心约束 |
| [pdf-extraction.md](./pdf-extraction.md) | PDF文档提取 | `pdf_extract.py`（首选，基于 pdf-inspector，支持自动乱码检测 + OCR 回退）；`pdftotext`、`pdfinfo`、`pdftoppm`（Poppler工具集，失败回退） |
| [annual-report-parser.md](./annual-report-parser.md) | 年报结构化抽取（trend-tech-screen 阶段四） | `annual_report_parser.py`（从年报 markdown 定向抽员工/子公司/研发/收入分部/新品/供应链 JSON） |
| [in-research-scan.md](./in-research-scan.md) | 在研重大项目信息获取（trend-tech-screen R8 数据源） | `in_research_scan.py`（gov/patent/bidding/academic/investor/website/research 多渠道一键扫描 + 年报解析，供 `score --r8` 填写） |
| [trend-tech-screen.md](./trend-tech-screen.md) | 景气趋势筛选打分引擎（trend-tech-screen） | `trend_tech_screen.py`（五维打分 + 地缘修正 + 技术面止损 + **R8在研评分** + 评级 + 反证清单，批量两轮） |
| 汇率获取（详见 [A股工具使用指南](../A股工具使用指南.md)） | 国际货币汇率获取 | `fx_rate.py`（Akshare 优先，yfinance 回退，19 个货币对，限流保护） |

> **trend-tech-screen 工具链**：本索引中的 `financial-calc`（新命令）、`a-share-data`/`hk-share-data`（扩展科目/动量/画像）、`annual-report-parser`、`in-research-scan`（在研项目 R8 数据源）、`trend-tech-screen` 构成景气趋势筛选技能的全量数据与计算支撑，详见 [trend-tech-screen.md](./trend-tech-screen.md)。

---

## Python 环境

- **Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`
- **工作目录基准**：`F:/Financial_Investment_Analysis/`

---

## 引用方式

其他技能引用公共工具指南时，根据需要引用具体子技能文件：

```markdown
## 工具使用指南

本技能的工具使用规范详见以下公共技能文件：
- A股/港股数据获取：[A股数据](../tools-scripts/a-share-data.md) / [港股数据](../tools-scripts/hk-share-data.md)
- 财务计算与验证：[financial-calc](../tools-scripts/financial-calc.md)
- 网络信息搜索：[web-search-tools](../tools-scripts/web-search-tools.md)
- 报告审核与抽检：[report-audit](../tools-scripts/report-audit.md)
- 全局约束规范：[global-constraints](../tools-scripts/global-constraints.md)
- 国际货币汇率获取：[fx_rate.py 说明](../A股工具使用指南.md#十三fx_ratepy---国际主要货币汇率)

以下为本技能特有的工具使用注意事项（如有）：
- ...
```

或直接引用本索引文件：

```markdown
## 工具使用指南

本技能的工具使用规范详见 [公共工具索引](../tools-scripts/common-tools-guide.md)。
```

---

## 版本信息

- **版本**：2.2.0（新增 `in-research-scan.md` 在研重大项目信息获取技能；`trend-tech-screen` 条目补充 R8 在研评分）
- **创建日期**：2026-07-31
- **更新日期**：2026-08-26
- **维护状态**：活跃维护
