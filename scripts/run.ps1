$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (Test-Path ".venv\Scripts\python.exe") {
  & .\.venv\Scripts\python.exe -m shortsfactory.cli
} else {
  python -m shortsfactory.cli
}
