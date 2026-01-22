Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location (Split-Path $PSScriptRoot -Parent)
python scripts/run_adjust_thresholds.py
