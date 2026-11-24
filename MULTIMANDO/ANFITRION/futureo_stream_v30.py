# -*- coding: utf-8 -*-
"""FUTUREO STREAM v3.0: FULL, DELTA y SMART, compatibilidad /stream v2.2.

Un unico productor, cero colas de fotogramas por espectador.
Los DELTA se calculan SIEMPRE frente a la imagen RAW del ultimo keyframe;
el navegador redibuja ese keyframe antes de aplicar cada delta. Por tanto,
un espectador puede saltar fotogramas intermedios sin perder sincronizacion.

Versiones del cable:
- Cliente antiguo (no envia FV3): FJ22 + JPEG completo de 20 bytes de cabecera.
- Cliente nuevo (envia FV3): FS30, 32 bytes de cabecera, tipos
  0=FULL (paleta + JPEG), 1=PIXEL_RGB, 2=PIXEL_PALETTE,
  3=REGION_JPEG, 4=BASE_UNCHANGED.
- La paleta (max 256 RGB) se envia SOLO dentro del keyframe FS30 y es
  exacta. Si un color no existe en ella, se usa RGB, REGION o FULL.
- Base_seq identifica el keyframe para cualquier delta independiente.
- Las actualizaciones se envian por el mismo WebSocket /stream.
"""
from __future__ import annotations

from collections import Counter
import io
import json
import socket
import struct
import threading
import time
from typing import Any, Callable

from futureo_stream_v22 import (
    FRAME_HEADER, FRAME_MAGIC, MAX_JPEG_BYTES, MAX_SEND_AGE_MS,
    FPS_CHOICES, SIZE_CHOICES, FrameHub, capture_rectangle, list_sources,
)

MAGIC_V3 = b"FS30"
HEADER_V3 = struct.Struct("!4sBBHHIIQHHH")  # 32 bytes
RECT = struct.Struct("!HHHH")
K_FULL, K_RGB, K_PALETTE, K_REGION, K_HOLD = range(5)
STREAM_MODES = ("full", "delta", "smart")
BASE_INTERVAL = 3.0
TILE = 16
MAX_PIXEL_TILES = 80
MAX_PIXEL_RECORDS = 7000
MAX_V3_PACKET = MAX_JPEG_BYTES + HEADER_V3.size + 2 + 256 * 3


def jpeg_encode(image: Any, quality: int) -> bytes:
    """JPEG con reduccion progresiva si el frame excede el limite v2.2."""
    for q in (quality, max(30, quality - 12), 25):
        stream = io.BytesIO()
        image.save(stream, format="JPEG", quality=q, optimize=False)
        jpeg = stream.getvalue()
        if len(jpeg) <= MAX_JPEG_BYTES:
            return jpeg
    return b""


def keyframe_palette(image: Any) -> tuple[tuple[bytes, ...], dict[bytes, int]]:
    """Seleccionar los 256 colores RGB exactos mas frecuentes de la captura."""
    # getdata es un iterador Pillow: solo se materializan colores distintos.
    colors = Counter(image.getdata()).most_common(256)
    palette = tuple(bytes(rgb) for rgb, _frequency in colors)
    return palette, {rgb: index for index, rgb in enumerate(palette)}


def full_body(jpeg: bytes, palette: tuple[bytes, ...]) -> bytes:
    return struct.pack("!H", len(palette)) + b"".join(palette) + jpeg


def _pixel_records(image: Any, baseline: Any, bbox: tuple,
                   limit: int = MAX_PIXEL_RECORDS) -> list[tuple[int, bytes]] | None:
    """Recorrer solo mosaicos cambiados para no examinar toda la pantalla en Python."""
    from PIL import ImageChops

    left, top, right, bottom = bbox
    width = image.width
    records: list[tuple[int, bytes]] = []
    tiles: list[tuple[int, int, int, int]] = []
    diff = ImageChops.difference(image, baseline)
    for y0 in range(top // TILE * TILE, bottom, TILE):
        for x0 in range(left // TILE * TILE, right, TILE):
            tile = (x0, y0, min(x0 + TILE, image.width), min(y0 + TILE, image.height))
            if diff.crop(tile).getbbox() is None:
                continue
            tiles.append(tile)
            if len(tiles) > MAX_PIXEL_TILES:
                return None
    for x0, y0, x1, y1 in tiles:
        rect = (x0, y0, x1, y1)
        current = image.crop(rect).tobytes()
        old = baseline.crop(rect).tobytes()
        row_pixels = x1 - x0
        for offset in range(0, len(current), 3):
            rgb = current[offset:offset + 3]
            if rgb == old[offset:offset + 3]:
                continue
            cell = offset // 3
            position = (y0 + cell // row_pixels) * width + (x0 + cell % row_pixels)
            records.append((position, rgb))
            if len(records) > limit:
                return None
    return records


def _position(position: int, length: int) -> bytes:
    return position.to_bytes(length, "big")


def encode_delta(image: Any, baseline: Any, palette_map: dict[bytes, int],
                 jpeg: bytes, quality: int, mode: str) -> tuple[int, bytes, int]:
    """Seleccionar paquete diferencial. El caller decide rebase en FULL.

    Devuelve: (tipo, payload, count). FULL retorna body vacio como
    indicador para que el caller construya el nuevo keyframe/paleta.
    """
    from PIL import ImageChops

    bbox = ImageChops.difference(image, baseline).getbbox()
    if bbox is None:
        return K_HOLD, b"", 0

    alternatives: list[tuple[int, bytes, int]] = []
    size_position = 2 if image.width * image.height <= 65535 else 3
    records = _pixel_records(image, baseline, bbox)
    if records is not None:
        rgb = b"".join(_position(pos, size_position) + color
                       for pos, color in records)
        alternatives.append((K_RGB, rgb, len(records)))
        if mode == "smart" and palette_map and all(color in palette_map
                                                     for _, color in records):
            packed = b"".join(
                _position(pos, size_position) + bytes((palette_map[color],))
                for pos, color in records)
            alternatives.append((K_PALETTE, packed, len(records)))

    # Region JPEG: un rectangulo con la envolvente de todos los cambios.
    x0, y0, x1, y1 = bbox
    if x1 > x0 and y1 > y0:
        region = jpeg_encode(image.crop(bbox), quality)
        if region:
            alternatives.append((
                K_REGION, RECT.pack(x0, y0, x1 - x0, y1 - y0) + region, 1))

    if not alternatives:
        return K_FULL, b"", 0

    best = min(alternatives, key=lambda item: len(item[1]))
    # Preferir keyframe si un delta NO ahorra bytes, incluyendo cabeceras.
    full_wire = HEADER_V3.size + 2 + len(jpeg)
    if HEADER_V3.size + len(best[1]) >= full_wire:
        return K_FULL, b"", 0
    return best


class SmartFrameHub(FrameHub):
    """Difusion dual: FJ22 para espectadores antiguos, FS30 para v3."""

    def __init__(self, max_viewers: int = 120):
        super().__init__(max_viewers=max_viewers)
        self.base_packet: bytes | None = None
        self.v3_packet: bytes | None = None
        self.base_seq = 0
        self.v3_kind = K_FULL
        self.last_wire_bytes = 0
        self.last_legacy_bytes = 0

    def set_active(self, active: bool, **meta: Any) -> None:
        with self.cv:
            super().set_active(active, **meta)
            self.base_packet = None
            self.v3_packet = None
            self.base_seq = 0
            self.v3_kind = K_FULL
            self.last_wire_bytes = 0
            self.last_legacy_bytes = 0

    def publish_encoded(self, jpeg: bytes, kind: int, body: bytes,
                        count: int, width: int, height: int, fps: int,
                        captured_ms: int, processing_ms: int) -> bool:
        if not jpeg or len(jpeg) > MAX_JPEG_BYTES:
            return False
        if width <= 0 or height <= 0 or kind not in range(5):
            return False
        stamp = int(captured_ms)
        with self.cv:
            if not self.active:
                return False
            self.seq += 1
            seq = self.seq & 0xffffffff
            if kind == K_FULL:
                self.base_seq = seq
            base_seq = self.base_seq
            h3 = HEADER_V3.pack(
                MAGIC_V3, kind, 0, width, height, seq, base_seq,
                stamp, min(65535, max(0, int(processing_ms))), fps, count)
            v3 = h3 + body
            if len(v3) > MAX_V3_PACKET:
                return False
            h2 = FRAME_HEADER.pack(
                FRAME_MAGIC, seq, stamp,
                min(65535, max(0, int(processing_ms))), fps)
            self.packet = h2 + jpeg
            self.captured_ms = stamp
            self.v3_packet = v3
            self.v3_kind = kind
            self.last_wire_bytes = len(v3)
            self.last_legacy_bytes = len(self.packet)
            if kind == K_FULL:
                self.base_packet = v3
            self.cv.notify_all()
        return True

    def spectator(self, websocket: Any, stop: threading.Event) -> None:
        """Compatibilidad progresiva: un FV3 inicial habilita el nuevo formato."""
        with self.cv:
            if self.viewers >= self.max_viewers:
                websocket.close(code=1013, reason="Limite de espectadores")
                return
            self.viewers += 1

        v3 = False
        try:
            # Los clientes v2.2 no escriben nada; timeout -> JPEG antiguo.
            try:
                hello = websocket.recv(timeout=0.18)
                v3 = isinstance(hello, str) and hello.strip() == "FV3"
            except TimeoutError:
                pass

            raw_socket = getattr(websocket, "socket", None)
            if raw_socket is not None:
                try:
                    raw_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                except (OSError, AttributeError):
                    pass

            seen = -1
            sent_base_seq = 0
            while not stop.is_set():
                if getattr(websocket, "close_code", None) is not None:
                    break
                state = getattr(websocket, "state", None)
                if getattr(state, "name", "") in ("CLOSING", "CLOSED"):
                    break
                with self.cv:
                    if seen == self.seq:
                        self.cv.wait(timeout=0.25)
                    if seen == self.seq:
                        continue
                    seen = self.seq
                    active = self.active
                    stamp = self.captured_ms
                    meta = dict(self.meta)
                    legacy_packet = self.packet
                    current_v3 = self.v3_packet
                    base_packet = self.base_packet
                    base_seq = self.base_seq

                if not active or (not legacy_packet and not current_v3):
                    websocket.send(json.dumps(
                        {"type": "futureo_stream", "active": active, **meta},
                        separators=(",", ":")))
                    sent_base_seq = 0
                    continue
                if v3:
                    if not base_packet:
                        continue
                    if sent_base_seq != base_seq:
                        websocket.send(base_packet)
                        sent_base_seq = base_seq
                    if (current_v3 is not None and current_v3 is not base_packet
                            and int(time.time() * 1000) - stamp <= MAX_SEND_AGE_MS):
                        websocket.send(current_v3)
                elif legacy_packet and int(time.time() * 1000) - stamp <= MAX_SEND_AGE_MS:
                    websocket.send(legacy_packet)
        except Exception:
            pass
        finally:
            with self.cv:
                self.viewers -= 1


class SmartScreenBroadcaster:
    """Captura FULL, DELTA y SMART con referencias verificables por base_seq."""

    def __init__(self, hub: SmartFrameHub, preview: Callable[[bytes], None] | None = None,
                 notice: Callable[[str], None] | None = None,
                 telemetry: Callable[[dict], None] | None = None):
        self.hub = hub
        self.preview = preview
        self.notice = notice or (lambda _: None)
        self.telemetry = telemetry
        self.worker: threading.Thread | None = None
        self.stopping = threading.Event()
        self.lock = threading.RLock()
        self.mode = "full"

    @property
    def running(self) -> bool:
        return self.worker is not None and self.worker.is_alive()

    def start(self, kind: str, source_id: int, size: tuple[int, int],
              fps: int = 10, quality: int = 50, mode: str = "full") -> None:
        if kind not in ("window", "screen") or type(source_id) is not int:
            raise ValueError("Selecciona una ventana o pantalla")
        if fps not in FPS_CHOICES or size not in SIZE_CHOICES or not 25 <= quality <= 85:
            raise ValueError("Parametros de transmision invalidos")
        if mode not in STREAM_MODES:
            raise ValueError("Tecnologia no disponible: " + str(mode))
        with self.lock:
            if self.running:
                raise RuntimeError("Detenga primero la transmision anterior")
            self.mode = mode
            self.stopping = threading.Event()
            self.hub.set_active(
                True, fps=fps, width=size[0], height=size[1], mode=mode, protocol=3)
            self.worker = threading.Thread(
                target=self._loop,
                args=(kind, source_id, size, fps, quality, mode, self.stopping),
                daemon=True, name="FUTUREO-Stream-v30-" + mode)
            self.worker.start()

    def stop(self) -> None:
        with self.lock:
            self.stopping.set()
            self.hub.set_active(False)
            worker = self.worker
        if worker and worker is not threading.current_thread():
            worker.join(timeout=3.0)

    def _loop(self, kind: str, source_id: int, size: tuple[int, int],
              fps: int, quality: int, mode: str,
              stopping: threading.Event) -> None:
        try:
            import mss
            from PIL import Image
            base_image = None
            palette: tuple[bytes, ...] = ()
            palette_map: dict[bytes, int] = {}
            base_time = 0.0
            last_preview = 0.0
            next_due = time.monotonic()
            stats_start = next_due
            frames = 0
            processing_total = 0.0
            wire_total = 0
            legacy_total = 0
            keyframes = 0
            delta_frames = 0
            interval = 1.0 / fps
            with mss.mss() as grabber:
                while not stopping.is_set():
                    started = time.monotonic()
                    stamp = int(time.time() * 1000)
                    rect = capture_rectangle(grabber, kind, source_id)
                    shot = grabber.grab(rect)
                    image = Image.frombytes(
                        "RGB", shot.size, shot.bgra, "raw", "BGRX")
                    image.thumbnail(size, Image.Resampling.BILINEAR)
                    jpeg = jpeg_encode(image, quality)
                    if jpeg and not stopping.is_set():
                        rebase = (
                            mode == "full" or base_image is None
                            or image.size != base_image.size
                            or started - base_time >= BASE_INTERVAL
                        )
                        if rebase:
                            which = K_FULL
                            # En FULL no hacer paletas innecesarias.
                            palette, palette_map = (
                                keyframe_palette(image) if mode != "full" else ((), {}))
                            body = full_body(jpeg, palette)
                            count = len(palette)
                            base_image = image.copy()
                            base_time = started
                        else:
                            which, body, count = encode_delta(
                                image, base_image, palette_map, jpeg, quality, mode)
                            if which == K_FULL:
                                palette, palette_map = keyframe_palette(image)
                                body = full_body(jpeg, palette)
                                count = len(palette)
                                base_image = image.copy()
                                base_time = started

                        elapsed_ms = (time.monotonic() - started) * 1000
                        delivered = self.hub.publish_encoded(
                            jpeg, which, body, count,
                            image.width, image.height, fps, stamp, int(elapsed_ms))
                        if delivered:
                            frames += 1
                            processing_total += elapsed_ms
                            wire_total += self.hub.last_wire_bytes
                            legacy_total += self.hub.last_legacy_bytes
                            if which == K_FULL:
                                keyframes += 1
                            else:
                                delta_frames += 1
                            if self.preview and started - last_preview >= 1:
                                self.preview(jpeg)
                                last_preview = started
                    now = time.monotonic()
                    if self.telemetry and now - stats_start >= 1:
                        seconds = max(0.001, now - stats_start)
                        self.telemetry({
                            "fps": round(frames / seconds, 1),
                            "capture_ms": round(processing_total / max(1, frames), 1),
                            "jpeg_kb": round(legacy_total / max(1, frames) / 1024, 1),
                            "wire_kb": round(wire_total / max(1, frames) / 1024, 2),
                            "saved_pct": round(
                                max(0.0, 100 * (1 - wire_total / max(1, legacy_total))), 1),
                            "full_frames": keyframes, "delta_frames": delta_frames,
                            "mode": mode,
                            "viewers": self.hub.viewers,
                            "target_fps": fps,
                        })
                        stats_start = now
                        frames = 0
                        processing_total = 0.0
                        wire_total = 0
                        legacy_total = 0
                        keyframes = 0
                        delta_frames = 0
                    next_due += interval
                    if next_due < now:
                        next_due = now
                    stopping.wait(max(0, next_due - now))
        except Exception as exc:
            self.notice("Captura detenida: " + str(exc)[:210])
        finally:
            if not stopping.is_set():
                self.hub.set_active(False)
            self.notice("Transmision detenida")


def stream_selftest_v30() -> None:
    """Prueba funcional de formatos y ahorro. Requiere Pillow, no Windows."""
    from PIL import Image
    base = Image.new("RGB", (320, 180), (20, 120, 40))
    palette, colors = keyframe_palette(base)
    assert colors[bytes((20, 120, 40))] == 0
    test = base.copy()
    test.putpixel((25, 40), (20, 120, 40))
    kind, payload, count = encode_delta(
        test, base, colors, b"\xff\xd8" + b"x" * 10000, 40, "smart")
    assert kind == K_HOLD and not payload and count == 0
    test.putpixel((64, 80), (21, 121, 41))
    kind, payload, count = encode_delta(
        test, base, colors, b"\xff\xd8" + b"x" * 10000, 40, "smart")
    assert kind == K_RGB and count == 1
    assert len(payload) == 5, (kind, len(payload))
    # El indice paleta utiliza 3 bytes si el color esta en la paleta compartida.
    base2 = Image.new("RGB", (320, 180), (255, 0, 0))
    base2.putpixel((0, 0), (0, 255, 0))
    p2, cmap = keyframe_palette(base2)
    test2 = base2.copy()
    test2.putpixel((40, 10), (0, 255, 0))
    test2.putpixel((43, 10), (0, 255, 0))
    kind, payload, count = encode_delta(
        test2, base2, cmap, b"\xff\xd8" + b"x" * 10000, 40, "smart")
    assert kind == K_PALETTE and count == 2
    assert len(payload) == 6
    # v3: base_keyframe + delta independiente, aunque se pierdan frames.
    hub = SmartFrameHub()
    hub.set_active(True, fps=15, width=320, height=180, mode="smart")
    stamp = int(time.time() * 1000)
    dummy_jpg = b"\xff\xd8\xff\xd9"
    assert hub.publish_encoded(dummy_jpg, K_FULL, full_body(dummy_jpg, p2),
                               len(p2), 320, 180, 15, stamp, 1)
    first_base = hub.base_seq
    assert hub.publish_encoded(dummy_jpg, K_PALETTE, payload, 2,
                               320, 180, 15, stamp, 1)
    assert hub.base_seq == first_base
    h = HEADER_V3.unpack(hub.v3_packet[:HEADER_V3.size])
    assert h[0] == MAGIC_V3 and h[1] == K_PALETTE
    assert h[6] == first_base and h[10] == 2
    assert hub.packet[:4] == FRAME_MAGIC
    print("OK: FUTUREO v3 FULL/DELTA/SMART, paleta exacta, base + delta sin dependencias")
