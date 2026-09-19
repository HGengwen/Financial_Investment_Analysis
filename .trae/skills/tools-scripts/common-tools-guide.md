---
name: common-tools-guide
description: "公共工具索引：为所有投研技能提供工具使用规范的总入口，按单一职责拆分为A股数据、港股数据、财务计算、网络搜索、报告审核、全局约束等独立技能文件。"
disable-model-invocation: true
---

# 公共工具使用指南（索引）

本文件为所有投研技能提供**工具使用规范的总入口**。按单一职责原则，工具指南已拆分为以下独立技能文件，其他技能按需引用对应文件。

---

## 工具技能清单

| 技能文件 | 职责 | 核心工具 |
|---------|------|---------|
| [a-share-data.md](./a-share-data.md) | A股数据获取 | `stock_info.py`（含 `--profile`）、`stock_financial.py`（含 `--advanced`）、`stock_quote.py`（含 `--realtime`/`--momentum`/`--auto-peers`）、`stock_screen.py`、`stock_equity.py` |
| [hk-share-data.md](./hk-share-data.md) | 港股数据获取 | `stock_financial.py`（含 `--advanced`）、`stock_quote.py`（含 `--realtime`/`--momentum`，动量含 `ATR(14)`）、`stock_screen.py` |
| [financial-calc.md](./financial-calc.md) | 财务计算与验证 | `financial_rigor.py`（市值验算、交叉验证、估值验算、三情景估值、五维估值 peg/ps-g/pe-percentile/implied-growth、GARP 计算核心 roic/incremental-roic/wacc/rule-of-40/ev-sales/adjusted-peg/dcf） |
| [terminal-value.md](./terminal-value.md) | 长期折现估值（十年尺度） | `terminal_value.py`（终值PE、十年IRR、三条硬约束 audit：C1 r/g 同币种、C2 r−g≥5pct、C3 离散风险不得进 r/β） |
| [web-search-tools.md](./web-search-tools.md) | 网络信息搜索（v3.0 五工具） | `anysearch.py`（A股投研首选）、`doubao_search.py`（实时资讯首选）、`exa_search.py`（美股深度研究首选）、`tavily_search.py`（港美股辅源）、`web_search.py`（仅兜底） |
| [report-audit.md](./report-audit.md) | 报告审核与抽检 | `report_audit.py`（15%随机抽样、准出/打回判决） |
| [global-constraints.md](./global-constraints.md) | 全局约束规范 | 误差处理规则、股价复权规范、七条核心约束 |
| [pdf-extraction.md](./pdf-extraction.md) | PDF文档提取 | `pdf_extract.py`（首选，基于 pdf-inspector，支持自动乱码检测 + OCR 回退）；`pdftotext`、`pdfinfo`、`pdftoppm`（Poppler工具集，失败回退） |
| [annual-report-parser.md](./annual-report-parser.md) | 年报结构化抽取（mid-trend-tech-screen 阶段四） | `annual_report_parser.py`（从年报 markdown 定向抽员工/子公司/研发/收入分部/新品/供应链/治理 JSON） |
| [in-research-scan.md](./in-research-scan.md) | 在研重大项目信息获取（mid-trend-tech-screen R8 数据源） | `in_research_scan.py`（gov/patent/bidding/academic/investor/website/research 多渠道一键扫描 + 年报解析，供 `score --r8` 填写） |
| [trend-tech-screen.md](./trend-tech-screen.md) | 景气趋势筛选打分引擎（mid-trend-tech-screen） | `trend_tech_screen.py`（五维打分 + 地缘修正 + 技术面止损 + **R8在研评分** + 评级 + 反证清单，批量两轮） |
| [garp-macro-tools.md](./garp-macro-tools.md) | 宏观校准引擎（GARP 宏观三表 + 阶段判定 + calibrate） | `macro_calibrator.py`（stage/data/calibrate 三子命令：美林四档查表、宏观指标软判定、PEG/现金/单只校准） |
| [garp-geo-policy-tools.md](./garp-geo-policy-tools.md) | 政策-资本-地缘矩阵与国产化率四档（GARP 第0步/第1步） | `geo_policy_screen.py`（screen/localize/examples/scan 四子命令：三维矩阵六行判定+赛道两分法、国产化率四档、半导体示例、实时来源快照） |
| [garp-governance-tools.md](./garp-governance-tools.md) | 治理数据评分（GARP 管理层/科研/ESG 折价） | `governance_data.py`（management/research/esg 三子命令：管理层 20 分制、科研转化 20 分制、ESG 三通道折价） |
| [garp-valuation-tools.md](./garp-valuation-tools.md) | GARP 估值计算核心（消费视角） | `financial_rigor.py` 7 个 GARP 估值子命令（roic / incremental-roic / wacc / rule-of-40 / ev-sales / adjusted-peg / dcf）：公司类型五分→主锚编排映射、输出字段、量纲三档、实测已知坑；算法权威登记见 [financial-calc.md](./financial-calc.md) |
| 汇率获取（详见 [A股工具使用指南](../A股工具使用指南.md)） | 国际货币汇率获取 | `fx_rate.py`（Akshare 优先，yfinance 回退，19 个货币对，限流保护） |

> **trend-tech-screen 工具链**：本索引中的 `financial-calc`（新命令）、`a-share-data`/`hk-share-data`（扩展科目/动量/画像）、`annual-report-parser`、`in-research-scan`（在研项目 R8 数据源）、`trend-tech-screen` 构成景气趋势筛选技能的全量数据与计算支撑，详见 [trend-tech-screen.md](./trend-tech-screen.md)。

---

## GARP 已知缺口与降级路径（P23-D1 ~ P23-D14）

本表为 **D 类挂账（P23-D1 ~ P23-D14）的唯一汇总入口**。均为「框架缺口 / 工具缺口 / 骨架与框架的口径差」，**本任务不修复、不改框架、不发明阈值**，只登记**现状 + 运行期要求 + 归属**；运行期一律按「运行期要求」列执行，并在报告中显式标注口径来源。

| 编号 | 缺口描述 | 现状 | 运行期要求 | 归属 |
| --- | --- | --- | --- | --- |
| **P23-D1** | 框架未定义行业/个股级「ROE 拐点」量化判据 | 框架无阈值条款 | 一律标「**定性推断**」，**不得自行发明阈值** | 框架缺口（只登记） |
| **P23-D2** | 支柱五「政策与资本覆盖度」无工具出口（注资比例 / 场景绑定兑现 / 政策门槛优势） | 无 CLI；须人工取证 | 用**代理指标**（检索类工具 + 年报字段）取证，结论标**低置信度** | 能力缺口 |
| **P23-D3** | 能力圈四维自检为主观自评（无工具化判据） | 无对应工具 | 运行期标「**自评项，非工具化判据**」 | 已知主观项 |
| **P23-D4** | 骨架「RPS / CAN-SLIM」项目内无实现 | 无对应工具 | 以 `stock_quote --momentum`（SMR）与 `trend-momentum-scan` **替代**，并标注**口径差异** | 工具缺口（**未修复**：原指派 P5-2，该任务已收口且未承接） |
| **P23-D5** | 骨架「地缘政治六维度」「华为式抗封锁韧性」框架无对应条款（含自造阈值） | 骨架推导口径 | 标「**骨架推导口径，非框架条款**」 | 骨架与框架口径差 |
| **P23-D6** | 骨架止损阈值（左侧 −15% / 右侧 −8%~−10% / 附录 B −15%）与框架行 529~539 **冲突** | 两套阈值并存 | 按**框架仓位状态分水岭**执行，冲突处标差异 | **直接冲突项** |
| **P23-D7** | 骨架「渗透率 → 仓位上限映射表」框架无对应条款 | 骨架推导口径 | 运行期须**显式标注来源**为骨架推导 | 骨架推导口径 |
| **P23-D8** | 骨架矛盾三（「基本面未变且估值合理可越跌越买」）与框架行 398 / 523~539 冲突 | 两套表述并存 | 登记**直接冲突项**，运行期标差异 | **直接冲突项** |
| **P23-D9** | 引擎 `base_total = Σ dims` **未做权重归一**；`counter_arguments` 模板含骨架表述；技术面红牌态 `counter_arguments` 被清空 | 工具局限 | 报告层须**覆写模板 / 自行重建反证清单** | 工具局限（**未修复**：P5-2 转办不修） |
| **P23-D10** | `batch` **无 `--markdown-only` 等价开关**（必然落盘非 GARP 命名文件） | 工具缺口 | 按**规避方式**使用（指定输出目录/改名）；工具侧修复**未实施**（P5-2 转办不修） | 工具缺口（**未修复**：P5-2 转办不修） |
| **P23-D11** | 框架全文**无「投资论文 / 假设 / 追踪 / 健康度」定义** | 框架缺口 | 如需补定义**只允许末尾附录**（禁止中间插入，否则行号锚点集体失效） | **非本任务范围** |
| **P23-D12** | `员工总数` 在 `stock_financial.py --advanced` 下**恒为 `null`**；无 `--peers` 时 `smr_percentile = null` | 数据降级 | 员工数走**年报解析 stage4 或搜索补充**；板块截面须用 `--auto-peers` | 降级路径 |
| **P23-D13** | 详细计划 P4-14「GARP PEG **五档**」与 `garp-valuation` 统一**六档**不一致 | 表述差（**非口径差**） | 统一收口**六档**，**不得新建「GARP PEG 五档」表** | 表述统一 |
| **P23-D14** | `reports/trend-screen/` **文件数记述时点差**（16 vs 17） | 时点差 | 以**最新批**为准，**不落具体文档章节** | 文档一致性说明 |

### 工具缺陷登记指针（E 类 / A 类，**收口状态已标注**）

| 编号 | 缺陷 | 登记落点 | 处置 |
| --- | --- | --- | --- |
| **P23-E1** | `governance_data.py` 三子命令 `--help` 全部崩溃（argparse `%` 未转义；父级 `--help` 正常） | [garp-governance-tools.md](./garp-governance-tools.md) | **已于 P5-2 §4.4 修复**（12 处 `%(` → `%%(`，四条 `--help` 退出码 0） |
| **P23-A4** | `geo_policy_screen.py scan` 直连抛 `ModuleNotFoundError` | [garp-geo-policy-tools.md](./garp-geo-policy-tools.md) | **已于 P5-2 §4.5 修复**（注入项目根到 `sys.path`，`python x.py` 与 `python -m x` 双形态均可调用） |
| **P23-A3** | 0.3 矩阵各场景**无量化系数**（框架仅定性「投资含义」） | [garp-geo-policy-tools.md](./garp-geo-policy-tools.md) | 运行期采「**定性档位 + 闸门**」，**不得发明系数** |
| **P23-B3** | `fx_rate.py` **跨币种折算不可用** | [garp-valuation-tools.md](./garp-valuation-tools.md) | 声明「**仅取汇率**」，折算由 `financial_rigor.py calc` 显式完成并**标注汇率时点**；工具侧补折算**未实施**（P5-2 转办不修） |

---
## Python 环境

- **Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`
- **工作目录基准**：`F:/Financial_Investment_Analysis/`

---

## 引用方式

其他技能引用公共工具指南时，根据需要引用具体子技能文件：

```markdown
## 工具使用指南

本技能的工具使用规范详见以下公共技能文件：
- A股/港股数据获取：[A股数据](../tools-scripts/a-share-data.md) / [港股数据](../tools-scripts/hk-share-data.md)
- 财务计算与验证：[financial-calc](../tools-scripts/financial-calc.md)
- 长期折现估值：[terminal-value](../tools-scripts/terminal-value.md)
- 网络信息搜索：[web-search-tools](../tools-scripts/web-search-tools.md)
- 报告审核与抽检：[report-audit](../tools-scripts/report-audit.md)
- 全局约束规范：[global-constraints](../tools-scripts/global-constraints.md)
- 国际货币汇率获取：[fx_rate.py 说明](../A股工具使用指南.md#十三fx_ratepy---国际主要货币汇率)

以下为本技能特有的工具使用注意事项（如有）：
- ...
```

或直接引用本索引文件：

```markdown
## 工具使用指南

本技能的工具使用规范详见 [公共工具索引](../tools-scripts/common-tools-guide.md)。
```

---

## 版本信息

- **版本**：2.6.1（2026-09-19 收口订正：E / A 类缺陷指针 8 处就地订正——P23-E1 / P23-A4 回改为**已修复**完成态，P23-D4 / D9 / D10 / B3 明确标注**未修复**（P5-2 转办不修）；2.6.0 为 P4-23 补 `garp-valuation-tools.md` 索引行与「GARP 已知缺口与降级路径」节）
- **创建日期**：2026-07-31
- **更新日期**：2026-09-19
- **维护状态**：活跃维护
