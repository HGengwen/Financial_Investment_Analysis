---
name: report-audit
description: "报告审核与数据抽检工具：使用 report_audit.py 对研究报告执行15%随机抽样数据核验，偏差≤1%准出，>1%打回修正。"
disable-model-invocation: true
---

# 报告审核与数据抽检（准出流程）

报告写入后必须执行数据抽检，通过方可发布。

---

## Step 1：提取抽检清单

```bash
# 提取抽检清单（15%随机抽样）
python tools/common/report_audit.py extract \
  --report {报告文件路径}
```

---

## Step 2：取数核验

按 [financial-data](../financial-data/SKILL.md) 技能规范，对清单每项从可靠信源取数。

关键数据来源优先级：
- **A 股**：东方财富（主） -> 巨潮资讯（副） -> 年报 PDF（原始一手）
- **港股**：aastocks（主） -> macrotrends/ADR（副） -> HKEX披露易（原始一手）
- **美股**：macrotrends（主） -> stockanalysis（副） -> SEC EDGAR（原始一手）

---

## Step 3：输出判决

```bash
# 输出准出/打回判决
python tools/common/report_audit.py verdict \
  --results '<填好的JSON>' \
  --report {报告文件名}
```

---

## 判决规则

| 判决 | 条件 | 后续动作 |
|------|------|---------|
| **【准出】** | 所有抽检点偏差 ≤ 1% | 报告可发布 |
| **【打回】** | 任意点偏差 > 1% | 修正后重新抽检 |

---

## 相关技能

- [财务计算与验证](./financial-calc.md)
- [全局约束规范](./global-constraints.md)
- [公共工具索引](./common-tools-guide.md)

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-07-31
