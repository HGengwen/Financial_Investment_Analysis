# Sprint 0 详细开发方案与实施计划

> **文档版本**：v1.0 | **创建日期**：2026-08-29 | **状态**：待确认
>
> **依据**：《1~3 年中长期投研系统完整开发方案与详细实施计划.md》第八节「Sprint 0：盘点与验证」。
>
> **基线核实**：撰写前已逐项核对当前代码库真实实现，发现与方案文档表述存在差异，详见下文「基线核实结果」。

## 〇、基线核实结果（影响 Sprint 0 任务范围）

| 文档表述 | 实际状态 | 对 Sprint 0 的影响 |
| --- | --- | --- |
| 任务 4「存量技能重命名（F-7，已完成）」 | 目录与技能自指**已完成**（`.trae/skills/` 下已是 `mid-trend-tech-screen`，SKILL.md `name` 字段、README 均为新名） | 重命名动作无需重做，**剩余工作 = 全量引用同步收尾** |
| 「同步更新全部引用」 | **未完成**，仍残留旧名 `trend-tech-screen` | Sprint 0 任务 4 的主体 |
| 报告目录创建 | `reports/valuation/`、`reports/exit-signals/` 均**不存在** | 需新建 |
| 估值命令「已全部内置」 | 已确认 `financial_rigor.py` 内置 10 个子命令 | 仅需实测记录 |
| 历史文档盘点 | `research/quality-screen/` 下 3 份文档均在 | 需通读产出三清单 |

**残留旧名引用清单**（Grep 已定位，需逐处甄别「技能名」vs「工具参考文档名」）：

- `.trae/skills/证券AI价值投资研究工作步骤.md` —— 约 12 处：L121/122/123/124、L244、L449/451、L850、L864/867、L903、L927
- `docs/A股工具使用指南.md` —— L248、L620
- `docs/港股工具使用指南.md` —— L330（L336 为指向工具参考文档的链接，保留）
- `docs/美股工具使用指南.md` —— L247
- `.trae/skills/tools-scripts/a-share-data.md` —— L43、L55

## 一、定位与目标

Sprint 0 是「零开发前提落地确认 + 基线就位」的前置冲刺，**不新增任何技能文件、不写任何 Python 代码**。目标是把后续 6 个 Sprint 的全部前置条件一次性做实：

1. 证明所有估值命令可用、参数与输出真实可复现（后续 `valuation-thermometer` / `exit-signal` 的直接依赖）；
2. 消化 3 份历史开发文档，避免 Sprint 1~3 重复设计；
3. 建好报告输出目录；
4. 完成 `trend-tech-screen` → `mid-trend-tech-screen` 的**引用同步收尾**（目录已重命名，剩文档引用）；
5. 建立全绿测试基线。

**工作量：1 天。**

## 二、前置条件

- Python 路径：`F:/Anaconda3/envs/Python_3_12_3/python.exe`（命令行示例中简写为 `python`）
- 环境依赖已安装（`pytest`、akshare、yfinance 等，见 `requirements.txt`）
- 开始前运行 `date` 确认当天日期，供产出物日期标注使用

## 三、任务分解（5 项，按依赖顺序）

### 任务 1：估值命令可用性验证（F-2 零开发确认）

**目标**：逐条实测 7 个命令，记录真实参数签名与输出结构，并用手工可算样本校准。

**子步骤**：

1. 对以下命令逐条执行 `--help`，记录参数签名：
   - `python tools/common/financial_rigor.py peg --help`
   - `python tools/common/financial_rigor.py ps-g --help`
   - `python tools/common/financial_rigor.py pe-percentile --help`
   - `python tools/common/financial_rigor.py implied-growth --help`
   - `python tools/common/financial_rigor.py verify-valuation --help`
   - `python tools/common/financial_rigor.py three-scenario --help`
   - `python tools/common/financial_rigor.py cross-validate --help`
   - （顺带记录同文件其余 3 个命令 `verify-market-cap`、`benford`、`calc` 的签名）
2. 用手工可算样本实测并比对：

| 命令 | 构造输入 | 预期输出 |
| --- | --- | --- |
| `peg` | `--pe 25 --growth 20` | PEG = 1.25（=25/20），档位「偏贵」 |
| `ps-g` | `--ps 5 --revenue-growth 30` | PSG ≈ 0.167 |
| `pe-percentile` | 构造 PE 序列，当前值取序列最小值 | 百分位 ≈ 0% |
| `implied-growth` | 构造市值/净利率/TTM营收/指引增速 | 输出红/黄/绿三态判定 |
| `three-scenario` | 构造悲观/中性/乐观参数 | 输出三情景估值 |
| `verify-valuation` | 构造 PE/市值/净利 | 输出校验结果 |
| `cross-validate` | 构造两来源数据 | 输出误差与标记 |

3. 将实测结果整理为「估值命令实测记录」（命令 + 参数签名 + 输出样例 + 手工校准对照），作为后续 `valuation-thermometer` 写命令模板的唯一依据。

**验收**：7 个命令全部可运行；`peg --pe 25 --growth 20` 输出与手工计算 1.25 一致；记录中无 LLM 心算数值。

### 任务 2：历史开发文档盘点（F-12）

**目标**：通读 `research/quality-screen/` 下 3 份文档，产出「三清单」。

**子步骤**：

1. 通读并摘录要点：
   - `research/quality-screen/trend-tech-screen.md技能文件完整修改建议.md`
   - `research/quality-screen/trend-tech-screen工具链开发方案.md`
   - `research/quality-screen/在研重大项目信息获取方法的整合与强化.md`
2. 产出三清单（写入盘点记录）：
   - **已被代码覆盖项**：文档结论已落地到 `mid-trend-tech-screen` SKILL.md / `trend_tech_screen.py` / `in_research_scan.py` 的内容；
   - **可复用设计结论**：尚未直接落地、但 Sprint 1~3 可直接引用的设计（阈值表、评分卡、信号分级等）；
   - **待吸收但尚未实现项**：需在 Sprint 1~3 补齐的缺口。

**验收**：三清单完整，每条注明「来源文档 + 结论 + 去向（已覆盖/待引用/待实现）」。

### 任务 3：报告目录创建

**子步骤**：

```powershell
New-Item -ItemType Directory -Force -Path reports/valuation, reports/exit-signals | Out-Null
```

**验收**：`reports/valuation/`、`reports/exit-signals/` 均存在。

### 任务 4：存量技能重命名收尾（F-7 引用同步，主体工作）

> 目录与 SKILL.md/README.md 自指已完成，本任务聚焦**残留旧名引用的甄别与同步**。

**子步骤**：

1. **git 状态核查**：`git status` + `git log --oneline -3`，确认重命名是否已提交；若未提交，先单独提交重命名（目录变更），再提交引用同步（内容变更），保持提交可回溯。
2. **甄别规则**（逐处判定，不得无脑全局替换）：
   - 引用**技能**（命令 `/trend-tech-screen`、导航/路由、技能表）→ 改为 `mid-trend-tech-screen`；
   - 引用**工具** `trend_tech_screen.py` 或**工具参考文档** `tools-scripts/trend-tech-screen.md` → **保留原名**。
3. **逐文件同步**（按上表残留清单）：
   - `.trae/skills/证券AI价值投资研究工作步骤.md` L121/122/123/124、L244、L449/451、L850、L864/867、L903、L927 —— 全部为技能引用，改为 `mid-trend-tech-screen`；
   - docs 三市场指南中的「trend-tech-screen 阶段一/三」—— 属技能流程阶段标注，改为 `mid-trend-tech-screen`；指向 `tools-scripts/trend-tech-screen.md` 的链接保留；
   - `.trae/skills/tools-scripts/a-share-data.md` L43、L55 —— 同改为 `mid-trend-tech-screen`。
4. **不修改项确认**：`tools/specialized/trend_tech_screen.py`、`tools-scripts/trend-tech-screen.md`、`tests/specialized/test_trend_tech_screen.py` 保留原名。
5. **全库复扫**：`Grep "trend-tech-screen"` 复核，剩余命中应**仅**为工具/参考文档/测试/本方案文档本身。

**验收**：复扫后技能引用 0 残留；工具与参考文档原名完好。

### 任务 5：测试基线确认

**子步骤**：

1. 全量运行 `pytest`（在工作区根目录）。
2. 记录结果；若有失败，区分「重命名引发」与「既有失败」：重命名引发 → 修复引用；既有失败 → 记录并标注，不阻断 Sprint 0（除非与本次变更相关）。

**验收**：`pytest` 全绿，或仅剩与本次变更无关的既有失败（须显式列出）。

## 四、产出物清单

1. 估值命令实测记录（含参数签名 + 手工校准对照）
2. 历史文档盘点三清单
3. `reports/valuation/`、`reports/exit-signals/` 目录
4. 重命名引用同步提交（git）
5. `pytest` 基线结果

## 五、退出条件（DoD）

- 全部 7 个估值命令实测通过，且与手工计算一致；
- 盘点三清单完成；
- 两个报告目录存在；
- 全库复扫 `trend-tech-screen` 无技能引用残留（工具/参考文档/测试除外）；
- `pytest` 全绿；
- `git status` 无未跟踪的旧技能目录。

## 六、风险与注意点

| 风险 | 应对 |
| --- | --- |
| 引用同步误伤工具名 | 严格按「技能→改 / 工具、参考文档→保留」甄别规则，逐处判定，改后全库复扫 |
| 重命名未提交导致提交混杂 | 先核查 git 状态，目录变更与内容变更分两次提交 |
| 港股/美股数据源网络不稳 | 任务 1 估值命令不依赖网络行情，仅用构造样本，规避该风险 |
| 估值命令实参与文档预期不符 | 以实测 `--help` 签名 + 手工校准为准，如实记录偏差，回写至 Sprint 1 命令模板 |
