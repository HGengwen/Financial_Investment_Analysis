# AKShare 东方财富反爬限流改进方案

> 状态：**方案（未实施）**（2026-09-21）
> 上游现状：[AKShare东方财富接口清单与反爬限流现状.md](AKShare东方财富接口清单与反爬限流现状.md)
> 外部参考：efinance 社区实战沉淀（跨进程文件锁全局限流 / 403 不重试 / 代理失败回直连 / push2→push2delay 主机回退 / SEC UA 身份声明）
> 适用规模：**单机多进程**（多子代理并行）为主，预留多机扩展点

---

## 0. 前置事实核查（决定方案骨架）

| 核查项 | 实测结果 | 结论 |
| --- | --- | --- |
| 并发形态 | 技能中「N 路 Agent 并行」= **N 个独立 Python 进程**（子代理每次 tool call 走 shell 起进程） | 进程内限流器**完全失效**，N 倍 QPS 叠加；这是子代理场景下的**常态**而非例外 |
| akshare HTTP 形态 | `requests.get(` **1125 处**、`requests.post(` 181 处、`requests.Session(` 仅 19 处 | 业务层装饰器覆盖率取决于是否漏改；**`requests` 层 host 过滤注入是唯一能保证 100% 覆盖的点** |
| 本机依赖 | `filelock 3.18.0`、`redis 7.1.0`、`fakeredis 2.33.0`、`curl_cffi 0.15.0`、`tenacity 9.1.2` **均已安装**，但 **`requirements.txt` 未声明**（属传递依赖） | 跨进程锁用 `filelock`，不必手写 `fcntl`/`msvcrt`；实施时须补声明 |
| 现有配置 | `.env.example` 无任何代理 / 闸门 / 冷却类配置项 | 需新增配置组 |

### 0.1 社区风控阈值（供预算设定参考）

| 行为 | 触发封禁阈值 | 本方案客户端预算（留 ≥3 倍余量） |
| --- | --- | --- |
| 每秒请求数 | > 5 次/秒 | ≤ 0.8 次/秒（最小间隔 1.2s + 抖动） |
| 单 IP 并发连接 | ≥ 10 | **1**（闸门强制串行，任一时刻至多一个东财请求在途） |
| 1 分钟请求总数 | ≥ 200 次 | ≤ 60 次 |
| 5 分钟请求总数 | ≥ 300 次 | ≤ 150 次 |

---

## 1. 架构：两层闸门 + 一个注入点

```
[子代理进程 × N]                                        ← N 个独立进程同时打东财
      │
      │  ① 业务层：em_gate.call() / @em_gate.guarded   ← 缓存优先 / 预算预检 / 降级语义
      ▼
[tools/a_share/*.py 裸调 ak.xxx()]                      ← 业务代码零改写
      │
      │  ② 传输层：em_gate.install()  host 过滤 hook     ← 强制覆盖，漏改也不失守
      ▼
┌─────────────────────────────────────────────────┐
│ 跨进程闸门（filelock + state.json + 熔断器）      │
│  · 全局限流：≤1 在东财请求、最小间隔 + 抖动        │
│  · 预算：分钟 / 5 分钟滑窗                        │
│  · 熔断：连续封禁 → 冷却窗口                       │
│  · 指纹：统一 UA / Referer / keep-alive           │
│  · 主机回退 / 代理绕过                            │
└─────────────────────────────────────────────────┘
      ▼
[push2his.eastmoney.com / push2delay.eastmoney.com / datacenter-web.eastmoney.com]
```

设计要点（与两份草稿的差异，均为实测后修正）：

1. **锁粒度 = 单个 HTTP 请求，而非逻辑调用**。akshare 的 `stock_yjbb_em` 等接口内部会**翻页发多次请求**，若按逻辑调用持锁并 enforce 间隔，内部翻页仍会以毫秒级连发；按请求粒度持锁才能让翻页也被节流。因此**不需要可重入锁**。
2. **锁内不做退避重试**。锁内只做「节奏 sleep」（≤ 最小间隔 + 抖动，硬上限 3s）；重试与退避一律在锁外。否则一个进程重试 4 次会长时间占锁，其余 N-1 个子代理全线阻塞。
3. **熔断短路发生在取锁之前**。冷却期内直接抛 `EmCircuitOpen`，连锁都不取，避免 N 个进程排队等一个注定失败的请求。
4. **传输层 hook 是承重件**，不是辅助。业务层装饰器只是「语义层」（缓存优先、降级返回），不承担覆盖率责任。

---

## 2. 新增组件：`tools/common/em_gate.py`

### 2.1 对外接口

| 接口 | 签名 | 用途 |
| --- | --- | --- |
| `install()` | `() -> None` | 装载 host 过滤 transport hook（幂等）。各工具 `main()` 首行调用 |
| `is_ban_signal(exc)` | `(BaseException) -> bool` | 从 `fx_rate.py:196-227` **迁出**，403 / `RemoteDisconnected` / 「Remote end closed connection」 |
| `is_transient(exc)` | `(BaseException) -> bool` | 从 `fx_rate.py:178-193` **迁出**，仅 `requests.exceptions.RequestException` |
| `guarded(fn, *, api, cache_first)` | 装饰器 / 包装器 | 业务层：缓存优先 → 预算预检 → 调用 → 封禁短路 → 降级标注 |
| `check_budget()` | `() -> BudgetReport` | **编排层预检**：`{allowed: bool, reason: str, circuit: "closed/open/half_open", remaining_min: int}` |
| `status()` / `report()` / `reset()` | CLI 子命令 | 观测与运维 |

### 2.2 跨进程状态文件

`data/.locks/em_gate_state.json`（闸门持有锁期间读写，原子 `os.replace`）：

```json
{
  "last_request_ts": 1789870000.123,
  "recent_ts": [1789869900.1, 1789869912.4],
  "consecutive_ban": 0,
  "circuit_open_until": 0,
  "half_open_probe_used": false,
  "hot_host": "push2his.eastmoney.com",
  "host_degraded_until": 0,
  "totals": {"calls": 0, "ban": 0, "stale": 0, "degraded": 0}
}
```

### 2.3 加锁协议（`filelock`，`data/.locks/em_gate.lock`）

```
def _before_request(url):
    1) 熔断检查：now < circuit_open_until → raise EmCircuitOpen（不取锁）
       half_open 且已用过探测位 → raise EmCircuitOpen
    2) lock.acquire(timeout=EM_GATE_LOCK_TIMEOUT=60s)   # 失败 → raise EmGateTimeout
    3) state = read_state()
    4) wait = max(
           min_interval + uniform(0, jitter),                # 节奏：1.2s + U(0,1.0)
           分钟滑窗约束: (now - recent_ts[-60]) 补足,
           5 分钟滑窗约束: (now - recent_ts[-150]) 补足,
       )
       if wait > 3.0: 放弃本次取锁并退避重试（防长占锁）；else sleep(wait)
    5) 注入指纹：UA / Referer: https://quote.eastmoney.com/ / Connection: keep-alive
       剥离代理：proxies={} （EM_GATE_BYPASS_PROXY=1）
    6) return token                     # 锁在响应后释放

def _after_request(url, token, exc):
    1) 写回 state：append now → recent_ts（裁剪 >5min）；last_request_ts = now
    2) 异常分类：
       is_ban_signal → consecutive_ban += 1；若 ≥ 阈值 → circuit_open_until = now + cooldown
       is_transient 且为主机连接类错误 → 主机回退候选计数 +1
    3) append `data/logs/em_gate.jsonl` 一行指标
    4) os.replace(state)  →  lock.release()
```

### 2.4 transport hook（host 过滤，可开关）

挂载点：包装 `requests.get` / `requests.post` / `requests.Session.request`（一次安装，全局生效）。

```python
_EM_HOST_RE = re.compile(r"(^|\.)eastmoney\.com(\.cn)?$")

def _patched_request(orig):
    def wrapper(*args, **kwargs):
        if not EM_GATE_ENABLED or not _is_em_url(kwargs.get("url") or args[0]):
            return orig(*args, **kwargs)        # 非东财：原样透传，零影响
        ...  # 进入 §2.3 的 _before_request → orig → _after_request
    return wrapper
```

**为什么安全**：仅对 `*.eastmoney.com` 生效，新浪 / 百度 / 巨潮 / yfinance / 东财以外的请求完全透传；响应体不做任何改写；`EM_GATE_ENABLED=0` 一键回退。

### 2.5 主机回退链

| 主主机 | 回退主机 | 触发条件 | 备注 |
| --- | --- | --- | --- |
| `push2his.eastmoney.com` | `push2delay.eastmoney.com` | 连续 2 次连接类错误（**非**封禁信号） | 字段与时间字段兼容，数据延迟 |
| `push2.eastmoney.com` | `push2delay.eastmoney.com` | 同上 | 对应现状文档缺口⑤ |

- 命中后写 `host_degraded_until = now + 10min`，期内**直接走回退主机**，不再重试死主机（避免每次请求都先失败一次）。
- 封禁信号（403 / `RemoteDisconnected`）**不触发回退**——封禁是全站级的，换主机无用，直接走熔断 + 降级。
- 回退形态与双源降级是两条独立防线：主机回退保「同源可用性」，双源降级保「换源可用性」。

---

## 3. 多子代理并发场景专项设计（本方案重点）

### 3.1 关键认知：并行的是推理，不是东财 QPS

技能中「四 Agent 并行」「六路 Agent 并行」指**推理并行**。若每个子代理都并发打东财，实际出口 IP 的 QPS 是 N 倍。方案须在文档层面把这句话写实：

> **子代理可并行做搜索、文档解析、财报读文；东财数据获取由闸门强制串行。**

### 3.2 进程外闸门（不可省略）

`filelock` 保证跨进程互斥，**任一时刻至多 1 个东财请求在途**，N 个子代理在锁上排队。这是唯一能覆盖「N 进程同时跑」的机制；任何进程内方案（含单纯加大 sleep）在子代理场景下都是无效的。

### 3.3 预算预检 + 编排层「第 0 步自检」

新增 CLI：`python tools/common/em_gate.py status`，输出：

```json
{"circuit": "closed", "last_request_ago_s": 3.2,
 "remaining_min": 47, "remaining_5min": 138, "allowed": true}
```

- **编排层**：在技能/工作步骤文档的「并行起 N 个 Agent」之前插入一步「东财闸门自检」；`allowed=false` 或 `circuit=open` 时，编排器改为**串行执行**或**延后到盘后**。
- **子代理层**：重活（`stock_yjbb_em` 全市场业绩报表）调用前跑 `check_budget()`；预算不足则优先读缓存、只对目标标的做定向取数。

### 3.4 降级语义统一（避免子代理死等）

闸门拒绝（`EmCircuitOpen` / `EmGateTimeout`）时，**所有工具禁止返回 `"success": true` 的伪造数据**，统一返回：

```json
{
  "success": false,
  "error": "东财闸门拒绝：熔断冷却中（剩余 24 分钟）",
  "meta": {
    "gate": "circuit_open",
    "stale": true,
    "cache_age_days": 3,
    "fallback_cmd": "python tools/a_share/stock_quote.py --code 600519 --source sina"
  }
}
```

子代理据此立即改用备用源继续（新浪 / 巨潮 / 交易所官网），而不是阻塞重试。**降级必须自带可执行的替代命令**，否则子代理无从下手。

### 3.5 单 skill 并发上限建议

| 场景 | 建议 |
| --- | --- |
| 六路 Agent 并行（如 `garp-private-company-research`） | 允许并行；东财调用由闸门串行，预期耗时 ≈ 请求数 × 1.2s |
| 五 Agent 并行财报精读（如 `garp-earnings-team`） | 同标的财报**先取数后分发给子代理**（一次取数，多代理共用），禁止 5 个代理各取一遍 |
| 行业漏斗（30-60 家粗筛） | **禁止**逐家裸调；必须走 `a_stock_cache` 缓存 + 批量脚本，且仅在盘后执行 |
| 冷启动首次全量刷新 | 分片 + 休眠，禁止一次性触发全部网络请求 |

### 3.6 批量脚本侧约束

`tools/a_share/stock_financial_batch.ps1`：

- 节流交给闸门（脚本层不再自行 sleep，避免双重节流与不可控）；
- **失败即停**：检测到封禁信号 → 立即中止整批并打印 `fallback_cmd`，不再继续下一个标的（当前是逐标的继续）；
- 增加 `-MaxCodes` 软上限与盘后时段校验（交易时段拒绝跑全市场批量）。

---

## 4. 迁移清单（精确到文件与行号）

| # | 文件 | 改动 | 侵入度 |
| --- | --- | --- | --- |
| 1 | `tools/common/em_gate.py` | **新建**（§2 全部能力） | — |
| 2 | `tools/common/fx_rate.py` | `_MIN_INTERVAL:93`、`_RateLimiter:150-175`、`_RATE_LIMITER:175` → 保留符号，内部委托 `em_gate`；`_is_transient:178-193`、`_is_ban_signal:196-227` → 迁至 em_gate 并 re-import；`_call_with_retry:230-274` 保留；直连 `requests.get:342` → 走闸门 Session | 中 |
| 3 | `tools/a_share/stock_quote.py`、`stock_info.py`、`stock_financial.py`、`stock_screen.py` | `main()` 首行加 `em_gate.install()`（**各 1 行**）；业务逻辑零改写 | 极低 |
| 4 | `tools/hk_stock/stock_financial.py`、`stock_screen.py`、`stock_info.py` | 同上（`*_em` 港股接口同属东财） | 极低 |
| 5 | `tools/a_share/stock_equity.py` | `_safe_api_call:125-147` 外包 `em_gate.guarded`；`_http_get_with_retry:388-425` 的 4xx 短路改调 `em_gate.is_ban_signal` | 低 |
| 6 | `tools/common/a_stock_cache.py` | 拉取函数（`:264`、`:418` 降级路径）外包 `guarded`；失败时**区分封禁与普通错误**——封禁直接 `stale` 不重试，普通错误短退避重试 1 次 | 低 |
| 7 | `tools/common/sector_screen.py` | 同 #6（截面批量拉取是东财批量请求来源之一） | 低 |
| 8 | `tools/a_share/stock_financial_batch.ps1` | §3.6（失败即停 + 盘后校验 + 去掉脚本层 sleep） | 低 |
| 9 | `.env` / `.env.example` | 新增 §5 配置组 | — |
| 10 | `requirements.txt` | 补声明 `filelock`（已安装，仅缺声明） | — |
| 11 | `tests/common/test_em_gate.py` | **新建**（§7 测试矩阵） | — |
| 12 | `docs/dev_docs/AKShare东方财富接口清单与反爬限流现状.md` | §4 缺口表逐条标注「已由本方案 §X 覆盖」 | — |
| 13 | `CLAUDE.md`「工作规范」 | 增加一条：东财取数统一经闸门，禁止裸调；并行 Agent 前先跑闸门自检 | — |

**核心承诺**：业务工具的函数签名、CLI 参数、JSON 输出结构**全部不变**，65 个技能无需改动（仅技能文档新增「第 0 步闸门自检」说明）。

---

## 5. 新增配置项（`.env` / `.env.example`）

```ini
# --- 东财请求闸门（em_gate）---
EM_GATE_ENABLED=1                    # 总开关，0=完全退化为改造前行为
EM_GATE_MIN_INTERVAL=1.2             # 两次东财请求最小间隔（秒）
EM_GATE_JITTER_MAX=1.0               # 随机抖动上限（秒），避免固定周期指纹
EM_GATE_LOCK_TIMEOUT=60              # 取锁超时（秒），超时抛 EmGateTimeout 而非无限阻塞
EM_GATE_MAX_HOLD_SECONDS=8           # 单请求在锁内最大停留（秒）
EM_GATE_BUDGET_PER_MIN=60            # 每分钟请求预算
EM_GATE_BUDGET_PER_5MIN=150          # 每 5 分钟请求预算
EM_GATE_CIRCUIT_THRESHOLD=3          # 连续封禁信号阈值 → 打开熔断
EM_GATE_CIRCUIT_COOLDOWN_MIN=30      # 熔断冷却时长（分钟）
EM_GATE_BYPASS_PROXY=1               # 东财域名剥离 HTTP(S)_PROXY（国内域名直连更稳）
EM_GATE_HOST_FALLBACK=1              # push2/push2his → push2delay 主机回退
EM_GATE_STATE_FILE=data/.locks/em_gate_state.json
EM_GATE_LOCK_FILE=data/.locks/em_gate.lock
EM_GATE_LOG_FILE=data/logs/em_gate.jsonl
```

---

## 6. 替代数据源路由强化（从源头减量）

现状文档已部分实现新浪优先，方案将其统一为**显式优先级路由**：

| 数据 | 优先级 | 说明 |
| --- | --- | --- |
| A股实时行情 | 新浪 → 东财 | 已实现（`stock_quote.py:443-447`） |
| A股日线 | 东财 `stock_zh_a_hist` → 腾讯/新浪 | 新增腾讯回退（社区成熟实践） |
| 全 A 代码列表 | 上交所/深交所/北交所官网 → 东财 | 现状已是交易所官网（`stock_info_a_code_name`），保持 |
| 财报 / 股东 | 巨潮资讯 → 东财 | 现状 `stock_equity.py` 已双源 |
| 港股行情 | 新浪 → 东财 | 现状已实现 |
| 港股财务 | 东财 `*_hk_*_em`（**唯一源**） | 无替代源 → **必须**受闸门保护，并延长 TTL |

> 原则：**东财定位为降级备胎而非第一主源**，从源头减少访问量；无替代源的港股财务链路是闸门保护的重点。

---

## 7. 测试矩阵（`tests/common/test_em_gate.py`）

| 类别 | 用例 | 断言 |
| --- | --- | --- |
| 跨进程限流 | `multiprocessing` 起 5 进程 × 各 4 次请求（tmp_path 隔离 lock/state） | 实际相邻请求间隔 ≥ `MIN_INTERVAL`；总请求在途数恒为 1；分钟预算不超 |
| 滑窗预算 | 单进程连打 70 次 | 第 61 次起被预算阻塞 |
| 封禁短路 | mock 抛 `RemoteDisconnected` | **不重试**；`consecutive_ban` +1 |
| 熔断 | 连续 3 次封禁信号 | `circuit_open_until` 写入；第 4 次**不取锁**直接抛 `EmCircuitOpen`；冷却后放行 1 个探测位 |
| 主机回退 | mock 主主机连接异常 ×2 | 切 `push2delay`；写 `host_degraded_until`；期内不再试死主机 |
| 代理绕过 | 设 `HTTP_PROXY` | 东财请求 `proxies` 为空；非东财请求代理不变 |
| 指纹 | 抓取实际 headers | UA / `Referer: quote.eastmoney.com` 注入且不覆盖调用方显式 headers |
| host 过滤 | 新浪 / 百度 / 巨潮 URL | 完全透传，不取锁、不计预算 |
| 降级语义 | 熔断打开时调用业务工具 | `success=false` + `meta.gate=circuit_open` + `fallback_cmd` 非空；**无伪造数据** |
| 开关回退 | `EM_GATE_ENABLED=0` | 行为与改造前完全一致（回归基线） |
| 指标 | 读 `em_gate.jsonl` | 每请求一行，字段完整 |

---

## 8. 风险与回退

| 风险 | 缓解 |
| --- | --- |
| monkey-patch 全局 `requests` 影响面不可控 | host 白名单过滤（仅 `*.eastmoney.com`）+ 不改写响应 + `EM_GATE_ENABLED=0` 一键关停 |
| 闸门串行拉长子代理总耗时 | 缓存优先 + 预算预检 + 降级语义兜底；量化：5 子代理 × 8 请求 × 1.2s ≈ 50s，可接受 |
| 锁竞争导致死锁 / 长阻塞 | 锁内硬上限 8s、取锁超时 60s 抛类型化异常而非无限等待；退避重试一律在锁外 |
| 熔断误判（把网络抖动当封禁） | 仅 403 / `RemoteDisconnected` / 明确文本计入；普通超时不计数（走重试） |
| 新增依赖 | `filelock` 已在本机安装，仅需补 `requirements.txt` 声明 |
| 状态文件被并发写坏 | 锁内写 + `os.replace` 原子替换（沿用 `a_stock_cache` 既有范式） |

---

## 9. 实施路线图

| 阶段 | 内容 | 对应缺口 | 工作量 |
| --- | --- | --- | --- |
| **P0** | `em_gate.py` 骨架：跨进程文件锁 + 最小间隔 + 抖动 + 预算 + 封禁短路 + transport hook；挂载 A股四工具 / 港股财务 / 批量脚本；配置项 + `requirements.txt` | ①②⑥ | 中 |
| **P0** | 降级语义统一（`success=false` + `fallback_cmd`）与编排层「第 0 步闸门自检」写入技能文档 | ①⑥ | 小 |
| **P1** | 熔断器（冷却窗口 + 半开探测）；`is_ban_signal` / `is_transient` 迁出共享；接入 `stock_equity.py`、`a_stock_cache.py`、`sector_screen.py` | ③④ | 中 |
| **P1** | 统一 UA / Referer / keep-alive；代理绕过 + 代理失败直连重试（仅连接类错误） | ⑤ | 中 |
| **P2** | 主机回退链（push2/push2his → push2delay），先接 `fx_rate.py` 与 A股日线 | — | 小 |
| **P2** | 监控 `em_gate report` + 数据源路由统一函数 | — | 小 |
| **P3（预留）** | 多机部署时切换 Redis 令牌桶（`redis` + `fakeredis` 已在环境内，改造仅换 `_acquire` 实现） | — | 小 |

---

## 10. 明确不做的方案（踩坑点）

1. ❌ **单纯调大 sleep** —— 多进程下 QPS 仍叠加，对子代理场景无效；
2. ❌ **只换 UA / Cookie** —— 东财以 IP 做全局限流，指纹只是辅助；
3. ❌ **对 403 / `RemoteDisconnected` 做指数退避重试** —— 会加重惩罚、延长封禁（项目已有此结论，不得引入通用爬虫重试模板）；
4. ❌ **把东财网页接口当生产唯一数据源** —— 接口随时改版，无 SLA；
5. ❌ **仅靠业务层装饰器** —— akshare 内部 1125 处 `requests.get` 无法逐一覆盖，漏改即失守；
6. ❌ **代理池当万能方案** —— 代理只解 IP 封禁，不解行为风控，且引入新的失败面。

---

## 11. 预期收益

1. 多子代理并发下的 N 倍 QPS 叠加被消除（**出口 IP 维度**全局串行，非进程内）；
2. 封禁信号即时短路 + 熔断冷却，不再持续无效请求加重惩罚；
3. A股主链路从「裸调」变为「受控」，冷启动 / 强制刷新不再瞬时爆发；
4. 业务代码改动极小（工具各 1 行 install），65 个技能无破坏性变更；
5. 东财访问量下降（双源路由 + 缓存吸收 + 小请求），并具备可观测指标。

> **合规提示**：本方案仅用于技术学习与研究；网页私有接口不商用；生产环境应优先官方授权行情源。