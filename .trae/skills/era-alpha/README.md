# 时代α捕手 (Era Alpha)

高增长核心资产的识别-验证-持有框架，聚焦时代级高增长主线的 α 企业识别与增长可持续性验证，给出明确的介入与退出纪律。

---

## 快速开始

### 基本调用方式

```
/era-alpha {行业/方向}
```

例如：

- `/era-alpha AI算力`
- `/era-alpha 人形机器人`
- `/era-alpha 创新药出海`

---

## 核心功能

对指定行业/方向执行"时代α五步法"，找出当下最核心高增长行业中真正有定价权、有壁垒、能持续跑赢同行的 α 企业。

### 五步研究框架

1. **行业认知地图** — 诊断行业处于周期/成长/时代拐点哪一阶段，锁定 2-3 个真正有时代 α 的核心环节
2. **自问核心问题** — 该资产为何此刻能产生超越市场的 α，写下 3-5 个可证伪的核心假设
3. **全方位验证** — 五维验证（财报/高频数据/行业跟踪/竞争格局/宏观）+ 四大师验证透镜
4. **估值锚点与介入** — 用精确工具求估值锚点，替代"不看股价"的盲目买入
5. **持有纪律与拐点清单** — 三层拐点信号（宏观/行业/公司），硬链接 `exit-signal` 与 `thesis-tracker`

### 三项修正（相比原版操作手册）

| 修正 | 内容 |
|------|------|
| 修正一（精简范围） | 不覆盖所有行业，聚焦 2-3 个核心环节做深做透 |
| 修正二（高频数据交叉验证） | 财报是三个月前的体检报告，用周度/月度高频数据做实时体温计校正 |
| 修正三（估值锚点） | 合理/低估重仓、明显泡沫减仓、拐点确认清仓，不闭眼买 |

### 四大师验证透镜（长期价值投资视角）

| 大师 | 验证透镜 | 核心追问 |
|------|---------|---------|
| 段永平 | 生意本质 | 这是一门好生意吗？ |
| 巴菲特 | 护城河 | 10 年后护城河还在吗？ |
| 芒格 | 风险逆向 | 最可能怎么失败？ |
| 李录 | 文明趋势定位 | 范式转移还是阶段性热潮？ |

---

## 使用示例

### 示例 1：研究 AI 算力主线
```
/era-alpha AI算力
```
诊断算力产业链各环节所处阶段，锁定核心高增长环节，识别核心 α，验证增长可持续性，给出估值锚点与拐点清单。

### 示例 2：研究人形机器人
```
/era-alpha 人形机器人
```
建立产业链认知地图，判断是否进入时代拐点，筛选真正有定价权与壁垒的 α，高频数据（订单/招标/出货）交叉验证。

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 时代α研究报告 | `reports/{方向/行业名}-era-alpha-{YYYYMMDD}.md` |

---

## 研究标准

### 与相邻技能的差异化定位

| Skill | 定位 | 何时用 |
|-------|------|--------|
| **`/era-alpha`（本Skill）** | 时代级高增长主线的 α 识别 + 增长验证 + 持有/退出纪律 | 锁定 10 年维度高增长核心资产 |
| `/industry-research` | 产业链全景扫描 + 四大师个股分析 | 首次研究一个行业，看清产业格局 |
| `/industry-funnel` | 全市场 30-60 家逐层精选到 3 家 | 产业研究后精选标的 |
| `/bottleneck-hunter` | 供应链咽喉位置挖第二、三层机会 | 物理供应链瓶颈套利 |

两者可互补：先用 `era-alpha` 锁定时代主线与核心 α，再用 `industry-research`/`investment-team` 做单公司深挖。

### 报告结构（六章节）

1. 行业认知地图（环节表 + 核心环节选择理由）
2. 核心问题的回答（最核心高增长环节 + 核心α + 为什么是它）
3. 增长可持续性验证（五维逐项 + 四大师透镜 + 矛盾信号明示）
4. 估值锚点与介入建议
5. 持有纪律与拐点清单（可观察、可证伪）
6. 本报告可能错在哪（至少 3 条自我证伪）

---

## 工具依赖

### 财务数据获取工具

#### A股数据

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/a_share/stock_info.py` | A股信息查询 | `python tools/a_share/stock_info.py --search {公司名}` |
| `tools/a_share/stock_financial.py` | A股财务指标 | `python tools/a_share/stock_financial.py --code {股票代码}` |
| `tools/a_share/stock_quote.py` | A股行情数据 | `python tools/a_share/stock_quote.py --code {股票代码}` |
| `tools/a_share/stock_equity.py` | A股股权结构与财报下载 | `python tools/a_share/stock_equity.py --code {股票代码}` |

#### 港股数据

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/hk_stock/stock_financial.py` | 港股信息查询与财务指标 | `python tools/hk_stock/stock_financial.py --financial {股票代码}` |
| `tools/hk_stock/stock_quote.py` | 港股历史K线、指数数据 | `python tools/hk_stock/stock_quote.py --code {股票代码}` |

#### 美股数据

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/us_stock/stock_info.py` | 美股实时行情与估值指标 | `python tools/us_stock/stock_info.py --realtime AAPL` |
| `tools/us_stock/stock_quote.py` | 美股历史K线、三大指数 | `python tools/us_stock/stock_quote.py --daily AAPL` |
| `tools/us_stock/stock_financial.py` | 美股财务报表、分红、机构持仓 | `python tools/us_stock/stock_financial.py --financials AAPL` |

### 估值计算与验证工具

| 工具 | 功能 |
|------|------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值校验、三情景估值） |
| `tools/common/terminal_value.py` | 长期折现估值（十年尺度终值、ROIC/g 硬约束） |
| `tools/common/fx_rate.py` | 国际主要货币汇率（Akshare 优先 + yfinance 回退，19 货币对） |
| `tools/common/commodity_price.py` | 大宗商品价格（Akshare 优先 + yfinance 回退，18 品种） |
| `tools/common/report_audit.py` | 报告审核与数据抽检 |

### 网络信息搜索

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。

**时代α场景下的搜索选型**：

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
3. **估值禁用 LLM 心算** — 用 `financial_rigor.py`/`terminal_value.py` 精确计算
4. **不虚构数据** — 搜不到就标注"信息不足"，不用推测填充
5. **客观不两面讨好** — 先摆数据 → 推逻辑 → 出结论，结论直接明确
6. **持有不等于死拿** — 持有纪律与拐点清单必须可观察、可证伪

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
- **高频数据可得性**：部分环节缺乏周度/月度公开高频数据
- **非实时数据**：工具获取的数据可能有延迟
- **AI 筛选偏见**：可能存在成熟行业偏好、龙头偏好、英文偏好
- **估值分位历史长度限制**：次新行业/公司历史分位参考价值有限
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [行业研究](../industry-research/README.md) — 产业链全景扫描与四大师分析
- [投资论文追踪](../thesis-tracker/README.md) — 建仓后持续跟踪
- [卖出信号](../exit-signal/README.md) — P0~P5 六级卖出纪律

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-09-10
- **最后更新**：2026-09-10（首次创建，移植自 era-alpha 技能，采用五步法 + 四大师验证透镜）
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。