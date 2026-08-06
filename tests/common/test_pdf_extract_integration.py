"""pdf_extract 工具集成测试：对真实 PDF 验证提取能力。

测试 PDF（位于 tests/common/ 目录下）：
    - 601899_2026半年报.pdf：3 页业绩预增公告（纯文本，含 1 个表格页）
    - 601899_2025年报.pdf：352 页年度报告（纯文本，含大量财务附表）

策略：
    - 半年报体量小，完整验证分类 / 纯文本 / Markdown / run_all 全流程；
    - 年报体量大，仅验证分类与"限页 Markdown 提取"，避免全文提取耗时。

运行方式：
    python -m pytest tests/common/test_pdf_extract_integration.py -v -s
"""

import sys
from pathlib import Path

import pytest

# 将项目根目录加入 sys.path（动态计算，兼容跨平台）
_PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.common import pdf_extract as tool  # noqa: E402

# 测试 PDF 所在目录（tests/common）
_PDF_DIR: Path = Path(__file__).resolve().parent


@pytest.fixture
def half_report_path() -> Path:
    """601899_2026半年报.pdf：3 页的业绩预增公告（纯文本，含 1 个表格页）。"""
    return _PDF_DIR / "601899_2026半年报.pdf"


@pytest.fixture
def annual_report_path() -> Path:
    """601899_2025年报.pdf：352 页的年度报告（纯文本，含大量财务附表）。"""
    return _PDF_DIR / "601899_2025年报.pdf"


# ===========================================================================
# 半年报（3 页，纯文本，含 1 个表格页）
# ===========================================================================
def test_classify_half_report(half_report_path: Path) -> None:
    """半年报应为纯文本、3 页、无需 OCR。"""
    cls = tool.classify_pdf_doc(half_report_path)
    assert cls.pdf_type == "text_based"
    assert cls.page_count == 3
    assert cls.pages_needing_ocr == []
    assert cls.confidence > 0.5


def test_extract_text_half_report(half_report_path: Path) -> None:
    """半年报纯文本应非空，且含公司名与证券代码。"""
    text = tool.extract_plain_text(half_report_path)
    assert len(text) > 100
    assert "紫金矿业" in text
    assert "601899" in text


def test_extract_markdown_half_report(half_report_path: Path) -> None:
    """半年报 Markdown 应含公司名，并识别到表格页（第 2 页，0 索引）。"""
    result = tool.extract_markdown(half_report_path)
    assert result.pdf_type == "text_based"
    assert len(result.markdown) > 100
    assert "紫金矿业" in result.markdown
    assert 2 in result.pages_with_tables


def test_run_all_half_report(half_report_path: Path, tmp_path: Path) -> None:
    """run_all 应返回完整汇总，save_md=True 时写盘 md 文件。"""
    summary = tool.run_all(half_report_path, save_md=True, out_dir=tmp_path)
    # 汇总字段正确
    assert summary["classify"]["page_count"] == 3
    assert summary["text"]["length"] > 100
    assert summary["markdown"]["length"] > 100
    assert 2 in summary["markdown"]["pages_with_tables"]
    # md 文件已写盘
    md_file = tmp_path / "601899_2026半年报_markdown.md"
    assert md_file.exists()
    assert summary["markdown"]["file"] == str(md_file)


# ===========================================================================
# 年报（352 页，纯文本，含大量财务附表）
# ===========================================================================
def test_classify_annual_report(annual_report_path: Path) -> None:
    """年报应为纯文本、352 页、无需 OCR。"""
    cls = tool.classify_pdf_doc(annual_report_path)
    assert cls.pdf_type == "text_based"
    assert cls.page_count == 352
    assert cls.pages_needing_ocr == []


def test_extract_markdown_annual_report_limited_pages(
    annual_report_path: Path,
) -> None:
    """对年报取前 2 页应快速返回 Markdown。"""
    result = tool.extract_markdown(annual_report_path, pages=[0, 1])
    assert result.page_count == 352
    assert len(result.markdown) > 50