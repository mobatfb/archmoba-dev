#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entrada AMBOT para AMDEV: recupera recursos junto a app.py al abrir desde repositorio.

En modo local usa los archivos visibles del repositorio. Cuando AMDEV instala
solo app.py y config.json, descarga los recursos faltantes del release inmutable.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

APP_VERSION = "0.1.0"
APP_NAME = "AMBOT"
ROOT = Path(__file__).resolve().parent
NECESSARY = ("servidor.py", "cerebro_robot.py", "index.html", "js/motor3d.js", "js/control.js")

def ensure_assets():
    missing = [path for path in NECESSARY if not (ROOT / path).is_file()]
    if not missing:
        return
    config_path = ROOT / "config.json"
    if not config_path.is_file():
        raise RuntimeError("Falta AMBOT/config.json. Inicia desde AMDEV o clona el repositorio completo.")
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    release_commit = str(config.get("release_commit", "")).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", release_commit, re.I):
        raise RuntimeError("AMBOT/config.json no tiene release_commit valido.")
    base = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/" + release_commit + "/AMBOT/"
    downloaded = {}
    for path in missing:
        req = Request(base + quote(path, safe="/"), headers={"User-Agent": "AMBOT/0.1"})
        with urlopen(req, timeout=25) as response:
            data = response.read(500000 + 1)
        if len(data) > 500000:
            raise RuntimeError("Archivo remoto demasiado grande: " + path)
        if not data:
            raise RuntimeError("Recurso remoto vacio: " + path)
        if path.endswith((".py", ".js", ".html")):
            data.decode("utf-8")
        downloaded[path] = data
    for path, data in downloaded.items():
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
    print("AMBOT: recursos sincronizados con release " + release_commit[:9], flush=True)

def main():
    ensure_assets()
    sys.path.insert(0, str(ROOT))
    from servidor import main as run
    run()

if __name__ == "__main__":
    main()
