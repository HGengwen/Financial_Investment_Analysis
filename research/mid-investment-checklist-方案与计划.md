# mid-investment-checklist 技能方案与计划

> 状态：等待用户明确确认。确认前不新建/修改任何技能或文档。
> 日期：2026-09-01

---

## 一、现状与问题

1. `.trae/skills/investment-checklist/SKILL.md` 是巴菲特六关长期（10年）技能，与 `research/个人投资者1~3年中长期投资思想与理念 V2.0.md` 的中期理念不匹配。
2. 中期链总纲 `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md` 的「③个股验证」环节目前仍在**复用长期 `investment-checklist`**，是本次补齐的核心位置。
3. 用户已提供基础稿 `research/early-version/investment-checklist技能文件（草稿）.md`（已按中期改造的 V0.0.1），以此为基础改写。

---

## 二、新技能设计：`mid-investment-checklist`（七关框架）

| 关卡 | 名称 | 核心内容 | 权威来源 |
| --- | --- | --- | --- |
| 第一关 | 产业赛道爆发潜力 | TAM≥1000亿、3年CAGR≥20%、渗透率10%~30%、连续2季业绩兑现 | V2.0 第1步 / mid-industry-research |
| 第二关 | 行业景气主升浪 | 景气周期阶段、二阶导方向、渗透率坐标 | V2.0 第1步 |
| 第三关 | 核心竞争力（1-3年视角） | 营收/增速/负债/现金流/扣非初筛 + 护城河1-3年有效性 | V2.0 第2步 |
| 第四关 | 管理层×科研转化（40分制） | 管理层4维20分 + 科研转化3维20分，≥15分可重仓 | V2.0 第3步 |
| 第五关 | PEG 估值与建仓 | **引用** `valuation-thermometer` 五档，1/3+1/3+1/3 分批 | valuation-thermometer |
| 第六关 | 仓位管理与卖出触发 | 底仓/机动仓、5~10只、**引用** `exit-signal` P0~P5 | V2.0 第4步 / exit-signal |
| 第七关 | 地缘政治与外部环境 | 6维评估 + 华为式抗封锁韧性 | V2.0 第3步 |

---

## 三、草稿与现有中期体系的 5 处冲突（已拟定对齐方案）

| # | 冲突点 | 对齐方案 |
| --- | --- | --- |
| 1 | 草稿卖出为 P0~P6，`exit-signal` 权威为 **P0~P5** | 统一为 P0~P5，第六关**直接引用** exit-signal，不自建 |
| 2 | 草稿风控码 R-1~R-10 与 `mid-industry-research` 已占用的 R-1~R-10 同名不同义 | 新技能风控码重命名为 **MC-1~MC-10** |
| 3 | 草稿自定 PEG 五档，`valuation-thermometer` 是唯一权威 | 第五关**引用不重复定义** |
| 4 | 草稿报告路径扁平 `reports/{公司名}-checklist-{date}.md` | 改为中期嵌套 **`reports/{公司名}/{公司名}-mid-checklist-{date}.md`** |
| 5 | 草稿内部 P0~P6 与 P0~P5 自相矛盾（速查卡） | 统一 P0~P5 引用，不内建速查卡 |

---

## 四、文件变更清单

**新建（2 个）**
- `.trae/skills/mid-investment-checklist/SKILL.md` — 七关正文，落实 5 处对齐
- `.trae/skills/mid-investment-checklist/README.md` — 快速上手 + 七关速览 + 报告路径

**修改（2 个）**
- `CLAUDE.md` — 中期投研类表格新增 `/mid-investment-checklist` 行；中期链路由加入；技能总数 27→28
- `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md` — 阶段三「③个股验证」由复用长期 checklist 改为 `/mid-investment-checklist`；中期技能全景图 7→8；修正「共8/7个」笔误；附录决策树替换；更新版本号与数据截止日期

**明确不动**
- 长期 `.trae/skills/investment-checklist/SKILL.md` 及长期工作步骤文档
- `research/early-version/` 草稿（归档保留）
- 全部 Python 工具与其余 25 个技能

---

## 五、执行计划（5 步，确认后依次执行）

1. 新建 `mid-investment-checklist/SKILL.md`（七关 + 5 处对齐）
2. 新建 `mid-investment-checklist/README.md`
3. 修改 `CLAUDE.md`
4. 修改 `证券AI中长期（1~3年）价值投资研究工作步骤.md`
5. `Grep` 自查：中期链不再残留「复用长期 investment-checklist」表述

---

## 六、待确认的 3 个口径

1. **是否按上述方案开发？**（确认开始 / 需要调整）
2. **冲突口径处理**：是否采用「统一 P0~P5 + 风控码改名 MC-1~MC-10」？（推荐，见第三节 #1/#2）
3. **报告落盘路径**：采用嵌套 `reports/{公司名}/{公司名}-mid-checklist-{date}.md`？（推荐，见第三节 #4）
