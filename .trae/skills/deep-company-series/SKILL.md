---
name: deep-company-series
description: "深度公司系列：8篇长文拆一家公司。为指定公司撰写8篇深度长文系列（约12万字），从认知重置到决策框架完整闭环，适合公众号/视频号等公开渠道发布。"
disable-model-invocation: true
---

# 深度公司系列：8 篇长文拆一家公司

为 $ARGUMENTS 撰写一个 8 篇深度长文系列，发布在公众号/视频号等公开渠道。**核心 IP 不是"会写"，而是"会改"——99% 的财经文章在违反本 skill 的事实核查标准**。

参考样本：`reports/腾讯/《看懂腾讯》/`

---

## 一、触发场景

用户希望为一家公司做"教科书级别"的深度研究，并以**系列长文**形式公开发布。区别于一篇研报：
- 8 篇约 12 万字，从认知重置到决策框架完整闭环
- 每篇独立成文（适合单篇分享），但贯穿一套估值/管理层/价格判断
- 写给"愿意花 90 分钟读懂一家公司"的读者，不是写给券商客户

**不适合用本 skill 的场景**：单篇研报、季报点评、行业研究——那些用 `/investment-research`、`/earnings-review`、`/industry-research`。

---

## 二、系列篇目模板（8 篇）

| # | 篇名模板 | 核心问题 | 字数 |
|---|---------|---------|------|
| 01 | 你以为你看懂了 X，其实没有 | 认知重置：破 3 个常见错觉 | 4,000-5,000 |
| 02 | X 的护城河——`<生意本质一句话>` | 护城河深不深、未来 5/10 年还在不在 | 6,000-8,000 |
| 03 | X 的最大利润引擎——`<最赚钱业务>` | 主业是什么、为什么能持续 | 6,000-8,000 |
| 04 | X 藏在账上的另一家公司——`<隐藏资产>` | 投资组合 / 子公司 / 隐藏价值 | 8,000-10,000 |
| 05 | AI（或当下叙事）时代，X 是赢家还是输家 | 时代变量：分业务拆 AI 影响 | 8,000-10,000 |
| 06 | 用巴菲特方式拆 X 的财报 | 财务深度：毛利率/FCF/ROE/SBC | 8,000-10,000 |
| 07 | `<管理层金句>`——X 的管理层值不值得托付 | 资本配置纪律 + 诚信检验 + 接班人 | 8,000-10,000 |
| 08 | 多少钱值得买，什么信号必须卖（系列终章） | DCF 三情景 + 红线清单 + 仓位框架 | 10,000-12,000 |

加一篇 `00-系列说明.md` 作为目录索引，不发表。

---

## 三、写作风格规范

### 语气

- **直接、犀利、不说废话**——第一句就给数字或反常识结论
- **价值投资框架**——巴菲特/芒格/段永平/李录视角穿插（但不堆砌名言）
- **不预设立场**——先摆数据、再推逻辑、最后得结论
- **呈现正反两面**——每个核心判断都附"但另一方面..."的反方
- **公众号体感**——前 18-20 字必须能独立站住（手机预览）

### 禁用词

| 禁用 | 原因 | 替代 |
|------|------|------|
| 显然 / 必然 / 一定 | 主观绝对化 | 数据显示 / 证据表明 |
| 我认为 / 我觉得 | 主观腔调 | 删除或改为"按本框架" |
| 教科书级别 / 神来之笔 | 流量党褒奖 | 描述具体事实 |
| 严重不匹配 / 严重低估 | 强主观词 | 给具体折让百分比 |
| 完美 / 无可挑剔 | 单边判断 | 加上反方观察 |

### 标题风格

- 用**反差数字**或**反共识结论**做钩子（"15 年 7 次挑战全失败"、"年薪 4292 万仅占利润的万分之 1.65"）
- 副标题中性、概括内容（"——`<本质判断>`"）
- **避免流量党比喻**："小巴菲特"、"中国版 X"、"YYDS" 一律避开
- 用专业读者熟悉的术语（"伯克希尔"而不是"巴菲特"，公司名优于人名）

---

## 四、严苛事实核查 Checklist（核心 IP）

### 写之前就要警惕的"伪精确"陷阱

1. **概率加权期望值**：`30% × A + 50% × B + 20% × C = 期望 +X%` 这种计算几乎全是垃圾——概率分配是纯主观，给读者错误精确感。**只列情景 + 触发条件 + 方向，不算加权期望**。
2. **第三方测算 MAU/份额**：QuestMobile/七麦/CBNData 等口径差异巨大（同一时点能差 2-3 倍）。**只用最可信的两个对比作 anchor，其他做定性描述**。
3. **历史增速线性外推**：`2025 年 +33% × 5 年复合 → 2030 年 X` 是金融文盲式预测。**情景假设 + 高/低区间 + 不是承诺**。
4. **未公开的持股比例**：字节、Halti 类未上市公司持股**从未公开披露**。**给区间，标"不可知"**。
5. **强归因**：竞争对手失败 = 因为 X。多重原因都列出来，**本文不做单一归因**。

### 修订时必跑的 7 项检查

```
□ 1. 跨篇数字一致性：总市值、Non-IFRS 净利润、关键持股 % 全系列对齐
□ 2. 口径标注：Non-IFRS / GAAP / Non-IFRS-SBC / FCF 各用哪个，全文清楚
□ 3. 重复加计扫描：已并表子公司不在"投资组合"里、SOTP 不双算
□ 4. 横向比较公平性：不能"主业 PE（剔除现金+组合）" vs "对手 PE（不剔）"
□ 5. 概率加权全删：见上一条
□ 6. 绝对化表述全弱化：grep "显然|必然|严重|教科书|完美"
□ 7. 第三方数据来源标注：每条非财报数据后跟"（来源：X）"
```

### 模型偏好

写之前**先列出已知硬错误风险**：
- 历史回报倍数：必须用累计投入口径（如 Riot 33 倍 不是 58 倍）
- 持股比例：必须看最新富途/财报口径（如腾讯持有美团 1.5% 不是 6.4%）
- "派息分派"会计处理：视同处置收益按 IFRIC 17 在宣派日确认（如京东在 2021，美团在 2022 但金额小）
- 总股本会反弹：SBC 集中年初授予会让股本短期上升

---

## 五、执行流程

### 阶段 1：调研（写 01-02 篇前完成）

1. **阅读公司近 5 年年报、最新季报**
   - A股公司：使用 `tools/a_share/stock_screen.py` 获取财务数据；使用 `tools/common/doubao_search.py`（首选）或 `tools/common/web_search.py` 搜索年报信息
   - 港股公司：使用 `tools/hk_stock/stock_screen.py` 获取财务数据；使用 `tools/common/doubao_search.py`（首选）或 `tools/common/tavily_search.py`（双源验证）搜索年报信息
   - 美股公司：使用 `tools/us_stock/stock_financial.py` 获取财务数据；使用 `tools/common/doubao_search.py`（首选）或 `tools/common/tavily_search.py`（双源验证）搜索年报信息

2. **阅读至少 3 份独立卖方研报**（找共识 + 反共识）
   - 使用 `tools/common/doubao_search.py`（首选）或 `tools/common/web_search.py` 搜索券商研报
   - 或用户提供研报材料

3. **使用 `/quality-screen` 先生成内部筛选底稿**
   - 执行7条去劣指标筛选
   - 确认公司是否符合一流公司标准

4. **与用户确认 8 篇的核心论点**（避免写完才发现方向不对）

### 阶段 2：写作（按 01→08 顺序写，不跳）

- 每篇写完先存 `reports/{公司名}/《看懂{公司名}》/0X-XX.md`
- 不立即推 GitHub——等用户审阅
- 用户提修订意见后修改
- 修订完才 git push

### 阶段 3：跨篇一致性扫描（08 篇全部写完后）

派 Task agent 并行扫描 8 篇做以下检查：
1. 同一数字（市值、净利润、持股比例）跨篇是否一致
2. 同一术语（FBS、SBC、Non-IFRS）首次出现是否解释
3. 引用关系：02 篇说"详见 06 篇"是否真的对应
4. 要点回顾 vs 正文是否数字一致

### 阶段 4：发布前最终核查

```bash
# 推送前必须本地 grep 一次（按本工作区隐私规则）
grep -r "<本机用户名>\|/Users/\|<个人身份信息>" reports/ | head
```

确认无误后才 `git pull --rebase && git commit && git push`。

---

## 六、修订意见处理流程

用户给修订意见时，按以下顺序处理：

### 1. 先核查事实（不要直接改）

如果用户说"X 数据不对"，先用工具找原始数据交叉验证：
- A股公司：使用 `tools/a_share/stock_screen.py` 或 `tools/a_share/stock_financial.py`；使用 `tools/common/doubao_search.py`（首选）或 `tools/common/web_search.py` 搜索官方披露
- 港股公司：使用 `tools/hk_stock/stock_screen.py` 或 `tools/hk_stock/stock_info.py`；使用 `tools/common/doubao_search.py`（首选）或 `tools/common/tavily_search.py`（双源验证）搜索官方披露
- 美股公司：使用 `tools/us_stock/stock_financial.py` 或 `tools/us_stock/stock_info.py`；使用 `tools/common/doubao_search.py`（首选）或 `tools/common/tavily_search.py`（双源验证）搜索官方披露
- 给出"用户说的数据 vs 我查到的数据 vs 我之前用的数据"三方对比

### 2. 判断修订级别

| 级别 | 类型 | 处理 |
|------|------|------|
| 🔥 硬错误 | 数字错、归因错、口径错 | 必改，不需犹豫 |
| ⚠️ 主观化 | 强主观词、绝对化、流量党比喻 | 弱化或删除 |
| 🔬 颗粒度 | 来源标注、口径细化 | 优先级低，按可读性平衡 |
| ❓ 不可靠 | 第三方测算差异大 | **删比改更稳**（用户明确指示） |

### 3. 修订后联动检查

修一处先想"哪些地方还会引用这个数字/概念"。例：
- 改了总市值 → 全系列联动改 PE / 主业 PE / 折让 / FCF Yield
- 改了持股 % → 改 TOP 10 排序 + 历史持股表 + 减持清单
- 改了术语口径 → 改首次定义 + 后续引用 + 要点回顾

### 4. 推送后立即报告

```
推送成功（commit hash）。
[N] 处修订总结 [带表]：
- 改了什么
- 联动改了什么
- 还有什么没改

下一步等指示。
```

---

## 七、数据获取工具使用指南

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
- **A股工具**：[docs/A股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/A股工具使用指南.md)
- **港股工具**：[docs/港股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/港股工具使用指南.md)
- **美股工具**：[docs/美股工具使用指南.md](file:///f:/Financial_Investment_Analysis/docs/美股工具使用指南.md)
- **国际货币汇率**（跨市场市值/估值统一口径折算）：`tools/common/fx_rate.py`，详见 [A股工具使用指南汇率章节](file:///f:/Financial_Investment_Analysis/docs/A股工具使用指南.md)

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

---

## 八、报告输出规范

### 报告目录结构

```
reports/
├── {公司名}/                        — 公司所有研究报告
│   ├── 《看懂{公司名}》/           — 8篇系列长文目录
│   │   ├── 00-系列说明.md          — 目录索引（不发表）
│   │   ├── 01-你以为你看懂了X，其实没有.md
│   │   ├── 02-X的护城河.md
│   │   ├── 03-X的最大利润引擎.md
│   │   ├── 04-X藏在账上的另一家公司.md
│   │   ├── 05-AI时代，X是赢家还是输家.md
│   │   ├── 06-用巴菲特方式拆X的财报.md
│   │   ├── 07-X的管理层值不值得托付.md
│   │   └── 08-多少钱值得买，什么信号必须卖.md
│   ├── {公司名}-quality-screen-{YYYYMMDD}.md — 去劣筛选报告
│   └── {公司名}-research-{YYYYMMDD}.md      — 其他研究报告
```

### 报告命名规范

- 系列长文：`reports/{公司名}/《看懂{公司名}》/0X-XX.md`
- 筛选报告：`reports/{公司名}/{公司名}-quality-screen-{YYYYMMDD}.md`
- 研究报告：`reports/{公司名}/{公司名}-research-{YYYYMMDD}.md`

---

## 九、GitHub 操作

- 本地仓库路径：`f:\Financial_Investment_Analysis\`
- 远程仓库：用户自行配置
- 推送前先 `git pull --rebase`（如有远程仓库）
- commit message 用中文，描述清楚改了什么
- 不要推送中间过程文件（如 data_collection.md），只推最终报告

## 常用命令

```bash
# 推送报告到GitHub
cd f:\Financial_Investment_Analysis
git add reports/xxx.md
git commit -m "添加xxx报告"
git pull --rebase
git push
```

---

## 十、本 skill 不做什么

- **不替读者做投资决策**——所有篇章末尾"不构成投资建议"
- **不预测股价**——只给"情景 + 触发条件"
- **不算"期望年化回报"加权值**——主观概率分配会误导读者
- **不写"X 大佬也持有"** —— 用别人的持仓为自己的判断背书是反价值投资的
- **不强求 8 篇都写**——如果某篇没足够独立内容（如某公司管理层不够特别），合并到其他篇或减篇数

---

## 十一、合规与隐私

- 所有公开报告**只用公开信息**（财报、官方披露、券商研报、知名第三方机构）
- 不用任何**用户个人信息**（公司花名、内部 IM、未公开持仓信息）
- 推送前必须用 grep 扫描 本机用户名 / `/Users/` / 真实姓名 等隐私字段
- 公开署名按用户多层身份策略，不混用

---

## 十二、注意事项

- 市值必须手算校验：股价 × 总股本，与报告市值对比
- 货币单位要明确（港币/人民币/美元），防止混淆
- PE/ROE等指标用 `tools/common/financial_rigor.py` 精确计算
- A股/港股/美股财务数据优先使用本地工具
- 网络信息需交叉验证，不要依赖单一来源
- 网络搜索须使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 港股/美股公司须 Doubao + Tavily 双源验证，确保信息准确性
- 估值数据须使用 `financial_rigor.py` 校验，禁止 LLM 心算
- 报告写完后主动询问是否推送到GitHub

---

## 一句话总结

**写《看懂 X 系列》的核心能力 ≠ 写得好，而是改得严**——
89% 的财经长文死于伪精确数字、主观加权期望值、绝对化表述。本 skill 的存在就是为了把这些坑全部标记出来，写之前避开，写之后扫干净。