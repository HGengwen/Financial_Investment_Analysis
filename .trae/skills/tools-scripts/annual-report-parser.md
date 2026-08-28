---
name: annual-report-parser
description: "年报结构化抽取工具：从 pdf_extract.py 产出的年报 markdown 中定向抽取员工情况、子公司列表、研发投入、收入分部、新品收入占比、供应链风险等结构化JSON，为人才维度与地缘Y轴评估提供数据，禁止LLM手工挖文本。"
disable-model-invocation: true
---

# 年报结构化抽取工具

使用 `annual_report_parser.py` 从 `pdf_extract.py` 产出的年报 markdown 中**定向抽取结构化字段**，替代 LLM 逐字阅读与手工摘录。

> 定位为"辅助结构化预抽取"：每项字段带 `confidence` 与源文本摘录，缺失字段置 `None` 并通过 `warnings` 标注，**不猜测**。

---

## Python 环境

- **Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`
- **工作目录基准**：`F:/Financial_Investment_Analysis/`

---

## 命令行用法

```bash
# 输出中文可读摘要
python tools/common/annual_report_parser.py {年报md路径}

# 输出纯 JSON（避免 Windows 控制台编码问题）
python tools/common/annual_report_parser.py {年报md路径} --output-json
```

其中 `{年报md路径}` 为 `pdf_extract.py` 输出的 markdown（如 `cninfo_reports/extracted/002709_2025年报.md`）。

---

## 结构化字段说明

抽取的 JSON 含以下六大块：

| 块 | 关键字段 | 支撑指标 |
|------|---------|---------|
| `employees` | total_employees / rd_staff_count / rd_staff_ratio / degree（硕博/本科/其他） | 人才密度 J、研发占比 |
| `subsidiaries` | subsidiaries[{name, relation, overseas}] / overseas_count | 地缘 Y 轴海外实体评估 |
| `rd` | rd_total_amount / rd_intensity / rd_capitalization_amount / rd_capitalization_rate | 研发转化 E/H |
| `revenue_segments` | segments[{dimension, name, amount, ratio}]（按产品/地区/销售模式） | 景气前瞻、收入结构 |
| `new_product` | found / excerpts（新品收入占比文本摘录） | 欧奈尔 N 因子 |
| `supply_chain` | found / excerpts（供应链风险文本摘录） | 反证清单红线 |

`warnings` 数组标注未定位到的章节（如新品收入/供应链未披露为正常情况）。

---

## Python 调用

```python
from tools.common import annual_report_parser
res = annual_report_parser.parse_markdown_file("cninfo_reports/extracted/002709_2025年报.md")
```

---

## 相关技能

- [PDF文档提取](./pdf-extraction.md)
- [景气趋势筛选打分引擎](./trend-tech-screen.md)
- [A股数据获取](./a-share-data.md)
- [公共工具索引](./common-tools-guide.md)

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-08-25
- **更新日期**：2026-08-25