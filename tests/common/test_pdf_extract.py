"""pdf_extract 工具单元测试。

使用 mock 隔离 pdf_inspector 库与真实 PDF 文件，保证测试快速、不依赖外部资源。
覆盖范围：工具函数、三个业务函数（classify/text/markdown）、run_all 全流程、
命令行解析与 main 入口的正常及异常分支。

运行方式：
    python -m pytest tests/common/test_pdf_extract.py -v
"""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# 将项目根目录加入 sys.path（动态计算，兼容跨平台）
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.common import pdf_extract as tool  # noqa: E402


# ===========================================================================
# 工具函数
# ===========================================================================
def test_output_path_naming() -> None:
    """输出文件名应形如 {stem}.md（后缀为空时不加后缀）。"""
    pdf = Path("/tmp/601899_2026半年报.pdf")
    out = tool._output_path(pdf, "", Path("/tmp/out"))
    assert out == Path("/tmp/out/601899_2026半年报.md")


def test_parse_pages_normal() -> None:
    """逗号分隔的页码应正确解析为整数列表；空输入返回 None。"""
    assert tool._parse_pages(None) is None
    assert tool._parse_pages("") is None
    assert tool._parse_pages("0,1,2") == [0, 1, 2]
    # 应自动去除空白并忽略空段
    assert tool._parse_pages(" 0 , 1 , ") == [0, 1]


def test_parse_pages_invalid() -> None:
    """非整数页码应抛出 ValueError。"""
    with pytest.raises(ValueError):
        tool._parse_pages("0,a,2")


def test_ensure_output_dir(tmp_path: Path) -> None:
    """应创建不存在的（含父级）输出目录并返回该路径。"""
    target = tmp_path / "nested" / "out"
    result = tool._ensure_output_dir(target)
    assert result == target
    assert target.is_dir()


# ===========================================================================
# 业务函数（mock pdf_inspector，不接触真实 PDF）
# ===========================================================================
def test_classify_pdf_doc_mocked(tmp_path: Path) -> None:
    """classify_pdf_doc 应透传路径并返回分类对象。"""
    pdf = tmp_path / "sample.pdf"
    pdf.write_text("dummy", encoding="utf-8")
    fake = MagicMock(
        pdf_type="text_based",
        page_count=5,
        pages_needing_ocr=[2, 3],
        confidence=0.9,
    )
    with patch.object(tool.pdf_inspector, "classify_pdf", return_value=fake) as mock_fn:
        result = tool.classify_pdf_doc(pdf)
    mock_fn.assert_called_once_with(str(pdf))
    assert result.pdf_type == "text_based"
    assert result.page_count == 5


def test_classify_pdf_doc_file_not_found() -> None:
    """文件不存在时应抛出 FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        tool.classify_pdf_doc(Path("nonexistent.pdf"))


def test_extract_plain_text_mocked(tmp_path: Path) -> None:
    """extract_plain_text 应返回库返回的文本。"""
    pdf = tmp_path / "sample.pdf"
    pdf.write_text("dummy", encoding="utf-8")
    with patch.object(tool.pdf_inspector, "extract_text", return_value="你好"):
        text = tool.extract_plain_text(pdf)
    assert text == "你好"


def test_extract_markdown_mocked(tmp_path: Path) -> None:
    """extract_markdown 应将 pages 透传给 process_pdf 并返回其结果。"""
    pdf = tmp_path / "sample.pdf"
    pdf.write_text("dummy", encoding="utf-8")
    fake = MagicMock(
        markdown="# 标题\n",
        title="标题",
        pages_with_tables=[1],
        pages_with_columns=[],
        processing_time_ms=10,
        pdf_type="text_based",
        page_count=2,
        confidence=1.0,
    )
    with patch.object(tool.pdf_inspector, "process_pdf", return_value=fake) as mock_fn:
        result = tool.extract_markdown(pdf, pages=[0, 1])
    mock_fn.assert_called_once_with(str(pdf), pages=[0, 1])
    assert result.markdown == "# 标题\n"


def test_extract_markdown_no_pages(tmp_path: Path) -> None:
    """未指定 pages 时应透传 None（表示提取全部页）。"""
    pdf = tmp_path / "sample.pdf"
    pdf.write_text("dummy", encoding="utf-8")
    fake = MagicMock(markdown="", title=None, pages_with_tables=[],
                     pages_with_columns=[], processing_time_ms=1)
    with patch.object(tool.pdf_inspector, "process_pdf", return_value=fake) as mock_fn:
        tool.extract_markdown(pdf)
    mock_fn.assert_called_once_with(str(pdf), pages=None)


def test_run_all_mocked(tmp_path: Path) -> None:
    """run_all 应依次执行三步并返回完整汇总字典。"""
    pdf = tmp_path / "sample.pdf"
    pdf.write_text("dummy", encoding="utf-8")
    out_dir = tmp_path / "out"
    fake_cls = MagicMock(
        pdf_type="text_based",
        page_count=3,
        pages_needing_ocr=[],
        confidence=1.0,
    )
    fake_result = MagicMock(
        markdown="|a|b|\n|---|---|\n|1|2|\n",
        title="标题",
        pages_with_tables=[2],
        pages_with_columns=[2],
        processing_time_ms=13,
    )
    with patch.object(tool.pdf_inspector, "classify_pdf", return_value=fake_cls), \
            patch.object(tool.pdf_inspector, "extract_text", return_value="一些文本"), \
            patch.object(tool.pdf_inspector, "process_pdf", return_value=fake_result):
        summary = tool.run_all(pdf, out_dir=out_dir)

    # 汇总字段正确
    assert summary["classify"]["pdf_type"] == "text_based"
    assert summary["text"]["length"] == len("一些文本")
    assert summary["text"]["content"] == "一些文本"
    assert summary["markdown"]["pages_with_tables"] == [2]


def test_run_all_save_md(tmp_path: Path) -> None:
    """save_md=True 时应将 Markdown 写盘为 md 文件并记录 file 字段。"""
    pdf = tmp_path / "sample.pdf"
    pdf.write_text("dummy", encoding="utf-8")
    out_dir = tmp_path / "out"
    fake_cls = MagicMock(
        pdf_type="text_based", page_count=1, pages_needing_ocr=[], confidence=1.0
    )
    fake_result = MagicMock(
        markdown="|a|b|\n|---|---|\n|1|2|\n",
        title="标题",
        pages_with_tables=[0],
        pages_with_columns=[],
        processing_time_ms=8,
    )
    with patch.object(tool.pdf_inspector, "classify_pdf", return_value=fake_cls), \
            patch.object(tool.pdf_inspector, "extract_text", return_value="txt"), \
            patch.object(tool.pdf_inspector, "process_pdf", return_value=fake_result):
        summary = tool.run_all(pdf, save_md=True, out_dir=out_dir)

    md_file = (out_dir / "sample.md")
    assert md_file.exists()
    assert md_file.read_text(encoding="utf-8").startswith("|a|b|")
    assert summary["markdown"]["file"] == str(md_file)


def test_run_all_no_save_md(tmp_path: Path) -> None:
    """save_md=False 时不应写盘，file 字段为 None。"""
    pdf = tmp_path / "sample.pdf"
    pdf.write_text("dummy", encoding="utf-8")
    out_dir = tmp_path / "out"
    fake_cls = MagicMock(
        pdf_type="text_based", page_count=1, pages_needing_ocr=[], confidence=1.0
    )
    fake_result = MagicMock(
        markdown="# m\n", title="", pages_with_tables=[], pages_with_columns=[],
        processing_time_ms=5,
    )
    with patch.object(tool.pdf_inspector, "classify_pdf", return_value=fake_cls), \
            patch.object(tool.pdf_inspector, "extract_text", return_value="txt"), \
            patch.object(tool.pdf_inspector, "process_pdf", return_value=fake_result):
        summary = tool.run_all(pdf, save_md=False, out_dir=out_dir)

    assert summary["markdown"]["file"] is None
    assert not (out_dir / "sample.md").exists()


# ===========================================================================
# 命令行解析与 main 入口
# ===========================================================================
def test_build_parser_subcommands() -> None:
    """各子命令与参数应被正确解析。"""
    parser = tool.build_parser()
    assert parser.parse_args(["detect", "x.pdf"]).command == "detect"
    args = parser.parse_args(["markdown", "x.pdf", "--pages", "0,1", "--save-md"])
    assert args.command == "markdown"
    assert args.pages == "0,1"
    assert args.save_md is True
    assert args.pdf == "x.pdf"


def test_resolve_out_dir() -> None:
    """--out-dir 优先于默认 OUTPUT_DIR。"""
    args = MagicMock()
    args.out_dir = None
    assert tool._resolve_out_dir(args) == tool.OUTPUT_DIR
    args.out_dir = "reports/other"
    assert tool._resolve_out_dir(args) == Path("reports/other")


def test_main_detect_missing_file(capsys: pytest.CaptureFixture[str]) -> None:
    """对不存在的文件，main 应返回退出码 2。"""
    code = tool.main(["detect", "nonexistent.pdf"])
    assert code == 2
    assert "不存在" in capsys.readouterr().err


def test_main_detect_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """detect 子命令成功时应返回 0 并输出 JSON。"""
    pdf = tmp_path / "s.pdf"
    pdf.write_text("d", encoding="utf-8")
    fake = MagicMock(
        pdf_type="text_based", page_count=1, pages_needing_ocr=[], confidence=1.0
    )
    with patch.object(tool.pdf_inspector, "classify_pdf", return_value=fake):
        code = tool.main(["detect", str(pdf)])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert out["data"]["pdf_type"] == "text_based"


def test_main_all_mocked(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """all 子命令应输出含 classify/text/markdown 的 JSON。"""
    pdf = tmp_path / "s.pdf"
    pdf.write_text("d", encoding="utf-8")
    fake_cls = MagicMock(
        pdf_type="text_based", page_count=2, pages_needing_ocr=[], confidence=1.0
    )
    fake_result = MagicMock(
        markdown="# m\n", title="", pages_with_tables=[], pages_with_columns=[],
        processing_time_ms=5,
    )
    with patch.object(tool.pdf_inspector, "classify_pdf", return_value=fake_cls), \
            patch.object(tool.pdf_inspector, "extract_text", return_value="txt"), \
            patch.object(tool.pdf_inspector, "process_pdf", return_value=fake_result):
        code = tool.main(["all", str(pdf)])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert "classify" in out["data"]
    assert "text" in out["data"]
    assert "markdown" in out["data"]


def test_main_markdown_save(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """markdown 子命令 --save-md 应写盘并记录 file 字段。"""
    pdf = tmp_path / "s.pdf"
    pdf.write_text("d", encoding="utf-8")
    out_dir = tmp_path / "out"
    fake_cls = MagicMock(
        pdf_type="text_based", page_count=1, pages_needing_ocr=[], confidence=1.0
    )
    fake = MagicMock(
        markdown="# m\n", title="", pages_with_tables=[], pages_with_columns=[],
        processing_time_ms=5,
    )
    with patch.object(tool.pdf_inspector, "classify_pdf", return_value=fake_cls), \
            patch.object(tool.pdf_inspector, "process_pdf", return_value=fake):
        code = tool.main(
            ["markdown", str(pdf), "--save-md", "--out-dir", str(out_dir)]
        )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["data"]["file"] == str(out_dir / "s.md")
    assert (out_dir / "s.md").exists()


# ===========================================================================
# 扫描格式检测（scanned / mixed）
# ===========================================================================
def test_scan_flag_text_based() -> None:
    """纯文本 PDF 不应标记为扫描格式。"""
    cls = MagicMock(pdf_type="text_based", pages_needing_ocr=[])
    flag = tool._scan_flag(cls)
    assert flag["scanned"] is False
    assert "note" not in flag


def test_scan_flag_scanned() -> None:
    """scanned 类型应标记为扫描格式，并给出需 OCR 提示。"""
    cls = MagicMock(pdf_type="scanned", pages_needing_ocr=[0, 1])
    flag = tool._scan_flag(cls)
    assert flag["scanned"] is True
    assert "OCR" in flag["note"]
    assert "0, 1" in flag["note"]


def test_scan_flag_mixed() -> None:
    """mixed 类型（含需 OCR 页面）应标记为扫描格式。"""
    cls = MagicMock(pdf_type="mixed", pages_needing_ocr=[3])
    flag = tool._scan_flag(cls)
    assert flag["scanned"] is True


def test_scan_flag_pages_needing_ocr() -> None:
    """即使 pdf_type 为 text_based，只要存在需 OCR 页面也应标记。"""
    cls = MagicMock(pdf_type="text_based", pages_needing_ocr=[2])
    flag = tool._scan_flag(cls)
    assert flag["scanned"] is True


def test_run_all_scanned(tmp_path: Path) -> None:
    """扫描 PDF 的 run_all 应返回 scanned 标志，且 content 为空。"""
    pdf = tmp_path / "scan.pdf"
    pdf.write_text("dummy", encoding="utf-8")
    fake_cls = MagicMock(
        pdf_type="scanned", page_count=1, pages_needing_ocr=[0], confidence=0.9
    )
    with patch.object(tool.pdf_inspector, "classify_pdf", return_value=fake_cls), \
            patch.object(tool.pdf_inspector, "extract_text") as mock_text, \
            patch.object(tool.pdf_inspector, "process_pdf") as mock_proc:
        summary = tool.run_all(pdf, out_dir=tmp_path)
    # 扫描格式：不应调用提取函数
    mock_text.assert_not_called()
    mock_proc.assert_not_called()
    assert summary["scanned"]["scanned"] is True
    assert summary["text"]["content"] == ""
    assert summary["markdown"]["content"] == ""


def test_main_text_scanned(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """text 子命令对扫描 PDF 应返回 scanned 标志与空内容。"""
    pdf = tmp_path / "scan.pdf"
    pdf.write_text("dummy", encoding="utf-8")
    fake_cls = MagicMock(
        pdf_type="scanned", page_count=1, pages_needing_ocr=[0], confidence=0.9
    )
    with patch.object(tool.pdf_inspector, "classify_pdf", return_value=fake_cls), \
            patch.object(tool.pdf_inspector, "extract_text") as mock_text:
        code = tool.main(["text", str(pdf)])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["data"]["scanned"]["scanned"] is True
    assert out["data"]["content"] == ""
    mock_text.assert_not_called()


def test_main_markdown_scanned(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """markdown 子命令对扫描 PDF 应返回 scanned 标志且不写盘。"""
    pdf = tmp_path / "scan.pdf"
    pdf.write_text("dummy", encoding="utf-8")
    out_dir = tmp_path / "out"
    fake_cls = MagicMock(
        pdf_type="scanned", page_count=1, pages_needing_ocr=[0], confidence=0.9
    )
    with patch.object(tool.pdf_inspector, "classify_pdf", return_value=fake_cls), \
            patch.object(tool.pdf_inspector, "process_pdf") as mock_proc:
        code = tool.main(
            ["markdown", str(pdf), "--save-md", "--out-dir", str(out_dir)]
        )
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["data"]["scanned"]["scanned"] is True
    assert out["data"]["content"] == ""
    assert out["data"]["file"] is None
    mock_proc.assert_not_called()
    assert not (out_dir / "scan.md").exists()