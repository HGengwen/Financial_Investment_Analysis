# 深度公司系列 (Deep Company Series)

8篇长文拆一家公司：从认知重置到决策框架完整闭环

---

## 快速开始

### 基本调用方式

```
/deep-company-series {公司名}
```

例如：
- `/deep-company-series 腾讯`
- `/deep-company-series 拼多多`
- `/deep-company-series 茅台`

---

## 核心功能

为指定公司撰写一个8篇深度长文系列（约12万字），从认知重置到决策框架完整闭环，适合公众号/视频号等公开渠道发布。

### 8篇文章结构

| # | 篇名 | 核心问题 | 字数 |
|---|------|---------|------|
| 01 | 你以为你看懂了 X，其实没有 | 认知重置：破3个常见错觉 | 4,000-5,000 |
| 02 | X 的护城河 | 护城河深不深、未来5/10年还在不在 | 6,000-8,000 |
| 03 | X 的最大利润引擎 | 主业是什么、为什么能持续 | 6,000-8,000 |
| 04 | X 藏在账上的另一家公司 | 投资组合/子公司/隐藏价值 | 8,000-10,000 |
| 05 | AI（或当下叙事）时代，X 是赢家还是输家 | 时代变量：分业务拆 AI 影响 | 8,000-10,000 |
| 06 | 用巴菲特方式拆 X 的财报 | 财务深度：毛利率/FCF/ROE/SBC | 8,000-10,000 |
| 07 | X 的管理层值不值得托付 | 资本配置纪律+诚信检验+接班人 | 8,000-10,000 |
| 08 | 多少钱值得买，什么信号必须卖 | DCF 三情景+红线清单+仓位框架 | 10,000-12,000 |

加一篇 `00-系列说明.md` 作为目录索引（不发表）。

---

## 使用示例

### 示例1：撰写腾讯深度系列
```
/deep-company-series 腾讯
```
 为腾讯撰写8篇深度长文，系列总量约12万字，参考样本 `reports/腾讯/《看懂腾讯》/`

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 深度系列 | `reports/{公司名}/《看懂{公司名}》/` 目录下的8篇文章 + `00-系列说明.md` |
| 去劣筛选 | `reports/{公司名}/{公司名}-quality-screen-{YYYYMMDD}.md` |
| 其他研究 | `reports/{公司名}/{公司名}-research-{YYYYMMDD}.md` |

### 报告目录结构

```
reports/
├── {公司名}/                        — 公司所有研究报告
│   ├── 《看懂{公司名}》/           — 8篇系列长文目录
│   │   ├── 00-系列说明.md          — 目录索引（不发表）
│   │   ├── 01-XX.md ~ 08-XX.md     — 8篇深度长文
│   ├── {公司名}-quality-screen-{YYYYMMDD}.md
│   └── {公司名}-research-{YYYYMMDD}.md
```

---

## 写作标准

### 核心 IP 不是"会写"，而是"会改"

99% 的财经文章在违反本 skill 的事实核查标准。

### 写作风格规范

- **语气**：直接、犀利、不说废话，第一句就给数字或反常识结论
- **价值投资框架**：巴菲特/芒格/段永平/李录视角穿插（但不堆砌名言）
- **不预设立场**：先摆数据→推逻辑→得结论
- **呈现正反两面**：每个核心判断都附"但另一方面..."的反方
- **公众号体感**：前18-20字必须能独立站住（手机预览）
- **标题风格**：用反差数字或反共识结论做钩子，避免流量党比喻

### 禁用词

| 禁用 | 替代 |
|------|------|
| 显然 / 必然 / 一定 | 数据显示 / 证据表明 |
| 我认为 / 我觉得 | 删除或改为"按本框架" |
| 严重不匹配 / 严重低估 | 给具体折让百分比 |
| 完美 / 无可挑剔 | 加上反方观察 |

### 严苛事实核查 Checklist（7项检查）

```
□ 1. 跨篇数字一致性：总市值、净利润、持股%全系列对齐
□ 2. 口径标注：Non-IFRS / GAAP / FCF 各用哪个清楚
□ 3. 重复加计扫描：已并表子公司不在"投资组合"里、SOTP 不双算
□ 4. 横向比较公平性：剔除项双方一致
□ 5. 概率加权全删：不算"30%A+50%B+20%C=期望X%"
□ 6. 绝对化表述全弱化：grep "显然|必然|严重|教科书|完美"
□ 7. 第三方数据来源标注：每条非财报数据后跟"（来源：X）"
```

### 5类"伪精确"陷阱（写之前就要警惕）

1. **概率加权期望值** — 只列情景+触发条件，不算加权
2. **第三方测算 MAU/份额** — 用最可信两个 anchor，其他定性描述
3. **历史增速线性外推** — 改用情景假设+高/低区间
4. **未公开的持股比例** — 给区间，标"不可知"
5. **强归因** — 多重原因都列出，不做单一归因

---

## 工具依赖

### 本地数据获取工具

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票信息查询 | `python tools/a_share/stock_info.py --search 紫金矿业` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 601899` |
| A股 | `tools/a_share/stock_quote.py` | 历史股价与实时行情 | `python tools/a_share/stock_quote.py --code 601899` |
| A股 | `tools/a_share/stock_screen.py` | 质量筛选7条指标 | `python tools/a_share/stock_screen.py --code 601899` |
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
- **国际货币汇率**（跨市场市值/估值统一口径折算）：`tools/common/fx_rate.py`，详见 [A股工具使用指南汇率章节](../../docs/A股工具使用指南.md)

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

1. **事实核查标准** — 每个数据必须来自可靠来源
2. **数据必须标注来源** — 关键数据至少2个来源交叉验证
3. **不虚构数据** — 搜不到就标注"估计"或"不可知"
4. **不用AI腔调** — 禁止"让我们一起来看看"等套话
5. **客观性原则** — 区分事实与观点，用数据支撑判断
6. **呈现正反两面** — 每个核心判断附反面论据
7. **诚实面对信息缺口** — 宁可标注"数据不足"，也不用推测填充
8. **不算期望年化回报加权值** — 主观概率分配会误导读者
9. **网络搜索时效性** — 使用 `--time-range month/week` 限制时间范围，优先获取最新信息
10. **非境内上市双源验证** — 港股/美股公司须 Doubao + Tavily 双源验证

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 所有数据必须标注来源
- 估计值必须明确标注"估计"
- 关键财务数据必须至少两个独立来源交叉验证
- 市值必须手算校验：股价 × 总股本，与报告市值对比
- 货币单位要明确（港币/人民币/美元），防止混淆
- PE/ROE 等指标用 `tools/common/financial_rigor.py` 精确计算
- 不预设立场：先摆数据 → 推逻辑 → 出结论
- 网络搜索须使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 港股/美股公司须 Doubao + Tavily 双源验证，确保信息准确性
- 估值数据须使用 `financial_rigor.py` 校验，禁止 LLM 心算
- 推送前必须用 grep 扫描本机用户名、`/Users/`、真实姓名等隐私字段
- 报告写完后主动询问是否推送到 GitHub

### 修订意见处理级别

| 级别 | 类型 | 处理 |
|------|------|------|
| 🔥 硬错误 | 数字错、归因错、口径错 | 必改，不需犹豫 |
| ⚠️ 主观化 | 强主观词、绝对化、流量党比喻 | 弱化或删除 |
| 🔬 颗粒度 | 来源标注、口径细化 | 按可读性平衡 |
| ❓ 不可靠 | 第三方测算差异大 | 删比改更稳 |

---

## 局限性说明

- 港股小票、新上市公司可能无法获取到完整信息
- 扫描版PDF限制：A股年报常为扫描版PDF，可能无法提取文本内容
- 非实时数据：工具获取的数据可能有延迟
- 第三方测算口径差异大（MAU/份额可能差2-3倍）
- 未上市公司持股比例从未公开披露，只能给区间
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [投研团队](../investment-team/README.md) — 四Agent全面公司研究
- [微信公众号文章](../wechat-article/README.md) — 公众号文章写作
- [质量筛选](../quality-screen/README.md) — 7条指标快速排除非一流公司

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-07-22
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。
