# momentum_backtest.py 可用性测试

## 测试目的

验证 `momentum_backtest.py` 在科学上网情况下是否可用。

## 测试范围

| 测试项 | 说明 |
|--------|------|
| **网络连接测试** | 测试 Yahoo Finance API 是否可访问 |
| **yfinance 库测试** | 测试 yfinance 库是否可用（作为对比） |
| **数据获取函数测试** | 测试 fetch_price_data() 函数 |
| **动量信号计算测试** | 测试 compute_momentum_signals() 函数 |
| **价值验证引擎测试** | 测试 verify_value() 函数 |
| **完整回测流程测试** | 测试完整的回测流程 |

## 使用方法

### 1. 运行测试

```bash
# 切换到工作区根目录
cd f:\Financial_Investment_Analysis

# 运行测试
python tests/test_momentum_backtest.py
```

### 2. 查看测试报告

测试完成后，会在 `tests/` 目录下生成 JSON 格式的测试报告：

```
tests/momentum_backtest_test_report_YYYYMMDD_HHMMSS.json
```

## 测试结果解读

### ✅ 所有测试通过

表示 `momentum_backtest.py` 可以正常使用。

**建议**：
- 可以直接运行 `python tools/momentum_backtest.py`
- 如需更稳定的数据获取，建议安装 yfinance

### ❌ 部分测试失败

**常见问题与解决方案**：

#### 1. Yahoo Finance API 连接失败

**原因**：
- 未开启科学上网
- 网络连接超时
- Yahoo Finance API 被限制

**解决方案**：
```bash
# 检查代理设置
echo $HTTP_PROXY
echo $HTTPS_PROXY

# 设置代理（如果需要）
set HTTP_PROXY=http://your-proxy:port
set HTTPS_PROXY=http://your-proxy:port

# 重新运行测试
python tests/test_momentum_backtest.py
```

#### 2. yfinance 测试失败

**原因**：
- yfinance 未安装
- 网络连接问题

**解决方案**：
```bash
# 安装 yfinance
pip install yfinance pandas

# 重新运行测试
python tests/test_momentum_backtest.py
```

#### 3. 数据获取失败

**原因**：
- API 限制
- 时间范围不合理

**解决方案**：
- 检查科学上网是否正常
- 尝试使用 yfinance（更稳定）
- 考虑使用 momentum_backtest_v2.py（从本地文件加载）

## 替代方案

如果测试失败，可以考虑：

### 方案1：使用 yfinance（推荐）

```python
import yfinance as yf

ticker = yf.Ticker("NVDA")
data = ticker.history(period="1y")
```

**优点**：
- 更稳定的API
- 内置重试机制
- 更好的错误处理

### 方案2：使用 momentum_backtest_v2.py

从本地 JSON 文件加载价格数据，不依赖外部 API。

**准备工作**：
1. 手动下载价格数据
2. 保存为 `data/NVDA_prices.json`
3. 运行 `python tools/momentum_backtest_v2.py`

### 方案3：使用多数据源 fallback

修改 `momentum_backtest.py`，实现多数据源 fallback：

```python
def fetch_price_data(ticker, start_date, end_date):
    # 优先级1：yfinance
    try:
        import yfinance as yf
        # ...
    except:
        pass
    
    # 优先级2：本地JSON文件
    json_file = f"data/{ticker}_prices.json"
    if os.path.exists(json_file):
        return load_from_json(json_file)
    
    # 优先级3：原始API
    return fetch_from_yahoo_api(ticker)
```

## 性能指标

测试会记录每个测试项的耗时：

| 测试项 | 预期耗时 | 说明 |
|--------|---------|------|
| 网络连接测试 | 1-10秒 | 取决于网络速度 |
| yfinance 库测试 | 1-5秒 | 取决于网络速度 |
| 数据获取函数测试 | 1-10秒 | 取决于数据量 |
| 动量信号计算测试 | <1秒 | 纯计算，无网络IO |
| 价值验证引擎测试 | <1秒 | 纯计算，无网络IO |
| 完整回测流程测试 | 5-30秒 | 取决于数据量 |

## 故障排查

### 问题1：导入模块失败

```
❌ 无法导入 momentum_backtest 模块
```

**解决方案**：
- 确认 `momentum_backtest.py` 位于 `tools/` 目录下
- 确认从工作区根目录运行测试

### 问题2：测试超时

```
❌ Yahoo Finance API 连接测试 FAIL 连接超时
```

**解决方案**：
- 检查科学上网是否正常
- 尝试使用代理
- 检查防火墙设置

### 问题3：返回空数据

```
❌ fetch_price_data(NVDA) 测试 FAIL 返回空数据
```

**解决方案**：
- 检查时间范围是否合理
- 检查股票代码是否正确
- 尝试使用 yfinance

## 相关文件

| 文件 | 说明 |
|------|------|
| `tools/momentum_backtest.py` | 主程序（原始版本） |
| `tools/momentum_backtest_v2.py` | 主程序（改进版本） |
| `tests/test_momentum_backtest.py` | 测试软件 |
| `tests/momentum_backtest_test_report_*.json` | 测试报告 |

## 联系与支持

如有问题，请查看：
- [A股工具使用指南](../docs/A股工具使用指南.md)
- [港股工具使用指南](../docs/港股工具使用指南.md)

---

**版本**：1.0.0  
**创建日期**：2026-07-23  
**维护状态**：活跃维护