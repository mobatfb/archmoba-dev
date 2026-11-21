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
import math
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

VERSION = "2.12.2"
FONDO = "#050A19"
VIDEO_SPEED = 1.20  # MP4 reproducido un 20 por ciento mas rapido
VIDEO_BACKGROUND_ENABLED = False  # Cambiar a True para reactivar MP4/GIF.
STREAMER_NEON_ENABLED = True  # Cuadro del streamer dibujado con Tkinter.
STREAMER_SIDE_RATIO = 0.27  # Altura del marco en proporcion al lienzo.
STREAMER_ASPECT_RATIO = 1.35  # Rectangulo 12.5% mas ancho que en v2.8.3.
STREAMER_MARGIN_PX = 5  # Separacion de los bordes superior e izquierdo.
STREAMER_CARS_PER_LANE = 5  # Coches circulan en ambos sentidos.
STREAMER_TRAFFIC_FPS = 24  # Movimiento suave y semaforos dinamicos.
STREAMER_LANE_SPACING = 14  # Dos carriles paralelos con linea central.
STREAMER_FOLLOW_DISTANCE = 23  # Separacion minima entre vehiculos.
STREAMER_TURN_PROBABILITY = 0.42  # Probabilidad de cambiar de carril en verde.
STREAMER_TURN_DURATION = 0.85  # Segundos para completar un giro en U.
STREAMER_TURN_CLEARANCE = 70  # Espacio libre antes de cambiar de carril.
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
URL_ROOT = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/FUTUREOLIVE/assets"
VIDEO_URL = URL_ROOT + "/fondo_sin_marcos_4k.mp4"
GIF_URL = URL_ROOT + "/fondo_sin_marcos.gif"
MAX_VIDEO_BYTES = 32 * 1024 * 1024
MAX_GIF_BYTES = 8 * 1024 * 1024




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
        # Id de los trazos del cuadrado neon dibujado en el Canvas.
        self._neon_item: int | None = None
        self._neon_resize_job: str | None = None
        self._streamer_traffic_job: str | None = None
        self._streamer_traffic_last = 0.0
        self._streamer_signal_epoch = time.monotonic()
        self._streamer_paths: list[dict] = []
        self._streamer_cars: list[dict] = []
        self._streamer_signals: list[dict] = []
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
        # Los rayos se calculan en un hilo de PIL; Tkinter solo muestra
        # imagenes RGBA preparadas, sin desenfoques ni fusion de pantalla.
        self._lightning_generation = 0
        self._lightning_waiting = False
        self._lightning_results: queue.Queue = queue.Queue(maxsize=2)
        self._lightning_poll_job: str | None = None
        self._lightning_frames: list[tuple[int, int, Image.Image]] = []
        self._lightning_photo: ImageTk.PhotoImage | None = None
        self._lightning_item: int | None = None
        # Fogonazo visible encima de la captura y vista previa inmediata.
        self._lightning_flash_photo: ImageTk.PhotoImage | None = None
        self._lightning_flash_item: int | None = None
        self._lightning_flash_size = (0, 0)
        self._lightning_preview_active = False
        self._lightning_preview_job: str | None = None
        self._background_item: int | None = None
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
        if STREAMER_NEON_ENABLED:
            self.after_idle(self._draw_neon_window)
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
        """Descarga fondos opcionales. El cuadro del streamer no necesita PNG."""
        choices = []
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
        new_size = (max(1, int(event.width)), max(1, int(event.height)))
        if new_size == self._size:
            return
        self._size = new_size
        # Una imagen del tamano anterior nunca debe sustituir a la actual.
        self._lightning_generation += 1
        self._lightning_waiting = False
        self._lightning_frames.clear()
        self._lightning_phase = -1
        self._hide_lightning_overlay()
        self._hide_lightning_preview()
        self._lightning_flash_photo = None
        self._lightning_flash_size = (0, 0)
        if self._lightning_clear_job is not None:
            self.after_cancel(self._lightning_clear_job)
            self._lightning_clear_job = None
        if self._lightning_poll_job is not None:
            self.after_cancel(self._lightning_poll_job)
            self._lightning_poll_job = None
        if not VIDEO_BACKGROUND_ENABLED:
            self.after_idle(self._show_static_background)
        if self._neon_resize_job is not None:
            self.after_cancel(self._neon_resize_job)
        # Evita regenerar una imagen grande en cada pixel durante resize.
        if STREAMER_NEON_ENABLED:
            self._neon_resize_job = self.after(90, self._draw_neon_window)
        if self._border_resize_job is not None:
            self.after_cancel(self._border_resize_job)
        if NEON_BORDER_ENABLED:
            self._border_resize_job = self.after(90, self._draw_neon_border)

    def _draw_neon_window(self) -> None:
        """Carretera neon de dos carriles; ida y vuelta, con semaforos."""
        self._neon_resize_job = None
        if not self._alive or not self.winfo_exists():
            return

        if self._streamer_traffic_job is not None:
            self.after_cancel(self._streamer_traffic_job)
            self._streamer_traffic_job = None
        self.delete("ventana_neon")
        self._streamer_paths.clear()
        self._streamer_cars.clear()
        self._streamer_signals.clear()
        self._neon_item = None
        if not STREAMER_NEON_ENABLED:
            return

        width, height = self._size
        if width < 160 or height < 120:
            return

        frame_h = max(110, int(min(width, height) * STREAMER_SIDE_RATIO))
        frame_h = min(
            frame_h, height - 2 * STREAMER_MARGIN_PX - 8,
            int((width - 2 * STREAMER_MARGIN_PX - 8) / STREAMER_ASPECT_RATIO),
        )
        if frame_h < 60:
            return
        frame_w = int(round(frame_h * STREAMER_ASPECT_RATIO))

        x0, y0 = STREAMER_MARGIN_PX + 4, STREAMER_MARGIN_PX + 4
        x1, y1 = x0 + frame_w - 8, y0 + frame_h - 8
        bevel = max(7, min(18, int(min(frame_w, frame_h) * .10)))

        def polygon_points(inset: int = 0) -> tuple[int, ...]:
            left, top, right, bottom = x0 + inset, y0 + inset, x1 - inset, y1 - inset
            cut = min(max(3, bevel - inset),
                      (right - left) // 3, (bottom - top) // 3)
            return (
                left + cut, top, right - cut, top,
                right, top + cut, right, bottom - cut,
                right - cut, bottom, left + cut, bottom,
                left, bottom - cut, left, top + cut,
                left + cut, top,
            )

        # Dos pistas visibles: azul-cian por fuera, violeta por dentro.
        # Cada carril es un circuito independiente con sentido opuesto.
        lane_layout = (
            (0, ((7, "#0C2C52"), (4, "#14639C"), (2, "#5BE8FF"))),
            (STREAMER_LANE_SPACING,
             ((7, "#271849"), (4, "#7251A8"), (2, "#C3A1FF"))),
        )
        for inset, effects in lane_layout:
            outline = polygon_points(inset)
            for stroke, color in effects:
                item = self.create_line(
                    *outline, fill=color, width=stroke, smooth=False,
                    joinstyle=tk.MITER, capstyle=tk.BUTT,
                    tags=("ventana_neon", "streamer_road"),
                )
                if self._neon_item is None:
                    self._neon_item = item
            self._streamer_paths.append(self._streamer_build_path(outline))

        # Linea discontinua central que sugiere una via de doble sentido.
        self.create_line(
            *polygon_points(STREAMER_LANE_SPACING // 2),
            fill="#4C719A", width=1, dash=(5, 8), smooth=False,
            joinstyle=tk.MITER, tags=("ventana_neon", "streamer_road"),
        )

        # Dos zonas de detencion: arriba para ida y abajo para vuelta.
        outer, inner = self._streamer_paths
        outer["stop"] = outer["segments"][0][4] * .53
        bottom_offset = (sum(seg[4] for seg in inner["segments"][:4])
                         + inner["segments"][4][4] * .48)
        inner["stop"] = (inner["length"] - bottom_offset) % inner["length"]

        for lane, path in enumerate(self._streamer_paths):
            sx, sy, _, _ = self._streamer_lane_point(lane, path["stop"])

            # Las 3 bombillas van DENTRO de la carretera: entre la linea
            # exterior y la interior, sin caja flotante ni marco de semaforo.
            # Arriba la via interior queda abajo; abajo la via exterior
            # tambien queda abajo. Por eso ambas suman medio ancho.
            road_y = sy + STREAMER_LANE_SPACING / 2
            signal_x = sx + (18 if lane == 0 else -18)

            # Linea de alto, al lado de las luces y dentro de su carril.
            self.create_line(
                sx, road_y - 4, sx, road_y + 4,
                fill="#D7F4FF", width=2,
                tags=("ventana_neon", "streamer_road"),
            )

            lamps = []
            halos = []
            for offset in (-9, 0, 9):
                cx = signal_x + offset
                cy = road_y
                halo = self.create_oval(
                    cx - 4.2, cy - 4.2, cx + 4.2, cy + 4.2,
                    fill="#102035", outline="",
                    tags=("ventana_neon", "streamer_signal"),
                )
                lamp = self.create_oval(
                    cx - 2.7, cy - 2.7, cx + 2.7, cy + 2.7,
                    fill="#203046", outline="",
                    tags=("ventana_neon", "streamer_signal"),
                )
                halos.append(halo)
                lamps.append(lamp)
            self._streamer_signals.append({
                "lane": lane, "lamps": lamps, "halos": halos,
            })

        self._start_streamer_traffic()
        self.tag_raise("ventana_neon")

    @staticmethod
    def _streamer_build_path(flat: tuple[int, ...]) -> dict:
        """Conserva las longitudes de los 8 tramos del poligono cerrado."""
        vertices = [
            (float(flat[i]), float(flat[i + 1]))
            for i in range(0, len(flat) - 2, 2)
        ]
        segments = []
        total = 0.0
        for index, (ax, ay) in enumerate(vertices):
            bx, by = vertices[(index + 1) % len(vertices)]
            distance = math.hypot(bx - ax, by - ay)
            if distance > 0:
                segments.append((ax, ay, bx, by, distance))
                total += distance
        return {"segments": segments, "length": total, "stop": 0.0}

    def _streamer_lane_point(
        self, lane: int, progress: float
    ) -> tuple[float, float, float, float]:
        """Posicion y orientacion sobre un carril, respetando su sentido."""
        path = self._streamer_paths[lane]
        perimeter = path["length"]
        if perimeter <= 0:
            return (0.0, 0.0, 1.0, 0.0)
        distance = (progress if lane == 0 else -progress) % perimeter
        for ax, ay, bx, by, length in path["segments"]:
            if distance <= length:
                ratio = distance / length
                direction = 1 if lane == 0 else -1
                return (
                    ax + (bx - ax) * ratio,
                    ay + (by - ay) * ratio,
                    direction * (bx - ax) / length,
                    direction * (by - ay) / length,
                )
            distance -= length
        ax, ay, bx, by, length = path["segments"][0]
        direction = 1 if lane == 0 else -1
        return (ax, ay, direction * (bx - ax) / length,
                direction * (by - ay) / length)

    @staticmethod
    def _streamer_car_shape(
        x: float, y: float, tx: float, ty: float, length: float, width: float
    ) -> tuple[float, ...]:
        """Carroceria rotada conforme al sentido del tramo."""
        front_x, front_y = tx * length * .5, ty * length * .5
        side_x, side_y = -ty * width * .5, tx * width * .5
        return (
            x - front_x - side_x, y - front_y - side_y,
            x + front_x - side_x, y + front_y - side_y,
            x + front_x + side_x, y + front_y + side_y,
            x - front_x + side_x, y - front_y + side_y,
        )

    def _streamer_show_car(self, car: dict, pose=None) -> None:
        """Mueve carroceria y luces; admite poses intermedias durante un giro."""
        x, y, tx, ty = (pose if pose is not None else
                         self._streamer_lane_point(car["lane"], car["progress"]))
        self.coords(
            car["body"],
            *self._streamer_car_shape(x, y, tx, ty, 13, 6),
        )
        self.coords(
            car["glass"],
            *self._streamer_car_shape(
                x + tx * 1.0, y + ty * 1.0, tx, ty, 5.0, 4.0
            ),
        )
        hx, hy = x + tx * 6.5, y + ty * 6.5
        rx, ry = x - tx * 6.5, y - ty * 6.5
        for item, px, py, radius in (
            (car["head"], hx, hy, 1.8),
            (car["tail"], rx, ry, 1.5),
        ):
            self.coords(item, px - radius, py - radius,
                        px + radius, py + radius)

    def _streamer_signal_state(self, lane: int, now: float) -> str:
        """Semaforos desfasados: verde, amarillo y rojo en ciclos regulares."""
        elapsed = now - self._streamer_signal_epoch
        phase = (elapsed + lane * 5.5) % 11.0
        if phase < 4.8:
            return "green"
        if phase < 5.8:
            return "yellow"
        return "red"

    def _start_streamer_traffic(self) -> None:
        """Crea automoviles de distinto color y velocidad en ambas vias."""
        palette = (
            "#FFB53D", "#42D5FF", "#FF679B", "#96FF77",
            "#E4F4FF", "#BB8AFF", "#FF6947",
        )
        now = time.monotonic()
        self._streamer_signal_epoch = now
        for lane, path in enumerate(self._streamer_paths):
            distance = path["length"]
            if distance <= 80:
                continue
            count = min(STREAMER_CARS_PER_LANE, max(3, int(distance / 135)))
            for i in range(count):
                # Espaciado inicial con variacion aleatoria; evita choques.
                position = distance * (i + random.uniform(.22, .67)) / count
                body = self.create_polygon(
                    0, 0, 1, 0, 1, 1, 0, 1, fill=random.choice(palette),
                    outline="#061121", width=1,
                    tags=("ventana_neon", "streamer_car"),
                )
                glass = self.create_polygon(
                    0, 0, 1, 0, 1, 1, 0, 1, fill="#DBF8FF", outline="",
                    tags=("ventana_neon", "streamer_car"),
                )
                head = self.create_oval(
                    0, 0, 1, 1, fill="#FFFFCB", outline="",
                    tags=("ventana_neon", "streamer_car"),
                )
                tail = self.create_oval(
                    0, 0, 1, 1, fill="#FF344D", outline="",
                    tags=("ventana_neon", "streamer_car"),
                )
                self._streamer_cars.append({
                    "lane": lane, "progress": position,
                    "speed": 0.0, "cruise": random.uniform(30.0, 59.0),
                    "turn": None, "turn_attempted": False,
                    "last_turn": -1000.0,
                    "body": body, "glass": glass,
                    "head": head, "tail": tail,
                })

        self._streamer_traffic_last = time.monotonic()
        self._streamer_traffic_tick()

    def _streamer_nearest_progress(
        self, lane: int, x: float, y: float
    ) -> float:
        """Proyecta una ubicacion al carril opuesto respetando su sentido."""
        path = self._streamer_paths[lane]
        best_distance = float("inf")
        best_progress = 0.0
        elapsed = 0.0
        for ax, ay, bx, by, segment_length in path["segments"]:
            vx, vy = bx - ax, by - ay
            ratio = max(0.0, min(
                1.0, ((x - ax) * vx + (y - ay) * vy)
                / max(segment_length * segment_length, .001)
            ))
            px, py = ax + vx * ratio, ay + vy * ratio
            distance = (x - px) ** 2 + (y - py) ** 2
            if distance < best_distance:
                best_distance = distance
                best_progress = elapsed + ratio * segment_length
            elapsed += segment_length
        return (best_progress if lane == 0 else
                path["length"] - best_progress) % path["length"]

    def _streamer_turn_is_safe(
        self, car: dict, target_lane: int, target_progress: float
    ) -> bool:
        """Requiere un espacio libre amplio en ambos sentidos del otro carril."""
        # Solo un coche gira al mismo tiempo; evita conflictos de trayectorias.
        if any(other["turn"] is not None for other in self._streamer_cars):
            return False
        perimeter = self._streamer_paths[target_lane]["length"]
        if perimeter <= 0:
            return False
        for other in self._streamer_cars:
            if other is car or other["lane"] != target_lane:
                continue
            forward = (target_progress - other["progress"]) % perimeter
            backward = (other["progress"] - target_progress) % perimeter
            # La separacion incluye la longitud del giro y el frenado
            # anticipado de los coches que llegan al punto de incorporacion.
            if min(forward, backward) < STREAMER_TURN_CLEARANCE:
                return False
        return True

    @staticmethod
    def _streamer_turn_pose(turn: dict, fraction: float):
        """Curva cubica: inicio y fin tangentes a sus respectivos carriles."""
        t = max(0.0, min(1.0, fraction))
        sx, sy, stx, sty = turn["start"]
        ex, ey, etx, ety = turn["end"]
        control = max(13.0, STREAMER_LANE_SPACING * .85)
        p0 = (sx, sy)
        p1 = (sx + stx * control, sy + sty * control)
        p2 = (ex - etx * control, ey - ety * control)
        p3 = (ex, ey)
        inv = 1.0 - t
        x = (inv ** 3 * p0[0] + 3 * inv * inv * t * p1[0]
             + 3 * inv * t * t * p2[0] + t ** 3 * p3[0])
        y = (inv ** 3 * p0[1] + 3 * inv * inv * t * p1[1]
             + 3 * inv * t * t * p2[1] + t ** 3 * p3[1])
        dx = (3 * inv * inv * (p1[0] - p0[0])
              + 6 * inv * t * (p2[0] - p1[0])
              + 3 * t * t * (p3[0] - p2[0]))
        dy = (3 * inv * inv * (p1[1] - p0[1])
              + 6 * inv * t * (p2[1] - p1[1])
              + 3 * t * t * (p3[1] - p2[1]))
        magnitude = math.hypot(dx, dy)
        if magnitude < .001:
            return (x, y, etx, ety)
        return (x, y, dx / magnitude, dy / magnitude)

    def _streamer_begin_turn(
        self, car: dict, now: float, target_lane: int,
        target_progress: float
    ) -> None:
        """Reserva el carril opuesto y comienza un giro visible de 180 grados."""
        car["turn"] = {
            "begin": now, "duration": STREAMER_TURN_DURATION,
            "from_lane": car["lane"], "target_lane": target_lane,
            "target_progress": target_progress,
            "start": self._streamer_lane_point(car["lane"], car["progress"]),
            "end": self._streamer_lane_point(target_lane, target_progress),
        }
        car["speed"] = 0.0
        car["turn_attempted"] = True

    def _streamer_advance_turns(self, now: float) -> None:
        """Anima cambios de carril con orientacion continua y sin teletransportes."""
        for car in self._streamer_cars:
            turn = car["turn"]
            if turn is None:
                continue
            elapsed = (now - turn["begin"]) / turn["duration"]
            if elapsed >= 1.0:
                car["lane"] = turn["target_lane"]
                car["progress"] = turn["target_progress"]
                car["turn"] = None
                car["last_turn"] = now
                car["turn_attempted"] = True
                car["speed"] = 0.0
                self._streamer_show_car(car)
            else:
                self._streamer_show_car(
                    car, pose=self._streamer_turn_pose(turn, elapsed)
                )

    def _streamer_merge_clearance(self, car: dict, perimeter: float) -> float:
        """Bloquea temporalmente la incorporacion para coches del otro sentido."""
        free = perimeter
        for other in self._streamer_cars:
            turn = other["turn"]
            if turn is None or turn["target_lane"] != car["lane"]:
                continue
            # Obstaculo virtual en el punto de incorporacion mientras gira.
            ahead = (turn["target_progress"] - car["progress"]) % perimeter
            if ahead < 140:
                free = min(free, max(0.0, ahead - STREAMER_FOLLOW_DISTANCE))
        return free

    def _streamer_traffic_tick(self) -> None:
        """Circulacion bidireccional real: frenado en rojo y distancia segura."""
        self._streamer_traffic_job = None
        if (not self._alive or not self.winfo_exists()
                or not STREAMER_NEON_ENABLED or not self._streamer_paths):
            return

        now = time.monotonic()
        # No perder tiempo real cuando otro dibujo retrase un fotograma.
        dt = min(.22, max(0.0, now - self._streamer_traffic_last))
        self._streamer_traffic_last = now
        for signal in self._streamer_signals:
            state = self._streamer_signal_state(signal["lane"], now)
            bright = ("#FF364E", "#FFD539", "#34FF82")
            muted = ("#471724", "#4A3A14", "#153D27")
            active = {"red": 0, "yellow": 1, "green": 2}[state]
            halo_colors = ("#521925", "#55431A", "#15553C")
            for j, lamp in enumerate(signal["lamps"]):
                self.itemconfigure(
                    lamp, fill=bright[j] if j == active else muted[j]
                )
                self.itemconfigure(
                    signal["halos"][j],
                    fill=halo_colors[j] if j == active else "#102035",
                )

        # Los giros se animan antes de calcular el trafico restante.
        self._streamer_advance_turns(now)

        for lane, path in enumerate(self._streamer_paths):
            perimeter = path["length"]
            cars = sorted(
                (c for c in self._streamer_cars if c["lane"] == lane),
                key=lambda c: c["progress"], reverse=True,
            )
            if not cars or perimeter <= 0:
                continue

            red = self._streamer_signal_state(lane, now) != "green"
            for i, car in enumerate(cars):
                if car["turn"] is not None:
                    # Se mantiene en el carril de origen como obstaculo
                    # hasta que termine de entrar en el otro carril.
                    continue

                leader = cars[i - 1] if i else cars[-1]
                gap = (leader["progress"] - car["progress"]) % perimeter
                if len(cars) == 1:
                    gap = perimeter
                free = max(0.0, gap - STREAMER_FOLLOW_DISTANCE)
                free = min(free, self._streamer_merge_clearance(car, perimeter))
                target = car["cruise"]
                if free < 70:
                    target = min(target, free * 1.8)

                distance_to_light = (
                    path["stop"] - car["progress"]
                ) % perimeter
                # Se vuelve a sortear solamente en la siguiente vuelta.
                if distance_to_light > 55:
                    car["turn_attempted"] = False

                must_stop = red and distance_to_light < 135
                if must_stop:
                    remaining = max(0.0, distance_to_light - 12.0)
                    target = min(target, math.sqrt(2 * 145.0 * remaining))

                # Solo al llegar al semaforo, con luz verde, se decide
                # aleatoriamente si realizar un giro en U hacia el otro carril.
                if (not red and not car["turn_attempted"]
                        and 8 <= distance_to_light <= 19
                        and now - car["last_turn"] > 4.0):
                    car["turn_attempted"] = True
                    if random.random() < STREAMER_TURN_PROBABILITY:
                        other_lane = 1 - lane
                        x, y, _, _ = self._streamer_lane_point(
                            lane, car["progress"]
                        )
                        other_progress = self._streamer_nearest_progress(
                            other_lane, x, y
                        )
                        if self._streamer_turn_is_safe(
                            car, other_lane, other_progress
                        ):
                            self._streamer_begin_turn(
                                car, now, other_lane, other_progress
                            )
                            self._streamer_show_car(
                                car, pose=car["turn"]["start"]
                            )
                            continue

                if target < car["speed"]:
                    car["speed"] = max(target, car["speed"] - 145.0 * dt)
                else:
                    car["speed"] = min(target, car["speed"] + 75.0 * dt)

                advance = min(car["speed"] * dt, free)
                if must_stop:
                    advance = min(
                        advance, max(0.0, distance_to_light - 12.0)
                    )
                car["progress"] = (car["progress"] + advance) % perimeter
                self._streamer_show_car(car)

        self.tag_raise("ventana_neon")
        self._streamer_traffic_job = self.after(
            max(25, int(1000 / STREAMER_TRAFFIC_FPS)),
            self._streamer_traffic_tick,
        )

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
        if STREAMER_NEON_ENABLED and self._neon_item is not None:
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
                    # Ventana del hablante sobre captura y marco.
                    if STREAMER_NEON_ENABLED and self._neon_item is not None:
                        self.tag_raise("ventana_neon")
                    # La captura se refresca continuamente: el rayo siempre
                    # debe quedar por encima o desapareceria detras de ella.
                    if self._lightning_phase >= 0 or self._lightning_preview_active:
                        self._raise_lightning_layers()
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
        """Genera una descarga, pero NO procesa desenfoques en Tkinter."""
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
                branch.append((int(max(0, min(width - 1, bx))),
                               int(min(height - 1, by))))
            branches.append(branch)

        self._lightning_path = path
        self._lightning_branches = branches
        self._lightning_target = (tx, ty)
        self._lightning_generation += 1
        generation = self._lightning_generation
        self._lightning_waiting = True
        self._lightning_phase = -1
        self._lightning_frames.clear()
        self._hide_lightning_overlay()
        # El rayo se ve al instante, incluso si su halo PIL tarda en salir.
        self._show_lightning_preview(path, branches)
        if self._lightning_clear_job is not None:
            self.after_cancel(self._lightning_clear_job)
            self._lightning_clear_job = None

        # El trabajador solo recibe datos simples e imagenes PIL; no usa Tk.
        thread = threading.Thread(
            target=self._lightning_render_worker,
            args=(generation, (width, height), tuple(path),
                  tuple(tuple(branch) for branch in branches)),
            name="futureo-lightning", daemon=True,
        )
        thread.start()
        if self._lightning_poll_job is None:
            self._lightning_poll_job = self.after(
                30, self._check_lightning_render
            )
        self._schedule_lightning()

    @staticmethod
    def _rasterize_lightning(
        size: tuple[int, int], path: tuple, branches: tuple
    ) -> list[tuple[int, int, Image.Image]]:
        """Precalcula los cinco destellos PIL, una sola vez por descarga.

        La region se recorta alrededor del rayo y ambos desenfoques se
        ejecutan una vez, no en cada fase como antes.
        """
        w, h = size
        scale = max(.5, min(w, h) / 700.0)
        padding = int(
            min(w, h) * .17 + 3 * max(12, int(42 * scale)) + 12
        )
        all_points = list(path)
        for branch in branches:
            all_points.extend(branch)
        x0 = max(0, min(x for x, _ in all_points) - padding)
        y0 = max(0, min(y for _, y in all_points) - padding)
        x1 = min(w, max(x for x, _ in all_points) + padding + 1)
        y1 = min(h, max(y for _, y in all_points) + padding + 1)
        cropped = (x1 - x0, y1 - y0)
        if cropped[0] <= 0 or cropped[1] <= 0:
            return []

        bolt = [(x - x0, y - y0) for x, y in path]
        branches_local = [
            [(x - x0, y - y0) for x, y in branch]
            for branch in branches
        ]
        layer_paths = [bolt] + branches_local

        cloud = Image.new("RGBA", cropped, (0, 0, 0, 0))
        cloud_draw = ImageDraw.Draw(cloud, "RGBA")
        radius = int(min(w, h) * .17)
        for x, y in (bolt[4], bolt[len(bolt) // 2], bolt[-1]):
            cloud_draw.ellipse(
                (x - radius, y - radius, x + radius, y + radius),
                fill=(45, 145, 255, 64),
            )
        cloud = cloud.filter(
            ImageFilter.GaussianBlur(max(12, int(42 * scale)))
        )

        glow = Image.new("RGBA", cropped, (0, 0, 0, 0))
        glow_draw = ImageDraw.Draw(glow, "RGBA")
        for points in layer_paths:
            thickness = (12 if points is bolt else 6) * scale
            glow_draw.line(
                points, fill=(39, 130, 255, 195),
                width=max(2, int(thickness)), joint="curve",
            )
        glow = glow.filter(
            ImageFilter.GaussianBlur(max(3, int(12 * scale)))
        )

        core = Image.new("RGBA", cropped, (0, 0, 0, 0))
        core_draw = ImageDraw.Draw(core, "RGBA")
        for points in layer_paths:
            branch = points is not bolt
            for index in range(len(points) - 1):
                t = index / max(1, len(points) - 1)
                thick = max(
                    1, int((2.8 if not branch else 1.35) * scale
                           * (1.15 - .55 * t))
                )
                a, b = points[index], points[index + 1]
                core_draw.line(
                    (a, b), fill=(35, 156, 255, 225),
                    width=max(2, thick + 3),
                )
                core_draw.line(
                    (a, b), fill=(235, 251, 255, 255),
                    width=thick,
                )

        base = Image.alpha_composite(
            Image.alpha_composite(cloud, glow), core
        )
        alpha = base.getchannel("A")
        rendered = []
        for phase, intensity in enumerate((.97, .16, 1.0, .34, .11)):
            # Se reduce la opacidad para mantener las fases originales.
            frame = base.copy()
            table = [min(255, int(a * intensity)) for a in range(256)]
            frame.putalpha(alpha.point(table))
            if phase in (0, 2):
                flash = Image.new(
                    "RGBA", cropped, (175, 216, 255, int(23 * intensity))
                )
                frame = Image.alpha_composite(flash, frame)
            rendered.append((x0, y0, frame))
        return rendered

    def _lightning_render_worker(
        self, generation: int, size: tuple[int, int],
        path: tuple, branches: tuple
    ) -> None:
        """Hilo auxiliar: jamas invoca funciones ni widgets de Tkinter."""
        try:
            frames = self._rasterize_lightning(size, path, branches)
            error = None
        except Exception as exc:
            frames = []
            error = str(exc)
        message = (generation, size, frames, error)
        try:
            self._lightning_results.put_nowait(message)
        except queue.Full:
            try:
                self._lightning_results.get_nowait()
            except queue.Empty:
                pass
            try:
                self._lightning_results.put_nowait(message)
            except queue.Full:
                pass

    def _check_lightning_render(self) -> None:
        """Recoge PIL desde el hilo y programa el destello en Tkinter."""
        self._lightning_poll_job = None
        if not self._alive or not self.winfo_exists():
            return
        newest = None
        try:
            while True:
                result = self._lightning_results.get_nowait()
                if result[0] == self._lightning_generation:
                    newest = result
        except queue.Empty:
            pass

        if newest is not None:
            generation, size, frames, error = newest
            self._lightning_waiting = False
            if error:
                print("[FUTUREO] Error de rayo:", error)
            if frames and size == self._size:
                self._lightning_frames = frames
                self._lightning_phase = 0
                self._show_lightning_frame(0)
                self._lightning_clear_job = self.after(
                    55, self._advance_lightning, 1
                )
            return
        if self._lightning_waiting:
            self._lightning_poll_job = self.after(
                30, self._check_lightning_render
            )

    def _set_lightning_flash(self, visible: bool) -> None:
        """Fogonazo de pantalla completa; se genera una sola vez por tamano."""
        if not visible:
            if self._lightning_flash_item is not None:
                self.itemconfigure(self._lightning_flash_item, state="hidden")
            return
        w, h = self._size
        if w < 2 or h < 2:
            return
        if self._lightning_flash_photo is None or self._lightning_flash_size != (w, h):
            # RGBA ligero y reutilizable: no se regenera cada 55 ms.
            image = Image.new("RGBA", (w, h), (152, 210, 255, 83))
            self._lightning_flash_photo = ImageTk.PhotoImage(image, master=self)
            self._lightning_flash_size = (w, h)
        if self._lightning_flash_item is None:
            self._lightning_flash_item = self.create_image(
                0, 0, image=self._lightning_flash_photo, anchor="nw",
                tags=("rayos", "rayos_flash"),
            )
        else:
            self.itemconfigure(
                self._lightning_flash_item, image=self._lightning_flash_photo,
                state="normal",
            )
            self.coords(self._lightning_flash_item, 0, 0)

    def _raise_lightning_layers(self) -> None:
        """Rayo y fogonazo arriba de la captura, marco y carretera."""
        # El orden importa: el fogonazo queda debajo del nucleo luminoso.
        self.tag_raise("rayos_flash")
        self.tag_raise("rayos_overlay")
        self.tag_raise("lightning_preview")

    def _show_lightning_preview(self, path: list, branches: list) -> None:
        """Destello vectorial inmediato, sin filtros ni procesamiento costoso."""
        if self._lightning_preview_job is not None:
            self.after_cancel(self._lightning_preview_job)
            self._lightning_preview_job = None
        self.delete("lightning_preview")
        self._lightning_preview_active = True
        self._set_lightning_flash(True)
        for points in [path] + branches:
            if len(points) < 2:
                continue
            coords = [value for point in points for value in point]
            for thickness, color in (
                (9, "#134D88"),
                (5, "#30ABFF"),
                (2, "#F3FCFF"),
            ):
                self.create_line(
                    *coords, fill=color, width=thickness, smooth=False,
                    joinstyle=tk.ROUND, capstyle=tk.ROUND,
                    tags=("rayos", "lightning_preview"),
                )
        self._raise_lightning_layers()
        # Una descarga corta, no un trazo fijo mientras el hilo termina.
        self._lightning_preview_job = self.after(
            185, self._hide_lightning_preview
        )

    def _hide_lightning_preview(self) -> None:
        self._lightning_preview_job = None
        self.delete("lightning_preview")
        self._lightning_preview_active = False
        if self._lightning_phase < 0:
            self._set_lightning_flash(False)

    def _hide_lightning_overlay(self) -> None:
        """Oculta la capa del rayo sin tocar fondo, carretera ni captura."""
        if self._lightning_item is not None:
            self.itemconfigure(self._lightning_item, state="hidden")
        self._lightning_photo = None
        if not self._lightning_preview_active:
            self._set_lightning_flash(False)

    def _show_lightning_frame(self, phase: int) -> None:
        """Actualiza solo la capa de luz; se ejecuta en el hilo Tk."""
        if phase >= len(self._lightning_frames):
            self._hide_lightning_overlay()
            return
        # La vista previa acaba al sustituirse por la composicion final.
        if self._lightning_preview_active:
            self._hide_lightning_preview()
        x, y, overlay = self._lightning_frames[phase]
        self._lightning_photo = ImageTk.PhotoImage(overlay, master=self)
        if self._lightning_item is None:
            self._lightning_item = self.create_image(
                x, y, image=self._lightning_photo, anchor="nw",
                tags=("rayos", "rayos_overlay"),
            )
        else:
            self.itemconfigure(
                self._lightning_item, image=self._lightning_photo,
                state="normal"
            )
            self.coords(self._lightning_item, x, y)
        # Restaurar el fogonazo global en fases fuertes (0 y 2).
        self._set_lightning_flash(phase in (0, 2))
        self._raise_lightning_layers()

    def _advance_lightning(self, phase: int) -> None:
        """Muestra los destellos previamente calculados, sin filtros caros."""
        self._lightning_clear_job = None
        if not self._alive:
            return
        self._lightning_phase = phase if phase < 5 else -1
        self._show_lightning_frame(phase)
        if phase < 5:
            intervals = (55, 42, 95, 115, 125)
            self._lightning_clear_job = self.after(
                intervals[phase], self._advance_lightning, phase + 1
            )

    def _present(self, frame: Image.Image) -> None:
        """Solo actualiza el fotograma base; el rayo vive en otra capa."""
        self._last_frame = frame
        self._photo = ImageTk.PhotoImage(frame, master=self)
        if self._background_item is None:
            self._background_item = self.create_image(
                frame.width // 2, frame.height // 2, anchor="center",
                image=self._photo, tags=("fondo",)
            )
        else:
            self.itemconfigure(
                self._background_item, image=self._photo, state="normal"
            )
            self.coords(
                self._background_item, frame.width // 2, frame.height // 2
            )
        self.tag_lower("fondo")
        if self._lightning_phase >= 0 or self._lightning_preview_active:
            self._raise_lightning_layers()

    def _refresh_last_frame(self) -> None:
        """Refresca el fondo solo cuando cambia, nunca por cada rayo."""
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
        if self._streamer_traffic_job is not None:
            try:
                self.after_cancel(self._streamer_traffic_job)
            except tk.TclError:
                pass
            self._streamer_traffic_job = None
        self._lightning_generation += 1
        self._lightning_waiting = False
        for job in (
            self._lightning_job, self._lightning_clear_job,
            self._lightning_poll_job,
        ):
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
        self._lightning_poll_job = None
        if self._lightning_preview_job is not None:
            try:
                self.after_cancel(self._lightning_preview_job)
            except tk.TclError:
                pass
            self._lightning_preview_job = None
        self._lightning_frames.clear()
        self._lightning_photo = None
        self._lightning_flash_photo = None
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