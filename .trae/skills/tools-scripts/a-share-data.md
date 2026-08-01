---
name: a-share-data
description: "A股数据获取工具：提供A股股票信息查询、财务指标、行情数据、质量筛选、股权结构与财报PDF下载等工具的使用规范。"
disable-model-invocation: true
---

# A股数据获取工具

数据源：东方财富、新浪财经、巨潮资讯

---

## Python 环境

- **Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`
- **工作目录基准**：`F:/Financial_Investment_Analysis/`

---

## 工具清单

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/a_share/stock_info.py` | A股信息查询 | `python tools/a_share/stock_info.py --search {公司名}` |
| `tools/a_share/stock_financial.py` | A股财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code {股票代码}` |
| `tools/a_share/stock_quote.py` | A股行情数据 | `python tools/a_share/stock_quote.py --code {股票代码}` |
| `tools/a_share/stock_screen.py` | 质量筛选7条指标 | `python tools/a_share/stock_screen.py --code {股票代码}` |
| `tools/a_share/stock_equity.py` | 股权结构与财报PDF下载 | `python tools/a_share/stock_equity.py --code {股票代码}` |

---

## 财报PDF下载

```bash
# 下载年报/半年报/季报（从巨潮资讯网）
python tools/a_share/stock_equity.py --code {股票代码} --download-report

# 下载的文件默认保存在 ./cninfo_reports/ 目录
# 文件命名：{股票代码}_{年份}年报.pdf，如 601899_2025年报.pdf
```

下载后的 PDF 提取流程详见 [PDF文档提取技能](./pdf-extraction.md)。

---

## 相关技能

- [港股数据获取](./hk-share-data.md)
- [财务计算与验证](./financial-calc.md)
- [公共工具索引](./common-tools-guide.md)

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-07-31
