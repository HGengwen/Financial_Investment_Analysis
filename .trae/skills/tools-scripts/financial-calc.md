---
name: financial-calc
description: "财务计算与验证工具：使用 financial_rigor.py 进行市值验算、关键数据交叉验证、估值指标验算、三情景估值模型等精确计算，禁止LLM心算。"
disable-model-invocation: true
---

# 财务计算与验证工具

所有涉及计算的数据必须通过 `financial_rigor.py` 工具验算，**禁止 LLM 心算**。

---

## 市值验算

```bash
python tools/common/financial_rigor.py verify-market-cap \
  --price {股价} --shares {总股本} --reported {报告市值} --currency {币种}
```

**用途**：手动计算 股价 × 总股本，与报告市值对比，校验数据一致性。

---

## 关键数据交叉验证

```bash
python tools/common/financial_rigor.py cross-validate \
  --field {字段名} --values '{"来源1": 数值, "来源2": 数值}' --unit {单位}
```

**用途**：对同一字段的不同来源数据进行对比，计算误差率。

---

## 估值指标验算

```bash
python tools/common/financial_rigor.py verify-valuation \
  --price {股价} --eps {EPS} --bvps {每股净资产} --fcf-per-share {每股FCF}
```

**用途**：验算 PE、PB、FCF Yield 等估值指标，确保计算准确。

---

## 三情景估值模型

```bash
python tools/common/financial_rigor.py three-scenario \
  --price {股价} --eps {EPS} --shares {总股本亿} \
  --growth {乐观增速} {中性增速} {悲观增速} \
  --pe {乐观PE} {中性PE} {悲观PE}
```

**用途**：基于乐观/中性/悲观三情景，计算目标市值与潜在回报。

---

## 误差处理规则

| 误差率 | 处理方式 |
|--------|---------|
| ≤ 1% | ✅ 一致，取来源1数值，标注两个来源 |
| 1% ~ 5% | ⚠️ 标记"数据存在差异"，注明两个数值，说明可能原因 |
| > 5% | ❌ 标记"数据存在重大差异"，必须查原始财报核实，不得直接使用 |

---

## 相关技能

- [报告审核与数据抽检](./report-audit.md)
- [全局约束规范](./global-constraints.md)
- [公共工具索引](./common-tools-guide.md)

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-07-31
