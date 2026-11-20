import os, sys, shutil, time, threading
import flet as ft
import yt_dlp


# Correção: Garantir que os binários embutidos no Appimage (ffmpeg, ffprobe, deno) estejam na porra do PATH, sem isso o sistema fica capado
if getattr(sys, "frozen", False) or os.environ.get("APPIMAGE"):
    bin_dir = os.path.dirname(os.path.abspath(sys.executable))
    os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"

class YtdpLogger:
    def __init__(self):
        self.erros = []

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        clean_msg = msg.replace("ERROR: ", "").strip()
        self.erros.append(clean_msg)


async def main(page: ft.Page):
    page.title = "Py4K Video Downloader"
    page.window.width = 680
    page.window.height = 520
    page.window.resizable = False
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 28

    default_dir = (
        "/app/downloads"
        if os.path.exists("/app/downloads")
        else os.path.join(os.path.expanduser("~"), "Downloads")
    )
    last_ui_update = 0.0

    clipboard = ft.Clipboard()
    file_picker = ft.FilePicker()

    # --- Interface ---
    url_input = ft.TextField(
        label="Link do vídeo ou playlist do YouTube",
        hint_text="https://www.youtube.com/watch?v=...",
        prefix_icon=ft.Icons.LINK,
        expand=True,
        border_radius=10,
    )

    async def paste_url(e):
        try:
            clip = await clipboard.get()
            if clip:
                url_input.value = clip.strip()
                page.update()
        except Exception:
            pass

    paste_btn = ft.IconButton(
        icon=ft.Icons.CONTENT_PASTE,
        tooltip="Colar link",
        on_click=paste_url,
    )

    def on_format_change(e):
        resolution_dropdown.disabled = format_dropdown.value == "MP3"
        page.update()

    format_dropdown = ft.Dropdown(
        label="Formato",
        value="MP4",
        width=180,
        border_radius=10,
        options=[
            ft.dropdown.Option("MP4", "MP4 (Vídeo)"),
            ft.dropdown.Option("MP3", "MP3 (Áudio)"),
        ],
        on_select=on_format_change,
    )

    resolution_dropdown = ft.Dropdown(
        label="Resolução Máxima",
        value="1080p",
        width=210,
        border_radius=10,
        options=[
            ft.dropdown.Option("best", "Melhor disponível (4K/2K)"),
            ft.dropdown.Option("1080p", "1080p (Full HD)"),
            ft.dropdown.Option("720p", "720p (HD)"),
            ft.dropdown.Option("480p", "480p"),
            ft.dropdown.Option("360p", "360p"),
        ],
    )

    folder_input = ft.TextField(
        label="Pasta de destino",
        value=default_dir,
        prefix_icon=ft.Icons.FOLDER,
        expand=True,
        border_radius=10,
    )

    async def open_folder_dialog(e):
        try:
            selected_path = await file_picker.get_directory_path(
                initial_directory=folder_input.value
            )
            if selected_path:
                folder_input.value = selected_path
                page.update()
        except Exception:
            status_text.value = "No modo navegador, digite o caminho da pasta diretamente no campo."
            status_text.color = ft.Colors.AMBER_300
            page.update()

    folder_btn = ft.Button(
        "Escolher Pasta",
        icon=ft.Icons.FOLDER_OPEN,
        height=48,
        on_click=open_folder_dialog,
    )

    progress_bar = ft.ProgressBar(
        value=0, color=ft.Colors.GREEN_400, bgcolor=ft.Colors.GREY_800, height=8
    )
    status_text = ft.Text("Pronto para baixar.", size=13, color=ft.Colors.GREY_400)

    # --- Download ---
    def progress_hook(d):
        nonlocal last_ui_update
        now = time.time()

        if d["status"] == "downloading":
            if now - last_ui_update < 0.15:
                return
            last_ui_update = now

            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            downloaded = d.get("downloaded_bytes", 0)
            filename = os.path.basename(d.get("filename", ""))

            if total:
                pct = downloaded / total
                progress_bar.value = pct
                status_text.value = f"Baixando ({pct * 100:.1f}%): {filename[:48]}"
                status_text.color = ft.Colors.WHITE
                page.update()

        elif d["status"] == "finished":
            progress_bar.value = 1.0
            status_text.value = "Mesclando áudio e vídeo com FFmpeg..."
            status_text.color = ft.Colors.AMBER_300
            page.update()

    def run_download(url: str, fmt: str, res: str, out_dir: str):
        os.makedirs(out_dir, exist_ok=True)
        logger = YtdlpLogger()
        ffmpeg_bin = shutil.which("ffmpeg")

        output_template = os.path.join(
            out_dir, "%(playlist_title&{}/|)s%(title)s.%(ext)s"
        )

        ydl_opts = {
            "outtmpl": output_template,
            "progress_hooks": [progress_hook],
            "logger": logger,
            "ignoreerrors": "only_download",
            "retries": 10,
            "fragment_retries": 10,
            "file_access_retries": 5,
            "continuedl": True,
            "concurrent_fragment_downloads": 3,
        }

        if ffmpeg_bin:
            ydl_opts["ffmpeg_location"] = os.path.dirname(ffmpeg_bin)

        if fmt == "MP3":
            ydl_opts.update(
                {
                    "format": "bestaudio/best",
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                }
            )
        else:
            if res == "best":
                video_fmt = "bestvideo+bestaudio/best"
            else:
                height = res.replace("p", "")
                video_fmt = f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best"

            ydl_opts.update(
                {
                    "format": video_fmt,
                    "merge_output_format": "mp4",
                }
            )

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                exit_code = ydl.download([url])

            if exit_code == 0 and not logger.errors:
                status_text.value = "Download concluído com sucesso!"
                status_text.color = ft.Colors.GREEN_400
                progress_bar.value = 1.0
            else:
                err_detail = logger.errors[-1] if logger.errors else "Falha parcial no download."
                status_text.value = f"Aviso/Erro: {err_detail[:95]}"
                status_text.color = ft.Colors.AMBER_300
                progress_bar.value = 0
        except Exception as ex:
            status_text.value = f"Erro no download: {ex}"
            status_text.color = ft.Colors.RED_400
            progress_bar.value = 0
        finally:
            download_btn.disabled = False
            page.update()

    def start_download(e):
        url = (url_input.value or "").strip()
        if not url:
            url_input.error_text = "Cole um link válido do YouTube"
            page.update()
            return

        url_input.error_text = None
        download_btn.disabled = True
        progress_bar.value = None
        status_text.value = "Obtendo informações do link..."
        status_text.color = ft.Colors.BLUE_300
        page.update()

        threading.Thread(
            target=run_download,
            args=(
                url,
                format_dropdown.value,
                resolution_dropdown.value,
                folder_input.value.strip(),
            ),
            daemon=True,
        ).start()

    download_btn = ft.Button(
        "Baixar Agora",
        icon=ft.Icons.DOWNLOAD,
        bgcolor=ft.Colors.GREEN_600,
        color=ft.Colors.WHITE,
        height=48,
        width=220,
        on_click=start_download,
    )

    page.add(
        ft.Column(
            spacing=18,
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(
                            ft.Icons.ONDEMAND_VIDEO,
                            color=ft.Colors.GREEN_400,
                            size=32,
                        ),
                        ft.Text(
                            "Py4K Video Downloader",
                            size=24,
                            weight=ft.FontWeight.BOLD,
                        ),
                    ]
                ),
                ft.Row(controls=[url_input, paste_btn]),
                ft.Row(controls=[format_dropdown, resolution_dropdown], spacing=20),
                ft.Row(controls=[folder_input, folder_btn]),
                ft.Container(
                    content=download_btn,
                    alignment=ft.Alignment.CENTER,
                    padding=ft.Padding.only(top=6),
                ),
                ft.Column(spacing=6, controls=[progress_bar, status_text]),
            ],
        )
    )


if __name__ == "__main__":
    is_native = bool(
        os.environ.get("APPIMAGE")
        or os.environ.get("DISPLAY")
        or os.environ.get("WAYLAND_DISPLAY")
    )
    if is_native:
        ft.run(main)
    else:
        ft.run(main, view=ft.AppView.WEB_BROWSER, host="0.0.0.0", port=8550)