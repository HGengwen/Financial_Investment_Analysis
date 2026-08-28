# 景气趋势筛选 (Trend-Tech Screen)

融合欧奈尔 CAN SLIM、林奇 GARP、郑希全球景气、李进产业验证四大投资思想，从 **1-3年中期回报周期** 识别最具爆发潜力的成长股。

---

## 快速开始

### 基本调用方式

```
/trend-tech-screen {公司名/行业/指数/主题}
```

支持四种输入格式：

| 输入方式 | 示例 | 说明 |
|---------|------|------|
| 个股 | `/trend-tech-screen 腾讯, 美团, 英伟达` | 逐家筛选 |
| 行业 | `/trend-tech-screen 中国AI算力行业` | 搜索行业主要公司（10-20家）后逐家筛选 |
| 市场/指数 | `/trend-tech-screen 恒生科技指数成分股` | 拉取成分股列表，逐家筛选 |
| 主题 | `/trend-tech-screen 全球AI算力链` | 搜索主题相关公司，逐家筛选 |

例如：
- `/trend-tech-screen 中际旭创`
- `/trend-tech-screen 全球半导体设备`
- `/trend-tech-screen 科创50`

---

## 核心功能

对指定公司/行业/指数/主题执行「四层递进式评估」，输出最终评级（S/A/B/C）与反证清单。

### 四层递进流程

```
第零层：产业链周期定位（前置判断，动态调权重）
  → 第一层：前置硬性淘汰（一票否决，3条）
  → 第二层：五维加权打分（满分100 + 奖励分）
  → 第三层：地缘政治二维修正（乘数系数）
  → 估值倒推验证（不占分，红灯降级）
  → 技术面止损校验（独立否决：破50日线预警降级 / 破200日线红牌清仓）
  → 最终评级 + 反证清单
```

### 五维加权打分（满分100 + 奖励分）

| 维度 | 权重 | 关键指标 | 大师思想 |
|---|---|---|---|
| ① 景气前瞻 | 35分（爆发期42） | 订单增速、政策环境、毛利率变化、供应链话语权 | 欧奈尔C + 李进 + 郑希 |
| ② 研发执行力与转化 | 25分（跃迁期32）+奖励 | MROI、新品收入占比、落地速度、自主替代分级 | 欧奈尔N + 郑希 |
| ③ 人才质量与密度 | 15分 | 人均创利增速、研发占比及硕博、核心团队稳定 | 郑希+李进 |
| ④ 动量与市场共识 | 15分 + 溢价 | 250日SMR、RSI(50)、盈利预测上调、低关注度 | 欧奈尔L+I |
| ⑤ 估值安全垫 | 10分（成熟期15） | PEG、PSG、PE分位、市值倒推 | 林奇GARP |

### 评级映射

- **S级（强烈买入）**：≥80分
- **A级（配置）**：65-79分
- **B级（观察/轻仓）**：50-64分
- **C级（回避）**：<50分

最终得分 = （五维加权总分 + 奖励分）× 地缘修正系数

---

## 使用示例

### 示例1：个股筛选

```
/trend-tech-screen 中际旭创
```

输出该公司的五维打分 + 地缘修正 + 技术面校验 + 反证清单。

### 示例2：行业筛选

```
/trend-tech-screen 中国AI算力行业
```

搜索该行业主要上市公司，逐家筛选，额外输出行业通过率、景气一致性判断、板块对比总结。

### 示例3：指数成分股筛选

```
/trend-tech-screen 恒生科技指数成分股
```

拉取成分股列表，逐家筛选，输出行业内排名与配置建议。

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 个股筛选 | `reports/trend-screen/{公司名}-trend-screen-{YYYYMMDD}.md` |
| 行业筛选 | `reports/trend-screen/{行业名}-industry-trend-{YYYYMMDD}.md` |
| 指数筛选 | `reports/trend-screen/{指数名}-index-trend-{YYYYMMDD}.md` |
| 主题筛选 | `reports/trend-screen/{主题名}-theme-trend-{YYYYMMDD}.md` |

### 报告结构

```markdown
# 📈 景气趋势筛选报告（1-3年配置视角）
## 🚫 第一层：前置淘汰名单（一票否决）
## 🛡️ 第二层：地缘韧性 & 全球合规对冲评估（二维修正矩阵）
## 🔥 景气-估值热力图（文字可视化版）
## 📊 第三层：五维打分详细表（满分100+奖励分）
## 🔬 第四层：大师思想验证（逐一对照：欧奈尔/林奇/郑希/李进）
## ⚠️ 第五层：反证清单（S/A级公司专属）
## 📝 最终投资结论
```

---

## 工具依赖

本技能四层流程依赖 `tools/` 下的数据获取与计算工具，核心是 **`trend_tech_screen.py` 打分引擎**（聚合计算层）与 **`financial_rigor.py` 五维估值命令**（精确计算），配合三市场数据工具、年报解析器与搜索工具。

### 核心工具清单

| 市场 | 工具 | 用途 | 关键参数 |
|------|------|------|---------|
| A股 | `stock_financial.py` | 合同负债/研发/存货周转/应付账款/预付款项/员工数 | `--advanced` |
| A股 | `stock_quote.py` | SMR相对强度 + RSI(50) + MA50/MA200 | `--momentum --auto-peers` |
| A股 | `stock_info.py` | 机构覆盖度（欧奈尔I因子） | `--profile` |
| A股 | `stock_equity.py` | 下载年报PDF | `--download-report` |
| 港股 | `stock_financial.py` | 合约负债/存货/应付账款/预付款项 | `--advanced` |
| 港股 | `stock_quote.py` | RSI(50)/MA（SMR截面不可用） | `--momentum` |
| 美股 | `stock_financial.py` | 指标化输出（毛利/研发/合同负债/存货周转） | `--indicators` |
| 美股 | `stock_quote.py` | RSI(50)/MA（SMR截面不可用） | `--momentum` |
| 估值 | `financial_rigor.py` | PEG/PSG/PE分位/市值倒推 | `peg`/`ps-g`/`pe-percentile`/`implied-growth` |
| 年报 | `annual_report_parser.py` | 年报结构化抽取（员工/子公司/研发/收入分部/新品/供应链） | `--output-json` |
| 打分 | `trend_tech_screen.py` | 五维打分 + 地缘修正 + 技术面止损 + 评级 + 反证清单 | `score`/`batch` |
| 在研 | `in_research_scan.py` | 在研项目多渠道扫描（gov/patent/bidding/academic/investor/website/research），供 R8 评分卡 | `scan {公司} --market sz --official-site {官网} --annual-report {年报md}` |
| 搜索 | `doubao_search.py` 等 | 政策/订单/制裁/卡脖子/行业周期 | `--finance`/`--sites` |

### 打分引擎配合方式（关键）

`trend_tech_screen.py` 是**聚合计算层**，不直接拉取网络数据。流程：

1. **LLM 采集判断**：用数据/搜索/年报工具采集指标，定性判断周期阶段、政策环境、自主替代分级、地缘二维（x=国产化率、y=海外对冲）、技术面数据
2. **工具计算**：`financial_rigor.py` 算 PEG/PSG/PE分位/隐含增速；`annual_report_parser.py` 结构化抽取年报字段；`in_research_scan.py` 一键扫描在研项目渠道供 R8 评分卡
3. **聚合打分**：将五维得分（`--dims`）、地缘二维（`--geo`）、技术面（`--tech`）传给 `trend_tech_screen.py score` 自动打分评级；批量 `batch --input` 做行业景气一致性两轮修正

### 关键约束

- **禁止 LLM 心算**：一切估值的算术计算用 `financial_rigor.py` 与 `trend_tech_screen.py`
- **年报一手数据**：关键财务数据须从年报 PDF 一手提取，禁止用研报替代
- **网络搜索**：禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一用本地五工具组合，详见 [web-search-tools](../tools-scripts/web-search-tools.md)
- **时效性**：搜索须用 `--time-range month` 或 `--time-range week` 限制时间范围
- **跨市场统一口径**：市值/估值对比用 `tools/common/fx_rate.py` 折算到统一货币

详细工具规范见 [公共工具索引](../tools-scripts/common-tools-guide.md)，本技能数据获取详见 [A股数据](../tools-scripts/a-share-data.md) / [港股数据](../tools-scripts/hk-share-data.md) / [美股工具使用指南](../../../docs/美股工具使用指南.md)。

---

## 核心原则

1. **正向排序** — 识别景气趋势公司，强调 1-3 年盈利爆发力（区别于 `quality-screen` 的逆向淘汰）
2. **边际优先** — 近 6 个季度边际变化比历史均值更重要，允许历史瑕疵但要求边际快速收窄
3. **数据驱动** — 所有判断基于财务数据，区分事实与观点
4. **禁止心算** — 关键算术走工具，尊重项目"禁止 LLM 心算"规范
5. **技术面纪律** — 200 日均线止损为最高优先级，触发即执行，无需等待基本面确认
6. **诚实面对缺口** — 数据无法获取时标注"数据缺失"，而非猜测补全

---

## 注意事项

- **与 `quality-screen` 的差异**：前者逆向淘汰（永续经营），本技能正向排序（1-3年爆发力），两者互补，按用户持有周期路由
- **周期权重纪律**：无法判断周期阶段时，默认"需求爆发期"权重；权重调整仅影响①②模块
- **数据窗口**：上市不足 3 年允许用 IPO 招股书"管理层指引"代替历史数据
- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 关键财务数据须至少两个来源交叉验证

---

## 局限性说明

- **纯周期股**（航运、养猪）与**早期未盈利 Biotech** 中有效性显著下降
- **地缘突变**（战争、突发极端制裁）无法预测，需用户自行关注新闻
- **非实时数据**：工具获取的数据可能有延迟
- **大师思想边界**：任何理论都不能替代对管理层诚信度与实际控制人背景的深入调研
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [去劣筛选](../quality-screen/README.md) — 互补技能（逆向淘汰）
- [景气趋势打分引擎工具](../tools-scripts/trend-tech-screen.md) — `trend_tech_screen.py` 使用说明
- [在研重大项目信息获取](../tools-scripts/in-research-scan.md) — `in_research_scan.py` 在研项目多渠道扫描（R8 数据源）
- [年报结构化抽取](../tools-scripts/annual-report-parser.md) — `annual_report_parser.py` 使用说明
- [财务计算与验证](../tools-scripts/financial-calc.md) — `financial_rigor.py` 五维估值命令
- [公共工具索引](../tools-scripts/common-tools-guide.md)

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-08-25
- **最后更新**：2026-08-26（工具清单补充 `in_research_scan.py` 在研项目多渠道扫描落地工具；R8 评分卡边界测试 41→47 通过，新增扫描器测试 23 项）
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。