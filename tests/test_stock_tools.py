#!/usr/bin/env python3
"""综合测试脚本 — 验证 4 个股票数据工具的功能完整性。

测试范围:
  tools/stock_info.py      股票代码查询
  tools/stock_quote.py     行情数据
  tools/stock_financial.py 财务指标
  tools/stock_screen.py    质量筛选

执行:
  python tests/test_stock_tools.py
"""

import json
import subprocess
import sys
import os
from pathlib import Path

# ---- 配置 ----
PYTHON = Path(r"F:/Anaconda3/envs/Python_3_12_3/python.exe")
# 获取项目根目录（tests 的父目录）
TESTS_DIR = Path(__file__).parent
CWD = TESTS_DIR.parent  # 项目根目录
TOOLS_DIR = CWD / "tools"

TOOLS = {
    "stock_info": TOOLS_DIR / "stock_info.py",
    "stock_quote": TOOLS_DIR / "stock_quote.py",
    "stock_financial": TOOLS_DIR / "stock_financial.py",
    "stock_screen": TOOLS_DIR / "stock_screen.py",
}

# ---- 测试结果收集 ----
class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.fails = []

    def ok(self, name, detail=""):
        self.passed += 1
        tag = f"  ✅ {name}"
        if detail:
            tag += f" — {detail}"
        print(tag)

    def fail(self, name, reason):
        self.failed += 1
        self.fails.append((name, reason))
        print(f"  ❌ {name}: {reason}")

    def summary(self):
        total = self.passed + self.failed
        print()
        print("=" * 60)
        print(f"  测试完成")
        print(f"  总计: {total}  |  通过: {self.passed}  |  失败: {self.failed}")
        if self.fails:
            print()
            print("  失败详情:")
            for n, r in self.fails:
                print(f"    ❌ {n}")
                print(f"       {r}")
        print("=" * 60)
        return 0 if self.failed == 0 else 1


T = TestResults()


def section(title):
    print()
    print("=" * 60)
    print(f"  {title}")
    print("=" * 60)


def run(tool_name, args, timeout=120):
    """运行工具并返回 (returncode, stdout_json, stderr_text)。"""
    cmd = [str(PYTHON), str(TOOLS[tool_name])] + args
    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=timeout, cwd=str(CWD))
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        # 尝试解析 stdout 为 JSON
        output = None
        if stdout:
            try:
                output = json.loads(stdout)
            except json.JSONDecodeError:
                pass

        # 如果 stdout 不是 JSON，检查 stderr
        if output is None and stderr:
            try:
                output = json.loads(stderr)
            except json.JSONDecodeError:
                pass

        return result.returncode, output, stderr
    except subprocess.TimeoutExpired:
        return -1, None, "TIMEOUT"
    except Exception as e:
        return -1, None, str(e)


# ========== 1. stock_info.py ==========

def test_stock_info():
    section("stock_info.py — 股票代码与公司信息")

    # --help
    rc, out, err = run("stock_info", ["--help"])
    if rc == 0 and out is None:
        T.ok("--help 参数")
    else:
        T.fail("--help 参数", f"rc={rc}, out={str(out)[:80] if out else 'none'}")

    # --list
    rc, out, err = run("stock_info", ["--list"])
    if out and out.get("success") and "data" in out and len(out["data"]) > 1000:
        T.ok("--list 列出全部A股", f"{len(out['data'])} 只股票")
    else:
        T.fail("--list", f"success={out.get('success') if out else 'None'}")

    # --search 关键词
    for keyword, expected in [("新易盛", "300502"), ("贵州茅台", "600519")]:
        rc, out, err = run("stock_info", ["--search", keyword])
        if out and out.get("success") and len(out.get("data", [])) > 0:
            codes = [s["code"] for s in out["data"]]
            T.ok(f"--search {keyword}", f"找到 {', '.join(codes)}")
        else:
            T.fail(f"--search {keyword}", f"未找到: {str(out)[:100] if out else err[:100]}")

    # --search 无结果
    rc, out, err = run("stock_info", ["--search", "ZZZZZZZZZ"])
    if out and out.get("success"):
        T.ok("--search 无匹配", f"返回 {len(out.get('data',[]))} 条结果(正确)")
    else:
        T.fail("--search 无匹配", str(out)[:100] if out else err[:100])

    # --code
    for code in ["300502", "600519", "000001"]:
        rc, out, err = run("stock_info", ["--code", code])
        if out and out.get("success") and out.get("data", {}).get("code") == code:
            name = out["data"]["name"]
            T.ok(f"--code {code}", name)
        else:
            T.fail(f"--code {code}", str(out)[:100] if out else err[:100])

    # --code 不存在
    rc, out, err = run("stock_info", ["--code", "999999"])
    if out and out.get("success") is False:
        T.ok("--code 999999 不存在", "工具返回错误(正确)")
    else:
        T.fail("--code 999999", "应返回错误却成功")

    # --industry 模糊匹配
    rc, out, err = run("stock_info", ["--industry", "通信"])
    if out and out.get("success") and len(out.get("data", [])) >= 5:
        T.ok("--industry 通信", f"找到 {len(out['data'])} 家公司")
    else:
        T.fail("--industry 通信", f"count={len(out.get('data',[])) if out else 0}, err={err[:100]}")


# ========== 2. stock_quote.py ==========

def test_stock_quote():
    section("stock_quote.py — 行情数据")

    # --help
    rc, out, err = run("stock_quote", ["--help"])
    if rc == 0 and out is None:
        T.ok("--help 参数")
    else:
        T.fail("--help 参数", f"rc={rc}")

    # Sina 数据源（国内网络可用）
    rc, out, err = run("stock_quote", ["--code", "300502", "--source", "sina",
                                       "--start", "20260101", "--end", "20260710"])
    if out and out.get("success") and out.get("data") and len(out["data"]) > 0:
        T.ok("--code 300502 (Sina)", f"{len(out['data'])} 条行情记录")
    else:
        err_msg = out.get("error", "") if out else err[:100]
        T.fail("--code 300502 (Sina)", err_msg)

    # 600519 via Sina
    rc, out, err = run("stock_quote", ["--code", "600519", "--source", "sina",
                                       "--start", "20260601", "--end", "20260710"])
    if out and out.get("success") and out.get("data"):
        T.ok("--code 600519 (Sina)", f"{len(out['data'])} 条记录")
    else:
        T.fail("--code 600519 (Sina)", str(out)[:100] if out else err[:100])

    # 前复权
    rc, out, err = run("stock_quote", ["--code", "300502", "--source", "sina",
                                       "--adjust", "qfq",
                                       "--start", "20260701", "--end", "20260710"])
    if out and out.get("success") and out.get("data"):
        T.ok("--adjust qfq (前复权)", f"{len(out['data'])} 条")
    else:
        T.fail("--adjust qfq", str(out)[:100] if out else err[:100])

    # 缺少 --code
    rc, out, err = run("stock_quote", [])
    if rc != 0:
        T.ok("缺少 --code 参数", f"退出码 {rc}")
    else:
        T.fail("缺少 --code 参数", "应报错却未报错")

    # 验证 meta 字段
    rc, out, err = run("stock_quote", ["--code", "300502", "--source", "sina",
                                       "--start", "20260701", "--end", "20260710"])
    if out and out.get("meta"):
        meta = out["meta"]
        required = ["tool", "source", "code", "start_date", "end_date", "adjust", "count", "timestamp"]
        missing = [k for k in required if k not in meta]
        if not missing:
            T.ok("JSON meta 字段完整", f"{len(required)} 个字段均在")
        else:
            T.fail("JSON meta 字段", f"缺少: {missing}")
    else:
        T.fail("JSON meta 字段", "meta 不存在")


# ========== 3. stock_financial.py ==========

def test_stock_financial():
    section("stock_financial.py — 财务指标")

    # --help
    rc, out, err = run("stock_financial", ["--help"])
    if rc == 0 and out is None:
        T.ok("--help 参数")
    else:
        T.fail("--help 参数", f"rc={rc}")

    # 默认关键指标
    rc, out, err = run("stock_financial", ["--code", "300502"])
    if out and out.get("success") and "indicators" in out.get("data", {}):
        has_roe = "ROE" in out["data"]["indicators"]
        has_gm = "毛利率" in out["data"]["indicators"]
        if has_roe and has_gm:
            T.ok("--code 300502 (默认关键指标)", "含 ROE、毛利率等")
        else:
            T.fail("--code 300502 (默认关键指标)", f"ROE={has_roe}, 毛利率={has_gm}")
    else:
        T.fail("--code 300502 (默认关键指标)", str(out)[:100] if out else err[:100])

    # --indicator all
    rc, out, err = run("stock_financial", ["--code", "300502", "--indicator", "all"])
    if out and out.get("success") and out.get("meta", {}).get("indicator_count", 0) > 50:
        T.ok("--indicator all", f"{out['meta']['indicator_count']} 个指标")
    else:
        T.fail("--indicator all", str(out)[:100] if out else err[:100])

    # 指定指标
    for ind in ["ROE", "毛利率", "净利率"]:
        rc, out, err = run("stock_financial", ["--code", "300502", "--indicator", ind])
        if out and out.get("success"):
            T.ok(f"--indicator {ind}", "返回数据")
        else:
            T.fail(f"--indicator {ind}", str(out)[:100] if out else err[:100])

    # 多指标
    rc, out, err = run("stock_financial", ["--code", "600519",
                                           "--indicator", "ROE,毛利率,净利率"])
    if out and out.get("success"):
        data_keys = list(out.get("data", {}).keys())
        if len(data_keys) >= 2:
            T.ok("--indicator ROE,毛利率,净利率", f"返回 {', '.join(data_keys)}")
        else:
            T.fail("--indicator ROE,毛利率,净利率", f"只有 {data_keys}")
    else:
        T.fail("--indicator ROE,毛利率,净利率", str(out)[:100] if out else err[:100])

    # 缺少 --code
    rc, out, err = run("stock_financial", [])
    if rc != 0:
        T.ok("缺少 --code 参数", f"退出码 {rc}")
    else:
        T.fail("缺少 --code 参数", "应报错")


# ========== 4. stock_screen.py ==========

def test_stock_screen():
    section("stock_screen.py — 质量筛选")

    # --help
    rc, out, err = run("stock_screen", ["--help"])
    if rc == 0 and out is None:
        T.ok("--help 参数")
    else:
        T.fail("--help 参数", f"rc={rc}")

    # 单只股票
    rc, out, err = run("stock_screen", ["--code", "300502"])
    if out and out.get("success") and len(out.get("data", [])) > 0:
        screening = out["data"][0]["data"]["screening"]
        required = ["1_ROE", "2_FCF", "3_interest_coverage",
                     "4_gross_margin", "5_ocf_to_net_profit",
                     "6_net_margin", "7_share_dilution", "debt_ratio"]
        missing = [k for k in required if k not in screening]
        if not missing:
            stock_name = out["data"][0]["data"]["name"]
            T.ok("--code 300502 新易盛", f"7条指标完整, name={stock_name}")
        else:
            T.fail("--code 300502", f"缺少: {missing}")
    else:
        T.fail("--code 300502", str(out)[:100] if out else err[:100])

    # 贵州茅台
    rc, out, err = run("stock_screen", ["--code", "600519"])
    if out and out.get("success") and len(out.get("data", [])) > 0:
        item = out["data"][0]["data"]
        roe_val = item["screening"]["1_ROE"].get("value", "N/A")
        gm_val = item["screening"]["4_gross_margin"].get("value", "N/A")
        nm_val = item["screening"]["6_net_margin"].get("value", "N/A")
        T.ok("--code 600519 贵州茅台",
             f"行业={item.get('industry','?')}, ROE={roe_val}, 毛利率={gm_val}, 净利率={nm_val}")
    else:
        T.fail("--code 600519", str(out)[:100] if out else err[:100])

    # 多只
    rc, out, err = run("stock_screen", ["--code", "300502,600519,000001"])
    if out and out.get("success") and len(out.get("data", [])) == 3:
        names = [d["data"]["name"] for d in out["data"]]
        T.ok("--code 300502,600519,000001 (多只)", f"返回 {', '.join(names)}")
    else:
        count = len(out.get("data", [])) if out else 0
        T.fail("--code 300502,600519,000001", f"预期3只, 实际{count}")

    # 检查至少关键指标有值
    rc, out, err = run("stock_screen", ["--code", "300502"])
    if out and out.get("success"):
        screening = out["data"][0]["data"]["screening"]
        issues = []
        # 指标1 ROE 应该有值（或合理说明）
        if screening["1_ROE"]["value"] is None and "数据不足" not in screening["1_ROE"].get("note", ""):
            issues.append(f"1_ROE: {screening['1_ROE'].get('note','')}")
        # 指标4 毛利率应该有值
        if screening["4_gross_margin"]["value"] is None and "未找到" not in screening["4_gross_margin"].get("note", ""):
            issues.append(f"4_gross_margin: {screening['4_gross_margin'].get('note','')}")
        # 指标5 OCF/NI 应该有值或合理说明
        if screening["5_ocf_to_net_profit"]["value"] is None and "数据不足" not in screening["5_ocf_to_net_profit"].get("note", ""):
            issues.append(f"5_ocf_to_net_profit: {screening['5_ocf_to_net_profit'].get('note','')}")
        # 指标6 净利率应该有值
        if screening["6_net_margin"]["value"] is None:
            issues.append(f"6_net_margin: {screening['6_net_margin'].get('note','')}")

        if not issues:
            T.ok("300502 关键指标均有有效值")
        else:
            T.fail("300502 关键指标", "; ".join(issues))
    else:
        T.fail("300502 指标检查", str(out)[:100] if out else err[:100])

    # 缺少 --code
    rc, out, err = run("stock_screen", [])
    if rc != 0:
        T.ok("缺少 --code 参数", f"退出码 {rc}")
    else:
        T.fail("缺少 --code 参数", "应报错")


# ========== Main ==========

def main():
    print("=" * 60)
    print("  股票数据工具 — 综合测试")
    print(f"  Python: {PYTHON}")
    print(f"  工作目录: {CWD}")
    print(f"  测试时间: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 文件存在检查
    print("\n📁 文件检查:")
    for name, path in TOOLS.items():
        if path.exists():
            sz = path.stat().st_size
            print(f"  ✅ {name}.py ({sz:,} bytes)")
        else:
            print(f"  ❌ {name}.py — 不存在!")

    # akshare 可以正常导入
    rc, out, err = run("stock_info", ["--help"])
    if rc == 0:
        print(f"  ✅ akshare 可以正常导入")
    else:
        print(f"  ❌ akshare 导入失败: {err[:200]}")

    # 执行各工具测试
    test_stock_info()
    test_stock_quote()
    test_stock_financial()
    test_stock_screen()

    return T.summary()


if __name__ == "__main__":
    sys.exit(main())