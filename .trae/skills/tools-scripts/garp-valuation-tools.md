---
name: garp-valuation-tools
description: "GARP 估值计算核心（1~5 年独立档）：financial_rigor.py 的 7 个估值子命令（roic / incremental-roic / wacc / rule-of-40 / ev-sales / adjusted-peg / dcf）的消费视角参考。回答：GARP 框架第 4 步怎么用这些命令、输出哪些字段、量纲怎么给、坑在哪。禁止 LLM 心算市值、估值与跨源校验，必须调用金融计算工具。"
disable-model-invocation: true
---
# GARP 估值计算核心工具（garp-valuation-tools）

**重要约束**：本文件为 **消费视角**——即调用 `financial_rigor.py` 7 个 GARP 估值子命令时的使用方法参考。**算法与公式的权威登记在 `financial-calc.md`，本文件只回答「GARP 框架第 4 步怎么用这些命令、输出哪些字段、量纲怎么给、坑在哪」**，不重复登记算法公式。

本文件服务于 **GARP 独立档（1~5 年）** 估值环节，与 1~3 年中期（`mid-*`）、10 年长期链在 **口径与档位上物理隔离**。所有命令输出为 JSON，便于结构化消费。

> **禁止 LLM 心算**：市值计算、调整后 PEG、DCF、跨源校验等一律调用本文件列出的命令（工具实测签名与输出字段以 P4-23 阶段一实跑为基准，2026-09-19）。

---

## 一、Python 环境

- **Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`
- **工作目录基准**：`F:/Financial_Investment_Analysis/`
- **调用规范**：`financial_rigor.py` 在 `tools/common/` 下，以 `python tools/common/financial_rigor.py <子命令> …` 调用；如需模块形态可 `python -m tools.common.financial_rigor`。

---

## 二、量纲总约定（**最易出错处，逐命令核对**）

`financial_rigor.py` 的 GARP 估值子命令 **量纲随命令而异**，给错单位会得到灾难性结果（已实测：`wacc --tax-rate 25` 得到 `wacc=-16.0` 的荒谬值）。三条硬约定：

| 量纲 | 含义 | 给参形态 |
| --- | --- | --- |
| **百分点（`35` = 35%）** | 增长率 / 利润率 / 成本 / 税率相关 | 直接给数值，如 `--growth 30`、`--cost-equity 10` |
| **小数（`0.12` = 12%）** | **仅** `wacc --tax-rate` 的取证税率 | 给小数，如 `--tax-rate 0.25` |
| **PE 数值** | 相对估值倍数 | 直接给数值 |

> **核心防错口诀**：除 `wacc --tax-rate` 用小数外，**其余百分比参数一律用百分点**（数值即百分数）。

**逐命令量纲核对清单**（编写示例、消费调用前逐条自检）：
- `roic`：`--nopat`/`--invested-capital` 金额（同币种）、`--wacc` 百分点
- `incremental-roic`：`--nopat-from/-to`、`--invested-capital-from/-to` 金额
- `wacc`：`--cost-equity`/`--cost-debt` 百分点、`--tax-rate` **小数**
- `rule-of-40`：`--revenue-growth`/`--profit-margin`/`--fcf-margin` 百分点，且 margin 二选一
- `ev-sales`：`--market-cap`/`--debt`/`--cash`/`--revenue` 金额（同币种）
- `adjusted-peg`：`--market-cap`/`--core-operating-profit`/`--rnd-expense` 金额、`--growth` 百分点
- `dcf`：`--g-high`/`--g-terminal`/`--r`/`--rf` 百分点、`--fcf` 金额、`--market-cap` 金额、`--shares` 股数

---

## 三、消费方编排映射（**只读 garp-valuation 技能结论**）

GARP 框架第 4 步按公司类型判定主锚工具，再辅以辅助工具。**类型决定主锚**，PEG 阈值以中性宏观为基准（宏观修正见 `garp-macro-tools.md`）。本文件只登记「类型 → 命令」的调用映射，**档位判定由 `garp-valuation` 技能执行**，本文件不重述。

| 公司类型 | 主锚命令 | 说明 |
| --- | --- | --- |
| 快速增长型 | `adjusted-peg` | 用调整后 PEG 作主锚 |
| 高研发投入型 | `ev-sales` + `rule-of-40` | PS/EV-Sales + Rule of 40 |
| 未盈利科技型 | `ev-sales` + `dcf`（研发管线 NPV） | PS/EV-Sales + 研发管线折现 |
| 稳定增长型 | `adjusted-peg`（远期 PE + 隐含 PEG） | 远期 PE 配隐含 PEG |
| 成熟型企业 | `dcf` | 现金流折现，三条硬约束审计 |

**辅助工具**（只降不升）：`pe-percentile`、`implied-growth` 归 `financial-calc.md`；跨档主锚的辅助 `roic`/`incremental-roic`/`wacc` 承载资本回报与折现率。`--type` 取值 `fast` / `rd-heavy` / `pre-profit` / `stable` / `mature`。

> **硬约束**：① 工具内置评级（`tier` / `rating` / `verdict`）**一律不进档位判定**（GARP 框架 `GV-2`）；② 辅助工具**只降不升**（`GV-5`）。

---

## 四、子命令逐条参考

### 4.1 `roic` — 存量资本回报率

**签名**：
```bash
python tools/common/financial_rigor.py roic --nopat NOPAT --invested-capital INVESTED_CAPITAL [--wacc WACC] [--expanding]
```

**输出字段**（实测）：`roic`、`tier`、`verdict`、`tech_adjustment_hint`、`wacc_applied`、`inputs`

**实测样例**（`--wacc` 提供时挂 WACC 判定）：
```bash
python tools/common/financial_rigor.py roic --nopat 12.5 --invested-capital 100 --wacc 8
# → {"roic": 12.5, "tier": "合格", "verdict": "合格（ROIC>WACC 且 ≥10%）", "wacc_applied": true, ...}
```

**边界**（实测）：
- 一票否决：`--nopat 3 --invested-capital 100 --expanding` → `{"roic": 3.0, "tier": "不达标", "verdict": "一票否决（ROIC<5% 且仍扩产）", "wacc_applied": false}`

**消费提示**：`tier` 为工具内置结果，**仅供参考不进档位**；`--expanding` 命中扩产场景须观察一票否决。

### 4.2 `incremental-roic` — 增量资本回报率

**签名**：
```bash
python tools/common/financial_rigor.py incremental-roic --nopat-from N --invested-capital-from C --nopat-to N --invested-capital-to C [--period-from P] [--period-to P]
```

**输出字段**（实测）：`delta_roic`、`verdict`、`period_from`、`period_to`、`delta_nopat`、`delta_invested_capital`、`tech_adjustment_hint`、`inputs`

**实测样例**：
```bash
python tools/common/financial_rigor.py incremental-roic --nopat-from 10 --invested-capital-from 80 --nopat-to 12.5 --invested-capital-to 100 --period-from 2023 --period-to 2024
# → {"delta_roic": 12.5, "verdict": "增量口径结果", "period_from": "2023", "period_to": "2024", "delta_nopat": 2.5, "delta_invested_capital": 20.0, ...}
```

**边界**（实测）：Δ投入资本 ≤ 0 时**分母非法**，降级为 `N/A`：
```bash
python tools/common/financial_rigor.py incremental-roic --nopat-from 10 --invested-capital-from 80 --nopat-to 12 --invested-capital-to 80
# → {"delta_roic": null, "verdict": "增量投入资本为 0，无法计算增量 ROIC（分母非法）", ...}
```

### 4.3 `wacc` — 加权平均资本成本

**签名**：
```bash
python tools/common/financial_rigor.py wacc --equity-value E --debt-value D --cost-equity CE --cost-debt CD --tax-rate T
```

**量纲**：`--cost-equity`/`--cost-debt` 用**百分点**；`--tax-rate`用**小数**（0~1）。已实测量纲错误后果：`--tax-rate 25` → `{"wacc": -16.0, "after_tax_debt_cost": -120.0, "warnings": ["税率 t 超出 [0,1) 区间，异常"]}`。

**输出字段**（实测）：`wacc`、`weights`（`equity`/`debt`）、`after_tax_debt_cost`、`warnings`、`re_reference`、`inputs`

**实测样例**：
```bash
python tools/common/financial_rigor.py wacc --equity-value 800 --debt-value 200 --cost-equity 10 --cost-debt 5 --tax-rate 0.25
# → {"wacc": 8.75, "weights": {"equity": 80.0, "debt": 20.0}, "after_tax_debt_cost": 3.75, "warnings": [], ...}
```

**消费提示**：税率写成百分点是**最隐蔽的量纲坑**（`35` vs `0.35`）；`re_reference` 为权益成本参考说明，供后续 `dcf` 的 `--r` 取用。

### 4.4 `rule-of-40` — Rule of 40 达标判定

**签名**：`--revenue-growth` 必填；`--profit-margin` 与 `--fcf-margin` **二选一**：
```bash
python tools/common/financial_rigor.py rule-of-40 --revenue-growth G [--profit-margin M|--fcf-margin F]
```

**量纲**：均用**百分点**。**须显式标注所选口径**（`margin_type`），不可混用利润口径与自由现金流口径。

**输出字段**（实测）：`rule_of_40`、`passed`、`margin_type`、`verdict`、`warnings`、`inputs`

**实测样例**（FCF 口径）：
```bash
python tools/common/financial_rigor.py rule-of-40 --revenue-growth 30 --fcf-margin 15
# → {"rule_of_40": 45.0, "passed": true, "margin_type": "fcf", "verdict": "通过（Rule of 40 = 45.00 ≥ 40）", ...}
```

**消费提示**：`margin_type` 在报告中必须体现（`profit` / `fcf`），消费方核验时注意口径一致性。

### 4.5 `ev-sales` — EV/Sales 估值

**签名**：
```bash
python tools/common/financial_rigor.py ev-sales --market-cap M --debt D --cash C --revenue R
```

**输出字段**（实测）：`ev`、`ev_sales`、`hint`、`warnings`、`inputs`

**实测样例**：
```bash
python tools/common/financial_rigor.py ev-sales --market-cap 500 --debt 100 --cash 50 --revenue 100
# → {"ev": 550.0, "ev_sales": 5.5, "hint": "EV/Sales 无绝对阈值，需与同业可比（高研发投入/未盈利科技股适用）", ...}
```

**消费提示**：**EV/Sales 无绝对阈值**，须与**≥2 家同业可比**并列表（`GV-3`），禁止用绝对数值断言贵贱；`ev_sales` 需结合可比公司基准解读。

### 4.6 `adjusted-peg` — 调整后 PEG 估值

**签名**：
```bash
python tools/common/financial_rigor.py adjusted-peg --market-cap M --core-operating-profit P --rnd-expense RND --growth G
```

**输出字段**（实测）：`adjusted_pe`、`adjusted_peg`、`tier`、`verdict`、`warnings`、`inputs`

**实测样例**：
```bash
python tools/common/financial_rigor.py adjusted-peg --market-cap 1000 --core-operating-profit 40 --rnd-expense 15 --growth 30
# → {"adjusted_pe": 18.18, "adjusted_peg": 0.61, "tier": "低估", "verdict": "低估（PEG<1，可加仓）", ...}
```

**消费提示**：**只取 `adjusted_peg` 数值，忽略工具 `tier`**（`GV-2`）；调整后 PE 采用「核心经营利润 + 研发费用加回」口径，`--core-operating-profit` 与 `--rnd-expense` 须同币种同口径。

### 4.7 `dcf` — 现金流折现（含三条硬约束审计）

**签名**（`--years-high` / `--years-fade` **必填**，非可选）：
```bash
python tools/common/financial_rigor.py dcf --fcf F --g-high G --years-high N --years-fade N --g-terminal G --r R --shares S --market-cap M [--currency CNY] [--rf RF] [--discrete-risks D]
```

**输出字段**（实测）：`pv`、`per_share`、`margin_of_safety_pct`、`verdict`、`audit`（`passed` / `alerts`）、`warnings`、`inputs`

**实测样例**：
```bash
python tools/common/financial_rigor.py dcf --fcf 10 --g-high 10 --years-high 5 --years-fade 5 --g-terminal 2 --r 9 --shares 100 --market-cap 800 --currency CNY --rf 2.5
# → {"pv": 227.54, "per_share": 2.28, "margin_of_safety_pct": -251.59, "verdict": "高估（市值高于DCF）",
#    "audit": {"passed": false, "alerts": ["C1: 无风险利率 2.50% 与 CNY 的 基准 1.70% 不符"]}, ...}
```

**三条硬约束审计**（继承 `terminal_value.py audit`，`GV-4`）：
- **C1 币种匹配**：`--r` / `--rf` 须与 `--currency` 的基准区间一致（CNY 的 `r` 区间 `[6.0%, 9.0%]`，`--rf` 基准 `1.70%`）
- **C2 `r − g ≥ 5pct`**：折现率与终值增长率之差下限
- **C3 离散风险不得进 `r`/`β`**：`--discrete-risks` 单独列示，**禁止**通过上调 `--r` 消化离散风险

**消费提示**：`audit.passed=false` 时须先复核参数而非直接采用结论；`--g-terminal` 在 CNY 下上限 `2.0%`。**ESG 环境风险导致上调 `--r` 时触发 C1 告警是必然结果**，不得为消警而把 `--r` 调回区间内（见 `garp-governance-tools.md` 的 ESG 折价）。

---

## 五、行情与财务取数（GARP 估值输入）

估值输入（市值 / 利润 / 研发费用 / 自由现金流 / 股数）须来自本地工具，禁止手工估计或 LLM 心算。

| 市场 | 取数命令 | 说明 |
| --- | --- | --- |
| A股 | `python tools/a_share/stock_quote.py --code {代码}` | 行情与市值 |
| A股 | `python tools/a_share/stock_financial.py --code {代码}` | 财务指标（含 `--advanced` 扩展科目） |
| 港股 | `python tools/hk_stock/stock_financial.py --financial {代码}` | 港股财务指标（**注意参数为 `--financial`，非 `--code`**） |
| 港股 | `python tools/hk_stock/stock_quote.py --code {代码}` | 港股历史 K 线与指数 |
| 美股 | `python tools/us_stock/stock_financial.py --code {代码}` | 美股财务指标 |
| 美股 | `python tools/us_stock/stock_quote.py --code {代码}` | 美股行情（日期参数为 `YYYY-MM-DD` 形态） |

**连通性说明与降级**：
- 美股数据源（yfinance）存在 **429 限流**风险，三大报表经 `tools/common/us_stock_cache.py` 本地缓存规避；失败时按 **hit → refresh → stale** 三态降级取旧缓存，须在报告中**标注数据时点**。
- 东方财富接口在中国大陆**连接不稳定**（非地理封锁），工具已内置重试；连续失败时**如实标注「取数失败」并降级为人工核验**，不得用推测填充。
- 缓存 TTL 由 `.env` 的 `STOCK_CACHE_TTL_DAYS` 控制；缓存落地 `data/` 目录。

---

## 六、跨币种折算（**显式折算，禁止隐式**）

`tools/common/fx_rate.py` **仅取汇率、不折算**：
```bash
python tools/common/fx_rate.py --code USDCNY
```

**折算须由 `financial_rigor.py calc` 显式完成**，并在报告中**标注汇率时点**：
```bash
python tools/common/financial_rigor.py calc "1250 * 7.12"   # 示例：USD 市值折算为 CNY
```

**硬约束**：
- 禁止把不同币种的金额直接代入同一命令（如 USD 市值 + CNY 利润）；
- 折算后须注明「汇率 = X（YYYY-MM-DD 取值）」；
- `dcf` 的 `--currency` 决定 C1 审计基准，**折算后的金额与 `--currency` 必须一致**。

---

## 七、已知坑与规避（**逐条实测留证**）

| # | 坑 | 实测表现 | 规避 |
| --- | --- | --- | --- |
| 1 | **工具内置评级不进档位判定** | `roic` 输出 `tier`、`adjusted-peg` 输出 `tier`、各命令输出 `verdict`——这些是**工具内置结果** | 档位一律由 `garp-valuation` 技能按框架阈值判定（`GV-2`）；消费方**只取数值字段**（`roic` / `adjusted_peg` / `ev_sales` / `rule_of_40` / `wacc` / `dcf.pv`） |
| 2 | **`calc` 需 `--expr`，且不支持 `^`** | `calc "2^10"` → 报错 `the following arguments are required: --expr`；补 `--expr` 后 → `❌ 不安全的表达式: 2^10`；`--expr "2**10"` → `1024` | 必须写 `--expr`；幂运算用 `**`，**禁止 `^`**；表达式整体加引号（负号开头同样加引号） |
| 3 | **`dcf` 的 C1 对 `--r`/`--rf` 有币种区间约束** | `--currency CNY --rf 2.5` → `C1: 无风险利率 2.50% 与 CNY 的 基准 1.70% 不符`；CNY 下 `--r` 区间 `[6.0%, 9.0%]`、`--g-terminal` 上限 `2.0%` | 先确认币种，再按该币种区间给 `--r`/`--rf`；跨币种标的须先显式折算（§六） |
| 4 | **ESG 上调 `--r` 触发 C1 告警是必然结果** | 按 `garp-governance-tools.md` 的 ESG 折价上调贴现率后，`--r` 可能越出币种区间 → C1 告警 | **不得为消警而下调 `--r`**；应在报告中说明「告警源于 ESG 风险溢价叠加」，并保留审计留痕 |
| 5 | **`--discrete-risks` 必须 `风险名:归属` 格式**（实测新增） | `--discrete-risks "客户集中度风险"` → `C3: '客户集中度风险' 格式应为 风险名:归属` | 用 `风险名:归属`；**合法归属**：`情景` / `尾部档` / `概率`（通过）；`未建模`（告警，须写入报告限制章节）；`折现率` / `r` / `beta` / `β`（**禁止**，离散风险不得进折现率） |
| 6 | **`wacc --tax-rate` 用小数，其余百分比用百分点** | `--tax-rate 25` → `wacc=-16.0`、`after_tax_debt_cost=-120.0` 且带告警 | 参见 §二 量纲总约定；给参后核对 `warnings` 是否为空 |
| 7 | **`rule-of-40` 的 margin 二选一** | `--profit-margin` 与 `--fcf-margin` 不可同给 | 选一并标注 `margin_type`，报告口径须一致 |
| 8 | **`incremental-roic` 分母非法降级** | Δ投入资本 ≤ 0 → `delta_roic: null` + `verdict` 说明分母非法 | 该场景**降级为 N/A**，不得用存量 ROIC 冒充增量 ROIC |

> **消费总则**：凡 `audit.passed=false` 或 `warnings` 非空，**先复核参数与口径，再决定是否采用结论**；参数错误的结论一律作废，不得「带告警采用」。

---

## 八、相关参考

| 文件 | 关系 |
| --- | --- |
| [financial-calc.md](./financial-calc.md) | **算法与公式权威登记**（7 子命令的算法说明以该文件为准） |
| [garp-macro-tools.md](./garp-macro-tools.md) | 宏观校准：PEG 区间 / 现金下限 / 单只上限的宏观修正 |
| [garp-geo-policy-tools.md](./garp-geo-policy-tools.md) | 地缘-政策-基金矩阵与国产化率四档（GARP 第 0 步 / 第 1 步） |
| [garp-governance-tools.md](./garp-governance-tools.md) | 管理层 / 科研转化 / ESG 折价（ESG 折价直接影响 `dcf` 的 `--r`） |
| [terminal-value.md](./terminal-value.md) | 长期（十年）折现估值；`dcf` 的三条硬约束审计与其 `audit` 同源（`GV-4`） |
| [common-tools-guide.md](./common-tools-guide.md) | 公共工具索引；含「GARP 已知缺口与降级路径」汇总 |

---

## 九、版本信息

- **版本**：1.0.0（新建，覆盖 `financial_rigor.py` 7 个 GARP 估值子命令的消费视角；P4-23）
- **创建日期**：2026-09-19
- **更新日期**：2026-09-19
- **实测基准**：全部命令示例与输出字段来自 2026-09-19 实跑（Python `F:/Anaconda3/envs/Python_3_12_3/python.exe`）
- **维护状态**：活跃维护
- **口径归属**：GARP 独立档（1~5 年），与 `mid-*`（1~3 年）、长期链（10 年）物理隔离