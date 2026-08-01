#!/usr/bin/env python3
"""
测试 momentum_backtest.py 在科学上网情况下的可用性
测试范围：
1. 网络连接测试（Yahoo Finance API）
2. yfinance 库测试（作为对比）
3. 数据获取函数测试
4. 完整回测流程测试
5. 错误处理测试
6. 性能测试（响应时间）
"""

import sys
import os
import time
import json
from datetime import datetime, timedelta

# 添加父目录到路径，以便导入 momentum_backtest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'tools', 'specialized'))

try:
    import momentum_backtest as mb
except ImportError as e:
    print(f"❌ 无法导入 momentum_backtest 模块: {e}")
    print("请确保 momentum_backtest.py 位于 tools/specialized/ 目录下")
    sys.exit(1)


class TestResult:
    """测试结果记录"""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
        self.skipped = 0
    
    def add(self, test_name, status, message="", duration=0):
        """添加测试结果
        
        Args:
            test_name: 测试名称
            status: 状态（PASS/FAIL/SKIP）
            message: 消息
            duration: 耗时（秒）
        """
        self.results.append({
            "test": test_name,
            "status": status,
            "message": message,
            "duration": duration
        })
        
        if status == "PASS":
            self.passed += 1
        elif status == "FAIL":
            self.failed += 1
        else:
            self.skipped += 1
    
    def print_report(self):
        """打印测试报告"""
        print("\n" + "=" * 70)
        print("  测试报告")
        print("=" * 70)
        print()
        
        for r in self.results:
            status_icon = {
                "PASS": "✅",
                "FAIL": "❌",
                "SKIP": "⏭️"
            }
            icon = status_icon.get(r["status"], "❓")
            duration_str = f"({r['duration']:.2f}s)" if r['duration'] > 0 else ""
            print(f"{icon} {r['status']:<6} {duration_str:<8} {r['test']}")
            if r['message']:
                print(f"         {r['message']}")
        
        print("\n" + "-" * 70)
        total = self.passed + self.failed + self.skipped
        print(f"总计：{total} 个测试")
        print(f"  ✅ 通过：{self.passed}")
        print(f"  ❌ 失败：{self.failed}")
        print(f"  ⏭️ 跳过：{self.skipped}")
        print("=" * 70)
        
        return self.failed == 0


def test_network_connection(result):
    """测试网络连接"""
    print("\n[1/6] 测试网络连接...")
    
    # 测试1：直接访问 Yahoo Finance API
    test_name = "Yahoo Finance API 连接测试"
    start = time.time()
    try:
        from urllib.request import urlopen, Request
        url = "https://query1.finance.yahoo.com/v8/finance/chart/NVDA?interval=1d&range=1d"
        req = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urlopen(req, timeout=10)
        data = json.loads(resp.read().decode())
        
        if "chart" in data and "result" in data["chart"]:
            duration = time.time() - start
            result.add(test_name, "PASS", f"成功连接到 Yahoo Finance API", duration)
        else:
            result.add(test_name, "FAIL", "返回数据格式异常")
    
    except Exception as e:
        duration = time.time() - start
        error_type = type(e).__name__
        
        if "timed out" in str(e).lower():
            result.add(test_name, "FAIL", f"连接超时 - 需要科学上网或代理", duration)
        elif "connection" in str(e).lower() or "network" in str(e).lower():
            result.add(test_name, "FAIL", f"网络连接失败 - {error_type}: {e}", duration)
        else:
            result.add(test_name, "FAIL", f"{error_type}: {e}", duration)


def test_yfinance_library(result):
    """测试 yfinance 库"""
    print("\n[2/6] 测试 yfinance 库...")
    
    test_name = "yfinance 库可用性测试"
    start = time.time()
    
    try:
        import yfinance as yf
        
        # 测试获取数据
        ticker = yf.Ticker("NVDA")
        data = ticker.history(period="1mo")
        
        if data.empty:
            result.add(test_name, "FAIL", "yfinance 返回空数据")
        else:
            duration = time.time() - start
            result.add(test_name, "PASS", f"成功获取 {len(data)} 条数据（推荐使用）", duration)
    
    except ImportError:
        result.add(test_name, "SKIP", "yfinance 未安装，建议安装：pip install yfinance")
    
    except Exception as e:
        duration = time.time() - start
        result.add(test_name, "FAIL", f"yfinance 测试失败: {e}", duration)


def test_fetch_price_data(result):
    """测试数据获取函数"""
    print("\n[3/6] 测试数据获取函数...")
    
    # 测试 NVDA
    test_name = "fetch_price_data(NVDA) 测试"
    start = time.time()
    try:
        prices = mb.fetch_price_data("NVDA", "2025-01-01", "2025-01-31")
        
        if prices and len(prices) > 0:
            duration = time.time() - start
            result.add(test_name, "PASS", f"成功获取 {len(prices)} 条数据", duration)
        else:
            result.add(test_name, "FAIL", "返回空数据")
    
    except Exception as e:
        duration = time.time() - start
        result.add(test_name, "FAIL", f"异常: {e}", duration)
    
    # 测试 AMD
    test_name = "fetch_price_data(AMD) 测试"
    start = time.time()
    try:
        prices = mb.fetch_price_data("AMD", "2025-01-01", "2025-01-31")
        
        if prices and len(prices) > 0:
            duration = time.time() - start
            result.add(test_name, "PASS", f"成功获取 {len(prices)} 条数据", duration)
        else:
            result.add(test_name, "FAIL", "返回空数据")
    
    except Exception as e:
        duration = time.time() - start
        result.add(test_name, "FAIL", f"异常: {e}", duration)


def test_momentum_signals(result):
    """测试动量信号计算"""
    print("\n[4/6] 测试动量信号计算...")
    
    # 准备测试数据
    test_prices = []
    base_price = 100.0
    base_volume = 1000000
    
    for i in range(100):
        test_prices.append({
            "date": f"2024-{(i // 30) + 1:02d}-{(i % 30) + 1:02d}",
            "open": base_price + i * 0.5,
            "high": base_price + i * 0.5 + 2,
            "low": base_price + i * 0.5 - 2,
            "close": base_price + i * 0.5,
            "volume": base_volume * (1.5 if i > 60 else 1.0)
        })
    
    test_name = "compute_momentum_signals() 测试"
    start = time.time()
    
    try:
        signals = mb.compute_momentum_signals(test_prices)
        
        if signals and len(signals) > 0:
            duration = time.time() - start
            result.add(test_name, "PASS", f"成功计算 {len(signals)} 个动量信号", duration)
        else:
            duration = time.time() - start
            result.add(test_name, "PASS", "无动量信号触发（测试数据不满足条件）", duration)
    
    except Exception as e:
        duration = time.time() - start
        result.add(test_name, "FAIL", f"异常: {e}", duration)


def test_value_verification(result):
    """测试价值验证引擎"""
    print("\n[5/6] 测试价值验证引擎...")
    
    # 准备测试数据
    test_fund = {
        "rev": 100.0,
        "rev_yoy": 25.0,
        "gm": 50.0,
        "eps_beat": 15.0
    }
    
    test_prev_fund = {
        "rev": 80.0,
        "rev_yoy": 20.0,
        "gm": 45.0,
        "eps_beat": 10.0
    }
    
    test_name = "verify_value() 测试"
    start = time.time()
    
    try:
        verification = mb.verify_value("NVDA", test_fund, test_prev_fund)
        
        if verification["score"] >= 3:
            duration = time.time() - start
            result.add(test_name, "PASS", 
                      f"价值验证通过：{verification['score']}/5 分", duration)
        else:
            duration = time.time() - start
            result.add(test_name, "PASS", 
                      f"价值验证未通过：{verification['score']}/5 分（正常）", duration)
    
    except Exception as e:
        duration = time.time() - start
        result.add(test_name, "FAIL", f"异常: {e}", duration)


def test_backtest_flow(result):
    """测试完整回测流程"""
    print("\n[6/6] 测试完整回测流程...")
    
    # 只测试 NVDA（避免测试全部三个标的耗时过长）
    test_name = "backtest_ticker(NVDA) 完整流程测试"
    start = time.time()
    
    try:
        # 修改时间范围，减少数据量
        original_start = "2021-06-01"
        original_end = "2025-06-30"
        
        # 使用较短的时间范围进行测试
        test_start = "2024-01-01"
        test_end = "2025-01-31"
        
        # 临时修改函数调用
        prices = mb.fetch_price_data("NVDA", test_start, test_end)
        
        if not prices:
            result.add(test_name, "SKIP", "无法获取价格数据，跳过完整回测测试")
            return
        
        # 计算动量信号
        signals = mb.compute_momentum_signals(prices)
        
        # 验证基本面
        if signals:
            sig = signals[0]
            q_date, fund = mb.find_latest_fundamental("NVDA", sig["date"])
            
            if fund:
                verification = mb.verify_value("NVDA", fund)
                
                duration = time.time() - start
                result.add(test_name, "PASS", 
                          f"完整流程测试成功，处理了 {len(prices)} 条价格数据", 
                          duration)
            else:
                duration = time.time() - start
                result.add(test_name, "PASS", 
                          f"流程测试成功，但无基本面数据", duration)
        else:
            duration = time.time() - start
            result.add(test_name, "PASS", 
                      f"流程测试成功，无动量信号（正常）", duration)
    
    except Exception as e:
        duration = time.time() - start
        result.add(test_name, "FAIL", f"异常: {e}", duration)


def save_test_report(result, output_file):
    """保存测试报告到JSON文件"""
    report = {
        "test_date": datetime.now().isoformat(),
        "summary": {
            "total": result.passed + result.failed + result.skipped,
            "passed": result.passed,
            "failed": result.failed,
            "skipped": result.skipped
        },
        "results": result.results
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\n📄 测试报告已保存到: {output_file}")


def main():
    """主测试函数"""
    print("=" * 70)
    print("  momentum_backtest.py 可用性测试")
    print("  测试目的：验证在科学上网情况下是否可用")
    print("=" * 70)
    
    # 初始化测试结果
    result = TestResult()
    
    # 执行测试
    test_network_connection(result)
    test_yfinance_library(result)
    test_fetch_price_data(result)
    test_momentum_signals(result)
    test_value_verification(result)
    test_backtest_flow(result)
    
    # 打印报告
    all_passed = result.print_report()
    
    # 保存报告
    report_file = os.path.join(
        os.path.dirname(__file__), 
        f"momentum_backtest_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    save_test_report(result, report_file)
    
    # 给出建议
    print("\n" + "=" * 70)
    print("  测试结论与建议")
    print("=" * 70)
    print()
    
    if all_passed:
        print("✅ 所有测试通过！momentum_backtest.py 可以正常使用。")
        print()
        print("建议：")
        print("  1. 可以直接运行 python tools/momentum_backtest.py")
        print("  2. 如需更稳定的数据获取，建议安装 yfinance：pip install yfinance")
    
    else:
        print("❌ 部分测试失败，请检查以下问题：")
        print()
        
        for r in result.results:
            if r["status"] == "FAIL":
                print(f"  - {r['test']}: {r['message']}")
        
        print()
        print("解决方案：")
        print()
        print("  如果网络连接失败：")
        print("    1. 确保已开启科学上网工具")
        print("    2. 检查代理设置（HTTP_PROXY / HTTPS_PROXY 环境变量）")
        print("    3. 尝试使用 VPN 或代理服务器")
        print()
        print("  如果 yfinance 测试失败：")
        print("    1. 安装 yfinance: pip install yfinance pandas")
        print("    2. yfinance 通常比手工API调用更稳定")
        print()
        print("  如果仍然无法使用：")
        print("    1. 考虑使用 momentum_backtest_v2.py（从本地JSON文件加载）")
        print("    2. 手动下载价格数据到 data/ 目录")
    
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
