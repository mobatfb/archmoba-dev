"""FUTUREO LIVE: reproduce el GIF original como fondo de toda la ventana.

Fondo: FUTUREOLIVE/assets/fondo_animado.gif (9 fotogramas, GIF animado).
Si falta, se descarga del repositorio en un hilo; sin conexion usa la
copia local. No se dibujan adornos, paneles ni animaciones alternativas.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import threading
import tkinter as tk
from urllib.request import Request, urlopen

from PIL import Image, ImageOps, ImageTk

VERSION = "1.5.0"
FONDO = "#050A19"
BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
GIF_PATH = ASSETS / "fondo_animado.gif"
GIF_URL = (
    "https://raw.githubusercontent.com/mobatfb/archmoba-dev/"
    "main/FUTUREOLIVE/assets/fondo_animado.gif"
)
MAX_GIF_BYTES = 8 * 1024 * 1024


class FondoFutureo(tk.Canvas):
    """Visualiza los fotogramas reales del GIF, adaptados al tamano actual."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, bg=FONDO, bd=0, highlightthickness=0)
        self._frames: list[Image.Image] = []
        self._durations: list[int] = []
        self._frame_index = 0
        self._photo: ImageTk.PhotoImage | None = None
        self._animation_job: str | None = None
        self._download_job: str | None = None
        self._download_complete = threading.Event()
        self._download_changed = False
        self._size = (0, 0)
        self.bind("<Configure>", self._resize)
        self.bind("<Destroy>", self._destroy, add="+")

        # La copia local se visualiza inmediatamente; la descarga posterior
        # permite actualizar el GIF sin bloquear la ventana de streaming.
        self.after_idle(self._load_local)
        threading.Thread(
            target=self._download_original, name="futureo-background",
            daemon=True,
        ).start()
        self._download_job = self.after(300, self._check_download)

    def _load_local(self) -> None:
        if not GIF_PATH.is_file():
            return
        try:
            frames: list[Image.Image] = []
            durations: list[int] = []
            with Image.open(GIF_PATH) as gif:
                count = getattr(gif, "n_frames", 1)
                if count < 2 or count > 200:
                    raise ValueError("El archivo debe ser un GIF animado valido.")
                for index in range(count):
                    gif.seek(index)
                    frames.append(gif.convert("RGB").copy())
                    durations.append(max(60, min(1000, int(gif.info.get("duration") or 220))))
            self._frames = frames
            self._durations = durations
            self._frame_index = 0
            self._refresh_animation()
        except (OSError, ValueError, EOFError):
            # La ventana se mantiene limpia en caso de archivo incompleto.
            pass

    def _download_original(self) -> None:
        try:
            request = Request(
                GIF_URL,
                headers={"User-Agent": "FUTUREO-LIVE/1.5", "Cache-Control": "no-cache"},
            )
            with urlopen(request, timeout=12) as response:
                data = response.read(MAX_GIF_BYTES + 1)
            if len(data) > MAX_GIF_BYTES or not data.startswith((b"GIF89a", b"GIF87a")):
                return
            with Image.open(io.BytesIO(data)) as gif:
                if getattr(gif, "n_frames", 1) < 2:
                    return
            if GIF_PATH.is_file():
                previous = hashlib.sha256(GIF_PATH.read_bytes()).digest()
                if hashlib.sha256(data).digest() == previous:
                    return
            ASSETS.mkdir(parents=True, exist_ok=True)
            temporary = GIF_PATH.with_name(GIF_PATH.name + ".tmp")
            try:
                temporary.write_bytes(data)
                os.replace(temporary, GIF_PATH)
                self._download_changed = True
            finally:
                temporary.unlink(missing_ok=True)
        except (OSError, ValueError, EOFError):
            # Sin conexion se conserva el ultimo fondo descargado.
            pass
        finally:
            self._download_complete.set()

    def _check_download(self) -> None:
        self._download_job = None
        if self._download_complete.is_set():
            if self._download_changed:
                self._load_local()
        elif self.winfo_exists():
            self._download_job = self.after(300, self._check_download)

    def _resize(self, event: tk.Event) -> None:
        size = (max(1, int(event.width)), max(1, int(event.height)))
        if size != self._size:
            self._size = size
            self._refresh_animation()

    def _refresh_animation(self) -> None:
        if self._animation_job is not None:
            self.after_cancel(self._animation_job)
            self._animation_job = None
        if self._frames and self._size[0] > 1 and self._size[1] > 1:
            self._show_frame()

    def _show_frame(self) -> None:
        self._animation_job = None
        if not self._frames or not self.winfo_exists():
            return
        index = self._frame_index
        frame = self._frames[index]
        width, height = self._size
        fitted = ImageOps.fit(
            frame, (width, height), method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        self._photo = ImageTk.PhotoImage(fitted, master=self)
        self.delete("fondo")
        self.create_image(
            width // 2, height // 2, image=self._photo,
            anchor="center", tags="fondo",
        )
        self._frame_index = (index + 1) % len(self._frames)
        self._animation_job = self.after(self._durations[index], self._show_frame)

    def _destroy(self, event: tk.Event) -> None:
        if event.widget is self:
            for job in (self._animation_job, self._download_job):
                if job is not None:
                    try:
                        self.after_cancel(job)
                    except tk.TclError:
                        pass
            self._animation_job = None
            self._download_job = None


def render(parent: tk.Misc) -> tk.Widget:
    """Integracion con el lanzador app.py del repositorio."""
    return FondoFutureo(parent)


def main() -> None:
    root = tk.Tk()
    root.title("FUTUREO LIVE")
    root.geometry("1366x768")
    root.minsize(800, 450)
    root.configure(bg=FONDO)
    root.bind(
        "<F11>",
        lambda _e: root.attributes("-fullscreen", not bool(root.attributes("-fullscreen"))),
    )
    root.bind("<Escape>", lambda _e: root.attributes("-fullscreen", False))
    render(root).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()