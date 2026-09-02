# mid-investment-research 技能建设方案与计划

> 状态：已开发完成（mid-investment-research 与 mid-management-deep-dive 均已落地）
> 日期：2026-09-02
> 范围说明：本次开发 `mid-investment-research`，并随后单独开发 `mid-management-deep-dive`，两者均已完成。

---

## 一、目标与命名（已确认）

**目标**：新建一套与长期链物理隔离的 1~3 年景气投资个股研究技能，彻底解决「中期链复用长期 `investment-research`（巴菲特-芒格-段永平-李录）导致框架错配」的问题。

**命名（已确认）**：
- 技能名：`mid-investment-research`
- 命令：`/mid-investment-research {公司名}`
- 与长期版 `/investment-research {公司名}` 和平共存，互不覆盖

**权威口径**：严格以《个人投资者1~3年中长期投资思想与理念 V2.0.md》为准（四大师：欧奈尔-林奇-郑希-李进）。

---

## 二、新建文件清单（本次仅 2 个）

| # | 文件 | 内容 |
|---|------|------|
| 1 | `.trae/skills/mid-investment-research/SKILL.md` | 正式版技能文件（基于 `investment-research技能文件（草稿）.md` 修正） |
| 2 | `.trae/skills/mid-investment-research/README.md` | 技能使用说明（参考长期版 README 结构） |

> `mid-management-deep-dive`（SKILL.md + README.md）已单独开发完成。

**mid-investment-research SKILL.md 主体框架**（沿用草稿八步，口径对齐中期链）：

1. 数据收集（双源交叉验证，误差>1% 标记）
2. 生意本质与产业定位（渗透率坐标：15% 加速临界 / 50% 减速）
3. 护城河（1~3 年视角，弱化永续性）
4. 逆向思考与风险清单（R-1~R-10）
5. 产业景气与 ROE 拐点（引用 `mid-industry-research` 口径）
6. 管理层评估（20 分制 + 科研转化 20 分制，内嵌评估；深化入口已由 `mid-management-deep-dive` 承接）
7. 估值与买入时机（引用 `valuation-thermometer`，左侧/右侧建仓）
8. 综合决策（引用 `exit-signal` P0~P5，底仓/机动仓配置）

另含：四大矛盾化解专节、决策优先级金字塔、季度复盘、能力圈声明。

---

## 三、需修改文件清单（含具体修改点）

| # | 文件 | 修改点 |
|---|------|--------|
| 1 | `CLAUDE.md` | 「中期投研类（1-3年）」表格（L58-70）新增一行：`/mid-investment-research {公司名}` |
| 2 | `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md` | L34/L48/L155/L286 四处 `investment-research` 改为 `mid-investment-research`；`management-deep-dive` 引用（L35/L157/L286/L353）**本次保持不动**，待后续开发 `mid-management-deep-dive` 时一并更新 |
| 3 | `research/early-version/investment-research技能文件（草稿）.md` | 作为 `mid-investment-research/SKILL.md` 的草稿来源，修正后落盘；草稿本身不再改动 |

> **长期版完全不动**：`investment-research/SKILL.md`、`management-deep-dive/SKILL.md`、`证券AI价值投资研究工作步骤.md`（长期文档）均保持原样。
>
> **后续已完成**：`mid-management-deep-dive` 技能文件、`research/early-version/management-deep-dive技能文件（草稿）.md` 修正、以及 CLAUDE.md / 中期工作步骤文档中 `management-deep-dive` 引用更新。

---

## 四、口径对齐原则（引用不重复定义）

遵循中期链既有惯例（`mid-investment-checklist`、`mid-industry-funnel` 已确立），正式版对以下口径**只引用、不独立定义**：

| 口径 | 权威来源 | mid-investment-research 中的处理 |
|------|----------|-------------------------------|
| PEG 五档估值 | `valuation-thermometer` | 引用，不重写分档 |
| 卖出优先级 P0~P5 | `exit-signal` | 引用，不重写 |
| 渗透率/四维产业景气 | `mid-industry-research` | 引用，不重写 |
| 买入前硬门槛（七关） | `mid-investment-checklist` | 指向，不重复 |
| 管理层纵深研究 | `mid-management-deep-dive`（已开发） | 第六步内嵌 20 分制评估；评级 B/C 或核心逻辑时调用 `/mid-management-deep-dive` 深化 |
| 数据精确计算 | `tools/common/financial_rigor.py` | 直接调用 |
| 报告审核 | `tools/common/report_audit.py` | 写出完整命令 |

---

## 五、草稿需修正的问题清单

### A. mid-investment-research 草稿（本次处理，6 点）

1. **命令名混乱**：草稿末尾关系表中 `/investment-research（本Skill，景气版）` → 改为 `/mid-investment-research`。
2. **长期框架人物残留**：删除矛盾二中「林奇/段永平派」及 7.7 节「段永平的检验（股市明天关闭5年）」，替换为中期视角（郑希景气检验/李进二阶导检验）。
3. **P0~P6 → P0~P5**：草稿第八步/专节的 P0~P6（含独立「时间止损 P5」「技术面辅助 P6」）对齐 `exit-signal` 的 P0~P5，时间止损归入 P2。
4. **数据抽检写法过简**：补全 `report_audit.py extract` / `verdict` 完整命令（与 workspace 规则一致）。
5. **估值口径**：PEG 五档改引用 `valuation-thermometer`，不独立定义。
6. **渗透率口径**：7.5 节左侧/右侧分段统一到 `mid-industry-research` 的黄金区（10%~30%）口径。

### B. mid-management-deep-dive 草稿（已处理）

以下问题已识别，已在 `mid-management-deep-dive` 单独开发时一并修正：

1. frontmatter 技能名 `management-deep-dive` → `mid-management-deep-dive`
2. 第 7 行标题乱码修正
3. P0~P6 → P0~P5（第十一步及附录 A/B）
4. 上游技能引用（第 677 行）→ `mid-investment-research`
5. 关联技能名（第 680/681 行）→ `mid-investment-checklist` / `exit-signal` / `portfolio-review`
6. 长期人物名言残留（第 13/15/351/362 行）按中期视角替换

---

## 六、实施步骤顺序

1. 撰写 `.trae/skills/mid-investment-research/SKILL.md`（基于草稿 + 第五节 A 组 6 点修正）
2. 撰写 `.trae/skills/mid-investment-research/README.md`
3. 更新 `CLAUDE.md`（中期投研类表格加一行）
4. 更新 `证券AI中长期（1~3年）价值投资研究工作步骤.md`（investment-research 4 处引用）
5. 全文 grep 复查 `investment-research` 引用，确认中期链个股研究无残留错配
6. 交付供审阅（不推送 GitHub，除非用户要求）

---

## 七、已确认的决策结果

| # | 决策点 | 结论 |
|---|--------|------|
| 1 | 技能命名 | `mid-investment-research`，命令 `/mid-investment-research {公司名}`，与长期版并存 |
| 2 | management-deep-dive | **已完成**：单独开发 `mid-management-deep-dive`，并在 `mid-investment-research` 内嵌管理层 20 分制评估；长期 `management-deep-dive` 未改动 |
| 3 | 长期版处理 | 长期 `investment-research` / `management-deep-dive` 及长期工作步骤文档**完全不动** |
