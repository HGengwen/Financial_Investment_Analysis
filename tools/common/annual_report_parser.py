#!/usr/bin/env python3
"""A 股/港股年报 Markdown 定向抽取器（阶段四：年报解析）。

输入为 `pdf_extract` / `report_hub.py extract` 产出的年报 markdown（可能含不规整的
pdf 文本抽取痕迹，如单元格内多余 `|`、跨行错位）。本模块按技能文件的年报章节定位，
定向抽取以下六大类字段并输出结构化 JSON（每项带 confidence 与源文本摘录，供上层
LLM 做人才维度与地缘 Y 轴评估，最终判定交给评分引擎而非本解析器）：

1. 员工情况（研发人数/占比/学历结构/员工总数） → 支撑人才密度 J 指标
2. 子公司列表（名称/关系/海外实体）           → 支撑地缘 Y 轴海外实体评估
3. 研发投入章节（金额/强度/资本化金额/资本化率）→ 支撑研发转化 E/H 指标
4. 收入分部（按产品/行业/地区）               → 支撑景气前瞻与收入结构
5. 新品收入占比（文本摘录）                   → 支撑欧奈尔 N 因子 F 指标
6. 供应链风险（文本摘录）                    → 支撑反证清单红线

解析器定位是"辅助结构化预抽取"，不追求 100% 覆盖；无法确定的字段置 None 并在
warnings 中标注，不猜测。

Usage:
    python tools/common/annual_report_parser.py <年报md路径> [--output-json]

    from tools.common import annual_report_parser
    res = annual_report_parser.parse_markdown_file("cninfo_reports/extracted/xxx.md")
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# 通用辅助
# ---------------------------------------------------------------------------

def _num(text: Optional[str]) -> Optional[float]:
    """把数值文本转为 float，去掉千分位逗号；无法解析返回 None。

    Args:
        text: 待转换文本。

    Returns:
        float 或 None。
    """
    if not text:
        return None
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(text))
    if not m:
        return None
    return float(m.group().replace(",", ""))


def _pct(text: Optional[str]) -> Optional[float]:
    """把百分比文本（如 "11.48%"）解析为小数（0.1148）。

    Args:
        text: 待转换文本。

    Returns:
        float 或 None。
    """
    if not text:
        return None
    m = re.search(r"-?\d[\d,]*(?:\.\d+)?\s*%?", str(text))
    if not m:
        return None
    raw = m.group()
    val = float(raw.replace(",", "").replace("%", "").strip())
    return val / 100.0 if "%" in raw else val


def _first_number_after(text: str, keyword: str) -> Optional[float]:
    """在指定行内，于 keyword 之后取第一个数字。

    Args:
        text: 目标文本行。
        keyword: 关键词。

    Returns:
        数字或 None。
    """
    idx = text.find(keyword)
    if idx < 0:
        return None
    tail = text[idx + len(keyword):]
    return _num(tail)


def _match_line(lines: List[str], pattern: str) -> Optional[str]:
    """返回首个匹配指定正则的行文本；未匹配返回 None。

    Args:
        lines: 文本行列表。
        pattern: 正则。

    Returns:
        匹配行或 None。
    """
    regex = re.compile(pattern)
    for line in lines:
        if regex.search(line):
            return line
    return None


# ---------------------------------------------------------------------------
# 各抽取器
# ---------------------------------------------------------------------------

def _extract_employees(lines: List[str]) -> Dict:
    """抽取员工情况。

    定位份年报"研发人员情况"表格与在职员工信息。支持 pdf 抽取的不规整表格
    （单元格内多余 `|`）。

    Args:
        lines: markdown 文本行。

    Returns:
        dict: {"total_employees", "rd_staff_count", "rd_staff_ratio",
               "degree": {masters, phd, bachelor, others}, "confidence", "source"}。
    """
    result: Dict = {
        "total_employees": None, "rd_staff_count": None, "rd_staff_ratio": None,
        "degree": {"masters": None, "phd": None, "bachelor": None, "others": None},
        "confidence": "low", "source": "",
    }
    sources = []

    # 员工总数：优先取"在职员工的数量合计"，避免误取母公司数量
    total_line = _match_line(lines, r"在职员工的数量合计.*?(\d[\d,]*)")
    if not total_line:
        total_line = _match_line(lines, r"在职员工.*?(\d[\d,]*)")
    if not total_line:
        total_line = _match_line(lines, r"员工总数.*?(\d[\d,]*)")
    if total_line:
        result["total_employees"] = _num(total_line)
        sources.append(total_line.strip())

    # 研发人员数量（人）
    rd_line = _match_line(lines, r"研发人员数量[（(]?人[）)]?")
    if rd_line:
        result["rd_staff_count"] = _num(rd_line)
        sources.append(rd_line.strip())

    # 研发人员数量占比
    ratio_line = _match_line(lines, r"研发人员数量占比")
    if ratio_line:
        result["rd_staff_ratio"] = _pct(ratio_line)
        sources.append(ratio_line.strip())

    # 学历结构（本科/硕士/博士/其他）：限定在研发人员学历结构表区域，避免命中全文首个"其他"单元格
    degree_zone_start = None
    for i, line in enumerate(lines):
        if "研发人员学历结构" in line or "研发人员数量占比" in line:
            degree_zone_start = i
            break
    if degree_zone_start is not None:
        for line in lines[degree_zone_start + 1:degree_zone_start + 12]:
            stripped = line.strip().strip("|").strip()
            for key, kw in (("masters", "硕士"), ("phd", "博士"),
                            ("bachelor", "本科"), ("others", "其他")):
                if stripped.startswith(kw):
                    result["degree"][key] = _num(line)
                    sources.append(line.strip())
                    break

    if sources:
        result["confidence"] = "medium"
        result["source"] = "；".join(sources[:6])
    return result


def _extract_subsidiaries(lines: List[str]) -> Dict:
    """抽取子公司列表（名称/关系/海外实体）。

    主要依据年报"释义"与"合并财务报表附注—在其他主体中的权益"中的
    "为公司的（全资/控股/参股）子公司"句式逐行识别。海外实体依据名称含非中文
    或含海外注册地名（新加坡、德国、美国、捷克、荷兰、韩国、摩洛哥、印尼、
    墨西哥、毛里求斯、津巴布韦、法国、瑞士、加拿大、香港等）标注。

    Args:
        lines: markdown 文本行。

    Returns:
        dict: {"subsidiaries": [{"name", "relation", "overseas"}],
               "overseas_count", "confidence", "source"}。
    """
    result: Dict = {"subsidiaries": [], "overseas_count": 0,
                    "confidence": "low", "source": ""}
    overseas_keywords = (
        "新加坡", "德国", "美国", "捷克", "荷兰", "韩国", "摩洛哥", "印尼",
        "墨西哥", "毛里求斯", "津巴布韦", "法国", "瑞士", "加拿大", "香港",
        "泰国", "印度", "巴西", "越南", "马来西亚",
    )
    relation_order = ["全资子公司", "控股子公司", "参股子公司"]
    seen: set = set()
    hits = 0

    # 释义行形如：|天津天赐|指|天津天赐高新材料有限公司，为公司的全资子公司。|
    # 或正文行：XXX，为公司的全资子公司。
    # 优先解析释义行，取首列"简称"作为名称（海外实体常为英文，能保留下文判别 overseas）
    definition_re = re.compile(
        r"^\|([^|]+)\|指\|.*?为公司的?(全资子公司|控股子公司|参股子公司)"
    )
    body_re = re.compile(
        r"([\u4e00-\u9fa5A-Za-z0-9·（）()\-]{2,40})"
        r"，?为公司的?(全资子公司|控股子公司|参股子公司|全资控股子公司)"
    )
    # 释义行直接命中简称；否则回退到正文行正则
    for line in lines:
        m = definition_re.match(line)
        if m:
            name, relation_txt = m.group(1).strip(), m.group(2)
        else:
            bm = body_re.search(line)
            if not bm:
                continue
            name, relation_txt = bm.group(1).strip(), bm.group(2)
        # 过滤噪声词（泛称与重复）
        if name in seen or len(name) < 2 or "指" in name:
            continue
        relation = "参股" if "参股" in relation_txt else \
                   ("控股" if "控股" in relation_txt else "全资")
        overseas = any(kw in line or kw in name for kw in overseas_keywords)
        seen.add(name)
        result["subsidiaries"].append({
            "name": name, "relation": relation, "overseas": overseas,
        })
        hits += 1

    if not result["subsidiaries"]:
        return result  # 保持 low

    result["overseas_count"] = sum(1 for s in result["subsidiaries"] if s["overseas"])
    result["confidence"] = "high" if hits >= 5 else "medium"
    result["source"] = f"抽取 {len(result['subsidiaries'])} 家子公司（海外 {result['overseas_count']} 家）"
    return result


def _extract_rd_section(lines: List[str]) -> Dict:
    """抽取研发投入章节（金额/强度/资本化）。

    Args:
        lines: markdown 文本行。

    Returns:
        dict: {"rd_total_amount", "rd_intensity", "rd_capitalization_amount",
               "rd_capitalization_rate", "rd_projects", "confidence", "source"}。
    """
    result: Dict = {
        "rd_total_amount": None, "rd_intensity": None,
        "rd_capitalization_amount": None, "rd_capitalization_rate": None,
        "rd_projects": [], "confidence": "low", "source": "",
    }

    amt_line = _match_line(lines, r"研发投入金额")
    if amt_line:
        result["rd_total_amount"] = _num(amt_line)
    intensity_line = _match_line(lines, r"研发投入占营业收入比例")
    if intensity_line:
        result["rd_intensity"] = _pct(intensity_line)
    cap_line = _match_line(lines, r"研发投入资本化(?:的金额)")
    if cap_line:
        result["rd_capitalization_amount"] = _num(cap_line)
    rate_line = _match_line(lines, r"资本化研发投入占研发投入的比例")
    if rate_line:
        result["rd_capitalization_rate"] = _pct(rate_line)

    # 研发项目清单：取自"主要研发项目名称"表
    project_pattern = re.compile(r"研发项目(?:名|目录)")
    capturing = False
    for line in lines:
        if project_pattern.search(line):
            capturing = True
            continue
        if capturing:
            # 项目行：|二氟双草酸磷酸锂|满足新型...
            if line.startswith("|") and not re.match(r"^\|\s*---", line):
                cells = [c.strip() for c in line.strip("|").split("|")]
                name = cells[0]
                if len(name) > 1 and name not in result["rd_projects"] and \
                        "项目" not in name[:3]:
                    result["rd_projects"].append(name)
            # 项目表结束（遇到新的主要标题或空行连续）
            if not line.strip():
                break

    sources = []
    if amt_line:
        sources.append(amt_line.strip())
    if rate_line:
        sources.append(rate_line.strip())
    if sources:
        result["confidence"] = "medium"
        result["source"] = "；".join(sources[:4])
    return result


def _extract_revenue_segments(lines: List[str]) -> Dict:
    """抽取收入分部（按产品/行业/地区）。

    依据"营业收入构成"表格，抽取按行业/产品/地区分类的各行名称与金额占比。

    Args:
        lines: markdown 文本行。

    Returns:
        dict: {"segments": [{"dimension", "name", "amount", "ratio"}],
               "confidence", "source"}。
    """
    result: Dict = {"segments": [], "confidence": "low", "source": "",
                    "raw_lines": []}
    start_idx = None
    for i, line in enumerate(lines):
        if "营业收入构成" in line or "营业收入分行业" in line:
            start_idx = i
            break
    if start_idx is None:
        return result
    # 跳过起始标题行（如"##### （1）营业收入构成"），从其下正文开始
    while start_idx < len(lines) and (
            re.match(r"^#+\s", lines[start_idx]) or not lines[start_idx].strip()):
        start_idx += 1
    # 维度标记：尾部" 分行业/分产品/分地区/分销售模式"；行中同时被标记为换维
    dim_map = {"分行业": "按行业", "分产品": "按产品",
               "分地区": "按地区", "分销售模式": "按销售模式"}
    dim_current = ""
    title_keywords = ("营业收入合计", "营业成本合计")
    segment_pattern = re.compile(
        r"^\|([\u4e00-\u9fa5A-Za-z0-9·（）()\- ]{2,25})\|([\d,\.]+)\|([\d,]*(?:\.\d+)?%)?")
    for line in lines[start_idx:start_idx + 150]:
        # markdown 标题即为该表结束（跳过后续其他表格，避免重复抽取）
        if re.match(r"^#{2,}\s", line):
            break
        # 维度切换：尾部含" 分X"
        for marker, dim in dim_map.items():
            if marker in line:
                dim_current = dim
                break
        # 跳过表头/汇总行/维度切换自身行
        stripped = line.strip().strip("|")
        if line.startswith("|") and (
                stripped.startswith(tuple(title_keywords))
                or any(stripped == d for d in ("按行业", "按产品", "按地区", "按销售模式"))
                or stripped.startswith(("2025", "金额", "项目", "营业收入    营业成本"))
                or re.match(r"^\|[\s\-]+$", line)):
            continue
        m = segment_pattern.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        if any(marker in name for marker in dim_map) or name in title_keywords:
            continue
        amount = _num(m.group(2))
        ratio = _pct(m.group(3)) if m.group(3) else None
        result["segments"].append({
            "dimension": dim_current or "",
            "name": name, "amount": amount, "ratio": ratio,
        })
    if result["segments"]:
        result["confidence"] = "medium"
        result["source"] = f"抽取 {len(result['segments'])} 个收入分部维度条目"
    return result


def _text_excerpt(lines: List[str], keywords: tuple) -> Dict:
    """按关键词抽取相关文本摘录（新品收入占比/供应链风险通用）。

    Args:
        lines: markdown 文本行。
        keywords: 关键词元组。

    Returns:
        dict: {"found": bool, "excerpts": [...], "confidence", "source"}。
    """
    found = [kw for kw in keywords if any(kw in l for l in lines)]
    excerpts = []
    for line in lines:
        if any(kw in line for kw in keywords) and \
                line.strip() and not line.startswith("#"):
            clean = line.strip().strip("|")
            if clean and len(clean) > 4 and clean not in excerpts:
                excerpts.append(clean[:160])
    return {
        "found": bool(found),
        "keywords_hit": found,
        "excerpts": excerpts[:8],
        "confidence": "medium" if excerpts else "low",
        "source": "；".join(excerpts[:3]) if excerpts else "未找到相关章节",
    }


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------

def parse_markdown_text(text: str) -> Dict:
    """解析年报 markdown 文本，返回结构化字段。

    Args:
        text: 年报 markdown 全文。

    Returns:
        dict: {"employees", "subsidiaries", "rd", "revenue_segments",
               "new_product", "supply_chain", "warnings"}。
    """
    lines = text.splitlines()
    warnings = []

    employees = _extract_employees(lines)
    subsidiaries = _extract_subsidiaries(lines)
    rd = _extract_rd_section(lines)
    revenue_segments = _extract_revenue_segments(lines)
    new_product = _text_excerpt(
        lines, ("新品收入", "新产品收入", "新品占比", "新产品销售额"))
    supply_chain = _text_excerpt(
        lines, ("供应链风险", "供应链安全", "供应风险", "核心原材料依赖"))

    if not employees.get("source"):
        warnings.append("员工情况章节未定位到")
    if not subsidiaries.get("subsidiaries"):
        warnings.append("未抽取到子公司列表")
    if rd.get("rd_total_amount") is None:
        warnings.append("研发投入金额未抽取到")
    if not revenue_segments.get("segments"):
        warnings.append("收入分部表格未抽取到")
    if not new_product.get("found"):
        warnings.append("新品收入占比未定位（可能未披露）")
    if not supply_chain.get("found"):
        warnings.append("供应链风险章节未定位")

    return {
        "employees": employees,
        "subsidiaries": subsidiaries,
        "rd": rd,
        "revenue_segments": revenue_segments,
        "new_product": new_product,
        "supply_chain": supply_chain,
        "warnings": warnings,
    }


def parse_markdown_file(path: str) -> Dict:
    """从文件读取年报 markdown 并解析。

    Args:
        path: markdown 文件路径。

    Returns:
        dict: 结构化解析结果（含 source_file 与 parsed_at）。
    """
    from datetime import datetime
    p = Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")
    result = parse_markdown_text(text)
    result["source_file"] = str(p)
    result["parsed_at"] = datetime.now().isoformat(timespec="seconds")
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI 入口。支持 --output-json（仅输出纯 JSON）以避免 Windows 控制台编码问题。"""
    parser = argparse.ArgumentParser(
        description="年报 markdown 定向抽取器（员工/子公司/研发/收入分部/新品/供应链）")
    parser.add_argument("path", metavar="MD_PATH",
                        help="年报 markdown 文件路径")
    parser.add_argument("--output-json", action="store_true",
                        help="仅输出纯 JSON 到 stdout（否则输出排版化的中文摘要）")
    args = parser.parse_args()

    try:
        result = parse_markdown_file(args.path)
    except Exception as e:  # noqa: BLE001
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False),
              file=sys.stderr)
        sys.exit(1)

    if args.output_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    # 默认：中文可读摘要
    def _brief(label: str, value) -> str:
        return f"{label}: {json.dumps(value, ensure_ascii=False)}"

    print("=== 年报结构化抽取结果 ===")
    print(_brief("员工情况", result["employees"]))
    print(_brief("子公司(前10)", {
        "subsidiaries": result["subsidiaries"]["subsidiaries"][:10],
        "overseas_count": result["subsidiaries"]["overseas_count"],
    }))
    print(_brief("研发投入", result["rd"]))
    print(_brief("收入分部(前10)", result["revenue_segments"]["segments"][:10]))
    print(_brief("新品收入", result["new_product"]))
    print(_brief("供应链风险", result["supply_chain"]))
    print(_brief("警告", result["warnings"]))
    print(_brief("来源文件", result.get("source_file")))


if __name__ == "__main__":
    main()