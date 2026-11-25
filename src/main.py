import os
import sys
import shutil
import time
import threading
import flet as ft
import yt_dlp


# Fix: Garantir que os binários embutidos no Appimage (ffmpeg, ffprobe, deno) estejam na porra do PATH, sem isso o sistema fica capado
if getattr(sys, "frozen", False) or os.environ.get("APPIMAGE"):
    bin_dir = os.path.dirname(os.path.abspath(sys.executable))
    os.environ["PATH"] = f"{bin_dir}:{os.environ.get('PATH', '')}"


class YtdlpLogger:
    def __init__(self):
        self.errors = []

    def debug(self, msg):
        pass

    def warning(self, msg):
        pass

    def error(self, msg):
        clean_msg = msg.replace("ERROR:", "").strip()
        self.errors.append(clean_msg)


def format_duration(seconds):
    if not seconds:
        return ""
    seconds = int(seconds)
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


class VideoQueueItem:
    def __init__(self, index: int, title: str, url: str, thumbnail: str, duration: str, on_toggle):
        self.index = index
        self.title = title
        self.url = url

        self.checkbox = ft.Checkbox(value=True, on_change=on_toggle)

        self.thumb = ft.Image(
            src=thumbnail,
            width=96,
            height=54,
            fit=ft.BoxFit.COVER,
            border_radius=6,
        ) if thumbnail else ft.Container(
            width=96,
            height=54,
            bgcolor=ft.Colors.GREY_800,
            border_radius=6,
            alignment=ft.Alignment.CENTER,
            content=ft.Icon(ft.Icons.MOVIE, color=ft.Colors.GREY_500),
        )

        self.status_label = ft.Text(
            f"Aguardando • {duration}" if duration else "Aguardando",
            size=12,
            color=ft.Colors.GREY_400,
        )
        self.progress_bar = ft.ProgressBar(
            value=0,
            height=5,
            color=ft.Colors.GREEN_400,
            bgcolor=ft.Colors.GREY_800,
        )

        self.container = ft.Container(
            padding=10,
            border_radius=10,
            bgcolor=ft.Colors.GREY_900,
            border=ft.Border.all(1, ft.Colors.GREY_800),
            content=ft.Row(
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    self.checkbox,
                    self.thumb,
                    ft.Column(
                        expand=True,
                        spacing=4,
                        controls=[
                            ft.Text(
                                f"{index}. {title}",
                                size=13,
                                weight=ft.FontWeight.W_600,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            self.progress_bar,
                            self.status_label,
                        ],
                    ),
                ],
            ),
        )


async def main(page: ft.Page):
    page.title = "Py4K Video Downloader"
    page.window.width = 760
    page.window.height = 680
    page.window.resizable = True
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 24

    default_dir = (
        "/app/downloads"
        if os.path.exists("/app/downloads")
        else os.path.join(os.path.expanduser("~"), "Downloads")
    )

    queue_items: list[VideoQueueItem] = []
    playlist_title_global: str | None = None
    is_downloading = False
    last_ui_update = 0.0

    clipboard = ft.Clipboard()
    file_picker = ft.FilePicker()

    # --- Controles Superiores ---
    url_input = ft.TextField(
        label="Link do vídeo ou playlist do YouTube",
        hint_text="https://www.youtube.com/watch?v=... ou playlist",
        prefix_icon=ft.Icons.LINK,
        expand=True,
        border=ft.OutlineInputBorder(border_radius=10),
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
        width=165,
        border=ft.OutlineInputBorder(border_radius=10),
        options=[
            ft.dropdown.Option("MP4", "MP4 (Vídeo)"),
            ft.dropdown.Option("MP3", "MP3 (Áudio)"),
        ],
        on_select=on_format_change,
    )

    resolution_dropdown = ft.Dropdown(
        label="Resolução",
        value="1080p",
        width=205,
        border=ft.OutlineInputBorder(border_radius=10),
        options=[
            ft.dropdown.Option("best", "Melhor (4K/2K)"),
            ft.dropdown.Option("1080p", "1080p (Full HD)"),
            ft.dropdown.Option("720p", "720p (HD)"),
            ft.dropdown.Option("480p", "480p"),
            ft.dropdown.Option("360p", "360p"),
        ],
    )

    folder_input = ft.TextField(
        label="Salvar em",
        value=default_dir,
        prefix_icon=ft.Icons.FOLDER,
        expand=True,
        border=ft.OutlineInputBorder(border_radius=10),
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
            global_status.value = "Digite o caminho da pasta diretamente no campo."
            global_status.color = ft.Colors.AMBER_300
            page.update()

    folder_btn = ft.IconButton(
        icon=ft.Icons.FOLDER_OPEN,
        tooltip="Escolher pasta",
        on_click=open_folder_dialog,
    )

    # --- Barra da Lista / Fila ---
    def update_selection_counter(e=None):
        selected = sum(1 for item in queue_items if item.checkbox.value)
        total = len(queue_items)
        selection_label.value = f"Selecionados: {selected} de {total}"
        select_all_cb.value = total > 0 and selected == total
        download_btn.disabled = is_downloading or selected == 0
        download_btn.text = f"Baixar Selecionados ({selected})" if total > 1 else "Baixar Vídeo"
        page.update()

    def toggle_select_all(e):
        checked = bool(select_all_cb.value)
        for item in queue_items:
            if not item.checkbox.disabled:
                item.checkbox.value = checked
        update_selection_counter()

    select_all_cb = ft.Checkbox(
        label="Selecionar todos",
        value=True,
        disabled=True,
        on_change=toggle_select_all,
    )
    selection_label = ft.Text("Nenhum vídeo carregado", size=13, color=ft.Colors.GREY_400)

    queue_list = ft.ListView(
        expand=True,
        spacing=8,
        padding=ft.Padding.only(right=6),
    )

    global_status = ft.Text("Cole um link acima e clique em Analisar.", size=13, color=ft.Colors.GREY_400)

    # --- Etapa 1: Analisar Link / Playlist ---
    def analyze_worker(url: str):
        nonlocal playlist_title_global
        ydl_opts = {
            "extract_flat": "in_playlist",
            "quiet": True,
            "no_warnings": True,
            "ignoreerrors": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                raise ValueError("Não foi possível obter informações deste link.")

            queue_items.clear()
            queue_list.controls.clear()

            if "entries" in info and info["entries"] is not None:
                playlist_title_global = info.get("title") or "Playlist_YouTube"
                entries = [e for e in info["entries"] if e]
                for idx, entry in enumerate(entries, start=1):
                    vid_id = entry.get("id", "")
                    vid_url = entry.get("url") or (f"https://www.youtube.com/watch?v={vid_id}" if vid_id else "")
                    if not vid_url:
                        continue
                    title = entry.get("title") or f"Vídeo {idx}"
                    thumbs = entry.get("thumbnails") or []
                    thumb_url = entry.get("thumbnail") or (thumbs[-1]["url"] if thumbs else "")
                    dur = format_duration(entry.get("duration"))

                    item = VideoQueueItem(idx, title, vid_url, thumb_url, dur, update_selection_counter)
                    queue_items.append(item)
                    queue_list.controls.append(item.container)

                global_status.value = f"Playlist carregada: {playlist_title_global} ({len(queue_items)} vídeos)"
            else:
                playlist_title_global = None
                title = info.get("title") or "Vídeo do YouTube"
                thumb_url = info.get("thumbnail") or ""
                dur = format_duration(info.get("duration"))
                vid_url = info.get("webpage_url") or url

                item = VideoQueueItem(1, title, vid_url, thumb_url, dur, update_selection_counter)
                queue_items.append(item)
                queue_list.controls.append(item.container)

                global_status.value = "Vídeo pronto para download."

            global_status.color = ft.Colors.GREEN_400
            select_all_cb.disabled = len(queue_items) == 0
            update_selection_counter()

        except Exception as ex:
            global_status.value = f"Erro ao analisar link: {ex}"
            global_status.color = ft.Colors.RED_400
        finally:
            analyze_btn.disabled = False
            page.update()

    def start_analyze(e):
        url = (url_input.value or "").strip()
        if not url:
            url_input.error_text = "Cole um link do YouTube"
            page.update()
            return

        url_input.error_text = None
        analyze_btn.disabled = True
        download_btn.disabled = True
        global_status.value = "Analisando link e buscando vídeos..."
        global_status.color = ft.Colors.BLUE_300
        page.update()

        threading.Thread(target=analyze_worker, args=(url,), daemon=True).start()

    # --- Etapa 2: Baixar Vídeos Selecionados ---
    def download_worker(selected_items: list[VideoQueueItem], fmt: str, res: str, base_dir: str):
        nonlocal is_downloading, last_ui_update

        target_dir = base_dir
        if playlist_title_global:
            safe_pl = "".join(c for c in playlist_title_global if c not in r'\/:*?"<>|').strip()
            target_dir = os.path.join(base_dir, safe_pl or "Playlist")

        os.makedirs(target_dir, exist_ok=True)
        ffmpeg_bin = shutil.which("ffmpeg")
        completed_count = 0

        for pos, item in enumerate(selected_items, start=1):
            global_status.value = f"Baixando {pos} de {len(selected_items)}..."
            global_status.color = ft.Colors.BLUE_300
            item.status_label.value = "Iniciando download..."
            item.status_label.color = ft.Colors.BLUE_300
            item.progress_bar.value = None
            page.update()

            logger = YtdlpLogger()

            def make_hook(current_item: VideoQueueItem):
                def hook(d):
                    nonlocal last_ui_update
                    now = time.time()
                    if d["status"] == "downloading":
                        if now - last_ui_update < 0.15:
                            return
                        last_ui_update = now
                        total = d.get("total_bytes") or d.get("total_bytes_estimate")
                        downloaded = d.get("downloaded_bytes", 0)
                        speed = d.get("_speed_str", "").strip()
                        if total:
                            pct = downloaded / total
                            current_item.progress_bar.value = pct
                            speed_txt = f" • {speed}" if speed else ""
                            current_item.status_label.value = f"Baixando: {pct * 100:.1f}%{speed_txt}"
                            current_item.status_label.color = ft.Colors.WHITE
                            page.update()
                    elif d["status"] == "finished":
                        current_item.progress_bar.value = 1.0
                        current_item.status_label.value = "Mesclando áudio/vídeo (FFmpeg)..."
                        current_item.status_label.color = ft.Colors.AMBER_300
                        page.update()

                return hook

            prefix = f"{item.index:02d} - " if playlist_title_global else ""
            ydl_opts = {
                "outtmpl": os.path.join(target_dir, f"{prefix}%(title)s.%(ext)s"),
                "progress_hooks": [make_hook(item)],
                "logger": logger,
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

                ydl_opts.update({"format": video_fmt, "merge_output_format": "mp4"})

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    code = ydl.download([item.url])

                if code == 0 and not logger.errors:
                    item.progress_bar.value = 1.0
                    item.progress_bar.color = ft.Colors.GREEN_400
                    item.status_label.value = "Concluído ✓"
                    item.status_label.color = ft.Colors.GREEN_400
                    completed_count += 1
                else:
                    err = logger.errors[-1] if logger.errors else "Erro ao baixar"
                    item.progress_bar.value = 0
                    item.status_label.value = f"Falha: {err[:75]}"
                    item.status_label.color = ft.Colors.RED_400
            except Exception as ex:
                item.progress_bar.value = 0
                item.status_label.value = f"Erro: {str(ex)[:75]}"
                item.status_label.color = ft.Colors.RED_400

            page.update()

        is_downloading = False
        for item in queue_items:
            item.checkbox.disabled = False
        select_all_cb.disabled = False
        analyze_btn.disabled = False

        global_status.value = f"Finalizado: {completed_count} de {len(selected_items)} baixados em {target_dir}"
        global_status.color = ft.Colors.GREEN_400 if completed_count == len(selected_items) else ft.Colors.AMBER_300
        update_selection_counter()

    def start_download(e):
        nonlocal is_downloading
        selected = [item for item in queue_items if item.checkbox.value]
        if not selected:
            return

        is_downloading = True
        analyze_btn.disabled = True
        download_btn.disabled = True
        select_all_cb.disabled = True
        for item in queue_items:
            item.checkbox.disabled = True
            if not item.checkbox.value:
                item.status_label.value = "Ignorado (desmarcado)"
                item.status_label.color = ft.Colors.GREY_600
        page.update()

        threading.Thread(
            target=download_worker,
            args=(selected, format_dropdown.value, resolution_dropdown.value, folder_input.value.strip()),
            daemon=True,
        ).start()

    analyze_btn = ft.Button(
        "Analisar Link",
        icon=ft.Icons.SEARCH,
        height=48,
        on_click=start_analyze,
    )

    download_btn = ft.Button(
        "Baixar Selecionados",
        icon=ft.Icons.DOWNLOAD,
        bgcolor=ft.Colors.GREEN_600,
        color=ft.Colors.WHITE,
        height=46,
        disabled=True,
        on_click=start_download,
    )

    # --- Layout Principal ---
    page.add(
        ft.Column(
            expand=True,
            spacing=14,
            controls=[
                ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ONDEMAND_VIDEO, color=ft.Colors.GREEN_400, size=30),
                        ft.Text("Py4K Video Downloader", size=22, weight=ft.FontWeight.BOLD),
                    ]
                ),
                ft.Row(controls=[url_input, paste_btn, analyze_btn]),
                ft.Row(controls=[format_dropdown, resolution_dropdown, folder_input, folder_btn]),
                ft.Divider(height=1, color=ft.Colors.GREY_800),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[select_all_cb, selection_label],
                ),
                ft.Container(
                    expand=True,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.BLACK),
                    padding=8,
                    content=queue_list,
                ),
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Container(expand=True, content=global_status),
                        download_btn,
                    ],
                ),
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
