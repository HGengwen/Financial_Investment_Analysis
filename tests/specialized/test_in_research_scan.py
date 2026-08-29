#!/usr/bin/env python3
"""Unit tests for in_research_scan.py 在研重大项目扫描器.

覆盖 mid-trend-tech-screen 步骤 3-A 落地工具：
1. 渠道查询配方构建（与方案文档指令一致、website 需官网域名）
2. 未知渠道报错
3. 渠道结果聚合（去重、top_links、total）
4. scan 全流程（search_fn 注入 mock）
5. Markdown 报告导出
6. CLI list / scan 命令
"""

import sys
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()