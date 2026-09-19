# Phase 3 完成门禁报告（地缘政策与治理数据）

- **Phase**：Phase 3 地缘政策与治理数据（P3-1 ~ P3-7，共 7 个子任务）
- **依据**：《GARP升级-软件与技能升级详细计划》§0.6「每个 Phase 完成后文档与技能同步（刚性）」
- **报告日期**：2026-09-16

---

## 0. 结论摘要（TL;DR）

- **全量回归**：`pytest -q` 全仓 **1457 passed, 62 skipped**，无 failed / error。
- **Phase 3 触及工具**：2 个新增专用工具（`geo_policy_screen.py`、`governance_data.py`）+ 1 个既有工具扩展（`annual_report_parser.py` 治理字段）。
- **文档与技能同步**：`docs/` 三指南各 **1 行**增量（`annual_report_parser.py` 功能列追加「治理」）；`.trae/skills/tools-scripts/` **新增 2 份** GARP 工具参考 md（`garp-geo-policy-tools.md`、`garp-governance-tools.md`）+ 更新 2 份（`annual-report-parser.md`、`common-tools-guide.md`）。
- **边界合规**：GARP 专用新增工具（`geo_policy_screen.py` / `governance_data.py`）**未写入** `docs/` 三指南，按总计划 4.3 边界由 `tools-scripts/` 承载。

---

## 1. 全量回归测试结果

```text
F:/Anaconda3/envs/Python_3_12_3/python.exe -m pytest -q
1457 passed, 62 skipped, 100 warnings in 1006.83s (0:16:46)
```

- 全仓 **1457 passed / 62 skipped / 0 failed / 0 error**。
- 62 项 skip 为既有网络依赖测试（akshare / yfinance 等）在受限网络下的既有跳过逻辑，非本 Phase 引入。
- 进程退出码 1 系沙箱对 `py-yfinance` 缓存文件（`cookies.db-shm`/`tkr-tz.db-shm`）的写入限制所致，与测试结果无关。

**Phase 3 相关测试单独复跑**：

```text
F:/Anaconda3/envs/Python_3_12_3/python.exe -m pytest \
  tests/specialized/test_geo_policy_screen.py \
  tests/specialized/test_governance_data.py \
  tests/common/test_annual_report_parser.py -q
225 passed in 2.82s
```

| 测试文件 | 覆盖任务 | 用例数 |
| --- | --- | --- |
| `tests/specialized/test_geo_policy_screen.py` | P3-1 / P3-2 / P3-3 | （含） |
| `tests/specialized/test_governance_data.py` | P3-4 / P3-5 / P3-6 | 113 |
| `tests/common/test_annual_report_parser.py` | P3-7 | 53 |
| **合计** | — | **225** |

---

## 2. Phase 3 触及的工具清单

| 任务 | 工具文件 | 工具命令 | 改动性质 |
| --- | --- | --- | --- |
| P3-1 | `tools/specialized/geo_policy_screen.py` | `screen` | 新建 |
| P3-2 | 同上 | `localize` / `examples` | 新建 |
| P3-3 | 同上 | `scan` | 新建 |
| P3-4 | `tools/specialized/governance_data.py` | `management` | 新建 |
| P3-5 | 同上 | `research` | 新建 |
| P3-6 | 同上 | `esg` | 新建 |
| P3-7 | `tools/common/annual_report_parser.py` | 顶层 `governance` 字段组 | 扩展（不改既有 6 类字段与函数签名） |

---

## 3. 文档与技能同步清单（含 diff 摘要）

### 3.1 `docs/` 三份工具使用指南（最小同步）

| 文件 | 同步内容 | diff 摘要 |
| --- | --- | --- |
| `docs/A股工具使用指南.md` | `annual_report_parser.py` 功能列追加「治理」 | `1 行`：`（员工/子公司/研发/收入分部/新品/供应链）` → `（员工/子公司/研发/收入分部/新品/供应链/治理）` |
| `docs/港股工具使用指南.md` | 同上 | `1 行`，同上 |
| `docs/美股工具使用指南.md` | 同上 | `1 行`，同上 |

> **说明**：P3-7 是 Phase 3 中唯一触及「已登记于三指南的工具」的任务。P3-1~P3-6 的 GARP 专用工具按总计划 4.3 边界**不写入三指南**（见 §4）。
>
> **变更归属澄清**：`docs/A股工具使用指南.md` 工作区累计 diff 为 57 行、港股/美股各 15 行，其中**仅 `@@ -34 +34 @@`（港股 -26、美股 -23）为本 Phase 3 增量**；其余为 Phase 1 遗留未提交变更（`--momentum` 的 `atr14`、`financial_rigor.py` 7 子命令登记等），不属本次 Phase 3 同步范围，不越权改动。

### 3.2 `.trae/skills/tools-scripts/` 工具技能参考

| 文件 | 改动性质 | diff 摘要 |
| --- | --- | --- |
| `garp-geo-policy-tools.md` | **新建** | 承载 `geo_policy_screen.py` 四子命令（`screen` 六行矩阵+赛道两分法 / `localize` 国产化率四档 / `examples` 半导体示例 / `scan` 实时来源快照不判档）的参数、结论表、输出字段与校验说明 |
| `garp-governance-tools.md` | **新建** | 承载 `governance_data.py` 三子命令（`management` 诚信前置+7+7+6 / `research` 8+8+4 / `esg` 三通道折价）的参数表、计分规则、输出字段与校验说明 |
| `annual-report-parser.md` | **更新** | `description` 补治理字段；「六大块」→「七大块」并新增 `governance` 行 + 「只抽事实不判档」边界注；版本 `1.0.0 → 1.1.0`，更新日期 `2026-08-25 → 2026-09-16` |
| `common-tools-guide.md` | **更新** | 索引新增 `garp-geo-policy-tools.md`、`garp-governance-tools.md` 两行；`annual-report-parser` 行功能列补「治理」；版本 `2.4.0 → 2.5.0`，更新日期 `2026-09-15 → 2026-09-16` |

> **未改动**：`financial-calc.md`（Phase 1 已登记 7 子命令，本 Phase 未新增计算核心）、`terminal-value.md`、`trend-tech-screen.md`、`web-search-tools.md`、`report-audit.md`、`global-constraints.md`、`pdf-extraction.md`、`a-share-data.md`、`hk-share-data.md`、`in-research-scan.md`、`garp-macro-tools.md`（Phase 2 已交付）等均**未越权改动**。

---

## 4. 边界合规声明

| 项 | 结论 |
| --- | --- |
| GARP 专用新增工具是否写入 `docs/` 三指南 | **否**（`geo_policy_screen.py`、`governance_data.py`、`macro_calibrator.py` 均按总计划 4.3 边界由 `tools-scripts/` 承载） |
| 是否越权改动非本 Phase 触及的指南条目 | **否**（三指南仅改 `annual_report_parser.py` 功能列 1 行；Phase 1 遗留变更保持原样未触碰） |
| 是否改动既有 43 技能 | **否**（Phase 3 全部子任务均未触碰 `.trae/skills/` 下技能文件） |
| 是否改动既有工具签名 | **否**（`annual_report_parser.py` 仅新增顶层 `governance` 字段，既有 6 类字段与函数签名不变） |

---

## 5. Phase 3 七个子任务完成状态

| 任务 | 标题 | 状态 |
| --- | --- | --- |
| P3-1 | `geo_policy_screen.py`（0.3 三维交叉矩阵 + 赛道两分法） | ✅ 完成门禁已通过 |
| P3-2 | `geo_policy_screen.py` 国产化率四梯队分层量化 | ✅ 完成门禁已通过 |
| P3-3 | `geo_policy_screen.py scan` 子命令 | ✅ 完成门禁已通过 |
| P3-4 | `governance_data.py`（管理层 20 分制：诚信前置 + 7+7+6） | ✅ 完成门禁已通过 |
| P3-5 | `governance_data.py` 科研转化 20 分制（8+8+4） | ✅ 完成门禁已通过 |
| P3-6 | `governance_data.py` ESG 环境风险折价 | ✅ 完成门禁已通过 |
| P3-7 | `annual_report_parser.py` 扩展治理字段 | ✅ 完成门禁已通过 |

---

## 6. 待用户确认

请确认 Phase 3 是否**收口通过**：
1. 全量回归 `1457 passed / 62 skipped` 无回归；
2. `docs/` 三指南最小同步（各 1 行）合规；
3. `tools-scripts/` 新增 2 份 + 更新 2 份 GARP 工具参考，GARP 专用工具未越权写入三指南。

确认通过后，方可流转至 Phase 4（P4-1 `garp-geo-policy` 技能）。