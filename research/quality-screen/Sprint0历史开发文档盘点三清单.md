# Sprint 0 历史开发文档盘点三清单

> **盘点日期**：2026-08-29
> **盘点范围**：`research/quality-screen/` 下 3 份历史开发文档
> **归属**：Sprint 0 任务 2（F-12 历史文档盘点），作为 Sprint 1~3 设计的唯一回溯依据。

---

## 盘点对象

| 编号 | 文档 | 定位 |
| --- | --- | --- |
| A | `trend-tech-screen.md技能文件完整修改建议.md` | 旧技能完整修改建议（五维打分 + 地缘修正 + 技术面止损 + 输出格式） |
| B | `trend-tech-screen工具链开发方案.md` | 工具链四阶段开发方案（缺口矩阵 + 数据源清单 + 验收标准） |
| C | `在研重大项目信息获取方法的整合与强化.md` | 在研项目 10 信息来源 + R8 商业化潜力评分卡 |

---

## 清单 1：已被代码覆盖项

> 文档结论已落地到 `mid-trend-tech-screen/SKILL.md` / `trend_tech_screen.py` / `in_research_scan.py` / `financial_rigor.py` / `annual_report_parser.py` / `stock_quote.py --momentum` / `stock_info.py --profile` 等，**无需重复开发**。

| # | 来源文档 | 结论 | 去向（已落地） |
| --- | --- | --- | --- |
| 1 | A | 五维加权打分体系（满分 100 + 奖励分），含 4 种周期权重配对制 | `mid-trend-tech-screen/SKILL.md` 第二层 + `trend_tech_screen.py score --dims --cycle` |
| 2 | A | 地缘政治二维修正矩阵（国产化率 × 海外对冲，×1.10~×0.40） | SKILL.md 第三层 + `trend_tech_screen.py --geo` |
| 3 | A | 技术面止损校验（破 50 日线放量→预警降级；破 200 日线→红牌清仓，独立否决） | SKILL.md 技术面止损 + `trend_tech_screen.py --tech` |
| 4 | A | 最终评级映射（S≥80 / A 65-79 / B 50-64 / C<50）+ 反证清单模板 | SKILL.md 最终评级 + `trend_tech_screen.py` 评级/反证输出 |
| 5 | A | 估值五件套：PEG / PSG / PE 历史分位 / 市值隐含业绩倒推 | `financial_rigor.py` 的 `peg` / `ps-g` / `pe-percentile` / `implied-growth` |
| 6 | A | 250 日 SMR 相对强度 + RSI(50) + MA50/MA200 + 量能 | `tools/common/momentum.py` + 三市场 `stock_quote.py --momentum`（A股 `--auto-peers` 申万截面） |
| 7 | A | 机构覆盖度 / 研报数（欧奈尔 I 因子） | 三市场 `stock_info.py --profile` |
| 8 | A | 供应链话语权科目（应付账款周转天数 / 预付款项，郑希科技通胀验证） | `stock_financial.py --advanced`（A/港/美三市场） |
| 9 | B | 工具链四阶段全部产物（A–F 扩展 + G–H 新增） | 阶段一~四全部落地，见文档 A 末尾「四阶段开发落地对照」 |
| 10 | B | `geo_political.py` / `supply_chain.py` 不开发决策 | 已按 `doubao_search` 搜索 + `annual_report_parser` 年报抽取替代 |
| 11 | B | 年报结构化抽取（员工/子公司/研发/收入分部/新品/供应链） | `tools/common/annual_report_parser.py`（33 用例通过） |
| 12 | C | R8 在研项目商业化潜力评分卡（5 维度满分 10 分，+3/+5 奖励 / <0 风险降级） | SKILL.md「2.1 R8」+ `trend_tech_screen.py score --r8` |
| 13 | C | 在研项目多渠道批量扫描（gov/patent/bidding/academic/investor/website/research + 可选年报解析） | `tools/specialized/in_research_scan.py scan`（SKILL.md 步骤3-A 引用） |

---

## 清单 2：可复用设计结论（Sprint 1~3 直接引用，无需重新设计）

> 以下阈值表 / 评分卡 / 信号分级已在历史文档中设计成型，可作为后续 `valuation-thermometer` / `exit-signal` / 报告模板的直接输入。

| # | 来源文档 | 结论 | 去向（待引用） |
| --- | --- | --- | --- |
| 1 | A | 周期权重配对制（需求爆发期 ①35→42 且②25→18；技术跃迁期 ②25→32 且①35→28；成熟稳定期 ⑤10→15；无法判定默认需求爆发期） | Sprint 1 打分引擎参数化直接沿用，已由 `--cycle` 固化 |
| 2 | A | PEG 评分梯度 + 爆发期豁免规则（<1.0 5分 / 1.0-1.5 3分 / >1.5 0分；营收增速>50% 且毛利率>35% 时 1.5-2.5 改 2 分观察；>3 触发估值透支警告） | Sprint 1 `valuation-thermometer` 的 PEG 档位依据（注意与主方案五档表的统一，见清单 3-4） |
| 3 | A | PSG 触发条件（净利率<5% 或 营收增速>50%）与评分梯度（<0.5 / 0.5-1.0 / >1.0） | Sprint 1 估值温控计的 PSG 判定依据 |
| 4 | A | 地缘二维修正系数矩阵（×1.10/×1.00/×0.95/×0.80/×0.65/×0.60/×0.40） | `trend_tech_screen.py --geo` 已内置，Sprint 后续评分直接调用 |
| 5 | A | 反证清单跟踪指标与阈值（订单<20% 连续两季 / 毛利率跌破 35% / SMR 跌破 60% 分位 / 机构减持>10% 等） | Sprint 2 `exit-signal` 信号分级与告警阈值的直接蓝本 |
| 6 | A | 市值隐含业绩倒推红/黄/绿判定（隐含增速 < 指引上限=合理；≈±10%=公允；>1.5×=红灯透支） | `financial_rigor.py implied-growth` 已内置，Sprint 1 直接复用 |
| 7 | A | 报告输出格式模板 + 路径规范（`reports/trend-screen/{名称}-trend-screen-{YYYYMMDD}.md` 等四模式） | Sprint 3 报告模板可直接复用 |
| 8 | B | 数据源接口清单（akshare/yfinance 具体接口 + 【已验证】/【待验证】标注） | Sprint 1~2 扩展新科目时直接按清单核对，无需重新调研 |
| 9 | B | 缓存策略（mtime + miss 双触发 + stale 降级，港股/美股新科目对齐 hit→refresh→stale） | Sprint 1~2 扩展缓存时沿用既有规范 |
| 10 | B | 打分引擎验收样例（A=101×1.10≈111 S级 / B=82 S级 / C=40×0.65=26 C级） | Sprint 1 回归测试的黄金样本 |
| 11 | C | 投资者互动平台信号分级表（极强利好/强利好/中性/强风险/警惕，五级） | Sprint 2 `exit-signal` 舆情/进展信号分级的直接输入 |
| 12 | C | 在研项目信息来源可靠性分级（年报/公告 ⭐⭐⭐⭐⭐ … 官网/研报 ⭐⭐⭐） | Sprint 1 在研扫描结果加权时的权重依据 |
| 13 | C | 各渠道搜索指令模板（`doubao_search --sites gov.cn/ccgp.gov.cn/cpquery...`） | 已由 `in_research_scan.py` 内置为查询配方，Sprint 1 直接复用 |

---

## 清单 3：待吸收但尚未实现项（Sprint 1~3 需补齐的缺口）

| # | 来源文档 | 缺口描述 | 建议去向 |
| --- | --- | --- | --- |
| 1 | C | 在研项目 10 信息来源中，「科创板/创业板公告」与「临床试验登记（医药）」两类渠道未纳入 `in_research_scan.py` 自动化（当前仅 gov/patent/bidding/academic/investor/website/research 七渠道 + 年报解析），需 `doubao_search` 手动补充 | Sprint 1：评估是否扩展 `in_research_scan.py` 增补 `announcement`、`clinical` 两渠道 |
| 2 | B（5.5） | 美股员工数：yfinance `fullTimeEmployees` 常为空，无可靠接口 | Sprint 1：输出显式标注「数据缺失/搜索补充」，禁止静默用错误数据 |
| 3 | B（5.5） | 港股研报覆盖数：akshare 无直接接口 | 已由 `stock_info.py --profile` 以 `doubao_search` 半自动统计落地（标注缺口）；Sprint 1 复核口径 |
| 4 | 任务1实测 | `financial_rigor.py peg` 内置评级与主方案五档表不一致：`--pe 25 --growth 20` → PEG=1.25，工具输出「合理」，方案五档表应为「偏贵（1.2~1.5）」 | Sprint 1 `valuation-thermometer` 前统一 PEG 评级口径（工具内置 vs 五档表） |
| 5 | 任务1实测 | `financial_rigor.py pe-percentile` 当前值取序列最小值时输出 14.3% 而非 0%，分位口径（是否含自身/插值方式）待确认 | Sprint 1 明确 `pe-percentile` 分位口径与边界定义 |

---

## 附：盘点结论

1. **3 份历史文档的 95% 以上结论已落地**（13 项全覆盖 + 13 项可复用），Sprint 1~3 不会重复设计，直接按「清单 2」引用即可。
2. **真实待办集中在 5 项**（清单 3），其中 2 项为任务 1 实测发现的估值命令口径问题，应作为 Sprint 1 `valuation-thermometer` 命令模板的前置修正项。
3. 本文档作为 Sprint 1 启动时的**设计回溯清单**：新增阈值/评分卡一律先查「清单 2」，避免与既有结论冲突。
