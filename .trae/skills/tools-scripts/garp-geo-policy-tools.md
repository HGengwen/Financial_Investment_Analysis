---
name: garp-geo-policy-tools
description: "政策资本地缘三维矩阵与国产化率四档（geo-policy-screen）：GARP 框架第0步·0.3 三维交叉矩阵六行判定与赛道两分法（screen），第1步国产化率四档分层（localize）与半导体设备内置示例（examples），以及第0步实时来源快照检索（scan，不判档），禁止 LLM 心算。"
disable-model-invocation: true
---

# 政策-资本-地缘矩阵与国产化率四档（geo-policy-screen）

使用 `tools/specialized/geo_policy_screen.py` 将《中长期价值成长（GARP）投资框架》第 0 步·0.3「政策-资本-地缘三维交叉矩阵」与第 1 步「国产化率位置」下沉为可执行命令。

- **只判档/只检索，不定值**：三维档位与国产化率的「取值」是时变项（制裁清单/出口管制/基金名录/国产化率随环境变化），本工具**不固化数值**；实时核验由 `scan` 子命令承接（只检索来源快照，不判档）。
- **四子命令**：`screen`（三维矩阵判定 + 赛道两分法）、`localize`（国产化率四档分层）、`examples`（半导体设备四梯队示例）、`scan`（地缘风险 + 政策基金实时来源快照）。

---

## Python 环境

- **Python 路径**：`F:/Anaconda3/envs/Python_3_12_3/python.exe`
- **工作目录基准**：`F:/Financial_Investment_Analysis/`

---

## 子命令一：screen —— 三维交叉矩阵六行判定 + 赛道两分法

```bash
python tools/specialized/geo_policy_screen.py screen \
  --geo 高 --policy 高 --fund 有直接注资 \
  --as-of 2026-09-16 --basis "P3-3 scan 检索结果 + 政策/基金公告"
```

| 参数 | 取值 |
| --- | --- |
| `--geo`（必填） | 地缘倒逼强度：高/中/低 |
| `--policy`（必填） | 政策覆盖度：高/中/低 |
| `--fund`（必填） | 国字号基金介入：有直接注资/有专项子基金/有覆盖/无覆盖 |
| `--as-of` / `--basis` | 档位判定时点与依据（仅透传，不参与判定） |

**六行权威结论**（显式命中）：

| 行 | 组合（geo/policy/fund） | matrix_row | track_type |
| --- | --- | --- | --- |
| 1 | 高/高/有直接注资 | 最优场景 | 地缘倒逼型 |
| 2 | 高/中/有专项子基金 | 次优场景 | 地缘倒逼型 |
| 3 | 中/高/有覆盖 | 潜伏场景 | 地缘倒逼型 |
| 4 | 高/低/无覆盖 | 高风险/回避 | 地缘倒逼型 |
| 5 | 低/(中或高)/(有覆盖及以上) | 政策驱动型增量创造 | 政策资本驱动型 |
| 6 | 低/低/无覆盖 | 回避 | 回避 |

**未列组合归档**：凡未显式列入六行的合法组合，一律按 `FALLBACK_MAP` 归档到「更审慎相邻档」，`archived=true`、`archive_from` 回显原组合，不默认放行。共 3×3×4=36 组合全覆盖（导入时自检）。

**输出（JSON）**：`row_index` / `matrix_row` / `conclusion` / `track_type` / `archived` / `archive_from` / `risk_note` / `time_sensitive` / `time_sensitivity_note` / `source` / `input`。

---

## 子命令二：localize —— 国产化率四档分层

```bash
python tools/specialized/geo_policy_screen.py localize \
  --industry 量测检测 --localization-rate 12.5 --as-of 2026-09-16

# 战略卡脖子环节例外（仅 rate<5 生效）
python tools/specialized/geo_policy_screen.py localize \
  --industry 光刻设备 --localization-rate 0.8 --strategic-choke-point
```

**四档判定（判定只依赖数值，不依赖行业名，天然支持任意行业）**：

| 档 | 区间 | phase | action_hint |
| --- | --- | --- | --- |
| 1 过早 | <5 | 不确定性高 | 观察不建仓 |
| 2 突破期 | [5,20) | 从0到1突破期 | 高弹性，跟踪/小仓 |
| 3 加速投资期 | [20,50) | 加速投资期 | 订单放量 |
| 4 替代空间收窄 | [50,100] | 替代空间收窄 | 转向龙头份额提升与整机放量 |

- `--strategic-choke-point`：仅 `rate<5` 时覆盖 action_hint 为「战略必争卡脖子环节，仅观察/小仓、不重仓（非回避）」。
- `--localization-rate`：0~100 百分数（可为 int/float），越界拒绝。

**输出（JSON）**：`industry` / `localization_rate_pct` / `tier` / `tier_index` / `phase` / `action_hint` / `strategic_choke_point` / `choke_point_applied` / `time_sensitive` / `time_sensitivity_note` / `source` / `input`。

---

## 子命令三：examples —— 半导体设备四梯队内置示例（回归锚点）

```bash
python tools/specialized/geo_policy_screen.py examples
```

内置框架第 1 步半导体设备示例（第一/二/三梯队 + 光刻），仅作格式回归锚点；判定逻辑不写死半导体，任意行业经 `localize` 按数值落档。

---

## 子命令四：scan —— 地缘风险 + 政策基金实时来源快照（不判档）

> **已修复（P23-A4，2026-09-19 登记 → P5-2 §4.5 修复）**：`scan` 子命令此前**仅支持 `python -m tools.specialized.geo_policy_screen` 模块调用形态**；直接 `python tools/specialized/geo_policy_screen.py` 会因 `_build_default_search_inject` 的导入路径问题触发 `ModuleNotFoundError`。修复方式：模块顶部注入项目根到 `sys.path`（与 `tools/a_share/stock_quote.py` 同款写法）。**两种形态现均可用**（2026-09-19 实测退出码 0）。

```bash
# 以下四条现均可用（实测 2026-09-19 退出码 0）
python tools/specialized/geo_policy_screen.py scan --industry 半导体
python -m tools.specialized.geo_policy_screen scan --industry 半导体
python -m tools.specialized.geo_policy_screen scan --fund 半导体设备
python -m tools.specialized.geo_policy_screen scan --industry 半导体 --fund 半导体设备
```

| 参数 | 说明 |
| --- | --- |
| `--industry` | 地缘风险维度检索对象（行业/领域名） |
| `--fund` | 政策基金维度检索对象（行业/领域/基金名） |

- 二者至少填一个、可同时填。
- 检索编排：anysearch → doubao_search →（仅地缘维度）exa_search；实时全失败时回退 `data/geo_policy/` 旧缓存（TTL 24h），再失败标注降级。

**输出（JSON）强制字段**：`data_as_of`（数据截止日期）、`retrieved_at`（检索执行时间）、`snapshot_example`（来源快照示例）、`degraded`（降级标注）、`disclaimer`/`note`（不写硬结论 + 框架示例非当前事实免责声明）。

> `scan` 只检索、只呈现来源快照，**不判定风险等级/基金力度、不输出 screen 档位结论**。

---

## 渗透率取数来源与口径基准（P23-A1 登记）

**当前无独立 CLI 出口**：框架「渗透率」指标目前**无专用命令行工具取数**，须**按来源人工核验**，禁止 LLM 心算或凭印象填写。

| 项 | 口径基准（框架） | 取数来源建议 | 说明 |
| --- | --- | --- | --- |
| 渗透率五档 | 关键区间 `15%` 至 `40%`，且市场 **TAM 不低于 1000 亿** 为基本盘门槛 | 行业研报 / 券商深度 / `anysearch` / `doubao_search` | **无独立 CLI 出口**，须人工核验并**标注来源日期** |
| 国产化率四档 | `<5` / `[5,20)` / `[20,50)` / `[50,100]` | `localize` 子命令（本工具） | 通过 `--localization-rate` 数值落档 |

> **硬约束**：渗透率与国产化率均为**时变数据**，结论仅对数据截止日期有效；报告中必须标注「数据截止日期 + 来源 + 参数基准」，不得以过期值断言当前档位。国产化率落档走 `localize`，渗透率走人工核验加标注。

---

## 与 trend_tech_screen 的差异标注（P23-A2 登记）

`trend_tech_screen.py` 当前地缘维度为 **二维（政策 + 资本）**，而本工具 `screen` 为 **0.3 矩阵三维（地缘 + 政策 + 资本）**，两者**口径不同源**：

- `trend_tech_screen.py`：地缘修正仍为二维，用于景气趋势筛选初筛。
- `garp-geo-policy-tools`（本文件）：0.3 矩阵三维入档，用于 GARP 第 0 步。

> **维度差异**：三维多一维「地缘倒逼强度」。三维扩展（`trend_tech_screen.py` 地缘三维化）**未实施**（原指 P5-2 / P5-3，两任务均已收口且未承接）；本文件**不改签名、只标注差异**。GARP 流程的地缘核验以本文件 `screen` 三维为准。

---

## 输入校验（非法即非零退出）

- `screen`：三档位须在合法词表内（geo 高/中/低，policy 高/中/低，fund 四档），非法即报错退出。
- `localize`：`--industry` 非空、`--localization-rate` 0~100。
- `scan`：`--industry`/`--fund` 须至少一非空字符串。

---

## 相关参考

- [公共工具索引](./common-tools-guide.md)
- [治理数据评分工具](./garp-governance-tools.md)（五大支柱三/四联动消费方）
- [GARP 估值计算核心](./garp-valuation-tools.md)（地缘档位进估值结论的消费方）

---

## 版本信息

- **版本**：1.2.1（2026-09-19 收口订正：L138「三维扩展转 P5-2 / P5-3」订正为**未实施**；1.2.0 为 P5-2 §4.5 修复 A4、补 P23-A1 / A2 与 `screen`/`localize` 输出字段）
- **创建日期**：2026-09-16
- **更新日期**：2026-09-19