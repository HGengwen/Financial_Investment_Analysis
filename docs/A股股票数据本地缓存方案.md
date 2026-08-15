# A股股票数据本地缓存方案

> 状态：已实施（2026-08-15）
> 实现文件：`tools/common/a_stock_cache.py`（新建）、`tools/a_share/stock_info.py`、`tools/a_share/stock_screen.py`、`tools/a_share/stock_financial.py`
> 测试文件：`tests/common/test_stock_cache.py`

---

## 1. 背景与问题

多数技能需要由股票名称查询股票代码，或由股票代码查询股票名称。当前 `tools/a_share/stock_info.py` 每次查询都调用 akshare 的 API 获取全部 A 股代码和名称（约 5700 条），导致：

1. **系统低效** — 每次查询均为全量网络拉取，多数场景下数据几乎无变化；
2. **易触发限流** — akshare 的 `RemoteDisconnected` 即为服务端封禁信号（见项目记忆）。

### 摸底发现的关键事实

| # | 发现 | 影响 |
|---|---|---|
| 1 | `--search`/`--code` 每次调用 `get_a_stock_industry_info()`，其内部拉取 `ak.stock_yjbb_em`（全市场业绩报表，约 5000 行），失败时最多重试 3 个季度日期 | 行业数据调用比代码列表更重，是限流的最大来源，必须一并缓存 |
| 2 | 纯"本地查不到才调 API"策略下，退市股永久残留缓存、改名股（戴帽 ST 等）按代码查询永远返回旧名 | 需引入 TTL 刷新策略 |
| 3 | `stock_screen.py`（557/573 行）与 `stock_financial.py`（285 行）调用完全相同的两个 API | 同样消耗限流配额，应接入同一缓存 |
| 4 | `stock_info.py` 的 `get_a_stock_industry_info()` 中，若 3 个季度候选全部失败，`df` 未定义会抛 `UnboundLocalError` | 现有隐患，本次一并修复 |
| 5 | akshare 无"查单只股票"接口，miss 后 API 返回的仍是全量列表 | miss 的合理语义为：拉全量 → 整体覆写缓存 → 再查一次 |

## 2. 已确认的设计决策

| 决策项 | 结论 |
|---|---|
| 行业数据（stock_yjbb_em） | **一并缓存**（按季度数据天然适合缓存） |
| 刷新策略 | **TTL + miss 双触发** |
| 缓存位置 | **`data/a_share/`**（工作区根目录 data/ 下按市场分目录，为港股/美股留位置） |
| 改造范围 | **抽公共缓存模块**，stock_info / stock_screen / stock_financial 三工具全部接入 |

## 3. 新建公共缓存模块 `tools/common/a_stock_cache.py`

### 3.1 接口设计

```python
get_code_name_list(force_refresh: bool = False) -> list[dict]
    """返回 [{"code": "000001", "name": "平安银行", "market": "a"}, ...]

    逻辑：
    - 缓存文件存在且未超 TTL → 读本地返回
    - 否则 → ak.stock_info_a_code_name() → 原子覆写 CSV → 返回
    """

get_industry_map(force_refresh: bool = False) -> dict[str, dict]
    """返回 {"300502": {"code", "name", "industry", "roe",
                        "gross_margin", "eps", "quarter"}, ...}

    逻辑：
    - 继承 stock_info.py 现有的 3 季度回退 + 有效性校验
      （>1000 行且 >100 条行业数据才算有效）
    - 成功后连同实际命中的季度号一起缓存
    - 修复隐患：全部季度失败时抛出明确 RuntimeError（而非 UnboundLocalError）
    """
```

### 3.2 容错（降级策略）

- 刷新失败（akshare 限流/断连）时，若本地存在旧缓存（即使已过期），**降级返回旧数据**并在返回值中标注 `stale=True`；
- 无任何可用缓存才向上抛错。

## 4. 缓存文件设计 — `data/a_share/`（新建目录）

| 文件 | 列 | 说明 |
|---|---|---|
| `stock_code.csv` | code, name, market | 全部 A 股代码名称 |
| `stock_industry.csv` | code, name, industry, roe, gross_margin, eps, quarter | 最新有效季度业绩数据 |

技术约定：

- **TTL**：以文件 mtime 判断，默认 **7 天**，`.env` 中 `STOCK_CACHE_TTL_DAYS` 可配；
- **编码**：UTF-8-SIG（Excel 打开中文不乱码，pandas 可正常读取）；
- **原子写**：先写 `.tmp` 临时文件再 `os.replace`（Windows 安全，避免并发写坏文件）；
- **损坏回退**：CSV 解析失败视为缓存 miss，重新拉取并覆写。

## 5. 三个工具接入（仅替换数据获取入口，输出 JSON 结构不变）

| 文件 | 改动 |
|---|---|
| `tools/a_share/stock_info.py` | `get_all_a_stocks()` / `get_a_stock_industry_info()` 改为调用缓存模块；新增 `--refresh` 参数强制刷新两类缓存并输出统计；meta 中追加 `cache: hit/miss/stale` 字段 |
| `tools/a_share/stock_screen.py` | 557 行 `ak.stock_info_a_code_name()`、573 行 `ak.stock_yjbb_em()` 两处替换为缓存模块查询 |
| `tools/a_share/stock_financial.py` | 285 行 yjbb 调用块替换为缓存模块查询 |

**导入方式**：文件顶部 `sys.path.insert(0, 项目根目录)` 后 `from tools.common import a_stock_cache`（符合"imports 置顶"规则；当前项目各工具以独立脚本运行，无现成跨目录导入先例）。

## 6. 查询行为矩阵（TTL + miss 双触发）

| 场景 | 行为 |
|---|---|
| 缓存新鲜 + 代码/名称命中 | 纯本地查询，零 API 调用 |
| 缓存新鲜 + 未命中（新 IPO 或输错码） | 拉一次全量刷新缓存 → 再查一次 → 仍无则报"未找到" |
| 缓存超过 7 天 | 任意查询触发刷新（退市股/改名股最迟 7 天自愈） |
| `--refresh` | 强制刷新两类缓存并输出统计 |

## 7. 测试计划 — `tests/common/test_stock_cache.py`

mock akshare（不联网），覆盖：

1. TTL 命中（新鲜缓存不触发 API）；
2. TTL 过期触发刷新；
3. miss 触发刷新并覆写缓存；
4. 损坏 CSV 回退；
5. 原子写（.tmp + os.replace）；
6. 季度回退逻辑与全部失败时的 RuntimeError；
7. 刷新失败时降级返回旧缓存（stale 标注）；
8. 回归运行三个工具的现有测试。

## 8. 已确认的权衡

- **输错代码会触发一次全量拉取** — 换取消灭重复全量调用，净收益为正；
- **7 天内退市股仍显示为有效** — TTL 到期自愈，可接受；
- **7 天内改名股按代码查询返回旧名** — 按新名称搜索会 miss 触发刷新，可自愈。

---

## 9. 实施记录（2026-08-15）

### 完成内容

1. 新建 `tools/common/a_stock_cache.py`，提供 `get_code_name_list()` / `get_industry_map()`，
   内置 TTL 判定（`STOCK_CACHE_TTL_DAYS`，默认 7 天）、原子写（.tmp + os.replace）、
   损坏 CSV 回退、限流降级（旧缓存兜底标注 stale），并通过
   `get_code_name_status()` / `get_industry_status()` 暴露最近一次缓存状态。
2. `stock_info.py` 接入缓存；新增 `--refresh` 命令（`cmd_refresh`）强制刷新两类缓存；
   `cmd_search` / `cmd_code` 实现 miss 双触发（本地查不到 → 强制刷新一次 → 再查）；
   meta 增加 `cache` 字段（hit / refresh / stale）。
3. `stock_screen.py` 两处 API 调用（557/573 行）替换为缓存模块查询；
   保留 `get_latest_quarter_date()`（既有测试依赖）。
4. `stock_financial.py` 的 `stock_yjbb_em` 调用块替换为缓存模块查询。
5. 修复原隐患：`get_a_stock_industry_info()` 原 3 季度候选全部失败时 `df` 未定义的
   `UnboundLocalError`，现改为抛出明确 `RuntimeError`。
6. 新建 `tests/common/test_stock_cache.py`（12 个用例，全程 mock akshare 不联网）。

### 验证结果

| 项目 | 结果 |
|---|---|
| tests/common/test_stock_cache.py | 12 passed |
| tests/a_share/test_stock_info.py | 29 passed, 1 skipped |
| tests/a_share/test_stock_screen.py + test_stock_financial.py | 140 passed |
| `--refresh` 真实运行 | stock_code.csv 5543 条 + stock_industry.csv 1123 条（13 秒） |
| 二次查询 `--search 新易盛` / `--code 300502` | `cache: "hit"`，即时返回 |
| 行业缓存数据核对 | 与 `ak.stock_yjbb_em("20260630")` 原始返回一致（1123 条，8 月中旬半年报未披露完） |

### 使用说明

- 缓存文件：`data/a_share/stock_code.csv`、`data/a_share/stock_industry.csv`
- 强制刷新：`python tools/a_share/stock_info.py --refresh`
- TTL 配置：`.env` 的 `STOCK_CACHE_TTL_DAYS`（默认 7 天）
