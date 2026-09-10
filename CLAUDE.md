# Financial Investment Analysis — 金融投资研究框架

本仓库是 [AI](https://github.com/ai-berkshire/ai-berkshire) 价值投资研究框架的工作目录。

---

## 目录结构

- `tools/` — 金融数据验证与分析工具（工作区根目录，独立副本）
  - `a_share/` — A股数据工具（akshare）
  - `hk_stock/` — 港股数据工具（东方财富/新浪）
  - `us_stock/` — 美股数据工具（yfinance）
  - `common/` — 通用工具（金融计算、长期折现估值、搜索、汇率、PDF提取、年报解析、动量计算、三市场数据缓存、报告审核等）
  - `specialized/` — 专用工具（景气趋势打分、在研项目扫描、动量回测、晨星公允价值）
- `reports/` — 研究报告输出（工作区根目录，含个股/行业/bottleneck-map/trend-screen/pdf 等子目录）
- `data/` — 本地数据缓存（三市场财务数据、A股代码/行业、板块截面，由 common/*_cache 模块自动维护）
- `research/` — 投资思想与理念研究文档（四位投资大师理念、个人投资者中长期投资思想）
- `refs/` — 参考资料（搜索服务对比、技能配套参考文档）
- `.trae/skills/` — 投研技能文件（43 个 SKILL.md + README.md，另有 `tools-scripts/` 工具使用参考文档）
- `docs/` — 工具使用指南（A股/港股/美股）与 `dev_docs/` 开发记录
- `tests/` — pytest 单元/集成测试（对应 tools/ 各模块）
- `.env` / `.env.example` — 环境变量配置（API密钥、限流参数、缓存 TTL 等）
- `requirements.txt` — Python 依赖清单（akshare、yfinance、pandas、requests、mcp、pdf-inspector 等）

## Skill 使用

技能安装在 `.trae/skills/` 目录下，共 **43 个技能**，覆盖行业研究、公司深度研究、买入决策、中期投研（1-3年）、财报跟踪、持仓管理、基础工具与内容输出、未上市公司研究八大类（另有 `tools-scripts/` 存放工具使用参考文档）。

完整的技能选用指南：

- 长期（10 年）参见 [证券AI价值投资研究工作步骤.md](.trae/skills/证券AI价值投资研究工作步骤.md)
- 中期（1-3 年）参见 [证券AI中长期（1~3年）价值投资研究工作步骤.md](.trae/skills/证券AI中长期（1~3年）价值投资研究工作步骤.md)

### 行业研究类

| 命令                              | 功能                                                        |
| --------------------------------- | ----------------------------------------------------------- |
| `/industry-research {行业名}`   | 产业链全景扫描 + 四大师个股分析，首次研究一个行业时使用      |
| `/industry-funnel {行业名}`     | 从全市场 30-60 家逐层精选到 3 家终选标的                     |
| `/bottleneck-hunter {趋势名}`   | 从供应链"咽喉位置"挖掘第二、第三层投资机会                   |
| `/era-alpha {行业/方向}`        | 时代α捕手：高增长核心资产的识别-验证-持有，聚焦时代级主线     |

### 公司深度研究类

| 命令                               | 功能                                                        |
| ---------------------------------- | ----------------------------------------------------------- |
| `/investment-research {公司名}`  | 单 Agent 四大师综合分析框架，快速产出研究报告               |
| `/investment-team {公司名}`      | 四 Agent 并行研究 + Team Lead 综合研判，产出系统化报告      |
| `/deep-company-series {公司名}`  | 8 篇长文（约 12 万字）拆一家公司，适合公众号发布            |
| `/management-deep-dive {公司名}` | 深度评估管理层诚信度、战略执行、资本配置、治理结构          |

### 买入决策类

| 命令                                   | 功能                                                              |
| -------------------------------------- | ----------------------------------------------------------------- |
| `/quality-screen {公司/行业/指数}`   | 去劣筛选：7 条硬指标 + 3 条豁免规则，快速排除非一流公司           |
| `/investment-checklist {公司名}`     | 巴菲特六关 Checklist + 镜子测试 + 8 条红线否决                    |
| `/income-investment {公司名}`        | 收入投资分析：分红持久性、现金流覆盖、收益陷阱识别                |
### 中期投研类（1-3年）

| 命令 | 功能 |
| --- | --- |
| `/mid-era-alpha {行业/方向}` | 时代α捕手（1~3年景气版）：时代级高增长主线与核心α识别-验证-持有，聚焦高景气主线的介入与退出纪律 |
| `/mid-industry-research {行业名}` | 中期行业景气研究：TAM/渗透率/业绩兑现/地缘风险四维筛选 |
| `/mid-industry-funnel {行业名}` | 中期行业漏斗精选：硬指标粗筛→四大支柱→四大师研判，收敛 3 家底仓 + 2 家机动仓 |
| `/mid-bottleneck-hunter {趋势名}` | 供应链瓶颈猎手（中期版）：从物理供应链咽喉位置挖掘第二、三层瓶颈机会，叠加景气度与地缘六维评估 |
| `/mid-trend-tech-screen {公司/行业/指数/主题}` | 景气趋势筛选：五维打分 + 地缘修正 + 技术面止损，1-3 年正向排序 |
| `/mid-investment-research {公司名}` | 单 Agent 四大师综合分析框架（1~3年景气版），快速产出中期研究报告 |
| `/mid-investment-team {公司名}` | 四角色并行研究 + Team Lead 综合研判（欧奈尔/林奇/郑希/李进），产出系统化中期报告 |
| `/mid-earnings-team {公司名} {期间}` | 财报精读团队（1~3年景气版）：林奇-郑希-欧奈尔-李进 四大师并行解读 + 编辑润色 + 读者评审，验证景气逻辑与更新卖出纪律 |
| `/mid-earnings-review {公司名} {期间}` | 财报精读（轻量版·1~3年景气版）：单 Agent 快速财报精读，四大师作为分析维度标尺，验证景气逻辑与更新卖出纪律 |
| `/mid-deep-company-series {公司名}` | 深度长文系列（1~3年景气版）：3-8 篇拆一家公司，认知重置到决策闭环，可公开发布 |
| `/mid-investment-checklist {公司名}` | 买入前检查：七关景气投资 Checklist（赛道/景气/护城河/管理层×科研/估值建仓/仓位卖出/地缘） |
| `/mid-management-deep-dive {公司名}` | 管理层纵深研究（1-3年）：诚信度/战略执行/科研转化/资本配置/治理结构，与 P0~P5 卖出纪律联动 |
| `/valuation-thermometer {公司名}` | 估值温度计：PEG/PSG/PE分位/implied-growth 五档温度 |
| `/qoq-accelerator {公司名}` | 季度加速度：连续 3 季二阶导，区分波动与拐点 |
| `/trend-momentum-scan {持仓代码}` | 持仓动量体检：SMR/RSI50/MA50/MA200 技术破位预警 |
| `/mid-thesis-drift {标的}` | 中期逻辑漂移：景气假设六大维度逐条验证 |
| `/exit-signal {标的}` | 卖出信号：P0~P5 六级优先级硬编码检查 |
| `/mid-news-pulse {公司名}` | 公司新闻脉搏（景气投资版）：股价异动快速归因 + P0~P5 卖出纪律触发检查 |
| `/garp-ask {问题}` | GARP 价值成长问答（1~3年）：林奇主轴 + 郑希/李进/欧奈尔辅助，PEG/六类分类/P0~P5 卖出纪律 |
| `/garp-liquidity-reinvestment {公司名}` | 流动性质量与再投资能力验证（1~3年景气版）：自由现金流质量、再投资效率与资本配置纪律 |

### 财报跟踪类

| 命令                               | 功能                                                        |
| ---------------------------------- | ----------------------------------------------------------- |
| `/earnings-review {公司名} {期间}` | 财报精读（快速版）：单 Agent 八步精读流程                    |
| `/earnings-team {公司名} {期间}`   | 财报精读团队：四大师并行解读 + 编辑润色 + 读者评审           |

### 持仓管理类

| 命令                             | 功能                                                        |
| -------------------------------- | ----------------------------------------------------------- |
| `/thesis-tracker {公司名}`     | 投资论文追踪：建立投资论文 + 季度健康度检查                 |
| `/thesis-drift {公司名}`       | 论文漂移检测：对比新旧报告，基于证据判定论文是否漂移        |
| `/portfolio-review {持仓清单}` | 组合管理：集中度、相关性、机会成本、压力测试四维度分析      |
| `/news-pulse {公司名}`         | 公司新闻脉搏：股价异动时 10-15 分钟快速归因                 |

### 基础工具与内容输出类

| 命令                          | 功能                                                          |
| ----------------------------- | ------------------------------------------------------------- |
| `/financial-data {公司名}`  | 数据获取标准流程，双源交叉验证，误差 >1% 须标记               |
| `/wechat-article {主题}`    | 微信公众号文章（长期版）：作者-编辑-读者三 Agent 协作产出可发布文章     |
| `/mid-wechat-article {主题}` | 微信公众号文章（中期景气版，1~3年）：四大师框架（林奇/郑希/欧奈尔/李进），景气投资为主、技术解读为辅 |
| `/dyp-ask {问题}`           | 段永平问答：以段永平投资哲学视角回答问题，投资思想参考        |

### 未上市公司研究类

| 命令                                 | 功能                                                          |
| ------------------------------------ | ------------------------------------------------------------- |
| `/private-company-research {公司名}` | 未上市公司研究：6 Agent 并行深度研究，拼凑信息还原真实价值   |
| `/mid-private-company-research {公司名}` | 未上市公司研究（1-3年景气版）：6 Agent 并行，判断上市后是否适用 GARP 框架、是否值得等待上市 |

## 持有周期路由规则（中期 vs 长期）

- **中期链（1-3 年）**：提及「1-3 年 / 中期 / 景气 / 趋势 / 成长爆发」→
  `mid-industry-research` → `mid-industry-funnel` → `mid-trend-tech-screen` → `mid-investment-checklist` → `valuation-thermometer` → `qoq-accelerator`
  → `trend-momentum-scan` → `mid-thesis-drift` → `exit-signal`
- **中期链 · 时代主线识别**：提及「时代α / 高增长核心资产 / 时代主线 / 范式转移」且属 1-3 年 / 中期 / 景气语境 →
  `mid-era-alpha` → `mid-industry-research` → `mid-industry-funnel` → `mid-trend-tech-screen` → `mid-investment-checklist` → `exit-signal`
- **股价异动应急**：提及「股价异动 / 暴跌 / 暴涨 / 为什么跌 / 为什么涨 / 新闻归因」→ `mid-news-pulse`（快速归因）→ 命中卖出纪律转 `exit-signal` → 景气逻辑复核转 `qoq-accelerator` / `mid-thesis-drift`
- **长期链（10 年）**：提及「10 年 / 长期 / 永续 / 护城河」→
  `quality-screen` → `investment-research` → `thesis-tracker` → `thesis-drift`
- **长期链 · 时代主线识别（10 年）**：提及「时代α / 高增长核心资产 / 时代主线 / 范式转移」且属 10 年 / 长期 / 永续语境 →
  `era-alpha` → `quality-screen` → `investment-research` → `thesis-tracker` → `thesis-drift`
- **`mid-` 前缀显式调用优先匹配**：`/mid-xxx` 直接命中对应中期技能，不受关键词路由影响
- **中期问答入口**：涉及中期景气/PEG/估值/卖出纪律的轻量问答，可用 `/garp-ask {问题}`（问答型、不生成报告，林奇主轴）；与长期链 `/dyp-ask`（段永平）物理隔离
- **未上市公司研究**：提及「未上市 / Pre-IPO / 独角兽 / 一级市场」→ 默认按持有周期分流：长期链 `/private-company-research`（10 年 / 护城河）、中期链 `/mid-private-company-research`（1-3 年景气 GARP）
- **持有周期不明**：先询问用户持有周期（1-3 年 or 10 年）再路由

## 研究质量规则

本项目的所有研究活动遵守以下全局约束：

1. **日期确认** — 开始研究前运行 `date` 确认当天日期，以此作为"最新数据"的基准，并在报告头部注明数据截止日期。不得依赖训练数据中的日期假设。
2. **数据交叉验证** — 关键财务数据须至少来自两个独立来源，误差 >1% 须标记。
3. **精确算术工具** — 市值计算、估值、跨源校验使用精确工具，禁止 LLM 心算：
   `python tools/common/financial_rigor.py ...`
4. **报告审核** — 发布前运行审计工具：
   `python tools/common/report_audit.py ...`
5. **不确定性标注** — 明确标注低置信度结论、不完整数据及来源缺口。
6. **免责声明** — 本项目用于学习与研究，不构成投资建议。

## 工作规范

- **路径基准**：所有路径以工作区根目录（`F:/Financial_Investment_Analysis/`）为基准
- **工具使用**：优先使用 `tools/` 下的共享验证工具，无需 `cd` 到子目录
- **报告输出**：输出到 `reports/`（工作区根目录）
- **技能修改**：修改 `.trae/skills/` 下的技能文件即可生效，无需额外同步脚本
- **配置文件**：`.env` 存放 API 密钥与工具参数（如 `FX_MAX_RECORDS_HARD_LIMIT`、`STOCK_CACHE_TTL_DAYS`、`ANYSEARCH_API_KEY`、`VOLC_AK/SK`、`EXA_API_KEY` 等），工具启动时自动加载；新增配置项同步写入 `.env.example`
- **数据缓存**：三市场财务数据、A股代码/行业、板块截面均落地 `data/` 目录（TTL 内免网络调用，过期自动刷新，失败降级旧缓存 hit→refresh→stale）
- **推送前**：询问用户是否需要推送到 GitHub；推送前务必 `git pull --rebase`

## 用户偏好

- 研究语言：中文
- 结论风格：直接明确，不两面讨好
- 数据要求：精确，支持多源交叉验证
- 对错误的态度：直接指出即可，用户会挑战 AI 判断，应重新评估而非辩护

## 网络限制 — WebSearch / WebFetch 不可用

**重要**：Anthropic 官方 WebSearch 和 WebFetch 在中国大陆被硬性地域封锁（geo-blocking），所有调用均返回空结果或连接失败。**在项目中禁止调用这两个工具。**

### 数据获取替代方案

#### 详细工具使用指南

- **A股数据工具**：参见 [docs/A股工具使用指南.md](docs/A股工具使用指南.md)
- **港股数据工具**：参见 [docs/港股工具使用指南.md](docs/港股工具使用指南.md)
- **美股数据工具**：参见 [docs/美股工具使用指南.md](docs/美股工具使用指南.md)

#### 1. 本地 akshare 工具（A股数据，首选）

| 工具文件                             | 功能               | 命令示例                                                  |
| ------------------------------------ | ------------------ | --------------------------------------------------------- |
| `tools/a_share/stock_info.py`      | A股信息查询        | `python tools/a_share/stock_info.py --search 新易盛`    |
| `tools/a_share/stock_quote.py`     | A股行情数据（含 `--momentum` 动量/技术面指标、`--auto-peers` 板块截面） | `python tools/a_share/stock_quote.py --code 300502` |
| `tools/a_share/stock_financial.py` | A股财务指标        | `python tools/a_share/stock_financial.py --code 300502` |
| `tools/a_share/stock_screen.py`    | 质量筛选7条指标    | `python tools/a_share/stock_screen.py --code 300502`    |
| `tools/a_share/stock_equity.py`    | 股权结构与财报PDF下载 | `python tools/a_share/stock_equity.py --code 601899 --download-report` |
| `tools/a_share/stock_financial_batch.ps1` | 批量财务指标脚本（PowerShell） | `.\tools\a_share\stock_financial_batch.ps1 -codes "601899,000960" -indicators "ROE,毛利率"` |

**Python路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

**数据源**：东方财富、新浪财经、巨潮资讯（财务/行情数据经 `tools/common/a_stock_cache.py` 本地缓存至 `data/a_share/`）

#### 2. 本地港股工具（港股数据）

| 工具文件                              | 功能                   | 命令示例                                                       |
| ------------------------------------- | ---------------------- | -------------------------------------------------------------- |
| `tools/hk_stock/stock_info.py`      | 港股信息查询（列表/搜索/实时行情/热度榜） | `python tools/hk_stock/stock_info.py --search 腾讯`      |
| `tools/hk_stock/stock_financial.py` | 港股信息查询、财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| `tools/hk_stock/stock_quote.py`     | 港股历史K线、指数数据  | `python tools/hk_stock/stock_quote.py --code 00700`          |
| `tools/hk_stock/stock_screen.py`    | 港股质量筛选7条指标    | `python tools/hk_stock/stock_screen.py --code 00700`         |

**数据源**：东方财富、新浪财经（报表/员工数经 `tools/common/hk_stock_cache.py` 本地缓存）

**注意**：东方财富接口在中国大陆网络连接不稳定（非地理封锁），工具已内置重试机制

#### 3. 本地美股工具（美股数据）

| 工具文件                              | 功能         | 命令示例                                                 |
| ------------------------------------- | ------------ | -------------------------------------------------------- |
| `tools/us_stock/stock_info.py`      | 美股信息查询 | `python tools/us_stock/stock_info.py --search Apple`   |
| `tools/us_stock/stock_financial.py` | 美股财务指标 | `python tools/us_stock/stock_financial.py --code AAPL` |
| `tools/us_stock/stock_quote.py`     | 美股行情数据 | `python tools/us_stock/stock_quote.py --code AAPL`     |

**数据源**：yfinance（三大报表经 `tools/common/us_stock_cache.py` 本地缓存，规避 429 限流）

#### 4. 通用工具

| 工具文件                            | 功能                                            | 命令示例                                                           |
| ----------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值校验、三情景估值）   | `python tools/common/financial_rigor.py verify-valuation --help` |
| `tools/common/terminal_value.py` | 长期折现估值（十年尺度：终值PE、十倍IRR、r/ROIC/g三输入、三条硬约束audit） | `python tools/common/terminal_value.py audit --currency CNY --r 0.08 --roic 0.20 --g 0.005,0.02,0.03` |
| `tools/common/fx_rate.py`         | 国际主要货币汇率（Akshare 优先，yfinance 回退） | `python tools/common/fx_rate.py --code USDCNY`                   |
| `tools/common/commodity_price.py` | 大宗商品价格（Akshare 优先，yfinance 回退）     | `python tools/common/commodity_price.py --code cu,GC,CL`         |
| `tools/common/pdf_extract.py`     | PDF文字与表格提取（pdf-inspector，自动乱码检测 + OCR 回退） | `python tools/common/pdf_extract.py markdown report.pdf` |
| `tools/common/annual_report_parser.py` | 年报 Markdown 定向抽取（员工/研发/收入分部/新品/供应链风险等6类字段） | `python tools/common/annual_report_parser.py 年报.md --output-json` |
| `tools/common/momentum.py`        | 动量与技术面纯计算核心（250日SMR/RSI50/MA50/MA200），三市场复用 | 由 `stock_quote --momentum` 调用                              |
| `tools/common/sector_screen.py`   | A股板块 SMR 截面数据（申万一级行业成分批量，本地缓存） | 由 `stock_quote --auto-peers` 调用                            |
| `tools/common/a_stock_cache.py`   | A股代码/行业/季度业绩本地缓存（data/a_share/）  | `python -c "from tools.common import a_stock_cache; a_stock_cache.get_code_name_list()"` |
| `tools/common/hk_stock_cache.py`  | 港股三大报表与员工数本地缓存                    | `python -c "from tools.common import hk_stock_cache; hk_stock_cache.get_financial_report('00700','资产负债表')"` |
| `tools/common/us_stock_cache.py`  | 美股三大报表本地缓存                            | `python -c "from tools.common import us_stock_cache; us_stock_cache.get_statement('AAPL','income')"` |
| `tools/common/report_audit.py`    | 报告审核工具                                    | `python tools/common/report_audit.py --help`                     |

#### 5. 网络搜索工具（v3.0 五工具组合）

| 工具文件                            | 角色定位                  | 命令示例                                                           |
| ----------------------------------- | ------------------------- | ------------------------------------------------------------------ |
| `tools/common/anysearch.py`       | **A 股投研首选**（23 类垂直库） | `python tools/common/anysearch.py "紫金矿业 财报" --tag finance` |
| `tools/common/doubao_search.py`   | **实时资讯/舆情首选**（火山引擎） | `python tools/common/doubao_search.py "腾讯 财报" --finance`     |
| `tools/common/exa_search.py`      | **美股深度研究首选**（SEC filings 直击原文） | `python tools/common/exa_search.py "AAPL 10-K" --type deep`      |
| `tools/common/tavily_search.py`   | 港美股深度内容辅源          | `python tools/common/tavily_search.py "腾讯 财报"`               |
| `tools/common/web_search.py`      | 仅阿里云生态/轻量验证兜底 | `python tools/common/web_search.py "搜索关键词"`                 |

选型策略：A股财报/公告深查用 `anysearch`，实时舆情用 `doubao_search`，美股 SEC 用 `exa_search`，港美股内容辅源用 `tavily_search`。完整决策流程见 [web-search-tools.md](.trae/skills/tools-scripts/web-search-tools.md)。

#### 6. 专用工具

| 工具文件                              | 功能                                            | 命令示例                                                           |
| ------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| `tools/specialized/trend_tech_screen.py` | 景气趋势五维打分引擎（score/batch，含地缘修正+技术面止损） | `python tools/specialized/trend_tech_screen.py score --help` |
| `tools/specialized/in_research_scan.py` | 在研重大项目扫描器（gov/patent/bidding/academic 等 8 渠道批量） | `python tools/specialized/in_research_scan.py scan 中芯国际 --market sh` |
| `tools/specialized/momentum_backtest.py` | 动量回测工具（yfinance，默认 NVDA/AMD/MU）      | `python tools/specialized/momentum_backtest.py --tickers NVDA AMD` |
| `tools/specialized/morningstar_fair_value.py` | 晨星公允价值筛选（Top 100 低估股票，输出 CSV） | `python tools/specialized/morningstar_fair_value.py`               |

#### 7. 浏览器手动获取（补充）

用户通过 Edge 浏览器（科学上网）手动搜索，将结果粘贴到对话中。主要用于美股第三方数据源（macrotrends、stockanalysis）和原始财报（SEC EDGAR）。
