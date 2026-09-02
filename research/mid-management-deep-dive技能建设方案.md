# mid-management-deep-dive 技能建设方案

- 日期：2026-09-02
- 状态：待用户确认
- 权威口径来源：
  - `research/个人投资者1~3年中长期投资思想与理念 V2.0.md`（中期链唯一权威理念口径）
  - `.trae/skills/exit-signal/SKILL.md`（卖出纪律 P0~P5 唯一权威口径）
  - `.trae/skills/valuation-thermometer/SKILL.md`（PEG 档位唯一权威口径）
  - `.trae/skills/mid-investment-research/SKILL.md`（中期链研究主框架，已建成）

---

## 一、背景与问题

当前 `.trae/skills/management-deep-dive/SKILL.md` 是**长期价值投资版**（巴菲特-芒格-段永平-李录口径，10 年持有），与 `V2.0.md`（欧奈尔-林奇-郑希-李进口径，1~3 年景气投资）不匹配。

`research/early-version/management-deep-dive技能文件（草稿）.md` 是参考长期版后针对 1~3 年目标修改的草稿，但存在如下问题，需在转正为 `mid-management-deep-dive` 时逐一修正：

1. frontmatter 名称仍为 `management-deep-dive`
2. 标题被错误嵌入新名称（乱码）
3. 段永平、巴菲特等长期人物残留
4. 卖出纪律仍用草稿自造的 P0~P6（权威口径应为 P0~P5）
5. PEG 五档自行重复定义（违反「引用不重复定义」）
6. 评分汇总符号混乱（「20（25）」）
7. 附录 B 阈值与正文矛盾（≥16 vs ≥15）
8. 跨技能引用残留长期链技能名

## 二、设计原则

1. **物理隔离**：中期链（1~3 年）与长期链（10 年）口径分离，禁止「护城河永续」「终局思维」「持有 10 年」等长期术语。
2. **四位大师口径**：欧奈尔（纪律止损）、林奇（常识与诚信观察）、郑希（科研转化与 ROE 拐点）、李进（治理与渗透率）。
3. **引用不重复定义**：
   - 估值 → 引用 `valuation-thermometer`（PEG 档位判定/边界约定/四工具交叉校验一律以其输出为准）
   - 卖出 → 引用 `exit-signal`（P0~P5 唯一权威口径，时间止损归 P2，技术面仅作 P3 辅助、不构成独立层级）
   - 产业景气/渗透率 → 引用 `mid-industry-research`
4. **数据规范**：双源交叉验证、误差 >1% 标记、禁止 LLM 心算、`financial_rigor.py` 精确计算、`report_audit.py` 抽检准出。
5. **网络限制**：禁止 Anthropic WebSearch/WebFetch，统一本地五工具（anysearch/doubao_search/exa_search/tavily_search/web_search）。

## 三、新建文件清单

| 文件 | 说明 |
|------|------|
| `.trae/skills/mid-management-deep-dive/SKILL.md` | 主技能文件（基于草稿 + 第五节修正清单转正） |
| `.trae/skills/mid-management-deep-dive/README.md` | 技能说明（命令、适用场景、与长期版差异、输出路径） |

## 四、需修改的其他文件清单

| 文件 | 修改点 |
|------|--------|
| `CLAUDE.md` | 「中期投研类（1-3年）」表格新增 `/mid-management-deep-dive` 一行（长期版 `/management-deep-dive` 行不动） |
| `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md` | 5 处（L35、L48、L157、L286、L353）「复用长期 `management-deep-dive`」→ `mid-management-deep-dive` |
| `.trae/skills/mid-industry-research/SKILL.md` | 3 处（L177、L456、L461）`management-deep-dive` → `mid-management-deep-dive` |
| `.trae/skills/mid-investment-research/SKILL.md` | L292 去掉「本次尚未建立，暂以本步评估为准」改为调用 `mid-management-deep-dive`；L736 去掉「（待开发）」 |

## 五、草稿修正清单（撰写 SKILL.md 时逐一落实）

**修正 1 — frontmatter**
- `name: management-deep-dive` → `name: mid-management-deep-dive`
- description 对齐 `mid-investment-research` 风格，追加 `Invoke when` 触发词（中期/1-3年管理层研究/诚信/科研转化/治理等）

**修正 2 — 标题乱码**
- `# 管理层纵深研mid-management-deep-dive技究：买股票就是买人（1~3 年景气草稿V0.0.1）` → 清理为正式标题，去掉「草稿 V0.0.1」版本标记（版本号处理见决策点）

**修正 3 — 长期人物残留**
- L13 段永平引语、L15 巴菲特引语 → 替换为欧奈尔/林奇口径；保留李进、郑希引语
- L239「巴菲特最看重的」、L351 巴菲特引语、L362「段永平式追问」、L414「段永平的『买人』标准」→ 改为四大师口径

**修正 4 — P0~P6 → P0~P5**
- L506-514 决策优先级表：完全替换为 `exit-signal` 的 P0~P5 映射表（时间止损归 P2，技术面仅作 P3 辅助、不构成独立层级），保留「与管理层评估的联动」列
- L699 附录A「P0~P6」→「P0~P5」；L710 附录B「P3~P6」→「P3~P5」

**修正 5 — PEG 五档重复定义**
- L470-480 删除自行列出的五档阈值定义，改为引用 `valuation-thermometer`；保留「管理层评级 → 估值折价/溢价调整」联动表，阈值表述对齐权威口径

**修正 6 — 评分汇总符号混乱**
- L455-462 将「E. 科研转化能力 5 分」「总分 20（25）」拆为**两个独立 20 分制表**（不合并）：
  - 管理层 20 分制：A 诚信 5 / B 股东态度 5 / C 战略眼光 5 / D 稳定性与激励 5
  - 科研转化 20 分制：A 研发投入质与量 8 / B 产出效率 8 / C 资本回报 4

**修正 7 — 阈值不一致**
- 正文评级标准（≥15 可重仓 / 10~14 轻仓 / <10 回避 / 一票否决立即清仓）与 V2.0 一致，保留
- 附录B「综合评分≥16分（A级）」→ 改为「管理层≥15 且科研转化≥15（A级）」
- 明确 A/B/C 级与分数区间映射（≥15=A / 10~14=B / <10=C）

**修正 8 — 跨技能引用残留**
- 「同原版 `management-deep-dive`」→ 自说明或指 `mid-investment-research`
- `investment-research`（景气版）→ `mid-investment-research`
- `quality-screen` → `mid-investment-checklist`（中期链无 quality-screen）
- `investment-checklist`（景气版）→ `mid-investment-checklist`
- `sell-discipline`/`position-management` → `exit-signal`

**保留内容（不修改）**
- 13 步执行流程骨架（识别关键管理层→诚信→科研转化→资本配置→治理→侧面验证→CEO 离开情景→矛盾化解→20 分制评分→「假如空仓」测试→决策优先级→季度复盘→保存报告）
- A+H / 多地上市流程、pdf_extract / OCR 流程、网络搜索矩阵

## 六、报告输出路径（已确认）

`reports/{公司名}/{公司名}-mid-management-{YYYYMMDD}.md`

- 英文后缀 `-mid-management-` 直白区分中期，且不与长期版 `-management-` 碰撞。

## 七、实施步骤顺序

1. 撰写 `.trae/skills/mid-management-deep-dive/SKILL.md`（按第五节修正清单）
2. 创建 `.trae/skills/mid-management-deep-dive/README.md`
3. 更新 `CLAUDE.md` 中期投研类表格
4. 更新 `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md`（5 处）
5. 更新 `.trae/skills/mid-industry-research/SKILL.md`（3 处）
6. 回改 `.trae/skills/mid-investment-research/SKILL.md`（2 处）
7. grep 全项目复查 `management-deep-dive` 中期链引用无残留错配

## 八、长期版不动声明

`.trae/skills/management-deep-dive/SKILL.md` 及其 README、`证券AI价值投资研究工作步骤.md`、`investment-research`、`investment-checklist`、`industry-funnel`、`industry-research`、`investment-team`、`news-pulse`、`thesis-tracker`、`earnings-review` 等长期链文件**一律不动**。

## 九、已确认决策点（2026-09-02）

1. **报告文件命名**：`reports/{公司名}/{公司名}-mid-management-{YYYYMMDD}.md`（选 `mid-management`）
2. **命令语法**：`/mid-management-deep-dive {公司名}` 或 `/mid-management-deep-dive {人名 公司名}`
3. **版本号标记**：标题去掉「草稿 V0.0.1」，frontmatter 不加版本字段，文末落款写「V1.0.0」
