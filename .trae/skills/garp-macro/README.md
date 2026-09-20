# GARP 宏观环境适配：三表校准 (Garp-Macro)

对指定市场执行 GARP 框架第五部分·四「宏观环境适配」：宏观指标取数与阶段软判定 → 美林四档三表查表 → 收口为**调整后 PEG 合理区间 + 现金仓位下限 + 单只上限（三档）+ 单一行业上限**四项参数。

> 本技能属 **GARP 独立档（1~5 年，五大师：费雪 / 林奇 / 郑希 / 李进 / 欧奈尔）**，与 1~3 年中期链、10 年长期链**物理隔离、功能互补**。定位为**参数时变调节器**——只调「估值容忍度」与「仓位尺度」，**不替代个股基本面判断，不作为择时清仓的依据**；三表参数一律由工具产出，禁止 AI 心算。

---

## 快速开始

### 基本调用方式

```
/garp-macro {市场} [可选参数]
```

例如：

- `/garp-macro A股`
- `/garp-macro A股 --peg 1.3 --current-cash 15 --single-stake 12`
- `/garp-macro 美股 --stage 过热`
- `/garp-macro 港股 --peg 1.1 --current-cash 22 --single-stake 13 --stake-tier initial`

### 可选参数

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `{市场}` | `A股` / `港股` / `美股`，决定 stage 判定的宏观数据源 | `A股` |
| `--stage` | 直接指定美林四档（`衰退`/`复苏`/`过热`/`滞胀`），跳过软判定 | 无 |
| `--peg` | 标的当前调整后 PEG（>0），填则执行标的级校准 | 无 |
| `--current-cash` | 当前现金占总资产 %（0~100），配合 `--peg` | 无 |
| `--single-stake` | 当前标的占总资产 %（0~100），配合 `--peg` | 无 |
| `--stake-tier` | 单只上限档位 `initial` / `verified` / `absolute` | `verified` |
| `--no-cache` | 强制刷新宏观数据缓存 | 关闭 |

---

## 核心功能

把 GARP 宏观三表下沉为一条可执行流程，六步完成：

1. **确认参数与数据基准** — 运行 `date` 确认当天日期；未给 `{市场}` 时取默认 `A股` 并显式声明
2. **宏观指标取数与阶段软判定** — 调 `macro_calibrator.py data`，读回六指标 + `rate_stage` / `econ_stage` 软判定 + 非权威标注为原样透传
3. **人工确认闸门（强制）** — 呈现软判定依据与指标现值，请用户确认 / 修正 stage；未确认前所有参数标「暂定」
4. **三表查表（工具判定）** — 调 `macro_calibrator.py stage`，读回利率表 / 经济表 / 美林矩阵，并**收口为单一结论**
5. **标的级校准（可选）** — 调 `macro_calibrator.py calibrate`，输出 PEG verdict / 现金达标与缺口 / 单只达标与缺口 / `red_flag`
6. **收口输出与下游转接** — 七段式报告 + 数据截止日期 + 边界声明 + 下游转接

### 三表收口规则（强制）

| 宏观阶段 | 利率环境 | 经济档 | 收口要求 |
| --- | --- | --- | --- |
| **衰退** | 降息启动（临时按 1.0） | 衰退档（收紧） | **上限临时收紧至 1.0**（而非降息档 1.5）；待信贷脉冲转正后再切 1.5 |
| **复苏** | 低利率（放宽至 1.5） | 中性 / 复苏档（基准） | 采用放宽档 1.5 |
| **过热** | 加息（收紧至 1.0） | 过热档（收紧） | 采用收紧档 1.0 |
| **滞胀** | 高利率 + 信用收缩（0.8） | 滞胀档（最紧） | 取 **0.8**（PEG ≥ 0.8 不新建仓） |

- **美林时钟定风格与行业 beta，信用周期定总仓位与现金**；二者同向最可靠，**背离时以信用周期为准**。
- **PEG > 2 为严重透支红线，不因降息而取消**。
- **现金下限**：中性 / 复苏 10% 起（不主动低于 10%），估值分位 > 80% 时提高至 20%~30%；进入衰退 / 滞胀 / 过热按矩阵值抬升。

### 按市场分层的 stage 判定输入

| 市场 | 输入 | 工具支持 | 降级 |
| --- | --- | --- | --- |
| **A股** | 中国宏观六指标 | ✅ 全覆盖 | 用户 `--stage` 直填 |
| **港股** | 中国六指标 + 美元流动性锚（搜索工具补） | ⚠️ 仅中国侧 | 冲突按更紧档；否则 `--stage` |
| **美股** | 美债收益率 / 美联储路径 / 美国信用周期 | ❌ 未覆盖 | 用户提供或检索后 `--stage` 直填 |

---

## 使用示例

### 示例 1：A股全景校准（无标的输入）

```
/garp-macro A股
```

产出：`reports/A股/macro-garp-20260916.md`，含六指标与软判定、三表参数收口结论（如软判定为利率降息 + 经济衰退 → 收口至**衰退档**：PEG 上限 1.0、现金 30%~40%、单只 8%/12%/15%、行业 ≤30%）。

### 示例 2：带标的的仓位体检

```
/garp-macro A股 --peg 1.3 --current-cash 15 --single-stake 12
```

产出：追加标的级校准——PEG verdict、现金达标与缺口、单只达标与缺口、`red_flag` 提示。

### 示例 3：指定阶段（工具未覆盖市场）

```
/garp-macro 美股 --stage 过热
```

产出：跳过软判定，直接查表（过热档：PEG 上限 1.0、现金 ≥25%、单只 8%/12%/15%、行业 ≤25%），并标注「stage 由用户提供，未做数据核验」。

### 示例 4：强制刷新宏观数据

```
/garp-macro A股 --no-cache
```

产出：跳过缓存有效期检查，从 akshare 强制刷新并覆写缓存后重新判定。

---

## 依赖

### 本地判定工具（核心）

| 子命令 | 用途 | 命令示例 |
| --- | --- | --- |
| `data` | 中国宏观六指标 + 阶段软判定 | `python tools/specialized/macro_calibrator.py data` |
| `stage` | 按美林四档查三表 | `python tools/specialized/macro_calibrator.py stage --stage 衰退 --markdown` |
| `calibrate` | 标的级校准 | `python tools/specialized/macro_calibrator.py calibrate --stage 衰退 --peg 1.2 --current-cash 25 --single-stake 13` |

- **完整入参与输出字段**见 [garp-macro-tools.md](../tools-scripts/garp-macro-tools.md)。
- `calibrate` 的 stage 来源二选一（互斥）：`--stage`（显式，推荐）或 `--from-data`（从缓存带入软判定，附 `manual_review=true`）。
- 缓存：`data/macro/macro_snapshot.json`，TTL 由 `.env` 的 `MACRO_CACHE_TTL_DAYS` 控制（默认 7 天）。
- **Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`｜**工作目录基准**：`F:/Financial_Investment_Analysis/`

### 网络搜索工具（非 A 股市场锚补充）

| 优先级 | 工具 | 用途 | 命令示例 |
| --- | --- | --- | --- |
| 1 | `exa_search` | 美联储 FOMC / 美财政部 / 美债原文 | `python tools/common/exa_search.py "{关键词}" --type deep` |
| 2 | `anysearch` | 利率 / 信用 / 政策文本深查 | `python tools/common/anysearch.py "{关键词}" --count 10 --zone cn` |
| 3 | `doubao_search` | 实时宏观资讯与舆情 | `python tools/common/doubao_search.py "{关键词}" --finance` |
| 4 | `tavily_search` / `web_search` | 辅源 / 兜底 | `python tools/common/tavily_search.py "{关键词}"` |

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用上述本地工具组合，选型细节见 [web-search-tools.md](../tools-scripts/web-search-tools.md)。

---

## 强制纪律

1. **先定 stage，再谈参数** — stage 未确认前，所有参数一律标注「暂定（待 stage 确认）」
2. **收口优先** — 三表不一致时收口为单一结论并写出说明；衰退期降息不等于放宽
3. **软判定非权威** — `confidence=低` / `manual_review=true` 原样透传，不得改写为确定语气
4. **数据截止日期必填** — 标注 `data_ts` / `cache_status` / `source` / `degraded`；`stale` 或 `degraded=true` 时提示 `--no-cache` 刷新
5. **跨市场不得套用** — 中国指标软判定不得直接充当港股 / 美股 stage
6. **禁止心算** — 参数一律来自工具输出；用户口述参数须标注「由用户提供，未做工具核验」

---

## 核心原则

1. **只调参数，不判价值** — 宏观调节估值容忍度与仓位尺度，不替代个股基本面判断
2. **不做择时清仓** — 不产出卖出信号，也不向卖出类技能转出信号；卖出交 `garp-exit`
3. **按月 / 季复跑** — 宏观参数是时变的，禁止刻舟求剑
4. **引用不重建** — 三表与校准引用工具；PEG 取值引用 `financial_rigor.py adjusted-peg`
5. **不越界** — 不做个股估值、不做组合集中度与相关性分析
6. **不替用户做决策** — 提供参数与依据，宏观阶段与仓位决策由用户确认

---

## 适用与不适用

| 类型 | 场景 |
| --- | --- |
| **适用** | ① 建仓前确定仓位尺度；② 按月 / 季参数复核；③ 为估值环节提供宏观校准后的 PEG 区间；④ 极端阶段（衰退 / 滞胀）的仓位收紧 |
| **不适用** | 个股价值判断（`garp-valuation` / `garp-investment-research`）、买入门槛（`garp-investment-checklist`）、**卖出决策**（`garp-exit`）、地缘政策前置（`garp-geo-policy`）、组合集中度分析（`garp-portfolio-review`） |

---

## 与其他 garp- 技能的关系

| 关系 | 技能 | 说明 |
| --- | --- | --- |
| 前置（联动） | `garp-geo-policy` | 地缘政策前置判定（并行，互不替代） |
| 后置（联动） | `garp-valuation` | 消费宏观校准后的 PEG 合理区间 |
| 后置（联动） | `garp-portfolio-review` | 消费现金下限 / 单只上限 / 行业上限 |
| 后置（联动） | `garp-investment-checklist` | 建仓期仓位尺度约束 |
| 后置（联动） | `garp-trend-tech-screen` | 景气打分输出的宏观 PEG 叠加项 |
| 后置（联动） | `garp-investment-research` / `garp-investment-team` | 综合研判中的宏观适配段落 |
| **不联动** | `garp-exit` | 宏观不作为择时清仓依据，本技能不转出卖出信号 |
| 同级（隔离） | 1~3 年中期链、10 年长期链 | 口径物理隔离，报告文件使用 `macro-garp-` 前缀区分 |

---

## 版本信息

- **版本**：1.0.0（新建，GARP 独立档 Phase 4 P4-2）
- **适用口径**：1~5 年 GARP 独立档（五大师）
- **依赖工具**：`tools/specialized/macro_calibrator.py`（data / stage / calibrate）+ 搜索工具
- **创建日期**：2026-09-16
- **更新日期**：2026-09-16
