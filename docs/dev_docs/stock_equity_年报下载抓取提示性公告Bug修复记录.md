# stock_equity.py 年报下载抓取"提示性公告"Bug 修复记录

## 概述

- **日期**：2026-08-13
- **涉及文件**：`tools/a_share/stock_equity.py`
- **触发场景**：下载新易盛（300502）2025年报时，`--download-report --report-type annual` 抓取到"关于2025年年度报告披露的提示性公告"（1页，100KB）而非完整年报（170页，2.8MB）
- **影响范围**：所有通过 `--download-report` 下载财报的流程

---

## 一、Bug 描述

### 1.1 表象

```bash
python tools/a_share/stock_equity.py --code 300502 --download-report --report-type annual --report-dir ./reports/新易盛/pdf
# 输出"年报下载成功"，但文件仅 100.16 KB，detect 显示 page_count=1
```

下载到的文件内容是"提示性公告"（仅告知年报将于某日披露），而非年报全文。半年报同样受影响。

### 1.2 根因

`StockEquityData._is_full_report()`（第479行）的排除关键词列表缺少"提示性公告"：

```python
# 修复前
exclude_keywords = ['摘要', '简版', '英文版', 'English', '自愿性披露', '自愿披露']
```

"关于2025年年度报告披露的**提示性公告**"标题含"年度报告"但不含任何排除词，被误判为完整版。两阶段搜索第一轮（require_full=True）找不到真正的完整年报，第二轮（可接受简版）又把它当作备选抓了回来。

---

## 二、修复方案

在第489行 `exclude_keywords` 中补充"提示性/披露提示/更正/补充"：

```python
# 修复后
exclude_keywords = [
    '摘要', '简版', '英文版', 'English',
    '自愿性披露', '自愿披露',
    '提示性', '披露提示', '更正', '补充'
]
```

- **提示性**：覆盖"披露的提示性公告"
- **更正/补充**：排除更正公告（标题如"关于…年报的更正公告"，通常不含完整报表）

---

## 三、验证

修复后重新下载：

```bash
rm -f reports/新易盛/pdf/300502_2025年报.pdf
python tools/a_share/stock_equity.py --code 300502 --download-report --report-type annual --report-dir ./reports/新易盛/pdf
# ✅ 文件大小 2834.39 KB（完整年报，170页）
```

## 四、遗留说明

- 若某公司确实只有"提示性公告"而无完整版（极少见），两阶段搜索仍会在第二轮接受简版作为兜底——这是设计行为
- 2026 半年报在 8 月中旬尚未披露时，工具正确回退到 2025 半年报（符合预期）
