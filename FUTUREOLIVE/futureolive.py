"""FUTUREO LIVE - Fondo MP4 sin marcos; base limpia para overlays futuros.

Fuente principal: assets/fondo_sin_marcos_4k.mp4 (H.264, 3840x2160).
La escena usa humo luminoso azul y violeta sobre un centro despejado.
Se reproduce continuamente sin sonido, con la ventana completamente cubierta.
Si OpenCV o el MP4 no estan disponibles, usa el GIF del mismo fondo limpio.
Al abrirse, comprueba el MP4 en GitHub sin bloquear la interfaz.
"""
from __future__ import annotations

import hashlib
import io
import os
import random
from pathlib import Path
import threading
import time
import tkinter as tk
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageTk

try:
    import cv2
except (ImportError, OSError):
    cv2 = None

VERSION = "2.2.2"
FONDO = "#050A19"
BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
VIDEO_PATH = ASSETS / "fondo_sin_marcos_4k.mp4"
GIF_PATH = ASSETS / "fondo_sin_marcos.gif"
URL_ROOT = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/FUTUREOLIVE/assets"
VIDEO_URL = URL_ROOT + "/fondo_sin_marcos_4k.mp4"
GIF_URL = URL_ROOT + "/fondo_sin_marcos.gif"
MAX_VIDEO_BYTES = 32 * 1024 * 1024
MAX_GIF_BYTES = 8 * 1024 * 1024


class FondoFutureo(tk.Canvas):
    """Renderiza el MP4 en un Canvas Tkinter; no muestra botones ni rótulos."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, bg=FONDO, bd=0, highlightthickness=0)
        self._size = (0, 0)
        self._photo: ImageTk.PhotoImage | None = None
        # Capa de tormenta completamente independiente del fondo MP4.
        self._lightning_job: str | None = None
        self._lightning_clear_job: str | None = None
        self._lightning_path: list[tuple[int, int]] = []
        self._lightning_branches: list[list[tuple[int, int]]] = []
        self._lightning_target = (0, 0)
        self._lightning_phase = -1
        self._lightning_cached: Image.Image | None = None
        self._lightning_cache_key = None
        self._last_frame: Image.Image | None = None
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
        self._schedule_lightning(initial=True)

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
                        "User-Agent": "FUTUREO-LIVE/2.0",
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
        self._lightning_cached = None
        self._lightning_cache_key = None

    def _schedule_lightning(self, initial: bool = False) -> None:
        """Intervalo aleatorio entre descargas."""
        if not self._alive:
            return
        delay = random.randint(1100, 2100) if initial else random.randint(2000, 6000)
        self._lightning_job = self.after(delay, self._strike_lightning)

    def _strike_lightning(self) -> None:
        """Traza una descarga quebrada con ramificaciones de longitud variable."""
        self._lightning_job = None
        if not self._alive:
            return
        width, height = self._size
        if width < 160 or height < 120:
            self._schedule_lightning()
            return
        tx = random.randint(int(width * .15), int(width * .85))
        ty = random.randint(int(height * .44), int(height * .9))
        sx = max(1, min(width - 2, tx + random.randint(-width // 6, width // 6)))
        count = random.randint(17, 27)
        path = [(sx, 0)]
        wander = 0.0
        for i in range(1, count):
            fraction = i / count
            wander = max(-width * .07, min(width * .07,
                         wander * .52 + random.gauss(0, width * .016)))
            x = sx + (tx - sx) * fraction + wander
            y = ty * fraction
            path.append((int(max(0, min(width - 1, x))), int(y)))
        path.append((tx, ty))
        branches = []
        for i in range(3, len(path) - 4):
            if random.random() > .27:
                continue
            x, y = path[i]
            direction = random.choice((-1, 1))
            length = random.uniform(.06, .16) * min(width, height)
            pieces = random.randint(3, 6)
            branch = [(x, y)]
            for j in range(1, pieces + 1):
                fraction = j / pieces
                bx = x + direction * length * fraction + random.gauss(0, width * .009)
                by = y + length * fraction * random.uniform(.46, .85)
                branch.append((int(max(0, min(width-1, bx))),
                               int(min(height-1, by))))
            branches.append(branch)
        self._lightning_path = path
        self._lightning_branches = branches
        self._lightning_target = (tx, ty)
        self._lightning_phase = 0
        self._lightning_cached = None
        self._lightning_cache_key = None
        self._refresh_last_frame()
        self._schedule_lightning()
        self._lightning_clear_job = self.after(55, self._advance_lightning, 1)

    def _advance_lightning(self, phase: int) -> None:
        """Dos impulsos intensos seguidos por un resplandor que se desvanece."""
        self._lightning_clear_job = None
        if not self._alive:
            return
        self._lightning_phase = phase if phase < 5 else -1
        self._lightning_cached = None
        self._lightning_cache_key = None
        self._refresh_last_frame()
        if phase < 5:
            intervals = (55, 42, 95, 115, 125)
            self._lightning_clear_job = self.after(
                intervals[phase], self._advance_lightning, phase + 1
            )

    def _lightning_overlay(self, size: tuple[int, int]) -> Image.Image | None:
        """Pinta brillo volumetrico y relampago antialias sobre RGBA."""
        phase = self._lightning_phase
        if phase < 0 or not self._lightning_path:
            return None
        key = (size, phase)
        if self._lightning_cached is not None and self._lightning_cache_key == key:
            return self._lightning_cached

        w, h = size
        scale = max(.5, min(w, h) / 700.0)
        intensity = (.97, .16, 1.0, .34, .11)[phase]
        core = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(core, "RGBA")
        path = self._lightning_path

        # Atmosfera localizada con radios amplios y gradiente difuso.
        cloud = Image.new("RGBA", size, (0, 0, 0, 0))
        cd = ImageDraw.Draw(cloud, "RGBA")
        for x, y in (path[4], path[len(path)//2], path[-1]):
            radius = int(min(w, h) * .17)
            cd.ellipse((x-radius, y-radius, x+radius, y+radius),
                       fill=(45, 145, 255, int(64 * intensity)))
        cloud = cloud.filter(ImageFilter.GaussianBlur(max(12, int(42 * scale))))

        # Halo de los canales electricos; la difusion se realiza antes del nucleo.
        glow = Image.new("RGBA", size, (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow, "RGBA")
        for pts in [path] + self._lightning_branches:
            thickness = (12 if pts is path else 6) * scale
            gd.line(pts, fill=(39, 130, 255, int(195 * intensity)),
                    width=max(2, int(thickness)), joint="curve")
        glow = glow.filter(ImageFilter.GaussianBlur(max(3, int(12 * scale))))
        cloud = Image.alpha_composite(cloud, glow)

        # La descarga tiene un nucleo central muy fino y bordes azulados.
        for pts in [path] + self._lightning_branches:
            branch = pts is not path
            for index in range(len(pts)-1):
                t = index / max(1, len(pts)-1)
                thick = max(1, int((2.8 if not branch else 1.35) * scale *
                                   (1.15 - .55 * t)))
                a, b = pts[index], pts[index+1]
                draw.line((a,b), fill=(35, 156, 255, int(225 * intensity)),
                          width=max(2, thick + 3))
                draw.line((a,b), fill=(235, 251, 255, int(255 * intensity)),
                          width=thick)
        # Fogonazo global corto: el propio fotograma se ilumina al impactar.
        if phase in (0, 2):
            flash = Image.new("RGBA", size,
                              (175, 216, 255, int(23 * intensity)))
            cloud = Image.alpha_composite(flash, cloud)
        overlay = Image.alpha_composite(cloud, core)
        self._lightning_cached = overlay
        self._lightning_cache_key = key
        return overlay

    def _present(self, frame: Image.Image) -> None:
        """Compone las luces sobre el fotograma, sin alterar el MP4 original."""
        self._last_frame = frame
        overlay = self._lightning_overlay(frame.size)
        composed = (Image.alpha_composite(frame.convert("RGBA"), overlay)
                    if overlay is not None else frame)
        self._photo = ImageTk.PhotoImage(composed, master=self)
        self.delete("fondo")
        self.create_image(frame.width // 2, frame.height // 2,
                          anchor="center", image=self._photo, tags="fondo")
        self.tag_lower("fondo")

    def _refresh_last_frame(self) -> None:
        if self._last_frame is not None and self._alive:
            self._present(self._last_frame)


    def _draw(self, image: Image.Image) -> None:
        if self._size[0] < 2 or self._size[1] < 2:
            return
        fitted = ImageOps.fit(
            image, self._size, method=Image.Resampling.BILINEAR,
            centering=(.5, .5),
        )
        self._present(fitted)

    def _draw_video(self, frame) -> None:
        """Escala el fotograma y aplica luces sin bloquear la reproduccion."""
        width, height = self._size
        if width < 2 or height < 2:
            return
        fh, fw = frame.shape[:2]
        if fw * height > fh * width:
            cw = max(1, fh * width // height)
            offset = (fw - cw) // 2
            frame = frame[:, offset:offset + cw]
        elif fw * height < fh * width:
            ch = max(1, fw * height // width)
            offset = (fh - ch) // 2
            frame = frame[offset:offset + ch, :]
        if frame.shape[1] != width or frame.shape[0] != height:
            method = cv2.INTER_AREA if frame.shape[1] >= width else cv2.INTER_CUBIC
            frame = cv2.resize(frame, (width, height), interpolation=method)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._present(Image.fromarray(rgb))

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
        for job in (self._lightning_job, self._lightning_clear_job):
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
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