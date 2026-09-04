# mid-bottleneck-hunter 开发方案与详细实施计划（1~3 年景气投资版）

> **任务来源**：用户要求以 `research/early-version/bottleneck-hunter技能文件（草稿）.md` 为底稿，参考 `.trae/skills/bottleneck-hunter/SKILL.md` 的格式与范式，按照 `research/个人投资者1~3年中长期投资思想与理念 V2.0.md`，撰写适合 1~3 年投资的 `mid-bottleneck-hunter` 技能文件，并同步更新、修改其他软件与文档。
>
> **本文件性质**：开发方案与计划（Phase 0 产出物）。**待用户确认后方可进入开发执行。**
>
> **数据截止日期**：2026-09-03 | **免责声明**：仅供学习研究参考，不构成投资建议。

---

## 一、背景与目标

### 1.1 现状

- `.trae/skills/bottleneck-hunter/SKILL.md` 是**长期价值投资链（10 年）**技能：从超级趋势的物理供应链"咽喉位置"挖掘第二、第三层投资机会，估值以 PS/PE + "10 年后 25x PE 退出"为口径，无景气度、PEG、地缘六维、仓位/止损纪律。
- `research/early-version/bottleneck-hunter技能文件（草稿）.md` 已尝试把该技能改造成 1~3 年景气版（命名为 mid-bottleneck-hunter），并附有一份"兼容性诊断表"与 17 项修改方向。
- `research/个人投资者1~3年中长期投资思想与理念 V2.0.md` 是 1~3 年投资框架的唯一权威依据（四位大师：欧奈尔/林奇/郑希/李进；渗透率/ROE 趋势/二阶导/PEG 估值/地缘六维/底仓机动仓/P0~P5 决策金字塔/四大矛盾化解）。

### 1.2 目标

1. 新建 `.trae/skills/mid-bottleneck-hunter/`（SKILL.md + README.md），成为中期链（1-3 年）的"供应链瓶颈机会发现"入口技能，与长期链 `bottleneck-hunter` **双轨并存、物理隔离**。
2. 全项目文档引用同步更新，确保路由与口径一致。
3. 遵守中期术语红线（禁止"护城河永续/终局思维/持有10年"等长期框架术语）。

---

## 二、底稿诊断：草稿的优点与待修正项

### 2.1 草稿优点（保留）

| 维度 | 内容 |
| --- | --- |
| 兼容性诊断 | "bottleneck-hunter 与 1~3 年景气框架匹配度"表格分析准确，核心架构（供应链物理拆解→瓶颈识别→公司筛选→交叉验证）天然兼容 |
| 景气度叠加 | 第三步新增"瓶颈景气度叠加判断"（渗透率位置/ROE 趋势/二阶导/订单能见度），符合 V2.0 郑希/李进维度 |
| 地缘政治六维 | 第四步深度筛选加入海外收入/供应链/制裁/本地化对冲/自主研发（"华为式"）评估，符合 V2.0 支柱四 |
| PEG 五档 | 引入林奇 PEG 估值作为核心估值工具，方向正确 |
| 卖出/风控 | 增加卖出触发条件提示、一页纸备忘卡、四位大师速查卡，方向正确 |

### 2.2 草稿待修正项（本方案必须解决）

| # | 问题 | 现状（草稿） | 修正方向（对齐现有中期体系） |
| --- | --- | --- | --- |
| 1 | **格式不符现有 mid-* 技能规范** | 无 frontmatter；无调用参数表；无设计原则；无风控硬编码；大量 ` ``` ` 代码块包裹导致版面脏乱 | 按 `mid-industry-funnel/SKILL.md` 的格式与范式重写（frontmatter + 设计原则 + 调用参数 + 硬编码规则 + 风控编号 + 版本信息） |
| 2 | **未拆分 SKILL.md / README.md** | 草稿为单文件 | 拆为 SKILL.md（详细指令）+ README.md（速览）双文件 |
| 3 | **卖出触发口径与 `exit-signal` 不一致** | 正文写 P0~P5（P5=持有满4季度）；对照表却写 P0~P6（含 P6 技术止损），**自相矛盾** | 统一对齐 `exit-signal` 的 **P0~P5**（时间止损已并入 P2，不设独立层级）；卖出优先级一律引用 `exit-signal`，本技能不重建 |
| 4 | **PEG 档位自建口径** | 草稿自建五档表 | 引用 `valuation-thermometer` 五档（`<0.8 显著低估 / 0.8~1.2 合理 / 1.2~1.5 偏贵 / 1.5~2.0 高估 / >2.0 严重透支`）为唯一权威口径 |
| 5 | **买入前检查技能名错误** | 草稿写 `/investment-checklist（景气版）` | 改为 `/mid-investment-checklist`（七关硬门槛），并明确联动关系 |
| 6 | **估值安全边际仍用 10 年口径** | 草稿"估值合理性检验"仍为"10 年后 25x PE 退出年化回报"（长期框架） | 改为 V2.0 中期口径：**远期 PE + 渗透率**（"3 年后预计利润 × 合理 PE"折现至当前，隐含回报 >25% 可建仓、<15% 等待更好价格）；同时保留 PEG 红灯底线 |
| 7 | **报告输出路径与长期技能共用** | `reports/bottleneck-map/{趋势名}/` 与长期版共用 | **物理隔离**：改为 `reports/mid-bottleneck/{趋势名}/`（参照 `portfolio-review --horizon mid` → `reports/portfolio-mid-*.md` 的隔离惯例；用户已确认） |
| 8 | **对照表声称有但正文未展开** | 对照表列出"左侧布局 vs 右侧重仓""底仓/机动仓分离""四大矛盾化解""季度复盘清单"，但正文未完整呈现 | 正文完整落地这些章节，且与 V2.0 第三/四/五部分一致 |
| 9 | **风控纪律无编号体系** | 无 | 设计 **BN-1~BN-10** 风控硬编码编号（避免与 `mid-industry-funnel` 的 F- 系列冲突） |
| 10 | **术语残留** | 需全篇核查 | 中期术语红线：禁用"护城河永续""终局思维""持有10年"等；`/mid-investment-checklist` 为七关（非长期六关） |

---

## 三、mid-bottleneck-hunter SKILL.md 内容设计

### 3.1 文件与元信息

| 项 | 内容 |
| --- | --- |
| 路径 | `.trae/skills/mid-bottleneck-hunter/SKILL.md` |
| name | `mid-bottleneck-hunter` |
| disable-model-invocation | `true` |
| 版本 | 1.0.0（创建日期 2026-09-03） |
| 定位 | 中期链（1-3 年）供应链瓶颈机会发现入口；与长期 `bottleneck-hunter` 物理隔离、功能互补 |

### 3.2 章节结构（对齐现有 mid-* 技能范式）

```
frontmatter（name/description/disable-model-invocation）
# 供应链瓶颈猎手（中期版）：AI 驱动的全球产业链瓶颈套利（1~3 年景气投资版）
├── 设计原则（7~8 条）
├── 调用参数（{趋势名} 位置参数 + --scope/--depth/--export/--json，不新增命令行开关）
├── 能力圈声明（适用/不适用场景）
├── 核心判定规则（硬编码）
│   ├── 规则一：超级趋势确认（1.1 四标准 + 1.2 清单 + 1.3 输出）
│   ├── 规则二：供应链物理拆解（Layer 0~4 + AI 基础设施/创新药模板 + 景气指标）
│   ├── 规则三：瓶颈识别（6 条标准 → S/A/B 评级）＋ 景气度叠加判断（渗透率/ROE/二阶导/订单）
│   ├── 规则四：公司筛选（初筛 + 业绩兑现 + 地缘六维 + 深度筛选模板）
│   ├── 规则五：估值检查（PEG 五档引用 valuation-thermometer + PS/PE 红灯/黄灯/绿灯 + 3 年隐含回报）
│   ├── 规则六：交叉验证（正向六维 + 芒格式反向 + 景气验证）
│   └── 规则七：输出（排名表 + 一页纸摘要 + 行动建议 + 卖出触发提示）
├── 风控硬编码 BN-1~BN-10（编号速查表）
├── 仓位与买卖纪律（底仓/机动仓、左侧/右侧、分批建仓 1/3→1/3→1/3、P0~P5 决策优先级引用 exit-signal）
├── 四大矛盾化解（买点/持有时间/止损 vs 越跌越买/分散 vs 集中，引用 V2.0 第五部分）
├── 存量更新（增量更新 + 状态文件 + 季度复盘清单）
├── 工具依赖（本地数据/精确计算/网络搜索，禁止 WebSearch/WebFetch）
├── 报告输出规范（reports/mid-bottleneck/{趋势名}/）
├── AI 研究偏见自觉（含"景气线性外推"新增偏见）
├── 核心原则（对齐原版 11 条 + 中期新增 2~3 条）
├── 注意事项
├── 局限性说明
├── 与其他 Skill 的关系（mid-industry-research / mid-industry-funnel / mid-trend-tech-screen / mid-investment-checklist / mid-management-deep-dive / valuation-thermometer / exit-signal）
├── 附录 A：四位大师速查卡 / 附录 B：一页纸备忘卡 / 附录 C：与原版差异对照表
└── 版本信息 + 免责声明
```

### 3.3 关键口径对齐（与现有中期体系 10 处）

| 项 | 对齐方式 |
| --- | --- |
| 渗透率坐标 | 统一到 V2.0：10%~30% 黄金区重仓、>50% 兑现、<5% 过早不参与 |
| ROE/二阶导 | 连续 3 季同向为准（对齐理念文档矛盾二），不靠单季 |
| PEG 估值档位 | 引用 `valuation-thermometer` 五档，不重复定义 |
| 卖出优先级 | 引用 `exit-signal` P0~P5（时间止损并入 P2），不自建 P 级 |
| 买入前检查 | 引用 `/mid-investment-checklist` 七关，本技能只出"观察名单" |
| 仓位规则 | 底仓 60%~80%、机动仓 20%~40%；单只 ≤10%/15%/20%；单行业 ≤40%；持股 5~10 只 |
| 风控编号 | 采用 **BN-1~BN-10**（避免与 F-/R-/MC- 冲突） |
| 报告路径 | `reports/mid-bottleneck/{趋势名}/`（与长期物理隔离） |
| 估值安全边际 | 3 年隐含回报（远期 PE + 渗透率），非 10 年 25x PE |
| 术语红线 | 剔除残留长期"护城河永续/终局思维/持有10年"表述 |

---

## 四、README.md 设计

`.trae/skills/mid-bottleneck-hunter/README.md`，结构对齐 `bottleneck-hunter/README.md` 与 `mid-industry-funnel/README.md`：

- 快速开始（`/mid-bottleneck-hunter {趋势名}` + 参数表）
- 核心功能（七步流程速览 + 与长期版差异一句话）
- 使用示例（AI 基础设施 / 创新药 各 1 例）
- 输出报告（`reports/mid-bottleneck/{趋势名}/` 目录结构与命名规则）
- 研究标准（瓶颈判定 6 条 + PEG 五档 + 景气度 + 地缘六维速览）
- 工具依赖 / 核心原则 / 注意事项 / 局限性 / 相关文档 / 版本信息 / 免责声明

---

## 五、全项目文档引用更新清单

以下为 `bottleneck-hunter` 相关引用的全量扫描结果（73 处命中，实际需改动约 8 处）与处理决策：

| # | 文件 | 现状 | 处理 |
| --- | --- | --- | --- |
| 1 | `CLAUDE.md` | L15 `reports/` 说明含 `bottleneck-map/`；L40 技能表 `bottleneck-hunter`（行业研究类） | ①技能表"中期投研类"新增 `/mid-bottleneck-hunter` 一行；②路由规则中期链补充该技能；③`reports/` 说明补充 `mid-bottleneck/` |
| 2 | `.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md` | L63/L75/L343 在中期链中使用 `/bottleneck-hunter` | 改为 `/mid-bottleneck-hunter`，并在六阶段闭环图与决策树中标注"中期版" |
| 3 | `research/1~3 年中长期投研系统完整开发方案与详细实施计划.md` | L144 行业研究列表含 `bottleneck-hunter`（长期类，保留）；L412 阶段一使用 `/bottleneck-hunter`（中期链） | L412 改为 `/mid-bottleneck-hunter`；L144 为长期技能清单，**不动**；补一节说明 mid-bottleneck-hunter 已落地 |
| 4 | `research/Sprint 5 开发方案与详细实施计划.md` | L105 中期六阶段闭环图中 `bottleneck-hunter` | 改为 `/mid-bottleneck-hunter` |
| 5 | `docs/dev_docs/搜索服务选择策略重构方案.md` | 有 `bottleneck` 引用（4 处命中） | 逐条核查：属于长期版搜索选型则保留；属于中期链则补 mid 版选型说明 |
| 6 | `docs/dev_docs/A股财报下载与提取统一缓存方案.md` | L168 工具引用列表中含 `bottleneck-hunter`（该处为"引用处统一替换"清单） | 追加 `mid-bottleneck-hunter` 一行（若该清单需同步则改，否则注释说明） |
| 7 | `research/early-version/bottleneck-hunter技能文件（草稿）.md` | 底稿 | **保留不动**（存档底稿）；新技能正文落在 `.trae/skills/mid-bottleneck-hunter/` |
| 8 | `.trae/skills/bottleneck-hunter/SKILL.md`、`README.md` | 长期版技能 | **不动**（双轨并存，物理隔离） |
| 9 | `.trae/skills/证券AI价值投资研究工作步骤.md` | L29/L89/L217/L223/L375/L519 等长期链引用 `/bottleneck-hunter` | **不动**（长期链继续使用长期版） |
| 10 | `.trae/skills/mid-industry-research/SKILL.md`、`README.md` | 可能与 bottleneck-hunter 有联动引用 | 逐条核查；若引用长期版则补 mid 版联动，若为互补关系则不动 |

> 原则：**长期链文档保留长期版 `bottleneck-hunter`；中期链文档改为 `mid-bottleneck-hunter`；两版物理隔离、互不覆盖。**

---

## 六、实施步骤（待确认后执行）

```
Phase 0（本文档）        → 方案确认（用户批准）
Phase 1：SKILL.md 撰写   → .trae/skills/mid-bottleneck-hunter/SKILL.md
Phase 2：README.md 撰写  → .trae/skills/mid-bottleneck-hunter/README.md
Phase 3：文档引用更新     → 第五节清单 1/2/3/4/5/6/10 逐文件修改
Phase 4：一致性验证       → 引用完整性与口径核对（见第七节验收标准）
```

### 各阶段关键动作

- **Phase 1**：以草稿为内容底稿，以 `mid-industry-funnel/SKILL.md` 为格式范式，按第三节大纲重写；PEG/卖出/仓位/决策金字塔一律引用现有权威技能，不重建口径。
- **Phase 2**：以 `bottleneck-hunter/README.md` 为模板改写，突出与长期版的差异。
- **Phase 3**：按第五节清单逐文件修改；改前 `git pull --rebase`，改后核查无残留 `/bottleneck-hunter` 出现在中期链上下文。
- **Phase 4**：Grep 全项目核查；逐项对照验收标准。

---

## 七、验收标准（DoD）

1. `.trae/skills/mid-bottleneck-hunter/` 下存在 SKILL.md + README.md，frontmatter `name: mid-bottleneck-hunter`。
2. 七步执行流程完整，且每一步均融入 1~3 年景气框架（渗透率/ROE/二阶导/PEG/地缘六维）。
3. PEG 档位、卖出优先级、决策金字塔、仓位规则与 `valuation-thermometer`、`exit-signal`、V2.0 完全一致，无自建冲突口径。
4. 报告中不出现"护城河永续/终局思维/持有10年/巴芒段李"等长期术语残留。
5. 报告输出路径为 `reports/mid-bottleneck/{趋势名}/`，与长期 `reports/bottleneck-map/` 物理隔离。
6. 第五节清单中 1/2/3/4/6/10 全部更新完毕；Grep 确认中期链上下文无残留 `/bottleneck-hunter`。
7. 长期链文档（`证券AI价值投资研究工作步骤.md`、`bottleneck-hunter/*`）未被误改。

---

## 八、需用户确认的决策点（已全部确认，2026-09-03）

| # | 决策点 | 默认方案 | 备选 | ✅ 用户确认结果 |
| --- | --- | --- | --- | --- |
| 1 | 报告输出目录命名 | `reports/bottleneck-map-mid/{趋势名}/` | `reports/mid-bottleneck/{趋势名}/` | **`reports/mid-bottleneck/{趋势名}/`**（选择备选） |
| 2 | 风控硬编码编号 | `BN-1~BN-10` | 沿用其他前缀（如 `MB-`） | **`BN-1~BN-10`**（按默认执行） |
| 3 | 是否保留原版"每小时扫描模式" | 保留（改为景气版，叠加 PEG/景气度/地缘检查） | 移除（1~3 年不频繁扫描） | **移除**，改为季度/月度增量更新（选择备选） |
| 4 | 估值安全边际口径 | 改为 3 年隐含回报（远期 PE + 渗透率） | 保留 10 年 25x PE（不推荐，违背 V2.0） | **3 年隐含回报**（按默认执行） |
| 5 | 草稿 17 项修改方向 | 全部吸收（其中 4/5/6/8/10/11/12/13/14/15/16/17 落地为正文章节；1/2/3/7/9 以引用对齐方式实现） | 按需裁剪 | **全部吸收**（按默认执行） |

> 注：决策点 2（风控编号 BN-1~BN-10）与决策点 5（草稿 17 项修改方向）用户未单独作答，按方案默认值执行；其余决策点均已确认。

---

## 九、范围与边界（不做的事）

- **不改动**长期版 `bottleneck-hunter/SKILL.md`、`README.md`、`证券AI价值投资研究工作步骤.md`（长期链继续使用）。
- **不新建**任何 Python 工具脚本（复用 `stock_financial.py`、`financial_rigor.py`、五工具搜索等现有工具）。
- **不创建**数据库/新软件，纯技能与文档工作。
- 草稿文件 `research/early-version/bottleneck-hunter技能文件（草稿）.md` 保留存档，不改写。

---

**版本信息**：v1.1.0 | **创建日期**：2026-09-03 | **确认日期**：2026-09-03 | **状态**：✅ 已获用户批准，Phase 1~4 全部完成（SKILL.md + README.md v1.0.0 已落地，全项目文档引用已同步，DoD 7 条验收通过）

**免责声明**：本方案仅用于学习与研究，不构成投资建议。
