# Financial Investment Analysis — 金融投资研究框架

本仓库是 [AI Berkshire](https://github.com/ai-berkshire/ai-berkshire) 价值投资研究框架的工作目录。

---

## 目录结构

- `ai-berkshire/` — AI Berkshire 上游源代码，只读参考，**不可修改**
- `tools/` — 金融数据验证与分析工具（工作区根目录，独立副本）
- `reports/` — 研究报告输出（工作区根目录）
- `scripts/` — 同步与安装脚本（工作区根目录，独立副本）
- `.claude/` — Claude Code 本地配置 & 技能
- `memory/` — 项目记忆文件（持久化存储，跨会话复用）
- `tests/` — 测试软件保存目录

## Skill 使用

技能安装在 `.claude/skills/` 目录下，通过 `/skills` 命令加载。目前可用技能：

| 命令                | 功能                                |
| ------------------- | ----------------------------------- |
| `/quality-screen` | 去劣筛选：7条指标快速排除非一流公司 |
| `/skill-creator`  | 创建/编辑/优化技能                  |

更多技能正在移植中。执行研究前建议先使用 `/skills` 加载最新列表。

## 研究质量规则（继承自 AI Berkshire）

本项目的所有研究活动遵守以下全局约束（源自 `ai-berkshire/AGENTS.md`）：

1. **日期确认** — 开始研究前运行 `date` 确认当天日期，以此作为"最新数据"的基准，并在报告头部注明数据截止日期。不得依赖训练数据中的日期假设。
2. **数据交叉验证** — 关键财务数据须至少来自两个独立来源。
3. **精确算术工具** — 市值计算、估值、跨源校验使用精确工具：
   `python3 tools/common/financial_rigor.py ...`
4. **报告审核** — 发布前运行审计工具：
   `python3 tools/common/report_audit.py ...`
5. **不确定性标注** — 明确标注低置信度结论、不完整数据及来源缺口。
6. **免责声明** — 本项目用于学习与研究，不构成投资建议。

## 工作规范

- **路径基准**：所有路径以工作区根目录（`F:/Financial_Investment_Analysis/`）为基准
- **工具使用**：优先使用 `tools/` 下的共享验证工具，无需 `cd` 到子目录
- **报告输出**：输出到 `reports/`（工作区根目录）
- **技能修改**：修改 `.claude/skills/` 下的技能文件即可，**不需要**运行同步脚本（工作区独立，无需与上游同步）
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

#### 1. 本地 akshare 工具（A股数据，首选）

| 工具文件 | 功能 | 命令示例 |
|---------|------|---------|
| `tools/a_share/stock_info.py` | A股信息查询 | `python tools/a_share/stock_info.py --search 新易盛` |
| `tools/a_share/stock_quote.py` | A股行情数据 | `python tools/a_share/stock_quote.py --code 300502` |
| `tools/a_share/stock_financial.py` | A股财务指标 | `python tools/a_share/stock_financial.py --code 300502` |
| `tools/a_share/stock_screen.py` | 质量筛选7条指标 | `python tools/a_share/stock_screen.py --code 300502` |
| `tools/a_share/stock_equity.py` | 股权结构与财报下载 | `python tools/a_share/stock_equity.py --code 601899` |

**Python路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`

**数据源**：东方财富、新浪财经、巨潮资讯

#### 2. 本地港股工具（港股数据）

| 工具文件 | 功能 | 命令示例 |
|---------|------|---------|
| `tools/hk_stock/stock_financial.py` | 港股信息查询、财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| `tools/hk_stock/stock_quote.py` | 港股历史K线、指数数据 | `python tools/hk_stock/stock_quote.py --code 00700` |
| `tools/hk_stock/stock_screen.py` | 港股质量筛选7条指标 | `python tools/hk_stock/stock_screen.py --code 00700` |

**数据源**：东方财富、新浪财经

**注意**：东方财富接口在中国大陆网络连接不稳定（非地理封锁），工具已内置重试机制

#### 3. 其他辅助工具

| 工具文件 | 功能 | 命令示例 |
|---------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE等） | `python tools/common/financial_rigor.py verify-valuation --help` |
| `tools/common/web_search.py` | 网络信息搜索（阿里云百炼） | `python tools/common/web_search.py "搜索关键词"` |
| `tools/common/report_audit.py` | 报告审核工具 | `python tools/common/report_audit.py --help` |

#### 4. 浏览器手动获取（非A股/港股数据）

用户通过 Edge 浏览器（科学上网）手动搜索，将结果粘贴到对话中。

#### 5. 国内可达 API 扩展（未来）

扩展工具通过新浪财经等国内可达 API 获取非A股数据。
