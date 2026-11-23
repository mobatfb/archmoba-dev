# -*- coding: utf-8 -*-
"""FUTUREO STREAM v2.2: captura JPEG de baja latencia y difusion publica PUSH.

Un unico productor publica unicamente el fotograma mas reciente. Cada cliente
de /stream es espectador anonimo: NO entra a Room, no necesita hello, no
consume turno y no transmite entradas. El mismo tunel Cloudflare sirve / y
/stream, sin HTTP polling de imagenes.

Protocolo binario v2.2 (20 bytes + JPEG):
    !4s I Q H H = b'FJ22', secuencia, captura_epoch_ms,
                  procesamiento_ms, fps_configurados
La pagina web tambien admite JPEG puro del anfitrion v2.1.
"""
from __future__ import annotations

import ctypes
import io
import json
import socket
import struct
import sys
import threading
import time
from typing import Any, Callable

FRAME_MAGIC = b"FJ22"
FRAME_HEADER = struct.Struct("!4sIQHH")
MAX_JPEG_BYTES = 180_000
MAX_SEND_AGE_MS = 450
FPS_CHOICES = (1, 2, 5, 10, 15, 20)
SIZE_CHOICES = ((320, 180), (480, 270), (640, 360))


class FrameHub:
    """Memoria constante: un fotograma global, cero colas por espectador."""

    def __init__(self, max_viewers: int = 120):
        self.cv = threading.Condition()
        self.seq = 0
        self.packet: bytes | None = None
        self.captured_ms = 0
        self.active = False
        self.meta: dict[str, Any] = {}
        self.viewers = 0
        self.max_viewers = max_viewers

    def set_active(self, active: bool, **meta: Any) -> None:
        with self.cv:
            self.active = bool(active)
            self.meta = meta if active else {}
            self.packet = None
            self.captured_ms = 0
            self.seq += 1
            self.cv.notify_all()

    def publish(self, jpeg: bytes, captured_ms: int | None = None,
                processing_ms: int = 0) -> bool:
        if not isinstance(jpeg, bytes) or not 0 < len(jpeg) <= MAX_JPEG_BYTES:
            raise ValueError("Fotograma JPEG fuera del limite de 180 KB")
        stamp = int(time.time() * 1000) if captured_ms is None else int(captured_ms)
        if stamp <= 0:
            raise ValueError("Marca de captura invalida")
        with self.cv:
            if not self.active:
                return False
            self.seq += 1
            fps = max(1, min(60, int(self.meta.get("fps", 10))))
            header = FRAME_HEADER.pack(
                FRAME_MAGIC, self.seq & 0xFFFFFFFF, stamp,
                max(0, min(65535, int(processing_ms))), fps)
            self.packet = header + jpeg
            self.captured_ms = stamp
            self.cv.notify_all()
        return True

    def spectator(self, websocket: Any, stop: threading.Event) -> None:
        """Solo recibe fotogramas en PUSH. Nunca solicita nombre ni pulsa mando."""
        with self.cv:
            if self.viewers >= self.max_viewers:
                websocket.close(code=1013, reason="Limite de espectadores")
                return
            self.viewers += 1

        # Reducir retraso por Nagle en la conexion local a cloudflared.
        raw_socket = getattr(websocket, "socket", None)
        if raw_socket is not None:
            try:
                raw_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except (OSError, AttributeError):
                pass

        seen = -1
        try:
            while not stop.is_set():
                # websockets procesa CLOSE en su hilo receptor. Si el visor
                # cierra sin que haya imagenes nuevas, no puede quedar
                # ocupado indefinidamente esperando otra captura.
                if getattr(websocket, "close_code", None) is not None:
                    break
                ws_state = getattr(websocket, "state", None)
                if getattr(ws_state, "name", "") in ("CLOSING", "CLOSED"):
                    break
                with self.cv:
                    if seen == self.seq:
                        self.cv.wait(timeout=0.25)
                    if seen == self.seq:
                        continue
                    seen = self.seq
                    packet = self.packet
                    stamp = self.captured_ms
                    active = self.active
                    meta = dict(self.meta)

                if active and packet:
                    # Si una conexion es lenta, nunca enviar un frame que ya
                    # quedo obsoleto mientras el socket estaba ocupado.
                    if int(time.time() * 1000) - stamp > MAX_SEND_AGE_MS:
                        continue
                    websocket.send(packet)
                else:
                    websocket.send(json.dumps(
                        {"type": "futureo_stream", "active": active, **meta},
                        separators=(",", ":")))
        except Exception:
            pass  # Desconexion de espectador: no afecta a la sala ni al resto.
        finally:
            with self.cv:
                self.viewers -= 1


def list_sources() -> list[tuple[str, str, int]]:
    """Pantallas y ventanas visibles de Windows."""
    import mss
    sources: list[tuple[str, str, int]] = []
    with mss.mss() as grabber:
        for i in range(1, len(grabber.monitors)):
            mon = grabber.monitors[i]
            sources.append((
                f"Pantalla {i} ({mon['width']}x{mon['height']})", "screen", i))
    if sys.platform != "win32":
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
    if kind != "window" or sys.platform != "win32":
        raise RuntimeError("Fuente de captura invalida")
    from ctypes import wintypes
    user32 = ctypes.windll.user32
    if not user32.IsWindow(value) or user32.IsIconic(value) or not user32.IsWindowVisible(value):
        raise RuntimeError("La ventana se cerro, oculto o minimizo")
    rect = wintypes.RECT()
    if not user32.GetClientRect(value, ctypes.byref(rect)):
        raise RuntimeError("No se pudo consultar la ventana")
    point = wintypes.POINT(0, 0)
    if not user32.ClientToScreen(value, ctypes.byref(point)):
        raise RuntimeError("No se pudo ubicar la ventana")
    x, y = point.x, point.y
    w, h = rect.right - rect.left, rect.bottom - rect.top
    mon = grabber.monitors[0]
    left = max(x, mon["left"])
    top = max(y, mon["top"])
    right = min(x + w, mon["left"] + mon["width"])
    bottom = min(y + h, mon["top"] + mon["height"])
    if right - left < 40 or bottom - top < 40:
        raise RuntimeError("La ventana no esta visible en pantalla")
    return {"left": left, "top": top, "width": right - left, "height": bottom - top}


class ScreenBroadcaster:
    """Captura independiente de clientes, con ritmo de frames no acumulativo."""

    def __init__(self, hub: FrameHub, preview: Callable[[bytes], None] | None = None,
                 notice: Callable[[str], None] | None = None,
                 telemetry: Callable[[dict], None] | None = None):
        self.hub = hub
        self.preview = preview
        self.notice = notice or (lambda _: None)
        self.telemetry = telemetry
        self.worker: threading.Thread | None = None
        self.stopping = threading.Event()
        self.lock = threading.RLock()

    @property
    def running(self) -> bool:
        return self.worker is not None and self.worker.is_alive()

    def start(self, kind: str, source_id: int, size: tuple[int, int],
              fps: int = 10, quality: int = 50) -> None:
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
                daemon=True, name="FUTUREO-Stream-v22")
            self.worker.start()

    def stop(self) -> None:
        with self.lock:
            self.stopping.set()
            self.hub.set_active(False)
            worker = self.worker
        if worker and worker is not threading.current_thread():
            worker.join(timeout=3.0)

    def _loop(self, kind: str, source_id: int, size: tuple[int, int],
              fps: int, quality: int, stopping: threading.Event) -> None:
        try:
            import mss
            from PIL import Image
            last_preview = 0.0
            next_due = time.monotonic()
            stats_start = next_due
            stats_frames = 0
            stats_cost_ms = 0.0
            stats_bytes = 0
            # Controlar el ritmo, no acumular tareas aunque el equipo vaya lento.
            interval = 1.0 / fps
            with mss.mss() as grabber:
                while not stopping.is_set():
                    started = time.monotonic()
                    capture_stamp = int(time.time() * 1000)
                    rect = capture_rectangle(grabber, kind, source_id)
                    shot = grabber.grab(rect)
                    # BGRA -> RGB nativo de Pillow, evita conversion rgb de mss.
                    image = Image.frombytes(
                        "RGB", shot.size, shot.bgra, "raw", "BGRX")
                    image.thumbnail(size, Image.Resampling.BILINEAR)

                    data = b""
                    for q in (quality, max(30, quality - 12), 25):
                        out = io.BytesIO()
                        image.save(out, format="JPEG", quality=q, optimize=False)
                        data = out.getvalue()
                        if len(data) <= MAX_JPEG_BYTES:
                            break
                    cost_ms = (time.monotonic() - started) * 1000.0
                    if len(data) <= MAX_JPEG_BYTES and not stopping.is_set():
                        self.hub.publish(
                            data, captured_ms=capture_stamp,
                            processing_ms=int(cost_ms))
                        stats_frames += 1
                        stats_cost_ms += cost_ms
                        stats_bytes += len(data)
                        if self.preview and started - last_preview >= 1:
                            self.preview(data)
                            last_preview = started

                    now = time.monotonic()
                    if self.telemetry and now - stats_start >= 1:
                        elapsed = max(0.001, now - stats_start)
                        self.telemetry({
                            "fps": round(stats_frames / elapsed, 1),
                            "capture_ms": round(stats_cost_ms / max(1, stats_frames), 1),
                            "jpeg_kb": round(stats_bytes / max(1, stats_frames) / 1024, 1),
                            "viewers": self.hub.viewers,
                            "target_fps": fps,
                        })
                        stats_start = now
                        stats_frames = 0
                        stats_cost_ms = 0.0
                        stats_bytes = 0

                    next_due += interval
                    # Si el ciclo se atrasa, saltar directamente a la proxima
                    # captura: NO ejecutar N capturas atrasadas para recuperarse.
                    if next_due < now:
                        next_due = now
                    stopping.wait(max(0, next_due - now))
        except Exception as exc:
            self.notice("Captura detenida: " + str(exc)[:210])
        finally:
            if not stopping.is_set():
                self.hub.set_active(False)
            self.notice("Transmision detenida")


def stream_selftest() -> None:
    """Valida formato, observador anonimo y descarte en sockets lentos."""
    class FakeSocket:
        def __init__(self, delay: float = 0):
            self.messages: list[bytes | str] = []
            self.delay = delay
        def send(self, data: bytes | str) -> None:
            if self.delay:
                time.sleep(self.delay)
            self.messages.append(data)
        def close(self, **_kwargs: Any) -> None:
            pass

    hub = FrameHub()
    stop = threading.Event()
    ws_fast = FakeSocket()
    ws_slow = FakeSocket(delay=0.04)
    workers = [
        threading.Thread(target=hub.spectator, args=(ws, stop), daemon=True)
        for ws in (ws_fast, ws_slow)
    ]
    for worker in workers:
        worker.start()
    hub.set_active(True, fps=15, width=320, height=180)
    for i in range(1, 12):
        jpeg = b"\xff\xd8" + bytes([i]) * 8 + b"\xff\xd9"
        assert hub.publish(jpeg, processing_ms=3)
        time.sleep(0.006)
    time.sleep(0.15)
    stop.set()
    with hub.cv:
        hub.cv.notify_all()
    for worker in workers:
        worker.join(timeout=2)
    assert hub.viewers == 0
    for ws in (ws_fast, ws_slow):
        packets = [msg for msg in ws.messages if isinstance(msg, bytes)]
        assert packets, "El espectador debe recibir datos sin hello"
        seqs = []
        for packet in packets:
            magic, seq, stamp, cost, fps = FRAME_HEADER.unpack(
                packet[:FRAME_HEADER.size])
            assert magic == FRAME_MAGIC
            assert packet[FRAME_HEADER.size:FRAME_HEADER.size + 2] == b"\xff\xd8"
            assert stamp > 0 and cost == 3 and fps == 15
            seqs.append(seq)
        assert seqs == sorted(set(seqs)), "No se debe repetir o retroceder"
        assert seqs[-1] == hub.seq, "Debe recibir el fotograma final"
    assert len(ws_slow.messages) < 12, "Socket lento sin cola por frame"
    assert hub.packet is not None and len(hub.packet) <= MAX_JPEG_BYTES + FRAME_HEADER.size
    print("OK: FUTUREO v2.2 PUSH, cabecera, FPS, espectadores anonimos y descarte de frames")
