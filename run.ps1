# FinInsight AI - start Streamlit with project .venv
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
$streamlit = Join-Path $PSScriptRoot ".venv\Scripts\streamlit.exe"

if (-not (Test-Path $python)) {
    Write-Error "Missing .venv. Run: python -m venv .venv; .venv\Scripts\pip install -r requirements.txt"
}

& $python -c "import torch; assert hasattr(torch, 'SymInt'), 'broken torch - reinstall torch==2.12.1'"

Write-Host "Using Python: $python"
Write-Host "Clearing Python cache..."
Get-ChildItem -Recurse -Path (Join-Path $PSScriptRoot "src"), (Join-Path $PSScriptRoot "ui") -Filter "__pycache__" -Directory -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Starting Streamlit..."
& $streamlit run ui/app.py
