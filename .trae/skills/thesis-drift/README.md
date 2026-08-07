# 论文漂移检测 (Thesis Drift)

分清事实变化与措辞变化：对比新旧报告，基于证据判定论文是否漂移，输出结构化漂移报告

---

## 快速开始

### 基本调用方式

```
/thesis-drift {公司名} {旧报告路径} {新报告路径}
```

支持三种输入格式：

| 输入方式 | 示例 | 说明 |
|---------|------|------|
| 指定报告对比 | `/thesis-drift 腾讯 reports/腾讯-thesis-20260101.md reports/腾讯-thesis-20260722.md` | 对比两份指定报告 |
| 自动快照对比 | `/thesis-drift 腾讯` | 自动查找 `reports/{公司名}-thesis*.md` 历史快照 |
| 缺失基线处理 | `/thesis-drift 腾讯`（无历史快照时） | 提示先建立论文基线 |

例如：
- `/thesis-drift 腾讯 reports/腾讯-thesis-20260101.md reports/腾讯-thesis-20260722.md`
- `/thesis-drift 茅台`
- `/thesis-drift 英伟达 reports/nvidia-thesis-q1.md reports/nvidia-thesis-q2.md`

---

## 核心功能

对指定公司的投资论文执行漂移检测，基于证据判定论文是否漂移，严格区分事实变化、价格变化与措辞变化。

### 三种操作模式

1. **模式A：指定报告对比** — 用户提供两份报告路径，完整执行七步漂移检测
2. **模式B：自动快照对比** — 自动查找 `reports/` 中的历史快照，按时间选取新旧报告对比
3. **模式C：缺失基线处理** — 无历史基线时，引导用户先建立论文

### 五大漂移检测维度

| 维度 | 判定重点 |
|------|---------|
| 估值锚点 | 内在价值、PE/PB/FCF Yield、安全边际、目标价区间 |
| 核心假设清单 | 收入增速、利润率、现金流、用户/订单/产能等可验证假设 |
| 红线清单 | 诚信、监管、业务衰退、竞争突破、管理层异常动作 |
| 管理层质量 | 诚信、资本配置、回购分红、执行力、股东友好度 |
| 竞争护城河 | 市占率、定价权、网络效应、成本优势、替代威胁 |

每个维度只能给出三类结论：**Improved / Unchanged / Weakened**。

### 指定报告对比七步流程

1. **A1 读取并校验两份报告** — 提取核心论文、假设清单、红线、估值锚点等结构
2. **A2 证据归一化** — 整理成同一张表，只比较证据不比较文风
3. **A3 数值与估值校验** — 使用 `financial_rigor.py` 精确计算，禁止 LLM 心算
4. **A4 逐维度判定漂移** — 固定五维度，判定 Improved / Unchanged / Weakened
5. **A5 证据驱动规则** — 每个 non-Unchanged 结论必须引用具体新证据
6. **A6 补充数据获取** — 必要时使用 A股/港股工具更新数据
7. **A7 输出漂移报告** — 生成结构化漂移报告

---

## 使用示例

### 示例1：指定两份报告对比
```
/thesis-drift 腾讯 reports/腾讯-thesis-20260101.md reports/腾讯-thesis-20260722.md
```
对比腾讯半年内的两份论文快照，输出五维度漂移表与建议动作迁移。

### 示例2：自动快照对比
```
/thesis-drift 茅台
```
自动查找 `reports/茅台-thesis*.md` 历史快照，选取最早和最新两份执行对比。

### 示例3：缺失基线处理
```
/thesis-drift 英伟达
```
若无历史基线，提示先运行 `/thesis-tracker 英伟达 建立论文` 建立结构化基线。

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 漂移检测报告 | `reports/{公司名}/{公司名}-drift-{YYYYMMDD}.md` |
| 缺失基线提示 | 控制台输出，不生成文件 |

### 报告结构

```markdown
# {公司名} 投资论文漂移检测报告
**对比时间跨度：{旧报告日期} ~ {新报告日期}**

## 一、总体结论：论文是否漂移
未漂移 / 正向漂移 / 负向漂移 / 证据不足无法判断

## 二、维度漂移表
| 维度 | 旧判断 | 新判断 | 漂移方向 | 触发证据 | 置信度 |

## 三、证据差异明细
## 四、估值与数值验算（financial_rigor.py 验算结果）
## 五、建议动作迁移（如 Watch → Buy、Hold → Reduce）
## 六、不确定项与需补充来源
## 七、下次跟踪重点
```

### 总体结论必须回答

1. **论文是否漂移？** 未漂移 / 正向漂移 / 负向漂移 / 证据不足无法判断
2. **漂移来自哪里？** 估值 / 基本面 / 管理层 / 竞争格局 / 红线事件
3. **是事实变化还是价格变化？** 明确拆开说明
4. **建议动作如何迁移？** 例如：Watch → Buy、Buy → Hold、Hold → Reduce、Reduce → Exit
5. **下一步需要什么证据？** 下一份财报 / 监管披露 / 管理层说明 / 竞对数据

---

## 检测标准

### 设计理念

长期持仓最难的是区分三件事：

1. **事实改变** — 收入、利润率、竞争格局、管理层行为、资本配置发生可验证变化
2. **价格改变** — 市场情绪或估值倍数变化，但生意本身未变
3. **措辞改变** — 两份报告表达不同，但底层证据和判断没有变化

**核心目标**：只在证据变化时承认论文变化。不能因为报告换了写法就制造漂移，也不能因为股价涨跌就误判基本面。

### 证据驱动规则

- 每个 non-Unchanged 结论必须引用具体新证据：财报行项目、监管披露、新闻事件、价格与估值变化
- **找不到能解释变化的证据，必须判定为 Unchanged 或无法判断**
- 不能用措辞差异推断漂移

### 依赖结构

本 Skill 依赖 `/thesis-tracker` 输出的结构化维度：核心假设清单、红线清单、估值锚点、追踪记录表。没有这些结构时，先补齐基线，再做漂移检测。

---

## 工具依赖

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
- **A股工具**：[docs/A股工具使用指南.md](../../docs/A股工具使用指南.md)
- **港股工具**：[docs/港股工具使用指南.md](../../docs/港股工具使用指南.md)
- **美股工具**：[docs/美股工具使用指南.md](../../docs/美股工具使用指南.md)
- **国际货币汇率**（跨市场估值/市值统一口径折算）：`tools/common/fx_rate.py`，详见 [A股工具使用指南汇率章节](../../docs/A股工具使用指南.md)

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证、交叉验证、三情景估值等） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |
| `tools/common/report_audit.py` | 报告数据抽检与审核 | `python tools/common/report_audit.py extract --report reports/xxx.md` |

### 网络搜索工具

由于官方 WebSearch/WebFetch 在中国大陆不可用，请使用本地网络搜索工具。

**工具优先级**（基于上市地点）：

| 上市地点 | 主搜索工具 | 辅助搜索工具 | 说明 |
|---------|-----------|------------|------|
| A股 | `tools/common/doubao_search.py` | `tools/common/web_search.py` | 豆包搜索为推荐首选 |
| 港股/美股 | `tools/common/doubao_search.py` | `tools/common/tavily_search.py` + `tools/common/web_search.py` | 非境内上市需双源验证 |

**搜索规范**：
- 使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 搜索结果必须包含数据来源日期；过时数据须标注时效性说明
- 非境内上市公司须 Doubao + Tavily 双源验证
- 关键信息缺失时标注"信息不足"，不得用推测填充

**重要约束**：
- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 使用本地工具进行网络搜索和数据获取
- 所有数值变化必须使用 `financial_rigor.py` 精确计算，禁止 LLM 心算
- 关键财务数据须至少两处独立来源交叉验证
- 港股/美股公司须 Doubao + Tavily 双源验证

---

## 核心原则

1. **证据优先于措辞** — 同义改写不是漂移，只有事实证据变化才是漂移
2. **基本面优先于股价** — 股价涨跌只影响估值锚点，不自动改变生意质量
3. **数值必须验算** — 所有百分比、估值倍数、目标价差异必须用 `financial_rigor.py`
4. **不确定就标注不确定** — 来源缺失、口径不一致、无法复核时，不要硬判
5. **红线单独处理** — 红线触发优先级高于估值便宜，不能被低 PE 掩盖
6. **输出必须可复盘** — 每个 Improved / Weakened 结论都要能追溯到具体证据
7. **不预设立场** — 不因为持有就倾向于"未漂移"，证据指向哪边就写哪边
8. **诚实面对信息缺口** — 宁可标注"无法判断"，也不要用推测填充

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 所有数值变化必须使用 `financial_rigor.py` 精确计算，禁止 LLM 心算
- 关键财务数据必须至少两个来源交叉验证
- 来源不足、口径不一致、无法复核的数字必须标注为"低置信度 / 待核实"
- 报告缺少关键结构时，先标注"结构缺失"，不能编造结论
- 两份报告不是同一家公司时，停止并要求用户确认，不做跨公司漂移判断
- 不预设立场：先摆数据 → 推逻辑 → 出结论
- 网络搜索须使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 港股/美股公司须 Doubao + Tavily 双源验证，确保信息准确性

---

## 局限性说明

- **数据可得性**：港股小票、新上市公司可能无法获取到完整信息
- **报告结构依赖**：如果报告缺少核心假设清单、红线清单等结构，漂移检测质量会下降
- **估值估算主观性**：内在价值估算存在主观判断，不同方法可能得出不同结论
- **非实时数据**：工具获取的数据可能有延迟，不是实时数据
- **证据判断主观性**：即使有证据，判断是否"显著"变化仍有主观性
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [论文跟踪](../thesis-tracker/README.md) — 建立和维护投资论文
- [投资团队](../investment-team/README.md) — 四Agent全面公司研究
- [财报团队](../earnings-team/README.md) — 六Agent团队精读 + 公众号发布
- [组合管理](../portfolio-review/README.md) — 组合层面审视与优化

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-07-26
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。
