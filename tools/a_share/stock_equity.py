#!/usr/bin/env python3
"""A股股票股权结构数据获取工具.

支持获取指定A股的股权结构信息，包括：
1. 前十大股东（总股本口径）
2. 前十大流通股东（流通股本口径）
3. 股本结构历史变动
4. 公司基础信息
5. 从巨潮资讯网下载最新财报PDF（支持年报、半年报、季报）

数据来源：东方财富、巨潮资讯等（通过akshare接口）

Usage:
    # 获取指定股票的股权结构数据
    python tools/a_share/stock_equity.py --code 601899

    # 指定报告期
    python tools/a_share/stock_equity.py --code 601899 --date 20251231

    # 导出为Excel文件
    python tools/a_share/stock_equity.py --code 601899 --export

    # JSON格式输出
    python tools/a_share/stock_equity.py --code 601899 --json

    # 下载最新年报PDF
    python tools/a_share/stock_equity.py --code 601899 --download-report

    # 下载最新半年报PDF
    python tools/a_share/stock_equity.py --code 601899 --download-report --report-type semiannual

    # 下载最新季报PDF
    python tools/a_share/stock_equity.py --code 601899 --download-report --report-type quarterly

    # 指定财报保存目录
    python tools/a_share/stock_equity.py --code 601899 --download-report --report-dir ./reports

注意：
    - 仅支持A股股票代码
    - 数据来源于网页爬虫，可能存在更新延迟
    - 无法拆分H股内部持有人（如香港中央结算代理人）
    - 无自动股权穿透功能
"""

import argparse
import io
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

    def _http_get_with_retry(self, url: str, params: Optional[Dict] = None,
                             headers: Optional[Dict] = None,
                             timeout: int = 25, retries: int = 3) -> requests.Response:
        """带重试的 HTTP GET 请求.

        网络异常（连接失败/超时）与 5xx 服务端错误会自动重试（指数退避），
        4xx 客户端错误不重试（重试无意义）。重试耗尽后抛出最后一次异常.

        Args:
            url: 请求地址
            params: 查询参数
            headers: 请求头
            timeout: 单次请求超时（秒）
            retries: 最大尝试次数

        Returns:
            requests.Response 对象

        Raises:
            requests.RequestException: 重试耗尽后抛出
        """
        last_exc: Optional[requests.RequestException] = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=timeout)
                resp.raise_for_status()
                return resp
            except requests.RequestException as e:
                last_exc = e
                # 4xx 客户端错误不重试，直接抛出
                if isinstance(e, requests.HTTPError) and e.response is not None \
                        and e.response.status_code < 500:
                    raise
                if attempt < retries:
                    time.sleep(1.5 * attempt)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("HTTP 请求失败（未知错误）")

    def _fetch_cninfo_announcements(self, search_key: str) -> List[Dict]:
        """从巨潮资讯网获取公告列表.

        使用巨潮资讯网全文搜索API，按指定关键词检索公告.

        Args:
            search_key: 搜索关键词（股票代码或组合关键词）

        Returns:
            公告列表，失败返回空列表
        """
        api_name = f"巨潮资讯搜索接口(关键词: {search_key})"

        try:
            # 使用巨潮资讯网全文搜索API
            api_url = "https://www.cninfo.com.cn/new/fulltextSearch/full"

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

            resp = self._http_get_with_retry(api_url, params=params, headers=headers, timeout=25)
            data = resp.json()
            ann_list = data.get("announcements", []) or []

            self.api_results.append({
                'api_name': api_name,
                'status': '成功' if ann_list else '失败',
                'rows': len(ann_list)
            })

            return ann_list

        except Exception as e:
            self.api_results.append({
                'api_name': api_name,
                'status': '失败',
                'error': str(e)
            })
            return []

    def _is_full_report(self, title_clean: str) -> bool:
        """判断标题是否为完整版报告（非摘要、非简版、非英文版）.

        Args:
            title_clean: 清理后的标题文本

        Returns:
            True 表示是完整版报告
        """
        # 排除项：摘要、简版、英文版、自愿性披露公告、提示性公告（不含完整财报）
        exclude_keywords = [
            '摘要', '简版', '英文版', 'English',
            '自愿性披露', '自愿披露',
            '提示性', '披露提示', '更正', '补充'
        ]
        for keyword in exclude_keywords:
            if keyword in title_clean:
                return False
        return True

    def _get_min_full_report_size_kb(self, report_type: str) -> int:
        """获取指定报告类型"完整版"的最小文件大小阈值（单位：KB）.

        用于两处过滤：
        1. 搜索阶段：排除 adjunctSize 过小的摘要版/提示性公告
        2. 下载阶段：判断已缓存文件是否为完整版

        阈值依据（2026-08-17 实测，紫金矿业 601899，adjunctSize 单位 = KB）：
        - 年报完整版 15410~78054 KB，摘要版 309~784 KB
        - 半年报完整版 4328~9829 KB，摘要版 191~298 KB
        - 季报完整版 200~688 KB（季报本身即精简版，无独立摘要版）

        Args:
            report_type: 报告类型 ('annual'-年报, 'semiannual'-半年报, 'quarterly'-季报)

        Returns:
            最小完整版文件大小阈值（KB）
        """
        thresholds = {
            'annual': 1024,      # 年报完整版 > 1MB
            'semiannual': 1024,  # 半年报完整版 > 1MB
            'quarterly': 100,    # 季报完整版 > 100KB（实测最小约 200KB）
        }
        return thresholds.get(report_type, 1024)

    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """清理字符串中的文件名非法字符（Windows 保留字符及控制字符）.

        Args:
            name: 原始名称

        Returns:
            清理后的名称（可能为空字符串）
        """
        return re.sub(r'[\\/:*?"<>|\x00-\x1f]', '', name.strip())

    def _find_report_by_priority(
        self,
        ann_list: List[Dict],
        report_type: str,
        require_full: bool = True
    ) -> Optional[Dict[str, str]]:
        """按优先级查找报告.

        Args:
            ann_list: 公告列表
            report_type: 报告类型
            require_full: True=只找完整版，False=可接受摘要/简版

        Returns:
            匹配的报告信息字典或 None
        """
        candidates = []

        for ann in ann_list:
            title = ann.get("announcementTitle", "")
            sec_code = ann.get("secCode", "")

            # 清理HTML标签
            title_clean = re.sub(r'<[^>]+>', '', title)

            # 确保是目标股票的公告
            # secCode 可能是逗号分隔的多证券代码（联合公告场景），先拆分再匹配，
            # 避免硬比较把目标财报误判为"非本股票"而漏掉；空值则跳过（保守，防止误收无关公告）
            sec_codes = [c.strip() for c in sec_code.split(',') if c.strip()]
            if not sec_codes or self.code not in sec_codes:
                continue

            # 检查是否为指定类型的报告
            is_target_report = False

            if report_type == 'annual':
                # 年报：包含"年度报告"，排除半年报、季报
                is_target_report = (
                    "年度报告" in title_clean and
                    "半年度" not in title_clean and
                    "季度" not in title_clean
                )
            elif report_type == 'semiannual':
                # 半年报：包含"半年度"，排除季报
                is_target_report = (
                    "半年度" in title_clean and
                    "季度" not in title_clean
                )
            elif report_type == 'quarterly':
                # 季报：包含"季度"，排除半年度
                is_target_report = (
                    "季度" in title_clean and
                    "半年度" not in title_clean
                )

            if not is_target_report:
                continue

            # 如果需要完整版，检查是否为完整版
            if require_full:
                # 标题排除：摘要、简版、英文版、提示性等
                if not self._is_full_report(title_clean):
                    continue
                # 文件大小排除：adjunctSize 单位为 KB（1 单位 = 1024 字节，已实测核实）
                # 阈值按报告类型区分：年报/半年报完整版 > 1MB，季报完整版 > 100KB（实测最小约 200KB）
                adjunct_size = ann.get("adjunctSize", 0)
                min_full_kb = self._get_min_full_report_size_kb(report_type)
                if isinstance(adjunct_size, (int, float)) and 0 < adjunct_size < min_full_kb:
                    continue

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

            candidates.append({
                "year": year,
                "quarter": quarter,
                "url": pdf_link,
                "title": title_clean,
                "report_type": report_type,
                "is_full": self._is_full_report(title_clean),
                "sec_name": (ann.get("secName", "") or "").strip(),
                "announcement_time": ann.get("announcementTime", 0) or 0,
            })

        # 按公告时间倒序排序，确保返回最新报告（不依赖 API 返回顺序）
        if candidates:
            candidates.sort(key=lambda c: c.get("announcement_time", 0), reverse=True)
            best = candidates[0]
            best.pop("announcement_time", None)  # 移除内部排序字段，保持返回结构干净
            return best

        return None

    def get_latest_report_url(self, report_type: str = 'annual') -> Optional[Dict[str, str]]:
        """获取最新财报PDF链接和年份.

        从巨潮资讯网查询上市公司最新财报信息.
        采用两阶段多关键词搜索策略:

        **搜索关键词优先级**（组合关键词优先，更精准）:
        1. 股票代码 + 报告类型关键词（如 "300274 年度报告"）
        2. 仅股票代码（如 "300274"）

        **两阶段筛选**:
        - 第一轮: 所有关键词均只找完整版报告
        - 第二轮: 仅当第一轮全部失败，才接受摘要/简版作为备选

        背景: 仅按股票代码搜索时，热门公司的公告量大（50+），
        完整版年报可能被其他类型公告挤出前50条，导致只找到摘要版.
        组合关键词搜索可精准定位财报公告，避免被无关公告淹没.

        Args:
            report_type: 报告类型 ('annual'-年报, 'semiannual'-半年报, 'quarterly'-季报)

        Returns:
            {"year": "2025", "url": "https://...", "title": "...", "report_type": "..."} 或 None
        """
        # 报告类型对应的关键词（用于组合搜索）
        report_keywords = {
            'annual': '年度报告',
            'semiannual': '半年度报告',
            'quarterly': '季度报告'
        }
        report_keyword = report_keywords.get(report_type, '报告')

        # 搜索关键词列表（按优先级排序，组合关键词优先）:
        # 1. 首选: 股票代码 + 报告类型关键词（精准定位财报公告）
        # 2. 备选: 仅按股票代码搜索（返回该股票所有公告）
        search_keys = [
            f"{self.code} {report_keyword}",
            self.code,
        ]

        # 两阶段搜索: 第一阶段所有关键词只找完整版；
        # 第二阶段复用已缓存的公告列表，才接受摘要/简版（避免重复请求与重复完整版搜索）
        ann_cache: Dict[str, List[Dict]] = {}

        # 第一阶段: 只找完整版
        for search_key in search_keys:
            ann_list = self._fetch_cninfo_announcements(search_key)
            ann_cache[search_key] = ann_list
            if not ann_list:
                continue
            result = self._find_report_by_priority(
                ann_list, report_type, require_full=True
            )
            if result:
                self.api_results.append({
                    'api_name': f"巨潮资讯财报查询(股票代码: {self.code}, "
                                f"报告类型: {report_type}, 阶段: 完整版, "
                                f"命中关键词: {search_key})",
                    'status': '成功',
                    'rows': 1
                })
                return result

        # 第二阶段: 完整版未命中，复用缓存接受摘要/简版
        for search_key in search_keys:
            ann_list = ann_cache.get(search_key) or []
            if not ann_list:
                continue
            result = self._find_report_by_priority(
                ann_list, report_type, require_full=False
            )
            if result:
                self.api_results.append({
                    'api_name': f"巨潮资讯财报查询(股票代码: {self.code}, "
                                f"报告类型: {report_type}, 阶段: 摘要/简版, "
                                f"命中关键词: {search_key})",
                    'status': '成功',
                    'rows': 1
                })
                return result

        # 所有搜索关键词和阶段均未找到目标报告
        error_msg = f'未找到{self._get_report_type_name(report_type)}（已尝试多关键词搜索）'
        self.api_results.append({
            'api_name': f"巨潮资讯财报查询(股票代码: {self.code}, 报告类型: {report_type})",
            'status': '失败',
            'error': error_msg
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

        # 文件名包含股票名称便于识别（清理非法字符；名称缺失时回退为仅股票代码）
        sec_name = self._sanitize_filename(report_info.get('sec_name', '') or '')
        if sec_name:
            pdf_filename = f"{self.code}_{sec_name}_{year}{report_name}.pdf"
        else:
            pdf_filename = f"{self.code}_{year}{report_name}.pdf"
        pdf_path = os.path.join(save_dir, pdf_filename)

        # 检查是否已下载（需验证文件大小，避免摘要版/提示性公告被误认为完整版）
        # 阈值按报告类型区分：年报/半年报完整版 > 1MB，季报完整版 > 100KB
        min_full_size = self._get_min_full_report_size_kb(report_type) * 1024
        if os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path)
            if file_size >= min_full_size:
                self.api_results.append({
                    'api_name': f'财报已存在({pdf_path}, {file_size/1024:.1f}KB)',
                    'status': '成功',
                    'rows': 1
                })
                return pdf_path
            else:
                # 文件过小，可能是摘要版，删除后重新下载
                print(f"⚠️  检测到文件过小（{file_size/1024:.1f}KB < {min_full_size/1024:.0f}KB），可能是摘要版，将重新下载...")
                os.remove(pdf_path)

        # 下载PDF
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0 Safari/537.36",
                "Referer": "https://www.cninfo.com.cn/new/disclosure"
            }

            resp = self._http_get_with_retry(report_info['url'], headers=headers, timeout=30)

            content = resp.content

            # 校验文件头：合法 PDF 以 %PDF 魔数开头，防止把 HTML 错误页/反爬页面写入 .pdf
            if not content.startswith(b'%PDF'):
                raise ValueError(
                    f"下载内容不是有效的 PDF 文件（Content-Type: "
                    f"{resp.headers.get('Content-Type', '未知')}，文件头: {content[:16]!r}）"
                )

            with open(pdf_path, "wb") as f:
                f.write(content)

            # 记录成功
            self.api_results.append({
                'api_name': f'PDF下载({report_info["url"]})',
                'status': '成功',
                'rows': 1
            })

            time.sleep(1.2)  # 避免频繁请求
            return pdf_path

        except Exception as e:
            # 下载失败时清理可能残留的残缺文件
            if os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except OSError:
                    pass
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
    # Windows GBK 控制台兼容：确保 emoji 和 Unicode 字符能正常输出
    if sys.stdout.encoding and sys.stdout.encoding.upper() not in ('UTF-8', 'UTF8'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    if sys.stderr.encoding and sys.stderr.encoding.upper() not in ('UTF-8', 'UTF8'):
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(
        description='获取A股股票股权结构数据',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取紫金矿业股权结构数据
  python tools/a_share/stock_equity.py --code 601899

  # 指定报告期
  python tools/a_share/stock_equity.py --code 601899 --date 20251231

  # 导出为Excel文件
  python tools/a_share/stock_equity.py --code 601899 --export

  # JSON格式输出
  python tools/a_share/stock_equity.py --code 601899 --json

  # 下载最新年报PDF
  python tools/a_share/stock_equity.py --code 601899 --download-report

  # 下载最新半年报PDF
  python tools/a_share/stock_equity.py --code 601899 --download-report --report-type semiannual

  # 下载最新季报PDF
  python tools/a_share/stock_equity.py --code 601899 --download-report --report-type quarterly
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
