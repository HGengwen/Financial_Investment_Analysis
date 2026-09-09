# 微信公众号文章（1~3年景气投资版）(Mid Wechat Article)

作者-编辑-读者三 Agent 协作深度研究，产出可直接发布的公众号文章，以景气投资（GARP）分析为主、技术解读为辅

> 本技能属**中期链（1-3 年）**，与长期版 [wechat-article](../wechat-article/README.md)（10 年 / 巴芒段李）**物理隔离、功能互补**。核心是「用文章把中期景气逻辑讲清楚」：林奇看生意与估值、郑希看产业景气、欧奈尔看风控底线、李进看组合管理与治理。

---

## 快速开始

### 基本调用方式

```
/mid-wechat-article {主题}
```

支持输入格式：

- **景气投资类（默认）**：财报解读 / 产业链分析 / 投资方法论
  - `腾讯2025Q4财报解读（景气视角）`
  - `AI算力产业链瓶颈分析`
  - `为什么PEG<1是买入信号`
  - `光模块行业中期景气怎么看`
- **技术解读类**：论文 / 技术报告 / 新产品解读
  - `大模型OPD技术解读`
  - `Qwen3技术报告解读`

例如：

- `/mid-wechat-article 腾讯2025Q4财报解读（景气视角）`
- `/mid-wechat-article AI算力产业链瓶颈分析`
- `/mid-wechat-article 大模型OPD技术解读`

---

## 核心功能

对指定主题进行深度研究，产出可直接发布的公众号文章。三个 Agent 各司其职：

- ✍️ **作者 Agent** — 深度研究后撰写初稿（景气投资类采用四大师分析框架）
- 🖊️ **编辑 Agent** — 精修结构、标题、节奏与表达
- 👀 **读者 Agent** — 从目标受众视角审读，找出"看不懂/不想看/不转发"的地方

### 四阶段流程

**阶段一·研究与素材收集**：明确文章定位（文章类型 / 目标读者 / 深度 / 长度）→ 并行启动 2-3 个研究 Agent 收集素材 → 信息丰富度评级（A/B/C）→ 整理素材框架

**阶段二·作者写初稿**：作者 Agent 按通用模板撰写；景气投资类追加四大师分析框架与 P0~P5 卖出纪律映射表

**阶段三·编辑 + 读者并行审阅**：编辑精修表达，读者模拟真实阅读体验，景气类文章另有额外审阅标准

**阶段四·定稿**：综合反馈 → 执行修改 → 提取配图 → **数据抽检准出（`report_audit.py`）** → 产出最终文件

### 设计理念

一篇好的公众号文章需要同时满足三个维度：

1. **深度**——对得起花时间读完的人（作者负责）
2. **可读性**——结构清晰、节奏好、不劝退（编辑负责）
3. **真的能看懂**——目标读者不会在中途放弃（读者负责）

单人写作容易"自嗨"。三 Agent 协作的本质是**强制引入外部视角**。

**景气投资类文章的特别说明**：文章视角采用四位景气大师框架（对齐 `research/个人投资者1~3年中长期投资思想与理念 V2.0.md` 权威分工表）：

| 大师 | 思维模式 | 在框架中的角色 | 在文章写作中的落点 |
|------|---------|---------------|-------------------|
| 欧奈尔 | 工程师思维 · 信号与纪律 | **风控底线**：8% 止损、卖出触发、防止深度套牢 | 风险与纪律章节：止损位、趋势信号、P0~P5 触发检查 |
| 林奇 | 侦探思维 · 常识与求证 | **选股起点 + 估值定价**：生活常识选股、六类分类、PEG | 生意本质章节：六类分类、常识验证、PEG 估值 |
| 郑希 | 物理学家思维 · 周期与第一性原理 | **赛道选择**：ROE 拐点、产业景气、渗透率、地缘政治 | 景气验证章节：ROE 趋势、产业景气、地缘风险 |
| 李进 | 系统工程师思维 · 均衡与渗透率 | **组合管理 + 治理**：渗透率定位、底仓/机动仓、管理层与科研转化、治理一票否决 | 风险与纪律章节：管理层评估、渗透率定位、仓位建议 |

---

## 使用示例

### 示例1：A股景气财报解读
```
/mid-wechat-article 新易盛2025Q3财报解读（景气视角）
```
 使用 `stock_financial.py` 获取财务数据，四大师框架拆解光模块景气逻辑，输出 `reports/新易盛/新易盛-mid-wechat-20260908.md`

### 示例2：产业链景气分析
```
/mid-wechat-article AI算力产业链瓶颈分析
```
 结合 `mid-industry-research` 口径分析渗透率位置与景气拐点，输出产业链分析文章

### 示例3：港股财报解读
```
/mid-wechat-article 腾讯2025Q4财报解读（景气视角）
```
 港股数据用 `hk_stock` 工具，双源验证（doubao+tavily），PEG 档位以 `valuation-thermometer` 输出为准

### 示例4：技术解读类
```
/mid-wechat-article 大模型OPD技术解读
```
 下载论文 PDF，`pdf_extract.py` 提取文字表格 + `pdftoppm` 渲染高清配图，输出技术解读文章

---

## 输出报告

报告将保存在以下位置：

| 报告类型 | 文件路径 |
|---------|---------|
| 景气投资主题 | `reports/{公司名}/{公司名}-mid-wechat-{YYYYMMDD}.md` |
| 技术主题 | `reports/AI产业研究/公众号-{主题关键词}-mid-wechat-{YYYYMMDD}.md` |
| 通用主题 | `reports/公众号-{主题关键词}-mid-wechat-{YYYYMMDD}.md` |
| 配图资源 | `assets/{主题简称}/fig{序号}-{描述}.png` |

### 输出文件结构

```
reports/
├── {公司名}/
│   ├── {公司名}-mid-wechat-{YYYYMMDD}.md        ← 景气投资类公众号文章（定稿）
│   └── {公司名}-mid-wechat-{YYYYMMDD}-底稿.md   ← 作者初稿/编辑读者反馈（可选，自用）
├── AI产业研究/
│   └── 公众号-{主题}-mid-wechat-{YYYYMMDD}.md   ← 技术解读类
└── assets/{主题简称}/fig{序号}-{描述}.png        ← 配图资源
```

> **命名规范**：所有输出文件使用 `-mid-wechat-` 后缀，与长期版 `/wechat-article` 的 `-公众号-` 命名**物理隔离**，避免文件碰撞。

---

## 质量标准

### 景气投资类文章的四大检视维度

1. **四大师视角均衡** — 林奇（六类分类 + PEG）、郑希（ROE 趋势 + 渗透率 + 地缘）、李进（管理层 + 科研转化 + 治理一票否决）、欧奈尔（止损位 + P0~P5）是否有遗漏？
2. **估值口径正确** — PEG 档位结论是否与 `valuation-thermometer` 五档一致？有无自行罗列阈值？
3. **卖出纪律准确** — 是否与 `exit-signal` P0~P5 一致？止损位是否具体明确？
4. **结论行动化** — 结论段是否对**持有者、观望者分别给出操作指引**（持有/加仓/减仓/清仓 + 核心理由）？

### 数据抽检准出（发布前必做）

文章落盘后**必须**执行数据抽检，通过后方可视为定稿：

```bash
# Step 1 - 提取抽检清单（15%随机抽样）
python tools/common/report_audit.py extract \
  --report reports/{公司名}/{公司名}-mid-wechat-{YYYYMMDD}.md --seed 42

# Step 2 - 对清单每项从可靠信源取数（按市场分别使用对应工具，计算验算用 financial_rigor.py）

# Step 3 - 输出准出/打回判决
python tools/common/report_audit.py verdict \
  --results '<填好的JSON>' \
  --report {公司名}-mid-wechat-{YYYYMMDD}.md
```

**【准出】** 所有抽检点偏差 ≤ 1% → 文章可发布；**【打回】** 任意点偏差 > 1% → 修正后重新抽检。

### 信息丰富度评级（景气投资类必做）

| 等级 | 特征 | 影响 |
| ---- | ---- | ---- |
| A级 | 获取到完整原文（财报/研报/一手数据） | 正常执行全部步骤 |
| B级 | 仅获取到部分原文或第三方汇总 | 标注「非原始来源」，推算数据标注置信度 |
| C级 | 仅有新闻报道和数据网站摘要 | 转第一性原理模式：聚焦核心数据变化，明确标注「一手资料不足」，不展开细节推断 |

---

## 工具依赖

### 本地数据获取工具（景气投资类文章适用）

根据上市地点选择相应的工具：

| 市场 | 工具 | 功能 | 命令示例 |
|------|------|------|---------|
| A股 | `tools/a_share/stock_info.py` | 股票信息查询 | `python tools/a_share/stock_info.py --search 紫金矿业` |
| A股 | `tools/a_share/stock_financial.py` | 财务指标（ROE、毛利率等） | `python tools/a_share/stock_financial.py --code 601899` |
| A股 | `tools/a_share/stock_quote.py` | 历史股价与实时行情 | `python tools/a_share/stock_quote.py --code 601899` |
| A股 | `tools/a_share/stock_equity.py` | 股权结构与财报下载 | `python tools/a_share/stock_equity.py --code 601899` |
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
- **国际货币汇率**（跨币种数据折算）：`python tools/common/fx_rate.py --code HKDCNY`

### 精确计算与口径引用工具

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/common/financial_rigor.py` | 精确金融计算（PEG、PE、ROE、市值校验等） | `python tools/common/financial_rigor.py peg --pe 25 --growth 20` |
| `tools/common/fx_rate.py` | 国际货币汇率（跨币种折算） | `python tools/common/fx_rate.py --code HKDCNY` |
| `tools/common/report_audit.py` | 报告数据抽检与审核（准出流程） | `python tools/common/report_audit.py extract --report reports/xxx.md` |

**重要约束（引用不重复定义）**：
- PEG 计算必须用 `financial_rigor.py`，**禁止 LLM 心算**
- **PEG 档位判定、边界约定与底仓/机动仓操作映射，一律以 `valuation-thermometer` 输出为准**，本技能不重复定义五档阈值
- **卖出纪律 P0~P5 触发条件与阈值，一律以 `exit-signal` 输出为准**，本技能仅作映射表引用
- **产业景气/渗透率区间，引用 `mid-industry-research` 口径**
- **管理层 20 分制 / 科研转化 20 分制，引用 `mid-management-deep-dive` 与 V2.0 第二部分**

### PDF 文档内容提取（技术类文章）

文字与表格提取**首选** `tools/common/pdf_extract.py`（基于 pdf-inspector 库，支持自动乱码检测 + OCR 回退），返回失败时才回退 Poppler 工具集；**高清图像渲染提取配图仍需使用 Poppler `pdftoppm`**：

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `pdf_extract.py` | PDF文字与表格提取（首选） | `python tools/common/pdf_extract.py markdown 论文.pdf --save-md --out-dir reports/pdf` |
| `pdftoppm` | 高清图像渲染（配图，900 DPI 起步） | `pdftoppm -png -r 900 -f {页码} 论文.pdf output/page` |

详见 [PDF文档内容提取技能](../tools-scripts/pdf-extraction.md)。

### 网络搜索工具

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用本地五工具组合。完整角色定位、市场×场景选型矩阵、命令速查、多源验证示例见 [web-search-tools](../tools-scripts/web-search-tools.md)。

**公众号文章场景下的搜索选型**：
- A股主题：`anysearch --tag finance` 主 + `doubao --finance` 辅
- 港股主题：`doubao --sites hkexnews.hk` 主 + `tavily` 辅（双源 doubao+tavily）
- 美股/国际主题：`exa --type deep` 主 + `doubao` 辅（双源 exa+doubao）
- 技术主题：英文文献 `exa --type deep`，中文资讯 `doubao`，多源互补

**重要约束**：
- 使用 `--time-range month/week` 限制时间范围，优先获取最新信息
- 港股/美股/国际主题须按市场双源验证
- 关键信息缺失时标注"信息不足"，不得用推测填充

---

## 核心原则

1. **不虚构数据** — 引用的数据必须有来源，搜不到就标注"估计"
2. **不用AI腔调** — 禁止"让我们一起来看看"、"不得不说"等套话
3. **公式必须配大白话** — 每个公式后面都要有"翻译成人话就是……"
4. **配图必须实际插入** — 禁止用 `[图X]` 占位符
5. **结尾必须有传播力** — 最后一句话要值得被单独截图转发
6. **引用不重复定义** — 估值档位引用 `valuation-thermometer`，卖出纪律引用 `exit-signal`（P0~P5），产业景气/渗透率引用 `mid-industry-research`，管理层/科研转化 20 分制引用 V2.0 与 `mid-management-deep-dive`
7. **中期口径红线** — 禁止使用「护城河永续」「终局思维」「持有10年」「巴芒段李」等长期框架术语，持有周期以「景气周期长度」为准
8. **数据抽检准出** — 文章落盘后必须执行 `report_audit.py extract → verdict`，偏差 ≤1% 准出、>1% 打回

---

## 注意事项

- 禁止使用 WebSearch 和 WebFetch 工具（中国大陆地区不可用）
- 信息丰富度评级（A/B/C级）需告知每个研究 Agent，影响其分析深度
- **共识偏见**：搜索结果高度一致看多/看空时（A级信息），主动做反面检验
- **光环效应**：不能因公司名气/股价上涨而放松对管理层诚信、财务质量的核查
- **信息缺口诚实**：渗透率等数据缺乏官方统计时，标注为「估计」并给出区间，不虚构精确值
- 关键财务数据至少两个独立来源交叉验证，误差 >1% 须标记
- 报告发布前必须通过 `tools/common/report_audit.py` 数据抽检
- 编辑和读者都指出的问题必须改；两者矛盾时偏向读者
- 景气投资类文章：PEG 必须附计算依据和来源；卖出纪律必须与 `exit-signal` P0~P5 一致；林奇六类分类不能跳过；结论段对持有者、观望者分别给出操作指引
- 网络搜索须使用 `--time-range month/week` 限制时间范围，优先获取最新信息

---

## 局限性说明

- **网络信息获取限制**：网络搜索须使用本地五工具组合
- **图片生成质量**：AI生成的图片可能不符合预期
- **论文PDF可得性**：部分论文可能需要付费或无法下载
- **技术术语准确性**：非常专业的领域可能需要领域专家审核
- **时效性限制**：网络搜索结果可能有延迟
- **读者视角模拟局限**：Agent模拟的读者视角可能无法完全代表真实读者体验
- **景气数据可得性**：部分行业渗透率等数据缺乏官方统计，需按 A/B/C 三级置信度标注
- **数据工具延迟**：本地数据工具获取的数据可能有延迟，非实时数据
- 不构成投资建议，仅供学习研究参考

---

## 相关文档

- [SKILL.md](./SKILL.md) — 技能详细指令文件
- [公众号文章（长期版）](../wechat-article/README.md) — 长期链巴芒段李公众号文章，物理隔离不互用
- [财报精读团队（中期版）](../mid-earnings-team/README.md) — 财报精读团队 + 公众号发布
- [中期投研团队](../mid-investment-team/README.md) — 四 Agent 中期全面公司研究（文章研究底稿来源）
- [深度长文系列（中期版）](../mid-deep-company-series/README.md) — 拆一家公司的系列长文发布承接
- [估值温度计](../valuation-thermometer/README.md) — PEG五档温度（文章估值档位口径来源）
- [卖出信号](../exit-signal/README.md) — P0~P5 卖出纪律（文章卖出纪律口径来源）
- [中期行业研究](../mid-industry-research/README.md) — 产业景气/渗透率口径来源
- [中期管理层纵深](../mid-management-deep-dive/README.md) — 管理层/科研转化 20 分制口径来源
- [景气大师问答](../garp-ask/README.md) — 林奇主轴轻量问答，口径参考

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-09-08
- **维护状态**：活跃维护

---

## 免责声明

本技能仅供学习研究参考，不构成投资建议。投资有风险，入市需谨慎。
