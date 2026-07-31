#!/usr/bin/env python3
"""
Morningstar 公允价值筛选工具

从 Morningstar 筛选器 API 抓取所有有公允价值估计的股票，
计算潜在涨幅，输出 Top 100。

================================================================================
软件功能
================================================================================

核心功能：
    1. 数据获取：
       - 从 Morningstar API 获取美股公允价值数据
       - 包含：公允价值估计、当前价格、星级评级、护城河等级、行业信息等
       - 支持分页获取（每页100条）

    2. 数据分析：
       - 计算潜在涨幅：（公允价值 - 当前价格）/ 当前价格 × 100%
       - 按潜在涨幅降序排序
       - 筛选低估股票（潜在涨幅 > 0）

    3. 结果输出：
       - 控制台输出：Top 100 低估股票表格
       - CSV 文件：完整数据（所有股票）
       - 统计摘要：低估/高估比例、平均涨幅、宽护城河低估数量

    4. 数据字段：
       - ticker: 股票代码
       - name: 公司名称
       - close_price: 当前价格
       - fair_value: 公允价值估计
       - upside_pct: 潜在涨幅（%）
       - star_rating: 星级评级（1-5星）
       - moat: 护城河等级（Wide/Narrow/None）
       - uncertainty: 公允价值不确定性
       - sector: 行业板块
       - industry: 细分行业

使用场景：
    - 快速筛选被 Morningstar 分析师认为低估的股票
    - 寻找具有宽护城河的低估股票
    - 获取 Morningstar 公允价值估计数据用于进一步分析

================================================================================
使用方法
================================================================================

命令行调用：
    # 运行筛选
    python tools/morningstar_fair_value.py

输出文件：
    data/morningstar_fair_value_{YYYYMMDD}.csv

输出内容：
    - 控制台：Top 100 潜在涨幅最高的股票
    - CSV 文件：所有股票完整数据（按潜在涨幅排序）
    - 统计摘要：低估/高估比例、平均涨幅等

依赖要求：
    - Python 3.6+
    - curl 命令（用于 API 调用）
    - 网络连接（访问 Morningstar API）

注意事项：
    - Morningstar API 可能有访问频率限制
    - 需要稳定的网络连接
    - 数据仅供参考，不构成投资建议

================================================================================
"""

import json
import subprocess
import time
import csv
import os
from datetime import datetime

API_BASE = (
    "https://lt.morningstar.com/api/rest.svc/klr5zyak8x/security/screener"
    "?page={page}&pageSize={page_size}"
    "&sortOrder=FairValueEstimate%20desc"
    "&outputType=json&version=1"
    "&languageId=en-US&currencyId=USD"
    "&universeIds=E0EXG%24XNAS%7CE0EXG%24XNYS"
    "&securityDataPoints=SecId%7CName%7CPriceCurrency%7CTenforeId%7CClosePrice"
    "%7CStarRatingM255%7CQuantitativeFairValue%7CFairValueEstimate"
    "%7CAssessmentOfFairValueUncertainty%7CEconomicMoat%7CIndustryName%7CSectorName"
    "&filters=FairValueEstimate:notnull"
)

PAGE_SIZE = 100
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data")


def fetch_page(page: int) -> dict:
    url = API_BASE.format(page=page, page_size=PAGE_SIZE)
    result = subprocess.run(
        ["curl", "-s", "-H", "User-Agent: Mozilla/5.0", url],
        capture_output=True, text=True, timeout=30,
    )
    return json.loads(result.stdout)


def extract_ticker(tenforeid: str) -> str:
    if not tenforeid:
        return ""
    parts = tenforeid.split(".")
    return parts[0] if len(parts) >= 3 else tenforeid


def main():
    print(f"\n{'='*80}")
    print(f"  Morningstar 公允价值筛选  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*80}\n")

    # 第一页获取总数
    print("  正在获取第 1 页...")
    data = fetch_page(1)
    total = data.get("total", 0)
    all_rows = data.get("rows", [])
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    print(f"  共 {total} 只股票，{total_pages} 页\n")

    # 抓取剩余页
    for page in range(2, total_pages + 1):
        if page % 10 == 0 or page == total_pages:
            print(f"  正在获取第 {page}/{total_pages} 页...")
        try:
            data = fetch_page(page)
            rows = data.get("rows", [])
            if not rows:
                break
            all_rows.extend(rows)
            time.sleep(0.3)
        except Exception as e:
            print(f"  ⚠️  第 {page} 页失败: {e}")
            time.sleep(1)

    print(f"\n  共获取 {len(all_rows)} 条记录")

    # 计算潜在涨幅
    stocks = []
    for row in all_rows:
        fair_value = row.get("FairValueEstimate")
        close_price = row.get("ClosePrice")
        if not fair_value or not close_price or close_price <= 0:
            continue

        ticker = extract_ticker(row.get("TenforeId", ""))
        upside = (fair_value - close_price) / close_price * 100

        stocks.append({
            "ticker": ticker,
            "name": row.get("Name", ""),
            "close_price": round(close_price, 2),
            "fair_value": round(fair_value, 2),
            "upside_pct": round(upside, 1),
            "star_rating": row.get("StarRatingM255", ""),
            "moat": row.get("EconomicMoat", ""),
            "uncertainty": row.get("AssessmentOfFairValueUncertainty", ""),
            "sector": row.get("SectorName", ""),
            "industry": row.get("IndustryName", ""),
        })

    # 按潜在涨幅排序
    stocks.sort(key=lambda x: x["upside_pct"], reverse=True)

    # 输出 Top 100
    print(f"\n{'='*80}")
    print(f"  潜在涨幅 Top 100")
    print(f"{'='*80}\n")
    print(f"  {'排名':>4} {'代码':<8} {'公司名':<35} {'现价':>10} {'公允价值':>10} {'潜在涨幅':>8} {'星级':>4} {'护城河':<8} {'行业':<20}")
    print(f"  {'-'*4} {'-'*8} {'-'*35} {'-'*10} {'-'*10} {'-'*8} {'-'*4} {'-'*8} {'-'*20}")

    for i, s in enumerate(stocks[:100], 1):
        print(
            f"  {i:>4} {s['ticker']:<8} {s['name'][:35]:<35} "
            f"${s['close_price']:>9,.2f} ${s['fair_value']:>9,.2f} "
            f"{s['upside_pct']:>+7.1f}% "
            f"{'★'*int(s['star_rating']) if s['star_rating'] else 'N/A':>4} "
            f"{s['moat']:<8} {s['industry'][:20]:<20}"
        )

    # 保存完整数据到 CSV
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    today = datetime.now().strftime("%Y%m%d")
    csv_path = os.path.join(OUTPUT_DIR, f"morningstar_fair_value_{today}.csv")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "rank", "ticker", "name", "close_price", "fair_value",
            "upside_pct", "star_rating", "moat", "uncertainty", "sector", "industry"
        ])
        writer.writeheader()
        for i, s in enumerate(stocks, 1):
            writer.writerow({"rank": i, **s})

    print(f"\n  完整数据已保存到: {csv_path}")
    print(f"  共 {len(stocks)} 只股票（按潜在涨幅排序）\n")

    # 统计摘要
    undervalued = [s for s in stocks if s["upside_pct"] > 0]
    overvalued = [s for s in stocks if s["upside_pct"] < 0]
    print(f"  📊 统计摘要:")
    print(f"     低估股票: {len(undervalued)} 只 ({len(undervalued)/len(stocks)*100:.0f}%)")
    print(f"     高估股票: {len(overvalued)} 只 ({len(overvalued)/len(stocks)*100:.0f}%)")
    if undervalued:
        avg_upside = sum(s["upside_pct"] for s in undervalued) / len(undervalued)
        print(f"     低估股票平均潜在涨幅: +{avg_upside:.1f}%")
    if stocks:
        wide_moat_undervalued = [s for s in stocks if s["moat"] == "Wide" and s["upside_pct"] > 0]
        print(f"     宽护城河+低估: {len(wide_moat_undervalued)} 只")


if __name__ == "__main__":
    main()
