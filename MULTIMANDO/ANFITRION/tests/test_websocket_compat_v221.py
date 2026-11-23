"""Prueba real sin hardware: control remoto WebSocket + visor publico /stream."""
import json
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from websockets.sync.client import connect
from MULTIMANDO_FUTUREO_Anfitrion_v2_2_1 import (
    DummyPads, MultimandoServer, websocket_channel,
)

for raw_path in ("/", "/ws?session=old", "/control?nickname=abc", "/?token=x"):
    assert websocket_channel(raw_path) == "controller"
for raw_path in ("/stream", "/stream/?v=2"):
    assert websocket_channel(raw_path) == "stream"

events = []
host = MultimandoServer(0, DummyPads(2), lambda kind, value: events.append((kind, value)))
host.start()
try:
    # El visor sin nombre/turno tampoco requiere hello: un canal diferente.
    viewer = connect(f"ws://127.0.0.1:{host.port}/stream", open_timeout=4)
    try:
        reply = json.loads(viewer.recv(timeout=4))
        assert reply["type"] == "futureo_stream"
        assert reply["active"] is False
        assert not host.room.players, "Espectador anonimo no ocupa plaza"
    finally:
        viewer.close()

    # MANDO: URLs con rutas o parametros como clientes antiguos.
    for i, route in enumerate(("/ws?game=old", "/control/legacy", "/?room=1"), 1):
        with connect(f"ws://127.0.0.1:{host.port}{route}", open_timeout=4) as ws:
            ws.send(json.dumps({
                "type": "hello", "name": f"Compat{i}", "heartbeat": True
            }))
            # El servidor devuelve welcome sin exigir un nombre de ruta.
            welcome = json.loads(ws.recv(timeout=4))
            assert welcome["type"] == "welcome", welcome
            assert welcome["resume_token"]
            assert welcome["version"] == "2.2.1"
            # La cola y los mandos siguen separados del espectador.
            assert host.room.players
            ws.send("bye")
            time.sleep(0.07)

    assert host.stream_hub.viewers == 0
    print("OK: WebSocket jugadores /, /ws y /control; espectador /stream sin turno")
finally:
    host.stop()
