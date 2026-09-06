# mid-earnings-team 技能建设方案

- 日期：2026-09-05
- 状态：**待用户确认**（确认后方可进入开发）
- 权威口径来源：
  - `research/个人投资者1~3年中长期投资思想与理念 V2.0.md`（中期链唯一权威理念口径）
  - `.trae/skills/earnings-team/SKILL.md`（长期版财报团队技能，格式范式参考）
  - `.trae/skills/exit-signal/SKILL.md`（卖出纪律 P0~P5 唯一权威口径）
  - `.trae/skills/valuation-thermometer/SKILL.md`（PEG 五档唯一权威口径）
  - `.trae/skills/mid-industry-research/SKILL.md`（产业景气/渗透率唯一权威口径）
  - `.trae/skills/mid-management-deep-dive/SKILL.md`（管理层 20 分制 / 科研转化 20 分制口径）
  - `.trae/skills/mid-investment-team/SKILL.md`（中期版团队技能执行流程范式参考）
  - `research/mid-investment-team技能建设方案.md`（方案文档格式模板）

---

## 一、背景与问题

当前 `.trae/skills/earnings-team/SKILL.md` 是**长期价值投资版**（段永平-巴菲特-芒格-李录口径，10 年持有，护城河/终局思维），与 `V2.0.md`（欧奈尔-林奇-郑希-李进口径，1~3 年景气投资）不匹配。

`research/early-version/earnings-team技能文件（草稿）.md` 是参考长期版后、针对 1~3 年目标修改的草稿（frontmatter `name: mid-earnings-team` 已正确），且其四大师分工**基本已替换为景气版**（林奇=生意与估值、郑希=ROE与景气、欧奈尔=趋势与纪律、李进=治理与风险）。但草稿仍存在以下需在转正时修正的问题：

1. **卖出纪律使用草稿自造的 P0~P6**（权威口径应为 P0~P5，时间止损归 P2，技术面不构成独立层级）。
2. **PEG 五档自行重复定义**，且把「渗透率修正」叠加进估值表（违反「引用不重复定义」）。
3. **李进职责缺「组合管理」**：草稿把李进定位为「治理与风险评估师」，缺少 V2.0 中「底仓/机动仓分离、渗透率定位、决策优先级执行」的组合管理职责。
4. **多处「同原版」占位**：草稿在 PDF 工具、读者评审输出、Team Lead 定稿、数据抽检、工具使用指南、注意事项、局限性等章节用「同原版」代替实际内容，转正后会导致技能不自洽（一旦脱离长期版即失效）。
5. **输出文件命名与长期版冲突**：草稿沿用 `{公司名}-earnings-{期间}.md`，与长期版完全相同，会互相覆盖。
6. **与现有 Skill 关系表错误**：把本技能写成「`/earnings-team`（本Skill，景气版）」，并引用不存在的「`/investment-team`（景气版）」「`/investment-checklist`（景气版）」。
7. **草稿开头重复**：标题与描述段落出现两次（L46-52 与 L78-82）。
8. **附录 C「与原版差异对照表」属开发过程说明**，转正时应删除。
9. **frontmatter description 未含触发词**，且未说明与长期版技能的路由区分。

---

## 二、设计原则

1. **物理隔离**：中期链（1~3 年）与长期链（10 年）口径分离，禁止「护城河永续」「终局思维」「封仓十年」等长期术语；采用欧奈尔-林奇-郑希-李进四大师口径。

2. **四位大师分工（对齐 V2.0「四位大师与个人投资者的连接方式」表）**：

   | 大师 | 思维模式 | 在财报精读中的角色 |
   |------|---------|-------------------|
   | 欧奈尔 | 工程师思维 · 信号与纪律 | **风控底线**：趋势信号、8%~10% 止损位更新、机构动向、抛售信号 |
   | 林奇 | 侦探思维 · 常识与求证 | **生意与估值**：六类分类复核、生意常识验证、收入量价拆解、PEG 估值更新、估值陷阱排查 |
   | 郑希 | 物理学家思维 · 周期与第一性原理 | **产业景气验证**：ROE 趋势/拐点、二阶导、渗透率位置、供需格局、景气卖出信号 |
   | 李进 | 系统工程师思维 · 均衡与渗透率 | **组合管理 + 治理**：管理层 20 分制、科研转化 20 分制、地缘政治六维度、治理一票否决、底仓/机动仓分离、决策优先级执行 |

3. **引用不重复定义**（中期技能体系铁律）：
   - 估值档位 → 引用 `valuation-thermometer`（PEG 五档判定/边界约定一律以其输出为准，不自行重复列出阈值）
   - 卖出纪律 → 引用 `exit-signal`（P0~P5 唯一权威口径，时间止损归 P2，技术面仅作 P3 辅助、不构成独立层级）
   - 产业景气/渗透率 → 引用 `mid-industry-research`
   - 管理层 20 分制 / 科研转化 20 分制 → 引用 `mid-management-deep-dive` 与 V2.0 理念文档
   - 季度加速度/二阶导 → 引用 `qoq-accelerator`（财报精读中仅作辅助判断，不重复定义其完整算法）

4. **数据规范**：双源交叉验证、误差 >1% 标记、禁止 LLM 心算、`financial_rigor.py` 精确计算、`report_audit.py` 抽检准出。

5. **网络限制**：禁止 Anthropic WebSearch/WebFetch，统一本地五工具（anysearch/doubao_search/exa_search/tavily_search/web_search）。

6. **执行流程范式**：保留长期版三阶段六 Agent 框架（研究 → 合成 → 发布），补齐「信息丰富度评估 → A 股 PDF 下载先决 → 4 Agent 并行 → 进度跟踪 → Team Lead 汇总 → 报告保存 → 数据抽检准出」完整闭环。

---

## 三、新建文件清单

| 文件 | 说明 |
|------|------|
| `.trae/skills/mid-earnings-team/SKILL.md` | 主技能文件（基于草稿 + 第五节修正清单转正） |
| `.trae/skills/mid-earnings-team/README.md` | 技能说明（命令、适用场景、与长期版差异、输出路径） |

---

## 四、需修改的其他文件清单

| 文件 | 修改点 |
|------|--------|
| `CLAUDE.md` | 「中期投研类（1-3年）」表格新增 `/mid-earnings-team {公司名} {期间}` 一行（长期版 `/earnings-team` 行在「财报跟踪类」中不动，见第八节） |
| `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md` | ① 全景图表格（L29-45）新增 `mid-earnings-team` 行，归入「⑤ 持仓管理」阶段（已确认，决策点 4）；② L3/L27「12 个中期技能」→「13 个」；③ L49 说明段「12 个中期技能」清单补 `mid-earnings-team`；④ 六阶段闭环图（L57-70）持仓管理分支加入 `mid-earnings-team`；⑤ 组合 4「财报季全套流程」（L394-406）将 `earnings-review` 替换/并列 `mid-earnings-team`；⑥ 附录决策树财报表跟踪分支加入 `/mid-earnings-team` |

> 注：经 Grep 确认，`mid-*` 各中期技能内暂无对 `earnings-team` 的跨引用；长期链技能（earnings-review、investment-team、news-pulse、wechat-article、thesis-drift、thesis-tracker、portfolio-review、financial-data 等）内的 `/earnings-team` 引用为**长期链自身约定，一律不动**（见第八节）。

---

## 五、草稿修正清单（撰写 SKILL.md 时逐一落实）

**修正 1 — frontmatter 重写**
- `name: mid-earnings-team` 保留（草稿已正确）。
- 保留 `disable-model-invocation: true`（与长期版一致，用户显式 `/mid-earnings-team` 调用）。
- description 重写为对齐 V2.0 的四大师分工，追加触发词说明（中期 / 1-3年 / 景气财报团队 / 财报季验证景气逻辑 / 更新卖出纪律），并明确与长期版 `/earnings-team` 的路由区分。

**修正 2 — 李进职责补「组合管理」（对齐 V2.0）**

草稿四大师分工基本正确（林奇=生意与估值、郑希=产业景气、欧奈尔=风控、李进=治理），仅需微调：

| Agent | 大师 | 修正后职责 |
|-------|------|-----------|
| Agent 1 | 林奇 | 六类分类复核、生意常识、收入量价拆解、PEG 更新（引用 valuation-thermometer）、估值陷阱排查 |
| Agent 2 | 郑希 | ROE 趋势/拐点、二阶导（辅助，主锚引用 qoq-accelerator）、渗透率位置、供需格局、景气卖出信号 |
| Agent 3 | 欧奈尔 | 趋势信号、止损位更新、机构动向、抛售信号、CAN-SLIM（如适用） |
| Agent 4 | 李进 | 管理层 20 分制、科研转化 20 分制、地缘政治六维度、治理一票否决 + **底仓/机动仓分离、决策优先级执行、四大矛盾化解落地** |

> 草稿在「仓位管理框架」「四大核心矛盾」章节已含组合管理内容，但未明确归属李进；转正时将这些段落挂靠到 Agent 4（李进）职责下，并在「阶段二 Team Lead 合成」中明确由李进视角输出底仓/机动仓建议。

**修正 3 — P0~P6 → P0~P5（核心修正）**
- 草稿 L74、L89、L393-403 决策优先级金字塔、L449-458 卖出触发检查表、L858-865 附录 B、L878/L883 附录 C 中的 P0~P6 全套，改为**文字引用** `exit-signal` 的 P0~P5 映射（已确认，决策点 5：SKILL.md 内不重复定义、不自建表格）。SKILL.md 中仅作如下文字性说明，不再列出完整表格：
  - 六层映射关系（P0 治理一票否决 / P1 硬止损 / P2 逻辑止损含时间止损 / P3 产业景气拐点 / P4 估值透支 / P5 性价比替换）的**触发条件与决策细节一律以 `exit-signal` 输出为准**；
  - 财报精读中「卖出纪律更新」章节的任务是：逐一核对 `exit-signal` 的 P0~P5 各层是否被新财报数据触发，并输出「是否触发 + 对应层级 + 建议动作」，不自行定义阈值；
  - 时间止损归 P2，技术面仅作 P3 辅助、不构成独立层级；
  - 核心原则统一为「P0 > P1 > P2 > P3 > P4 > P5，命中即停，禁止跳过 P0」。

**修正 4 — PEG 五档改为引用，不重复定义（核心修正）**
- 草稿 L186-203 删除自行列出的 PEG 五档表（含「底仓操作/机动仓操作/渗透率修正」列），改为引用 `valuation-thermometer` 输出的五档温度。
- 「渗透率作为估值修正因子」不再在估值表内叠加，而是归入郑希「产业景气/渗透率位置」判断（引用 `mid-industry-research`），由 Team Lead 在合成时交叉比对，而非在 PEG 数值上自行加减。
- 三种估值陷阱提醒（低 PE 陷阱 / 高 PE 不可持续 / 忽略股权稀释）保留并随估值职责明确归属林奇。

**修正 5 — 补齐「同原版」内容（核心修正）**
- 草稿中以下占位章节必须补齐为可独立运行的完整内容，不得依赖长期版：
  - L125「PDF 文档阅读工具」（补 `pdf_extract.py` 首选 + Poppler 回退 + 乱码/OCR 说明）
  - L534「读者评审输出格式」、L538「Team Lead 定稿流程」
  - L711「数据抽检（准出流程）」（补 `report_audit.py extract → verdict` 完整命令）
  - L717「工具使用指南」（补三市场工具 + 财报下载 + PDF + 精确计算 + 网络五工具）
  - L736「注意事项」、L757「局限性」

**修正 6 — 输出文件命名改为中期版**
- 草稿 L694-705 输出文件统一加 `mid` 前缀，与长期版物理隔离：

```
reports/{公司名}/
├── {公司名}-mid-earnings-{期间}.md           ← 最终公众号文章（定稿）
├── {公司名}-mid-earnings-{期间}-研究底稿.md   ← 四大师合成研究报告（自用）
├── {公司名}-mid-earnings-{期间}-林奇.md       ← 生意分类与估值解读
├── {公司名}-mid-earnings-{期间}-郑希.md       ← ROE与景气验证
├── {公司名}-mid-earnings-{期间}-欧奈尔.md     ← 趋势与纪律审计
├── {公司名}-mid-earnings-{期间}-李进.md       ← 组合管理与治理评估
└── {公司名}-mid-earnings-{期间}-读者评审.md   ← 读者评审报告
```

**修正 7 — 修正「与现有 Skill 关系」表**
- 草稿 L766-768 表中：
  - 「`/earnings-team`（本Skill，景气版）」→「`/mid-earnings-team`（本Skill）」
  - 「`/investment-team`（景气版）」→「`/mid-investment-team`（中期版）」
  - 「`/investment-checklist`（景气版）」→「`/mid-investment-checklist`（中期版）」
- 补充中期链相关技能引用（`exit-signal`、`valuation-thermometer`、`mid-industry-research`、`mid-management-deep-dive`、`qoq-accelerator`）。

**修正 8 — 删除重复开头与开发过程说明**
- 草稿 L46-52 与 L78-82 标题/描述重复，转正时仅保留一份。
- 草稿 L869-892 附录 C「与原版差异对照表（12 维度）」属草稿开发过程说明，正式 SKILL.md 不保留。

**修正 9 — 补齐执行流程范式**
- 在草稿现有「第一步获取资料 → 第二步展示团队框架 → 第三步 4 Agent 并行 → 第四步跟踪进度」基础上，参照长期版补齐：
  - 资料可得性评级（A/B/C 级）作为独立步骤，明确告知每个研究 Agent 影响其分析深度；
  - 阶段二 Team Lead 汇总后，新增「保存报告」步骤（研究底稿 + 各 Agent 底稿 + 定稿）；
  - 阶段三后新增「数据抽检准出」步骤（`report_audit.py`, 通过方可发布）。

**修正 10 — 保留内容（不修改）**
- 能力圈声明（适用科技/医药/高端制造/景气周期成长股，渗透率 10%~30% 黄金区；不适用纯周期/困境反转/金融/被动指数）。
- 与段永平价值投资的关系说明（段永平仅作哲学补充，不参与估值/择时/止损层）。
- 六类分类复核、ROE 八季度趋势、二阶导、渗透率位置、左侧 vs 右侧策略匹配。
- 管理层四维度 20 分制、科研转化 20 分制、地缘政治六维度、华为式抗封锁韧性框架。
- 底仓（60%~80%）/ 机动仓（20%~40%）分离、分批建仓规则、行业分散与个股集中表。
- 四大核心矛盾与化解方案、「假如空仓」测试、季度复盘 7 项必查、三种估值陷阱提醒。
- 附录 A 四大师速查卡、附录 B 一页纸操作备忘卡（P0~P5 改后）。

---

## 六、报告输出路径（建议）

`reports/{公司名}/{公司名}-mid-earnings-{期间}.md`

- 英文后缀 `-mid-earnings-` 直白区分中期，且不与长期版 `-earnings-` 碰撞（长期版输出 `{公司名}-earnings-{期间}.md` 保持不变）。

---

## 七、实施步骤顺序

1. 撰写 `.trae/skills/mid-earnings-team/SKILL.md`（按第五节修正清单，以草稿为底稿逐项落实）
2. 创建 `.trae/skills/mid-earnings-team/README.md`
3. 更新 `CLAUDE.md` 中期投研类表格
4. 更新 `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md`（6 处，见第四节）
5. grep 全项目复查 `mid-earnings-team` / `earnings-team` 引用无残留错配、无命令名混淆

---

## 八、长期版不动声明

以下长期链文件**一律不动**：

- `.trae/skills/earnings-team/SKILL.md` 及其 README
- `.trae/skills/earnings-review/SKILL.md` 及其 README
- `.trae/skills/证券AI价值投资研究工作步骤.md`（10 年长期链）
- 其他长期链技能中对 `/earnings-team` 的跨引用（investment-team、news-pulse、wechat-article、thesis-drift、thesis-tracker、portfolio-review、financial-data 等）

中期版 `mid-earnings-team` 仅通过「中期投研类」与「中长期工作步骤」两个入口挂载，不改写长期链既有引用。

---

## 九、决策点确认记录（2026-09-05 已逐条确认）

| # | 决策点 | 确认结果 |
|---|--------|---------|
| 1 | 命令语法 | **确认** `/mid-earnings-team {公司名} {期间}`（如 `/mid-earnings-team 腾讯 2025Q4`），沿用 mid-* 系列统一语法 |
| 2 | 报告文件命名 | **确认** `reports/{公司名}/{公司名}-mid-earnings-{期间}.md`，加 `mid` 前缀与长期版物理隔离 |
| 3 | 李进职责补组合管理 | **确认** 李进 =「组合管理 + 治理」，「仓位管理框架」「四大核心矛盾」挂靠李进 Agent 视角 |
| 4 | 文档体系归位 | **确认** 中长期工作步骤文档归入「⑤ 持仓管理」阶段（与 trend-momentum-scan、mid-thesis-drift 并列）；CLAUDE.md 放入「中期投研类（1-3年）」表格（与 mid-investment-team 并列） |
| 5 | P0~P5 引用方式 | **确认** 直接引用 `exit-signal` 的 P0~P5 映射（时间止损归 P2，技术面仅作 P3 辅助），SKILL.md 内不重复定义、不自建表格 |
| 6 | PEG 估值引用方式 | **确认** 删除自建 PEG 五档表，只引用 `valuation-thermometer` 输出；渗透率修正归郑希赛道判断（引用 `mid-industry-research`），不在 PEG 数值上自行加减 |
| 7 | 交付范围 | **确认** 本轮仅交付 `mid-earnings-team`（团队版），不新建单 Agent 版 `mid-earnings-review`；长期链 `earnings-review` 继续跨链复用 |
| 8 | 附录 C 差异对照表 | **确认** 转正时删除，不再保留 |
| 9 | 版本号标记 | **确认** 标题去掉「草稿」，frontmatter 不加版本字段，文末落款写「V1.0.0」 |

> 以上确认结果已同步落实到第二节（设计原则）、第三节（新建文件）、第四节（修改文件）、第五节（草稿修正清单）与第六节（报告输出路径），后续开发按此执行。