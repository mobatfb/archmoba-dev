"""FUTUREO LIVE - Fondo MP4 sin marcos; base limpia para overlays futuros.

Fuente principal: assets/fondo_sin_marcos_4k.mp4 (H.264, 3840x2160).
La escena usa humo luminoso azul y violeta sobre un centro despejado.
Se reproduce continuamente sin sonido, con la ventana completamente cubierta.
Si OpenCV o el MP4 no estan disponibles, usa el GIF del mismo fondo limpio.
Al abrirse, comprueba el MP4 en GitHub sin bloquear la interfaz.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import io
import os
import queue
import random
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.request import Request, urlopen

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageGrab, ImageOps, ImageTk

try:
    import cv2
except (ImportError, OSError):
    cv2 = None

try:
    import mss
except (ImportError, OSError):
    mss = None

VERSION = "2.7.4"
FONDO = "#050A19"
VIDEO_SPEED = 1.20  # MP4 reproducido un 20 por ciento mas rapido
VIDEO_BACKGROUND_ENABLED = False  # Cambiar a True para reactivar MP4/GIF.
WINDOW_OVERLAY_ENABLED = False  # Marco PNG anterior, desactivado.
NEON_BORDER_ENABLED = True  # Nuevo borde dibujado, sin PNG ni fondo.
NEON_BORDER_WIDTH = 0.80  # 80% del ancho del lienzo.
NEON_BORDER_HEIGHT = 0.80  # 80% del alto del lienzo.
NEON_CORNER_RADIUS_RATIO = 0.045  # Esquinas 31% menos redondeadas que antes.
SCREEN_CAPTURE_FPS = 12  # Captura local, no transmision a Internet.
SCREEN_CAPTURE_BLEED_PX = 3  # Solapa 3 px debajo del marco, sin ranuras.
SCREEN_SOURCE_CROP_PX = 2  # Elimina 2 px exteriores de cada ventana capturada.
SCREEN_CAPTURE_CORNER_OVERLAP_PX = 2  # Cubre tambien la curva interna del marco.
BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
VIDEO_PATH = ASSETS / "fondo_sin_marcos_4k.mp4"
GIF_PATH = ASSETS / "fondo_sin_marcos.gif"
WINDOW_PATH = ASSETS / "ventana_neon.png"
URL_ROOT = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/FUTUREOLIVE/assets"
VIDEO_URL = URL_ROOT + "/fondo_sin_marcos_4k.mp4"
GIF_URL = URL_ROOT + "/fondo_sin_marcos.gif"
WINDOW_URL = URL_ROOT + "/ventana_neon.png"
MAX_VIDEO_BYTES = 32 * 1024 * 1024
MAX_GIF_BYTES = 8 * 1024 * 1024
MAX_WINDOW_BYTES = 8 * 1024 * 1024




def _win_rect(hwnd: int) -> dict | None:
    """Rectangulo visible de una ventana Windows."""
    if os.name != "nt":
        return None
    user = ctypes.windll.user32
    user.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    user.GetWindowRect.restype = wintypes.BOOL
    for name in ("IsWindow", "IsWindowVisible", "IsIconic"):
        fn = getattr(user, name)
        fn.argtypes = [wintypes.HWND]
        fn.restype = wintypes.BOOL
    if not user.IsWindow(hwnd) or not user.IsWindowVisible(hwnd) or user.IsIconic(hwnd):
        return None
    rect = wintypes.RECT()
    if not user.GetWindowRect(hwnd, ctypes.byref(rect)):
        return None
    w, h = rect.right - rect.left, rect.bottom - rect.top
    if w < 80 or h < 60:
        return None
    return {"left": rect.left, "top": rect.top, "width": w, "height": h}


def _win_list() -> list[tuple[int, str]]:
    """Lista ventanas visibles con titulo real, excluyendo FUTUREO."""
    if os.name != "nt":
        return []
    user = ctypes.WinDLL("user32", use_last_error=True)
    cbtype = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user.EnumWindows.argtypes = [cbtype, wintypes.LPARAM]
    user.EnumWindows.restype = wintypes.BOOL
    user.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user.GetWindowTextLengthW.restype = ctypes.c_int
    user.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user.GetWindowTextW.restype = ctypes.c_int
    user.IsWindowVisible.argtypes = [wintypes.HWND]
    user.IsWindowVisible.restype = wintypes.BOOL
    user.IsIconic.argtypes = [wintypes.HWND]
    user.IsIconic.restype = wintypes.BOOL
    found = []

    @cbtype
    def visit(hwnd, _):
        try:
            if not user.IsWindowVisible(hwnd):
                return True
            n = user.GetWindowTextLengthW(hwnd)
            if n < 1:
                return True
            buffer = ctypes.create_unicode_buffer(min(n + 1, 512))
            user.GetWindowTextW(hwnd, buffer, len(buffer))
            title = buffer.value.strip()
            if not title or "FUTUREO LIVE" in title.upper():
                return True
            hwnd_id = int(hwnd)
            # Mostrar minimizadas en el selector, con aviso de restaurarlas.
            if user.IsIconic(hwnd):
                title += " (minimizada: restaurar para capturar)"
            elif _win_rect(hwnd_id) is None:
                return True
            found.append((hwnd_id, title[:160]))
        except (OSError, ValueError, TypeError):
            pass
        return True

    user.EnumWindows(visit, 0)
    return found



def _capture_via_printwindow(hwnd: int, width: int, height: int) -> Image.Image:
    """Captura HWND con la API GDI de Windows sin exigir Pillow 11.2+."""
    if not (1 <= width <= 7680 and 1 <= height <= 4320):
        raise RuntimeError("Tamano de ventana no admitido")

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
            ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
            ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
            ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
            ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
            ("biClrImportant", wintypes.DWORD),
        ]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [("bmiHeader", BITMAPINFOHEADER),
                    ("bmiColors", ctypes.c_uint32 * 1)]

    user = ctypes.WinDLL("user32", use_last_error=True)
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)

    user.GetWindowDC.argtypes = [wintypes.HWND]
    user.GetWindowDC.restype = wintypes.HDC
    user.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
    user.ReleaseDC.restype = ctypes.c_int
    user.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
    user.PrintWindow.restype = wintypes.BOOL

    gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi.CreateCompatibleDC.restype = wintypes.HDC
    gdi.CreateDIBSection.argtypes = [
        wintypes.HDC, ctypes.POINTER(BITMAPINFO), wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD
    ]
    gdi.CreateDIBSection.restype = wintypes.HBITMAP
    gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
    gdi.SelectObject.restype = wintypes.HGDIOBJ
    gdi.DeleteDC.argtypes = [wintypes.HDC]
    gdi.DeleteDC.restype = wintypes.BOOL
    gdi.DeleteObject.argtypes = [wintypes.HGDIOBJ]
    gdi.DeleteObject.restype = wintypes.BOOL

    hwnd = int(hwnd)
    source_dc = user.GetWindowDC(hwnd)
    if not source_dc:
        raise RuntimeError("Windows no permite acceder al contenido de la ventana")
    memory_dc = None
    bitmap = None
    previous = None
    try:
        memory_dc = gdi.CreateCompatibleDC(source_dc)
        if not memory_dc:
            raise RuntimeError("No se pudo crear el lienzo de captura GDI")

        info = BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height  # DIB top-down.
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0  # BI_RGB.
        bits = ctypes.c_void_p()
        bitmap = gdi.CreateDIBSection(
            source_dc, ctypes.byref(info), 0, ctypes.byref(bits), None, 0
        )
        if not bitmap or not bits.value:
            raise RuntimeError("Windows no pudo reservar la imagen")
        previous = gdi.SelectObject(memory_dc, bitmap)
        if not previous:
            raise RuntimeError("No se pudo preparar la imagen GDI")

        # PW_RENDERFULLCONTENT captura ventanas que estan detras de otras,
        # cuando la propia aplicacion y Windows lo permiten.
        success = user.PrintWindow(hwnd, memory_dc, 2)
        if not success:
            success = user.PrintWindow(hwnd, memory_dc, 0)
        if not success:
            raise RuntimeError("PrintWindow no pudo obtener fotogramas")

        pixels = ctypes.string_at(bits.value, width * height * 4)
        return Image.frombytes("RGB", (width, height), pixels, "raw", "BGRX")
    finally:
        if memory_dc and previous:
            gdi.SelectObject(memory_dc, previous)
        if bitmap:
            gdi.DeleteObject(bitmap)
        if memory_dc:
            gdi.DeleteDC(memory_dc)
        user.ReleaseDC(hwnd, source_dc)


def _image_is_empty(image: Image.Image) -> bool:
    """Detecta capturas completamente negras, tipicas de apps protegidas."""
    preview = image.convert("RGB").resize((32, 18), Image.Resampling.NEAREST)
    return all(maximum <= 3 for _minimum, maximum in preview.getextrema())


def _capture_app_window(hwnd: int) -> Image.Image:
    """Captura ventana real via PrintWindow, Pillow o pantalla visible."""
    if os.name != "nt":
        raise RuntimeError("La captura de ventanas requiere Windows")
    region = _win_rect(hwnd)
    if region is None:
        raise RuntimeError("La ventana esta cerrada o minimizada: restaurala")

    errors = []
    # Primero usar la API nativa: funciona incluso con versiones viejas de Pillow.
    try:
        image = _capture_via_printwindow(
            hwnd, region["width"], region["height"]
        )
        if not _image_is_empty(image):
            return image
        errors.append("PrintWindow devolvio imagen negra")
    except (OSError, ValueError, RuntimeError) as exc:
        errors.append(str(exc))

    # Si Pillow es reciente, probar su captura HWND como alternativa.
    try:
        image = ImageGrab.grab(window=int(hwnd))
        if not _image_is_empty(image):
            return image.convert("RGB")
        errors.append("Pillow devolvio imagen negra")
    except (TypeError, OSError, ValueError):
        pass

    # Ultimo recurso: tomar el area visible SOLO cuando esa ventana tiene foco.
    # No se anuncia como captura de fondo: podria incluir superposiciones.
    user = ctypes.WinDLL("user32")
    user.GetForegroundWindow.restype = wintypes.HWND
    if int(user.GetForegroundWindow() or 0) == int(hwnd):
        r = region
        bbox = (r["left"], r["top"],
                r["left"] + r["width"], r["top"] + r["height"])
        try:
            image = ImageGrab.grab(bbox=bbox, all_screens=True)
            if not _image_is_empty(image):
                return image.convert("RGB")
        except (OSError, ValueError) as exc:
            errors.append(str(exc))

    raise RuntimeError(
        "No se pudo capturar la ventana. " + "; ".join(errors[:2])
        + ". Prueba restaurarla o desactivar la aceleracion grafica "
          "de la aplicacion. Para juegos, usa Pantalla completa."
    )


class FondoFutureo(tk.Canvas):
    """Renderiza el MP4, relampagos y una imagen PNG flotante."""

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent, bg=FONDO, bd=0, highlightthickness=0)
        self._size = (0, 0)
        self._photo: ImageTk.PhotoImage | None = None
        # Imagen PNG transparente cargada desde assets, separada del video.
        self._neon_source: Image.Image | None = None
        self._neon_photo: ImageTk.PhotoImage | None = None
        self._neon_item: int | None = None
        self._neon_resize_job: str | None = None
        self._border_photo: ImageTk.PhotoImage | None = None
        self._border_item: int | None = None
        self._border_resize_job: str | None = None
        self._screen_photo: ImageTk.PhotoImage | None = None
        self._screen_item: int | None = None
        self._screen_source: tuple[str, int] = ("monitor", 1)
        self._screen_after: str | None = None
        self._screen_grabber = None
        self._window_capture_queue: queue.Queue = queue.Queue(maxsize=2)
        self._window_capture_stop = threading.Event()
        self._capture_error: str | None = None
        self._source_dialog: tk.Toplevel | None = None
        self._host_root = self.winfo_toplevel()
        self._insert_binding: str | None = None
        self._global_insert_event = threading.Event()
        self._global_insert_stop = threading.Event()
        self._global_insert_thread_id = 0
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
        if WINDOW_OVERLAY_ENABLED:
            self.after_idle(self._load_neon_overlay)
        threading.Thread(target=self._download_asset, name="futureo-mp4", daemon=True).start()
        self._check_job = self.after(350, self._check_download)
        self._schedule_lightning(initial=True)
        try:
            self._screen_grabber = mss.mss() if mss is not None else None
        except (OSError, RuntimeError):
            self._screen_grabber = None
        # El dialogo solo aparece al presionar Insert.
        self._insert_binding = self._host_root.bind(
            "<Insert>", self._open_source_dialog, add="+"
        )
        self._screen_after = self.after(150, self._screen_tick)
        if os.name == "nt":
            threading.Thread(target=self._window_capture_worker,
                             name="futureo-window-capture",
                             daemon=True).start()
            threading.Thread(target=self._global_insert_listener,
                             name="futureo-insert", daemon=True).start()

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
        if not VIDEO_BACKGROUND_ENABLED:
            self._stop_playback()
            self._mode = "static"
            self._show_static_background()
            return
        if not self._start_video():
            self._start_gif()

    def _show_static_background(self) -> None:
        """Fondo fijo sin MP4 ni GIF; permite conservar los rayos y el PNG."""
        if not self._alive or not self.winfo_exists():
            return
        width, height = self._size
        if width > 1 and height > 1:
            self._present(Image.new("RGB", (width, height), FONDO))

    def _download_asset(self) -> None:
        """Descarga por separado la imagen PNG y los fondos con cache local."""
        choices = ([(WINDOW_URL, WINDOW_PATH, MAX_WINDOW_BYTES, "png")]
                   if WINDOW_OVERLAY_ENABLED else [])
        if VIDEO_BACKGROUND_ENABLED:
            if cv2 is not None:
                choices.append((VIDEO_URL, VIDEO_PATH, MAX_VIDEO_BYTES, "mp4"))
            choices.append((GIF_URL, GIF_PATH, MAX_GIF_BYTES, "gif"))
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
                    if kind == "png" and not data.startswith(b"\x89PNG\r\n\x1a\n"):
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
                if WINDOW_OVERLAY_ENABLED:
                    self._load_neon_overlay()
                self._load_local()
        else:
            self._check_job = self.after(350, self._check_download)


    def _resize(self, event: tk.Event) -> None:
        new_size = (max(1, int(event.width)), max(1, int(event.height)))
        if new_size == self._size:
            return
        self._size = new_size
        self._lightning_cached = None
        self._lightning_cache_key = None
        if not VIDEO_BACKGROUND_ENABLED:
            self.after_idle(self._show_static_background)
        if self._neon_resize_job is not None:
            self.after_cancel(self._neon_resize_job)
        # Evita regenerar una imagen grande en cada pixel durante resize.
        if WINDOW_OVERLAY_ENABLED:
            self._neon_resize_job = self.after(90, self._draw_neon_window)
        if self._border_resize_job is not None:
            self.after_cancel(self._border_resize_job)
        if NEON_BORDER_ENABLED:
            self._border_resize_job = self.after(90, self._draw_neon_border)

    def _load_neon_overlay(self) -> None:
        """Abre el PNG local sin dibujar su geometria mediante codigo."""
        if not WINDOW_OVERLAY_ENABLED or not self._alive or not WINDOW_PATH.is_file():
            return
        try:
            with Image.open(WINDOW_PATH) as source:
                source.load()
                if source.width < 128 or source.height < 72:
                    raise ValueError("Imagen de ventana demasiado pequena")
                self._neon_source = source.convert("RGBA").copy()
        except (OSError, ValueError, EOFError):
            return
        self._draw_neon_window()

    def _draw_neon_window(self) -> None:
        """Coloca la ventana PNG arriba a la izquierda, al 10% del area visible."""
        self._neon_resize_job = None
        if not self._alive or not self.winfo_exists():
            return
        if not WINDOW_OVERLAY_ENABLED:
            if self._neon_item is not None:
                self.itemconfigure(self._neon_item, state="hidden")
            return

        width, height = self._size
        if self._neon_source is None or width < 160 or height < 120:
            if self._neon_item is not None:
                self.itemconfigure(self._neon_item, state="hidden")
            return

        # Escalar por area para mantener la proporcion real del PNG.
        target_area = width * height * 0.10
        src_w, src_h = self._neon_source.size
        aspect = src_w / src_h if src_h else 1.0
        new_w = int((target_area * aspect) ** 0.5)
        new_h = int(new_w / aspect)

        # Limitar el cuadro para no tapar una parte excesiva de la escena.
        new_w = max(80, min(new_w, int(width * 0.45)))
        new_h = max(45, min(new_h, int(height * 0.45)))

        frame = self._neon_source.resize(
            (new_w, new_h), resample=Image.Resampling.LANCZOS
        )
        self._neon_photo = ImageTk.PhotoImage(frame, master=self)

        margin_x = int(width * 0.02)
        margin_y = int(height * 0.02)

        if self._neon_item is None:
            self._neon_item = self.create_image(
                margin_x, margin_y, anchor="nw",
                image=self._neon_photo, tags=("ventana_neon",)
            )
        else:
            self.itemconfigure(
                self._neon_item, image=self._neon_photo, state="normal"
            )
            self.coords(self._neon_item, margin_x, margin_y)

        self.tag_raise("ventana_neon")

    def _draw_neon_border(self) -> None:
        """Marco neón con centro completamente transparente y esquinas redondeadas.

        El marco ocupa el 80% del ancho y el 80% del alto del lienzo.
        Se dibuja en memoria y no usa el PNG del marco anterior.
        """
        self._border_resize_job = None
        if not self._alive or not self.winfo_exists():
            return
        if not NEON_BORDER_ENABLED:
            if self._border_item is not None:
                self.itemconfigure(self._border_item, state="hidden")
            return

        screen_w, screen_h = self._size
        if screen_w < 160 or screen_h < 120:
            return
        border_w = max(120, int(screen_w * NEON_BORDER_WIDTH))
        border_h = max(90, int(screen_h * NEON_BORDER_HEIGHT))
        margin_x = int(screen_w * .02)
        margin_y = int(screen_h * .02)

        # Los bordes tienen margen interno para que el resplandor no se corte.
        min_side = min(border_w, border_h)
        padding = max(10, int(min_side * .025))
        radius = max(12, int(min_side * NEON_CORNER_RADIUS_RATIO))
        stroke = max(3, int(min_side * .007))
        bounds = (padding, padding, border_w - padding - 1,
                  border_h - padding - 1)
        size = (border_w, border_h)

        # No existe relleno: todo lo que no sea borde mantiene alpha=0.
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        mask = Image.new("L", size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            bounds, radius=radius, outline=255, width=stroke + 2
        )

        for blur, strength, color in (
            (max(9, int(min_side * .025)), .58, (25, 95, 255)),
            (max(3, int(min_side * .009)), .92, (0, 213, 255)),
        ):
            halo = Image.new("RGBA", size, (*color, 0))
            alpha = mask.filter(ImageFilter.GaussianBlur(blur))
            halo.putalpha(alpha.point(lambda v, strength=strength: int(v * strength)))
            image.alpha_composite(halo)

        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle(
            bounds, radius=radius, outline=(20, 151, 255, 235),
            width=stroke
        )
        inner = (padding + 2, padding + 2,
                 border_w - padding - 3, border_h - padding - 3)
        draw.rounded_rectangle(
            inner, radius=max(1, radius - 2),
            outline=(190, 246, 255, 255), width=max(1, stroke // 2)
        )

        self._border_photo = ImageTk.PhotoImage(image, master=self)
        if self._border_item is None:
            self._border_item = self.create_image(
                margin_x, margin_y, anchor="nw",
                image=self._border_photo, tags=("neon_border",)
            )
        else:
            self.itemconfigure(
                self._border_item, image=self._border_photo, state="normal"
            )
            self.coords(self._border_item, margin_x, margin_y)
        self.tag_raise("neon_border")


    def _global_insert_listener(self) -> None:
        """Atajo Insert global para Windows, con respaldo local de Tkinter."""
        try:
            user = ctypes.WinDLL("user32", use_last_error=True)
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            user.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int,
                                            wintypes.UINT, wintypes.UINT]
            user.RegisterHotKey.restype = wintypes.BOOL
            user.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
            user.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG),
                                          wintypes.HWND, wintypes.UINT, wintypes.UINT]
            user.GetMessageW.restype = ctypes.c_int
            kernel.GetCurrentThreadId.restype = wintypes.DWORD
            hotkey_id = 0x3609
            self._global_insert_thread_id = int(kernel.GetCurrentThreadId())
            if not user.RegisterHotKey(None, hotkey_id, 0x4000, 0x2D):
                return
            try:
                msg = wintypes.MSG()
                while not self._global_insert_stop.is_set():
                    if user.GetMessageW(ctypes.byref(msg), None, 0, 0) <= 0:
                        break
                    if msg.message == 0x0312 and msg.wParam == hotkey_id:
                        self._global_insert_event.set()
            finally:
                user.UnregisterHotKey(None, hotkey_id)
        except (AttributeError, OSError, ValueError):
            pass

    def _window_capture_worker(self) -> None:
        """Captura ventanas en un hilo para evitar bloquear la interfaz Tk."""
        while not self._window_capture_stop.is_set():
            source = self._screen_source
            if source[0] != "window":
                self._window_capture_stop.wait(.2)
                continue
            frame = None
            error = None
            try:
                frame = _capture_app_window(source[1])
            except Exception as exc:
                error = str(exc)
            packet = (source, frame, error)
            try:
                self._window_capture_queue.put_nowait(packet)
            except queue.Full:
                try:
                    self._window_capture_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    self._window_capture_queue.put_nowait(packet)
                except queue.Full:
                    pass
            self._window_capture_stop.wait(1 / SCREEN_CAPTURE_FPS)

    def _screen_tick(self) -> None:
        """Visualiza pantalla o ventana real bajo el marco neon, sin controles."""
        self._screen_after = None
        if not self._alive:
            return
        if self._global_insert_event.is_set():
            self._global_insert_event.clear()
            self._open_source_dialog()
        try:
            sw, sh = self._size
            grabber = self._screen_grabber
            if sw >= 160 and sh >= 120:
                bw = max(120, int(sw * NEON_BORDER_WIDTH))
                bh = max(90, int(sh * NEON_BORDER_HEIGHT))
                side = min(bw, bh)
                # Coincidir con la geometria de _draw_neon_border.
                # La captura solapa todo el borde interior, incluso las esquinas.
                padding = max(10, int(side * .025))
                stroke = max(3, int(side * .007))
                radius = max(12, int(side * NEON_CORNER_RADIUS_RATIO))
                inset = max(1, padding + stroke - SCREEN_CAPTURE_BLEED_PX)
                left = int(sw * .02) + inset
                top = int(sh * .02) + inset
                width, height = bw - 2 * inset, bh - 2 * inset
                clip_radius = max(1, radius - (inset - padding) - SCREEN_CAPTURE_CORNER_OVERLAP_PX)
                kind, index = self._screen_source
                if kind == "window":
                    # Recuperar solo el ultimo fotograma producido en otro hilo.
                    latest = None
                    try:
                        while True:
                            latest = self._window_capture_queue.get_nowait()
                    except queue.Empty:
                        pass
                    if latest is None or latest[0] != self._screen_source:
                        return
                    _source, original, window_error = latest
                    if window_error is not None:
                        raise RuntimeError(window_error)
                elif kind == "monitor":
                    if grabber is None:
                        raise RuntimeError(
                            "No se encontro mss. Instala: python -m pip install mss"
                        )
                    monitors = grabber.monitors
                    if not (0 < index < len(monitors)):
                        raise RuntimeError("El monitor seleccionado no esta conectado")
                    shot = grabber.grab(dict(monitors[index]))
                    original = Image.frombytes("RGB", shot.size, shot.rgb)
                else:
                    raise RuntimeError("Fuente de captura no valida")

                if width > 20 and height > 20:
                    # Retirar el margen exterior de ventanas capturadas.
                    # Los monitores se mantienen completos.
                    if kind == "window" and SCREEN_SOURCE_CROP_PX:
                        crop = SCREEN_SOURCE_CROP_PX
                        if original.width > 2 * crop + 20 and original.height > 2 * crop + 20:
                            original = original.crop((
                                crop, crop, original.width - crop, original.height - crop
                            ))
                    # COVER: sin bandas y sin deformar las proporciones.
                    frame = ImageOps.fit(
                        original.convert("RGBA"), (width, height),
                        method=Image.Resampling.BILINEAR, centering=(.5, .5),
                    )
                    # Recorte redondeado menos pronunciado y extendido bajo el borde neon.
                    mask = Image.new("L", (width, height), 0)
                    ImageDraw.Draw(mask).rounded_rectangle(
                        (0, 0, width - 1, height - 1),
                        radius=clip_radius,
                        fill=255
                    )
                    frame.putalpha(ImageChops.multiply(
                        frame.getchannel("A"), mask
                    ))
                    self._screen_photo = ImageTk.PhotoImage(frame, master=self)
                    if self._screen_item is None:
                        self._screen_item = self.create_image(
                            left, top, image=self._screen_photo, anchor="nw",
                            tags=("screen_capture",)
                        )
                    else:
                        self.itemconfigure(
                            self._screen_item, image=self._screen_photo,
                            state="normal"
                        )
                        self.coords(self._screen_item, left, top)
                    self.tag_raise("screen_capture")
                    if self._border_item is not None:
                        self.tag_raise("neon_border")
                    self._capture_error = None
        except Exception as exc:
            # No ocultar errores: disponibles en Insert y en la consola.
            error = str(exc)
            if error != self._capture_error:
                print("[FUTUREO] Error de captura:", error)
            self._capture_error = error
            if self._screen_item is not None:
                self.itemconfigure(self._screen_item, state="hidden")
        finally:
            if self._alive:
                self._screen_after = self.after(
                    max(50, int(1000 / SCREEN_CAPTURE_FPS)), self._screen_tick
                )

    def _open_source_dialog(self, _event=None) -> None:
        """Dialogo con fuentes disponibles: aparece solo al presionar Insert."""
        if not self._alive:
            return
        if self._source_dialog is not None:
            try:
                if self._source_dialog.winfo_exists():
                    self._source_dialog.lift()
                    self._source_dialog.focus_force()
                    return
            except tk.TclError:
                pass
        try:
            if self._host_root.state() == "iconic":
                self._host_root.deiconify()
        except tk.TclError:
            pass
        dialog = tk.Toplevel(self._host_root)
        self._source_dialog = dialog
        dialog.title("FUTUREO LIVE - Configurar captura")
        dialog.geometry("550x410")
        dialog.resizable(False, False)
        dialog.configure(bg="#0A142B")
        dialog.transient(self._host_root)
        dialog.attributes("-topmost", True)
        mode = tk.StringVar(master=dialog, value=self._screen_source[0])
        screens = []
        if self._screen_grabber is not None:
            for i, monitor in enumerate(self._screen_grabber.monitors[1:], 1):
                name = (f"Pantalla {i} - {monitor['width']}x{monitor['height']} "
                        f"(X:{monitor['left']}, Y:{monitor['top']})")
                screens.append((name, i))
        windows = []
        body = tk.Frame(dialog, bg="#0A142B", padx=20, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(body, text="CONFIGURACION DE CAPTURA",
                 bg="#0A142B", fg="#6FDCFF",
                 font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 12))
        common = {"bg": "#0A142B", "fg": "#F4F8FF",
                  "selectcolor": "#173153", "activebackground": "#0A142B"}
        tk.Radiobutton(
            body, text="Pantalla completa", variable=mode, value="monitor",
            **common
        ).pack(anchor="w")
        screen_box = ttk.Combobox(body, state="readonly", width=63)
        screen_box["values"] = [label for label, _idx in screens]
        screen_box.pack(fill="x", pady=(4, 12))
        if screens:
            selected = self._screen_source[1] if mode.get() == "monitor" else 1
            screen_box.current(next(
                (i for i, (_name, idx) in enumerate(screens) if idx == selected), 0
            ))
        window_radio = tk.Radiobutton(
            body, text="Ventana especifica", variable=mode, value="window",
            **common
        )
        window_radio.pack(anchor="w")
        window_box = ttk.Combobox(body, state="readonly", width=63)
        window_box.pack(fill="x", pady=(4, 6))

        def refresh():
            nonlocal windows
            windows = [(f"{name}  [0x{hwnd:X}]", hwnd)
                       for hwnd, name in _win_list()]
            window_box["values"] = [name for name, _hwnd in windows]
            if windows:
                previously = (self._screen_source[1]
                              if self._screen_source[0] == "window" else None)
                window_box.current(next(
                    (i for i, (_name, hwnd) in enumerate(windows)
                     if hwnd == previously), 0
                ))
            else:
                window_box.set("No se encontraron ventanas")
        refresh()
        tk.Button(body, text="Actualizar ventanas", command=refresh,
                  bg="#13314E", fg="white", relief="flat").pack(anchor="w")

        def change_mode(*_args):
            screen_box.configure(
                state="readonly" if mode.get() == "monitor" else "disabled"
            )
            window_box.configure(
                state="readonly" if mode.get() == "window" else "disabled"
            )
        mode.trace_add("write", change_mode)
        if os.name != "nt":
            window_radio.configure(state="disabled")
            mode.set("monitor")
        change_mode()

        def close():
            if self._source_dialog is dialog:
                self._source_dialog = None
            try:
                dialog.grab_release()
            except tk.TclError:
                pass
            dialog.destroy()

        def apply():
            if mode.get() == "monitor":
                idx = screen_box.current()
                if idx < 0 or idx >= len(screens):
                    messagebox.showwarning(
                        "FUTUREO LIVE", "Selecciona una pantalla.", parent=dialog
                    )
                    return
                chosen = ("monitor", screens[idx][1])
            else:
                idx = window_box.current()
                if idx < 0 or idx >= len(windows):
                    messagebox.showwarning(
                        "FUTUREO LIVE", "Selecciona una ventana.", parent=dialog
                    )
                    return
                chosen = ("window", windows[idx][1])
                if _win_rect(chosen[1]) is None:
                    messagebox.showwarning(
                        "FUTUREO LIVE",
                        "Restaura esa ventana: las minimizadas no pueden capturarse.",
                        parent=dialog
                    )
                    return
            self._screen_source = chosen
            if self._screen_item is not None:
                self.itemconfigure(self._screen_item, state="hidden")
            close()

        footer = tk.Frame(body, bg="#0A142B")
        footer.pack(side="bottom", fill="x", pady=(9, 0))
        tk.Button(footer, text="Cancelar", command=close, bg="#22334C",
                  fg="white", padx=18).pack(side="right", padx=(8, 0))
        tk.Button(footer, text="Aplicar", command=apply, bg="#007BB9",
                  fg="white", padx=18).pack(side="right")
        dialog.protocol("WM_DELETE_WINDOW", close)
        dialog.grab_set()
        dialog.focus_force()
        if self._screen_grabber is None and os.name != "nt":
            messagebox.showwarning(
                "FUTUREO LIVE",
                "Captura de monitor no disponible. Instala: pip install mss",
                parent=dialog
            )
        elif self._capture_error:
            tk.Label(
                body, text="Captura: " + self._capture_error[:100],
                bg="#0A142B", fg="#FFBC94",
                wraplength=490, justify="left",
                font=("Segoe UI", 9)
            ).pack(anchor="w", pady=(6, 0))

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
                self._next_due += 1.0 / (self._fps * VIDEO_SPEED)
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
        self._window_capture_stop.set()
        self._global_insert_stop.set()
        if self._global_insert_thread_id:
            try:
                ctypes.windll.user32.PostThreadMessageW(
                    self._global_insert_thread_id, 0x0012, 0, 0
                )
            except (AttributeError, OSError):
                pass
        if self._screen_after is not None:
            try:
                self.after_cancel(self._screen_after)
            except tk.TclError:
                pass
            self._screen_after = None
        if self._screen_grabber is not None:
            self._screen_grabber.close()
            self._screen_grabber = None
        if self._insert_binding:
            try:
                self._host_root.unbind("<Insert>", self._insert_binding)
            except tk.TclError:
                pass
        if self._source_dialog is not None:
            try:
                self._source_dialog.destroy()
            except tk.TclError:
                pass
            self._source_dialog = None
        if self._border_resize_job is not None:
            try:
                self.after_cancel(self._border_resize_job)
            except tk.TclError:
                pass
            self._border_resize_job = None
        if self._neon_resize_job is not None:
            try:
                self.after_cancel(self._neon_resize_job)
            except tk.TclError:
                pass
            self._neon_resize_job = None
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