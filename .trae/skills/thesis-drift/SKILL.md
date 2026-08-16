---
name: thesis-drift
description: 投资论文漂移检测：分清事实变化与措辞变化。对比新旧报告，基于证据判定论文是否漂移，输出结构化漂移报告。
disable-model-invocation: true
---

# 投资论文漂移检测：分清事实变化与措辞变化

对 $ARGUMENTS 执行投资论文漂移检测。基于证据判定论文是否漂移，区分事实变化与价格变化。

**支持输入格式**：
- `公司名 旧报告路径 新报告路径` — 指定两份研究报告或论文快照进行对比
- `公司名 reports/{公司名}-thesis-旧日期.md reports/{公司名}-thesis-新日期.md` — 对比两份带日期的论文快照
- `公司名` — 自动查找 `reports/{公司名}-thesis.md` 及同目录历史快照；如果没有基线则转入缺失基线处理

> "当事实改变时，我就改变想法。你呢？" —— 凯恩斯
>
> "股价波动不是论文漂移，事实变了才是。" —— AI Berkshire

## 设计理念

长期持仓最难的不是每天读新闻，而是区分三件事：

1. **事实改变**：收入、利润率、竞争格局、管理层行为、资本配置发生可验证变化
2. **价格改变**：市场情绪或估值倍数变化，但生意本身未变
3. **措辞改变**：两份报告表达不同，但底层证据和判断没有变化

投资论文漂移检测的目标是：**只在证据变化时承认论文变化**。不能因为报告换了写法就制造漂移，也不能因为股价涨跌就误判基本面。

本 Skill 依赖 `/thesis-tracker` 输出的结构化维度：核心假设清单、红线清单、估值锚点、追踪记录表。没有这些结构时，先补齐基线，再做漂移检测。

---

## 执行流程

### 第一步：判断操作模式

解析 `$ARGUMENTS`：

- 如果提供两份报告路径 → 进入**指定报告对比**模式
- 如果只提供公司名 → 查找 `reports/{公司名}-thesis.md` 及历史快照，进入**自动快照对比**模式
- 如果只找到一份报告或没有历史基线 → 进入**缺失基线处理**模式
- 如果两份报告不是同一家公司 → 停止并要求用户确认，不做跨公司漂移判断

---

## 模式A：指定报告对比

### A1：读取并校验两份报告

读取旧报告和新报告，提取：

- 报告日期、公司名、股票代码
- 核心论文（5句话）
- 核心假设清单
- 红线清单
- 估值锚点
- 追踪记录表
- 管理层质量判断
- 竞争护城河判断
- 当前建议动作（买入 / 持有 / 观察 / 减仓 / 清仓）

如果报告缺少关键结构，先标注"结构缺失"，但仍尽量从正文中抽取证据；抽取不到的维度标为"无法判断"，不能编造结论。

---

### A2：证据归一化

把两份报告中的事实证据整理成同一张表：

| 维度 | 旧报告证据 | 新报告证据 | 数据来源 | 是否可验证 |
|------|-----------|-----------|---------|-----------|
| 估值锚点 | | | | |
| 核心假设 | | | | |
| 红线 | | | | |
| 管理层质量 | | | | |
| 竞争护城河 | | | | |

**只比较证据，不比较文风。** 如果新旧报告只是同义改写、排序变化、语气变化，但事实数据和判断阈值没有变化，判定为 Unchanged。

---

### A3：数值与估值校验

所有数值变化必须使用 `tools/common/financial_rigor.py` 做精确计算，禁止 LLM 心算：

```bash
# 估值验证
python tools/common/financial_rigor.py verify-valuation \
  --price {当前价格} \
  --eps {EPS} \
  --bvps {每股净资产} \
  --fcf-per-share {每股自由现金流}

# 提示：跨币种（港股/美股）市值统一口径时，先用 `python tools/common/fx_rate.py --code USDCNY,HKDCNY` 获取实时汇率，勿用固定汇率
# 市值验证
python tools/common/financial_rigor.py verify-market-cap \
  --price {价格} --shares {股本} --reported {报告市值} --currency {币种}

# 数据交叉验证
python tools/common/financial_rigor.py cross-validate \
  --field {字段} --values '{JSON}' --unit {单位}

# 三情景估值
python tools/common/financial_rigor.py three-scenario \
  --price {价格} --eps {EPS} --shares {股本亿} \
  --growth {乐观} {中性} {悲观} --pe {乐观PE} {中性PE} {悲观PE}

# 精确计算
python tools/common/financial_rigor.py calc --expr '{精确算式}'
```

关键财务数据必须至少两处独立来源交叉验证。来源不足、口径不一致、无法复核的数字必须标注为"低置信度 / 待核实"。

---

### A4：逐维度判定漂移

固定使用以下维度，不要临时增减：

| 维度 | 判定重点 | Improved | Unchanged | Weakened |
|------|---------|----------|-----------|----------|
| 估值锚点 | 内在价值、PE/PB/FCF Yield、安全边际、目标价区间 | 安全边际扩大或内在价值上修且经工具验算 | 估值区间和安全边际无实质变化 | 安全边际收窄、内在价值下修或估值假设失效 |
| 核心假设清单 | 收入增速、利润率、现金流、用户/订单/产能等可验证假设 | 更多假设被新证据强化 | 假设状态与证据基本一致 | 假设边际弱化、受损或破裂 |
| 红线清单 | 诚信、监管、业务衰退、竞争突破、管理层异常动作 | 原有红线风险解除或显著下降 | 未触发且风险水平不变 | 红线被触发或触发概率上升 |
| 管理层质量 | 诚信、资本配置、回购分红、执行力、股东友好度 | 新行为提高信任度 | 行为延续旧判断 | 行为损害信任或资本配置变差 |
| 竞争护城河 | 市占率、定价权、网络效应、成本优势、替代威胁 | 护城河变宽或竞争优势被验证 | 格局无实质变化 | 护城河被削弱或竞对突破 |

每个维度只能给出三类结论：**Improved / Unchanged / Weakened**。

---

### A5：证据驱动规则

每个非 Unchanged 的结论必须引用导致变化的具体新证据：

- 财报行项目：例如收入增速、毛利率、经营现金流、回购金额、净现金
- 监管披露：例如 10-K/20-F、年报、中报、港交所公告、SEC filing
- 新闻事件：例如管理层变动、监管处罚、重大客户流失、竞品突破
- 价格与估值：必须说明这是"估值变化"还是"基本面变化"，不能混淆

如果找不到能解释变化的证据，必须判定为 **Unchanged** 或 **无法判断**，不能用措辞差异推断漂移。

---

### A6：补充数据获取（如需要）

如果报告中的数据需要更新或验证，使用以下工具：

#### A股数据

```bash
# 股票信息查询
python tools/a_share/stock_info.py --search {公司名}

# 财务指标
python tools/a_share/stock_financial.py --code {股票代码}

# 股票行情
python tools/a_share/stock_quote.py --code {股票代码}
```

#### 港股数据

```bash
# 股票信息与财务指标
python tools/hk_stock/stock_financial.py --financial {股票代码}

# 股票行情
python tools/hk_stock/stock_quote.py --code {股票代码}
```

#### 网络信息获取

统一使用本地五工具组合（详见 [web-search-tools](../tools-scripts/web-search-tools.md)）：

- A股：`anysearch` 主 + `doubao --finance` 辅
- 港股：`doubao --sites hkexnews.hk` 主 + `tavily` 辅（双源 doubao+tavily）
- 美股：`exa --type deep` 主 + `doubao` 辅（双源 exa+doubao）

---

### A7：输出漂移报告

#### 报告结构

```markdown
# {公司名} 投资论文漂移检测报告
**对比时间跨度：{旧报告日期} ~ {新报告日期}**

## 一、总体结论：论文是否漂移
未漂移 / 正向漂移 / 负向漂移 / 证据不足无法判断

## 二、维度漂移表
| 维度 | 旧判断 | 新判断 | 漂移方向 | 触发证据 | 置信度 |
|------|-------|-------|:--------:|---------|:------:|

## 三、证据差异明细
各维度的具体证据对比

## 四、估值与数值验算
使用 financial_rigor.py 的验算结果

## 五、建议动作迁移
例如：Watch → Buy、Buy → Hold、Hold → Reduce、Reduce → Exit

## 六、不确定项与需补充来源
标注无法判断的维度和原因

## 七、下次跟踪重点
下一份财报 / 监管披露 / 管理层说明 / 竞对数据
```

#### 维度漂移表

| 维度 | 旧判断 | 新判断 | 漂移方向 | 触发证据 | 置信度 |
|------|-------|-------|:--------:|---------|:------:|
| 估值锚点 | | | Improved / Unchanged / Weakened | | 高/中/低 |
| 核心假设清单 | | | Improved / Unchanged / Weakened | | 高/中/低 |
| 红线清单 | | | Improved / Unchanged / Weakened | | 高/中/低 |
| 管理层质量 | | | Improved / Unchanged / Weakened | | 高/中/低 |
| 竞争护城河 | | | Improved / Unchanged / Weakened | | 高/中/低 |

**Unchanged 行的触发证据写 `—`，不要为了填表编造证据。**

#### 总体结论必须回答

1. **论文是否漂移？** 未漂移 / 正向漂移 / 负向漂移 / 证据不足无法判断
2. **漂移来自哪里？** 估值 / 基本面 / 管理层 / 竞争格局 / 红线事件
3. **是事实变化还是价格变化？** 明确拆开说明
4. **建议动作如何迁移？** 例如：Watch → Buy、Buy → Hold、Hold → Reduce、Reduce → Exit
5. **下一步需要什么证据？** 下一份财报 / 监管披露 / 管理层说明 / 竞对数据

---

## 模式B：自动快照对比

### B1：查找快照

在 `reports/` 中查找：

- `reports/{公司名}-thesis.md`
- `reports/{公司名}-thesis-*.md`
- `reports/{公司名}/` 目录下包含 `thesis`、`论文`、`追踪` 的报告

选择时间最早且结构完整的文件作为旧报告，时间最新的文件作为新报告。若用户指定日期，以用户指定为准。

---

### B2：防止错误配对

对比前必须确认：

- 公司名或股票代码一致
- 报告日期不同
- 两份报告都包含可抽取的论文结构或研究结论

如果无法确认同一公司，停止并要求用户提供明确路径。

---

### B3：执行模式A

找到两份有效快照后，按模式A完整执行。

---

## 模式C：缺失基线处理

如果只找到一份报告或没有找到旧快照：

1. 明确说明：**缺少可比较的历史基线，不能执行漂移检测**
2. 不要根据记忆或市场印象补造旧论文
3. 引导用户先使用 `/thesis-tracker {公司名} 建立论文` 建立结构化基线
4. 如果当前报告已足够完整，可建议将它保存为 `reports/{公司名}-thesis.md` 作为未来漂移检测基线

输出格式：

```markdown
# 无法执行论文漂移检测

**原因**：缺少历史基线

## 已找到
- 当前报告：{路径 / 未找到}
- 历史基线：未找到

## 建议
1. 先运行 `/thesis-tracker {公司名} 建立论文`
2. 下次有新财报或重大事件后，再运行 `/thesis-drift {公司名} 旧报告 新报告`
```

---

## 工具使用指南

### 本地数据获取工具

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票信息查询 | `python tools/a_share/stock_info.py --search 紫金矿业` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 601899` |
| A股 | `tools/a_share/stock_quote.py` | 历史股价与实时行情 | `python tools/a_share/stock_quote.py --code 601899` |
| A股 | `tools/a_share/stock_equity.py` | 股权结构与年报下载 | `python tools/a_share/stock_equity.py --code 601899` |
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
- **国际货币汇率**（跨市场估值/市值统一口径折算）：`tools/common/fx_rate.py`，详见 [A股工具使用指南汇率章节](file:///f:/Financial_Investment_Analysis/docs/A股工具使用指南.md)

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证、交叉验证、三情景估值等） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |
| `tools/common/report_audit.py` | 报告数据抽检与审核 | `python tools/common/report_audit.py extract --report reports/xxx.md` |

**漂移检测中的应用**：
- 估值锚点数值验算（PE、ROE、安全边际等）
- 市值校验（股价 × 总股本）
- 数据交叉验证（新旧报告数据对比）
- 三情景估值模型（验证估值假设变化）

### 网络搜索工具

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。完整角色定位、市场×场景选型矩阵、命令速查、多源验证示例见 [web-search-tools](../tools-scripts/web-search-tools.md)。

**投资论文漂移场景下的搜索选型**：
- A股：`anysearch --tag finance` 主 + `doubao --finance` 辅
- 港股：`doubao --sites hkexnews.hk` 主 + `tavily` 辅；双源 doubao+tavily
- 美股：`exa --type deep` 主 + `doubao` 辅；双源 exa+doubao

**搜索规范**（必须遵守）：
1. **时效性优先**：使用 `--time-range month/week` 限制时间范围，优先获取最新信息，避免使用过时数据
2. **数据源日期**：搜索结果必须包含数据来源日期；过时数据须明确标注时效性说明
3. **双源验证**：非境内上市须按市场双源验证（港股 doubao+tavily；美股 exa+doubao）
4. **多角度搜索**：从财报数据、管理层发言、监管披露、竞对动态等多维度收集信息
5. **信息缺口标注**：关键信息缺失时标注"信息不足"，不得用推测填充

**重要内容（同时调用）**：

对于港股/美股的重要漂移检测，建议**同时调用多个工具**，互为补充：

```bash
# 港股/美股：双源验证（并行执行）
python tools/common/doubao_search.py "腾讯 最新财报 管理层讨论" --finance --need-content --time-range month
python tools/common/tavily_search.py "腾讯 最新财报 管理层讨论" --max-results 5
```

---

## 注意事项

1. **证据优先于措辞** — 同义改写不是漂移，只有事实证据变化才是漂移
2. **基本面优先于股价** — 股价涨跌只影响估值锚点，不自动改变生意质量
3. **数值必须验算** — 所有百分比、估值倍数、目标价差异必须用 `tools/common/financial_rigor.py`
4. **不确定就标注不确定** — 来源缺失、口径不一致、无法复核时，不要硬判
5. **红线单独处理** — 红线触发优先级高于估值便宜，不能被低 PE 掩盖
6. **输出必须可复盘** — 每个 Improved / Weakened 结论都要能追溯到具体证据
7. **不预设立场** — 不因为持有就倾向于"未漂移"，证据指向哪边就写哪边
8. **诚实面对信息缺口** — 宁可标注"无法判断"，也不要用推测填充
9. **网络搜索时效性**：使用 `--time-range month/week` 限制时间范围，优先获取最新信息
10. **非境内上市双源验证**：港股/美股公司须按市场双源验证（港股 doubao+tavily；美股 exa+doubao）

---

## 局限性

1. **数据可得性**：港股小票、新上市公司可能无法获取到完整信息
2. **报告结构依赖**：如果报告缺少核心假设清单、红线清单等结构，漂移检测质量会下降
3. **估值估算主观性**：内在价值估算存在主观判断，不同方法可能得出不同结论
4. **非实时数据**：工具获取的数据可能有延迟，不是实时数据
5. **不构成投资建议**：本技能仅用于学习与研究，不构成任何投资建议
6. **证据判断主观性**：即使有证据，判断是否"显著"变化仍有主观性

---

## 与现有 Skill 的关系

| Skill | 定位 | 何时用 |
|-------|------|--------|
| **`/thesis-drift`（本Skill）** | **论文漂移检测** | **有新财报或重大事件时，对比旧论文** |
| `/thesis-tracker` | 建立和维护投资论文 | 首次建立论文或定期更新 |
| `/investment-team` | 四Agent全面公司研究 | 首次研究一家公司 |
| `/earnings-team` | 六Agent团队精读 + 公众号发布 | 重要公司的关键财报 |
| `/portfolio-review` | 组合层面审视与优化 | 季度组合审视 |

---

## 报告示例

### 输入示例

```
腾讯 reports/腾讯-thesis-20260101.md reports/腾讯-thesis-20260722.md
```

### 输出文件

`reports/腾讯/腾讯-drift-20260722.md`

### 报告摘要示例

```markdown
# 腾讯投资论文漂移检测报告
**对比时间跨度：2026-01-01 ~ 2026-07-22**

## 一、总体结论：论文是否漂移

**结论**：正向漂移（强化）

**漂移来源**：基本面改善 + 估值下降

**事实变化 vs 价格变化**：
- 事实变化：游戏业务恢复增长、视频号DAU超预期
- 价格变化：股价下跌10%，估值从20x PE降至18x PE，安全边际扩大

## 二、维度漂移表

| 维度 | 旧判断 | 新判断 | 漂移方向 | 触发证据 | 置信度 |
|------|-------|-------|:--------:|---------|:------:|
| 估值锚点 | 20x PE，安全边际15% | 18x PE，安全边际25% | Improved | Q2财报、股价下跌 | 高 |
| 核心假设清单 | 游戏增长-5%，广告增长15% | 游戏增长+8%，广告增长20% | Improved | Q2财报数据 | 高 |
| 红线清单 | 未触发 | 未触发 | Unchanged | — | 高 |
| 管理层质量 | 回购积极，诚信度高 | 回购金额超预期，诚信度高 | Improved | Q2回购公告 | 高 |
| 竞争护城河 | 视频号DAU增长，但落后抖音 | DAU超预期，差距缩小 | Improved | Q2运营数据 | 中 |

## 三、建议动作迁移

**从 Hold → Buy**

理由：
- 核心假设改善：游戏业务恢复增长
- 估值锚点改善：安全边际从15%扩大到25%
- 管理层质量维持高水平，回购超预期
- 竞争护城河有改善迹象

## 四、下次跟踪重点

- Q3财报：游戏业务增长持续性
- 视频号商业化进展
- 监管政策变化
```