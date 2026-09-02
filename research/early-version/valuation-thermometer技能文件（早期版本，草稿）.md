## valuation-thermometer技能文件（早期版本，草稿）

版本号：V0.0.1

---
name: valuation-thermometer
description: >
  估值温度计——基于 PEG/PE历史分位/PSG/implied-growth 四工具给出"显著低估/合理/偏贵/高估/严重透支"五档温度，
  映射到底仓/机动仓操作建议，并与 exit-signal P4 估值透支级别联动。
  核心锚定 PEG（林奇 GARP），辅以渗透率/ROE趋势/景气加速度/地缘政治四维修正（郑希/李进框架），
  硬性规则禁止 LLM 心算，所有数值必须走 financial_rigor.py 工具链。
disable-model-invocation: true
---

# 估值温度计：PEG / PE分位 / PSG / implied-growth 五档评级

对 $ARGUMENTS 标的进行系统性估值评估，输出五档温度评级及对应底仓/机动仓操作建议。

## 设计理念

在 1~3 年的中长期投资中，**估值是"温度计"，不是"锚"**。PEG 和 PE 历史分位决定买卖时点，而非 DCF 绝对估值。

本技能融合四位大师的估值思想：

| 大师 | 估值层面的贡献 | 在本技能中的体现 |
|------|---------------|-----------------|
| **林奇** | PEG 估值法（PEG<1 为低估，GARP 理念） | PEG 是核心锚定指标，五档温度表的基础 |
| **李进** | 渗透率坐标定位产业阶段 + 二阶导思维 | 渗透率辅助修正估值判断；增速加速度纳入修正因子 |
| **郑希** | ROE 拐点决定估值中枢方向 + 全球产业链视角 | ROE 趋势修正估值判断；地缘政治风险纳入修正因子 |
| **欧奈尔** | 底线思维，拒绝"再等等"的幻想 | 高估区/严重透支区执行减仓/清仓纪律，硬性规则不可裁量 |

**核心理念**：估值温度计不预测"股价会涨到多少"，而是回答——**"当前价格处于什么温度区间，应该采取什么动作"**。

**与 exit-signal 的联动**：本技能输出的 PEG 档位直接映射到 `exit-signal` 的 P4（估值透支）级别：
- PEG > 1.5 → P4 减机动仓
- PEG > 2.0 → P4 加速清机动仓

---

## 输入参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `{标的}` | 字符串 | 是 | 无 | 公司名称或股票代码（支持 A 股/港股/美股） |
| `--growth-horizon` | 整数 | 否 | 2 | 增长预期年限（年），用于计算 PEG 的增速基准 |
| `--pe-source` | 字符串 | 否 | auto | PE 数据来源：auto / ttm / forward |
| `--export` | 标志 | 否 | false | 是否导出 Markdown 报告 |
| `--export-path` | 字符串 | 否 | reports/valuation/ | 报告输出路径 |
| `--json` | 标志 | 否 | false | 是否以 JSON 格式输出 |

**批量模式**：支持逗号分隔多个标的，如 `valuation-thermometer 中际旭创,新易盛,天孚通信`

---

## 执行流程

### 第一步：获取标的估值数据

根据标的所属市场，调用对应工具获取估值数据：

**A 股**：

```bash
# 获取当前 PE、TTM EPS、当前股价
python tools/a_share/stock_info.py --code {code} --profile

# 获取历史 5 年 PE 序列（用于计算 PE 分位）
python tools/a_share/stock_quote.py --code {code} --pe-history --years 5
```

**港股**：

```bash
# 获取当前 PE、TTM EPS
python tools/hk_stock/stock_info.py --code {code}

# 获取历史 5 年 PE 序列
python tools/hk_stock/stock_quote.py --code {code} --pe-history --years 5
```

**美股**：

```bash
# 获取当前 PE、TTM EPS
python tools/us_stock/stock_info.py --realtime {code}

# 获取历史 5 年 PE 序列
python tools/us_stock/stock_quote.py --code {code} --pe-history --years 5
```

**数据提取要点**：

| 数据项 | 来源 | 备注 |
|--------|------|------|
| 当前 PE（TTM） | `stock_info.py --profile` 或 `stock_info.py --realtime` | 优先使用 TTM PE |
| 当前股价 | 同上 | 用于参考 |
| TTM EPS | 从 PE 和股价反推 | 或直接从财务数据获取 |
| 历史 5 年 PE 序列 | `stock_quote.py --pe-history` | 用于计算 PE 分位 |
| 一致预期 EPS 增速 | `anysearch` 抓取券商研报 | 详见第二步 |
| 当前市值 | `stock_info.py` | 用于 implied-growth 计算 |
| 当前 PS（市销率） | `stock_info.py` 或 `stock_financial.py` | 用于 PSG 计算 |

---

### 第二步：获取一致预期 EPS 增速

由于免费数据源（Tushare/AkShare）不直接提供一致预期数据，需通过搜索服务抓取券商研报：

**搜索策略（按优先级）**：

```bash
# A 股优先：anysearch 金融垂直库
python tools/common/anysearch.py "{公司名} 一致预期 EPS {年份}" --tag finance

# A 股备选：doubao 财经定向
python tools/common/doubao_search.py "{公司名} 一致预期 EPS {年份}" --finance --need-content

# 美股/港股：exa 深度搜索
python tools/common/exa_search.py "{公司名} {年份} EPS consensus estimate" --type deep
```

**数据提取与校验**：

| 步骤 | 操作 | 说明 |
|------|------|------|
| 1 | 搜索"公司名 + 一致预期 + EPS" | 关键词含年份（如 2026/2027） |
| 2 | 从搜索结果提取 EPS 预测值 | 优先取平均值（mean/consensus） |
| 3 | 与历史增速交叉验证 | 若一致预期增速 > 历史 3 年增速 × 2，标记为 "过于乐观预警" |
| 4 | 多源对比 | 至少 2 个来源，误差 > 10% 标记差异 |

**未来 2 年 EPS 复合增速计算公式**：

```
未来2年EPS复合增速 = (未来第2年一致预期EPS / 当前TTM EPS) ^ (1/2) - 1
```

**数据缺失处理**：

- 若无法获取一致预期，使用历史 3 年 EPS 复合增速作为替代，并标记为 "基于历史增速推算，未经一致预期验证"
- 若两者均无法获取，输出 "数据不足，无法计算 PEG"

---

### 第三步：计算 PEG（核心锚定指标）

**调用工具（禁止 LLM 心算）**：

```bash
python tools/common/financial_rigor.py peg --pe {当前PE} --growth {未来2年EPS复合增速}
```

**五档温度表**（对齐开发方案 6.2 + 理念文档 V2.0 第三部分）：

| PEG 范围 | 档位 | 含义 | 操作建议 |
|----------|------|------|----------|
| PEG < 0.8 | **显著低估** | 市场严重低估成长性，绝佳买点 | 底仓可加仓；分批建仓：先在合理区间下沿建 1/3 底仓，恐慌时再加 1/3 |
| 0.8 <= PEG < 1.2 | **合理** | 估值与成长性匹配 | 合理买入区间，先建 1/3 底仓；已持仓者保留底仓，机动仓暂不操作 |
| 1.2 <= PEG < 1.5 | **偏贵** | 估值已基本反映成长性 | 机动仓观望，不追高；已持仓者底仓保留，机动仓不加仓 |
| 1.5 <= PEG < 2.0 | **高估** | 估值已透支增长 | 机动仓减持 30%~50%；对应 exit-signal P4 减机动仓 |
| PEG >= 2.0 | **严重透支** | 极度高估，增长远不能支撑估值 | 加速清机动仓；若渗透率同时 > 50%，底仓也考虑减仓；对应 exit-signal P4 加速清机动仓 |

> **阈值口径说明**：理念文档 V2.0 对 PEG 阈值有三处表述——第一部分"PEG<1 低估、1~1.2 合理、>1.5 高估"；第三部分"合理区间 0.8~1.2、<0.8 绝佳买点、>1.5 高估"；备忘卡"PEG<1.2 买入、>1.5 减仓"。本表以第三部分"0.8~1.2 合理区间"为主锚；"1.2~1.5 偏贵"档为衔接 1.2 买入线与 1.5 高估线而设的过渡档，理念文档无此档。

---

### 第四步：计算 PE 历史分位

**调用工具（禁止 LLM 心算）**：

```bash
python tools/common/financial_rigor.py pe-percentile \
  --pe-series '{json格式PE序列}' \
  --current {当前PE}
```

**解读标准**（结合理念文档"卖出规则"）：

| PE 分位范围 | 含义 | 对评级的修正 |
|------------|------|-------------|
| < 30% | 历史低位 | 上调评级一档（如合理 → 显著低估） |
| 30% ~ 70% | 历史中位 | 无修正 |
| 70% ~ 90% | 历史高位 | 下调评级一档（如合理 → 偏贵） |
| > 90% | 历史极端高位 | 下调评级两档（如合理 → 高估） |

---

### 第五步：计算 PSG（市销率增长比，爆发期专用）

**适用场景**：需求爆发期/技术跃迁期的科技公司，当前利润尚未充分释放，PSG 作为 PEG 的补充。

**调用工具（禁止 LLM 心算）**：

```bash
python tools/common/financial_rigor.py ps-g \
  --ps {当前PS} \
  --revenue-growth {未来2年营收复合增速}
```

**解读标准**：

| PSG 范围 | 档位 |
|----------|------|
| PSG < 0.5 | 低估 |
| 0.5 <= PSG < 1.0 | 合理 |
| 1.0 <= PSG < 1.5 | 偏高 |
| PSG >= 1.5 | 高估 |

---

### 第五步（续）：implied-growth 市值隐含业绩倒推

**适用场景**：验证当前市值是否已透支未来业绩。通过市值倒推所需的营收/利润增速，与管理层指引及一致预期对比，判断估值是否可持续。

**调用工具（禁止 LLM 心算）**：

```bash
python tools/common/financial_rigor.py implied-growth \
  --market-cap {当前市值} \
  --target-pe {合理PE} \
  --net-margin {净利率} \
  --ttm-revenue {TTM营收} \
  --guidance-growth {管理层指引增速}
```

**解读标准**：

| 判定 | 条件 | 含义 |
|------|------|------|
| 绿灯 | 倒推所需增速 <= 一致预期增速上限 | 估值可被业绩消化，安全 |
| 黄灯 | 倒推所需增速 > 一致预期增速但在管理层指引范围内 | 需密切关注业绩兑现 |
| 红灯 | 倒推所需增速 > 管理层指引上限 | 估值透支，预警 |

---

### 第五步（续）：估值交叉验证

使用 `verify-valuation`、`three-scenario`、`cross-validate` 命令进行多角度交叉验证：

```bash
# 估值合理性验证（综合多维度判断）
python tools/common/financial_rigor.py verify-valuation {相关参数}

# 三情景分析（乐观/中性/悲观）
python tools/common/financial_rigor.py three-scenario {相关参数}

# 跨源数据交叉校验（关键财务数据至少 2 个独立来源，误差 > 1% 标记）
python tools/common/financial_rigor.py cross-validate {相关参数}
```

**交叉验证规则**：关键财务数据（PE、EPS、增速）至少 2 个独立来源，误差 > 1% 在报告中显式标记。

---

### 第六步：辅助因子修正（郑希/李进框架）

在 PEG 评级基础上，根据产业景气状态进行修正。**每个修正因子必须有明确的数据来源和计算依据，禁止凭空主观打分。**

| 修正因子 | 数据来源 | 修正规则 | 必须提供的数据证据 |
|----------|----------|----------|-------------------|
| **渗透率位置** | 行业研究报告 / `mid-industry-research` 输出 | 渗透率 < 15%：+0.3 档（偏乐观）；15%~40%：无修正；> 50%：-0.5 档（偏悲观） | 第三方行业报告、券商研报中的具体渗透率数字 |
| **ROE 趋势** | `stock_financial.py --indicator ROE` | ROE 连续 3 个季度向上：+0.3 档；ROE 拐头向下：-0.5 档 | 连续 3 个季度的 ROE 数据 |
| **景气加速度** | `qoq-accelerator` 输出 | 加速度连续 2 个季度为正：+0.3 档；加速度为负：-0.5 档 | `qoq-accelerator` 的原始输出数据 |
| **地缘政治风险** | 理念文档"支柱四"评估 | 高敞口且无对冲：-0.5 档；有对冲能力（海外建厂/多元供应链）：无修正 | 海外收入占比、制裁清单查询结果、本地化产能情况 |

**修正后评级**：将"显著低估/合理/偏贵/高估/严重透支"五档视为数值 -2, -1, 0, +1, +2，累加修正因子后重新映射回五档。修正幅度上限为 +/-1 档（防止过度修正）。

---

### 第七步：输出五档综合评级

综合 PEG、PE 分位、PSG、implied-growth 和辅助修正，输出最终五档评级：

| 评级 | 颜色标识 | 综合条件 | 操作建议 |
|------|----------|----------|----------|
| **显著低估** | 绿色 | PEG < 0.8 且 PE 分位 < 40% 且修正因子无负向 | 绝佳买点。可建仓或加仓。分批建仓：先建 1/3 底仓，恐慌时加 1/3，景气确认后补 1/3 |
| **合理** | 蓝色 | PEG 0.8~1.2 且 PE 分位 40%~70% | 合理买入区间。先建 1/3 底仓；已持仓者保留底仓，机动仓暂不操作 |
| **偏贵** | 黄色 | PEG 1.2~1.5 或 PE 分位 70%~80% | 机动仓观望，不追高。已持仓者底仓保留，机动仓不加仓，等待回调 |
| **高估** | 橙色 | PEG > 1.5 或 PE 分位 > 80% 或 implied-growth 红灯 或修正因子负向 | 减机动仓 30%~50%。当 PEG > 1.5 且 PE 分位 > 80% 时，系统性减持机动仓 |
| **严重透支** | 红色 | PEG > 2.0 或（PEG > 1.5 且 PE 分位 > 90%）或 implied-growth 红灯 + 渗透率 > 50% | 加速清机动仓。若渗透率同时 > 50%，底仓也考虑减仓 |

---

### 第八步：输出安全边际参考价位

基于理念文档 V2.0"分批建仓规则"，输出安全边际参考价位：

| 参考价位 | 计算方法 | 用途 |
|----------|----------|------|
| **低估阈值** | 当前盈利 x 合理PE x 0.8 | 低于此价位进入"显著低估"区间，绝佳买点 |
| **合理区间下沿** | 当前盈利 x 合理PE x 0.9 | 可建第一批 1/3 底仓 |
| **合理区间上沿** | 当前盈利 x 合理PE x 1.1 | 机动仓可考虑减持的起点 |
| **高估阈值** | 当前盈利 x 合理PE x 1.5 | 机动仓应系统性减持 |

**合理 PE 的计算**：

```
合理PE = 未来2年EPS复合增速 x 1.2（林奇 GARP 规则）
上限：合理PE <= 40（避免过高估值假设）
下限：合理PE >= 8（避免极端保守假设）
```

**分批建仓规则**（对齐理念文档 V2.0 第一部分第 4 步）：

1. 当股价进入"合理买入区间"后，先建 **1/3 底仓**
2. 若股价继续回调至合理区间下限以下（如 PEG < 0.7），再加 **1/3**
3. 确认产业景气加速或财报超预期后，补齐剩余 **1/3**
4. 总仓位控制：单只个股初始 <= 总资产的 10%，逻辑验证后 <= 15%，绝对上限 <= 20%；单一行业不超过总资产的 40%

---

## 输出格式

### JSON 格式

```json
{
  "success": true,
  "data": {
    "symbol": "300502",
    "name": "新易盛",
    "market": "A股",
    "evaluation_date": "2026-08-29",
    "current_price": 85.20,
    "current_pe": 32.5,
    "pe_percentile": 45.2,
    "eps_ttm": 2.62,
    "eps_growth_forward_2y": 38.5,
    "peg": 0.84,
    "peg_rating": "合理",
    "ps": 6.8,
    "psg": 0.52,
    "psg_rating": "合理",
    "implied_growth": {
      "required_growth": 0.32,
      "consensus_growth_upper": 0.42,
      "guidance_growth_upper": 0.40,
      "signal": "绿灯"
    },
    "rating": "合理",
    "rating_color": "blue",
    "rating_score": 0,
    "correction_factors": {
      "penetration_rate": "22%（光模块）",
      "penetration_adjustment": 0,
      "roe_trend": "向上（连续3个季度）",
      "roe_adjustment": 0.3,
      "qoq_acceleration": "正（连续2个季度）",
      "qoq_adjustment": 0.3,
      "geo_political_risk": "低（供应链可控）",
      "geo_adjustment": 0
    },
    "final_rating": "合理",
    "final_color": "blue",
    "action_suggestion": "合理买入区间。先建1/3底仓；已持仓者保留底仓，机动仓暂不操作。",
    "exit_signal_mapping": {
      "peg_to_p4": "当前PEG=0.84，未触发P4（需PEG>1.5）"
    },
    "buy_reference": {
      "undervalue_threshold": 52.80,
      "reasonable_lower": 59.40,
      "reasonable_upper": 72.60,
      "overvalue_threshold": 99.00
    },
    "position_rules": {
      "initial_max_pct": 10,
      "verified_max_pct": 15,
      "absolute_max_pct": 20,
      "single_industry_max_pct": 40
    },
    "risk_warnings": [],
    "data_sources": {
      "pe": "东方财富",
      "eps_growth": "券商一致预期（3家）",
      "pe_percentile": "financial_rigor.py",
      "implied_growth": "financial_rigor.py"
    },
    "data_confidence": "A级（高置信度）",
    "cross_validation": {
      "pe_sources": 2,
      "pe_deviation_pct": 0.5,
      "eps_growth_sources": 3,
      "eps_growth_deviation_pct": 2.1
    }
  },
  "meta": {
    "tool": "valuation-thermometer",
    "command": "evaluate",
    "timestamp": "2026-08-29T14:30:00"
  }
}
```

### Markdown 报告格式

当使用 `--export` 参数时，生成以下格式的 Markdown 报告，输出至 `reports/valuation/{公司名}-valuation-{YYYYMMDD}.md`：

```markdown
# 估值温度计报告

**标的**：新易盛（300502）
**评估日期**：2026-08-29
**市场**：A股（深交所创业板）

---

## 一、核心估值指标

| 指标 | 数值 | 评价 |
|------|------|------|
| 当前股价 | 85.20元 | -- |
| 当前PE（TTM） | 32.5x | 行业均值：45.3x |
| PE历史分位（5年） | 45.2% | 位于历史中位 |
| TTM EPS | 2.62元 | -- |
| 未来2年EPS复合增速 | 38.5% | 来源：券商一致预期（3家） |
| **PEG** | **0.84** | **合理区间** |
| 当前PS | 6.8x | -- |
| PSG | 0.52 | 合理 |
| implied-growth 信号 | 绿灯 | 倒推所需增速32% < 一致预期上限42% |

---

## 二、五档评级

### 合理

**评级得分**：0分（基准）

**评级依据**：
- PEG=0.84，处于 0.8~1.2 合理区间
- PE历史分位=45.2%，处于中位区间（无修正）
- 产业渗透率=22%，处于加速黄金区（无修正）
- ROE连续3个季度向上，修正+0.3档
- 景气加速度连续2个季度为正，修正+0.3档
- 地缘政治风险低，无修正
- implied-growth 绿灯，无修正

**最终评级**：合理

---

## 三、安全边际参考价位

| 价位 | 计算依据 | 操作参考 |
|------|----------|----------|
| 52.80元 | 低估阈值（合理PE x 0.8） | 低于此价位进入"显著低估"区间 |
| 59.40元 | 合理区间下沿（合理PE x 0.9） | 可建第一批 1/3 底仓 |
| 72.60元 | 合理区间上沿（合理PE x 1.1） | 机动仓可考虑减持 |
| 99.00元 | 高估阈值（合理PE x 1.5） | 机动仓应系统性减持 |

**合理PE计算**：38.5% x 1.2 = 46.2x，上限 40x 取 40x

---

## 四、操作建议

### 当前状态：已持有

| 仓位类型 | 当前占比建议 | 操作建议 |
|----------|-------------|----------|
| **底仓（60%~80%）** | 建议维持 | 继续持有。只要产业景气上行、护城河稳固，不因短期波动卖出 |
| **机动仓（20%~40%）** | 暂不操作 | 等待 PEG > 1.5 或 PE 分位 > 80% 时减持 |

### 若未建仓

当前估值处于合理区间，可按分批建仓规则操作：
1. 当前价位（85.20元）建 1/3 底仓
2. 若回调至合理区间下沿（59.40元）以下，加 1/3
3. 确认产业景气加速或财报超预期后，补齐剩余 1/3

### 仓位上限规则

| 规则 | 上限 |
|------|------|
| 单只个股初始仓位 | <= 总资产 10% |
| 逻辑验证后仓位 | <= 总资产 15% |
| 单只个股绝对上限 | <= 总资产 20% |
| 单一行业上限 | <= 总资产 40% |

---

## 五、与 exit-signal 联动

| exit-signal 级别 | 本技能触发条件 | 当前状态 |
|-----------------|---------------|----------|
| P4 减机动仓 | PEG > 1.5 | 未触发（当前 PEG=0.84） |
| P4 加速清机动仓 | PEG > 2.0 | 未触发 |

---

## 六、风险提示

| 风险 | 描述 | 概率 |
|------|------|------|
| 一致预期过于乐观 | 券商一致预期增速38.5%，若实际增速低于预期，PEG将被动抬升 | 中 |
| 行业竞争加剧 | 光模块行业竞争激烈，若毛利率下降，估值中枢下移 | 低 |
| 技术路线切换 | 若出现新的光通信技术路线，公司护城河可能受损 | 低 |

---

## 七、数据来源与置信度

| 数据项 | 来源 | 置信度 |
|--------|------|--------|
| 当前PE | 东方财富 | A级 |
| PE历史分位 | financial_rigor.py 计算 | A级 |
| 一致预期EPS增速 | 券商研报（3家均值） | A级 |
| implied-growth | financial_rigor.py 计算 | A级 |
| 渗透率数据 | 行业研究报告 | B级 |
| ROE趋势 | 东方财富财务数据 | A级 |

**综合置信度**：A级（高置信度）

**交叉验证**：
- PE 数据来源 2 个，偏差 0.5%（通过）
- EPS 增速来源 3 个，偏差 2.1%（通过，< 10% 阈值）

---

*报告生成时间：2026-08-29 14:30:00*
*免责声明：本报告仅供学习研究参考，不构成投资建议。市场有风险，投资需谨慎。*
```

---

## 依赖工具

### Python 工具（零开发，全部已内置）

| 工具 | 命令 | 用途 |
|------|------|------|
| `stock_info.py` | `python tools/a_share/stock_info.py --code {code} --profile` | A 股实时估值数据 |
| `stock_info.py` | `python tools/hk_stock/stock_info.py --code {code}` | 港股实时估值数据 |
| `stock_info.py` | `python tools/us_stock/stock_info.py --realtime {code}` | 美股实时估值数据 |
| `stock_quote.py` | `python tools/a_share/stock_quote.py --code {code} --pe-history` | PE 历史序列 |
| `stock_financial.py` | `python tools/a_share/stock_financial.py --code {code} --indicator ROE` | ROE 趋势数据 |
| `financial_rigor.py` | `python tools/common/financial_rigor.py peg --pe {pe} --growth {growth}` | PEG 计算（核心） |
| `financial_rigor.py` | `python tools/common/financial_rigor.py pe-percentile --pe-series '{json}' --current {pe}` | PE 历史分位 |
| `financial_rigor.py` | `python tools/common/financial_rigor.py ps-g --ps {ps} --revenue-growth {growth}` | PSG 计算 |
| `financial_rigor.py` | `python tools/common/financial_rigor.py implied-growth --market-cap {cap} --target-pe {pe} --net-margin {margin} --ttm-revenue {revenue} --guidance-growth {growth}` | 市值隐含业绩倒推 |
| `financial_rigor.py` | `python tools/common/financial_rigor.py verify-valuation {参数}` | 估值合理性综合验证 |
| `financial_rigor.py` | `python tools/common/financial_rigor.py three-scenario {参数}` | 三情景分析（乐观/中性/悲观） |
| `financial_rigor.py` | `python tools/common/financial_rigor.py cross-validate {参数}` | 跨源数据交叉校验 |

### 搜索工具

| 工具 | 命令 | 用途 |
|------|------|------|
| `anysearch.py` | `python tools/common/anysearch.py "{公司名} 一致预期 EPS" --tag finance` | A 股一致预期（主） |
| `doubao_search.py` | `python tools/common/doubao_search.py "{公司名} 一致预期 EPS" --finance --need-content` | A 股一致预期（辅） |
| `exa_search.py` | `python tools/common/exa_search.py "{公司名} {年份} EPS consensus estimate" --type deep` | 美股/港股一致预期 |

### 上游依赖技能

| 技能 | 提供的数据 | 用途 |
|------|-----------|------|
| `mid-industry-research` | 渗透率位置、产业空间、地缘政治风险 | 修正因子中的渗透率和地缘政治维度 |
| `qoq-accelerator` | 景气加速度（连续季度增速趋势） | 修正因子中的景气加速度维度 |
| `mid-trend-tech-screen` | 景气筛选结果、RS Rating | 前置确认景气方向 |

---

## 注意要点

### 1. 一致性原则

- PEG 计算中 PE 和增速必须**同口径**（均为 TTM 或均为 Forward），本技能统一使用 **TTM PE + 未来 2 年一致预期增速**
- 若使用 Forward PE，须在报告中明确标注，且增速也要使用对应 Forward 口径

### 2. 数据时效性

| 数据项 | 最大可接受时效 | 超时处理 |
|--------|---------------|----------|
| 当前 PE | 1 个交易日 | 获取最新收盘价重新计算 |
| PE 历史分位 | 1 个交易日 | 同上 |
| 一致预期 EPS 增速 | 3 个月 | 标记"预期数据可能已过时" |
| ROE 趋势 | 1 个季度 | 使用最近季报数据 |

### 3. 不同市场的 PE 读数差异

| 市场 | PE 平均水平 | 注意事项 |
|------|-----------|----------|
| A 股 | 偏高（15~25x） | 需与行业均值对比 |
| 港股 | 偏低（8~15x） | 流动性折价，PEG 阈值可下调 0.2 |
| 美股 | 偏高（20~30x） | 成长股溢价，PEG 阈值可上调 0.2 |

### 4. 禁止 LLM 心算（硬性规则）

所有数值计算（PEG、PE 分位、PSG、implied-growth、安全边际价位）**必须**通过 `financial_rigor.py` 工具计算，禁止 LLM 心算。

```bash
# 正确用法
python tools/common/financial_rigor.py peg --pe 32.5 --growth 38.5

# 错误用法
# "PEG = 32.5 / 38.5 = 0.84" <-- 禁止手动计算
```

### 5. 评级修正确认

每个修正因子必须有**明确的数据来源**和**计算依据**，禁止凭空主观打分：

| 修正因子 | 必须提供的数据证据 |
|----------|-------------------|
| 渗透率位置 | 第三方行业报告、券商研报中的具体数字 |
| ROE 趋势 | 连续 3 个季度的 ROE 数据 |
| 景气加速度 | `qoq-accelerator` 的原始输出 |
| 地缘政治风险 | 海外收入占比、制裁清单查询结果、本地化产能情况 |

### 6. 风控硬编码（不可裁量）

以下规则为硬性规则，写入 Prompt 后不允许 AI 自由裁量：

| 硬性规则 | 内容 |
|----------|------|
| PEG > 1.5 | 机动仓必须减持，不可"再等等看" |
| PEG > 2.0 | 加速清机动仓，不可"信仰持有" |
| PE 分位 > 90% | 必须下调评级，不可忽略 |
| 止损 8%~10% | 由 `exit-signal` P1 执行，本技能不直接触发但需在报告中标注当前浮盈/浮亏比例 |
| 底仓/机动仓区间 | 底仓 60%~80%、机动仓 20%~40%，不可随意突破 |

---

## 局限性

1. **一致预期数据可得性**：Akshare/Tushare 免费版不直接提供一致预期，需通过搜索抓取，可能存在缺失或延迟
2. **PE 历史分位计算基础**：需要 5 年 PE 序列，上市不足 5 年的公司数据不足，需标注
3. **行业差异**：PEG 不适用于所有行业（银行/保险/资源类不适用），需结合行业特征判断
4. **渗透率数据**：第三方数据可能存在延迟或口径差异
5. **修正因子的量化精度**：修正幅度为 +/-0.3 或 +/-0.5 档，属于定性量化，精度有限
6. **不构成投资建议**：本技能仅为估值参考工具，需结合其他技能综合决策

---

## 与现有技能的关系

| 技能 | 关系 | 使用顺序 |
|------|------|----------|
| `mid-trend-tech-screen` | 前置 | 景气筛选确认方向后，再进行估值评估 |
| `quality-screen` | 前置 | 先排雷再估值 |
| `mid-industry-research` | 前置 | 提供渗透率位置和地缘政治风险评估 |
| `qoq-accelerator` | 前置 | 提供景气加速度修正因子 |
| `investment-checklist` | 并行 | 估值合理后进入投资检查清单 |
| `thesis-tracker --horizon mid` | 后置 | 估值合理后建仓并建立中期论文 |
| `exit-signal` | 后置 | 估值高估时触发 P4 卖出信号 |
| `financial-data` | 共享 | 数据获取规范 |

**典型使用流程**：

```
/mid-industry-research {行业名}              <-- 确认景气赛道 + 渗透率位置
        |
/mid-trend-tech-screen {行业名}              <-- 正向排序领涨标的
        |
/quality-screen {标的}                       <-- 排雷
        |
/valuation-thermometer {标的}                <-- 【本技能】五档估值温度
        |
/qoq-accelerator {标的}                      <-- 提供加速度修正因子
        |
（若估值合理/低估）:
    -> /investment-checklist {标的}          <-- 投资检查清单
    -> /thesis-tracker --horizon mid {标的}  <-- 建立中期论文
（若估值偏贵/高估）:
    -> 等待回调或寻找替代标的
（若估值严重透支）:
    -> /exit-signal {标的}                   <-- 触发 P4 卖出检查
```

---

## 版本记录

| 版本 | 日期 | 修订内容 |
| --- | --- | --- |
| V0.0.1 | 2026-08-29 | 初版草稿 |

