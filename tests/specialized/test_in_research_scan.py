#!/usr/bin/env python3
"""Unit tests for in_research_scan.py 在研重大项目扫描器.

覆盖 mid-trend-tech-screen 步骤 3-A 落地工具：
1. 渠道查询配方构建（与方案文档指令一致、website 需官网域名）
2. 未知渠道报错
3. 渠道结果聚合（去重、top_links、total）
4. scan 全流程（search_fn 注入 mock）
5. Markdown 报告导出
6. CLI list / scan 命令
7. pipeline-npv 子命令（P3-8：校验 / 计算 / 敏感性 / 编排 / 候选提取 / CLI 退出码）
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from unittest import mock

# Add project root to path for imports (dynamic, cross-platform)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from tools.specialized.in_research_scan import (  # noqa: E402
    CHANNELS,
    ANNUAL_REPORT_KEYWORDS,
    ChannelQuery,
    build_queries,
    channel_result,
    aggregate,
    scan,
    export_markdown,
    _main,
    PipelineNpvError,
    load_project_candidates,
    parse_sensitivity_spec,
    extract_project_candidates,
    parse_projects,
    compute_pipeline_npv,
    build_sensitivity,
    run_pipeline_npv,
)


def _mk_item(title: str, url: str, pub: str = "2026-01") -> dict:
    """构造一条标准化搜索结果 dict."""
    return {
        "title": title,
        "url": url,
        "site_name": "某来源",
        "publish_time": pub,
        "summary": f"{title} 摘要",
        "snippet": "",
        "content": "",
        "auth_level": 0,
        "auth_des": "",
        "rank_score": 1,
    }


def _mock_search(dataset=None, **kwargs):
    """mock 搜索函数：按 query 是否包含特征词返回不同结果集.

    Args:
        dataset: 可选，key 为查询关键词子串、value 为结果列表的映射。
        kwargs: 透传搜索参数（scan 调用时注入）。

    Returns:
        匹配的结果列表。
    """
    dataset = dataset or {"默认": [_mk_item("默认结果", "http://default")]}
    query = kwargs.get("query", "")
    for keyword, results in dataset.items():
        if keyword in query:
            return results
    return dataset.get("默认", [])


class TestBuildQueries(unittest.TestCase):
    """Test 渠道查询配方构建."""

    def test_all_channels_built(self):
        """全渠道构建返回 CHANNELS 全部键."""
        queries = build_queries("中芯国际")
        self.assertEqual(set(queries.keys()), set(CHANNELS.keys()))

    def test_gov_query_matches_doc(self):
        """gov 渠道查询词与方案文档一致，限定 gov.cn."""
        q = build_queries("中芯国际")["gov"][0]
        self.assertIn("国家重点研发计划", q.query)
        self.assertIn("重大科技专项", q.query)
        self.assertEqual(q.sites, "gov.cn")
        self.assertEqual(q.time_range, "year")

    def test_patent_query_matches_doc(self):
        """patent 渠道限定国家知识产权局站点."""
        q = build_queries("中芯国际")["patent"][0]
        self.assertIn("发明", q.query)
        self.assertEqual(q.sites, "cpquery.cponline.cnipa.gov.cn")

    def test_bidding_query_matches_doc(self):
        """bidding 渠道限定政府采购平台."""
        q = build_queries("中芯国际")["bidding"][0]
        self.assertIn("中标", q.query)
        self.assertEqual(q.sites, "ccgp.gov.cn")

    def test_academic_sites_pipe(self):
        """academic 渠道站点以 | 分隔（豆包接口口径）."""
        q = build_queries("中芯国际")["academic"][0]
        self.assertIn("arxiv.org", q.sites)
        self.assertIn("|", q.sites)

    def test_investor_two_queries(self):
        """investor 渠道含深交所 + 上交所两条查询."""
        queries = build_queries("中芯国际")["investor"]
        self.assertEqual(len(queries), 2)
        hints = {q.label_hint for q in queries}
        self.assertIn("深交所互动易", hints)
        self.assertIn("上交所 e 互动", hints)

    def test_research_uses_finance(self):
        """research 渠道启用 finance 定向 + 权威度限制."""
        q = build_queries("中芯国际")["research"][0]
        self.assertEqual(q.industry, "finance")
        self.assertEqual(q.auth_level, 1)

    def test_website_requires_site(self):
        """website 渠道在无官网域名时返回空列表."""
        self.assertEqual(build_queries("中芯国际")["website"], [])
        queries = build_queries("中芯国际", official_site="smics.com")["website"]
        self.assertEqual(len(queries), 1)
        self.assertEqual(queries[0].sites, "smics.com")

    def test_unknown_channel_raises(self):
        """未知渠道键抛 ValueError."""
        with self.assertRaises(ValueError):
            build_queries("中芯国际", channels=["nope"])

    def test_subset_channels(self):
        """指定渠道子集时仅返回该子集."""
        queries = build_queries("中芯国际", channels=["patent", "gov"])
        self.assertEqual(set(queries.keys()), {"patent", "gov"})

    def test_annual_report_keywords_present(self):
        """年报在研项目关键词与方案文档一致."""
        for kw in ("在研项目", "研发管线", "研发资本化", "开发支出"):
            self.assertIn(kw, ANNUAL_REPORT_KEYWORDS)


class TestChannelResult(unittest.TestCase):
    """Test 渠道结果聚合."""

    def test_dedup_across_queries(self):
        """跨查询去重：相同标题+链接只计一次."""
        query = ChannelQuery(query="q", sites="site")
        qs = [query, query]
        dup = _mk_item("A", "http://a")
        unique = _mk_item("B", "http://b")
        ch = channel_result("patent", qs, [[dup, unique], [dup, _mk_item("A2", "http://a2")]])
        self.assertEqual(ch["total"], 3)  # A, B, A2

    def test_top_links_capped(self):
        """top_links 最多 5 条."""
        qs = [ChannelQuery(query="q", sites="s")]
        results = [[_mk_item(f"T{i}", f"http://x/{i}") for i in range(8)]]
        ch = channel_result("gov", qs, results)
        self.assertEqual(ch["total"], 8)
        self.assertEqual(len(ch["top_links"]), 5)

    def test_label_resolved(self):
        """渠道 label 从 CHANNELS 解析."""
        qs = [ChannelQuery(query="q", sites="s")]
        ch = channel_result("patent", qs, [[_mk_item("A", "http://a")]])
        self.assertEqual(ch["label"], CHANNELS["patent"].label)

    def test_empty_results(self):
        """无结果时 total=0."""
        qs = [ChannelQuery(query="q", sites="s")]
        ch = channel_result("gov", qs, [[]])
        self.assertEqual(ch["total"], 0)
        self.assertEqual(ch["top_links"], [])


class TestScan(unittest.TestCase):
    """Test scan 全流程."""

    def setUp(self):
        """每个用例前准备一致的 mock 数据."""
        self.data = {
            "中芯国际": [_mk_item("专利一", "http://p1")],
            "中标": [_mk_item("中标公告", "http://b1", "2026-06")],
        }

    def test_scan_aggregates_single_channel(self):
        """指定单渠道扫描返回对应结构."""
        res = scan("中芯国际", channels=["patent"], search_fn=_mock_search)
        self.assertEqual(res["company"], "中芯国际")
        self.assertIn("patent", res["channels"])
        self.assertEqual(res["channels"]["patent"]["total"], 1)

    def test_scan_empty_search(self):
        """搜索无结果不回退到默认，total 应为 0."""
        def empty_search(**kwargs):
            return []
        res = scan("某公司", channels=["gov"], search_fn=empty_search)
        self.assertEqual(res["channels"]["gov"]["total"], 0)

    def test_scan_search_failure_does_not_block(self):
        """单渠道搜索抛异常不阻断整体扫描."""
        def failing_search(**kwargs):
            raise RuntimeError("boom")
        res = scan("某公司", channels=["bidding"], search_fn=failing_search)
        self.assertEqual(res["channels"]["bidding"]["total"], 0)

    def test_scan_without_annual_report(self):
        """未提供年报路径时 annual_report 为空."""
        res = scan("中芯国际", channels=["patent"], search_fn=_mock_search)
        self.assertEqual(res["annual_report"], {})

    def test_aggregate_shapes(self):
        """aggregate 输出字段完整."""
        qb = build_queries("中芯国际", channels=["patent"])
        rb = {"patent": [[_mk_item("A", "http://a")]]}
        out = aggregate("中芯国际", qb, rb, {"有": True})
        self.assertIn("scanned_at", out)
        self.assertEqual(out["company"], "中芯国际")
        self.assertEqual(out["annual_report"]["有"], True)


class TestExportMarkdown(unittest.TestCase):
    """Test Markdown 报告导出."""

    def test_export_writes_sections(self):
        """导出含渠道标题、结果链接、年报 JSON."""
        qb = build_queries("中芯国际", channels=["patent"])
        rb = {"patent": [[_mk_item("专利一", "http://p1")]]}
        out = aggregate("中芯国际", qb, rb, {"员工": {"研发人数": 100}})
        tmp = Path(__file__).parent / "test_in_research_tmp.md"
        try:
            saved = export_markdown(out, str(tmp))
            text = tmp.read_text(encoding="utf-8")
            self.assertIn("在研重大项目扫描报告", text)
            self.assertIn("专利一", text)
            self.assertIn("http://p1", text)
            self.assertIn("年报在研项目章节", text)
            self.assertEqual(saved, str(tmp))
        finally:
            tmp.unlink(missing_ok=True)

    def test_export_empty_channel(self):
        """空结果渠道导出"未检索到有效结果"."""
        qb = build_queries("某公司", channels=["gov"])
        out = aggregate("某公司", qb, {"gov": [[]]}, None)
        tmp = Path(__file__).parent / "test_in_research_tmp2.md"
        try:
            export_markdown(out, str(tmp))
            self.assertIn("未检索到有效结果", tmp.read_text(encoding="utf-8"))
        finally:
            tmp.unlink(missing_ok=True)


class TestCli(unittest.TestCase):
    """Test 命令行入口."""

    def test_list_command(self):
        """list 命令列出渠道并返回 0."""
        self.assertEqual(_main(["list"]), 0)


# ---------------------------------------------------------------------------
# pipeline-npv 子命令（P3-8 研发管线 NPV 粗算子）
# ---------------------------------------------------------------------------

#: 哨兵值：在 _pj() 中传入以显式删除某字段（构造缺项用例）
_DROP = object()


def _pj(**overrides) -> dict:
    """构造一个默认合法的在研项目参数 dict.

    Args:
        **overrides: 覆盖默认字段；某字段传 _DROP 表示**删除**该字段。

    Returns:
        项目参数 dict（默认：2 期后上市、概率 0.4、峰值收入 100、投入 20）。
    """
    item = {
        "name": "示例在研项目",
        "peak_revenue": 100.0,
        "launch_year": 2029,
        "probability": 0.4,
        "cost": 20.0,
        "source": "公司2025年报·在研项目章节（第 88 页）",
    }
    item.update(overrides)
    return {key: value for key, value in item.items() if value is not _DROP}


def _mk_scan_payload() -> dict:
    """构造仿 scan --json 的结果（含重复标题，用于候选去重用例）."""
    return {
        "command": "scan",
        "channels": {
            "patent": {
                "top_links": [
                    {"title": "示例公司 新一代光刻胶中试进展", "url": "http://a"},
                    {"title": "示例公司 车规级碳化硅模块量产", "url": "http://b"},
                ]
            },
            "gov": {
                "top_links": [
                    {"title": "示例公司 新一代光刻胶中试进展", "url": "http://a"},
                    {"title": "示例公司 固态电池中试线立项", "url": "http://c"},
                ]
            },
        },
    }


class _PipelineNpvTestBase(unittest.TestCase):
    """pipeline-npv 测试基类：统一提供临时目录与 CLI 捕获辅助."""

    def setUp(self):
        """每个用例独立临时目录，避免夹具互相污染."""
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        """清理临时目录."""
        self._tmpdir.cleanup()

    def write_json(self, name: str, payload) -> str:
        """写 JSON 夹具到临时目录.

        Args:
            name: 文件名。
            payload: 任意可 JSON 序列化对象（str 则原样写入，便于构造非法 JSON）。

        Returns:
            夹具的绝对路径字符串。
        """
        path = self.tmp / name
        text = payload if isinstance(payload, str) else json.dumps(
            payload, ensure_ascii=False
        )
        path.write_text(text, encoding="utf-8")
        return str(path)

    def run_cli(self, argv: List[str]) -> Tuple[int, str, str]:
        """执行 CLI 入口并捕获输出.

        Args:
            argv: 参数列表（不含解释器与脚本名）。

        Returns:
            (退出码, stdout, stderr)。
        """
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = _main(argv)
        return code, out.getvalue(), err.getvalue()

    def npv_argv(self, projects_path: str, **opts) -> List[str]:
        """构造 pipeline-npv 的常用参数列表.

        Args:
            projects_path: --projects 取值（路径或 '-'）。
            **opts: 可选 as_of_year / sensitivity / from_scan / json / currency
                / discount_rate 覆盖值。

        Returns:
            参数列表。
        """
        argv = [
            "pipeline-npv", "--projects", projects_path,
            "--discount-rate", str(opts.get("discount_rate", 0.10)),
            "--currency", opts.get("currency", "CNY"),
            "--as-of-year", str(opts.get("as_of_year", 2026)),
        ]
        if opts.get("sensitivity"):
            argv += ["--sensitivity", opts["sensitivity"]]
        if opts.get("from_scan"):
            argv += ["--from-scan", opts["from_scan"]]
        if opts.get("json", True):
            argv.append("--json")
        return argv


class TestPipelineNpvParseProjects(_PipelineNpvTestBase):
    """Test 项目清单解析与校验（缺项=业务状态、非法=用法错误）."""

    def test_valid_project_fields(self):
        """合法项目解析出全部字段，且初始 NPV 为空."""
        parsed = parse_projects({"projects": [_pj()]}, 2026)
        self.assertFalse(parsed["data_insufficient"])
        self.assertEqual(parsed["missing"], [])
        self.assertEqual(parsed["defaults_applied"], [])
        entry = parsed["projects"][0]
        self.assertEqual(entry["years_to_launch"], 3)
        self.assertEqual(entry["probability"], 0.4)
        self.assertIsNone(entry["npv"])
        self.assertIsNone(entry["pv_peak"])

    def test_cost_default_zero_and_echoed(self):
        """cost 缺省=0，且必须写入 defaults_applied（唯一允许的缺省）."""
        parsed = parse_projects({"projects": [_pj(cost=_DROP)]}, 2026)
        self.assertEqual(parsed["projects"][0]["cost"], 0.0)
        self.assertEqual(parsed["defaults_applied"], ["projects[0].cost=0"])
        self.assertFalse(parsed["data_insufficient"])

    def test_explicit_zero_cost_not_a_default(self):
        """显式 cost=0 不得进入 defaults_applied."""
        parsed = parse_projects({"projects": [_pj(cost=0.0)]}, 2026)
        self.assertEqual(parsed["defaults_applied"], [])

    def test_missing_probability_is_business_state(self):
        """缺 probability 记入 missing，不抛错（数据不足=业务状态）."""
        parsed = parse_projects({"projects": [_pj(), _pj(probability=_DROP)]}, 2026)
        self.assertTrue(parsed["data_insufficient"])
        self.assertEqual(parsed["missing"], ["projects[1].probability"])

    def test_blank_string_counts_as_missing(self):
        """空白字符串等同缺项（不抛错）."""
        parsed = parse_projects({"projects": [_pj(source="  ")]}, 2026)
        self.assertEqual(parsed["missing"], ["projects[0].source"])

    def test_empty_or_absent_projects_list(self):
        """projects 缺失或空数组 → 数据不足且不产生数值."""
        for payload in ({}, {"projects": []}):
            parsed = parse_projects(payload, 2026)
            self.assertTrue(parsed["data_insufficient"])
            self.assertEqual(parsed["missing"], ["projects"])
            self.assertEqual(parsed["projects"], [])

    def test_probability_out_of_range_raises(self):
        """概率越界（>1 或 <0）为用法错误，抛出 PipelineNpvError."""
        for bad in (1.5, -0.01):
            with self.assertRaises(PipelineNpvError):
                parse_projects({"projects": [_pj(probability=bad)]}, 2026)

    def test_launch_year_before_as_of_raises(self):
        """折现期数为负 → 用法错误."""
        with self.assertRaises(PipelineNpvError):
            parse_projects({"projects": [_pj(launch_year=2025)]}, 2026)

    def test_non_integer_launch_year_raises(self):
        """launch_year 非整数（含 bool）→ 用法错误."""
        for bad in (2029.0, True, "2029"):
            with self.assertRaises(PipelineNpvError):
                parse_projects({"projects": [_pj(launch_year=bad)]}, 2026)

    def test_invalid_field_type_raises(self):
        """已提供字段类型非法 → 用法错误（而非缺项）."""
        cases = (
            {"peak_revenue": "100"},
            {"cost": "20"},
            {"name": 123},
            {"probability": None},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                payload = {"projects": [_pj(**overrides)]}
                if overrides.get("probability", 1) is None:
                    # None 属缺项（业务状态），不抛错
                    self.assertTrue(parse_projects(payload, 2026)["data_insufficient"])
                    continue
                with self.assertRaises(PipelineNpvError):
                    parse_projects(payload, 2026)

    def test_non_dict_project_raises(self):
        """项目条目非 JSON 对象 → 用法错误."""
        with self.assertRaises(PipelineNpvError):
            parse_projects({"projects": ["not-a-dict"]}, 2026)

    def test_non_finite_numbers_raise(self):
        """NaN / inf 视为非法数值（不得静默参与计算）."""
        for bad in (float("nan"), float("inf")):
            with self.assertRaises(PipelineNpvError):
                parse_projects({"projects": [_pj(peak_revenue=bad)]}, 2026)


class TestPipelineNpvCompute(_PipelineNpvTestBase):
    """Test NPV 计算核心（单期峰值折现 + 概率线性调整）."""

    def test_single_project_formula(self):
        """单项目：pv_peak/pv_cost/npv 与手算整式一致（样例 S1 项目A）."""
        projects = parse_projects({"projects": [_pj()]}, 2026)["projects"]
        computed = compute_pipeline_npv(projects, 0.10, 2026)
        entry = computed["projects"][0]
        self.assertEqual(entry["years_to_launch"], 3)
        self.assertAlmostEqual(entry["pv_peak"], 75.13148009015775, places=12)
        self.assertAlmostEqual(entry["pv_cost"], 15.02629601803155, places=12)
        self.assertAlmostEqual(entry["npv"], 15.026296018031553, places=12)

    def test_project_without_cost(self):
        """cost=0 时 NPV 仅含概率调整后的峰值（样例 S1 项目B）."""
        projects = parse_projects(
            {"projects": [_pj(peak_revenue=80.0, launch_year=2028,
                              probability=0.7, cost=_DROP)]}, 2026
        )["projects"]
        entry = compute_pipeline_npv(projects, 0.10, 2026)["projects"][0]
        self.assertEqual(entry["years_to_launch"], 2)
        self.assertAlmostEqual(entry["npv"], 46.280991735537185, places=12)

    def test_pipeline_total_equals_sum(self):
        """合计等于逐项目 NPV 之和（样例 S1 两项目）."""
        projects = parse_projects(
            {"projects": [
                _pj(),
                _pj(peak_revenue=80.0, launch_year=2028, probability=0.7, cost=_DROP),
            ]}, 2026
        )["projects"]
        computed = compute_pipeline_npv(projects, 0.10, 2026)
        total = sum(item["npv"] for item in computed["projects"])
        self.assertAlmostEqual(computed["pipeline_npv"], total, places=12)
        self.assertAlmostEqual(computed["pipeline_npv"], 61.30728775356874, places=12)

    def test_zero_period_uses_nominal_value(self):
        """n=0（当年商业化）合法：折现因子为 1，NPV = p×peak − cost（样例 S3）."""
        projects = parse_projects(
            {"projects": [_pj(launch_year=2026, probability=0.5, cost=10.0)]}, 2026
        )["projects"]
        entry = compute_pipeline_npv(projects, 0.10, 2026)["projects"][0]
        self.assertEqual(entry["years_to_launch"], 0)
        self.assertEqual(entry["pv_peak"], 100.0)
        self.assertEqual(entry["pv_cost"], 10.0)
        self.assertEqual(entry["npv"], 40.0)

    def test_probability_bounds_accepted(self):
        """概率取边界 0 / 1 合法（不截断、不报错）."""
        projects = parse_projects(
            {"projects": [_pj(probability=0.0), _pj(name="B", probability=1.0)]}, 2026
        )["projects"]
        computed = compute_pipeline_npv(projects, 0.10, 2026)
        self.assertAlmostEqual(computed["projects"][0]["npv"], -15.02629601803155,
                               places=12)
        self.assertAlmostEqual(computed["projects"][1]["npv"], 60.1051840721262,
                               places=12)

    def test_compute_rejects_defensive_bad_input(self):
        """防御性校验：绕过多项目概率越界 / 期数为负仍抛错."""
        for bad in (
            [{"name": "X", "launch_year": 2026, "probability": 1.2,
              "peak_revenue": 100.0, "cost": 0.0}],
            [{"name": "X", "launch_year": 2025, "probability": 0.5,
              "peak_revenue": 100.0, "cost": 0.0}],
        ):
            with self.assertRaises(PipelineNpvError):
                compute_pipeline_npv(bad, 0.10, 2026)

    def test_empty_project_list_gives_zero_total(self):
        """空清单（已通过校验路径）合计为 0，不做任何臆造."""
        computed = compute_pipeline_npv([], 0.10, 2026)
        self.assertEqual(computed["projects"], [])
        self.assertEqual(computed["pipeline_npv"], 0.0)


class TestPipelineNpvSensitivity(_PipelineNpvTestBase):
    """Test 敏感性网格（3×3 绝对步长，越界截断需标注）."""

    def setUp(self):
        """准备两个常用项目集（a=不越界，d=概率上界截断）."""
        super().setUp()
        self.projects_a = parse_projects(
            {"projects": [
                _pj(),
                _pj(peak_revenue=80.0, launch_year=2028, probability=0.7, cost=_DROP),
            ]}, 2026
        )["projects"]
        self.projects_d = parse_projects(
            {"projects": [_pj(launch_year=2027, probability=0.95, cost=0.0)]}, 2026
        )["projects"]

    def test_spec_parsed_as_absolute_steps(self):
        """规格解析为绝对步长二元组，容忍空格与大小写."""
        self.assertEqual(parse_sensitivity_spec("r=0.01;p=0.10"), (0.01, 0.1))
        self.assertEqual(parse_sensitivity_spec(" R = 0.01 ; P = 0.1 "), (0.01, 0.1))

    def test_grid_nine_cells_and_spec_echo(self):
        """网格 9 格，spec 回显绝对步长（样例 S2）."""
        result = build_sensitivity(self.projects_a, 0.10, 2026, "r=0.01;p=0.10")
        self.assertEqual(len(result["grid"]), 9)
        self.assertEqual(result["spec"], {"discount_rate_step": 0.01,
                                          "probability_step": 0.1})
        self.assertEqual(
            [(cell["discount_rate"], cell["probability_shift"]) for cell in result["grid"]][0],
            (0.1 - 0.01, -0.1),
        )

    def test_base_equals_pipeline_npv(self):
        """base 与 pipeline_npv 同值（同一计算路径）."""
        result = build_sensitivity(self.projects_a, 0.10, 2026, "r=0.01;p=0.10")
        direct = compute_pipeline_npv(self.projects_a, 0.10, 2026)["pipeline_npv"]
        self.assertEqual(result["base"], direct)
        self.assertAlmostEqual(result["base"], 61.30728775356874, places=12)

    def test_low_high_are_grid_extremes(self):
        """npv_low / npv_high 为网格极值（样例 S2）."""
        result = build_sensitivity(self.projects_a, 0.10, 2026, "r=0.01;p=0.10")
        values = [cell["pipeline_npv"] for cell in result["grid"]]
        self.assertEqual(result["npv_low"], min(values))
        self.assertEqual(result["npv_high"], max(values))
        self.assertAlmostEqual(result["npv_low"], 46.269790608724136, places=12)
        self.assertAlmostEqual(result["npv_high"], 77.03302397089175, places=12)

    def test_no_clipping_when_in_range(self):
        """概率平移后均在 [0,1] 内 → 全部 clipped=false（样例 S2）."""
        result = build_sensitivity(self.projects_a, 0.10, 2026, "r=0.01;p=0.10")
        self.assertFalse(any(cell["clipped"] for cell in result["grid"]))

    def test_clipping_flagged_transparently(self):
        """概率越界格截断至 1.0 并标注 clipped=true（样例 S5）."""
        result = build_sensitivity(self.projects_d, 0.10, 2026, "r=0.01;p=0.10")
        clipped = [cell for cell in result["grid"] if cell["clipped"]]
        self.assertEqual(len(clipped), 3)
        for cell in clipped:
            self.assertAlmostEqual(cell["probability_shift"], 0.1)
        self.assertAlmostEqual(result["npv_high"], 91.74311926605503, places=12)
        self.assertAlmostEqual(result["base"], 86.36363636363636, places=12)

    def test_spec_missing_key_raises(self):
        """规格缺 r 或缺 p → 用法错误（两键必须同给）."""
        for spec in ("r=0.01", "p=0.10"):
            with self.assertRaises(PipelineNpvError):
                parse_sensitivity_spec(spec)

    def test_spec_non_positive_or_unknown_key_raises(self):
        """步长非正 / 未知键 / 无等号 → 用法错误."""
        for spec in ("r=0;p=0.1", "r=0.01;p=-0.1", "x=0.01;p=0.1", "0.01;0.1"):
            with self.subTest(spec=spec):
                with self.assertRaises(PipelineNpvError):
                    parse_sensitivity_spec(spec)

    def test_discount_rate_floor_raises(self):
        """折现率网格下限 ≤ 0 → 用法错误（不得产生非正折现率）."""
        with self.assertRaises(PipelineNpvError):
            build_sensitivity(self.projects_a, 0.10, 2026, "r=0.20;p=0.10")


class TestPipelineNpvRun(_PipelineNpvTestBase):
    """Test run_pipeline_npv 全流程编排与退出语义."""

    def _a_payload(self) -> dict:
        """样例 S1 的输入载荷."""
        return {"currency": "CNY", "projects": [
            _pj(),
            _pj(name="示例在研项目B", peak_revenue=80.0, launch_year=2028,
                probability=0.7, cost=_DROP,
                source="券商深度研报《示例公司管线拆解》2026-06-30"),
        ]}

    def test_full_run_fields(self):
        """正常全流程输出契约字段与数值（样例 S1）."""
        path = self.write_json("a.json", self._a_payload())
        result = run_pipeline_npv(path, 0.10, "CNY", 2026)
        self.assertEqual(result["command"], "pipeline-npv")
        self.assertEqual(result["as_of_year"], 2026)
        self.assertEqual(result["currency"], "CNY")
        self.assertFalse(result["data_insufficient"])
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["defaults_applied"], ["projects[1].cost=0"])
        self.assertEqual([item["name"] for item in result["projects"]],
                         ["示例在研项目", "示例在研项目B"])
        self.assertAlmostEqual(result["pipeline_npv"], 61.30728775356874, places=12)
        self.assertIsNone(result["sensitivity"])
        self.assertEqual(result["project_candidates"], [])

    def test_insufficient_skips_every_number(self):
        """存在缺项时**不计算任何数值**（含参数完整项目），敏感性恒为 null."""
        path = self.write_json("c.json", {"currency": "CNY", "projects": [
            _pj(),
            _pj(name="缺概率项目", probability=_DROP),
        ]})
        result = run_pipeline_npv(path, 0.10, "CNY", 2026,
                                  sensitivity_spec="r=0.01;p=0.10")
        self.assertTrue(result["data_insufficient"])
        self.assertEqual(result["missing"], ["projects[1].probability"])
        self.assertIsNone(result["pipeline_npv"])
        self.assertIsNone(result["sensitivity"])
        for item in result["projects"]:
            self.assertIsNone(item["npv"])
            self.assertIsNone(item["pv_peak"])
            self.assertIsNone(item["pv_cost"])

    def test_sensitivity_attached_only_when_requested(self):
        """提供 --sensitivity 才产出敏感性对象."""
        path = self.write_json("a.json", self._a_payload())
        result = run_pipeline_npv(path, 0.10, "CNY", 2026,
                                  sensitivity_spec="r=0.01;p=0.10")
        self.assertIsNotNone(result["sensitivity"])
        self.assertEqual(result["sensitivity"]["base"], result["pipeline_npv"])

    def test_as_of_year_defaults_to_current_year(self):
        """未给 as_of_year → 取系统当前年份并回显（无历史年份假设）."""
        path = self.write_json("a.json", self._a_payload())
        result = run_pipeline_npv(path, 0.10, "CNY")
        self.assertEqual(result["as_of_year"], datetime.now().year)

    def test_currency_conflict_raises(self):
        """文件 currency 与 CLI 不一致 → 用法错误（不静默取其一）."""
        path = self.write_json("usd.json", {"currency": "USD",
                                            "projects": [_pj()]})
        with self.assertRaises(PipelineNpvError):
            run_pipeline_npv(path, 0.10, "CNY", 2026)

    def test_currency_match_is_case_insensitive(self):
        """币种大小写不同视为一致（不做换算）."""
        path = self.write_json("cny.json", {"currency": "cny",
                                            "projects": [_pj()]})
        result = run_pipeline_npv(path, 0.10, "CNY", 2026)
        self.assertEqual(result["currency"], "CNY")

    def test_unsupported_currency_raises(self):
        """非法币种 → 用法错误（无默认币种）."""
        path = self.write_json("a.json", self._a_payload())
        with self.assertRaises(PipelineNpvError):
            run_pipeline_npv(path, 0.10, "JPY", 2026)

    def test_invalid_discount_rate_raises(self):
        """折现率 ≤ -1 或非有限 → 用法错误."""
        path = self.write_json("a.json", self._a_payload())
        for bad in (-1.0, -1.5, float("nan")):
            with self.subTest(bad=bad):
                with self.assertRaises(PipelineNpvError):
                    run_pipeline_npv(path, bad, "CNY", 2026)

    def test_discount_rate_above_ceiling_raises(self):
        """折现率超上限（百分数当小数的量纲误用）→ 用法错误."""
        path = self.write_json("a.json", self._a_payload())
        for bad in (1.5, 10.0):
            with self.subTest(bad=bad):
                with self.assertRaises(PipelineNpvError):
                    run_pipeline_npv(path, bad, "CNY", 2026)

    def test_payload_as_of_year_conflict_raises(self):
        """文件内 as_of_year 与本次基准年不一致 → 用法错误（不静默忽略）."""
        payload = self._a_payload()
        payload["as_of_year"] = 2025
        path = self.write_json("y.json", payload)
        with self.assertRaises(PipelineNpvError):
            run_pipeline_npv(path, 0.10, "CNY", 2026)

    def test_payload_as_of_year_match_ok(self):
        """文件内 as_of_year 与本次基准年一致 → 正常计算并回显."""
        payload = self._a_payload()
        payload["as_of_year"] = 2026
        path = self.write_json("y.json", payload)
        result = run_pipeline_npv(path, 0.10, "CNY", 2026)
        self.assertEqual(result["as_of_year"], 2026)
        self.assertFalse(result["data_insufficient"])

    def test_payload_as_of_year_non_integer_raises(self):
        """文件内 as_of_year 非整数年份 → 用法错误."""
        for bad in ("2026", 2026.0, True):
            with self.subTest(bad=bad):
                payload = self._a_payload()
                payload["as_of_year"] = bad
                path = self.write_json("y.json", payload)
                with self.assertRaises(PipelineNpvError):
                    run_pipeline_npv(path, 0.10, "CNY", 2026)

    def test_projects_file_errors_raise(self):
        """文件不存在 / JSON 非法 / 顶层非对象 → 用法错误."""
        missing = str(self.tmp / "nope.json")
        bad_json = self.write_json("bad.json", '{ "projects": [ ')
        not_object = self.write_json("list.json", "[1, 2]")
        for path in (missing, bad_json, not_object):
            with self.subTest(path=path):
                with self.assertRaises(PipelineNpvError):
                    run_pipeline_npv(path, 0.10, "CNY", 2026)

    def test_from_scan_only_fills_candidates(self):
        """--from-scan 只填候选名，不改变任何数值."""
        path = self.write_json("a.json", self._a_payload())
        scan_path = self.write_json("scan.json", _mk_scan_payload())
        with_scan = run_pipeline_npv(path, 0.10, "CNY", 2026,
                                     from_scan_path=scan_path)
        without = run_pipeline_npv(path, 0.10, "CNY", 2026)
        self.assertEqual(len(with_scan["project_candidates"]), 3)
        self.assertEqual(with_scan["pipeline_npv"], without["pipeline_npv"])
        self.assertEqual([i["npv"] for i in with_scan["projects"]],
                         [i["npv"] for i in without["projects"]])


class TestPipelineNpvCandidates(_PipelineNpvTestBase):
    """Test scan 结果的项目名候选提取（只取标题、不含数值）."""

    def test_extract_dedup_and_order(self):
        """跨渠道去重并保持首次出现顺序（4 标题 → 3 候选）."""
        candidates = extract_project_candidates(_mk_scan_payload())
        self.assertEqual(candidates, [
            "示例公司 新一代光刻胶中试进展",
            "示例公司 车规级碳化硅模块量产",
            "示例公司 固态电池中试线立项",
        ])

    def test_extract_ignores_non_title_fields(self):
        """仅取 title：数值型 URL/摘要等字段不进入候选."""
        payload = {"channels": {"patent": {"top_links": [
            {"title": "候选一", "url": "http://a", "total": 9},
            {"title": "候选一", "url": "http://b"},
        ]}}}
        candidates = extract_project_candidates(payload)
        self.assertEqual(candidates, ["候选一"])

    def test_extract_tolerates_missing_channels(self):
        """无 channels / 结构异常 → 返回空列表（不抛错）."""
        for payload in ({}, {"channels": []}, {"channels": {"patent": {}}}):
            self.assertEqual(extract_project_candidates(payload), [])

    def test_extract_skips_blank_and_non_string_titles(self):
        """空白标题与非字符串标题被跳过."""
        payload = {"channels": {"gov": {"top_links": [
            {"title": "  "}, {"title": 123}, {"title": "有效标题"},
        ]}}}
        self.assertEqual(extract_project_candidates(payload), ["有效标题"])

    def test_load_candidates_file_errors_raise(self):
        """文件不存在 / JSON 非法 / 顶层非对象 → 用法错误."""
        missing = str(self.tmp / "nope.json")
        bad_json = self.write_json("bad.json", "{ nope")
        not_object = self.write_json("list.json", "[]")
        for path in (missing, bad_json, not_object):
            with self.subTest(path=path):
                with self.assertRaises(PipelineNpvError):
                    load_project_candidates(path)


class TestPipelineNpvCli(_PipelineNpvTestBase):
    """Test pipeline-npv 命令行入口（退出码 0 / 2 与输出分工）."""

    def _a_path(self) -> str:
        """写样例 S1 夹具并返回路径."""
        return self.write_json("a.json", {"currency": "CNY", "projects": [
            _pj(),
            _pj(name="示例在研项目B", peak_revenue=80.0, launch_year=2028,
                probability=0.7, cost=_DROP),
        ]})

    def test_json_normal_exit_zero(self):
        """正常用例：退出码 0，stdout 为可解析 JSON."""
        code, out, err = self.run_cli(self.npv_argv(self._a_path()))
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        payload = json.loads(out)
        self.assertEqual(payload["command"], "pipeline-npv")
        self.assertAlmostEqual(payload["pipeline_npv"], 61.30728775356874, places=12)
        self.assertEqual(payload["defaults_applied"], ["projects[1].cost=0"])

    def test_data_insufficient_exit_zero(self):
        """数据不足：退出码 0，全表 null，不产生替代数值."""
        path = self.write_json("c.json", {"currency": "CNY", "projects": [
            _pj(), _pj(name="缺概率项目", probability=_DROP),
        ]})
        code, out, err = self.run_cli(self.npv_argv(path))
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        payload = json.loads(out)
        self.assertTrue(payload["data_insufficient"])
        self.assertIsNone(payload["pipeline_npv"])
        self.assertEqual(payload["missing"], ["projects[1].probability"])

    def test_usage_errors_exit_two_stdout_empty(self):
        """6 类用法错误：退出码 2、stdout 为空、错误写 stderr."""
        a_path = self._a_path()
        cases = {
            "概率越界": self.npv_argv(
                self.write_json("p15.json", {"currency": "CNY",
                                             "projects": [_pj(probability=1.5)]})),
            "期数为负": self.npv_argv(
                self.write_json("y.json", {"currency": "CNY",
                                           "projects": [_pj(launch_year=2025)]})),
            "币种冲突": self.npv_argv(
                self.write_json("usd.json", {"currency": "USD",
                                             "projects": [_pj()]})),
            "敏感性缺键": self.npv_argv(a_path, sensitivity="r=0.01"),
            "折现率下限": self.npv_argv(a_path, sensitivity="r=0.20;p=0.10"),
            "projects 不存在": self.npv_argv(str(self.tmp / "nope.json")),
        }
        for label, argv in cases.items():
            with self.subTest(case=label):
                code, out, err = self.run_cli(argv)
                self.assertEqual(code, 2)
                self.assertEqual(out, "")
                self.assertIn("[错误]", err)

    def test_from_scan_missing_file_exit_two(self):
        """--from-scan 文件不存在 → 退出码 2（不静默忽略）."""
        argv = self.npv_argv(self._a_path(), from_scan=str(self.tmp / "nope.json"))
        code, out, err = self.run_cli(argv)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("--from-scan", err)

    def test_missing_required_cli_arg_exits_two(self):
        """缺 --discount-rate：argparse 以退出码 2 终止（无默认折现率）."""
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli(["pipeline-npv", "--projects", self._a_path(),
                          "--currency", "CNY", "--as-of-year", "2026"])
        self.assertEqual(ctx.exception.code, 2)

    def test_invalid_currency_choice_exits_two(self):
        """--currency 非枚举值：argparse choices 拦截（退出码 2）."""
        with self.assertRaises(SystemExit) as ctx:
            self.run_cli(self.npv_argv(self._a_path(), currency="JPY"))
        self.assertEqual(ctx.exception.code, 2)

    def test_stdin_projects(self):
        """--projects - 从 stdin 读取并正常计算."""
        payload = {"currency": "CNY", "projects": [_pj()]}
        stdin = io.StringIO(json.dumps(payload, ensure_ascii=False))
        with mock.patch.object(sys, "stdin", stdin):
            code, out, err = self.run_cli(self.npv_argv("-"))
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertAlmostEqual(json.loads(out)["pipeline_npv"], 15.026296018031553,
                               places=12)

    def test_stdin_parse_failure_exit_two(self):
        """stdin 内容非法 → 退出码 2，错误信息标注 stdin."""
        stdin = io.StringIO("")
        with mock.patch.object(sys, "stdin", stdin):
            code, out, err = self.run_cli(self.npv_argv("-"))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("stdin", err)

    def test_from_scan_candidates_in_json(self):
        """--from-scan 候选出现在 JSON 输出中."""
        scan_path = self.write_json("scan.json", _mk_scan_payload())
        code, out, _ = self.run_cli(self.npv_argv(self._a_path(),
                                                  from_scan=scan_path))
        self.assertEqual(code, 0)
        candidates = json.loads(out)["project_candidates"]
        self.assertEqual(len(candidates), 3)
        self.assertIn("示例公司 固态电池中试线立项", candidates)

    def test_human_readable_summary(self):
        """非 --json：输出人读摘要（含合计、缺省回显、敏感性三元组）."""
        code, out, err = self.run_cli(
            self.npv_argv(self._a_path(), sensitivity="r=0.01;p=0.10", json=False)
        )
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        self.assertIn("研发管线 NPV 粗算子", out)
        self.assertIn("合计 NPV: 61.30728775356874", out)
        self.assertIn("[缺省回显] projects[1].cost=0", out)
        self.assertIn("敏感性: base=", out)

    def test_human_readable_insufficient(self):
        """非 --json + 数据不足：明确标注数据不足与 null 合计."""
        path = self.write_json("c.json", {"currency": "CNY", "projects": [
            _pj(), _pj(name="缺概率项目", probability=_DROP),
        ]})
        code, out, _ = self.run_cli(self.npv_argv(path, json=False))
        self.assertEqual(code, 0)
        self.assertIn("[数据不足] 缺失项: projects[1].probability", out)
        self.assertIn("[数据不足] 合计 NPV: null", out)

    def test_discount_rate_ceiling_exit_two(self):
        """折现率超上限：退出码 2、stdout 为空、错误说明量纲要求."""
        code, out, err = self.run_cli(
            self.npv_argv(self._a_path(), discount_rate=10.0)
        )
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("超出上限", err)

    def test_sensitivity_rate_upper_bound_exit_two(self):
        """敏感性折现率网格上限越界 → 退出码 2（与下限同口径）."""
        code, out, err = self.run_cli(
            self.npv_argv(self._a_path(), discount_rate=0.95,
                          sensitivity="r=0.10;p=0.10")
        )
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("折现率上限", err)

    def test_payload_as_of_year_conflict_exit_two(self):
        """文件内 as_of_year 冲突：退出码 2，并给出显式对齐提示."""
        path = self.write_json("y.json", {"as_of_year": 2025,
                                          "currency": "CNY", "projects": [_pj()]})
        code, out, err = self.run_cli(self.npv_argv(path))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("基准年冲突", err)
        self.assertIn("--as-of-year 2025", err)

    def test_human_readable_null_mapping(self):
        """数据不足时人读摘要以 null 呈现缺值（不得出现 Python None 字面量）."""
        path = self.write_json("c.json", {"currency": "CNY", "projects": [
            _pj(), _pj(name="缺概率项目", probability=_DROP),
        ]})
        code, out, _ = self.run_cli(self.npv_argv(path, json=False))
        self.assertEqual(code, 0)
        self.assertNotIn("None", out)
        self.assertIn("概率: 0.4 | NPV: null", out)
        self.assertIn("概率: null | NPV: null", out)


class TestPipelineNpvEdgeBranches(_PipelineNpvTestBase):
    """Test 边界与防御性分支（容错路径 + 用法错误的细分分支）."""

    def test_sensitivity_ignores_empty_segment(self):
        """规格中的空段（多余分号）被忽略，不误判为非法."""
        self.assertEqual(parse_sensitivity_spec("r=0.01;;p=0.1;"), (0.01, 0.1))

    def test_sensitivity_non_numeric_step_raises(self):
        """步长非数值 → 用法错误."""
        with self.assertRaises(PipelineNpvError):
            parse_sensitivity_spec("r=abc;p=0.1")

    def test_extract_skips_non_dict_channel(self):
        """channels 内非 dict 项被跳过（容错，不抛错）."""
        payload = {"channels": {"patent": "not-a-dict",
                                "gov": {"top_links": [{"title": "有效"}]}}}
        self.assertEqual(extract_project_candidates(payload), ["有效"])

    def test_extract_skips_non_dict_link(self):
        """top_links 内非 dict 项被跳过（容错，不抛错）."""
        payload = {"channels": {"gov": {"top_links": ["nope", {"title": "有效"}]}}}
        self.assertEqual(extract_project_candidates(payload), ["有效"])

    def test_sensitivity_rate_upper_bound_raises(self):
        """折现率网格上限 > 1.0 → 用法错误（与下限 ≤0 同口径）."""
        projects = parse_projects({"projects": [_pj()]}, 2026)["projects"]
        with self.assertRaises(PipelineNpvError):
            build_sensitivity(projects, 0.95, 2026, "r=0.10;p=0.10")

    def test_project_source_non_string_raises(self):
        """source 已提供但非字符串 → 用法错误."""
        with self.assertRaises(PipelineNpvError):
            parse_projects({"projects": [_pj(source=123)]}, 2026)

    def test_project_probability_non_numeric_raises(self):
        """probability 已提供但非数值 → 用法错误（区别于缺项）."""
        with self.assertRaises(PipelineNpvError):
            parse_projects({"projects": [_pj(probability="0.4")]}, 2026)

    def test_compute_rejects_non_integer_launch_year(self):
        """防御性校验：launch_year 非整数仍抛错."""
        with self.assertRaises(PipelineNpvError):
            compute_pipeline_npv(
                [{"name": "X", "launch_year": 2029.0, "probability": 0.5,
                  "peak_revenue": 100.0, "cost": 0.0}], 0.10, 2026)

    def test_human_summary_reports_candidates_count(self):
        """人读摘要列出 scan 项目名候选条数（明确不含数值）."""
        scan_path = self.write_json("scan.json", _mk_scan_payload())
        a_path = self.write_json("a.json", {"currency": "CNY", "projects": [_pj()]})
        code, out, _ = self.run_cli(
            self.npv_argv(a_path, from_scan=scan_path, json=False)
        )
        self.assertEqual(code, 0)
        self.assertIn("[scan 项目名候选] 3 条（仅名称，不含数值）", out)


if __name__ == "__main__":
    unittest.main()
