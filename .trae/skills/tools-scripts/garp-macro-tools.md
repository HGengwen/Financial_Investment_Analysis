---
name: garp-macro-tools
description: "宏观校准引擎（macro-calibrator）：GARP 框架宏观三表（利率/PEG、经济/仓位、美林矩阵）逐格硬编码查表（stage）+ 宏观指标取数与利率/经济阶段软判定（data）+ 按美林四档校准 PEG/现金/单只上限（calibrate），禁止 LLM 心算。"
disable-model-invocation: true
---

# 宏观校准引擎（macro-calibrator）

使用 `tools/specialized/macro_calibrator.py` 作为《中长期价值成长（GARP）投资框架》第五部分·四「宏观环境适配」的**权威数据结构载体与校准中枢**。

- **权威口径唯一来源**：框架第五部分·四（行 687-747），本工具不臆造框架未显式给出的数值（一律 `None`）。
- **主键**：美林四档「衰退 / 复苏 / 过热 / 滞胀」，直接查表、零换算、零心算。
- **默认零网络**：`stage` / `calibrate` 为纯查表 + 精确数值比较；仅 `data`（及 `--no-cache`）触发 akshare 拉取。

---

## Python 环境

- **Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`
- **工作目录基准**：`F:/Financial_Investment_Analysis/`

---

## 子命令一：stage —— 按美林四档查宏观三表

```bash
python tools/specialized/macro_calibrator.py stage --stage 复苏
python tools/specialized/macro_calibrator.py stage --stage 滞胀 --markdown
```

- `--stage`：美林四档，枚举 `衰退 / 复苏 / 过热 / 滞胀`（必填）。
- `--markdown`：在 JSON 之外追加打印人类可读 Markdown 三张表（可选）。

**输出（JSON）**：`stage` + 三张子表 `rate_stage` / `econ_stage` / `merrill_stage` + 聚合字段 `peg_interval` / `cash_floor` / `single_cap`（默认验证后档）。

---

## 子命令二：data —— 取宏观指标 + 阶段软判定

```bash
python tools/specialized/macro_calibrator.py data
python tools/specialized/macro_calibrator.py data --no-cache
```

- `--no-cache`：跳过缓存有效期检查，强制从 akshare 刷新并覆写缓存。
- 缓存文件：`data/macro/macro_snapshot.json`；TTL 默认 7 天，可由 `.env` 的 `MACRO_CACHE_TTL_DAYS` 覆盖；刷新失败且无旧缓存时整体报错。

**输出（JSON）**：`data_ts` / `rate_stage`（利率阶段软判定）/ `econ_stage`（美林经济阶段软判定）/ `indicators`（6 指标）/ `source` / `degraded` / `cache_status`（hit/refresh/stale）/ `search_hints`（指标缺失时的搜索提示）。

**指标清单**：`cn_10y_yield`（10Y 国债收益率，含 6 月趋势）、`pmi_manufacturing`、`cpi_yoy`、`ppi_yoy`、`social_financing_increment`、`credit_impulse`（社融 TTM 同比派生，公式落盘）。

> **软判定边界（重要）**：`data` 的利率/经济阶段判定与 `calibrate --from-data` 带入的 stage 均为**非权威启发式**，一律 `manual_review = true`、`confidence = 低`。框架正文只给定性规则、未给显式数值阈值，软判定结果**必须人工确认后定稿**，不替代人工宏观判断。

---

## 子命令三：calibrate —— 按 stage 校准 PEG / 现金 / 单只上限

```bash
# 显式指定 stage（推荐，默认为此）
python tools/specialized/macro_calibrator.py calibrate \
  --stage 复苏 --peg 1.3 --current-cash 15 --single-stake 12

# 从 data 缓存软判定带入 stage（可选，附 manual_review=true）
python tools/specialized/macro_calibrator.py calibrate \
  --from-data --peg 1.3 --current-cash 15 --single-stake 12

# 指定单只上限档位（默认 verified）
python tools/specialized/macro_calibrator.py calibrate \
  --stage 过热 --peg 1.1 --current-cash 26 --single-stake 8 --stake-tier initial
```

- `--stage` / `--from-data`：**二选一（互斥，必填其一）**。`--from-data` 从 `data` 缓存带入软判定 stage，不触发网络刷新。
- `--peg`：标的当前调整后 PEG（> 0，必填）。
- `--current-cash`：当前现金占总资产百分比（0~100，必填）。
- `--single-stake`：当前标的占总资产百分比（0~100，必填）。
- `--stake-tier`：单只上限档位 `initial / verified / absolute`，默认 `verified`。

**输出（JSON）**：回显输入 + `calibrated_peg_verdict` + 现金校准字段（`cash_floor` / `cash_floor_min` / `cash_ok` / `cash_gap`）+ 单只校准字段（`single_cap_upper` / `single_cap_value` / `single_cap_ok` / `single_cap_gap` / `single_caps` / `industry_cap`）+ 可审计 `validation`。

**validation 字段**：`stage_source`（explicit / soft_infer）、`inputs`、`rate_source`、`econ_source`、`peg_compare`、`cash_compare`、`single_compare`、`note`；`--from-data` 时追加 `manual_review = true`。

---

## 量化口径（三张数值常量表）

> 三表逐格来自框架权威原文，禁止 LLM 心算；任何实现与框架正文不一致时以框架正文为准。

### PEG 校准阈值（`CALIBRATE_PEG`）

| 阶段 | 合理买入上限 peg_ceiling | 低估 peg_under | 高估 peg_over |
| --- | ---: | ---: | ---: |
| 衰退 | 1.0 | 未给（None） | 未给（None） |
| 复苏 | 1.5 | 1.2 | 1.5 |
| 过热 | 1.0 | 0.7 | 1.2 |
| 滞胀 | 0.8 | 未给（None） | 未给（None） |

**PEG verdict 判定顺序**：低估（可加仓）→ 合理买入 → 高估（减机动仓）→ 合理偏贵（持有不加仓）→ 超出合理上限（不新建仓）；全局红线 `peg > 2.0` 附加 `red_flag`（不因降息取消）。

### 现金下限最小值（`CALIBRATE_CASH_FLOOR`，占总资产 %）

| 阶段 | 现金下限 |
| --- | ---: |
| 衰退 | 30% |
| 复苏 | 10% |
| 过热 | 25% |
| 滞胀 | 40% |

> 复苏档现金下限在估值分位 >80% 时提高至 20%~30%；本工具未引入分位输入，`calibrate` 的 `validation.note` 会提示人工复核。

### 单只上限三档 + 单一行业上限（`CALIBRATE_SINGLE_CAP`，占总资产 %）

| 阶段 | initial | verified | absolute | 行业上限 |
| --- | ---: | ---: | ---: | ---: |
| 衰退 | 8% | 12% | 15% | 30% |
| 复苏 | 10% | 15% | 20% | 40% |
| 过热 | 8% | 12% | 15% | 25% |
| 滞胀 | 6% | 10% | 12% | 20% |

---

## 输入校验（严格校验，非法即非零退出）

- `stage` 必须为美林四档；`stake_tier` 必须为 `initial/verified/absolute`。
- `--peg` 须 > 0（NaN 拒绝）；`--current-cash` / `--single-stake` 须在 0~100。
- 任一输入非法均打印 `❌ ...` 并返回退出码 1。

---

## 相关参考

- [公共工具索引](./common-tools-guide.md)
- [财务计算与验证](./financial-calc.md)（PEG 计算核心 `adjusted-peg`，供 `--peg` 取值）

---

## 版本信息

- **版本**：1.0.0（新建，覆盖 `macro_calibrator.py` stage / data / calibrate 三子命令，Phase 2）
- **创建日期**：2026-09-15
- **更新日期**：2026-09-15