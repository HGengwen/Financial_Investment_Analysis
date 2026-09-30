# AKShare 东方财富反爬限流改进 —— 改进完成报告

> **状态**：**已实施完成（步骤 1~7 全部兑现）**（2026-09-28）
> **上游方案（唯一权威规格，未改动）**：[AKShare东方财富反爬限流改进方案.md](AKShare东方财富反爬限流改进方案.md)
> **上游现状快照**：[AKShare东方财富接口清单与反爬限流现状.md](AKShare东方财富接口清单与反爬限流现状.md)
> **适用规模**：单机多进程（多子代理并行）
> **数据截止**：2026-09-30（本报告字节数 / 行数 / 用例数以当日实测为准；2026-09-28 基线及口径修正说明见 §5.1 / §5.2）
> **免责声明**：本报告与技术改进仅供学习与研究，不构成投资建议。

---

## 1. 结论概览

**方案 §9「实施路线图」中 P0 / P1 / P2 三个阶段的 6 项工作全部兑现，P3（多机 Redis 令牌桶）因前提未出现而保持预留。** 方案 §4「迁移清单」**13 项全部落地**（含 #12 现状文档 §4 缺口表逐条标注，已于 2026-09-28 收口，见 §9.1）。

| 阶段 | 方案 §9 工作项 | 实施步骤 | 状态 |
| --- | --- | --- | --- |
| **P0** | `em_gate.py` 骨架：跨进程文件锁 + 最小间隔 + 抖动 + 预算 + 封禁短路 + transport hook；挂载 A股四工具 / 港股财务 / 批量脚本；配置项 + `requirements.txt` | 步骤 1~2 | **已兑现** |
| **P0** | 降级语义统一（`success=false` + `fallback_cmd`）与编排层「第 0 步闸门自检」写入技能文档 | 步骤 3 | **已兑现** |
| **P1** | 熔断器（冷却窗口 + 半开探测）；`is_ban_signal` / `is_transient` 迁出共享；接入 `stock_equity.py`、`a_stock_cache.py`、`sector_screen.py` | 步骤 4 | **已兑现** |
| **P1** | 统一 UA / Referer / keep-alive；代理绕过 + 代理失败直连重试（仅连接类错误） | 步骤 5 | **已兑现** |
| **P2** | 主机回退链（push2 / push2his → push2delay），先接 `fx_rate.py` 与 A股日线 | 步骤 6（含加固） | **已兑现** |
| **P2** | 监控 `em_gate report` + 数据源路由统一函数 | 步骤 7 | **已兑现** |
| **P3（预留）** | 多机部署时切换 Redis 令牌桶 | — | **保持预留**（仍为单机多进程场景，前提未出现） |

**方案外新增能力 1 项**（经用户裁定后实施）：东财请求**强制 IPv4**（`EM_GATE_FORCE_IPV4`）。

---

## 2. 交付件总清单

| 类别 | 交付件 | 规模（2026-09-30 修正） | 性质 |
| --- | --- | --- | --- |
| **核心组件（新建）** | `tools/common/em_gate.py` | 92,449 B / 2,328 行 | 跨进程闸门：锁 / 限流 / 预算 / 封禁短路 / 熔断 / 指纹 / 代理策略 / 主机回退 / 强制 IPv4 / 降级语义 / 观测 CLI |
| **核心组件（新建）** | `tools/common/source_router.py` | 18,829 B / 513 行 | 声明式数据源路由表 + 通用执行器 |
| **工具接入（改）** | `tools/a_share/stock_quote.py` | 30,147 B / 739 行 | 闸门挂载 + 日线路由接入 + 腾讯回退源 |
| **工具接入（改）** | `tools/a_share/stock_equity.py` | 43,907 B / 1,126 行 | 闸门挂载 + `guarded` 外包 + 封禁短路 |
| **工具接入（改）** | `tools/a_share/stock_info.py` / `stock_financial.py` / `stock_screen.py` | — | 各 `main()` 首行挂载闸门（业务逻辑零改写） |
| **工具接入（改）** | `tools/hk_stock/stock_info.py` / `stock_financial.py` / `stock_screen.py` | — | 同上 |
| **工具接入（改）** | `tools/common/fx_rate.py` | 41,609 B / 1,034 行 | 闸门挂载 + 异常分类迁出委托 + 限流器让位 |
| **工具接入（改）** | `tools/common/a_stock_cache.py` | 26,680 B / 747 行 | `guarded` 外包 + 封禁不重试 / 普通错误短退避重试 |
| **工具接入（改）** | `tools/common/sector_screen.py` | 18,167 B / 457 行 | `guarded` 外包 + 封禁即停整批 → stale 降级 |
| **批量脚本（改）** | `tools/a_share/stock_financial_batch.ps1` | — | 移除脚本层 sleep、新增 `-MaxCodes` 软上限与盘后时段校验 |
| **配置（改）** | `.env` / `.env.example` | 15 项 `EM_GATE_*` + `A_FINANCIAL_TTL_DAYS` | 见 §4 |
| **依赖声明（改）** | `requirements.txt` | 1 行 | 补声明 `filelock`（此前为传递依赖） |
| **测试（新建）** | `tests/common/test_em_gate.py` | 70,473 B / 1,693 行 / **54 用例** | 方案 §7 测试矩阵落地 |
| **测试（新建）** | `tests/common/test_source_router.py` | 11,570 B / 266 行 / **19 用例** | 路由表口径与执行器 |
| **测试（改）** | `tests/a_share/test_stock_quote.py` | 39,953 B / 876 行 / **70 用例** | 腾讯源 + 路由接入断言 |
| **测试（改）** | `tests/conftest.py` | 2 行 | `EM_GATE_ENABLED=0` 默认旁路（`setdefault`，外部显式设置仍优先） |
| **文档（改）** | `CLAUDE.md`「工作规范」 | 1 条 | 并发前置：并行子代理前先跑 `em_gate.py status` 读 `data.allowed` / `data.circuit` |
| **文档（改）** | 9 个编排类技能 + 3 个工作步骤文档 | 12 文件 | 写入「第 0 步：东财闸门自检」 |
| **文档（改）** | `docs/dev_docs/AKShare东方财富接口清单与反爬限流现状.md` | 状态更新 2 行 + §4 缺口表加 1 列 | L7 状态更新收口至 #1~#6 全覆盖；§4 缺口表逐条加覆盖标注（方案 §4 迁移清单 #12） |
| **编排留痕** | `upgrade1.0/GARP升级-软件与技能升级详细计划.md` §0.7 | 增量登记（二十一）~（三十一） | 每步骤完成门禁与偏离报备 |

---

## 3. 逐阶段实现摘要

### 3.1 P0 · 步骤 1~3：闸门骨架 + 工具挂载 + 降级语义统一

**步骤 1（闸门骨架）**：`em_gate.py` 落地跨进程闸门——`filelock` 跨进程互斥（`data/.locks/em_gate.lock`）、`data/.locks/em_gate_state.json` 状态文件（锁内读 / 原子 `os.replace` 写）、最小间隔 1.2 s + 抖动 U(0, 1.0)、分钟 / 5 分钟滑窗预算、封禁信号即时短路、`requests.sessions.Session.request` transport hook、`status` / `report` / `reset` 观测子命令。**业务体零改写**。

设计要点严格执行方案 §1：① 锁粒度 = 单个 HTTP 请求（akshare 内部翻页也被节流，故不需要可重入锁）；② 锁内不做退避重试（锁内仅「节奏 sleep」且硬上限 3 s，超出则放弃取锁退避重试，防长占锁阻塞其余子代理）；③ 熔断短路发生在取锁之前。

**步骤 2（工具挂载）**：7 个 A股 / 港股工具（A股 `stock_quote` / `stock_info` / `stock_financial` / `stock_screen`，港股 `stock_info` / `stock_financial` / `stock_screen`）各在 `main()` 首行调用闸门装载，**每处仅 1 行 + 一个 fail-open 包装**；`stock_financial_batch.ps1` 按 §3.6 归位——移除脚本层 `-interval` / `Start-Sleep`（节流唯一归闸门，避免双重节流）、新增 `-MaxCodes`（默认 20，超出即中止）与盘后时段校验（`-AllowIntraday` 显式放行）。

**步骤 3（降级语义统一与编排层自检）**：按 §3.4 落地 `gate_code()` / `is_gate_error()` / `degraded_payload()` / `emit_rejection()` / `install_cli()`，并以 **`sys.exit` + `sys.excepthook` 双进程级兜底**保证闸门拒绝时**一律**输出 `success=false` + `meta.gate` + 可执行 `fallback_cmd`，**绝不伪造 `success=true`**；9 个编排类技能 + 3 个工作步骤文档 + `CLAUDE.md` 写入「并发前置：东财闸门自检」。**收口补丁 3.1-e**：修复 `a_stock_cache._is_cache_fresh` 恒用 `STOCK_CACHE_TTL_DAYS` 致 `_get_financial_json(..., ttl_days)` 形参失效的缺陷（财务缓存口径由**事实 30 天**回到**设计 7 天**），并在 `.env` / `.env.example` 文档化 `A_FINANCIAL_TTL_DAYS`。

### 3.2 P1 · 步骤 4：熔断器 + 异常分类迁出 + 三工具接入

- **4.1 熔断器核心**：三相位（`closed` / `open` / `half_open`）+ 冷却窗口（默认 30 min）+ **半开单探测位**。熔断短路按 §1 要点 3 置于**取锁之前**（锁外无锁快读预检 → 锁内权威二次校验，双段），冷却期内 N 个进程**连锁都不取**；探测位占位即立即落盘，使跨进程即刻可见；探测成功则关闭熔断并清零 `consecutive_ban`，探测再被封禁则**立即重开冷却**（不重新累计到阈值）；非封禁瞬时错误**不**计入 `consecutive_ban`（对应 §8「熔断误判」缓解）。
- **4.3 异常分类迁出共享**：`fx_rate.py` 的 `_is_transient` / `_is_ban_signal` **委托 `em_gate`**（保留私有符号名，零调用点改动，模块缺失时回退本地等价实现）；`_RateLimiter.wait(*, covered_by_gate=...)` **仅在「东财调用且闸门生效」时让位**（yfinance 路径保留本地 0.5 s 节流，否则退化为无节流裸调）。
- **4.4 三工具接入**：`stock_equity.py`（`_safe_api_call` 外包 `guarded` + `_http_get_with_retry` 加封禁短路 + `main()` 装载闸门）、`a_stock_cache.py`（`_fetch_em()`：`guarded` + 封禁不重试 + 普通错误短退避 2 s 重试 1 次；封禁时不再换季度候选）、`sector_screen.py`（东财回退源经 `guarded`；封禁即停整批 → stale 降级）。
- 观测增强：`status` / `report` / 日志新增 `circuit` / `circuit_open_until` / `half_open_probe_used` / `probe`，`meta.circuit_enforced` 由 `false` 转 `true`。

### 3.3 P1 · 步骤 5：请求指纹与代理策略

- **指纹**：东财请求统一注入 `User-Agent`（浏览器指纹）/ `Referer: https://quote.eastmoney.com/` / `Connection: keep-alive`，**不覆盖调用方显式 headers**（键名大小写不敏感比对，只补空缺）。
- **代理绕过**：`EM_GATE_BYPASS_PROXY=1`（默认）时东财请求剥离 `HTTP(S)_PROXY`——实现上把 `http` / `https` **显式置为空串**，因为传 `{}` 会被 requests 的 `merge_environment_settings` 以 `setdefault` 回填 env 代理（**等于没绕过**，属实测后修正）。
- **代理失败直连重试**：仅在因**连接类错误**（**非**封禁信号）失败时剥离代理直连重试**一次**，且该次重试仍走**完整闸门**（重新取锁 + 重新节奏间隔，不在锁内重试，遵 §1 要点 2）。新增 `is_connection_error()`，**先排除封禁信号**——`RemoteDisconnected` 同属 `ConnectionError`，但换直连无用且加重惩罚（§10 第 3 条禁止重试）。
- 指标日志新增 `proxy_retry` 字段，`_meta` 暴露 `fingerprint_enforced` / `bypass_proxy`。**指纹与代理全部落在传输层，业务工具零改动。**

### 3.4 P2 · 步骤 6：主机回退链（含自愈加固）

- **回退链**：新增 `_HOST_FALLBACK_MAP`（`push2his` / `push2` → `push2delay`）、`_HOST_FAIL_THRESHOLD=2`、`_HOST_DEGRADED_SECONDS=600`，以及 `_fallback_host()` / `_swap_host()` / `_pick_fallback_host()` / `_update_host_health()` 四个纯函数。触发条件严格按 §2.5：**连续 2 次连接类错误且非封禁信号** → 写 `host_degraded_until = now + 600 s` 并改写 URL 走回退主机（期内不再先试死主机）；**封禁信号不触发回退**（全站级，换主机无用）但会打断连续计数；成功请求亦清零连续计数。改写落在**传输层 hook**，9 个工具零改动。
- **自愈加固（由现场发现派生）**：原实现中若**回退主机自身不可达**，降级窗口会把请求钉在死主机上整整 10 分钟。故 `_update_host_health()` 新增 `degraded` 参数——当本次请求已由降级窗口改写、且回退主机连续 2 次连接类错误时，**立即清零降级窗口回主主机重新评估**。不新增配置项、不改方案阈值。

### 3.5 P2 · 步骤 7：监控加固 + 数据源路由统一函数

- **7.1 `report` 监控加固**（修复真实可观测性缺陷）：原 `cmd_report` 把**尾部截断计数当总量呈现**（日志 1,074 行时 `log.lines` 仅报尾部行数），会系统性低估封禁率。现改为全量读入后分离 `total_lines` / `scanned` / `truncated` / `scan_limit` / `unparsable`（`log.lines` 恒等于 `scanned` 以兼容既有键），新增 `--limit 0` 全量扫描；相位与预算改为与 `status` **共用 `check_budget()`**（消除两处口径漂移）；新增 `_health_verdict()` 三档健康判定（`critical`＝熔断非 `closed`；`warn`＝连续封禁 / 主机降级窗口生效 / 累计降级或封禁 > 0 / 统计被截断；`ok`＝其余及闸门停用），输出 `ban_rate` 与 `health.level` / `health.reasons`。
- **7.2 `source_router.py`（新建）**：把此前**分散在各工具的「主源失败 → 备源」逻辑**（`stock_quote` 局内闭包、`stock_info` 百度→东财、`stock_equity` 巨潮→东财、`hk_stock.stock_quote` 3 次重试）收敛为**声明式路由表 + 通用执行器**：

  | 数据 | 优先级（方案 §6 逐行落实） |
  | --- | --- |
  | A股实时行情 | 新浪 → 东财 |
  | A股日线 | 东财 → **腾讯（新增）** → 新浪 |
  | 全 A 代码列表 | 交易所官网 → 东财 |
  | 财报 / 股东 | 巨潮资讯 → 东财 |
  | 港股行情 | 新浪 → 东财 |
  | 港股财务 | 东财（**唯一源，无替代**） |

  `route()` 按优先级逐源尝试并返回首个成功结果；未提供 fetcher 的源记 `skipped`（**非失败**）且不中断；`RouteOutcome.as_dict()` 输出逐源尝试记录（`source` / `status` / `elapsed_s` / `error` 截断 200 字符）；全源失败抛 `AllSourcesFailed`，**自带 §3.4 要求的可执行 `fallback_cmd`**；`sources_for()` 支持 `start_from`（起点源含）/ `limit_to` 白名单；另提供只读 CLI（`--list` / `--source`）。
- **7.3 `stock_quote.py` 单点接入 + 腾讯回退**：新增 `get_quote_tencent()`；日线取数改走路由；`--source` 语义由「锁死单源」改为**起点源**（其后仍按路由表回退），choices 扩为 `eastmoney` / `tencent` / `sina`；`meta` 追加 `source_actual` 与 `routing`（逐源尝试留痕）；失败分支补 `meta.fallback_cmd`。
  **腾讯源字段语义经实测交叉验证**：`sh600519` 2026-09-17 腾讯 `amount` = 17554 与同新浪 `volume` = 1755380 股 = 17553.8 **手**一致 → 腾讯该列实为**成交量且单位为手**（非成交额），且 OHLC 与新浪逐字段完全一致。故重命名为 `volume` 且不做「股 → 手」换算。

### 3.6 方案外加固：东财请求强制 IPv4（经用户裁定）

按根因定位（TCP / TLS 均成功但请求发出后服务端回空响应 → 表现为 `RemoteDisconnected`）实施 `EM_GATE_FORCE_IPV4=1`：以 urllib3 官方地址族选择点 `urllib3.util.connection.allowed_gai_family` 为注入点，patch 为 `_scoped_allowed_gai_family()`——**线程局部开关**仅在**受管控的东财调用**内（`_dispatch_gated` 以 try/finally 包裹，嵌套时保留并还原外层状态）置位并返回 `AF_INET`，其余情况一律交还原实现。**新浪 / 巨潮 / yfinance 等非东财请求零影响**（实测非东财解析族仍为 v4+v6、`family_arg=AF_UNSPEC`）。

---

## 4. 新增配置项（`.env` / `.env.example`）

| 配置项 | 默认值 | 作用 |
| --- | --- | --- |
| `EM_GATE_ENABLED` | 1 | 总开关，`0` = 完全退化为改造前行为（回归基线） |
| `EM_GATE_MIN_INTERVAL` | 1.2 | 两次东财请求最小间隔（秒） |
| `EM_GATE_JITTER_MAX` | 1.0 | 随机抖动上限（秒），避免固定周期指纹 |
| `EM_GATE_LOCK_TIMEOUT` | 60 | 取锁超时（秒），超时抛 `EmGateTimeout` 而非无限阻塞 |
| `EM_GATE_MAX_HOLD_SECONDS` | 8 | 单请求在锁内最大停留（秒） |
| `EM_GATE_BUDGET_PER_MIN` | 60 | 每分钟请求预算 |
| `EM_GATE_BUDGET_PER_5MIN` | 150 | 每 5 分钟请求预算 |
| `EM_GATE_CIRCUIT_THRESHOLD` | 3 | 连续封禁信号阈值 → 打开熔断 |
| `EM_GATE_CIRCUIT_COOLDOWN_MIN` | 30 | 熔断冷却时长（分钟） |
| `EM_GATE_BYPASS_PROXY` | 1 | 东财域名剥离 `HTTP(S)_PROXY` |
| `EM_GATE_HOST_FALLBACK` | 1 | `push2` / `push2his` → `push2delay` 主机回退 |
| `EM_GATE_FORCE_IPV4` | 1 | 东财请求强制 IPv4（**方案外新增**） |
| `EM_GATE_STATE_FILE` | `data/.locks/em_gate_state.json` | 跨进程状态文件 |
| `EM_GATE_LOCK_FILE` | `data/.locks/em_gate.lock` | 跨进程锁文件 |
| `EM_GATE_LOG_FILE` | `data/logs/em_gate.jsonl` | 指标日志（每请求一行） |
| `A_FINANCIAL_TTL_DAYS` | 7 | 财务缓存 TTL（步骤 3 收口补丁文档化） |

配套：`requirements.txt` 补声明 `filelock`（跨进程文件锁）。

---

## 5. 测试与验证证据

### 5.1 用例增长

| 测试文件 | 步骤 1 起点 | 步骤 4 | 步骤 5 | 步骤 6 | 步骤 6 加固 | 强制 IPv4 | **步骤 7 收口** |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `test_em_gate.py` | 23 | 30 | 35 | 40 | 41 | 44 | **44** |
| `test_source_router.py` | — | — | — | — | — | — | **19（新建）** |
| `test_stock_quote.py` | 57 | 57 | 57 | 57 | 57 | 57 | **70** |

> **口径修正说明（2026-09-30）**：`步骤 7 收口` 列原记 **52** 系**统计口径错误**——8 条 `report` 监控加固测试（方案 §9 P2）**从未落盘**（文件行数 1,487 与当日实录完全一致可证，字节数亦吻合），按代码实测应为 **44**。2026-09-30 filelock 预检修复（+2，见 §7 #10）后为 **46**；同日补写 8 条 `report` 加固测试后为 **54**（§2 交付件清单已按 2026-09-30 实测更新）。

### 5.2 回归基线（`pytest tests/common tests/a_share`）

| 时点 | 用例数 | 结果 |
| --- | --- | --- |
| 步骤 4 收口 | 约 890 | 0 failed / 0 error |
| 步骤 5 收口 | 906 | 0 failed / 0 error |
| 步骤 6 收口 | 911 | 0 failed / 0 error |
| 步骤 6 加固 | 912 | 0 failed / 0 error |
| 强制 IPv4 | 915 | 0 failed / 0 error |
| **步骤 7 收口（最终）** | **947** | **exit=0，0 failed / 0 error** |
| **2026-09-30 修正与补录** | **957** | **exit=0，0 failed / 0 error** |

> **口径修正说明（2026-09-30）**：`步骤 7 收口` 行原记 **955** 系**统计口径错误**（与 §5.1 同一成因，全仓库无 parametrize、收集数 == def 数可证），按代码实测应为 **947**。2026-09-30 补写 8 条 `report` 加固测试后全量 **957**（0 failed / 0 error，37 项既有 skip 除外）。

`tests/conftest.py` 以 `os.environ.setdefault("EM_GATE_ENABLED", "0")` 保证测试期闸门默认旁路（外部显式设置仍优先），使回归不受闸门节流影响。

### 5.3 端到端实测（真实联网）

| 场景 | 实测结果 |
| --- | --- |
| 闸门节流与封禁短路（步骤 4） | `fx_rate.py --code USDCNY` 东财 `RemoteDisconnected` → 日志 `status: ban`、`wait_s` 2.15 s ≥ 最小间隔、**未重试**、立即回退 yfinance |
| 指纹与代理（步骤 5） | 东财请求实抓 UA / `Referer: https://quote.eastmoney.com/` / `Connection: keep-alive`，`proxies` 空串化且 `select_proxy()` 返回空（**真实直连**）；新浪请求 `Referer` 为 `None`（**零注入**） |
| 主机回退（步骤 6） | 降级窗口生效时请求确实落到回退主机且 HTTP 200；窗口过期自动回主主机；开关关闭即便窗口未过期也不改写 |
| 强制 IPv4（方案外） | 东财 `family_arg=AF_INET` / 解析族 `['v4']`；非东财 `family_arg=AF_UNSPEC` / 解析族 `['v4','v6']` |
| 路由回退（步骤 7，关键） | 东财 `push2his` `RemoteDisconnected`（1.98 s，闸门按封禁**短路不重试**）→ 路由自动回退腾讯（0.81 s）→ 输出 14 条 2026-09-01~09-18 记录，`meta.source="eastmoney"` / `meta.source_actual="tencent"` / `meta.routing.attempts` 完整留痕 |
| `report --limit 0`（步骤 7） | `total_lines` / `scanned` / `truncated` / `scan_limit` / `unparsable` / `ban_rate` / `health` 齐备，相位与 `status` 一致 |
| `source_router --list`（步骤 7） | 6 条路由输出正确 |

---

## 6. 缺口覆盖对照（方案 §4 迁移清单 → 现状文档 §4 缺口）

| 缺口（现状文档 §4） | 覆盖方式 | 状态 |
| --- | --- | --- |
| #1 A股四工具裸调 akshare，零重试零间隔 | 步骤 2：四工具 `main()` 挂载闸门（传输层强制覆盖） | **已覆盖** |
| #2 `stock_financial_batch.ps1` 无调用间隔 | 步骤 2：移除脚本层 sleep，节流归闸门 + `-MaxCodes` + 盘后校验 | **已覆盖** |
| #3 `stock_equity.py` 的 `_safe_api_call` 不重试 | 步骤 4：`guarded` 外包 + 封禁短路 | **已覆盖** |
| #4 `a_stock_cache` 刷新无重试 | 步骤 4：`_fetch_em()` 区分封禁与普通错误 | **已覆盖** |
| #5 无 UA 伪装 / 代理池 / Cookie 会话复用 | 步骤 5：统一 UA / Referer / keep-alive + 代理绕过 | **已覆盖** |
| #6 无全局并发闸门（跨进程不共享） | 步骤 1：`filelock` 跨进程闸门，任一时刻至多 1 个东财请求在途 | **已覆盖** |

**方案 §4 迁移清单 13 项**：**全部落地**（含 #12 现状文档 §4 缺口表逐条标注，2026-09-28 收口，见 §9.1）。

---

## 7. 偏离与发现汇总（须报备项）

| # | 类别 | 步骤 | 内容 | 处置 |
| --- | --- | --- | --- | --- |
| 1 | 偏离 | 1~3 | §3.3 示例的扁平 JSON 字段（`allowed` / `circuit` / `remaining_min` 等）在实现中位于仓库统一三层信封 `data.*` 之下 | 保留信封一致性；编排层自检一律读 `data.allowed` / `data.circuit`；方案文档不改 |
| 2 | 偏离 | 4 | §4 #5 未列 `stock_equity.py` 装载闸门——只做业务级 `guarded` 而无 `install()` 时 transport hook 不生效 | 补 `_install_em_gate()`（fail-open） |
| 3 | 偏离 | 4 | `guarded` 需按接口限定——`_safe_api_call` 同时承载东财 `*_em` 与巨潮 `*_cninfo`，无条件外包会让东财预算耗尽**误拦巨潮调用** | 以 `_em(` 标识判定，仅东财接口纳入闸门 |
| 4 | 偏离 | 4 | `fetch_peer_pct_250d` 由「吞掉返回 None」改为**上抛**以实现整批失败即停，并修正「前半程成功 + 后半程封禁」把**截断截面**写入缓存的残留缺陷 | 新增 `stopped_by_ban` 标记，一律走 stale / 空截面降级（附 2 条回归用例） |
| 5 | 发现 | 5 | `EM_GATE_BYPASS_PROXY` 名末 6 字符恰为 `_proxy`，被 `urllib.request.getproxies_environment()` 误当代理方案注入 env 代理字典 | **无功能影响**（键名非 URL scheme，永不选中）；方案 §5 已固化变量名，**不改名**，测试改按键级断言 |
| 6 | 发现 | 5 | 既有用例 `test_5min_window_budget_blocks` 时间敏感脆弱性（滑窗 monkeypatch 1.5 s 却用绝对下限 1.2 s） | 已改为语义断言（窗口放宽至 3.0 s + 前置前提校验 + 容差 0.2 s），连跑 5 次全绿 |
| 7 | 发现 | 6 | 本机对 `push2*.eastmoney.com` 全路径（含剥离代理与全量浏览器请求头）一律 `RemoteDisconnected`，同刻 `datacenter-web` 正常 200 | 闸门正确归类为**封禁信号**（按 §2.5 不触发回退，走熔断 + 降级），**非产品缺陷** |
| 8 | 偏离 | 7 | 原定「`describe_routes()` 供 `em_gate report` 展示」改为 `source_router` 自带只读 CLI | **避免层次倒置**：`em_gate` 是传输层、`source_router` 是业务层选源，确立**单向依赖**（互不 import） |
| 9 | 偏离 | 7 | 腾讯源字段集窄于东财——仅 `date` / `open` / `close` / `high` / `low` / `volume` 六列，**缺涨跌幅 / 涨跌额 / 振幅 / 换手率 / 成交额** | **非破坏性变更**（东财与新浪字段集本就不同，既有契约即「换源则字段集随之变化」）；调用方据 `meta.routing.source` 判断字段完整性 |
| 10 | 发现 | 7 | 完成报告 §5 记录的「`test_em_gate.py` **52** 用例 / 全量 **955**」系**统计口径错误**——8 条 `report` 监控加固测试从未落盘（文件 1,487 行与实录一致可证），按代码实测应为 44 / 947 | **2026-09-30 修正**：补写 8 条 `report` 加固测试（§14，现 54 用例，全量 957 全绿）；文档 §5.1 / §5.2 数字已修正；另发现并修复 `check_budget()` 在 filelock 缺失时谎报 `allowed=true` 的同类缺口（见 `upgrade1.0/GARP升级-软件与技能升级详细计划.md` §0.7 登记（三十一）） |

---

## 8. 环境限制与现场发现（重要）

### 8.1 出口 IP 对东财 push2 主机组的应用层封禁

分层实测结论：① TCP 443 对 `push2` / `push2his` / `push2delay` **均可建立**且 TLS 握手成功（TLSv1.3），但请求发出后服务端直接关闭连接 → 表现为 `RemoteDisconnected`，即**应用层拒绝**而非网络不通；② 同一次实测内 A/B 对照显示 `push2his` 经**强制 IPv4** 可成功（HTTP 200），而 `datacenter-web` 的 IPv6 正常 → **非全局 IPv6 故障，而是 push2 主机组独有**；③ 方案 §2.5 的回退目标 `push2delay` 在本机 IPv4 / IPv6 **双双返回空响应**，即**回退目标本身不可达**（此发现直接派生了 §3.4 的回退链自愈加固）；④ 该封禁状态与更早诊断中**绕过闸门的连发约 30 次请求**有关，需时间自然衰减——这恰好**反向验证了闸门存在的必要性**。

### 8.2 处置结论（按步骤 7 实测更新）

**即使出口 IP 仍处东财 push2 封禁，A 股日线取数已由腾讯回退恢复可用**——（此前登记中「期间 A 股行情取数应走缓存 + 非 push2 类接口」的限制**部分解除**：日线可直接走腾讯源，无需缓存让位。东财其余接口（财务 / 股东 / 代码列表 / 港股财务）仍受封禁影响；其中 `hk_financial` 因**东财为唯一源**，仍须依赖 TTL 缓存 + 熔断降级，是闸门保护的重点链路。

---

## 9. 遗留事项与运维

### 9.1 遗留（无）

原披露的 1 项文档同步（[AKShare东方财富接口清单与反爬限流现状.md](AKShare东方财富接口清单与反爬限流现状.md) L7 状态更新滞后于步骤 4 / 5）已于 **2026-09-28 收口**：L7 补充收口行（#3 / #4 由步骤 4、#5 由步骤 5 兑现，#1~#6 全部覆盖），§4 缺口表按方案 §4 迁移清单 **#12** 逐条加「覆盖情况」列。**至此方案 §4 迁移清单 13 项全部落地，无遗留项。**

### 9.2 运维入口

| 操作 | 命令 |
| --- | --- |
| 并发前置自检（编排层） | `python tools/common/em_gate.py status` → 读 `data.allowed` / `data.circuit` |
| 累计计数与健康判定 | `python tools/common/em_gate.py report`（`--limit 0` 全量扫描不截断） |
| 路由表查看（只读） | `python tools/common/source_router.py --list` / `--source` |
| 清空状态 | `python tools/common/em_gate.py reset`（**默认保留日志**；需连日志一并清空时加 `--purge-log`） |

### 9.3 回退路径（方案 §8）

`EM_GATE_ENABLED=0` 一键退化为改造前行为（完全旁路）；`EM_GATE_HOST_FALLBACK=0` 关闭主机回退；`EM_GATE_FORCE_IPV4=0` 关闭强制 IPv4 并还原地址族钩子。状态文件写入均在锁内并以 `os.replace` 原子替换（沿用既有范式）。

### 9.4 明确不做（方案 §10 保持有效）

不采用「单纯调大 sleep」、「只换 UA / Cookie」、「对 403 / `RemoteDisconnected` 做指数退避重试」、「把东财网页接口当生产唯一数据源」、「仅靠业务层装饰器」、「代理池当万能方案」六类做法。

---

## 10. 预期收益兑现情况（对照方案 §11）

| 方案预期收益 | 兑现情况 |
| --- | --- |
| 消除多子代理并发下的 N 倍 QPS 叠加 | **已兑现**：跨进程 `filelock` 使出口 IP 维度全局串行，任一时刻至多 1 个东财请求在途 |
| 封禁信号即时短路 + 熔断冷却 | **已兑现**：封禁不重试（实测 1.98 s 内短路）、连续 3 次触发 30 min 冷却 + 半开单探测位 |
| A股主链路从「裸调」变为「受控」 | **已兑现**：9 个工具挂载闸门（传输层强制覆盖），批量脚本归位 |
| 业务代码改动极小，技能无破坏性变更 | **已兑现**：工具函数签名 / CLI 参数 / JSON 输出结构全部不变（仅 `meta` 追加字段） |
| 东财访问量下降 + 可观测指标 | **已兑现**：双源路由 + 缓存吸收 + `em_gate.jsonl` 每请求一行（含 `host` / `status` / `wait_s` / `circuit` / `probe` / `proxy_retry` / `degraded_host`） |

---

> **合规提示**：本改进仅用于技术学习与研究；网页私有接口不商用；生产环境应优先官方授权行情源。