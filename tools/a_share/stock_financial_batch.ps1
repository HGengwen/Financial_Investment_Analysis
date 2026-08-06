<#
.SYNOPSIS
批量查询A股财务指标（调用 stock_financial.py）

.DESCRIPTION
通过调用 tools/a_share/stock_financial.py 批量获取多只A股股票的指定财务指标，
输出每只股票最近 N 期数据。所有模式的输出结构统一为
d['data']['indicators']（{指标名: {报告期: 值}}）。

.NOTES
Python 路径解析优先级：-python 参数 > 环境变量 PYTHON_EXE > 系统PATH中的 python > 项目默认路径
数据源：东方财富（akshare）

.EXAMPLE
# 使用默认代码列表和指标（近5期）
.\stock_financial_batch.ps1

# 指定股票代码和指标
.\stock_financial_batch.ps1 -codes "601899,000960" -indicators "ROE,毛利率"

# 指定期数
.\stock_financial_batch.ps1 -codes "601899" -periods 3
#>

param(
    # 股票代码列表（逗号分隔）
    [string]$codes = "000960,000962,000426,002155",
    # 财务指标列表（逗号分隔）
    [string]$indicators = "营业总收入,归母净利润,基本每股收益,ROE,毛利率,资产负债率",
    # 输出的最近期数
    [int]$periods = 5,
    # Python 可执行文件路径（留空时按优先级自动解析）
    [string]$python = ""
)

# 脚本所在目录（兼容任意工作目录调用）
$script_dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$tool_path = Join-Path $script_dir "stock_financial.py"

# Python 路径解析：-python 参数 > 环境变量 PYTHON_EXE > 系统PATH中的 python > 项目默认路径
if (-not $python) {
    if ($env:PYTHON_EXE) {
        $python = $env:PYTHON_EXE
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $python = "python"
    } else {
        $python = "F:/Anaconda3/envs/Python_3_12_3/python.exe"
    }
}

# 解析参数
$code_list = $codes.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }
$indicator_list = $indicators.Split(',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' }

# 解析 JSON 的内联 Python 代码
$keys_py = ($indicator_list | ForEach-Object { "'$_'" }) -join ","
$parser = @"
import sys, json
# 兼容 Windows 管道输出的 UTF-8 BOM
d = json.loads(sys.stdin.buffer.read().decode('utf-8-sig'))
# 所有模式的输出结构统一为 d['data']['indicators']
ind = d['data']['indicators']
keys = [$keys_py]
for k in keys:
    items = sorted(ind.get(k, {}).items())[-${periods}:]
    print(k, {y: v for y, v in items})
"@

# 逐只股票查询
foreach ($code in $code_list) {
    Write-Host "===== $code ====="
    & $python $tool_path --code $code --indicator $indicators 2>$null |
        & $python -c $parser 2>&1
}
