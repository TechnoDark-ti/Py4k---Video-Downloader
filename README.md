# Py4K Video Downloader

Aplicação desktop gratuita e de código aberto para baixar vídeos e playlists do YouTube em **MP4** ou **MP3**, desenvolvida em **Python** com **Flet** e **yt-dlp**, totalmente containerizada com **Docker** e empacotável como **`.AppImage`** independente para Linux.

---

## Funcionalidades

- **Vídeos e Playlists:** Suporte a links individuais ou playlists completas (cria automaticamente uma subpasta com o nome da playlist).
- **Escolha de Formato:** Download de vídeo em **MP4** ou extração de áudio em **MP3 (192 kbps)**.
- **Seleção de Resolução:** Melhor qualidade disponível (4K/2K), 1080p, 720p, 480p ou 360p.
- **Interface Moderna e Responsiva:** Tema escuro, botão rápido para colar link da área de transferência, seletor de pasta de destino e barra de progresso em tempo real sem travar a interface.
- **Zero Dependências no AppImage:** O empacotamento Linux já embute binários estáticos do `ffmpeg` e `ffprobe`, dispensando instalações extras na máquina final.

---

## Tecnologias Utilizadas

- **[Python 3.11](https://www.python.org/)**
- **[Flet](https://flet.dev/)** — Interface gráfica multiplataforma baseada em Flutter
- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — Motor de extração e download de mídia
- **[FFmpeg](https://ffmpeg.org/)** — Mesclagem de faixas de vídeo/áudio em alta resolução e conversão para MP3
- **[Docker & Docker Compose](https://www.docker.com/)** — Ambiente isolado de execução e compilação

---

## Estrutura do Projeto

```text
py4k-downloader/
├── src/
│   └── main.py          # Código principal da interface (Flet) e download (yt-dlp)
├── build_appimage.sh    # Script de empacotamento AppImage + FFmpeg estático
├── Dockerfile           # Imagem de execução e desenvolvimento
├── Dockerfile.build     # Imagem de compilação (Flutter Linux + appimagetool)
├── docker-compose.yml   # Orquestração do ambiente local
├── pyproject.toml       # Metadados e configurações de build do Flet
└── requirements.txt     # Dependências Python