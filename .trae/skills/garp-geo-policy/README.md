# GARP 第0步前置：地缘政治与政策资本判定 (Garp-Geo-Policy)

对指定行业/公司执行 GARP 框架第0步前置判定：地缘倒逼强度 + 政策资本覆盖度 → 政策-资本-地缘三维交叉矩阵 + 赛道两分法 + 国产化率四档 → 收口为「放行 / 观察 / 回避（一票否决）」三档前置闸门结论。

> 本技能属 **GARP 独立档（1~5 年，五大师：费雪 / 林奇 / 郑希 / 李进 / 欧奈尔）**，与 1~3 年中期链、10 年长期链**物理隔离、功能互补**。核心理念：**地缘政治倒逼决定国产替代的"确定性下限"，政策与国字号基金支持决定"国产企业能不能接得住"——两者缺一，赛道都走不通**。本技能只做赛道级前置闸门，档位判定一律由工具产出，禁止 AI 心算。

---

## 快速开始

### 基本调用方式

```
/garp-geo-policy {行业/公司} [可选参数]
```

例如：

- `/garp-geo-policy 半导体设备`
- `/garp-geo-policy 量测检测 --localization-rate 12.5`
- `/garp-geo-policy 中芯国际`（填公司时先定位所属赛道/环节，再按赛道判定）
- `/garp-geo-policy 稀土 --depth fast`

### 可选参数

| 参数 | 说明 | 默认 |
| --- | --- | --- |
| `--depth` | `standard`（含实时检索核验 + 搜索五工具）/ `fast`（跳过实时检索，仅用既有信息） | `standard` |
| `--geo` / `--policy` / `--fund` | 用户已判定的三维档位，填则直接进入矩阵判定（实时检索失败时的降级通道） | 无 |
| `--localization-rate` | 国产化率百分数（0~100，科技赛道可选） | 无 |
| `--strategic-choke-point` | 战略卡脖子环节标记，**仅用户显式指定**时使用 | 关闭 |

---

## 核心功能

把 GARP 框架**第0步（0.1 / 0.2 / 0.3）**与**第1步国产化率四档**下沉为一条可执行流程，六步完成：

1. **确认参数与数据基准** — 运行 `date` 确认当天日期，作为「数据截止日期」；填公司时先定位赛道/环节并写出依据
2. **0.1 地缘倒逼强度** — 逆全球化四类信号渗透 → 三种风险形态传导链定位 → 四项评估（制裁覆盖度 / 断供现实性 / 政策强制力 / 制裁可持续性）→ `geo` 档位（高/中/低）
3. **0.2 政策与国字号基金支持强度** — 规划政策 / 基金资本 / 时效核验三层面 → `policy` 档位（高/中/低）+ `fund` 档位（有直接注资 / 有专项子基金 / 有覆盖 / 无覆盖）
4. **0.3 三维交叉矩阵（工具判定）** — 调 `geo_policy_screen.py screen` 输出矩阵行 / 结论 / 赛道类型 / 归档标记
5. **国产化率四档分层（工具判定）** — 调 `geo_policy_screen.py localize` 输出档位 / 阶段 / 行动提示
6. **收口输出与下游转接** — 前置闸门三档结论 + 数据基准 + 时变警示 + 转接指引

### 三维交叉矩阵与赛道两分法

| 矩阵行 | 前置结论 | 处置 |
| --- | --- | --- |
| 1 最优场景 / 2 次优场景 | **放行** | 进入下游细研 |
| 3 潜伏场景 | **观察** | 提前布局等待催化，不建仓，纳入跟踪 |
| 4 高风险/回避 | **回避（一票否决）** | 政策+资本两维同时失守；另附「须先验证国产承接能力」的重估路径 |
| 5 政策驱动型增量创造 | **放行** | 不以地缘倒逼为门槛，达标与否交支柱五 |
| 6 回避 | **回避（一票否决）** | 政策+资本两维同时失守，纯市场驱动不确定性过高 |

赛道两分法（由矩阵行自动判定）：

| 赛道类型 | 对支柱四（地缘政治与外部环境）的门槛 |
| --- | --- |
| **地缘倒逼型** | **硬门槛**：地缘倒逼强度非「低/无」方可建仓；同时以支柱五验证政策资本能否接住 |
| **政策资本驱动型** | **仅敞口体检**：海外收入 / 供应链 / 地区冲突暴露可控即可，达标与否交支柱五 |

### 国产化率四档

| 档 | 区间（%） | phase | action_hint |
| --- | --- | --- | --- |
| 1 过早 | <5 | 不确定性高 | 观察不建仓 |
| 2 突破期 | [5,20) | 从0到1突破期 | 高弹性，跟踪/小仓 |
| 3 加速投资期 | [20,50) | 加速投资期 | 订单放量 |
| 4 替代空间收窄 | [50,100] | 替代空间收窄 | 转向龙头份额提升与整机放量 |

> 战略卡脖子例外：`<5%` 中若属战略必争卡脖子环节（如光刻），可作高风险高弹性的观察/小仓、非回避（`--strategic-choke-point`，仅用户显式指定时使用）。

---

## 使用示例

### 示例 1：行业级前置判定

```
/garp-geo-policy 半导体设备
```

产出：`reports/半导体设备/半导体设备-garp-geo-20260916.md`，含 0.1 证据链、0.2 证据链、矩阵判定（行 1 最优场景 · 地缘倒逼型）、国产化率分层、前置结论「放行」。

### 示例 2：指定国产化率数值

```
/garp-geo-policy 量测检测 --localization-rate 12.5
```

产出：国产化率落第 2 档「从0到1突破期」·高弹性，跟踪/小仓。

### 示例 3：公司输入（先定位赛道）

```
/garp-geo-policy 中芯国际
```

产出：先定位「中芯国际 → 晶圆代工 / 半导体制造环节」并写出定位依据，再按该赛道做第0步前置判定；**不做**个股级支柱四/五细研（转 `garp-investment-checklist`）。

### 示例 4：降级模式

```
/garp-geo-policy 稀土 --depth fast --geo 高 --policy 高 --fund 有直接注资
```

产出：跳过实时检索，直接用用户提供的档位调 `screen`；报告中注明「档位由用户提供，未做实时核验」。

---

## 依赖

### 本地判定工具（核心）

| 子命令 | 用途 | 命令示例 |
| --- | --- | --- |
| `screen` | 三维交叉矩阵六行判定 + 赛道两分法 | `python tools/specialized/geo_policy_screen.py screen --geo 高 --policy 高 --fund 有直接注资 --as-of 2026-09-16 --basis "scan 检索结果 + 政策公告"` |
| `localize` | 国产化率四档分层 | `python tools/specialized/geo_policy_screen.py localize --industry 量测检测 --localization-rate 12.5 --as-of 2026-09-16` |
| `examples` | 半导体设备四梯队内置示例（回归锚点） | `python tools/specialized/geo_policy_screen.py examples` |
| `scan` | 地缘风险 + 政策基金实时来源快照（只检索、不判档） | `python -m tools.specialized.geo_policy_screen scan --industry 半导体 --fund 半导体设备` |

> **调用形式提示**：`screen` / `localize` / `examples` 可直接以脚本形式调用；**`scan` 必须用 `-m` 模块形式**，脚本形式会抛 `ModuleNotFoundError: No module named 'tools'`（`tools` 包不在 `sys.path`）。

详细字段说明与输入校验见 [garp-geo-policy-tools.md](../tools-scripts/garp-geo-policy-tools.md)。

### 网络搜索工具（档位判定依据）

| 优先级 | 工具 | 用途 | 命令示例 |
| --- | --- | --- | --- |
| 1 | `scan`（本地编排） | 地缘风险 + 政策基金结构化检索与快照 | `python -m tools.specialized.geo_policy_screen scan --industry {行业}` |
| 2 | `anysearch` | A股投研首选（垂直库），政策文本 / 公告 / 制裁清单深查 | `python tools/common/anysearch.py "{关键词}" --count 10 --zone cn` |
| 3 | `doubao_search` | 实时资讯/舆情（政策发布、基金设立动态） | `python tools/common/doubao_search.py "{关键词}" --finance` |
| 4 | `tavily_search` | 港美股深度内容辅源 | `python tools/common/tavily_search.py "{关键词}"` |
| 5 | `exa_search` | SEC filings 原文（美股标的的地缘披露） | `python tools/common/exa_search.py "{关键词}" --type deep` |
| 6 | `web_search` | 兜底（仅轻量验证） | `python tools/common/web_search.py "{关键词}"` |

**Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`｜**工作目录基准**：`F:/Financial_Investment_Analysis/`

禁止使用 Anthropic 官方 WebSearch/WebFetch（中国大陆不可用），统一使用上述本地搜索工具组合，选型细节见 [web-search-tools.md](../tools-scripts/web-search-tools.md)。

---

## 强制纪律

1. **工具判定，禁止心算** — 三维矩阵行与国产化率档位一律由 `geo_policy_screen.py` 产出，禁止自行推导
2. **数据截止日期必填** — 制裁清单、政策文本、基金名录、国产化率数值均为时变项，报告未标数据截止日期即不合格
3. **未列组合不解释性放行** — 归档组合（`archived=true`）原样呈现归档目标与原组合，不做"实际上应该更好"的补充判断
4. **降级必须如实标注** — `scan` 返回 `degraded=true` 时须写明降级原因与替代来源，并提示以实时检索复核
5. **政策基金三层架构仅作格式示范** — 保留「示例」标注与免责声明，禁止表述为"当前基金布局"
6. **公司输入先定位赛道** — 不定位到具体赛道/环节不得判定，定位依据须可追溯

---

## 核心原则

1. **先检索、后判定** — 不得因"该行业看起来不像地缘敏感行业"就跳过检索；风险行业边界持续外扩
2. **四信号 / 三形态 / 四评估是检查项不是打分表** — 输出逐项依据与档位结论，不产出"地缘风险得分"
3. **引用不重复定义** — 矩阵与国产化率引用工具；个股级支柱四/五引用下游技能；卖出引用 `garp-exit`
4. **不越界** — 不做个股细研、不做估值、不做宏观校准、不判定渗透率
5. **引用不重建** — 精确算术交 `financial_rigor.py`，报告准出交 `report_audit.py`（禁 LLM 心算）
6. **不替用户做决策** — 给出前置结论与转接指引，买卖决策由用户判断

---

## 适用与不适用

| 类型 | 场景 |
| --- | --- |
| **适用** | ① 新赛道/新环节首次前置筛查；② 制裁、出口管制、政策、基金注资等事件后的复检；③ 行业级前置判定（为 `garp-industry-research` / `garp-industry-funnel` / `garp-trend-tech-screen` 提供第0步输入）；④ 股价异动归因中的地缘政策信号核验（由 `garp-news-pulse` 反向调用） |
| **不适用** | 个股深度研究（`garp-investment-research` / `garp-investment-team`）、买入前门槛检查（`garp-investment-checklist`）、估值（`garp-valuation`）、宏观校准（`garp-macro`）、财报解读（`garp-earnings-review` / `garp-earnings-team`）、卖出纪律（`garp-exit`） |

---

## 与其他 garp- 技能的关系

| 关系 | 技能 | 说明 |
| --- | --- | --- |
| 后置（联动） | `garp-investment-checklist` | 前置结论「放行 / 观察」后进入买入前门槛检查 |
| 后置（联动） | `garp-valuation` | 通过门槛后进行多工具估值矩阵 |
| 后置（联动） | `garp-industry-research` | 行业级研究时作为第0步输入 |
| 后置（联动） | `garp-industry-funnel` | 漏斗筛选时的地缘政策初筛 |
| 后置（联动） | `garp-trend-tech-screen` | 景气趋势打分的地缘修正口径 |
| 后置（联动） | `garp-bottleneck-hunter` | 供应链瓶颈分层叠加国产化率与三维矩阵 |
| 后置（联动） | `garp-macro` | 宏观环境校准（并行，互不替代） |
| 反向调用 | `garp-news-pulse` | 股价异动归因中的地缘政策信号核验 |
| 同级（隔离） | 1~3 年中期链、10 年长期链 | 口径物理隔离，报告文件使用 `-garp-geo-` 前缀区分 |

---

## 版本信息

- **版本**：1.0.0（新建，GARP 独立档 Phase 4 P4-1）
- **适用口径**：1~5 年 GARP 独立档（五大师）
- **依赖工具**：`tools/specialized/geo_policy_screen.py`（screen / localize / examples / scan）+ 搜索五工具
- **创建日期**：2026-09-16
- **更新日期**：2026-09-16
