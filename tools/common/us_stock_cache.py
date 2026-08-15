#!/usr/bin/env python3
"""美股股票代码列表与慢变字段本地缓存模块（美股数据缓存）。

本模块位于 tools/common/ 目录下，为美股数据工具（stock_info 等）提供：

1. 全部美股「代码/名称/交易所」列表的本地 CSV 缓存，数据源为 NASDAQ
   Trader 官方文件（nasdaqlisted.txt + otherlisted.txt，约 11000 只），
   避免每次查询都调用外部接口下载全量列表；
2. 「慢变字段」本地缓存（公司名称、市值、PE、PB、股息率、Beta、ROE、
   ROA、52 周高低等），用于 yfinance 接口限流（HTTP 429）或断连时
   的估值数据降级兜底。

数据源（列表，按优先级逐源尝试）：
    1. NASDAQ Trader 官网（nasdaqlisted.txt + otherlisted.txt，主源）
    2. NASDAQ 官方 screener API（api.nasdaq.com，备源，JSON）
    3. .env 配置的自定义镜像（US_TICKER_MIRROR_URLS，逗号分隔）
    4. 旧缓存降级（stale）/ 无缓存时抛 RuntimeError

列表解析要点（管道分隔文件）：
- 表头为第一行，末尾 File Creation Time 时间戳行按列数校验过滤
- 过滤测试股（Test Issue == "Y"）
- otherlisted 按 Exchange 列映射交易所（N=NYSE, A=NYSE American,
  P=NYSE Arca, Z=BATS, V=IEXG）
- 生成 yf_symbol 列（点号替换为连字符，兼容 yfinance，如 BRK.B → BRK-B）

配置项（.env，可选项）：
- STOCK_CACHE_TTL_DAYS：列表缓存有效期天数（默认 7 天）
- US_STOCK_INFO_TTL_DAYS：慢变字段缓存有效期天数（默认 1 天）
- US_TICKER_MIRROR_URLS：自定义镜像 URL 列表（逗号分隔）

Usage:
    from tools.common import us_stock_cache

    # 获取全部美股代码与名称（优先本地缓存）
    stocks = us_stock_cache.get_us_code_name_list()

    # 读取/更新单只股票的慢变字段缓存
    slow = us_stock_cache.get_slow_fields("AAPL")
    us_stock_cache.update_slow_fields("AAPL", info_dict)
"""

import json
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - 依赖缺失时降级为不读取 .env
    load_dotenv = None

try:
    import requests
except ImportError:  # pragma: no cover - 列表下载依赖 requests
    requests = None

try:
    import yfinance as yf
except ImportError:  # pragma: no cover - 列表主源之外的备用抓取可能需要 yfinance
    yf = None


# ---------------------------------------------------------------------------
# 路径与配置常量
# ---------------------------------------------------------------------------

# 工作区根目录（本文件位于 tools/common/，向上 3 层到达项目根）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 美股缓存目录与缓存文件
CACHE_DIR = _PROJECT_ROOT / "data" / "us_stock"
CODE_CACHE_FILE = CACHE_DIR / "stock_code.csv"
SLOW_FIELDS_FILE = CACHE_DIR / "symbol_info.csv"

# 默认缓存有效期（天）
_DEFAULT_LIST_TTL_DAYS = 7
_DEFAULT_INFO_TTL_DAYS = 1

# NASDAQ Trader 官方列表文件 URL（主源）
_NASDAQ_LIST_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
_OTHER_LIST_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

# NASDAQ 官方 screener API（备源，download=true 返回全量）
_NASDAQ_SCREENER_URL = (
    "https://api.nasdaq.com/api/screener/stocks"
    "?tableonly=true&limit=25&download=true"
)

# otherlisted 的 Exchange 代码到交易所名称映射
_EXCHANGE_MAP = {
    "N": "NYSE",
    "A": "NYSE American",
    "P": "NYSE Arca",
    "Z": "BATS",
    "V": "IEXG",
}


def _load_dotenv() -> None:
    """从项目根目录 .env 加载环境变量（若已安装 python-dotenv）。"""
    if load_dotenv is not None:
        load_dotenv(_PROJECT_ROOT / ".env", override=False)


def _parse_int_env(var_name: str, default: int) -> int:
    """从环境变量读取整数配置，非法值或缺失时回退到默认值。

    Args:
        var_name: 环境变量名。
        default: 解析失败时使用的默认值。

    Returns:
        解析后的整数。
    """
    raw = os.getenv(var_name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


_load_dotenv()

# 列表缓存有效期（天），复用 .env 的 STOCK_CACHE_TTL_DAYS
LIST_TTL_DAYS: int = _parse_int_env("STOCK_CACHE_TTL_DAYS", _DEFAULT_LIST_TTL_DAYS)
# 慢变字段缓存有效期（天），.env 可配置
SLOW_FIELDS_TTL_DAYS: int = _parse_int_env("US_STOCK_INFO_TTL_DAYS", _DEFAULT_INFO_TTL_DAYS)

# 最近一次列表缓存访问状态：hit / refresh / stale
_list_status: str = "unknown"


# ---------------------------------------------------------------------------
# 通用工具函数
# ---------------------------------------------------------------------------

def _is_cache_fresh(cache_file: Path, ttl_days: int) -> bool:
    """判断缓存文件是否在 TTL 有效期之内。

    Args:
        cache_file: 缓存文件路径。
        ttl_days: 有效期天数。

    Returns:
        新鲜（未过期）返回 True；文件不存在或已过期返回 False。
    """
    if not cache_file.exists():
        return False
    mtime = datetime.fromtimestamp(cache_file.stat().st_mtime)
    age = datetime.now() - mtime
    return age.days < ttl_days


def _atomic_write_csv(df: pd.DataFrame, cache_file: Path) -> None:
    """原子写入 CSV：先写 .tmp 临时文件再 os.replace，避免并发写坏缓存。

    Args:
        df: 待写入的 DataFrame。
        cache_file: 目标缓存文件路径。
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = cache_file.with_suffix(cache_file.suffix + ".tmp")
    df.to_csv(tmp_file, index=False, encoding="utf-8-sig")
    os.replace(tmp_file, cache_file)


def _to_float_or_none(value) -> float | None:
    """安全转换为 float，失败返回 None。

    Args:
        value: 待转换值。

    Returns:
        float 或 None。
    """
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 列表数据源拉取（官网 → 备源 → 镜像）
# ---------------------------------------------------------------------------

def _parse_pipe_file(text: str, expected_cols: set[str], exchange_fixed: str | None) -> list[dict]:
    """解析 NASDAQ Trader 管道分隔列表文件。

    按文件实际表头顺序解析：首行为表头，后续行为数据；末尾
    File Creation Time 时间戳行及表头列数不匹配的行自动过滤。

    Args:
        text: 文件全文。
        expected_cols: 合法列名集合（用于校验表头合法性）。
        exchange_fixed: 非 None 时将该交易所固定写入所有记录（nasdaqlisted）。

    Returns:
        记录列表 [{"symbol", "name", "exchange", "etf"}, ...]。
    """
    lines = text.splitlines()
    if not lines:
        return []
    # 首行为表头（nasdaqlisted/otherlisted 格式一致）
    header = [h.strip() for h in lines[0].split("|")]
    if not set(header).issubset(expected_cols) or "Security Name" not in header:
        raise RuntimeError(f"美股列表文件表头异常: {header}")

    records = []
    for line in lines[1:]:
        if not line or "|" not in line:
            continue
        fields = [f.strip() for f in line.split("|")]
        # 列数与表头不符的行（时间戳行/异常行）过滤
        if len(fields) != len(header):
            continue
        row = dict(zip(header, fields))
        # 过滤测试股
        if row.get("Test Issue", "").upper() == "Y":
            continue
        symbol = row.get("Symbol") or row.get("ACT Symbol") or ""
        name = row.get("Security Name") or ""
        if not symbol or not name:
            continue
        exchange = exchange_fixed or _EXCHANGE_MAP.get(row.get("Exchange", ""), "")
        records.append({
            "symbol": symbol,
            "name": name,
            "exchange": exchange,
            "etf": row.get("ETF", ""),
        })
    return records


def _fetch_from_nasdaq_trader() -> list[dict]:
    """从 NASDAQ Trader 官网下载并解析两个列表文件（主源）。

    Returns:
        记录列表 [{"symbol", "name", "exchange", "etf"}, ...]。

    Raises:
        RuntimeError: requests 缺失或下载/解析失败。
    """
    if requests is None:
        raise RuntimeError("requests 库未安装，无法下载美股列表。请运行: pip install requests")
    headers = {"User-Agent": "Mozilla/5.0"}

    # nasdaqlisted.txt（NASDAQ 交易所，无 Exchange 列）
    resp = requests.get(_NASDAQ_LIST_URL, timeout=20, headers=headers)
    resp.raise_for_status()
    nasdaq_records = _parse_pipe_file(resp.text, {"Symbol", "Security Name", "Market Category", "Test Issue", "Financial Status", "Round Lot Size", "ETF", "NextShares"}, exchange_fixed="NASDAQ")

    # otherlisted.txt（NYSE / AMEX / Arca / BATS / IEXG，含 Exchange 列）
    resp2 = requests.get(_OTHER_LIST_URL, timeout=20, headers=headers)
    resp2.raise_for_status()
    other_records = _parse_pipe_file(resp2.text, {"ACT Symbol", "Security Name", "Exchange", "CQS Symbol", "ETF", "Round Lot Size", "Test Issue", "NASDAQ Symbol"}, exchange_fixed=None)

    return nasdaq_records + other_records


def _fetch_from_nasdaq_api() -> list[dict]:
    """从 NASDAQ 官方 screener API 获取全市场列表（备源，JSON）。

    Returns:
        记录列表 [{"symbol", "name", "exchange", "etf"}, ...]。

    Raises:
        RuntimeError: requests 缺失或下载/解析失败。
    """
    if requests is None:
        raise RuntimeError("requests 库未安装，无法下载美股列表。请运行: pip install requests")
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(_NASDAQ_SCREENER_URL, timeout=30, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    rows = (data.get("data") or {}).get("rows") or []
    if not rows:
        raise RuntimeError("NASDAQ API 返回空列表")
    records = []
    for row in rows:
        symbol = str(row.get("symbol", "")).strip()
        name = str(row.get("name", "")).strip()
        if not symbol or not name:
            continue
        records.append({
            "symbol": symbol,
            "name": name,
            "exchange": "",
            "etf": "",
        })
    return records


def _fetch_from_mirror() -> list[dict]:
    """从 .env 配置的自定义镜像 URL 获取列表（用户自定义源）。

    镜像格式：与 nasdaqlisted.txt 相同管道分隔，或 nasdaq API 相同 JSON
    （自动识别：以 { 开头按 JSON 解析，否则按管道文件解析）。

    Returns:
        记录列表。

    Raises:
        RuntimeError: 未配置镜像或全部镜像失败。
    """
    if requests is None:
        raise RuntimeError("requests 库未安装，无法下载美股列表。请运行: pip install requests")
    mirror_urls = [
        u.strip() for u in os.getenv("US_TICKER_MIRROR_URLS", "").split(",")
        if u.strip()
    ]
    if not mirror_urls:
        raise RuntimeError("未配置自定义镜像 US_TICKER_MIRROR_URLS")
    headers = {"User-Agent": "Mozilla/5.0"}
    last_error: Exception | None = None
    for url in mirror_urls:
        try:
            resp = requests.get(url, timeout=30, headers=headers)
            resp.raise_for_status()
            text = resp.text
            if text.lstrip().startswith("{"):
                # JSON 格式（兼容 nasdaq API 结构）
                data = json.loads(text)
                rows = (data.get("data") or {}).get("rows") or []
                records = []
                for row in rows:
                    symbol = str(row.get("symbol", "")).strip()
                    name = str(row.get("name", "")).strip()
                    if symbol and name:
                        records.append({"symbol": symbol, "name": name, "exchange": "", "etf": ""})
                if records:
                    return records
            else:
                # 管道分隔格式
                records = _parse_pipe_file(text, {"Symbol", "Security Name", "Market Category", "Test Issue", "Financial Status", "Round Lot Size", "ETF", "NextShares"}, exchange_fixed="NASDAQ")
                if records:
                    return records
        except Exception as e:  # noqa: BLE001 - 多个镜像逐个尝试
            last_error = e
            continue
    raise RuntimeError(f"全部镜像下载失败: {last_error}")


def _fetch_us_code_name_list() -> list[dict]:
    """拉取全部美股代码与名称（官网 → 备源 → 镜像）。

    Returns:
        记录列表。

    Raises:
        RuntimeError: 所有数据源均失败。
    """
    last_error: Exception | None = None
    for fetch in (_fetch_from_nasdaq_trader, _fetch_from_nasdaq_api, _fetch_from_mirror):
        try:
            records = fetch()
            if records:
                return records
        except Exception as e:  # noqa: BLE001 - 数据源逐个重试，需捕获所有异常
            last_error = e
            continue
    raise RuntimeError(f"美股列表获取失败（官网/备源/镜像均不可用）: {last_error}")


def _records_to_cache_rows(records: list[dict]) -> list[dict]:
    """为记录生成缓存行（含 yf_symbol 列）。

    Args:
        records: [{"symbol", "name", "exchange", "etf"}, ...]。

    Returns:
        含 yf_symbol 的缓存行列表。
    """
    rows = []
    for rec in records:
        symbol = rec["symbol"]
        rows.append({
            "symbol": symbol,
            "name": rec["name"],
            "yf_symbol": symbol.replace(".", "-"),
            "exchange": rec.get("exchange", ""),
            "etf": rec.get("etf", ""),
            "market": "us",
        })
    return rows


# ---------------------------------------------------------------------------
# 美股代码/名称列表（本地缓存）
# ---------------------------------------------------------------------------

def _read_code_csv() -> list[dict] | None:
    """从缓存文件读取全部美股代码与名称。

    Returns:
        记录列表；缓存缺失或解析失败返回 None。
    """
    try:
        df = pd.read_csv(CODE_CACHE_FILE, dtype=str, keep_default_na=False,
                         encoding="utf-8-sig")
        records = []
        for _, row in df.iterrows():
            records.append({
                "symbol": str(row["symbol"]).strip(),
                "name": str(row["name"]).strip(),
                "yf_symbol": str(row.get("yf_symbol", "")).strip(),
                "exchange": str(row.get("exchange", "")).strip(),
                "etf": str(row.get("etf", "")).strip(),
                "market": "us",
            })
        return records if records else None
    except Exception:
        return None


def _write_code_csv(records: list[dict]) -> None:
    """将美股代码/名称记录原子写入缓存文件。

    Args:
        records: 记录列表（含 yf_symbol）。
    """
    _atomic_write_csv(pd.DataFrame(records), CODE_CACHE_FILE)


def get_us_code_name_list(force_refresh: bool = False) -> list[dict]:
    """获取全部美股代码与名称（优先本地缓存）。

    查询顺序：
    1. 缓存新鲜且未强制刷新 → 直接读本地（状态 hit）；
    2. 缓存缺失/过期/损坏 → 拉取全量并原子覆写缓存（状态 refresh）；
    3. 刷新失败但存在旧缓存 → 降级返回旧数据（状态 stale）；
    4. 刷新失败且无缓存 → 抛出 RuntimeError（由调用方处理）。

    Args:
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        记录列表 [{"symbol", "name", "yf_symbol", "exchange", "etf", "market"}, ...]。

    Raises:
        RuntimeError: 无缓存且所有数据源均不可用。
    """
    global _list_status
    if not force_refresh and _is_cache_fresh(CODE_CACHE_FILE, LIST_TTL_DAYS):
        cached = _read_code_csv()
        if cached is not None:
            _list_status = "hit"
            return cached
    try:
        records = _fetch_us_code_name_list()
        cache_rows = _records_to_cache_rows(records)
        _write_code_csv(cache_rows)
        _list_status = "refresh"
        return cache_rows
    except Exception:
        cached = _read_code_csv()
        if cached is not None:
            _list_status = "stale"
            return cached
        _list_status = "stale"
        raise


def get_us_code_name_status() -> str:
    """返回最近一次美股列表访问的缓存状态。

    Returns:
        "hit"（缓存命中）/ "refresh"（拉取刷新）/ "stale"（旧缓存降级）。
    """
    return _list_status


def search_us_stocks(keyword: str) -> list[dict]:
    """在美股列表缓存中按名称关键词搜索（不区分大小写）。

    Args:
        keyword: 搜索关键词（支持代码/名称，如 "Apple"、"AAPL"）。

    Returns:
        匹配的记录列表（含 yf_symbol）。
    """
    keyword_upper = keyword.strip().upper()
    if not keyword_upper:
        return []
    stocks = get_us_code_name_list()
    matched = []
    for s in stocks:
        if keyword_upper in s["symbol"].upper() or keyword_upper in s["name"].upper():
            matched.append(s)
    return matched


# ---------------------------------------------------------------------------
# 慢变字段缓存（用于 yfinance 限流时估值降级）
# ---------------------------------------------------------------------------
# 慢变字段：公司名称、市值、流通股本、总股本、PE(TTM)、PB、股息率、Beta、
#           ROE、ROA、52周最高/最低
SLOW_FIELD_KEYS: list[str] = [
    "公司名称", "市值", "流通市值", "总股本", "市盈率TTM", "市净率PB",
    "股息率", "Beta系数", "ROE", "ROA", "52周最高", "52周最低",
]


# 慢变字段中的字符串字段（其余均为数值字段，读取时转 float）
_STRING_SLOW_FIELDS: set[str] = {"公司名称"}


def get_slow_fields(symbol: str) -> dict | None:
    """读取单只股票的慢变字段缓存。

    仅在缓存新鲜（TTL 内）时返回，过期视作无缓存。

    Args:
        symbol: 美股代码，如 "AAPL"。

    Returns:
        慢变字段字典；无新鲜缓存时返回 None。
    """
    if not _is_cache_fresh(SLOW_FIELDS_FILE, SLOW_FIELDS_TTL_DAYS):
        return None
    try:
        df = pd.read_csv(SLOW_FIELDS_FILE, dtype=str, keep_default_na=False,
                         encoding="utf-8-sig")
        target = df[df["symbol"] == symbol]
        if target.empty:
            return None
        row = target.iloc[0]
        result = {}
        for key in SLOW_FIELD_KEYS:
            if key not in row:
                result[key] = None
            elif key in _STRING_SLOW_FIELDS:
                # 字符串字段保持原样（如公司名称）
                raw = row[key]
                result[key] = raw if raw else None
            else:
                # 数值字段安全转换为 float
                result[key] = _to_float_or_none(row[key])
        return result
    except Exception:
        return None


def update_slow_fields(symbol: str, slow_fields: dict) -> None:
    """更新单只股票的慢变字段缓存。

    以 symbol 为键进行 upsert：存在则更新，不存在则追加。

    Args:
        symbol: 美股代码，如 "AAPL"。
        slow_fields: 慢变字段字典（键为 SLOW_FIELD_KEYS 的子集）。
    """
    rows: list[dict] = []
    if SLOW_FIELDS_FILE.exists():
        try:
            df = pd.read_csv(SLOW_FIELDS_FILE, dtype=str, keep_default_na=False,
                             encoding="utf-8-sig")
            rows = df.where(pd.notna(df), "").to_dict("records")
        except Exception:
            rows = []
    # 移除同 symbol 的旧行
    rows = [r for r in rows if r.get("symbol") != symbol]
    new_row = {"symbol": symbol}
    for key in SLOW_FIELD_KEYS:
        value = slow_fields.get(key)
        if value is None:
            new_row[key] = ""
        else:
            new_row[key] = value
    rows.append(new_row)
    _atomic_write_csv(pd.DataFrame(rows), SLOW_FIELDS_FILE)


# ---------------------------------------------------------------------------
# 美股财务数据（本地缓存，JSON）
# ---------------------------------------------------------------------------
# 缓存三大报表与分红拆股历史，用于 yfinance 限流（HTTP 429）时降级返回，
# 保证研究流程不中断。缓存内容为 stock_financial.py 处理后的 data 字典，
# 结构完全一致，读取时按键容错。

# 财务数据缓存目录（按股票分文件）
FINANCIAL_DIR = CACHE_DIR / "financial"

# 缓存有效期（天），.env 可配置
_DEFAULT_FINANCIAL_TTL_DAYS = 7    # 三大报表（季报披露节奏）
_DEFAULT_DIVIDENDS_TTL_DAYS = 30   # 分红拆股历史（历史数据几乎不变）
FINANCIAL_TTL_DAYS: int = _parse_int_env("US_FINANCIAL_TTL_DAYS", _DEFAULT_FINANCIAL_TTL_DAYS)
DIVIDENDS_TTL_DAYS: int = _parse_int_env("US_DIVIDENDS_TTL_DAYS", _DEFAULT_DIVIDENDS_TTL_DAYS)

# 最近一次财务缓存访问状态：hit / refresh / stale
_financial_status: str = "unknown"


def _financial_cache_file(symbol: str, kind: str) -> Path:
    """生成美股财务数据缓存文件路径。

    Args:
        symbol: 美股代码，如 "AAPL"。
        kind: 数据种类（"statements" / "dividends"）。

    Returns:
        对应的缓存文件路径。
    """
    return FINANCIAL_DIR / f"{symbol}_{kind}.json"


def _atomic_write_json(data: dict, cache_file: Path) -> None:
    """原子写入 JSON：先写 .tmp 临时文件再 os.replace，避免并发写坏缓存。

    Args:
        data: 待写入的字典。
        cache_file: 目标缓存文件路径。
    """
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = cache_file.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, default=str)
    os.replace(tmp_file, cache_file)


def _read_financial_json(cache_file: Path) -> dict | None:
    """从缓存文件读取财务数据字典。

    Args:
        cache_file: 缓存文件路径。

    Returns:
        数据字典；缓存缺失或解析失败返回 None。
    """
    try:
        with open(cache_file, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) and data else None
    except Exception:
        return None


def _fetch_statements_data(symbol: str) -> dict:
    """从 yfinance 拉取三大报表并构建 data 字典（不缓存）。

    Args:
        symbol: 美股代码，如 "AAPL"。

    Returns:
        含 "年度利润表" / "季度利润表" / ... 的 data 字典（按键容错）。

    Raises:
        RuntimeError: yfinance 未安装。
    """
    if yf is None:
        raise RuntimeError("yfinance 未安装，无法获取美股财务报表。请运行: pip install yfinance")
    stock = yf.Ticker(symbol)
    data: dict = {}
    spec = [
        ("年度利润表", "income_stmt"),
        ("季度利润表", "quarterly_income_stmt"),
        ("年度资产负债表", "balance_sheet"),
        ("季度资产负债表", "quarterly_balance_sheet"),
        ("年度现金流量表", "cashflow"),
        ("季度现金流量表", "quarterly_cashflow"),
    ]
    for label, attr in spec:
        try:
            df = getattr(stock, attr)
            if df is not None and not df.empty:
                data[label] = {
                    "count": len(df),
                    "columns": [str(c) for c in df.columns],
                    "index": [str(i) for i in list(df.index)[:10]],
                }
            else:
                data[label] = {"count": 0, "error": "未获取到数据"}
        except Exception as e:  # noqa: BLE001 - 单表失败不影响其余报表
            data[label] = {"error": str(e)}
    return data


def _fetch_dividends_data(symbol: str) -> dict:
    """从 yfinance 拉取分红拆股历史并构建 data 字典（不缓存）。

    Args:
        symbol: 美股代码，如 "AAPL"。

    Returns:
        含 "分红历史" / "拆股历史" 的 data 字典。

    Raises:
        RuntimeError: yfinance 未安装。
    """
    if yf is None:
        raise RuntimeError("yfinance 未安装，无法获取美股分红拆股。请运行: pip install yfinance")
    stock = yf.Ticker(symbol)
    data: dict = {}
    try:
        div_df = stock.dividends
        if div_df is not None and not div_df.empty:
            data["分红历史"] = {
                "count": len(div_df),
                "latest": div_df.iloc[-1],
                "total_years": int(div_df.resample("YE").count().count()),
            }
        else:
            data["分红历史"] = {"count": 0, "note": "无分红记录"}
    except Exception as e:  # noqa: BLE001 - 分红失败不影响拆股
        data["分红历史"] = {"error": str(e)}
    try:
        split_df = stock.splits
        if split_df is not None and not split_df.empty:
            data["拆股历史"] = {
                "count": len(split_df),
                "latest": split_df.iloc[-1],
            }
        else:
            data["拆股历史"] = {"count": 0, "note": "无拆股记录"}
    except Exception as e:  # noqa: BLE001 - 拆股失败不影响分红
        data["拆股历史"] = {"error": str(e)}
    return data


def _cached_financial_json(cache_file: Path, ttl_days: int, fetch_func, force_refresh: bool) -> dict | None:
    """财务数据通用缓存读取逻辑（hit → refresh → stale）。

    Args:
        cache_file: 缓存文件路径。
        ttl_days: 有效期（天）。
        fetch_func: 无参拉取函数，返回 data 字典。
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        data 字典；无缓存且拉取失败时返回 None。
    """
    global _financial_status
    if not force_refresh and _is_cache_fresh(cache_file, ttl_days):
        cached = _read_financial_json(cache_file)
        if cached is not None:
            _financial_status = "hit"
            return cached
    try:
        data = fetch_func()
        if not data:
            raise RuntimeError(f"财务数据为空: {cache_file.name}")
        _atomic_write_json(data, cache_file)
        _financial_status = "refresh"
        return data
    except Exception:
        # 刷新失败（限流 429/断连）时优先降级返回旧缓存
        cached = _read_financial_json(cache_file)
        if cached is not None:
            _financial_status = "stale"
            return cached
        _financial_status = "stale"
        return None


def get_financial_statements(symbol: str, force_refresh: bool = False) -> dict | None:
    """获取美股三大报表数据（优先本地缓存）。

    查询顺序：
    1. 缓存新鲜且未强制刷新 → 直接读本地（状态 hit）；
    2. 缓存缺失/过期/损坏 → 拉取并原子覆写缓存（状态 refresh）；
    3. 刷新失败但存在旧缓存 → 降级返回旧数据（状态 stale）；
    4. 刷新失败且无缓存 → 返回 None。

    Args:
        symbol: 美股代码，如 "AAPL"。
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        data 字典（含六张报表）；无缓存且拉取失败时返回 None。
    """
    return _cached_financial_json(
        _financial_cache_file(symbol, "statements"), FINANCIAL_TTL_DAYS,
        lambda: _fetch_statements_data(symbol), force_refresh)


def get_dividends_splits(symbol: str, force_refresh: bool = False) -> dict | None:
    """获取美股分红拆股历史（优先本地缓存）。

    Args:
        symbol: 美股代码，如 "AAPL"。
        force_refresh: 为 True 时跳过缓存有效期检查，强制刷新。

    Returns:
        data 字典（含分红/拆股历史）；无缓存且拉取失败时返回 None。
    """
    return _cached_financial_json(
        _financial_cache_file(symbol, "dividends"), DIVIDENDS_TTL_DAYS,
        lambda: _fetch_dividends_data(symbol), force_refresh)


def get_financial_status() -> str:
    """返回最近一次美股财务数据访问的缓存状态。

    Returns:
        "hit"（缓存命中）/ "refresh"（拉取刷新）/ "stale"（旧缓存降级）。
    """
    return _financial_status
