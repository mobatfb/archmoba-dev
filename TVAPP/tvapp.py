"""MINGA TV: bienvenida y visor IPTV sin controles visibles para Windows.

El catalogo initial.json se consulta desde GitHub al abrir; si no hay
conexion se utiliza la ultima copia local valida. No incluye canales fijos.
"""

import importlib
import json
import os
from pathlib import Path
import queue
import random
import subprocess
import sys
import threading
import time
import tkinter as tk
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
SPLASH_MIN_MS = 3000
SPLASH_MAX_MS = 5400
VIDEO_START_TIMEOUT_S = 15
VIDEO_STALL_TIMEOUT_S = 12
RETRY_ALL_CHANNELS_MS = 60000
PLAYER_MONITOR_MS = 1000
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


class TVViewer(tk.Frame):
    """Visor VLC panoramico, con explorador de listas M3U bajo el video."""

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
        self.failed_channel_ids = set()
        self.video_started_at = None
        self.video_ready = False
        self.stall_since = None

        # Solo el video, sin barra de titulo, detalles ni controles visibles.
        # 380 x 214: visor panoramico 16:9 en la parte superior.
        self.video = tk.Frame(
            self, bg="#000000", height=214, highlightthickness=0,
            borderwidth=0,
        )
        self.video.pack(side="top", fill="x")
        self.video.pack_propagate(False)

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
        self.playlist_list = tk.Listbox(
            self.search_panel, bg=BG, fg=WHITE,
            font=("Segoe UI", 12), bd=0, relief="flat",
            highlightthickness=0, selectbackground="#1d2630",
            selectforeground="#ffd000", activestyle="none",
            exportselection=False,
        )
        self.playlist_scroll = tk.Scrollbar(
            self.search_panel, orient="vertical", command=self.playlist_list.yview
        )
        self.playlist_list.configure(yscrollcommand=self.playlist_scroll.set)
        self.playlist_list.pack(
            side="left", fill="both", expand=True, padx=(12, 0), pady=(8, 6)
        )
        self.playlist_scroll.pack(
            side="right", fill="y", padx=(0, 5), pady=(8, 6)
        )

        # VLC dibuja sobre su propia superficie; el indicador es un widget
        # hermano y queda encima sin interferir con la reproduccion.
        self.video_surface = tk.Frame(
            self.video, bg=BG, bd=0, highlightthickness=0,
        )
        self.video_surface.place(x=0, y=0, relwidth=1, relheight=1)
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

        self.bind("<Destroy>", self.on_destroy, add="+")
        self.after(125, self.poll_events)

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
        if name == "Buscar":
            self.search_panel.pack(fill="both", expand=True)
            if self.playlist_catalog is None and not self.playlists_loading:
                self.load_playlist_catalog()
        else:
            self.search_panel.pack_forget()

    def load_playlist_catalog(self):
        """Descarga las listas M3U solo al entrar en Buscar."""
        if self.dead or self.playlists_loading:
            return
        self.playlists_loading = True
        self.playlists_request += 1
        token = self.playlists_request
        self.playlist_list.delete(0, tk.END)
        self.playlist_list.insert(tk.END, "Cargando listas M3U...")

        def worker():
            try:
                playlists, offline = read_playlist_catalog()
                self.events.put(("playlists", token, playlists, offline))
            except Exception as exc:
                self.events.put(("playlists_error", token, str(exc), False))

        threading.Thread(target=worker, daemon=True).start()

    def on_playlist_catalog(self, playlists):
        self.playlists_loading = False
        self.playlist_catalog = playlists
        self.playlist_list.delete(0, tk.END)
        for item in playlists:
            self.playlist_list.insert(tk.END, item["name"])

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

    def on_catalog(self, data, offline):
        old_id = self.channel["id"] if self.channel else None
        self.data = data
        self.failed_channel_ids.clear()  # Un catalogo nuevo permite reintentar canales anteriores.
        self.channel = choose_channel(data, previous_id=old_id if data["selected_id"] == 0 else None)
        self.channel_name.set(self.channel["name"])
        label = self.channel.get("group", "General")
        if data["selected_id"] == 0:
            label += "  ·  Selección aleatoria"
        else:
            label += f"  ·  Canal #{data['selected_id']}"
        if offline:
            label += "  ·  Copia local"
        self.channel_group.set(label)
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
        """Cambia a otro canal aleatorio sin repetir los fallidos en la ronda."""
        failed = self.channel
        self.release_player()
        self.show_loading()
        self.status.set(reason)
        if self.dead or failed is None or self.data is None:
            self.hide_loading()
            return
        if self.data["selected_id"] != 0:
            self.hide_loading()
            return  # Un ID fijado en initial.json debe seguir siendo respetado.

        self.failed_channel_ids.add(failed["id"])
        available = [
            item for item in self.data["channels"]
            if item["id"] not in self.failed_channel_ids
        ]
        if available:
            self.channel = random.choice(available)
            self.channel_name.set(self.channel["name"])
            self.channel_group.set(
                self.channel.get("group", "General") + "  ·  Selección aleatoria"
            )
            self.play_current()
            return

        # Si todos fallan, esperar antes de releer initial.json, sin bucle rapido.
        self.channel = None
        self.channel_name.set("")
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
            self.status.set("Conectando a la señal de video...")
            self.after(PLAYER_MONITOR_MS, lambda: self.monitor_player(token))
        except Exception as exc:
            self.channel_failed("No se pudo abrir el canal: " + str(exc)[:120])

    def monitor_player(self, token):
        if self.dead or token != self.request_id or self.player is None:
            return
        try:
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
                self.video_ready = True
                self.stall_since = None
                self.hide_loading()
                self.status.set("En vivo · " + self.channel["name"])
            elif not self.video_ready:
                self.show_loading()
                if (self.video_started_at is not None
                        and now - self.video_started_at >= VIDEO_START_TIMEOUT_S):
                    self.channel_failed("La señal tardó demasiado en mostrar video.")
                    return
                self.status.set("Cargando señal en directo...")
            else:
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
                    self.playlist_list.delete(0, tk.END)
                    self.playlist_list.insert(tk.END, "Error al cargar. Pulsa Buscar otra vez.")
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
        self.hide_loading()
        self.dead = True
        self.request_id += 1
        self.catalog_request += 1
        self.playlists_request += 1
        self.release_player()
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