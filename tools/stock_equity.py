#!/usr/bin/env python3
"""股票股权结构数据获取工具.

支持获取指定A股的股权结构信息，包括：
1. 前十大股东（总股本口径）
2. 前十大流通股东（流通股本口径）
3. 股本结构历史变动
4. 公司基础信息
5. 从巨潮资讯网下载最新财报PDF（支持年报、半年报、季报）

数据来源：东方财富、巨潮资讯等（通过akshare接口）

Usage:
    # 获取指定股票的股权结构数据
    python tools/stock_equity.py --code 601899

    # 指定报告期
    python tools/stock_equity.py --code 601899 --date 20251231

    # 导出为Excel文件
    python tools/stock_equity.py --code 601899 --export

    # JSON格式输出
    python tools/stock_equity.py --code 601899 --json

    # 下载最新年报PDF
    python tools/stock_equity.py --code 601899 --download-report

    # 下载最新半年报PDF
    python tools/stock_equity.py --code 601899 --download-report --report-type semiannual

    # 下载最新季报PDF
    python tools/stock_equity.py --code 601899 --download-report --report-type quarterly

    # 指定财报保存目录
    python tools/stock_equity.py --code 601899 --download-report --report-dir ./reports

注意：
    - 仅支持A股股票代码
    - 数据来源于网页爬虫，可能存在更新延迟
    - 无法拆分H股内部持有人（如香港中央结算代理人）
    - 无自动股权穿透功能
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

import akshare as ak
import pandas as pd
import requests


class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理日期类型."""

    def default(self, obj):
        """处理无法序列化的对象类型.

        Args:
            obj: 要序列化的对象

        Returns:
            序列化后的值
        """
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        elif isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        return super().default(obj)


class StockEquityData:
    """股票股权结构数据获取类.

    Attributes:
        code: 股票代码（6位数字）
        report_date: 报告期（格式：YYYYMMDD）
        symbol_em: 东方财富接口格式代码（如：sh601899）
        exchange: 交易所简称（沪/深）
    """

    def __init__(self, code: str, report_date: Optional[str] = None):
        """初始化股权数据获取器.

        Args:
            code: 6位股票代码
            report_date: 报告期（格式：YYYYMMDD），默认使用最新报告期
        """
        self.code = code.strip()
        self.report_date = report_date
        self.exchange = self._determine_exchange()
        self.symbol_em = self._format_symbol_em()
        self.api_results: List[Dict] = []  # 记录API调用结果

    def _determine_exchange(self) -> str:
        """根据股票代码判断交易所.

        Returns:
            交易所简称：'沪' 或 '深'
        """
        if self.code.startswith('6'):
            return '沪'
        elif self.code.startswith(('0', '3')):
            return '深'
        else:
            raise ValueError(f"无法识别的股票代码格式: {self.code}")

    def _format_symbol_em(self) -> str:
        """格式化为东方财富接口所需的股票代码格式.

        Returns:
            东方财富格式的股票代码（如：sh601899）
        """
        prefix = 'sh' if self.exchange == '沪' else 'sz'
        return f"{prefix}{self.code}"

    def _safe_api_call(self, func, api_name: str) -> Optional[pd.DataFrame]:
        """安全的API调用封装.

        Args:
            func: API调用函数
            api_name: API接口名称

        Returns:
            成功返回DataFrame，失败返回None
        """
        try:
            result = func()
            self.api_results.append({
                'api_name': api_name,
                'status': '成功',
                'rows': len(result) if isinstance(result, pd.DataFrame) else 0
            })
            return result
        except Exception as e:
            self.api_results.append({
                'api_name': api_name,
                'status': '失败',
                'error': str(e)
            })
            return None

    def get_top10_holders(self) -> Dict:
        """获取前十大股东（总股本口径）.

        Returns:
            包含股东数据的字典，格式为：
            {
                'success': bool,
                'data': List[Dict],  # 股东数据列表
                'columns': List[str],  # 列名
                'api_name': str,
                'error': Optional[str]
            }
        """
        # 如果没有指定报告期，尝试获取最新数据
        if self.report_date:
            api_name = f"ak.stock_gdfx_top_10_em(symbol='{self.symbol_em}', date='{self.report_date}')"
            df = self._safe_api_call(
                lambda: ak.stock_gdfx_top_10_em(symbol=self.symbol_em, date=self.report_date),
                api_name
            )
        else:
            # 不指定日期，获取最新数据
            api_name = f"ak.stock_gdfx_top_10_em(symbol='{self.symbol_em}')"
            df = self._safe_api_call(
                lambda: ak.stock_gdfx_top_10_em(symbol=self.symbol_em),
                api_name
            )

        if df is not None and not df.empty:
            # 转换为字典列表
            records = df.to_dict('records')
            # 格式化数值字段
            for record in records:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None
                    elif isinstance(value, (int, float)):
                        record[key] = value

            return {
                'success': True,
                'data': records,
                'columns': list(df.columns),
                'api_name': api_name,
                'count': len(records)
            }
        else:
            return {
                'success': False,
                'data': [],
                'columns': [],
                'api_name': api_name,
                'error': '数据为空或获取失败'
            }

    def get_top10_free_holders(self) -> Dict:
        """获取前十大流通股东（流通股本口径）.

        Returns:
            包含流通股东数据的字典
        """
        # 如果没有指定报告期，尝试获取最新数据
        if self.report_date:
            api_name = f"ak.stock_gdfx_free_top_10_em(symbol='{self.symbol_em}', date='{self.report_date}')"
            df = self._safe_api_call(
                lambda: ak.stock_gdfx_free_top_10_em(symbol=self.symbol_em, date=self.report_date),
                api_name
            )
        else:
            # 不指定日期，获取最新数据
            api_name = f"ak.stock_gdfx_free_top_10_em(symbol='{self.symbol_em}')"
            df = self._safe_api_call(
                lambda: ak.stock_gdfx_free_top_10_em(symbol=self.symbol_em),
                api_name
            )

        if df is not None and not df.empty:
            records = df.to_dict('records')
            for record in records:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None
                    elif isinstance(value, (int, float)):
                        record[key] = value

            return {
                'success': True,
                'data': records,
                'columns': list(df.columns),
                'api_name': api_name,
                'count': len(records)
            }
        else:
            return {
                'success': False,
                'data': [],
                'columns': [],
                'api_name': api_name,
                'error': '数据为空或获取失败'
            }

    def get_share_structure(self) -> Dict:
        """获取股本结构历史变动.

        Returns:
            包含股本变动数据的字典
        """
        api_name = f"ak.stock_share_change_cninfo(symbol='{self.code}')"

        df = self._safe_api_call(
            lambda: ak.stock_share_change_cninfo(symbol=self.code),
            api_name
        )

        if df is not None and not df.empty:
            records = df.to_dict('records')
            for record in records:
                for key, value in record.items():
                    if pd.isna(value):
                        record[key] = None
                    elif isinstance(value, (int, float)):
                        record[key] = value

            return {
                'success': True,
                'data': records,
                'columns': list(df.columns),
                'api_name': api_name,
                'count': len(records)
            }
        else:
            return {
                'success': False,
                'data': [],
                'columns': [],
                'api_name': api_name,
                'error': '数据为空或获取失败'
            }

    def get_company_info(self) -> Dict:
        """获取公司基础信息.

        Returns:
            包含公司信息的字典
        """
        api_name = f"ak.stock_profile_cninfo(symbol='{self.code}')"

        df = self._safe_api_call(
            lambda: ak.stock_profile_cninfo(symbol=self.code),
            api_name
        )

        if df is not None and not df.empty:
            # 转置数据，将字段名作为键
            info_dict = {}
            for col in df.columns:
                value = df[col].iloc[0] if len(df) > 0 else None
                info_dict[col] = value if not pd.isna(value) else None

            return {
                'success': True,
                'data': info_dict,
                'api_name': api_name
            }
        else:
            return {
                'success': False,
                'data': {},
                'api_name': api_name,
                'error': '数据为空或获取失败'
            }

    def get_all_equity_data(self) -> Dict:
        """获取所有股权结构数据.

        Returns:
            包含所有数据的字典，格式为：
            {
                'code': str,
                'exchange': str,
                'report_date': str,
                'top10_holders': Dict,
                'top10_free_holders': Dict,
                'share_structure': Dict,
                'company_info': Dict,
                'api_summary': List[Dict]
            }
        """
        return {
            'code': self.code,
            'exchange': self.exchange,
            'report_date': self.report_date,
            'symbol_em': self.symbol_em,
            'top10_holders': self.get_top10_holders(),
            'top10_free_holders': self.get_top10_free_holders(),
            'share_structure': self.get_share_structure(),
            'company_info': self.get_company_info(),
            'api_summary': self.api_results
        }

    def export_to_excel(self, output_path: Optional[str] = None) -> str:
        """导出数据到Excel文件.

        Args:
            output_path: 输出文件路径，默认为当前目录下以股票代码命名

        Returns:
            导出的文件路径
        """
        if output_path is None:
            output_path = f"{self.code}_股权结构.xlsx"

        data = self.get_all_equity_data()

        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            # 前十大股东
            if data['top10_holders']['success']:
                df = pd.DataFrame(data['top10_holders']['data'])
                df.to_excel(writer, sheet_name='前十大股东', index=False)

            # 前十大流通股东
            if data['top10_free_holders']['success']:
                df = pd.DataFrame(data['top10_free_holders']['data'])
                df.to_excel(writer, sheet_name='前十大流通股东', index=False)

            # 股本变动
            if data['share_structure']['success']:
                df = pd.DataFrame(data['share_structure']['data'])
                df.to_excel(writer, sheet_name='股本变动', index=False)

            # 公司信息
            if data['company_info']['success']:
                df = pd.DataFrame([data['company_info']['data']])
                df.to_excel(writer, sheet_name='公司信息', index=False)

        return output_path

    def get_latest_report_url(self, report_type: str = 'annual') -> Optional[Dict[str, str]]:
        """获取最新财报PDF链接和年份.

        从巨潮资讯网查询上市公司最新财报信息.

        Args:
            report_type: 报告类型 ('annual'-年报, 'semiannual'-半年报, 'quarterly'-季报)

        Returns:
            {"year": "2025", "url": "https://...", "title": "...", "report_type": "..."} 或 None
        """
        api_name = f"巨潮资讯财报查询接口(股票代码: {self.code}, 报告类型: {report_type})"

        try:
            # 使用巨潮资讯网全文搜索API
            api_url = "https://www.cninfo.com.cn/new/fulltextSearch/full"

            # 搜索关键词：使用股票代码
            search_key = self.code

            # API参数格式
            params = {
                "searchkey": search_key,
                "sdate": "",
                "edate": "",
                "isfulltext": "false",
                "sortName": "nothing",
                "sortType": "desc",
                "pageNum": 1,
                "pageSize": 50  # 增加页面大小，提高找到报告的概率
            }

            # 请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36",
                "Referer": "https://www.cninfo.com.cn/new/disclosure"
            }

            resp = requests.get(api_url, params=params, headers=headers, timeout=25)
            data = resp.json()
            ann_list = data.get("announcements", [])
            total_count = data.get("totalAnnouncement", 0)

            if not ann_list:
                self.api_results.append({
                    'api_name': api_name,
                    'status': '失败',
                    'error': '未找到任何公告'
                })
                return None

            # 查找最新财报（根据报告类型过滤）
            for ann in ann_list:
                title = ann.get("announcementTitle", "")
                sec_code = ann.get("secCode", "")

                # 清理HTML标签
                title_clean = re.sub(r'<[^>]+>', '', title)

                # 确保是目标股票的公告
                if sec_code != self.code:
                    continue

                # 检查是否为指定类型的报告
                is_target_report = False

                if report_type == 'annual':
                    # 年报：包含"年度报告"，排除摘要、半年报、季报
                    is_target_report = ("年度报告" in title_clean and
                                        "摘要" not in title_clean and
                                        "半年度" not in title_clean and
                                        "季度" not in title_clean)
                elif report_type == 'semiannual':
                    # 半年报：包含"半年度"，排除摘要
                    # 注意：有些公司可能用"半年度报告"，有些可能用"半年度"
                    is_target_report = ("半年度" in title_clean and
                                        "摘要" not in title_clean and
                                        "季度" not in title_clean)
                elif report_type == 'quarterly':
                    # 季报：包含"季度"，排除摘要
                    is_target_report = ("季度" in title_clean and
                                        "摘要" not in title_clean and
                                        "半年度" not in title_clean)

                if is_target_report:
                    # 提取年份和季度信息
                    year_match = re.search(r'(\d{4})', title_clean)
                    year = year_match.group(1) if year_match else "未知"

                    # 提取季度信息（用于季报）
                    quarter = ""
                    if report_type == 'quarterly':
                        quarter_match = re.search(r'第([一二三四])季度', title_clean)
                        if quarter_match:
                            quarter_map = {'一': 'Q1', '二': 'Q2', '三': 'Q3', '四': 'Q4'}
                            quarter = quarter_map.get(quarter_match.group(1), '')

                    adjunct_url = ann.get("adjunctUrl", "")
                    pdf_link = f"https://static.cninfo.com.cn/{adjunct_url}"

                    # 记录成功
                    self.api_results.append({
                        'api_name': api_name,
                        'status': '成功',
                        'rows': 1
                    })

                    return {
                        "year": year,
                        "quarter": quarter,
                        "url": pdf_link,
                        "title": title_clean,
                        "report_type": report_type
                    }

            # 所有公告都未匹配
            error_msg = f'未找到{self._get_report_type_name(report_type)}'
            self.api_results.append({
                'api_name': api_name,
                'status': '失败',
                'error': error_msg
            })
            return None

        except Exception as e:
            self.api_results.append({
                'api_name': api_name,
                'status': '失败',
                'error': str(e)
            })
            return None

    def _get_report_type_name(self, report_type: str) -> str:
        """获取报告类型的中文名称.

        Args:
            report_type: 报告类型代码

        Returns:
            报告类型中文名称
        """
        type_map = {
            'annual': '年度报告',
            'semiannual': '半年度报告',
            'quarterly': '季度报告'
        }
        return type_map.get(report_type, '报告')

    def get_latest_annual_report_url(self) -> Optional[Dict[str, str]]:
        """获取最新年报PDF链接和年份（兼容旧版本）.

        Returns:
            {"year": "2025", "url": "https://...", "title": "..."} 或 None
        """
        result = self.get_latest_report_url('annual')
        if result:
            # 移除report_type字段，保持兼容
            return {
                "year": result["year"],
                "url": result["url"],
                "title": result["title"]
            }
        return None

    def download_report(self, save_dir: Optional[str] = None,
                       report_type: str = 'annual') -> Optional[str]:
        """下载最新财报PDF文件.

        Args:
            save_dir: 保存目录，默认为当前目录下的 cninfo_reports 子目录
            report_type: 报告类型 ('annual'-年报, 'semiannual'-半年报, 'quarterly'-季报)

        Returns:
            下载的PDF文件路径，失败返回None
        """
        # 设置保存目录
        if save_dir is None:
            save_dir = "./cninfo_reports"
        os.makedirs(save_dir, exist_ok=True)

        # 查询最新财报
        report_info = self.get_latest_report_url(report_type)
        if not report_info:
            return None

        # 构造文件名
        year = report_info['year']
        quarter = report_info.get('quarter', '')

        if report_type == 'annual':
            report_name = '年报'
        elif report_type == 'semiannual':
            report_name = '半年报'
        elif report_type == 'quarterly':
            report_name = f'{quarter}季报' if quarter else '季报'
        else:
            report_name = '报告'

        pdf_filename = f"{self.code}_{year}{report_name}.pdf"
        pdf_path = os.path.join(save_dir, pdf_filename)

        # 检查是否已下载
        if os.path.exists(pdf_path):
            self.api_results.append({
                'api_name': f'财报已存在({pdf_path})',
                'status': '成功',
                'rows': 1
            })
            return pdf_path

        # 下载PDF
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36",
                "Referer": "https://www.cninfo.com.cn/new/disclosure"
            }

            resp = requests.get(report_info['url'], headers=headers, timeout=30)
            with open(pdf_path, "wb") as f:
                f.write(resp.content)

            # 记录成功
            self.api_results.append({
                'api_name': f'PDF下载({report_info["url"]})',
                'status': '成功',
                'rows': 1
            })

            time.sleep(1.2)  # 避免频繁请求
            return pdf_path

        except Exception as e:
            self.api_results.append({
                'api_name': f'PDF下载({report_info["url"]})',
                'status': '失败',
                'error': str(e)
            })
            return None


class CnInfoReportDownloader:
    """巨潮资讯网财报下载器.

    提供从巨潮资讯网下载上市公司财报PDF的功能（支持年报、半年报、季报）。

    Attributes:
        code: 股票代码（6位数字）
        save_dir: 报告保存目录
    """

    def __init__(self, code: str, save_dir: str = "./cninfo_reports"):
        """初始化财报下载器.

        Args:
            code: 6位股票代码
            save_dir: 报告保存目录
        """
        self.code = code.strip()
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.api_results: List[Dict] = []

    def download_latest_report(self, report_type: str = 'annual') -> Optional[str]:
        """下载最新财报PDF.

        Args:
            report_type: 报告类型 ('annual'-年报, 'semiannual'-半年报, 'quarterly'-季报)

        Returns:
            下载的PDF文件路径，失败返回None
        """
        equity = StockEquityData(self.code)
        pdf_path = equity.download_report(self.save_dir, report_type)
        self.api_results = equity.api_results
        return pdf_path

    def download_annual_report(self) -> Optional[str]:
        """下载最新年报PDF（兼容旧版本）.

        Returns:
            下载的PDF文件路径，失败返回None
        """
        return self.download_latest_report('annual')


def main():
    """命令行入口函数."""
    parser = argparse.ArgumentParser(
        description='获取A股股票股权结构数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取紫金矿业股权结构数据
  python tools/stock_equity.py --code 601899

  # 指定报告期
  python tools/stock_equity.py --code 601899 --date 20251231

  # 导出为Excel文件
  python tools/stock_equity.py --code 601899 --export

  # JSON格式输出
  python tools/stock_equity.py --code 601899 --json

  # 下载最新年报PDF
  python tools/stock_equity.py --code 601899 --download-report

  # 下载最新半年报PDF
  python tools/stock_equity.py --code 601899 --download-report --report-type semiannual

  # 下载最新季报PDF
  python tools/stock_equity.py --code 601899 --download-report --report-type quarterly
        """
    )

    parser.add_argument('--code', required=True, help='6位股票代码')
    parser.add_argument('--date', help='报告期（格式：YYYYMMDD），默认最新')
    parser.add_argument('--export', action='store_true', help='导出为Excel文件')
    parser.add_argument('--json', action='store_true', help='以JSON格式输出')
    parser.add_argument('--output', help='输出文件路径（配合--export使用）')
    parser.add_argument('--download-report', action='store_true',
                        help='下载最新财报PDF')
    parser.add_argument('--report-type', default='annual',
                        choices=['annual', 'semiannual', 'quarterly'],
                        help='报告类型：annual-年报, semiannual-半年报, quarterly-季报')
    parser.add_argument('--report-dir', default='./cninfo_reports',
                        help='财报保存目录（默认：./cninfo_reports）')

    args = parser.parse_args()

    try:
        # 下载财报PDF
        if args.download_report:
            # 获取报告类型中文名称
            report_type_names = {
                'annual': '年报',
                'semiannual': '半年报',
                'quarterly': '季报'
            }
            report_type_name = report_type_names.get(args.report_type, '年报')

            print(f"\n{'=' * 80}")
            print(f"  从巨潮资讯网下载最新{report_type_name}")
            print(f"  股票代码：{args.code}")
            print(f"  报告类型：{report_type_name}")
            print(f"{'=' * 80}")

            downloader = CnInfoReportDownloader(args.code, args.report_dir)
            pdf_path = downloader.download_latest_report(args.report_type)

            if pdf_path:
                print(f"\n✅ {report_type_name}下载成功：{pdf_path}")
                if os.path.exists(pdf_path):
                    file_size = os.path.getsize(pdf_path) / 1024  # KB
                    print(f"   文件大小：{file_size:.2f} KB")
            else:
                print(f"\n❌ {report_type_name}下载失败")
                # 打印API调用结果
                if downloader.api_results:
                    print("\nAPI调用统计：")
                    for result in downloader.api_results:
                        status = "✓" if result['status'] == '成功' else "✗"
                        print(f"  {status} {result['api_name']}: {result['status']}")
                        if 'error' in result:
                            print(f"     错误：{result['error']}")

            print(f"\n{'=' * 80}")
            return

        # 创建数据获取器
        equity = StockEquityData(args.code, args.date)

        if args.json:
            # JSON格式输出
            data = equity.get_all_equity_data()
            print(json.dumps(data, indent=2, ensure_ascii=False, cls=CustomJSONEncoder))
        elif args.export:
            # 导出Excel
            output_path = equity.export_to_excel(args.output)
            print(f"✅ 数据已导出至：{output_path}")
        else:
            # 默认输出
            print(f"\n{'=' * 80}")
            print(f"  股票代码：{equity.code} ({equity.exchange})")
            print(f"  报告期：{equity.report_date or '最新'}")
            print(f"{'=' * 80}")

            # 获取并显示数据
            print("\n【前十大股东】")
            top10 = equity.get_top10_holders()
            if top10['success']:
                print(f"共 {top10['count']} 条数据")
                for i, holder in enumerate(top10['data'][:5], 1):
                    name = holder.get('股东名称', 'N/A')
                    ratio = holder.get('占总股本持股比例', 'N/A')
                    print(f"  {i}. {name}: {ratio}")
            else:
                print("  获取失败")

            print("\n【前十大流通股东】")
            free10 = equity.get_top10_free_holders()
            if free10['success']:
                print(f"共 {free10['count']} 条数据")
                for i, holder in enumerate(free10['data'][:5], 1):
                    name = holder.get('股东名称', 'N/A')
                    ratio = holder.get('占流通股比例', 'N/A')
                    print(f"  {i}. {name}: {ratio}")
            else:
                print("  获取失败")

            print("\n【股本变动】")
            share = equity.get_share_structure()
            if share['success']:
                print(f"共 {share['count']} 条变动记录")
                for record in share['data'][:3]:
                    date = record.get('变动日期', 'N/A')
                    reason = record.get('变动原因', 'N/A')
                    total = record.get('总股本', 'N/A')
                    print(f"  {date}: {reason} - 总股本 {total}")
            else:
                print("  获取失败")

            print("\n【公司信息】")
            info = equity.get_company_info()
            if info['success']:
                company_data = info['data']
                name = company_data.get('公司名称', 'N/A')
                industry = company_data.get('行业', 'N/A')
                print(f"  公司名称：{name}")
                print(f"  所属行业：{industry}")
            else:
                print("  获取失败")

            # API调用统计
            print(f"\n{'=' * 80}")
            print("API调用统计：")
            for result in equity.api_results:
                status = "✓" if result['status'] == '成功' else "✗"
                print(f"  {status} {result['api_name']}: {result['status']}")
            print(f"{'=' * 80}")

    except Exception as e:
        print(f"❌ 错误：{e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()