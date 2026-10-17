# Windows 下跑 scripts/cx.py 的统一入口：先修编码，再挑可用的 python。
#
#   .\scripts\run.ps1 roster
#   .\scripts\run.ps1 check
#
# 编码不修的话，中文在控制台会变成乱码，判分日志和错误信息都没法读。

$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'

$candidates = @(
    $env:DSH_PYTHON,
    'C:\Users\27263\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe',
    'python'
) | Where-Object { $_ -and (Test-Path $_) -or $_ -eq 'python' }

$py = $candidates | Select-Object -First 1
if (-not $py) {
    throw '找不到 python：设置环境变量 DSH_PYTHON 指向可用的解释器'
}

& $py (Join-Path $PSScriptRoot 'cx.py') @args
exit $LASTEXITCODE
