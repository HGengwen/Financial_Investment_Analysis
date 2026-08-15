---
name: management-deep-dive
description: "管理层纵深研究：买股票就是买人。对指定公司进行管理层深度研究，评估诚信度、战略执行能力、资本配置能力、治理结构等核心维度。"
disable-model-invocation: true
---

# 管理层纵深研究：买股票就是买人

对 $ARGUMENTS 进行管理层深度研究。

**支持输入格式**：`公司名` 或 `人名 公司名`，例如：`美团`、`王兴 美团`、`黄仁勋 英伟达`

> "买股票就是买人。找到你信任的人，然后长期持有。" —— 段永平
>
> "评估管理层，要看他们在没人看着的时候做什么。" —— 巴菲特

## 设计理念

大多数投资分析对管理层的评估停留在表面：履历、持股比例、薪酬。但巴菲特花大量时间**和管理层吃饭聊天**，李录说**他投资的本质是投人**，段永平说**买股票就是买人**。

本Skill是 `/investment-research` 第五步管理层评估的**深化版**。当标准投资研究中管理层评分不确定（★★★或以下）、或管理层是核心投资逻辑时，使用本Skill做纵深研究。

AI无法和管理层吃饭，但可以通过公开信息做到：
- **追踪管理层的话与做是否一致**（承诺vs兑现）
- **分析每一笔重大资本配置决策的回报**
- **从困难时期的决策中推断品格**
- **通过员工/商家/客户的反馈侧面验证**

---

## 执行流程

### 第一步：识别关键管理层并启动并行数据收集

使用网络搜索工具确认以下关键人物：

| 角色 | 姓名 | 任期 | 背景 | 持股/期权 |
|------|------|------|------|----------|
| CEO/董事长 | | | | |
| CFO | | | | |
| 创始人（如不在位） | | | | |
| 实际控制人（如不同于CEO） | | | | |
| 其他关键高管 | | | | |

**注意**：区分"谁在做决策"和"谁的名字在头衔上"。有些公司创始人虽然卸任但仍是灵魂人物（如黄峥之于拼多多）。

**识别上市地点**：

首先搜索确认公司的上市情况：
- 是否在A股、港股、美股等多个市场上市？
- 各市场的股票代码是什么？

**常见多地上市情况**：
- **A+H股**：紫金矿业（A股:601899，H股:02899）、中国移动（A股:600941，H股:00941）
- **港股+美股ADR**：阿里巴巴（港股:09988，美股:BABA）、京东（港股:09618，美股:JD）
- **A股+港股+美股**：百济神州（A股:688235，港股:06160，美股:BGNE）

**使用股权结构工具获取持股数据**：

根据上市情况，选择相应的工具：

| 上市情况 | 工具 | 命令示例 |
|---------|------|---------|
| 仅A股 | `tools/common/report_hub.py`（财报下载与提取） | `python tools/common/report_hub.py ensure --code 601899 --report-type annual` |
| 仅港股 | `tools/hk_stock/stock_financial.py` | `python tools/hk_stock/stock_financial.py --financial 00700` |
| A+H股 | **同时使用两个工具** | 见下方详细说明 |
| 港股+美股ADR | **港股工具 + 美股工具/搜索** | 港股：`python tools/hk_stock/stock_financial.py --financial 09988`<br>美股：`python tools/us_stock/stock_info.py --search Alibaba` |

**A+H股股权结构综合分析**：

对于A+H股两地上市的公司，需要**同时获取A股和港股的股权结构数据**，进行综合分析：

```bash
# 1. 获取A股股权结构数据
python tools/a_share/stock_equity.py --code 601899 --export

# 2. 获取港股财务指标数据（包含股权结构）
python tools/hk_stock/stock_financial.py --financial 02899

# 3. 搜索两地上市公司的股权结构差异
python tools/common/doubao_search.py "紫金矿业 A股 H股 股权结构 差异" --time-range month
```

**返回数据包括**：
- 前十大股东（总股本口径）
- 前十大流通股东（流通股本口径）
- 股本结构历史变动
- 公司基础信息
- **A股与H股股本占比**（对于A+H股公司）

确认关键人物后，使用 Task 工具启动多个后台 Agent **并行**收集以下数据：
1. Agent 1：CEO公开发言与预测记录（股东信、电话会、采访、社交媒体）
2. Agent 2：资本配置决策记录（并购、回购、分红、新业务投资）
3. Agent 3：治理结构与薪酬（股权结构、关联交易、高管薪酬）
4. Agent 4：侧面验证信息（员工评价、客户反馈、行业口碑）

### 第二步：CEO能力圈评估

#### 2.1 战略眼光

搜索CEO过去5年的公开发言（股东信、电话会、采访、社交媒体），提取其对以下问题的判断：

| 时间 | CEO的判断/预测 | 实际结果 | 准确度 |
|------|--------------|---------|:------:|
| | "我们认为X市场会..." | X市场实际... | ✅/❌ |
| | "未来3年我们的重点是..." | 实际执行... | ✅/❌ |

**关键问题**：
- CEO有没有做过超前于市场的正确判断？
- CEO有没有在大家都看好的时候保持冷静？
- CEO对行业趋势的理解是跟随市场还是独立思考？

#### 2.2 执行能力

| 维度 | 评估 | 证据 |
|------|------|------|
| 战略到落地 | 说了的事做到了吗？ | |
| 组织能力 | 能不能吸引和留住人才？ | |
| 危机处理 | 遇到困难时怎么应对？ | |
| 迭代速度 | 犯错后纠正的速度快吗？ | |

### 第三步：诚信度评估（最重要）

**巴菲特**："我们寻找三种品质：正直、智慧和精力。如果没有第一种，后两种会害死你。"

#### 3.1 承诺vs兑现追踪

从过去3年的财报电话会、股东信、公开采访中，提取管理层做过的**具体承诺**：

**使用财报下载工具获取年报**：

报告获取与提取统一使用 report_hub.py（带下载与提取缓存），详见 [报告下载与提取统一入口](../tools-scripts/report-hub.md)。

对于A股公司，使用 `tools/common/report_hub.py` 获取年报、半年报、季报PDF：

```bash
# 获取最新年报
python tools/common/report_hub.py ensure --code 601899 --report-type annual

# 获取最新半年报
python tools/common/report_hub.py ensure --code 601899 --report-type semiannual

# 获取最新季报
python tools/common/report_hub.py ensure --code 601899 --report-type quarterly
```

**下载的财报统一保存到 cninfo_reports/ 目录**：
- 文件命名：`{股票代码}_{年份}{报告类型}.pdf`
- 示例：`601899_2025年报.pdf`

**从下载的年报中提取管理层承诺**（统一用 `report_hub.py extract`，详见 [报告下载与提取统一入口](../tools-scripts/report-hub.md)）：

| # | 时间 | 承诺内容 | 承诺场合 | 兑现情况 | 评价 |
|---|------|---------|---------|---------|------|
| 1 | | "我们将在2025年实现X业务盈利" | 2024年报电话会 | | ✅/⚠️/❌ |
| 2 | | "我们计划回购$X亿" | 2024年股东信 | | ✅/⚠️/❌ |

**兑现率统计**：

| 承诺兑现率 | 评价 |
|:---------:|------|
| >80% | 优秀——说到做到 |
| 60-80% | 合格——大方向对但执行有偏差 |
| 40-60% | 令人担忧——承诺过多交付不足 |
| <40% | 严重问题——不可信赖 |

#### 3.2 困难时期的表现

搜索公司历史上遭遇的重大危机/困难（股价暴跌、业绩miss、监管冲击、竞争加剧），分析管理层的应对：

| 危机事件 | 时间 | 管理层反应 | 事后回看的评价 |
|---------|------|-----------|-------------|

**关注**：
- 是主动沟通还是躲避？
- 是归因内部还是甩锅外部？
- 是趁机做困难但正确的事，还是选择短期讨好市场？

#### 3.3 对利益相关方的态度

| 利益相关方 | 管理层态度 | 证据 | 评价 |
|-----------|-----------|------|------|
| 股东 | 尊重/忽视/利用 | | |
| 员工 | 善待/压榨/漠视 | | |
| 客户/用户 | 以客户为中心/短期榨取 | | |
| 商家/供应商 | 公平合作/极端压价 | | |
| 监管/社会 | 合规配合/打擦边球 | | |

**李录**："对利益相关方的态度决定了企业的长期生命力。短期压榨能提升效率，但长期会损害生态。"

### 第四步：资本配置能力

这是巴菲特最看重的管理层能力——**每赚一块钱，管理层能把它变成多少钱？**

#### 4.1 资本配置决策记录

搜索公司过去5年的重大资本配置决策，逐笔评估：

**并购记录**：

| 时间 | 收购标的 | 金额 | 战略逻辑 | 事后回报 | 评分(1-5) |
|------|---------|------|---------|---------|:---------:|

**回购记录**：

使用 `tools/common/financial_rigor.py verify-valuation` 校验回购时和当前的PE等估值指标。

| 时间 | 回购金额 | 平均回购价 | 当时PE | 事后回看 | 评分(1-5) |
|------|---------|-----------|:------:|---------|:---------:|

**分红记录**：

| 年份 | 分红金额 | 分红率 | 同期FCF | 是否可持续 |
|------|---------|:------:|---------|:---------:|

**新业务投资**：

| 时间 | 投资领域 | 累计投入 | 当前状态 | 回报评估 | 评分(1-5) |
|------|---------|---------|---------|---------|:---------:|

#### 4.2 资本配置评分

| 维度 | 评分(1-5) | 说明 |
|------|:---------:|------|
| 并购纪律 | | 是否在合理价格收购？收购后整合如何？ |
| 回购时机 | | 是否在低估时回购、高估时停止？ |
| 分红合理性 | | 分红率是否与FCF匹配？ |
| 新业务投资 | | 成功率如何？止损纪律如何？ |
| 现金管理 | | 现金储备是否合理？是否囤积过多？ |
| **综合评分** | | |

**巴菲特标准**：理想的管理层在有好机会时果断投资，没有好机会时积极回购/分红，永远不做高价并购。

### 第五步：治理结构评估

#### 5.1 股权结构

**识别多地上市情况**：

首先搜索确认公司是否在多个市场上市：

```bash
# 搜索公司上市情况
python tools/common/doubao_search.py "{公司名} A股 港股 股票代码" --time-range month
```

**使用股权结构工具获取详细数据**：

根据上市情况，选择相应的工具：

**情况1：仅A股上市**
```bash
python tools/a_share/stock_equity.py --code 601899 --export
```

**情况2：仅港股上市**
```bash
python tools/hk_stock/stock_financial.py --financial 00700
```

**情况3：A+H股两地上市（需要综合分析）**

对于A+H股两地上市的公司，股权结构分析需要额外关注：

```bash
# 1. 获取A股股权结构数据
python tools/a_share/stock_equity.py --code 601899 --export

# 2. 获取港股财务指标数据
python tools/hk_stock/stock_financial.py --financial 02899

# 3. 获取A股最新股价（用于A股/H股溢价计算）
python tools/a_share/stock_quote.py --code 601899

# 4. 获取H股最新股价（用于A股/H股溢价计算）
python tools/hk_stock/stock_quote.py --code 02899

# 5. 搜索两地上市的股权结构差异和H股占比
python tools/common/doubao_search.py "{公司名} A股 H股 股权结构 占比" --time-range month
```

**A+H股股权结构分析要点**：

| 分析维度 | 关注点 | 风险评估 | 数据来源 |
|---------|-------|---------|---------|
| **H股占比** | H股占总股本比例，是否影响控制权？ | H股占比过高可能导致控制权分散 | 股权结构工具+网络搜索 |
| **A股/H股溢价** | A股相对H股的溢价水平，是否合理？获取具体股价数据，计算溢价率 | 溢价过高可能存在套利压力 | A股：`stock_quote.py`<br>H股：`stock_quote_hk.py` |
| **流通性差异** | A股和H股的流通性差异 | 流通性差的市场可能影响股价表现 | 网络搜索 |
| **投资者结构** | A股（国内投资者）vs H股（国际投资者） | 投资者结构差异可能导致股价波动 | 网络搜索 |
| **分红差异** | A股和H股的分红是否一致？ | 分红差异可能引发套利 | 公司公告 |

**A+H股股权结构分析表格**：

| 项目 | 详情 | 风险评估 |
|------|------|---------|
| 是否有AB股/超级投票权？ | | |
| 创始人/实控人持股比例？ | | |
| 是否有VIE结构？ | | |
| 独立董事是否真正独立？ | | |
| 大股东近期增减持记录？ | | |
| 5年股本膨胀情况？ | 从股本变动数据中计算 | |
| **是否多地上市？** | A+H股、港股+美股ADR等 | |
| **H股占比** | 仅A+H股公司需分析（例如：22.52%） | 控制权分散风险 |
| **A股股价** | 仅A+H股公司需填写（例如：29.25元） | 获取日期需标注 |
| **H股股价** | 仅A+H股公司需填写（例如：30.56港元） | 获取日期需标注 |
| **A股/H股溢价率** | 仅A+H股公司需计算（例如：-7.0%） | 负值表示H股溢价 |
| **两地分红一致性** | 仅A+H股公司需分析 | 套利风险 |

**注**：A股/H股溢价率计算公式：
- A股价格（元）vs H股价格（港元）
- A/H溢价率 = (A股价格 - H股价格 × 汇率) / (H股价格 × 汇率) × 100%
- **实时汇率**：计算前先用 `python tools/common/fx_rate.py --code HKDCNY`（1港币=x人民币）获取实时汇率，**不要用固定值**（如旧的"1港币≈0.91"）

**返回数据包括**：
- 前十大股东（总股本口径）
- 前十大流通股东（流通股本口径）
- 股本结构历史变动（可用于分析5年股本膨胀情况）
- 公司基础信息
- **A股与H股股本占比**（对于A+H股公司）

#### 5.2 薪酬合理性

| 高管 | 年度总薪酬 | 占公司净利润比 | 与同行对比 | 是否合理 |
|------|-----------|:------------:|:---------:|:-------:|

**关注**：激励结构是否与长期股东利益一致？还是鼓励短期行为？

#### 5.3 关联交易

| 关联方 | 交易内容 | 金额 | 是否公允 | 风险评估 |
|--------|---------|------|:-------:|---------|

### 第六步：侧面验证

AI无法和管理层面对面交流，但可以通过公开渠道的侧面信息验证。**注意**：以下信息取决于公开可搜索的内容，可能不完整，标注信息来源和可得性。

#### 6.1 员工视角

搜索 Glassdoor评分摘要、知乎讨论等**可公开搜索**的员工评价（脉脉等需登录的平台标注"用户可自行补充"）：

| 维度 | 评分趋势 | 关键反馈 |
|------|---------|---------|
| 企业文化 | | |
| 管理层评价 | | |
| 工作强度 | | |
| 薪酬满意度 | | |
| 发展前景 | | |

#### 6.2 客户/商家视角

搜索App Store评分、消费者投诉、商家论坛：

| 维度 | 评分/趋势 | 关键反馈 |
|------|----------|---------|
| 产品满意度 | | |
| 客户服务 | | |
| 商家/供应商关系 | | |

#### 6.3 行业口碑

搜索行业论坛、社交媒体，了解同行和业内人士对该管理层的评价。

### 第七步：CEO离开后的情景分析

**巴菲特**："好公司应该是傻瓜都能经营的——因为迟早会有傻瓜来经营。"

| 问题 | 回答 |
|------|------|
| 如果CEO明天离开，公司能正常运转吗？ | |
| 现有管理团队的深度如何？有没有明确的继任者？ | |
| 公司的竞争优势是依赖CEO个人，还是依赖组织/系统？ | |
| 历史上的管理层交接是否顺利？ | |

### 第八步：输出管理层评估报告

#### 报告结构

```
一、关键人物速览（表格）
二、诚信度评估
   - 承诺兑现率
   - 困难时期表现
   - 对利益相关方态度
三、能力评估
   - 战略眼光（预判准确度）
   - 执行能力
   - 资本配置记录
四、治理结构
   - 股权结构风险
   - 薪酬合理性
   - 关联交易
五、侧面验证
   - 员工视角
   - 客户/商家视角
六、综合评分与结论
```

#### 综合评分

| 维度 | 权重 | 评分(1-5) | 加权 |
|------|:----:|:---------:|:----:|
| 诚信度 | 35% | | |
| 战略与执行能力 | 25% | | |
| 资本配置能力 | 25% | | |
| 治理结构 | 15% | | |
| **综合评分** | 100% | | |

#### 段永平的"买人"标准

> 回答以下三个问题：
> 1. **这个人是否正直？**（诚实、不占股东便宜）
> 2. **这个人是否有能力？**（战略眼光+执行力+资本配置）
> 3. **你愿意把钱交给这个人管10年吗？**
>
> 三个都是"是" = ★★★★★（5分）
> 前两个是"是" = ★★★★（4分）
> 只有第一个是"是" = ★★★（3分）
> 第一个不是"是" = ★（1分，不投）

### 第九步：保存报告

将报告写入 `reports/{公司名}/{公司名}-management-{YYYYMMDD}.md`，例如 `reports/腾讯/腾讯-management-20260409.md`

---

## 工具使用指南

### 本地数据获取工具

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票代码查询 | `python tools/a_share/stock_info.py --search 紫金矿业` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 601899` |
| A股 | `tools/a_share/stock_quote.py` | 实时行情与历史K线 | `python tools/a_share/stock_quote.py --code 601899` |
| A股 | `tools/common/report_hub.py` | 财报下载与提取统一入口（带缓存） | `python tools/common/report_hub.py ensure --code 601899 --report-type annual` |
| A股 | `tools/a_share/stock_equity.py` | 股权结构数据 | `python tools/a_share/stock_equity.py --code 601899` |
| A股 | `tools/a_share/stock_screen.py` | 质量筛选7条指标 | `python tools/a_share/stock_screen.py --code 601899` |
| 港股 | `tools/hk_stock/stock_info.py` | 港股信息查询 | `python tools/hk_stock/stock_info.py --search 腾讯` |
| 港股 | `tools/hk_stock/stock_financial.py` | 港股财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| 港股 | `tools/hk_stock/stock_quote.py` | 港股实时行情与历史K线 | `python tools/hk_stock/stock_quote.py --code 00700` |
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
- **国际货币汇率**（跨市场估值/市值统一口径折算）：`tools/common/fx_rate.py`，详见 [A股工具使用指南汇率章节](file:///f:/Financial_Investment_Analysis/docs/A股工具使用指南.md)

**⚠️ 汇率获取强制规范**：任何涉及汇率折算（A/H溢价、市值统一口径、跨币种估值对比）的场景，**必须首选 `python tools/common/fx_rate.py --code USDCNY,HKDCNY` 获取实时汇率**（Akshare 优先、yfinance 回退）。**仅当 `fx_rate.py` 返回失败（退出码非0 / 数据为空）时，才可回退调用 `doubao_search`/`exa`/`anysearch` 等搜索工具查询汇率，且回退搜索结果必须双源验证**（同一汇率至少两个独立来源交叉一致）方可使用。汇率不是网络信息，是精确数据，须优先用专用工具获取。

### 财报下载与股权结构工具

管理层研究的核心数据来源是年报 PDF（提取管理层承诺、战略发言、资本配置记录）。报告获取与提取统一使用 report_hub.py（带下载与提取缓存），详见 [报告下载与提取统一入口](../tools-scripts/report-hub.md)。A股使用 `tools/common/report_hub.py`：

| 功能 | 命令示例 |
|------|---------|
| 获取年报 | `python tools/common/report_hub.py ensure --code 601899 --report-type annual` |
| 获取半年报 | `python tools/common/report_hub.py ensure --code 601899 --report-type semiannual` |
| 获取季报 | `python tools/common/report_hub.py ensure --code 601899 --report-type quarterly` |
| 股权结构数据 | `python tools/a_share/stock_equity.py --code 601899` |
| 提取 Markdown | `python tools/common/report_hub.py extract --code 601899 --report-type annual` |
| 导出Excel | `python tools/a_share/stock_equity.py --code 601899 --export` |

**文件保存位置**：统一保存到 `./cninfo_reports/`，命名格式 `{股票代码}_{年份}{报告类型}.pdf`

**返回数据包括**：前十大股东、前十大流通股东、股本结构历史变动、公司基础信息、A股与H股股本占比（A+H股公司）

**在管理层研究中的应用**：
1. **承诺追踪**：下载年报，查找管理层承诺，追踪兑现情况
2. **战略发言分析**：从年报、半年报中提取管理层战略判断
3. **困难时期表现**：下载历史年报，分析危机应对
4. **资本配置记录**：从年报中提取并购、回购、分红决策
5. **股本变动追踪**：查看5年股本膨胀情况，评估股东友好度

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证、回购估值等） | `python tools/common/financial_rigor.py verify-valuation --help` |

**管理层研究中的应用**：回购记录分析时，使用 `verify-valuation` 校验回购时和当前的PE等估值指标；市值必须手算校验（股价 × 总股本）。

### 网络搜索工具

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。完整角色定位、市场×场景选型矩阵、命令速查、多源验证示例见 [web-search-tools](../tools-scripts/web-search-tools.md)。

**管理层研究场景下的搜索选型**（按公司上市地点，引用 web-search-tools.md 矩阵）：
- A股：管理层背景/公开发言/治理结构 → `anysearch --tag finance` 主 + `doubao --finance --need-content` 辅；员工评价/客户反馈 → `doubao` 主
- 港股：管理层讨论/分析师点评 → `tavily` 主 + `doubao` 辅；公告/回购/薪酬 → `doubao --sites hkexnews.hk` 主 + `tavily` 辅；双源 doubao+tavily
- 美股：SEC filings/CEO发言/治理结构 → `exa --type deep` 主 + `tavily` 辅；新闻/舆情/分析师点评 → `doubao` 主 + `anysearch --zone intl` 辅；双源 exa+doubao

**搜索规范**（管理层研究特有）：
- **时效性优先**：管理层信息须覆盖最近12个月动态，使用 `--time-range month/week` 限制时间范围，避免使用过时数据
- **多维度收集**：从管理层背景、公开发言、治理结构、资本配置、员工评价、客户反馈六个维度分别检索，不可依赖单次搜索
- **双源验证**：非境内上市公司须按市场矩阵双源验证（A股 anysearch+doubao；港股 doubao+tavily；美股 exa+doubao）
- **精确数据用专用工具，禁止用搜索**：汇率用 `fx_rate.py`、财务计算用 `financial_rigor.py`、财务指标用 `stock_financial.py`。查询汇率等精确数值**必须首选专用工具**，仅当 `fx_rate.py` 返回失败时才可回退 `doubao_search`/`exa`/`anysearch`，且回退搜索结果须**双源验证**（见上文"汇率获取强制规范"）
- **信息缺口标注**：关键信息缺失时标注"信息不足"，不得用推测填充——侧面信息（员工/客户反馈）尤其容易不完整
- **数据源日期**：搜索结果必须包含数据来源日期；过时数据须明确标注时效性说明

**典型搜索场景**（管理层研究专属关键词）：

| 场景 | 示例搜索关键词 | 目的 |
|------|---------------|------|
| 管理层背景信息 | `腾讯 马化腾 背景` | 了解CEO履历 |
| 管理层公开发言 | `马化腾 股东信 2025` | 查找CEO发言记录 |
| 公司治理结构 | `腾讯 股权结构 AB股` | 了解治理结构 |
| 资本配置决策 | `腾讯 回购 2025` | 查找资本配置记录 |
| 员工评价 | `腾讯 Glassdoor 员工评价` | 侧面验证管理层 |
| 客户反馈 | `腾讯 客户投诉 App Store` | 了解客户满意度 |

### PDF文档内容提取（经 report_hub extract 统一调用）

下载的财报 PDF 提取管理层承诺、战略发言等内容时，统一使用 `tools/common/report_hub.py extract`（内置类型检测、自动乱码检测 + OCR 回退与提取缓存），返回失败（退出码非0 / success=false / 扫描件）时才按 report-hub.md 回退 Poppler 工具集。

```bash
# 提取 Markdown（含表格）并搜索管理层承诺与战略发言（report_hub 自动检测 PDF 类型）
python tools/common/report_hub.py extract --code 601899 --report-type annual

# 强制 OCR 提取（适用于提取乱码时，如 Adobe-CNS1 繁体中文 PDF）
python tools/common/report_hub.py extract --code 601899 --report-type annual --force-ocr --ocr-langs chi_tra+eng
```

**典型工作流**：

```bash
# 1. 获取年报PDF
python tools/common/report_hub.py ensure --code 601899 --report-type annual

# 2（首选）：提取 Markdown 并搜索管理层承诺与战略发言（report_hub 内置类型检测 + 提取缓存）
python tools/common/report_hub.py extract --code 601899 --report-type annual

# 3（OCR 回退）：若提取乱码，强制 OCR
python tools/common/report_hub.py extract --code 601899 --report-type annual --force-ocr --ocr-langs chi_tra+eng

# 4（回退）：若 report_hub extract 返回失败，回退 Poppler（命令详见 report-hub.md）
```

**注意事项**：
- 首选 `pdf_extract.py` 提取文字与表格；返回失败时才回退 Poppler（详见 [PDF文档内容提取技能](../tools-scripts/pdf-extraction.md)）
- A股年报常为扫描版PDF（图像格式），`pdf_extract.py` 会返回 scanned 标志，回退后需使用 `pdftoppm` 渲染为图像或 OCR 处理
- 提取的数据必须与其他来源交叉验证
- Windows 用户需安装 [Poppler for Windows](http://blog.alivate.com.au/poppler-windows/)
- 完整使用说明请参考 [PDF文档内容提取技能](../tools-scripts/pdf-extraction.md)

### 多地上市公司数据获取

对于多地上市公司，需**综合获取多个市场的数据**进行分析。常见情况：

| 上市类型 | 典型公司 | 数据获取策略 |
|---------|---------|------------|
| A+H股 | 紫金矿业（A股:601899，H股:02899） | A股工具为主 + 港股工具补充 |
| 港股+美股ADR | 阿里巴巴（港股:09988，美股:BABA） | 港股工具为主 + 美股工具/搜索补充 |
| A股+港股+美股 | 百济神州（A股:688235，港股:06160，美股:BGNE） | A股工具为主 + 港股/美股工具补充 |

**A+H股数据获取流程**：

```bash
# 1. 搜索确认上市情况
python tools/common/doubao_search.py "紫金矿业 A股 H股 股票代码" --time-range month

# 2. 获取A股股权结构数据
python tools/a_share/stock_equity.py --code 601899 --export

# 3. 获取港股财务指标数据
python tools/hk_stock/stock_financial.py --financial 02899

# 4. 获取A股和H股最新股价（用于溢价计算）
python tools/a_share/stock_quote.py --code 601899
python tools/hk_stock/stock_quote.py --code 02899

# 5. 搜索H股占比和两地上市影响
python tools/common/doubao_search.py "紫金矿业 H股占比 A股H股 差异" --time-range month
```

**A+H股股权结构分析要点**：

| 分析维度 | 数据来源 | 关注点 |
|---------|---------|-------|
| 股权结构 | A股工具（`stock_equity.py`） | 前十大股东、实控人持股比例 |
| H股占比 | 港股工具+网络搜索 | H股占总股本比例，是否影响控制权 |
| A股/H股溢价率 | 手动计算 | (A股价格 - H股价格 × 汇率) / (H股价格 × 汇率) × 100% |
| 股本变动 | A股工具 | 5年股本膨胀情况 |
| 分红差异 | 网络搜索+公司公告 | A股和H股的分红是否一致 |

**注**：计算 A/H 溢价率前，先用 `python tools/common/fx_rate.py --code HKDCNY`（1港币=x人民币）获取实时汇率，不要用固定值。

**报告输出要求**（A+H股公司）：
- 关键人物速览表格中标注上市情况，如 `紫金矿业（A股:601899，H股:02899）`
- 治理结构评估部分增加：H股占比、A股股价、H股股价、A股/H股溢价率、两地分红一致性
- 风险评估部分增加：多地上市风险（H股占比、溢价套利、监管差异等）

### 报告审核工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/report_audit.py` | 报告数据抽检与审核 | `python tools/common/report_audit.py extract --report reports/xxx.md` |

---

## 报告输出规范

### 报告目录结构

```
reports/
├── {公司名}/                        — 公司所有研究报告
│   ├── {公司名}-management-{YYYYMMDD}.md — 管理层深度研究报告
│   ├── {公司名}-research-{YYYYMMDD}.md   — 其他研究报告
│   └── {公司名}-quality-screen-{YYYYMMDD}.md — 去劣筛选报告
```

### 报告命名规范

- 管理层研究：`reports/{公司名}/{公司名}-management-{YYYYMMDD}.md`

---

## 注意事项

- **诚信是一票否决项** — 能力不足可以学习，品格有问题无法修复
- **看行为不看言辞** — 管理层说什么不重要，做了什么才重要
- **在困难中看真相** — 顺风时谁都是好CEO，逆风时才见真功夫
- **资本配置是终极考试** — 赚钱容易，把赚到的钱配置好难
- **不要爱上管理层** — 保持客观，即使是你欣赏的人也可能犯大错
- **数据必须标注来源** — 关键数据至少2个来源交叉验证
- **货币单位要明确** — 港币/人民币/美元，防止混淆
- **市值必须手算校验** — 股价 × 总股本，与报告市值对比
- **网络搜索时效性** — 使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- **报告写完后主动询问是否推送到GitHub**

---

## 局限性

1. **信息不对称**：AI无法像巴菲特那样和管理层面对面吃饭聊天，只能依赖公开信息
2. **时效性限制**：公开信息可能有延迟，最新动态可能无法及时获取
3. **侧面信息不完整**：员工评价、客户反馈等可能因平台限制而不完整
4. **主观判断风险**：尽管遵循客观原则，评分仍有一定主观性
5. **扫描版PDF限制**：A股年报常为扫描版PDF，可能无法提取文本内容
6. **多地上市复杂性**：A+H股、港股+美股ADR等股权结构分析较复杂

**管理层深度研究是投资决策的重要参考，但不是唯一依据。** 投资者应结合商业模式、财务分析、行业竞争等多个维度综合判断。

---

## 与其他Skill的关系

- **上游技能**：本Skill是 `investment-research` 第五步管理层评估的深化版
- **数据支撑**：使用 `financial-data` 技能的数据源规范和交叉验证流程
- **质量筛选**：研究前可先用 `quality-screen` 技能快速筛选
- **投资检查**：研究后可用 `investment-checklist` 技能做买入前检查
- **段永平思想**：参考 `dyp-ask` 技能理解"买人"投资思想
