---
name: report-hub
description: "A股财报下载与提取统一入口：使用 tools/common/report_hub.py 的 ensure（披露窗口感知下载）/ extract（带结果缓存提取）/ list（缓存清单）命令，统一管理 cninfo_reports/ 目录下的年报、半年报、季报，消除技能间的重复下载与重复提取。"
disable-model-invocation: true
---

# A股财报下载与提取统一入口（report_hub）

**所有涉及 A 股年报/半年报/季报下载与提取的技能流程，统一使用 `tools/common/report_hub.py`**。
它同时管理两层缓存：
- **下载层**：披露窗口感知 —— 窗口外零网络直接返回本地 PDF；窗口内才查询巨潮 API
- **提取层**：提取结果缓存 —— 同一 PDF 未变时秒回已生成的 Markdown

> 底层细节（pdf-inspector 子命令、OCR、Poppler 回退）见 [PDF文档提取技能](./pdf-extraction.md)；
> 完整参数参考见 docs/A股工具使用指南.md。

---

## 下载（ensure）—— 确保最新报告就绪

```bash
# 确保最新年报已下载（窗口外直接命中缓存，零网络）
python tools/common/report_hub.py ensure --code 601899 --report-type annual

# 半年报 / 季报
python tools/common/report_hub.py ensure --code 601899 --report-type semiannual
python tools/common/report_hub.py ensure --code 601899 --report-type quarterly

# 强制刷新（跳过窗口检查，直查巨潮 API）
python tools/common/report_hub.py ensure --code 601899 --report-type annual --force
```

- PDF 统一保存在 `cninfo_reports/`，命名 `{股票代码}_{年份}{报告类型}.pdf`
- 元数据（最近检查时间、年份）保存在 `cninfo_reports/.meta/{代码}_{类型}.json`
- **流程检查点**：确认返回 `"success": true` 后方可进入阅读分析

## 提取（extract）—— 带结果缓存的 PDF→Markdown

```bash
# 全量提取（缓存命中时秒回）
python tools/common/report_hub.py extract --code 601899 --report-type annual

# 两步法：先取目录页（0-10），再按目录取目标章节
python tools/common/report_hub.py extract --pdf cninfo_reports/601899_2025年报.pdf --pages 0-10
python tools/common/report_hub.py extract --pdf cninfo_reports/601899_2025年报.pdf --pages 40-60,120-135

# 强制 OCR（扫描件场景）
python tools/common/report_hub.py extract --code 601899 --report-type annual --force-ocr
```

- 提取产物统一输出到 `cninfo_reports/extracted/`
- 全量：`{stem}.md`；目录页：`{stem}_p0_10.md`；章节：`{stem}_p40_60_120_135.md`
- **缓存失效**：PDF 重新下载（mtime 更新）后自动失效重提取

## 查看本地缓存（list）

```bash
python tools/common/report_hub.py list --code 601899
```

输出该代码已缓存的各报告：年份、PDF 是否存在、大小、是否已提取。

---

## 缓存语义（meta.cache）

| 值 | 含义 |
| --- | --- |
| `hit` | 本地缓存直接命中（窗口外零网络） |
| `check_hit` | 窗口内查巨潮确认无更新后返回本地（首次下载也为此值） |
| `refresh` | 检测到新版本并重新下载 / 重新提取 |
| `stale` | 巨潮 API 失败，降级返回旧文件 |
| `error` | 无缓存且获取失败 |

---

## 设计要点

- **披露窗口**：年报 1-5 月、半年报 7-9 月、季报 4-5 月或 10-11 月（含缓冲期）。窗口内最多每 7 天查一次巨潮，窗口外完全零网络
- **禁用 `--report-dir`**：统一存 `cninfo_reports/` 才能命中缓存，自定义目录会破坏缓存
- **并行安全**：多 Agent 并行 ensure 同一公司时，`.part` 临时文件 + 原子替换，不会产生损坏文件
