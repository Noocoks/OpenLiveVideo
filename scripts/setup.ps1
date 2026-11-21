$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
  throw "Python 3.10+ no está en PATH. Instálalo desde https://www.python.org/"
}
python -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -e ".[dev]"
Write-Host "Instalación terminada. Ejecuta scripts/run.ps1"
