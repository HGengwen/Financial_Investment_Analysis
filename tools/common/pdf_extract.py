#!/usr/bin/env python3
"""PDF 文字与表格提取工具。

基于 Firecrawl 开源的 pdf-inspector 库（底层 Rust，Python 绑定，预编译二进制），
提取 PDF 格式文档中的文字与表格，专门面向财报/年报等含复杂附表的文档场景。

注意：本工具文件命名为 pdf_extract.py，避免与库模块 pdf_inspector 同名导致
`import pdf_inspector` 解析到工具自身（同名模块遮蔽问题）。

核心能力：
    - detect   分类检测：快速判断 PDF 类型（text_based / scanned / mixed），并返回需 OCR 页码
    - text     纯文本提取：提取扁平化纯文本（不含表格排版信息）
    - markdown 含表格的 Markdown 提取：自动完成类型检测 + 文字提取 + 表格识别 + 多栏重排
    - all      全流程：依次执行 分类 + 纯文本 + Markdown

输出规范：
    - 所有子命令统一在 stdout 打印 JSON（便于调用方解析）
    - 检测到扫描格式（scanned/mixed 或含需 OCR 页面）时，data 中返回
      "scanned": {"scanned": true, "note": "..."} 标志，提示调用方需走 OCR 流程
    - markdown / all 子命令可通过 --save-md 参数选择是否将 Markdown 写盘为 md 文件
    - text 子命令不写 txt 文件，纯文本仅放入 JSON 字段

Usage:
    {py} tools/common/pdf_extract.py detect    <pdf>                  # 分类检测
    {py} tools/common/pdf_extract.py text      <pdf>                  # 纯文本提取
    {py} tools/common/pdf_extract.py markdown  <pdf> [--pages 0,1]    # 含表格 Markdown
    {py} tools/common/pdf_extract.py all       <pdf> [--save-md]      # 全流程
    {py} tools/common/pdf_extract.py markdown  <pdf> --save-md --out-dir reports/pdf
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdf_inspector

# ---------------------------------------------------------------------------
# 日志配置
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
# 默认输出目录：与 tools/common 同级的 reports/pdf 子目录
OUTPUT_DIR: Path = Path(__file__).resolve().parent.parent.parent / "reports" / "pdf"


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def _ensure_output_dir(out_dir: Path) -> Path:
    """确保输出目录存在（含父级），返回该目录路径。

    Args:
        out_dir: 输出目录路径。

    Returns:
        已确保存在的输出目录。
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _output_path(pdf_path: Path, suffix: str, out_dir: Path) -> Path:
    """根据 PDF 文件名生成 Markdown 输出文件路径。

    Args:
        pdf_path: 源 PDF 路径（取其 stem 作为前缀）。
        suffix: 功能后缀，如 markdown。
        out_dir: 输出目录。

    Returns:
        拼接后的输出文件路径，形如 {stem}_{suffix}.md。
    """
    return out_dir / f"{pdf_path.stem}_{suffix}.md"


def _parse_pages(spec: Optional[str]) -> Optional[List[int]]:
    """将 "0,1,2" 形式的字符串解析为 0 索引页码列表。

    Args:
        spec: 逗号分隔的页码字符串，如 "0,1,2"；为 None 或空串时返回 None。

    Returns:
        页码列表；输入为空时返回 None（表示提取全部页）。

    Raises:
        ValueError: 当存在非整数页码时。
    """
    if not spec:
        return None
    return [int(token.strip()) for token in spec.split(",") if token.strip() != ""]


def _check_exists(pdf_path: Path) -> None:
    """校验 PDF 文件是否存在，不存在则抛出 FileNotFoundError。

    Args:
        pdf_path: 待校验的 PDF 路径。

    Raises:
        FileNotFoundError: 文件不存在时。
    """
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF 文件不存在: {pdf_path}")


def _scan_flag(cls: pdf_inspector.PdfClassification) -> Dict[str, Any]:
    """判断 PDF 是否为扫描格式，并返回标志信息。

    当文档类型为 scanned / mixed，或存在需 OCR 的页面时，视为无法直接提取
    文本与表格，需由调用方转交 OCR 流程处理。

    Args:
        cls: classify_pdf 返回的分类结果。

    Returns:
        标志字典，结构：
            {"scanned": bool, "note": str}
        其中 scanned 为 True 表示扫描格式；note 为给调用方的提示信息。
    """
    is_scanned = cls.pdf_type in ("scanned", "mixed") or bool(cls.pages_needing_ocr)
    flag: Dict[str, Any] = {"scanned": is_scanned}
    if is_scanned:
        flag["note"] = (
            "检测到扫描格式或含需 OCR 的页面，无法直接提取文本/表格，"
            "请使用 OCR 流程处理（需要 OCR 的页码: {}）。".format(
                list(cls.pages_needing_ocr)
            )
        )
    return flag


# ---------------------------------------------------------------------------
# 业务函数（每个对应一个库能力，便于测试与复用）
# ---------------------------------------------------------------------------
def classify_pdf_doc(pdf_path: Path) -> pdf_inspector.PdfClassification:
    """对 PDF 进行轻量分类（快速，不提取文本）。

    Args:
        pdf_path: PDF 文件路径。

    Returns:
        PdfClassification，含字段：pdf_type / page_count / pages_needing_ocr / confidence。

    Raises:
        FileNotFoundError: 文件不存在时。
    """
    _check_exists(pdf_path)
    return pdf_inspector.classify_pdf(str(pdf_path))


def extract_plain_text(pdf_path: Path) -> str:
    """提取 PDF 纯文本（不含表格排版信息）。

    Args:
        pdf_path: PDF 文件路径。

    Returns:
        提取到的纯文本字符串。

    Raises:
        FileNotFoundError: 文件不存在时。
    """
    _check_exists(pdf_path)
    return pdf_inspector.extract_text(str(pdf_path))


def extract_markdown(
    pdf_path: Path, pages: Optional[List[int]] = None
) -> pdf_inspector.PdfResult:
    """提取含财务附表的完整 Markdown 及文档元数据。

    Args:
        pdf_path: PDF 文件路径。
        pages: 可选，仅提取指定 0 索引页；None 表示提取全部页。

    Returns:
        PdfResult，含字段：markdown / title / pdf_type / page_count /
        pages_with_tables / pages_with_columns / processing_time_ms / confidence 等。

    Raises:
        FileNotFoundError: 文件不存在时。
    """
    _check_exists(pdf_path)
    return pdf_inspector.process_pdf(str(pdf_path), pages=pages)


# ---------------------------------------------------------------------------
# 汇总与 JSON 构建
# ---------------------------------------------------------------------------
def _build_meta(tool: str, command: str, pdf_path: Path) -> Dict[str, Any]:
    """构建统一的 meta 字段。

    Args:
        tool: 工具名。
        command: 子命令名。
        pdf_path: PDF 文件路径。

    Returns:
        包含 tool / command / pdf / timestamp 的字典。
    """
    return {
        "tool": tool,
        "command": command,
        "pdf": str(pdf_path),
        "timestamp": datetime.now().isoformat(),
    }


def run_all(
    pdf_path: Path,
    pages: Optional[List[int]] = None,
    save_md: bool = False,
    out_dir: Path = OUTPUT_DIR,
) -> Dict[str, Any]:
    """依次执行分类、纯文本、Markdown 提取，并返回完整结果字典。

    Args:
        pdf_path: PDF 文件路径。
        pages: 可选，仅作用于 Markdown 提取步骤（透传给 process_pdf）。
        save_md: 是否将 Markdown 写盘为 md 文件。
        out_dir: 输出目录，默认为 OUTPUT_DIR。

    Returns:
        汇总字典，结构：
            {
              "classify": {"pdf_type", "page_count", "pages_needing_ocr", "confidence"},
              "text": {"length", "content"},
              "markdown": {"title", "pages_with_tables", "pages_with_columns",
                           "processing_time_ms", "length", "content", "file"},
            }
        当检测到扫描格式（scanned/mixed）时，额外返回 "scanned" 标志字段，
        且 text/markdown 的 content 均为空字符串。

    Raises:
        FileNotFoundError: 文件不存在时。
    """
    # 步骤 0：轻量分类，判断是否为扫描格式
    cls = classify_pdf_doc(pdf_path)
    scan = _scan_flag(cls)
    classify_info: Dict[str, Any] = {
        "pdf_type": cls.pdf_type,
        "page_count": cls.page_count,
        "pages_needing_ocr": list(cls.pages_needing_ocr),
        "confidence": cls.confidence,
    }

    # 扫描格式：无法提取文本/表格，直接返回标志，跳过无意义的提取
    if scan["scanned"]:
        return {
            "classify": classify_info,
            "scanned": scan,
            "text": {"length": 0, "content": ""},
            "markdown": {
                "title": None,
                "pages_with_tables": [],
                "pages_with_columns": [],
                "processing_time_ms": 0,
                "length": 0,
                "content": "",
                "file": None,
            },
        }

    # 步骤 2：纯文本提取
    text = extract_plain_text(pdf_path)
    text_info: Dict[str, Any] = {"length": len(text), "content": text}

    # 步骤 3：Markdown（含表格）提取
    result = extract_markdown(pdf_path, pages=pages)
    md_file: Optional[str] = None
    if save_md:
        _ensure_output_dir(out_dir)
        md_file_path = _output_path(pdf_path, "markdown", out_dir)
        md_file_path.write_text(result.markdown, encoding="utf-8")
        md_file = str(md_file_path)

    markdown_info: Dict[str, Any] = {
        "title": result.title,
        "pages_with_tables": list(result.pages_with_tables),
        "pages_with_columns": list(result.pages_with_columns),
        "processing_time_ms": result.processing_time_ms,
        "length": len(result.markdown),
        "content": result.markdown,
        "file": md_file,
    }

    return {
        "classify": classify_info,
        "text": text_info,
        "markdown": markdown_info,
    }


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器。

    Returns:
        配置好的 ArgumentParser。
    """
    parser = argparse.ArgumentParser(
        prog="pdf_extract",
        description="基于 pdf-inspector 库提取 PDF 中的文字与附表",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # detect：仅分类检测
    p_detect = sub.add_parser("detect", help="检测/分类 PDF 类型（快速，不提取文本）")
    p_detect.add_argument("pdf", help="PDF 文件路径")

    # text：纯文本提取
    p_text = sub.add_parser("text", help="提取纯文本（不写文件，仅输出 JSON）")
    p_text.add_argument("pdf", help="PDF 文件路径")

    # markdown：含表格的 Markdown 提取
    p_md = sub.add_parser("markdown", help="提取含附表的 Markdown")
    p_md.add_argument("pdf", help="PDF 文件路径")
    p_md.add_argument(
        "--pages",
        default=None,
        help="仅提取指定页（0 索引，逗号分隔，如 0,1,2）；默认提取全部页",
    )
    p_md.add_argument(
        "--save-md",
        action="store_true",
        help="是否将 Markdown 内容写盘为 md 文件",
    )
    p_md.add_argument("--out-dir", default=None, help="md 文件输出目录，默认 reports/pdf")

    # all：全流程
    p_all = sub.add_parser("all", help="执行分类+纯文本+Markdown 全流程")
    p_all.add_argument("pdf", help="PDF 文件路径")
    p_all.add_argument(
        "--pages",
        default=None,
        help="仅作用于 Markdown 步骤（0 索引，逗号分隔）；纯文本仍为全文",
    )
    p_all.add_argument(
        "--save-md",
        action="store_true",
        help="是否将 Markdown 内容写盘为 md 文件",
    )
    p_all.add_argument("--out-dir", default=None, help="md 文件输出目录，默认 reports/pdf")

    return parser


def _resolve_out_dir(args: argparse.Namespace) -> Path:
    """解析输出目录：优先取 --out-dir，否则用默认 OUTPUT_DIR。

    Args:
        args: 已解析的命令行参数。

    Returns:
        输出目录路径。
    """
    return Path(args.out_dir) if args.out_dir else OUTPUT_DIR


def main(argv: Optional[List[str]] = None) -> int:
    """命令行入口。

    Args:
        argv: 可选的参数列表，默认从 sys.argv 读取。

    Returns:
        进程退出码：0 成功；1 处理异常；2 文件未找到。
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    pdf_path = Path(args.pdf)
    meta_tool = "pdf_extract"

    try:
        if args.command == "detect":
            cls = classify_pdf_doc(pdf_path)
            output = {
                "success": True,
                "data": {
                    "pdf_type": cls.pdf_type,
                    "page_count": cls.page_count,
                    "pages_needing_ocr": list(cls.pages_needing_ocr),
                    "confidence": cls.confidence,
                    "scanned": _scan_flag(cls),
                },
                "meta": _build_meta(meta_tool, "detect", pdf_path),
            }

        elif args.command == "text":
            cls = classify_pdf_doc(pdf_path)
            scan = _scan_flag(cls)
            # 扫描格式：无法提取文本，返回标志与空内容
            if scan["scanned"]:
                output = {
                    "success": True,
                    "data": {
                        "scanned": scan,
                        "length": 0,
                        "content": "",
                    },
                    "meta": _build_meta(meta_tool, "text", pdf_path),
                }
            else:
                text = extract_plain_text(pdf_path)
                output = {
                    "success": True,
                    "data": {
                        "scanned": scan,
                        "length": len(text),
                        "content": text,
                    },
                    "meta": _build_meta(meta_tool, "text", pdf_path),
                }

        elif args.command == "markdown":
            pages = _parse_pages(args.pages)
            cls = classify_pdf_doc(pdf_path)
            scan = _scan_flag(cls)
            # 扫描格式：无法提取表格/Markdown，返回标志与空内容
            if scan["scanned"]:
                output = {
                    "success": True,
                    "data": {
                        "scanned": scan,
                        "title": None,
                        "pages_with_tables": [],
                        "pages_with_columns": [],
                        "processing_time_ms": 0,
                        "length": 0,
                        "content": "",
                        "file": None,
                    },
                    "meta": _build_meta(meta_tool, "markdown", pdf_path),
                }
            else:
                result = extract_markdown(pdf_path, pages=pages)
                md_file: Optional[str] = None
                if args.save_md:
                    out_dir = _resolve_out_dir(args)
                    _ensure_output_dir(out_dir)
                    md_file_path = _output_path(pdf_path, "markdown", out_dir)
                    md_file_path.write_text(result.markdown, encoding="utf-8")
                    md_file = str(md_file_path)
                output = {
                    "success": True,
                    "data": {
                        "scanned": scan,
                        "title": result.title,
                        "pages_with_tables": list(result.pages_with_tables),
                        "pages_with_columns": list(result.pages_with_columns),
                        "processing_time_ms": result.processing_time_ms,
                        "length": len(result.markdown),
                        "content": result.markdown,
                        "file": md_file,
                    },
                    "meta": _build_meta(meta_tool, "markdown", pdf_path),
                }

        elif args.command == "all":
            pages = _parse_pages(args.pages)
            out_dir = _resolve_out_dir(args)
            data = run_all(
                pdf_path, pages=pages, save_md=args.save_md, out_dir=out_dir
            )
            output = {
                "success": True,
                "data": data,
                "meta": _build_meta(meta_tool, "all", pdf_path),
            }

        print(json.dumps(output, ensure_ascii=False))

    except FileNotFoundError as exc:
        print(
            json.dumps(
                {"success": False, "error": str(exc),
                 "meta": _build_meta(meta_tool, args.command, pdf_path)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2
    except Exception as exc:  # noqa: BLE001  命令行入口需兜底所有异常
        print(
            json.dumps(
                {"success": False, "error": f"处理失败: {exc}",
                 "meta": _build_meta(meta_tool, args.command, pdf_path)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())