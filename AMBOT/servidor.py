#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Servidor HTTP local de AMBOT: navegador + cerebro Python."""
from __future__ import annotations
import argparse
import json
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from cerebro_robot import Cerebro, CuerpoSimulado, Memoria

RAIZ = Path(__file__).resolve().parent
BLOQUEO = threading.Lock()
memoria = Memoria(RAIZ / "data" / "memoria.json")
cerebro = Cerebro(CuerpoSimulado(), memoria)

def estado() -> dict:
    cuerpo = cerebro.cuerpo
    s = cuerpo.percibir()
    accion, razon = cerebro.decidir()
    return {
        "nombre": "AMBOT", "version": "0.1",
        "mapa": list(cuerpo.mapa),
        "robot": {
            "x": cuerpo.x, "y": cuerpo.y,
            "orientacion": cuerpo.orientacion,
            "bateria": round(cuerpo.bateria, 1),
            "pasos": cuerpo.pasos,
            "distancia_cm": s.distancia_frontal_cm,
        },
        "decision": {"accion": accion, "razon": razon},
        "memoria": len(cerebro.memoria.hechos),
    }

class Controlador(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(RAIZ), **kwargs)

    def log_message(self, formato: str, *args):
        print("[AMBOT] " + (formato % args))

    def _json(self, status: int, valor: dict):
        cuerpo = json.dumps(valor, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        ruta = urlparse(self.path).path
        if ruta.startswith(("/data/", "/pruebas/", "/__pycache__/")) or ruta in (
            "/cerebro_robot.py", "/servidor.py", "/app.py", "/config.json"
        ):
            return self._json(403, {"error": "Ruta privada"})
        if ruta == "/api/estado":
            with BLOQUEO:
                resultado = estado()
            return self._json(200, resultado)
        return super().do_GET()

    def do_POST(self):
        ruta = urlparse(self.path).path
        if ruta not in ("/api/comando", "/api/reiniciar"):
            return self._json(404, {"error": "Ruta no encontrada"})
        try:
            tamano = int(self.headers.get("Content-Length", "0"))
            if tamano < 0 or tamano > 4096:
                return self._json(413, {"error": "Solicitud demasiado grande"})
            datos = json.loads(self.rfile.read(tamano)) if tamano else {}
            if not isinstance(datos, dict):
                raise ValueError("Se requiere un objeto JSON")
        except (ValueError, UnicodeDecodeError) as exc:
            return self._json(400, {"error": str(exc)})
        with BLOQUEO:
            if ruta == "/api/reiniciar":
                cerebro.cuerpo = CuerpoSimulado()
                respuesta = "Cuerpo simulado reiniciado. Memoria conservada."
            else:
                comando = datos.get("comando", "")
                if not isinstance(comando, str) or len(comando) > 1000:
                    return self._json(400, {"error": "Comando invalido"})
                respuesta, _ = cerebro.ejecutar(comando)
            resultado = estado()
            resultado["respuesta"] = respuesta
        return self._json(200, resultado)

def main():
    p = argparse.ArgumentParser(description="AMBOT: laboratorio robotico 3D")
    p.add_argument("--puerto", type=int, default=8765)
    p.add_argument("--sin-navegador", action="store_true")
    args = p.parse_args()
    servidor = None
    for puerto in ([args.puerto] if args.puerto != 8765 else list(range(8765, 8776))):
        try:
            servidor = ThreadingHTTPServer(("127.0.0.1", puerto), Controlador)
            break
        except OSError:
            continue
    if servidor is None:
        raise RuntimeError("AMBOT: puertos 8765-8775 ocupados.")
    url = "http://127.0.0.1:" + str(servidor.server_port) + "/"
    print("AMBOT 0.1 | ARCHMOBA ROBOTICS | " + url, flush=True)
    if not args.sin_navegador:
        threading.Timer(.7, lambda: webbrowser.open(url)).start()
    try:
        servidor.serve_forever(poll_interval=.3)
    except KeyboardInterrupt:
        print("AMBOT apagado.")
    finally:
        servidor.server_close()

if __name__ == "__main__":
    main()
