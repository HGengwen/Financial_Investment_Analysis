# 未上市公司研究 (Private Company Research)

多Agent并行深度研究框架：6个Agent从商业模式、财务、竞争、风险、技术、替代数据多维度拼凑信息，还原未上市公司的真实价值

---

## 快速开始

### 基本调用方式

```
/private-company-research {公司名}
```

例如：
- `/private-company-research 蚂蚁集团`
- `/private-company-research 小红书`
- `/private-company-research SpaceX`
- `/private-company-research Stripe`

**支持输入格式**：未上市公司名称（中英文均可），如 `蚂蚁集团`、`ByteDance`、`SHEIN`

---

## 核心功能

对指定未上市公司进行团队化深度研究分析。6个Agent并行研究，Team Lead 综合交叉验证与信息拼图，产出系统化的未上市公司真实价值研究报告。

### 7人团队结构

| 角色 | 职责 | 核心视角 |
|------|------|----------|
| **team-lead**（你自己） | 统筹协调、信息拼图、交叉验证、输出最终报告 | 投资决策整合 |
| business-decoder | 商业模式拆解 & 产品用户分析 | "这门生意的本质是什么" |
| financial-detective | 财务数据拼凑 & 估值推演 | "在信息缺失下尽可能还原真实财务面貌" |
| competitive-mapper | 行业格局 & 竞争态势 & 替代威胁 | "谁在和它竞争，谁可能颠覆它" |
| risk-governance-analyst | 风险全景 & 管理层/治理/投资人评估 | "什么可能出错，谁在掌舵" |
| tech-ip-analyst | 技术栈/专利/研发能力/技术护城河 | "技术壁垒是真是假，能撑多久" |
| signal-miner | 替代数据挖掘：招聘/专利/诉讼/App数据/供应链 | "常规信息之外，还有什么蛛丝马迹" |

### AI研究偏见自觉（核心前提）

未上市公司是AI研究偏见最严重的领域，本框架内建4大偏见识别：

| 偏见类型 | 表现 | 应对 |
|---------|------|------|
| **虚假保守** | 因资料少给出保守/模糊结论，但资料少≠公司不好 | 切换"第一性原理模式"聚焦核心问题 |
| **虚假精确** | 用"合理推测"伪装成"有据分析"填满模板 | 每个数据点标注置信度（🟢高/🟡中/🔴低） |
| **对标陷阱** | 强行与上市公司对标，继承估值逻辑 | 独立判断，说明对标局限性 |
| **幸存者偏差** | 网上信息有正面偏向 | 主动搜索负面/争议信息 |

**反向利用信息不对称**：市场对未上市公司信息少→定价效率低→恰恰可能是超额收益的来源。

### 核心挑战

未上市公司 vs 上市公司研究的核心差异：
- **无标准化财报**：需多源拼凑、交叉验证
- **估值锚定少**：依赖融资轮次、可比公司法、情景推演
- **信息不对称大**：需要更多"拼图式"研究方法
- **退出路径不确定**：IPO/并购/二级转让均有可能

---

## 使用示例

### 示例1：研究国内金融科技独角兽
```
/private-company-research 蚂蚁集团
```
6个Agent并行从招股书、ABS发行文件、监管处罚、母公司年报关联披露等多源拼凑财务数据，交叉验证估值。

### 示例2：研究内容社交平台
```
/private-company-research 小红书
```
重点挖掘App Store排名、用户口碑、融资历史、招聘信号等替代数据，拼图还原真实经营面貌。

### 示例3：研究海外科技公司
```
/private-company-research SpaceX
```
中英文双语搜索，结合SEC Filing、Bloomberg、TechCrunch等来源，用 `doubao_search.py` + `tavily_search.py` 双源验证。

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 未上市公司研究报告 | `reports/{公司名}/{公司名}-private-{YYYYMMDD}.md` |

如果 `reports/{公司名}/` 目录不存在则创建。

### 报告结构（14节）

1. **一句话结论** — 50-100字概括真实价值判断
2. **公司画像速览** — 名称/成立时间/总部/创始人/核心业务/估值/融资轮次/推算收入利润用户/投资方/架构
3. **六维评分总表** — 6个维度评分(★1-5) + 核心判断 + 置信度 + 信息完整度 + 综合评分
4. **关键数据拼图** — 仅保留经过交叉验证的数据（指标/数据/来源数量/来源明细/置信度/备注）
5. **信号一致性矩阵** — 增长叙事vs招聘、技术叙事vs专利、估值vs竞争地位、管理层叙事vs行动
6. **各维度分析摘要** — 每个维度3-5条最重要发现（标注来源和置信度）
7. **真实价值评估** — 生意本质判断 + 护城河评分卡（7类） + 估值判断（5种方法） + 综合真实价值区间（保守/合理/乐观/当前/安全边际）
8. **投资论点（看多 vs 看空）** — 看多5-7条 + 看空5-7条 + 哪方更有说服力
9. **风险矩阵** — 风险/概率/影响/严重度/可对冲/监控指标 + Top 3核心风险应对
10. **退出路径评估** — 最可能退出方式、时间窗口、预期回报
11. **投资决策表** — 一页纸决策表 + 分层建议（PE/VC领投/跟投/二级/IPO后/不建议） + 关键催化剂
12. **信息盲区地图** — 已知/缺失/缺失影响/获取建议 + 对核心结论可靠性影响说明
13. **持续跟踪清单** — 跟踪事项/频率/来源/指标/预警阈值
14. **总结段落** — 150-250字最终总结

### 发布审核

报告保存后须运行审核流程：
```bash
python tools/common/report_audit.py extract --report reports/{公司名}/{公司名}-private-{YYYYMMDD}.md
python tools/common/report_audit.py verdict --results '<verified JSON>' --report reports/{公司名}/{公司名}-private-{YYYYMMDD}.md
```

---

## 执行流程

### 六阶段执行

1. **展示团队框架** — 确认7人团队结构后启动6个并行Agent
2. **启动6个并行Agent** — 同一条消息中调用6次 Task 工具（`subagent_type: general_purpose_task`），每个Agent按角色任务模板研究
3. **接收报告并跟踪进度** — 实时展示进度表，每收到一份报告展示核心要点（3-5条）
4. **交叉验证与信息拼图** — team-lead 执行数据冲突仲裁、信号一致性检验、信息拼图还原、反偏见检查
5. **汇总最终报告** — 综合6份报告输出14节结构的最终报告，找交叉和矛盾而非拼报告
6. **保存报告与审核** — 写入 `reports/{公司名}/{公司名}-private-{YYYYMMDD}.md`，运行 `report_audit.py` 准出流程

### 6个Agent核心任务

| Agent | 核心任务 | 核心问题 |
|-------|---------|---------|
| business-decoder | 商业模式与产品用户深度分析 | 这门生意的本质是什么？护城河宽窄？ |
| financial-detective | 财务数据拼凑与估值推演 | 在信息缺失下还原真实财务面貌，值多少钱？ |
| competitive-mapper | 行业格局与竞争态势分析 | 谁在和它竞争，谁可能颠覆它？ |
| risk-governance-analyst | 风险全景与治理评估 | 什么可能出错，谁在掌舵，怎么退出？ |
| tech-ip-analyst | 技术能力与知识产权分析 | 技术壁垒是真是假，能撑多久？ |
| signal-miner | 替代数据信号挖掘 | 常规信息之外，还有什么蛛丝马迹？ |

### Team Lead 汇总要点

不是拼报告，是找交叉和矛盾：
1. **数据冲突仲裁** — 不同Agent引用的相同数据是否一致，冲突时列出所有来源并仲裁
2. **信号一致性检验** — 业务增长vs招聘、技术叙事vs专利、估值vs竞争、管理层叙事vs行动
3. **信息拼图还原** — 拼合信息碎片，标注"白区"（已知）、"灰区"（有线索）、"黑区"（未知）
4. **反偏见检查** — 检查"正面详细、负面简略"偏差，确认每个正面判断有反面检验

---

## 工具依赖

### 网络搜索工具

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。完整角色定位、市场×场景选型矩阵、命令速查、多源验证示例见 [web-search-tools](../tools-scripts/web-search-tools.md)。

**未上市公司研究场景下的搜索选型**：
- 国内未上市公司信息：`doubao --finance` 主（权威信源 + `--need-content` 抓正文）+ `anysearch` 辅（通用搜索）
- A股对标公司：`anysearch --tag finance` 主（财报/研报/公告深查）+ `doubao --finance` 辅；双源 anysearch+doubao
- 港股对标公司：`doubao --sites hkexnews.hk` 主 + `tavily` 辅（管理层讨论）；双源 doubao+tavily
- 美股对标公司：`exa --type deep` 主（SEC filings 深度检索）+ `doubao` 辅（新闻/舆情）；双源 exa+doubao
- 深度研究报告：`exa_search.py --type deep`

**搜索规范**（未上市公司研究特有）：
- 使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 使用 `--need-content` 抓取公告正文做精确解读
- 使用 `--sites sec.gov` 或 `--sites hkexnews.hk` 定向检索 SEC/港交所披露
- A股/港股/美股对标公司须按市场矩阵双源验证（A股 anysearch+doubao；港股 doubao+tavily；美股 exa+doubao）
- 每个搜索关键词至少用3-5种不同组合，中英文各搜索一次
- 关键信息缺失时标注"信息不足"，不得用推测填充

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、估值、市值校验、三情景） | `python tools/common/financial_rigor.py verify-valuation --pe 15 --eps 5` |
| `tools/common/report_audit.py` | 报告数据抽检与审核（准出流程） | `python tools/common/report_audit.py extract --report reports/xxx.md` |

### 汇率工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/fx_rate.py` | 国际货币汇率（跨币种估值折算） | `python tools/common/fx_rate.py --code USDCNY` |

**汇率使用规范**：跨币种估值对比时，先用 `fx_rate.py` 获取实时汇率，禁用固定汇率。美元→人民币用 `USDCNY`，港币→人民币用 `HKDCNY`。

### 辅助数据工具（可比上市公司对标）

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_financial.py` | 财务指标（对标同业） | `python tools/a_share/stock_financial.py --code 600941` |
| 港股 | `tools/hk_stock/stock_financial.py` | 港股财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| 美股 | `tools/us_stock/stock_financial.py` | 美股财务指标 | `python tools/us_stock/stock_financial.py --code AAPL` |

**Python路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

详细使用说明请参考：
- **网络搜索工具**：[web-search-tools](../tools-scripts/web-search-tools.md)
- **财务计算与验证**：[financial-calc](../tools-scripts/financial-calc.md)
- **报告审核与抽检**：[report-audit](../tools-scripts/report-audit.md)
- **全局约束规范**：[global-constraints](../tools-scripts/global-constraints.md)
- **A股工具**：[docs/A股工具使用指南.md](../../docs/A股工具使用指南.md)
- **港股工具**：[docs/港股工具使用指南.md](../../docs/港股工具使用指南.md)
- **美股工具**：[docs/美股工具使用指南.md](../../docs/美股工具使用指南.md)
- **国际货币汇率**：`tools/common/fx_rate.py`，详见 [A股工具使用指南汇率章节](../../docs/A股工具使用指南.md)

---

## 核心原则

1. **6个Agent必须并行启动** — 在同一条消息中调用6次 Task 工具，不可串行
2. **数据置信度标注** — 每个关键数据标注来源和置信度（🟢高/🟡中/🔴低），让读者自己判断
3. **推算要透明** — 所有推算过程展示计算逻辑和每一步假设，不能凭空给数字
4. **交叉验证** — 关键数据至少2个来源交叉验证，来源冲突时全部列出
5. **信号一致性检验** — 汇总阶段必须做跨维度的信号一致性检查
6. **诚实留白** — 宁可留白说"不知道"，也不用推测填满表格伪装确定性；信息不足时直接说"信息不足，无法给出可靠估值"
7. **反偏见核心原则** — 资料少≠公司不好，AI分析篇幅短≠投资确定性低；信息极度稀缺时切换"第一性原理模式"
8. **替代数据不是噪音** — 招聘、专利、诉讼、App数据等替代数据可能比新闻报道更接近真实经营状况
9. **真实价值导向** — 最终目标是判断生意值多少钱，不是输出一份好看的报告
10. **中英文搜索** — 未上市公司信息可能分布在中英文媒体，需要两种语言搜索

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用），所有网络信息必须使用本地搜索工具
- 6个Agent必须在同一条消息中并行启动，不可串行
- 所有数据必须标注来源，关键财务数据至少两个来源交叉验证
- 估值估算须使用 `tools/common/financial_rigor.py` 精确计算，不得 LLM 心算
- 跨币种估值折算须用 `tools/common/fx_rate.py` 获取实时汇率，禁用固定汇率
- 报告保存后须运行 `tools/common/report_audit.py` 审核流程，未通过审核的是草稿
- 研究前运行 `date` 确认当天日期，在报告头部注明数据截止日期
- 信息稀缺时宁可留白标注"数据不足"，不用推测填满框架伪装确定性
- 不构成投资建议，仅供学习研究参考

---

## 局限性说明

- **数据可得性**：未上市公司无标准化财报，部分数据需多源拼凑，可能不完整或相互矛盾
- **估值主观性**：多方法估值存在主观判断，不同方法可能得出不同结论
- **替代数据局限**：招聘、App数据等替代数据可能有时效延迟，不代表实时经营状况
- **信息偏差**：网上能搜到的公司信息往往有正面偏向（公司主动传播的多是好消息）
- **非实时数据**：工具获取的数据可能有延迟，不是实时数据
- **AI解读局限**：AI无法完全替代专业投资分析师对未上市公司的深度判断能力
- **退出路径不确定**：IPO/并购/二级转让均有可能，退出时间和回报存在较大不确定性
- **并行执行复杂度**：6个Agent并行执行可能需要较长时间
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [投资研究](../investment-research/README.md) — 四大师综合分析框架（上市公司）
- [投研团队](../investment-team/README.md) — 四Agent并行公司研究（上市公司）
- [投资检查清单](../investment-checklist/README.md) — 巴菲特六关 Checklist
- [论文跟踪](../thesis-tracker/README.md) — 投资论文追踪与季度检查
- [网络搜索工具](../tools-scripts/web-search-tools.md) — 本地搜索工具选用规范
- [财务计算工具](../tools-scripts/financial-calc.md) — financial_rigor.py 使用指南
- [报告审核工具](../tools-scripts/report-audit.md) — report_audit.py 准出流程

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-08-07
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。未上市公司投资风险更高，流动性差，信息不对称大，投资有风险，入市需谨慎。
