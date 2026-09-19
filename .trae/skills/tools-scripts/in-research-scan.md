---
name: in-research-scan
description: "在研重大项目信息获取（R8在研评分数据源）：通过 in_research_scan.py 一键扫描 gov/patent/bidding/academic/investor/website/research 多渠道 + 年报解析，或用 doubao_search 单条补充科创板公告、临床试验登记，采集科创企业在研项目的商业化确定性、市场空间、外部背书、专利验证、管理层一致性五子分，供 trend_tech_screen.py score --r8 自动判定奖励分与风险降级，禁止LLM心算。"
disable-model-invocation: true
---

# 在研重大项目信息获取

科创企业的**在研重大项目**是判断其未来 1-3 年爆发力的核心先验指标，往往比历史财务数据更具前瞻性——发明专利公开比产品上市提前 2-3 年，中标公告意味着确定性收入，超过 80% 的信息藏在公开的"非正式公告"中（官网新闻、投资者问答、政府公示、专利、招投标等）。

本工具将"在研项目扫描"从手动逐条 `doubao_search` 提取升级为**一键批量扫描 + 结构化聚合**，输出直接供 `trend_tech_screen.py score --r8` 填写的 R8 五子分证据，全程**禁止 LLM 手工挖文本与心算**。

> **适用对象**：研发驱动型科创企业（AI/半导体/生物医药/高端装备/信创）。传统制造业或低研发强度企业（研发费用率<5%）可简化执行或跳过。

---

## Python 环境

- **Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`
- **工作目录基准**：`F:/Financial_Investment_Analysis/`

---

## 一键扫描工具 `in_research_scan.py`

将方案文档步骤 3-A 的 8 条手动搜索指令整合为批量入口，复用 `doubao_search.py` 的模块接口（共享自动回退 + QPS 限流），单渠道失败不阻断整体扫描。

```bash
# 全渠道扫描 + 官网 + 年报解析 + 导出 Markdown 报告
python tools/specialized/in_research_scan.py scan "{公司}" \
  --market sz --official-site "{官网域名}" --annual-report "{年报md路径}" --export

# 指定渠道子集（加速验证）
python tools/specialized/in_research_scan.py scan "寒武纪" --channels patent,gov,bidding --json

# 列出全部渠道元信息
python tools/specialized/in_research_scan.py list
```

**参数说明**：

| 参数 | 说明 |
|------|------|
| `company` | 公司名（位置参数） |
| `--market` | 市场代码：`sz`（深交所互动易）/ `sh`（上交所 e互动）/ `hk` / `us` |
| `--channels` | 渠道键逗号分隔（如 `patent,gov,bidding`），省略则全渠道 |
| `--official-site` | 公司官网域名（`website` 渠道必需） |
| `--annual-report` | 年报 markdown 路径（`annual_report` 渠道必需） |
| `--json` / `--export` | 输出 JSON / 导出 Markdown 报告到 `reports/` |

**聚合输出结构**：`company` / `scanned_at` / `channels{ key: { label, queries, total, results, top_links } }` / `annual_report`。

---

## 渠道清单与信号分级

### 一、公开合规披露渠道（确定性信息，7 渠道已落地）

| 渠道键 | 渠道 | 采集要点 | 信号分级 / 评估意义 |
|--------|------|---------|---------------------|
| `annual_report` | 年报/招股书"管理层讨论与分析" | 项目名称、目标、所处阶段（实验室/中试/小批量/客户验证）、商业化时间表、投入金额、研发资本化率 | 合规必披露，可靠性最高（⭐⭐⭐⭐⭐） |
| `gov` | 政府科技项目立项公示（gov.cn） | 国家重点研发计划、重大科技专项 | 获国家级背书 → 确认"卡脖子/硬科技"地位，增信显著 |
| `patent` | 国家知识产权局专利检索 | 专利名称、申请/公开日期、技术摘要 | 无对应领域专利 → 研发管线真实性存疑；发明专利占比反映研发厚度 |
| `bidding` | 招投标平台（ccgp.gov.cn） | 中标金额、甲方身份、项目名称 | 直接验证商业化确定性；甲方（军工集团/政府机关）判断客户层级 |
| `academic` | 学术/技术社区（arxiv/github/cnki） | 顶级会议论文、开源项目 | 顶级会议（NeurIPS/ICML）→ 研发实力强；高产但产品未落地 → "论文型研发"存疑 |
| `research` | 券商深度研报 | "核心假设"部分项目放量节奏、收入预测 | 验证性"硬信息"，商业化量价预测 |
| `investor` | 投资者互动平台（深交所互动易 + 上交所 e互动） | 最新进展、管理层语气 | 见下"信号分级表" |

**投资者互动平台信号分级表**（`investor` 渠道重点）：

| 信号等级 | 回复内容示例 | 投资含义 |
|---------|-------------|---------|
| **极强利好** | "已进入最后验证阶段"、"预计 Q3 交付" | 商业化确定性极高 |
| **强利好** | "已实现小批量出货"、"通过客户验证" | 产品已获市场认可 |
| **中性** | "正在按计划推进" | 无新增信息 |
| **强风险** | "技术路线存在不确定性，存在流片失败风险" | 项目可能失败，需紧急调降评级 |
| **警惕** | 回避问题、回复"暂无进展"、"尚未立项" | 项目可能不及预期或已取消 |

### 二、手动补充渠道（尚未一键化，用 `doubao_search` 单条执行）

以下两类渠道具有行业/市场特殊性，未纳入 `in_research_scan.py` 默认批量，需按需手动检索：

```bash
# 科创板/创业板"科技创新信息"披露（A股特有）
python tools/common/doubao_search.py --sites sse.com.cn,szse.cn --time-range year "{公司} 项目进展公告 新产品研发成功 通过客户验证"

# 临床试验登记（生物医药/医疗器械专用，国家药监局药物临床试验登记平台）
python tools/common/doubao_search.py --sites chinadrugtrials.org.cn --time-range year "{公司} 药物临床试验 适应症 分期"
```

---

## R8 评分卡对照（供 `score --r8` 填写）

五子分直接对应 `trend_tech_screen.py score --r8`，满分 10，**禁止 LLM 心算**（由引擎自动判定奖励/风险）：

| 评估维度 | 满分 | 评分标准 | 主要数据来源 |
|---------|:---:|---------|-------------|
| **商业化确定性** | 4 | **4**=确认"已进入客户验证/小批量产/最后验证阶段"；**2**="样品交付/通过认证"；**0**=仅年报提及无进展；**-3**=实验室阶段>3年且无进展 | `investor`/`annual_report`/`website` |
| **市场空间** | 2 | **2**=千亿级市场；**1**=百亿级；**0**=<50亿且平稳；**-2**=萎缩市场 | `research` |
| **外部背书** | 2 | **2**=国家重点研发计划/政府资助；**1**=省市级资助；**0**=无外部资助 | `gov` |
| **专利验证** | 1 | **1**=对应领域有发明专利授权或在审；**0**=无相关专利申请 | `patent` |
| **管理层一致性** | 1 | **1**=公开场合多次列为"第一优先级"；**0**=无特别强调；**-2**=提及频次降低/回避 | `investor` |

**奖励/风险规则**（引擎自动执行）：

| R8 总分 | 处置 |
|---------|------|
| R8 ≥ 8 | 在②研发模块**额外 +5 分奖励** |
| 6 ≤ R8 < 8 | 在②研发模块**额外 +3 分奖励** |
| R8 < 0 | 触发**在研项目风险警告**，评级下调一级（S→A→B→C） |

## 研发管线 NPV 粗算子 `pipeline-npv`（GARP 独立档）

> **口径归属**：本节属 **GARP 独立档（1~5 年，五大师：费雪 / 林奇 / 郑希 / 李进 / 欧奈尔）**，服务框架第 4 步·估值工具矩阵「未盈利科技型」行的**辅助工具「研发管线 NPV」**（主锚仍为 PS / EV-Sales），由 P4-5 `garp-valuation` 编排调用。与上文 `scan` 的 R8 评分口径**物理共存、语义隔离**，两者不混用。

### 用法

```bash
# 最小用法（折现率 / 币种 / 基准年一律由调用方提供）
python tools/specialized/in_research_scan.py pipeline-npv \
    --projects p.json --discount-rate 0.10 --currency CNY --as-of-year 2026 --json

# 附敏感性（绝对步长，3×3 网格）
python tools/specialized/in_research_scan.py pipeline-npv \
    --projects p.json --discount-rate 0.10 --currency CNY --as-of-year 2026 \
    --sensitivity "r=0.01;p=0.10" --json

# 从 scan 结果提取候选项目名（只取名称，不含数值）
python tools/specialized/in_research_scan.py pipeline-npv \
    --from-scan scan.json --discount-rate 0.10 --currency CNY --as-of-year 2026

# stdin 传入项目文件
python tools/specialized/in_research_scan.py pipeline-npv \
    --projects - --discount-rate 0.10 --currency CNY --as-of-year 2026 < p.json
```

### 输入（`--projects` JSON）

| 字段 | 必填 | 说明 |
|------|:---:|------|
| `name` | ✅ | 项目名 |
| `peak_revenue` | ✅ | 峰值年收入（金额单位由调用方自定，工具不解释） |
| `launch_year` | ✅ | 商业化年份（早于基准年即报错） |
| `probability` | ✅ | 成功概率（0~1） |
| `source` | ✅ | 参数来源（原样回显，供审计追溯） |
| `cost` | — | 投入成本；**唯一允许的缺省**，缺省 `0.0` 且写入 `defaults_applied` 回显 |
| `currency` / `as_of_year` | — | 文件级可选；币种须与 `--currency` 一致，基准年须为**整数**且与 `--as-of-year` 一致，否则报错（不静默忽略） |

### 计算口径（写死，禁止 LLM 心算）

| 项 | 公式 |
|----|------|
| 期数 | `n_i = launch_year_i − as_of_year` |
| 峰值现值 | `PV_peak = peak_revenue / (1+r)**n` |
| 成本现值 | `PV_cost = cost / (1+r)**n` |
| 项目 NPV | `NPV_i = probability × PV_peak − PV_cost` |
| 管线 NPV | `pipeline_npv = Σ NPV_i` |

### 输出与退出码

- `--json`：`{task, as_of_year, currency, discount_rate, projects[], pipeline_npv, sensitivity, data_insufficient, missing[], defaults_applied[], note}`；
- **缺项属业务状态**：`data_insufficient=true` + `missing[]`，逐项目数值与 `pipeline_npv` **均为 `null`（不做部分计算）**、`sensitivity` 恒 `null`，**退出码 0**；
- **用法错误**：参数缺失/非法、币种或基准年冲突、折现率 `≤ -1` 或 `> 1.0`、敏感性折现率网格越界 → **退出码 2**，错误写 stderr、stdout 不出 JSON；
- 敏感性：`--sensitivity "r=Δr;p=Δp"` → 3×3 网格 + `npv_low` / `npv_high` / `base`；概率越界**截断并标 `clipped=true`**（唯一允许的截断）。

### 红线

1. **不内置任何默认假设**：折现率 / 币种 / 概率 / 峰值收入 / 商业化年份一律由调用方提供，缺失即标注数据不足；
2. 不换算汇率、不解释金额单位；
3. 不做分年爬坡、税率、摊销、项目相关性调整（概率是唯一风险调整因子）；
4. 不输出买卖结论、档位、评级、排序；
5. 不替换 PS / EV-Sales 主锚；不叠加 ESG 折价（由 P4-5 编排层完成）。

> 折现率上限 `1.0` **仅拦「百分数当小数」的量纲误用**（如把 10% 写成 `10`），不是默认值或经验值。完整口径、样例与验收对照见 `upgrade1.0/P3-8/`（开发方案与计划 / 样例与期望输出 / 测试记录 / 回归核对记录 / 口径隔离声明）。

---

## 信息来源速查表（完整版）

| 信息来源 | 信息类型 | 可获取关键数据 | 可靠性 | 适用对象 |
|---------|---------|---------------|:---:|---------|
| 年报/招股书（管理层讨论） | 合规披露 | 项目名称、阶段、目标、预算、研发资本化 | ⭐⭐⭐⭐⭐ | 所有 |
| 科创板/创业板公告 | 合规披露 | 项目进展、产品验证 | ⭐⭐⭐⭐⭐ | A股科创 |
| 政府科技项目公示 | 外部权威背书 | 国家/省级认可 | ⭐⭐⭐⭐ | 所有 |
| 临床试验登记 | 合规披露 | 分期进度、预计完成日 | ⭐⭐⭐⭐⭐ | 医药 |
| 国家知识产权局专利检索 | 技术先验指标 | 专利名称、技术摘要、研发方向 | ⭐⭐⭐⭐⭐ | 所有 |
| 招投标平台 | 商业化验证 | 中标金额、甲方身份、项目名称 | ⭐⭐⭐⭐⭐ | ToB/ToG |
| 学术/技术社区 | 前沿技术曝光 | 论文、开源项目、技术实力 | ⭐⭐⭐ | AI/半导体 |
| 公司官网/官方公众号 | 前瞻性"软信息" | 样品交付、客户导入 | ⭐⭐⭐ | 所有 |
| 投资者互动平台 | 高频更新 | 最新进展、管理层语气 | ⭐⭐⭐⭐ | A股 |
| 券商深度研报 | 验证性"硬信息" | 商业化量价预测 | ⭐⭐⭐ | 所有 |

---

## 模块导入接口

```python
from tools.specialized.in_research_scan import scan, build_queries, export_markdown

# 一键扫描（search_fn 可注入 mock 便于测试）
result = scan(
    "中芯国际",
    channels=["patent", "gov", "bidding"],
    official_site="smics.com",
    annual_report_path="reports/002709_2025年报.md",
)

# 仅构建查询配方（不执行搜索）
queries = build_queries("中芯国际", channels=["patent", "gov"])
```

```python
from tools.specialized.in_research_scan import run_pipeline_npv

# 研发管线 NPV 粗算（GARP 独立档；参数全部由调用方提供，缺失即标注数据不足）
result = run_pipeline_npv(
    "p.json", discount_rate=0.10, currency="CNY", as_of_year=2026,
)
print(result["pipeline_npv"], result["data_insufficient"])
```

---

## 相关技能

- [景气趋势筛选打分引擎](./trend-tech-screen.md)（`score --r8` 消费方）
- [网络信息搜索](./web-search-tools.md)（底层 `doubao_search` 五工具）
- **消费方**：P4-5 `garp-valuation`（GARP 独立档估值编排层）—— 消费本文档的 `pipeline-npv` 数值段；`scan` 段的消费方为 `trend_tech_screen.py score --r8`
- [年报结构化抽取](./annual-report-parser.md)
- [PDF文档提取](./pdf-extraction.md)
- [公共工具索引](./common-tools-guide.md)

---

## 版本信息

- **版本**：**1.1.0**
- **创建日期**：2026-08-26
- **更新日期**：2026-09-17
- **来源**：《在研重大项目信息获取方法的整合与强化.md》（`research/quality-screen/`）整合落地；1.1.0 追加 `pipeline-npv` 子命令说明（P3-8，GARP 独立档，2026-09-17）
- **维护状态**：活跃维护