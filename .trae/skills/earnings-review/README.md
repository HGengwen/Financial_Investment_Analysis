# 财报精读 (Earnings Review)

一手资料深度解读：关注巴菲特和李录真正会看的内容

---

## 快速开始

### 基本调用方式

```
/earnings-review {公司名} {期间}
```

支持输入格式：
- `{公司名} {季度}` — 例如：`腾讯 2025Q4`、`美团 2025Q3`
- `{公司名} {年报}` — 例如：`PDD 2025年报`、`茅台 2025年报`
- `{公司名} 最新` — 默认读取最近一期，例如：`美团 最新`

例如：
- `/earnings-review 腾讯 2025Q4`
- `/earnings-review 茅台 2024年报`
- `/earnings-review 美团 最新`

---

## 核心功能

对指定公司进行财报精读分析，从一手资料深度解读，关注巴菲特和李录真正会看的内容。

### 设计理念

> "我从不看卖方研报，只读原始财报。" —— 李录
>
> "我每天读500页。知识就是这样积累的，像复利一样。" —— 巴菲特

大多数AI投研工具依赖二手信息（新闻、研报摘要、数据网站），本Skill直接解读一手资料（年报、季报、电话会纪要），避免二手信息被筛选、有时滞、缺乏语境的问题。

### 八步精读流程

1. **资料可得性评级** — A级（完整原文）/ B级（部分原文）/ C级（仅第三方摘要）
2. **获取一手资料** — A股优先下载财报PDF，港股美股并行获取多源材料
3. **核心财务数据提取与验证** — 收入利润表、现金流表、资产负债表健康度
4. **管理层讨论精读（MD&A）** — 语气分析、承诺追踪、关键问题识别
5. **附注与隐藏信息挖掘** — 关联交易、股权激励、或有负债、异常信号检测
6. **与历史数据对比** — 趋势分析、与管理层指引对比
7. **输出精读报告** — 七部分结构，结论必须明确回答4个问题
8. **数据抽检（准出流程）** — 使用 `report_audit.py` 执行抽检，通过方可发布

---

## 使用示例

### 示例1：精读腾讯季度财报
```
/earnings-review 腾讯 2025Q4
```
 下载/获取腾讯2025Q4财报原文，执行八步精读流程，输出 `reports/腾讯/腾讯-earnings-2025Q4.md`

### 示例2：精读A股年报
```
/earnings-review 紫金矿业 2024年报
```
 使用 `stock_equity.py` 下载年报PDF，提取关键内容后精读分析

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 财报精读报告 | `reports/{公司名}/{公司名}-earnings-{期间}.md` |

### 报告结构

```
一、核心数据速览（一页表格）
二、本期最重要的3个变化（不超过500字）
三、管理层语气与承诺追踪
四、附注中的隐藏信息
五、关键问题（电话会Q&A精选）
六、与投资论文的关系（如有持仓）
七、结论：这份财报改变了什么？
```

### 结论必须明确回答4个问题

1. **这份财报是超预期、符合预期、还是低于预期？**（不能说"基本符合"然后列两面话）
2. **对投资论文的影响**：强化 / 无影响 / 削弱 / 破裂
3. **需要关注的下一个催化剂是什么？**
4. **如果你已持有，该加仓/持有/减仓？**

---

## 精读标准

### 读原文，不读摘要

巴菲特和李录的核心能力是**读一手资料**——年报、季报、电话会纪要。二手信息的问题：
- 被筛选过——分析师选择性呈现对其观点有利的数据
- 有时滞——等别人消化完，alpha已经没了
- 缺乏语境——"收入增长15%"脱离了管理层对增长质量的讨论

### 管理层语气信号识别

| 信号类型 | 具体表现 |
|---------|---------|
| 🟢 **坦诚信号** | 主动承认问题、给出具体原因 |
| 🟢 **清晰信号** | 战略表述具体、有量化目标 |
| 🔴 **模糊信号** | 大量使用"我们相信"、"长期来看"等无实质内容的话 |
| 🔴 **转移信号** | 回避直接问题、用其他话题带过 |
| 🔴 **归因外部化** | 把问题全归咎于宏观/行业/竞争对手 |

### 异常信号检测（必查）

- 应收账款增速 > 收入增速（可能在塞渠道）
- 存货增速 > 收入增速（可能在积压）
- 经营现金流 < 净利润且差距扩大（利润质量存疑）
- 资本化开支突然增加（可能在美化利润）
- 非经常性收益占比突然上升

### 数据验证标准

关键数据必须至少来自两个独立来源，误差>1%须标记。使用 `tools/common/financial_rigor.py` 进行：
- 收入和净利润交叉验证
- 市值校验（股价 × 总股本）
- 估值指标验算（PE、ROE等）

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
- **国际货币汇率**（跨币种财报数据折算）：`tools/common/fx_rate.py`，详见 A股工具使用指南汇率章节

### 财报下载工具（A股专用）

财报精读的核心数据来源是一手财报PDF。A股使用 `tools/a_share/stock_equity.py` 下载：

| 功能 | 命令示例 |
|------|---------|
| 下载年报 | `python tools/a_share/stock_equity.py --code 601899 --download-report --report-type annual` |
| 下载半年报 | `python tools/a_share/stock_equity.py --code 601899 --download-report --report-type semiannual` |
| 下载季报 | `python tools/a_share/stock_equity.py --code 601899 --download-report --report-type quarterly` |
| 股权结构数据 | `python tools/a_share/stock_equity.py --code 601899` |

**文件保存位置**：默认目录 `./cninfo_reports/`，命名格式：`{股票代码}_{年份}{报告类型}.pdf`

**流程检查点**：确认PDF文件下载成功后，方可进行后续的财报阅读分析。

### PDF文档阅读工具（首选 pdf_extract.py）

提取文字与表格**首选** `tools/common/pdf_extract.py`（基于 pdf-inspector 库，支持自动乱码检测 + OCR 回退），返回失败（退出码非0 / success=false / 扫描件）时才回退 Poppler 工具集：

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `pdf_extract.py` | PDF文字与表格提取（首选） | `python tools/common/pdf_extract.py markdown cninfo_reports/002465_2025年报.pdf --save-md` |
| `pdftotext` | 将PDF转换为文本格式（回退） | `pdftotext cninfo_reports/002465_2025年报.pdf cninfo_reports/002465_2025年报.txt` |
| `pdfinfo` | 查看PDF文件信息（回退） | `pdfinfo cninfo_reports/002465_2025年报.pdf` |
| `pdftoppm` | 将PDF转换为图像（回退，用于扫描版PDF） | `pdftoppm -png cninfo_reports/002465_2025年报.pdf cninfo_reports/002465_2025年报` |

详见 [PDF文档内容提取技能](../tools-scripts/pdf-extraction.md)。

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证、交叉验证等） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |
| `tools/common/report_audit.py` | 报告数据抽检与审核（准出流程） | `python tools/common/report_audit.py extract --report reports/xxx.md` |

### 网络搜索工具

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。完整角色定位、市场×场景选型矩阵、命令速查、多源验证示例见 [web-search-tools](../tools-scripts/web-search-tools.md)。

**财报精读场景下的搜索选型**：
- A股：`anysearch --tag finance` 主 + `doubao --finance` 辅
- 港股：`doubao --sites hkexnews.hk` 主 + `tavily` 辅；双源 doubao+tavily
- 美股：`exa --type deep` 主 + `doubao` 辅；双源 exa+doubao

**搜索规范**（财报精读特有）：
- 使用 `--time-range month/week` 限制时间范围，财报数据须标注报告期与发布日期
- 港股公司须 doubao + tavily 双源验证；美股公司须 exa + doubao 双源验证
- 优先读取一手财报原文（A股 `stock_equity.py` 下载 PDF，美股 SEC EDGAR，港股披露易），搜索结果仅作补充
- 关键财务数据两源误差>1% 须明确标记，并标注"非原始财报，来自第三方汇总"
- 管理层语气/承诺追踪须从电话会纪要原文提取，搜索摘要不得替代一手材料

**重要约束**：
- A股财报必须优先使用 `stock_equity.py` 下载原始PDF
- 估值数据须使用 `financial_rigor.py` 校验，禁止 LLM 心算
- 关键财务数据须至少两个来源交叉验证

---

## 核心原则

1. **读原文，不读摘要** — 尽一切可能获取一手资料，避免依赖二手信息
2. **看变化，不看绝对值** — 趋势比数字本身重要
3. **听语气，不只听内容** — 管理层怎么说和说了什么一样重要
4. **查附注，不只看正文** — 魔鬼藏在细节里
5. **给结论，不做汇总** — 精读的目的是形成判断，不是复述财报
6. **数据验证** — 关键数据必须至少来自两个独立来源，误差>1%须标记
7. **客观分析** — 严格区分"事实"与"观点"，不预设立场
8. **呈现两面** — 每个核心判断都必须附带反面论据

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- A股公司必须首先使用 `stock_equity.py` 下载原始财报PDF，**下载完成后方可进行下一步分析**
- 所有数据必须标注来源，关键财务数据至少两个独立来源交叉验证
- 误差>1%的关键数据须明确标记
- 资料评级为B/C级时，必须在报告中标注"非原始来源"或"一手资料不足"
- 报告发布前必须通过 `tools/common/report_audit.py` 数据抽检
- 不预设立场：先摆数据 → 推逻辑 → 出结论
- 结论不能说"基本符合"然后列两面话，必须明确判断

---

## 局限性说明

- **资料可得性**：部分公司的完整财报原文可能难以获取，导致评级为B或C级
- **扫描版PDF限制**：A股年报常为扫描版PDF，可能无法提取文本内容
- **语言限制**：非中英文财报可能无法准确解读
- **非实时数据**：工具获取的数据可能有延迟，不是实时数据
- **AI解读局限**：AI无法完全替代专业财务分析师的深度分析能力
- 不构成投资建议，仅供学习研究参考

---

## 与其他Skill的关系

| Skill | 定位 | 何时用 |
|-------|------|--------|
| **`/earnings-review`（本Skill）** | **一手财报资料精读** | **季度财报发布后的深度解读** |
| `/earnings-team` | 六Agent团队精读 + 公众号发布 | 重要公司的关键财报需多Agent协作时 |
| `/investment-research` | 四大师综合投资研究 | 首次深度研究一家公司 |
| `/investment-team` | 四Agent全面公司研究 | 首次研究一家公司 |
| `/thesis-tracker` | 投资论文追踪 | 买入后的持续跟踪与论文检查 |
| `/management-deep-dive` | 管理层纵深研究 | 管理层是核心投资逻辑时 |
| `/portfolio-review` | 组合层面审视与优化 | 季度组合审视 |

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [深度公司系列](../deep-company-series/README.md) — 8篇长文拆一家公司
- [投研团队](../investment-team/README.md) — 四Agent全面公司研究
- [段永平问答](../dyp-ask/README.md) — 段永平投资思想问答

---

## 版本信息

- **版本**：1.1.0
- **创建日期**：2026-07-22
- **最后更新**：2026-08-13（新增自动乱码检测 + OCR 回退功能）
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。
