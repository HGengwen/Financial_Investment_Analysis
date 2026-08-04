# 供应链瓶颈猎手 (Bottleneck Hunter)

AI驱动的全球产业链瓶颈套利：从超级趋势的"咽喉位置"挖掘第二、第三层投资机会

---

## 快速开始

### 基本调用方式

```
/bottleneck-hunter {趋势名}
```

例如：
- `/bottleneck-hunter AI基础设施`
- `/bottleneck-hunter 能源转型`
- `/bottleneck-hunter 创新药`
- `/bottleneck-hunter 国防现代化`

---

## 核心功能

对指定超级趋势执行供应链瓶颈扫描与套利机会挖掘，从物理供应链的咽喉位置出发，找出那些没人注意但一旦断货整个行业都得停下来等的公司。

### 七步执行流程

1. **超级趋势确认** — 验证趋势的持续性/物理性/规模性/加速性
2. **供应链物理拆解** — 从 Layer 0 终端拆到 Layer 4 基础设施
3. **瓶颈识别** — 6条标准判定"咽喉"，输出 S/A/B 级瓶颈地图
4. **公司筛选** — 从瓶颈到标的，初筛+估值检查+深度筛选
5. **交叉验证** — 正向验证+芒格式反向否定
6. **输出瓶颈机会看板** — 排名表+一页纸摘要+行动建议
7. **存量更新** — 瓶颈地图动态维护

### 当前跟踪的超级趋势

1. **AI基础设施建设** — 数据中心、GPU集群、网络互联、电力
2. **能源转型** — 核电重启、电网升级、储能
3. **国防现代化** — 西方军费上升周期、供应链重构
4. **半导体再工业化** — 美欧日补贴建厂、设备/材料瓶颈
5. **太空经济** — 卫星互联网、发射频次激增
6. **生物药/创新药** — 抗体/ADC/CAR-T/GLP-1爆发

---

## 使用示例

### 示例1：扫描AI基础设施供应链瓶颈
```
/bottleneck-hunter AI基础设施
```
 拆解GPU→光模块→激光器→InP衬底的物理链条，定位Layer 2-3的S级瓶颈公司

### 示例2：扫描创新药供应链瓶颈
```
/bottleneck-hunter 创新药
```
 拆解生物药生产→CDMO→培养基/层析树脂/病毒载量/预充注射器瓶颈，挖掘未充分定价的供应商

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 完整扫描报告 | `reports/bottleneck-map/{趋势名}-bottleneck-{YYYYMMDD}.md` |
| 每日扫描 | `reports/bottleneck-map/daily/{YYYY-MM-DD}-{am/pm}.md` |
| 瓶颈总地图 | `reports/bottleneck-map/master-map.md` |
| 观察名单 | `reports/bottleneck-map/watchlist.md` |

**每日扫描文件命名规则**（通过文件名一眼看出有没有标的）：
- 发现明确标的：`HH-MM-标的代码1-标的代码2.md`
- 仅有信号扫描：`HH-MM-信号扫描.md`
- 无新发现：不生成文件

---

## 研究标准

### 核心理念：不问"AI推荐什么股票"，问"哪一环会先不够用"

超额收益来源：第一层瓶颈（GPU、HBM、电力）已被充分定价，真正的 alpha 在第二层、第三层——光模块、激光器、InP衬底、SOI晶圆、外延设备等。

### 瓶颈判定6条标准

| # | 标准 | 🔴 高瓶颈 | 🟡 中等 | 🟢 低瓶颈 |
|---|------|---------|---------|---------|
| 1 | 供给集中度 | ≤2家 | 3-5家 | >5家 |
| 2 | 扩产周期 | >2年 | 1-2年 | <1年 |
| 3 | 替代难度 | 不可替代 | 部分可替代 | 易替代 |
| 4 | 产能利用率 | >90% | 70-90% | <70% |
| 5 | 需求增速 | >50%/年 | 20-50% | <20% |
| 6 | 客户验证周期 | >1年 | 6-12月 | <6月 |

**瓶颈评级**：🔴≥4个 = S级（单点故障）/ 🔴3个 = A级 / 🔴1-2个 = B级

### 估值检查硬门槛

**瓶颈真实 ≠ 投资机会。** 必须对每家公司计算 PS、PE 并标注。

- **红灯**（信号强度封顶★★）：市值>TAM的20%、PS>30x且增速<100%、增发后60天股价翻倍
- **黄灯**（需额外解释）：亏损+PS>15x、PE>80x
- **绿灯**（加分项）：PS<10x且收入增长、PE<30x且有护城河
- **安全边际检验**：以当前市值买入，10年后25x PE退出，年化回报<10% → 标注"不具备安全边际"

### 信号强度评级

- ★★★★★：多重交叉验证+绿灯+客户已导入
- ★★★★：大部分验证通过+绿灯/黄灯
- ★★★：逻辑成立但部分待验证
- ★★：早期信号或估值红灯
- ★：纯概念、未验证

---

## 工具依赖

### 本地数据获取工具

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票信息查询 | `python tools/a_share/stock_info.py --search 新易盛` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 300502` |
| A股 | `tools/a_share/stock_quote.py` | 历史股价与实时行情 | `python tools/a_share/stock_quote.py --code 300502` |
| A股 | `tools/a_share/stock_equity.py` | 股权结构与财报下载 | `python tools/a_share/stock_equity.py --code 601899` |
| 港股 | `tools/hk_stock/stock_financial.py` | 港股信息与财务指标 | `python tools/hk_stock/stock_financial.py --financial 00700` |
| 港股 | `tools/hk_stock/stock_quote.py` | 港股历史K线 | `python tools/hk_stock/stock_quote.py --code 00700` |
| 港股 | `tools/hk_stock/stock_screen.py` | 港股质量筛选 | `python tools/hk_stock/stock_screen.py --code 00700` |
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
| `tools/common/financial_rigor.py` | 精确金融计算（PE、ROE、市值验证、三情景估值） | `python tools/common/financial_rigor.py verify-valuation --pe 25.5 --eps 10.2` |
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
- 港股/美股重要研究建议同时调用 Doubao 和 Tavily 互为补充
- 关键财务数据必须至少两个独立来源交叉验证
- 估值数据须使用 `financial_rigor.py` 校验，禁止 LLM 心算

---

## 核心原则

1. **不让AI推荐股票，让AI拆供应链** — 问题比答案重要
2. **物理优先** — 只关注需要实际物理产品/材料/设备的环节
3. **第二层、第三层** — 不追已被充分定价的龙头
4. **交叉验证** — 每个结论至少2个独立信源
5. **诚实面对不确定性** — 找不到数据就写"数据不足"，不用推测填充
6. **瓶颈有时效性** — 每个瓶颈都会被解除，关键是判断时间窗口
7. **小市值≠好机会** — 小市值也可能是烂公司，必须过财务质量关
8. **瓶颈真实≠投资机会** — 估值是硬门槛，PS>30x或仍在亏损就不是买点
9. **遵循客观性原则** — 不预设看多，先数据后结论
10. **网络搜索时效性** — 使用 `--time-range month/week` 限制时间范围，优先获取最新信息
11. **非境内上市双源验证** — 港股/美股公司须 Doubao + Tavily 双源验证

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 所有数据必须标注来源
- 估计值必须明确标注"估计"
- 关键财务数据必须至少来自两个独立来源进行交叉验证
- 不预设立场：先摆数据 → 推逻辑 → 出结论
- 呈现正反两面：每个核心判断附反面论据
- 必须执行强制反向验证（芒格式否定）
- 估值检查不可跳过：市值、年收入、PS、PE 为必填项，不可用"待核实"跳过
- 网络搜索须使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 港股/美股公司须 Doubao + Tavily 双源验证，确保信息准确性
- 估值数据须使用 `financial_rigor.py` 校验，禁止 LLM 心算

---

## 局限性说明

- 数据依赖本地工具和API可用性
- 网络搜索接口在中国大陆网络连接可能不稳定
- 对于信息稀缺的环节，无法保证分析完整性
- 国际市场覆盖可能因语言限制遗漏日韩台欧供应商
- 非实时数据：工具获取的数据可能有延迟
- AI筛选偏见：可能存在龙头偏好、英文偏好、叙事偏好、确认偏见、时效偏见
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [行业投资研究](../industry-research/README.md) — 产业链全景扫描与四大师分析
- [行业漏斗筛选](../industry-funnel/README.md) — 行业漏斗精选标的

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-07-26
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。
