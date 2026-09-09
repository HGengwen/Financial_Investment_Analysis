# garp-liquidity-reinvestment 技能建设方案

- 日期：2026-09-06
- 状态：**已确认**（决策点见第九节，已逐条确认，可进入开发）
- 权威口径来源：
  - `research/个人投资者1~3年中长期投资思想与理念 V2.0.md`（中期链唯一权威理念口径，GARP 林奇主轴）
  - `.trae/skills/income-investment/SKILL.md`（长期版收入投资技能，本次「格式与范式」参考）
  - `research/early-version/garp-liquidity-reinvestment-1.md`（底稿一：完整投研草稿）
  - `research/early-version/garp-liquidity-reinvestment-2.md`（底稿二：流动性质量与再投资能力专项草稿）
  - `.trae/skills/garp-ask/SKILL.md`（GARP 问答技能，命名先例 + 四大师分工 + 引用铁律参照）
  - `.trae/skills/valuation-thermometer/SKILL.md`（PEG 五档唯一权威口径）
  - `.trae/skills/exit-signal/SKILL.md`（卖出纪律 P0~P5 唯一权威口径）
  - `.trae/skills/mid-management-deep-dive/SKILL.md`（ROIC / 再投资回报率 / 资本配置 20 分制权威口径）
  - `.trae/skills/mid-investment-research/SKILL.md`（全面公司研究，本技能的边界参照）
  - `research/mid-earnings-review技能建设方案.md`（方案文档格式模板）

---

## 一、背景与问题

1. `.trae/skills/income-investment/SKILL.md` 是**长期收入/分红投资版**（分红历史、派息覆盖、股息率、DDM、收益陷阱），核心目标是「寻找持久可持续的分红收入」，与 `V2.0.md`（1~3 年景气投资，PEG 核心、快速增长型公司、四大师口径）**根本冲突**：一个收息，一个赚「估值 + 业绩」双击，投资逻辑本质对立（草稿二 L5-16 的诊断已有准确结论）。

2. 用户已提供两份改造底稿：
   - **底稿一** `garp-liquidity-reinvestment-1.md`：一份**完整投研技能草稿**（8 步执行流程 + 分类门控 + 12 章报告），内容与现有 `mid-investment-research` / `mid-investment-checklist` / `mid-management-deep-dive` **高度重复**，若单独转正将造成严重的职责重叠。
   - **底稿二** `garp-liquidity-reinvestment-2.md`：前半部分是「income-investment 与 1~3 年景气框架匹配度诊断」（开发过程说明），后半部分是**「流动性质量与再投资能力验证」专项技能草稿**（含 frontmatter、九步流程、判决分类、报告结构）。定位精准、与现有中期技能形成互补，是本技能的正确落点。

3. **本方案的核心判断**：以**底稿二的后半部分（专项验证技能）** 为主体底稿，**底稿一**仅作为理念参考与禁忌边界来源（不转正为独立技能）。理由见第二节第 1 条。

4. 底稿二的改造方向正确（FCF 质量 + 增量 ROIC + 资本配置纪律 + PEG 视角，四大师融入），但存在以下需在转正时修正的问题：

   - **占位残留**：多处写「同原版 `income-investment` 的数据获取工具 / 网络搜索规范 / 数据抽检流程 / 工具使用指南（详见上方）」，但底稿并未包含这些「上方」内容，转正后无法独立执行，必须补齐。
   - **PEG 五档重复定义**：底稿二 L272 自建 `<0.8绝佳 / 0.8~1.2合理 / >1.5高估` 档位，违反「引用不重复定义」铁律，应引用 `valuation-thermometer`。
   - **卖出纪律缺失**：底稿二仅在「判决门控 L304」提到「管理层诚信问题一票否决 → 立即回避」，未引用 `exit-signal` 的 P0~P5，也未与估值透支/逻辑止损联动。
   - **ROIC / 再投资口径需引用权威**：底稿二 L185-201 自建 ROIC 阈值表与增量资本回报率表，其口径与 `mid-management-deep-dive`（L236-237）一致，但应明确**引用**权威口径，避免口径漂移。
   - **关系表命令名混乱**：底稿二 L68-70、L378-379 引用 `/investment-research`（景气版）、`/investment-team`（景气版），应为正式中期命令 `/mid-investment-research`、`/mid-investment-team`；`/portfolio-review` 应标注 `--horizon mid`。
   - **报告命名不合中期链约定**：底稿二 L326 用 `reports/{company}-liquidity-{YYYYMMDD}.md`，未归入 `reports/{公司名}/` 子目录，也未用中期语义前缀。
   - **关系表未覆盖完整闭环**：底稿二关系表缺少 `valuation-thermometer`、`exit-signal`、`mid-industry-research` 等中期闭环关键技能引用。
   - **「修改分析」诊断段落属开发过程说明**：底稿二 L1-40 的匹配度诊断表，转正时删除。

---

## 二、设计原则

### 1. 定位：专项验证技能（不重复造完整投研轮子）

`/garp-liquidity-reinvestment` = **流动性质量与再投资能力专项验证**，聚焦回答一个核心问题：

> **这家快速增长型公司的自由现金流质量如何？管理层在高效地再投资吗？资本配置纪律是否严格？它的成长是建立在大幅账期/股权稀释/债务扩张之上，还是建立在真实的现金创造与高效再投资之上？**

- 它是 **`mid-investment-research`（全面研究）的专项深化**：全面研究给出「这家公司好不好 + 值不值」，本技能给出「它的成长现金流是否扎实、再投资是否创造价值」的专项证据。
- 它是 **`valuation-thermometer`（估价格）的质量互补**：温度计回答「贵不贵」，本技能回答「增长质量真不真、能否撑住估值」。
- 它是 **`mid-management-deep-dive`（管理层）的财务侧延伸**：管理层深挖覆盖「管理层诚信 + 资本配置」的评分维度，本技能以 FCF/再投资为起点做系统化的财务纵深验证。
- **本技能不是**：分红选股工具、股息率筛选器、全面投研报告工具、收入型投资决策工具。
- **本技能不转正底稿一**：底稿一的 8 步完整投研流程与现有 `mid-investment-research` / `mid-investment-checklist` 重复，仅作理念参考。

### 2. 命名规范

`/garp-liquidity-reinvestment`（无 `mid-` 前缀）。理由：

- 中期链技能命名并非一律 `mid-` 前缀。`mid-` 前缀用于「与长期链对应技能做区分」的场合（`mid-earnings-review` vs `earnings-review`、`mid-investment-research` vs `investment-research`）。
- 本技能**没有长期链对应技能**——`income-investment` 虽是来源参照，但定位完全不同（分红收入 vs 流动性/再投资），不构成「同一技能的中期版」。属于 `valuation-thermometer`、`qoq-accelerator`、`exit-signal`、`trend-momentum-scan` 一类「中期独有、无长期对应」的技能，无需 `mid-` 前缀。
- 与 `/garp-ask`（GARP 问答入口，同样无 `mid-` 前缀）构成 **GARP 系列**：`garp-ask` 负责「问答型」、`garp-liquidity-reinvestment` 负责「产出型专项验证」。

（待确认决策点 1）

### 3. 四位大师分工（对齐 V2.0，作为单 Agent 分析维度标尺）

| 大师 | 思维模式 | 在本技能中的维度 |
|------|---------|-----------------|
| 林奇 | 侦探思维 · 常识与求证 | **GARP 主轴 + 分类闸门**：六类分类确认标的适用性（快速增长型/稳定增长型适用，缓慢增长型请转收入投资）；PEG 估值引用 valuation-thermometer；利润真实性直觉（「赚的是真钱还是账面利润」） |
| 郑希 | 物理学家思维 · 周期与第一性原理 | **现金流支撑景气**：ROE 向上必须以真实经营现金流为底（「如果净利润涨但经营现金流萎缩，ROE 向上是虚假的」） |
| 李进 | 系统工程师思维 · 均衡与渗透率 | **再投资效率 + 资本配置**：增量资本回报率 > 存量 ROIC 才创造价值；管理层资本配置记录逐笔评估；治理一票否决 |
| 欧奈尔 | 工程师思维 · 信号与纪律 | **风控底线**：卖出触发一律引用 exit-signal 的 P0~P5，不自行发明；流动性恶化时对应 P4/P5 联动 |

### 4. 引用不重复定义（中期技能体系铁律）

- **PEG 五档** → 引用 `valuation-thermometer`（唯一权威口径），本技能只算 PEG 数值（`financial_rigor.py peg`），档位判定以其输出为准，不自行列出 `<0.8 / 0.8~1.2 / >1.5` 阈值表。
- **卖出纪律** → 引用 `exit-signal` 的 P0~P5（时间止损归 P2，技术面仅作 P3 辅助，不构成独立层级；P0 治理一票否决命中即停）。
- **ROIC / 再投资回报率** → 引用 `mid-management-deep-dive`（其 L236-237 已是权威口径：ROIC>WACC 且≥10% 合格 +1；>15% 优秀 +2；<5% 却仍扩产一票否决；增量资本回报率 > 存量 ROIC = 创造价值 +2）。本技能在**不重复定义阈值**的前提下，展开更细的 FCF 质量 / 资本开支结构 / 再投资充分性 / 财务弹性分析。
- **产业景气 / 渗透率** → 引用 `mid-industry-research`（本技能仅在必要时交叉引用，不重复定义）。
- **管理层 20 分制 / 科研 20 分制** → 引用 `mid-management-deep-dive` 与 V2.0 第二部分。

### 5. 数据规范

双源交叉验证、误差 >1% 标记、禁止 LLM 心算、`financial_rigor.py` 精确计算、`report_audit.py` 抽检准出、`fx_rate.py` 取实时汇率。

### 6. 网络限制

禁止 Anthropic WebSearch/WebFetch，统一本地五工具（anysearch/doubao_search/exa_search/tavily_search/web_search）。

### 7. 执行流程范式

保留长期版 `income-investment` 的「数据质量确立 → 核心分析维度 → 质量评分卡 → 阻断门控 → 判决 → 报告格式 → 发布审核」闭环骨架，将核心维度替换为景气版的「六类分类闸门 → FCF 质量 → 再投资效率 → 资本配置 → 财务弹性 → PEG 安全边际 → 流动性危机情景」。

---

## 三、新建文件清单

| 文件 | 说明 |
|------|------|
| `.trae/skills/garp-liquidity-reinvestment/SKILL.md` | 主技能文件（基于底稿二后半部分 + 第五节修正清单转正） |
| `.trae/skills/garp-liquidity-reinvestment/README.md` | 技能说明（命令、适用场景、与 income-investment / mid-investment-research / mid-management-deep-dive / garp-ask 的边界、输出路径） |

---

## 四、需修改的其他文件清单

| 文件 | 修改点 |
|------|--------|
| `CLAUDE.md` | 「中期投研类（1-3年）」表格新增 `/garp-liquidity-reinvestment {公司名}` 一行（放在 `/garp-ask` 之前或之后，归入 GARP 系列；长期版 `/income-investment` 行在「买入决策类」中不动，见第八节） |
| `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md` | ① 全景图表格新增 `garp-liquidity-reinvestment` 行，归入「③ 个股验证」阶段（作为现金流/再投资质量专项验证）；② 中期技能计数「14 个」→「15 个」，并区分「1 个问答技能 garp-ask」与「1 个 GARP 专项产出技能 garp-liquidity-reinvestment」；③ 六阶段闭环图个股验证分支加入 `garp-liquidity-reinvestment`；④ 附录决策树个股验证分支加入该技能 |

> 注：正式开发前先 grep 全项目确认 `garp-liquidity-reinvestment` / `income-investment` / 流动性质量等引用现状，确保无残留错配；长期链技能（income-investment、investment-research、investment-checklist、portfolio-review 等）内的 `/income-investment` 引用为**长期链自身约定，一律不动**（见第八节）。

---

## 五、草稿修正清单（撰写 SKILL.md 时逐一落实）

以**底稿二**（`garp-liquidity-reinvestment-2.md`）为底稿，按下表转正：

**修正 1 — 保留 frontmatter，微调 description + 去「草稿」**
- 底稿二 L43-47 已有 frontmatter（`name: garp-liquidity-reinvestment` / `disable-model-invocation: true`），保留。
- `description` 对齐 V2.0 四大师口径，追加触发词（流动性质量 / 自由现金流 / FCF / 再投资 / 增量 ROIC / 资本配置 / 现金流验证 / 1-3年 / 中期），并说明与长期版 `/income-investment` 的路由区分。
- 标题（L49）去掉「草稿」语境，文末落款写「V1.0.0」。

**修正 2 — 删除「修改分析」诊断段落（核心）**
- 底稿二 L1-40「修改分析：income-investment 与 1~3 年景气投资框架的匹配度」诊断表 + 「修改后的 income-investment 技能文件（草稿…）」（L40）系开发过程说明，转正时删除。
- 诊断结论中「本技能不替代分红投资分析」一句，作为「设计理念 / 边界」在 SKILL.md 中保留为一行说明。

**修正 3 — 补齐占位残留（核心，多处）**
底稿二以下「同原版…（详见上方）」占位项均须补全为可独立执行内容：
- L125「数据获取工具」→ 补 A股/港股/美股三市场工具命令（参照 `income-investment/SKILL.md` 第一步，A股 stock_info/stock_financial/stock_quote、港股 stock_financial/stock_quote、美股 stock_financial/stock_quote）+ `fx_rate.py` 汇率命令。
- L129「网络搜索规范」→ 补本技能场景搜索选型（FCF/资本开支/并购回购/股权稀释线索：A股 anysearch 主 + doubao 辅；美股 exa --type deep 主 + doubao 辅；现金流失真/应收账款异常线索优先 anysearch --tag finance）。
- L330「数据抽检流程」→ 补 `report_audit.py extract` + `verdict` 完整流程 + Windows 兼容说明（`$null` / `%TEMP%` / `--output-json`）。
- L335-340「工具使用指南」→ 落地为完整的「工具使用指南」列表，不再写「详见上方」。

**修正 4 — PEG 改为引用，不重复定义（核心）**
- 底稿二 L272 PEG 档位自建表（`<0.8绝佳 / 0.8~1.2合理 / >1.5高估`）删除，改为：PEG 数值经 `python tools/common/financial_rigor.py peg --pe {PE} --growth {增速}` 计算，五档判定引用 `valuation-thermometer` 输出。
- 「第七步：估值与安全边际」保留 FCF 收益率、EV/EBITDA 等非 PEG 指标的自由现金流估值视角，明确「FCF 质量是估值安全边际的底层支撑」。

**修正 5 — 补卖出纪律引用（核心）**
- 底稿二仅在「判决门控 L304」写「管理层诚信问题一票否决 → 立即回避」，转正时明确：
  - 「管理层诚信问题」= `exit-signal` 的 **P0 治理一票否决**，命中即停；
  - 本技能不定义卖出级别，涉及估值透支 / 逻辑止损 / 性价比替换时，一律引用 `exit-signal` 的 P0~P5。
- 判决分类（高质量/中等/低质量/数据不足）与 `exit-signal` 的关系说明：**本技能输出的是「流动性质量维度」的专项判决，不替代 `exit-signal` 的组合级卖出决策**；若流动性质量触发「低质量」，应提示进入 `exit-signal` 复核。

**修正 6 — ROIC / 再投资口径引用权威（核心）**
- 底稿二 L185-201 的 ROIC 阈值表、增量资本回报率表删除自建阈值，改为引用 `mid-management-deep-dive` L236-237 口径（文字引用 + 一行「口径以 mid-management-deep-dive 为准」）。
- 本技能保留并展开 `mid-management-deep-dive` 未覆盖的两项纵深：**FCF/净利润比率趋势**（≥4 季度序列）与**资本开支结构**（维护性 vs 扩张性占比）、**再投资充分性**（FCF vs 再投资需求）、**外部融资检查**（股本稀释率/有息负债变化）。

**修正 7 — 关系表命令名修正 + 补闭环（核心）**
- 底稿二 L68-70 关系表、L372-380「与现有 Skill 关系」表：
  - `/investment-research`（景气版）→ `/mid-investment-research`
  - `/investment-team`（景气版）→ `/mid-investment-team`
  - `/portfolio-review` → `/portfolio-review {持仓清单} --horizon mid`
  - 补 `/valuation-thermometer`（PEG 五档）、`/exit-signal`（P0~P5）、`/mid-industry-research`（产业景气/渗透率）三个中期闭环技能。
  - 明确与 `/mid-management-deep-dive` 的分工：前者是「管理层诚信 + 资本配置的 20 分制评分」，本技能是「FCF/再投资/财务弹性的系统化纵深验证」，二者口径一致、职责互补。

**修正 8 — 报告命名归入中期链子目录（核心）**
- 底稿二 L326 `reports/{company}-liquidity-{YYYYMMDD}.md` → 对齐中期链 `reports/{公司名}/{公司名}-garp-liquidity-{YYYYMMDD}.md`（见第六节，待确认决策点 2）。

**修正 9 — 保留内容（不修改）**
- 林奇六类分类适用性表（快速增长型最适用 / 稳定增长型适用 / 缓慢增长型不适用 → 转 income-investment）。
- 利润质量检验四表（FCF/净利润、经营现金流/净利润、应收周转、存货周转）与 ≥4 季度趋势模板。
- 资本开支结构分析（扩张性占比 >60% 为成长型特征；扩张+ROIC<WACC = 毁灭式扩张）。
- 增量资本回报率判断（>存量 ROIC 创造价值 / ≈ 维持 / < 稀释）。
- 资本配置决策记录 + 评分（李进维度 C）。
- 资产负债强度（净现金/净负债、有息负债/EBITDA、利息覆盖率、流动性比率）与财务弹性。
- 三情景估值命令 + 流动性危机情景分析。
- 判决分类（高质量/中等质量/低质量/数据不足）+ 阻断门控列表。
- 报告结构 11 节 → 转正后对齐为与 `income-investment` 等观的标准节次。

---

## 六、报告输出路径

`reports/{公司名}/{公司名}-garp-liquidity-{YYYYMMDD}.md`

- 用 `-garp-liquidity-` 区分：
  - 长期版收入投资：`reports/{公司名}-income-investment-{YYYYMMDD}.md`（不变）
  - 全面研究中期版：`reports/{公司名}/{公司名}-mid-investment-research-{YYYYMMDD}.md`
  - 本技能：`reports/{公司名}/{公司名}-garp-liquidity-{YYYYMMDD}.md`（单文件，归入公司子目录）

---

## 七、实施步骤顺序

1. 撰写 `.trae/skills/garp-liquidity-reinvestment/SKILL.md`（按第五节修正清单，以底稿二后半部分为底稿逐项落实）
2. 创建 `.trae/skills/garp-liquidity-reinvestment/README.md`
3. 更新 `CLAUDE.md` 中期投研类表格
4. 更新 `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md`（见第四节）
5. grep 全项目复查 `garp-liquidity-reinvestment` / `income-investment` 引用无残留错配、无命令名混淆

---

## 八、长期版不动声明

以下长期链文件**一律不动**：

- `.trae/skills/income-investment/SKILL.md` 及其 README
- `.trae/skills/证券AI价值投资研究工作步骤.md`（10 年长期链）
- 其他长期链技能中对 `/income-investment` 的跨引用（investment-research、investment-checklist、portfolio-review、thesis-tracker 等）

中期版 `garp-liquidity-reinvestment` 仅通过「中期投研类」与「中长期工作步骤」两个入口挂载，不改写长期链既有引用。

---

## 九、决策点确认记录（2026-09-06 已逐条确认）

| # | 决策点 | 确认结果 |
|---|--------|---------|
| 1 | 命令命名 | **确认** `/garp-liquidity-reinvestment {公司名}`（无 `mid-` 前缀），与 `garp-ask` 构成 GARP 系列 |
| 2 | 底稿取舍 | **确认** 以底稿二后半部分（专项流动性/再投资验证）为主体底稿；底稿一完整投研草稿不转正，仅作理念参考 |
| 3 | 报告命名 | **确认** `reports/{公司名}/{公司名}-garp-liquidity-{YYYYMMDD}.md`（归入公司子目录，加 garp-liquidity 前缀） |
| 4 | CLAUDE.md 归位 | **确认** 「中期投研类（1-3年）」表格，与 `/garp-ask` 相邻；长期版 `/income-investment` 保留在「买入决策类」不动 |
| 5 | 工作步骤文档归位 | **确认** 归入「③ 个股验证」阶段；中期技能计数「14 → 15」，区分问答技能 garp-ask 与产出技能 garp-liquidity-reinvestment |
| 6 | PEG 引用方式 | **确认** 引用 `valuation-thermometer` 五档（`financial_rigor.py peg` 计算数值），删除底稿二自建阈值表 |
| 7 | 卖出纪律引用方式 | **确认** 引用 `exit-signal` 的 P0~P5（P0 治理一票否决命中即停）；本技能输出「流动性质量」专项判决，不替代 exit-signal 组合级卖出决策 |
| 8 | ROIC/再投资口径 | **确认** 引用 `mid-management-deep-dive` ROIC/增量资本回报率口径，本技能只展开 FCF 质量 / 资本开支结构 / 再投资充分性 / 财务弹性纵深 |
| 9 | 交付范围 | **确认** 本轮仅交付 `garp-liquidity-reinvestment`（产出型 GARP 专项技能），长期链 `income-investment` 继续保留 |

> 以上确认结果已同步落实到第二节（设计原则）、第三节（新建文件）、第四节（修改文件）、第五节（草稿修正清单）与第六节（报告输出路径），后续开发按第七节实施步骤执行。