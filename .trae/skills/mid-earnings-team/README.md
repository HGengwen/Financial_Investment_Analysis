# 财报精读团队（1~3年景气投资版）(Mid Earnings Team)

林奇-郑希-欧奈尔-李进四大师并行解读财报 + 编辑润色 + 读者评审，产出可直接发布的公众号文章

> 本技能属**中期链（1-3 年）**，与长期版 [earnings-team](../earnings-team/README.md)（10 年 / 段永平-巴菲特-芒格-李录）**物理隔离、功能互补**。核心是「用每季度财报验证景气逻辑、更新卖出纪律」。

---

## 快速开始

### 基本调用方式

```
/mid-earnings-team {公司名} {期间}
```

支持输入格式：
- `{公司名} {季度}` — 例如：`腾讯 2025Q4`、`快手 2025Q3`
- `{公司名} {年报}` — 例如：`宁德时代 2025年报`、`中际旭创 2024年报`
- `{公司名} 最新` — 默认读取最近一期，例如：`新易盛 最新`

例如：
- `/mid-earnings-team 新易盛 2025Q2`
- `/mid-earnings-team 中际旭创 2024年报`
- `/mid-earnings-team 腾讯 最新`

---

## 核心功能

对指定公司进行团队化财报精读分析。四位景气大师并行解读财报，编辑润色成文，读者评审把关质量，最终产出可直接发布的公众号文章。

### 三阶段六Agent流程

**阶段一·研究**：四大师并行精读财报
- 🔍 林奇 · 生意与估值解读者 — 六类分类有变化吗？PEG 更新了没有？
- ⚡ 郑希 · ROE 与景气验证师 — ROE 拐点到了吗？二阶导是正是负？渗透率到哪了？
- 🛡️ 欧奈尔 · 风控底线审计师 — 趋势信号如何？止损位要不要更新？
- ⚖️ 李进 · 组合管理与治理评估师 — 管理层诚信变化？科研转化进展？仓位怎么调？

**阶段二·合成**：Team Lead 综合四个视角，产出研究报告初稿，**重点回答「景气逻辑是否成立、卖出纪律是否触发」**

**阶段三·发布**：
- ✍️ 编辑 Agent — 改写为公众号文章
- 👀 读者评审 Agent — 提出修改意见
- 📝 Team Lead — 定稿

### 设计理念

一份好的景气投资财报分析要解决两个问题：
1. **自己敢不敢拿着** — 需要四个不同视角深度验证「景气逻辑是否持续、卖出纪律是否触发」
2. **读者能不能看懂** — 需要编辑润色和读者视角的质量把关

---

## 使用示例

### 示例1：精读A股一季度财报并产出公众号文章
```
/mid-earnings-team 新易盛 2025Q1
```
 四大师并行精读新易盛2025Q1财报，重点验证光模块景气逻辑与订单兑现，输出可直接发布的公众号文章+研究底稿

### 示例2：精读A股年报并产出公众号文章
```
/mid-earnings-team 中际旭创 2024年报
```
 使用 `stock_equity.py` 下载年报PDF，启动六Agent流程

### 示例3：精读港股季度财报
```
/mid-earnings-team 腾讯 2025Q4
```
 聚焦 ROE 趋势与 AI 渗透率，验证景气逻辑并更新卖出纪律

### 示例4：快速精读最新一期财报
```
/mid-earnings-team 美团 最新
```
 自动读取最近一期财报，执行完整团队化精读

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 公众号定稿 | `reports/{公司名}/{公司名}-mid-earnings-{期间}.md` |
| 研究底稿 | `reports/{公司名}/{公司名}-mid-earnings-{期间}-研究底稿.md` |
| 林奇视角 | `reports/{公司名}/{公司名}-mid-earnings-{期间}-林奇.md` |
| 郑希视角 | `reports/{公司名}/{公司名}-mid-earnings-{期间}-郑希.md` |
| 欧奈尔视角 | `reports/{公司名}/{公司名}-mid-earnings-{期间}-欧奈尔.md` |
| 李进视角 | `reports/{公司名}/{公司名}-mid-earnings-{期间}-李进.md` |
| 读者评审 | `reports/{公司名}/{公司名}-mid-earnings-{期间}-读者评审.md` |

### 输出文件结构

```
reports/{公司名}/
├── {公司名}-mid-earnings-{期间}.md           ← 最终公众号文章（定稿）
├── {公司名}-mid-earnings-{期间}-研究底稿.md   ← 四大师合成研究报告（自用）
├── {公司名}-mid-earnings-{期间}-林奇.md       ← 生意与估值解读
├── {公司名}-mid-earnings-{期间}-郑希.md       ← ROE与景气验证
├── {公司名}-mid-earnings-{期间}-欧奈尔.md     ← 风控底线审计
├── {公司名}-mid-earnings-{期间}-李进.md       ← 组合管理与治理评估
└── {公司名}-mid-earnings-{期间}-读者评审.md   ← 读者评审报告
```

---

## 质量标准

### Team Lead 的合成价值：找交叉和矛盾

不是拼报告，是找交叉和矛盾：
1. **四个视角的共识点** — 四位大师都同意的结论，可信度最高
2. **四个视角的矛盾点** — 比如林奇说 PEG 合理，但郑希说 ROE 已拐头——这种矛盾才是最有价值的分析
3. **被忽略的角落** — 四个人都没重点提的东西，是否恰恰是最重要的？
4. **卖出纪律触发评估** — 本季度数据是否触发了 `exit-signal` 的 P0~P5 任何一级卖出条件？

### 编辑 Agent 的核心原则

- 保留所有关键数据和结论，**不降低专业深度**
- 改善表达方式，让非专业投资者也能跟上逻辑
- 突出「景气逻辑验证」和「卖出纪律更新」两个核心看点
- 文章长度控制在 1000-3000 字（太长读者会跳出）

### 读者评审 Agent 的四大维度（景气投资版）

| 维度 | 权重 | 核心问题 |
|------|------|---------|
| 可读性 | 25% | 有没有想跳过的段落？哪些地方看不懂？ |
| 信息价值 | 25% | 读完后对这家公司的理解是否加深了？ |
| 可信度 | 20% | 数据是否有来源？是否呈现了正反两面？ |
| 行动指导性 | 30% | 读完后知道该怎么做吗？卖出纪律清晰吗？ |

### 结论必须明确回答4个问题

1. **这份财报是超预期、符合预期、还是低于预期？**
2. **景气逻辑影响**：强化 / 部分验证 / 无影响 / 削弱 / 破裂
3. **卖出纪律是否触发？触发哪一级？**（依据 `exit-signal` P0~P5）
4. **如果你已持有，底仓与机动仓分别该加仓/持有/减仓/清仓？**

---

## 工具依赖

### 本地数据获取工具

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票信息查询 | `python tools/a_share/stock_info.py --search 中际旭创` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 300308` |
| A股 | `tools/a_share/stock_quote.py` | 历史股价与实时行情 | `python tools/a_share/stock_quote.py --code 300308` |
| A股 | `tools/a_share/stock_equity.py` | 股权结构与财报下载 | `python tools/a_share/stock_equity.py --code 300308` |
| 港股 | `tools/hk_stock/stock_financial.py` | 港股信息与财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| 港股 | `tools/hk_stock/stock_quote.py` | 港股历史K线 | `python tools/hk_stock/stock_quote.py --code 00700` |
| 美股 | `tools/us_stock/stock_info.py` | 美股信息查询 | `python tools/us_stock/stock_info.py --search Apple` |
| 美股 | `tools/us_stock/stock_financial.py` | 美股财务指标 | `python tools/us_stock/stock_financial.py --code AAPL` |
| 美股 | `tools/us_stock/stock_quote.py` | 美股行情数据 | `python tools/us_stock/stock_quote.py --code AAPL` |

**Python路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

**数据源**：东方财富、新浪财经、巨潮资讯（A股）；东方财富、新浪财经（港股）；yfinance（美股）

详细使用说明请参考：
- **A股工具**：[docs/A股工具使用指南.md](../../docs/A股工具使用指南.md)
- **港股工具**：[docs/港股工具使用指南.md](../../docs/港股工具使用指南.md)
- **美股工具**：[docs/美股工具使用指南.md](../../docs/美股工具使用指南.md)
- **国际货币汇率**（跨币种财报数据折算）：`python tools/common/fx_rate.py --code USDCNY,HKDCNY`

### 财报下载工具（A股专用）

财报精读的核心数据来源是一手财报PDF。A股使用 `tools/a_share/stock_equity.py` 下载：

| 功能 | 命令示例 |
|------|---------|
| 下载年报 | `python tools/a_share/stock_equity.py --code 300308 --download-report --report-type annual` |
| 下载半年报 | `python tools/a_share/stock_equity.py --code 300308 --download-report --report-type semiannual` |
| 下载季报 | `python tools/a_share/stock_equity.py --code 300308 --download-report --report-type quarterly` |
| 股权结构数据 | `python tools/a_share/stock_equity.py --code 300308` |

**文件保存位置**：默认目录 `./cninfo_reports/`，命名格式：`{股票代码}_{年份}{报告类型}.pdf`

**流程检查点**：确认PDF文件下载成功后，方可启动4个研究Agent。

### PDF文档阅读工具（首选 pdf_extract.py）

提取文字与表格**首选** `tools/common/pdf_extract.py`（基于 pdf-inspector 库，支持自动乱码检测 + OCR 回退），返回失败（退出码非0 / success=false / 扫描件）时才回退 Poppler 工具集：

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `pdf_extract.py` | PDF文字与表格提取（首选） | `python tools/common/pdf_extract.py markdown cninfo_reports/300308_2024年报.pdf --save-md` |
| `pdftotext` | 将PDF转换为文本格式（回退） | `pdftotext cninfo_reports/300308_2024年报.pdf cninfo_reports/300308_2024年报.txt` |
| `pdfinfo` | 查看PDF文件信息（回退） | `pdfinfo cninfo_reports/300308_2024年报.pdf` |
| `pdftoppm` | 将PDF转换为图像（回退，用于扫描版PDF） | `pdftoppm -png cninfo_reports/300308_2024年报.pdf cninfo_reports/300308_2024年报` |

详见 [PDF文档内容提取技能](../tools-scripts/pdf-extraction.md)。

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证、交叉验证、PEG 等） | `python tools/common/financial_rigor.py peg --pe 25 --growth 20` |
| `tools/common/report_audit.py` | 报告数据抽检与审核（准出流程） | `python tools/common/report_audit.py extract --report reports/xxx.md` |

**重要约束**：
- 估值数据须使用 `financial_rigor.py` 校验，禁止 LLM 心算
- PEG 估值档位以 `/valuation-thermometer` 输出为准，本技能不重复定义五档阈值
- 卖出纪律以 `/exit-signal` 的 P0~P5 输出为准，本技能不重复定义触发阈值

### 网络搜索工具

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。完整角色定位、市场×场景选型矩阵、命令速查、多源验证示例见 [web-search-tools](../tools-scripts/web-search-tools.md)。

**财报团队精读场景下的搜索选型**：
- A股：`anysearch --tag finance` 主 + `doubao --finance` 辅
- 港股：`doubao --sites hkexnews.hk` 主 + `tavily` 辅；双源 doubao+tavily
- 美股：`exa --type deep` 主 + `doubao` 辅；双源 exa+doubao

**重要约束**：
- A股财报必须优先使用 `stock_equity.py` 下载原始PDF，**下载完成后方可启动4个研究Agent**
- 关键财务数据须至少两个来源交叉验证，误差 >1% 须标记

---

## 核心原则

1. **读原文，不读摘要** — 尽一切可能获取一手资料，避免依赖二手信息
2. **四个视角不是四个部门** — 必须相互印证和挑战，不是各说各话
3. **Team Lead 的价值在于综合判断** — 找交集和矛盾点，不是拼报告
4. **结论要明确** — 不允许"总体来看基本符合预期但也有一些值得关注的点"
5. **反面检验贯穿全程** — 每个积极发现都附带反面论据
6. **每季必答核心问题** — 景气逻辑是否成立？卖出纪律是否触发？
7. **引用不重复定义** — 估值/卖出/产业景气/二阶导/治理评分一律引用对应权威 Skill
8. **中期口径红线** — 禁止使用「护城河永续」「终局思维」「持有10年」等长期框架术语

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- A股公司必须首先使用 `stock_equity.py` 下载原始财报PDF，**下载完成后方可启动4个研究Agent**
- 资料可得性评级（A/B/C级）需告知每个研究Agent，影响其分析深度
- 所有数据必须标注来源，关键财务数据至少两个独立来源交叉验证
- 报告发布前必须通过 `tools/common/report_audit.py` 数据抽检
- 编辑改写时：不可降低专业深度，文章长度控制在1000-3000字
- 读者评审的"必须修改"项需逐条处理，"建议优化"项选择性采纳
- 不预设立场：先摆数据 → 推逻辑 → 出结论
- 网络搜索须使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 港股/美股公司须按市场双源验证（港股 doubao+tavily；美股 exa+doubao）

---

## 局限性说明

- **资料可得性**：部分公司的完整财报原文可能难以获取，导致评级为B或C级
- **扫描版PDF限制**：A股年报常为扫描版PDF，可能无法提取文本内容，影响附注分析
- **语言限制**：非中英文财报可能无法准确解读
- **非实时数据**：工具获取的数据可能有延迟，不是实时数据
- **渗透率数据可得性**：细分行业渗透率缺乏官方统计，需依赖第三方估算
- **地缘政治数据更新频率**：制裁清单、关税政策等变化较快，需定期更新
- **并行执行复杂度**：6个Agent并行执行可能需要较长时间
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [财报精读（长期版）](../earnings-team/README.md) — 长期链段永平-巴菲特-芒格-李录财报团队
- [中期投研团队](../mid-investment-team/README.md) — 四角色中期全面公司研究
- [中期投资检查清单](../mid-investment-checklist/README.md) — 买入前七关景气检查
- [估值温度计](../valuation-thermometer/README.md) — PEG五档温度（本 Skill Agent 1 口径来源）
- [卖出信号](../exit-signal/README.md) — P0~P5 卖出纪律（本 Skill「卖出纪律更新」口径来源）
- [季度加速度](../qoq-accelerator/README.md) — 二阶导判断（本 Skill Agent 2 辅助）
- [中期行业研究](../mid-industry-research/README.md) — 产业景气/渗透率口径来源
- [中期管理层纵深](../mid-management-deep-dive/README.md) — 管理层/科研转化口径来源

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-09-05
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。