"""MINGA TV: pantalla de bienvenida para la nueva interfaz."""

from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from urllib.request import Request, urlopen

VERSION = "1.0.17"
SLOGAN = "Tu mundo de entretenimiento"

# La imagen se mantiene como recurso independiente, no incrustada en el .py.
LOGO_URL = (
    "https://raw.githubusercontent.com/mobatfb/archmoba-dev/"
    "main/TVAPP/assets/minga_tv_logo.png"
)
LOGO_FILE = Path(__file__).resolve().parent / "assets" / "minga_tv_logo.png"
SPLASH_MIN_MS = 3000
SPLASH_MAX_MS = 5400


def render(parent):
    """Muestra el splash y deja lista una pantalla vacia para construir TVAPP."""
    screen = tk.Frame(parent, bg="#171820")

    # Cubrir también la barra del iniciador, sin modificar app.py.
    window = parent.winfo_toplevel()
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

    logo_label = tk.Label(
        center, text="MINGA TV", bg="#000000", fg="#f9fbff",
        font=("Segoe UI", 28, "bold"), borderwidth=0,
    )
    logo_label.pack()

    tk.Label(
        center, text=SLOGAN, bg="#000000", fg="#e9f5ff",
        font=("Segoe UI", 12), borderwidth=0,
    ).pack(pady=(10, 0))
    tk.Frame(center, bg="#11a8ff", height=2, width=78).pack(pady=(15, 0))

    started = time.monotonic()
    loaded_at = [None]
    failed = [False]
    messages = queue.Queue()

    def use_logo():
        try:
            image = tk.PhotoImage(file=str(LOGO_FILE))
            logo_label.config(image=image, text="")
            logo_label.image = image  # Tk debe conservar la referencia.
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
    else:
        # Ya estaba en cache y se muestra inmediatamente.
        pass

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
        logo_ms = (
            (time.monotonic() - loaded_at[0]) * 1000
            if loaded_at[0] is not None else 0
        )
        can_finish = (
            elapsed >= SPLASH_MIN_MS
            and (failed[0] or (loaded_at[0] is not None and logo_ms >= 1400))
        )
        if can_finish or elapsed >= SPLASH_MAX_MS:
            splash.destroy()
            if getattr(window, "_minga_tv_splash", None) is splash:
                window._minga_tv_splash = None
        else:
            screen.after(100, tick)

    screen.after(100, tick)
    return screen