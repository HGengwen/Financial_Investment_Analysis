# mid-wechat-article 技能建设方案

- 日期：2026-09-08
- 状态：**方案已最终确认（2026-09-08）**，开发已按第九节实施顺序推进（任务 1~8）
- 权威口径来源：
  - `research/个人投资者1~3年中长期投资思想与理念 V2.0.md`（中期链唯一权威理念口径）
  - `.trae/skills/wechat-article/SKILL.md`（长期版格式与范式参考）
  - `research/early-version/wechat-article技能文件（草稿）.md`（本方案底稿）
  - `.trae/skills/exit-signal/SKILL.md`（卖出纪律 P0~P5 唯一权威口径）
  - `.trae/skills/valuation-thermometer/SKILL.md`（PEG 五档唯一权威口径）
  - `.trae/skills/mid-industry-research/SKILL.md`（产业景气/渗透率唯一权威口径）
  - `.trae/skills/mid-management-deep-dive/SKILL.md`（管理层 20 分制 / 科研转化 20 分制口径）

---

## 一、TL;DR

- **新增技能模块**：`.trae/skills/mid-wechat-article/`（SKILL.md + README.md），基于草稿转正，对齐 V2.0 四大师分工（欧奈尔/林奇/郑希/李进）与中期链规范。
- **核心变更**：①卖出纪律从草稿自造"P0~P3 分级"统一为 `exit-signal` P0~P5（引用不重复定义）；②PEG 阈值改为引用 `valuation-thermometer` 五档；③四大师分工按 V2.0 权威分工表精确化（郑希补地缘政治、李进=组合管理+治理、林奇=选股起点+估值定价、欧奈尔=风控底线）；④新增能力圈声明、A/B/C 信息丰富度评级、数据抽检准出（`report_audit.py`）、报告输出路径 `-mid-wechat-` 物理隔离；⑤关系表修正（不存在的 `/garp-team` → `/mid-investment-team`）；⑥默认文章类型改为「景气投资」。
- **文档联动**：`CLAUDE.md` 基础工具与内容输出类新增 `/mid-wechat-article`；`证券AI中长期（1~3年）价值投资研究工作步骤.md` 组合 5 发布承接改为 `/mid-wechat-article` 并同步计数；`mid-deep-company-series` 两处 `/wechat-article` 引用补充 mid 版；历史开发方案标注已落地。
- **长期版不动**：`.trae/skills/wechat-article/`、`证券AI价值投资研究工作步骤.md`、`deep-company-series/README.md` 等长期链文件一律不动。

---

## 二、背景与问题

当前 `.trae/skills/wechat-article/SKILL.md` 是**通用公众号文章写作技能**（技术解读为主、投资类文章隐含长期价值投资视角），与 `V2.0.md`（欧奈尔-林奇-郑希-李进口径，1~3 年景气投资）不匹配。

`research/early-version/wechat-article技能文件（草稿）.md` 前半部分是兼容性诊断（冲突程度**中等**：核心是三 Agent 内容生产框架，非投资决策工具），后半部分是 mid 版草稿全文（frontmatter `name: mid-wechat-article` 已正确）。草稿转正为正式技能时存在以下问题，需逐一修正：

1. **四大师分工未严格对齐 V2.0**：草稿作者 Prompt 中郑希缺地缘政治角色、李进未明确"组合管理 + 治理一票否决"、林奇未强调"选股起点"。
2. **卖出纪律用草稿自造"P0~P3 分级"**：权威口径应为 `exit-signal` P0~P5（P0 治理一票否决、P1 硬止损、P2 逻辑止损含时间止损、P3 产业景气拐点、P4 估值透支、P5 性价比替换）。
3. **PEG 阈值自行展开**：草稿直接写"PEG<1.2 合理买入区间""PEG>1.5 高估"，违反「引用不重复定义」铁律，应引用 `valuation-thermometer` 五档输出。
4. **渗透率/管理层口径未引用**：草稿写"渗透率 10~30% 黄金区"与李进管理层评估，未引用 `mid-industry-research` 与 `mid-management-deep-dive`。
5. **缺能力圈声明**（中期技能体系必备范式）。
6. **缺 A/B/C 信息丰富度评级与 AI 研究偏见预警**（中期技能体系必备）。
7. **缺数据抽检准出流程**（`report_audit.py extract → verdict`）。
8. **报告输出路径无物理隔离**：草稿 `reports/{公司名}/{公司名}-公众号-{YYYYMMDD}.md` 与长期版同路径，会碰撞。
9. **关系表引用不存在的 `/garp-team`**：实际应为 `/mid-investment-team`。
10. **文章类型默认值**：作为中期景气投资版，默认文章类型应调整为景气投资类（技术解读保留为次要）。

---

## 三、兼容性诊断与差距分析

草稿前半部分诊断表（原样采纳，作为转正依据）：

| 维度 | 长期版（通用版） | 1~3 年景气投资要求 | 冲突程度 |
|------|---------------|---------------------|----------|
| 核心定位 | 深度技术/投资主题的公众号文章写作 | 同样需要——内容生产流程是通用的 | ✅ 兼容 |
| 三 Agent 架构 | 作者-编辑-读者协作 | 同样适用 | ✅ 兼容 |
| 投资类文章视角 | 隐含巴芒段李录长期价值投资框架 | 需明确欧奈尔/林奇/郑希/李进景气投资框架 | ⚠️ 需调整 |
| 内容深度 | 中深度（有公式但要解释清楚） | GARP 投资分析同样需要深度 | ✅ 兼容 |
| 配图要求 | 论文解读必须从 PDF 提取原图 | 投资类文章图表需求类似 | ✅ 兼容 |
| 示例主题 | 以大模型 OPD 技术解读为主 | 需补充景气投资类示例 | ⚠️ 需补充 |
| 数据工具 | 有 A 股/港股/美股数据获取工具 | 同样适用 | ✅ 兼容 |
| 输出格式 | 公众号文章 | 同样适用 | ✅ 兼容 |

**保持不变**：三 Agent 协作架构（作者-编辑-读者）、写作风格规范（纯中文 / 段落≤4 行 / 不用 emoji / 禁 AI 腔调）、四阶段执行流程骨架、配图提取流程（pdftoppm + PIL）、本地数据工具与网络搜索工具、公式 LaTeX 规范——这些是内容生产标准，与投资框架无关。

**需替换/增强**：投资类文章的核心内容与结构（四大师 GARP 视角）、作者 Agent Prompt 的景气投资扩展、编辑/读者审阅的景气类标准、卖出纪律与估值口径（引用 `exit-signal` / `valuation-thermometer`）、示例报告（景气投资类）。

---

## 四、设计原则

1. **物理隔离**：中期链（1~3 年）与长期链（10 年）口径分离，禁止「护城河永续」「终局思维」「持有 10 年」「巴芒段李」等长期术语；采用欧奈尔-林奇-郑希-李进四大师口径。
2. **四大师口径（对齐 V2.0「四位大师与个人投资者的连接方式」表）**：

   | 大师 | 思维模式 | 在框架中的角色 | 在文章写作中的落点 |
   |------|---------|---------------|-------------------|
   | 欧奈尔 | 工程师思维 · 信号与纪律 | **风控底线**：8% 止损、卖出触发、防止深度套牢 | 风险与纪律章节：止损位、趋势信号、P0~P5 触发检查 |
   | 林奇 | 侦探思维 · 常识与求证 | **选股起点 + 估值定价**：生活常识选股、六类分类、PEG | 生意本质章节：六类分类、常识验证、PEG 估值 |
   | 郑希 | 物理学家思维 · 周期与第一性原理 | **赛道选择**：ROE 拐点、产业景气、渗透率、地缘政治 | 景气验证章节：ROE 趋势、产业景气、地缘风险 |
   | 李进 | 系统工程师思维 · 均衡与渗透率 | **组合管理 + 治理**：渗透率定位、底仓/机动仓、管理层与科研转化、治理一票否决 | 风险与纪律章节：管理层评估、渗透率定位、仓位建议 |

3. **引用不重复定义**（中期技能体系铁律）：
   - 估值档位 → 引用 `valuation-thermometer`（PEG 五档判定，不自行罗列阈值）
   - 卖出纪律 → 引用 `exit-signal`（P0~P5 唯一权威口径，时间止损归 P2）
   - 产业景气/渗透率 → 引用 `mid-industry-research`
   - 管理层 20 分制 / 科研转化 20 分制 → 引用 `mid-management-deep-dive` 与 V2.0
   - 轻量问答 → 引用 `garp-ask`（林奇主轴）
4. **写作框架不变**：三 Agent 协作、四阶段流程、写作风格规范、配图提取流程、公式规范——原样保留，仅内容视角中期化。
5. **数据规范**：双源交叉验证、误差 >1% 标记、禁止 LLM 心算、`financial_rigor.py` 精确计算、`report_audit.py` 抽检准出。
6. **网络限制**：禁止 Anthropic WebSearch/WebFetch，统一本地五工具（anysearch / doubao_search / exa_search / tavily_search / web_search）。

---

## 五、新建文件清单

| 文件 | 说明 |
|------|------|
| `.trae/skills/mid-wechat-article/SKILL.md` | 主技能文件（基于草稿 + 第七节修正清单转正，格式对齐长期版章节结构） |
| `.trae/skills/mid-wechat-article/README.md` | 技能说明（命令、适用场景、与长期版差异、输出路径、工具依赖） |

---

## 六、需修改的其他文件清单

| 文件 | 修改点 |
|------|--------|
| `CLAUDE.md` | 「基础工具与内容输出类」表格新增 `/mid-wechat-article {主题}` 一行（长期版 `/wechat-article` 行不动） |
| `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md` | ① 组合 5（第 515 行）`/wechat-article {主题} ← 单篇长文的公众号排版发布承接` 改为 `/mid-wechat-article`；② 技能全景图说明补充「1 个内容输出技能 mid-wechat-article」；③ 中期技能计数 15→16（并核对文档首部与全景图两处口径不一致）；④ 多技能组合建议 / 附录决策树检查 |
| `.trae/skills/mid-deep-company-series/SKILL.md`（第 410 行） | 「与现有 Skill 的关系」表 `/wechat-article` 行补充 `mid-wechat-article`（1~3 年发布承接） |
| `.trae/skills/mid-deep-company-series/README.md`（第 368 行） | 同上 |
| `research/1~3 年中长期投研系统完整开发方案与详细实施计划.md` | 历史方案文档：核对是否已把 `wechat-article` 列入中期链升级清单；若列了则标注「已由 mid-wechat-article 落地」，不修改原文 |
| `research/early-version/wechat-article技能文件（草稿）.md` | 草稿存档，文末标注「已转正为 .trae/skills/mid-wechat-article/」 |

**Grep 确认的 `wechat-article` 交叉引用清单与处置**：

| 文件 | 处置 |
|------|------|
| `.trae/skills/wechat-article/SKILL.md`、`README.md`（长期版） | **不动**（长期链文件） |
| `.trae/skills/证券AI价值投资研究工作步骤.md`（长期版） | **不动** |
| `.trae/skills/deep-company-series/README.md`（第 347 行） | **不动**（长期链） |
| `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md`（第 515 行） | 需更新（见上表） |
| `.trae/skills/mid-deep-company-series/SKILL.md`（第 410 行）、`README.md`（第 368 行） | 需更新（见上表） |
| `CLAUDE.md`（第 103 行） | 需更新（见上表） |
| `research/1~3 年中长期投研系统完整开发方案与详细实施计划.md` | 历史方案，标注已落地 |
| `docs/dev_docs/搜索服务选择策略重构方案.md`、`A股财报下载与提取统一缓存方案.md`、`PDF提取乱码检测Bug修复记录.md` | 低优先级：工具方案文档，不涉及命令名变更，可留待后续 |

> 注：经 Grep 确认，`mid-earnings-team` / `mid-earnings-review` 等中期技能使用**自有的公众号发布阶段**（内嵌编辑/读者 Agent），不交叉引用 `wechat-article` 命令，本轮无需回改。

---

## 七、草稿修正清单（撰写 SKILL.md 时逐一落实）

**修正 1 — frontmatter description 重写**
- `name: mid-wechat-article`、`disable-model-invocation: true` 保留（草稿已正确）。
- description 重写为对齐 V2.0 四大师分工：明确"公众号文章（1~3 年景气投资版）"，支持两类内容（景气投资分析为主、技术解读为辅），追加触发词（1~3 年 / 中期 / 公众号文章 / 财报解读 / 产业链分析 / 景气投资 / 卖出纪律等）。

**修正 2 — 四大师分工严格对齐 V2.0**
- 作者 Agent 景气投资 Prompt 扩展中的四大师角色按 V2.0 权威分工表重写：

  | 大师 | 草稿角色 | 修正后（对齐 V2.0） |
  |------|---------|---------------------|
  | 林奇 | 常识与 PEG | ✅ 选股起点 + 估值定价：六类分类、常识验证、PEG 估值 |
  | 郑希 | ROE 与景气 | ✅ 赛道选择：ROE 拐点、产业景气、渗透率、**补地缘政治风险** |
  | 李进 | 管理层与治理 | ✅ 组合管理 + 治理：渗透率定位、底仓/机动仓、管理层与科研转化、**治理一票否决** |
  | 欧奈尔 | 纪律与趋势 | ✅ 风控底线：8% 止损、趋势信号、P0~P5 触发检查 |

- 文章定位确认表默认文章类型由「技术解读」改为「景气投资」。

**修正 3 — 卖出纪律统一为 `exit-signal` P0~P5（核心修正）**
- 删除草稿自造"P0~P3 分级"，统一映射为 `exit-signal` P0~P5（时间止损归 P2，技术面仅作 P3 辅助、不构成独立层级）：

  | 级别 | 触发条件 | 决策 | 思想来源 |
  |------|---------|------|---------|
  | P0 治理一票否决 | 管理层失信、财务造假实锤、监管立案 | 立即清仓，不看估值趋势 | 李进（治理） |
  | P1 硬止损 | 单笔亏损 8%~10%，且无基本面反转信号 | 无条件止损 | 欧奈尔 |
  | P2 逻辑止损 | 连续 2 季业绩低于预期且产业景气未改善；或持有满 4 季度逻辑未兑现（时间止损） | 减仓或清仓 | 林奇 + 郑希 |
  | P3 产业景气拐点 | 渗透率减速 / ROE 拐头向下 | 减机动仓 | 李进 + 郑希 |
  | P4 估值透支 | PEG 进入高估/严重透支档 | 减 / 清机动仓 | 林奇 |
  | P5 性价比替换 | 其他标的 PEG 显著更低且产业趋势更强 | 调仓（每季度最多 1 次） | 机会成本 |

- SKILL.md 正文只列映射表，细则引用 `exit-signal` 输出，不重复展开 P0~P5 完整判定流程。

**修正 4 — PEG 阈值改为引用，不重复定义**
- 删除草稿自行罗列的 PEG 阈值（<1.2 买入、>1.5 高估），改为"调用 `valuation-thermometer` 得出 PEG 五档温度"，文中呈现估值结论时以该技能输出为准。
- 分批建仓规则（1/3+1/3+1/3、合理区间下沿/恐慌/景气确认）与底仓/机动仓分离保留（V2.0 原文，引用即可）。

**修正 5 — 产业景气/渗透率引用 `mid-industry-research`**
- 渗透率区间判断（10%~30% 黄金区、15% 临界点、50%~60% 兑现）引用 `mid-industry-research` 与 V2.0，不自行另立口径。

**修正 6 — 管理层 20 分制 / 科研转化 20 分制引用 `mid-management-deep-dive`**
- 李进管理层评估部分补全为：管理层四维度 20 分制 + 科研转化 20 分制，评分细则引用 `mid-management-deep-dive` 与 V2.0 第二部分；加入"治理一票否决"红线表述。

**修正 7 — 新增能力圈声明**
- 文首补充"能力圈声明"段（对齐 mid-earnings-team 范式）：适用于 1~3 年景气投资框架下的公众号文章写作，非短期交易工具、非「封仓十年」式超长期持有；适用场景（景气成长股财报解读、产业链分析、投资方法论）与不适用场景（纯周期股 PEG 不适用、困境反转、金融股、被动指数）。

**修正 8 — 补齐 A/B/C 信息丰富度评级与 AI 研究偏见预警**
- 调研阶段前置信息丰富度评级（同 mid-investment-team）：A 级共识过强需反面检验；B 级推算数据标置信度；C 级转第一性原理模式。

**修正 9 — 补齐数据抽检准出流程**
- 定稿阶段写入：文章落盘后执行 `python tools/common/report_audit.py extract → verdict`，偏差 ≤1% 准出、>1% 打回重查。

**修正 10 — 报告输出路径物理隔离**
- 草稿 `reports/{公司名}/{公司名}-公众号-{YYYYMMDD}.md`（与长期版同路径，碰撞）→ 改为 `reports/{公司名}/{公司名}-mid-wechat-{YYYYMMDD}.md`；技术主题 `reports/AI产业研究/公众号-{主题}-mid-wechat-{YYYYMMDD}.md`。

**修正 11 — 工具使用指南补全 `report_audit.py`**
- 工具表中补充 `tools/common/report_audit.py`（报告审核），与数据抽检准出流程呼应；其余数据/搜索/PDF 工具按长期版最新规范对齐。

**修正 12 — 关系表修正与补充**
- 草稿关系表引用不存在的 `/garp-team`，修正为 `/mid-investment-team`（四 Agent 全面公司研究，中期版）。
- 关系表补齐：`mid-earnings-team`（财报精读团队 + 发布）、`mid-earnings-review`（轻量财报）、`mid-deep-company-series`（深度长文系列）、`mid-investment-research` / `mid-investment-team`、`mid-private-company-research`、`garp-ask`、`valuation-thermometer` / `exit-signal` / `mid-industry-research` / `mid-management-deep-dive`（口径引用）、`wechat-article`（长期版，物理隔离）。

**修正 13 — 景气投资类文章结构对齐 V2.0 决策要点**
- 保留草稿 6 段结构（开头钩子 → 生意本质 → 景气验证 → 估值判断 → 风险与纪律 → 结论），并在"结论"段要求：给出对持有者/观望者分别的操作指引（对齐 mid-earnings-team 的读者价值检测），结论需落到"持有/加仓/减仓/清仓 + 核心理由"。

**修正 14 — 报告示例对齐**
- 腾讯 Q4 示例的 PEG 计算与卖出纪律标注为"以 `valuation-thermometer` / `exit-signal` 输出为准"；P0/P1/P3 分级改为 P0~P5 映射。

**修正 15 — 保留内容（不修改）**
- 三 Agent 协作架构、四阶段流程骨架、写作风格规范、配图提取流程（pdftoppm + PIL）、公式 LaTeX 规范、本地数据工具与网络搜索工具、PDF 提取（`pdf_extract.py` 首选）、文件命名、注意事项、局限性框架——原样保留，仅按上述修正增强中期化内容。

---

## 八、报告输出路径（建议）

```
reports/
├── {公司名}/
│   ├── {公司名}-mid-wechat-{YYYYMMDD}.md        ← 景气投资类公众号文章（定稿）
│   └── {公司名}-mid-wechat-{YYYYMMDD}-底稿.md   ← 作者初稿/编辑读者反馈（可选，自用）
├── AI产业研究/
│   └── 公众号-{主题}-mid-wechat-{YYYYMMDD}.md   ← 技术解读类
└── assets/{主题简称}/fig{序号}-{描述}.png        ← 配图资源
```

---

## 九、实施步骤顺序

1. 撰写 `.trae/skills/mid-wechat-article/SKILL.md`（按第七节修正清单）
2. 创建 `.trae/skills/mid-wechat-article/README.md`
3. 更新 `CLAUDE.md`「基础工具与内容输出类」表格
4. 更新 `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md`（组合 5 发布承接 + 全景图说明 + 计数）
5. 更新 `.trae/skills/mid-deep-company-series/SKILL.md` 与 `README.md` 关系表
6. `research/1~3 年中长期投研系统完整开发方案与详细实施计划.md` 标注已落地
7. `research/early-version/wechat-article技能文件（草稿）.md` 文末标注已转正
8. grep 全项目复查 `wechat-article` / `mid-wechat-article` 引用无残留错配

---

## 十、长期版不动声明

`.trae/skills/wechat-article/SKILL.md` 及其 README、`证券AI价值投资研究工作步骤.md`、`deep-company-series/README.md` 等长期链文件**一律不动**。

---

## 十一、影响与风险评估

| 风险点 | 等级 | 说明与应对 |
|--------|------|-----------|
| 兼容性风险 | 低-中 | 本技能是内容生产框架，与中期链决策技能无硬依赖冲突；主要风险是卖出纪律 / PEG 口径与既有技能不一致，已由修正 3/4 消除 |
| 路由风险 | 低 | 命令名 `mid-wechat-article` 带 `mid-` 前缀，明确命中中期链，不影响长期版 `/wechat-article` 路由 |
| 文档联动遗漏 | 低 | `wechat-article` 交叉引用清单已逐项评估（见第六节），长期版一律不动，仅中期链文档与 CLAUDE.md 联动 |
| 测试建议 | - | ① 调用 `/mid-wechat-article 腾讯2025Q4财报解读（景气视角）` 验证输出路径为 `-mid-wechat-{YYYYMMDD}` 隔离命名；② 抽查文章卖出纪律是否与 `exit-signal` P0~P5 一致；③ 抽查 PEG 结论是否与 `valuation-thermometer` 五档一致；④ 对产出文章跑 `report_audit.py` 抽检验证；⑤ grep 确认长期链上下文（巴芒段李 / 护城河永续 / 持有10年）未被误改 |
| 维护提示 | - | `research/early-version/` 草稿仅存档，不再作为活文档；后续口径变更以转正后的 SKILL.md 为准 |

---

## 十二、待确认决策点

> **确认记录（2026-09-08）：8 项决策点已逐条经用户确认，全部采纳推荐方案。** 同日用户对方案给出最终确认（"确认方案，开始开发"），已按第九节进入开发实施。

1. **命令语法**：`/mid-wechat-article {主题}` → ✅ **已确认**（与既有 mid-* 系列命名一致，带 `mid-` 前缀明确命中中期链，不影响长期版 `/wechat-article` 路由）
2. **报告目录命名**：`reports/{公司名}/{公司名}-mid-wechat-{YYYYMMDD}.md` → ✅ **已确认**（英文后缀 `-mid-wechat-` 与长期版物理隔离，避免碰撞）
3. **四大师分工调整**：认可「修正 2」分工（郑希补地缘政治、李进=组合管理+治理、林奇=选股起点+估值定价、欧奈尔=风控底线）→ ✅ **已确认**（严格对齐 V2.0「四位大师与个人投资者的连接方式」表）
4. **文章类型默认值**：默认「景气投资」（技术解读保留为次要类型）→ ✅ **已确认**
5. **卖出纪律 / PEG 口径**：统一引用 `exit-signal` P0~P5 与 `valuation-thermometer` 五档，SKILL.md 不重复罗列阈值 → ✅ **已确认**（引用不重复定义，草稿自造 P0~P3 与自列 PEG 阈值一律删除）
6. **是否创建 README.md**：对齐既有 mid-* 技能范式创建 → ✅ **已确认**
7. **关系表修正**：将草稿不存在的 `/garp-team` 修正为 `/mid-investment-team` → ✅ **已确认**
8. **低优先级联动**：本轮仅核心联动（CLAUDE.md + 中期工作步骤 + mid-deep-company-series 两处），`docs/dev_docs/` 三个工具方案文档留待后续 → ✅ **已确认**

---

*方案草拟完成 | 基于 early-version 草稿 + 长期版格式范式 + V2.0 理念口径 | 决策点已全部确认（8/8） | 2026-09-08 用户已最终确认，开发已按第九节实施顺序推进（任务 1~8）*
