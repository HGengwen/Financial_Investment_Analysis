# 景气趋势筛选（trend-tech-screen）工具链开发方案与计划

> 文档日期：2026-08-19（2026-08-25 修订，对齐最新技能文件：250日SMR/RSI(50)/技术面止损/PSG/供应链话语权科目）
> 状态：已修订；阶段推进与决策点确认见 §8
> 关联技能文件：`research\quality-screen\trend-tech-screen.md技能文件完整修改建议.md`

---

## 1. 背景

待开发的新技能 `trend-tech-screen`（景气趋势筛选）融合四位投资大师思想（欧奈尔 CAN SLIM、林奇 GARP、郑希全球景气、李进产业验证），构建 **五维加权打分（满分 100 + 奖励分）+ 地缘政治二维修正 + 估值倒推验证 + 反证清单** 的量化筛选体系，覆盖 A 股 / 港股 / 美股三市场，支持个股、行业、指数、主题四种输入模式，以及批量筛选（10-20 家）。

经与 `tools/` 路径下现有工具逐一比对，现有工具为 **数据获取型**，而本技能需要 **指标计算型** 能力，存在多处硬缺口。本文档给出工具链改造的完整方案、数据源清单与分阶段开发计划。

---

## 2. 技能文件的核心数据与计算需求

### 2.1 技能流程（四层递进）

```
第零层：产业链周期定位（前置判断，动态调权重）
  → 第一层：前置硬性淘汰（一票否决，3 条）
  → 第二层：五维加权打分（100 分 + 奖励分）
  → 第三层：地缘政治二维修正（乘数系数）
  → 估值倒推验证（不占分，红灯降级）
  → 技术面止损校验（独立否决：破 50 日线放量预警降级、破 200 日线红牌强制降级/清仓）
  → 最终评级 + 反证清单
```

### 2.2 五维打分指标明细

| 维度 | 权重 | 指标 |
|---|---|---|
| ① 景气前瞻 | 35 分（需求爆发期 42 分 / 技术跃迁期 28 分） | 订单增速（合同负债同比，12 分）、政策环境（8 分）、毛利率边际变化（8 分）、供应链话语权：应付账款周转天数 + 预付款项同比（7 分）、行业景气一致性（批量模式 ±2 分） |
| ② 研发执行力与转化 | 25 分（技术跃迁期 32 分 / 需求爆发期 18 分）+ 奖励 | MROI（主公式 + 研发滞后备选公式）、新品收入占比及溢价、落地速度、存货-研发匹配、自主替代成果（分级奖励，Level A 已量产最高 +8）、供应链备选（上限 +3） |
| ③ 人才质量与密度 | 15 分 | 人均创利增速、研发人员占比及硕博、核心团队稳定性及薪酬分位 |
| ④ 动量与市场共识 | 15 分 + 奖励 | 250 日 SMR 相对强度（5 分）、RSI(50) 中期动量（备选，5 分）、盈利预测上调次数（5 分）、低关注度溢价(+2)；技术面止损校验为独立否决项（不占分，见 2.1） |
| ⑤ 估值安全垫 | 10 分（成熟稳定期 15 分） | PEG（5 分）、PSG 市销率增长比（爆发期专用，3 分）、PE 5 年历史分位（2 分）、市值隐含业绩倒推（辅助校验） |

> 注：权重调整为配对制——需求爆发期 ①35→42 且 ②25→18；技术跃迁期 ②25→32 且 ①35→28；无法判断周期阶段时默认按"需求爆发期"权重执行。

### 2.3 能力分类

1. **财务科目获取**：合同负债、研发费用、毛利、存货周转天数、应付账款周转天数、预付款项、员工总数、开发支出、无形资产
2. **行情与动量计算**：250 日 SMR 相对强度（同板块百分位）、RSI(50)、MA50/MA200（技术面止损）、PE 历史分位、PEG、PSG、市值倒推
3. **年报文本字段抽取**：员工情况、子公司列表/注册地、新品收入占比、供应链风险、收入分部

---

## 3. 现有工具能力差距矩阵

| 技能文件指标 | 数据现状 | 缺口定性 |
|---|---|---|
| 合同负债同比（欧奈尔 C 因子） | A股/港股工具均未暴露资产负债表 | **硬缺口**（需资产负债表） |
| 毛利率边际变化 | A股 abstract ✓、港股分析指标 ✓、美股利润表 ✓ | 基本可用 |
| 研发费用（MROI 分子） | A股新浪利润表已含 ✓、美股 ✓、**港股 CLI 未暴露** | 部分缺口 |
| 存货周转天数 | 三市场均无 | **硬缺口**（需营运指标或存货/成本推算） |
| 应付账款周转天数、预付款项（供应链话语权，7 分） | 三市场均无 | **硬缺口**（需资产负债表/营运指标） |
| 员工总数（人均创利、人才密度） | 三市场均无 | **硬缺口** |
| 开发支出/无形资产（落地速度） | A股/港股无资产负债表、美股 ✓ | 部分缺口 |
| 250 日 SMR 相对强度（同板块百分位） | 行情数据 ✓，但无计算；且需板块成分截面数据（A股可复用 a_stock_cache 行业缓存） | **计算缺口 + 截面数据缺口** |
| RSI(50) / MA50 / MA200 | 行情数据 ✓，无计算 | 计算缺口 |
| 盈利预测上调次数/机构覆盖 | 美股 `--analyst` 部分 ✓；A股/港股无 | 部分缺口 |
| PEG / PE 5 年分位 / 市值倒推 | `financial_rigor.py` 均无 | 计算缺口 |
| 新品收入占比、员工情况、子公司列表、供应链风险 | 仅靠 `pdf_extract.py` 输出 markdown 后 LLM 手动挖 | **结构化缺口** |

**总体判断**：最硬的缺口集中在五个科目（合同负债、存货周转、员工数、开发支出、应付账款/预付款项）+ 四块计算（动量指标 SMR/RSI(50)/均线、估值分位/PEG/PSG、市值倒推、年报结构化抽取）。

---

## 4. 总体方案

### 4.1 现有工具扩展（A–F，6 处）

| # | 工具 | 新增功能 | 优先级 |
|---|---|---|---|
| A | `common/financial_rigor.py` | 新增 `peg`、`ps-g`（爆发期专用）、`pe-percentile`、`implied-growth`（市值倒推，含指引对照判定）四个纯计算命令 | 高（零网络依赖） |
| B | `a_share/stock_financial.py` + `a_stock_cache.py` | 暴露资产负债表（合同负债/存货/开发支出/无形资产/应付账款/预付款项）、营运指标（存货周转天数/应付账款周转天数）、员工数；支持季度数据输出；扩展缓存 | 高 |
| C | `hk_stock/stock_financial.py` | 暴露三大报表中的研发费用、合同负债、存货等科目（接口已有，仅 CLI 未接出） | 高 |
| D | 三市场 `stock_quote.py` | 新增 `--momentum` 模式输出 250 日 SMR 相对强度（同板块百分位）、RSI(50)、MA50/MA200 及量能（技术面止损）；A股增加指数行情作基准；SMR 板块成分截面方案见 5.4 | 中 |
| E | 三市场 `stock_info.py` | 增加总市值/流通市值；A股增加机构覆盖度/研报数统计 | 中 |
| F | `us_stock/stock_financial.py` | 新增 `--indicators` 模式，从已有三张报表指标化输出（毛利/研发费用/合同负债/存货周转） | 中 |

### 4.2 新增工具（G–H，2 个）

| 工具 | 定位 | 必要性 |
|---|---|---|
| G：`specialized/trend_tech_screen.py` | **景气趋势打分引擎**：聚合数据、内置五维打分（含周期权重参数，4 种周期模式，默认需求爆发期）+ 地缘修正矩阵 + 技术面止损校验（独立否决：破 50 日线预警降级、破 200 日线红牌强制降级）+ 评级映射 + 反证清单；批量模式支持两轮计算（行业通过率 >60% 集体 +2 / <30% 集体 -2）；输出结构化 JSON + Markdown（路径遵循 `reports/trend-screen/` 规范） | **强烈建议新增**。批量模式（10-20 家 × 15 项指标）若全靠 LLM 手工算，既慢又易错，且违背项目"禁止 LLM 心算"规范 |
| H：`common/annual_report_parser.py` | **年报结构化抽取器**：从 `pdf_extract.py` 的 markdown 中定向抽取员工情况、子公司列表、新品收入、供应链风险、收入分部 | 建议新增，可放第二阶段 |

### 4.3 明确不新增

- 搜索类工具（`doubao_search` 等 5 件套已够用）
- 独立的 RSI/相对强度、估值计算工具（并入现有 `stock_quote` / `financial_rigor`）
- `geo_political.py` / `supply_chain.py`（技能文件工具清单曾引用，实际不存在）：**不开发**（2026-08-25 已决策）。地缘政治评估由 `doubao_search`/`anysearch`（制裁/实体清单/国产化率搜索）替代；供应链卡点排查由 `doubao_search` + `annual_report_parser`（年报"供应链风险"章节抽取）替代；技能文件工具清单表已同步修订

---

## 5. 原始数据源清单

标注：【已验证】= 项目代码/文档已引用；【待验证】= 开发时需核对字段名与可用性。

### 5.1 A. `financial_rigor.py` 新命令

| 新命令 | 所需原始数据源 | 来源 |
|---|---|---|
| `peg` | PE（当前）、盈利增速 | 不联网；输入取自 `stock_financial`（净利润同比）与行情/市值 |
| `ps-g` | PS（当前）、营收增速 | 不联网；输入取自行情/市值（市销率）与 `stock_financial`（营收同比）；触发条件（净利率<5% 或营收增速>50%）由调用方判断后传入 |
| `pe-percentile` | PE 历史序列 | A股：`ak.stock_a_indicator_lg`（pe_ttm 历史）或 `ak.stock_zh_valuation_baidu`【待验证】；港股：`ak.stock_hk_valuation_baidu`【已验证】；美股：yfinance `history` + `financials`(EPS) 自行合成【待验证】 |
| `implied-growth` | 市值、目标 PE、净利率、TTM 营收、公司指引增速上限 | 市值=股价×股本（`stock_quote`+`stock_equity`/`stock_info`）；净利率与营收=`stock_financial`；指引增速由搜索/年报获取。命令须含 `--guidance-growth` 参数，作为红/黄/绿判定基准 |

### 5.2 B. A股 `stock_financial.py` + `a_stock_cache.py`

| 补齐科目 | 原始数据源 | 备注 |
|---|---|---|
| 合同负债、存货、开发支出、无形资产、**应付账款、预付款项** | `ak.stock_financial_report_sina(stock, symbol="资产负债表")`【与现有利润表同源】；或 `ak.stock_balance_sheet_by_report_em(symbol="SH600519")`【待验证】 | 东财版字段含"合同负债"，字段更标准 |
| 存货周转天数、**应付账款周转天数** | `ak.stock_financial_analysis_indicator(symbol, start_year)`【待验证】 | 东财财务分析指标；应付账款周转天数供供应链话语权（D 指标）使用 |
| 员工总数 | 首选雪球 `ak.stock_individual_basic_info_xq(symbol)`（含 employee_total 字段）【待验证】；备选 `ak.stock_individual_info_em(symbol)`【待验证】 | `stock_individual_info_em` 返回以市值/行业/上市时间为主，可能不含员工数，故首选雪球源 |
| 人均薪酬（现金流量表） | `ak.stock_financial_report_sina(stock, symbol="现金流量表")`【待验证】 | "支付给职工以及为职工支付的现金" |

### 5.3 C. 港股 `stock_financial.py`

| 补齐科目 | 原始数据源 | 备注 |
|---|---|---|
| 研发费用、合同负债（合约负债）、存货 | `ak.stock_financial_hk_report_em(symbol, report_type="利润表"/"资产负债表")`【已验证】 | CLI 已接入分析指标，仅未接出三大报表 |
| 财务分析指标（现有） | `ak.stock_financial_hk_analysis_indicator_em`【已验证】 | 已含毛利率/净利率/ROE |
| 员工数 | `ak.stock_individual_basic_info_hk_xq(symbol)`【已验证】 | 需确认含员工字段 |
| PE 历史 | `ak.stock_hk_valuation_baidu(symbol)`【已验证】 | 供 `pe-percentile` 使用 |

### 5.4 D. 三市场 `stock_quote.py --momentum`

| 数据 | 原始数据源 |
|---|---|
| A股个股行情 | `ak.stock_zh_a_hist`（东财）/ `ak.stock_zh_a_daily`（新浪）【已验证】 |
| A股指数基准（新增） | `ak.stock_zh_index_daily_em(symbol="sh000300")`（沪深300）或 `ak.stock_zh_index_daily`（新浪）【待验证】 |
| SMR 板块成分截面（250 日涨幅百分位，新增） | A股：申万一级行业成分（`sw_index_first_info` + `index_component_sw`）一次性构建全市场"代码→申万一级行业"映射并缓存（覆盖 5000+ 只，远优于东财行业缓存的当季已披露口径），成分 250 日涨幅距 `ak.stock_zh_a_daily`（新浪）优先、`ak.stock_zh_a_hist`（东财）回退批量【已实现】；港股：恒生行业指数成分【待验证】；美股：行业 ETF 成分（如 SOXX/XLK）经 yfinance 批量【待验证】 |
| 港股个股行情 | `ak.stock_hk_hist` / `ak.stock_hk_daily`【已验证】 |
| 港股指数基准 | `ak.stock_hk_index_daily_sina(symbol="HSI"/"CES100")`【已验证】 |
| 美股个股/指数 | yfinance `Ticker.history`、`^IXIC`/`^DJI`/`^GSPC`【已验证】 |

> 注：SMR 百分位按"同板块"口径计算（技能文件允许"全市场或同板块"），避免全市场 5000+ 只全量拉取；批量模式下板块截面一次拉取、多家复用，并做本地缓存。

### 5.5 E. 三市场 `stock_info.py` 市值/机构覆盖

| 数据 | 原始数据源 |
|---|---|
| A股总市值/流通市值 | `ak.stock_individual_info_em`【待验证】或 `ak.stock_zh_a_spot_em`【待验证】 |
| A股机构覆盖/研报数 | `ak.stock_research_report_em(symbol)`（按机构去重计数）【待验证】 |
| A股盈利预测 | `ak.stock_rank_forecast_cninfo`【待验证】 |
| 港股市值 | `ak.stock_hk_valuation_baidu` 或 `ak.stock_hk_spot_em`【待验证】 |
| 港股研报覆盖 | 无直接 akshare 接口【缺口，需用 `doubao_search` 半自动统计】 |
| 美股市值/员工数 | yfinance `Ticker.info`（`marketCap`、`fullTimeEmployees`）【已验证，`fullTimeEmployees` 常为空】 |
| 美股机构覆盖/评级 | yfinance `Ticker.recommendations` + `institutional_holders`【已验证】 |

### 5.6 F. 美股 `stock_financial.py --indicators`

| 指标 | 原始数据源 |
|---|---|
| 毛利、研发费用、合同负债（deferred revenue）、存货 | yfinance 三大报表 `income_stmt`/`balance_sheet`（年/季）【已验证】 |
| 存货周转天数 | 由资产负债表存货 + 利润表成本推算（无需新数据源） |
| 员工数 | yfinance 无可靠接口【缺口，标注并用搜索补充】 |

### 5.7 G. `trend_tech_screen.py` 打分引擎

不直接拉取网络数据，作为 **聚合与计算层**，输入 = A–F 各工具结构化 JSON 输出 + 搜索类工具产出的非结构化结论：

| 数据 | 原始数据源 |
|---|---|
| 政策环境、制裁状态、国产化率、自主替代公告、订单传闻 | `doubao_search.py` / `anysearch.py`（已有） |
| 行业周期定位（供需/价格/渗透率） | `doubao_search.py --time-range month`（已有） |

### 5.8 H. `annual_report_parser.py` 年报解析器

| 抽取字段 | 原始数据源 |
|---|---|
| 员工情况、子公司列表、新品收入占比、供应链风险、收入分部 | 本地年报 markdown（`pdf_extract.py` 产出）【已验证】 |
| 年报 PDF 原始文件 | `stock_equity.py --download-report`（巨潮资讯 cninfo）【已验证】 |

### 5.9 关键结论

1. 大部分缺口可通过 akshare/yfinance 现有接口补齐，无需接入新数据供应商。
2. **四处需特别注意**：
   - 港股研报覆盖数：akshare 无直接接口，只能搜索半自动统计（`doubao_search`）。
   - 美股员工数：yfinance `fullTimeEmployees` 经常为空，需搜索补充或接受缺口。
   - A股指数行情、东财资产负债表、`stock_individual_basic_info_xq`（员工数首选源）、`stock_research_report_em` 四个接口为【待验证】，是阶段二、三开发的第一步验证对象。
   - SMR 板块成分截面：三市场板块成分批量拉取的可行性与速率是阶段三第一步验证对象（见 5.4 注）。
3. 打分引擎与年报解析器不新增网络数据源，复用现有工具链输出。

---

## 6. 开发计划（分四阶段）

### 阶段一：估值计算 + 打分引擎骨架（可立即做，无网络依赖）

**目标**：先建立本技能的"计算中枢"，让后续阶段补数据即可逐步点亮指标。

**任务**：
1. `financial_rigor.py` 新增四命令：
   - `peg`：`--pe --growth` → 输出 PEG 及林奇评级（<1 / 1-1.5 / >1.5）
   - `ps-g`：`--ps --revenue-growth` → 输出 PSG 及判定（<0.5 / 0.5-1.0 / >1.0），爆发期专用
   - `pe-percentile`：`--pe-series JSON` → 输出当前 PE 所处历史分位
   - `implied-growth`：`--market-cap --target-pe --net-margin --ttm-revenue --guidance-growth` → 输出隐含增速要求与红/黄/绿判定（对照公司指引增速上限）
2. `trend_tech_screen.py` 骨架：
   - 定义五维打分表（含 4 种周期权重模式，默认需求爆发期）、地缘修正矩阵、评级映射、反证清单模板（先硬编码阈值，阈值可从技能文件读取）
   - 技术面止损校验：输入现价/MA50/MA200/量能，输出通过/预警/红牌，红牌对 S/A 级强制降级
   - 批量两轮计算：先算各公司基础分，再按行业通过率（>60% 集体 +2 / <30% 集体 -2）修正
   - 输入接口：接收结构化 JSON（各维度指标值 + 地缘二维评估值 + 技术面数据）
   - 输出接口：结构化 JSON（逐项得分、总分、修正后得分、评级、反证清单）+ Markdown 报告（路径遵循 `reports/trend-screen/` 规范）
   - 缺失科目留空并标注 `"note": "数据缺失"`，不阻断打分

**验证**：`financial_rigor.py peg --pe 30 --growth 40`、`financial_rigor.py ps-g --ps 5 --revenue-growth 80` 等单元测试；`trend_tech_screen.py` 用技能文件中的示例数据（A/B/C 公司）跑通打分流程。

**验收标准**：四命令精确复现手算结果；打分引擎输出与技能文件示例（A=101×1.10≈111 分 S 级、B=82 分 S 级、C=40×0.65=26 分 C 级）一致。

---

### 阶段二：数据获取扩展（A股/港股财务科目 + 缓存）

**目标**：补齐五类硬缺口科目（合同负债、存货周转、员工数、开发支出、应付账款/预付款项）。

**任务**：
1. **第一步（验证接口）**：
   - 验证 `ak.stock_balance_sheet_by_report_em`（含"合同负债""应付账款""预付款项"字段）
   - 验证 `ak.stock_financial_analysis_indicator`（含"存货周转天数""应付账款周转天数"）
   - 验证 `ak.stock_individual_basic_info_xq`（employee_total 员工数，首选源）；备选 `ak.stock_individual_info_em`
   - 验证 `ak.stock_financial_report_sina(symbol="资产负债表"/"现金流量表")` 字段
2. `a_share/stock_financial.py` 扩展：
   - 新增 `--indicator 合同负债,研发费用,存货周转天数,应付账款周转天数,预付款项,员工总数,开发支出,无形资产`
   - 新增季度数据输出模式
3. `a_stock_cache.py` 扩展：新增资产负债表、现金流量表、员工数的缓存文件与 TTL 策略（沿用现有 mtime + stale 降级模式）
4. `hk_stock/stock_financial.py` 扩展：接出 `stock_financial_hk_report_em` 三大报表科目（研发费用、合约负债、存货、应付账款、预付款项）；接入 `stock_individual_basic_info_hk_xq` 员工数（验证字段）。东财港股接口不稳定且批量模式（10-20 家×多科目）有速率风险：新科目做简单文件缓存（对齐 hit→refresh→stale 模式）或沿用 safe_api_call 重试 + 限速
5. `us_stock/stock_financial.py` 扩展：新增 `--indicators` 模式；yfinance 财务报表做本地 JSON 缓存（TTL 7 天），防范 429 限流

**验证**：以 2-3 只实测股票（如 300502 新易盛、00700 腾讯、AAPL）验证每个新科目的取值与年报披露一致。

**验收标准**：A/港/美股均能输出本技能所需的全部财务科目，缓存第二次命中 0 API 调用。

---

### 阶段三：动量与共识（行情 + 市值/覆盖度）

**任务**：
1. `stock_quote.py`（三市场）新增 `--momentum`：
   - **第一步（验证 SMR 截面）**：验证板块成分批量拉取可行性——A股复用申万一级行业成分映射（`sw_index_first_info` + `index_component_sw`）+ `ak.stock_zh_a_daily`（新浪）/`ak.stock_zh_a_hist`（东财）双源批量【已完成】；港/美股用行业指数/ETF 成分经 yfinance 批量【待验证】；截面一次拉取、批量复用并缓存
   - 计算 250 日 SMR 相对强度（同板块百分位排名，主指标）
   - 计算 RSI(50) 中期动量（备选指标）
   - 计算 MA50/MA200 及量能（技术面止损校验：破 50 日线放量预警 / 破 200 日线红牌）
   - A股新增指数行情（先验证 `ak.stock_zh_index_daily_em`）
2. `stock_info.py`（三市场）新增 `--profile`（完整画像）：
   - A股总市值：百度 `stock_zh_valuation_baidu`（主源，可靠）；流通市值：东财 `stock_individual_info_em`（东财不稳时置 None 并标缺口）【已完成】
   - A股机构覆盖度/研报数：东财 `stock_research_report_em`，输出研报总数/去重机构/最新日期/近一月研报数【已完成】
   - 港股总市值：百度 `stock_hk_valuation_baidu`（亿港元；流通市值接口不支持，标缺口）【已完成】
   - 港股研报覆盖：`doubao_search --finance --json` 半自动统计券商/投行覆盖（正则去噪，"证券/投行"后缀，标注缺口）【已完成】
   - 美股总市值/流通市值：美股 `stock_info.py` 已有（marketCap/floatShares）【无需改动】

**验证**：RSI(50)、MA50/MA200 与主流软件（同花顺/雪球）数值比对；SMR 抽样与手算百分位一致。

**验收标准**：动量维度（L 主指标 SMR + M 备选 RSI(50)）与技术面止损校验均可由工具直接输出，无需 LLM 计算。

---

### 阶段四：年报解析
> 状态：**【已完成】2026-08-25**

**任务**：
1. `annual_report_parser.py` 开发：
   - 输入：`pdf_extract.py` 产出的年报 markdown
   - 定向抽取：员工情况（研发人数/占比/学历结构/员工总数）、子公司列表（名称/关系/海外实体）、新品收入占比、供应链风险、收入分部（按产品/地区/销售模式）、研发投入章节（金额/强度/资本化金额/资本化率）
   - 输出：结构化 JSON（每项带 confidence 与源文本摘录，缺失字段置 None 并写 warnings，不猜测）

**验证**：用 `cninfo_reports/` 下已有年报 markdown 测试抽取准确率。
- 真实样例 `cninfo_reports/extracted/002709_2025年报.md` 验证通过：
  - 员工总数 7,389、研发人数 848、研发占比 11.48%、硕博 267/32、本科 446、其他 103 ✓
  - 子公司 30 家（海外 5 家：香港/德国/捷克/美国/新加坡）✓
  - 研发投入 8.47 亿、强度 5.09%、资本化 0 ✓
  - 收入分部按产品/地区/销售模式（锂电 90.39%、境内 96.20%、直销 100%）✓
  - 新品收入未披露产生 warning（预期行为）✓

**验收标准**：人才维度（H/I/J 指标）与地缘 Y 轴（海外实体评估）所需字段可结构化获取。
- 测试：`tests/common/test_annual_report_parser.py`（33 个用例，全量通过，纯逻辑无网络依赖）

---

## 7. 验收标准（整体）

1. 技能文件五维打分 + 地缘修正 + 技术面止损校验 + 评级 + 反证清单全流程可工具化执行，关键算术零 LLM 心算。
2. A/港/美三市场均覆盖，批量模式（10-20 家，含行业景气一致性两轮修正）可跑通。
3. 输出与技能文件示例数据打分结果一致（A=101×1.10≈111 分 S 级、B=82 分 S 级、C=26 分 C 级）。
4. 技术面止损校验（50/200 日均线 + 量能）可由工具直接输出，并对 S/A 级结果强制降级。
5. 所有新接口经实测验证字段名与取值正确，缓存遵循既有 TTL + stale 降级规范。

## 8. 待确认决策点

1. 是否同意新增 `trend_tech_screen.py` 打分引擎为核心工具？
2. `annual_report_parser.py` 是否纳入本次开发，还是留到后续迭代？——**已实施（2026-08-25）**：作为阶段四开发完成，`tools/common/annual_report_parser.py` + `tests/common/test_annual_report_parser.py`（33 用例通过）。
3. 实施顺序：按阶段一 → 四推进，还是优先阶段二（数据获取）再写打分引擎？
4. 打分引擎输出形态：结构化 JSON + Markdown 双输出是否符合预期？
5. `geo_political.py` / `supply_chain.py` 如何处理？——**已决策（2026-08-25）**：不开发，由 `doubao_search`/`anysearch` 搜索 + `annual_report_parser` 年报抽取替代，技能文件工具清单表已同步修订。

## 9. 风险与注意事项

- **接口字段不确定性**：【待验证】接口必须先验证（含 A股员工数首选源改为雪球 `stock_individual_basic_info_xq`），避免按错误字段名开发。
- **SMR 截面数据风险**：250 日 SMR 百分位依赖板块成分截面批量拉取，港/美股成分获取与速率是阶段三第一步验证对象；批量模式下截面一次拉取并缓存。
- **HK/US 缓存缺口**：当前工作区仅 `a_stock_cache.py`，港股新科目（东财不稳定）与美股 yfinance（429 限流）需在阶段二落实文件缓存或限速，避免批量模式触发封禁。
- **数据缺口兜底**：港股研报覆盖、美股员工数无可靠接口，需在工具输出中显式标注"数据缺失/搜索补充"，避免静默使用错误数据。
- **缓存一致性**：扩展 `a_stock_cache.py` 时沿用既有 mtime + miss 双触发 + stale 降级模式，不引入新模式。
- **路径基准**：所有新工具遵循工作区根目录 `F:/Financial_Investment_Analysis/`（本工作区为 `d:\Agent_Project\Financial_Investment_Analysis`）基准，Python 路径 `F:/Anaconda3/envs/Python_3_12_3/python.exe`。
- **跨市场口径**：市值统一币种需走 `fx_rate.py`；估值计算统一走 `financial_rigor.py`。

---

## 附：技能文件流程与工具映射速查

| 技能步骤 | 依赖工具（扩展后） |
|---|---|
| 第零层：周期定位 | `doubao_search.py` |
| 第一层：硬淘汰 | `stock_financial`（合同负债/存货周转）+ `pdf_extract`/`annual_report_parser`（员工/子公司） |
| 第二层①景气前瞻 | `stock_financial`（合同负债/毛利率/应付账款周转/预付款项）+ `doubao_search`（政策） |
| 第二层②研发转化 | `stock_financial`（研发费用/毛利/开发支出）+ `annual_report_parser`（新品占比/研发资本化率） |
| 第二层③人才 | `stock_financial`（员工数/净利润）+ `annual_report_parser`（研发占比/硕博/薪酬） |
| 第二层④动量共识 | `stock_quote --momentum`（SMR/RSI(50)）+ `stock_info`（覆盖度）+ 美股 `--analyst` |
| 第二层⑤估值 | `financial_rigor`（peg/ps-g/pe-percentile/implied-growth） |
| 第三层：地缘修正 | `doubao_search`/`anysearch`（制裁/国产化率，替代 geo_political）+ `annual_report_parser`（子公司/收入分部） |
| 估值倒推验证 | `financial_rigor`（implied-growth，含指引对照） |
| 技术面止损校验 | `stock_quote --momentum`（MA50/MA200/量能） |
| 供应链卡点排查 | `doubao_search` + `annual_report_parser`（供应链风险章节，替代 supply_chain） |
| 打分与评级 | `trend_tech_screen.py` |
