"""MINGA TV: bienvenida y visor IPTV sin controles visibles para Windows.

El catalogo initial.json se consulta desde GitHub al abrir; si no hay
conexion se utiliza la ultima copia local valida. No incluye canales fijos.
"""

import ctypes
from ctypes import wintypes
import importlib
import json
import os
from pathlib import Path
import queue
import random
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import unicodedata
from urllib.request import Request, urlopen

VERSION = "1.0.17"
SLOGAN = "Tu mundo de entretenimiento"
BASE_DIR = Path(__file__).resolve().parent
RAW_BASE = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/TVAPP"
LOGO_URL = f"{RAW_BASE}/assets/minga_tv_logo.png"
LOGO_FILE = BASE_DIR / "assets" / "minga_tv_logo.png"
CHANNELS_URL = f"{RAW_BASE}/initial.json"
CHANNELS_FILE = BASE_DIR / "initial.json"
PLAYLISTS_URL = f"{RAW_BASE}/channels.json"
PLAYLISTS_FILE = BASE_DIR / "channels.json"
USER_DATA_DIR = (Path(os.environ.get("LOCALAPPDATA") or
                      (Path.home() / ".local" / "share")) / "ARCHMOBA" / "TVAPP")
FAVORITES_FILE = USER_DATA_DIR / "favorites.json"
TRASH_FILE = USER_DATA_DIR / "trash.json"
LAST_CHANNEL_FILE = USER_DATA_DIR / "last_channel.json"
SPLASH_MIN_MS = 3000
SPLASH_MAX_MS = 5400
VIDEO_START_TIMEOUT_S = 15
VIDEO_STALL_TIMEOUT_S = 12
RETRY_ALL_CHANNELS_MS = 60000
PLAYER_MONITOR_MS = 1000
MAX_M3U_BYTES = 35 * 1024 * 1024
GLOBAL_M3U_URL = "https://iptv-org.github.io/iptv/index.m3u"
PREVIEW_X, PREVIEW_Y = 9, 9
PREVIEW_WIDTH, PREVIEW_HEIGHT = 116, 72
BG = "#000000"
WHITE = "#f3f7ff"
MUTED = "#a2acc0"
CYAN = "#11a8ff"


def parse_channels(text):
    """Valida el contrato exacto de initial.json, sin modificar su contenido."""
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("initial.json debe ser un objeto JSON.")
    selected = data.get("selected_id")
    if type(selected) is not int or selected < 0:
        raise ValueError("selected_id debe ser un numero entero mayor o igual a cero.")
    channels = data.get("channels")
    if not isinstance(channels, list) or not channels:
        raise ValueError("La lista channels esta vacia o no existe.")
    seen = set()
    for item in channels:
        if not isinstance(item, dict):
            raise ValueError("Hay un canal con formato incorrecto.")
        channel_id = item.get("id")
        url = item.get("url")
        if type(channel_id) is not int or channel_id < 1 or channel_id in seen:
            raise ValueError("Los ids de los canales deben ser unicos y positivos.")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise ValueError("El canal no tiene una URL HTTP(S) valida.")
        if not isinstance(item.get("name"), str) or not item["name"].strip():
            raise ValueError("El canal no tiene nombre.")
        if not isinstance(item.get("headers", {}), dict):
            raise ValueError("Los headers del canal deben ser un objeto JSON.")
        seen.add(channel_id)
    if selected and selected not in seen:
        raise ValueError(f"No existe ningun canal con id {selected}.")
    return data


def choose_channel(data, previous_id=None):
    """selected_id=0: aleatorio; distinto de 0: canal con ese id."""
    channels = data["channels"]
    selected = data["selected_id"]
    if selected:
        return next(item for item in channels if item["id"] == selected)
    candidates = [item for item in channels if item["id"] != previous_id]
    return random.choice(candidates or channels)


def read_initial_json():
    """Consulta remota con anticache, guarda copia y tolera desconexion."""
    try:
        request = Request(
            f"{CHANNELS_URL}?v={time.time_ns()}",
            headers={"User-Agent": "MINGA-TV/1.0", "Cache-Control": "no-cache"},
        )
        with urlopen(request, timeout=8) as response:
            payload = response.read(512 * 1024 + 1)
        if len(payload) > 512 * 1024:
            raise ValueError("initial.json supera el tamano admitido.")
        text = payload.decode("utf-8-sig")
        data = parse_channels(text)
        try:
            CHANNELS_FILE.parent.mkdir(parents=True, exist_ok=True)
            temporary = CHANNELS_FILE.with_suffix(".json.tmp")
            temporary.write_text(text, encoding="utf-8")
            temporary.replace(CHANNELS_FILE)
        except OSError:
            pass  # El video funciona incluso en una carpeta sin permiso de escritura.
        return data, False
    except (OSError, TimeoutError, ValueError, UnicodeError, json.JSONDecodeError):
        try:
            return parse_channels(CHANNELS_FILE.read_text(encoding="utf-8-sig")), True
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("No se pudo obtener initial.json de GitHub ni leer una copia local valida.") from exc


def parse_playlist_catalog(text):
    """Lee las listas M3U configuradas en channels.json, ordenadas por nombre."""
    data = json.loads(text)
    playlists = data.get("playlists") if isinstance(data, dict) else None
    if not isinstance(playlists, list) or not playlists:
        raise ValueError("channels.json no contiene listas M3U.")
    result, seen = [], set()
    for item in playlists:
        if not isinstance(item, dict):
            raise ValueError("Hay una lista M3U con formato incorrecto.")
        name, url = item.get("name"), item.get("url")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Una lista M3U no tiene nombre.")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise ValueError("Una lista M3U no tiene URL valida.")
        key = name.strip().casefold()
        if key in seen:
            raise ValueError("Hay nombres de listas M3U duplicados.")
        seen.add(key)
        result.append({"name": name.strip(), "url": url})
    return sorted(result, key=lambda item: item["name"].casefold())


def read_playlist_catalog():
    """Obtiene channels.json en segundo plano y guarda una copia local util."""
    try:
        request = Request(
            f"{PLAYLISTS_URL}?v={time.time_ns()}",
            headers={"User-Agent": "MINGA-TV/1.0", "Cache-Control": "no-cache"},
        )
        with urlopen(request, timeout=8) as response:
            payload = response.read(128 * 1024 + 1)
        if len(payload) > 128 * 1024:
            raise ValueError("channels.json es demasiado grande.")
        source = payload.decode("utf-8-sig")
        playlists = parse_playlist_catalog(source)
        try:
            temp = PLAYLISTS_FILE.with_suffix(".json.tmp")
            temp.write_text(source, encoding="utf-8")
            temp.replace(PLAYLISTS_FILE)
        except OSError:
            pass
        return playlists, False
    except (OSError, TimeoutError, ValueError, UnicodeError):
        try:
            return parse_playlist_catalog(
                PLAYLISTS_FILE.read_text(encoding="utf-8-sig")
            ), True
        except (OSError, ValueError, UnicodeError) as exc:
            raise RuntimeError("No se pudo cargar channels.json de GitHub.") from exc


def parse_m3u_streams(text):
    """Extrae nombres y URLs de canales desde un M3U extendido."""
    if not text.lstrip("\ufeff \t\r\n").startswith("#EXTM3U"):
        raise ValueError("El enlace no contiene una lista M3U valida.")
    channels = []
    pending = None
    headers = {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            # Encontrar la coma fuera de comillas para respetar nombres y atributos.
            in_quotes = False
            comma = -1
            for pos, char in enumerate(line):
                if char == '"':
                    in_quotes = not in_quotes
                elif char == "," and not in_quotes:
                    comma = pos
                    break
            if comma < 0:
                pending = None
                headers = {}
                continue
            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', line[:comma]))
            pending = (line[comma + 1:].strip()
                       or attrs.get("tvg-name") or "Canal sin nombre")
            headers = {}
        elif line.startswith("#EXTVLCOPT:") and pending:
            key, sep, value = line[11:].partition("=")
            if sep and key.strip().lower() in (
                "http-user-agent", "http-referrer", "user-agent", "referer"
            ):
                headers[key.strip()] = value.strip()
        elif pending and line.startswith(("http://", "https://")):
            channels.append({
                "name": pending[:240],
                "url": line,
                "headers": headers.copy(),
            })
            pending = None
            headers = {}
    return sorted(channels, key=lambda item: item["name"].casefold())


def download_m3u_channels(url):
    """Descarga y analiza un M3U sin tocar la interfaz Tkinter."""
    request = Request(
        url, headers={"User-Agent": "MINGA-TV/1.0", "Cache-Control": "no-cache"}
    )
    with urlopen(request, timeout=14) as response:
        payload = response.read(MAX_M3U_BYTES + 1)
    if len(payload) > MAX_M3U_BYTES:
        raise ValueError("La lista M3U supera 35 MB.")
    channels = parse_m3u_streams(payload.decode("utf-8-sig", errors="replace"))
    if not channels:
        raise ValueError("La lista M3U no contiene canales validos.")
    return channels


def normalized_search(text):
    """Ignora mayusculas y tildes en la busqueda de canales."""
    return "".join(
        char for char in unicodedata.normalize("NFKD", text.casefold())
        if not unicodedata.combining(char)
    )


def read_saved_channels(path):
    """Compatible con favoritos de las versiones anteriores de MINGA TV."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
        items = raw.values() if isinstance(raw, dict) else raw
        if not isinstance(items, (list, type({}.values()))):
            return {}
        return {
            item["url"]: item for item in items
            if isinstance(item, dict)
            and isinstance(item.get("url"), str)
            and item["url"].startswith(("https://", "http://"))
            and isinstance(item.get("name"), str)
        }
    except (OSError, ValueError, UnicodeError, TypeError, KeyError):
        return {}


def save_saved_channels(path, channels):
    """Guardado atomico local; nunca modifica channels.json de GitHub."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(channels, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def read_last_played_channel():
    """Recupera el ultimo canal reproducido correctamente, si es valido."""
    try:
        record = json.loads(LAST_CHANNEL_FILE.read_text(encoding="utf-8-sig"))
        channel = record.get("channel") if isinstance(record, dict) else None
        if (isinstance(channel, dict)
                and isinstance(channel.get("url"), str)
                and channel["url"].startswith(("https://", "http://"))
                and isinstance(channel.get("name"), str)
                and channel["name"].strip()
                and isinstance(channel.get("headers", {}), dict)):
            return dict(channel)
    except (OSError, ValueError, TypeError, UnicodeError):
        pass
    return None


class SlimScrollbar(tk.Canvas):
    """Barra vertical fina y oscura, sin el aspecto gris del control nativo."""

    def __init__(self, parent, command):
        super().__init__(
            parent, width=11, bg="#0a0b0e", bd=0,
            highlightthickness=0, relief="flat",
        )
        self.command = command
        self.first, self.last = 0.0, 1.0
        self.drag_offset = None
        self.thumb = self.create_rectangle(
            2, 0, 9, 25, fill="#505965", outline="", tags="thumb",
        )
        self.bind("<Configure>", lambda _event: self.draw_thumb())
        self.bind("<ButtonPress-1>", self.begin_drag)
        self.bind("<B1-Motion>", self.drag_thumb)
        self.bind("<ButtonRelease-1>", lambda _event: setattr(
            self, "drag_offset", None
        ))
        self.bind("<MouseWheel>", self.scroll_wheel)
        self.bind("<Button-4>", lambda _event: self.command("scroll", -3, "units"))
        self.bind("<Button-5>", lambda _event: self.command("scroll", 3, "units"))

    def set(self, first, last):
        try:
            self.first = max(0.0, min(1.0, float(first)))
            self.last = max(self.first, min(1.0, float(last)))
        except (TypeError, ValueError):
            return
        self.draw_thumb()

    def geometry_thumb(self):
        height = max(1, self.winfo_height())
        span = self.last - self.first
        length = min(height, max(25, int(height * span)))
        top = round(self.first / max(1e-9, 1.0 - span) * (height - length))
        return top, length

    def draw_thumb(self):
        top, length = self.geometry_thumb()
        self.coords(self.thumb, 2, top, 9, top + length)

    def begin_drag(self, event):
        top, length = self.geometry_thumb()
        if top <= event.y <= top + length:
            self.drag_offset = event.y - top
        else:
            self.drag_offset = length / 2
            self.drag_thumb(event)

    def drag_thumb(self, event):
        if self.drag_offset is None:
            return
        _, length = self.geometry_thumb()
        total = max(1, self.winfo_height() - length)
        span = self.last - self.first
        top = max(0, min(total, event.y - self.drag_offset))
        self.command("moveto", max(0.0, (top / total) * (1.0 - span)))

    def scroll_wheel(self, event):
        steps = -int(event.delta / 120) if event.delta else 0
        if steps:
            self.command("scroll", steps * 3, "units")


class TVViewer(tk.Frame):
    """Visor VLC panoramico con Favoritos, Buscar y Papelera."""

    def __init__(self, parent):
        super().__init__(parent, bg=BG, highlightthickness=0)
        self.events = queue.Queue()
        self.data = None
        self.channel = None
        self.player = None
        self.media = None
        self.instance = None
        self.vlc_module = None
        self.dll_handles = []
        self.dead = False
        self.splash_finished = False
        self.request_id = 0
        self.catalog_request = 0
        self.playlists_request = 0
        self.playlists_loading = False
        self.playlist_catalog = None
        self.m3u_request = 0
        self.m3u_cache = {}
        self.current_category = None
        self.current_channels = []
        self.list_mode = "categories"
        self.list_render_token = 0
        self.global_search_url = GLOBAL_M3U_URL
        self.global_search_loading = False
        self.global_search_request = 0
        self.global_search_error = None
        self.search_job = None
        self._ignore_search_change = False
        self.failed_channel_ids = set()
        # Solo se importa initial.json cuando NO existen colecciones locales.
        # Un favorites.json vacio cuenta como configuracion existente para
        # no volver a agregar canales que el usuario elimino voluntariamente.
        self.first_run_pending = (
            not FAVORITES_FILE.exists()
            and not TRASH_FILE.exists()
            and not LAST_CHANNEL_FILE.exists()
        )
        self.startup_auto_active = False
        self.startup_failed_urls = set()
        self.favorites = read_saved_channels(FAVORITES_FILE)
        self.trash = read_saved_channels(TRASH_FILE)
        self.last_played_channel = read_last_played_channel()
        # Un canal enviado a papelera no debe mostrarse en favoritos.
        for url in self.trash:
            self.favorites.pop(url, None)
        self._row_action_job = None
        self._row_action_widgets = []
        self._row_playing_widgets = []
        self._playing_marker_url = None
        self._video_controls_hover = False
        self._pip_hover = False
        self._row_full_names = []
        self._list_reflow_job = None
        self._last_list_width = 0
        self._tooltip_job = None
        self._tooltip_index = None
        self._list_font = tkfont.Font(root=self, family="Segoe UI", size=13)
        self._now_font = tkfont.Font(root=self, family="Segoe UI", size=9)
        self.is_muted = False
        self.fullscreen_active = False
        self._fullscreen_saved = None
        self._fullscreen_escape_down = False
        self.video_started_at = None
        self.video_ready = False
        self.stall_since = None
        self.manual_playback = False
        self.preview_player = None
        self.preview_media = None
        self.preview_instance = None
        self.preview_channel = None
        self.preview_manual_playback = False
        self.preview_started_at = None
        self.preview_video_ready = False
        self.preview_stall_since = None
        self._preview_mouse_down = False
        self._preview_mouse_api = None
        if os.name == "nt":
            try:
                api = ctypes.WinDLL("user32", use_last_error=True)
                api.GetAsyncKeyState.argtypes = (ctypes.c_int,)
                api.GetAsyncKeyState.restype = ctypes.c_short
                api.GetCursorPos.argtypes = (ctypes.POINTER(wintypes.POINT),)
                api.GetCursorPos.restype = wintypes.BOOL
                api.GetForegroundWindow.argtypes = ()
                api.GetForegroundWindow.restype = wintypes.HWND
                api.GetWindowThreadProcessId.argtypes = (
                    wintypes.HWND, ctypes.POINTER(wintypes.DWORD),
                )
                api.GetWindowThreadProcessId.restype = wintypes.DWORD
                self._preview_mouse_api = api
            except (OSError, AttributeError):
                pass

        # Solo el video, sin barra de titulo, detalles ni controles visibles.
        # 380 x 214: visor panoramico 16:9 en la parte superior.
        self.video = tk.Frame(
            self, bg="#000000", height=214, highlightthickness=0,
            borderwidth=0,
        )
        self.video.pack(side="top", fill="x")
        self.video.pack_propagate(False)
        self.fullscreen_exit = tk.Button(
            self.video, text="×", command=self.exit_fullscreen,
            bg="#181818", fg="#ffffff", activebackground="#333333",
            activeforeground="#ffffff", font=("Segoe UI", 17),
            relief="flat", bd=0, highlightthickness=0,
            cursor="hand2",
        )

        # Informacion del canal principal y acciones rapidas.
        self.now_playing = tk.Frame(self, bg=BG, height=34)
        self.now_playing.pack(side="top", fill="x", padx=3, pady=(2, 0))
        self.now_playing.pack_propagate(False)
        self.now_title = tk.StringVar(value="Sin reproducción")
        self.now_actions = tk.Frame(self.now_playing, bg=BG)
        self.now_actions.pack(side="right", padx=(2, 2))
        quick_actions = (
            ("mute", "🔊", self.toggle_mute, "Segoe UI Emoji"),
            ("fullscreen", "⛶", self.toggle_fullscreen, "Segoe UI Symbol"),
            ("favorite", "☆", self.toggle_current_favorite, "Segoe UI Symbol"),
            ("trash", "🗑", self.toggle_current_trash, "Segoe UI Emoji"),
        )
        self.quick_buttons = {}
        self.quick_frames = {}
        for key, glyph, action, font_name in quick_actions:
            slot = tk.Frame(self.now_actions, bg=BG, width=30, height=30)
            slot.pack_propagate(False)
            button = tk.Button(
                slot, text=glyph, command=action,
                bg="#17191d", fg="#ffffff", activebackground="#30353f",
                activeforeground="#ffd000", relief="flat",
                bd=0, highlightthickness=0, cursor="hand2",
                font=(font_name, 12), padx=0, pady=0,
            )
            button.place(x=1, y=1, width=28, height=28)
            button.bind(
                "<Enter>", lambda _event, w=button: w.configure(bg="#292e38"),
            )
            button.bind(
                "<Leave>", lambda _event, w=button: w.configure(bg="#17191d"),
            )
            self.quick_frames[key] = slot
            self.quick_buttons[key] = button
        self.now_indicator = tk.Label(
            self.now_playing, text="", bg=BG, fg="#ffd000",
            font=("Segoe UI Symbol", 11, "bold"),
            width=2, anchor="center",
        )
        self.now_indicator.pack(side="left")
        self.now_label = tk.Label(
            self.now_playing, textvariable=self.now_title,
            bg=BG, fg=WHITE, font=("Segoe UI", 9),
            anchor="w", justify="left", width=1,
        )
        self.now_label.pack(side="left", fill="both", expand=True)
        self.now_playing.update_idletasks()
        # El titulo permanece visible; los botones se muestran al acercar
        # el cursor al video o a esta barra, para aprovechar el espacio.
        self.video.bind("<Enter>", lambda _event: self.set_controls_hover(True), add="+")
        self.video.bind("<Leave>", lambda _event: self.maybe_hide_controls(), add="+")
        self.now_playing.bind("<Enter>", lambda _event: self.set_controls_hover(True), add="+")
        self.now_playing.bind("<Leave>", lambda _event: self.maybe_hide_controls(), add="+")
        self.now_label.bind("<Enter>", lambda _event: self.set_controls_hover(True), add="+")

        # Pestanas de texto, centradas y con linea blanca inferior.
        self.active_tab = "Favoritos"
        self.tab_labels = {}
        self.sections = tk.Frame(self, bg=BG, bd=0, highlightthickness=0)
        self.sections.pack(side="top", fill="x", pady=(5, 0))
        self.sections.columnconfigure(0, weight=1, uniform="tabs")
        self.sections.columnconfigure(1, weight=1, uniform="tabs")
        for column, name in enumerate(("Favoritos", "Buscar")):
            tab = tk.Label(
                self.sections, text=name, bg=BG,
                fg="#ffd000" if name == self.active_tab else "#ffffff",
                font=("Segoe UI", 14, "bold" if name == self.active_tab else "normal"),
                anchor="center", cursor="hand2",
                bd=0, highlightthickness=0, pady=4,
            )
            tab.grid(row=0, column=column, sticky="ew")
            tab.bind("<Button-1>", lambda _event, tab_name=name: self.select_tab(tab_name))
            self.tab_labels[name] = tab
        tk.Frame(self.sections, bg="#ffffff", height=1).grid(
            row=1, column=0, columnspan=2, sticky="ew", pady=(1, 0)
        )

        # El contenido de Buscar aparece solo cuando se elige esa pestana.
        self.tab_content = tk.Frame(self, bg=BG, bd=0, highlightthickness=0)
        self.tab_content.pack(side="top", fill="both", expand=True)
        self.search_panel = tk.Frame(self.tab_content, bg=BG)
        # Cabecera en una sola fila: volver a la izquierda y buscar a la derecha.
        self.search_header = tk.Frame(self.search_panel, bg=BG)
        self.search_header.pack(side="top", fill="x", padx=8, pady=(7, 0))
        self.search_header.columnconfigure(1, weight=1)
        self.back_button = tk.Button(
            self.search_header, text="← Volver a categorías",
            command=self.show_categories,
            bg=BG, fg="#ffd000", activebackground=BG,
            activeforeground="#ffffff",
            font=("Segoe UI", 10, "bold"), anchor="w",
            cursor="hand2", relief="flat", bd=0,
            highlightthickness=0, padx=0, pady=5,
        )
        self.back_button.grid(row=0, column=0, sticky="w", padx=(0, 12))
        self.back_button.grid_remove()  # Oculto en la portada de categorias.

        self.search_query = tk.StringVar()
        # Canvas dibuja bordes redondos sin depender de librerias externas.
        self.search_bar = tk.Canvas(
            self.search_header, bg=BG, height=42, width=140,
            bd=0, highlightthickness=0, relief="flat",
        )
        self.search_bar.grid(row=0, column=1, sticky="ew")
        self.search_inner = tk.Frame(self.search_bar, bg="#181818", bd=0)
        self.search_window = self.search_bar.create_window(
            14, 21, anchor="w", window=self.search_inner,
        )
        tk.Label(
            self.search_inner, text="⌕", bg="#181818", fg="#ffd000",
            font=("Segoe UI Symbol", 17), padx=4,
        ).pack(side="left")
        self.search_entry = tk.Entry(
            self.search_inner, textvariable=self.search_query,
            bg="#181818", fg="#ffffff", insertbackground="#ffffff",
            selectbackground="#385a6c", relief="flat", bd=0,
            highlightthickness=0, font=("Segoe UI", 11), width=1,
        )
        self.search_entry.pack(
            side="left", fill="both", expand=True, ipady=5,
        )
        self.search_clear = tk.Button(
            self.search_inner, text="×", command=self.clear_general_search,
            bg="#181818", fg="#9ec3ff", activebackground="#2a2a2a",
            activeforeground="#ffffff", font=("Segoe UI", 14),
            relief="flat", bd=0, highlightthickness=0, cursor="hand2",
            padx=5, pady=0,
        )
        self.search_clear.pack(side="right")
        self.search_bar.bind(
            "<Configure>", self.draw_rounded_search_bar, add="+",
        )
        self.search_query.trace_add(
            "write", lambda *_: self.on_global_search_changed()
        )
        # Fina linea inferior como en el modelo.
        self.search_header_line = tk.Frame(
            self.search_panel, bg="#494949", height=1,
        )
        self.search_header_line.pack(
            side="top", fill="x", padx=4, pady=(6, 0),
        )
        self.list_frame = tk.Frame(self.search_panel, bg=BG)
        self.list_frame.pack(side="top", fill="both", expand=True)
        self.playlist_list = tk.Listbox(
            self.list_frame, bg=BG, fg=WHITE,
            font=self._list_font, bd=0, relief="flat",
            highlightthickness=0, selectbackground="#1d2630",
            selectforeground="#ffd000", activestyle="none",
            exportselection=False,
        )
        self.playlist_scroll = SlimScrollbar(
            self.list_frame, command=self.playlist_list.yview,
        )
        self.playlist_list.configure(yscrollcommand=self.on_list_scroll)
        self.playlist_list.pack(
            side="left", fill="both", expand=True, padx=(4, 0), pady=(8, 6)
        )
        self.playlist_scroll.pack(
            side="right", fill="y", padx=(1, 3), pady=(8, 6)
        )
        self.row_tooltip = tk.Label(
            self.list_frame, bg="#252a33", fg=WHITE,
            font=("Segoe UI", 10), justify="left",
            anchor="w", padx=9, pady=6, relief="solid",
            bd=1, highlightthickness=0,
        )
        # Los botones se reutilizan para las filas visibles (M3U muy grandes).
        self.row_actions = tk.Frame(self.list_frame, bg=BG, width=66)
        self.row_actions.pack_propagate(False)
        # Reserva la misma columna a la izquierda de TODOS los nombres.
        # El triangulo solo aparece para el canal que reproduce VLC en grande.
        self.playing_gutter = tk.Frame(self.list_frame, bg=BG, width=24)
        self.playing_gutter.pack_propagate(False)
        self.playlist_list.bind("<<ListboxSelect>>", self.on_list_select)
        self.playlist_list.bind(
            "<Configure>", self.on_listbox_resize, add="+",
        )
        self.playlist_list.bind("<Motion>", self.on_list_mouse_move, add="+")
        self.playlist_list.bind("<Leave>", lambda _event: self.hide_row_tooltip(), add="+")
        self.playlist_list.bind("<ButtonPress-1>", lambda _event: self.hide_row_tooltip(), add="+")

        # VLC dibuja sobre su propia superficie; el indicador es un widget
        # hermano y queda encima sin interferir con la reproduccion.
        self.video_surface = tk.Frame(
            self.video, bg=BG, bd=0, highlightthickness=0,
        )
        self.video_surface.place(x=0, y=0, relwidth=1, relheight=1)

        # Segunda superficie VLC: conserva en vivo el canal anterior.
        # Al cambiar canales intercambiamos superficies, no ventanas VLC.
        self.preview_surface = tk.Frame(
            self.video, bg=BG, bd=0, highlightthickness=0,
        )
        self.preview_surface.bind("<Button-1>", lambda _event: self.restore_previous())
        self.preview_border = tk.Frame(
            self.video, bg="#3c434d", bd=0, highlightthickness=0,
        )
        self.preview_surface.bind(
            "<Enter>", lambda _event: self.set_preview_hover(True), add="+"
        )
        self.preview_surface.bind(
            "<Leave>", lambda _event: self.set_preview_hover(False), add="+"
        )
        self.preview_close = tk.Button(
            self.video, text="×", command=self.close_preview,
            bg="#111111", fg="#ffffff", activebackground="#a32020",
            activeforeground="#ffffff", font=("Segoe UI", 13, "bold"),
            relief="flat", bd=0, highlightthickness=0, cursor="hand2",
        )
        self.loading = tk.Canvas(
            self.video, width=68, height=68, bg=BG,
            bd=0, highlightthickness=0,
        )
        self.loading.create_oval(
            12, 12, 56, 56, outline="#213344", width=4,
        )
        self.loading_arc = self.loading.create_arc(
            12, 12, 56, 56, start=90, extent=102,
            style=tk.ARC, outline=CYAN, width=4,
        )
        self.spinner_angle = 90
        self.spinner_job = None
        self.spinner_visible = False
        self.show_loading()

        # Estado interno no visible; los errores no agregan elementos al visor.
        self.status = tk.StringVar(value="")
        self.channel_name = tk.StringVar(value="")
        self.channel_group = tk.StringVar(value="")

        self.show_favorites()
        self.bind("<Destroy>", self.on_destroy, add="+")
        self.after(125, self.poll_events)
        if self._preview_mouse_api is not None:
            self.after(25, self._poll_preview_click)

    def set_controls_hover(self, hovering):
        """Oculta acciones solo al salir del video; mantiene el nombre visible."""
        if self.dead or not hasattr(self, "quick_frames"):
            return
        show = bool(hovering) and not self.fullscreen_active
        if show == self._video_controls_hover:
            return
        self._video_controls_hover = show
        for slot in self.quick_frames.values():
            if show:
                slot.pack(side="left", padx=(2, 1), fill="y")
            else:
                slot.pack_forget()
        self.refresh_now_title()

    def pointer_near_player(self):
        """Detecta el puntero sin depender del HWND nativo de VLC."""
        x, y = self.winfo_pointerx(), self.winfo_pointery()
        vx, vy = self.video.winfo_rootx(), self.video.winfo_rooty()
        ux, uy = self.now_playing.winfo_rootx(), self.now_playing.winfo_rooty()
        video_area = (
            vx <= x < vx + self.video.winfo_width()
            and vy <= y < vy + self.video.winfo_height()
        )
        controls_area = (
            ux <= x < ux + self.now_playing.winfo_width()
            and uy - 4 <= y < uy + self.now_playing.winfo_height()
        )
        return video_area or controls_area

    def maybe_hide_controls(self):
        if self._preview_mouse_api is None and not self.dead:
            self.after(35, lambda: self.set_controls_hover(
                self.pointer_near_player()
            ))

    def set_preview_hover(self, hovering):
        """Contorno amarillo solo al apuntar a la miniatura."""
        if self.dead or not hasattr(self, "preview_border"):
            return
        show = bool(hovering) and self.preview_player is not None
        if show != self._pip_hover:
            self._pip_hover = show
            self.preview_border.configure(
                bg="#ffd000" if show else "#3c434d",
            )

    def _poll_preview_click(self):
        """Mouse nativo: hover y clic en miniatura aunque VLC absorba Tk."""
        if self.dead or self._preview_mouse_api is None:
            return
        try:
            api = self._preview_mouse_api
            foreground_pid = wintypes.DWORD(0)
            api.GetWindowThreadProcessId(
                api.GetForegroundWindow(), ctypes.byref(foreground_pid),
            )
            is_active = foreground_pid.value == os.getpid()
            esc_pressed = bool(api.GetAsyncKeyState(0x1B) & 0x8000)
            if (is_active and esc_pressed and not self._fullscreen_escape_down
                    and self.fullscreen_active):
                self.exit_fullscreen()
            self._fullscreen_escape_down = esc_pressed

            cursor = wintypes.POINT()
            if api.GetCursorPos(ctypes.byref(cursor)):
                x = cursor.x - self.video.winfo_rootx()
                y = cursor.y - self.video.winfo_rooty()
                over_video = (
                    0 <= x < self.video.winfo_width()
                    and 0 <= y < self.video.winfo_height()
                )
                over_controls = (
                    self.now_playing.winfo_rootx() <= cursor.x <
                    self.now_playing.winfo_rootx() + self.now_playing.winfo_width()
                    and self.now_playing.winfo_rooty() - 4 <= cursor.y <
                    self.now_playing.winfo_rooty() + self.now_playing.winfo_height()
                )
                self.set_controls_hover(
                    is_active and (over_video or over_controls)
                )
                over_preview = (
                    is_active and self.preview_player is not None
                    and not self.fullscreen_active
                    and PREVIEW_X <= x < PREVIEW_X + PREVIEW_WIDTH
                    and PREVIEW_Y <= y < PREVIEW_Y + PREVIEW_HEIGHT
                )
                self.set_preview_hover(over_preview)
                over_close = (
                    PREVIEW_X + PREVIEW_WIDTH - 25 <= x
                    < PREVIEW_X + PREVIEW_WIDTH - 2
                    and PREVIEW_Y + 2 <= y < PREVIEW_Y + 25
                )
                pressed = bool(api.GetAsyncKeyState(0x01) & 0x8000)
                if (pressed and not self._preview_mouse_down
                        and over_preview and not over_close):
                    self.restore_previous()
                self._preview_mouse_down = pressed
            else:
                self.set_controls_hover(False)
                self.set_preview_hover(False)
        except (OSError, AttributeError, ValueError, tk.TclError):
            self._preview_mouse_down = False
            self._fullscreen_escape_down = False
        if not self.dead:
            self.after(40, self._poll_preview_click)

    def draw_rounded_search_bar(self, _event=None):
        """Dibuja las esquinas redondeadas y ajusta el campo al ancho."""
        width = self.search_bar.winfo_width()
        height = self.search_bar.winfo_height()
        if width < 42 or height < 20:
            return
        inset = 1
        radius = min(16, (height - 2) // 2)
        left, top = inset, inset
        right, bottom = width - inset, height - inset
        self.search_bar.delete("rounded_search")
        self.search_bar.create_polygon(
            left + radius, top,
            right - radius, top,
            right - radius, top,
            right, top,
            right, top + radius,
            right, top + radius,
            right, bottom - radius,
            right, bottom - radius,
            right, bottom,
            right - radius, bottom,
            right - radius, bottom,
            left + radius, bottom,
            left + radius, bottom,
            left, bottom,
            left, bottom - radius,
            left, bottom - radius,
            left, top + radius,
            left, top + radius,
            left, top,
            left + radius, top,
            fill="#181818", outline="#46515b", width=1,
            smooth=True, splinesteps=20, tags="rounded_search",
        )
        self.search_bar.tag_lower("rounded_search")
        self.search_bar.coords(self.search_window, 14, height / 2)
        self.search_bar.itemconfigure(
            self.search_window,
            width=max(20, width - 28), height=max(20, height - 12),
        )

    def clear_general_search(self):
        """Borra el texto sin salir de la categoria actual."""
        if self.search_query.get():
            self.search_query.set("")

    def on_global_search_changed(self):
        """Filtra la categoria abierta o busca globalmente desde las categorias."""
        if self.dead or self._ignore_search_change:
            return
        if self.search_job is not None:
            try:
                self.after_cancel(self.search_job)
            except tk.TclError:
                pass
            self.search_job = None
        if self.active_tab != "Buscar":
            return
        if not self.search_query.get().strip():
            if self.list_mode in ("channels", "trash"):
                # Al borrar el texto, conservar la categoria en pantalla.
                self.refresh_channel_view()
            else:
                self.show_categories(clear_search=False)
        else:
            self.search_job = self.after(280, self.run_global_search)

    def run_global_search(self):
        """Busqueda contextual: local en una categoria, general fuera de ella."""
        self.search_job = None
        if self.dead or self.active_tab != "Buscar":
            return
        if not self.search_query.get().strip():
            if self.list_mode in ("channels", "trash"):
                self.refresh_channel_view()
            else:
                self.show_categories(clear_search=False)
            return
        if self.list_mode in ("channels", "trash"):
            # No descargar "Todos" ni salir de la categoria seleccionada.
            self.refresh_channel_view()
            return
        self.list_mode = "search_results"
        self.current_category = None
        self.back_button.grid()
        self.set_row_actions_visible(True)
        self.refresh_channel_view()
        self.ensure_global_catalog()

    def ensure_global_catalog(self):
        """Descarga Todos en un hilo; solo una solicitud simultanea."""
        self.global_search_url = next((
            item["url"] for item in (self.playlist_catalog or [])
            if item["name"].casefold() == "todos"
        ), GLOBAL_M3U_URL)
        url = self.global_search_url
        if url in self.m3u_cache:
            self.refresh_channel_view()
            return
        if self.global_search_loading:
            return
        self.global_search_loading = True
        self.global_search_error = None
        self.global_search_request += 1
        token = self.global_search_request
        self.refresh_channel_view()

        def worker():
            try:
                channels = download_m3u_channels(url)
                self.events.put(("global_m3u", token, channels, url))
            except Exception as exc:
                self.events.put(("global_m3u_error", token, str(exc), url))

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def ellipsize(text, max_width, font):
        """Acorta por pixeles, no por caracteres; conserva URL y nombre reales."""
        if max_width < 24 or font.measure(text) <= max_width:
            return text
        suffix = "…"
        low, high = 0, len(text)
        while low < high:
            mid = (low + high + 1) // 2
            if font.measure(text[:mid] + suffix) <= max_width:
                low = mid
            else:
                high = mid - 1
        return text[:low].rstrip() + suffix

    def on_listbox_resize(self, event):
        self.schedule_row_actions()
        if abs(event.width - self._last_list_width) < 3:
            return
        self._last_list_width = event.width
        if self._list_reflow_job is not None:
            try:
                self.after_cancel(self._list_reflow_job)
            except tk.TclError:
                pass
        self._list_reflow_job = self.after(120, self.reflow_channel_titles)

    def reflow_channel_titles(self):
        self._list_reflow_job = None
        if self.dead or not self._row_full_names:
            return
        self._show_rows(self._row_full_names, keep_position=True)

    def show_full_row_tooltip(self, index):
        self._tooltip_job = None
        if (self.dead or self.list_mode == "categories"
                or self._tooltip_index != index
                or index >= len(self._row_full_names)
                or index >= self.playlist_list.size()):
            return
        full_name = self._row_full_names[index]
        if self.playlist_list.get(index) == full_name:
            return
        bbox = self.playlist_list.bbox(index)
        if bbox is None:
            return
        self.row_tooltip.configure(
            text=full_name,
            wraplength=max(140, min(360, self.list_frame.winfo_width() - 24)),
        )
        top = self.playlist_list.winfo_y() + bbox[1]
        proposed = top + bbox[3] + 4
        wanted = self.row_tooltip.winfo_reqheight()
        if proposed + wanted > self.list_frame.winfo_height() - 3:
            proposed = top - wanted - 4
        self.row_tooltip.place(
            x=self.playlist_list.winfo_x() + 5,
            y=max(3, proposed),
        )
        self.row_tooltip.lift()

    def hide_row_tooltip(self):
        if self._tooltip_job is not None:
            try:
                self.after_cancel(self._tooltip_job)
            except tk.TclError:
                pass
            self._tooltip_job = None
        self._tooltip_index = None
        if hasattr(self, "row_tooltip"):
            self.row_tooltip.place_forget()

    def on_list_mouse_move(self, event):
        if self.list_mode == "categories":
            self.hide_row_tooltip()
            return
        index = self.playlist_list.nearest(event.y)
        if (index >= self.playlist_list.size()
                or index >= len(self._row_full_names)):
            self.hide_row_tooltip()
            return
        bbox = self.playlist_list.bbox(index)
        if (bbox is None or event.y < bbox[1]
                or event.y >= bbox[1] + bbox[3]
                or self.playlist_list.get(index) == self._row_full_names[index]):
            self.hide_row_tooltip()
            return
        if index == self._tooltip_index:
            return
        self.hide_row_tooltip()
        self._tooltip_index = index
        self._tooltip_job = self.after(
            450, lambda i=index: self.show_full_row_tooltip(i),
        )

    def on_list_scroll(self, first, last):
        """Actualiza los botones y la barra oscura al desplazarse."""
        self.playlist_scroll.set(first, last)
        self.hide_row_tooltip()
        self.schedule_row_actions()

    def schedule_row_actions(self):
        if self.dead or self._row_action_job is not None:
            return
        self._row_action_job = self.after_idle(self.draw_row_actions)

    def set_playing_marker(self, url=None):
        """Sincroniza el triangulo de la lista y la barra del video grande."""
        if self._playing_marker_url != url:
            self._playing_marker_url = url
            self.schedule_row_actions()
        self.update_now_playing()

    def update_now_playing(self):
        """El nombre y los botones siguen al canal principal, no a la miniatura."""
        if self.dead or not hasattr(self, "now_title"):
            return
        channel = self.channel
        url = channel.get("url") if isinstance(channel, dict) else None
        if url and self.splash_finished:
            self.now_title.set(channel.get("name", "Canal sin nombre"))
        else:
            self.now_title.set("Sin reproducción")
        self.now_indicator.configure(
            text="▶" if url and url == self._playing_marker_url else ""
        )
        self.quick_buttons["mute"].configure(
            text="🔇" if self.is_muted else "🔊",
            fg="#ffd000" if self.is_muted else WHITE,
        )
        self.quick_buttons["fullscreen"].configure(
            text="⛶", fg=WHITE,
        )
        self.quick_buttons["favorite"].configure(
            text="★" if url in self.favorites else "☆",
            fg="#ffd000" if url in self.favorites else WHITE,
            state="normal" if url else "disabled",
        )
        self.quick_buttons["trash"].configure(
            text="↩" if url in self.trash else "🗑",
            fg="#11a8ff" if url in self.trash else "#ef7373",
            state="normal" if url else "disabled",
        )

    def toggle_current_favorite(self):
        if self.channel and self.channel.get("url"):
            self.toggle_favorite(self.channel["url"])

    def toggle_current_trash(self):
        if self.channel and self.channel.get("url"):
            self.toggle_trash(self.channel["url"])

    def toggle_mute(self):
        """Mute global del canal grande; la miniatura siempre sigue muda."""
        if self.dead:
            return
        self.is_muted = not self.is_muted
        self.sync_player_audio()
        self.update_now_playing()

    def toggle_fullscreen(self):
        """Pantalla completa del video; Esc regresa sin reiniciar VLC."""
        if self.dead:
            return
        if self.fullscreen_active:
            self.exit_fullscreen()
            return
        root = self.winfo_toplevel()
        hidden = []
        # El lanzador tiene un bloqueo de tamaño: suspender temporalmente su
        # controlador Configure y restaurarlo al salir del modo completo.
        saved = {
            "root": root,
            "geometry": root.geometry(),
            "minsize": root.minsize(),
            "maxsize": root.maxsize(),
            "resizable": root.resizable(),
            "configure_bind": root.bind("<Configure>"),
            "escape_bind": root.bind("<Escape>"),
            "f11_bind": root.bind("<F11>"),
            "hidden": hidden,
        }
        self._fullscreen_saved = saved
        self.fullscreen_active = True
        try:
            root.bind("<Configure>", "")
            root.minsize(1, 1)
            root.maxsize(root.winfo_screenwidth(), root.winfo_screenheight())
            root.resizable(True, True)
            for widget in root.winfo_children():
                if widget is self.master:
                    continue
                manager = widget.winfo_manager()
                if manager == "pack":
                    hidden.append((widget, manager, widget.pack_info()))
                    widget.pack_forget()
                elif manager == "place":
                    hidden.append((widget, manager, widget.place_info()))
                    widget.place_forget()
                elif manager == "grid":
                    hidden.append((widget, manager, widget.grid_info()))
                    widget.grid_remove()
            self.now_playing.pack_forget()
            self.sections.pack_forget()
            self.tab_content.pack_forget()
            self.video.pack_configure(side="top", fill="both", expand=True)
            root.bind("<Escape>", lambda _event: self.exit_fullscreen())
            root.bind("<F11>", lambda _event: self.exit_fullscreen())
            root.attributes("-fullscreen", True)
            self.fullscreen_exit.place(
                relx=1, x=-12, y=12, anchor="ne", width=34, height=32
            )
            self.layout_video_layers()
            self.fullscreen_exit.lift()
            root.focus_force()
        except (tk.TclError, ValueError):
            self.exit_fullscreen()

    def exit_fullscreen(self):
        """Restablece tamaño, controles y barra original del lanzador."""
        if not self.fullscreen_active:
            return
        saved = self._fullscreen_saved
        self.fullscreen_active = False
        self._fullscreen_saved = None
        if saved is None:
            return
        root = saved["root"]
        try:
            self.fullscreen_exit.place_forget()
            root.attributes("-fullscreen", False)
            self.video.pack_configure(side="top", fill="x", expand=False)
            self.now_playing.pack(
                side="top", fill="x", padx=3, pady=(2, 0), after=self.video
            )
            self.sections.pack(
                side="top", fill="x", pady=(5, 0), after=self.now_playing
            )
            self.tab_content.pack(
                side="top", fill="both", expand=True, after=self.sections
            )
            for widget, manager, info in saved["hidden"]:
                if not widget.winfo_exists():
                    continue
                if manager == "pack":
                    options = {k: v for k, v in info.items() if k != "in"}
                    widget.pack(before=self.master, **options)
                elif manager == "place":
                    widget.place(**info)
                elif manager == "grid":
                    widget.grid(**info)
            root.minsize(*saved["minsize"])
            root.maxsize(*saved["maxsize"])
            root.resizable(*saved["resizable"])
            root.geometry(saved["geometry"])
            self.layout_video_layers()
        except tk.TclError:
            pass
        finally:
            try:
                root.bind("<Configure>", saved["configure_bind"] or "")
                root.bind("<Escape>", saved["escape_bind"] or "")
                root.bind("<F11>", saved["f11_bind"] or "")
            except tk.TclError:
                pass

    def set_row_actions_visible(self, visible):
        if visible:
            if not self.playing_gutter.winfo_manager():
                self.playing_gutter.pack(
                    side="left", fill="y", padx=(8, 0), pady=(8, 6),
                    before=self.playlist_list,
                )
            if not self.row_actions.winfo_manager():
                self.row_actions.pack(
                    side="right", fill="y", padx=(0, 3), pady=(8, 6)
                )
        else:
            self.playing_gutter.pack_forget()
            self.row_actions.pack_forget()
        self.schedule_row_actions()

    def draw_row_actions(self):
        """Dibuja estrella, papelera y ▶ solo en las filas visibles."""
        self._row_action_job = None
        if self.dead:
            return
        if (not self.row_actions.winfo_manager()
                or not self.playing_gutter.winfo_manager()
                or self.list_mode not in (
                    "channels", "favorites", "trash", "search_results"
                )):
            for star, bin_button in self._row_action_widgets:
                star.place_forget()
                bin_button.place_forget()
            for marker in self._row_playing_widgets:
                marker.place_forget()
            return

        height = self.playlist_list.winfo_height()
        if height <= 1:
            return
        first = self.playlist_list.nearest(0)
        last = self.playlist_list.nearest(max(0, height - 1))
        slot = 0
        for index in range(first, min(last + 1, len(self.current_channels))):
            bbox = self.playlist_list.bbox(index)
            if bbox is None:
                continue
            _, y, _, row_height = bbox
            if y + row_height <= 0 or y >= height:
                continue
            if slot == len(self._row_action_widgets):
                star = tk.Button(
                    self.row_actions, bg=BG, fg="#ffffff",
                    activebackground="#20242b", activeforeground="#ffd000",
                    font=("Segoe UI Symbol", 14), relief="flat", bd=0,
                    highlightthickness=0, cursor="hand2", padx=0, pady=0,
                )
                bin_button = tk.Button(
                    self.row_actions, bg=BG, fg="#ef7373",
                    activebackground="#20242b", activeforeground="#ffffff",
                    font=("Segoe UI Emoji", 11), relief="flat", bd=0,
                    highlightthickness=0, cursor="hand2", padx=0, pady=0,
                )
                self._row_action_widgets.append((star, bin_button))
            star, bin_button = self._row_action_widgets[slot]
            url = self.current_channels[index]["url"]
            if slot == len(self._row_playing_widgets):
                self._row_playing_widgets.append(tk.Label(
                    self.playing_gutter, bg=BG, fg="#ffd000",
                    font=("Segoe UI Symbol", 13, "bold"),
                    anchor="center", bd=0, highlightthickness=0,
                ))
            marker = self._row_playing_widgets[slot]
            marker.configure(
                text="▶" if url == self._playing_marker_url else ""
            )
            marked = url in self.favorites
            star.configure(
                text="★" if marked else "☆",
                fg="#ffd000" if marked else "#ffffff",
                command=lambda link=url: self.toggle_favorite(link),
            )
            in_trash = self.list_mode == "trash"
            bin_button.configure(
                text="↩" if in_trash else "🗑",
                fg="#11a8ff" if in_trash else "#ef7373",
                command=lambda link=url: self.toggle_trash(link),
            )
            row_height = max(20, row_height)
            marker.place(x=0, y=y, width=24, height=row_height)
            star.place(x=0, y=y, width=31, height=row_height)
            bin_button.place(x=33, y=y, width=31, height=row_height)
            slot += 1
        for star, bin_button in self._row_action_widgets[slot:]:
            star.place_forget()
            bin_button.place_forget()
        for marker in self._row_playing_widgets[slot:]:
            marker.place_forget()

    def save_collections(self):
        for path, items in (
            (FAVORITES_FILE, self.favorites), (TRASH_FILE, self.trash)
        ):
            try:
                save_saved_channels(path, items)
            except (OSError, TypeError, ValueError) as exc:
                self.status.set("No se pudieron guardar los canales: " + str(exc))

    def saved_channel(self, url):
        for item in self.current_channels:
            if item["url"] == url:
                result = dict(item)
                if not result.get("group"):
                    result["group"] = (
                        self.current_category["name"]
                        if self.current_category else "MINGA TV"
                    )
                return result
        # Los botones bajo el video funcionan aunque la lista muestre
        # otra categoria o el canal provenga de initial.json.
        if isinstance(self.channel, dict) and self.channel.get("url") == url:
            return dict(self.channel)
        if (isinstance(self.preview_channel, dict)
                and self.preview_channel.get("url") == url):
            return dict(self.preview_channel)
        return None

    def toggle_favorite(self, url):
        if url in self.favorites:
            self.favorites.pop(url, None)
        else:
            channel = self.saved_channel(url)
            if channel is None:
                return
            self.trash.pop(url, None)  # Favorito desde Papelera: restaurar.
            self.favorites[url] = channel
        self.save_collections()
        self.update_now_playing()
        # En categorias y resultados generales, mostrar favoritos arriba.
        self.refresh_channel_view(
            keep_position=self.list_mode not in ("channels", "search_results")
        )

    def toggle_trash(self, url):
        if url in self.trash:
            self.trash.pop(url, None)  # Restaurar un canal descartado.
        else:
            channel = self.saved_channel(url)
            if channel is None:
                return
            self.trash[url] = channel
            self.favorites.pop(url, None)
            self.clear_last_played_channel(url)
        self.save_collections()
        self.update_now_playing()
        self.refresh_channel_view(keep_position=True)

    def refresh_channel_view(self, keep_position=False):
        """Recalcula la lista sin reiniciar ni detener el canal en pantalla."""
        if self.list_mode == "favorites":
            self.current_channels = sorted(
                self.favorites.values(), key=lambda item: item["name"].casefold()
            )
            names = [item["name"] for item in self.current_channels]
            if not names:
                names = ["No tienes canales favoritos."]
        elif self.list_mode == "trash":
            terms = (
                normalized_search(self.search_query.get().strip()).split()
                if self.active_tab == "Buscar" else []
            )
            self.current_channels = sorted(
                (
                    item for item in self.trash.values()
                    if all(
                        term in normalized_search(item["name"])
                        for term in terms
                    )
                ),
                key=lambda item: item["name"].casefold(),
            )
            names = [item["name"] for item in self.current_channels]
            if not names:
                names = [
                    "No hay canales en la Papelera que coincidan."
                    if terms else "La Papelera está vacía."
                ]
        elif self.list_mode == "search_results":
            query = normalized_search(self.search_query.get().strip())
            terms = query.split()
            available = {}
            # Incluye favoritos locales y listas abiertas, incluso sin red.
            sources = [self.favorites.values()]
            if self.global_search_url in self.m3u_cache:
                sources.append(self.m3u_cache[self.global_search_url])
            else:
                sources.extend(self.m3u_cache.values())
            for source in sources:
                for item in source:
                    url = item.get("url", "")
                    if url in self.trash or url in available:
                        continue
                    if all(term in normalized_search(item.get("name", ""))
                           for term in terms):
                        available[url] = item
            self.current_channels = sorted(
                available.values(), key=lambda item: (
                    item["url"] not in self.favorites,
                    item["name"].casefold(), item["url"],
                )
            )
            names = [item["name"] for item in self.current_channels]
            if not names:
                if self.global_search_loading:
                    names = ["Buscando en todos los canales..."]
                elif self.global_search_error:
                    names = ["No se pudo descargar el catálogo general."]
                else:
                    names = ["No se encontraron canales."]
        elif self.list_mode == "channels" and self.current_category:
            base = self.m3u_cache.get(
                self.current_category["url"], self.current_channels
            )
            terms = normalized_search(self.search_query.get().strip()).split()
            # Dentro de una categoria, filtrar SOLO su propia lista M3U.
            # Favoritos activos primero; despues el resto por nombre.
            self.current_channels = sorted(
                (
                    item for item in base
                    if item["url"] not in self.trash
                    and all(
                        term in normalized_search(item["name"])
                        for term in terms
                    )
                ),
                key=lambda item: (
                    item["url"] not in self.favorites,
                    item["name"].casefold(),
                    item["url"],
                ),
            )
            names = [item["name"] for item in self.current_channels]
            if not names:
                if self.current_category["url"] not in self.m3u_cache:
                    names = ["Cargando canales de esta categoría..."]
                elif terms:
                    names = ["No se encontraron canales en esta categoría."]
                else:
                    names = ["No hay canales disponibles en esta categoría."]
        else:
            return
        self._show_rows(names, keep_position=keep_position)

    def show_favorites(self):
        self.list_mode = "favorites"
        self.current_category = None
        self.back_button.grid_remove()
        self.search_header.pack_forget()
        self.search_header_line.pack_forget()
        if not self.search_panel.winfo_manager():
            self.search_panel.pack(fill="both", expand=True)
        self.set_row_actions_visible(True)
        self.refresh_channel_view()

    def show_trash(self):
        self.list_mode = "trash"
        self.current_category = {"name": "Papelera"}
        self.back_button.grid()
        self.set_row_actions_visible(True)
        self.refresh_channel_view()

    def select_tab(self, name):
        """Cambia de pestana sin interrumpir el video en directo."""
        if name not in self.tab_labels:
            return
        self.active_tab = name
        for tab_name, label in self.tab_labels.items():
            selected = tab_name == name
            label.configure(
                fg="#ffd000" if selected else "#ffffff",
                font=("Segoe UI", 14, "bold" if selected else "normal"),
            )
        self.search_panel.pack(fill="both", expand=True)
        if name == "Buscar":
            if not self.search_header.winfo_manager():
                self.search_header.pack(
                    side="top", fill="x", padx=8, pady=(7, 0),
                    before=self.list_frame,
                )
            if not self.search_header_line.winfo_manager():
                self.search_header_line.pack(
                    side="top", fill="x", padx=4, pady=(6, 0),
                    before=self.list_frame,
                )
            if self.list_mode == "favorites":
                if self.search_query.get().strip():
                    self.run_global_search()
                else:
                    self.show_categories()
            if self.playlist_catalog is None and not self.playlists_loading:
                self.load_playlist_catalog()
        else:
            self.show_favorites()

    def load_playlist_catalog(self):
        """Descarga las listas M3U solo al entrar en Buscar."""
        if self.dead or self.playlists_loading:
            return
        self.playlists_loading = True
        self.playlists_request += 1
        token = self.playlists_request
        if self.list_mode == "categories":
            self.show_categories(clear_search=False)

        def worker():
            try:
                playlists, offline = read_playlist_catalog()
                self.events.put(("playlists", token, playlists, offline))
            except Exception as exc:
                self.events.put(("playlists_error", token, str(exc), False))

        threading.Thread(target=worker, daemon=True).start()

    def _show_rows(self, names, keep_position=False):
        """Lista por bloques; los nombres largos muestran puntos suspensivos."""
        names = list(names)
        old_index = self.playlist_list.nearest(0) if keep_position else 0
        self.hide_row_tooltip()
        self._row_full_names = names
        self.list_render_token += 1
        token = self.list_render_token
        self.playlist_list.delete(0, tk.END)
        self.playlist_list.yview_moveto(0)

        def add_rows(start=0):
            if self.dead or token != self.list_render_token:
                return
            chunk = names[start:start + 250]
            if chunk:
                if self.list_mode in (
                    "channels", "favorites", "trash", "search_results"
                ):
                    width = self.playlist_list.winfo_width() - 10
                    chunk = [
                        self.ellipsize(value, width, self._list_font)
                        if start + offset < len(self.current_channels)
                        else value
                        for offset, value in enumerate(chunk)
                    ]
                self.playlist_list.insert(tk.END, *chunk)
            if start + 250 < len(names):
                self.after(1, lambda: add_rows(start + 250))
            elif keep_position and names:
                self.playlist_list.yview(min(old_index, len(names) - 1))
            self.schedule_row_actions()

        add_rows()

    def on_playlist_catalog(self, playlists):
        self.playlists_loading = False
        self.playlist_catalog = playlists
        if (self.active_tab == "Buscar" and self.list_mode == "categories"
                and not self.search_query.get().strip()):
            self.show_categories(clear_search=False)

    def show_categories(self, clear_search=True):
        """Regresa a las categorias y limpia la busqueda activa."""
        if clear_search and self.search_query.get():
            self._ignore_search_change = True
            try:
                self.search_query.set("")
            finally:
                self._ignore_search_change = False
        if self.search_job is not None:
            try:
                self.after_cancel(self.search_job)
            except tk.TclError:
                pass
            self.search_job = None
        self.m3u_request += 1  # Descarta respuestas de categorias abandonadas.
        self.list_mode = "categories"
        self.current_category = None
        self.current_channels = []
        self.back_button.grid_remove()
        self.set_row_actions_visible(False)
        names = [item["name"] for item in (self.playlist_catalog or [])]
        names.append("Papelera")  # Siempre al final, incluso sin conexion.
        self._show_rows(names)

    def on_list_select(self, _event):
        if self.dead or self.active_tab not in ("Buscar", "Favoritos"):
            return
        selection = self.playlist_list.curselection()
        if not selection:
            return
        index = selection[0]
        if self.list_mode == "categories":
            entries = self.playlist_catalog or []
            if index == len(entries):
                self.show_trash()
            elif index < len(entries):
                self.open_category(entries[index])
        elif self.list_mode in ("channels", "favorites", "trash", "search_results"):
            if index < len(self.current_channels):
                self.play_from_search(self.current_channels[index])

    def play_from_search(self, stream):
        """Abre el canal y conserva fija la miniatura mientras este visible."""
        if self.dead or not isinstance(stream, dict):
            return
        if self.channel and self.channel.get("url") == stream.get("url"):
            return
        # Si seleccionan el canal anclado, lo abrimos y cerramos su miniatura.
        if (self.preview_player is not None and self.preview_channel
                and self.preview_channel.get("url") == stream.get("url")):
            self.restore_previous()
            return
        # Solo capturar el canal actual si no existe una miniatura anclada.
        if self.player is not None and self.preview_player is None:
            self.keep_current_as_preview()
        self.channel = dict(stream)
        self.manual_playback = True
        self.startup_auto_active = False
        self.startup_failed_urls.clear()
        self.channel_name.set(self.channel["name"])
        group = self.channel.get("group") or (
            self.current_category["name"] if self.current_category else self.active_tab
        )
        self.channel["group"] = group
        self.channel_group.set(group)
        if self.splash_finished:
            self.play_current()

    def open_category(self, category):
        """Al pulsar una categoria, muestra sus canales sin parar el video."""
        self.current_category = category
        self.current_channels = []
        self.list_mode = "channels"
        self.back_button.grid()
        self.set_row_actions_visible(True)
        self.m3u_request += 1
        token = self.m3u_request
        self._show_rows(["Cargando canales de " + category["name"] + "..."])
        url = category["url"]
        if url in self.m3u_cache:
            self.on_category_channels(self.m3u_cache[url])
            return

        def worker():
            try:
                channels = download_m3u_channels(url)
                self.events.put(("m3u", token, channels, url))
            except Exception as exc:
                self.events.put(("m3u_error", token, str(exc), url))

        threading.Thread(target=worker, daemon=True).start()

    def on_category_channels(self, channels):
        if self.current_category is None or self.list_mode != "channels":
            return
        self.current_channels = channels
        self.refresh_channel_view()

    def layout_video_layers(self):
        """Coloca la miniatura por encima del reproductor principal."""
        if self.dead:
            return
        try:
            # place conserva medidas anteriores si no se reinician.
            self.video_surface.place(
                x=0, y=0, width=0, height=0, relwidth=1, relheight=1
            )
            self.video_surface.lift()
            if self.preview_player is not None and not self.fullscreen_active:
                self.preview_border.place(
                    x=PREVIEW_X - 2, y=PREVIEW_Y - 2,
                    width=PREVIEW_WIDTH + 4, height=PREVIEW_HEIGHT + 4,
                )
                self.preview_border.lift()
                self.preview_surface.place(
                    x=PREVIEW_X, y=PREVIEW_Y,
                    width=PREVIEW_WIDTH, height=PREVIEW_HEIGHT,
                    relwidth=0, relheight=0,
                )
                self.preview_surface.lift()
                self.preview_close.place(
                    x=PREVIEW_X + PREVIEW_WIDTH - 25, y=PREVIEW_Y + 2,
                    width=23, height=23,
                )
                self.preview_close.lift()
            else:
                self.preview_surface.place_forget()
                self.preview_border.place_forget()
                self.preview_close.place_forget()
            if self.spinner_visible:
                self.loading.tk.call("raise", str(self.loading))
        except tk.TclError:
            pass

    def sync_player_audio(self):
        """Audio exclusivo del video grande, siempre que no este silenciado.

        VLC puede restablecer el audio al crear una salida nueva. Ademas del
        estado mute, ponemos volumen 0 a la miniatura y recuperamos 100 al
        devolverla al reproductor grande. Nunca silenciamos el video en si.
        """
        # Mute y volumen se aplican por separado: si VLC rechaza uno,
        # el otro aun puede mantener silenciada la vista secundaria.
        for player, silenced in (
            (self.preview_player, True),
            (self.player, self.is_muted),
        ):
            if player is None:
                continue
            for method, value in (
                ("audio_set_volume", 0 if silenced else 100),
                ("audio_set_mute", silenced),
            ):
                try:
                    getattr(player, method)(value)
                except (OSError, AttributeError, RuntimeError):
                    pass

    def close_preview(self):
        """Cierra la miniatura y libera el reproductor secundario."""
        player, media, instance = (
            self.preview_player, self.preview_media, self.preview_instance
        )
        self.preview_player = self.preview_media = self.preview_instance = None
        self.preview_channel = None
        self.preview_manual_playback = False
        self.preview_started_at = None
        self.preview_video_ready = False
        self.preview_stall_since = None
        self.set_preview_hover(False)
        for resource, method in (
            (player, "stop"), (player, "release"),
            (media, "release"), (instance, "release"),
        ):
            if resource is not None:
                try:
                    getattr(resource, method)()
                except Exception:
                    pass
        if not self.dead:
            self.layout_video_layers()

    def keep_current_as_preview(self):
        """Fija el canal actual una sola vez; no reemplaza una miniatura abierta."""
        if self.player is None or self.preview_player is not None:
            return
        # Silenciar ANTES de mover el player a la miniatura.
        try:
            self.player.audio_set_mute(True)
            self.player.audio_set_volume(0)
        except (OSError, AttributeError, RuntimeError):
            pass
        self.preview_channel = self.channel
        self.preview_manual_playback = self.manual_playback
        self.preview_player, self.preview_media, self.preview_instance = (
            self.player, self.media, self.instance,
        )
        self.preview_started_at = self.video_started_at
        self.preview_video_ready = self.video_ready
        self.preview_stall_since = self.stall_since
        self.player = self.media = self.instance = None
        self.video_started_at = None
        self.video_ready = False
        self.stall_since = None
        self.video_surface, self.preview_surface = (
            self.preview_surface, self.video_surface,
        )
        self.layout_video_layers()
        self.sync_player_audio()
        # El canal anterior ahora esta solo en la miniatura, no en grande.
        self.set_playing_marker(None)

    def restore_previous(self):
        """Abre el canal anclado a pantalla completa y retira la miniatura."""
        if self.dead or self.preview_player is None:
            return
        self.request_id += 1
        token = self.request_id

        # Cerramos solamente el video grande; el de la miniatura sigue vivo.
        self.release_player()
        self.channel = self.preview_channel
        self.manual_playback = self.preview_manual_playback
        self.player, self.media, self.instance = (
            self.preview_player, self.preview_media, self.preview_instance,
        )
        self.video_started_at, self.video_ready, self.stall_since = (
            self.preview_started_at, self.preview_video_ready,
            self.preview_stall_since,
        )
        self.preview_player = self.preview_media = self.preview_instance = None
        self.preview_channel = None
        self.preview_manual_playback = False
        self.preview_started_at = None
        self.preview_video_ready = False
        self.preview_stall_since = None

        # La superficie de la miniatura pasa al visor principal. Ya no queda PiP.
        self.video_surface, self.preview_surface = (
            self.preview_surface, self.video_surface,
        )
        self.layout_video_layers()
        self.sync_player_audio()
        self.set_playing_marker(
            self.channel.get("url") if self.video_ready else None
        )
        if self.video_ready:
            self.remember_playing_channel()
        self.channel_name.set(self.channel["name"])
        self.channel_group.set(self.channel.get("group", "Canal anterior"))
        self.status.set("En vivo · " + self.channel["name"])
        if self.video_ready:
            self.hide_loading()
        else:
            self.show_loading()
        self.after(PLAYER_MONITOR_MS, lambda: self.monitor_player(token))

    def show_loading(self):
        """Muestra el anillo animado en el centro del area de video."""
        if self.dead:
            return
        self.spinner_visible = True
        self.loading.place(relx=0.5, rely=0.5, anchor="center")
        self.loading.tk.call("raise", str(self.loading))
        if self.spinner_job is None:
            self.animate_loading()

    def animate_loading(self):
        self.spinner_job = None
        if self.dead or not self.spinner_visible:
            return
        self.spinner_angle = (self.spinner_angle - 18) % 360
        self.loading.itemconfigure(self.loading_arc, start=self.spinner_angle)
        self.spinner_job = self.after(65, self.animate_loading)

    def hide_loading(self):
        """Retira y detiene la animacion cuando aparece el video."""
        self.spinner_visible = False
        if self.spinner_job is not None:
            try:
                self.after_cancel(self.spinner_job)
            except tk.TclError:
                pass
            self.spinner_job = None
        try:
            self.loading.place_forget()
        except tk.TclError:
            pass  # El widget puede estar destruido al cerrar o recargar la vista.

    def startup(self):
        self.reload_catalog()

    def finish_splash(self):
        self.splash_finished = True
        if self.channel is not None:
            self.play_current()

    def reload_catalog(self):
        if self.dead:
            return
        self.catalog_request += 1
        token = self.catalog_request
        self.show_loading()
        self.status.set("Leyendo initial.json desde GitHub...")

        def worker():
            try:
                data, offline = read_initial_json()
                self.events.put(("catalog", token, data, offline))
            except Exception as exc:
                self.events.put(("catalog_error", token, str(exc), False))

        threading.Thread(target=worker, daemon=True).start()

    def remember_playing_channel(self):
        """Guarda el canal grande SOLO cuando VLC confirma video real."""
        channel = self.channel
        if (self.dead or self.player is None or not self.video_ready
                or not isinstance(channel, dict)):
            return
        url = channel.get("url")
        if not isinstance(url, str) or url in self.trash:
            return
        if (self.last_played_channel is not None
                and self.last_played_channel.get("url") == url):
            return  # No escribir el disco cada segundo de reproduccion.
        record = dict(channel)
        try:
            save_saved_channels(LAST_CHANNEL_FILE, {"channel": record})
        except (OSError, TypeError, ValueError) as exc:
            self.status.set("No se pudo guardar el ultimo canal: " + str(exc))
            return
        self.last_played_channel = record

    def clear_last_played_channel(self, url):
        """Una emisora en Papelera no puede ser el inicio automatico."""
        if (self.last_played_channel is None
                or self.last_played_channel.get("url") != url):
            return
        self.last_played_channel = None
        try:
            LAST_CHANNEL_FILE.unlink(missing_ok=True)
        except OSError:
            pass  # La comprobacion de Papelera tambien protege el reinicio.

    def import_initial_favorites_once(self, data):
        """Primera instalacion: guarda TODOS los canales del initial.json."""
        if not self.first_run_pending:
            return False
        self.first_run_pending = False
        imported = False
        for item in data["channels"]:
            url = item["url"]
            if url not in self.trash:
                self.favorites.setdefault(url, dict(item))
                imported = True
        if not imported:
            return False
        try:
            save_saved_channels(FAVORITES_FILE, self.favorites)
        except (OSError, TypeError, ValueError) as exc:
            # Se puede reproducir aunque Windows bloquee el guardado.
            self.status.set("No se pudieron guardar los favoritos iniciales: " + str(exc))
        if self.list_mode == "favorites":
            self.refresh_channel_view()
        self.update_now_playing()
        return True

    def on_catalog(self, data, offline):
        old_id = self.channel.get("id") if self.channel else None
        self.data = data
        first_run = self.import_initial_favorites_once(data)
        if self.manual_playback:
            return  # No reemplazar un canal elegido por el usuario.
        self.failed_channel_ids.clear()
        self.startup_failed_urls.clear()
        self.startup_auto_active = False
        source_label = ""
        last = self.last_played_channel
        favorites = [
            item for item in self.favorites.values()
            if item["url"] not in self.trash
        ]
        if first_run and favorites:
            # Primera vez: todos los initial.json son Favoritos; elegir uno.
            self.channel = dict(random.choice(favorites))
            source_label = "Favorito aleatorio (primera vez)"
            self.startup_auto_active = True
        elif last is not None and last["url"] not in self.trash:
            # Siguientes inicios: reproducir incluso si no estaba en Favoritos.
            self.channel = dict(last)
            source_label = "Ultimo canal reproducido"
            self.startup_auto_active = True
        elif favorites:
            # Sin ultimo canal valido (o enviado a Papelera).
            self.channel = dict(random.choice(favorites))
            source_label = "Favorito aleatorio"
            self.startup_auto_active = True
        else:
            # Mantener la seleccion original cuando no hay favoritos guardados,
            # sin volver a ofrecer ningun canal que este en Papelera.
            available = [
                item for item in data["channels"]
                if item["url"] not in self.trash
            ]
            selected = data["selected_id"]
            fixed = next(
                (item for item in available if item["id"] == selected), None
            ) if selected else None
            candidates = [
                item for item in available if item.get("id") != old_id
            ]
            self.channel = dict(
                fixed or random.choice(candidates or available)
            ) if available else None
            source_label = ("Canal fijo" if fixed else "Seleccion aleatoria")
        if self.channel is None:
            self.channel_name.set("")
            self.channel_group.set("")
            self.update_now_playing()
            self.hide_loading()
            self.status.set("No hay canales fuera de la Papelera para iniciar.")
            return
        self.channel_name.set(self.channel["name"])
        label = self.channel.get("group", "General") + "  ·  " + source_label
        if offline:
            label += "  ·  Copia local"
        self.channel_group.set(label)
        self.update_now_playing()
        if self.splash_finished:
            self.play_current()
        else:
            self.status.set("Canal seleccionado. Abriendo después de la bienvenida...")

    def another_channel(self):
        if self.data is None or self.data["selected_id"] != 0:
            return
        if len(self.data["channels"]) < 2:
            return
        previous = self.channel["id"] if self.channel else None
        self.channel = choose_channel(self.data, previous_id=previous)
        self.channel_name.set(self.channel["name"])
        self.channel_group.set(self.channel.get("group", "General") + "  ·  Selección aleatoria")
        self.play_current()

    def replay_current(self):
        if self.channel is not None:
            self.play_current()

    def channel_failed(self, reason):
        """Si falla el ultimo canal, intenta otros favoritos sin repetirlos."""
        failed = self.channel
        self.release_player()
        self.show_loading()
        self.status.set(reason)
        if self.manual_playback:
            if self.preview_player is not None:
                self.restore_previous()
                self.status.set("Se restauro el canal anterior: " + self.channel["name"])
            else:
                self.hide_loading()
            return
        if self.startup_auto_active and failed is not None:
            self.startup_failed_urls.add(failed["url"])
            candidates = [
                item for item in self.favorites.values()
                if item["url"] not in self.trash
                and item["url"] not in self.startup_failed_urls
            ]
            if candidates:
                self.channel = dict(random.choice(candidates))
                self.channel_name.set(self.channel["name"])
                self.channel_group.set(
                    self.channel.get("group", "General") + "  ·  Favorito alternativo"
                )
                self.play_current()
                return
            # No reabrir automaticamente el canal fallido desde initial.json.
            self.startup_auto_active = False
            self.channel = None
            self.channel_name.set("")
            self.update_now_playing()
            self.hide_loading()
            self.status.set("No hay favoritos disponibles con señal.")
            return
        if self.dead or failed is None or self.data is None:
            self.hide_loading()
            return
        if self.data["selected_id"] != 0:
            self.hide_loading()
            return  # Respetar los canales fijos seleccionados en initial.json.

        failed_id = failed.get("id")
        if isinstance(failed_id, int):
            self.failed_channel_ids.add(failed_id)
        available = [
            item for item in self.data["channels"]
            if item["id"] not in self.failed_channel_ids
            and item["url"] not in self.trash
            and item["url"] != failed.get("url")
        ]
        if available:
            self.channel = dict(random.choice(available))
            self.channel_name.set(self.channel["name"])
            self.channel_group.set(
                self.channel.get("group", "General") + "  ·  Selección aleatoria"
            )
            self.play_current()
            return

        # Si todos fallan, releer initial.json mas tarde, sin bucle rapido.
        self.channel = None
        self.channel_name.set("")
        self.update_now_playing()
        self.status.set("No hay canales con video. Nuevo intento en 60 segundos.")
        catalog_token = self.catalog_request

        def retry_catalog():
            if (not self.dead and self.channel is None
                    and self.catalog_request == catalog_token):
                self.reload_catalog()

        self.after(RETRY_ALL_CHANNELS_MS, retry_catalog)

    def _prepare_vlc_windows(self):
        if not sys.platform.startswith("win"):
            return
        folders = []
        for variable in ("ProgramW6432", "ProgramFiles", "ProgramFiles(x86)"):
            home = os.environ.get(variable)
            if home:
                folders.append(Path(home) / "VideoLAN" / "VLC")
        for folder in folders:
            dll = folder / "libvlc.dll"
            if not dll.is_file():
                continue
            if hasattr(os, "add_dll_directory"):
                try:
                    self.dll_handles.append(os.add_dll_directory(str(folder)))
                except OSError:
                    pass
            os.environ.setdefault("PYTHON_VLC_LIB_PATH", str(dll))
            os.environ.setdefault("PYTHON_VLC_MODULE_PATH", str(folder / "plugins"))
            break

    def play_current(self):
        if self.dead or self.channel is None or not self.splash_finished:
            return
        self.request_id += 1
        token = self.request_id
        self.release_player()
        self.update_now_playing()
        self.show_loading()
        self.status.set("Preparando reproducción de " + self.channel["name"] + "...")
        self._prepare_vlc_windows()

        def load_vlc():
            try:
                try:
                    module = importlib.import_module("vlc")
                except ModuleNotFoundError:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                         "--no-input", "python-vlc"],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, timeout=120, check=False,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    if result.returncode != 0:
                        raise RuntimeError("No se pudo instalar python-vlc mediante pip.")
                    importlib.invalidate_caches()
                    module = importlib.import_module("vlc")
                self.events.put(("vlc", token, module, None))
            except Exception as exc:
                self.events.put(("vlc", token, None, str(exc)))

        if self.vlc_module is not None:
            self.after(0, lambda: self.start_embedded(self.vlc_module, token))
        else:
            threading.Thread(target=load_vlc, daemon=True).start()

    def start_embedded(self, module, token):
        if token != self.request_id or self.dead or self.channel is None:
            return
        try:
            self.vlc_module = module
            self.video_surface.update_idletasks()
            instance = module.Instance(
                "--quiet", "--network-caching=1500", "--live-caching=1500",
                "--no-video-title-show", "--no-video-deco",
            )
            if instance is None:
                raise RuntimeError("No se pudo inicializar libVLC.")
            player = instance.media_player_new()
            media = instance.media_new(self.channel["url"])
            for key, value in self.channel.get("headers", {}).items():
                if not isinstance(value, str):
                    continue
                normalized = key.lower()
                if normalized in ("http-user-agent", "user-agent"):
                    media.add_option(":http-user-agent=" + value)
                if normalized in ("http-referrer", "referer"):
                    media.add_option(":http-referrer=" + value)
            player.set_media(media)
            if sys.platform.startswith("win"):
                player.set_hwnd(self.video_surface.winfo_id())
            elif sys.platform == "darwin":
                player.set_nsobject(self.video_surface.winfo_id())
            else:
                player.set_xwindow(self.video_surface.winfo_id())
            self.instance, self.player, self.media = instance, player, media
            self.video_started_at = time.monotonic()
            self.video_ready = False
            self.stall_since = None
            if player.play() == -1:
                raise RuntimeError("VLC no pudo iniciar la transmisión.")
            self.sync_player_audio()
            self.status.set("Conectando a la señal de video...")
            self.after(PLAYER_MONITOR_MS, lambda: self.monitor_player(token))
        except Exception as exc:
            self.channel_failed("No se pudo abrir el canal: " + str(exc)[:120])

    def monitor_player(self, token):
        if self.dead or token != self.request_id or self.player is None:
            return
        try:
            # VLC puede restablecer el volumen mientras conecta o cambia pista.
            # Volvemos a imponer miniatura muda; sonido solo en video grande.
            self.sync_player_audio()
            now = time.monotonic()
            state = str(self.player.get_state()).lower()
            if any(value in state for value in ("error", "ended", "stopped")):
                self.channel_failed("La transmisión falló o terminó.")
                return

            # Playing puede aparecer antes de que haya fotogramas de video.
            # has_vout comprueba que VLC haya creado una salida de video real.
            try:
                video_available = self.player.has_vout() > 0
            except (AttributeError, OSError):
                video_available = "playing" in state

            if "playing" in state and video_available:
                just_started = not self.video_ready
                self.video_ready = True
                self.stall_since = None
                if just_started:
                    # VLC puede reiniciar el mute al empezar un flujo nuevo.
                    self.sync_player_audio()
                    # Memorizar solo transmisiones comprobadas, nunca al elegir.
                    self.remember_playing_channel()
                if just_started:
                    self.startup_failed_urls.clear()
                self.set_playing_marker(self.channel.get("url"))
                self.hide_loading()
                self.status.set("En vivo · " + self.channel["name"])
            elif not self.video_ready:
                self.set_playing_marker(None)
                self.show_loading()
                if (self.video_started_at is not None
                        and now - self.video_started_at >= VIDEO_START_TIMEOUT_S):
                    self.channel_failed("La señal tardó demasiado en mostrar video.")
                    return
                self.status.set("Cargando señal en directo...")
            else:
                self.set_playing_marker(None)
                self.show_loading()
                if self.stall_since is None:
                    self.stall_since = now
                if now - self.stall_since >= VIDEO_STALL_TIMEOUT_S:
                    self.channel_failed("La reproducción dejó de responder.")
                    return
                self.status.set("Recuperando señal de video...")
        except Exception as exc:
            self.channel_failed("Error al comprobar video: " + str(exc)[:120])
            return
        self.after(PLAYER_MONITOR_MS, lambda: self.monitor_player(token))

    def stop_current(self):
        self.request_id += 1
        self.release_player()
        self.hide_loading()
        if not self.dead:
            self.status.set("Reproducción detenida.")

    def release_player(self):
        player, media, instance = self.player, self.media, self.instance
        self.player = self.media = self.instance = None
        self.set_playing_marker(None)
        self.video_started_at = None
        self.video_ready = False
        self.stall_since = None
        for resource, method in ((player, "stop"), (player, "release"),
                                 (media, "release"), (instance, "release")):
            if resource is not None:
                try:
                    getattr(resource, method)()
                except Exception:
                    pass

    def poll_events(self):
        if self.dead:
            return
        try:
            while True:
                event, token, value, extra = self.events.get_nowait()
                if event == "catalog" and token == self.catalog_request:
                    self.on_catalog(value, extra)
                elif event == "catalog_error" and token == self.catalog_request:
                    self.hide_loading()
                    self.status.set(value)
                    self.channel_name.set("No se pudo abrir initial.json")
                elif event == "playlists" and token == self.playlists_request:
                    self.on_playlist_catalog(value)
                elif event == "playlists_error" and token == self.playlists_request:
                    self.playlists_loading = False
                    if self.active_tab == "Buscar" and self.list_mode == "categories":
                        self.show_categories()
                elif event == "global_m3u" and token == self.global_search_request:
                    self.global_search_loading = False
                    self.global_search_error = None
                    self.m3u_cache[extra] = value
                    if self.active_tab == "Buscar" and self.list_mode == "search_results":
                        self.refresh_channel_view()
                elif event == "global_m3u_error" and token == self.global_search_request:
                    self.global_search_loading = False
                    self.global_search_error = str(value)
                    if self.active_tab == "Buscar" and self.list_mode == "search_results":
                        self.refresh_channel_view()
                elif event == "m3u" and token == self.m3u_request:
                    if self.current_category and extra == self.current_category["url"]:
                        self.m3u_cache[extra] = value
                        self.on_category_channels(value)
                elif event == "m3u_error" and token == self.m3u_request:
                    if self.current_category and extra == self.current_category["url"]:
                        self._show_rows([
                            "No se pudieron cargar los canales.",
                            str(value)[:100],
                        ])
                elif event == "vlc" and token == self.request_id:
                    if value is None:
                        self.hide_loading()
                        self.status.set("Instala VLC Desktop en Windows. " + str(extra)[:110])
                    else:
                        self.start_embedded(value, token)
        except queue.Empty:
            pass
        self.after(125, self.poll_events)

    def on_destroy(self, event):
        if event.widget is not self:
            return
        if self.fullscreen_active:
            self.exit_fullscreen()
        self.hide_loading()
        self.dead = True
        self.request_id += 1
        self.catalog_request += 1
        self.playlists_request += 1
        self.m3u_request += 1
        self.list_render_token += 1
        if self.search_job is not None:
            try:
                self.after_cancel(self.search_job)
            except tk.TclError:
                pass
            self.search_job = None
        self.global_search_request += 1
        self.release_player()
        self.close_preview()
        for handle in self.dll_handles:
            try:
                handle.close()
            except OSError:
                pass
        self.dll_handles.clear()


def ensure_launcher_toolbar(window, body):
    """Restaura la barra blanca incluso si app.py local es una version anterior."""
    if not isinstance(window, tk.Tk):
        return None, None

    # La version original tiene barra con etiqueta de estado y boton.
    for child in window.winfo_children():
        if child is body or not isinstance(child, tk.Frame):
            continue
        widgets = child.winfo_children()
        if (any(isinstance(w, tk.Button) for w in widgets)
                and any(isinstance(w, tk.Label) for w in widgets)):
            if child.winfo_manager() != "pack":
                child.pack(side="top", fill="x", before=body)
            return child, None

    # Compatibilidad OTA: algunos app.py antiguos solo tienen boton flotante.
    old_button = next((
        child for child in window.winfo_children()
        if isinstance(child, tk.Button)
        and str(child.cget("text")) in ("↻", "⟳")
        and child.cget("command")
    ), None)
    if old_button is None:
        return None, None

    bar = getattr(window, "_minga_tv_toolbar_compat", None)
    if bar is None or not bar.winfo_exists():
        bar = tk.Frame(window, bg="#ffffff", height=54)
        bar.pack(side="top", fill="x", before=body)
        bar.pack_propagate(False)
        status = tk.Label(
            bar, text="Comprobando actualizaciones...",
            bg="#ffffff", fg="#475467", anchor="w", justify="left",
            font=("Segoe UI", 9), wraplength=294,
        )
        try:
            variables = window.tk.call("info", "globals", "PY_VAR*")
            if isinstance(variables, str):
                variables = window.tk.splitlist(variables)
            variables = sorted(
                (name for name in variables
                 if name.startswith("PY_VAR") and name[6:].isdigit()),
                key=lambda name: int(name[6:]),
            )
            if variables:
                status.configure(textvariable=variables[0])
        except tk.TclError:
            pass
        status.pack(side="left", fill="both", expand=True, padx=(9, 54), pady=5)
        window._minga_tv_toolbar_compat = bar

    # Conservamos EL MISMO boton original y su callback de actualizacion.
    old_button.configure(
        bg="#ffffff", fg="#087f91",
        activebackground="#e9f6f7", activeforeground="#075e6e",
        font=("Segoe UI Symbol", 20, "bold"),
        relief="flat", bd=0, highlightthickness=0,
    )
    old_button.place(relx=1.0, x=-10, y=7, anchor="ne", width=38, height=40)
    return bar, old_button


def render(parent):
    """Devuelve el visor y conserva visible la barra original del lanzador."""
    parent.configure(bg=BG)
    window = parent.winfo_toplevel()
    window.configure(bg=BG)
    toolbar, legacy_button = ensure_launcher_toolbar(window, parent)
    screen = TVViewer(parent)
    previous = getattr(window, "_minga_tv_splash", None)
    if previous is not None:
        try:
            previous.destroy()
        except tk.TclError:
            pass

    splash = tk.Frame(window, bg="#000000")
    window._minga_tv_splash = splash
    splash.place(x=0, y=0, relwidth=1, relheight=1)
    splash.lift()
    # La barra opaca permanece por encima del splash y del visor VLC.
    if toolbar is not None:
        toolbar.lift()
    if legacy_button is not None:
        legacy_button.lift()
    center = tk.Frame(splash, bg="#000000")
    center.place(relx=0.5, rely=0.45, anchor="center")
    logo_label = tk.Label(center, text="MINGA TV", bg="#000000", fg=WHITE,
                          font=("Segoe UI", 28, "bold"), borderwidth=0)
    logo_label.pack()
    tk.Label(center, text=SLOGAN, bg="#000000", fg="#e9f5ff",
             font=("Segoe UI", 12), borderwidth=0).pack(pady=(10, 0))
    tk.Frame(center, bg=CYAN, height=2, width=78).pack(pady=(15, 0))
    started = time.monotonic()
    loaded_at = [None]
    failed = [False]
    messages = queue.Queue()

    def use_logo():
        try:
            image = tk.PhotoImage(file=str(LOGO_FILE))
            logo_label.config(image=image, text="")
            logo_label.image = image
            loaded_at[0] = time.monotonic()
            return True
        except (OSError, tk.TclError):
            return False

    if not LOGO_FILE.is_file() or not use_logo():
        def download_logo():
            try:
                request = Request(LOGO_URL, headers={"User-Agent": "MingaTV/1.0"})
                with urlopen(request, timeout=4) as response:
                    data = response.read(1024 * 1024 + 1)
                if len(data) > 1024 * 1024 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("Recurso de imagen inesperado")
                LOGO_FILE.parent.mkdir(parents=True, exist_ok=True)
                temp = LOGO_FILE.with_suffix(".png.tmp")
                temp.write_bytes(data)
                temp.replace(LOGO_FILE)
                messages.put(True)
            except (OSError, ValueError, TimeoutError):
                messages.put(False)

        threading.Thread(target=download_logo, daemon=True).start()

    def tick():
        if not splash.winfo_exists():
            return
        try:
            while True:
                ok = messages.get_nowait()
                if ok:
                    if not use_logo():
                        failed[0] = True
                else:
                    failed[0] = True
        except queue.Empty:
            pass
        elapsed = (time.monotonic() - started) * 1000
        logo_ms = ((time.monotonic() - loaded_at[0]) * 1000
                   if loaded_at[0] is not None else 0)
        done = (elapsed >= SPLASH_MIN_MS
                and (failed[0] or (loaded_at[0] is not None and logo_ms >= 1400)))
        if done or elapsed >= SPLASH_MAX_MS:
            splash.destroy()
            if getattr(window, "_minga_tv_splash", None) is splash:
                window._minga_tv_splash = None
            if screen.winfo_exists():
                screen.finish_splash()
        else:
            screen.after(100, tick)

    screen.startup()  # Prepara la lista mientras el splash esta visible.
    screen.after(100, tick)
    return screen