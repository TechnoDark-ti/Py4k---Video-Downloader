#!/usr/bin/env bash
set -euo pipefail

# Evitar a porra do erro "detect devious ownnership" quando o flutter SDK é extraído como root
git config --global --add safe.directory '*'

APP_NAME="Py4K_Video_Downloader"
APP_DIR="/build/${APP_NAME}.AppDir"

echo "==> 1. Compilando aplicação nativa com Flet..."
flet build linux --yes -v

echo "==> 2. Localizando bundle compilado..."
BIN_PATH="$(find build/linux -name "py4k_downloader" -type f | head -n 1)"
if [ -z "${BIN_PATH}" ]; then
    echo "ERRO: Executável py4k_downloader não encontrado dentro de build/linux!"
    find build/linux -maxdepth 5
    exit 1
fi
BUNDLE_DIR="$(dirname "${BIN_PATH}")"
echo "Bundle encontrado em: ${BUNDLE_DIR}"

rm -rf "${APP_DIR}"
mkdir -p "${APP_DIR}/usr/bin" "${APP_DIR}/usr/lib"
cp -a "${BUNDLE_DIR}/." "${APP_DIR}/usr/bin/"

echo "==> 3. Embutindo FFmpeg, FFprobe e Deno (runtime JS) estáticos..."
curl -fSL "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz" -o /tmp/ffmpeg.tar.xz
tar -xf /tmp/ffmpeg.tar.xz -C /tmp
cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffmpeg "${APP_DIR}/usr/bin/"
cp /tmp/ffmpeg-master-latest-linux64-gpl/bin/ffprobe "${APP_DIR}/usr/bin/"

curl -fSL "https://github.com/denoland/deno/releases/latest/download/deno-x86_64-unknown-linux-gnu.zip" -o /tmp/deno.zip
unzip -qo /tmp/deno.zip -d "${APP_DIR}/usr/bin/"

chmod +x "${APP_DIR}/usr/bin/ffmpeg" "${APP_DIR}/usr/bin/ffprobe" "${APP_DIR}/usr/bin/deno"

echo "==> 4. Coletando bibliotecas compartilhadas (.so) para tornar o AppImage autossuficiente..."
copy_deps() {
    local target="$1"
    ldd "$target" 2>/dev/null | awk '/=> \// {print $3}' | while read -r lib; do
        base="$(basename "$lib")"
        # Exclui apenas glibc base e drivers gráficos de hardware que devem vir do sistema hospedeiro
        case "$base" in
            libc.so*|libm.so*|libdl.so*|librt.so*|libpthread.so*|libresolv.so*|ld-linux*|\
            libGL.so*|libEGL.so*|libGLES*|libGLX*|libGLdispatch*|libdrm.so*|libgbm.so*|\
            libwayland*|libX11*|libxcb*|libvulkan*)
                continue
                ;;
        esac
        if [ -f "$lib" ] && [ ! -f "${APP_DIR}/usr/lib/${base}" ]; then
            cp -L "$lib" "${APP_DIR}/usr/lib/${base}"
        fi
    done
}

copy_deps "${APP_DIR}/usr/bin/py4k_downloader"
if [ -d "${APP_DIR}/usr/bin/lib" ]; then
    for sofile in "${APP_DIR}/usr/bin/lib/"*.so*; do
        [ -f "$sofile" ] && copy_deps "$sofile"
    done
fi

echo "==> 5. Criando AppRun, ícone e arquivo .desktop..."
cat << 'EOF' > "${APP_DIR}/AppRun"
#!/usr/bin/env bash
HERE="$(dirname "$(readlink -f "${0}")")"
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${HERE}/usr/bin/lib:${LD_LIBRARY_PATH:-}"
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

echo "==> 6. Gerando arquivo .AppImage..."
mkdir -p /build/dist
ARCH=x86_64 /opt/appimagetool/AppRun "${APP_DIR}" "/build/dist/${APP_NAME}-x86_64.AppImage"

echo "==> Concluído! Arquivo salvo em ./dist/${APP_NAME}-x86_64.AppImage"