---
name: garp-governance-tools
description: "治理数据评分工具（governance-data）：GARP 框架第3步·支柱三管理层 20 分制（诚信前置+7+7+6，management）与科研转化 20 分制（8+8+4，research），以及第4步 ESG 环境风险折价（esg 三通道修正量），禁止 LLM 心算。"
disable-model-invocation: true
---

# 治理数据评分工具（governance-data）

使用 `tools/specialized/governance_data.py` 将《中长期价值成长（GARP）投资框架》第 3 步·支柱三的两套 20 分制与第 4 步·ESG 环境风险估值折价下沉为可执行命令。

- **只评分/只折价，不取证**：各评分项的「取值判定」是时变项（兑现率/分红率/质押率/研发强度/ROIC 系列数值、以及 ESG 事实判定），本工具**不检索、不判定事实真伪**，只对调用方传入的电平值做确定性评分；实时取证由 `annual_report_parser.py` 的 `governance` 字段与技能编排承接。
- **三子命令**：`management`（管理层 20 分制，含诚信否决闸门）、`research`（科研转化 20 分制，无诚信否决）、`esg`（ESG 环境风险折价修正量）。

---

## Python 环境

- **Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`
- **工作目录基准**：`F:/Financial_Investment_Analysis/`

---

## 已知限制：子命令 `--help` 崩溃（P23-E1 → P5-2 §4.4 已修复）

**已修复（2026-09-19）**：此前三个子命令的 `--help` 均**不可用**，会抛 `ValueError: unsupported format character '?' (0xff0c)`——根因是 argparse 的 `help` 字符串内含未转义的 `%`（被当作格式符解析）。已对 12 处 `help=` 字符串中的 `%（` 转义为 `%%（`，三个子命令与父级 `--help` 现均正常（退出码 0，实测 2026-09-19）。

```bash
# 以下四条现均可用（实测 2026-09-19 退出码 0）
python -m tools.specialized.governance_data --help
python -m tools.specialized.governance_data management --help
python -m tools.specialized.governance_data research --help
python -m tools.specialized.governance_data esg --help
```

> 历史登记（P23-E1，存档）：崩溃仅发生在打印 help 时，直接带参调用原本即正常（如 `... management --fulfillment-rate 72.0 ...` 可直接输出 JSON）。此限制现已在 P5-2 修复。

---

## 子命令一：management —— 管理层 20 分制（诚信前置 + 7+7+6）

```bash
python tools/specialized/governance_data.py management \
  --fulfillment-rate 72.0 \
  --dividend-payout-ratio 35.0 --financing 优 --buyback 优 --pledge-ratio 28.0 \
  --core-focus 优 --strategy-exec 优 --industry-cog 优 \
  --turnover-rate 7.0 --equity-incentive 优 \
  --as-of 2026-09-16

# 纯否决路径（任一命中即放弃，总分无效）
python tools/specialized/governance_data.py management --financial-fraud
```

**诚信否决闸门（不计分，命中即放弃/清仓）**：

| 参数 | 触发条件 |
| --- | --- |
| `--fulfillment-rate`（%，0~100） | < 50 → 否决 |
| `--guidance-misstatement` | 业绩预告重大失真 |
| `--attribution-habit` | 归因习惯异常 |
| `--regulatory-filing` | 监管立案 |
| `--financial-fraud` | 财务造假实锤 |

**20 分制三维子项（7+7+6）**：

| 维度 | 参数 | 计分 |
| --- | --- | --- |
| 对待股东（7） | `--dividend-payout-ratio` | [30,100]=2 / [15,30)=1 / [0,15)=0 |
| | `--financing` / `--buyback`（优/中/差） | 优=2 / 中=1 / 差=0 |
| | `--pledge-ratio` | ≤50=1 / >50=0（预警） |
| 战略执行力（7） | `--core-focus`（优/中/差） | 优=3 / 中=1 / 差=0 |
| | `--strategy-exec` / `--industry-cog`（优/中/差） | 优=2 / 中=1 / 差=0 |
| 稳定性与激励（6） | `--turnover-rate` | <10=2 / [10,20)=1 / ≥20=0 |
| | `--equity-incentive`（优/中/差） | 优=2 / 中=1 / 差=0 |
| | `--insider-abnormal`（异常增减持） | 无异常=2 / 异常=0 |

**输出（JSON）**：`integrity_veto` / `integrity_veto_reasons` / `total` / `verdict`（重仓/观察/放弃）/ `position_note` / `score_breakdown` / `data_as_of`。三档：`total≥15` 重仓；`10≤total<15` 观察（单只≤5%，不重仓）；`<10` 放弃。

---

## 子命令二：research —— 科研转化 20 分制（8+8+4，无诚信否决）

```bash
python tools/specialized/governance_data.py research \
  --rd-intensity 18.0 --rd-intensity-rising \
  --capitalization-rate 12.0 --rd-personnel-ratio 32.0 \
  --patent-quality 优 --new-product-revenue-ratio 25.0 \
  --commercialization-cycle 优 --project-milestone 优 \
  --roic 16.0 --wacc 8.0 --incremental-roic 19.0 \
  --as-of 2026-09-16
```

**三维子项（8+8+4）**：

| 维度 | 参数 | 计分 |
| --- | --- | --- |
| 研发投入（8） | `--rd-intensity` + `--rd-intensity-rising` | ≥15 且提升=3 / ≥15 未提升=2 / <15=0 |
| | `--capitalization-rate` | <30=2 / ≥30=0 |
| | `--rd-personnel-ratio` | ≥30=3 / [15,30)=1 / <15=0 |
| 研发产出（8） | `--patent-quality` / `--commercialization-cycle` / `--project-milestone`（优/中/差） | 优=2 / 中=1 / 差=0 |
| | `--new-product-revenue-ratio` | ≥20=2 / [10,20)=1 / <10=0 |
| 资本回报（4） | `--roic` vs `--wacc` | 严格 `roic>wacc`=2，否则 0 |
| | `--incremental-roic` vs `--roic` | 严格 `增量>存量`=2，否则 0 |

**资本回报缺省降级**：`--roic`/`--wacc`/`--incremental-roic` 缺省 → 对应子项 0 分 + `warning`（不报错、不猜）。`--roic` 为主要输入，数值引用 `financial_rigor.py roic/incremental-roic/wacc` 结果透传，本工具不重算 ROIC。

**输出（JSON）**：`total` / `verdict` / `position_note` / `score_breakdown` / `warning` / `data_as_of`。**无 `integrity_veto` 字段**。三档与 `management` 同：≥15 重仓 / 10~14 观察 / <10 放弃。

> 科技股「管理层 + 科研转化两套都须≥15」的合成由 `garp-management`（P4-6）技能编排承担，本工具只输出单套 verdict。

---

## 子命令三：esg —— ESG 环境风险估值折价（三通道修正量）

```bash
python tools/specialized/governance_data.py esg \
  --env-risk-level 高 --transition-pathway 无 \
  --stranded-asset --esg-tail --position-cap-base 20.0 \
  --as-of 2026-09-16
```

| 参数 | 取值 | 说明 |
| --- | --- | --- |
| `--env-risk-level`（必填） | 高/低 | 高=高碳排放/高环境风险行业 |
| `--transition-pathway` | 明确/无（默认 无） | 是否明确碳减排承诺与可验证转型路径 |
| `--stranded-asset` | flag | 是否面临搁浅资产风险 |
| `--esg-tail` | flag | ESG 评级是否行业尾部/最低档 |
| `--position-cap-base` | %（0~100，默认 20） | 单只仓位上限基线 |

**三通道输出（JSON）**：

| 通道 | 字段 | 规则 |
| --- | --- | --- |
| 估值折价 | `discount_factor` | 高+无=0.85；高+明确=0.95；低=1.00；搁浅再 −0.05（下限 0.80） |
| | `discount_pct` | `(1-discount_factor)×100` |
| 贴现率上调 | `discount_rate_adj_bps` | 搁浅命中=150，否则 0（回显区间 `[100,200]`） |
| 仓位下调 | `position_cap_downgrade` | 高环境风险 或 esg-tail 任一命中 =5.0（20%→15%）；不叠加 |

> 折价是在基本面估值之上**再打一次折扣**，不替代多工具估值；由 `garp-valuation`（P4-5）技能把 `discount_factor`/`discount_rate_adj_bps`/`position_cap_downgrade` 叠加到估值结论与仓位上限上。

---

## 输入校验（严格校验，非法即非零退出）

- 定性档位：`management`/`research` 取 `优/中/差`；`esg` 取 `高/低`、`明确/无`。
- 百分比：评分项 0~100；`--roic`/`--wacc`/`--incremental-roic` 允许负值；`--position-cap-base` 0~100。
- 任一非法均打印 `错误：...` 并返回退出码 1（fail-fast，不猜）。

---

## 相关参考

- [公开工具索引](./common-tools-guide.md)
- [年报结构化抽取](./annual-report-parser.md)（`governance` 字段供本工具取值）
- [财务计算与验证](./financial-calc.md)（`roic`/`incremental-roic`/`wacc` 供 `research` 透传）
- [GARP 估值计算核心](./garp-valuation-tools.md)（ESG 折价的 `discount_rate_adj_bps` 直接影响其 `dcf --r`）

---

## 版本信息

- **版本**：1.2.0（P5-2 §4.4 修复 U1：12 处 `help=` 字符串 `%`→`%%` 转义，三子命令 `--help` 恢复正常；撤销 1.1.0 的「已知限制 + 规避形态」登记（P23-E1）；P5-2）
- **创建日期**：2026-09-16
- **更新日期**：2026-09-19