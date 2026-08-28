#!/usr/bin/env python3
"""动量与技术面指标纯计算模块测试。

测试 tools/common/momentum.py 的各计算函数。所有测试均为纯计算，无网络依赖，
可在任意环境稳定运行（离线可全绿）。

测试范围:
  1. TestSma            — 简单移动平均（含窗口边界/None 处理）
  2. TestRsi            — Wilder 平滑 RSI（已知序列、极端情况）
  3. TestPctChange      — N 期涨跌幅
  4. TestPercentileRank — 同板块百分位
  5. TestAvgVolume      — 成交量均值
  6. TestTechCheck      — 技术面止损布尔项（与打分引擎 TechData 对齐）
  7. TestComputeMomentum— 汇总计算

运行方式:
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe -m pytest tests/common/test_momentum.py -v
    F:\\Anaconda3\\envs\\Python_3_12_3\\python.exe tests/common/test_momentum.py
"""

import math
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from tools.common import momentum


class TestSma(unittest.TestCase):
    """简单移动平均测试。"""

    def test_sma_basic(self) -> None:
        """1..10 的 3 日均线：第 3 点起为滚动均值。"""
        closes = [float(i) for i in range(1, 11)]
        out = momentum.sma(closes, 3)
        self.assertIsNone(out[0])
        self.assertIsNone(out[1])
        # (1+2+3)/3, (2+3+4)/3, ...
        self.assertEqual(out[2], 2.0)
        self.assertEqual(out[3], 3.0)
        self.assertEqual(out[9], 9.0)

    def test_sma_insufficient_data(self) -> None:
        """数据少于窗口时全为 None。"""
        out = momentum.sma([1.0, 2.0], 5)
        self.assertEqual(out, [None, None])

    def test_sma_empty(self) -> None:
        """空序列返回空列表；window<=0 返回同长 None。"""
        self.assertEqual(momentum.sma([], 3), [])
        self.assertEqual(momentum.sma([1.0, 2.0], 0), [None, None])

    def test_sma_converges_to_flat(self) -> None:
        """全相等序列的均线恒等于该值。"""
        closes = [3.0] * 100
        out = momentum.sma(closes, 20)
        self.assertEqual(out[-1], 3.0)


class TestRsi(unittest.TestCase):
    """Wilder RSI 测试。"""

    def test_rsi_all_gains_is_100(self) -> None:
        """全程上涨：RSI 应为 100。"""
        closes = [float(i) for i in range(1, 60)]
        self.assertEqual(momentum.rsi(closes, 14), 100.0)

    def test_rsi_all_losses_is_0(self) -> None:
        """全程下跌：RSI 应为 0。"""
        closes = [float(60 - i) for i in range(1, 60)]
        self.assertEqual(momentum.rsi(closes, 14), 0.0)

    def test_rsi_flat_is_100(self) -> None:
        """无涨跌（losses=0）：RSI=100。"""
        closes = [5.0] * 60
        self.assertEqual(momentum.rsi(closes, 14), 100.0)

    def test_rsi_insufficient_data(self) -> None:
        """样本不足返回 None。"""
        self.assertIsNone(momentum.rsi([1.0, 2.0, 3.0], 14))
        self.assertIsNone(momentum.rsi([1.0] * 15, 0))

    def test_rsi_known_alternating_sequence(self) -> None:
        """涨跌幅交替 1/-1 的对称序列：RSI 应约为 50。"""
        closes = [100.0]
        for i in range(1, 101):
            closes.append(closes[-1] + (1.0 if i % 2 == 1 else -1.0))
        r = momentum.rsi(closes, 14)
        self.assertIsNotNone(r)
        self.assertGreater(r, 45.0)
        self.assertLess(r, 55.0)


class TestPctChange(unittest.TestCase):
    """N 期涨跌幅测试。"""

    def test_pct_change_positive(self) -> None:
        """100 -> 125（5 期后）涨幅 25%。"""
        closes = [100.0, 100.0, 100.0, 100.0, 100.0, 125.0]
        self.assertAlmostEqual(momentum.pct_change(closes, 5), 25.0, places=6)

    def test_pct_change_negative(self) -> None:
        """200 -> 100 跌幅 50%。"""
        closes = [200.0, 150.0, 100.0]
        self.assertAlmostEqual(momentum.pct_change(closes, 2), -50.0, places=6)

    def test_pct_change_insufficient(self) -> None:
        """样本不足或基准为 0 返回 None。"""
        self.assertIsNone(momentum.pct_change([1.0, 2.0], 5))
        self.assertIsNone(momentum.pct_change([0.0, 5.0], 1))


class TestPercentileRank(unittest.TestCase):
    """同板块百分位测试。"""

    def test_percentile_rank_median(self) -> None:
        """板块涨跌幅 [-10,0,10]，own=0 应居第 2 位（含等于）→ 66.67。"""
        peers = [-10.0, 0.0, 10.0]
        rank = momentum.percentile_rank(peers, 0.0)
        self.assertAlmostEqual(rank, 2 / 3 * 100, places=6)

    def test_percentile_rank_top(self) -> None:
        """own 为板块最大涨幅 → 100。"""
        peers = [1.0, 2.0, 3.0, 9.0]
        self.assertEqual(momentum.percentile_rank(peers, 9.0), 100.0)

    def test_percentile_rank_empty(self) -> None:
        """空板块返回 None。"""
        self.assertIsNone(momentum.percentile_rank([], 5.0))


class TestAvgVolume(unittest.TestCase):
    """成交量均值测试。"""

    def test_avg_volume_basic(self) -> None:
        """近 3 期均值。"""
        self.assertEqual(momentum.avg_volume([1.0, 2.0, 3.0, 4.0], 3), 3.0)

    def test_avg_volume_ignores_none(self) -> None:
        """忽略 None 样本。"""
        self.assertEqual(momentum.avg_volume([1.0, None, 3.0], 10), 2.0)

    def test_avg_volume_all_none(self) -> None:
        """全 None 返回 None。"""
        self.assertIsNone(momentum.avg_volume([None, None], 5))


class TestTechCheck(unittest.TestCase):
    """技术面止损布尔项测试。"""

    def _make_closes(self, flat: float, up_count: int) -> list:
        """构造 flat 之后连续上涨 up_count 日的价格，接近平坦后再上翘。"""
        return [flat] * 220 + [flat * (1 + 0.005 * k) for k in range(1, up_count + 1)]

    def test_above_both_ma(self) -> None:
        """价格远高于 MA50/MA200 且未放量。"""
        closes = self._make_closes(100.0, 60)
        tech = momentum.tech_check(closes, [1.0] * len(closes))
        self.assertIs(tech["close_above_ma50"], True)
        self.assertIs(tech["close_above_ma200"], True)
        self.assertIs(tech["volume_above_1_5x"], False)

    def test_below_ma200_triggers_red(self) -> None:
        """价格跌破 200 日均线：close_above_ma200 为 False。"""
        closes = [100.0] * 220 + [80.0] * 5
        tech = momentum.tech_check(closes, [1.0] * len(closes))
        self.assertIs(tech["close_above_ma200"], False)
        self.assertIs(tech["close_above_ma50"], False)

    def test_volume_surge(self) -> None:
        """当日放量 2 倍 → volume_above_1_5x 为 True。"""
        closes = [100.0] * 220 + [105.0]
        volumes = [1.0] * 220 + [3.0]
        tech = momentum.tech_check(closes, volumes)
        self.assertIs(tech["volume_above_1_5x"], True)

    def test_insufficient_ma_returns_none(self) -> None:
        """200 日窗口数据不足时 close_above_ma200 为 None。"""
        tech = momentum.tech_check([1.0] * 30, [1.0] * 30)
        self.assertIsNone(tech["close_above_ma200"])
        self.assertEqual(
            set(tech.keys()),
            {"close_above_ma50", "close_above_ma200", "volume_above_1_5x"},
        )

    def test_insufficient_volume_returns_none(self) -> None:
        """成交量不足时 volume_above_1_5x 为 None。"""
        tech = momentum.tech_check([100.0] * 220, [1.0])
        self.assertIsNone(tech["volume_above_1_5x"])


class TestComputeMomentum(unittest.TestCase):
    """汇总计算测试。"""

    def test_compute_full_output(self) -> None:
        """提供完整序列与板块截面时的汇总字段齐全。"""
        closes = [float(i) for i in range(1, 260)]
        volumes = [1.0] * 259 + [1.0]
        peers = [20.0, 50.0, 200.0]  # own 250日涨幅≈... 应排最高
        res = momentum.compute_momentum(closes, volumes, peer_pcts=peers)
        self.assertIn("close", res)
        self.assertIn("ma50", res)
        self.assertIn("ma200", res)
        self.assertIn("rsi50", res)
        self.assertIsNotNone(res["return_250d_pct"])
        self.assertAlmostEqual(res["smr_percentile"], 100.0, places=6)
        self.assertEqual(set(res["tech"].keys()),
                         {"close_above_ma50", "close_above_ma200", "volume_above_1_5x"})

    def test_compute_without_peers(self) -> None:
        """无板块截面时 smr_percentile 为 None，不阻断。"""
        closes = [float(i) for i in range(1, 260)]
        res = momentum.compute_momentum(closes)
        self.assertIsNone(res["smr_percentile"])
        self.assertIsNotNone(res["return_250d_pct"])

    def test_compute_insufficient_data(self) -> None:
        """序列过短时不抛异常，关键字段为 None。"""
        res = momentum.compute_momentum([1.0, 2.0])
        self.assertIsNone(res["return_250d_pct"])
        self.assertIsNone(res["rsi50"])
        self.assertIsNone(res["ma200"])


def run_tests():
    """以 unittest 方式运行全部测试。"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    for cls in (TestSma, TestRsi, TestPctChange, TestPercentileRank,
                TestAvgVolume, TestTechCheck, TestComputeMomentum):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    run_tests()