# 收入投资分析 (Income Investment)

评估公司是否能够产生足够持久且有吸引力的可分配收入，判断其适合长期收入核心持仓还是机会型收益仓位

---

## 快速开始

### 基本调用方式

```
/income-investment {公司名或股票代码} [mode=new|existing] [role=core-income|opportunistic-income|unspecified]
```

例如：
- `/income-investment 中国移动`
- `/income-investment 00700`（港股腾讯）
- `/income-investment KO mode=existing role=core-income`（美股可口可乐，已有持仓）

### 可选参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `mode` | 新建或已有持仓 | `mode=new`、`mode=existing` |
| `role` | 期望的收入角色 | `role=core-income`、`role=opportunistic-income` |
| `quantity` | 持仓数量 | `quantity=500` |
| `cost_basis` | 成本价 | `cost_basis=480` |
| `portfolio_weight` | 组合占比 | `portfolio_weight=5%` |
| `target_yield` | 目标收益率 | `target_yield=4%` |
| `tax_residence` | 税务居民地 | `tax_residence=CN` |
| `portfolio_file` | 组合文件路径 | `portfolio_file=reports/portfolio-latest.md` |
| `horizon` | 持有期限 | `horizon=5y` |

---

## 核心功能

对指定公司进行系统化**收入投资分析**，评估其分红持久性、现金流覆盖、资产负债表健康度、估值合理性及组合适配度，产出完整的收入投资研究报告。

### 八步执行流程

1. **解析请求与数据质量确立** — 确定标的、上市地、货币、分红货币、模式、期望角色；评级证据质量 A/B/C
2. **理解分红** — 覆盖至少五年：频率、普通/特别/可变状态、支付货币、年度每股分红、增减削减次数、CAGR、日历
3. **追踪可分配现金流** — 净利润/FCF 派息率、现金流稳定性、利息覆盖、净债务、再融资、资本开支、表外承诺、回购竞争
4. **测试质量与持久性** — 商业模式、护城河、周期性、敏感性、收入可预测性、下行情景维持分红能力
5. **估值收入流** — 当前收益率、历史平均、行业倍数、FCF 收益率、内在价值区间、安全边际、组合情景
6. **计算可用收入** — 毛分红、预扣税、净收入、组合贡献、交易后收入（税务不完整时只展示毛收入）
7. **检查组合适配** — 当前/建议权重、集中度、重复风险、资本分散 vs 分红分散、月度收入日历
8. **构建三情景** — 基准/不利/严重，每个明确测试分红削减而非假设不变

### 行业特定指标

| 行业 | 必需指标 |
|------|---------|
| REIT / SIIC | FFO、AFFO、出租率、LTV |
| 银行 | CET1、可分配收益、监管约束 |
| 保险 | 偿付能力与资本生成 |
| BDC | NII、NAV、不良率 |
| 资源类 | 周期中段现金流与可变分红政策 |
| 电信 / 公用事业 | 资本开支、债务与 FCF 覆盖率 |

### 收入特征分类

- **信念 + 持久收入**：优质业务、可持续且可能增长的分红、可合理长期持有
- **机会型收入**：临时性高收益或折价，有明确的进入、监控、持有期和退出规则
- **收益陷阱**：反复覆盖不足、杠杆/投资需求不兼容、结构性衰退，或收益率主要由股价下跌驱动
- **不适合收入投资**：无实质性分红、边际收益率、证据不足

### 判决选项

| 判决 | 含义 |
|------|------|
| `核心收入` | 优质业务 + 可持续增长分红 + 可长期持有 |
| `机会型收入` | 临时性高收益，有明确进入/退出规则 |
| `观察名单` | 暂不符合，持续关注 |
| `持有 - 不加仓` | 公司质量尚可但组合集中度限制加仓 |
| `减仓` | 已有持仓面临分红风险或组合过度集中 |
| `拒绝 / 收益陷阱` | 覆盖不足、杠杆过高、结构性衰退 |
| `数据不足` | 基本面数据严重不足，无法判断 |

---

## 使用示例

### 示例1：分析A股收息股
```
/income-investment 中国移动
```
使用 A 股本地工具获取财务数据与分红历史，按八步流程分析其作为核心收入持仓的适配度。

### 示例2：分析港股收息股
```
/income-investment 00700 mode=existing role=core-income quantity=500 cost_basis=380
```
评估腾讯已持仓的收入特征，计算成本收益率与组合贡献。用 `fx_rate.py --code HKDCNY` 获取实时汇率折算。

### 示例3：分析美股收息股
```
/income-investment KO role=core-income target_yield=4% tax_residence=CN
```
评估可口可乐的分红持久性与净收入（考虑中美税务协定预扣税）。

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 收入投资报告 | `reports/{公司名}-income-investment-{YYYYMMDD}.md` |

### 报告结构（18节）

1. 执行摘要
2. 判决与分类（含评分卡和阻断门控结果）
3. 可能的组合角色
4. 业务与分配现金来源
5. 分红历史与日历
6. 分配覆盖与安全性
7. 资产负债表与再融资
8. 收入增长
9. 估值与安全边际
10. 税务与货币
11. 组合适配（含月度收入日历，如可计算）
12. 情景：基准、不利、严重
13. 分红削减风险
14. 买入或加仓条件
15. 减仓或卖出条件
16. 监控表
17. 一句话结论
18. 来源与数据质量

### 发布审核

报告保存后须运行审核流程：
```bash
python tools/common/report_audit.py extract --report reports/{公司名}-income-investment-{YYYYMMDD}.md
python tools/common/report_audit.py verdict --results '<verified JSON>' --report reports/{公司名}-income-investment-{YYYYMMDD}.md
```

---

## 工具依赖

### 本地数据获取工具

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票信息查询 | `python tools/a_share/stock_info.py --search 中国移动` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 600941` |
| A股 | `tools/a_share/stock_quote.py` | 历史股价与实时行情 | `python tools/a_share/stock_quote.py --code 600941` |
| A股 | `tools/a_share/stock_equity.py` | 股权结构与财报下载 | `python tools/a_share/stock_equity.py --code 600941` |
| 港股 | `tools/hk_stock/stock_financial.py` | 港股信息与财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| 港股 | `tools/hk_stock/stock_quote.py` | 港股历史K线 | `python tools/hk_stock/stock_quote.py --code 00700` |
| 美股 | `tools/us_stock/stock_info.py` | 美股信息查询 | `python tools/us_stock/stock_info.py --search Coca-Cola` |
| 美股 | `tools/us_stock/stock_financial.py` | 美股财务指标 | `python tools/us_stock/stock_financial.py --code KO` |
| 美股 | `tools/us_stock/stock_quote.py` | 美股行情数据 | `python tools/us_stock/stock_quote.py --code KO` |

**Python路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

详细使用说明请参考：
- **A股工具**：[docs/A股工具使用指南.md](../../docs/A股工具使用指南.md)
- **港股工具**：[docs/港股工具使用指南.md](../../docs/港股工具使用指南.md)
- **美股工具**：[docs/美股工具使用指南.md](../../docs/美股工具使用指南.md)
- **国际货币汇率**（跨市场收入折算）：`tools/common/fx_rate.py`，详见 [A股工具使用指南汇率章节](../../docs/A股工具使用指南.md)

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（分红率、收益率、估值、市值、三情景） | `python tools/common/financial_rigor.py verify-valuation --pe 15 --eps 5` |
| `tools/common/report_audit.py` | 报告数据抽检与审核（准出流程） | `python tools/common/report_audit.py extract --report reports/xxx.md` |

### 网络搜索工具

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。完整角色定位、市场×场景选型矩阵、命令速查、多源验证示例见 [web-search-tools](../tools-scripts/web-search-tools.md)。

**收入投资分析场景下的搜索选型**：
- A股分红公告/分红政策：anysearch 主 + doubao 辅，须从交易所官方披露确认
- 港股/美股分红历史：港股 doubao + tavily 双源；美股 exa + doubao 双源
- 分红政策/指引变更：doubao --need-content 主 + anysearch 辅，抓取公告正文做精确解读
- 税务/预扣税/协定税率：doubao --finance 主 + anysearch 辅，须标注司法管辖区和生效日期
- 收益陷阱/削减信号：exa --type deep 主 + doubao 辅，深度检索分析师质疑和削减先兆

**搜索规范**（收入投资分析特有）：
- 时效性优先：使用 `--time-range month/week` 限制时间范围，分红公告须覆盖最近一个除息日
- 双源验证：港股 doubao + tavily；美股 exa + doubao；A股 anysearch + doubao
- 分红政策变更须从交易所官方披露确认，不得仅依赖第三方汇总
- 税务信息须标注司法管辖区和生效日期，协定税率因个人情况而异
- 关键信息缺失时标注"信息不足"，不得用推测填充

**重要约束**：
- 估值数据须使用 `financial_rigor.py` 校验，禁止 LLM 心算
- 关键财务数据须至少两个来源交叉验证

---

## 核心原则

1. **高股息率不等于好机会** — 收益率由股价下跌驱动是收益陷阱的典型特征
2. **可分配现金 > 会计利润** — 区分净利润与可重复的自由现金流
3. **分红覆盖是核心** — 净利润/FCF 派息率、利息覆盖、净债务是持久性关键
4. **不跨行业机械套用** — REIT 看 FFO/AFFO，银行看 CET1，保险看偿付能力
5. **税务影响净收入** — 预扣税、协定税率、账户类型决定实际到手收入
6. **组合适配优先于个股质量** — 优质收入证券仍可能因集中度而不宜加仓
7. **成本收益率是回溯信息** — 绝不是继续持有的理由
8. **诚实面对不确定性** — 数据不足时标注 `数据不足`，不用假设填充

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 所有数据必须标注来源，关键财务数据至少两个来源交叉验证
- 估值估算须使用 `tools/common/financial_rigor.py` 精确计算，不得手算
- 跨币种收入折算须用 `tools/common/fx_rate.py` 获取实时汇率，禁用固定汇率
- 分红历史须覆盖至少五年（如可得），包括增加/持平/削减/暂停次数
- 税务信息不完整时只展示毛收入，明确说明净收入不可计算的原因
- 不利和严重情景必须明确测试分红削减，而非假设分红不变
- 报告保存后须运行 `report_audit.py` 审核流程，未通过审核的是草稿
- 不构成投资建议，仅供学习研究参考

---

## 局限性说明

- **数据可得性**：部分港股/美股分红历史可能不完整，需从多个来源拼凑
- **税务复杂性**：预扣税、协定税率因个人情况而异，工具仅提供通用估算
- **估值主观性**：三情景假设存在主观判断，不同方法可能得出不同结论
- **分红非保证**：历史分红不代表未来，公司可随时削减或暂停分红
- **非实时数据**：工具获取的数据可能有延迟，不是实时数据
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [财务数据获取](../financial-data/README.md) — 数据交叉验证规范
- [投资研究](../investment-research/README.md) — 四大师全面基本面研究
- [组合管理](../portfolio-review/README.md) — 组合适配与集中度分析
- [买入前清单](../investment-checklist/README.md) — 最终买入决策清单
- [论文跟踪](../thesis-tracker/README.md) — 投资论文长期跟踪

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-08-07
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。
