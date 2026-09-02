# Sprint 5 开发方案与详细实施计划（文档与路由）

> 依据：`research/个人投资者1~3年中长期投资思想与理念 V2.0.md` 与 `research/1~3 年中长期投研系统完整开发方案与详细实施计划.md` 第八节。
>
> 数据截止日期：2026-08-30
>
> 审核状态：**D-1、D-2 两项决策已由用户确认接受，可直接进入开发执行。**
>
> 免责声明：本方案用于学习与研究，不构成投资建议。

---

## 一、Sprint 5 定位与目标

Sprint 5 是中期闭环的**最后一公里**：前四个 Sprint 已交付 6 个新增技能 + 2 个增强技能（`--horizon mid`），但用户尚缺一个**入口**把整条中期链串起来。Sprint 5 不写任何技能逻辑，只做三件事：

| 任务 | 产出物 | 工作量 |
| --- | --- | --- |
| 任务 1：编写中期导航文档 | `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md` | 1 天 |
| 任务 2：修改 CLAUDE.md | 技能表新增 7 行（中期投研类）+ 路由规则段落 | 0.25 天 |
| 任务 3：修改长期导航文档 | "目标 3.6"补充指向 + 命名残留同步 | 0.25 天 |

**目标**：打通"选股之后"的中期闭环入口；用户按持有周期关键词或 `/mid-xxx` 显式调用，即可被正确路由到中期链，且六阶段闭环无断点。

---

## 二、前置现状核查结论（已逐项核实代码库）

| 项 | 实施计划要求 | 实际状态 | 对 Sprint 5 的影响 |
| --- | --- | --- | --- |
| `mid-trend-tech-screen` 重命名（F-7） | Sprint 0 完成 | ✅ 已重命名（原 `trend-tech-screen` 目录已消失） | 无 |
| 6 个新增技能目录 | Sprint 1~3 完成 | ✅ 全部存在（含 SKILL.md + README.md） | 无 |
| `thesis-tracker --horizon mid` | Sprint 4 完成 | ✅ 已实现 | 无 |
| `portfolio-review --horizon mid` | Sprint 4 完成 | ✅ 已实现 | 无 |
| 中期导航文档 | Sprint 5 新建 | ❌ **不存在** | 本次核心交付 |
| CLAUDE.md 技能表/路由 | Sprint 5 修改 | ❌ 未新增 6 个中期技能、无路由规则 | 本次交付 |
| 长期导航文档"目标 3.6"指向 | Sprint 5 修改 | ❌ 未补充指向 | 本次交付 |
| `reports/exit-signals/` 目录 | Sprint 0 新建 | ❌ **未创建**（仅 `valuation/` 已建） | 前置清理项（D-2） |
| 长期文档 `/trend-tech-screen` 残留 | Sprint 0 全量同步 | ⚠️ 第 123 行仍写 `/trend-tech-screen`（第 903 行决策树已同步） | 前置清理项（D-2） |
| 长期文档"22 个技能"口径 | Sprint 0（F-1） | ⚠️ 第 3、21 行仍为"22 个技能"（应为 21） | 前置清理项（D-2） |

> 结论：Sprint 5 的**前置技能依赖全部就绪**；存在 3 项 Sprint 0 遗留清理项，已确认随 Sprint 5 一并处理（D-2），否则路由验收 R-5 与长期文档一致性无法达标。

---

## 三、任务分解总览

```
Sprint 5（1.5 天）
├── 前置清理（0.25 天，随任务 2/3 顺带完成）
│   ├── C-1 创建 reports/exit-signals/ 目录
│   ├── C-2 长期文档 /trend-tech-screen → /mid-trend-tech-screen 残留同步
│   └── C-3 长期文档 "22 个技能" → "21 个技能" 口径同步
├── 任务 1：中期导航文档（1 天）
├── 任务 2：CLAUDE.md 修改（0.25 天）
└── 任务 3：长期导航文档修改（0.25 天）
```

---

## 四、任务 1：编写中期导航文档（1 天）

### 4.1 文档元信息

- **路径**：`.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md`（与长期文档同级，双轨并存）
- **数据截止日期**：2026-08-30（开工前运行 `date` 确认，写入头部）
- **免责声明**：仅供学习研究参考，不构成投资建议

### 4.2 完整章节结构（逐章要点）

```
# 证券AI中长期（1~3年）价值投资研究工作步骤
一、中期技能全景图（7 个中期技能 + 2 个增强模式）
二、六阶段闭环工作流程（核心）
三、决策优先级金字塔（P0~P5）
四、底仓/机动仓分离规则
五、与长期文档的关系与路由规则
六、数据与工具依赖（复用长期文档工具总览，不重复罗列）
七、全局约束（引用研究质量规则 6 条）
附录：中期技能速查决策树
```

### 4.3 关键内容设计

**(1) 中期技能全景图（共 7 技能，按六阶段排列）**

| 阶段 | 技能 | 命令 | 输出路径 |
| --- | --- | --- | --- |
| ① 行业扫描 | 中期行业景气研究 | `/mid-industry-research {行业名}` | `reports/{行业名}-mid-industry-{YYYYMMDD}.md` |
| ② 正向排序 | 景气趋势筛选 | `/mid-trend-tech-screen {公司/行业/指数/主题}` | `reports/trend-screen/{标的}-trend-screen-{YYYYMMDD}.md` |
| ③ 个股验证 | 复用长期 `investment-research`/`investment-checklist`/`management-deep-dive` | — | `reports/{公司名}/` |
| ④ 估值择时 | 估值温度计 | `/valuation-thermometer {公司名}` | `reports/valuation/{公司名}-valuation-{YYYYMMDD}.md` |
| ④ 估值择时 | 季度加速度 | `/qoq-accelerator {公司名}` | `reports/{公司名}/{公司名}-qoq-{YYYYMMDD}.md` |
| ⑤ 持仓管理 | 持仓动量体检 | `/trend-momentum-scan {持仓代码}` | `reports/{公司名}/{公司名}-momentum-{YYYYMMDD}.md` |
| ⑤ 持仓管理 | 中期逻辑漂移 | `/mid-thesis-drift {标的}` | `reports/{公司名}/{公司名}-mid-drift-{YYYYMMDD}.md` |
| ⑤ 持仓管理 | 论文追踪（中期） | `/thesis-tracker {公司名} --horizon mid` | `reports/{公司名}/{公司名}-mid-thesis.md` |
| ⑤ 持仓管理 | 组合审视（中期） | `/portfolio-review {持仓清单} --horizon mid` | `reports/portfolio-{YYYYMMDD}.md` |
| ⑥ 卖出触发 | 卖出信号 | `/exit-signal {标的}` | `reports/exit-signals/{公司名}-exit-{YYYYMMDD}.md` |

**(2) 六阶段闭环工作流**（与实施计划 7.2 完全一致）

```
行业扫描 ──► 正向排序 ──► 个股验证 ──► 估值择时 ──► 持仓管理 ──► 卖出触发
mid-industry-research  mid-trend-tech-screen  investment-research  valuation-thermometer  thesis-tracker --horizon mid  exit-signal
bottleneck-hunter                            investment-checklist  qoq-accelerator       trend-momentum-scan
                                             management-deep-dive                         mid-thesis-drift
                                                                                          portfolio-review --horizon mid
```

**(3) 决策优先级金字塔（硬编码，与 `exit-signal` P0~P5 完全对齐）**

| 优先级 | 触发条件 | 决策 |
| --- | --- | --- |
| P0 治理一票否决 | 管理层失信/财务造假实锤/监管立案 | 立即清仓 |
| P1 硬止损 | 单笔亏损 8%~10% 且无基本面反转 | 无条件止损 |
| P2 逻辑止损 | 连续 2 季低于预期且景气未改善；或满 4 季度未兑现 | 减仓或清仓 |
| P3 产业景气拐点 | 渗透率减速 / ROE 拐头向下 | 减机动仓 |
| P4 估值透支 | PEG>1.5 减机动仓；PEG>2 加速清机动仓 | 减/清机动仓 |
| P5 性价比替换 | 替代标的 PEG 显著更低且趋势更强 | 调仓（每季度≤1 次） |

**(4) 路由规则段落**（与任务 2 CLAUDE.md 保持一致，避免两处口径漂移）

**(5) 附录：中期技能速查决策树**

```
你的中期投研诉求是什么？
├── 选赛道 → /mid-industry-research
├── 在赛道内排序领涨标的 → /mid-trend-tech-screen
├── 验证候选公司 → /investment-research + /investment-checklist
├── 判断估值/买卖区间 → /valuation-thermometer + /qoq-accelerator
├── 检查持仓趋势是否走坏 → /trend-momentum-scan
├── 检查景气逻辑是否漂移 → /mid-thesis-drift
├── 建立/检查中期论文 → /thesis-tracker --horizon mid
├── 审视中期组合 → /portfolio-review --horizon mid
└── 判断该不该卖 → /exit-signal
```

---

## 五、任务 2：修改 CLAUDE.md（0.25 天）

### 5.1 技能表新增"中期投研类（1-3年）"分类

在现有七大类基础上，新增一个独立分类（置于"买入决策类"之后、"财报跟踪类"之前），共 7 个中期技能：

| 命令 | 功能 |
| --- | --- |
| `/mid-industry-research {行业名}` | 中期行业景气研究：TAM/渗透率/业绩兑现/地缘风险四维筛选 |
| `/mid-trend-tech-screen {公司/行业/指数/主题}` | 景气趋势筛选：五维打分 + 地缘修正 + 技术面止损，1-3 年正向排序 |
| `/valuation-thermometer {公司名}` | 估值温度计：PEG/PSG/PE分位/implied-growth 五档温度 |
| `/qoq-accelerator {公司名}` | 季度加速度：连续 3 季二阶导，区分波动与拐点 |
| `/trend-momentum-scan {持仓代码}` | 持仓动量体检：SMR/RSI50/MA50/MA200 技术破位预警 |
| `/mid-thesis-drift {标的}` | 中期逻辑漂移：景气假设六大维度逐条验证 |
| `/exit-signal {标的}` | 卖出信号：P0~P5 六级优先级硬编码检查 |

> **已确认决策（D-1）**：`mid-trend-tech-screen` 从 CLAUDE.md"买入决策类"**移入**新设的"中期投研类"，保持中期链一目了然。

### 5.2 新增路由规则段落

在"Skill 使用"章节末尾追加：

```markdown
## 持有周期路由规则（中期 vs 长期）

- **中期链（1-3 年）**：提及「1-3 年 / 中期 / 景气 / 趋势 / 成长爆发」→
  `mid-industry-research` → `mid-trend-tech-screen` → `valuation-thermometer` → `qoq-accelerator`
  → `trend-momentum-scan` → `mid-thesis-drift` → `exit-signal`
- **长期链（10 年）**：提及「10 年 / 长期 / 永续 / 护城河」→
  `quality-screen` → `investment-research` → `thesis-tracker` → `thesis-drift`
- **`mid-` 前缀显式调用优先匹配**：`/mid-xxx` 直接命中对应中期技能，不受关键词路由影响
- **持有周期不明**：先询问用户持有周期（1-3 年 or 10 年）再路由
```

### 5.3 技能总数口径

- 第 27 行"共 **21 个技能**" → 改为"共 **27 个技能**"（21 存量 + 6 新增）。
- 目录结构一节（第 19 行）"21 个 SKILL.md" → "27 个 SKILL.md"。

---

## 六、任务 3：修改长期导航文档（0.25 天）

文件：`.trae/skills/证券AI价值投资研究工作步骤.md`

| 位置 | 现状 | 修改 |
| --- | --- | --- |
| 第 117~124 行"目标 3.6" | 仅有表格 | 表格后追加一行：`> 完整的中期闭环（估值择时→持仓管理→卖出触发）见《证券AI中长期（1~3年）价值投资研究工作步骤.md》` |
| 第 123 行 | `/trend-tech-screen` 残留 | 改为 `/mid-trend-tech-screen` |
| 第 3、21 行 | "22 个技能" | 改为 "21 个技能"（F-1 口径同步） |

> "阶段二：快速筛选"（第 231 行）选股路由**保持不变**——已正确实现"1-3 年→`mid-trend-tech-screen`、10 年→`quality-screen`"。

---

## 七、前置清理项（0.25 天，已确认随 Sprint 5 一并处理）

| 编号 | 清理项 | 操作 |
| --- | --- | --- |
| C-1 | `reports/exit-signals/` 未创建 | 新建空目录（`exit-signal` 技能输出依赖） |
| C-2 | 长期文档 `/trend-tech-screen` 残留 | 已并入任务 3 |
| C-3 | 长期文档"22 个技能"口径 | 已并入任务 3 |

> **已确认决策（D-2）**：以上 3 项 Sprint 0 遗留清理项随 Sprint 5 一并处理。

---

## 八、产出物清单

| 产出物 | 类型 | 状态 |
| --- | --- | --- |
| `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md` | 新建 | 本次交付 |
| `CLAUDE.md`（技能表 + 路由规则 + 27 技能口径） | 修改 | 本次交付 |
| `.trae/skills/证券AI价值投资研究工作步骤.md`（目标 3.6 指向 + 命名/口径同步） | 修改 | 本次交付 |
| `reports/exit-signals/` 目录 | 新建 | 前置清理 |

---

## 九、退出条件（DoD）

1. 中期导航文档可**独立通读**，六阶段闭环无断点（每个阶段均标注技能、命令、输出路径）。
2. 中期导航文档中的技能命令/输出路径与各技能 SKILL.md 实际 `name`、输出路径**逐字一致**（已核实 9 个 SKILL.md）。
3. CLAUDE.md 路由规则与附录 A（实施计划）完全一致。
4. 抽查关键词「1-3 年 / 景气 / 趋势 / 中期」能触发中期链；「10 年 / 长期 / 护城河」触发长期链；`/mid-trend-tech-screen` 等 `/mid-xxx` 显式调用直接命中。
5. 长期文档"目标 3.6"已指向中期导航文档；`/trend-tech-screen` 残留清零；"22 个技能"口径修正为"21 个"。
6. `git status` 确认新增/修改文件齐全，无遗漏；`reports/exit-signals/` 目录存在。

---

## 十、验收用例（对应实施计划 10.3 路由与集成）

| 编号 | 输入 | 预期路由 |
| --- | --- | --- |
| R-1 | "1-3 年" / "中期" / "景气" / "趋势" | 中期链 |
| R-2 | `/mid-trend-tech-screen` | 直接命中，归中期链 |
| R-3 | `/mid-industry-research`、`/mid-thesis-drift` | 直接命中 |
| R-4 | `/exit-signal`、`/valuation-thermometer` | 功能命名技能正确触发（无 `mid-` 前缀，不误判长期） |
| R-5 | "10 年" / "长期" / "护城河" | 长期链 |
| R-6 | 持有周期不明 | 询问用户后再路由 |

---

## 十一、风险与应对

| 风险 | 影响 | 应对 |
| --- | --- | --- |
| 中期导航文档与 SKILL.md 实际参数不一致 | 用户按文档操作失败 | DoD-2 强制逐字核对；文档引用参数仅列已核实字段（`--scope/--depth/--quarters/--horizon mid` 等） |
| CLAUDE.md 与中期导航文档路由规则漂移 | 两处口径打架 | 路由规则在 CLAUDE.md 定义**唯一权威版**，中期导航文档只做引用链接 |

---

## 十二、排期

| 步骤 | 内容 | 用时 |
| --- | --- | --- |
| 前置清理 C-1~C-3 | 建目录 + 长期文档口径/命名同步 | 0.25 天 |
| 任务 1 | 编写中期导航文档 | 1 天 |
| 任务 2 | CLAUDE.md 修改 | 0.25 天 |
| 任务 3 | 长期文档"目标 3.6"指向 | 0.25 天 |
| **合计** | | **1.5 天** |

---

## 附：已确认决策记录

| 编号 | 决策内容 | 结论 | 确认时间 |
| --- | --- | --- | --- |
| D-1 | `mid-trend-tech-screen` 从 CLAUDE.md"买入决策类"移入新设"中期投研类" | **移入** | 2026-08-30 |
| D-2 | 3 项 Sprint 0 遗留清理项（exit-signals 目录、trend-tech-screen 残留、22→21 口径）随 Sprint 5 一并处理 | **一并处理** | 2026-08-30 |
