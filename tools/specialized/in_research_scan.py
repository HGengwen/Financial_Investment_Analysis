#!/usr/bin/env python3
"""在研重大项目扫描器（mid-trend-tech-screen 步骤 3-A 落地工具）。

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


    # 研发管线 NPV 粗算子（参数全部由调用方提供，缺失即标注数据不足）
    {py} tools/specialized/in_research_scan.py pipeline-npv --projects p.json \
        --discount-rate 0.10 --currency CNY --json
    # 列出渠道元信息
    {py} tools/specialized/in_research_scan.py list
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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
    seen: set[str] = set()
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
# 研发管线 NPV 粗算子（pipeline-npv 子命令）
# ---------------------------------------------------------------------------

#: 支持的币种（本工具只做同口径运算，**不做汇率换算**）
SUPPORTED_CURRENCIES: Tuple[str, ...] = ("CNY", "HKD", "USD")

#: 项目级必填字段（任一缺失即判定「数据不足」，工具不产生替代数值）
REQUIRED_PROJECT_FIELDS: Tuple[str, ...] = (
    "name",
    "peak_revenue",
    "launch_year",
    "probability",
    "source",
)

#: 敏感性规格允许的键：r=折现率绝对步长，p=概率绝对步长
_SENSITIVITY_KEYS: Tuple[str, ...] = ("r", "p")

#: 折现率上限：仅拦截「百分数当小数」的量纲误用（折现率以小数给出，如 0.10 表示 10%）
MAX_DISCOUNT_RATE: float = 1.0


class PipelineNpvError(ValueError):
    """pipeline-npv 的用法错误（对应进程退出码 2）。"""


def _is_number(value: Any) -> bool:
    """判断是否为有限实数（排除 bool / NaN / inf）。

    Args:
        value: 待判断的值。

    Returns:
        是有限实数返回 True，否则 False。
    """
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def load_projects(source: str) -> Dict[str, Any]:
    """读取 `--projects` 参数（JSON 文件路径，或 `-` 表示从 stdin 读取）。

    Args:
        source: 文件路径或 `-`。

    Returns:
        解析后的顶层 JSON 对象。

    Raises:
        PipelineNpvError: 文件不存在、JSON 解析失败或顶层不是对象。
    """
    if source == "-":
        raw_text = sys.stdin.read()
        origin = "stdin"
    else:
        path = Path(source)
        if not path.is_file():
            raise PipelineNpvError(f"--projects 文件不存在: {source}")
        raw_text = path.read_text(encoding="utf-8")
        origin = str(path)

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PipelineNpvError(
            f"--projects JSON 解析失败（{origin}）: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise PipelineNpvError("--projects 顶层必须为 JSON 对象（含 projects 数组）")
    return payload


def parse_sensitivity_spec(spec: str) -> Tuple[float, float]:
    """解析 `--sensitivity` 规格（形如 `r=0.01;p=0.10`，绝对步长）。

    Args:
        spec: 规格字符串。

    Returns:
        (折现率步长, 概率步长)。

    Raises:
        PipelineNpvError: 规格格式非法、键缺失/未知、步长非正数。
    """
    values: Dict[str, float] = {}
    for part in (chunk.strip() for chunk in spec.split(";")):
        if not part:
            continue
        if "=" not in part:
            raise PipelineNpvError(
                f'--sensitivity 规格非法（应形如 "r=0.01;p=0.10"）: "{part}"'
            )
        key, _, raw_value = part.partition("=")
        key = key.strip().lower()
        if key not in _SENSITIVITY_KEYS:
            raise PipelineNpvError(
                f'--sensitivity 含未知键 "{key}"（仅支持 r / p）'
            )
        try:
            value = float(raw_value.strip())
        except ValueError as exc:
            raise PipelineNpvError(f"--sensitivity 步长非数值: {part}") from exc
        if not math.isfinite(value) or value <= 0:
            raise PipelineNpvError(f"--sensitivity 步长必须为正数: {part}")
        values[key] = value

    # 3×3 网格需要两个键同时给出，缺一即视为规格非法
    for key in _SENSITIVITY_KEYS:
        if key not in values:
            raise PipelineNpvError(
                f'--sensitivity 缺少键 "{key}"（须同时给出 r=…;p=…）'
            )
    return values["r"], values["p"]


def extract_project_candidates(scan_result: Dict[str, Any]) -> List[str]:
    """从 `scan --json` 结果中提取**项目名候选**（仅标题，不含任何数值）。

    Args:
        scan_result: `scan --json` 的解析结果。

    Returns:
        去重后的候选标题列表（保持原顺序）。
    """
    candidates: List[str] = []
    seen: set[str] = set()
    channels = scan_result.get("channels")
    if not isinstance(channels, dict):
        return candidates

    for channel in channels.values():
        if not isinstance(channel, dict):
            continue
        for item in channel.get("top_links") or []:
            title = item.get("title") if isinstance(item, dict) else None
            if not isinstance(title, str):
                continue
            candidate = title.strip()
            if candidate and candidate not in seen:
                seen.add(candidate)
                candidates.append(candidate)
    return candidates


def load_project_candidates(path: str) -> List[str]:
    """读取 `--from-scan` 文件并提取项目名候选。

    Args:
        path: `scan --json` 输出文件路径。

    Returns:
        项目名候选列表。

    Raises:
        PipelineNpvError: 文件不存在、JSON 解析失败或顶层不是对象。
    """
    scan_path = Path(path)
    if not scan_path.is_file():
        raise PipelineNpvError(f"--from-scan 文件不存在: {path}")
    try:
        payload = json.loads(scan_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PipelineNpvError(
            f"--from-scan JSON 解析失败（{path}）: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise PipelineNpvError("--from-scan 顶层必须为 JSON 对象（scan --json 输出）")
    return extract_project_candidates(payload)


def parse_projects(payload: Dict[str, Any], as_of_year: int) -> Dict[str, Any]:
    """解析并校验 `--projects` 中的项目清单。

    校验规则（与《P3-8 开发方案与计划》§2.1/§3.2 一致）：
      - 必填字段缺失 / None / 空字符串 → 记入 missing（**业务状态**，不报错）；
      - 字段存在但类型或取值非法 → 抛 PipelineNpvError（**用法错误**）；
      - `cost` 缺省视为 0，并记入 defaults_applied（唯一允许的缺省，须透明回显）。

    Args:
        payload: `--projects` 顶层 JSON 对象。
        as_of_year: 基准年份。

    Returns:
        {"projects": [条目...], "missing": [...], "defaults_applied": [...],
         "data_insufficient": bool}；条目中 pv_peak / pv_cost / npv 初始为 None。

    Raises:
        PipelineNpvError: 字段类型非法、概率越界、折现期数为负。
    """
    raw_projects = payload.get("projects")
    missing: List[str] = []
    defaults_applied: List[str] = []
    projects: List[Dict[str, Any]] = []

    # 项目清单为空同样属「数据不足」，不产生任何数值
    if not isinstance(raw_projects, list) or not raw_projects:
        return {
            "projects": [],
            "missing": ["projects"],
            "defaults_applied": [],
            "data_insufficient": True,
        }

    for idx, raw in enumerate(raw_projects):
        if not isinstance(raw, dict):
            raise PipelineNpvError(f"projects[{idx}] 必须为 JSON 对象")

        # ① 必填字段缺失识别（缺失不报错，仅记为数据不足）
        missing_here = [
            field
            for field in REQUIRED_PROJECT_FIELDS
            if raw.get(field) is None
            or (isinstance(raw.get(field), str) and not raw.get(field).strip())
        ]

        # ② 已提供字段的类型与取值校验（非法即用法错误）
        name = raw.get("name")
        if "name" not in missing_here and not isinstance(name, str):
            raise PipelineNpvError(f"projects[{idx}].name 必须为字符串")
        source = raw.get("source")
        if "source" not in missing_here and not isinstance(source, str):
            raise PipelineNpvError(
                f"projects[{idx}].source 必须为字符串（参数来源，如年报页码）"
            )

        peak_revenue = raw.get("peak_revenue")
        if "peak_revenue" not in missing_here and not _is_number(peak_revenue):
            raise PipelineNpvError(f"projects[{idx}].peak_revenue 必须为数值")

        launch_year = raw.get("launch_year")
        if "launch_year" not in missing_here:
            if not isinstance(launch_year, int) or isinstance(launch_year, bool):
                raise PipelineNpvError(
                    f"projects[{idx}].launch_year 必须为整数年份"
                )
            if launch_year - as_of_year < 0:
                raise PipelineNpvError(
                    f"projects[{idx}].launch_year={launch_year} 早于基准年 "
                    f"{as_of_year}（折现期数不得为负）"
                )

        probability = raw.get("probability")
        if "probability" not in missing_here:
            if not _is_number(probability):
                raise PipelineNpvError(f"projects[{idx}].probability 必须为数值")
            if not 0.0 <= probability <= 1.0:
                raise PipelineNpvError(
                    f"projects[{idx}].probability={probability} 越界（须在 [0,1]）"
                )

        # ③ cost 是唯一允许的缺省项：缺省=0 且必须透明回显
        cost = raw.get("cost")
        if cost is None:
            cost = 0.0
            defaults_applied.append(f"projects[{idx}].cost=0")
        elif not _is_number(cost):
            raise PipelineNpvError(f"projects[{idx}].cost 必须为数值")

        missing.extend(f"projects[{idx}].{field}" for field in missing_here)
        years_to_launch = (
            launch_year - as_of_year if isinstance(launch_year, int) else None
        )
        projects.append(
            {
                "name": name,
                "launch_year": launch_year,
                "years_to_launch": years_to_launch,
                "probability": probability,
                "peak_revenue": peak_revenue,
                "cost": cost,
                "pv_peak": None,
                "pv_cost": None,
                "npv": None,
                "source": source,
            }
        )

    return {
        "projects": projects,
        "missing": missing,
        "defaults_applied": defaults_applied,
        "data_insufficient": bool(missing),
    }


def compute_pipeline_npv(
    projects: List[Dict[str, Any]], discount_rate: float, as_of_year: int
) -> Dict[str, Any]:
    """计算各项目 NPV 与合计（单期峰值现金流折现 + 概率线性调整）。

    公式（P3-8 方案 §2.2，写死）::

        n_i         = launch_year_i - as_of_year
        PV_peak_i   = peak_revenue_i / (1 + r) ** n_i
        PV_cost_i   = cost_i / (1 + r) ** n_i
        NPV_i       = probability_i * PV_peak_i - PV_cost_i
        pipeline_npv = Σ NPV_i

    Args:
        projects: 已校验的项目参数字典列表。
        discount_rate: 折现率（小数）。
        as_of_year: 基准年份。

    Returns:
        {"projects": [含 pv_peak / pv_cost / npv 的条目...],
         "pipeline_npv": 合计 NPV}。

    Raises:
        PipelineNpvError: 概率越界或折现期数为负（防御性校验）。
    """
    computed: List[Dict[str, Any]] = []
    total = 0.0

    for entry in projects:
        label = entry.get("name")
        launch_year = entry.get("launch_year")
        probability = entry.get("probability")

        if not isinstance(launch_year, int) or isinstance(launch_year, bool):
            raise PipelineNpvError(f"项目「{label}」的 launch_year 必须为整数年份")
        years_to_launch = launch_year - as_of_year
        if years_to_launch < 0:
            raise PipelineNpvError(
                f"项目「{label}」的折现期数为负（launch_year={launch_year}）"
            )
        if not _is_number(probability) or not 0.0 <= probability <= 1.0:
            raise PipelineNpvError(f"项目「{label}」的 probability 越界（须在 [0,1]）")

        # 折现因子：负期数已排除，正期数与 0 期（当年商业化）均合法
        factor = (1 + discount_rate) ** years_to_launch
        pv_peak = entry["peak_revenue"] / factor
        pv_cost = entry["cost"] / factor
        npv = probability * pv_peak - pv_cost

        item = dict(entry)
        item.update(
            {
                "years_to_launch": years_to_launch,
                "pv_peak": pv_peak,
                "pv_cost": pv_cost,
                "npv": npv,
            }
        )
        computed.append(item)
        total += npv

    return {"projects": computed, "pipeline_npv": total}


def build_sensitivity(
    projects: List[Dict[str, Any]],
    discount_rate: float,
    as_of_year: int,
    spec: str,
) -> Dict[str, Any]:
    """构建 3×3 敏感性网格（折现率 × 概率绝对步长）。

    概率按**绝对步长**逐项目平移，越界者截断至 [0,1] 并在该格标注 clipped=True
    （唯一允许的截断，且必须透明标注）；折现率网格越界（下限 ≤ 0 或上限 > 1.0）
    视为用法错误。

    Args:
        projects: 已校验的项目参数字典列表。
        discount_rate: 基准折现率。
        as_of_year: 基准年份。
        spec: `--sensitivity` 规格字符串。

    Returns:
        {"spec": {...}, "grid": [...], "npv_low": float, "npv_high": float,
         "base": float}。

    Raises:
        PipelineNpvError: 规格非法或折现率网格越界（下限 ≤ 0 / 上限 > 1.0）。
    """
    step_r, step_p = parse_sensitivity_spec(spec)
    if discount_rate - step_r <= 0:
        raise PipelineNpvError(
            f"--sensitivity 折现率下限 {discount_rate - step_r} ≤ 0（步长过大）"
        )
    if discount_rate + step_r > MAX_DISCOUNT_RATE:
        raise PipelineNpvError(
            f"--sensitivity 折现率上限 {discount_rate + step_r} 超出 "
            f"{MAX_DISCOUNT_RATE}（步长过大）"
        )

    grid: List[Dict[str, Any]] = []
    for rate in (discount_rate - step_r, discount_rate, discount_rate + step_r):
        for shift in (-step_p, 0.0, step_p):
            shifted: List[Dict[str, Any]] = []
            clipped = False
            for entry in projects:
                probability = entry["probability"] + shift
                if probability < 0.0 or probability > 1.0:
                    clipped = True
                    probability = min(1.0, max(0.0, probability))
                item = dict(entry)
                item["probability"] = probability
                shifted.append(item)
            cell_npv = compute_pipeline_npv(shifted, rate, as_of_year)["pipeline_npv"]
            grid.append(
                {
                    "discount_rate": rate,
                    "probability_shift": shift,
                    "pipeline_npv": cell_npv,
                    "clipped": clipped,
                }
            )

    values = [cell["pipeline_npv"] for cell in grid]
    return {
        "spec": {"discount_rate_step": step_r, "probability_step": step_p},
        "grid": grid,
        "npv_low": min(values),
        "npv_high": max(values),
        "base": compute_pipeline_npv(projects, discount_rate, as_of_year)["pipeline_npv"],
    }


def run_pipeline_npv(
    projects_source: str,
    discount_rate: float,
    currency: str,
    as_of_year: Optional[int] = None,
    sensitivity_spec: Optional[str] = None,
    from_scan_path: Optional[str] = None,
) -> Dict[str, Any]:
    """执行 pipeline-npv 全流程，返回输出 JSON 契约。

    Args:
        projects_source: `--projects`（文件路径或 `-`）。
        discount_rate: 折现率（无默认值）。
        currency: 币种（无默认值，不换算）。
        as_of_year: 基准年份；缺省取系统当前年份并回显。
        sensitivity_spec: `--sensitivity` 规格；缺省则 sensitivity=None。
        from_scan_path: `--from-scan` 文件；缺省则 project_candidates=[]。

    Returns:
        与《P3-8 开发方案与计划》§3.3 一致的输出字典。

    Raises:
        PipelineNpvError: 一切用法错误（对应退出码 2）。
    """
    if not math.isfinite(discount_rate) or discount_rate <= -1:
        raise PipelineNpvError("--discount-rate 必须为大于 -1 的实数（如 0.10）")
    # 上限仅拦量纲误用（如把 10% 写成 10），不限制任何现实合理的折现率
    if discount_rate > MAX_DISCOUNT_RATE:
        raise PipelineNpvError(
            f"--discount-rate={discount_rate} 超出上限 {MAX_DISCOUNT_RATE}"
            "（须以小数给出，如 0.10 表示 10%）"
        )
    if currency not in SUPPORTED_CURRENCIES:
        raise PipelineNpvError(
            f"--currency 仅支持 {'/'.join(SUPPORTED_CURRENCIES)}（本工具不换算）"
        )

    resolved_year = as_of_year if as_of_year is not None else datetime.now().year

    payload = load_projects(projects_source)
    # 币种冲突：文件内 currency 与 CLI --currency 必须一致（不得静默取其一）
    file_currency = payload.get("currency")
    if isinstance(file_currency, str) and file_currency.strip():
        if file_currency.strip().upper() != currency.upper():
            raise PipelineNpvError(
                f"币种冲突：--projects 内 currency={file_currency.strip()} 与 "
                f"--currency={currency} 不一致（本工具不换算）"
            )

    # 基准年冲突：文件内 as_of_year 不得被静默忽略（与 CLI 基准年必须一致）
    file_year = payload.get("as_of_year")
    if file_year is not None:
        if not isinstance(file_year, int) or isinstance(file_year, bool):
            raise PipelineNpvError("--projects 内 as_of_year 必须为整数年份")
        if file_year != resolved_year:
            raise PipelineNpvError(
                f"基准年冲突：--projects 内 as_of_year={file_year} 与本次基准年 "
                f"{resolved_year} 不一致（如确需该基准年，请显式传 "
                f"--as-of-year {file_year}）"
            )

    parsed = parse_projects(payload, resolved_year)
    result: Dict[str, Any] = {
        "command": "pipeline-npv",
        "as_of_year": resolved_year,
        "discount_rate": discount_rate,
        "currency": currency,
        "data_insufficient": parsed["data_insufficient"],
        "missing": parsed["missing"],
        "defaults_applied": parsed["defaults_applied"],
        "projects": parsed["projects"],
        "pipeline_npv": None,
        "sensitivity": None,
        "project_candidates": load_project_candidates(from_scan_path)
        if from_scan_path
        else [],
    }

    # 存在缺项时**不计算任何数值**（合计与逐项目 NPV 均为 null），避免部分数值被误用
    if not parsed["data_insufficient"]:
        computed = compute_pipeline_npv(
            parsed["projects"], discount_rate, resolved_year
        )
        result["projects"] = computed["projects"]
        result["pipeline_npv"] = computed["pipeline_npv"]
        if sensitivity_spec:
            result["sensitivity"] = build_sensitivity(
                parsed["projects"], discount_rate, resolved_year, sensitivity_spec
            )
    return result


def _format_scalar(value: Any) -> str:
    """把人读摘要中的标量格式化为文本（缺值统一为 `null`，与 JSON 口径一致）。

    Args:
        value: 待格式化的值。

    Returns:
        数值的字符串形式；None 返回 "null"。
    """
    return "null" if value is None else str(value)


def _print_pipeline_summary(result: Dict[str, Any]) -> None:
    """打印 pipeline-npv 的人读摘要（非 JSON 模式）。

    Args:
        result: run_pipeline_npv 的输出字典。
    """
    print(
        f"研发管线 NPV 粗算子 | 基准年: {result['as_of_year']} | "
        f"折现率: {result['discount_rate']} | 币种: {result['currency']}"
    )
    if result["data_insufficient"]:
        print(f"[数据不足] 缺失项: {', '.join(result['missing'])}")
        print("[数据不足] 合计 NPV: null（存在缺失项，工具不产生替代数值）")
    else:
        print(f"合计 NPV: {_format_scalar(result['pipeline_npv'])}")

    for entry in result["projects"]:
        print(
            f"  - {_format_scalar(entry['name'])} | "
            f"期数: {_format_scalar(entry['years_to_launch'])} | "
            f"概率: {_format_scalar(entry['probability'])} | "
            f"NPV: {_format_scalar(entry['npv'])}"
        )
    if result["defaults_applied"]:
        print(f"[缺省回显] {', '.join(result['defaults_applied'])}")

    sensitivity = result["sensitivity"]
    if sensitivity:
        print(
            f"敏感性: base={sensitivity['base']} | low={sensitivity['npv_low']} | "
            f"high={sensitivity['npv_high']}"
        )
    if result["project_candidates"]:
        count = len(result["project_candidates"])
        print(f"[scan 项目名候选] {count} 条（仅名称，不含数值）")


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
        description="在研重大项目扫描器（mid-trend-tech-screen 步骤 3-A）",
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

    p_npv = sub.add_parser(
        "pipeline-npv",
        help="研发管线 NPV 粗算子（参数全部由调用方提供，缺失即标注数据不足）",
    )
    p_npv.add_argument("--projects", required=True,
                       help="在研项目参数 JSON 文件路径；- 表示从 stdin 读取")
    p_npv.add_argument("--discount-rate", type=float, required=True,
                       help="折现率（小数，如 0.10）；无默认值")
    p_npv.add_argument("--currency", required=True,
                       choices=list(SUPPORTED_CURRENCIES),
                       help="币种（本工具不做汇率换算）")
    p_npv.add_argument("--as-of-year", type=int,
                       help="基准年份（缺省=系统当前年份）")
    p_npv.add_argument("--sensitivity",
                       help='敏感性绝对步长，形如 "r=0.01;p=0.10"')
    p_npv.add_argument("--from-scan",
                       help="scan --json 结果文件；仅提取项目名候选，不生成数值")
    p_npv.add_argument("--json", action="store_true", help="输出 JSON")
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

    if args.command == "pipeline-npv":
        try:
            result = run_pipeline_npv(
                projects_source=args.projects,
                discount_rate=args.discount_rate,
                currency=args.currency,
                as_of_year=args.as_of_year,
                sensitivity_spec=args.sensitivity,
                from_scan_path=args.from_scan,
            )
        except PipelineNpvError as exc:
            # 用法错误：错误信息写 stderr，退出码 2（stdout 不输出 JSON）
            print(f"[错误] {exc}", file=sys.stderr)
            return 2
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            _print_pipeline_summary(result)
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(_main())
