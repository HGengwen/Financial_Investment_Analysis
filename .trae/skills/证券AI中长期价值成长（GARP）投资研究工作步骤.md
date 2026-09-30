# 证券AI中长期价值成长（GARP）投资研究工作步骤

> 本文档基于 `.trae/skills/` 下的 GARP 独立档技能（**22 个 `garp-*` 技能 + 2 个复用中期技能**），按照「第 0 步地缘政策前置 → 赛道扫描（+漏斗精选）→ 正向排序 → 个股验证（能力圈 + 五大支柱）→ 估值建仓 → 持仓管理 → 卖出触发」闭环，提供 1~5 年 GARP 价值成长投研的技能选用与组合建议。
>
> **适用持有周期：1~5 年（GARP 独立档）。**
>
> 与《证券AI价值投资研究工作步骤.md》（10 年长期链）及《证券AI中长期（1~3年）价值投资研究工作步骤.md》（1-3 年中期链）**三档并存、物理隔离**：长期链回答「这家公司 10 年后还在吗？」，中期链回答「这家公司未来 1-3 年景气向上吗？值不值得进？」，GARP 链回答「这家公司未来 1~5 年价值成长能否兑现？」。
>
> 三档各自拥有独立的口令前缀体系（`garp-` / `mid-` / 无前缀）、独立的编号体系（**GARP 五级卖出** vs 中期 P0~P5 vs 长期六关 Checklist）与独立的阈值口径，**不得互相引用其可执行口令、编号与阈值**。
>
> **数据截止日期**：2026-09-19 | **免责声明**：仅供学习研究参考，不构成投资建议。

---

## 目录

- [一、GARP 技能全景图](#一garp-技能全景图)
- [二、闭环工作流程](#二闭环工作流程)
- [三、卖出决策优先级金字塔（五级）](#三卖出决策优先级金字塔五级)
- [四、底仓/机动仓分离与仓位上限](#四底仓机动仓分离与仓位上限)
- [五、与另两档文档的关系与路由规则](#五与另两档文档的关系与路由规则)
- [六、数据与工具依赖](#六数据与工具依赖)
- [七、全局约束](#七全局约束)
- [八、多技能组合建议](#八多技能组合建议)
- [附录：GARP 技能速查决策树](#附录garp-技能速查决策树)

**三份工作步骤文档的边界一句话摘要**：

- **10 年后这家公司还在吗？** → 读《证券AI价值投资研究工作步骤.md》（长期链，无前缀技能）
- **未来 1-3 年景气向上吗？值不值得进？** → 读《证券AI中长期（1~3年）价值投资研究工作步骤.md》（中期链，`mid-` 前缀）
- **未来 1~5 年价值成长能否兑现？** → **读本文档**（GARP 独立档，`garp-` 前缀）

---

## 一、GARP 技能全景图

GARP 独立档共 **22 个 `garp-*` 技能**（不含复用）+ **2 个复用中期技能**（`qoq-accelerator` / `trend-momentum-scan`）= **24 个可用入口**，按闭环阶段排列：

| 阶段 | 技能 | 命令 | 报告输出路径 |
| --- | --- | --- | --- |
| ⓪ 未上市预研 | 未上市公司「上市后 GARP 适配性预判」 | `/garp-private-company-research {公司名}` | `reports/{公司名}/{公司名}-garp-private-{YYYYMMDD}.md` |
| 第0步 地缘政策前置 | 地缘政治与政策资本前置判定 | `/garp-geo-policy {行业/公司}` | `reports/{对象}/{对象}-garp-geo-{YYYYMMDD}.md` |
| 第0步 宏观校准（并行） | 宏观环境适配 | `/garp-macro {市场}` | `reports/{市场}/macro-garp-{YYYYMMDD}.md` |
| ① 赛道扫描·时代主线 | 时代α捕手 | `/garp-era-alpha {行业/方向}` | `reports/era-alpha/{方向}/`（`full-scan/*-garp-era-alpha-*`、`mainline-map.md`、`alpha-watchlist.md` 等） |
| ① 赛道扫描·行业全景 | GARP 行业研究 | `/garp-industry-research {行业名}` | `reports/industry/{行业名}-garp-industry-{YYYYMMDD}.md` |
| ① 赛道扫描·瓶颈挖掘 | 供应链瓶颈猎手 | `/garp-bottleneck-hunter {趋势名}` | `reports/garp-bottleneck/{趋势名}/`（`full-scan/*-garp-bottleneck-*`、`monthly/*-garp-update-*`、`master-map.md`、`watchlist.md`、`deep-dive/*-garp-deep-*`） |
| ①→② 漏斗精选 | GARP 行业漏斗精选 | `/garp-industry-funnel {行业名}` | `reports/industry/{行业名}-garp-funnel-{YYYYMMDD}.md` |
| ② 正向排序 | GARP 景气趋势筛选 | `/garp-trend-tech-screen {公司/行业/指数/主题}` | `reports/trend-screen/`（`--export` 开启时落盘） |
| ③ 个股验证·买入前门槛 | GARP 买入前检查 | `/garp-investment-checklist {公司名}` | `reports/{公司名}/{公司名}-garp-checklist-{YYYYMMDD}.md` |
| ③ 个股验证·快速研究 | GARP 个股深度研究（单 Agent 五大师） | `/garp-investment-research {公司名}` | `reports/{公司名}/{公司名}-garp-research-{YYYYMMDD}.md` |
| ③ 个股验证·团队研判 | GARP 投研团队 | `/garp-investment-team {公司名}` | `reports/{公司名}/{公司名}-garp-investment-team-{YYYYMMDD}.md` |
| ③ 个股验证·管理层 | GARP 管理层与科研转化 | `/garp-management {公司名}` | `reports/{公司名}/{公司名}-garp-management-{YYYYMMDD}.md` |
| ④ 估值建仓 | GARP 估值锚定 | `/garp-valuation {公司名}` | `reports/{公司名}/{公司名}-garp-valuation-{YYYYMMDD}.md` |
| ⑤ 持仓管理·论文建档 | GARP 投资论文追踪 | `/garp-thesis-tracker {公司名}` | `reports/{公司名}/{公司名}-garp-thesis.md`（活文档）+ `-garp-track-{YYYYMMDD}.md`（季度体检） |
| ⑤ 持仓管理·漂移检测 | GARP 论文漂移检测 | `/garp-thesis-drift {标的}` | `reports/{标的}/{标的}-garp-drift-{YYYYMMDD}.md` |
| ⑤ 持仓管理·组合审视 | GARP 组合管理 | `/garp-portfolio-review {持仓清单}` | `reports/portfolio-garp-{YYYYMMDD}.md` |
| ⑤ 持仓管理·异动归因 | GARP 公司新闻脉搏 | `/garp-news-pulse {公司名}` | `reports/{公司名}/{公司名}-garp-news-{YYYYMMDD}.md` |
| ⑤ 持仓管理·财报精读（轻量） | GARP 财报精读（单 Agent） | `/garp-earnings-review {公司名} {期间}` | `reports/{公司名}/{公司名}-garp-earnings-review-{期间}.md` |
| ⑤ 持仓管理·财报精读（团队） | GARP 财报精读团队 | `/garp-earnings-team {公司名} {期间}` | `reports/{公司名}/{公司名}-garp-earnings-team-{期间}.md`（+ 7 份分报告） |
| ⑥ 卖出触发 | GARP 卖出信号 | `/garp-exit {标的}` | **不独立落盘**（见下方说明） |
| 内容输出·深度长文 | GARP 深度公司系列 | `/garp-deep-company-series {公司名}` | `reports/{公司名}/《看懂{公司名}》-garp-{YYYYMMDD}/0X-XX.md` |
| 内容输出·公众号 | GARP 微信公众号文章 | `/garp-wechat-article {主题}` | `reports/{公司名}/{公司名}-garp-wechat-{YYYYMMDD}.md` |
| **合计** | **22 个 `garp-*`** | — | — |

### 1.1 复用中期技能（2 个）

以下 2 个技能属 **1-3 年中期链**，被 GARP 链**复用**；其**判定逻辑、参数与核心口令完全归属于中期链**，GARP 链仅经其「出口转接段」接收结论：

| 阶段 | 技能 | 命令 | 报告输出路径 | GARP 链用途 |
| --- | --- | --- | --- | --- |
| ④/⑤ 估值与景气交叉验证 | `/qoq-accelerator` | `/qoq-accelerator {公司名}` | `reports/{公司名}/{公司名}-qoq-{YYYYMMDD}.md` | 增速二阶导 → 提供 `garp-valuation` 估值修正输入 |
| ⑤/⑥ 持仓动量体检 | `/trend-momentum-scan` | `/trend-momentum-scan {持仓代码}` | `reports/{持仓代码}-momentum-{YYYYMMDD}.md` | MA200 破位 / ATR(14) → 提供 `garp-exit` 技术面否决与止损价 |

> **复用纪律**：两技能的 `--horizon` 等参数与判定规则**均为中期链口径，GARP 链不改动、不覆盖**；GARP 链只消费其输出结论（详见两技能 `SKILL.md` / `README.md` 的「出口转接」节）。

### 1.2 计数与路径说明

| # | 说明 |
| --- | --- |
| ① | 本档技能计数口径：**22 个 `garp-*`**（与 `CLAUDE.md`「GARP 独立档类（1~5 年）」表 22 项一一对应）+ **2 个复用中期技能** = **24 个可用入口**。项目技能总数口径为 **65 个 = 43 个非 GARP + 22 个 GARP**（本档「22」指 `garp-*` 目录数，不含复用技能）。 |
| ② | **`/garp-exit` 不独立落盘**：其 `SKILL.md` 仅声明**读取**上游文件（`-garp-thesis.md` / `-garp-valuation-*.md`），**未声明自身报告落盘路径**——结论**在对话内输出**。这是如实口径，**不得臆造路径**。 |
| ③ | 所有 `garp-*` 技能**均已交付**，命令与输出路径以其各自 `SKILL.md` 原文为准；本表为聚合视图，不重新定义。 |

---

## 二、闭环工作流程

GARP 链的完整闭环（第 0 步为**强制闸门**，⓪ 为可选前置）：

```text
 ⓪ 未上市预研（可选前置）
      └─ garp-private-company-research
                      │
 第0步 地缘政策前置（强制闸门）
      ├─ garp-geo-policy  → 0.3 三维交叉矩阵 + 赛道两分法
      └─ garp-macro       → 宏观三表（并行校准估值区间与仓位下限）
                      │
 ① 赛道扫描（确定主赛道，渗透率 15%~40% 黄金窗）
      ├─ garp-era-alpha         时代主线识别
      ├─ garp-industry-research 行业全景
      └─ garp-bottleneck-hunter 卡脖子环节
                      │
 ①→② 漏斗精选
      └─ garp-industry-funnel   → 建立公司池
                      │
 ② 正向排序
      └─ garp-trend-tech-screen → S/A/B/C 评级 + 反证清单
                      │
 ③ 个股验证（能力圈四维 → 五大支柱）
      ├─ garp-investment-checklist（硬门槛，一票否决）
      ├─ garp-investment-research / garp-investment-team（深度研判）
      └─ garp-management（管理层 + 科研转化）
                      │
 ④ 估值建仓
      └─ garp-valuation → 多工具估值矩阵 + 宏观 PE 区间 + ESG 折价 → 分批建仓
                      │
 ⑤ 持仓管理
      ├─ garp-thesis-tracker（论文建档 + 季度体检）
      ├─ garp-thesis-drift（H1~H7 漂移）
      ├─ garp-portfolio-review（组合审视）
      ├─ garp-news-pulse（异动归因）
      └─ garp-earnings-review / garp-earnings-team（财报精读）
                      │
 ⑥ 卖出触发
      └─ garp-exit → 五级优先级硬编码检查
```

### 阶段〇：未上市公司预研（可选前置）

**阶段目标**：对公司尚处 Pre-IPO 阶段、暂无二级市场数据的标的，判断其**上市后是否适用 GARP 框架**、是否值得等待上市。

**推荐流程**：6 路 Agent 并行拼凑分散信息 → 还原真实价值 → 输出「上市后 GARP 适配性预判」。

**技能与命令**：

| 技能 | 命令 | 用途 |
| --- | --- | --- |
| `garp-private-company-research` | `/garp-private-company-research {公司名}` | 未上市公司建档与适配性预判 |

**硬门槛**：无（预研性质，**可选**）。

> **特殊说明**：本阶段**不属闭环强制环节**；其结论仅作「上市后 GARP 适配性预判」，**不产生任何买入动作**。公司上市后须**从头进入第 0 步**重新判定。

---

### 第 0 步：地缘政策前置（强制闸门）

**阶段目标**：判定目标赛道的地缘倒逼强度与政策资本强度，**避免进入「政策否决」或「地缘逆风」赛道**；同步完成宏观环境校准，确定估值区间与仓位下限。

**推荐流程**：

1. 先执行 `garp-geo-policy`，产出 **0.3 三维交叉矩阵**落点（六行判定）+ **赛道两分法**结论；
2. 并行执行 `garp-macro`，产出**宏观三表**（利率 PEG 区间 / 经济周期仓位 / 美林时钟矩阵）；
3. 二者结论合并为后续阶段的**估值区间**与**现金仓位下限**约束。

**技能与命令**：

| 技能 | 命令 | 关键产出 |
| --- | --- | --- |
| `garp-geo-policy` | `/garp-geo-policy {行业/公司}` | 地缘倒逼强度 + 政策覆盖度 → 0.3 三维交叉矩阵 + 赛道两分法 |
| `garp-macro` | `/garp-macro {市场}` | 美林四档查表 → 调整后 PEG 区间 + 现金仓位下限 + 单只上限（三档） |

**硬门槛**：

- **三维交叉矩阵落在「回避区」→ 立即终止**，不得进入 ① 赛道扫描；
- 宏观结论中的**调整后 PEG 区间**为后续 ④ 估值建仓的**强制上沿**，不得突破。

---

### 阶段一：赛道扫描

**阶段目标**：找到**渗透率处于 15%~40% 黄金窗**且 TAM ≥ 1000 亿元的主赛道，并识别其中的卡脖子环节。

**推荐流程**：按需择路（可并行）：

| 路径 | 适用情形 |
| --- | --- |
| 时代主线识别 | 判断某方向是否属**时代级主线 / 范式转移** |
| 行业全景研究 | 首次进入一个行业，需要产业链全景 + Tier1~4 分层 |
| 卡脖子环节挖掘 | 已锁定趋势，需要从供应链咽喉位置挖掘**第二、三层**机会 |

**技能与命令**：

| 技能 | 命令 | 关键产出 |
| --- | --- | --- |
| `garp-era-alpha` | `/garp-era-alpha {行业/方向}` | 渗透率 15%~40% 黄金窗收敛闸门 + 五维景气验证 + 五大师透镜 → 介入锚点 |
| `garp-industry-research` | `/garp-industry-research {行业名}` | 六维筛选 + 0.3 三维矩阵与赛道两分法 + 卡脖子环节 + Tier1~4 + 十四节报告 |
| `garp-bottleneck-hunter` | `/garp-bottleneck-hunter {趋势名}` | 咽喉位置第二、三层机会 + 国产化率四梯队 + 六档与 3 年隐含回报检查 |

**硬门槛**：

- **渗透率 < 15% 或 > 40%：不得建底仓**（仅可入观察池）；
- **TAM < 1000 亿元：不进入 GARP 主赛道**；
- 国产化率须落在**四梯队**判定框架内（决定成长空间与政策强度）。

---

### 阶段一·五：漏斗精选

**阶段目标**：从全行业候选收敛到 **3 家底仓 + 2 家机动仓**的终选组合。

**推荐流程**：**能力圈四维自检 → 6 硬指标粗筛 → 五大支柱精析 → 五大师研判**四层递进。

**技能与命令**：

| 技能 | 命令 | 关键产出 |
| --- | --- | --- |
| `garp-industry-funnel` | `/garp-industry-funnel {行业名}` | 3 家底仓 + 2 家机动仓终选组合 |

**硬门槛**：

- 6 硬指标粗筛**不达标者直接出池**；
- 五大支柱精析中 **V1~V4 任一否决即为出池**；
- 能力圈四维不满足者**不得进入终选**。

---

### 阶段二：正向排序

**阶段目标**：对漏斗产出的候选池按**景气五维加权打分**排序，形成建仓优先级。

**推荐流程**：四层递进 + 五维加权打分 → **S/A/B/C 评级** → 地缘修正 → 技术面止损位 → 输出**反证清单**。

**技能与命令**：

| 技能 | 命令 | 关键产出 |
| --- | --- | --- |
| `garp-trend-tech-screen` | `/garp-trend-tech-screen {公司/行业/指数/主题}` | S/A/B/C 评级 + GARP 三档结论 + 反证清单 |

**硬门槛**：

- 评级 **C 者不进入 ③ 个股验证**；
- 反证清单须**逐条回应**，不得留空。

---

### 阶段三：个股验证

**阶段目标**：完成「**能力圈四维 + 五大支柱**」双闸门验证，形成可建仓结论。

**推荐流程**：

1. **硬门槛先行**：`garp-investment-checklist`（能力圈四维 → 财务五门槛 → 五大支柱 V1~V4 一票否决 / S1~S5 达标 → 三档结论 + 镜子测试）；
2. **深度研判**：`garp-investment-research`（单 Agent 五大师）或 `garp-investment-team`（五角色并行 + Team Lead 综合研判）；
3. **管理层纵深**：`garp-management`（诚信前置否决闸门 → 管理层 / 科研转化两套 20 分制合成）。

**技能与命令**：

| 技能 | 命令 | 关键产出 |
| --- | --- | --- |
| `garp-investment-checklist` | `/garp-investment-checklist {公司名}` | 能力圈四维 + 财务五门槛（科技豁免 L1/L2/L3）+ 五大支柱 → 三档结论 |
| `garp-investment-research` | `/garp-investment-research {公司名}` | 林奇六类归类 / 渗透率五档 / ROIC 四档 / 多工具估值矩阵 / 五级卖出 |
| `garp-investment-team` | `/garp-investment-team {公司名}` | 五角色并行分析 + Team Lead 综合研判 |
| `garp-management` | `/garp-management {公司名}` | 诚信前置否决 → 管理层 / 科研转化两套 20 分制合成 |

**硬门槛**：

- **能力圈四维不满足 → 直接放弃**（不进入后续任何阶段）；
- **V1~V4 任一否决 → 一票否决**；
- **管理层诚信前置闸门不通过 → 一票否决**，不得以其他维度高分抵扣。

---

### 阶段四：估值建仓

**阶段目标**：按公司类型选定**主锚估值方法**，结合宏观 PE 区间与 ESG 折价，确定买入区间并**分批建仓**。

**推荐流程**：

1. **选主锚**（按公司类型）：快速增长型 → 调整后 PEG；高研发投入型 → PS / EV-Sales + Rule of 40；未盈利科技型 → PS / EV-Sales + 研发管线 NPV；稳定增长型 → 远期 PE + 隐含 PEG；成熟型 → DCF；
2. **宏观校准**：叠加第 0 步 `garp-macro` 的**调整后 PEG 区间 / PE 区间**；
3. **ESG 折价**：高环境风险行业按 **8~9 折**调整；
4. **分批建仓**：按三分法分批，结合 ATR(14) 设定止损位。

**技能与命令**：

| 技能 | 命令 | 关键产出 |
| --- | --- | --- |
| `garp-valuation` | `/garp-valuation {公司名}` | 多工具估值矩阵 + 宏观 PE 区间 + ESG 折价 → 统一六档结论 |
| `qoq-accelerator`（复用） | `/qoq-accelerator {公司名}` | 增速二阶导 → 估值修正输入（±1 档上限） |

**硬门槛**：

- **估值高于区间上沿 → 不得建仓**（等待或放弃）；
- **分批纪律**：不得一次性满仓，须按三分法执行；
- 单只初始仓位上限见第四节。

---

### 阶段五：持仓管理

**阶段目标**：为已建仓标的建立**投资论文**并持续体检，及时发现逻辑漂移与组合失衡。

**推荐流程**：

1. **建档**：`garp-thesis-tracker` 建立投资论文 + 五大师假设清单；
2. **季度体检**：`garp-thesis-tracker` 季度更新 → 健康度评分与底仓/机动仓相对动作；
3. **按需触发**：财报季 / 异动 / 季度再平衡 / 漂移复核。

**技能与命令**：

| 技能 | 命令 | 关键产出 |
| --- | --- | --- |
| `garp-thesis-tracker` | `/garp-thesis-tracker {公司名}` | 投资论文（活文档）+ 季度体检（健康度评分） |
| `garp-thesis-drift` | `/garp-thesis-drift {标的}` | H1~H7 七维假设逐条验证 → 四级漂移等级 + 五级卖出映射 |
| `garp-portfolio-review` | `/garp-portfolio-review {持仓清单}` | 底仓/机动仓分离 + 单只与行业上限 + 流动性/ESG/宏观调档 |
| `garp-news-pulse` | `/garp-news-pulse {公司名}` | 股价异动快速归因 + 五级卖出触发初筛 + H1~H7 影响评估 |
| `garp-earnings-review` | `/garp-earnings-review {公司名} {期间}` | GARP 财报精读（轻量版） |
| `garp-earnings-team` | `/garp-earnings-team {公司名} {期间}` | 五大师并行解读 + Team Lead 五维评分合成 |
| `qoq-accelerator`（复用） | `/qoq-accelerator {公司名}` | 连续 3 季二阶导 → 拐点预警 |
| `trend-momentum-scan`（复用） | `/trend-momentum-scan {持仓代码}` | SMR / RSI50 / MA50 / MA200 技术破位预警 |

**硬门槛**：

- 论文漂移达**「四级漂移」→ 交 `garp-exit`**；
- `trend-momentum-scan` 的 **MA200 破位为独立否决项**（不直接映射单一级别，须走决策树后交 `garp-exit`）；
- 组合层面：单一行业 **≤ 40%**；单只绝对上限 **≤ 20%**。

---

### 阶段六：卖出触发

**阶段目标**：按**五级优先级**执行卖出纪律，先保命再谈收益。

**推荐流程**：五级硬编码检查（**诚信否决 > 硬止损 > 逻辑止损 > 产业景气 > 估值**）+ 补充机制（时间止损 / 性价比替换）。

**技能与命令**：

| 技能 | 命令 | 关键产出 |
| --- | --- | --- |
| `garp-exit` | `/garp-exit {标的}` | 五级优先级硬编码检查（结论在对话内输出，不独立落盘） |
| `trend-momentum-scan`（复用） | `/trend-momentum-scan {持仓代码}` | MA200 破位独立否决 + ATR(14) 止损价 |

**硬门槛**：

- **诚信否决 / 硬止损任一命中 → 无条件执行**，不得讨论；
- ATR(14) 动态止损位由 `momentum.py stop_price` 提供，硬止损阈值为 **8%~10%**。

---

## 三、卖出决策优先级金字塔（五级）

> **口径来源**：GARP 框架 第三部分·三（五级卖出规则 + 补充机制）、第五部分·二（决策优先级金字塔 + 一票否决语境边界）。本节为**引用与编排**，不重建口径。

### 3.1 五级优先级（自高而低）

| 级别 | 名称 | 触发条件 | 执行动作 |
| --- | --- | --- | --- |
| **一级** | **诚信否决** | 管理层诚信问题被证实（造假、承诺系统性不兑现、重大利益侵占） | **一票否决，无论盈亏立即清仓** |
| **二级** | **硬止损** | 单笔亏损达 **8%~10%**，或 ATR(14) 动态止损位被击穿 | **无条件止损** |
| **三级** | **逻辑止损** | 投资论文核心假设（H1~H7）被证伪，或五大支柱出现结构性破坏 | 减仓至观察仓 / 清仓 |
| **四级** | **产业景气** | 赛道渗透率越过黄金窗上限、景气度连续下行、政策/地缘反转 | 降级 / 减仓 |
| **五级** | **估值** | 估值超出目标区间上沿显著幅度且无基本面支撑 | 减仓 / 换仓 |

### 3.2 一票否决的语境边界

| 语境 | 一票否决适用对象 | 说明 |
| --- | --- | --- |
| **买入前**（阶段三） | 能力圈四维、五大支柱 **V1~V4**、管理层**诚信前置闸门** | 任一不通过即**不建仓** |
| **持有中**（阶段五/六） | **诚信否决**（一级） | 证实即清仓，与其他维度评分无关 |

> **边界要点**：`V1~V4` 的否决效力**限于买入前**；持有期内的持续否决权仅归**诚信否决**。不得把买入前否决项直接套用为持有期卖出触发（须经 `garp-thesis-drift` 判定为逻辑止损）。

### 3.3 补充机制

| 机制 | 触发 | 动作 |
| --- | --- | --- |
| **时间止损** | 持有超过预定周期而逻辑未兑现（论文假设长期不推进） | 减仓 / 退出，释放资金 |
| **性价比替换** | 组合内出现显著更优标的（风险调整后回报差达阈值） | 换仓，不新增总仓位 |

### 3.4 与中期链的区隔声明

> **本档卖出不使用中期链 `exit-signal` 的 P0~P5 编号体系**，亦不使用长期链的 Checklist + 红线否决口径。GARP 档仅使用**上表五级**，五级与 P0~P5 **物理隔离、不得混用**。

---

## 四、底仓/机动仓分离与仓位上限

> **口径来源**：GARP 框架 第三部分·一/二（底仓/机动仓与仓位上限、ATR 止损）、第五部分·四（宏观环境适配三表）。本节为**引用与编排**，不重建口径。

### 4.1 仓位结构

| 仓位类型 | 占比区间 | 定位 |
| --- | --- | --- |
| **底仓** | **60%~80%** | 逻辑已验证、决定长期收益的核心持仓 |
| **机动仓** | **20%~40%** | 景气/事件驱动的弹性仓位，可快进快出 |

### 4.2 单只仓位上限（三级）

| 阶段 | 单只上限 | 说明 |
| --- | --- | --- |
| 初始建仓 | **≤ 10%** | 未经持有验证的新仓 |
| 验证后 | **≤ 15%** | 论文经 ≥1 个季度体检未被削弱 |
| 绝对上限 | **≤ 20%** | 无论验证程度，**任何单只不得超过 20%** |

### 4.3 行业集中度

单一行业合计仓位 **≤ 40%**。超限须经 `garp-portfolio-review` 审视并给出减仓路径。

### 4.4 现金纪律

现金常态仓位 **10%~20%**；上限由**宏观三表**（第 0 步 `garp-macro`）调档确定。市场处于明确逆风档位时，现金下限**上调**。

### 4.5 动态止损（ATR）

| 项 | 口径 |
| --- | --- |
| 止损价公式 | **止损价 = 买入价 −（2~3）× ATR(14)** |
| 硬止损阈值 | 单笔亏损 **8%~10%** → 二级卖出（无条件） |
| 工具 | `tools/common/momentum.py` 的 `atr` / `stop_price` |

### 4.6 宏观环境调档（宏观三表）

| 表 | 用途 |
| --- | --- |
| **利率 × PEG 区间表** | 按利率档位给出**调整后 PEG 区间**（估值强制上沿） |
| **经济周期 × 仓位表** | 按经济周期档位给出**现金仓位下限** |
| **美林时钟矩阵** | 按美林四档给出**单只上限**（三档）与配置偏向 |

> **禁止心算**：ATR、止损价、仓位占比、PEG 区间等一切算术均须经 `financial_rigor.py` 或 `momentum.py` 执行。

---

## 五、与另两档文档的关系与路由规则

### 5.1 三轨并存，按持有周期分流

| 维度 | 中期链（1-3 年） | **GARP 链（1~5 年）** | 长期链（10 年） |
| --- | --- | --- | --- |
| 核心问题 | 未来 1-3 年景气向上吗？ | **未来 1~5 年价值成长能否兑现？** | 10 年后还在吗？ |
| 入口技能 | `mid-industry-research` | **`garp-geo-policy`（第 0 步）→ `garp-industry-research`** | `industry-research` |
| 筛选逻辑 | 正向排序（识别爆发力） | **正向排序 + 五大师透镜（能力圈 / 景气 / 护城河 / 治理 / 估值）** | 逆向淘汰（排除非一流） |
| 筛选技能 | `mid-trend-tech-screen` | **`garp-trend-tech-screen`** | `quality-screen` |
| 个股验证 | `mid-investment-checklist`（七关）+ `mid-investment-research`/`mid-management-deep-dive` | **`garp-investment-checklist`（七关）+ `garp-investment-research`/`garp-investment-team`/`garp-management`** | `investment-checklist`（六关）+ `investment-research`/`management-deep-dive` |
| 估值口径 | PEG/PSG/PE 分位/implied-growth 五档温度 | **统一六档（调整后 PEG / Rule of 40 + EV-Sales / 研发管线 NPV / 远期 PE / DCF）+ 宏观 PE 区间 + ESG 折价** | DCF/安全边际/三情景 |
| 漂移检测 | `mid-thesis-drift`（景气假设） | **`garp-thesis-tracker` → `garp-thesis-drift`（H1~H7 七维假设）** | `thesis-drift`（护城河永续性） |
| 卖出 | `exit-signal` P0~P5 | **`garp-exit` 五级卖出（一级~五级）** | Checklist + 红线否决 |
| 禁止术语 | 护城河永续、终局思维、持有 10 年 | **其他档位的可执行口令、编号体系、命令名、路径与文件名、长期退出倍数口径** | 景气爆发、趋势动量 |

> **本档补充**：GARP 链完整闭环（八节全景、五级卖出金字塔、底仓/机动仓与仓位上限、多技能组合建议）见**本文档**；中期文档仅做路由层隔离说明。

### 5.2 持有周期路由规则

> 路由规则以 **CLAUDE.md 为唯一权威版**，本处为引用，保持与 CLAUDE.md 完全一致：

- **中期链（1-3 年）**：提及「1-3 年 / 中期 / 景气 / 趋势 / 成长爆发」→ `mid-industry-research` → `mid-industry-funnel` → `mid-trend-tech-screen` → `mid-investment-checklist` → `valuation-thermometer` → `qoq-accelerator` → `trend-momentum-scan` → `mid-thesis-drift` → `exit-signal`
- **中期链 · 时代主线识别**：提及「时代α / 高增长核心资产 / 时代主线 / 范式转移」且属 1-3 年 / 中期 / 景气语境 → `mid-era-alpha` → `mid-industry-research` → `mid-industry-funnel` → `mid-trend-tech-screen` → `mid-investment-checklist` → `exit-signal`
- **GARP 链（1~5 年）**：提及「1~5 年 / GARP / 价值成长 / 成长爆发 / 五大师」→ `garp-geo-policy` → `garp-industry-research` → `garp-industry-funnel` → `garp-trend-tech-screen` → `garp-investment-checklist` → `garp-valuation` → `garp-portfolio-review` / `garp-news-pulse` / `garp-earnings-review` / `garp-thesis-drift` → `garp-exit`
- **GARP 链 · 时代主线识别（1~5 年）**：提及「时代α / 高增长核心资产 / 时代主线 / 范式转移」且属 1~5 年 / GARP / 价值成长语境 → `garp-era-alpha` → `garp-industry-research` → `garp-industry-funnel` → `garp-trend-tech-screen` → `garp-investment-checklist` → `garp-exit`
- **长期链（10 年）**：提及「10 年 / 长期 / 永续 / 护城河」→ `quality-screen` → `investment-research` → `thesis-tracker` → `thesis-drift`
- **长期链 · 时代主线识别（10 年）**：提及「时代α / 高增长核心资产 / 时代主线 / 范式转移」且属 10 年 / 长期 / 永续语境 → `era-alpha` → `quality-screen` → `investment-research` → `thesis-tracker` → `thesis-drift`
- **`mid-` / `garp-` 前缀显式调用优先匹配**：`/mid-xxx` 直接命中对应中期技能，`/garp-xxx` 直接命中对应 GARP 技能，均不受关键词路由影响
- **持有周期不明**：先询问用户持有周期（1-3 年 / 1~5 年 / 10 年）再路由

### 5.3 显式前缀优先

`/garp-xxx` 直接命中对应 GARP 技能，**不受关键词路由影响**。凡使用 `garp-` 前缀，一律按**本档 1~5 年口径**执行。

### 5.4 三档物理隔离（不得互相引用）

> **三档物理隔离**：`garp-` 前缀唯一归属 1~5 年 GARP 独立档；`mid-` 前缀唯一归属 1-3 年中期链；无前缀技能归属 10 年长期链；三档不得互相引用其可执行口令、编号体系与阈值口径。

| 禁止事项 | 说明 |
| --- | --- |
| 不得把 GARP 五级卖出写成 `P0~P5` | GARP 档**只使用五级**（一级~五级），`P0~P5` 属中期链 `exit-signal` |
| 不得把 GARP 仓位口径写成中期口径 | 底仓 60%~80% / 机动仓 20%~40% / 单只 10-15-20% 为**本档口径** |
| 不得在本档引用长期链退出倍数口径 | 终值 PE、十倍 IRR 等属**长期链** `terminal_value.py` 口径 |
| 不得改写复用技能的中期链参数 | `qoq-accelerator --horizon` 固定 `mid`，GARP 链不改动 |

---

## 六、数据与工具依赖

GARP 链在复用项目通用工具生态的基础上，另有 **9 项专用工具**（均已交付，签名冻结）。

### 6.1 GARP 专用工具

| 用途 | 工具 | 子命令 / 函数 | 交付任务 |
| --- | --- | --- | --- |
| 0.3 三维交叉矩阵 + 国产化率四档 | `tools/specialized/geo_policy_screen.py` | `screen` / `localize` / `examples` / `scan` | P3-1~P3-3 |
| 宏观三表校准（利率 / 经济 / 美林） | `tools/specialized/macro_calibrator.py` | 见 `tools-scripts/garp-macro-tools.md` | P2-1~P2-3 |
| 治理与 ESG 数据 | `tools/specialized/governance_data.py` | `management` / `research` / `esg` | P3-7 |
| 精确估值（7 个 GARP 子命令） | `tools/common/financial_rigor.py` | `roic` / `incremental-roic` / `wacc` / `rule-of-40` / `ev-sales` / `adjusted-peg` / `dcf` | P1-1~P1-7 |
| ATR 动态止损 | `tools/common/momentum.py` | `atr` / `stop_price` | P1-8 / P1-9 |
| 景气五维打分引擎 | `tools/specialized/trend_tech_screen.py` | `score` / `batch` | 既有（签名冻结） |
| 研发管线 NPV | `tools/specialized/in_research_scan.py` | `scan` / `pipeline-npv` | P3-8 |
| 年报结构化抽取（含治理字段） | `tools/common/annual_report_parser.py` | `--output-json`（`governance` 字段） | P3-7 |
| 报告准出审核 | `tools/common/report_audit.py` | `extract` / `verdict` | 既有 |

> **引用纪律**：本表只列**命令与用途**，不复制工具内部字段定义；详细字段见 `.trae/skills/tools-scripts/garp-*-tools.md`。

### 6.2 三市场基础数据工具

| 用途 | 工具 | 关键参数 |
| --- | --- | --- |
| A 股行情 + 动量/技术面 | `tools/a_share/stock_quote.py` | `--momentum --auto-peers` |
| A 股财务指标 | `tools/a_share/stock_financial.py` | `--code` |
| 港股财务/行情 | `tools/hk_stock/stock_financial.py`、`tools/hk_stock/stock_quote.py` | `--financial` / `--code` |
| 美股财务/行情 | `tools/us_stock/stock_financial.py`、`tools/us_stock/stock_quote.py` | `--code` |
| 年报/季报 PDF 获取与提取 | `tools/common/report_hub.py`、`tools/common/pdf_extract.py` | `ensure` / `extract` |
| 大宗商品价格 | `tools/common/commodity_price.py` | `--code` |
| 汇率 | `tools/common/fx_rate.py` | `--code` |

### 6.3 网络搜索工具选型

| 市场 | 主源 | 辅源 |
| --- | --- | --- |
| A 股 | `tools/common/anysearch.py`（行业/主题级 `--count 10 --zone cn`；判例 / 专利定向 `--tag legal.case` / `--tag ip.global`；金融子标签须两级 + 必填 params） | `tools/common/doubao_search.py`（`--finance`） |
| 港股 | `tools/common/doubao_search.py`（`--sites hkexnews.hk`） | `tools/common/tavily_search.py` |
| 美股 | `tools/common/exa_search.py`（`--type deep`） | `tools/common/doubao_search.py` |

> **禁止使用 Anthropic 官方 WebSearch / WebFetch**（中国大陆不可用），统一用上述本地搜索工具。

### 6.4 计算与审核约束

- **禁止 LLM 心算**：市值、ROIC、WACC、PEG、Rule of 40、EV/Sales、DCF、ATR、止损价、仓位占比等一切算术必须经 `financial_rigor.py` / `momentum.py` 或对应工具执行；
- **报告准出**：发布前运行 `tools/common/report_audit.py`；
- **数据交叉验证**：关键财务数据须至少两个独立来源，误差 >1% 须标记。

---

## 七、全局约束

本档全部研究活动遵守以下 **7 条通用约束 + 2 条 GARP 特有约束**：

| # | 约束 | 说明 |
| --- | --- | --- |
| 1 | **日期确认** | 开始研究前运行 `date` 确认当天日期，以此作为「最新数据」基准，并在报告头部注明数据截止日期；**不得依赖训练数据中的日期假设**。 |
| 2 | **数据交叉验证** | 关键财务数据（营收 / 净利 / 毛利 / 现金流 / 研发投入）须至少来自两个独立来源，误差 >1% 须标记。 |
| 3 | **禁止心算** | 市值、ROIC、WACC、PEG、Rule of 40、EV/Sales、PSG、DCF、ATR(14)、止损价、仓位占比等**一切算术**必须经 `tools/common/financial_rigor.py`、`tools/common/momentum.py`、`tools/common/terminal_value.py` 或对应工具执行，禁止 LLM 心算。 |
| 4 | **报告审核** | 报告发布前运行 `python tools/common/report_audit.py ...`。 |
| 5 | **不确定性标注** | 低置信度结论、不完整数据及来源缺口须显式标注。 |
| 6 | **免责声明** | 本项目用于学习与研究，不构成投资建议。 |
| G1 | **框架只读** | 《中长期价值成长（GARP）投资框架.md》为口径权威源（0.3 三维交叉矩阵、渗透率黄金窗 15%~40%、国产化率四梯队、五大支柱、多工具估值矩阵、ESG 折价、7+7+6 分制等），本文档与各 `garp-*` 技能**只引用、不重建、不改写**。 |
| G2 | **转接段纪律** | 复用技能（`qoq-accelerator` / `trend-momentum-scan`）属 **1-3 年中期链**，其判定逻辑、`--horizon` 参数与核心口令**不得改动、不得覆盖**；GARP 链仅经其「出口转接段」接收结论（详见两技能 `SKILL.md` / `README.md` 的「出口转接：GARP 独立档（1~5 年）适配」节）。 |
| 7 | **东财闸门自检** | 并行启动多个子代理前先跑 `python tools/common/em_gate.py status`，读 `data.allowed` / `data.circuit`；`allowed=false` 或 `circuit=open` 时改串行或延后盘后。**注意**：此项为**数据面并发闸门**，与第 0 步「地缘政策前置」无关（方案 §3.3）。 |

---

## 八、多技能组合建议

以下 **9 组**为 GARP 链最常用组合。每组链路中出现的命令**必须**在本档 §一 全景表或 §1.1 复用表中存在，**不得出现虚构命令**。

### 组合 1：全链冷启动（从零研究一个新行业并建仓）

```text
/garp-geo-policy {行业名}                    ← 第 0 步强制闸门：地缘倒逼强度 + 政策覆盖度
        ↓
/garp-macro {市场}                           ← 宏观三表：调整后 PEG 区间 + 现金仓位下限
        ↓
/garp-industry-research {行业名}             ← 产业链全景 + 卡脖子环节 + Tier1~4
        ↓
/garp-industry-funnel {行业名}               ← 漏斗精选 → 3 家底仓 + 2 家机动仓
        ↓
/garp-trend-tech-screen {终选标的}           ← 五维加权打分 → S/A/B/C 评级 + 反证清单
        ↓
/garp-investment-checklist {公司名}          ← 能力圈四维 + 财务五门槛 + 五大支柱（V1~V4 一票否决）
        ↓
/garp-valuation {公司名}                     ← 多工具估值矩阵 + 宏观 PE 区间 + ESG 折价 → 分批建仓
        ↓
/garp-thesis-tracker {公司名}                ← 建立 GARP 论文（先写好五级卖出条件）
```

**适用场景**：首次进入一个新行业并系统化建仓，从第 0 步地缘政策闸门一路走到论文建档。

### 组合 2：时代主线快速识别

```text
/garp-era-alpha {行业/方向}                  ← 渗透率 15%~40% 黄金窗收敛闸门 + 五维景气验证
        ↓
/garp-industry-research {行业名}             ← 行业全景（确认 TAM ≥ 1000 亿元）
        ↓
/garp-trend-tech-screen {候选标的}           ← 景气五维加权排序
        ↓
/garp-investment-checklist {公司名}          ← 买入前硬门槛
```

**适用场景**：判断某方向是否属**时代级主线 / 范式转移**，并快速验证其中核心 α 的可建仓性。

### 组合 3：供应链卡脖子环节挖掘

```text
/garp-bottleneck-hunter {趋势名}             ← 咽喉位置第二/三层机会 + 国产化率四梯队
        ↓
/garp-industry-funnel {行业名}               ← 漏斗精选（能力圈四维 → 6 硬指标 → 五大支柱）
        ↓
/garp-investment-research {公司名}           ← 单 Agent 五大师深度研究
```

**适用场景**：从 AI 算力、能源转型等超级趋势中，挖掘未被充分定价的供应链隐性机会。

### 组合 4：个股深度验证（单一重仓标的）

```text
/garp-investment-checklist {公司名}          ← 硬门槛先行（V1~V4 任一否决即出池）
        ↓ (通过)
/garp-investment-team {公司名}               ← 五角色并行分析 + Team Lead 综合研判
        ↓
/garp-management {公司名}                    ← 诚信前置否决闸门 + 管理层/科研转化两套 20 分制
        ↓
/garp-valuation {公司名}                     ← 按公司类型选主锚的估值矩阵 → 统一六档结论
```

**适用场景**：单一重仓标的建仓前的完整验证，尤其是**高研发投入型 / 未盈利科技型**公司。

### 组合 5：建仓后首季体检

```text
/garp-thesis-tracker {公司名}                ← 季度体检（论文健康度评分 + 底仓/机动仓相对动作）
        ↓
/garp-earnings-review {公司名} {期间}        ← 财报精读（轻量版），验证景气逻辑
        ↓
/garp-earnings-team {公司名} {期间}          ← 关键/重要财报走团队深度版（+ 公众号发布）
        ↓
/qoq-accelerator {公司名}                    ← 连续 3 季增速二阶导（中期链复用·出口转接）
        ↓
/garp-thesis-drift {标的}                    ← H1~H7 七维假设逐条验证 → 四级漂移等级
```

**适用场景**：建仓后第一个财报季，回答「论文还成立吗」；日常财报用 `garp-earnings-review`，关键财报用 `garp-earnings-team`。

### 组合 6：股价异动应急归因

```text
/garp-news-pulse {公司名}                    ← 股价异动快速归因 + 五级卖出触发初筛
        ↓ (命中五级卖出)
/garp-exit {标的}                            ← 五级优先级硬编码检查，命中即停
        ↓ (未触发卖出)
/garp-thesis-drift {标的}                    ← H1~H7 逻辑漂移复核
```

**适用场景**：持仓股单日 ±5% 或一周 ±10% 异动，**先做卖出纪律检查，再归因**。

### 组合 7：组合层面审视

```text
/garp-portfolio-review {持仓清单}            ← 底仓/机动仓分离 + 单只/行业上限 + 五级卖出联动
        ↓
/trend-momentum-scan {持仓代码}              ← MA200 破位 / ATR(14)（中期链复用·出口转接）
        ↓
/garp-exit {标的}                            ← 逐只走五级优先级检查
```

**适用场景**：季度组合再平衡，校验「底仓 60%~80% / 机动仓 20%~40%」结构与集中度上限。

### 组合 8：估值与宏观校准

```text
/garp-macro {市场}                           ← 美林四档查表 → 调整后 PEG 区间 + 现金仓位下限
        ↓
/garp-valuation {公司名}                     ← 多工具估值矩阵 + 宏观 PE 区间 + ESG 折价
        ↓
/qoq-accelerator {公司名}                    ← 增速二阶导（提供估值修正输入·出口转接）
```

**适用场景**：宏观档位切换（利率周期 / 经济周期变化）时的估值重估与仓位调档。

### 组合 9：未上市公司预研

```text
/garp-private-company-research {公司名}      ← 6 路 Agent 并行拼凑分散信息 + 上市后适配性预判
        ↓ (公司上市后)
/garp-industry-research {行业名}             ← 从头进入第 0 步重新判定
```

**适用场景**：Pre-IPO 标的的「上市后 GARP 适配性预判」；**公司上市后须从头进入第 0 步重新判定，预判结论不产生任何买入动作**。

---

## 附录：GARP 技能速查决策树

```text
你的 GARP 投研诉求是什么？
│
├── 未上市公司（Pre-IPO）适配性预判 → /garp-private-company-research
│
├── 地缘与政策是否支持这个赛道 → /garp-geo-policy
│
├── 宏观环境适合几成仓 → /garp-macro
│
├── 锁定时代级主线与核心 α → /garp-era-alpha
│
├── 选赛道（1~5 年价值成长能否兑现？）
│   ├── 首次研究赛道 → /garp-industry-research
│   └── 供应链第二/三层卡脖子机会 → /garp-bottleneck-hunter
│
├── 赛道内精选出 3+2 组合（底仓 3 + 机动仓 2）→ /garp-industry-funnel
│
├── 在赛道内排序领涨标的 → /garp-trend-tech-screen
│
├── 验证候选公司
│   ├── 买入前检查（硬门槛）→ /garp-investment-checklist
│   ├── 快速报告 → /garp-investment-research
│   ├── 系统化团队研判 → /garp-investment-team
│   └── 管理层与科研转化深挖 → /garp-management
│
├── 判断估值 / 建仓区间 → /garp-valuation（+ /qoq-accelerator 修正）
│
├── 检查持仓
│   ├── 建立 / 检查 GARP 论文 → /garp-thesis-tracker
│   ├── 财报精读 → /garp-earnings-review（轻量版）或 /garp-earnings-team（深度版）
│   ├── 逻辑是否漂移（H1~H7）→ /garp-thesis-drift
│   ├── 股价异动快速归因 → /garp-news-pulse
│   ├── 趋势是否走坏（技术面）→ /trend-momentum-scan
│   └── 审视 GARP 组合（底仓 / 机动仓）→ /garp-portfolio-review
│
├── 判断该不该卖 → /garp-exit
│
└── 输出内容
    ├── 深度长文系列 → /garp-deep-company-series
    └── 微信公众号文章 → /garp-wechat-article
```

---

**版本信息**：v1.0.0 | **创建日期**：2026-09-19 | **最后更新**：2026-09-19（P5-4 首次交付：22 个 `garp-*` 技能 + 2 个复用中期技能全景图；第 0 步地缘政策前置强制闸门 + 六阶段闭环工作流程；五级卖出决策优先级金字塔；底仓/机动仓分离与仓位上限；三档并存路由规则；GARP 工具依赖；8 条全局约束；9 组多技能组合；速查决策树） | **维护状态**：活跃维护

**免责声明**：本文档仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。
