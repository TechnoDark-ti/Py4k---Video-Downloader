FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Instala FFmpeg, libsecret, OpenGL/GLES e dependências gráficas do Flet Desktop
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    xdg-user-dirs \
    fontconfig \
    libsecret-1-0 \
    libgtk-3-0 \
    libnotify4 \
    libayatana-appindicator3-1 \
    libgl1 \
    libegl1 \
    libgles2 \
    libgl1-mesa-dri \
    libgstreamer1.0-0 \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    libmpv2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./src ./src

CMD ["python", "src/main.py"]