#!/usr/bin/env bash
set -e

APP_NAME="Py4K_Video_Downloader"
APP_DIR="/build/${APP_NAME}.AppDir"

echo "==> 1. Compilando aplicação nativa com Flet..."
flet build linux --yes

echo "==> 2. Montando estrutura AppDir..."
rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}/usr/bin"

# Copia o executável, libs e data gerados pelo Flutter/Flet
cp -r build/linux/* "${APP_DIR}/usr/bin/"

echo "==> 3. Baixando FFmpeg estático para embutir no AppImage..."
curl -L -s "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz" -o /tmp/ffmpeg.tar.xz
tar -xf /tmp/ffmpeg.tar.xz -C /tmp
cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffmpeg "${APP_DIR}/usr/bin/"
cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffprobe "${APP_DIR}/usr/bin/"
chmod +x "${APP_DIR}/usr/bin/ffmpeg" "${APP_DIR}/usr/bin/ffprobe"

echo "==> 4. Criando AppRun, ícone e arquivo .desktop..."
cat << 'EOF' > "${APP_DIR}/AppRun"
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/bin/lib:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/py4k_downloader" "$@"
EOF
chmod +x "${APP_DIR}/AppRun"

cat << 'EOF' > "${APP_DIR}/py4k-downloader.desktop"
[Desktop Entry]
Type=Application
Name=Py4K Video Downloader
Comment=Baixar vídeos e playlists do YouTube
Exec=py4k_downloader
Icon=py4k-downloader
Categories=AudioVideo;Video;Network;
Terminal=false
EOF

cat << 'EOF' > "${APP_DIR}/py4k-downloader.svg"
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <rect width="128" height="128" rx="28" fill="#16a34a"/>
  <polygon points="50,38 50,90 92,64" fill="#ffffff"/>
</svg>
EOF

echo "==> 5. Gerando arquivo .AppImage..."
mkdir -p /build/dist
ARCH=x86_64 /usr/local/bin/appimagetool --appimage-extract-and-run "${APP_DIR}" "/build/dist/${APP_NAME}-x86_64.AppImage"

echo "==> Concluído! Arquivo salvo em ./dist/${APP_NAME}-x86_64.AppImage"