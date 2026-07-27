#!/usr/bin/env python3
"""测试股本推算方法"""

import akshare as ak

def test_share_calculation():
    """测试通过净资产和每股净资产推算股本"""
    code = '300750'
    df = ak.stock_financial_abstract(symbol=code)

    # 解析数据
    parsed = {}
    for _, row in df.iterrows():
        parsed[row['指标']] = row

    # 尝试不同年份
    years = ['20251231', '20211231', '20201231', '20191231', '20181231']

    print(f"测试股票: {code}")
    print("-" * 60)

    for year in years:
        # 获取净资产和每股净资产
        net_assets_key = '股东权益合计(净资产)'
        eps_net_key = '每股净资产'

        # 检查数据是否存在
        if year not in parsed.get(net_assets_key, {}) or year not in parsed.get(eps_net_key, {}):
            print(f"{year[:4]}年: 数据缺失")
            continue

        net_assets = parsed[net_assets_key][year]
        eps_net = parsed[eps_net_key][year]

        # 检查是否为有效数值
        try:
            net_assets = float(net_assets)
            eps_net = float(eps_net)
            if net_assets == 0 or eps_net == 0:
                print(f"{year[:4]}年: 数据为0")
                continue

            shares = net_assets / eps_net
            print(f"{year[:4]}年: 净资产={net_assets:.2e}, 每股净资产={eps_net:.2f}, 股本={shares:.0f}股")
        except (ValueError, TypeError) as e:
            print(f"{year[:4]}年: 数据转换失败 - {e}")

if __name__ == "__main__":
    test_share_calculation()