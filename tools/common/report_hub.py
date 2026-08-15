#!/usr/bin/env python3
"""A股财报下载与提取统一入口工具。

提供 ensure / extract / list 三个命令，统一管理 A 股财报 PDF 的下载与提取，
所有报告集中存储在 cninfo_reports/ 目录，避免技能间重复下载与重复提取。

下载层（ensure）：
  - 披露窗口感知：仅窗口内 + 距上次检查超过 7 天时查询巨潮 API
  - 窗口外完全零网络，直接返回本地缓存
  - 四 Agent 并行安全：.part 临时文件 + os.replace 原子落盘

提取层（extract）：
  - 结果缓存：{stem}.md 存在且 mtime 新于 PDF 时秒回
  - PDF 重新下载后 mtime 更新，提取自动失效重提取
  - 统一输出到 cninfo_reports/extracted/ 目录

Usage:
    python tools/common/report_hub.py ensure --code 601899 --report-type annual
    python tools/common/report_hub.py extract --code 601899 --report-type annual
    python tools/common/report_hub.py extract --pdf cninfo_reports/601899_2025年报.pdf --pages 0-10
    python tools/common/report_hub.py list --code 601899
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CNINFO_DIR = PROJECT_ROOT / "cninfo_reports"
META_DIR = CNINFO_DIR / ".meta"
EXTRACT_DIR = CNINFO_DIR / "extracted"
TOOLS_DIR = PROJECT_ROOT / "tools"

# 将项目根目录加入 sys.path，使本工具以独立脚本方式运行时也能导入 tools 包
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MIN_REPORT_SIZE = 1024 * 1024  # 1MB（完整版报告通常 > 1MB）

# 披露窗口（月份范围）：年报 1-5 月、半年报 7-9 月、季报 4-5 月或 10-11 月
# 含缓冲期（官方截止月 + 半个月）
DISCLOSURE_WINDOWS = {
    "annual": [(1, 5)],
    "semiannual": [(7, 9)],
    "quarterly": [(4, 5), (10, 11)],
}

REPORT_TYPE_NAMES = {
    "annual": "年报",
    "semiannual": "半年报",
    "quarterly": "季报",
}

# ---------------------------------------------------------------------------
# 缓存状态（全局变量，供 get_cache_status() 查询）
# ---------------------------------------------------------------------------

_cache_status = "unknown"


def get_cache_status() -> str:
    """返回最近一次操作的缓存状态。

    Returns:
        "hit" / "refresh" / "check_hit" / "stale" / "error"
    """
    return _cache_status


def _set_cache_status(status: str) -> None:
    global _cache_status
    _cache_status = status


# ---------------------------------------------------------------------------
# 披露窗口判断
# ---------------------------------------------------------------------------


def _in_disclosure_window(report_type: str, now: Optional[datetime] = None) -> bool:
    """判断当前是否在某报告类型的披露窗口内（含缓冲期）。

    Args:
        report_type: 报告类型（annual/semiannual/quarterly）。
        now: 当前时间，默认 datetime.now()。

    Returns:
        窗口内返回 True。
    """
    if now is None:
        now = datetime.now()
    month = now.month
    windows = DISCLOSURE_WINDOWS.get(report_type, [])
    return any(start <= month <= end for start, end in windows)


# ---------------------------------------------------------------------------
# 文件名工具
# ---------------------------------------------------------------------------


def _build_pdf_name(code: str, year: str, report_type: str) -> str:
    """构造标准 PDF 文件名。

    Args:
        code: 6 位股票代码。
        year: 4 位年份。
        report_type: 报告类型。

    Returns:
        文件名，如 "601899_2025年报.pdf"。
    """
    suffix = REPORT_TYPE_NAMES.get(report_type, "报告")
    return f"{code}_{year}{suffix}.pdf"


# ---------------------------------------------------------------------------
# 元数据管理（.meta/{code}_{report_type}.json）
# ---------------------------------------------------------------------------


def _meta_path(code: str, report_type: str) -> Path:
    """返回元数据文件路径。

    Args:
        code: 股票代码。
        report_type: 报告类型。

    Returns:
        .meta 目录下的 JSON 文件路径。
    """
    META_DIR.mkdir(parents=True, exist_ok=True)
    return META_DIR / f"{code}_{report_type}.json"


def _load_meta(code: str, report_type: str) -> dict:
    """加载元数据。

    Args:
        code: 股票代码。
        report_type: 报告类型。

    Returns:
        元数据字典；不存在时返回空字典。
    """
    path = _meta_path(code, report_type)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def _save_meta(code: str, report_type: str, data: dict) -> None:
    """保存元数据（原子写入）。

    Args:
        code: 股票代码。
        report_type: 报告类型。
        data: 元数据字典。
    """
    path = _meta_path(code, report_type)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    tmp.replace(path)


# ---------------------------------------------------------------------------
# 下载层（复用 stock_equity.py 的下载能力）
# ---------------------------------------------------------------------------


# pylint: disable=import-outside-toplevel
def _download_report(
    code: str, report_type: str
) -> tuple[Optional[str], Optional[str]]:
    """调用 stock_equity.py 下载最新报告。

    Args:
        code: 6 位股票代码。
        report_type: 报告类型。

    Returns:
        (pdf_path, year)；下载失败时返回 (None, None)。
    """
    from tools.a_share.stock_equity import CnInfoReportDownloader

    downloader = CnInfoReportDownloader(code, str(CNINFO_DIR))
    new_path = downloader.download_latest_report(report_type)
    if not new_path or not os.path.exists(new_path):
        return None, None
    filename = os.path.basename(new_path)
    m = re.search(r"_(\d{4})", filename)
    if not m:
        return None, None
    new_year = m.group(1)

    # 重命名为标准文件名，确保后续 _build_pdf_name / _find_pdf 能一致定位
    standard_name = _build_pdf_name(code, new_year, report_type)
    standard_path = str(CNINFO_DIR / standard_name)
    if os.path.abspath(new_path) != os.path.abspath(standard_path):
        os.replace(new_path, standard_path)
        new_path = standard_path

    return new_path, new_year


# ---------------------------------------------------------------------------
# ensure 命令
# ---------------------------------------------------------------------------


def cmd_ensure(args: argparse.Namespace) -> dict:
    """确保指定类型的最新报告已就绪（窗口感知，避免重复下载）。

    Args:
        args: 命令行参数。

    Returns:
        结果字典，含 success / pdf_path / meta.cache 等字段。
    """
    code = args.code
    report_type = args.report_type
    force = getattr(args, "force", False)

    now = datetime.now()
    meta = _load_meta(code, report_type)

    # 尝试从元数据确定本地文件路径
    pdf_path = None
    local_valid = False
    if meta.get("year"):
        pdf_name = _build_pdf_name(code, meta["year"], report_type)
        candidate = CNINFO_DIR / pdf_name
        if candidate.exists() and candidate.stat().st_size >= MIN_REPORT_SIZE:
            pdf_path = candidate
            local_valid = True

    # 是否需要查询 API？
    in_window = _in_disclosure_window(report_type, now)
    last_check_str = meta.get("last_check", "")
    last_check = None
    if last_check_str:
        try:
            last_check = datetime.fromisoformat(last_check_str)
        except (ValueError, TypeError):
            pass
    check_expired = not last_check or (now - last_check).days > 7

    needs_api = force or not local_valid or (in_window and check_expired)

    if not needs_api:
        _set_cache_status("hit")
        return {
            "success": True,
            "code": code,
            "report_type": report_type,
            "year": meta.get("year", ""),
            "pdf_path": str(pdf_path) if pdf_path else "",
            "meta": {
                "tool": "report_hub",
                "command": "ensure",
                "cache": "hit",
                "timestamp": now.isoformat(),
            },
        }

    # 需要查询 API
    new_path, new_year = _download_report(code, report_type)

    if new_path and new_year:
        meta = {
            "year": new_year,
            "report_type": report_type,
            "pdf_name": os.path.basename(new_path),
            "last_check": now.isoformat(),
            "last_download": now.isoformat(),
        }
        _save_meta(code, report_type, meta)
        cache_status = "refresh" if local_valid else "check_hit"
        _set_cache_status(cache_status)
        return {
            "success": True,
            "code": code,
            "report_type": report_type,
            "year": new_year,
            "pdf_path": new_path,
            "meta": {
                "tool": "report_hub",
                "command": "ensure",
                "cache": cache_status,
                "timestamp": now.isoformat(),
            },
        }

    # API 失败，降级返回旧缓存
    if local_valid:
        _set_cache_status("stale")
        return {
            "success": True,
            "code": code,
            "report_type": report_type,
            "year": meta.get("year", ""),
            "pdf_path": str(pdf_path) if pdf_path else "",
            "meta": {
                "tool": "report_hub",
                "command": "ensure",
                "cache": "stale",
                "timestamp": now.isoformat(),
            },
        }

    _set_cache_status("error")
    return {
        "success": False,
        "code": code,
        "report_type": report_type,
        "error": "无法获取报告，且无本地缓存",
        "meta": {
            "tool": "report_hub",
            "command": "ensure",
            "cache": "error",
            "timestamp": now.isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# extract 命令
# ---------------------------------------------------------------------------


def _normalize_pages(pages_str: str) -> str:
    """将 pages 参数转换为文件名安全键。

    Args:
        pages_str: 原始 pages 参数，如 "0-5,10,20-25"。

    Returns:
        文件名安全字符串，如 "p0_5_10_20_25"。
    """
    safe = re.sub(r"[,\-]", "_", pages_str)
    return f"p{safe}"


def _find_pdf(code: str, report_type: str) -> Optional[str]:
    """在 cninfo_reports/ 中扫描匹配的 PDF 文件（无元数据时的兜底）。

    Args:
        code: 股票代码。
        report_type: 报告类型。

    Returns:
        PDF 文件路径；未找到返回 None。
    """
    suffix = REPORT_TYPE_NAMES.get(report_type, "")
    pattern = f"{code}_*{suffix}.pdf"
    if not CNINFO_DIR.exists():
        return None
    matches = sorted(CNINFO_DIR.glob(pattern))
    for m in matches:
        if m.stat().st_size >= MIN_REPORT_SIZE:
            return str(m)
    return None


def cmd_extract(args: argparse.Namespace) -> dict:
    """提取财报 PDF 为 Markdown（带结果缓存）。

    Args:
        args: 命令行参数。

    Returns:
        结果字典，含 success / extract_path / meta.cache 等字段。
    """
    pdf_path = getattr(args, "pdf", None)
    code = getattr(args, "code", None)
    report_type = getattr(args, "report_type", "annual")

    # 解析 PDF 路径：优先 --pdf，其次 --code + meta，最后扫目录
    if not pdf_path and code:
        meta = _load_meta(code, report_type)
        if meta.get("year"):
            pdf_name = _build_pdf_name(code, meta["year"], report_type)
            pdf_path = str(CNINFO_DIR / pdf_name)
        if not pdf_path or not os.path.exists(pdf_path):
            pdf_path = _find_pdf(code, report_type)

    if not pdf_path or not os.path.exists(pdf_path):
        return {
            "success": False,
            "error": "PDF 文件不存在，请先执行 ensure",
            "meta": {
                "tool": "report_hub",
                "command": "extract",
                "cache": "error",
                "timestamp": datetime.now().isoformat(),
            },
        }

    pdf_path_obj = Path(pdf_path)
    stem = pdf_path_obj.stem
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    # 确定缓存输出路径
    pages = getattr(args, "pages", None)
    if pages:
        pages_key = _normalize_pages(pages)
        md_path = EXTRACT_DIR / f"{stem}_{pages_key}.md"
    else:
        md_path = EXTRACT_DIR / f"{stem}.md"

    now = datetime.now()

    # 检查提取缓存是否有效（md 存在且 mtime >= pdf mtime）
    if md_path.exists():
        md_mtime = os.path.getmtime(md_path)
        pdf_mtime = os.path.getmtime(pdf_path)
        if md_mtime >= pdf_mtime:
            _set_cache_status("hit")
            return {
                "success": True,
                "code": code or "",
                "report_type": report_type,
                "pdf_path": str(pdf_path_obj),
                "extract_path": str(md_path),
                "meta": {
                    "tool": "report_hub",
                    "command": "extract",
                    "cache": "hit",
                    "timestamp": now.isoformat(),
                },
            }

    # 调用 pdf_extract.py（子进程）
    # 注意：pdf_extract 无论是否指定 --pages 都输出 {stem}.md；
    # 指定 pages 时需在成功后重命名为 {stem}_{pages_key}.md 缓存名
    raw_md_path = EXTRACT_DIR / f"{stem}.md"
    cmd = [
        sys.executable,
        str(TOOLS_DIR / "common" / "pdf_extract.py"),
        "markdown",
        str(pdf_path_obj),
        "--save-md",
        "--out-dir",
        str(EXTRACT_DIR),
    ]
    if pages:
        cmd.extend(["--pages", pages])
    force_ocr = getattr(args, "force_ocr", False)
    if force_ocr:
        cmd.extend(["--force-ocr"])
    ocr_langs = getattr(args, "ocr_langs", None)
    if ocr_langs:
        cmd.extend(["--ocr-langs", ocr_langs])

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        _set_cache_status("error")
        return {
            "success": False,
            "error": "提取超时（300 秒）",
            "meta": {
                "tool": "report_hub",
                "command": "extract",
                "cache": "error",
                "timestamp": now.isoformat(),
            },
        }

    # 提取成功后若指定 pages，将 {stem}.md 重命名为带后缀的缓存名
    if proc.returncode == 0 and raw_md_path.exists():
        if pages and raw_md_path != md_path:
            raw_md_path.replace(md_path)

    if proc.returncode == 0 and md_path.exists():
        _set_cache_status("refresh")
        return {
            "success": True,
            "code": code or "",
            "report_type": report_type,
            "pdf_path": str(pdf_path_obj),
            "extract_path": str(md_path),
            "meta": {
                "tool": "report_hub",
                "command": "extract",
                "cache": "refresh",
                "timestamp": now.isoformat(),
            },
        }

    # 检查是否扫描件
    try:
        output = json.loads(proc.stdout or "")
        if isinstance(output, dict) and output.get("scanned"):
            _set_cache_status("error")
            return {
                "success": False,
                "scanned": True,
                "note": output.get(
                    "note", "检测到扫描格式，请使用 --force-ocr 参数重试"
                ),
                "meta": {
                    "tool": "report_hub",
                    "command": "extract",
                    "cache": "error",
                    "timestamp": now.isoformat(),
                },
            }
    except (json.JSONDecodeError, ValueError):
        pass

    _set_cache_status("error")
    return {
        "success": False,
        "error": "提取失败",
        "details": (proc.stderr or "")[:500] or (proc.stdout or "")[:500],
        "meta": {
            "tool": "report_hub",
            "command": "extract",
            "cache": "error",
            "timestamp": now.isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# list 命令
# ---------------------------------------------------------------------------


def cmd_list(args: argparse.Namespace) -> dict:
    """列出本地已缓存的报告与提取产物。

    Args:
        args: 命令行参数。

    Returns:
        结果字典，含 reports 列表。
    """
    code = args.code
    result = {
        "success": True,
        "code": code,
        "reports": [],
        "meta": {
            "tool": "report_hub",
            "command": "list",
            "timestamp": datetime.now().isoformat(),
        },
    }

    if not META_DIR.exists():
        return result

    for meta_file in sorted(META_DIR.glob(f"{code}_*.json")):
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            pdf_name = meta.get("pdf_name", "")
            pdf_path = CNINFO_DIR / pdf_name
            pdf_exists = pdf_path.exists()
            pdf_size = (
                round(pdf_path.stat().st_size / 1024, 1)
                if pdf_exists
                else 0
            )

            report = {
                "report_type": meta.get("report_type", ""),
                "year": meta.get("year", ""),
                "pdf_name": pdf_name,
                "pdf_exists": pdf_exists and pdf_size >= 1.0,
                "pdf_size_kb": pdf_size,
                "last_check": meta.get("last_check", ""),
                "last_download": meta.get("last_download", ""),
            }

            # 检查提取缓存
            if pdf_exists and pdf_size >= 1.0:
                stem = pdf_path.stem
                md_path = EXTRACT_DIR / f"{stem}.md"
                report["extracted"] = md_path.exists()
                report["extract_path"] = (
                    str(md_path) if md_path.exists() else ""
                )
            else:
                report["extracted"] = False
                report["extract_path"] = ""

            result["reports"].append(report)
        except (json.JSONDecodeError, OSError):
            continue

    return result


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """构建参数解析器。

    Returns:
        配置好的 ArgumentParser 实例。
    """
    parser = argparse.ArgumentParser(
        description="A股财报下载与提取统一入口工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 确保最新年报已下载（窗口感知，零网络直接返回缓存）
  python tools/common/report_hub.py ensure --code 601899 --report-type annual

  # 强制刷新（跳过窗口检查，直查巨潮 API）
  python tools/common/report_hub.py ensure --code 601899 --report-type annual --force

  # 提取全量 Markdown（缓存命中时秒回）
  python tools/common/report_hub.py extract --code 601899 --report-type annual

  # 两步法取目录页 → 目标章节
  python tools/common/report_hub.py extract --pdf cninfo_reports/601899_2025年报.pdf --pages 0-10
  python tools/common/report_hub.py extract --pdf cninfo_reports/601899_2025年报.pdf --pages 40-60,120-135

  # 强制 OCR 提取（扫描件场景）
  python tools/common/report_hub.py extract --code 601899 --report-type annual --force-ocr

  # 列出本地缓存
  python tools/common/report_hub.py list --code 601899
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ensure
    p_ensure = subparsers.add_parser(
        "ensure", help="确保最新报告已就绪（窗口感知，避免重复下载）"
    )
    p_ensure.add_argument("--code", required=True, help="6 位股票代码")
    p_ensure.add_argument(
        "--report-type",
        default="annual",
        choices=["annual", "semiannual", "quarterly"],
        help="报告类型：annual-年报, semiannual-半年报, quarterly-季报",
    )
    p_ensure.add_argument(
        "--force",
        action="store_true",
        help="跳过窗口检查，强制刷新",
    )

    # extract
    p_extract = subparsers.add_parser(
        "extract", help="提取财报 PDF 为 Markdown（带结果缓存）"
    )
    p_extract.add_argument(
        "--code", help="6 位股票代码（与 --pdf 二选一）"
    )
    p_extract.add_argument(
        "--report-type",
        default="annual",
        choices=["annual", "semiannual", "quarterly"],
        help="报告类型（配合 --code 使用）",
    )
    p_extract.add_argument("--pdf", help="PDF 文件路径（与 --code 二选一）")
    p_extract.add_argument(
        "--pages", help="页码范围，如 '0-10' 或 '40-60,120-135'"
    )
    p_extract.add_argument(
        "--force-ocr", action="store_true", help="强制 OCR 提取"
    )
    p_extract.add_argument(
        "--ocr-langs", default=None, help="OCR 语言包，如 'chi_sim+eng'"
    )

    # list
    p_list = subparsers.add_parser(
        "list", help="列出本地已缓存的报告与提取产物"
    )
    p_list.add_argument("--code", required=True, help="6 位股票代码")

    return parser


def main(argv: Optional[list] = None) -> int:
    """命令行入口。

    Args:
        argv: 可选参数列表，默认 sys.argv[1:]。

    Returns:
        退出码：0 成功，1 失败。
    """
    # 确保 cninfo_reports/ 目录存在
    CNINFO_DIR.mkdir(parents=True, exist_ok=True)

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "ensure":
        result = cmd_ensure(args)
    elif args.command == "extract":
        result = cmd_extract(args)
    elif args.command == "list":
        result = cmd_list(args)
    else:
        parser.print_help()
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success", False) else 1


if __name__ == "__main__":
    sys.exit(main())