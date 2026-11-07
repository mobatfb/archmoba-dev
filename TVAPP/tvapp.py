"""ARCHMOBA TVAPP - interfaz IPTV con reproductor integrado.

El visor superior utiliza el logotipo de TVAPP como imagen de espera.
Todo funciona con tkinter y recursos integrados sin archivos graficos externos.
"""

import os
import tkinter as tk

VERSION = "1.0.16"
WINDOW_WIDTH = 380
WINDOW_HEIGHT = 650
HERO_BOTTOM = 222  # El contenido empieza mas arriba, sin la barra de estado simulada

# Logotipo de la referencia grafica integrado en el codigo.
_LOGO_PNG = "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"

BG = "#171820"
SIDE = "#101116"
PANEL = "#1b1c25"
CARD = "#292b38"
CARD_ACTIVE = "#204650"
CYAN = "#6cc6d7"
GOLD = "#f6c95e"
WHITE = "#f5f5f7"
MUTED = "#9b9eaf"


def lock_mobile_window(window):
    """Evita redimensionar y maximizar, tambien con Snap de Windows."""
    if getattr(window, "_archmoba_mobile_size_locked", False):
        return
    window._archmoba_mobile_size_locked = True
    window.resizable(False, False)
    window.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
    window.maxsize(WINDOW_WIDTH, WINDOW_HEIGHT)

    def restore_size():
        try:
            if window.state() == "zoomed":
                window.state("normal")
            if window.state() == "normal" and (
                window.winfo_width() != WINDOW_WIDTH
                or window.winfo_height() != WINDOW_HEIGHT
            ):
                window.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        except tk.TclError:
            pass

    def on_resize(event):
        if event.widget is window:
            window.after_idle(restore_size)

    window.bind("<Configure>", on_resize, add="+")
    window.after_idle(restore_size)

    if os.name == "nt":
        def disable_maximize():
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
                user32.GetAncestor.restype = wintypes.HWND
                user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
                user32.GetWindowLongW.restype = ctypes.c_long
                user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
                user32.SetWindowLongW.restype = ctypes.c_long
                user32.SetWindowPos.argtypes = [
                    wintypes.HWND, wintypes.HWND,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    wintypes.UINT,
                ]
                user32.SetWindowPos.restype = wintypes.BOOL
                hwnd = user32.GetAncestor(wintypes.HWND(window.winfo_id()), 2)
                if hwnd:
                    style = user32.GetWindowLongW(hwnd, -16)
                    style &= ~0x00050000  # WS_MAXIMIZEBOX | WS_THICKFRAME
                    user32.SetWindowLongW(hwnd, -16, style)
                    user32.SetWindowPos(hwnd, wintypes.HWND(0), 0, 0, 0, 0, 0x27)
            except (OSError, AttributeError, ValueError):
                pass
        window.after_idle(disable_maximize)


# Catalogo IPTV-org: cada seccion se descarga bajo demanda, sin bloquear Tk.
import base64
import hashlib
import importlib
import io
import json
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlsplit, quote
from urllib.error import HTTPError, URLError
import webbrowser

PLAYLIST_ROOT = "https://iptv-org.github.io/iptv/"
SOURCES = {
    "Todos": "index.m3u",
    "Categorías": "index.category.m3u",
    "Noticias": "categories/news.m3u",
    "Deportes": "categories/sports.m3u",
    "Películas": "categories/movies.m3u",
    "Música": "categories/music.m3u",
    "Países": "index.country.m3u",
    "Idiomas": "index.language.m3u",
    "Ecuador": "countries/ec.m3u",
    "Español": "languages/spa.m3u",
    "Infantil": "categories/kids.m3u",
    "Cultura": "categories/culture.m3u",
    "Documentales": "categories/documentary.m3u",
}
GROUPED_SOURCES = {"Categorías", "Países", "Idiomas"}
XTREAM_SECTIONS = ("Xtream TV", "Xtream Cine", "Xtream Series")
XTREAM_SERVER_DEFAULT = "http://xcmas.ddns.net:80"
XTREAM_MAX_RESPONSE = 32 * 1024 * 1024

CACHE_LIFETIME = 60 * 60  # 1 hora
MAX_PLAYLIST_BYTES = 35 * 1024 * 1024


def parse_m3u(text):
    """Convierte #EXTINF de IPTV-org a canales; no abre transmisiones."""
    if not text.lstrip("\ufeff \r\n\t").startswith("#EXTM3U"):
        raise ValueError("La direccion no devolvio una lista M3U valida.")
    entries, current, extras = [], None, {}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#EXTINF:"):
            # Primera coma fuera de comillas: admite comas en los atributos.
            quoted, marker = False, -1
            for index, character in enumerate(line):
                if character == '"':
                    quoted = not quoted
                elif character == ',' and not quoted:
                    marker = index
                    break
            if marker < 0:
                current, extras = None, {}
                continue
            attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', line[:marker]))
            title = line[marker+1:].strip() or attrs.get("tvg-name", "Canal")
            current = {
                "name": title[:240],
                "id": attrs.get("tvg-id", "")[:160],
                "logo": attrs.get("tvg-logo", "")[:800],
                "group": attrs.get("group-title", "Sin categoría")[:120],
            }
            extras = {}
        elif line.startswith("#EXTVLCOPT:") and current:
            opt = line.partition(":")[2]
            key, _, value = opt.partition("=")
            if key in ("http-referrer", "http-user-agent"):
                extras[key] = value[:300]
        elif current is not None and (line.startswith("https://") or line.startswith("http://")):
            entry = dict(current)
            entry["url"] = line[:4096]
            entry["headers"] = dict(extras)
            if not entry["id"]:
                entry["id"] = hashlib.sha1(entry["url"].encode("utf-8")).hexdigest()[:16]
            entries.append(entry)
            current, extras = None, {}
            if len(entries) >= 25000:
                break
    return entries


def tvapp_data_dir():
    base = os.getenv("LOCALAPPDATA")
    root = Path(base) if base else Path.home() / ".local" / "share"
    directory = root / "ARCHMOBA" / "TVAPP"
    directory.mkdir(parents=True, exist_ok=True)
    return directory



def normalize_xtream_server(server):
    """Solo acepta URL HTTP(S) sin credenciales ni rutas."""
    parts = urlsplit(server.strip().rstrip("/"))
    try:
        port = parts.port
    except ValueError:
        raise ValueError("Puerto Xtream no válido.") from None
    if (parts.scheme not in ("http", "https") or not parts.hostname
            or parts.username or parts.password or parts.query or parts.fragment
            or parts.path not in ("", "/") or (port is not None and port < 1)):
        raise ValueError("Servidor inválido: escribe http(s)://host:puerto.")
    return parts.scheme + "://" + parts.netloc


def xtream_request(session, action=None, **params):
    """Acceso Xtream; no guardar ni registrar credenciales."""
    query = {"username": session["user"], "password": session["password"]}
    if action:
        query["action"] = action
    query.update(params)
    url = session["server"] + "/player_api.php?" + urlencode(query)
    request = Request(url, headers={
        "User-Agent": "ARCHMOBA-TVAPP/1.0", "Accept": "application/json",
    })
    try:
        with urlopen(request, timeout=18) as response:
            payload = response.read(XTREAM_MAX_RESPONSE + 1)
    except HTTPError as exc:
        raise ValueError("Servidor Xtream: HTTP " + str(exc.code)) from None
    except (URLError, TimeoutError, OSError):
        raise ValueError("No se pudo conectar al servidor Xtream.") from None
    if len(payload) > XTREAM_MAX_RESPONSE:
        raise ValueError("El catálogo Xtream excede el límite de descarga.")
    try:
        return json.loads(payload.decode("utf-8-sig"))
    except (ValueError, UnicodeError):
        raise ValueError("El servidor no devolvió JSON válido.") from None


def xtream_stream_url(session, item):
    """Construye la dirección solo en memoria al iniciar la reproducción."""
    base = session["server"]
    user = quote(session["user"], safe="")
    password = quote(session["password"], safe="")
    stream_id = quote(str(item["stream_id"]), safe="")
    kind = item.get("kind")
    if kind == "live":
        return f"{base}/live/{user}/{password}/{stream_id}.{session.get('output', 'ts')}"
    if kind == "movie":
        folder = "movie"
    elif kind == "episode":
        folder = "series"
    else:
        raise ValueError("Selecciona un episodio de la serie.")
    ext = str(item.get("extension") or "mp4").lower()
    if not re.fullmatch(r"[a-z0-9]{2,8}", ext):
        ext = "mp4"
    return f"{base}/{folder}/{user}/{password}/{stream_id}.{ext}"


def xtream_favorite_key(item):
    if item.get("source") != "xtream":
        return item.get("url", "")
    return "xc:" + ":".join((
        str(item.get("account_tag", "")),
        str(item.get("kind", "")),
        str(item.get("stream_id", "")),
    ))


def xtream_parse_catalog(items, groups, kind, account_tag):
    result = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        stream_id = item.get("series_id") if kind == "series" else item.get("stream_id")
        if stream_id is None or not str(stream_id).isdigit():
            continue
        result.append({
            "source": "xtream",
            "kind": kind,
            "id": str(stream_id),
            "stream_id": str(stream_id),
            "name": str(item.get("name") or "Sin título")[:240],
            "logo": str(item.get("cover") or item.get("stream_icon") or "")[:800],
            "group": groups.get(str(item.get("category_id") or ""), "Sin categoría")[:120],
            "extension": str(item.get("container_extension") or "mp4")[:10],
            "account_tag": account_tag,
        })
        if len(result) >= 25000:
            break
    return result


def xtream_parse_episodes(info, series, account_tag):
    result = []
    episodes = info.get("episodes", {}) if isinstance(info, dict) else {}
    if not isinstance(episodes, dict):
        return result
    for season, items in episodes.items():
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
                continue
            episode_id = str(item["id"])
            result.append({
                "source": "xtream",
                "kind": "episode",
                "id": episode_id,
                "stream_id": episode_id,
                "name": ("E" + str(item.get("episode_num") or i + 1) +
                         " · " + str(item.get("title") or series["name"]))[:240],
                "logo": series.get("logo", ""),
                "group": "Temporada " + str(season)[:10],
                "extension": str(item.get("container_extension") or "mp4")[:10],
                "account_tag": account_tag,
            })
            if len(result) >= 3000:
                return result
    return result


class TVSports(tk.Frame):
    CATEGORIES = list(XTREAM_SECTIONS) + list(SOURCES.keys()) + ["Favoritos"]
    NAV = ["Inicio", "Vivo", "VOD", "Partidos", "Cuenta"]

    def __init__(self, parent):
        super().__init__(parent, bg=BG, highlightthickness=0)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0, bd=0, relief="flat")
        self.canvas.pack(fill="both", expand=True)
        self.active_tab = "Vivo"
        self.mode = None  # Elegir modo de acceso en el primer inicio.
        self.category = ""
        self.use_internal = False
        self.category_offset = 0
        self.channel_offset = 0
        self.search_open = False
        self.query = tk.StringVar()
        self.query.trace_add("write", lambda *_: self._on_filter_changed())
        self.search_field = tk.Entry(
            self, textvariable=self.query, bg="#292c38", fg="white",
            insertbackground="white", relief="flat", font=("Segoe UI", 10),
            highlightthickness=0,
        )
        self.search_field.bind("<Escape>", lambda _: self._toggle_search(False))

        from tkinter import ttk
        self.group_choice = tk.StringVar(value="Todos")
        self.group_picker = ttk.Combobox(self, textvariable=self.group_choice,
                                         state="readonly", font=("Segoe UI", 9))
        self.group_picker.bind("<<ComboboxSelected>>", lambda _: self._on_filter_changed())
        self.group_values = ["Todos"]

        # Inicio de sesión efímero: nunca se persiste la contraseña.
        self.xtream_session = None
        self.xtream_auth_token = 0
        self.xtream_connecting = False
        self.xtream_note = "Introduce usuario y contraseña para conectar."
        self.xc_server = tk.StringVar(value=XTREAM_SERVER_DEFAULT)
        self.xc_user = tk.StringVar()
        self.xc_password = tk.StringVar()
        self.series_items = None
        self.series_name = ""
        self.series_request_id = 0
        self._build_xtream_form()

        self.storage = tvapp_data_dir()
        self.catalogs = {}
        self.favorites = self._read_favorites()
        self.events = queue.Queue()
        self.request_id = 0
        self.loading = False
        self.hint = "Conectando con IPTV-org..."
        self.logo_cache = {}
        self.logo_requested = set()
        self.pending_logos = 0
        self.video_frame = None
        # Barra superpuesta sobre el visor, independiente del Canvas.
        # El frame nativo de VLC ocupa exactamente el area del banner.
        self.video_controls = tk.Frame(self, bg="#111924", height=31)
        self.video_controls.pack_propagate(False)
        self.video_title = tk.Label(
            self.video_controls, bg="#111924", fg="#f5f5f7",
            font=("Segoe UI", 9, "bold"), anchor="w",
        )
        self.video_title.pack(side="left", fill="x", expand=True, padx=(8, 2))
        for symbol, method, tip_width in (
            ("⏯", self._toggle_playback, 3),
            ("♫", self._toggle_mute, 2),
            ("VLC", self._open_external, 4),
            ("×", self._close_player, 2),
        ):
            button = tk.Button(
                self.video_controls, text=symbol, command=method,
                bg="#202d39", fg="#e9f3f5", activebackground="#275568",
                activeforeground="white", borderwidth=0, relief="flat",
                highlightthickness=0, cursor="hand2", font=("Segoe UI", 9),
                width=tip_width, padx=0, pady=0,
            )
            button.pack(side="left", padx=(0, 3), pady=3)
        self.selected = None
        self.player_state = ""
        self.vlc_player = None
        self.vlc_instance = None
        self.vlc_dll_handles = []
        self.player_token = 0
        self.player_muted = False

        try:
            self.logo = tk.PhotoImage(data=_LOGO_PNG, format="png")
            # Se reutiliza el mismo logo en el encabezado y en el visor.
            self.hero_logo = self.logo.zoom(2, 2)
        except tk.TclError:
            self.logo = None
            self.hero_logo = None

        self.canvas.bind("<Configure>", lambda _: self.redraw())
        self.canvas.bind("<MouseWheel>", self._wheel)
        self.canvas.bind("<Button-4>", lambda _: self._wheel_linux(-1))
        self.canvas.bind("<Button-5>", lambda _: self._wheel_linux(1))
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.after(100, self._check_events)
        # Muestra la selección de modos; no inicia conexiones automáticamente.
        self.redraw()

    def _build_xtream_form(self):
        form = tk.Frame(self, bg=PANEL, highlightthickness=0)
        self.xtream_form = form
        tk.Label(form, text="XTREAM CODES", bg=PANEL, fg=CYAN,
                 font=("Segoe UI", 14, "bold"), anchor="w").pack(
                     fill="x", padx=9, pady=(4, 0))
        for title, variable, secret in (
            ("Servidor", self.xc_server, False),
            ("Usuario", self.xc_user, False),
            ("Contraseña", self.xc_password, True),
        ):
            tk.Label(form, text=title, bg=PANEL, fg=WHITE,
                     font=("Segoe UI", 9), anchor="w").pack(
                         fill="x", padx=9, pady=(2, 0))
            entry = tk.Entry(
                form, textvariable=variable, show="*" if secret else "",
                bg="#2b2d3b", fg="white", insertbackground="white",
                relief="flat", font=("Segoe UI", 10),
            )
            entry.pack(fill="x", padx=9, ipady=3)
            if secret:
                entry.bind("<Return>", lambda _e: self._connect_xtream())
        buttons = tk.Frame(form, bg=PANEL)
        buttons.pack(fill="x", padx=9, pady=(7, 2))
        self.xc_connect_button = tk.Button(
            buttons, text="Conectar", command=self._connect_xtream,
            bg="#286578", fg="white", activebackground="#3585a0",
            relief="flat", font=("Segoe UI", 10, "bold"),
        )
        self.xc_connect_button.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.xc_disconnect_button = tk.Button(
            buttons, text="Salir", command=self._disconnect_xtream,
            bg="#3b3444", fg="white", activebackground="#504059",
            relief="flat", font=("Segoe UI", 9),
        )
        self.xc_disconnect_button.pack(side="right")
        self.xc_internal_button = tk.Button(
            form, text="← Cambiar modo de acceso",
            command=self._switch_mode,
            bg="#24535d", fg=WHITE, activebackground="#367887",
            activeforeground=WHITE, relief="flat",
            font=("Segoe UI", 10, "bold"), cursor="hand2",
            borderwidth=0,
        )
        self.xc_internal_button.pack(fill="x", padx=9, pady=(5, 1), ipady=3)
        self.xc_note_label = tk.Label(
            form, text="", bg=PANEL, fg=MUTED, anchor="w", justify="left",
            wraplength=325, font=("Segoe UI", 8),
        )
        self.xc_note_label.pack(fill="x", padx=9, pady=(4, 0))

    def _draw_xtream_form(self, w, h):
        self.group_picker.place_forget()
        self.xtream_form.place(
            x=9, y=HERO_BOTTOM + 7, width=max(210, w - 18),
            height=max(215, min(299, h - HERO_BOTTOM - 88)),
        )
        self.xtream_form.lift()
        self.xc_note_label.config(text=self.xtream_note)
        self.xc_connect_button.config(
            state="disabled" if self.xtream_connecting else "normal",
            text="Conectando..." if self.xtream_connecting else "Conectar",
        )
        self.xc_disconnect_button.config(
            state="normal" if self.xtream_session else "disabled",
        )

    def _clear_external_session(self):
        """Cancela consultas y descarta las credenciales del servidor externo."""
        self.xtream_auth_token += 1
        self.xtream_connecting = False
        self.xtream_session = None
        self.xc_password.set("")
        self.catalogs = {
            key: value for key, value in self.catalogs.items()
            if key not in XTREAM_SECTIONS
        }

    def _use_internal(self):
        """Usa los canales IPTV-org preconfigurados sin autenticación."""
        self._clear_external_session()
        self.mode = "local"
        self.use_internal = True
        self.category_offset = 0
        self.active_tab = "Vivo"
        self._select_category("Todos")

    def _use_external(self):
        """Abre el inicio de sesión del servidor Xtream."""
        self._clear_external_session()
        self.mode = "external"
        self.use_internal = False
        self.category_offset = 0
        self.active_tab = "Vivo"
        self._select_category("Xtream TV")

    def _switch_mode(self):
        """Vuelve a elegir entre local multirregión y servidor externo."""
        self._clear_external_session()
        self.mode = None
        self.use_internal = False
        self.active_tab = "Vivo"
        self.category = ""
        self.category_offset = 0
        self.channel_offset = 0
        self.series_request_id += 1
        self.series_items = None
        self.series_name = ""
        self.request_id += 1
        self._release_player()
        self.selected = None
        self.group_picker.place_forget()
        self.redraw()

    def _connect_xtream(self):
        if self.xtream_connecting:
            return
        try:
            server = normalize_xtream_server(self.xc_server.get())
        except ValueError as exc:
            self.xtream_note = str(exc)
            self.redraw()
            return
        user, password = self.xc_user.get().strip(), self.xc_password.get()
        if not user or not password:
            self.xtream_note = "Introduce usuario y contraseña."
            self.redraw()
            return
        self.xtream_auth_token += 1
        token = self.xtream_auth_token
        self.xtream_connecting = True
        self.xtream_note = "Comprobando cuenta Xtream..."
        session = {
            "server": server, "user": user, "password": password,
            "account_tag": hashlib.sha256(
                (server + "\0" + user).encode("utf-8")).hexdigest()[:16],
        }
        self.redraw()
        threading.Thread(
            target=self._xtream_auth_worker, args=(token, session),
            daemon=True,
        ).start()

    def _xtream_auth_worker(self, token, session):
        try:
            payload = xtream_request(session)
            info = payload.get("user_info", {}) if isinstance(payload, dict) else {}
            if str(info.get("auth")) != "1":
                raise ValueError("Usuario o contraseña incorrectos.")
            if str(info.get("status", "")).lower() != "active":
                raise ValueError("La cuenta está inactiva.")
            formats = info.get("allowed_output_formats") or []
            session["output"] = "m3u8" if isinstance(formats, list) and "m3u8" in formats else "ts"
            self.events.put(("xc_auth", (token, session)))
        except Exception as exc:
            self.events.put(("xc_auth_error", (token, str(exc)[:120])))

    def _disconnect_xtream(self):
        self.xtream_auth_token += 1
        self.xtream_connecting = False
        self.xtream_session = None
        self.xc_password.set("")
        self.catalogs = {
            key: value for key, value in self.catalogs.items()
            if key not in XTREAM_SECTIONS
        }
        self.series_items = None
        self._release_player()
        self.selected = None
        self.xtream_note = "Cuenta desconectada. La contraseña no se guardó."
        self.mode = "external"
        self.use_internal = False
        self.active_tab = "Vivo"
        self._select_category("Xtream TV")
        self.redraw()

    def _xtream_catalog_worker(self, category, token, session):
        kind, action, category_action = {
            "Xtream TV": ("live", "get_live_streams", "get_live_categories"),
            "Xtream Cine": ("movie", "get_vod_streams", "get_vod_categories"),
            "Xtream Series": ("series", "get_series", "get_series_categories"),
        }[category]
        try:
            raw_categories = xtream_request(session, category_action)
            groups = {
                str(item.get("category_id")): str(item.get("category_name") or "Otros")
                for item in raw_categories if isinstance(item, dict)
            } if isinstance(raw_categories, list) else {}
            raw_items = xtream_request(session, action)
            if not isinstance(raw_items, list):
                raise ValueError("No se recibió un catálogo Xtream válido.")
            items = xtream_parse_catalog(
                raw_items, groups, kind, session["account_tag"],
            )
            self.events.put(("loaded", (token, category, items, False)))
        except Exception as exc:
            self.events.put(("load_error", (token, category, str(exc)[:120])))

    def _xtream_series_worker(self, token, session, series):
        try:
            info = xtream_request(
                session, "get_series_info", series_id=series["stream_id"],
            )
            episodes = xtream_parse_episodes(info, series, session["account_tag"])
            if not episodes:
                raise ValueError("Esta serie no tiene episodios disponibles.")
            self.events.put(("xc_episodes", (token, series["name"], episodes)))
        except Exception as exc:
            self.events.put(("xc_episode_error", (token, str(exc)[:120])))

    def _show_xtream_series(self, series):
        if (not self.xtream_session or
                series.get("account_tag") != self.xtream_session["account_tag"]):
            self.hint = "Conecta la cuenta de esta serie."
            self.redraw()
            return
        self._release_player()
        self.selected = None
        self.active_tab = "Vivo"
        self.category = "Xtream Series"
        self.series_request_id += 1
        token = self.series_request_id
        self.series_name = series["name"]
        self.series_items = []
        self.channel_offset = 0
        self.group_choice.set("Todos")
        self.loading = True
        self.hint = "Consultando episodios..."
        threading.Thread(
            target=self._xtream_series_worker,
            args=(token, dict(self.xtream_session), series),
            daemon=True,
        ).start()
        self.redraw()

    def _back_to_series(self):
        self._select_category("Xtream Series")

    def _on_destroy(self, event):
        if event.widget is self:
            self._release_player()

    def _read_favorites(self):
        try:
            raw = json.loads((self.storage / "favorites.json").read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return {k: v for k, v in raw.items()
                        if isinstance(k, str) and isinstance(v, dict)
                        and (isinstance(v.get("url"), str) or
                             (v.get("source") == "xtream" and
                              isinstance(v.get("stream_id"), str) and
                              isinstance(v.get("account_tag"), str)))}
        except (OSError, ValueError):
            pass
        return {}

    def _save_favorites(self):
        path = self.storage / "favorites.json"
        tmp = path.with_suffix(".tmp")
        try:
            clean = {}
            for key, item in self.favorites.items():
                if item.get("source") == "xtream":
                    safe_fields = ("source", "kind", "id", "stream_id",
                                   "account_tag", "name", "logo", "group",
                                   "extension")
                    clean[key] = {k: item[k] for k in safe_fields if k in item}
                else:
                    clean[key] = item
            tmp.write_text(json.dumps(clean, ensure_ascii=False, indent=2),
                           encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            self.hint = f"No se guardaron los favoritos: {exc}"

    def _download_playlist(self, category, token):
        cache_path = self.storage / ("iptv_" + category.encode("utf-8").hex() + ".m3u")
        data, from_cache = None, False
        try:
            if cache_path.exists() and (time.time() - cache_path.stat().st_mtime < CACHE_LIFETIME):
                data = cache_path.read_text(encoding="utf-8-sig")
                from_cache = True
        except OSError:
            pass
        if data is None:
            try:
                request = Request(PLAYLIST_ROOT + SOURCES[category], headers={
                    "User-Agent": "ARCHMOBA-TVAPP/1.1", "Accept": "text/plain, */*",
                    "Cache-Control": "no-cache",
                })
                with urlopen(request, timeout=16) as response:
                    raw = response.read(MAX_PLAYLIST_BYTES + 1)
                if len(raw) > MAX_PLAYLIST_BYTES:
                    raise ValueError("La lista excede el tamaño permitido.")
                data = raw.decode("utf-8-sig", errors="replace")
                if not data.lstrip().startswith("#EXTM3U"):
                    raise ValueError("El servidor no devolvió una lista M3U.")
                try:
                    tmp = cache_path.with_suffix(".tmp")
                    tmp.write_text(data, encoding="utf-8")
                    os.replace(tmp, cache_path)
                except OSError:
                    pass
            except Exception as exc:
                if cache_path.exists():
                    try:
                        data = cache_path.read_text(encoding="utf-8-sig")
                        from_cache = True
                    except OSError:
                        pass
                if data is None:
                    self.events.put(("load_error", (token, category, str(exc))))
                    return
        try:
            channels = parse_m3u(data)
            self.events.put(("loaded", (token, category, channels, from_cache)))
        except Exception as exc:
            self.events.put(("load_error", (token, category, str(exc))))

    def _check_events(self):
        if not self.winfo_exists():
            return
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "loaded":
                    token, category, channels, from_cache = payload
                    self.catalogs[category] = channels
                    if token == self.request_id and self.category == category:
                        self.loading = False
                        unit = "elementos" if category in XTREAM_SECTIONS else "canales"
                        self.hint = f"{len(channels):,} {unit}" + (" (copia local)" if from_cache else "")
                        groups = sorted({c["group"] for c in channels if c["group"]}, key=str.casefold)
                        self.group_values = ["Todos"] + groups
                        self.group_picker["values"] = self.group_values
                        if self.group_choice.get() not in self.group_values:
                            self.group_choice.set("Todos")
                        self.redraw()
                elif kind == "load_error":
                    token, category, message = payload
                    if token == self.request_id and category == self.category:
                        self.loading = False
                        self.hint = "No se pudo descargar: " + message[:110]
                        self.redraw()
                elif kind == "xc_auth":
                    token, session = payload
                    if token == self.xtream_auth_token:
                        self.xtream_connecting = False
                        self.xtream_session = session
                        self.use_internal = False
                        self.xc_password.set("")
                        self.xtream_note = (
                            "Cuenta activa. HTTP sin cifrar; evita redes públicas."
                            if session["server"].startswith("http://")
                            else "Cuenta activa. Puedes abrir TV, Cine y Series."
                        )
                        self.catalogs = {
                            k: v for k, v in self.catalogs.items()
                            if k not in XTREAM_SECTIONS
                        }
                        self.active_tab = "Vivo"
                        self._select_category("Xtream TV")
                elif kind == "xc_auth_error":
                    token, message = payload
                    if token == self.xtream_auth_token:
                        self.xtream_connecting = False
                        self.xtream_note = "Acceso fallido: " + message
                        self.redraw()
                elif kind == "xc_episodes":
                    token, title, episodes = payload
                    if token == self.series_request_id and self.category == "Xtream Series":
                        self.series_items = episodes
                        self.series_name = title
                        self.loading = False
                        self.hint = f"{len(episodes)} episodios disponibles"
                        self._set_group_values(episodes)
                        self.redraw()
                elif kind == "xc_episode_error":
                    token, message = payload
                    if token == self.series_request_id:
                        self.loading = False
                        self.hint = message
                        self.redraw()
                elif kind == "logo":
                    url, raw = payload
                    self.pending_logos = max(0, self.pending_logos - 1)
                    if raw and len(self.logo_cache) < 140:
                        img = self._create_logo(raw)
                        if img:
                            self.logo_cache[url] = img
                    self.redraw()
                elif kind == "vlc_ready":
                    token, module, error = payload
                    if token == self.player_token and self.selected:
                        if module is None:
                            self.player_state = error or "VLC no está disponible"
                            self.redraw()
                        else:
                            self._start_embedded_vlc(module)
        except queue.Empty:
            pass
        self.after(110, self._check_events)

    def _sidebar_categories(self):
        """Categorías exclusivas para el modo de acceso elegido."""
        if self.mode == "local":
            return list(SOURCES.keys()) + ["Favoritos"]
        if self.mode == "external":
            return list(XTREAM_SECTIONS) + ["Favoritos"]
        return []

    def _sidebar_row_count(self, height):
        """Filas del menú visibles sin invadir la navegación flotante."""
        return max(1, int((height - HERO_BOTTOM - 138) // 44) + 1)

    def _select_category(self, category):
        if self.mode == "local" and category not in SOURCES and category != "Favoritos":
            return
        if self.mode == "external" and category not in XTREAM_SECTIONS and category != "Favoritos":
            return
        if self.mode is None:
            return
        self._release_player()
        self.selected = None
        self.category = category
        self.use_internal = self.mode == "local"
        sidebar = self._sidebar_categories()
        rows = self._sidebar_row_count(self.canvas.winfo_height())
        if category in sidebar:
            index = sidebar.index(category)
            if index < self.category_offset:
                self.category_offset = index
            elif index >= self.category_offset + rows:
                self.category_offset = index - rows + 1
        self.series_request_id += 1
        self.series_items = None
        self.series_name = ""
        self.channel_offset = 0
        self.group_choice.set("Todos")
        self.group_picker.place_forget()
        self.request_id += 1
        token = self.request_id
        if category == "Favoritos":
            self.loading = False
            self.hint = f"{len(self.favorites)} favoritos guardados"
        elif category in XTREAM_SECTIONS and not self.xtream_session:
            self.loading = False
            self.hint = "Introduce tu acceso Xtream Codes."
        elif category in self.catalogs:
            self.loading = False
            self.hint = f"{len(self.catalogs[category]):,} canales"
            self._set_group_values(self.catalogs[category])
        else:
            self.loading = True
            if category in XTREAM_SECTIONS:
                self.hint = "Consultando servidor Xtream..."
                threading.Thread(
                    target=self._xtream_catalog_worker,
                    args=(category, token, dict(self.xtream_session)),
                    daemon=True,
                ).start()
            else:
                self.hint = "Descargando lista M3U..."
                threading.Thread(
                    target=self._download_playlist, args=(category, token),
                    daemon=True,
                ).start()
        self.redraw()

    def _set_group_values(self, channels):
        self.group_values = ["Todos"] + sorted(
            {c["group"] for c in channels if c["group"]}, key=str.casefold)
        self.group_picker["values"] = self.group_values

    def _visible_channels(self):
        if self.category == "Favoritos":
            channels = list(self.favorites.values())
            if self.mode == "local":
                channels = [item for item in channels
                            if item.get("source") != "xtream"]
            elif self.mode == "external":
                account = (self.xtream_session or {}).get("account_tag")
                channels = [item for item in channels
                            if item.get("source") == "xtream"
                            and item.get("account_tag") == account]
        elif self.category == "Xtream Series" and self.series_items is not None:
            channels = self.series_items
        else:
            channels = self.catalogs.get(self.category, [])
        group = self.group_choice.get()
        if (self.category in GROUPED_SOURCES or self.category in XTREAM_SECTIONS) and group != "Todos":
            channels = [c for c in channels if c["group"] == group]
        q = self.query.get().strip().casefold()
        if q:
            channels = [c for c in channels if q in c["name"].casefold()]
        return channels

    def _on_filter_changed(self):
        self.channel_offset = 0
        self.redraw()

    def _toggle_search(self, enable=None):
        self.search_open = not self.search_open if enable is None else bool(enable)
        if not self.search_open:
            self.query.set("")
            self.search_field.place_forget()
        self.redraw()
        if self.search_open:
            self.search_field.focus_set()

    def _select_tab(self, tab):
        if self.mode is None:
            self.redraw()
            return
        self.active_tab = tab
        if tab in ("VOD", "Partidos", "Vivo"):
            if self.mode == "local":
                target = {"VOD": "Películas", "Partidos": "Deportes",
                          "Vivo": "Todos"}[tab]
            else:
                target = {"VOD": "Xtream Cine", "Partidos": "Xtream TV",
                          "Vivo": "Xtream TV"}[tab]
            self._select_category(target)
        else:
            self._release_player()
            self.selected = None
            self.redraw()

    def _toggle_favorite(self, channel):
        key = xtream_favorite_key(channel)
        if not key:
            return
        if key in self.favorites:
            del self.favorites[key]
        elif channel.get("source") == "xtream":
            fields = ("source", "kind", "id", "stream_id", "account_tag",
                      "name", "logo", "group", "extension")
            self.favorites[key] = {k: channel[k] for k in fields if k in channel}
        else:
            self.favorites[key] = dict(channel)
        self._save_favorites()
        self.redraw()

    def _wheel(self, event):
        self._wheel_linux(-1 if event.delta > 0 else 1, event.x)

    def _wheel_linux(self, direction, x=None):
        if self.active_tab not in ("Vivo", "VOD", "Partidos"):
            return
        if x is None or x < 112:
            sidebar = self._sidebar_categories()
            rows = self._sidebar_row_count(self.canvas.winfo_height())
            self.category_offset = max(
                0, min(max(0, len(sidebar) - rows),
                       self.category_offset + direction)
            )
        else:
            self._page_channels(direction)
        self.redraw()

    def _page_channels(self, direction):
        total = len(self._visible_channels())
        self.channel_offset = max(0, min(max(0, total-1), self.channel_offset + direction * 2))
        self.redraw()

    def _round(self, x1, y1, x2, y2, radius, fill, outline="", width=1, tags=()):
        r = min(radius, max(0, (x2-x1)/2), max(0, (y2-y1)/2))
        p = [x1+r,y1, x2-r,y1, x2,y1, x2,y1+r,
             x2,y2-r, x2,y2, x2-r,y2, x1+r,y2,
             x1,y2, x1,y2-r, x1,y1+r, x1,y1]
        return self.canvas.create_polygon(p, smooth=True, splinesteps=10,
                                          fill=fill, outline=outline, width=width, tags=tags)

    def _text(self, x, y, text, size=12, color=WHITE, bold=False,
              anchor="w", tags=(), italic=False, width=0):
        style = ("Segoe UI", size, ("bold italic" if bold and italic else
                 "bold" if bold else "italic" if italic else "normal"))
        args = {"text": text, "fill": color, "font": style,
                "anchor": anchor, "tags": tags}
        if width:
            args["width"] = width
        return self.canvas.create_text(x, y, **args)

    def _click(self, tag, callback):
        self.canvas.tag_bind(tag, "<Button-1>", lambda _e: callback())
        self.canvas.tag_bind(tag, "<Enter>", lambda _e: self.canvas.config(cursor="hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda _e: self.canvas.config(cursor=""))

    def _draw_header(self, w):
        c = self.canvas
        c.create_rectangle(0, 0, w, 80, fill=BG, outline="")
        if self.logo:
            c.create_image(14, 17, image=self.logo, anchor="nw")
        else:
            self._text(18, 42, "GDX", 31, "#ed458c", bold=True)
        self._round(w-54, 16, w-14, 56, 20, "#30313d", outline="#484955", tags=("search",))
        c.create_oval(w-41, 28, w-30, 39, outline="white", width=1.8, tags=("search",))
        c.create_line(w-31, 38, w-26, 44, fill="white", width=2, tags=("search",))
        self._click("search", self._toggle_search)
        if self.search_open:
            self.search_field.place(x=10, y=23, width=max(135, w-80), height=28)
        else:
            self.search_field.place_forget()

    def _draw_hero(self, w):
        """Logo centrado en reposo; VLC lo sustituye al reproducir un canal."""
        c = self.canvas
        showing_video = self.selected is not None and self.vlc_player is not None
        c.create_rectangle(0, 80, w, HERO_BOTTOM,
                           fill="#050607" if showing_video else "#12141a",
                           outline="")
        if showing_video:
            return
        if self.hero_logo:
            logo_y = (80 + HERO_BOTTOM) / 2 - (15 if self.selected else 0)
            c.create_image(w/2, logo_y, image=self.hero_logo, anchor="center")
        else:
            self._text(w/2, 145, "GDX", 36, "#f14b87", bold=True, anchor="center")
        if self.selected is not None:
            state = self.player_state or "Preparando reproducción..."
            self._text(w/2, HERO_BOTTOM-17, state, 9, MUTED, anchor="center",
                       width=max(200, w-28))

    def _create_logo(self, raw):
        try:
            image_module = importlib.import_module("PIL.Image")
            image_tk = importlib.import_module("PIL.ImageTk")
            im = image_module.open(io.BytesIO(raw)).convert("RGBA")
            im.thumbnail((35, 35), image_module.Resampling.LANCZOS)
            return image_tk.PhotoImage(im, master=self)
        except (ImportError, OSError, ValueError, tk.TclError):
            try:
                image = tk.PhotoImage(data=base64.b64encode(raw).decode("ascii"), master=self)
                return image.subsample(max(1, image.width() // 35), max(1, image.height() // 35))
            except tk.TclError:
                return None

    def _download_logo(self, url):
        raw = None
        try:
            req = Request(url, headers={"User-Agent": "ARCHMOBA-TVAPP/1.1"})
            with urlopen(req, timeout=6) as response:
                if (response.headers.get("Content-Type") or "").startswith("image/"):
                    data = response.read(300 * 1024 + 1)
                    if len(data) <= 300 * 1024:
                        raw = data
        except (OSError, ValueError):
            pass
        self.events.put(("logo", (url, raw)))

    def _schedule_logo(self, url):
        if not url.startswith(("http://", "https://")) or url in self.logo_requested:
            return
        if len(self.logo_requested) > 120 or self.pending_logos >= 3:
            return
        self.logo_requested.add(url)
        self.pending_logos += 1
        threading.Thread(target=self._download_logo, args=(url,), daemon=True).start()

    def _draw_channel_icon(self, channel, x, y, tags=()):
        c = self.canvas
        url = channel.get("logo", "")
        self._round(x-19,y-19,x+19,y+19,10,"#383b4b",tags=tags)
        if url in self.logo_cache:
            c.create_image(x, y, image=self.logo_cache[url], anchor="center", tags=tags)
        else:
            c.create_oval(x-16,y-16,x+16,y+16,fill="#1a2831",outline="#5caebe",tags=tags)
            initial = channel["name"].strip()[:2].upper() or "TV"
            self._text(x, y, initial, 11, CYAN, bold=True, anchor="center", tags=tags)
            if url:
                self._schedule_logo(url)

    def _draw_live(self, w, h):
        c = self.canvas
        if self.category in XTREAM_SECTIONS and not self.xtream_session:
            c.create_rectangle(0, HERO_BOTTOM, w, h, fill=PANEL, outline="")
            self._draw_xtream_form(w, h)
            return
        left = 112
        c.create_rectangle(0, HERO_BOTTOM, left, h, fill=SIDE, outline="")
        c.create_rectangle(left, HERO_BOTTOM, w, h, fill=PANEL, outline="")

        sidebar = self._sidebar_categories()
        rows = self._sidebar_row_count(h)
        self.category_offset = max(
            0, min(self.category_offset, max(0, len(sidebar) - rows))
        )
        for i, category in enumerate(
            sidebar[self.category_offset:self.category_offset + rows]
        ):
            y = HERO_BOTTOM + 32 + i * 44
            tag = f"category_{i}"
            if category == self.category:
                self._round(5,y-19,left-6,y+19,10,"#24505e",tags=(tag,))
                self._text(left/2, y, "★" if category=="Favoritos" else category[:13],
                           10,CYAN,True,"center",tags=(tag,))
            else:
                label = category if len(category)<13 else category[:11]+"…"
                self._text(left/2,y,label,10,WHITE,False,"center",tags=(tag,))
            self._click(tag, lambda item=category: self._select_category(item))

        heading = self.series_name if self.series_items is not None else self.category
        self._text(left+8,HERO_BOTTOM+21,heading[:24],15,WHITE,bold=True,
                   width=w-left-25)
        if self.series_items is not None:
            self._round(w-58,HERO_BOTTOM+2,w-8,HERO_BOTTOM+28,8,
                        "#2d4550",tags=("series_back",))
            self._text(w-33,HERO_BOTTOM+15,"Volver",9,WHITE,
                       anchor="center",tags=("series_back",))
            self._click("series_back",self._back_to_series)
        if ((self.category in GROUPED_SOURCES or self.category in XTREAM_SECTIONS)
                and (self.catalogs.get(self.category) or self.series_items)):
            self.group_picker.place(x=left+6,y=HERO_BOTTOM+33,
                                    width=w-left-15,height=26)
        else:
            self.group_picker.place_forget()
        cards_top = HERO_BOTTOM + (74 if (self.category in GROUPED_SOURCES or self.category in XTREAM_SECTIONS) else 47)
        available = self._visible_channels()
        self._text(left+8,cards_top-6,
                   "Cargando canales..." if self.loading else self.hint,
                   8,MUTED,width=w-left-20)
        cards_top += 8
        limit_bottom = h-84
        card_h, gap = 59, 7
        max_rows = max(0, int((limit_bottom-cards_top+gap)/(card_h+gap)))
        for row, channel in enumerate(available[self.channel_offset:self.channel_offset+max_rows]):
            y = cards_top + row*(card_h+gap)
            x1, x2 = left+6, w-7
            tag = f"channel_{row}"
            self._round(x1,y,x2,y+card_h,11,CARD_ACTIVE if row%2 else CARD,tags=(tag,))
            self._draw_channel_icon(channel,x1+25,y+30,tags=(tag,))
            short = channel["name"]
            if len(short)>25:
                short=short[:24]+"…"
            self._text(x1+51,y+18,short,10,CYAN if row%2 else WHITE,
                       bold=True,italic=True,tags=(tag,))
            sub = (channel.get("group") or "Canal en vivo")[:29]
            self._text(x1+51,y+40,sub,9,MUTED,italic=True,tags=(tag,))
            star_tag=f"favorite_{row}"
            marked = xtream_favorite_key(channel) in self.favorites
            self._text(x2-14,y+29,"★" if marked else "☆",18,
                       GOLD if marked else MUTED,anchor="center",tags=(star_tag,))
            self._click(tag,lambda ch=channel:self._open_channel(ch))
            self._click(star_tag,lambda ch=channel:self._toggle_favorite(ch))
        if not available and not self.loading:
            self._text(left+8,cards_top+38,
                       "Sin resultados. Cambia categoría o busca otro canal.",
                       10,MUTED,width=w-left-20)
        if len(available)>max_rows and max_rows>0:
            # Paginador con controles alcanzables sin desplazar la barra inferior.
            self._round(w-79,h-113,w-46,h-88,8,"#2e3443",tags=("prev_channels",))
            self._round(w-42,h-113,w-9,h-88,8,"#2e3443",tags=("next_channels",))
            self._text(w-62,h-101,"‹",16,WHITE,anchor="center",tags=("prev_channels",))
            self._text(w-26,h-101,"›",16,WHITE,anchor="center",tags=("next_channels",))
            self._click("prev_channels",lambda:self._page_channels(-1))
            self._click("next_channels",lambda:self._page_channels(1))
            self._text(left+8,h-100,f"{self.channel_offset+1}-{min(len(available),self.channel_offset+max_rows)} de {len(available)}",8,MUTED)
        if self.loading and not available:
            self._text(left+10,HERO_BOTTOM+112,"Obteniendo lista M3U...",10,CYAN,width=w-left-20)

    def _draw_mode_choice(self, w, h):
        """Selección inicial de acceso sin mezclar categorías."""
        c = self.canvas
        c.create_rectangle(0, HERO_BOTTOM, w, h, fill=PANEL, outline="")
        self._text(w/2, HERO_BOTTOM+25, "Elige cómo ver TV",
                   17, WHITE, bold=True, anchor="center")
        y1 = HERO_BOTTOM + 49
        self._round(13, y1, w-13, y1+78, 14, "#253f4c",
                    outline="#3f798b", tags=("mode_local",))
        self._text(28, y1+25, "Modo local multirregión", 14, CYAN,
                   bold=True, tags=("mode_local",))
        self._text(28, y1+53, "Canales IPTV-org por región y categoría",
                   10, WHITE, tags=("mode_local",))
        self._click("mode_local", self._use_internal)
        y2 = HERO_BOTTOM + 140
        self._round(13, y2, w-13, y2+78, 14, "#302e3e",
                    outline="#59546e", tags=("mode_external",))
        self._text(28, y2+25, "Modo servidor externo", 14, WHITE,
                   bold=True, tags=("mode_external",))
        self._text(28, y2+53, "Conexión Xtream con usuario y contraseña",
                   10, MUTED, tags=("mode_external",))
        self._click("mode_external", self._use_external)
        self._text(w/2, HERO_BOTTOM+247,
                   "Puedes cambiar de modo desde Cuenta.",
                   9, MUTED, anchor="center")

    def _draw_other(self, w, h):
        c=self.canvas
        c.create_rectangle(0,HERO_BOTTOM,w,h,fill=PANEL,outline="")
        if self.active_tab == "Cuenta":
            self._draw_mode_choice(w, h)
            return
        if self.active_tab=="Inicio":
            heading = "TVAPP · " + (
                "IPTV-org" if self.mode == "local" else "Servidor externo"
            )
            desc = ("Canales por región y categoría."
                    if self.mode == "local"
                    else "Canales disponibles desde tu servidor Xtream.")
        elif self.active_tab=="Cuenta":
            heading,desc="Tu cuenta","Favoritos guardados en este dispositivo."
        else:
            heading,desc=self.active_tab,"Explora listas IPTV disponibles."
        self._text(18,HERO_BOTTOM+40,heading,17,WHITE,bold=True)
        self._text(18,HERO_BOTTOM+76,desc,11,MUTED,width=w-36)
        self._round(15,HERO_BOTTOM+108,w-15,HERO_BOTTOM+176,14,CARD,tags=("to_live",))
        self._text(26,HERO_BOTTOM+132,"▶  Explorar canales",15,CYAN,bold=True,tags=("to_live",))
        self._text(26,HERO_BOTTOM+157,"Noticias · Deportes · Películas · Música",10,MUTED,tags=("to_live",))
        self._click("to_live",lambda:self._select_tab("Vivo"))
        self._text(19,HERO_BOTTOM+210,f"Favoritos: {len(self.favorites)}",11,MUTED)

    def _icon(self, name, x, y, color, tags=()):
        c=self.canvas
        if name=="Inicio":
            c.create_line(x-9,y,x,y-8,x+9,y,fill=color,width=2,tags=tags)
            c.create_rectangle(x-7,y,x+7,y+10,outline=color,width=1.5,tags=tags)
        elif name=="Vivo":
            c.create_rectangle(x-10,y-5,x+10,y+11,outline=color,width=1.5,tags=tags)
            c.create_polygon(x-3,y-2,x+5,y+3,x-3,y+8,fill=color,tags=tags)
        elif name=="VOD":
            c.create_rectangle(x-10,y-5,x+10,y+11,outline=color,width=1.5,tags=tags)
            c.create_line(x-10,y-8,x+10,y-8,fill=color,width=1.6,tags=tags)
        elif name=="Partidos":
            c.create_arc(x-9,y-7,x+9,y+9,start=180,extent=180,style="arc",outline=color,width=1.6,tags=tags)
            c.create_line(x,y+9,x,y+16,fill=color,width=1.5,tags=tags)
        else:
            c.create_oval(x-5,y-9,x+5,y+1,outline=color,width=1.6,tags=tags)
            c.create_arc(x-10,y+3,x+10,y+23,start=0,extent=180,style="arc",outline=color,width=1.6,tags=tags)

    def _draw_nav(self,w,h):
        x1,x2=11,w-11
        y1,y2=h-75,h-8
        self._round(x1,y1,x2,y2,25,"#2c2e40",outline="#565a74")
        segment=(x2-x1)/5
        for i,tab in enumerate(self.NAV):
            x=x1+segment*(i+.5)
            tag=f"nav_{i}"
            active=tab==self.active_tab
            if active:
                self._round(x-segment*.46,y1+2,x+segment*.46,y2-2,18,"#2b5464",tags=(tag,))
            col=CYAN if active else "#c1c6d1"
            self._icon(tab,x,y1+18,col,tags=(tag,))
            self._text(x,y2-15,tab,9,col,active,"center",tags=(tag,),italic=True)
            self._click(tag,lambda t=tab:self._select_tab(t))

    def _find_vlc(self):
        paths=[]
        for var in ("ProgramFiles", "ProgramFiles(x86)"):
            if os.environ.get(var):
                paths.append(Path(os.environ[var])/"VideoLAN"/"VLC")
        for folder in paths:
            if (folder/"libvlc.dll").is_file():
                if hasattr(os,"add_dll_directory"):
                    try:
                        self.vlc_dll_handles.append(os.add_dll_directory(str(folder)))
                    except OSError:
                        pass
                os.environ.setdefault("PYTHON_VLC_LIB_PATH",str(folder/"libvlc.dll"))
                os.environ.setdefault("PYTHON_VLC_MODULE_PATH",str(folder/"plugins"))
                return folder/"vlc.exe"
        return shutil.which("vlc")

    def _ensure_vlc_in_worker(self, token):
        error=None
        try:
            importlib.invalidate_caches()
            try:
                module=importlib.import_module("vlc")
            except ModuleNotFoundError:
                process=subprocess.run([sys.executable,"-m","pip","install","--disable-pip-version-check",
                                        "--no-input","python-vlc"],stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,text=True,timeout=120,
                                       creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
                if process.returncode:
                    raise RuntimeError("No se pudo instalar python-vlc. Instala VLC en Windows.")
                importlib.invalidate_caches()
                module=importlib.import_module("vlc")
            self.events.put(("vlc_ready",(token,module,None)))
            return
        except Exception as exc:
            error=f"VLC no disponible: {str(exc)[:100]}"
        self.events.put(("vlc_ready",(token,None,error)))

    def _open_channel(self, channel):
        if channel.get("source") == "xtream":
            if not self.xtream_session:
                self.xtream_note = "Conecta la cuenta en la pestaña Cuenta."
                self.active_tab = "Cuenta"
                self.redraw()
                return
            if channel.get("account_tag") != self.xtream_session["account_tag"]:
                self.hint = "El favorito pertenece a otra cuenta Xtream."
                self.redraw()
                return
            if channel.get("kind") == "series":
                self._show_xtream_series(channel)
                return
            try:
                playback_item = dict(channel)
                playback_item["url"] = xtream_stream_url(
                    self.xtream_session, channel)
                channel = playback_item
            except ValueError as exc:
                self.hint = str(exc)
                self.redraw()
                return
        self._release_player()
        self.selected=channel
        self.player_state="Preparando reproducción..."
        self.player_token+=1
        token=self.player_token
        self.redraw()
        self._find_vlc()
        threading.Thread(target=self._ensure_vlc_in_worker,args=(token,),daemon=True).start()

    def _start_embedded_vlc(self, vlc):
        """VLC reproduce en el mismo rectangulo donde estaba la fotografia."""
        if self.selected is None:
            return
        try:
            self.video_frame = tk.Frame(self, bg="black", bd=0, highlightthickness=0)
            self._position_video()
            self.video_frame.update_idletasks()
            instance = vlc.Instance(
                "--quiet", "--network-caching=1200", "--no-video-title-show",
                "--no-video-deco",
            )
            if instance is None:
                raise RuntimeError("No se pudo inicializar libVLC.")
            player = instance.media_player_new()
            media = instance.media_new(self.selected["url"])
            for key, value in self.selected.get("headers", {}).items():
                if key == "http-user-agent":
                    media.add_option(":http-user-agent=" + value)
                elif key == "http-referrer":
                    media.add_option(":http-referrer=" + value)
            player.set_media(media)
            if sys.platform.startswith("win"):
                player.set_hwnd(self.video_frame.winfo_id())
            elif sys.platform == "darwin":
                player.set_nsobject(self.video_frame.winfo_id())
            else:
                player.set_xwindow(self.video_frame.winfo_id())
            self.vlc_instance = instance
            self.vlc_player = player
            result = player.play()
            self.player_state = (
                "Conectando transmisión..." if result != -1
                else "No se pudo iniciar la transmisión."
            )
            if result == -1:
                self._release_player()
        except Exception as exc:
            self.player_state = "Reproductor no disponible: " + str(exc)[:110]
            self._release_player()
        self.redraw()

    def _position_video(self):
        """Solo cubre el visor superior: y=80 hasta HERO_BOTTOM."""
        if self.selected is None:
            self.video_controls.place_forget()
            return
        width = max(1, self.canvas.winfo_width())
        height = max(1, HERO_BOTTOM - 80)
        if self.video_frame and self.video_frame.winfo_exists():
            self.video_frame.place(x=0, y=80, width=width, height=height)
            self.video_frame.lift()
        title = self.selected.get("name", "En vivo")
        if len(title) > 29:
            title = title[:28] + "…"
        self.video_title.configure(text=title)
        # Controles encima del video, sin tapar las tarjetas ni el menu inferior.
        self.video_controls.place(x=0, y=HERO_BOTTOM-31, width=width, height=31)
        self.video_controls.lift()

    def _release_player(self):
        self.player_token+=1
        if self.vlc_player:
            try:
                self.vlc_player.stop()
                self.vlc_player.release()
            except Exception:
                pass
        self.vlc_player=None
        if self.vlc_instance:
            try:self.vlc_instance.release()
            except Exception:pass
        self.vlc_instance=None
        if self.video_frame:
            try:self.video_frame.destroy()
            except tk.TclError:pass
        self.video_frame=None
        try:
            if self.video_controls.winfo_exists():
                self.video_controls.place_forget()
        except tk.TclError:
            pass

    def _close_player(self):
        self._release_player()
        self.selected=None
        self.redraw()

    def _toggle_playback(self):
        if self.vlc_player:
            try:self.vlc_player.pause()
            except Exception:pass
        self.redraw()

    def _toggle_mute(self):
        if self.vlc_player:
            self.player_muted=not self.player_muted
            try:self.vlc_player.audio_set_mute(self.player_muted)
            except Exception:pass
        self.redraw()

    def _open_external(self):
        if not self.selected:return
        url=self.selected["url"]
        path=self._find_vlc()
        if path:
            try:
                subprocess.Popen([str(path),url],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                self.player_state="Abriendo VLC externo..."
            except OSError as exc:
                self.player_state="No se pudo abrir VLC: "+str(exc)[:70]
        else:
            webbrowser.open(url)
            self.player_state="Sin VLC. El navegador podría no reproducir HLS."
        self.redraw()

    def redraw(self):
        c=self.canvas
        if not c.winfo_exists():return
        w,h=c.winfo_width(),c.winfo_height()
        if w<10 or h<10:return
        c.delete("all")
        self.xtream_form.place_forget()
        c.create_rectangle(0,0,w,h,fill=BG,outline="")
        self._draw_header(w)
        self._draw_hero(w)
        if self.mode is None:
            self.group_picker.place_forget()
            self._draw_mode_choice(w,h)
        elif self.active_tab in ("Vivo","VOD","Partidos"):
            self._draw_live(w,h)
        else:
            self.group_picker.place_forget()
            self._draw_other(w,h)
        self._draw_nav(w,h)
        # No se reemplaza la lista de canales al elegir uno:
        # el visor superior muestra VLC y la lista permanece visible.
        self._position_video()


def render(parent):
    """Regresa un widget embebible dentro de app.py."""
    lock_mobile_window(parent.winfo_toplevel())
    return TVSports(parent)


def main():
    root = tk.Tk()
    root.title(f"ARCHMOBA - TVAPP v{VERSION}")
    root.configure(bg=BG)
    root.update_idletasks()
    x = max(0, (root.winfo_screenwidth()-WINDOW_WIDTH)//2)
    y = max(0, (root.winfo_screenheight()-WINDOW_HEIGHT)//2)
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
    lock_mobile_window(root)
    render(root).pack(fill="both",expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()