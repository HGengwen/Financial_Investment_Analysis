---
name: financial-calc
description: "财务计算与验证工具：使用 financial_rigor.py 进行市值验算、关键数据交叉验证、估值指标验算、三情景估值模型，以及 GARP 计算核心（ROIC/增量ROIC/WACC/Rule of 40/EV-Sales/调整后PEG/DCF）等精确计算，禁止LLM心算。"
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

## 五维估值命令（mid-trend-tech-screen 阶段一新增）

以下四命令为估值安全垫维度与"市值倒推验证"的计算命令，均为纯计算、零网络依赖。

### PEG 估值（林奇）

```bash
python tools/common/financial_rigor.py peg --pe {市盈率TTM} --growth {盈利增速百分点}
```

**判定**：PEG < 1 低估 / 1~1.5 合理 / >1.5 高估。

### PSG 市销率增长比（爆发期专用）

```bash
python tools/common/financial_rigor.py ps-g --ps {市销率} --revenue-growth {营收增速百分点}
```

**用途**：高成长/尚未盈利公司估值校验，触发条件（净利率<5% 或营收增速>50%）由调用方判断。

### PE 历史分位

```bash
python tools/common/financial_rigor.py pe-percentile \
  --pe-series '[{"val":12.5,...}]' --current {当前PE}
```

**用途**：输入历史 PE 序列，输出当前 PE 所处 5 年历史分位。

### 市值隐含业绩倒推验证

```bash
python tools/common/financial_rigor.py implied-growth \
  --market-cap {市值} --target-pe {目标PE} --net-margin {年化净利率,以小数输入,如 0.15} \
  --ttm-revenue {TTM营收} --guidance-growth {公司指引增速上限,以小数输入,如 0.25}
```

**用途**：倒推当前市值隐含的业绩增速要求，并与公司指引增速上限对照，输出红/黄/绿判定（红灯降级）。

> **单位约定**：`--net-margin`（净利率）与 `--guidance-growth`（增速）**一律以小数输入**（如 `0.15` 表示 15%），禁止以百分数输入（如 `15`）。

---

## GARP 计算核心（Phase 1 新增）

以下七命令为中长期价值成长（GARP）框架的计算核心，均为纯计算、零网络依赖，禁止 LLM 心算。

### ROIC 投入资本回报率（GARP 支柱二核心口径）

```bash
python tools/common/financial_rigor.py roic \
  --nopat {税后净营业利润} --invested-capital {投入资本} \
  [--wacc {WACC,百分点,如 8 表示 8%}] [--expanding]
```

- `--wacc`：可选，传入后与 ROIC 对比给出贵/便宜判断；百分数输入（如 8 表示 8%）。
- `--expanding`：仍在拼命扩产 flag；ROIC<5% 时触发一票否决。
- 输出字段：`roic` / `tier`（四档）/ `verdict` / `tech_adjustment_hint` / `wacc_applied` / `inputs`。

### Incremental ROIC 增量投入资本回报率（增量口径）

```bash
python tools/common/financial_rigor.py incremental-roic \
  --nopat-from {上期NOPAT} --invested-capital-from {上期投入资本} \
  --nopat-to {本期NOPAT} --invested-capital-to {本期投入资本} \
  [--period-from 2023] [--period-to 2024]
```

- 公式：增量 ROIC = (NOPAT_to − NOPAT_from) ÷ (投入资本_to − 投入资本_from) × 100%。
- Δ投入资本 ≤ 0 时降级为 N/A（非除零异常）。
- 输出字段：`delta_roic` / `verdict` / `period_from` / `period_to` / `delta_nopat` / `delta_invested_capital` / `tech_adjustment_hint` / `inputs`。

### WACC 加权平均资本成本（资本成本侧）

```bash
python tools/common/financial_rigor.py wacc \
  --equity-value {股权价值E} --debt-value {有息债务D} \
  --cost-equity {股权成本re,百分点} --cost-debt {债务成本rd,税前百分点} \
  --tax-rate {企业所得税税率,小数,如 0.25}
```

- `--cost-equity` / `--cost-debt` 以百分点输入；`--tax-rate` 以小数输入。
- 输出字段：`wacc` / `weights`（equity/debt 权重）/ `after_tax_debt_cost` / `warnings` / `re_reference` / `inputs`。

### Rule of 40 成长质量判定（高研发投入型）

```bash
# 二选一：--profit-margin 或 --fcf-margin（均为百分点）
python tools/common/financial_rigor.py rule-of-40 \
  --revenue-growth {营收增速,百分点} --profit-margin {利润率,百分点}

python tools/common/financial_rigor.py rule-of-40 \
  --revenue-growth {营收增速,百分点} --fcf-margin {FCF利润率,百分点}
```

- Rule of 40 = 营收增速 + 利润率（或 FCF 利润率）≥ 40 视为通过。
- 输出字段：`rule_of_40` / `passed` / `margin_type` / `verdict` / `warnings` / `inputs`。

### EV/Sales 企业价值营收倍数（未盈利科技股）

```bash
python tools/common/financial_rigor.py ev-sales \
  --market-cap {市值} --debt {有息负债} --cash {现金及等价物} --revenue {TTM营收}
```

- EV = 市值 + 有息负债 − 现金及等价物；四参数须同一货币单位。
- 输出字段：`ev` / `ev_sales` / `hint` / `warnings` / `inputs`。

### Adjusted PEG 调整后 PEG（研发费用加回口径）

```bash
python tools/common/financial_rigor.py adjusted-peg \
  --market-cap {市值} --core-operating-profit {核心经营利润} \
  --rnd-expense {当期费用化研发支出} --growth {盈利增速,百分点}
```

- 调整后净利润 = 核心经营利润 + 费用化研发支出；调整后 PE = 市值 ÷ 调整后净利润。
- 输出字段：`adjusted_pe` / `adjusted_peg` / `tier`（四档）/ `verdict` / `warnings` / `inputs`。

### DCF 简化三阶段折现估值（成熟型企业）

```bash
python tools/common/financial_rigor.py dcf \
  --fcf {基准自由现金流} --g-high {高增长增速,百分点} \
  --years-high {高增长年数} --years-fade {过渡年数} \
  --g-terminal {永续终值增速,百分点} --r {折现率,百分点} \
  --shares {总股本} --market-cap {当前市值} \
  [--currency CNY|USD|HKD] [--rf {无风险利率,百分点}] \
  [--discrete-risks "风险名:归属,逗号分隔"]
```

- 增速/折现率/无风险利率均以百分点输入（如 9 表示 9%）。
- `--currency` / `--rf` / `--discrete-risks` 供三条硬约束审计（C1 币种匹配、C2 r−g≥5pct、C3 离散风险不得进 r/β）。
- 输出字段：`pv` / `per_share` / `margin_of_safety_pct` / `verdict` / `audit` / `warnings` / `inputs`。

> **百分点 vs 小数约定**：WACC、股权/债务成本、营收增速、利润/FCF 利润率、增速、折现率、无风险利率一律**百分点输入**（如 8 表示 8%）；企业所得税税率、净利率、指引增速（`implied-growth` 命令）一律**小数输入**（如 0.25 表示 25%）。

> **消费视角参考**：本节登记的是**算法与参数**（权威口径）。「GARP 框架第 4 步怎么调用这 7 个命令、按公司类型选哪个主锚、输出字段怎么读、量纲坑与实测边界（如 `dcf --discrete-risks` 的合法归属值、`calc` 需 `--expr` 且不支持 `^`、工具内置 `tier` 不进档位判定）」详见 [GARP 估值计算核心（garp-valuation-tools）](./garp-valuation-tools.md)。

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
- [GARP 估值计算核心](./garp-valuation-tools.md)（7 子命令的消费视角：编排映射 / 输出字段 / 量纲坑）
- [长期折现估值](./terminal-value.md)（十年尺度；`dcf` 的三条硬约束审计与其同源）

---

## 版本信息

- **版本**：1.3.0（复核 GARP 计算核心 7 子命令登记 + 补消费视角交叉引用 `garp-valuation-tools.md` + 相关技能区补链接；P4-23）
- **创建日期**：2026-07-31
- **更新日期**：2026-09-19
