#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Entrada AMBOT para AMDEV: recupera recursos junto a app.py al abrir desde repositorio.

En modo local usa los archivos visibles del repositorio. Cuando AMDEV instala
solo app.py y config.json, descarga los recursos faltantes del release inmutable.
"""
from __future__ import annotations
import base64
import json
import os
import time
import traceback
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote

APP_VERSION = "0.1.2"
APP_NAME = "AMBOT"
ROOT = Path(__file__).resolve().parent
LAUNCH_LOG = ROOT / "launch.log"
REPO = "mobatfb/archmoba-dev"
MAX_BYTES = 700_000
NECESSARY = ("servidor.py", "cerebro_robot.py", "index.html", "js/motor3d.js", "js/control.js")

def _remote_bytes(path: str, release_commit: str) -> bytes:
    """Download a pinned resource with a raw-GitHub/API fallback."""
    remote = quote("AMBOT/" + path, safe="/")
    raw_url = "https://raw.githubusercontent.com/" + REPO + "/" + release_commit + "/" + remote
    api_url = "https://api.github.com/repos/" + REPO + "/contents/" + remote + "?ref=" + release_commit
    failures = []
    for attempt in range(3):
        for provider, url in (("raw", raw_url), ("api", api_url)):
            try:
                req = Request(url, headers={
                    "User-Agent": "AMBOT/0.1.2 (ARCHMOBA)",
                    "Accept": "application/vnd.github+json" if provider == "api" else "*/*",
                })
                with urlopen(req, timeout=15) as response:
                    data = response.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise ValueError("Archivo remoto demasiado grande")
                if provider == "api":
                    info = json.loads(data.decode("utf-8"))
                    if not isinstance(info, dict) or info.get("encoding") != "base64":
                        raise ValueError("Respuesta de API no compatible")
                    data = base64.b64decode(info["content"], validate=False)
                    if len(data) > MAX_BYTES:
                        raise ValueError("Archivo de API demasiado grande")
                if not data:
                    raise ValueError("Archivo remoto vacio")
                if path.endswith((".py", ".js", ".html")):
                    data.decode("utf-8")
                return data
            except Exception as exc:
                failures.append(f"{provider} intento {attempt+1}: {type(exc).__name__}: {exc}")
        if attempt < 2:
            time.sleep(0.65 * (attempt + 1))
    raise RuntimeError(
        "No se pudo descargar " + path + " del release " + release_commit[:12]
        + ".\n" + "\n".join(failures[-4:])
        + "\nComprueba el acceso a raw.githubusercontent.com y api.github.com."
    )


def ensure_assets():
    """Sincroniza tambien archivos presentes de versiones antiguas en AMDEV."""
    missing = [path for path in NECESSARY if not (ROOT / path).is_file()]
    repo_mode = os.environ.get("AMDEV_MODE") == "repo"
    if not repo_mode and not missing:
        return

    config_path = ROOT / "config.json"
    if not config_path.is_file():
        raise RuntimeError("Falta AMBOT/config.json. Inicia desde AMDEV o clona AMBOT completo.")
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    release_commit = str(config.get("release_commit", "")).strip()
    if not re.fullmatch(r"[0-9a-fA-F]{40}", release_commit):
        raise RuntimeError("AMBOT/config.json no tiene release_commit valido.")

    marker = ROOT / ".ambot_release"
    installed_release = marker.read_text(encoding="utf-8").strip() if marker.is_file() else ""
    if repo_mode and installed_release != release_commit:
        # AMDEV reutiliza la carpeta local; un archivo antiguo puede estar roto.
        needed = list(NECESSARY)
    else:
        needed = missing
    if not needed:
        return

    downloaded = {path: _remote_bytes(path, release_commit) for path in needed}
    for path, data in downloaded.items():
        if path.endswith(".py"):
            compile(data.decode("utf-8"), path, "exec")

    for path, data in downloaded.items():
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(target)
    if repo_mode:
        marker.write_text(release_commit + "\n", encoding="utf-8")
    print("AMBOT: sincronizado con release " + release_commit[:12], flush=True)


def main():
    ensure_assets()
    sys.path.insert(0, str(ROOT))
    from servidor import main as run
    run()

def run_logged():
    try:
        if LAUNCH_LOG.exists():
            LAUNCH_LOG.unlink()
    except OSError:
        pass
    try:
        main()
    except BaseException:
        details = traceback.format_exc()
        try:
            LAUNCH_LOG.write_text(
                "AMBOT v" + APP_VERSION + " - fallo de inicio\n"
                + "Python: " + sys.version + "\n\n" + details,
                encoding="utf-8"
            )
        except OSError:
            pass
        if sys.stderr is not None:
            print(details, file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    run_logged()
