---
name: "investment-checklist"
description: "Execute Buffett-style pre-purchase checklist analysis for stocks. Invoke when user requests buy-side due diligence, investment decision analysis, or multi-company comparison."
disable-model-invocation: true
---

# 巴菲特价值投资买入前 Checklist

对指定公司执行巴菲特价值投资买入前 Checklist 分析。

**支持输入格式**：单个或多个公司，用逗号/顿号/空格分隔。例如：`腾讯, 茅台, 英伟达` 或 `NVDA AAPL MSFT`

---

## 执行流程

### 第一步：解析输入，识别所有待分析公司

从用户输入中解析出所有公司名称/代码。对每家公司确定：
- 公司全称、股票代码、上市交易所
- 如果公司未上市，标记为"未上市"并给出简要说明（是否有间接投资途径），跳过完整Checklist

### 第一步半：AI研究偏见预警

对每家公司进行"信息丰富度"快速评级（A/B/C），并在报告中标注：

| 等级 | 判断标准 | 对Checklist的影响 |
|------|---------|-----------------|
| A级 | 上市多年、数据充裕 | 正常执行，但警惕"共识陷阱"——所有指标看起来都清晰不代表真的确定 |
| B级 | 数据有限需推算 | 每个推算指标标注置信度，"好生意"判断加权考虑数据可靠性 |
| C级 | 信息极度稀缺 | 不勉强填满六关表格，诚实标注"数据不足无法判断"，聚焦可验证的核心问题 |

**核心原则**：Checklist的目标是**排除坏选择**。对于C级公司，"数据不足"不等于"不通过"，也不等于"通过"——应诚实标注为"灰色地带，需补充一手信息"，而不是因为AI无法填满表格就判为否决。

段永平说过："看不懂"有两种——一种是生意太复杂真的看不懂，一种是你还没花时间去看。AI研究的局限是容易把"资料少"和"看不懂"混为一谈。

### 第二步：并行数据收集

使用 Task 工具为**每家公司**启动独立的后台 Agent 进行数据收集（所有公司同时并行启动），每个Agent负责收集：

1. **盈利能力**：ROE（5-10年趋势）、毛利率、净利率、自由现金流
2. **估值数据**：当前股价、市值、PE(TTM)、前瞻PE、PB、股息率
3. **增长趋势**：近3年收入/利润增速
4. **财务健康**：负债水平、资本开支需求、现金储备、净现金/净负债
5. **竞争格局**：市场份额、主要竞争对手、份额变化趋势
6. **护城河证据**：品牌/转换成本/网络效应/规模效应/技术壁垒的具体证据
7. **管理层记录**：CEO履历、关键决策、持股、资本配置记录
8. **最新动态**：近6个月重大事件（业绩、并购、监管、管理层变动等）

**数据获取工具规范**（详见"工具使用指南"章节）：
- A股数据：使用 `tools/a_share/stock_info.py`、`tools/a_share/stock_quote.py`、`tools/a_share/stock_financial.py`、`tools/a_share/stock_screen.py`
- **A股批量财务指标**（多公司对比时）：使用 `tools/a_share/stock_financial_batch.ps1`，一次获取多只股票的 ROE、毛利率、净利率等指标（PowerShell 7 运行）
- 港股数据：使用 `tools/hk_stock/stock_info.py`、`tools/hk_stock/stock_quote.py`、`tools/hk_stock/stock_screen.py`
- 美股数据：使用 `tools/us_stock/stock_info.py`、`tools/us_stock/stock_financial.py`、`tools/us_stock/stock_quote.py`
- 精确计算：使用 `tools/common/financial_rigor.py` 进行PE、ROE、市值等指标的精确计算
- 网络搜索：根据公司上市地点选择相应工具（详见"工具使用指南"）

#### 网络搜索工具选择

| 上市地点 | 主搜索工具 | 辅助搜索工具 | 说明 |
|---------|-----------|------------|------|
| A股 | `tools/common/doubao_search.py` | `tools/common/web_search.py` | 豆包搜索为推荐首选 |
| 港股/美股 | `tools/common/doubao_search.py` | `tools/common/tavily_search.py` + `tools/common/web_search.py` | 非境内上市需双源验证 |

**搜索规范**（必须遵守）：
1. **时效性优先**：使用 `--time-range month/week` 限制时间范围，优先获取最新信息，避免使用过时数据
2. **数据源日期**：搜索结果必须包含数据来源日期；过时数据须明确标注时效性说明
3. **双源验证**：非境内上市公司须 Doubao + Tavily 双源验证
4. **多角度搜索**：从竞争格局、护城河、管理层、最新动态等多维度收集信息

**搜索示例**：

| 数据收集维度 | A股搜索 | 港股/美股搜索 |
|------------|---------|--------------|
| 竞争格局 | `python tools/common/doubao_search.py "{公司名} 行业排名 市场份额" --time-range month` | `python tools/common/doubao_search.py "{公司名} market share competitors" --time-range month` |
| 护城河证据 | `python tools/common/doubao_search.py "{公司名} 护城河 竞争优势" --time-range month` | `python tools/common/tavily_search.py "{公司名} competitive advantage moat" --max-results 5` |
| 管理层记录 | `python tools/common/doubao_search.py "{公司名} CEO 履历 资本配置" --time-range month` | `python tools/common/tavily_search.py "{公司名} CEO management capital allocation" --max-results 5` |
| 最新动态 | `python tools/common/doubao_search.py "{公司名} 最新消息" --time-range week` | `python tools/common/doubao_search.py "{公司名} latest news" --time-range week` |

**重要约束**：
- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 关键财务数据必须至少来自两个独立来源进行交叉验证
- 所有估计值必须明确标注"估计"
- 网络搜索结果需交叉验证，不要依赖单一来源

### 第三步：逐公司执行六关 Checklist

对每家已上市公司，依次过六关：

---

#### 第一关：我能理解这门生意吗（能力圈）

必须回答：
- [ ] 能用一句话说清楚这家公司靠什么赚钱吗？
- [ ] 10年后大概率还在做什么生意？
- [ ] 哪些关键变量决定成败？
- [ ] 对这个行业的认知是来自深度研究还是道听途说？

**评分标准**（★1-5）：
- ★★★★★：商业模式极其简单清晰，10年确定性高（如茅台：酿酒卖酒）
- ★★★★☆：模式清晰但有技术门槛，需要一定专业知识理解
- ★★★☆☆：模式可理解但10年确定性不高，行业变化快
- ★★☆☆☆：业务线复杂或行业剧变中，难以预判未来
- ★☆☆☆☆：完全不在能力圈内

**硬性否决**：如果连赚钱方式都说不清，直接标记为"不在能力圈，不做分析"。

---

#### 第二关：这是一门好生意吗（经济特征）

用数据说话，**关键指标必须通过工具精确计算**：

```bash
python tools/common/financial_rigor.py verify-valuation \
  --price {股价} --eps {EPS} --bvps {每股净资产} --fcf-per-share {每股FCF} --dividend {每股股息}
```

| 指标 | 该公司数值 | 参考标准 | 判断 |
|------|-----------|---------|------|
| ROE（5年均值） | | >15%优秀, >20%卓越 | |
| 毛利率 | | >40%暗示定价权 | |
| 自由现金流 | | 持续为正、≈净利润 | |
| 资本开支强度 | | 轻资产优于重资产 | |
| 负债水平 | | 有息负债/净利润<3年 | |

**评分标准**（★1-5）：
- ★★★★★：ROE>25%、高毛利、强FCF、轻资产、低负债（全部达标）
- ★★★★☆：4项达标
- ★★★☆☆：3项达标
- ★★☆☆☆：2项达标或趋势恶化
- ★☆☆☆☆：多数不达标或FCF持续为负

---

#### 第三关：护城河够不够深（竞争优势）

逐项检查：

| 护城河类型 | 是否具备 | 具体证据 | 变宽还是变窄？ |
|-----------|---------|---------|--------------|
| 品牌/定价权 | | | |
| 转换成本 | | | |
| 网络效应 | | | |
| 成本/规模优势 | | | |
| 技术/专利壁垒 | | | |

追加检验：如果给竞争对手100亿，能否复制这门生意？

**评分标准**（★1-5）：
- ★★★★★：多重护城河叠加且在变宽
- ★★★★☆：至少一条强护城河且稳定
- ★★★☆☆：有护城河但不够深，或趋势不明
- ★★☆☆☆：护城河正在被侵蚀
- ★☆☆☆☆：无明显护城河

---

#### 第四关：管理层是否值得信任（人的因素）

| 检查项 | 评估 |
|--------|------|
| 诚实度（承诺vs交付） | |
| 资本配置能力（回购/分红/并购记录） | |
| 股东利益导向（持股、薪酬） | |
| 所有者心态（创始人 vs 职业经理人） | |
| 公司治理（关联交易、商誉、审计） | |
| CEO离开后能否照常运转？ | |

**评分标准**（★1-5）：
- ★★★★★：创始人掌舵、资本配置卓越、利益完全一致
- ★★★★☆：管理层优秀但有小瑕疵
- ★★★☆☆：管理层合格但有治理隐患
- ★★☆☆☆：有诚信或治理问题
- ★☆☆☆☆：严重诚信问题（→硬性否决）

---

#### 第五关：价格是否足够便宜（安全边际）

| 指标 | 数值 | 历史分位 | 判断 |
|------|------|---------|------|
| PE (TTM) | | | |
| 前瞻PE | | | |
| PB | | | |
| 股息率 | | | |
| FCF Yield | | | |

追加检验（**必须通过工具精确计算，禁止心算**）：

```bash
# 跨币种（港股/美股）折算前，先用 python tools/common/fx_rate.py --code USDCNY,HKDCNY 获取实时汇率，勿用固定汇率
python tools/common/financial_rigor.py three-scenario \
  --price {股价} --eps {EPS} --shares {股本亿} \
  --growth {乐观} {中性} {悲观} --pe {乐观PE} {中性PE} {悲观PE} --currency {币种}
```

- 三情景下的估值区间（取工具输出结果）
- 如果判断有误，在当前价格买入最多亏多少？
- 股价腰斩你敢加仓吗？

**评分标准**（★1-5）：
- ★★★★★：相对内在价值打5折以下，极端安全边际
- ★★★★☆：打7折，有良好安全边际
- ★★★☆☆：合理估值，安全边际一般
- ★★☆☆☆：偏贵，安全边际不足
- ★☆☆☆☆：严重高估

---

#### 第六关：仓位与决策纪律（防止情绪失控）

检查以下情绪信号：
- 是否因为FOMO想买？
- 是否因为别人推荐才想买？
- 如果停牌5年你能接受吗？
- 买入论述能否用200字以内写清楚？

---

### 第四步：镜子测试

对每家公司写出镜子测试语句：

> "我以 ___元 买入 ___公司，因为：
> 1. 这门生意的本质是___，我理解它；
> 2. 它的护城河是___，而且在变宽/变窄；
> 3. 管理层___，值得/不值得信赖；
> 4. 当前价格相当于内在价值的___折，有/无足够安全边际；
> 5. 即使我错了，下行风险可控/不可控，因为___。"

**5句话说不完整 = 不买。** 明确标注"通过"或"未通过"。

---

### 第五步：快速否决清单

对每家公司逐条检查，触发任何一条直接标注为"否决"：

- [ ] 说不清楚这家公司怎么赚钱
- [ ] 连续3年自由现金流为负且看不到改善
- [ ] 管理层有诚信污点
- [ ] 竞争优势正在被不可逆侵蚀
- [ ] 需要靠"下一个接盘者出更高价"来赚钱（博傻）
- [ ] 无法承受这笔投资归零的后果
- [ ] 买入理由主要是"别人都在买"或"最近涨得好"
- [ ] 无法用200字以内写清楚买入理由

---

### 第六步：输出总览对比表（多公司时必须输出）

当分析多家公司时，必须生成对比总览表：

| 公司 | Checklist通过？ | 能力圈 | 好生意 | 护城河 | 管理层 | 安全边际 | 核心结论 |
|------|----------------|--------|--------|--------|--------|---------|---------|
| | | ★☆☆☆☆ | ★☆☆☆☆ | ★☆☆☆☆ | ★☆☆☆☆ | ★☆☆☆☆ | |

---

### 第七步：最终结论与写入文件

对每家公司给出明确结论（不回避）：
- ✅ **通过 Checklist**（X/6关）— 可以进入深度研究阶段
- ❌ **未通过 Checklist** — 说明哪条红线被触发
- ❓ **灰色地带** — 说明关键争议点是什么，投资者需要自行判断什么
- N/A — 未上市/无法买入

将完整报告写入 `reports/{公司名}-checklist-{YYYYMMDD}.md`

---

## 输出格式要求

1. 每家公司独立成章，包含：六关评分表 + 核心数据表 + 关键风险（3-5条）+ 镜子测试 + 明确结论
2. 多公司时在最后附总览对比表
3. 所有评分必须使用★符号（★1-5），不含半星
4. 数据必须标注来源时间，估计值必须注明"估计"
5. 文末附结语，呼应巴菲特名言："投资的第一条规则是不要亏损"
6. 语言风格：直接、犀利、不说废话。用巴菲特/芒格/段永平的语录穿插点评

---

## 关键原则

- **宁可错过，不可做错**：Checklist的目标是排除坏选择，不是找到最好的
- **诚实面对能力圈**：看不懂就说看不懂，不要勉强分析
- **安全边际是生命线**：好公司买贵了也会亏钱
- **镜子测试不可跳过**：说不清楚理由就不买，没有例外

---

## 工具使用指南

### 本地数据获取工具

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票信息查询 | `python tools/a_share/stock_info.py --search 紫金矿业` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 601899` |
| A股 | `tools/a_share/stock_financial_batch.ps1` | 批量财务指标（多公司对比用） | `powershell -File tools/a_share/stock_financial_batch.ps1 -codes "601899,000960"` |
| A股 | `tools/a_share/stock_quote.py` | 历史股价 | `python tools/a_share/stock_quote.py --code 601899` |
| A股 | `tools/a_share/stock_screen.py` | 质量筛选7条指标 | `python tools/a_share/stock_screen.py --code 601899` |
| 港股 | `tools/hk_stock/stock_financial.py` | 港股信息与财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| 港股 | `tools/hk_stock/stock_quote.py` | 港股历史K线 | `python tools/hk_stock/stock_quote.py --code 00700` |
| 港股 | `tools/hk_stock/stock_screen.py` | 港股质量筛选 | `python tools/hk_stock/stock_screen.py --code 00700` |
| 美股 | `tools/us_stock/stock_info.py` | 美股信息查询 | `python tools/us_stock/stock_info.py --search Apple` |
| 美股 | `tools/us_stock/stock_financial.py` | 美股财务指标 | `python tools/us_stock/stock_financial.py --code AAPL` |
| 美股 | `tools/us_stock/stock_quote.py` | 美股行情数据 | `python tools/us_stock/stock_quote.py --code AAPL` |

**Python路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

**数据源**：东方财富、新浪财经、巨潮资讯（A股）；东方财富、新浪财经（港股）；yfinance（美股）

详细使用说明请参考：
- **A股工具**：[docs/A股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/A股工具使用指南.md)
- **港股工具**：[docs/港股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/港股工具使用指南.md)
- **美股工具**：[docs/美股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/美股工具使用指南.md)
- **国际货币汇率**（跨市场估值/市值统一口径折算）：`tools/common/fx_rate.py`，详见 A股工具使用指南汇率章节

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证、三情景估值） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |

**关键计算命令**：

```bash
# 估值指标验证
python tools/common/financial_rigor.py verify-valuation \
  --price {股价} --eps {EPS} --bvps {每股净资产} --fcf-per-share {每股FCF} --dividend {每股股息}

# 三情景估值模型
python tools/common/financial_rigor.py three-scenario \
  --price {股价} --eps {EPS} --shares {股本亿} \
  --growth {乐观} {中性} {悲观} --pe {乐观PE} {中性PE} {悲观PE} --currency {币种}
```

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
| `tools/common/doubao_search.py` | 豆包搜索（推荐首选，支持财务/内容/导出/站点过滤） | `python tools/common/doubao_search.py "腾讯 护城河" --finance --need-content --time-range month` |
| `tools/common/tavily_search.py` | Tavily 搜索（非境内上市辅助，支持高级搜索） | `python tools/common/tavily_search.py "Apple AAPL competitive advantage" --max-results 5` |
| `tools/common/web_search.py` | 阿里云百炼搜索 | `python tools/common/web_search.py "紫金矿业 最新消息"` |

**搜索规范**（必须遵守）：
1. **时效性优先**：使用 `--time-range month/week` 限制时间范围，优先获取最新信息，避免使用过时数据
2. **数据源日期**：搜索结果必须包含数据来源日期；过时数据须明确标注时效性说明
3. **双源验证**：非境内上市公司须 Doubao + Tavily 双源验证
4. **多角度搜索**：从竞争格局、护城河、管理层、最新动态等多维度收集信息
5. **信息缺口标注**：关键信息缺失时标注"信息不足"，不得用推测填充

### 报告审核工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/report_audit.py` | 报告数据抽检与审核 | `python tools/common/report_audit.py extract --report reports/xxx.md` |

---

## 报告输出规范

- **单公司报告**：`reports/{公司名}/{公司名}-checklist-{YYYYMMDD}.md`
- **多公司对比报告**：`reports/多公司对比-checklist-{YYYYMMDD}.md`
- 报告必须包含：交易所、板块、上市日期、上市年限等信息
- 数据截止日期必须在报告头部明确标注

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 关键财务数据必须至少来自两个独立来源进行交叉验证
- 所有估计值必须明确标注"估计"
- 市值必须手算校验：股价 × 总股本
- 货币单位要明确（港币/人民币/美元），防止混淆
- PE/ROE等指标用 `tools/common/financial_rigor.py` 精确计算，禁止LLM心算
- 网络搜索须使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 非境内上市公司须 Doubao + Tavily 双源验证

---

## 局限性

1. **网络限制**：WebSearch/WebFetch 在中国大陆不可用，需使用本地搜索工具
2. **数据源覆盖**：本地工具覆盖A股、港股、美股，但美股数据源依赖 yfinance
3. **实时性**：本地工具数据可能滞后1-2天，最新财报建议查原始来源
4. **港股接口稳定性**：东方财富港股接口在中国大陆网络连接不稳定（已内置重试机制）
5. **信息稀缺公司**：对于C级公司（信息稀缺），无法保证分析完整性
6. 不构成投资建议，仅供学习研究参考

---

## 与其他Skill的关系

- **数据支撑**：使用 `financial-data` 技能的数据源规范和交叉验证流程
- **深度研究**：通过 Checklist 后可使用 `investment-research` 技能进行完整投资研究
- **管理层深化**：管理层评估部分可深化为 `management-deep-dive` 技能
- **质量筛选**：研究前可先用 `quality-screen` 技能快速筛选
- **财报跟踪**：研究后可用 `thesis-tracker` 技能持续跟踪
