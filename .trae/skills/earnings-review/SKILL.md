---
name: earnings-review
description: 财报精读技能——对指定公司进行财报精读分析，从一手资料深度解读，关注巴菲特和李录真正会看的内容。
disable-model-invocation: true
---
# 财报精读：一手资料深度解读

对 $ARGUMENTS 进行财报精读分析。

**支持输入格式**：`公司名 季度`，例如：`腾讯 2025Q4`、`PDD 2025年报`、`美团 最新`（默认读取最近一期）

> "我从不看卖方研报，只读原始财报。" —— 李录
>
> "我每天读500页。知识就是这样积累的，像复利一样。" —— 巴菲特

## 设计理念

大多数AI投研工具依赖二手信息（新闻、研报摘要、数据网站）。但巴菲特和李录的核心能力是**读一手资料**——年报、季报、电话会纪要。

二手信息的问题：

- 被筛选过——分析师选择性呈现对其观点有利的数据
- 有时滞——等别人消化完，alpha已经没了
- 缺乏语境——"收入增长15%"脱离了管理层对增长质量的讨论

本Skill直接解读一手资料，关注巴菲特和李录真正会看的内容。

## 执行流程

### 前置步骤：资料可得性评级

| 等级 | 特征                                   | 影响                                                   |
| ---- | -------------------------------------- | ------------------------------------------------------ |
| A级  | 获取到完整原文（10-K/年报/电话会纪要） | 正常执行全部步骤                                       |
| B级  | 仅获取到部分原文或第三方汇总           | 标注"非原始来源"，降低附注分析权重                     |
| C级  | 仅有新闻报道和数据网站摘要             | 聚焦核心财务数据变化，跳过附注挖掘，标注"一手资料不足" |

### 第一步：获取一手资料

#### 1.1 A股财报原文下载（优先执行，必须完成）

**重要流程**：对于A股公司，必须首先使用 `stock_equity.py` 工具下载原始财报PDF，**下载完成后方可进行下一步的阅读分析工作**。

```bash
# 下载最新年报PDF
python tools/a_share/stock_equity.py --code {股票代码} --download-report --report-type annual

# 下载最新半年报PDF（如需分析半年报）
python tools/a_share/stock_equity.py --code {股票代码} --download-report --report-type semiannual

# 下载最新季报PDF（如需分析季报）
python tools/a_share/stock_equity.py --code {股票代码} --download-report --report-type quarterly
```

下载的PDF文件保存在 `cninfo_reports/` 目录，文件命名格式：

- 年报：`{股票代码}_{年份}年报.pdf`
- 半年报：`{股票代码}_{年份}半年报.pdf`
- 季报：`{股票代码}_{年份}{季度}季报.pdf`

可使用 `--report-dir` 参数指定其他保存目录：

```bash
python tools/a_share/stock_equity.py --code 601899 --download-report --report-type annual --report-dir ./reports/紫金矿业
```

**流程检查点**：确认PDF文件下载成功后，方可进行后续的财报阅读分析。

#### 1.2 PDF文档阅读工具

下载的财报PDF文档提取文字与表格**首选** `tools/common/pdf_extract.py`（基于 pdf-inspector 库），返回失败（退出码非0 / success=false / 扫描件）时才回退 Poppler 工具集：

**首选工具**：
```bash
# 分类检测 PDF 类型
python tools/common/pdf_extract.py detect cninfo_reports/002465_2025年报.pdf

# 提取含财务附表的 Markdown 并写盘
python tools/common/pdf_extract.py markdown cninfo_reports/002465_2025年报.pdf --save-md --out-dir reports/pdf
```

**回退工具（Poppler 工具集，仅当 pdf_extract.py 返回失败时使用）**：

- `pdftotext`：将PDF转换为文本格式
- `pdfinfo`：查看PDF文件信息
- `pdftoppm`：将PDF转换为图像

```bash
# 查看PDF文件信息
pdfinfo cninfo_reports/002465_2025年报.pdf

# 将PDF转换为文本文件
pdftotext cninfo_reports/002465_2025年报.pdf cninfo_reports/002465_2025年报.txt

# 将PDF转换为图像（用于扫描版PDF）
pdftoppm -png cninfo_reports/002465_2025年报.pdf cninfo_reports/002465_2025年报
```

**注意事项**：

- 首选 `pdf_extract.py` 提取文字与表格；返回失败时才回退 Poppler 工具集（详见 [PDF文档内容提取技能](../tools-scripts/pdf-extraction.md)）
- 如果PDF无法提取内容，应在报告中标注"资料评级：B级"，说明扫描版PDF限制

#### 1.3 并行获取其他原始材料

使用 Task 工具启动多个后台 Agent **并行**获取以下原始材料：

1. **财报原文**：
   - A股：已通过 `stock_equity.py` 下载，从PDF中提取关键内容
   - 美股：从公司IR页面、SEC EDGAR（10-K/10-Q）获取
   - 港股：从港交所披露易获取
2. **业绩电话会纪要/录音**：从 Seeking Alpha、公司IR页面、雪球等获取
3. **管理层致股东信**（如有年报）：完整阅读
4. **投资者日/分析师日材料**（如近期有）

如果无法获取完整原文，按数据获取规范使用标准数据源拼凑，但必须标注"非原始财报，来自第三方汇总"，且关键数据两源误差>1%须标记。

**注意**：WebSearch/WebFetch 在中国大陆不可用，请使用以下替代方案：

| 市场 | 工具 | 命令示例 |
|------|------|---------|
| A股数据 | `tools/a_share/stock_info.py`、`stock_financial.py`、`stock_quote.py`、`stock_equity.py` | `python tools/a_share/stock_financial.py --code 601899` |
| 港股数据 | `tools/hk_stock/stock_financial.py`、`stock_quote.py` | `python tools/hk_stock/stock_financial.py --financial 00700` |
| 美股数据 | `tools/us_stock/stock_info.py`、`stock_financial.py`、`stock_quote.py` | `python tools/us_stock/stock_financial.py --code AAPL` |
| 网络搜索（A股） | `tools/common/doubao_search.py`（首选）、`tools/common/web_search.py` | `python tools/common/doubao_search.py "{公司名} 最新财报" --finance --need-content --time-range month` |
| 网络搜索（港股/美股） | `tools/common/doubao_search.py`（首选）+ `tools/common/tavily_search.py`（双源验证） | `python tools/common/doubao_search.py "{公司名} 财报" --finance --need-content --time-range month` |

### 第二步：核心财务数据提取与验证

#### 2.1 收入与利润表

| 指标 | 本期 | 上期 | YoY变化 | 管理层指引 | 是否达标 |
| ---- | ---- | ---- | ------- | ---------- | -------- |

必须覆盖：

- 总收入及分业务/分地区收入拆解
- 毛利润、毛利率变化
- 经营利润、经营利润率变化（区分GAAP和Non-GAAP）
- 净利润（注意非经常性损益的影响）
- EPS（基本 vs 稀释）

#### 2.2 现金流表（巴菲特最看重）

| 指标 | 本期 | 上期 | 变化 | 关注点 |
| ---- | ---- | ---- | ---- | ------ |

必须覆盖：

- 经营性现金流 vs 净利润的比率（>100%为佳，<80%需警惕）
- 资本开支及其构成（维护性 vs 扩张性）
- 自由现金流 = 经营现金流 - 资本开支
- 回购金额、分红金额
- 现金及等价物期末余额

#### 2.3 资产负债表健康度

必须覆盖：

- 现金+短期投资 vs 有息负债
- 净现金/净负债变化趋势
- 应收账款周转天数变化（是否在放松信用条件冲收入？）
- 存货周转天数变化（是否在积压？）
- 商誉及无形资产占比（是否有减值风险？）

**数据验证**：使用 `tools/common/financial_rigor.py` 对关键数据进行校验：

```bash
# 收入和净利润交叉验证（至少2个来源）
python tools/common/financial_rigor.py cross-validate \
  --metric "revenue" --values 108.3e9 107.9e9 --sources "公司财报" "Yahoo Finance"

# 市值校验
python tools/common/financial_rigor.py verify-market-cap \
  --price 101 --shares 1.488e9 --reported 1.44e11 --currency USD

# 估值指标验算
python tools/common/financial_rigor.py verify-valuation \
  --price 101 --eps 9.6 --bvps 26.5 --fcf-per-share 10.2
```

### 第三步：管理层讨论精读（MD&A）

这是巴菲特和李录花最多时间的部分。不是看数字，是**听管理层怎么说**。

#### 3.1 管理层语气分析

逐段阅读管理层讨论/电话会发言，标注以下信号：

| 信号类型               | 具体表现                                         | 示例                                                  |
| ---------------------- | ------------------------------------------------ | ----------------------------------------------------- |
| 🟢**坦诚信号**   | 主动承认问题、给出具体原因                       | "本季度利润率下降主要因为我们在X领域的投入超出预期"   |
| 🟢**清晰信号**   | 战略表述具体、有量化目标                         | "我们计划在未来12个月将X业务的市场份额从15%提升到20%" |
| 🔴**模糊信号**   | 大量使用"我们相信"、"长期来看"等没有实质内容的话 | "我们对未来充满信心"                                  |
| 🔴**转移信号**   | 回避直接问题、用其他话题带过                     | 被问利润率时转谈收入增速                              |
| 🔴**归因外部化** | 把问题全归咎于宏观/行业/竞争对手                 | "由于宏观环境影响..."                                 |

#### 3.2 承诺追踪

从上一期财报/电话会中提取管理层的具体承诺，与本期实际情况对比：

| 上期承诺                 | 本期兑现情况 | 评价                             |
| ------------------------ | ------------ | -------------------------------- |
| "下半年利润率将恢复到X%" | 实际Y%       | ✅达标 / ❌未达标 / ⚠️部分达标 |

**段永平**："看一个管理层靠不靠谱，最简单的方法就是看他以前说的话做到了没有。"

#### 3.3 关键问题识别

从电话会Q&A环节提取分析师最尖锐的问题，以及管理层的回答质量：

| 分析师问题 | 管理层回答 | 回答质量(1-5) | 是否回避 |
| ---------- | ---------- | :-----------: | :------: |

### 第四步：附注与隐藏信息挖掘

财报附注里藏着管理层不想让你轻易看到的信息：

#### 4.1 必查附注项

- [ ] **关联交易**：与大股东/关联方的交易条款是否公允？
- [ ] **股权激励**：期权/RSU的稀释效应有多大？行权价是多少？
- [ ] **或有负债**：诉讼、担保、承诺等表外风险
- [ ] **会计政策变更**：是否改变了收入确认方式、折旧年限等？
- [ ] **分部信息**：不同业务的利润率差异，是否有"好业务补贴坏业务"
- [ ] **客户/供应商集中度**：前五大客户/供应商占比

#### 4.2 异常信号检测

- [ ] 应收账款增速 > 收入增速（可能在塞渠道）
- [ ] 存货增速 > 收入增速（可能在积压）
- [ ] 经营现金流 < 净利润且差距扩大（利润质量存疑）
- [ ] 资本化开支突然增加（可能在美化利润）
- [ ] 非经常性收益占比突然上升

### 第五步：与历史数据对比

#### 5.1 趋势分析

将本期关键指标放入至少4个季度（或3年年报）的时间序列中：

| 指标 | Q-4 | Q-3 | Q-2 | Q-1 | 本期 | 趋势判断 |
| ---- | --- | --- | --- | --- | ---- | -------- |

重点关注：

- 利润率是在改善还是恶化？
- 收入增速是在加速还是减速？
- 现金流质量是在提升还是下降？
- 资本开支强度是在增加还是减少？

#### 5.2 与管理层指引对比

| 指标 | 管理层此前指引 | 实际结果 | 偏差 | 解读 |
| ---- | -------------- | -------- | ---- | ---- |

### 第六步：输出精读报告

#### 报告结构

```
一、核心数据速览（一页表格）
二、本期最重要的3个变化（不超过500字）
三、管理层语气与承诺追踪
四、附注中的隐藏信息
五、关键问题（电话会Q&A精选）
六、与投资论文的关系（如有持仓）
七、结论：这份财报改变了什么？
```

#### 结论必须明确回答

1. **这份财报是超预期、符合预期、还是低于预期？**（不能说"基本符合"然后列一堆两面话）
2. **对投资论文的影响**：强化 / 无影响 / 削弱 / 破裂
3. **需要关注的下一个催化剂是什么？**
4. **如果你已持有，该加仓/持有/减仓？**

### 第七步：保存报告

将报告写入 `reports/{公司名}/{公司名}-earnings-{期间}.md`，例如 `reports/腾讯/腾讯-earnings-2025Q4.md`

### 第八步：数据抽检（准出流程）

报告写入后，执行数据抽检，通过方可发布：

```bash
# Step 1 — 提取抽检清单
python tools/common/report_audit.py extract \
  --report reports/{公司名}/{公司名}-earnings-{期间}.md

# Step 2 — 对清单每项从可靠信源取数

# Step 3 — 输出准出/打回判决
python tools/common/report_audit.py verdict \
  --results '<填好的JSON>' \
  --report {报告文件名}
```

**【准出】** 全部通过 → 发布；**【打回】** 有不通过 → 修正后重审。

---

## 工具使用指南

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
- **A股工具**：[docs/A股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/A股工具使用指南.md)
- **港股工具**：[docs/港股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/港股工具使用指南.md)
- **美股工具**：[docs/美股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/美股工具使用指南.md)

### 财报下载工具（A股专用）

财报精读的核心数据来源是一手财报PDF。A股使用 `tools/a_share/stock_equity.py` 下载：

| 功能 | 命令示例 |
|------|---------|
| 下载年报 | `python tools/a_share/stock_equity.py --code 601899 --download-report --report-type annual` |
| 下载半年报 | `python tools/a_share/stock_equity.py --code 601899 --download-report --report-type semiannual` |
| 下载季报 | `python tools/a_share/stock_equity.py --code 601899 --download-report --report-type quarterly` |
| 股权结构数据 | `python tools/a_share/stock_equity.py --code 601899` |

**文件保存位置**：默认目录 `./cninfo_reports/`，命名格式：
- 年报：`{股票代码}_{年份}年报.pdf`
- 半年报：`{股票代码}_{年份}半年报.pdf`
- 季报：`{股票代码}_{年份}{季度}季报.pdf`

**流程检查点**：确认PDF文件下载成功后，方可进行后续的财报阅读分析。

### PDF文档阅读工具（首选 pdf_extract.py）

提取文字与表格**首选** `tools/common/pdf_extract.py`（基于 pdf-inspector 库，能自动还原财务附表），返回失败（退出码非0 / success=false / 扫描件）时才回退 Poppler 工具集：

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `pdf_extract.py` | PDF文字与表格提取（首选） | `python tools/common/pdf_extract.py markdown cninfo_reports/002465_2025年报.pdf --save-md` |
| `pdftotext` | 将PDF转换为文本格式（回退） | `pdftotext cninfo_reports/002465_2025年报.pdf cninfo_reports/002465_2025年报.txt` |
| `pdfinfo` | 查看PDF文件信息（回退） | `pdfinfo cninfo_reports/002465_2025年报.pdf` |
| `pdftoppm` | 将PDF转换为图像（回退，用于扫描版PDF） | `pdftoppm -png cninfo_reports/002465_2025年报.pdf cninfo_reports/002465_2025年报` |

**注意**：首选 `pdf_extract.py`，返回失败时才回退 Poppler（详见 [PDF文档内容提取技能](../tools-scripts/pdf-extraction.md)）；如果PDF无法提取内容，应在报告中标注"资料评级：B级"，说明扫描版PDF限制。

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证、交叉验证等） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |
| `tools/common/report_audit.py` | 报告数据抽检与审核（准出流程） | `python tools/common/report_audit.py extract --report reports/xxx.md` |

**财报精读中的应用**：
- 收入和净利润交叉验证（至少2个来源）
- 市值校验（股价 × 总股本）
- 估值指标验算（PE、ROE等）

### 网络搜索工具

由于官方 WebSearch/WebFetch 在中国大陆不可用，请使用本地网络搜索工具。

**工具优先级**（基于上市地点）：

| 上市地点 | 主搜索工具 | 辅助搜索工具 | 说明 |
|---------|-----------|------------|------|
| A股 | `tools/common/doubao_search.py` | `tools/common/web_search.py` | 豆包搜索为推荐首选 |
| 港股/美股 | `tools/common/doubao_search.py` | `tools/common/tavily_search.py` + `tools/common/web_search.py` | 非境内上市需双源验证 |

**搜索工具能力**：

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/doubao_search.py` | 豆包搜索（推荐首选，支持财务/内容/导出/站点过滤） | `python tools/common/doubao_search.py "腾讯 2025Q4 财报" --finance --need-content --time-range month` |
| `tools/common/tavily_search.py` | Tavily 搜索（非境内上市辅助，支持高级搜索） | `python tools/common/tavily_search.py "Apple AAPL latest earnings" --max-results 5` |
| `tools/common/web_search.py` | 阿里云百炼搜索 | `python tools/common/web_search.py "紫金矿业 最新财报"` |

**搜索规范**（必须遵守）：
1. **时效性优先**：使用 `--time-range month/week` 限制时间范围，优先获取最新信息，避免使用过时数据
2. **数据源日期**：搜索结果必须包含数据来源日期；过时数据须明确标注时效性说明
3. **双源验证**：非境内上市公司须 Doubao + Tavily 双源验证
4. **多角度搜索**：从财报原文、管理层发言、业绩电话会纪要、分析师提问等多维度收集信息
5. **信息缺口标注**：关键信息缺失时标注"信息不足"，不得用推测填充

**重要内容（同时调用）**：

对于港股/美股的重要财报分析，建议**同时调用多个工具**，互为补充：

```bash
# 港股/美股：双源验证（并行执行）
python tools/common/doubao_search.py "腾讯 2025Q4 财报 管理层讨论" --finance --need-content --time-range month
python tools/common/tavily_search.py "腾讯 2025Q4 财报 管理层讨论" --max-results 5
```

---

## 注意事项

1. **读原文，不读摘要**：尽一切可能获取一手资料，避免依赖二手信息
2. **看变化，不看绝对值**：趋势比数字本身重要
3. **听语气，不只听内容**：管理层怎么说和说了什么一样重要
4. **查附注，不只看正文**：魔鬼藏在细节里
5. **给结论，不做汇总**：精读的目的是形成判断，不是复述财报
6. **数据验证**：关键数据必须至少来自两个独立来源，误差>1%须标记
7. **客观分析**：严格区分"事实"与"观点"，不预设立场
8. **呈现两面**：每个核心判断都必须附带反面论据
9. **网络搜索时效性**：使用 `--time-range month/week` 限制时间范围，优先获取最新信息
10. **非境内上市双源验证**：港股/美股公司须 Doubao + Tavily 双源验证

---

## 局限性

1. **资料可得性**：部分公司的完整财报原文可能难以获取，导致评级为B或C级
2. **语言限制**：非中英文财报可能无法准确解读
3. **非实时数据**：工具获取的数据可能有延迟，不是实时数据
4. **AI解读局限**：AI无法完全替代专业财务分析师的深度分析能力
5. **不构成投资建议**：本技能仅用于学习与研究，不构成任何投资建议

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

## 报告示例

### 输入示例

```
腾讯 2025Q4
```

### 输出文件

`reports/腾讯/腾讯-earnings-2025Q4.md`

### 报告摘要示例

```markdown
# 腾讯 2025Q4 财报精读

## 一、核心数据速览

| 指标 | 本期 | 上期 | YoY变化 |
|------|------|------|---------|
| 总收入 | 166.1亿元 | 154.6亿元 | +7.4% |
| 毛利率 | 53.2% | 50.8% | +2.4pp |
| 净利润 | 42.7亿元 | 39.8亿元 | +7.3% |

## 二、本期最重要的3个变化

1. **广告收入超预期**：同比增长18%，主要受益于视频号广告加载率提升
2. **游戏业务回暖**：《王者荣耀》海外版用户数突破5000万
3. **成本控制见效**：销售费用率下降3个百分点，员工数量精简5%

...
```
