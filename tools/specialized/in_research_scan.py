#!/usr/bin/env python3
"""在研重大项目扫描器（trend-tech-screen 步骤 3-A 落地工具）。

将 `research/quality-screen/在研重大项目信息获取方法的整合与强化.md` 中
"五、实操执行指令" 拆分的手动搜索指令整合为一条可编程调用的批量入口：

- 按渠道统一构建查询配方（query / sites / time_range / industry / auth_level），
  与方案文档指令逐条对应，可复现、可单测。
- 通过 `tools/common/doubao_search.py` 的**模块接口**（而非子进程）执行各渠道搜索，
  共享其自动回退（订阅套餐→按量计费）与 QPS 限流能力。
- 可选接入 `tools/common/annual_report_parser.py` 解析年报在研项目章节。
- 聚合各渠道结果，输出候选链接与信号摘要，供上层 LLM 填写 **R8 在研项目评分卡**
  （评分判定交给 `trend_tech_screen.py score --r8`，禁止 LLM 心算）。

渠道清单（对应方案文档步骤 3-A）:
    gov        政府立项背书（国家重点研发计划 / 重大科技专项）
    patent     国家知识产权局专利检索（技术先验指标）
    bidding    招投标平台（ToB/ToG 商业化验证）
    academic   学术/技术社区（前沿技术曝光）
    investor   投资者互动平台（区分深交所互动易 / 上交所 e 互动）
    website    公司官网/公众号动态（需 --official-site）
    research   券商深度研报（核心假设项目拆分）
    annual_report  年报"管理层讨论与分析"章节（需 --annual-report 指向 markdown）

Usage:
    # 全渠道扫描（普通搜索渠道）
    {py} tools/specialized/in_research_scan.py scan 中芯国际 --market sh --export

    # 指定渠道子集，加速验证
    {py} tools/specialized/in_research_scan.py scan 寒武纪 --channels patent,gov,bidding --json

    # 附带官网域名 + 年报文件
    {py} tools/specialized/in_research_scan.py scan 中芯国际 \\
        --official-site smics.com --annual-report reports/002709_2025年报.md --export

    # 列出渠道元信息
    {py} tools/specialized/in_research_scan.py list
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

# 项目根目录（本文件位于 tools/specialized/，向上 3 层）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

#: 模块接口（可替换注入以便测试）
def _default_search_fn(query, count=10, time_range=None, industry=None,
                       auth_info_level=0, sites=None, **kwargs):
    """默认搜索函数：委托 doubao_search 模块接口，抽取 BOM 掉 kwargs 以防传参过多。

    Args:
        query: 搜索关键词。
        count: 返回条数。
        time_range: 时间范围。
        industry: 行业类型。
        auth_info_level: 权威度 0/1。
        sites: 站点列表。

    Returns:
        doubao_search 标准化的结果列表。
    """
    from tools.common import doubao_search  # 延迟导入，避免循环依赖
    return doubao_search.doubao_search(
        query=query,
        count=count,
        time_range=time_range,
        industry=industry,
        auth_info_level=auth_info_level,
        sites=sites,
    )


# ---------------------------------------------------------------------------
# 常量：渠道元信息与查询配方
# ---------------------------------------------------------------------------

#: 默认返回条数
DEFAULT_COUNT = 10


@dataclass
class ChannelQuery:
    """单个渠道的查询配方。

    Attributes:
        query: 搜索关键词。
        sites: 限定站点（豆包接口以 "|" 分隔）。
        time_range: 时间范围（day/week/month/year）。
        industry: 行业类型（finance/game/gov）。
        auth_level: 权威度限制 0/1。
        count: 返回条数。
    """

    query: str
    sites: Optional[str] = None
    time_range: Optional[str] = None
    industry: Optional[str] = None
    auth_level: int = 0
    count: int = DEFAULT_COUNT
    label_hint: Optional[str] = None


@dataclass
class ChannelSpec:
    """渠道定义。

    Attributes:
        label: 渠道中文名。
        build: 渲染查询配方的回调（注入公司名/官网域名）。
        accepts_official_site: 是否依赖 --official-site。
    """

    label: str
    build: Callable[[str, Optional[str]], List[ChannelQuery]]
    accepts_official_site: bool = False


def _cn(company: str, official_site: Optional[str]) -> List[ChannelQuery]:
    """渠道 gov：政府科技项目立项背书。

    Args:
        company: 公司名。
        official_site: 官网域名（本渠道不用）。

    Returns:
        查询配方列表。
    """
    del official_site
    return [ChannelQuery(
        query=f"{company} 国家重点研发计划 重大科技专项",
        sites="gov.cn", time_range="year",
    )]


def _patent(company: str, official_site: Optional[str]) -> List[ChannelQuery]:
    """渠道 patent：国家知识产权局专利检索（技术先验指标）。

    Args:
        company: 公司名。
        official_site: 官网域名（本渠道不用）。

    Returns:
        查询配方列表。
    """
    del official_site
    return [ChannelQuery(
        query=f"{company} 发明 在研 新型 制备",
        sites="cpquery.cponline.cnipa.gov.cn", time_range="year", count=15,
    )]


def _bidding(company: str, official_site: Optional[str]) -> List[ChannelQuery]:
    """渠道 bidding：招投标平台（ToB/ToG 商业化验证）。

    Args:
        company: 公司名。
        official_site: 官网域名（本渠道不用）。

    Returns:
        查询配方列表。
    """
    del official_site
    return [ChannelQuery(
        query=f"{company} 中标 研发 项目 系统",
        sites="ccgp.gov.cn", time_range="year", count=15,
    )]


def _academic(company: str, official_site: Optional[str]) -> List[ChannelQuery]:
    """渠道 academic：学术/技术社区（前沿技术曝光）。

    Args:
        company: 公司名。
        official_site: 官网域名（本渠道不用）。

    Returns:
        查询配方列表。
    """
    del official_site
    # 豆包接口站点以 "|" 分隔（方案文档以逗号书写，此处归一为接口口径）
    return [ChannelQuery(
        query=f"{company} 技术 论文 开源",
        sites="arxiv.org|github.com|cnki.net", time_range="year",
    )]


def _investor(company: str, official_site: Optional[str]) -> List[ChannelQuery]:
    """渠道 investor：投资者互动平台问答（区分深交所/上交所）。

    Args:
        company: 公司名。
        official_site: 官网域名（本渠道不用）。

    Returns:
        查询配方列表。
    """
    del official_site
    return [
        ChannelQuery(
            query=f"{company} 研发 进展 在研",
            sites="irm.cninfo.com.cn", time_range="month", count=15,
            label_hint="深交所互动易",
        ),
        ChannelQuery(
            query=f"{company} 研发 项目 进展",
            sites="www.sse.com.cn/assess/analysis", time_range="month", count=15,
            label_hint="上交所 e 互动",
        ),
    ]


def _website(company: str, official_site: Optional[str]) -> List[ChannelQuery]:
    """渠道 website：公司官网/官方公众号动态（需官网域名）。

    Args:
        company: 公司名（本渠道不作为关键词，仅返回空列表兜底）。
        official_site: 官网域名。

    Returns:
        查询配方列表；official_site 为空时返回空列表。
    """
    del company
    if not official_site:
        return []
    return [ChannelQuery(
        query="研发 突破 成功 交付 验证",
        sites=official_site, time_range="month",
    )]


def _research(company: str, official_site: Optional[str]) -> List[ChannelQuery]:
    """渠道 research：券商深度研报。

    Args:
        company: 公司名。
        official_site: 官网域名（本渠道不用）。

    Returns:
        查询配方列表。
    """
    del official_site
    year = datetime.now().year
    return [ChannelQuery(
        query=f"{company} 深度 研报 在研项目 {year}",
        industry="finance", auth_level=1, time_range="year",
    )]


#: 渠道注册表（annual_report 单独处理，不入此表）
CHANNELS: Dict[str, ChannelSpec] = {
    "gov": ChannelSpec("政府立项背书", _cn),
    "patent": ChannelSpec("专利检索（技术先验）", _patent),
    "bidding": ChannelSpec("招投标（商业化验证）", _bidding),
    "academic": ChannelSpec("学术/技术社区", _academic),
    "investor": ChannelSpec("投资者互动平台", _investor),
    "website": ChannelSpec("官网/公众号动态", _website, accepts_official_site=True),
    "research": ChannelSpec("券商深度研报", _research),
}

#: 年报表在研项目关键词（与方案文档"管理层讨论"章节一致）
ANNUAL_REPORT_KEYWORDS: List[str] = [
    "在研项目", "研发管线", "产品进度", "商业化时间表", "研发资本化", "开发支出", "在建工程",
]


def build_queries(
    company: str,
    channels: Optional[List[str]] = None,
    official_site: Optional[str] = None,
) -> Dict[str, List[ChannelQuery]]:
    """按渠道构建查询配方词典。

    Args:
        company: 公司名。
        channels: 需要构建的渠道键列表；None 表示全部渠道。
        official_site: 官网域名（供 website 渠道）。

    Returns:
        dict: 渠道键 -> 查询配方列表。

    Raises:
        ValueError: 当 channels 中出现未知渠道键时抛出。
    """
    keys = list(CHANNELS.keys()) if channels is None else channels
    out: Dict[str, List[ChannelQuery]] = {}
    for key in keys:
        if key not in CHANNELS:
            raise ValueError(
                f"未知渠道 '{key}'，可选: {list(CHANNELS.keys())} + annual_report"
            )
        out[key] = CHANNELS[key].build(company, official_site)
    return out


# ---------------------------------------------------------------------------
# 聚合与输出
# ---------------------------------------------------------------------------

def _result_fingerprint(item: Dict) -> str:
    """从单条搜索结果提取去重指纹（标题+链接）。

    Args:
        item: 标准化的搜索结果 dict。

    Returns:
        指纹字符串。
    """
    return f"{item.get('title', '')}|{item.get('url', '')}"


def channel_result(
    key: str,
    queries: List[ChannelQuery],
    results_by_query: List[List[Dict]],
) -> Dict:
    """将一个渠道的多组查询结果聚合为结构化条目。

    Args:
        key: 渠道键。
        queries: 该渠道的查询配方列表。
        results_by_query: 与 queries 一一对应的搜索结果列表（外层为查询，内层为结果）。

    Returns:
        聚合后的渠道条目 dict。
    """
    all_items: List[Dict] = []
    seen: set = set()
    query_records: List[Dict] = []
    for q, results in zip(queries, results_by_query):
        items = []
        for r in results:
            fp = _result_fingerprint(r)
            if fp in seen:
                continue
            seen.add(fp)
            items.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "site_name": r.get("site_name", ""),
                "publish_time": r.get("publish_time", ""),
                "summary": r.get("summary", ""),
            })
        all_items.extend(items)
        query_records.append({
            "query": q.query,
            "label_hint": q.label_hint,
            "count": len(items),
        })
    return {
        "key": key,
        "label": CHANNELS.get(key, ChannelSpec(key, lambda *_: [])).label if key in CHANNELS else key,
        "queries": query_records,
        "total": len(all_items),
        "results": all_items,
        "top_links": [
            {"title": it["title"], "url": it["url"],
             "publish_time": it["publish_time"]}
            for it in all_items[:5]
        ],
    }


def aggregate(
    company: str,
    queries_by_channel: Dict[str, List[ChannelQuery]],
    results_by_channel: Dict[str, List[List[Dict]]],
    annual_report: Optional[Dict] = None,
) -> Dict:
    """聚合全部渠道结果，生成结构化输出。

    Args:
        company: 公司名。
        queries_by_channel: 渠道 -> 查询配方列表。
        results_by_channel: 渠道 -> （每个查询）搜索结果列表。
        annual_report: 可选，annual_report_parser 的年报解析结果。

    Returns:
        完整的扫描结果 dict，供 --json / --export 输出。
    """
    channels_dict: Dict[str, Dict] = {}
    for key in queries_by_channel:
        channels_dict[key] = channel_result(
            key,
            queries_by_channel[key],
            results_by_channel.get(key, [[] for _ in queries_by_channel[key]]),
        )
    return {
        "company": company,
        "scanned_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "channels": channels_dict,
        "annual_report": annual_report or {},
    }


def export_markdown(result: Dict, save_path: str) -> str:
    """将扫描结果导出为 Markdown 报告（供 R8 评分卡填写）。

    Args:
        result: aggregate 产生的扫描结果。
        save_path: 导出路径。

    Returns:
        保存路径。
    """
    lines = [
        "# 在研重大项目扫描报告",
        "",
        f"- **公司**：{result['company']}",
        f"- **扫描时间**：{result.get('scanned_at', '')}",
        "",
    ]
    for key, ch in result["channels"].items():
        lines.append(f"## {ch['label']}（{ch['total']} 条）")
        for q in ch["queries"]:
            hint = f"（{q['label_hint']}）" if q.get("label_hint") else ""
            lines.append(f"- {q['query']}{hint}")
        if ch["results"]:
            for it in ch["results"]:
                title = it["title"] or "无标题"
                url = it["url"] or ""
                pub = it["publish_time"] or "未知"
                lines.append(f"  - [{title}]({url})（{pub}）")
        else:
            lines.append("  - 未检索到有效结果")
        lines.append("")
    if result.get("annual_report"):
        lines.append("## 年报在研项目章节（annual_report_parser）")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(result["annual_report"], ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("")
    with open(save_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    return save_path


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------

def scan(
    company: str,
    channels: Optional[List[str]] = None,
    official_site: Optional[str] = None,
    annual_report_path: Optional[str] = None,
    search_fn: Callable = _default_search_fn,
) -> Dict:
    """对指定公司执行在研项目多渠道扫描。

    Args:
        company: 公司名。
        channels: 需要扫描的渠道键列表；None 表示全部普通渠道。
        official_site: 官网域名（供 website 渠道）。
        annual_report_path: 年报 markdown 路径（可选）。
        search_fn: 搜索函数；默认 doubao_search，可在测试中注入 mock。

    Returns:
        聚合的扫描结果 dict。
    """
    queries_by_channel = build_queries(company, channels, official_site)

    # 并发执行各渠道搜索（QPS 限流由 doubao_search 内部承担）
    results_by_channel: Dict[str, List[List[Dict]]] = {}
    for key, queries in queries_by_channel.items():
        channel_results: List[List[Dict]] = []
        for q in queries:
            try:
                channel_results.append(search_fn(
                    query=q.query,
                    count=q.count,
                    time_range=q.time_range,
                    industry=q.industry,
                    auth_info_level=q.auth_level,
                    sites=q.sites,
                ))
            except Exception as exc:  # 单渠道失败不阻断整体扫描
                sys.stderr.write(
                    f"[警告] 渠道 {key} 查询失败（{q.query}）: {exc}\n"
                )
                channel_results.append([])
        results_by_channel[key] = channel_results

    # 可选：解析年报在研项目章节
    annual_report: Optional[Dict] = None
    if annual_report_path and Path(annual_report_path).exists():
        try:
            from tools.common import annual_report_parser
            annual_report = annual_report_parser.parse_markdown_file(annual_report_path)
        except Exception as exc:  # noqa: BLE001 - 年报解析失败不阻断扫描
            sys.stderr.write(f"[警告] 年报解析失败: {exc}\n")

    return aggregate(company, queries_by_channel, results_by_channel, annual_report)


# ---------------------------------------------------------------------------
# 命令行入口
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    """构建命令行解析器。

    Returns:
        配置完成 argparse.ArgumentParser。
    """
    parser = argparse.ArgumentParser(
        prog="in_research_scan",
        description="在研重大项目扫描器（trend-tech-screen 步骤 3-A）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "渠道列表: "
            + ", ".join(f"{k}({v.label})" for k, v in CHANNELS.items())
            + ", annual_report(年报解析)"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="执行在研项目扫描")
    p_scan.add_argument("company", help="公司名")
    p_scan.add_argument("--market", choices=["sz", "sh", "hk", "us"],
                        help="市场代码（sz=深交/互动易, sh=上交/e互动）")
    p_scan.add_argument("--channels",
                        help="扫描渠道键，逗号分隔（如 patent,gov,bidding）")
    p_scan.add_argument("--official-site", help="公司官网域名（website 渠道用）")
    p_scan.add_argument("--annual-report", help="年报 markdown 路径（可选）")
    p_scan.add_argument("--count", type=int, default=DEFAULT_COUNT,
                        help=f"每查询默认返回条数（默认 {DEFAULT_COUNT}）")
    p_scan.add_argument("--json", action="store_true", help="输出 JSON")
    p_scan.add_argument("--export", action="store_true",
                        help="导出 Markdown 报告到 reports/")
    p_scan.add_argument("--export-path", help="自定义导出路径")

    sub.add_parser("list", help="列出渠道元信息")
    return parser


def _main(argv: Optional[List[str]] = None) -> int:
    """命令行主入口。

    Args:
        argv: 命令行参数（测试时注入）。

    Returns:
        进程退出码。
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        for key, spec in CHANNELS.items():
            need_site = "（需 --official-site）" if spec.accepts_official_site else ""
            print(f"{key}: {spec.label}{need_site}")
        print("annual_report: 年报管理层讨论章节（需 --annual-report）")
        return 0

    if args.command == "scan":
        channels = None
        if getattr(args, "channels", None):
            channels = [c.strip() for c in args.channels.split(",") if c.strip()]
        result = scan(
            company=args.company,
            channels=channels,
            official_site=getattr(args, "official_site", None),
            annual_report_path=getattr(args, "annual_report", None),
        )
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            total = sum(ch["total"] for ch in result["channels"].values())
            print(f"公司: {result['company']} | 渠道: {len(result['channels'])} | 结果: {total}")
            for key, ch in result["channels"].items():
                print(f"\n[{ch['label']}] {ch['total']} 条")
                for it in ch["top_links"]:
                    print(f"  - {it['title']} | {it['url']} | {it['publish_time']}")
        if args.export:
            reports_dir = _PROJECT_ROOT / "reports"
            reports_dir.mkdir(exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = args.export_path or str(
                reports_dir / f"in_research_{args.company}_{ts}.md"
            )
            saved = export_markdown(result, path)
            print(f"\n[成功] 报告已保存至: {saved}")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(_main())