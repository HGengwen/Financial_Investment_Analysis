# A股财报下载与提取统一缓存方案（report_hub）

> 状态：待确认（2026-08-15）
> 新增文件：`tools/common/report_hub.py`（统一入口）、`tests/common/test_report_hub.py`、`.trae/skills/tools-scripts/report-hub.md`
> 改造文件：`tools/a_share/stock_equity.py`（复用其下载逻辑，不改动其对外接口）、约 10+ 个技能文件（SKILL.md / README.md）、`tools-scripts/` 指南文档（a-share-data.md / pdf-extraction.md / common-tools-guide.md）、`docs/A股工具使用指南.md`（新增章节 + 引导修改）
> 前置成果：三市场财务数据本地缓存方案已实施（`a_stock_cache.py` / `hk_stock_cache.py` / `us_stock_cache.py`，hit/refresh/stale 语义）
> 范围说明：**本期只做 A 股**（港美股无自动化下载工具，不存在重复下载问题，留待二期）

---

## 0. 已确认决策记录（2026-08-15）

| 决策点 | 结论 | 理由 |
| --- | --- | --- |
| 刷新策略 | **披露窗口感知** | 纯"存在即跳过"与"最新报告"语义矛盾（新年报发布后永久读旧报告）；固定 TTL 会白查；窗口外零网络 |
| 报告目录 | **沿用 `cninfo_reports/`** | 存量 PDF 立即变为缓存命中，零迁移成本 |
| 技能改动 | **一次性全改** | 避免过渡期新旧指令并存的不一致 |
| 市场范围 | **本期只做 A 股** | 重复下载实际发生在 A 股（stock_equity.py 自动下载）；港美股手动获取无此问题 |

---

## 1. 问题：三层重复

### 1.1 下载层 — 跳过逻辑位置错误

`stock_equity.py download_report` 现流程（L704-L785）：

```
调巨潮API查公告列表（多关键词、可能多轮请求）→ 构造文件名 → 检查本地文件是否存在（≥1MB跳过）
```

文件已存在时 PDF 不会重复下载，但**每次都白查一次巨潮 API**（本地检查在 API 查询之后）。

真正的重复下载来自两处：

1. **目录不统一**：各技能默认 `cninfo_reports/`，但 earnings-review / investment-team 的 SKILL.md 均示例了 `--report-dir ./reports/紫金矿业` —— 同一报告会下载两份，且互相不可见对方的缓存；
2. **并行竞态**：earnings-team / investment-team 四 Agent 并行分析同一公司，同时启动下载，文件未落盘时谁都检查不到，重复下载同一 PDF。

### 1.2 提取层 — 零缓存（最昂贵）

`pdf_extract.py` 的 `_check_exists` 只验证输入 PDF 存在，**不检查提取结果（.md）是否已生成**。每次技能执行都对同一 300+ 页 PDF 重新提取；OCR 场景（Adobe-CNS1 乱码回退）单次可达数分钟。"先目录页（0-10）后目标章节"的两步法约定散落在各技能内联指令中，无统一入口。

### 1.3 技能层 — 指令复制粘贴

559 处 `download-report / stock_equity / pdf_extract / pdftotext / 巨潮` 引用分布在 42 个文件。约 10+ 个技能各自内联几乎相同的"下载命令块 + pdf_extract 命令块 + Poppler 回退块"。`tools-scripts/pdf-extraction.md` 虽是提取指南，但无技能引用它，全是复制粘贴，导致指南更新无法传播。

---

## 2. 方案设计：`tools/common/report_hub.py`

### 2.1 命令设计

```bash
# ① 确保报告就绪（下载层统一入口，替代各技能的 stock_equity --download-report）
python tools/common/report_hub.py ensure --code 601899 --report-type annual
python tools/common/report_hub.py ensure --code 300502 --report-type quarterly

# ② 提取（提取层统一入口，内包 pdf_extract.py，带结果缓存）
python tools/common/report_hub.py extract --code 601899 --report-type annual                    # 全量 → 缓存 {stem}.md
python tools/common/report_hub.py extract --code 601899 --report-type annual --pages 0-10       # 目录页 → 缓存 {stem}_toc.md
python tools/common/report_hub.py extract --pdf cninfo_reports/601899_2025年报.pdf --pages 40-60,120-135  # 指定PDF章节

# ③ 查看本地已有报告与提取产物
python tools/common/report_hub.py list --code 601899
```

`--report-type`：`annual` / `semiannual` / `quarterly`（与 stock_equity.py 一致）。

### 2.2 下载层：披露窗口感知刷新

**检查时间戳**：sidecar 元数据文件 `cninfo_reports/{stem}.meta.json`，记录 `last_check`（最近一次巨潮确认时间）、`source_url`（公告URL）、`title`（公告标题，便于溯源）。

**窗口定义**（A 股法定披露节奏，月度粒度常量表）：

| 报告类型 | 披露窗口 | 缓冲期（容纳晚披露） |
| --- | --- | --- |
| annual（次年披露） | 1-4 月 | 5 月上半月 |
| quarterly 一季报 | 4 月 | 5 月上半月 |
| semiannual | 7-8 月 | 9 月上半月 |
| quarterly 三季报 | 10 月 | 11 月上半月 |

**ensure 决策流程**：

```
本地文件不存在 → 调 stock_equity 下载（.part 临时文件 + os.replace 原子落盘）→ meta.json 落盘 → return refresh
本地文件存在且 ≥1MB：
  ├─ 当前不在窗口+缓冲期内 → 零网络直接返回 → cache: hit
  └─ 在窗口内/缓冲期内，且 last_check 距今 > 7 天
      ├─ 查一次巨潮公告列表（get_latest_report_url，只查列表）
      │   ├─ 最新报告年份/标题与本地一致 → 更新 last_check → cache: check_hit
      │   └─ 有更新版本 → 下载新报告（旧文件保留供历史对比）→ cache: refresh
      └─ 距今 ≤ 7 天（本周期已查过）→ 零网络返回 → cache: hit
本地文件存在但 <1MB → 删除重下（沿用现有摘要版防护）
巨潮查询/下载失败且本地有文件 → 返回旧文件 → cache: stale
```

窗口内最多每 7 天查一次公告列表，窗口外完全零网络。

### 2.3 提取层：结果缓存

- 缓存对象：`pdf_extract.py markdown --save-md` 生成的 Markdown 文件
- 缓存位置与命名（`cninfo_reports/extracted/` 子目录）：
  - 全量：`{stem}.md`
  - 目录页（`--pages 0-10` 固定语义）：`{stem}_toc.md`
  - 章节提取：`{stem}_p{页码规范化串}.md`（页码排序去重后哈希，如 `_p40-60,120-135.md`）
- **失效判定**：`md 不存在 or md.mtime < pdf.mtime`（PDF 重新下载必然更新 mtime，天然触发失效；PDF 为静态文件，无需内容哈希）
- 提取失败（扫描件 / pdf-inspector 异常）：透传 pdf_extract.py 的 `{"scanned": true, ...}` 标志与退出码，**不生成缓存文件**（避免坏结果被缓存）；OCR 提取成功后同样落缓存（OCR 最昂贵，收益最大）
- 回退链保持现状不变：`report_hub extract` 内部先 pdf_extract.py，失败时按现有约定提示 Poppler 回退（Poppler 手动命令集中在 `tools-scripts/report-hub.md`，技能不再内联）

### 2.4 并行竞态处理

- 下载：写入 `{final}.part.{pid}` 临时文件，完成后 `os.replace` 原子替换。四 Agent 并行时各自写各自的 .part，最终内容一致（同一公告 URL），无害且无半成品文件被读到
- 提取：同样 .part + os.replace；并行重复提取只是浪费一次 CPU，不会产生损坏文件
- 不引入跨进程文件锁（os.replace 幂等已够，锁会增加 Windows 复杂度）

### 2.5 输出格式

与三市场缓存方案一致的 JSON + meta.cache 语义：

```json
{
  "success": true,
  "code": "601899",
  "report_type": "annual",
  "year": "2025",
  "pdf_path": "cninfo_reports/601899_2025年报.pdf",
  "extract_path": "cninfo_reports/extracted/601899_2025年报.md",
  "meta": {
    "tool": "report_hub",
    "cache": "hit | check_hit | refresh | stale",
    "checked_at": "2026-08-15T...",
    "timestamp": "..."
  }
}
```

### 2.6 与 stock_equity.py 的关系

**复用不重写**：`report_hub.py` import `CnInfoReportDownloader` 的公告查询与下载能力（`get_latest_report_url` 等），不改其对外接口；`stock_equity.py --download-report` 保持可用（存量命令兼容），但技能层不再直接调用它下载报告。

---

## 3. 技能层改造（一次性全改）

### 3.1 改造原则

1. **下载指令块** → 替换为单命令 `python tools/common/report_hub.py ensure --code {代码} --report-type {类型}`
2. **提取指令块** → 替换为 `python tools/common/report_hub.py extract ...`（含两步法：先 `--pages 0-10` 取目录，再按目录取章节）
3. **删除所有 `--report-dir` 示例**（统一目录才能命中缓存）
4. 详细用法（Poppler 回退命令、OCR 参数、文件命名）集中到 **`tools-scripts/report-hub.md`** 一份文档，各技能一句话引用："报告获取与提取统一使用 report_hub.py，详见 tools-scripts/report-hub.md"
5. 流程检查点保留："确认 ensure 返回 success=true 后方可进入阅读分析"（呼应既有约束：报告须完整下载后方可分析）

### 3.2 技能改造清单

| 技能/文档 | 改动点 |
| --- | --- |
| financial-data | SKILL.md L59-L78 下载+提取命令块替换；README.md 同步 |
| earnings-review | SKILL.md L44-L99（含 --report-dir 示例 L64）、L356-L373 工具表；README.md |
| earnings-team | SKILL.md L35-L99 下载+提取块；README.md |
| investment-team | SKILL.md L72-L99（含 --report-dir 示例 L81）；README.md |
| management-deep-dive | SKILL.md L146、L470 下载说明；README.md |
| industry-research | SKILL.md L390-L397 提取命令块；README.md |
| industry-funnel | SKILL.md L515-L522；README.md |
| investment-research | SKILL.md / README.md 下载引用 |
| investment-checklist | SKILL.md / README.md 下载引用 |
| quality-screen | SKILL.md / README.md 下载引用 |
| deep-company-series | SKILL.md / README.md 下载引用 |
| bottleneck-hunter / dyp-ask / news-pulse / wechat-article / thesis-tracker / thesis-drift / portfolio-review / income-investment | 引用处统一替换（多为工具表一行） |
| 证券AI价值投资研究工作步骤.md | 报告获取章节同步 |

### 3.3 工具文档同步清单

| 文档 | 改动点 |
| --- | --- |
| **docs/A股工具使用指南.md** | ① 工具总表（L20/L45 附近）新增 report_hub.py 行；② 第五章 stock_equity.py 的 `--download-report`（L510-L528）加"技能流程推荐改用 report_hub.py ensure"引导，`--report-dir` 示例（L528）标注"技能流程中禁用（破坏缓存命中）"；③ 第十六章 pdf_extract.py 的"下载→提取"组合流程示例（L1846-L1850）改为 report_hub ensure + extract；④ **新增独立章节**"report_hub.py — 财报下载与提取统一入口"（ensure/extract/list 命令、披露窗口感知、缓存语义、提取缓存失效规则） |
| **tools-scripts/report-hub.md（新增）** | 技能层唯一详细指南：ensure/extract/list 用法、meta.cache 语义（hit/check_hit/refresh/stale）、两步法（目录页→章节）、Poppler 回退命令、OCR 参数、竞态与 .part 说明、.meta.json 溯源字段 |
| tools-scripts/common-tools-guide.md | 公共工具索引表（L17 a-share-data 行、L23 pdf-extraction 行）加入 report_hub.py；工具使用指南索引（L40-L46）加入 report-hub 链接 |
| tools-scripts/a-share-data.md | "财报PDF下载"章节（L32-L42）改为 report_hub.py ensure 优先；stock_equity.py `--download-report` 降级为底层工具说明（保留兼容） |
| tools-scripts/pdf-extraction.md | **保持底层提取指南定位**：顶部新增引导段——"经 report_hub.py extract 调用可自动缓存提取结果；直接调用 pdf_extract.py 不走缓存，仅适用于临时性/一次性提取"；L280 附近下载命令同步为 report_hub |

> 分层文档关系：`report-hub.md`（统一入口层：下载 + 提取 + 缓存）→ `pdf-extraction.md`（底层提取层：pdf-inspector 子命令、OCR、Poppler 回退）→ `docs/A股工具使用指南.md`（完整工具参考：全部参数与数据源细节）。三层互链，避免再次复制粘贴。

---

## 4. 测试计划

`tests/common/test_report_hub.py`（unittest + mock，无网络依赖）：

1. **窗口判断纯函数**：各报告类型 × 12 个月的 needs_check 矩阵；缓冲期边界；last_check 7 天内不重复查
2. **ensure 缓存路径**：窗口外命中（零 API 调用，mock 断言巨潮未被调用）；窗口内首查触发公告列表比对；查到新版触发下载；查询失败降级 stale
3. **提取缓存**：md 存在且新于 PDF 秒回；PDF 更新（mtime 推后）自动失效；扫描件失败不落缓存
4. **竞态模拟**：多线程并行 ensure 同一代码，最终只存在一份完整文件且无 .part 残留
5. **存量兼容**：cninfo_reports/ 已有旧 PDF（无 meta.json）首次 ensure 的行为（视为 last_check=文件 mtime）

集成冒烟（网络）：`ensure --code 601899 --report-type annual` 两次连跑，第二次 meta.cache=hit 且耗时显著下降。

---

## 5. 验收标准

1. 同一报告第二次 `ensure`（窗口外）**零网络调用**
2. 四进程并行 `ensure` 只产生一份完整 PDF，无 .part 残留
3. 同一 PDF 第二次 `extract`（PDF 未变）**秒回缓存**
4. PDF 重新下载后 `extract` 自动失效重提取
5. 所有技能文件不再含内联下载/提取命令块（仅统一引用 + tools-scripts/report-hub.md）；`docs/A股工具使用指南.md` 含 report_hub.py 完整章节；tools-scripts 三个指南（a-share-data / pdf-extraction / common-tools-guide）与 report-hub.md 互链一致，无过时的 `--report-dir` 技能层示例
6. 全量测试通过（新增测试 + 三市场缓存/A股/港股/美股既有测试回归）

---

## 6. 明确不做的事

- **港美股报告自动下载**（港股披露易 / SEC EDGAR）：无现有重复问题，二期评估
- **K 线/行情缓存**：已在前序方案中明确排除
- **cninfo_reports/ 清理策略**：磁盘占用暂不管理，未来按需加 `--prune`
- **跨进程文件锁**：os.replace 原子性已满足需求
- **stock_equity.py 对外接口变更**：完全兼容，仅技能层切换调用方
