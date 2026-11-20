"""FUTUREO LIVE - Fondo animado mas dinamico, sin marcos ni paneles.

Fuente principal: assets/fondo_rapido_4k_v1_9.mp4 (H.264, 3840x2160).
La escena usa humo luminoso azul y violeta sobre un centro despejado.
Se reproduce continuamente sin sonido, con la ventana completamente cubierta.
Si OpenCV o el MP4 no estan disponibles, usa el GIF del mismo fondo limpio.
Al abrirse, comprueba el MP4 en GitHub sin bloquear la interfaz.
"""
from __future__ import annotations

import hashlib
import io
import os
from pathlib import Path
import threading
import time
import tkinter as tk
from urllib.request import Request, urlopen

from PIL import Image, ImageOps, ImageTk

try:
    import cv2
except (ImportError, OSError):
    cv2 = None

VERSION = "1.9.0"
FONDO = "#050A19"
BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
VIDEO_PATH = ASSETS / "fondo_rapido_4k_v1_9.mp4"
GIF_PATH = ASSETS / "fondo_rapido_v1_9.gif"
URL_ROOT = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/FUTUREOLIVE/assets"
VIDEO_URL = URL_ROOT + "/fondo_rapido_4k_v1_9.mp4"
GIF_URL = URL_ROOT + "/fondo_rapido_v1_9.gif"
MAX_VIDEO_BYTES = 32 * 1024 * 1024
MAX_GIF_BYTES = 8 * 1024 * 1024


class FondoFutureo(tk.Canvas):
    """Renderiza el MP4 en un Canvas Tkinter; no muestra botones ni rótulos."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, bg=FONDO, bd=0, highlightthickness=0)
        self._size = (0, 0)
        self._photo: ImageTk.PhotoImage | None = None
        self._job: str | None = None
        self._check_job: str | None = None
        self._cap = None
        self._fps = 30.0
        self._next_due = 0.0
        self._gif_frames: list[Image.Image] = []
        self._gif_delays: list[int] = []
        self._gif_index = 0
        self._mode: str | None = None
        self._download_ready = threading.Event()
        self._download_changed = False
        self._alive = True
        self.bind("<Configure>", self._resize)
        self.bind("<Destroy>", self._destroy, add="+")
        self.after_idle(self._load_local)
        threading.Thread(target=self._download_asset, name="futureo-mp4", daemon=True).start()
        self._check_job = self.after(350, self._check_download)

    def _stop_playback(self) -> None:
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except tk.TclError:
                pass
            self._job = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def _start_video(self) -> bool:
        if cv2 is None or not VIDEO_PATH.is_file():
            return False
        cap = cv2.VideoCapture(str(VIDEO_PATH))
        try:
            if not cap.isOpened():
                return False
            ok, _frame = cap.read()
            if not ok:
                return False
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self._stop_playback()
            self._cap = cap
            cap = None
            raw_fps = self._cap.get(cv2.CAP_PROP_FPS)
            self._fps = float(raw_fps) if 1 <= raw_fps <= 60 else 30.0
            self._next_due = time.monotonic()
            self._mode = "mp4"
            self._gif_frames.clear()
            self._gif_delays.clear()
            self._job = self.after(1, self._next_frame)
            return True
        finally:
            if cap is not None:
                cap.release()

    def _start_gif(self) -> bool:
        if not GIF_PATH.is_file():
            return False
        try:
            frames: list[Image.Image] = []
            delays: list[int] = []
            with Image.open(GIF_PATH) as img:
                count = getattr(img, "n_frames", 1)
                if count < 2 or count > 300:
                    return False
                for i in range(count):
                    img.seek(i)
                    frames.append(img.convert("RGB").copy())
                    delays.append(max(50, min(1500, int(img.info.get("duration") or 220))))
            self._stop_playback()
            self._gif_frames, self._gif_delays = frames, delays
            self._gif_index = 0
            self._mode = "gif"
            self._job = self.after(1, self._next_frame)
            return True
        except (OSError, ValueError, EOFError):
            return False

    def _load_local(self) -> None:
        if not self._alive:
            return
        if not self._start_video():
            self._start_gif()

    def _download_asset(self) -> None:
        """Descarga el archivo original y mantiene la copia local si falla Internet."""
        choices = (
            [(VIDEO_URL, VIDEO_PATH, MAX_VIDEO_BYTES, "mp4")]
            if cv2 is not None else []
        ) + [(GIF_URL, GIF_PATH, MAX_GIF_BYTES, "gif")]
        try:
            for url, path, limit, kind in choices:
                # Descargar solo el video si OpenCV funciona; GIF queda de respaldo.
                if kind == "gif" and self._mode == "mp4":
                    break
                try:
                    req = Request(url, headers={
                        "User-Agent": "FUTUREO-LIVE/1.9",
                        "Cache-Control": "no-cache",
                    })
                    with urlopen(req, timeout=18) as resp:
                        data = resp.read(limit + 1)
                    if not data or len(data) > limit:
                        continue
                    if kind == "mp4" and data[4:8] != b"ftyp":
                        continue
                    if kind == "gif" and not data.startswith((b"GIF89a", b"GIF87a")):
                        continue
                    if path.is_file():
                        if hashlib.sha256(path.read_bytes()).digest() == hashlib.sha256(data).digest():
                            if kind == "mp4":
                                break
                            continue
                    ASSETS.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix(path.suffix + ".tmp")
                    try:
                        tmp.write_bytes(data)
                        # En Windows un MP4 en reproduccion puede estar bloqueado.
                        # Si sucede, la version anterior continua funcionando.
                        os.replace(tmp, path)
                        self._download_changed = True
                    finally:
                        tmp.unlink(missing_ok=True)
                    if kind == "mp4":
                        break
                except (OSError, ValueError, TimeoutError):
                    continue
        finally:
            self._download_ready.set()

    def _check_download(self) -> None:
        self._check_job = None
        if not self._alive:
            return
        if self._download_ready.is_set():
            if self._download_changed:
                self._load_local()
        else:
            self._check_job = self.after(350, self._check_download)

    def _resize(self, event: tk.Event) -> None:
        self._size = (max(1, int(event.width)), max(1, int(event.height)))

    def _draw(self, image: Image.Image) -> None:
        if self._size[0] < 2 or self._size[1] < 2:
            return
        fitted = ImageOps.fit(
            image, self._size, method=Image.Resampling.BILINEAR,
            centering=(.5, .5),
        )
        self._photo = ImageTk.PhotoImage(fitted, master=self)
        self.delete("fondo")
        self.create_image(
            self._size[0] // 2, self._size[1] // 2,
            anchor="center", image=self._photo, tags="fondo",
        )

    def _draw_video(self, frame) -> None:
        """Ajusta el fotograma con OpenCV conservando su centro y nitidez."""
        width, height = self._size
        if width < 2 or height < 2:
            return
        frame_height, frame_width = frame.shape[:2]
        if frame_width * height > frame_height * width:
            crop_width = max(1, frame_height * width // height)
            offset = (frame_width - crop_width) // 2
            frame = frame[:, offset:offset + crop_width]
        elif frame_width * height < frame_height * width:
            crop_height = max(1, frame_width * height // width)
            offset = (frame_height - crop_height) // 2
            frame = frame[offset:offset + crop_height, :]
        if frame.shape[1] != width or frame.shape[0] != height:
            method = cv2.INTER_AREA if frame.shape[1] >= width else cv2.INTER_CUBIC
            frame = cv2.resize(frame, (width, height), interpolation=method)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._photo = ImageTk.PhotoImage(Image.fromarray(rgb), master=self)
        self.delete("fondo")
        self.create_image(width // 2, height // 2, anchor="center",
                          image=self._photo, tags="fondo")

    def _next_frame(self) -> None:
        self._job = None
        if not self._alive or not self.winfo_exists():
            return
        if self._mode == "mp4" and self._cap is not None and cv2 is not None:
            success, frame = self._cap.read()
            if not success:
                # MP4 en bucle continuo sin volver a abrir el archivo.
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                success, frame = self._cap.read()
            if success:
                # Decodificar el MP4 y pasarlo a Tkinter sin filtros añadidos.
                self._draw_video(frame)
                self._next_due += 1.0 / self._fps
                now = time.monotonic()
                if self._next_due < now - .2:
                    self._next_due = now
                wait = max(1, int((self._next_due - now) * 1000))
                self._job = self.after(wait, self._next_frame)
                return
            if self._start_gif():
                return
            self._job = self.after(1500, self._next_frame)
        elif self._mode == "gif" and self._gif_frames:
            index = self._gif_index
            self._draw(self._gif_frames[index])
            self._gif_index = (index + 1) % len(self._gif_frames)
            self._job = self.after(self._gif_delays[index], self._next_frame)

    def _destroy(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        self._alive = False
        self._stop_playback()
        if self._check_job is not None:
            try:
                self.after_cancel(self._check_job)
            except tk.TclError:
                pass
            self._check_job = None


def render(parent: tk.Misc) -> tk.Widget:
    """Entrada compatible con el lanzador app.py del repositorio."""
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