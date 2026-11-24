#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas FUTUREO FULL/DELTA/SMART sin hardware Windows."""
import pathlib
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from futureo_stream_v22 import FRAME_MAGIC
from futureo_stream_v30 import (
    HEADER_V3, MAGIC_V3, K_FULL, K_HOLD, K_RGB, K_PALETTE, K_REGION,
    SmartFrameHub, encode_delta, full_body, jpeg_encode,
    keyframe_palette, stream_selftest_v30,
)

stream_selftest_v30()

# Un video con solo dos pixeles editados se comprime con indices de paleta.
baseline = Image.new("RGB", (320, 180), (240, 20, 20))
baseline.putpixel((0, 0), (0, 250, 0))
palette, mapping = keyframe_palette(baseline)
image = baseline.copy()
image.putpixel((40, 50), (0, 250, 0))
image.putpixel((41, 50), (0, 250, 0))
jpeg = jpeg_encode(image, 40)
kind, data, count = encode_delta(image, baseline, mapping, jpeg, 40, "smart")
assert kind == K_PALETTE and count == 2 and len(data) == 6
assert data == bytes((0x3E, 0xA8, 0x01, 0x3E, 0xA9, 0x01)), data.hex()

# DELTA normal no usa paleta; RGB ocupa 10 bytes en la misma escena.
kind2, data2, count2 = encode_delta(image, baseline, mapping, jpeg, 40, "delta")
assert kind2 == K_RGB and count2 == 2 and len(data2) == 10

# Pixel RGB nuevo fuera de la paleta: no redondear, conservar color original.
image3 = baseline.copy()
image3.putpixel((1, 1), (13, 17, 19))
kind3, data3, count3 = encode_delta(image3, baseline, mapping,
                                    jpeg_encode(image3, 40), 40, "smart")
assert kind3 == K_RGB and count3 == 1
assert data3.endswith(bytes((13, 17, 19)))

# Otra captura igual al fotograma base: se envia HOLD y se borra el delta anterior.
kind4, data4, count4 = encode_delta(
    baseline, baseline, mapping, jpeg_encode(baseline, 40), 40, "smart")
assert kind4 == K_HOLD and data4 == b"" and count4 == 0

# Formato de posiciones de 3 bytes en las resoluciones superiores a 65535 px.
large_base = Image.new("RGB", (480, 270), (4, 5, 6))
large = large_base.copy()
large.putpixel((400, 200), (7, 8, 9))
p_large, m_large = keyframe_palette(large_base)
typ, payload, num = encode_delta(
    large, large_base, m_large, jpeg_encode(large, 50), 50, "smart")
assert typ == K_RGB and num == 1 and len(payload) == 6
assert int.from_bytes(payload[:3], "big") == 200 * 480 + 400

# Pruebas de usuarios nuevos que llegan despues de los deltas y de visores viejos.
hub = SmartFrameHub()
hub.set_active(True, fps=15, mode="smart", width=320, height=180)
stamp = int(time.time() * 1000)
jpg = jpeg_encode(baseline, 40)
assert hub.publish_encoded(jpg, K_FULL, full_body(jpg, palette),
                           len(palette), 320, 180, 15, stamp, 1)
base_seq = hub.base_seq
assert hub.publish_encoded(jpeg, K_PALETTE, data, count,
                           320, 180, 15, stamp, 1)
assert hub.base_seq == base_seq
assert hub.last_wire_bytes < hub.last_legacy_bytes

class Viewer:
    def __init__(self, hello):
        self.hello = hello
        self.sent = []
        self.closed = False
    def recv(self, timeout=None):
        if self.hello is None:
            raise TimeoutError()
        return self.hello
    def send(self, packet):
        self.sent.append(packet)
    def close(self, **kw):
        self.closed = True

def capture_viewer(hello):
    sock = Viewer(hello)
    stop = threading.Event()
    thread = threading.Thread(target=hub.spectator, args=(sock, stop), daemon=True)
    thread.start()
    limit = time.monotonic() + 2
    expected = 2 if hello == "FV3" else 1
    while time.monotonic() < limit and len(sock.sent) < expected:
        time.sleep(0.01)
    stop.set()
    with hub.cv:
        hub.cv.notify_all()
    thread.join(timeout=1)
    assert not thread.is_alive(), "Espectador no libero el hilo"
    assert hub.viewers == 0, hub.viewers
    return [v for v in sock.sent if isinstance(v, bytes)]

v3_packets = capture_viewer("FV3")
assert len(v3_packets) >= 2, [len(p) for p in v3_packets]
h0 = HEADER_V3.unpack(v3_packets[0][:HEADER_V3.size])
h1 = HEADER_V3.unpack(v3_packets[1][:HEADER_V3.size])
assert h0[0] == MAGIC_V3 and h0[1] == K_FULL
assert h1[0] == MAGIC_V3 and h1[1] == K_PALETTE
assert h0[5] == h1[6] == base_seq
# Una actualizacion diferencial es independiente de los fotogramas omitidos.
assert h1[5] > h0[5], "Secuencia monotona"
legacy_packets = capture_viewer(None)
assert legacy_packets and legacy_packets[0].startswith(FRAME_MAGIC)
assert legacy_packets[0][-2:] == b"\xff\xd9"

# Cambio de escena actualiza referencia y el espectador obtiene un nuevo keyframe.
assert hub.publish_encoded(jpg, K_FULL, full_body(jpg, palette),
                           len(palette), 320, 180, 15, stamp, 1)
assert hub.base_seq > base_seq
new_packets = capture_viewer("FV3")
assert len(new_packets) == 1
assert HEADER_V3.unpack(new_packets[0][:HEADER_V3.size])[1] == K_FULL

print("OK: FULL/DELTA/SMART, PALETTE256, RGB no-loss, offsets u24, "
      "visores nuevos, FJ22 antiguo, keyframe y perdidas intermedias")
