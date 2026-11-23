# -*- coding: utf-8 -*-
"""Captura liviana y difusion PUSH para MULTIMANDO FUTUREO.
Cada espectador abre /stream (solo lectura). No entra a la sala ni a la cola.
Una sola captura JPEG por fotograma se comparte entre todos los espectadores.
"""
from __future__ import annotations
import ctypes
import io
import json
import threading
import time
from typing import Any, Callable

MAX_JPEG_BYTES = 180_000
FPS_CHOICES = (1, 2, 5, 10, 15)
SIZE_CHOICES = ((320, 180), (480, 270), (640, 360))

class FrameHub:
    """Estado ultimo-fotograma: sin cola por espectador ni solicitudes de polling."""
    def __init__(self, max_viewers: int = 80):
        self.cv = threading.Condition()
        self.seq = 0
        self.jpeg: bytes | None = None
        self.active = False
        self.meta: dict = {}
        self.viewers = 0
        self.max_viewers = max_viewers

    def set_active(self, active: bool, **meta: Any) -> None:
        with self.cv:
            self.active = bool(active)
            self.meta = meta if active else {}
            self.jpeg = None
            self.seq += 1
            self.cv.notify_all()

    def publish(self, jpeg: bytes) -> None:
        if not isinstance(jpeg, bytes) or not 0 < len(jpeg) <= MAX_JPEG_BYTES:
            raise ValueError("Fotograma JPEG fuera del limite de 180 KB")
        with self.cv:
            if not self.active:
                return
            self.jpeg = jpeg
            self.seq += 1
            self.cv.notify_all()

    def spectator(self, websocket: Any, stop: threading.Event) -> None:
        """Salida unidireccional: JAMAS pide hello, nombre ni manda datos a Room."""
        with self.cv:
            if self.viewers >= self.max_viewers:
                websocket.close(code=1013, reason="Limite de espectadores")
                return
            self.viewers += 1
        seen = -1
        try:
            while not stop.is_set():
                with self.cv:
                    if seen == self.seq:
                        self.cv.wait(timeout=1.0)
                    if seen == self.seq:
                        continue
                    seen = self.seq
                    jpeg = self.jpeg
                    active = self.active
                    meta = dict(self.meta)
                if active and jpeg is not None:
                    websocket.send(jpeg)     # binario JPEG, no base64 ni HTTP GET por frame
                else:
                    websocket.send(json.dumps(
                        {"type": "futureo_stream", "active": active, **meta},
                        separators=(",", ":")))
        except Exception:
            pass
        finally:
            with self.cv:
                self.viewers -= 1

def list_sources() -> list[tuple[str, str, int]]:
    """Pantallas y ventanas visibles de Windows. No guarda nombres privados."""
    if ctypes.sizeof(ctypes.c_void_p) < 4:
        return []
    import mss
    sources: list[tuple[str, str, int]] = []
    with mss.mss() as grabber:
        for i in range(1, len(grabber.monitors)):
            monitor = grabber.monitors[i]
            sources.append((f"Pantalla {i} ({monitor['width']}x{monitor['height']})", "screen", i))
    if __import__("sys").platform != "win32":
        return sources
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    cb_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def add(hwnd: int, _param: int) -> bool:
        if not user32.IsWindowVisible(hwnd) or user32.IsIconic(hwnd):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        if not 1 <= length <= 180:
            return True
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        label = title.value.strip()
        if label:
            sources.append((f"Ventana: {label[:85]}", "window", int(hwnd)))
        return True
    fn = cb_type(add)
    user32.EnumWindows(fn, 0)
    return sources

def capture_rectangle(grabber: Any, kind: str, value: int) -> dict:
    if kind == "screen":
        if not 1 <= value < len(grabber.monitors):
            raise RuntimeError("La pantalla seleccionada ya no existe")
        return dict(grabber.monitors[value])
    if kind != "window" or __import__("sys").platform != "win32":
        raise RuntimeError("Fuente de captura invalida")
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    if not user32.IsWindow(value) or user32.IsIconic(value) or not user32.IsWindowVisible(value):
        raise RuntimeError("La ventana se cerro, oculto o minimizo")
    rect = wintypes.RECT()
    if not user32.GetClientRect(value, ctypes.byref(rect)):
        raise RuntimeError("No se pudo consultar el area de la ventana")
    point = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(value, ctypes.byref(point)):
        raise RuntimeError("No se pudo ubicar la ventana")
    x, y = point.x, point.y
    w, h = rect.right - rect.left, rect.bottom - rect.top
    virtual = grabber.monitors[0]
    left = max(x, virtual["left"])
    top = max(y, virtual["top"])
    right = min(x + w, virtual["left"] + virtual["width"])
    bottom = min(y + h, virtual["top"] + virtual["height"])
    if right - left < 40 or bottom - top < 40:
        raise RuntimeError("La ventana no esta visible en pantalla")
    # Captura el area VISIBLE, no ventanas tapadas ni juego minimizado.
    return {"left": left, "top": top, "width": right - left, "height": bottom - top}

class ScreenBroadcaster:
    """Un productor JPEG independiente del numero de visitantes."""
    def __init__(self, hub: FrameHub, preview: Callable[[bytes], None] | None = None,
                 notice: Callable[[str], None] | None = None):
        self.hub = hub
        self.preview = preview
        self.notice = notice or (lambda _: None)
        self.worker: threading.Thread | None = None
        self.stopping = threading.Event()
        self.lock = threading.RLock()

    @property
    def running(self) -> bool:
        return self.worker is not None and self.worker.is_alive()

    def start(self, kind: str, source_id: int, size: tuple[int, int],
              fps: int = 5, quality: int = 55) -> None:
        if kind not in ("window", "screen") or type(source_id) is not int:
            raise ValueError("Seleccione una ventana o pantalla")
        if fps not in FPS_CHOICES or size not in SIZE_CHOICES or not 25 <= quality <= 85:
            raise ValueError("Parametros de transmision invalidos")
        with self.lock:
            if self.running:
                raise RuntimeError("Detenga primero la transmision anterior")
            self.stopping = threading.Event()
            self.hub.set_active(True, fps=fps, width=size[0], height=size[1])
            self.worker = threading.Thread(
                target=self._loop,
                args=(kind, source_id, size, fps, quality, self.stopping),
                daemon=True, name="FUTUREO-Stream-Capture")
            self.worker.start()

    def stop(self) -> None:
        with self.lock:
            self.stopping.set()
            self.hub.set_active(False)
            worker = self.worker
        if worker and worker is not threading.current_thread():
            worker.join(timeout=3)

    def _loop(self, kind: str, source_id: int, size: tuple[int, int],
              fps: int, quality: int, stopping: threading.Event) -> None:
        try:
            import mss
            from PIL import Image
            last_preview = 0.0
            with mss.mss() as grabber:
                while not stopping.is_set():
                    started = time.monotonic()
                    rect = capture_rectangle(grabber, kind, source_id)
                    raw = grabber.grab(rect)
                    im = Image.frombytes("RGB", raw.size, raw.rgb)
                    im.thumbnail(size, Image.Resampling.BILINEAR)
                    data = b""
                    for q in (quality, max(30, quality - 15), 25):
                        buf = io.BytesIO()
                        im.save(buf, format="JPEG", quality=q, optimize=False)
                        data = buf.getvalue()
                        if len(data) <= MAX_JPEG_BYTES:
                            break
                    if len(data) <= MAX_JPEG_BYTES:
                        self.hub.publish(data)
                        if self.preview and started - last_preview >= 0.9:
                            self.preview(data)
                            last_preview = started
                    stopping.wait(max(0, 1.0 / fps - (time.monotonic() - started)))
        except Exception as exc:
            self.notice("Captura detenida: " + str(exc)[:210])
        finally:
            if not stopping.is_set():
                self.hub.set_active(False)
            self.notice("Transmision detenida")

def stream_selftest() -> None:
    """Prueba de difusion sin Windows ni Pillow; incluye espectador anonimo."""
    class Socket:
        def __init__(self): self.messages = []
        def send(self, data): self.messages.append(data)
    hub = FrameHub()
    stop = threading.Event()
    sock = Socket()
    t = threading.Thread(target=hub.spectator, args=(sock, stop), daemon=True)
    t.start()
    hub.set_active(True, fps=2, width=320, height=180)
    hub.publish(b"\xff\xd8" + b"x" * 10)
    time.sleep(0.1)
    stop.set()
    with hub.cv: hub.cv.notify_all()
    t.join(timeout=2)
    assert any(isinstance(v, bytes) and v[:2] == b"\xff\xd8" for v in sock.messages)
    assert hub.viewers == 0
    print("OK: espectador anonimo, difusion PUSH, sin sala ni cola")
