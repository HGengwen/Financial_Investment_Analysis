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

## 高级财务科目（mid-trend-tech-screen 阶段二）

```bash
# 暴露资产负债表/营运指标/员工数等高级科目
python tools/a_share/stock_financial.py --code {代码} --advanced 合同负债,存货,研发费用,员工总数
```

可用科目：合同负债、存货、开发支出、无形资产、应付账款、应付票据及应付账款、预付款项、研发费用、营业成本、支付给职工现金、购建固定资产现金、存货周转天数、应收账款周转天数、应付账款周转天数、员工总数。**无直接接口的科目（员工数/应付账款周转天数等）统一标注缺口，不静默使用错误数据**。

---

## 动量与技术面（trend-tech-screen 阶段三）

```bash
# 计算 250日 SMR 相对强度（同板块百分位）、RSI(50)、MA50/MA200、量能
python tools/a_share/stock_quote.py --code {代码} --momentum

# 自动获取申万一级行业成分做 SMR 截面排名
python tools/a_share/stock_quote.py --code {代码} --momentum --auto-peers
```

申万一级行业映射（`sw_index_first_info` + `index_component_sw`）一次性构建全市场"代码→行业"映射并缓存至 `data/a_share/sector/sw_industry_map.json`（覆盖 5000+ 只，远优于东财行业缓存的当季披露口径）。成分 250 日涨幅距 `stock_zh_a_daily`（新浪）优先、`stock_zh_a_hist`（东财）回退批量。

## 完整画像（trend-tech-screen 阶段三）

```bash
# 输出总市值/流通市值 + 机构覆盖度/研报数
python tools/a_share/stock_info.py --code {代码} --profile
```

- 总市值：百度 `stock_zh_valuation_baidu`（主源）；流通市值：东财 `stock_individual_info_em`（东财不稳时置 None 并标缺口）
- 机构覆盖：东财 `stock_research_report_em`，含研报总数/去重机构/最新日期/近一月研报数

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
