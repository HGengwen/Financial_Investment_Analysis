---
name: trend-tech-screen
description: "景气趋势筛选打分引擎（trend-tech-screen）：聚合上游工具数据，执行五维加权打分（100+奖励）、地缘政治二维修正、技术面止损校验（独立否决）、评级映射与反证清单，批量模式支持行业景气一致性两轮修正，输出结构化JSON+Markdown，禁止LLM心算。"
disable-model-invocation: true
---

# 景气趋势筛选打分引擎

使用 `trend_tech_screen.py` 作为景气趋势筛选技能（欧奈尔 CAN SLIM / 林奇 GARP / 郑希全球景气 / 李进产业验证）的**聚合与计算中枢**，遵循项目"禁止 LLM 心算"规范。

> 本引擎输入为上游各工具的**指标得分**（不直接拉取网络），地缘二维评估与技术面数据由调用方传入。缺失科目留空并标注 `"note": "数据缺失"`，不阻断打分。

---

## Python 环境

- **Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`
- **工作目录基准**：`F:/Financial_Investment_Analysis/`

---

## 单公司打分

```bash
python tools/specialized/trend_tech_screen.py score \
  --name {公司} --cycle 需求爆发期 \
  --dims '{"a":40,"b":27,"c":13,"d":17,"e":4}' \
  --geo '{"x":"高","y":"高"}' \
  --tech '{"close_above_ma200":true,"close_above_ma50":true,"volume_above_1_5x":false}' \
  --r8 '{"商业化确定性":2,"市场空间":2,"外部背书":2,"专利验证":1,"管理层一致性":1}'
```

- `--cycle`：周期模式（需求爆发期 / 技术跃迁期 / 成熟稳定期 / 无法判断），默认"需求爆发期"，采用配对制权重调整
- `--dims`：五维得分（a=景气前瞻 / b=研发执行力 / c=人才 / d=动量共识 / e=估值）
- `--geo`：地缘二维评估（x=制裁风险 / y=海外实体）→ 乘数修正
- `--tech`：技术面数据 → 独立否决校验（破 50 日线放量预警降级、破 200 日线红牌强制降级）
- `--r8`：在研项目商业化潜力五子分（科创企业必查）→ 引擎自动判定奖励分（≥8 → +5 / 6-8 → +3）与风险降级（<0 → 评级下调一级），满分 10，禁止 LLM 心算

## 批量两轮计算

```bash
python tools/specialized/trend_tech_screen.py batch --input companies.json --cycle 需求爆发期
```

先算各公司基础分，再按行业通过率修正：通过率 >60% 集体 +2 分 / <30% 集体 -2 分。

---

## 输出

- **结构化 JSON**：逐项得分、加权总分、地缘修正后得分、最终评级（S/A/B/C）、反证清单
- **Markdown 报告**：路径遵循 `reports/trend-screen/` 规范

---

## 上游数据工具

| 维度 | 数据来源 |
|------|---------|
| 财务科目 | `stock_financial.py`（A股 `--advanced` / 港股 `--advanced` / 美股 `--indicators`） |
| 动量与技术面 | `stock_quote.py --momentum`（SMR/RSI(50)/MA50/MA200/量能） |
| 市值/覆盖度 | `stock_info.py --profile` |
| 估值计算 | `financial_rigor.py`（peg / ps-g / pe-percentile / implied-growth） |
| 年报字段 | `annual_report_parser.py`（员工/子公司/新品/供应链/收入分部） |
| 在研项目扫描 | `in_research_scan.py scan {公司} --market sz --official-site {官网} --annual-report {年报md}`（gov/patent/bidding/academic/investor/website/research 多渠道，R8 数据源） |
| 政策/制裁/国产化 | `doubao_search.py` / `anysearch.py` |

详见各对应技能文件与 [公共工具索引](./common-tools-guide.md)。

---

## 在研项目扫描（R8 数据源，科创企业必查）

R8 在研项目商业化潜力评分卡的五子分由 `in_research_scan.py` 一键获取，将方案文档步骤 3-A 的 8 条手动搜索指令整合为批量入口：

```bash
# 全渠道扫描 + 年报解析 + 导出 Markdown 报告
python tools/specialized/in_research_scan.py scan "{公司}" \
  --market sz --official-site "{官网}" --annual-report "{年报md}" --export

# 指定渠道子集（加速验证）
python tools/specialized/in_research_scan.py scan "寒武纪" --channels patent,gov,bidding --json

# 列出渠道
python tools/specialized/in_research_scan.py list
```

渠道清单：`gov`（政府立项背书）/ `patent`（专利检索）/ `bidding`（招投标）/ `academic`（学术社区）/ `investor`（深交所互动易 + 上交所 e互动）/ `website`（官网，需 `--official-site`）/ `research`（券商研报）/ `annual_report`（年报章节，需 `--annual-report`）。

将聚合结果填入 R8 评分卡五项，再传入 `trend_tech_screen.py score --r8` 自动判定奖励分与风险降级，**禁止 LLM 心算**。

---

## 相关技能

- [财务计算与验证](./financial-calc.md)
- [年报结构化抽取](./annual-report-parser.md)
- [在研重大项目信息获取](./in-research-scan.md)（R8 在研评分数据源，科创企业必查）
- [A股数据获取](./a-share-data.md) / [港股数据获取](./hk-share-data.md)
- [网络信息搜索](./web-search-tools.md)

---

## 版本信息

- **版本**：1.1.0
- **创建日期**：2026-08-25
- **更新日期**：2026-08-26（补齐 `--r8` 参数说明；新增在研项目扫描工具 `in_research_scan.py` 章节）