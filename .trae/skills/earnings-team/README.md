# 财报精读团队 (Earnings Team)

四大师并行解读财报 + 编辑润色 + 读者评审，产出可直接发布的公众号文章

---

## 快速开始

### 基本调用方式

```
/earnings-team {公司名} {期间}
```

支持输入格式：
- `{公司名} {季度}` — 例如：`腾讯 2025Q4`、`快手 2025Q3`
- `{公司名} {年报}` — 例如：`PDD 2025年报`、`茅台 2024年报`
- `{公司名} 最新` — 默认读取最近一期，例如：`美团 最新`

例如：
- `/earnings-team 腾讯 2025Q4`
- `/earnings-team 茅台 2024年报`
- `/earnings-team 美团 最新`

---

## 核心功能

对指定公司进行团队化财报精读分析。四位大师并行解读财报，编辑润色成文，读者评审把关质量，最终产出可直接发布的公众号文章。

### 三阶段六Agent流程

**阶段一·研究**：四大师并行精读财报
- 🎯 段永平 · 生意本质解读者 — 这门生意变好了还是变差了？
- 💰 巴菲特 · 财务质量审计师 — 赚的是真钱还是假钱？
- ⚔️ 芒格 · 竞争变化解读者 — 竞争格局在怎么变？
- 🛡️ 李录 · 风险信号猎手 — 管理层在隐瞒什么？

**阶段二·合成**：Team Lead 综合四个视角，产出研究报告初稿

**阶段三·发布**：
- ✍️ 编辑 Agent — 改写为公众号文章
- 👀 读者评审 Agent — 提出修改意见
- 📝 Team Lead — 定稿

### 设计理念

一份好的财报分析要解决两个问题：
1. **自己能看懂未来** — 需要四个不同视角的深度研究
2. **读者能看懂价值** — 需要编辑润色和读者视角的质量把关

---

## 使用示例

### 示例1：精读腾讯季度财报并产出公众号文章
```
/earnings-team 腾讯 2025Q4
```
 四大师并行精读腾讯2025Q4财报，输出可直接发布的公众号文章+研究底稿

### 示例2：精读A股年报并产出公众号文章
```
/earnings-team 茅台 2024年报
```
 使用 `stock_equity.py` 下载年报PDF，启动六Agent流程

### 示例3：快速精读最新一期财报
```
/earnings-team 美团 最新
```
 自动读取最近一期财报，执行完整团队化精读

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 公众号定稿 | `reports/{公司名}/{公司名}-earnings-{期间}.md` |
| 研究底稿 | `reports/{公司名}/{公司名}-earnings-{期间}-研究底稿.md` |
| 段永平视角 | `reports/{公司名}/{公司名}-earnings-{期间}-段永平.md` |
| 巴菲特视角 | `reports/{公司名}/{公司名}-earnings-{期间}-巴菲特.md` |
| 芒格视角 | `reports/{公司名}/{公司名}-earnings-{期间}-芒格.md` |
| 李录视角 | `reports/{公司名}/{公司名}-earnings-{期间}-李录.md` |
| 读者评审 | `reports/{公司名}/{公司名}-earnings-{期间}-读者评审.md` |

### 输出文件结构

```
reports/{公司名}/
├── {公司名}-earnings-{期间}.md           ← 最终公众号文章（定稿）
├── {公司名}-earnings-{期间}-研究底稿.md   ← 四大师合成研究报告（自用）
├── {公司名}-earnings-{期间}-段永平.md     ← 生意本质解读
├── {公司名}-earnings-{期间}-巴菲特.md     ← 财务质量审计
├── {公司名}-earnings-{期间}-芒格.md       ← 竞争格局解读
├── {公司名}-earnings-{期间}-李录.md       ← 风险信号分析
└── {公司名}-earnings-{期间}-读者评审.md   ← 读者评审报告
```

---

## 质量标准

### Team Lead 的合成价值：找交叉和矛盾

不是拼报告，是找交叉和矛盾：
1. **四个视角的共识点** — 四位大师都同意的结论，可信度最高
2. **四个视角的矛盾点** — 比如段永平说生意变好了，但芒格说竞争在恶化——这种矛盾才是最有价值的分析
3. **被忽略的角落** — 四个人都没重点提的东西，是否恰恰是最重要的？

### 编辑 Agent 的核心原则

- 保留所有关键数据和结论，**不降低专业深度**
- 改善表达方式，让非专业投资者也能跟上逻辑
- 不是"科普化"，是"让专业内容读起来不累"
- 文章长度控制在 1000-3000 字（太长读者会跳出）

### 读者评审 Agent 的四大维度

| 维度 | 权重 | 核心问题 |
|------|------|---------|
| 可读性 | 30% | 有没有想跳过的段落？哪些地方看不懂？ |
| 信息价值 | 30% | 读完后对这家公司的理解是否加深了？ |
| 可信度 | 20% | 数据是否有来源？是否呈现了正反两面？ |
| 行动指导性 | 20% | 读完后知道该怎么做吗？ |

### 结论必须明确回答4个问题

1. **这份财报是超预期、符合预期、还是低于预期？**
2. **对投资论文的影响**：强化 / 无影响 / 削弱 / 破裂
3. **需要关注的下一个催化剂是什么？**
4. **如果你已持有，该加仓/持有/减仓？**

---

## 工具依赖

### 本地数据获取工具

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票信息查询 | `python tools/a_share/stock_info.py --search 紫金矿业` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 601899` |
| A股 | `tools/a_share/stock_quote.py` | 历史股价与实时行情 | `python tools/a_share/stock_quote.py --code 601899` |
| A股 | `tools/a_share/stock_equity.py` | 股权结构与财报下载 | `python tools/a_share/stock_equity.py --code 601899` |
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

### 财报下载工具（A股专用）

财报精读的核心数据来源是一手财报PDF。A股使用 `tools/a_share/stock_equity.py` 下载：

| 功能 | 命令示例 |
|------|---------|
| 下载年报 | `python tools/a_share/stock_equity.py --code 601899 --download-report --report-type annual` |
| 下载半年报 | `python tools/a_share/stock_equity.py --code 601899 --download-report --report-type semiannual` |
| 下载季报 | `python tools/a_share/stock_equity.py --code 601899 --download-report --report-type quarterly` |
| 股权结构数据 | `python tools/a_share/stock_equity.py --code 601899` |

**文件保存位置**：默认目录 `./cninfo_reports/`，命名格式：`{股票代码}_{年份}{报告类型}.pdf`

**流程检查点**：确认PDF文件下载成功后，方可启动4个研究Agent。

### PDF文档阅读工具（Poppler 工具集）

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `pdftotext` | 将PDF转换为文本格式 | `pdftotext cninfo_reports/002465_2025年报.pdf cninfo_reports/002465_2025年报.txt` |
| `pdfinfo` | 查看PDF文件信息 | `pdfinfo cninfo_reports/002465_2025年报.pdf` |
| `pdftoppm` | 将PDF转换为图像（用于扫描版PDF） | `pdftoppm -png cninfo_reports/002465_2025年报.pdf cninfo_reports/002465_2025年报` |

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证、交叉验证、三情景估值等） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |
| `tools/common/report_audit.py` | 报告数据抽检与审核（准出流程） | `python tools/common/report_audit.py extract --report reports/xxx.md` |

### 网络搜索工具

由于官方 WebSearch/WebFetch 在中国大陆不可用，请使用本地网络搜索工具。

**工具优先级**（基于上市地点）：

| 上市地点 | 主搜索工具 | 辅助搜索工具 | 说明 |
|---------|-----------|------------|------|
| A股 | `tools/common/doubao_search.py` | `tools/common/web_search.py` | 豆包搜索为推荐首选 |
| 港股/美股 | `tools/common/doubao_search.py` | `tools/common/tavily_search.py` + `tools/common/web_search.py` | 非境内上市需双源验证 |

**搜索规范**：
- 使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 搜索结果必须包含数据来源日期；过时数据须标注时效性说明
- 非境内上市公司须 Doubao + Tavily 双源验证
- 关键信息缺失时标注"信息不足"，不得用推测填充

**重要约束**：
- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- A股财报必须优先使用 `stock_equity.py` 下载原始PDF，**下载完成后方可启动4个研究Agent**
- 港股/美股重要分析建议同时调用 Doubao 和 Tavily 互为补充
- 估值数据须使用 `financial_rigor.py` 校验，禁止 LLM 心算
- 关键财务数据须至少两个来源交叉验证

---

## 核心原则

1. **读原文，不读摘要** — 尽一切可能获取一手资料，避免依赖二手信息
2. **四个视角不是四个部门** — 必须相互印证和挑战，不是各说各话
3. **Team Lead 的价值在于综合判断** — 找交集和矛盾点，不是拼报告
4. **结论要明确** — 不允许"总体来看基本符合预期但也有一些值得关注的点"
5. **反面检验贯穿全程** — 每个积极发现都附带反面论据
6. **编辑不是降低专业度** — 是让专业内容更易读，不是变成科普
7. **读者评审不是走过场** — 真的站在读者角度挑毛病
8. **数据准确性** — 关键数据交叉验证，使用 `financial_rigor.py` 工具验算

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
- 港股/美股公司须 Doubao + Tavily 双源验证，确保信息准确性

---

## 局限性说明

- **资料可得性**：部分公司的完整财报原文可能难以获取，导致评级为B或C级
- **扫描版PDF限制**：A股年报常为扫描版PDF，可能无法提取文本内容，影响附注分析
- **语言限制**：非中英文财报可能无法准确解读
- **非实时数据**：工具获取的数据可能有延迟，不是实时数据
- **AI解读局限**：AI无法完全替代专业财务分析师的深度分析能力
- **并行执行复杂度**：6个Agent并行执行可能需要较长时间
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [财报精读](../earnings-review/README.md) — 单Agent财报精读（快速版）
- [投研团队](../investment-team/README.md) — 四Agent全面公司研究
- [深度公司系列](../deep-company-series/README.md) — 8篇长文拆一家公司

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-07-22
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。
