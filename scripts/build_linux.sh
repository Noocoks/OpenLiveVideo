#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
command -v ffmpeg >/dev/null || { echo "Instala FFmpeg antes de empaquetar." >&2; exit 1; }
command -v ffprobe >/dev/null || { echo "Instala FFprobe antes de empaquetar." >&2; exit 1; }
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
mkdir -p build/bin
cp "$(command -v ffmpeg)" build/bin/ffmpeg
cp "$(command -v ffprobe)" build/bin/ffprobe
python -m PyInstaller --noconfirm --clean --onedir --name OLV --collect-all edge_tts --collect-all cairosvg --collect-all keyring --collect-all secretstorage --collect-all jeepney --add-data "assets:assets" --add-data "shortsfactory/assets:shortsfactory/assets" --copy-metadata keyring --add-binary "build/bin/ffmpeg:bin" --add-binary "build/bin/ffprobe:bin" olv_launcher.py
mkdir -p dist/packages/olv_0.4.0_amd64/opt/olv
mkdir -p dist/packages/olv_0.4.0_amd64/usr/bin
mkdir -p dist/packages/olv_0.4.0_amd64/usr/share/applications
mkdir -p dist/packages/olv_0.4.0_amd64/DEBIAN
cp -a dist/OLV/. dist/packages/olv_0.4.0_amd64/opt/olv/
cat > dist/packages/olv_0.4.0_amd64/usr/bin/olv <<'EOF'
#!/bin/sh
exec /opt/olv/OLV "$@"
EOF
chmod +x dist/packages/olv_0.4.0_amd64/usr/bin/olv
cat > dist/packages/olv_0.4.0_amd64/usr/share/applications/olv.desktop <<'EOF'
[Desktop Entry]
Name=OLV
Comment=Open Live Video — producción local de Shorts
Exec=/usr/bin/olv
Terminal=false
Type=Application
Categories=AudioVideo;Video;
EOF
cat > dist/packages/olv_0.4.0_amd64/DEBIAN/control <<'EOF'
Package: olv
Version: 0.4.0
Section: video
Priority: optional
Architecture: amd64
Depends: ffmpeg, libc6, libstdc++6, libx11-6, libxext6, libxrender1, libxinerama1, libxi6, libxkbcommon0, libglib2.0-0, libfontconfig1, libfreetype6, libcairo2, libasound2 | libasound2t64
Maintainer: OLV Project
Description: Open Live Video — local YouTube Shorts production
 Desktop app for preparing and rendering vertical videos locally.
EOF
dpkg-deb --build dist/packages/olv_0.4.0_amd64 dist/olv_0.4.0_amd64.deb
tar -czf dist/olv-0.4.0-linux-x86_64.tar.gz -C dist OLV
echo "Paquete DEB y portable creados en dist/."
