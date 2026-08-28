#!/usr/bin/env python3
"""年报 markdown 定向抽取器测试模块。

测试 tools/common/annual_report_parser.py 的各抽取功能，使用 unittest 框架。

测试范围：
  1. TestNumPctHelpers     — 数值/百分比辅助转换（_num / _pct / _first_number_after）
  2. TestExtractEmployees  — 员工情况（总数/研发人数/占比/学历结构）
  3. TestExtractSubsidiaries — 子公司列表（释义行/正文行/关系/海外实体去重）
  4. TestExtractRdSection  — 研发投入（金额/强度/资本化）
  5. TestExtractRevenueSegments — 收入分部（维度标记/汇总行/跨表截断）
  6. TestTextExcerpt       — 关键词文本摘录（新品/供应链）
  7. TestParseMarkdown     — 组装与警告（parse_markdown_text / parse_markdown_file）

运行方式：
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/common/test_annual_report_parser.py -v

注意：
    本模块全部为纯函数逻辑测试，无网络依赖，可离线运行。
"""

import os
import sys
import unittest

# 添加项目根目录到路径（测试位于 tests/common/，需上溯两级到项目根）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from tools.common.annual_report_parser import (
    _extract_employees,
    _extract_subsidiaries,
    _extract_rd_section,
    _extract_revenue_segments,
    _first_number_after,
    _num,
    _pct,
    _text_excerpt,
    parse_markdown_file,
    parse_markdown_text,
)

# ---------------------------------------------------------------------------
# 1. 数值/百分比辅助
# ---------------------------------------------------------------------------
class TestNumPctHelpers(unittest.TestCase):
    """测试数值与百分比辅助转换函数。"""

    def test_num_plain(self):
        """整数文本转 float。"""
        self.assertEqual(_num("123"), 123.0)

    def test_num_thousands(self):
        """千分位逗号去除。"""
        self.assertEqual(_num("846,948,352.88"), 846948352.88)

    def test_num_negative(self):
        """负数字符串。"""
        self.assertEqual(_num("-331,538,134.12"), -331538134.12)

    def test_num_empty_none(self):
        """空文本返回 None。"""
        self.assertIsNone(_num(""))
        self.assertIsNone(_num(None))

    def test_num_no_digit(self):
        """无数字文本返回 None。"""
        self.assertIsNone(_num("无数据披露"))

    def test_pct_percent(self):
        """百分比转小数。"""
        self.assertAlmostEqual(_pct("90.39%"), 0.9039)

    def test_pct_raw_number(self):
        """无 % 号按原值返回。"""
        self.assertEqual(_pct("5.09"), 5.09)

    def test_pct_accumulation_point(self):
        """百分点表述（如 0.50 个百分点中的数字）。"""
        self.assertEqual(_pct("增加 0.70 个百分点"), 0.70)

    def test_pct_empty_none(self):
        """空百分比返回 None。"""
        self.assertIsNone(_pct(None))

    def test_first_number_after(self):
        """关键词后首个数字。"""
        self.assertEqual(_first_number_after("研发投入金额（元）||846,948,352.88", "研发投入金额"), 846948352.88)

    def test_first_number_after_missing_keyword(self):
        """关键词缺失返回 None。"""
        self.assertIsNone(_first_number_after("研发投入金额（元）||848", "不存在"))


# ---------------------------------------------------------------------------
# 2. 员工情况
# ---------------------------------------------------------------------------
class TestExtractEmployees(unittest.TestCase):
    """测试员工情况抽取。"""

    def test_total_employees_priority_total(self):
        """存在母公司/子公司/合计时优先取合计。"""
        lines = [
            "|报告期末母公司在职员工的数量（人）||772|",
            "|报告期末主要子公司在职员工的数量（人）||6,617|",
            "|报告期末在职员工的数量合计（人）||7,389|",
        ]
        res = _extract_employees(lines)
        self.assertEqual(res["total_employees"], 7389.0)

    def test_total_employees_fallback(self):
        """无合计行时回退到首个在职员工数。"""
        lines = ["|报告期末在职员工的数量（人）||3,000|"]
        res = _extract_employees(lines)
        self.assertEqual(res["total_employees"], 3000.0)

    def test_rd_staff_count_and_ratio(self):
        """研发人员数量与占比抽取。"""
        lines = [
            "|研发人员数量（人）||848|||702||20.80%|",
            "|研发人员数量占比 研发人员学历结构||11.48%|||10.78%||增加 0.70 个百分点|",
        ]
        res = _extract_employees(lines)
        self.assertEqual(res["rd_staff_count"], 848.0)
        self.assertAlmostEqual(res["rd_staff_ratio"], 0.1148)

    def test_degree_limited_to_zone(self):
        """学历结构限定在研发人员学历表区域内，避免命中全文首个'其他'。"""
        lines = [
            "|其他|1|",  # 干扰行（全文首个"其他"开头）
            "公司研发人员情况",
            "|研发人员数量占比 研发人员学历结构||11.48%|||10.78%|",
            "|本科||446|||359|",
            "|硕士||267|||208|",
            "|博士||32|||25|",
            "|其他 研发人员年龄构成||103|||110||-6.36%|",
        ]
        res = _extract_employees(lines)
        self.assertEqual(res["degree"]["bachelor"], 446.0)
        self.assertEqual(res["degree"]["masters"], 267.0)
        self.assertEqual(res["degree"]["phd"], 32.0)
        self.assertEqual(res["degree"]["others"], 103.0)

    def test_employees_none_when_absent(self):
        """无员工信息时返回 low 且各字段 None。"""
        res = _extract_employees(["与员工无关的句子"])
        self.assertIsNone(res["total_employees"])
        self.assertIsNone(res["rd_staff_count"])
        self.assertEqual(res["confidence"], "low")


# ---------------------------------------------------------------------------
# 3. 子公司列表
# ---------------------------------------------------------------------------
class TestExtractSubsidiaries(unittest.TestCase):
    """测试子公司列表抽取。"""

    def test_definition_rows_capture_short_name(self):
        """释义行应捕获首列简称而非英文全称。"""
        lines = [
            "|德国天赐|指|TINCI MATERIALS GmbH，为公司的全资子公司。|",
            "|香港天赐|指|天赐（香港）有限公司，为公司的全资子公司。|",
        ]
        res = _extract_subsidiaries(lines)
        names = [s["name"] for s in res["subsidiaries"]]
        self.assertIn("德国天赐", names)
        self.assertIn("香港天赐", names)

    def test_overseas_detection(self):
        """海外实体标记（地名关键词）。"""
        lines = [
            "|新加坡天赐|指|TINCI SINGAPORE PTE. LTD.，为公司的全资子公司。|",
            "|广州天赐|指|广州天赐高新材料有限公司，为公司的全资子公司。|",
        ]
        res = _extract_subsidiaries(lines)
        by_name = {s["name"]: s for s in res["subsidiaries"]}
        self.assertTrue(by_name["新加坡天赐"]["overseas"])
        self.assertFalse(by_name["广州天赐"]["overseas"])

    def test_relation_parse(self):
        """控股/参股/全资关系识别。"""
        lines = [
            "|容汇锂业|指|江苏容汇通用锂业股份有限公司，为公司的参股子公司。|",
            "|东莞腾威|指|东莞腾威电子材料有限公司，为公司的控股子公司。|",
            "|锂电池公司|指|某某锂电池有限公司，为公司的全资子公司。|",
        ]
        res = _extract_subsidiaries(lines)
        by_name = {s["name"]: s for s in res["subsidiaries"]}
        self.assertEqual(by_name["容汇锂业"]["relation"], "参股")
        self.assertEqual(by_name["东莞腾威"]["relation"], "控股")
        self.assertEqual(by_name["锂电池公司"]["relation"], "全资")

    def test_body_text_rows(self):
        """正文行（非释义表格）也能识别。"""
        lines = ["深圳某某科技有限公司，为公司的全资子公司。"]
        res = _extract_subsidiaries(lines)
        self.assertEqual(len(res["subsidiaries"]), 1)
        self.assertEqual(res["subsidiaries"][0]["name"], "深圳某某科技有限公司")

    def test_deduplication(self):
        """同一简称去重。"""
        lines = [
            "|天津天赐|指|天津天赐高新材料有限公司，为公司的全资子公司。|",
            "|天津天赐|指|天津天赐高新材料有限公司，为公司的全资子公司。|",
        ]
        res = _extract_subsidiaries(lines)
        self.assertEqual(len(res["subsidiaries"]), 1)

    def test_subsidiaries_empty(self):
        """无子公司信息返回空列表。"""
        res = _extract_subsidiaries(["没有子公司相关内容"])
        self.assertEqual(res["subsidiaries"], [])
        self.assertEqual(res["confidence"], "low")


# ---------------------------------------------------------------------------
# 4. 研发投入
# ---------------------------------------------------------------------------
class TestExtractRdSection(unittest.TestCase):
    """测试研发投入章节抽取。"""

    def test_amount_and_intensity(self):
        """研发投入金额、强度、资本化率。"""
        lines = [
            "|研发投入金额（元）||846,948,352.88|||668,213,487.72|",
            "|研发投入占营业收入比例|||5.09%||5.34%|",
            "|研发投入资本化的金额（元）|||0.00||0.00|",
            "|资本化研发投入占研发投入的比例|||0.00%||0.00%|",
        ]
        res = _extract_rd_section(lines)
        self.assertEqual(res["rd_total_amount"], 846948352.88)
        self.assertAlmostEqual(res["rd_intensity"], 0.0509)
        self.assertEqual(res["rd_capitalization_amount"], 0.0)
        self.assertEqual(res["rd_capitalization_rate"], 0.0)

    def test_nonzero_capitalization(self):
        """非零资本化金额与比例。"""
        lines = [
            "|研发投入金额（元）||100,000,000.00|",
            "|研发投入资本化的金额（元）||20,000,000.00|",
            "|资本化研发投入占研发投入的比例|||20.00%|",
        ]
        res = _extract_rd_section(lines)
        self.assertEqual(res["rd_capitalization_amount"], 20000000.0)
        self.assertAlmostEqual(res["rd_capitalization_rate"], 0.20)

    def test_rd_absent(self):
        """无研发投入信息。"""
        res = _extract_rd_section(["无研发内容"])
        self.assertIsNone(res["rd_total_amount"])
        self.assertEqual(res["confidence"], "low")


# ---------------------------------------------------------------------------
# 5. 收入分部
# ---------------------------------------------------------------------------
class TestExtractRevenueSegments(unittest.TestCase):
    """测试收入分部抽取。"""

    def test_segment_by_dimension(self):
        """按产品/地区维度切分并带占比。"""
        lines = [
            "##### （1） 营业收入构成",
            "",
            "|营业收入合计 分行业|16,649,892,556.28|100%|12,518,297,342.63|100%|33.00%|",
            "|精细化工行业 分产品|16,649,892,556.28|100.00%|12,518,297,342.63|100%|33.00%|",
            "|锂离子电池材料|15,050,539,053.67|90.39%|10,974,225,487.87|87.67%|37.14%|",
            "|日化材料及特种 化学品|1,284,576,597.36|7.72%|1,160,567,349.33|9.27%|10.69%|",
            "|其他 分地区|314,776,905.25|1.89%|383,504,505.43|3.06%|-17.92%|",
            "|境内|16,016,375,022.13|96.20%|11,969,614,285.13|95.62%|33.81%|",
            "|境外 分销售模式|633,517,534.15|3.80%|548,683,057.50|4.38%|15.46%|",
            "|直销|16,649,892,556.28|100.00%|12,518,297,342.63|100%|33.00%|",
            "##### 另一小节标题",
        ]
        res = _extract_revenue_segments(lines)
        segs = res["segments"]
        # 仅取第一张表（跨标题截断），不应包含其他小节
        self.assertGreater(len(segs), 3)
        # 跳过汇总行（营业收入合计/精细化工行业 分产品 等）
        names = [s["name"] for s in segs]
        self.assertNotIn("营业收入合计", names)
        self.assertNotIn("精细化工行业", names)
        # 维度归属正确
        by_name = {s["name"]: s for s in segs}
        self.assertEqual(by_name["锂离子电池材料"]["dimension"], "按产品")
        self.assertAlmostEqual(by_name["锂离子电池材料"]["ratio"], 0.9039)
        self.assertEqual(by_name["境内"]["dimension"], "按地区")
        self.assertEqual(by_name["直销"]["dimension"], "按销售模式")

    def test_revenue_absent(self):
        """无营业收入构成表。"""
        res = _extract_revenue_segments(["没有收入分部表"])
        self.assertEqual(res["segments"], [])
        self.assertEqual(res["confidence"], "low")


# ---------------------------------------------------------------------------
# 6. 关键词文本摘录
# ---------------------------------------------------------------------------
class TestTextExcerpt(unittest.TestCase):
    """测试关键词文本摘录。"""

    def test_new_product_found(self):
        """新品收入关键词命中与摘录。"""
        lines = ["公司新产品收入占比达到 25%，较上年提升 8 个百分点。"]
        res = _text_excerpt(lines, ("新品收入", "新产品收入", "新品占比", "新产品销售额"))
        self.assertTrue(res["found"])
        self.assertIn("新产品收入", res["keywords_hit"])
        self.assertTrue(res["excerpts"])

    def test_supply_chain_found(self):
        """供应链风险关键词命中。"""
        lines = ["公司面临核心原材料依赖所致的供应链风险。"]
        res = _text_excerpt(lines, ("供应链风险", "供应链安全", "供应风险", "核心原材料依赖"))
        self.assertTrue(res["found"])
        self.assertIn("供应链风险", res["keywords_hit"])

    def test_not_found(self):
        """关键词未命中时 low 且 found=False。"""
        res = _text_excerpt(["无关内容"], ("新品收入",))
        self.assertFalse(res["found"])
        self.assertEqual(res["confidence"], "low")


# ---------------------------------------------------------------------------
# 7. 组装与警告
# ---------------------------------------------------------------------------
class TestParseMarkdown(unittest.TestCase):
    """测试解析组装与文件入口。"""

    _SAMPLE = """# 广州天赐高新材料股份有限公司 2025 年年度报告

## 释义
|天津天赐|指|天津天赐高新材料有限公司，为公司的全资子公司。|
|德国天赐|指|TINCI MATERIALS GmbH，为公司的全资子公司。|

## 员工情况
|报告期末在职员工的数量合计（人）||7,389|
|研发人员数量（人）||848|
|研发人员数量占比 研发人员学历结构||11.48%|10.78%
|本科||446||359|
|硕士||267||208|
|博士||32||25|
|其他 研发人员年龄构成||103||110|

## 研发投入
|研发投入金额（元）||846,948,352.88|
|研发投入占营业收入比例|||5.09%|
|资本化研发投入占研发投入的比例|||0.00%|

## 营业收入构成
##### （1）
|营业收入合计 分行业|16,649,892,556.28|100%|33.00%|
|精细化工行业 分产品|16,649,892,556.28|100.00%|33.00%|
|锂离子电池材料|15,050,539,053.67|90.39%|
|日化材料及特种 化学品|1,284,576,597.36|7.72%|
|其他 分地区|314,776,905.25|1.89%|
|境内|16,016,375,022.13|96.20%|
|境外 分销售模式|633,517,534.15|3.80%|
|直销|16,649,892,556.28|100.00%|
"""

    def test_parse_markdown_text_full(self):
        """完整内容解析：各块均有值，无相关警告。"""
        res = parse_markdown_text(self._SAMPLE)
        self.assertEqual(res["employees"]["total_employees"], 7389.0)
        self.assertEqual(res["employees"]["rd_staff_count"], 848.0)
        self.assertGreaterEqual(len(res["subsidiaries"]["subsidiaries"]), 2)
        self.assertTrue(res["subsidiaries"]["subsidiaries"][1]["overseas"])
        self.assertEqual(res["rd"]["rd_total_amount"], 846948352.88)
        self.assertGreaterEqual(len(res["revenue_segments"]["segments"]), 2)
        # 样本含有的核心章节（员工/子公司/研发/收入分部）不应产生相关警告；
        # 新品收入与供应链风险章节样本未披露，产生对应警告属正常行为
        core_warnings = [w for w in res["warnings"]
                         if any(k in w for k in ("员工", "子公司", "研发", "收入分部"))]
        self.assertEqual(core_warnings, [])

    def test_parse_markdown_text_warnings(self):
        """缺失章节产生警告而非猜测。"""
        res = parse_markdown_text("只有一行无关文本")
        self.assertTrue(any("员工" in w for w in res["warnings"]))
        self.assertTrue(any("子公司" in w for w in res["warnings"]))
        self.assertTrue(any("研发" in w for w in res["warnings"]))

    def test_parse_markdown_file(self):
        """文件入口含 source_file 与 parsed_at。"""
        import tempfile
        with tempfile.NamedTemporaryFile(
                mode="w", suffix=".md", encoding="utf-8", delete=False) as f:
            f.write(self._SAMPLE)
            tmp_path = f.name
        try:
            res = parse_markdown_file(tmp_path)
            self.assertIn("source_file", res)
            self.assertIn("parsed_at", res)
            self.assertEqual(res["employees"]["total_employees"], 7389.0)
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)