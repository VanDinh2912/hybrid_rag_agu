<#
.SYNOPSIS
    Chạy một chuỗi round từ spec JSON (T7) — wrapper mỏng quanh tools/loop/run_chain.py.

.EXAMPLE
    # xem lệnh, không chạy gì
    pwsh -File tools/loop/run_chain.ps1 -Chain tools/loop/chains/t5a_reranker.json -DryRun

.EXAMPLE
    # chạy thật
    pwsh -File tools/loop/run_chain.ps1 -Chain tools/loop/chains/t5a_reranker.json

.NOTES
    Không tự export biến nào: mọi biến của từng bước nằm trong spec và được in ra trước khi chạy.
    Cần venv của app (venv/Scripts/python.exe) — nếu thiếu, run_chain.py dùng python đang gọi.
#>
param(
    [Parameter(Mandatory = $true)][string]$Chain,
    [switch]$DryRun,
    [switch]$Resume,
    [string[]]$Set = @(),
    [string]$ManifestOut = "",
    [string]$Only = ""
)

$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$py = Join-Path $repo "venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$env:PYTHONIOENCODING = "utf-8"
$argv = @(
    (Join-Path $PSScriptRoot "run_chain.py"),
    "--chain", $Chain
)
if ($DryRun) { $argv += "--dry-run" }
if ($Resume) { $argv += "--resume" }
if ($ManifestOut) { $argv += @("--manifest-out", $ManifestOut) }
if ($Only) { $argv += @("--only", $Only) }
foreach ($kv in $Set) { $argv += @("--set", $kv) }

& $py @argv
exit $LASTEXITCODE
