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
SPLASH_MIN_MS = 3000
SPLASH_MAX_MS = 5400
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


class TVViewer(tk.Frame):
    """Visor VLC panoramico, sin interfaz adicional ni bloqueo Tk."""

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

        # Solo el video, sin barra de titulo, detalles ni controles visibles.
        # 380 x 214: visor panoramico 16:9 en la parte superior.
        self.video = tk.Frame(
            self, bg="#000000", height=214, highlightthickness=0,
            borderwidth=0,
        )
        self.video.pack(side="top", fill="x")
        self.video.pack_propagate(False)

        # Estado interno no visible; los errores no agregan elementos al visor.
        self.status = tk.StringVar(value="")
        self.channel_name = tk.StringVar(value="")
        self.channel_group = tk.StringVar(value="")

        self.bind("<Destroy>", self.on_destroy, add="+")
        self.after(125, self.poll_events)

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
            self.video.update_idletasks()
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
                player.set_hwnd(self.video.winfo_id())
            elif sys.platform == "darwin":
                player.set_nsobject(self.video.winfo_id())
            else:
                player.set_xwindow(self.video.winfo_id())
            self.instance, self.player, self.media = instance, player, media
            if player.play() == -1:
                raise RuntimeError("VLC no pudo iniciar la transmisión.")
            self.status.set("Conectando a la señal de video...")
            self.after(1300, lambda: self.monitor_player(token))
        except Exception as exc:
            self.release_player()
            self.status.set("VLC no disponible: " + str(exc)[:120] + ". Instala VLC Desktop.")

    def monitor_player(self, token):
        if self.dead or token != self.request_id or self.player is None:
            return
        try:
            state = str(self.player.get_state()).lower()
            if "error" in state:
                self.release_player()
                self.status.set("Error de la transmisión. Prueba Reproducir u Otro canal.")
                return
            if "ended" in state:
                self.release_player()
                self.status.set("La transmisión finalizó. Puedes volver a reproducirla.")
                return
            if "playing" in state:
                self.status.set("En vivo · " + self.channel["name"])
            elif "buffering" in state:
                self.status.set("Cargando señal en directo...")
        except Exception:
            pass
        self.after(1500, lambda: self.monitor_player(token))

    def stop_current(self):
        self.request_id += 1
        self.release_player()
        if not self.dead:
            self.status.set("Reproducción detenida.")

    def release_player(self):
        player, media, instance = self.player, self.media, self.instance
        self.player = self.media = self.instance = None
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
                    self.status.set(value)
                    self.channel_name.set("No se pudo abrir initial.json")
                elif event == "vlc" and token == self.request_id:
                    if value is None:
                        self.status.set("Instala VLC Desktop en Windows. " + str(extra)[:110])
                    else:
                        self.start_embedded(value, token)
        except queue.Empty:
            pass
        self.after(125, self.poll_events)

    def on_destroy(self, event):
        if event.widget is not self:
            return
        self.dead = True
        self.request_id += 1
        self.catalog_request += 1
        self.release_player()
        for handle in self.dll_handles:
            try:
                handle.close()
            except OSError:
                pass
        self.dll_handles.clear()


def render(parent):
    """Devuelve el visor y superpone la bienvenida original de MINGA TV."""
    parent.configure(bg=BG)
    window = parent.winfo_toplevel()
    window.configure(bg=BG)
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