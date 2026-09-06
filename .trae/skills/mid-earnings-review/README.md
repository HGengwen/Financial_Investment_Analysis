# 财报精读（轻量版·1~3年景气投资版）(Mid Earnings Review)

单 Agent 快速财报精读，核心是「用每季度财报验证景气逻辑、更新卖出纪律」

> 本技能属**中期链（1-3 年）**，与长期版 [earnings-review](../earnings-review/README.md)（10 年 / 巴菲特-李录一手资料精读）及团队版 [mid-earnings-team](../mid-earnings-team/README.md)（四大师并行 + 编辑 + 读者评审 + 公众号发布）**物理隔离、功能互补**。禁止使用「护城河永续」「终局思维」「持有 10 年」等长期框架术语。

---

## 快速开始

### 基本调用方式

```
/mid-earnings-review {公司名} {期间}
```

支持输入格式：
- `{公司名} {季度}` — 例如：`腾讯 2025Q4`、`新易盛 2025Q2`
- `{公司名} {年报}` — 例如：`中际旭创 2024年报`、`宁德时代 2025年报`
- `{公司名} 最新` — 默认读取最近一期，例如：`美团 最新`

例如：
- `/mid-earnings-review 新易盛 2025Q2`
- `/mid-earnings-review 中际旭创 2024年报`
- `/mid-earnings-review 腾讯 最新`

---

## 核心功能

对指定公司进行单 Agent 轻量财报精读分析，从一手资料出发，用四大景气大师的分析维度验证景气逻辑、更新卖出纪律。

### 四位大师分析维度（单 Agent 内并行应用，非多 Agent 角色）

- ⚡ **郑希 · 产业景气验证** — ROE 拐点到了吗？二阶导是正是负？渗透率到哪了？
- 🕵️ **林奇 · 生意与估值** — 收入量价拆解、现金流质量、PEG 更新（引用 `valuation-thermometer`）、估值陷阱排查
- 🛡️ **欧奈尔 · 风控底线** — 止损位要不要更新？趋势信号如何？
- ⚖️ **李进 · 组合管理与治理** — 管理层诚信变化？科研转化进展？底仓/机动仓怎么调？

### 十二步精读流程

1. **资料可得性评级** — A级（完整原文）/ B级（部分原文）/ C级（仅第三方摘要）
2. **获取一手资料** — A股优先下载财报PDF，港股美股并行获取多源材料
3. **核心财务数据提取与验证** — 景气三要素（ROE/增速/二阶导）、收入利润、现金流、资产负债表
4. **PEG 估值定位** — 引用 `valuation-thermometer`，不重复定义五档阈值
5. **分批建仓规则** — 底仓 1/3 起，调用回调/确认加仓；仓位红线硬编码
6. **左侧布局 vs 右侧重仓策略对照**
7. **管理层讨论精读** — 景气趋势判断、语气分析、承诺追踪
8. **附注与隐藏信息挖掘** — 科研转化、管理层四维度、地缘政治
9. **决策优先级检查** — 引用 `exit-signal` P0~P5，命中即停、禁止跳过 P0
10. **底仓/机动仓分离管理** — 底仓 60%~80%，机动仓 20%~40%
11. **「假如空仓」测试**
12. **季度复盘检查清单** — 7 项必查

### 设计理念

一份好的景气投资财报分析要回答两个问题：
1. **景气逻辑是否成立** — ROE 趋势、二阶导、渗透率、管理层是否在抓住窗口
2. **卖出纪律是否触发** — 本季度数据是否触发了 `exit-signal` 的 P0~P5 任何一级

一句话：核心从「生意分析」转向「景气验证 + 卖出纪律」。

---

## 使用示例

### 示例1：精读A股季度财报
```
/mid-earnings-review 新易盛 2025Q2
```
 下载新易盛2025Q2财报，快速验证光模块景气逻辑与订单兑现，更新卖出纪律

### 示例2：精读A股年报
```
/mid-earnings-review 中际旭创 2024年报
```
 使用 `stock_equity.py` 下载年报PDF，按十二步流程精读

### 示例3：精读港股季度财报
```
/mid-earnings-review 腾讯 2025Q4
```
 聚焦 ROE 趋势与 AI 渗透率，验证景气逻辑并更新卖出纪律

### 示例4：快速精读最新一期财报
```
/mid-earnings-review 美团 最新
```
 自动读取最近一期财报，执行单 Agent 快速精读

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 财报精读报告 | `reports/{公司名}/{公司名}-mid-earnings-review-{期间}.md` |

### 报告结构

```
一、核心数据速览（景气三要素表格）
二、本期最重要的 3 个景气变化（不超过 500 字）
三、ROE 趋势与二阶导判断
四、管理层语气与承诺追踪
五、附注中的景气信号（科研转化/管理层四维度）
六、PEG 估值定位与操作建议（引用 valuation-thermometer）
七、地缘政治风险更新
八、仓位管理状态（底仓/机动仓）
九、假如空仓测试
十、卖出纪律更新（P0~P5 检查表，引用 exit-signal）
十一、季度复盘检查清单（7 项必查）
十二、结论：景气逻辑是否成立，卖出纪律是否触发，操作建议
```

### 结论必须明确回答 5 个问题

1. **ROE 趋势如何？** 上升 / 持平 / 拐头向下 → 对景气逻辑的影响
2. **二阶导（增速加速度）如何？** 正 / 负 / 持平 → 对估值中枢的影响
3. **PEG 处于哪一档？** （引用 `valuation-thermometer`）结合渗透率位置交叉比对
4. **卖出纪律触发了吗？** 引用 `exit-signal` P0~P5 检查结果
5. **操作建议**：持有 / 加仓 / 减仓 / 清仓，底仓/机动仓分层说明

---

## 工具依赖

### 本地数据获取工具

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票信息查询 | `python tools/a_share/stock_info.py --search 新易盛` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 300502` |
| A股 | `tools/a_share/stock_quote.py` | 历史股价与实时行情 | `python tools/a_share/stock_quote.py --code 300502` |
| A股 | `tools/a_share/stock_equity.py` | 股权结构与财报下载 | `python tools/a_share/stock_equity.py --code 300502` |
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
- **国际货币汇率**（跨币种财报数据折算）：`python tools/common/fx_rate.py --code USDCNY,HKDCNY`

### 财报下载与 PDF 阅读工具（A股专用）

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `stock_equity.py` | 下载年报/半年报/季报PDF | `python tools/a_share/stock_equity.py --code 300502 --download-report --report-type annual` |
| `pdf_extract.py` | PDF文字与表格提取（首选） | `python tools/common/pdf_extract.py markdown cninfo_reports/300502_2024年报.pdf --save-md` |

**流程检查点**：确认PDF下载成功后，方可进行后续财报阅读分析。`pdf_extract.py` 返回失败时才回退 Poppler 工具集，详见 [PDF文档内容提取技能](../tools-scripts/pdf-extraction.md)。

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证、交叉验证等） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |
| `tools/common/report_audit.py` | 报告数据抽检与审核（准出流程） | `python tools/common/report_audit.py extract --report reports/xxx.md` |

**重要约束**：
- 估值数据须使用 `financial_rigor.py` 校验，禁止 LLM 心算
- PEG 估值档位以 `/valuation-thermometer` 输出为准，本技能不重复定义五档阈值
- 卖出纪律以 `/exit-signal` 的 P0~P5 输出为准，本技能不重复定义触发阈值

### 网络搜索工具

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。完整角色定位、市场×场景选型矩阵、命令速查、多源验证示例见 [web-search-tools](../tools-scripts/web-search-tools.md)。

**财报精读场景下的搜索选型**：
- A股：`anysearch --tag finance` 主 + `doubao --finance` 辅
- 港股：`doubao --sites hkexnews.hk` 主 + `tavily` 辅；双源 doubao+tavily
- 美股：`exa --type deep` 主 + `doubao` 辅；双源 exa+doubao

**重要约束**：
- A股财报必须优先使用 `stock_equity.py` 下载原始PDF，**下载完成后方可进行后续分析**
- 关键财务数据须至少两个来源交叉验证，误差 >1% 须标记

---

## 核心原则

1. **读原文，不读摘要** — 尽一切可能获取一手资料，避免依赖二手信息
2. **看变化，不看绝对值** — 趋势比数字本身重要，景气投资尤其关注增速变化
3. **听语气，不只听内容** — 管理层怎么说和说了什么一样重要
4. **查附注，不只看正文** — 魔鬼藏在细节里：研发资本化率、关联交易、或有负债
5. **给结论，不做汇总** — 精读的目的是形成判断，不是复述财报
6. **每季必答核心问题** — 景气逻辑是否成立？卖出纪律是否触发？
7. **引用不重复定义** — 估值/卖出/产业景气/二阶导/治理评分一律引用对应权威 Skill
8. **中期口径红线** — 禁止使用「护城河永续」「终局思维」「持有10年」等长期框架术语

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- A股公司必须首先使用 `stock_equity.py` 下载原始财报PDF，**下载完成后**方可进行后续分析
- 资料可得性评级（A/B/C级）需在报告中标注，影响分析深度
- 所有数据必须标注来源，关键财务数据至少两个独立来源交叉验证，误差>1%须标记
- 报告发布前必须通过 `tools/common/report_audit.py` 数据抽检
- 不预设立场：先摆数据 → 推逻辑 → 出结论
- 网络搜索须使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 港股/美股公司须按市场双源验证（港股 doubao+tavily；美股 exa+doubao）
- 止损纪律优先：当 PEG「便宜」与 P0/P1 止损信号冲突时，止损优先于估值

---

## 局限性说明

- **资料可得性**：部分公司的完整财报原文可能难以获取，导致评级为 B 或 C 级
- **扫描版PDF限制**：A股年报常为扫描版PDF，可能无法提取文本内容，影响附注分析
- **语言限制**：非中英文财报可能无法准确解读
- **非实时数据**：工具获取的数据可能有延迟，不是实时数据
- **景气判断不确定性**：ROE 趋势和二阶导是滞后指标，可能无法提前捕捉拐点
- **渗透率数据可得性**：细分行业渗透率缺乏官方统计，需依赖第三方估算，按 A/B/C 三级置信度标注
- **地缘政治不可预测**：制裁、关税等黑天鹅事件无法通过框架完全规避
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [财报精读团队（中期版）](../mid-earnings-team/README.md) — 四大师并行 + 公众号发布（需深度 + 发布时用）
- [财报精读（长期版）](../earnings-review/README.md) — 长期链巴菲特-李录一手资料精读
- [中期投研团队](../mid-investment-team/README.md) — 四角色中期全面公司研究
- [中期投资检查清单](../mid-investment-checklist/README.md) — 买入前七关景气检查
- [估值温度计](../valuation-thermometer/README.md) — PEG五档温度（本 Skill 估值口径来源）
- [卖出信号](../exit-signal/README.md) — P0~P5 卖出纪律（本 Skill 卖出纪律口径来源）
- [季度加速度](../qoq-accelerator/README.md) — 二阶导判断（辅助）
- [中期行业研究](../mid-industry-research/README.md) — 产业景气/渗透率口径来源
- [中期管理层纵深](../mid-management-deep-dive/README.md) — 管理层/科研转化口径来源

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-09-05
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。