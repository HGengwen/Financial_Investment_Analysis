# 组合管理 (Portfolio Review)

从"研究公司"到"管理组合"：对投资组合进行系统化审视与优化，分析集中度、相关性、机会成本与压力测试，给出调仓建议。

---

## 快速开始

### 基本调用方式

```
/portfolio-review {持仓清单}
```

支持三种输入格式：
- 持仓比例：`/portfolio-review 腾讯30%, 美团20%, 茅台20%, 英伟达15%, 现金15%`
- 持仓明细：`/portfolio-review 腾讯 500股 @480港元, 美团 1000股 @130港元, ...`
- 历史组合：`/portfolio-review 我的持仓`（读取 `reports/portfolio-latest.md`）

---

## 核心功能

对指定投资组合执行七步系统化审视，从持仓健康检查到组合层面分析，最终给出可执行的调仓建议。

### 七步执行流程

1. **解析持仓** — 标准化为持仓表格（标的/代码/持仓量/成本价/现价/市值/占比/盈亏）
2. **获取最新数据** — 并行获取每只持仓的股价、估值、财务变化、重大事件、分析师预期
3. **单仓位体检** — 检查买入逻辑是否变化、论文健康度评分、仓位建议
4. **组合层面分析** — 集中度、相关性、机会成本、压力测试四维度分析
5. **优化建议** — 给出加仓/减仓/清仓/新建仓/不动等具体调仓动作
6. **输出组合报告** — 生成结构化的投资组合审视报告
7. **保存组合文件** — 写入 `reports/portfolio-{YYYYMMDD}.md` 便于历史追溯

### 组合层面四维度分析

- **集中度分析** — 第一大持仓、前三大持仓、总持仓数量、现金占比
- **相关性检查** — 识别行业、主题、国家/货币的隐性关联与风险共振
- **机会成本分析** — 按"预期年化回报×确定性"排序，淘汰不及现金的仓位
- **压力测试** — 全球衰退、中美冲突、利率飙升、科技泡沫破裂等极端情景

---

## 使用示例

### 示例1：按比例审视组合
```
/portfolio-review 腾讯30%, 美团20%, 茅台20%, 英伟达15%, 现金15%
```
按比例分析组合集中度、相关性与机会成本，给出调仓建议。

### 示例2：按持仓明细审视
```
/portfolio-review 腾讯 500股 @480港元, 美团 1000股 @130港元, 茅台 100股 @1800元
```
计算实际市值与盈亏，结合最新行情做全面体检。

### 示例3：基于历史组合审视
```
/portfolio-review 我的持仓
```
读取 `reports/portfolio-latest.md`，对已有组合进行季度复盘。

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 组合审视报告 | `reports/portfolio-{YYYYMMDD}.md` |
| 同日多次审视 | `reports/portfolio-{YYYYMMDD}-v2.md`（递增版本号） |

### 报告结构

```markdown
# 投资组合审视报告
**审视日期：{YYYY-MM-DD}**

## 一、组合概览（持仓表格）
## 二、单仓位体检（每个持仓的健康状态）
## 三、组合分析
  ### 3.1 集中度
  ### 3.2 相关性
  ### 3.3 机会成本
  ### 3.4 压力测试
## 四、调仓建议（具体操作 + 理由）
## 五、下次审视时间和关注重点
```

### 结论必须明确回答

1. **组合整体健康度**：优秀 / 良好 / 需要调整 / 问题严重
2. **最应该做的一件事是什么？**（加仓X / 减仓Y / 不动）
3. **当前最大风险是什么？**

---

## 审视标准

### 巴菲特与李录的组合哲学

- **李录的标准**：3-5只核心持仓，前3占80%+（要求每只都研究透彻）
- **巴菲特的标准**：核心持仓不超过10只，允许更多卫星仓位
- **现金即仓位**：找不到好机会时，现金是最好的仓位（巴菲特持有$3,820亿现金）

### 单仓位体检三问

- 如果今天没有持仓，你还会在当前价格买入吗？
- 如果明天不能交易，持有5年你舒服吗？
- 买入论文还完整吗？

### 集中度建议范围

| 指标 | 建议范围 |
|------|---------|
| 第一大持仓占比 | <40% |
| 前三大持仓占比 | 50-80% |
| 总持仓数量 | 5-15只 |
| 现金占比 | 10-30%（视市场环境） |

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

### 精确计算工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证、交叉验证、三情景估值等） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |
| `tools/common/report_audit.py` | 报告数据抽检与审核（准出流程） | `python tools/common/report_audit.py extract --report reports/xxx.md` |

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
- 估值数据须使用 `financial_rigor.py` 校验，禁止 LLM 心算
- 关键财务数据须至少两个来源交叉验证
- 港股/美股公司须 Doubao + Tavily 双源验证

---

## 核心原则

1. **每一块钱都有机会成本** — 持有一只平庸的股票，成本是错过了一只优秀的
2. **集中不是风险，无知才是** — 持有3只深度理解的股票，比持有30只一知半解的安全
3. **现金是一种仓位** — 找不到好机会时，持有现金不丢人
4. **组合层面 > 个股层面** — 一只好股票在错误的仓位上也会拖累你
5. **定期审视，但不要过度交易** — 每季度审视一次足够，不要每天盯盘调仓
6. **客观性原则** — 所有判断基于数据和事实，区分事实与观点
7. **不替用户做决策** — 给出调仓建议，但最终决策权在用户
8. **诚实面对不确定性** — 对于信息不足的持仓，明确标注"数据不足"

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 所有数据必须标注来源，关键财务数据至少两个来源交叉验证
- 估值估算须使用 `tools/common/financial_rigor.py` 精确计算，不得手算
- 信息丰富度C级持仓的分析结论须标注低置信度
- 不预设立场：先摆数据 → 推逻辑 → 出结论
- 不直接推荐个股，替代标的选择交给 `/industry-research` 或 `/investment-checklist`
- 网络搜索须使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 港股/美股公司须 Doubao + Tavily 双源验证，确保信息准确性

---

## 局限性说明

- **数据可得性**：港股小票、新上市公司可能无法获取到完整信息
- **估值估算主观性**：预期回报估算存在主观判断，不同方法可能得出不同结论
- **压力测试简化**：情景分析基于假设，可能与实际市场表现有较大差异
- **非实时数据**：工具获取的数据可能有延迟，不是实时数据
- **相关性动态变化**：持仓相关性会随市场环境变化，历史相关性不代表未来
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [投资团队](../investment-team/README.md) — 四Agent全面公司研究
- [买入前清单](../investment-checklist/README.md) — 巴菲特买入前Checklist
- [财报团队](../earnings-team/README.md) — 六Agent团队精读 + 公众号发布
- [论文跟踪](../thesis-tracker/README.md) — 投资论文长期跟踪

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-07-26
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。
