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
import json
import os
import queue
import random
from pathlib import Path
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
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

VERSION = "2.13.0"
FONDO = "#050A19"
VIDEO_SPEED = 1.20  # MP4 reproducido un 20 por ciento mas rapido
VIDEO_BACKGROUND_ENABLED = False  # Cambiar a True para reactivar MP4/GIF.
WINDOW_OVERLAY_ENABLED = True  # Ventana del hablante activa, sin alterar marco principal.
STREAMER_AREA_RATIO = 0.08  # Area base del cuadro del hablante.
STREAMER_SIZE_SCALE = 0.80  # Reduce ancho y alto un 20% respecto de v2.12.4.
STREAMER_BORDER_THINNING_PX = 0  # Conserva intactos los brillos y detalles del nuevo logo HD.
NEON_BORDER_ENABLED = True  # Nuevo borde dibujado, sin PNG ni fondo.
NEON_BORDER_WIDTH = 0.80  # 80% del ancho del lienzo.
NEON_BORDER_HEIGHT = 0.80  # 80% del alto del lienzo.
SCREEN_VIEWER_MARGIN_PX = 5  # Visor y marco neon alineados a 5 px de los bordes.
NEON_CORNER_RADIUS_RATIO = 0.045  # Esquinas 31% menos redondeadas que antes.
SCREEN_CAPTURE_FPS = 12  # Captura local, no transmision a Internet.
SCREEN_CAPTURE_BLEED_PX = 3  # Solapa 3 px debajo del marco, sin ranuras.
SCREEN_SOURCE_CROP_PX = 2  # Elimina 2 px exteriores de cada ventana capturada.
SCREEN_CAPTURE_CORNER_OVERLAP_PX = 2  # Cubre tambien la curva interna del marco.
BASE = Path(__file__).resolve().parent
ASSETS = BASE / "assets"
VIDEO_PATH = ASSETS / "fondo_sin_marcos_4k.mp4"
GIF_PATH = ASSETS / "fondo_sin_marcos.gif"
WINDOW_PATH = ASSETS / "ventana_futureo_hd.png"
SPEAKER_PHOTO_PATH = ASSETS / "hablante_futureo.jpg"
URL_ROOT = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/FUTUREOLIVE/assets"
VIDEO_URL = URL_ROOT + "/fondo_sin_marcos_4k.mp4"
GIF_URL = URL_ROOT + "/fondo_sin_marcos.gif"
WINDOW_URL = URL_ROOT + "/ventana_futureo_hd.png"
SPEAKER_PHOTO_URL = URL_ROOT + "/hablante_futureo.jpg"
MAX_VIDEO_BYTES = 32 * 1024 * 1024
MAX_GIF_BYTES = 8 * 1024 * 1024
MAX_WINDOW_BYTES = 8 * 1024 * 1024
MAX_SPEAKER_PHOTO_BYTES = 3 * 1024 * 1024




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
        # Imagen fija del hablante en capa independiente, debajo del marco.
        self._speaker_source: Image.Image | None = None
        self._speaker_photo: ImageTk.PhotoImage | None = None
        self._speaker_item: int | None = None
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
        self._right_click_binding: str | None = None
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
            self.after_idle(self._load_speaker_image)
        threading.Thread(target=self._download_asset, name="futureo-mp4", daemon=True).start()
        self._check_job = self.after(350, self._check_download)
        self._schedule_lightning(initial=True)
        try:
            self._screen_grabber = mss.mss() if mss is not None else None
        except (OSError, RuntimeError):
            self._screen_grabber = None
        # Insert o clic derecho en FUTUREO abren el mismo selector de fuentes.
        self._insert_binding = self._host_root.bind(
            "<Insert>", self._open_source_dialog, add="+"
        )
        self._right_click_binding = self._host_root.bind(
            "<Button-3>", self._open_source_dialog, add="+"
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
        choices = ([
            (WINDOW_URL, WINDOW_PATH, MAX_WINDOW_BYTES, "png"),
            (SPEAKER_PHOTO_URL, SPEAKER_PHOTO_PATH,
             MAX_SPEAKER_PHOTO_BYTES, "jpg"),
        ] if WINDOW_OVERLAY_ENABLED else [])
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
                    if kind == "jpg" and not (
                        data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9")
                    ):
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
                    self._load_speaker_image()
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
        if not WINDOW_OVERLAY_ENABLED or not self._alive:
            return
        # En la primera carga, conservar la imagen antigua como respaldo
        # mientras se descarga automaticamente el marco FUTUREO.
        source_path = WINDOW_PATH
        if not source_path.is_file():
            source_path = ASSETS / "ventana_neon.png"
        if not source_path.is_file():
            return
        try:
            with Image.open(source_path) as source:
                source.load()
                if source.width < 128 or source.height < 72:
                    raise ValueError("Imagen de ventana demasiado pequena")
                overlay = source.convert("RGBA")
                # Adelgazar los bordes del marco del streamer SIN afectar
                # al borde principal, colores originales ni tamano del PNG.
                if STREAMER_BORDER_THINNING_PX > 0:
                    radius = max(1, int(STREAMER_BORDER_THINNING_PX))
                    radius = min(radius, 8)
                    alpha = overlay.getchannel("A")
                    # Erosion de transparencia: cada lado del trazo pierde 2 px.
                    core = alpha.filter(ImageFilter.MinFilter(2 * radius + 1))
                    # Un halo muy sutil conserva la iluminacion cyan/violeta.
                    halo = alpha.point(lambda value: int(value * 0.16))
                    overlay.putalpha(ImageChops.lighter(core, halo))
                self._neon_source = overlay.copy()
        except (OSError, ValueError, EOFError):
            return
        self._draw_neon_window()

    def _load_speaker_image(self) -> None:
        """Lee la foto descargada; el marco FUTUREO HD se conserva por encima."""
        if not WINDOW_OVERLAY_ENABLED or not self._alive:
            return
        if not SPEAKER_PHOTO_PATH.is_file():
            return
        try:
            with Image.open(SPEAKER_PHOTO_PATH) as photo:
                photo.load()
                if photo.width < 80 or photo.height < 45:
                    return
                self._speaker_source = photo.convert("RGB").copy()
        except (OSError, ValueError, EOFError) as exc:
            print("[FUTUREO] No se pudo abrir la imagen del hablante:", exc)
            return
        self._draw_neon_window()

    def _draw_speaker_background(
        self, margin_x: int, margin_y: int, new_w: int, new_h: int
    ) -> None:
        """Coloca la foto solo en la apertura, debajo de los bordes de la imagen."""
        if self._speaker_source is None:
            if self._speaker_item is not None:
                self.itemconfigure(self._speaker_item, state="hidden")
            return

        # Margenes interiores: el contenido no se sale del marco transparente.
        inset_x = max(5, round(new_w * .065))
        inset_y = max(8, round(new_h * .12))
        photo_w = max(1, new_w - 2 * inset_x)
        photo_h = max(1, new_h - 2 * inset_y)
        fitted = ImageOps.fit(
            self._speaker_source, (photo_w, photo_h),
            method=Image.Resampling.LANCZOS, centering=(.5, .5),
        )
        self._speaker_photo = ImageTk.PhotoImage(fitted, master=self)
        px, py = margin_x + inset_x, margin_y + inset_y
        if self._speaker_item is None:
            self._speaker_item = self.create_image(
                px, py, image=self._speaker_photo, anchor="nw",
                tags=("speaker_background",),
            )
        else:
            self.itemconfigure(
                self._speaker_item, image=self._speaker_photo,
                state="normal"
            )
            self.coords(self._speaker_item, px, py)

        # Fondo encima de captura, pero siempre bajo el PNG del marco.
        self.tag_raise("speaker_background")
        if self._neon_item is not None:
            self.tag_raise("ventana_neon")

    def _draw_neon_window(self) -> None:
        """Coloca la ventana del hablante arriba a la izquierda, con tamano reducido."""
        self._neon_resize_job = None
        if not self._alive or not self.winfo_exists():
            return
        if not WINDOW_OVERLAY_ENABLED:
            if self._neon_item is not None:
                self.itemconfigure(self._neon_item, state="hidden")
            if self._speaker_item is not None:
                self.itemconfigure(self._speaker_item, state="hidden")
            return

        width, height = self._size
        if self._neon_source is None or width < 160 or height < 120:
            if self._neon_item is not None:
                self.itemconfigure(self._neon_item, state="hidden")
            if self._speaker_item is not None:
                self.itemconfigure(self._speaker_item, state="hidden")
            return

        # Escalar por area para mantener la proporcion real del PNG.
        target_area = width * height * STREAMER_AREA_RATIO
        src_w, src_h = self._neon_source.size
        aspect = src_w / src_h if src_h else 1.0
        new_w = int((target_area * aspect) ** 0.5)
        new_h = int(new_w / aspect)

        # Limitar el cuadro para no tapar una parte excesiva de la escena.
        new_w = max(80, min(new_w, int(width * 0.45)))
        new_h = max(45, min(new_h, int(height * 0.45)))

        # Reduccion uniforme del 20% respecto al cuadro anterior.
        new_w = max(1, round(new_w * STREAMER_SIZE_SCALE))
        new_h = max(1, round(new_h * STREAMER_SIZE_SCALE))

        frame = self._neon_source.resize(
            (new_w, new_h), resample=Image.Resampling.LANCZOS
        )
        self._neon_photo = ImageTk.PhotoImage(frame, master=self)

        # Ventana del hablante anclada a 5 px del borde superior e izquierdo.
        margin_x = 5
        margin_y = 5

        # Primero se dibuja la fotografia; despues el PNG que la enmarca.
        self._draw_speaker_background(margin_x, margin_y, new_w, new_h)

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
        margin_x = SCREEN_VIEWER_MARGIN_PX
        margin_y = SCREEN_VIEWER_MARGIN_PX

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
        if WINDOW_OVERLAY_ENABLED:
            if self._speaker_item is not None:
                self.tag_raise("speaker_background")
            if self._neon_item is not None:
                self.tag_raise("ventana_neon")


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
                left = SCREEN_VIEWER_MARGIN_PX + inset
                top = SCREEN_VIEWER_MARGIN_PX + inset
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
                    # Foto y marco sobre la captura: el PNG debe ir encima.
                    if WINDOW_OVERLAY_ENABLED:
                        if self._speaker_item is not None:
                            self.tag_raise("speaker_background")
                        if self._neon_item is not None:
                            self.tag_raise("ventana_neon")
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
        """Dialogo de fuentes: se abre mediante Insert o clic derecho."""
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
        if self._right_click_binding:
            try:
                self._host_root.unbind("<Button-3>", self._right_click_binding)
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



# TikTok LIVE mode. Lives in futureolive.py so app.py can update it as one file.
TIKTOK_SCENE_WIDTH = 720
TIKTOK_SCENE_HEIGHT = 1280
TIKTOK_SCENE_SETTINGS = BASE / 'tiktok_scene_settings.json'
TIKTOK_SLOTS = {
    'mini': (22, 128, 495, 333),
    'qr': (515, 135, 689, 290),
    'game': (22, 357, 698, 753),
    'title': (26, 771, 694, 824),
    'chat': (22, 880, 345, 1168),
    'speaker': (366, 880, 698, 1168),
    'footer': (22, 1181, 698, 1256),
}
TIKTOK_LABELS = {
    'mini': 'Minijuego superior', 'qr': 'QR interactivo',
    'game': 'Juego principal', 'title': 'Nombre del juego',
    'chat': 'Zona libre: comentarios de TikTok',
    'speaker': 'Hablante (derecha)', 'footer': 'Barra inferior',
}
TIKTOK_SOURCE_LABELS = {
    'monitor': 'Pantalla completa', 'window': 'Ventana del PC',
    'camera': 'Camara web', 'image': 'Archivo de imagen',
    'url': 'Codigo QR con URL', 'text': 'Texto personalizado',
    'none': 'Vacio / transparente',
}


class TikTokLiveScene(tk.Canvas):
    '''Escena vertical configurable por region, con captura y QR reales.'''

    def __init__(self, parent: tk.Misc):
        super().__init__(parent, bg='#060918', bd=0, highlightthickness=0)
        self._active = True
        self._geometry = (0.0, 0.0, 1.0)
        self._frame = None
        self._static = self._create_backdrop()
        self._static_photo = None
        self._slot_items = {}
        self._slot_photos = {}
        self._slot_overlays = {}
        self._cached_images = {}
        self._latest_frames = {}
        self._update_queue = queue.Queue(maxsize=12)
        self._guard = threading.Lock()
        self._stop = threading.Event()
        self._config_dialog = None
        self._right_click_menu = None
        self._settings = self._read_config()
        self._tick_job = None
        self._resize_job = None
        self.bind('<Configure>', self._on_resize, add='+')
        self.bind('<Button-3>', self._show_popup, add='+')
        self.bind('<Control-Button-1>', self._show_popup, add='+')
        self.bind('<Destroy>', self._on_destroy, add='+')
        self._host_root = self.winfo_toplevel()
        self._insert_handle = self._host_root.bind('<Insert>', lambda _e: self._edit_slot('game'), add='+')
        self._capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True, name='futureo-tiktok-capture'
        )
        self._capture_thread.start()
        self._download_thread = threading.Thread(
            target=self._fetch_speaker_image, daemon=True, name='futureo-speaker-image'
        )
        self._download_thread.start()
        self._tick_job = self.after(100, self._tick)

    @staticmethod
    def _defaults():
        return {
            'mini': {'type': 'none', 'value': ''},
            'qr': {'type': 'url', 'value': ''},
            'game': {'type': 'monitor', 'value': '1'},
            'title': {'type': 'text', 'value': 'NOMBRE DEL JUEGO...'},
            'chat': {'type': 'none', 'value': ''},
            'speaker': {'type': 'image', 'value': str(SPEAKER_PHOTO_PATH)},
            'footer': {'type': 'text', 'value': 'SÍGUEME   •   DALE LIKE   •   COMPARTE'},
        }

    def _read_config(self):
        data = self._defaults()
        try:
            restored = json.loads(TIKTOK_SCENE_SETTINGS.read_text(encoding='utf-8'))
            if isinstance(restored, dict):
                for key, cfg in restored.items():
                    if (key in data and isinstance(cfg, dict)
                            and cfg.get('type') in TIKTOK_SOURCE_LABELS):
                        data[key] = {
                            'type': cfg['type'], 'value': str(cfg.get('value', ''))[:2048]
                        }
        except (OSError, ValueError, TypeError):
            pass
        return data

    def _save_config(self):
        try:
            tmp = TIKTOK_SCENE_SETTINGS.with_suffix('.json.tmp')
            tmp.write_text(json.dumps(self._settings, ensure_ascii=False, indent=2),
                           encoding='utf-8')
            tmp.replace(TIKTOK_SCENE_SETTINGS)
        except OSError as exc:
            print('[FUTUREO] No se pudo guardar la configuracion:', exc)

    @staticmethod
    def _font(px, bold=False):
        from PIL import ImageFont
        options = (['C:/Windows/Fonts/arialbd.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf']
                   if bold else ['C:/Windows/Fonts/arial.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'])
        for font in options:
            try:
                return ImageFont.truetype(font, px)
            except OSError:
                pass
        return ImageFont.load_default()

    @classmethod
    def _create_backdrop(cls):
        '''Produce tech neon panels once in PIL; never redraw expensive effects per frame.'''
        from PIL import Image, ImageDraw, ImageFilter
        w, h = TIKTOK_SCENE_WIDTH, TIKTOK_SCENE_HEIGHT
        base = Image.new('RGBA', (w, h), '#06071B')
        pixels = ImageDraw.Draw(base)
        for y in range(h):
            z = y / h
            pixels.line((0, y, w, y), fill=(int(5 + 5*z), int(10 + 4*z), int(32 + 20*z), 255))
        # Smoky purple effects at the bottom, independent of livestream content.
        haze = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        hz = ImageDraw.Draw(haze, 'RGBA')
        for x,y,r,col in [(-20,1070,250,(128,24,230,120)), (650,1110,240,(80,9,222,90)),
                          (200,1220,190,(54,18,167,70)),(440,60,200,(0,72,171,55))]:
            hz.ellipse((x-r,y-r,x+r,y+r), fill=col)
        haze = haze.filter(ImageFilter.GaussianBlur(84))
        base = Image.alpha_composite(base,haze)
        d = ImageDraw.Draw(base,'RGBA')
        # Semi-transparent diagonal energy fragments.
        for k in range(25):
            y = 48 + k * 50
            x = (k * 79) % 740 - 120
            d.polygon([(x,y),(x+18,y),(x+90,y-90),(x+74,y-90)],
                      fill=(16,68,132,32))
        # Header, footer and angular frame bodies.
        def panel(box, name, fill=(7,14,38,245), tint=(27,209,255,255)):
            x0,y0,x1,y1=box
            c=15
            poly=[(x0+c,y0),(x1-c,y0),(x1,y0+c),(x1,y1-c),
                  (x1-c,y1),(x0+c,y1),(x0,y1-c),(x0,y0+c)]
            d.polygon(poly,fill=fill)
            d.line(poly+[poly[0]],fill=(10,47,91,255),width=13,joint='curve')
            d.line(poly+[poly[0]],fill=(4,102,226,255),width=7,joint='curve')
            d.line(poly+[poly[0]],fill=tint,width=3,joint='curve')
            for xx, yy in ((x0+32,y0+3),(x1-44,y1-3)):
                d.line((xx,yy,xx+18,yy), fill=(210,252,255,225),width=3)
        panel((15,11,706,105),'header', fill=(4,10,28,250),tint=(0,190,255,255))
        panel((16,119,501,340),'mini')
        panel((508,119,704,343),'qr', fill=(8,12,31,250),tint=(91,207,255,255))
        panel((14,350,706,760),'game')
        panel((17,768,703,831),'title', fill=(2,33,72,250))
        panel((16,844,352,1175),'chat',fill=(16,8,43,220),tint=(129,50,255,255))
        panel((359,844,704,1175),'speaker',fill=(3,16,52,255),tint=(21,226,254,255))
        panel((15,1182,705,1265),'footer',fill=(4,12,37,250),tint=(138,60,255,255))
        # Geometric stripes of header, title & footer.
        for a in range(3):
            d.polygon([(29+a*18,43),(40+a*18,43),(23+a*18,65),(12+a*18,65)],
                      fill=(0,240,255,250))
            d.polygon([(646+a*18,44),(657+a*18,44),(640+a*18,65),(629+a*18,65)],
                      fill=(0,240,255,250))
        # Logo highlights, crown, and live pill.
        d.text((105,20),'FUTUREO',font=cls._font(49,True),fill=(23,110,220,255),stroke_width=5,stroke_fill=(1,2,12))
        d.text((102,15),'FUTUREO',font=cls._font(49,True),fill=(238,249,255,255),stroke_width=1,stroke_fill=(42,155,255))
        d.polygon([(268,25),(279,7),(290,22),(306,3),(319,23),(334,11),(341,36),(274,36)],
                  fill=(245,169,6,255))
        d.line([(271,36),(339,36)],fill=(255,249,167,255),width=5)
        d.rounded_rectangle((472,32,603,81),radius=18,fill=(225,31,64,255),outline=(255,145,159,255),width=2)
        d.text((490,39),'● LIVE',font=cls._font(28,True),fill='white')
        d.text((527,307),'ESCANEA Y JUEGA',font=cls._font(15,True),fill=(219,250,255,255))
        d.text((35,777),'◀',font=cls._font(27,True),fill=(37,216,255,255))
        d.text((662,777),'▶',font=cls._font(27,True),fill=(37,216,255,255))
        d.text((35,854),'CHAT DE TIKTOK',font=cls._font(17,True),fill=(132,154,210,225))
        d.text((367,854),'HABLANTE',font=cls._font(17,True),fill=(91,232,255,230))
        d.text((28,1205),'TikTok',font=cls._font(31,True),fill=(250,250,255,255))
        d.rounded_rectangle((147,1210,221,1244),radius=7,fill=(224,24,66,255))
        d.text((158,1214),'LIVE',font=cls._font(20,True),fill='white')
        # Focus bars above content, subtle accents.
        d.line((20,348,700,348),fill=(91,13,239,245),width=2)
        d.line((20,844,702,844),fill=(20,180,246,255),width=3)
        return base

    def _scene_rect(self, key):
        x0,y0,x1,y1 = TIKTOK_SLOTS[key]
        ox,oy,s = self._geometry
        return (round(ox+x0*s),round(oy+y0*s),round(ox+x1*s),round(oy+y1*s))

    def _on_resize(self, event):
        if not self._active or event.width < 100 or event.height < 100:
            return
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(100, self._layout)

    def _layout(self):
        self._resize_job = None
        if not self._active:
            return
        w, h = self.winfo_width(), self.winfo_height()
        factor = min(w/TIKTOK_SCENE_WIDTH, h/TIKTOK_SCENE_HEIGHT)
        left = (w - factor*TIKTOK_SCENE_WIDTH)/2
        top = (h - factor*TIKTOK_SCENE_HEIGHT)/2
        if factor <= 0: return
        self._geometry = (left, top, factor)
        self.delete('tiktok_stage')
        self._slot_items.clear()
        self._slot_overlays.clear()
        self._slot_photos.clear()
        ww = max(1, round(TIKTOK_SCENE_WIDTH*factor))
        hh = max(1, round(TIKTOK_SCENE_HEIGHT*factor))
        bg = self._static.resize((ww,hh),Image.Resampling.LANCZOS)
        self._static_photo = ImageTk.PhotoImage(bg, master=self)
        self.create_image(left,top,image=self._static_photo,anchor='nw',tags=('tiktok_stage','tiktok_base'))
        for key in TIKTOK_SLOTS:
            self._render_slot(key)

    def _render_slot(self,key):
        if not self._active: return
        cfg = self._settings.get(key,{'type':'none','value':''})
        source, value = cfg['type'],cfg['value']
        if key in ('title','footer'):
            self._draw_slot_text(key, value if source=='text' else '')
            return
        if source=='text':
            self._draw_slot_text(key,value)
            return
        if source=='none' or (source=='url' and not value):
            if key!='chat':
                message = ('CLIC DERECHO PARA CONFIGURAR' if key!='qr'
                           else 'CONFIGURA UNA URL CON CLIC DERECHO')
                self._draw_slot_text(key,message,dim=True)
            return
        if source=='image':
            path = Path(value).expanduser()
            if path.is_file():
                try:
                    cached = self._cached_images.get(str(path))
                    if cached is None:
                        with Image.open(path) as im:
                            cached=im.convert('RGB').copy()
                        self._cached_images[str(path)]=cached
                    self._set_slot_image(key,cached)
                except (OSError,ValueError):
                    self._draw_slot_text(key,'IMAGEN NO DISPONIBLE',dim=True)
            else:
                self._draw_slot_text(key,'DESCARGANDO IMAGEN...' if key=='speaker' else 'IMAGEN NO ENCONTRADA',dim=True)
        elif source=='url':
            self._set_qr(key,value)
        elif source in ('monitor','window','camera'):
            image = self._latest_frames.get(key)
            if image is not None:
                self._set_slot_image(key,image)
            else:
                self._draw_slot_text(key,'ESPERANDO FUENTE...',dim=True)

    def _draw_slot_text(self,key,value,dim=False):
        if key in self._slot_overlays:
            self.delete(self._slot_overlays[key])
        x0,y0,x1,y1=self._scene_rect(key)
        fs = max(9, min(30, round(26*self._geometry[2])))
        if key=='footer':
            self._slot_overlays[key]=self.create_text(
                x0+round(230*self._geometry[2]),(y0+y1)/2,
                anchor='w',text=value or '',fill='#EAFBFF',
                font=('Arial',max(8,round(15*self._geometry[2])),'bold'),
                width=max(50,x1-x0-round(245*self._geometry[2])),
                tags=('tiktok_stage','slot_text'),
            )
            return
        if key=='chat' and not value: return
        self._slot_overlays[key]=self.create_text(
            (x0+x1)/2,(y0+y1)/2,text=value,
            fill=('#6E9FBA' if dim else '#EAFBFF'),
            font=('Arial',max(9,fs if key=='title' else round(fs*.55)),'bold'),
            width=max(30,x1-x0-22),justify='center',
            tags=('tiktok_stage','slot_text'),
        )

    def _set_slot_image(self,key,img):
        x0,y0,x1,y1=self._scene_rect(key)
        border=max(2,round(5*self._geometry[2]))
        if key=='qr':
            border=max(2,round(6*self._geometry[2]))
        px,py=x0+border,y0+border
        w,h=max(1,x1-x0-2*border),max(1,y1-y0-2*border)
        if key=='qr':
            img=ImageOps.contain(img,(w,h),Image.Resampling.NEAREST)
        elif key=='speaker':
            # Keep all the branding visible in the portrait, not a hard crop.
            img=ImageOps.contain(img,(w,h),Image.Resampling.LANCZOS)
        else:
            img=ImageOps.fit(img,(w,h),method=Image.Resampling.BILINEAR)
        photo=ImageTk.PhotoImage(img,master=self)
        self._slot_photos[key]=photo
        if key not in self._slot_items:
            self._slot_items[key]=self.create_image(
                px+(w-img.width)//2,py+(h-img.height)//2,
                image=photo,anchor='nw',tags=('tiktok_stage','slot_image'),
            )
        else:
            self.itemconfigure(self._slot_items[key],image=photo,state='normal')
            self.coords(self._slot_items[key],px+(w-img.width)//2,py+(h-img.height)//2)
        if key in self._slot_overlays:
            self.delete(self._slot_overlays.pop(key))

    def _set_qr(self,key,value):
        if not (value.startswith('https://') or value.startswith('http://')):
            self._draw_slot_text(key,'URL DEBE COMENZAR CON HTTPS://',dim=True)
            return
        try:
            import qrcode
            code=qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                               border=2,box_size=6)
            code.add_data(value)
            code.make(fit=True)
            img=code.make_image(fill_color='black',back_color='white').convert('RGB')
            self._set_slot_image(key,img)
        except (ImportError,ValueError,RuntimeError) as exc:
            self._draw_slot_text(key,'QR NO DISPONIBLE: '+str(exc)[:80],dim=True)

    def _capture_loop(self):
        '''Grab multiple sources on a worker. Never invokes Tk APIs.'''
        cameras={}
        last_error=None
        last_report=0.0
        try:
            while not self._stop.is_set():
                with self._guard:
                    current={key:dict(cfg) for key,cfg in self._settings.items()}
                sources={k:cfg for k,cfg in current.items()
                         if cfg['type'] in ('monitor','window','camera')}
                if not sources:
                    self._stop.wait(.4)
                    continue
                try:
                    for key,cfg in sources.items():
                        if self._stop.is_set():break
                        typ,val=cfg['type'],cfg['value']
                        img=None
                        if typ=='monitor' and mss is not None:
                            with mss.mss() as grabber:
                                monitors=grabber.monitors
                                number=int(val or 1)
                                if 0 < number < len(monitors):
                                    shot=grabber.grab(dict(monitors[number]))
                                    img=Image.frombytes('RGB',shot.size,shot.rgb)
                        elif typ=='window' and os.name=='nt':
                            img=_capture_app_window(int(val))
                        elif typ=='camera' and cv2 is not None:
                            number=int(val or 0)
                            if number not in cameras:
                                cameras[number]=cv2.VideoCapture(number)
                            ok,frame=cameras[number].read()
                            if ok:
                                img=Image.fromarray(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB))
                        if img is not None:
                            rect=TIKTOK_SLOTS[key]
                            iw,ih=rect[2]-rect[0],rect[3]-rect[1]
                            img=ImageOps.fit(img,(iw,ih),method=Image.Resampling.BILINEAR)
                            if self._update_queue.full():
                                try:self._update_queue.get_nowait()
                                except queue.Empty:pass
                            self._update_queue.put_nowait((key,typ,val,img))
                except (OSError,ValueError,RuntimeError,AttributeError,IndexError) as exc:
                    if str(exc)!=last_error or time.monotonic()-last_report>20:
                        print('[FUTUREO] Fuente de TikTok:',exc)
                        last_error=str(exc)
                        last_report=time.monotonic()
                self._stop.wait(.10)
        finally:
            for stream in cameras.values():
                try:stream.release()
                except Exception:pass

    def _fetch_speaker_image(self):
        if SPEAKER_PHOTO_PATH.exists(): return
        try:
            request=Request(SPEAKER_PHOTO_URL,headers={'User-Agent':'FUTUREO-LIVE/2.13'})
            with urlopen(request,timeout=12) as resp:
                data=resp.read(MAX_SPEAKER_PHOTO_BYTES+1)
            if not (4<len(data)<=MAX_SPEAKER_PHOTO_BYTES and data[:2]==b'\xff\xd8'
                    and data[-2:]==b'\xff\xd9'): return
            ASSETS.mkdir(parents=True,exist_ok=True)
            tmp=SPEAKER_PHOTO_PATH.with_suffix('.jpg.tmp')
            tmp.write_bytes(data)
            os.replace(tmp,SPEAKER_PHOTO_PATH)
        except (OSError,ValueError,TimeoutError):pass

    def _tick(self):
        if not self._active:return
        changed=set()
        try:
            while True:
                key,typ,val,img=self._update_queue.get_nowait()
                with self._guard:
                    cfg=self._settings.get(key,{})
                    current=(cfg.get('type'),cfg.get('value'))
                if current==(typ,val):
                    self._latest_frames[key]=img
                    changed.add(key)
        except queue.Empty:pass
        for key in changed:
            self._set_slot_image(key,self._latest_frames[key])
        if self._settings['speaker']['type']=='image' and 'speaker' not in self._slot_items:
            if SPEAKER_PHOTO_PATH.is_file():
                self._render_slot('speaker')
        self._tick_job=self.after(100,self._tick)

    def _zone_at(self,x,y):
        ox,oy,s=self._geometry
        if s<=0:return 'game'
        px,py=(x-ox)/s,(y-oy)/s
        for key,(a,b,c,d) in TIKTOK_SLOTS.items():
            if a<=px<=c and b<=py<=d:return key
        return 'game'

    def _show_popup(self,event):
        key=self._zone_at(event.x,event.y)
        m=tk.Menu(self,tearoff=0,bg='#10162F',fg='white',activebackground='#13548B',activeforeground='white')
        m.add_command(label='Zona: '+TIKTOK_LABELS[key],state='disabled')
        m.add_separator()
        m.add_command(label='Configurar esta zona...',command=lambda k=key:self._edit_slot(k))
        m.add_command(label='Elegir una imagen...',command=lambda k=key:self._select_image(k))
        m.add_command(label='Dejar esta zona vacia',command=lambda k=key:self._save_slot(k,'none',''))
        zones=tk.Menu(m,tearoff=0)
        for zone,label in TIKTOK_LABELS.items():
            zones.add_command(label=label,command=lambda k=zone:self._edit_slot(k))
        m.add_cascade(label='Configurar otra zona',menu=zones)
        m.add_separator()
        m.add_command(label='Ayuda: las selecciones se guardan automaticamente',state='disabled')
        try:m.tk_popup(event.x_root,event.y_root)
        finally:m.grab_release()
        return 'break'

    def _select_image(self,key):
        path=filedialog.askopenfilename(parent=self.winfo_toplevel(),
             title='Imagen para '+TIKTOK_LABELS[key],
             filetypes=[('Imagenes','*.png *.jpg *.jpeg *.webp *.gif *.bmp'),('Todos','*.*')])
        if path:self._save_slot(key,'image',path)

    def _save_slot(self,key,typ,value):
        value=str(value).strip()
        if typ=='url' and value and not value.lower().startswith(('https://','http://')):
            messagebox.showwarning('FUTUREO','Introduce una URL completa https://...',parent=self.winfo_toplevel())
            return
        with self._guard:
            self._settings[key]={'type':typ,'value':value}
            self._latest_frames.pop(key,None)
        self._save_config()
        self._cached_images.clear()
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job=self.after(70,self._layout)

    def _edit_slot(self,key):
        '''Right-click configuration: each region chooses its own source.'''
        top=tk.Toplevel(self)
        top.title('FUTUREO LIVE - '+TIKTOK_LABELS[key])
        top.configure(bg='#0A1327')
        top.geometry('520x290')
        top.resizable(False,False)
        top.transient(self.winfo_toplevel())
        top.grab_set()
        for i in range(3):top.grid_columnconfigure(i,weight=1 if i==1 else 0)
        label_fg='#D9F6FF'
        tk.Label(top,text='CONFIGURAR CONTENIDO DE LA ZONA',bg='#0A1327',fg='#42D8FF',
                 font=('Arial',13,'bold')).grid(row=0,column=0,columnspan=3,pady=12,padx=14,sticky='w')
        tk.Label(top,text='Zona:',bg='#0A1327',fg=label_fg).grid(row=1,column=0,padx=15,pady=8,sticky='e')
        zone_var=tk.StringVar(value=TIKTOK_LABELS[key])
        zones={label:zone for zone,label in TIKTOK_LABELS.items()}
        zone_box=ttk.Combobox(top,textvariable=zone_var,state='readonly',values=list(zones),width=35)
        zone_box.grid(row=1,column=1,columnspan=2,sticky='ew',padx=15)
        tk.Label(top,text='Mostrar:',bg='#0A1327',fg=label_fg).grid(row=2,column=0,padx=15,pady=8,sticky='e')
        back={v:k for k,v in TIKTOK_SOURCE_LABELS.items()}
        typ_var=tk.StringVar(value=TIKTOK_SOURCE_LABELS.get(self._settings[key]['type'],'Vacio / transparente'))
        type_box=ttk.Combobox(top,textvariable=typ_var,state='readonly',values=list(back),width=35)
        type_box.grid(row=2,column=1,columnspan=2,sticky='ew',padx=15)
        tk.Label(top,text='Fuente/valor:',bg='#0A1327',fg=label_fg).grid(row=3,column=0,padx=15,pady=8,sticky='e')
        value_var=tk.StringVar(value=self._settings[key]['value'])
        value_box=ttk.Combobox(top,textvariable=value_var,width=35)
        value_box.grid(row=3,column=1,sticky='ew',padx=(15,4))
        browse=tk.Button(top,text='Examinar',command=lambda:self._browse_for_dialog(value_var),
                          bg='#134A79',fg='white',relief='flat')
        browse.grid(row=3,column=2,padx=(0,15),sticky='ew')
        help_var=tk.StringVar()
        tk.Label(top,textvariable=help_var,bg='#0A1327',fg='#8AA9C6',justify='left',
                 wraplength=460).grid(row=4,column=0,columnspan=3,pady=13,padx=16,sticky='w')
        def source_changed(*_):
            typ=back.get(typ_var.get(),'none')
            if typ=='monitor':
                names=['1']
                if mss is not None:
                    try:
                        with mss.mss() as grab:
                            names=[str(i) for i in range(1,len(grab.monitors))] or ['1']
                    except (OSError,ValueError):pass
                value_box.configure(values=names)
                help_var.set('Selecciona el monitor. 1 es la pantalla principal.')
            elif typ=='window':
                found=_win_list()
                mappings={f'{title}  [HWND:{hwnd}]':str(hwnd) for hwnd,title in found}
                value_box.configure(values=list(mappings))
                help_var.set('Elige una ventana abierta; el programa la capturara en vivo.')
                value_box._window_map=mappings
            elif typ=='camera':
                value_box.configure(values=['0','1','2','3'])
                help_var.set('Indice de camara. 0 suele ser la camara integrada.')
            elif typ=='image':
                value_box.configure(values=[])
                help_var.set('Archivo PNG, JPG o WEBP. Usa Examinar.')
            elif typ=='url':
                value_box.configure(values=[])
                help_var.set('URL real del sitio que abriran quienes escaneen el QR.')
            elif typ=='text':
                value_box.configure(values=[])
                help_var.set('Escribe el texto que aparecera en esta zona.')
            else:
                value_box.configure(values=[])
                help_var.set('Deja espacio libre para los comentarios reales de TikTok.')
            if typ!=self._settings[zones.get(zone_var.get(),key)]['type']:
                value_var.set('')
        def zone_changed(*_):
            z=zones.get(zone_var.get(),key)
            c=self._settings[z]
            typ_var.set(TIKTOK_SOURCE_LABELS.get(c['type'],TIKTOK_SOURCE_LABELS['none']))
            value_var.set(c['value'])
        zone_box.bind('<<ComboboxSelected>>',zone_changed)
        type_box.bind('<<ComboboxSelected>>',source_changed)
        source_changed()
        def apply():
            z=zones.get(zone_var.get(),key)
            typ=back.get(typ_var.get(),'none')
            val=value_var.get()
            if typ=='window':
                val=getattr(value_box,'_window_map',{}).get(val,val)
                if not str(val).isdigit():
                    messagebox.showwarning('FUTUREO','Selecciona una ventana valida.',parent=top)
                    return
            if typ in ('monitor','camera') and not str(val).isdigit():
                messagebox.showwarning('FUTUREO','Selecciona un numero de pantalla/camara.',parent=top)
                return
            self._save_slot(z,typ,val)
            top.destroy()
        tk.Button(top,text='GUARDAR ZONA',command=apply,bg='#0587C4',fg='white',
                  relief='flat',font=('Arial',10,'bold')).grid(row=5,column=1,padx=15,pady=12,sticky='ew')
        tk.Button(top,text='CANCELAR',command=top.destroy,bg='#202945',fg='white',
                  relief='flat').grid(row=5,column=2,padx=(0,15),sticky='ew')

    def _browse_for_dialog(self,value_var):
        path=filedialog.askopenfilename(parent=self.winfo_toplevel(),
             title='Escoge una imagen',filetypes=[('Imagenes','*.png *.jpg *.jpeg *.webp *.gif *.bmp'),('Todos','*.*')])
        if path:value_var.set(path)

    def _on_destroy(self,event):
        if event.widget is not self:return
        self._active=False
        self._stop.set()
        for job in (self._tick_job,self._resize_job):
            if job is not None:
                try:self.after_cancel(job)
                except tk.TclError:pass
        if self._insert_handle:
            try:self._host_root.unbind('<Insert>',self._insert_handle)
            except tk.TclError:pass


def render(parent: tk.Misc) -> tk.Widget:
    """Entrada compatible con el lanzador app.py del repositorio."""
    return TikTokLiveScene(parent)


def main() -> None:
    root = tk.Tk()
    root.title("FUTUREO LIVE")
    root.geometry("620x1050")
    root.minsize(450, 720)
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