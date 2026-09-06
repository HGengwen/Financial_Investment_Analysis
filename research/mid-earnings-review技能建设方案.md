# mid-earnings-review 技能建设方案

- 日期：2026-09-05
- 状态：**已确认**（9 个决策点已逐条确认，可进入开发）
- 权威口径来源：
  - `research/个人投资者1~3年中长期投资思想与理念 V2.0.md`（中期链唯一权威理念口径）
  - `.trae/skills/earnings-review/SKILL.md`（长期版财报精读技能，本次「格式与范式」参考）
  - `research/early-version/earnings-review技能文件（草稿）.md`（本次底稿）
  - `.trae/skills/exit-signal/SKILL.md`（卖出纪律 P0~P5 唯一权威口径）
  - `.trae/skills/valuation-thermometer/SKILL.md`（PEG 五档唯一权威口径）
  - `.trae/skills/mid-industry-research/SKILL.md`（产业景气 / 渗透率唯一权威口径）
  - `.trae/skills/mid-management-deep-dive/SKILL.md`（管理层 20 分制 / 科研转化 20 分制口径）
  - `.trae/skills/qoq-accelerator/SKILL.md`（季度加速度 / 二阶导口径）
  - `.trae/skills/mid-earnings-team/SKILL.md`（姊妹技能：团队版，引用口径与术语红线参照）
  - `research/mid-earnings-team技能建设方案.md`（方案文档格式模板）

---

## 一、背景与问题

1. `.trae/skills/earnings-review/SKILL.md` 是**长期价值投资版**（巴菲特-李录一手资料精读口径，10 年持有，护城河/生意分析），与 `V2.0.md`（欧奈尔-林奇-郑希-李进口径，1~3 年景气投资）不匹配。

2. `research/early-version/earnings-review技能文件（草稿）.md` 是参考长期版后、针对 1~3 年目标修改的**轻量版草稿**（标题已标「mid-earnings-review」），其景气化改造方向正确（四大师维度、景气三要素、PEG、底仓/机动仓、假如空仓、季度复盘），且定位为「单 Agent 快速财报精读」。但仍存在以下需在转正时修正的问题：

   - **P0~P6 与权威口径冲突**：草稿使用 P0~P6（P6=趋势走坏辅助），权威 `exit-signal` 为 **P0~P5**（时间止损归 P2，技术面仅作 P3 辅助、不构成独立层级）。
   - **PEG 五档重复定义**：草稿自行列出 PEG 五档表与「渗透率修正」叠加公式，违反「引用不重复定义」铁律。
   - **frontmatter 缺失**：草稿无 frontmatter（长期版有 `name` / `description` / `disable-model-invocation`），无法注册命令。
   - **大量未填充骨架**：前置步骤、第一步、第二步 2.1/2.2/2.3、第三步 3.1、第五步、第六步 6.1/6.2、第七步 7.1/7.2/7.3、第八步 8.1、第十二步等多处为空表或空段落，转正后不自洽。
   - **输出文件名使用长期版语义**：草稿沿用 `-earnings-{期间}-景气版.md`，既非 mid 前缀，也与长期版 `-earnings-` 语义易混。
   - **缺失保存报告与数据抽检准出步骤**：长期版有「第七步保存报告 + 第八步数据抽检」，草稿「输出精读报告」后直接结束，无准出闭环。
   - **设计定位引错技能名**：草稿 L9、L412 写「如需深度团队分析请使用 `earnings-team`」，应为 `mid-earnings-team`。
   - **附录 C「与原版差异对照表」属开发过程说明**，转正时删除。
   - **林奇定位偏选股场景**：附录 A 速查卡把林奇写为「选股起点」，财报精读场景应统一为「生意与估值」。

---

## 二、设计原则

1. **轻量版定位（与团队版分工）**：
   - `/mid-earnings-review` = **单 Agent** 快速财报精读，日常季度财报快速跟踪，不启动多 Agent。
   - `/mid-earnings-team` = 四大师并行 + 编辑 + 读者评审的团队精读（重要财报深度 + 公众号发布）。
   - 二者共享同一套权威口径（`exit-signal` / `valuation-thermometer` / `mid-industry-research` / `mid-management-deep-dive` / `qoq-accelerator`），轻量版结论可被团队版复用。

2. **物理隔离**：中期链（1~3 年）与长期链（10 年）口径分离，禁止「护城河永续」「终局思维」「封仓十年」等长期术语；采用欧奈尔-林奇-郑希-李进四大师口径。

3. **四位大师分工（对齐 V2.0，作为单 Agent 的分析维度标尺，非多 Agent 角色）**：

   | 大师 | 思维模式 | 在财报精读中的维度 |
   |------|---------|-------------------|
   | 郑希 | 物理学家思维 · 周期与第一性原理 | **产业景气验证**：ROE 趋势/拐点、二阶导、渗透率位置、供需格局 |
   | 林奇 | 侦探思维 · 常识与求证 | **生意与估值**：收入量价拆解、毛利率/现金流质量、PEG 估值更新（引用 valuation-thermometer）、估值陷阱排查 |
   | 欧奈尔 | 工程师思维 · 信号与纪律 | **风控底线**：止损位更新、趋势信号、抛售信号 |
   | 李进 | 系统工程师思维 · 均衡与渗透率 | **组合管理 + 治理**：管理层/科研转化评估、地缘政治、底仓/机动仓分离、卖出纪律执行 |

4. **引用不重复定义**（中期技能体系铁律）：
   - 估值档位 → 引用 `valuation-thermometer`（PEG 五档判定/边界约定一律以其输出为准，不自行重复列出阈值）。
   - 卖出纪律 → 引用 `exit-signal`（P0~P5 唯一权威口径，时间止损归 P2，技术面仅作 P3 辅助、不构成独立层级）。
   - 产业景气 / 渗透率 → 引用 `mid-industry-research`。
   - 管理层 / 科研转化 → 引用 `mid-management-deep-dive` 与 V2.0 理念文档。
   - 季度加速度 / 二阶导 → 引用 `qoq-accelerator`（财报精读中仅作辅助判断，不重复定义其完整算法）。

5. **数据规范**：双源交叉验证、误差 >1% 标记、禁止 LLM 心算、`financial_rigor.py` 精确计算、`report_audit.py` 抽检准出。

6. **网络限制**：禁止 Anthropic WebSearch/WebFetch，统一本地五工具（anysearch/doubao_search/exa_search/tavily_search/web_search）。

7. **执行流程范式**：保留长期版「前置评级 → 获取一手资料 → 核心财务 → MD&A → 附注 → 历史对比 → 输出报告 → 保存 → 数据抽检准出」完整闭环，将核心环节替换为景气版（景气三要素 / PEG / 管理层景气判断 / 科研转化附注 / 底仓机动仓 / 假如空仓 / 季度复盘）。

---

## 三、新建文件清单

| 文件 | 说明 |
|------|------|
| `.trae/skills/mid-earnings-review/SKILL.md` | 主技能文件（基于草稿 + 第五节修正清单转正） |
| `.trae/skills/mid-earnings-review/README.md` | 技能说明（命令、适用场景、与长期版 / 团队版差异、输出路径） |

---

## 四、需修改的其他文件清单

| 文件 | 修改点 |
|------|--------|
| `CLAUDE.md` | 「中期投研类（1-3年）」表格新增 `/mid-earnings-review {公司名} {期间}` 一行（长期版 `/earnings-review` 行在「财报跟踪类」中不动，见第八节） |
| `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md` | ① 全景图表格新增 `mid-earnings-review` 行，归入「⑤ 持仓管理」阶段（与 `mid-earnings-team` 并列）；② 中期技能计数「13 个」→「14 个」；③ 说明段中期技能清单补 `mid-earnings-review`；④ 六阶段闭环图持仓管理分支加入 `mid-earnings-review`；⑤ 组合「财报季全套流程」相关段落补 `mid-earnings-review`（轻量快速版）与 `mid-earnings-team`（深度版）分工说明；⑥ 附录决策树财报跟踪分支加入 `/mid-earnings-review` |

> 注：正式开发前先 grep 全项目确认 `mid-*` 各中期技能内对 `earnings-review` 的跨引用情况；长期链技能（earnings-team、investment-team、news-pulse、wechat-article、thesis-drift、thesis-tracker、portfolio-review、financial-data 等）内的 `/earnings-review` 引用为**长期链自身约定，一律不动**（见第八节）。

---

## 五、草稿修正清单（撰写 SKILL.md 时逐一落实）

**修正 1 — 补 frontmatter + 标题去「草稿」**
- 草稿 L1 直接是标题，无 frontmatter。参照长期版补：
  - `name: mid-earnings-review`
  - `disable-model-invocation: true`
  - `description` 对齐 V2.0 四大师口径，追加触发词（中期 / 1-3年 / 景气财报 / 财报季验证景气逻辑 / 更新卖出纪律），并说明与长期版 `/earnings-review` 的路由区分。
- 标题去掉「（草稿）」，文末落款写「V1.0.0」。

**修正 2 — P0~P6 → P0~P5（核心修正，多处）**
- 草稿 L8「每季必答四问」、L47「设计理念」、L180-184「第九步决策优先级金字塔」、L203/L222 报告结构、L380-395 决策金字塔表（含 P6 行）、L530-539 示例表标题、L603-613 附录 B「卖出触发条件」中的 P0~P6 全套，统一改为**文字引用** `exit-signal` 的 P0~P5，SKILL.md 内**不重复定义、不自建表格**。
- 仅在「卖出纪律更新」章节说明任务：逐一核对 `exit-signal` 的 P0~P5 各层是否被新财报数据触发，输出「是否触发 + 对应层级 + 建议动作」。
- 明确口径：时间止损归 P2，技术面仅作 P3 辅助、不构成独立层级，删除 P6。
- 核心原则统一为「P0 > P1 > P2 > P3 > P4 > P5，命中即停，禁止跳过 P0」。

**修正 3 — PEG 五档改为引用，不重复定义（核心修正）**
- 草稿 L84-91「第三步」与 L283-294 PEG 五档表（含「操作建议」列）删除，改为引用 `valuation-thermometer` 输出的五档温度及对应底仓/机动仓操作映射。
- 「渗透率修正因子」（草稿 L112-117）不再在 PEG 数值上加减，改为归入郑希「产业景气/渗透率位置」判断（引用 `mid-industry-research`），在结论处与估值交叉比对。
- 三种估值陷阱（低 PE 陷阱 / 高 PE 不可持续 / 忽略股权稀释）保留，归属林奇「生意与估值」维度。

**修正 4 — 补齐未填充骨架（核心修正）**
- 草稿中以下空白/占位章节补全为可独立运行的完整内容，不得依赖长期版：
  - L58 前置步骤（补 A/B/C 评级表——草稿 L232-239 已散落评级表，前置引用）
  - L85-87「2.1 景气三要素」、L94-96「2.2 收入利润」、L98-104「2.3 现金流 / 2.4 资产负债」（有明确指标项，补填报说明 + 数据验证命令）
  - L111「3.1 PEG 操作矩阵」（改引用后弱化为操作联动说明）
  - L139「第五步左侧 vs 右侧」（草稿 L296-305 已有对照表，前置引用）
  - L147-148「6.1 管理层景气判断」、L150「6.2 语气分析」、L152-154「6.3 承诺追踪」（草稿 L307-333 已有模板，前置引用）
  - L159-165「7.1 科研转化 / 7.2 管理层四维度 / 7.3 地缘政治六维度」（草稿 L334-369 已有模板，前置引用 + 补「引用 mid-management-deep-dive」提示）
  - L169-172「8.1/8.2 历史趋势与渗透率位置」、L205「第十二步季度复盘」（草稿 L371-378、L397-412 已有模板，前置引用）
- 关键：把草稿文末散落的模板表格**归位到对应步骤正文**，使 SKILL.md 自洽可独立执行（长期版范式：每步正文内嵌模板）。

**修正 5 — 补「保存报告」与「数据抽检准出」步骤（核心修正）**
- 长期版第七步「保存报告」、第八步「数据抽检」草稿完全缺失；转正时补齐：
  - 输出报告后保存至 `reports/{公司名}/{公司名}-mid-earnings-review-{期间}.md`。
  - 增加「数据抽检（准出流程）」：`report_audit.py extract → 取数 → verdict`，通过方可发布，并保留 Windows 兼容说明（`$null` / `%TEMP%` / `--output-json` 等，参照长期版 L307-312）。

**修正 6 — 输出文件命名改为中期版（待确认决策点 2）**
- 草稿 L466 `reports/腾讯/腾讯-earnings-2025Q4-景气版.md` 改为 mid 前缀（见第六节）。

**修正 7 — 设计定位 / 关系表技能名修正**
- 草稿 L9、L412「请使用 `earnings-team`」→「请使用 `mid-earnings-team`」。
- 草稿 L446-454「与现有 Skill 关系」表改为引用中期链闭环技能：`mid-earnings-team`、`mid-investment-research`、`mid-investment-team`、`mid-management-deep-dive`、`exit-signal`、`valuation-thermometer`、`qoq-accelerator`、`mid-industry-research`；`portfolio-review` 标注为「通用盘后组合审视（可选）」。
- 补充本技能与 `/mid-earnings-team` 的轻量/深度分工说明（见第二节第 1 条）。

**修正 8 — 林奇定位对齐 V2.0**
- 附录 A 速查卡（草稿 L570-579）林奇「选股起点」→「生意与估值」（与第二节分工表一致）。

**修正 9 — 删除开发过程说明**
- 附录 C「与原版差异对照表」（草稿 L617-633）属草稿开发过程说明，正式 SKILL.md 不保留。

**修正 10 — 保留内容（不修改）**
- 能力圈声明（适用科技/医药/高端制造/景气周期成长股；不适用纯周期/困境反转/金融/被动指数/短期交易）。
- 与段永平价值投资的关系说明（仅作哲学补充，不参与估值/择时/止损层）。
- 景气三要素、ROE 八季度趋势、二阶导、渗透率位置、左侧 vs 右侧策略。
- 管理层四维度、科研转化附注、地缘政治六维度、华为式抗封锁韧性框架。
- 底仓（60%~80%）/ 机动仓（20%~40%）分离、分批建仓规则、仓位红线（单只初始 ≤10% / 验证后 ≤15% / 绝限 ≤20% / 单行业 ≤40%）。
- 「假如空仓」测试、季度复盘 7 项必查、三种估值陷阱提醒。
- 附录 A 四大师速查卡（林奇改后）、附录 B 一页纸操作备忘卡（P0~P5 改后）。

---

## 六、报告输出路径（建议，待确认）

`reports/{公司名}/{公司名}-mid-earnings-review-{期间}.md`

- 用 `-mid-earnings-review-` 区分：
  - 长期版：`{公司名}-earnings-{期间}.md`（不变）
  - 团队版：`{公司名}-mid-earnings-{期间}.md`（最终发布）+ 各大师底稿
  - 轻量版：`{公司名}-mid-earnings-review-{期间}.md`（本技能，单文件）

---

## 七、实施步骤顺序

1. 撰写 `.trae/skills/mid-earnings-review/SKILL.md`（按第五节修正清单，以草稿为底稿逐项落实）
2. 创建 `.trae/skills/mid-earnings-review/README.md`
3. 更新 `CLAUDE.md` 中期投研类表格
4. 更新 `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md`（见第四节）
5. grep 全项目复查 `mid-earnings-review` / `earnings-review` 引用无残留错配、无命令名混淆

---

## 八、长期版不动声明

以下长期链文件**一律不动**：

- `.trae/skills/earnings-review/SKILL.md` 及其 README
- `.trae/skills/earnings-team/SKILL.md` 及其 README
- `.trae/skills/证券AI价值投资研究工作步骤.md`（10 年长期链）
- 其他长期链技能中对 `/earnings-review` 的跨引用（earnings-team、investment-team、news-pulse、wechat-article、thesis-drift、thesis-tracker、portfolio-review、financial-data 等）

中期版 `mid-earnings-review` 仅通过「中期投研类」与「中长期工作步骤」两个入口挂载，不改写长期链既有引用。

---

## 九、决策点确认记录（2026-09-05 已逐条确认）

| # | 决策点 | 确认结果 |
|---|--------|---------|
| 1 | 命令语法 | **确认** `/mid-earnings-review {公司名} {期间}`（如 `/mid-earnings-review 腾讯 2025Q4`），沿用 mid-* 系列统一语法 |
| 2 | 报告文件命名 | **确认** `reports/{公司名}/{公司名}-mid-earnings-review-{期间}.md`，加 `mid-earnings-review` 前缀，与长期版 `-earnings-`、团队版 `-mid-earnings-` 三者物理隔离 |
| 3 | CLAUDE.md 归位 | **确认** 「中期投研类（1-3年）」表格，与 `/mid-earnings-team` 并列；长期版 `/earnings-review` 保留在「财报跟踪类」不动 |
| 4 | 工作步骤文档归位 | **确认** 归入「⑤ 持仓管理」阶段，与 `mid-earnings-team` 并列；中期技能计数「13 个 → 14 个」 |
| 5 | P0~P5 引用方式 | **确认** 直接引用 `exit-signal` 的 P0~P5（时间止损归 P2，技术面仅作 P3 辅助），SKILL.md 内不重复定义、不自建表格，删除草稿 P6 |
| 6 | PEG 估值引用方式 | **确认** 引用 `valuation-thermometer` 的 PEG 五档，渗透率修正归郑希赛道判断（引用 `mid-industry-research`），不在 PEG 数值上自行加减 |
| 7 | 交付范围 | **确认** 本轮仅交付 `mid-earnings-review`（轻量版），长期链 `earnings-review` 继续保留 |
| 8 | 附录 C 差异对照表 | **确认** 转正时删除，不再保留 |
| 9 | 版本号标记 | **确认** 标题去掉「草稿」，frontmatter 不加版本字段，文末落款写「V1.0.0」 |

> 以上确认结果已同步落实到第二节（设计原则）、第三节（新建文件）、第四节（修改文件）、第五节（草稿修正清单）与第六节（报告输出路径），后续开发按此执行。