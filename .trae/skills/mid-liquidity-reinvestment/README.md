# 流动性质量与再投资能力验证（1~3 年景气投资版）

评估快速增长型公司的自由现金流质量、再投资效率与资本配置纪律，判断其成长是否建立在真实现金创造与高效再投资之上。

---

## 快速开始

### 基本调用方式

```
/garp-liquidity-reinvestment {公司名或股票代码}
```

例如：

- `/garp-liquidity-reinvestment 新易盛`
- `/garp-liquidity-reinvestment 300502`（A股股票代码）
- `/garp-liquidity-reinvestment 00700`（港股腾讯）
- `/garp-liquidity-reinvestment NVDA`（美股英伟达）

### 适用前自检

本技能**仅适用**快速增长型（增速 >20%）或稳定增长型（增速 10~20%）等有再投资需求的成长型公司。

- ✅ 增速 >20% 的成长标的 → 最适用
- ✅ 增速 10~20% 的稳定增长标的 → 适用
- ❌ 缓慢增长型（增速 <10%、主要靠分红）→ 请转长期版 `income-investment`

---

## 核心功能

对指定公司进行系统化**流动性质量与再投资能力专项验证**，回答一个核心问题：**这家公司的自由现金流质量如何？管理层在高效地再投资吗？资本配置纪律是否严格？**

### 九步执行流程

1. **确认标的适用性** — 用林奇六类分类确认标的属于快速增长型/稳定增长型
2. **数据收集与质量确立** — 确定标的、上市地、货币、证据质量评级 A/B/C
3. **自由现金流质量分析** — FCF/净利润比率、经营现金流、应收账款/存货周转、资本开支结构
4. **再投资效率分析** — ROIC（引用 `mid-management-deep-dive`）、增量资本回报率、再投资充分性、外部融资检查
5. **管理层资本配置评估** — 回购/并购/分红/新业务逐笔记录，李进维度 C
6. **资产负债强度与财务弹性** — 净现金/净负债、有息负债/EBITDA、利息覆盖率、流动性比率
7. **估值与安全边际** — PEG 数值计算（引用 `valuation-thermometer` 五档）、三情景估值
8. **流动性危机情景分析** — 收入归零 + 融资收紧 + 回款拉长下的流动性断裂推演
9. **综合判决** — 高质量 / 中等质量 / 低质量 / 数据不足，输出阻断门控结果

### 判决分类

| 判决 | 定义 |
|------|------|
| **高质量流动性** | FCF 质量高、再投资效率高、财务弹性强 |
| **中等质量流动性** | FCF 质量一般、再投资效率中等、财务弹性可接受 |
| **低质量流动性** | FCF/净利润 <50%、增量 ROIC < 存量 ROIC、财务弹性弱 |
| **数据不足** | 无法获取足够的流动性数据 |

### 阻断门控

| 阻断门控 | 触发条件 | 操作 |
|---------|---------|------|
| 利润质量严重存疑 | FCF/净利润 < 50% 且连续 2 年恶化 | 判决 ≤ 中等质量流动性 |
| 扩张毁灭价值 | 增量 ROIC < 存量 ROIC 且持续 2 年 | 判决 ≤ 中等质量流动性 |
| 债务风险过高 | 有息负债/EBITDA > 5x | 判决 ≤ 中等质量流动性 |
| 管理层诚信问题 | 一票否决 | **立即回避**（对应 `exit-signal` 的 P0） |

---

## 使用示例

### 示例 1：分析 A 股成长股

```
/garp-liquidity-reinvestment 新易盛
```

用 A 股本地工具获取财务数据，按九步流程验证其光模块业务的高增速是否建立在真实的自由现金流与高效再投资之上。

### 示例 2：分析港股科技股

```
/garp-liquidity-reinvestment 00700
```

评估腾讯的自由现金流质量与资本配置纪律（回购、并购、研发投入），跨币种折录用 `fx_rate.py --code HKDCNY` 获取实时汇率。

### 示例 3：分析美股成长股

```
/garp-liquidity-reinvestment NVDA
```

评估英伟达的资本开支结构（扩张性占比）、增量资本回报率与自由现金流质量，判断其高增长的可兑现性。

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 流动性质量验证报告 | `reports/{公司名}/{公司名}-garp-liquidity-{YYYYMMDD}.md` |

### 报告结构（11 节）

1. 执行摘要（一句话结论）
2. 判决与分类（含阻断门控结果）
3. 六类分类确认（林奇）
4. 自由现金流质量分析
5. 再投资效率分析
6. 管理层资本配置评估
7. 资产负债强度与财务弹性
8. 估值与安全边际（PEG 视角，引用 `valuation-thermometer`）
9. 流动性危机情景分析
10. 关键监控指标
11. 来源与数据质量

### 发布审核

报告保存后须运行审核流程：

```bash
python tools/common/report_audit.py extract --report reports/{公司名}/{公司名}-garp-liquidity-{YYYYMMDD}.md
python tools/common/report_audit.py verdict --results '<verified JSON>' --report reports/{公司名}/{公司名}-garp-liquidity-{YYYYMMDD}.md
```

---

## 工具依赖

### 本地数据获取工具

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票信息查询 | `python tools/a_share/stock_info.py --search 新易盛` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、FCF 等） | `python tools/a_share/stock_financial.py --code 300502` |
| A股 | `tools/a_share/stock_quote.py` | 历史股价与行情 | `python tools/a_share/stock_quote.py --code 300502` |
| 港股 | `tools/hk_stock/stock_financial.py` | 港股信息与财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| 港股 | `tools/hk_stock/stock_quote.py` | 港股历史K线 | `python tools/hk_stock/stock_quote.py --code 00700` |
| 美股 | `tools/us_stock/stock_info.py` | 美股信息查询 | `python tools/us_stock/stock_info.py --search NVIDIA` |
| 美股 | `tools/us_stock/stock_financial.py` | 美股财务指标 | `python tools/us_stock/stock_financial.py --code NVDA` |
| 美股 | `tools/us_stock/stock_quote.py` | 美股行情数据 | `python tools/us_stock/stock_quote.py --code NVDA` |

**Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

详细使用说明请参考：

- **A股工具**：[docs/A股工具使用指南.md](../../docs/A股工具使用指南.md)
- **港股工具**：[docs/港股工具使用指南.md](../../docs/港股工具使用指南.md)
- **美股工具**：[docs/美股工具使用指南.md](../../docs/美股工具使用指南.md)
- **国际货币汇率**（跨市场折算）：`tools/common/fx_rate.py`

### 精确计算工具（禁 LLM 心算）

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | FCF、ROIC、增量回报率、估值、PEG、三情景 | `python tools/common/financial_rigor.py peg --pe 30 --growth 25` |
| `tools/common/report_audit.py` | 报告数据抽检与审核（准出流程） | `python tools/common/report_audit.py extract --report reports/xxx.md` |

> `--growth` 为「百分点」数值（如 25 表示 25%）；PEG 五档判定统一引用 `valuation-thermometer`，本技能只计算数值。

### 网络搜索工具

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。完整选型见 [web-search-tools](../tools-scripts/web-search-tools.md)。

**流动性质量与再投资能力场景下的搜索选型**：

- FCF/资本开支/并购回购/股权稀释线索：A股 `anysearch --tag finance` 主 + `doubao --finance` 辅；美股 `exa --type deep` 主 + `doubao --finance` 辅
- 现金流失真/应收账款异常线索：`anysearch --tag finance` 主 + `doubao --finance` 辅
- 资本配置动作（回购/并购/增发公告）：`doubao --finance` 主 + 交易所官方披露确认
- 管理层诚信/治理/造假线索（P0 判断）：`anysearch --tag legal` 主 + `doubao --finance` 辅

**搜索规范**（本技能特有）：

- 时效性优先：使用 `--time-range month/week` 限制时间范围
- 双源验证：港股 doubao + tavily；美股 exa + doubao；A股 anysearch + doubao
- 关键信息缺失时标注「信息不足」，不得用推测填充

---

## 核心原则

1. **FCF 质量是核心** — 赚真钱比赚账面利润重要得多（郑希：ROE 向上须以真实现金流为底）
2. **再投资效率比 FCF 绝对值更重要** — 即使 FCF 为负，若增量回报率极高也可能是好的投资（李进）
3. **快速增长型公司不分红是正常的** — 不要因为分红率低而扣分
4. **引用不重复定义** — PEG 五档、P0~P5、ROIC 阈值/评分一律引用权威技能，不自建表格阈值
5. **与 `income-investment` 路由互斥** — 本技能验证成长型公司的现金流与再投资，不评估分红收入
6. **数据规范** — 算术须经 `financial_rigor.py`；关键财务数据双源交叉验证，误差 >1% 须标记；开始前 `date` 确认

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 所有数据必须标注来源，关键财务数据至少两个来源交叉验证，误差 >1% 须标记
- FCF、ROIC、增量资本回报率、估值、流动性指标须用 `financial_rigor.py` 精确计算，禁止 LLM 心算
- 跨币种收入折算须用 `funds/common/fx_rate.py` 获取实时汇率，禁用固定汇率
- 本技能不替代分红投资分析；缓慢增长型/收息标的请转长期版 `income-investment`
- 本技能输出的「低质量流动性」不替代 `exit-signal` 的组合级卖出决策，卖出纪律一律引用 P0~P5
- 报告保存后须运行 `report_audit.py` 审核流程，未通过审核的是草稿
- 不构成投资建议，仅供学习研究参考

---

## 局限性说明

- **资料可得性**：部分公司的完整财报原文可能难以获取
- **FCF 口径差异**：不同来源对资本开支（维护性 vs 扩张性）的定义可能不同
- **增量回报率计算依赖准确的分部数据**：部分公司不披露分部资本开支，无法精确拆分
- **再投资效率的判断依赖历史推断**：未来再投资回报可能与历史不同
- **AI 解读局限**：AI 无法完全替代专业财务分析师的深度分析能力
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [估值温度计](../valuation-thermometer/README.md) — PEG 五档唯一权威口径
- [卖出信号](../exit-signal/README.md) — P0~P5 卖出优先级唯一权威口径
- [管理层纵深研究（中期版）](../mid-management-deep-dive/README.md) — ROIC / 增量资本回报率 / 资本配置 20 分制口径
- [中期行业景气研究](../mid-industry-research/README.md) — 产业景气 / 渗透率 / 地缘政治口径
- [GARP 价值成长问答](../garp-ask/README.md) — GARP 系列问答入口（问答型，不生成报告）
- [收入投资分析（长期版）](../income-investment/README.md) — 分红收入分析，与本技能**路由互斥**

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-09-06
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。