# 估值温度计 (Valuation Thermometer)

用 PEG / PSG / PE 历史分位 / implied-growth 四个工具，输出「显著低估 / 合理 / 偏贵 / 高估 / 严重透支」五档估值温度，并映射到底仓/机动仓操作。属于 1-3 年中期链功能技能，与长期链（10 年 / `quality-screen`）估值口径物理隔离。

---

## 快速开始

### 基本调用方式

```
/valuation-thermometer {公司名}
```

支持两种输入形态：

| 输入方式 | 示例 | 说明 |
|---------|------|------|
| 个股 | `/valuation-thermometer 新易盛` | 单标的估值温度 |
| 个股+代码 | `/valuation-thermometer 新易盛 300502` | 显式指定代码，跨市场明确 |

例如：
- `/valuation-thermometer 新易盛`
- `/valuation-thermometer 腾讯 00700`

---

## 核心功能

对指定公司执行「四工具估值 + 交叉校验」，输出五档温度与底仓/机动仓操作建议。

### 五档温度表（唯一权威口径）

| 档位     | PEG 区间（边界约定） | 操作建议                       |
| -------- | -------------------- | ------------------------------ |
| 显著低估 | PEG < 0.8            | 绝佳买点，底仓可加             |
| 合理     | 0.8 ≤ PEG ≤ 1.2    | 合理买入区间，先建 1/3 底仓    |
| 偏贵     | 1.2 < PEG ≤ 1.5     | 机动仓观望（过渡档，不买不卖） |
| 高估     | 1.5 < PEG ≤ 2.0     | 机动仓减持                     |
| 严重透支 | PEG > 2.0            | 加速清机动仓                   |

> 边界约定：PEG=0.8 归「合理」；PEG=1.2 归「合理」；PEG=1.5 归「偏贵」；PEG=2.0 归「高估」。区间下开上闭（首档除外）。

### 主锚选择规则

| 场景                                  | 主锚                                                                     | 辅助校验                     |
| ------------------------------------- | ------------------------------------------------------------------------ | ---------------------------- |
| 常规增长（增速 >0 且非爆发期）        | PEG                                                                      | PSG、PE 分位、implied-growth |
| 爆发期（净利率 <5% 或 营收增速 >50%） | PSG（<0.5 显著低估 / 0.5~1.0 合理 / >1.0 高估）                          | PEG 降为辅助                 |
| 增速 ≤ 0（PEG 无意义）               | 直接判「不适用 PEG」，转 PSG 或标注「亏损/负增长不适用」                  | PE 分位、implied-growth      |

### 交叉校验与降级规则

- PE 历史分位（<40% 低估 / 40%~60% 合理 / >60% 偏高）与主锚冲突时，**降一档并显式标注原因**；
- implied-growth 红灯（隐含增速 > 指引 ×1.5）时，**主锚下调一档**；黄灯标注「偏贵预警」；绿灯标注「估值未透支」。

---

## 使用示例

### 示例1：常规增长个股

```
/valuation-thermometer 新易盛
```

输出 PEG 主锚档位 + PSG/PE 分位/implied-growth 交叉校验 + 底仓/机动仓操作建议。

### 示例2：爆发期个股（PSG 主锚）

```
/valuation-thermometer {某高增长未盈利/低净利率标的}
```

净利率 <5% 或营收增速 >50% 时，主锚切换为 PSG，PEG 降为辅助。

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 个股估值 | `reports/valuation/{公司名}-valuation-{YYYYMMDD}.md` |

### 报告结构

```markdown
# {公司名} 估值温度计报告（1-3年中期）
## 一、估值结论
## 二、四工具数值表
## 三、档位判定依据
## 四、底仓/机动仓操作建议
## 五、数据来源与口径标注
## 六、不确定性标注
```

---

## 工具依赖

核心计算工具为 **`financial_rigor.py` 四估值命令**（零网络依赖，纯计算），配合三市场数据工具与搜索工具采集输入。

| 用途 | 工具 | 关键参数 |
|------|------|---------|
| PEG | `financial_rigor.py peg` | `--pe --growth` |
| PSG | `financial_rigor.py ps-g` | `--ps --revenue-growth` |
| PE 历史分位 | `financial_rigor.py pe-percentile` | `--pe-series --current` |
| 隐含增速 | `financial_rigor.py implied-growth` | `--market-cap --target-pe --net-margin --ttm-revenue --guidance-growth` |
| 复合增速 | `financial_rigor.py calc` | `--expr` |
| 三情景估值（可选） | `financial_rigor.py three-scenario` | `--price --eps --shares --growth --pe --years --currency` |
| A股财务/行情 | `a_share/stock_financial.py`、`stock_quote.py` | `--code` |
| 港股财务/行情 | `hk_stock/stock_financial.py`、`stock_quote.py` | `--financial`/`--code` |
| 美股财务/行情 | `us_stock/stock_financial.py`、`stock_quote.py` | `--code` |
| 一致预期增速 | `anysearch.py` / `doubao_search.py` / `exa_search.py` | `--tag finance` / `--finance` / `--type deep` |

### 关键约束

- **禁止 LLM 心算**：PEG、复合增速、分位、隐含增速一律走 `financial_rigor.py`。
- **只取数值，不取评级**：`peg` 命令内置的林奇三档评级文字不进入档位判定，仅取数值按五档表二次映射。
- **同口径**：统一 TTM PE + 未来 2 年一致预期增速。

---

## 与 `exit-signal` 的衔接（P4 输入）

本技能输出的 PEG 档位是 `exit-signal` 的 P4 估值透支判定输入：

| valuation-thermometer 输出 | exit-signal P4 动作 |
|---------------------------|---------------------|
| 高估（1.5 < PEG ≤ 2.0）   | 减机动仓            |
| 严重透支（PEG > 2.0）     | 加速清机动仓        |
| 偏贵及以下                | P4 不触发           |

---

## 核心原则

1. **四工具交叉** — 不靠单一指标，冲突时降级而非硬套。
2. **只出温度，不给价位** — 输出档位与操作建议，不定义安全边际价位公式。
3. **仓位硬编码** — 底仓/机动仓区间、单只/行业上限写死，AI 不得自由裁量。
4. **禁止心算** — 所有数值来自 `financial_rigor.py` 输出。

---

## 注意事项

- 开始前运行 `date` 确认当天日期，报告头部注明数据截止日期。
- 关键财务数据须至少两个来源交叉验证，误差 >1% 须标记。
- PE 分位采用「历史 PE 中 ≤ 当前 PE 的样本占比（含等于）」口径，边界处显式标注。
- 禁止使用 WebSearch / WebFetch 工具（中国大陆不可用），统一用本地五工具组合。

---

## 局限性说明

- 只输出估值档位与仓位操作建议，不给出具体目标价或买卖价位。
- 一致预期增速存在分析师乐观偏差，仅做「>历史3年增速×2」预警。
- 港股流动性折价、美股成长溢价的市场阈值微调（±0.2）为经验值。
- 修正因子打分（渗透率/ROE/景气加速度/地缘政治）由上游 `mid-industry-research`、`qoq-accelerator` 承担，本技能不做主观打分。
- 不构成投资建议，仅供学习研究参考。

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [卖出信号](../exit-signal/README.md) — 后置技能（P4 估值透支输入）
- [财务计算与验证](../tools-scripts/financial-calc.md) — `financial_rigor.py` 四估值命令
- [公共工具索引](../tools-scripts/common-tools-guide.md)

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-08-30
- **最后更新**：2026-08-30
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。
