$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$ffmpeg = Get-Command ffmpeg -ErrorAction SilentlyContinue
$ffprobe = Get-Command ffprobe -ErrorAction SilentlyContinue
if (-not $ffmpeg -or -not $ffprobe) {
  throw "Instala FFmpeg (incluyendo ffprobe) y asegúrate de que ambos están en PATH antes de empaquetar."
}
$ffmpegPath = $ffmpeg.Source
$ffprobePath = $ffprobe.Source
$ffmpegDir = Split-Path $ffmpegPath
if ($env:ChocolateyInstall) {
  $chocoBin = Join-Path $env:ChocolateyInstall "lib\ffmpeg\tools\ffmpeg\bin"
  if ((Test-Path (Join-Path $chocoBin "ffmpeg.exe")) -and (Test-Path (Join-Path $chocoBin "ffprobe.exe"))) {
    $ffmpegPath = Join-Path $chocoBin "ffmpeg.exe"
    $ffprobePath = Join-Path $chocoBin "ffprobe.exe"
    $ffmpegDir = $chocoBin
  }
}
python -m venv .venv
$python = Join-Path (Get-Location) ".venv\Scripts\python.exe"
& $python -m pip install --upgrade pip
& $python -m pip install -e ".[dev]"
New-Item -ItemType Directory -Force build\bin | Out-Null
Copy-Item $ffmpegPath build\bin\ffmpeg.exe -Force
Copy-Item $ffprobePath build\bin\ffprobe.exe -Force
Get-ChildItem $ffmpegDir -Filter "*.dll" -ErrorAction SilentlyContinue | Copy-Item -Destination build\bin -Force
$pyArgs = @("--noconfirm", "--clean", "--onedir", "--windowed", "--name", "OLV",
  "--collect-all", "edge_tts", "--collect-all", "cairosvg", "--collect-all", "keyring",
  "--add-data", "LICENSE;.",
  "--add-data", "assets;assets",
  "--add-data", "shortsfactory\assets;shortsfactory\assets",
  "--copy-metadata", "keyring",
  "--add-binary", "build\bin\ffmpeg.exe;bin",
  "--add-binary", "build\bin\ffprobe.exe;bin")
Get-ChildItem build\bin -Filter "*.dll" | ForEach-Object {
  $pyArgs += @("--add-binary", "$($_.FullName);bin")
}
$pyArgs += "olv_launcher.py"
& $python -m PyInstaller @pyArgs
$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$isccPath = if ($iscc) { $iscc.Source } else { $null }
if (-not $isccPath -and $env:ProgramFiles) {
  $candidate = Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe"
  if (Test-Path $candidate) { $isccPath = $candidate }
}
if (-not $isccPath) {
  $programFilesX86 = [Environment]::GetFolderPath("ProgramFilesX86")
  if ($programFilesX86) {
    $candidate = Join-Path $programFilesX86 "Inno Setup 6\ISCC.exe"
    if (Test-Path $candidate) { $isccPath = $candidate }
  }
}
if ($isccPath) {
  & $isccPath installer\OLV.iss
} else {
  Write-Host "Portable listo en dist\OLV. Instala Inno Setup para generar el instalador EXE."
}
