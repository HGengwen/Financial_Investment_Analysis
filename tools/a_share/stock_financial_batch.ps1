<#
.SYNOPSIS
批量查询A股财务指标（调用 stock_financial.py）

.DESCRIPTION
通过调用 tools/a_share/stock_financial.py 批量获取多只A股股票的指定财务指标，
输出每只股票最近 N 期数据。所有模式的输出结构统一为
d['data']['indicators']（{指标名: {报告期: 值}}）。

节流全部交给东财请求闸门（tools/common/em_gate.py，方案 §3.6）：
stock_financial.py 的 main() 首行 install_cli() 后，所有东财请求经跨进程锁
串行化（最小间隔 + 随机抖动 + 滑窗预算）。**脚本层不再自行 sleep**——双重
节流会造成不可控的叠加等待，且无法与其它子代理进程共享同一份配额。

失败即停：任一只标的失败（非零退出码，或工具输出 "success": false）时，
脚本立即中止整批并打印失败原因与替代命令，不再继续下一个标的。该行为是
刻意设计——批量场景下的连续失败通常意味着东财已开始限流/封禁，继续调用
只会加重惩罚并延长封禁。闸门拒绝时工具会输出统一降级载荷
（success=false + meta.gate + meta.fallback_cmd），脚本原样透传给调用方。

批量规模约束（方案 §3.6）：
- -MaxCodes（默认 20）：单次批量的标的上限，超出即中止，防误传全市场列表；
- 交易时段（09:15-11:30 / 13:00-15:00，周一至周五）默认禁止跑批量（> 5 只），
  仅允许盘后执行；确有需要可加 -AllowIntraday 显式放行。

.NOTES
参数向后兼容：-codes / -indicators / -periods / -python 语义不变；
-MaxCodes / -AllowIntraday 为新增可选参数；原 -interval 已移除（节流统一归闸门）
Python 路径解析优先级：-python 参数 > 环境变量 PYTHON_EXE > 系统PATH中的 python > 项目默认路径
数据源：东方财富（akshare）

.EXAMPLE
# 使用默认代码列表和指标（近5期）
.\stock_financial_batch.ps1

# 指定股票代码和指标
.\stock_financial_batch.ps1 -codes "601899,000960" -indicators "ROE,毛利率"

# 指定期数
.\stock_financial_batch.ps1 -codes "601899" -periods 3

# 放宽标的上限（默认 20）
.\stock_financial_batch.ps1 -codes "601899,000960,000962" -MaxCodes 30
#>

param(
    # 股票代码列表（逗号分隔）
    [string]$codes = "000960,000962,000426,002155",
    # 财务指标列表（逗号分隔）
    [string]$indicators = "营业总收入,归母净利润,基本每股收益,ROE,毛利率,资产负债率",
    # 输出的最近期数
    [int]$periods = 5,
    # Python 可执行文件路径（留空时按优先级自动解析）
    [string]$python = "",
    # 单次批量的标的上限（软上限，方案 §3.6）；传 0 表示不限制
    [int]$MaxCodes = 20,
    # 允许在 A 股交易时段跑批量（默认禁止，方案 §3.6）
    [switch]$AllowIntraday
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

# 校验 1：标的上限（防误传全市场列表，方案 §3.6）
if ($MaxCodes -gt 0 -and $code_list.Count -gt $MaxCodes) {
    Write-Host "[FAIL] 标的数 $($code_list.Count) 超过 -MaxCodes 上限 $MaxCodes，已中止。" -ForegroundColor Red
    Write-Host "[FAIL] 请拆分批次执行，或显式放宽上限：-MaxCodes 0（不限制）" -ForegroundColor Red
    exit 1
}

# 校验 2：交易时段禁止跑批量（> 5 只），方案 §3.6
if (-not $AllowIntraday -and $code_list.Count -gt 5) {
    $now = Get-Date
    $isWeekday = $now.DayOfWeek -ne [System.DayOfWeek]::Saturday -and `
                 $now.DayOfWeek -ne [System.DayOfWeek]::Sunday
    $t = $now.TimeOfDay
    $morning = ($t -ge [System.TimeSpan]::new(9, 15, 0)) -and ($t -le [System.TimeSpan]::new(11, 30, 0))
    $afternoon = ($t -ge [System.TimeSpan]::new(13, 0, 0)) -and ($t -le [System.TimeSpan]::new(15, 0, 0))
    if ($isWeekday -and ($morning -or $afternoon)) {
        Write-Host "[FAIL] 当前为 A 股交易时段（$($now.ToString('HH:mm'))），禁止跑批量财取（$($code_list.Count) 只）。" -ForegroundColor Red
        Write-Host "[FAIL] 请在盘后执行，或显式放行：-AllowIntraday" -ForegroundColor Red
        exit 1
    }
}

# 解析 JSON 的内联 Python 代码
# 注意：禁止用 PowerShell 管道（|）把工具 stdout 喂给 python。
# PowerShell 5.1 在原生程序间管道传输时按系统 ANSI/GBK 重编码，中文键（"毛利率"等）
# 会被破坏，导致 json.loads 报 JSONDecodeError。故在 Python 内用 subprocess 直接捕获
# 工具 stdout，保持 UTF-8 编码，避免 PowerShell 管道重编码。
$keys_py = ($indicator_list | ForEach-Object { "'$_'" }) -join ","
$runner_tpl = @'
import subprocess, json, sys
r = subprocess.run(['__PY__', '__TOOL__', '--code', '__CODE__',
                    '--indicator', '__INDICATORS__'],
                   capture_output=True, text=True)
if r.returncode != 0:
    print('ERROR', r.stderr, file=sys.stderr)
    sys.exit(r.returncode)
try:
    d = json.loads(r.stdout)
except json.JSONDecodeError as exc:
    print('ERROR 工具输出非合法 JSON: %s' % exc, file=sys.stderr)
    sys.exit(3)
# 工具以 JSON 语义报错时退出码仍为 0，故 success=false 同样视为失败
if not d.get('success', False):
    print('ERROR 工具返回 success=false: %s' % str(d.get('error', d))[:300],
          file=sys.stderr)
    sys.exit(2)
ind = d['data']['indicators']
keys = [__KEYS__]
for k in keys:
    items = sorted(ind.get(k, {}).items())[-__PERIODS__:]
    print(k, {y: v for y, v in items})
'@

# 逐只股票查询（失败即停：任一只失败立刻中止整批，不再跑后续标的）
# 标的之间不再自行 sleep：东财请求节奏由闸门（em_gate）在 stock_financial.py 内强制施加
foreach ($code in $code_list) {
    Write-Host "===== $code ====="
    # 嵌入 Python 源码前转义路径反斜杠，避免被当作字符串转义序列（如 \t、\a）
    $python_esc = $python.Replace('\', '\\')
    $tool_esc = $tool_path.Replace('\', '\\')
    $runner = $runner_tpl `
        -replace '__PY__', $python_esc `
        -replace '__TOOL__', $tool_esc `
        -replace '__CODE__', $code `
        -replace '__INDICATORS__', $indicators `
        -replace '__KEYS__', $keys_py `
        -replace '__PERIODS__', $periods

    $output = & $python -c $runner 2>&1
    $exit_code = $LASTEXITCODE
    $output | ForEach-Object { Write-Host $_ }

    # 失败即停：非零退出码（含 success=false 触发的退出码）→ 中止整批
    if ($exit_code -ne 0) {
        Write-Host ""
        Write-Host "[FAIL] 标的 $code 查询失败（退出码 $exit_code），已中止整批。" -ForegroundColor Red
        Write-Host "[FAIL] 原因：$($output -join ' | ')" -ForegroundColor Red
        Write-Host "[FAIL] 替代命令：$python $tool_path --code $code --indicator `"$indicators`"" -ForegroundColor Red
        break
    }
}