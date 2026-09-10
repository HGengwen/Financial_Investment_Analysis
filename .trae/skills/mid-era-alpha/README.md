# 时代α捕手（1~3年景气版） (Mid Era Alpha)

时代级高增长主线与核心 α 的识别-验证-持有框架，聚焦 1-3 年持有周期内的高景气主线锁定与核心 α 验证，给出明确的介入与退出纪律。

本技能是 `/era-alpha`（长期 10 年版）的中期双轨对应物，两者**物理隔离**：长期链回答「10 年后还在吗？」，本技能回答「未来 1-3 年景气向上吗？值不值得进？」。

---

## 快速开始

### 基本调用方式

```
/mid-era-alpha {行业/方向}
```

例如：

- `/mid-era-alpha AI算力`
- `/mid-era-alpha 人形机器人`
- `/mid-era-alpha 创新药出海`

---

## 核心功能

对指定行业/方向执行"时代α五步法（中期版）"，找出当下 1-3 年最核心高景气主线中真正有定价权、有景气壁垒、能持续跑赢同行的核心 α。

### 五步研究框架

1. **时代主线认知地图** — 基于渗透率坐标 + 四大支柱定位主线与产业链环节，锁定 2-3 个核心环节（含地缘风险敞口与华为式抗封锁韧性）
2. **自问核心问题** — 当下最核心高景气主线是什么？核心 α 是谁？为什么是它而不是老二？
3. **景气可持续性验证** — 五维交叉（财报 + 高频数据）+ 四大师透镜 + 管理层/科研转化评估
4. **PEG 估值锚点与介入** — 用精确工具求 PEG 五档，替代"不看股价"的盲目买入
5. **持仓与卖出纪律** — 底仓/机动仓 + 三层拐点清单（宏观/行业/公司），硬链接 `exit-signal`、`thesis-tracker --horizon mid`、`mid-thesis-drift`

### 三项修正（相比原版操作手册，落到 1-3 年景气语境）

| 修正 | 内容 |
|------|------|
| 修正一（精简范围） | 不覆盖所有行业，聚焦主线中 2-3 个核心环节做深做透 |
| 修正二（高频数据交叉验证） | 财报是三个月前的体检报告，用周度/月度出货量、价格、订单、渗透率做实时体温计校正 |
| 修正三（估值锚点） | 以 PEG 五档为核心锚点替代"闭眼买"，低估/合理重仓、偏贵观望、严重透支减机动仓、拐点确认清仓 |

### 四大师验证透镜（中期景气投资视角）

| 大师 | 验证透镜 | 核心追问 |
|------|---------|---------|
| 林奇 | 常识与求证 | 这门生意"看得懂"吗？六类中的哪一类？增长来自真实需求还是题材炒作？ |
| 郑希 | 产业景气与第一性原理 | 产业处于 ROE 曲线哪个位置？有无 ROE 向上拐点？全球产业链哪个环节率先景气？ |
| 李进 | 渗透率坐标与系统均衡 | 渗透率处于哪个区间？二阶导是加速还是减速？治理有无硬伤？ |
| 欧奈尔 | 信号与风控底线 | 技术面趋势是否确认？突破买点/抛售日信号？8% 止损底线在哪？ |

---

## 使用示例

### 示例 1：研究 AI 算力主线
```
/mid-era-alpha AI算力
```
定位算力产业链各环节渗透率区间，锁定核心高景气环节，识别核心 α，验证景气可持续性，给出 PEG 估值锚点与底仓/机动仓计划。

### 示例 2：研究人形机器人
```
/mid-era-alpha 人形机器人
```
建立主线认知地图，判断渗透率是否进入 10%-30% 黄金加速区，筛选真正有定价权与景气壁垒的 α，高频数据（订单/招标/出货）交叉验证。

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 时代α（1-3年景气版）研究报告 | `reports/{方向/行业名}-mid-era-alpha-{YYYYMMDD}.md` |

---

## 研究标准

### 与相邻技能的差异化定位

| Skill | 定位 | 何时用 |
|-------|------|--------|
| **`/mid-era-alpha`（本Skill）** | 时代级高增长主线的核心 α 识别 + 景气验证 + 底仓/机动仓与退出纪律 | 锁定 1-3 年高景气主线与核心 α |
| `/mid-industry-research` | 单赛道四维筛选（TAM/渗透率/业绩/地缘） | 锁定主线后深扫该赛道 |
| `/mid-industry-funnel` | 单赛道内逐层收敛到 3 底仓 + 2 机动仓 | 偏个股漏斗收敛 |
| `/mid-bottleneck-hunter` | 供应链咽喉位置挖第二、三层机会 | 物理供应链瓶颈机会 |

两者可互补：先用 `mid-era-alpha` 锁定时代主线与核心 α，再用 `mid-industry-research` 深扫该主线赛道、`mid-investment-research` / `mid-investment-team` 对锁定核心 α 做单公司深挖。

### 报告结构（六章节）

1. 时代主线认知地图（环节表 + 渗透率坐标 + 核心环节选择理由）
2. 核心问题的回答（最核心 1-3 年高景气主线 + 核心α + 为什么是它）
3. 景气可持续性验证（五维逐项 + 四大师透镜 + 管理层/科研转化 + 矛盾信号明示）
4. PEG 估值锚点与介入建议（PEG 五档 + 二阶导 + 分批建仓）
5. 底仓/机动仓与卖出纪律（拐点清单，链接 exit-signal/thesis-tracker --horizon mid/mid-thesis-drift）
6. 本报告可能错在哪（至少 3 条自我证伪）

---

## 工具依赖

### 财务数据获取工具

#### A股数据

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/a_share/stock_info.py` | A股信息查询 | `python tools/a_share/stock_info.py --search {公司名}` |
| `tools/a_share/stock_financial.py` | A股财务指标 | `python tools/a_share/stock_financial.py --code {股票代码}` |
| `tools/a_share/stock_quote.py` | A股行情数据（含 `--momentum` 动量/技术面） | `python tools/a_share/stock_quote.py --code {股票代码}` |
| `tools/a_share/stock_equity.py` | A股股权结构与财报下载 | `python tools/a_share/stock_equity.py --code {股票代码}` |

#### 港股数据

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/hk_stock/stock_financial.py` | 港股信息查询与财务指标 | `python tools/hk_stock/stock_financial.py --financial {股票代码}` |
| `tools/hk_stock/stock_quote.py` | 港股历史K线、指数数据 | `python tools/hk_stock/stock_quote.py --code {股票代码}` |

#### 美股数据

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/us_stock/stock_info.py` | 美股信息查询 | `python tools/us_stock/stock_info.py --search {公司名}` |
| `tools/us_stock/stock_quote.py` | 美股行情数据 | `python tools/us_stock/stock_quote.py --code {股票代码}` |
| `tools/us_stock/stock_financial.py` | 美股财务指标 | `python tools/us_stock/stock_financial.py --code {股票代码}` |

### 估值计算与验证工具

| 工具 | 功能 |
|------|------|
| `tools/common/financial_rigor.py` | 精确金融计算（`peg`/`implied-growth`/`pe-percentile`） |
| `tools/common/fx_rate.py` | 国际主要货币汇率（Akshare 优先 + yfinance 回退） |
| `tools/common/commodity_price.py` | 大宗商品价格（Akshare 优先 + yfinance 回退） |
| `tools/common/report_audit.py` | 报告审核与数据抽检 |

> **明确禁用 `tools/common/terminal_value.py`（十年 DCF）**：该工具属长期链估值口径，中期链不引用。PEG 五档口径唯一权威来源为 `/valuation-thermometer {公司名}`。

### 在研项目与年报抽取

| 工具 | 功能 |
|------|------|
| `tools/specialized/in_research_scan.py` | 在研重大项目扫描（gov/patent/bidding/academic 等 8 渠道） |
| `tools/common/annual_report_parser.py` | 年报 Markdown 定向抽取（员工/研发/收入分部/新品/供应链风险等） |
| `tools/specialized/trend_tech_screen.py` | 景气趋势五维打分（如需对核心 α 正向排序） |

### 网络信息搜索

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。

**中期景气·时代α场景下的搜索选型**：

- A股财报/研报/公告深查：anysearch 主 + doubao 辅
- 港股披露易/公告/回购：doubao --sites hkexnews.hk 主 + tavily 辅
- 美股 SEC filings/10-K：exa --type deep 主 + doubao 辅
- 实时资讯/舆情：doubao --finance

**搜索规范**：

- 时效性优先：使用 `--time-range month/week` 限制时间范围，禁止采用过时数据，搜索结果须标注来源日期
- 双源验证：A股 anysearch + doubao；港股 doubao + tavily；美股 exa + doubao
- 高频数据交叉验证是本技能核心（修正二），须尽可能获取周度/月度出货量、价格、订单、渗透率等实时指标

### PDF 文档提取

| 工具 | 功能 |
|------|------|
| `tools/common/pdf_extract.py`（首选） | 从年报 PDF 提取财务数据作为一手数据源 |
| Poppler 工具集（`pdftotext`/`pdftoppm`） | 回退方案：`pdf_extract.py` 返回失败时使用 |

---

## 核心原则

1. **证伪优先** — 每个核心判断附反面论据，矛盾信号优先采信，不按需取舍
2. **数据必须标注来源** — 关键数据至少 2 个来源交叉验证，误差 >1% 须标记
3. **估值禁用 LLM 心算** — 用 `financial_rigor.py` 的 `peg`/`implied-growth`/`pe-percentile` 精确计算，PEG 五档引用 `valuation-thermometer`
4. **不虚构数据** — 搜不到就标注"信息不足"，不用推测填充
5. **客观不两面讨好** — 先摆数据 → 推逻辑 → 出结论，结论直接明确
6. **持有不等于死拿** — 底仓/机动仓 + 拐点清单必须可观察、可证伪，命中 `exit-signal` 即执行

---

## 注意事项

- 开始研究前运行 `date` 确认当天日期，报告头部标注数据截止日期
- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 关键财务数据须从年报 PDF 一手数据源交叉验证
- 拐点清单必须逐条写明"观察什么数据、多久看一次"
- 报告发布前需通过 `report_audit.py` 数据抽检
- 并发硬约束：同时运行的子代理最多 2 个，产业链环节分批串行处理，搜索请求间隔 ≥ 2 秒，防止触发服务端 request burst 保护

---

## 局限性说明

- **资料可得性**：新兴行业资料较少，分析深度受限
- **未上市公司信息**：估值和财务信息可能不够准确
- **高频数据可得性**：部分环节缺乏周度/月度公开高频数据，交叉验证可能降级为季度数据
- **非实时数据**：工具获取的数据可能有延迟
- **AI 筛选偏见**：可能存在成熟行业偏好、龙头偏好、英文偏好
- **估值分位历史长度限制**：次新行业/公司历史分位参考价值有限
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [中长期（1~3年）价值投资研究工作步骤](../证券AI中长期（1~3年）价值投资研究工作步骤.md) — 中期链主工作流
- [中期行业研究](../mid-industry-research/README.md) — 单赛道四维筛选
- [估值温度计](../valuation-thermometer/README.md) — PEG 五档权威口径
- [投资论文追踪](../thesis-tracker/README.md) — `--horizon mid` 建仓后持续跟踪
- [卖出信号](../exit-signal/README.md) — P0~P5 六级卖出纪律
- [中期论文漂移](../mid-thesis-drift/README.md) — 景气假设六大维度逐条验证

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-09-10
- **最后更新**：2026-09-10（首次创建，移植自 era-alpha 技能，将四大师透镜/估值/持有卖出口径整体替换为 V2.0 中期景气口径）
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。