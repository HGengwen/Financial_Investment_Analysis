---
name: websearch-cn-block
description: Anthropic WebSearch/WebFetch geo-blocked in China mainland, prohibited
metadata:
  type: reference
---

# Anthropic WebSearch / WebFetch 中国大陆封锁记录

## 封锁性质

Anthropic 官方原生 WebSearch 和 WebFetch 工具（Claude Code、Claude API、Claude 桌面客户端内置）在中国大陆完全不可用，属于硬性地域封锁（geo-blocking）：

- 后端服务器部署在美国，服务策略层面未开放中国大陆 IP 的访问权限
- 无合规国内接入节点或 CDN 加速
- 无论是国内直连还是通过非系统级代理（如浏览器 VPN 插件），均无法正常访问
- 即使国内网站（如百度、新浪等）能被 curl 正常访问，WebFetch 也会因境外域名验证服务被阻断而失败

## 根本原因

不是代理/VPN 配置问题，而是 Anthropic 的联网搜索基础设施（搜索 API、域名验证服务）全部部署在境外，中国大陆网络环境无法到达。

## 禁止规则

所有涉及 WebSearch / WebFetch 的调用，在项目会话中默认禁止。包括但不限于：

- 直接调用 WebSearch 工具搜索中文或英文内容
- 直接调用 WebFetch 工具抓取任何 URL
- 在技能（skills）中引用 WebSearch 作为数据获取手段
- 在研究报告或质量筛选流程中使用 WebSearch 来查找财务数据

## 替代方案

### 替代方案 1：Akshare 本地工具（A股数据，优先使用）

项目已开发基于 akshare 的本地 Python CLI 工具，可直接获取 A 股数据：

| 工具 | 功能 | 数据源 |
|------|------|--------|
| `tools/stock_info.py` | 股票代码、名称、行业查询 | 东方财富（国内可达） |
| `tools/stock_quote.py` | 历史行情数据 | 新浪（国内可达，推荐） |
| `tools/stock_financial.py` | 财务指标（ROE、毛利率、净利率等 70+ 指标） | 新浪（国内可达） |
| `tools/stock_screen.py` | 7条质量筛选指标一站式输出 | 整合多个国内可达源 |

调用方式：`F:/Anaconda3/envs/Python_3_12_3/python.exe tools/xxx.py --code 300502`

### 替代方案 2：浏览器手动搜索 + 粘贴

对于无法通过本地工具获取的数据（如港股、美股，或特定新闻），用户在 Edge 浏览器中通过科学上网手动搜索，将结果链接或内容粘贴到对话中。

### 替代方案 3：国内 API 直调（港股/美股未来规划）

未来可扩展工具通过国内可达的财经 API（如新浪财经的港股/美股接口）获取非 A 股数据。

## 历史背景

- 首次发现：2026-07-10，在质量筛选工作中发现 WebSearch 搜索百度等国内网站也返回空结果
- 确认封锁：同一环境下国内网站 curl 可正常访问（百度返回 200），但 WebSearch/WebFetch 工具始终返回空结果或无法验证域名安全性
- Python akshare 工具在国内网络环境下正常工作（新浪、东方财富数据源均可达）

## 关联记忆

- [[independent-workspace]] — 工作区独立于 ai-berkshire 上游