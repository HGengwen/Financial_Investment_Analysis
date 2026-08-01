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
| [a-share-data.md](./a-share-data.md) | A股数据获取 | `stock_info.py`、`stock_financial.py`、`stock_quote.py`、`stock_screen.py`、`stock_equity.py` |
| [hk-share-data.md](./hk-share-data.md) | 港股数据获取 | `stock_financial.py`、`stock_quote.py`、`stock_screen.py` |
| [financial-calc.md](./financial-calc.md) | 财务计算与验证 | `financial_rigor.py`（市值验算、交叉验证、估值验算、三情景估值） |
| [web-search-tools.md](./web-search-tools.md) | 网络信息搜索 | `doubao_search.py`（火山引擎，推荐）、`tavily_search.py`（Tavily）、`web_search.py`（阿里云百炼） |
| [report-audit.md](./report-audit.md) | 报告审核与抽检 | `report_audit.py`（15%随机抽样、准出/打回判决） |
| [global-constraints.md](./global-constraints.md) | 全局约束规范 | 误差处理规则、股价复权规范、七条核心约束 |
| [pdf-extraction.md](./pdf-extraction.md) | PDF文档提取 | `pdftotext`、`pdfinfo`、`pdftoppm`（Poppler工具集） |

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

- **版本**：2.0.0（从 v1.0 单文件拆分为多文件架构）
- **创建日期**：2026-07-31
- **维护状态**：活跃维护
