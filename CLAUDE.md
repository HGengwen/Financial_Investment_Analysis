# Financial Investment Analysis — 金融投资研究框架

本仓库是 [AI](https://github.com/ai-berkshire/ai-berkshire) 价值投资研究框架的工作目录。

---

## 目录结构

- `tools/` — 金融数据验证与分析工具（工作区根目录，独立副本）
  - `a_share/` — A股数据工具（akshare）
  - `hk_stock/` — 港股数据工具（东方财富/新浪）
  - `us_stock/` — 美股数据工具（yfinance）
  - `common/` — 通用工具（金融计算、搜索、汇率、PDF提取、报告审核等）
  - `specialized/` — 专用工具（动量回测、晨星公允价值）
- `reports/` — 研究报告输出（工作区根目录）
- `scripts/` — 同步与安装脚本（工作区根目录，独立副本）
- `.trae/skills/` — 投研技能文件（SKILL.md + README.md）
- `docs/` — 工具使用指南（A股/港股/美股）
- `memory/` — 项目记忆文件（持久化存储，跨会话复用）
- `tests/` — 测试软件保存目录
- `.env` — 环境变量配置（API密钥、限流参数等）

## Skill 使用

技能安装在 `.trae/skills/` 目录下，共 20 个技能，覆盖行业研究、公司深度研究、买入决策、收入投资、财报跟踪、持仓管理、基础工具与内容输出七大类。

完整的技能选用指南参见 [证券AI价值投资研究工作步骤.md](.trae/skills/证券AI价值投资研究工作步骤.md)。

主要技能：

| 命令                      | 功能                                          |
| ------------------------- | --------------------------------------------- |
| `/investment-research`  | 四大师综合分析框架，快速产出研究报告          |
| `/investment-team`      | 四 Agent 并行深度研究                         |
| `/quality-screen`       | 去劣筛选：7条指标快速排除非一流公司           |
| `/investment-checklist` | 巴菲特六关 Checklist + 镜子测试 + 8条红线否决 |
| `/income-investment`    | 收入投资分析：分红持久性、收益陷阱识别        |
| `/portfolio-review`     | 组合管理：集中度、相关性、机会成本、压力测试  |
| `/earnings-review`      | 财报精读（快速版）                            |
| `/thesis-tracker`       | 投资论文追踪与季度检查                        |
| `/financial-data`       | 数据获取标准流程，双源交叉验证                |

## 研究质量规则

本项目的所有研究活动遵守以下全局约束：

1. **日期确认** — 开始研究前运行 `date` 确认当天日期，以此作为"最新数据"的基准，并在报告头部注明数据截止日期。不得依赖训练数据中的日期假设。
2. **数据交叉验证** — 关键财务数据须至少来自两个独立来源。
3. **精确算术工具** — 市值计算、估值、跨源校验使用精确工具：
   `python tools/common/financial_rigor.py ...`
4. **报告审核** — 发布前运行审计工具：
   `python tools/common/report_audit.py ...`
5. **不确定性标注** — 明确标注低置信度结论、不完整数据及来源缺口。
6. **免责声明** — 本项目用于学习与研究，不构成投资建议。

## 工作规范

- **路径基准**：所有路径以工作区根目录（`F:/Financial_Investment_Analysis/`）为基准
- **工具使用**：优先使用 `tools/` 下的共享验证工具，无需 `cd` 到子目录
- **报告输出**：输出到 `reports/`（工作区根目录）
- **技能修改**：修改 `.trae/skills/` 下的技能文件即可，**不需要**运行同步脚本（工作区独立，无需与上游同步）
- **配置文件**：`.env` 存放 API 密钥与工具参数（如 `FX_MAX_RECORDS_HARD_LIMIT`），工具启动时自动加载
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
| `tools/a_share/stock_quote.py`     | A股行情数据        | `python tools/a_share/stock_quote.py --code 300502`     |
| `tools/a_share/stock_financial.py` | A股财务指标        | `python tools/a_share/stock_financial.py --code 300502` |
| `tools/a_share/stock_screen.py`    | 质量筛选7条指标    | `python tools/a_share/stock_screen.py --code 300502`    |
| `tools/a_share/stock_equity.py`    | 股权结构与财报下载 | `python tools/a_share/stock_equity.py --code 601899`    |

**Python路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

**数据源**：东方财富、新浪财经、巨潮资讯

#### 2. 本地港股工具（港股数据）

| 工具文件                              | 功能                   | 命令示例                                                       |
| ------------------------------------- | ---------------------- | -------------------------------------------------------------- |
| `tools/hk_stock/stock_financial.py` | 港股信息查询、财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| `tools/hk_stock/stock_quote.py`     | 港股历史K线、指数数据  | `python tools/hk_stock/stock_quote.py --code 00700`          |
| `tools/hk_stock/stock_screen.py`    | 港股质量筛选7条指标    | `python tools/hk_stock/stock_screen.py --code 00700`         |

**数据源**：东方财富、新浪财经

**注意**：东方财富接口在中国大陆网络连接不稳定（非地理封锁），工具已内置重试机制

#### 3. 本地美股工具（美股数据）

| 工具文件                              | 功能         | 命令示例                                                 |
| ------------------------------------- | ------------ | -------------------------------------------------------- |
| `tools/us_stock/stock_info.py`      | 美股信息查询 | `python tools/us_stock/stock_info.py --search Apple`   |
| `tools/us_stock/stock_financial.py` | 美股财务指标 | `python tools/us_stock/stock_financial.py --code AAPL` |
| `tools/us_stock/stock_quote.py`     | 美股行情数据 | `python tools/us_stock/stock_quote.py --code AAPL`     |

**数据源**：yfinance

#### 4. 通用工具

| 工具文件                            | 功能                                            | 命令示例                                                           |
| ----------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------ |
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值校验、三情景估值）   | `python tools/common/financial_rigor.py verify-valuation --help` |
| `tools/common/fx_rate.py`         | 国际主要货币汇率（Akshare 优先，yfinance 回退） | `python tools/common/fx_rate.py --code USDCNY`                   |
| `tools/common/commodity_price.py` | 大宗商品价格（Akshare 优先，yfinance 回退）     | `python tools/common/commodity_price.py --code cu,GC,CL`         |
| `tools/common/pdf_extract.py`     | PDF文字与表格提取（基于 pdf-inspector）         | `python tools/common/pdf_extract.py markdown report.pdf`         |
| `tools/common/report_audit.py`    | 报告审核工具                                    | `python tools/common/report_audit.py --help`                     |
| `tools/common/anysearch.py`      | AnySearch（**A 股投研首选**，23 类垂直库）       | `python tools/common/anysearch.py "紫金矿业 财报" --tag finance` |
| `tools/common/doubao_search.py`   | 豆包搜索（**实时资讯/舆情首选**，火山引擎）     | `python tools/common/doubao_search.py "腾讯 财报" --finance`     |
| `tools/common/exa_search.py`      | Exa（**美股深度研究首选**，SEC filings 直击原文）| `python tools/common/exa_search.py "AAPL 10-K" --type deep`      |
| `tools/common/tavily_search.py`   | Tavily（港美股深度内容辅源）                     | `python tools/common/tavily_search.py "腾讯 财报"`               |
| `tools/common/web_search.py`      | WebSearch（仅阿里云生态/轻量验证兜底）          | `python tools/common/web_search.py "搜索关键词"`                 |

#### 5. 浏览器手动获取（补充）

用户通过 Edge 浏览器（科学上网）手动搜索，将结果粘贴到对话中。主要用于美股第三方数据源（macrotrends、stockanalysis）和原始财报（SEC EDGAR）。
