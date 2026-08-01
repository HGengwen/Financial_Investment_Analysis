---
name: hk-share-data
description: "港股数据获取工具：提供港股股票信息查询、财务指标、历史K线与指数数据、质量筛选等工具的使用规范。"
disable-model-invocation: true
---

# 港股数据获取工具

数据源：东方财富、新浪财经

---

## 工具清单

| 工具 | 功能 | 命令示例 |
|------|------|---------|
| `tools/hk_stock/stock_financial.py` | 港股信息查询与财务指标 | `python tools/hk_stock/stock_financial.py --financial {股票代码}` |
| `tools/hk_stock/stock_quote.py` | 港股历史K线与指数数据 | `python tools/hk_stock/stock_quote.py --code {股票代码}` |
| `tools/hk_stock/stock_screen.py` | 港股质量筛选7条指标 | `python tools/hk_stock/stock_screen.py --code {股票代码}` |

---

## 注意事项

- 东方财富港股接口在中国大陆网络连接不稳定（非地理封锁），工具已内置重试机制
- 港股股票代码不含前导零时需补齐（如 `00700` 而非 `700`）

---

## 相关技能

- [A股数据获取](./a-share-data.md)
- [财务计算与验证](./financial-calc.md)
- [公共工具索引](./common-tools-guide.md)

---

## 版本信息

- **版本**：1.0.0
- **创建日期**：2026-07-31
