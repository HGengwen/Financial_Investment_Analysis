#!/usr/bin/env python3
"""report_hub 工具测试模块。

测试 tools/common/report_hub.py 的各功能模块，使用 unittest + mock，无网络依赖。

测试范围:
  1. TestDisclosureWindow — 披露窗口判断纯函数
  2. TestEnsureCache      — ensure 缓存路径（窗口外命中/窗口内刷新/API失败降级）
  3. TestExtractCache     — extract 结果缓存（md 有效秒回/mtime 失效）
  4. TestListCache        — list 命令元数据枚举

运行方式:
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/common/test_report_hub.py -v
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.common import report_hub  # noqa: E402


class TestDisclosureWindow(unittest.TestCase):
    """披露窗口判断纯函数测试。"""

    def test_annual_in_window(self) -> None:
        """年报 3 月属于披露窗口。"""
        now = datetime(2026, 3, 15)
        self.assertTrue(report_hub._in_disclosure_window("annual", now))

    def test_annual_in_buffer(self) -> None:
        """年报 5 月 15 日（缓冲期）属于披露窗口。"""
        now = datetime(2026, 5, 15)
        self.assertTrue(report_hub._in_disclosure_window("annual", now))

    def test_annual_outside_window(self) -> None:
        """年报 6 月不属于披露窗口（已过缓冲期）。"""
        now = datetime(2026, 6, 15)
        self.assertFalse(report_hub._in_disclosure_window("annual", now))

    def test_semiannual_window(self) -> None:
        """半年报 8 月属于披露窗口，1 月不属于。"""
        self.assertTrue(
            report_hub._in_disclosure_window("semiannual", datetime(2026, 8, 1))
        )
        self.assertFalse(
            report_hub._in_disclosure_window("semiannual", datetime(2026, 1, 15))
        )

    def test_quarterly_window(self) -> None:
        """季报 4 月和 10 月属于披露窗口，6 月不属于。"""
        self.assertTrue(
            report_hub._in_disclosure_window("quarterly", datetime(2026, 4, 1))
        )
        self.assertTrue(
            report_hub._in_disclosure_window("quarterly", datetime(2026, 10, 15))
        )
        self.assertFalse(
            report_hub._in_disclosure_window("quarterly", datetime(2026, 6, 15))
        )

    def test_unknown_type(self) -> None:
        """未知报告类型不在任何窗口内。"""
        now = datetime(2026, 3, 15)
        self.assertFalse(report_hub._in_disclosure_window("unknown", now))


class TestEnsureCache(unittest.TestCase):
    """ensure 缓存路径测试（mock 下载层，无网络）。"""

    def setUp(self) -> None:
        """每个测试前隔离 cninfo_reports 与 .meta 目录。"""
        self.tmp = tempfile.TemporaryDirectory()
        report_hub.CNINFO_DIR = Path(self.tmp.name) / "cninfo_reports"
        report_hub.META_DIR = report_hub.CNINFO_DIR / ".meta"
        report_hub.EXTRACT_DIR = report_hub.CNINFO_DIR / "extracted"
        report_hub.META_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        """清理临时目录并恢复默认常量。"""
        self.tmp.cleanup()
        report_hub.CNINFO_DIR = PROJECT_ROOT / "cninfo_reports"
        report_hub.META_DIR = report_hub.CNINFO_DIR / ".meta"
        report_hub.EXTRACT_DIR = report_hub.CNINFO_DIR / "extracted"

    def _make_args(self, code: str = "601899",
                   report_type: str = "annual", force: bool = False):
        """构造 ensure 的 mock 参数对象。"""
        return SimpleNamespace(
            code=code, report_type=report_type, force=force
        )

    def test_ensure_downloads_when_no_cache(self) -> None:
        """无本地缓存时调用下载并返回 refresh。"""
        pdf_path = str(report_hub.CNINFO_DIR / "601899_2025年报.pdf")
        with patch(
            "tools.common.report_hub._download_report",
            return_value=(pdf_path, "2025"),
        ):
            args = self._make_args()
            result = report_hub.cmd_ensure(args)
        self.assertTrue(result["success"])
        self.assertEqual(result["meta"]["cache"], "check_hit")
        self.assertEqual(result["year"], "2025")
        # 元数据已保存
        meta = report_hub._load_meta("601899", "annual")
        self.assertEqual(meta["year"], "2025")

    def test_ensure_window_hit_zero_api(self) -> None:
        """窗口外 + 元数据有效 → 零 API 直接命中。"""
        # 预置元数据与本地文件
        pdf_path = str(report_hub.CNINFO_DIR / "601899_2025年报.pdf")
        Path(pdf_path).write_bytes(b"x" * (1024 * 1024 + 10))
        report_hub._save_meta("601899", "annual", {
            "year": "2025",
            "report_type": "annual",
            "pdf_name": "601899_2025年报.pdf",
            "last_check": "2026-03-01T00:00:00",
        })
        with patch(
            "tools.common.report_hub._download_report",
            return_value=(None, None),
        ) as mock_download:
            # 6 月（窗口外）
            args = self._make_args()
            with patch(
                "tools.common.report_hub._in_disclosure_window",
                return_value=False,
            ):
                result = report_hub.cmd_ensure(args)
        mock_download.assert_not_called()
        self.assertEqual(result["meta"]["cache"], "hit")
        self.assertTrue(result["success"])

    def test_ensure_window_in_refreshes(self) -> None:
        """窗口内 + 超 7 天未查 → 调用下载刷新。"""
        pdf_path = str(report_hub.CNINFO_DIR / "601899_2025年报.pdf")
        Path(pdf_path).write_bytes(b"x" * (1024 * 1024 + 10))
        report_hub._save_meta("601899", "annual", {
            "year": "2025",
            "report_type": "annual",
            "pdf_name": "601899_2025年报.pdf",
            "last_check": "2026-01-01T00:00:00",
        })
        with patch(
            "tools.common.report_hub._download_report",
            return_value=(pdf_path, "2025"),
        ) as mock_download:
            args = self._make_args()
            with patch(
                "tools.common.report_hub._in_disclosure_window",
                return_value=True,
            ):
                result = report_hub.cmd_ensure(args)
        mock_download.assert_called_once_with("601899", "annual")
        self.assertEqual(result["meta"]["cache"], "refresh")

    def test_ensure_api_fail_stale(self) -> None:
        """API 失败但本地有旧文件 → 降级返回 stale。"""
        pdf_path = str(report_hub.CNINFO_DIR / "601899_2025年报.pdf")
        Path(pdf_path).write_bytes(b"x" * (1024 * 1024 + 10))
        report_hub._save_meta("601899", "annual", {
            "year": "2025",
            "report_type": "annual",
            "pdf_name": "601899_2025年报.pdf",
            "last_check": "2026-01-01T00:00:00",
        })
        with patch(
            "tools.common.report_hub._download_report",
            return_value=(None, None),
        ):
            args = self._make_args()
            with patch(
                "tools.common.report_hub._in_disclosure_window",
                return_value=True,
            ):
                result = report_hub.cmd_ensure(args)
        self.assertTrue(result["success"])
        self.assertEqual(result["meta"]["cache"], "stale")

    def test_ensure_no_cache_fail_error(self) -> None:
        """无本地缓存且 API 失败 → 返回 error。"""
        with patch(
            "tools.common.report_hub._download_report",
            return_value=(None, None),
        ):
            args = self._make_args()
            result = report_hub.cmd_ensure(args)
        self.assertFalse(result["success"])
        self.assertEqual(result["meta"]["cache"], "error")

    def test_ensure_force_bypasses_window(self) -> None:
        """--force 跳过窗口检查直接下载。"""
        pdf_path = str(report_hub.CNINFO_DIR / "601899_2025年报.pdf")
        with patch(
            "tools.common.report_hub._download_report",
            return_value=(pdf_path, "2025"),
        ) as mock_download:
            args = self._make_args(force=True)
            result = report_hub.cmd_ensure(args)
        mock_download.assert_called_once()
        self.assertEqual(result["meta"]["cache"], "check_hit")


class TestExtractCache(unittest.TestCase):
    """extract 结果缓存测试（mock 子进程，无网络）。"""

    def setUp(self) -> None:
        """隔离提取目录与构造测试 PDF。"""
        self.tmp = tempfile.TemporaryDirectory()
        report_hub.CNINFO_DIR = Path(self.tmp.name) / "cninfo_reports"
        report_hub.META_DIR = report_hub.CNINFO_DIR / ".meta"
        report_hub.EXTRACT_DIR = report_hub.CNINFO_DIR / "extracted"
        report_hub.META_DIR.mkdir(parents=True, exist_ok=True)
        report_hub.EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        self.pdf = report_hub.CNINFO_DIR / "601899_2025年报.pdf"
        self.pdf.write_bytes(b"x" * (1024 * 1024 + 10))

    def tearDown(self) -> None:
        """清理临时目录。"""
        self.tmp.cleanup()
        report_hub.CNINFO_DIR = PROJECT_ROOT / "cninfo_reports"
        report_hub.META_DIR = report_hub.CNINFO_DIR / ".meta"
        report_hub.EXTRACT_DIR = report_hub.CNINFO_DIR / "extracted"

    def test_extract_md_valid_returns_hit(self) -> None:
        """md 存在且新于 PDF → 秒回 hit。"""
        md_path = report_hub.EXTRACT_DIR / "601899_2025年报.md"
        md_path.write_text("# 提取结果", encoding="utf-8")
        # 确保 md mtime >= pdf mtime
        pdf_mtime = os.path.getmtime(self.pdf)
        os.utime(md_path, (pdf_mtime, pdf_mtime))

        args = SimpleNamespace(
            pdf=str(self.pdf), code=None, report_type="annual",
            pages=None, force_ocr=False, ocr_langs=None,
        )
        with patch(
            "tools.common.report_hub.subprocess.run",
        ) as mock_run:
            result = report_hub.cmd_extract(args)
        mock_run.assert_not_called()
        self.assertEqual(result["meta"]["cache"], "hit")

    def test_extract_md_stale_triggers_extract(self) -> None:
        """md 过期（mtime 旧于 PDF）→ 调用 pdf_extract 重提取。"""
        md_path = report_hub.EXTRACT_DIR / "601899_2025年报.md"
        md_path.write_text("# 旧结果", encoding="utf-8")
        # 故意让 md mtime 早于 pdf
        os.utime(md_path, (1, 1))

        args = SimpleNamespace(
            pdf=str(self.pdf), code=None, report_type="annual",
            pages=None, force_ocr=False, ocr_langs=None,
        )

        def _fake_run(*_args, **_kwargs):
            """模拟 pdf_extract 成功并覆写目标 md 文件。"""
            md_path.write_text("# 新结果", encoding="utf-8")
            return unittest.mock.MagicMock(returncode=0, stdout="", stderr="")

        with patch(
            "tools.common.report_hub.subprocess.run",
            side_effect=_fake_run,
        ) as mock_run:
            result = report_hub.cmd_extract(args)
        mock_run.assert_called_once()
        self.assertEqual(result["meta"]["cache"], "refresh")

    def test_extract_with_pages_naming(self) -> None:
        """--pages 使用规范化文件名缓存（{stem}.md 重命名为带后缀缓存名）。"""
        args = SimpleNamespace(
            pdf=str(self.pdf), code=None, report_type="annual",
            pages="0-10", force_ocr=False, ocr_langs=None,
        )
        expected = report_hub.EXTRACT_DIR / "601899_2025年报_p0_10.md"
        raw_md = report_hub.EXTRACT_DIR / "601899_2025年报.md"

        def _fake_run(*_args, **_kwargs):
            """模拟 pdf_extract 成功并写盘 {stem}.md（pdf_extract 的真实行为）。"""
            raw_md.write_text("# mock", encoding="utf-8")
            return unittest.mock.MagicMock(returncode=0, stdout="", stderr="")

        with patch(
            "tools.common.report_hub.subprocess.run",
            side_effect=_fake_run,
        ):
            result = report_hub.cmd_extract(args)
        self.assertEqual(result["extract_path"], str(expected))
        self.assertEqual(result["meta"]["cache"], "refresh")

    def test_extract_scanned_failure(self) -> None:
        """扫描件失败返回 scanned 标志且不落缓存。"""
        args = SimpleNamespace(
            pdf=str(self.pdf), code=None, report_type="annual",
            pages=None, force_ocr=False, ocr_langs=None,
        )
        mock_proc = unittest.mock.MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({
            "scanned": True,
            "note": "检测到扫描格式",
        })
        mock_proc.stderr = ""
        with patch(
            "tools.common.report_hub.subprocess.run",
            return_value=mock_proc,
        ):
            result = report_hub.cmd_extract(args)
        self.assertFalse(result["success"])
        self.assertTrue(result["scanned"])
        # 错误响应 meta 应包含 timestamp，与其他错误响应格式一致
        self.assertIn("timestamp", result["meta"])


class TestListCache(unittest.TestCase):
    """list 命令测试。"""

    def setUp(self) -> None:
        """隔离元数据目录。"""
        self.tmp = tempfile.TemporaryDirectory()
        report_hub.CNINFO_DIR = Path(self.tmp.name) / "cninfo_reports"
        report_hub.META_DIR = report_hub.CNINFO_DIR / ".meta"
        report_hub.EXTRACT_DIR = report_hub.CNINFO_DIR / "extracted"
        report_hub.META_DIR.mkdir(parents=True, exist_ok=True)
        report_hub.EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        """清理临时目录。"""
        self.tmp.cleanup()
        report_hub.CNINFO_DIR = PROJECT_ROOT / "cninfo_reports"
        report_hub.META_DIR = report_hub.CNINFO_DIR / ".meta"
        report_hub.EXTRACT_DIR = report_hub.CNINFO_DIR / "extracted"

    def test_list_empty(self) -> None:
        """无缓存时返回空列表。"""
        args = SimpleNamespace(code="601899")
        result = report_hub.cmd_list(args)
        self.assertTrue(result["success"])
        self.assertEqual(result["reports"], [])

    def test_list_reports(self) -> None:
        """列出已缓存报告及其提取状态。"""
        pdf_path = report_hub.CNINFO_DIR / "601899_2025年报.pdf"
        pdf_path.write_bytes(b"x" * (1024 * 1024 + 10))
        md_path = report_hub.EXTRACT_DIR / "601899_2025年报.md"
        md_path.write_text("# 提取", encoding="utf-8")
        report_hub._save_meta("601899", "annual", {
            "year": "2025",
            "report_type": "annual",
            "pdf_name": "601899_2025年报.pdf",
            "last_check": "2026-03-01T00:00:00",
            "last_download": "2026-03-01T00:00:00",
        })
        args = SimpleNamespace(code="601899")
        result = report_hub.cmd_list(args)
        self.assertEqual(len(result["reports"]), 1)
        report = result["reports"][0]
        self.assertEqual(report["year"], "2025")
        self.assertTrue(report["pdf_exists"])
        self.assertTrue(report["extracted"])


class TestHelperFunctions(unittest.TestCase):
    """辅助函数测试。"""

    def test_build_pdf_name(self) -> None:
        """PDF 文件名构造。"""
        self.assertEqual(
            report_hub._build_pdf_name("601899", "2025", "annual"),
            "601899_2025年报.pdf",
        )
        self.assertEqual(
            report_hub._build_pdf_name("300502", "2025", "quarterly"),
            "300502_2025季报.pdf",
        )

    def test_normalize_pages(self) -> None:
        """pages 参数规范化。"""
        self.assertEqual(report_hub._normalize_pages("0-10"), "p0_10")
        self.assertEqual(
            report_hub._normalize_pages("40-60,120-135"), "p40_60_120_135"
        )

    def test_meta_roundtrip(self) -> None:
        """元数据保存与加载往返。"""
        tmp = tempfile.TemporaryDirectory()
        report_hub.META_DIR = Path(tmp.name) / ".meta"
        try:
            report_hub._save_meta("601899", "annual", {
                "year": "2025", "report_type": "annual",
            })
            meta = report_hub._load_meta("601899", "annual")
            self.assertEqual(meta["year"], "2025")
            # 不存在的 key 返回空字典
            self.assertEqual(
                report_hub._load_meta("999999", "annual"), {}
            )
        finally:
            tmp.cleanup()
            report_hub.META_DIR = report_hub.CNINFO_DIR / ".meta"


class TestDownloadReport(unittest.TestCase):
    """_download_report 年份提取逻辑测试（mock 下载器，无网络）。"""

    def setUp(self) -> None:
        """每个测试前创建临时目录并隔离 CNINFO_DIR。"""
        self.tmp = tempfile.TemporaryDirectory()
        report_hub.CNINFO_DIR = Path(self.tmp.name)
        self.downloader_patch = patch(
            "tools.a_share.stock_equity.CnInfoReportDownloader"
        )
        self.mock_downloader_cls = self.downloader_patch.start()

    def tearDown(self) -> None:
        """清理 mock 与临时目录，恢复默认常量。"""
        self.downloader_patch.stop()
        self.tmp.cleanup()
        report_hub.CNINFO_DIR = PROJECT_ROOT / "cninfo_reports"

    def _make_pdf(self, name: str) -> str:
        """在临时目录创建真实存在的 PDF 占位文件并返回路径。"""
        path = Path(self.tmp.name) / name
        path.write_bytes(b"fake pdf content")
        return str(path)

    def test_year_extracted_from_filename(self) -> None:
        """文件名含 _YYYY 时正确提取年份并返回文件路径。"""
        pdf_path = self._make_pdf("601899_2025年报.pdf")
        self.mock_downloader_cls.return_value.download_latest_report.return_value = (
            pdf_path
        )
        result_path, year = report_hub._download_report("601899", "annual")
        self.assertEqual(result_path, pdf_path)
        self.assertEqual(year, "2025")

    def test_rename_quarterly_to_standard_name(self) -> None:
        """季报文件名含季度前缀（如 20251季报）时重命名为标准名（2025季报）。"""
        # stock_equity 下载的季报文件名：601899_20251季报.pdf
        raw_path = self._make_pdf("601899_20251季报.pdf")
        self.mock_downloader_cls.return_value.download_latest_report.return_value = (
            raw_path
        )
        result_path, year = report_hub._download_report("601899", "quarterly")
        # 应返回标准路径
        standard_path = str(Path(self.tmp.name) / "601899_2025季报.pdf")
        self.assertEqual(result_path, standard_path)
        self.assertEqual(year, "2025")
        # 原文件应已不存在（被重命名）
        self.assertFalse(os.path.exists(raw_path))
        self.assertTrue(os.path.exists(standard_path))

    def test_no_rename_when_already_standard(self) -> None:
        """文件名已是标准名时不做重命名操作。"""
        pdf_path = self._make_pdf("601899_2025半年报.pdf")
        self.mock_downloader_cls.return_value.download_latest_report.return_value = (
            pdf_path
        )
        result_path, year = report_hub._download_report("601899", "semiannual")
        self.assertEqual(result_path, pdf_path)
        self.assertEqual(year, "2025")
        # 文件仍在原位置
        self.assertTrue(os.path.exists(pdf_path))

    def test_year_missing_returns_none(self) -> None:
        """文件名不含 _YYYY 模式时返回 (None, None)，避免误判为下载成功。"""
        pdf_path = self._make_pdf("601899_年度报告.pdf")
        self.mock_downloader_cls.return_value.download_latest_report.return_value = (
            pdf_path
        )
        result_path, year = report_hub._download_report("601899", "annual")
        self.assertIsNone(result_path)
        self.assertIsNone(year)

    def test_download_failure_returns_none(self) -> None:
        """下载失败（返回空路径）时返回 (None, None)。"""
        self.mock_downloader_cls.return_value.download_latest_report.return_value = (
            None
        )
        result_path, year = report_hub._download_report("601899", "annual")
        self.assertIsNone(result_path)
        self.assertIsNone(year)


if __name__ == "__main__":
    unittest.main()