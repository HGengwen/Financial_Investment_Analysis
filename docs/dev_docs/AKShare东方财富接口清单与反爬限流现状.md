# AKShare 东方财富接口清单与反爬限流现状

> 状态：现状盘点（2026-09-21）
> 盘点范围：`tools/a_share/`、`tools/hk_stock/`、`tools/us_stock/`、`tools/common/`、`tools/specialized/` 全部 akshare 调用点
> 数据源归属依据：**逐一核对 akshare 安装包源码**（`F:\Anaconda3\envs\Python_3_12_3\Lib\site-packages\akshare\`），不按函数名后缀臆测
> 注意：本文仅记录**现状**，不含改造方案

---

## 1. 东方财富接口清单（akshare → 东财）

| # | akshare 函数 | 东财后端模块 | 项目调用点 | 上层入口 |
| --- | --- | --- | --- | --- |
| 1 | `stock_zh_a_hist(symbol, period, start_date, end_date, adjust)` | push2his K线 `stock_feature/stock_hist_em.py` | `tools/a_share/stock_quote.py:82` | `stock_quote.py` 默认 / `--source eastmoney` |
| 2 | `stock_zh_index_daily_em(symbol)` | 东财指数 `index/index_stock_zh.py` | `tools/a_share/stock_quote.py:369` | `stock_quote.py --index` |
| 3 | `stock_yjbb_em(date)` | 东财数据中心-业绩报表 `stock_feature/stock_yjbb_em.py` | `tools/a_share/stock_info.py:80`、`stock_financial.py:462`、`stock_screen.py:573`、`tools/common/a_stock_cache.py:286` | 行业映射、去劣筛选、缓存刷新 |
| 4 | `stock_individual_info_em(symbol)` | 东财个股概况 `stock/stock_info_em.py` | `tools/a_share/stock_info.py:157` | `stock_info.py --code` |
| 5 | `stock_research_report_em(symbol)` | 东财研报 `stock_feature/stock_research_report_em.py` | `tools/a_share/stock_info.py:249` | `stock_info.py --reports` |
| 6 | `stock_gdfx_top_10_em(symbol, date)` | 东财十大股东 | `tools/a_share/stock_equity.py:166`、`:173` | `stock_equity.py` |
| 7 | `stock_gdfx_free_top_10_em(symbol, date)` | 东财十大流通股东 | `tools/a_share/stock_equity.py:214`、`:221` | `stock_equity.py` |
| 8 | `stock_financial_hk_analysis_indicator_em(symbol, indicator)` | 东财港股财务指标 | `tools/hk_stock/stock_financial.py:178`、`tools/hk_stock/stock_screen.py:44` | 港股财务 / 筛选 |
| 9 | `stock_financial_hk_report_em(stock, symbol, indicator)` | 东财港股三大报表 | `tools/hk_stock/stock_screen.py:107`、`:136` | 港股质量筛选 |
| 10 | `stock_hk_hot_rank_em()` | 东财港股人气榜 `stock/stock_hk_hot_rank_em.py` | `tools/hk_stock/stock_info.py:256` | `stock_info.py --hot` |
| 11 | `bond_zh_us_rate()` | 东财数据中心-中美国债收益率 `bond/bond_em.py` | `tools/specialized/macro_calibrator.py:466` | `macro_calibrator.py data` |
| 12 | `forex_hist_em(symbol)` | 东财外汇 `forex/forex_em.py` | `tools/common/fx_rate.py:327`（仅 secid 解析失败时回退） | `fx_rate.py` |
| 13 | **直连** `https://push2his.eastmoney.com/api/qt/stock/kline/get` | 东财 push2his | `tools/common/fx_rate.py:329-342` | `fx_rate.py` 主路径 |

### 1.1 易混淆、实际**非**东财的接口

| akshare 函数 | 真实数据源 | 判定依据 |
| --- | --- | --- |
| `stock_info_a_code_name()` | **上交所 + 深交所 + 北交所官网** | `stock/stock_info.py:447-461` 调 `stock_info_sh_name_code` / `_sz_` / `_bj_` |
| `stock_zh_a_spot()` / `stock_zh_a_daily` | 新浪 | `stock/stock_zh_a_sina.py` |
| `stock_financial_abstract` / `stock_financial_report_sina` | 新浪 | `stock_fundamental/stock_finance_sina.py` |
| `stock_hk_spot` / `stock_hk_daily` / `stock_hk_index_daily_sina` | 新浪 | `stock/stock_hk_sina.py` |
| `stock_zh_valuation_baidu` / `stock_hk_valuation_baidu` | 百度 | `stock_feature/stock_zh_valuation_baidu.py` |
| `stock_profile_cninfo` / `stock_share_change_cninfo` | 巨潮资讯 | `tools/a_share/stock_equity.py:258`、`:296` |
| `stock_ipo_info` | **待核实** | akshare 源码未取得 URL，不臆断 |

---

## 2. 反爬 / 限流 / 重试措施

| 措施 | 具体实现 | 位置 |
| --- | --- | --- |
| **最小调用间隔限流器** | `_RateLimiter`，`_MIN_INTERVAL = 0.5s`，模块级单例 `_RATE_LIMITER.wait()` 在每次 API 调用前阻塞 | `tools/common/fx_rate.py:93`、`:150-175` |
| **指数退避重试** | `_call_with_retry`：`_MAX_RETRIES = 3`、`_BACKOFF_BASE = 1.0` → 等待 1s / 2s / 4s | `tools/common/fx_rate.py:230-274` |
| **瞬时 vs 非瞬时判定** | 仅 `requests.exceptions.RequestException` 重试；`KeyError` 等参数类错误立即抛出 | `tools/common/fx_rate.py:178-193` |
| **封禁信号识别（关键）** | `_is_ban_signal`：`RemoteDisconnected` / 文本「Remote end closed connection」/ HTTP 403 → **立即放弃重试直接回退下一源**（封禁期间重试会延长封禁） | `tools/common/fx_rate.py:196-227` |
| **小请求替代大请求** | 自建 `_eastmoney_hist_small`：绕过 akshare 默认 `lmt=50000`，只取 `lmt=10` 条 + `fields2=f51,f53`（仅日期 + 收盘价），请求/响应体最小化 | `tools/common/fx_rate.py:302-351` |
| **记录数硬上限** | `MAX_RECORDS_HARD_LIMIT`（默认 50，`.env` → `FX_MAX_RECORDS_HARD_LIMIT=50`），超出裁剪并告警 | `tools/common/fx_rate.py:104-107` |
| **批量调用节流** | `BATCH_CALL_INTERVAL = 1.0s`、`MAX_BATCH_SIZE = 5`；大宗商品为 10 品种、品种间隔 1s、yfinance 间隔 2s | `tools/common/fx_rate.py:108-111`、`tools/common/commodity_price.py:7-12` |
| **HTTP 级重试 + 伪装头** | `_http_get_with_retry(retries=3)`，退避 `1.5 × attempt`（线性），**4xx 不重试**；配 `User-Agent` + `Referer: cninfo`；PDF 逐条 `sleep(1.2)` | `tools/a_share/stock_equity.py:388-425`、`:457-459`、`:853` |
| **`safe_api_call` 重试封装** | 默认 `max_retries=3, delay=2.0`（固定间隔） | 港股：`tools/hk_stock/stock_info.py:51`、`stock_financial.py:66`、`stock_quote.py:76`；美股 `tools/us_stock/` 三文件同款 |
| **本地缓存降级（主力手段）** | `hit → refresh → stale` 三态：TTL 内零网络调用；过期刷新失败降级旧缓存并标注 `stale`；原子写 `.tmp` + `os.replace`；CSV 损坏视为 miss | `tools/common/a_stock_cache.py:12-21`、`:129-155` |
| **双源策略主动绕开东财** | ① A股实时行情改用新浪 `stock_zh_a_spot`（东财 push2 实时接口在大陆网络下 `RemoteDisconnected`）；② 板块截面批量拉 250 日涨幅时新浪优先（深沪稳定、批量不易限流） | `tools/a_share/stock_quote.py:443-447`、`tools/common/sector_screen.py:230-245` |

### 2.1 缓存 TTL 一览

| 配置项 | 默认值 | 现网 `.env` | 覆盖对象 |
| --- | --- | --- | --- |
| `STOCK_CACHE_TTL_DAYS` | 7 天 | **30** | A股代码/名称、行业映射（并沿用为港股/美股代码列表 TTL） |
| `A_FINANCIAL_TTL_DAYS` | 7 天 | — | A股 per-stock 财报（`data/a_share/financial/`） |
| `_SECTOR_TTL_DAYS`（硬编码） | 7 天 | — | 板块截面（`data/a_share/sector/{行业}.json`） |
| `HK_FINANCIAL_TTL_DAYS` | 7 天 | — | 港股三大报表 |
| `US_STOCK_INFO_TTL_DAYS` | 1 天 | 1 | 美股慢变字段 |
| `MACRO_CACHE_TTL_DAYS` | 7 天 | 7 | 宏观指标快照 |

> 搜索类工具另有客户端 QPS 限流（`ANYSEARCH_MAX_QPS=20`、`VOLC_QPS=5`），**与东财链路无关**，不计入本文。

---

## 3. 已知封禁信号与项目内结论

| 出处 | 原文摘录 |
| --- | --- |
| `tools/common/a_stock_cache.py:9-10` | 「规避 akshare 限流 —— 大幅减少对 `stock_info_a_code_name` / `stock_yjbb_em` 的调用次数（akshare 的 `RemoteDisconnected` 即服务端封禁信号）」 |
| `tools/common/fx_rate.py:199-201` | 「东方财富对高频调用会临时封禁 IP，典型表现为 `RemoteDisconnected`（连接被服务端直接断开）。封禁期间重试毫无意义且会延长封禁时长」 |
| `tools/a_share/stock_quote.py:446-447` | 「东财 push2 实时接口（`stock_bid_ask_em` / `stock_zh_a_spot_em`）在中国大陆网络下连接不稳定（`RemoteDisconnected`），故以新浪 `stock_zh_a_spot` 为主源」 |
| `tools/common/sector_screen.py:230` | 「双源策略（规避东财批量拉取限流）：新浪 `stock_zh_a_daily` 优先（深沪稳定）」 |
| `tools/hk_stock/stock_info.py:180` | 「使用新浪接口获取港股实时行情（东方财富接口经常被限流）」 |
| `tools/a_share/stock_quote.py:423-424`、`:614-615` | 异常文本含 `Connection` / `RemoteDisconnected` 时统一转译为「网络连接失败（东方财富不可达）」 |

**小结**：项目已形成的共识是——**东财 = 限流风险源，新浪/交易所官网 = 稳定源**；对东财的策略是「能绕则绕（双源）+ 必须用时缩小请求（lmt=10）+ 缓存吸收（TTL）+ 识别封禁即退（不重试）」。

---

## 4. 缺口（当前**没有**防护的地方）

| # | 缺口 | 证据 |
| --- | --- | --- |
| 1 | **A股四工具裸调 akshare，零重试、零间隔**：`stock_quote.py`、`stock_info.py`、`stock_financial.py`、`stock_screen.py` 除调用外无任何 `sleep` / 退避 / 重试 | 全仓 `tools/a_share/` 仅 `stock_equity.py` 有两处 sleep（`:422`、`:853`） |
| 2 | **`stock_financial_batch.ps1` 批量脚本无调用间隔**：串行调用 `stock_financial.py`，脚本内无 `Start-Sleep`，多代码批量时对东财为连续突发 | `tools/a_share/stock_financial_batch.ps1` |
| 3 | **`stock_equity.py` 的 `_safe_api_call` 不重试**：失败仅记入 `api_results` 并返回 `None`；重试只存在于其自建 HTTP 层，akshare 调用层无 | `tools/a_share/stock_equity.py:125-147` |
| 4 | **`a_stock_cache` 刷新无重试**：`ak.stock_info_a_code_name()` / `stock_yjbb_em()` 直接调用，失败即降级 `stale` | `tools/common/a_stock_cache.py:264`、`:418` |
| 5 | **无 UA 伪装 / 代理池 / Cookie 会话复用**（东财链路）：`fx_rate.py` 直连东财用 `requests.get` **不带任何 headers**，等同 akshare 默认 UA | `tools/common/fx_rate.py:342` |
| 6 | **无全局并发闸门**：限流器为模块级单例，**跨进程不共享**；并发跑多个工具时对东财的实际 QPS 叠加 | `tools/common/fx_rate.py:175` |

---

## 5. 结论

限流防护呈**点状分布**而非体系化：只有 `fx_rate.py`（汇率）与 `stock_equity.py`（股权/公告）两条链路具备完整的「限流 + 退避重试 + 封禁短路」，其余 A股主链路完全依赖 `a_stock_cache` 的 TTL 缓存吸收压力，一旦缓存冷启动或强制刷新，东财接口（尤其 `stock_yjbb_em` 全市场业绩报表）会被连续裸调。

收益最高的一处补强方向：将 `fx_rate.py` 的「最小间隔 + 指数退避 + 封禁短路」抽为 `tools/common/` 下的共享装饰器，统一挂到 A股四工具与批量脚本上（本文不含实施方案，仅记录现状）。