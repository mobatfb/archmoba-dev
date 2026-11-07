#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - lanzador de escritorio GitHub, con actualizacion en vivo.

* Consulta cada 5 segundos el ultimo commit que modifica desktop.py.
* Descarga versiones por SHA inmutable y solo reinicia si cambia el contenido.
* Si el feed no esta disponible, comprueba el archivo principal como alternativa.
* Guarda el codigo y la configuracion temporal en RAM, nunca en un disco.
* NO usa desktop_offline.py, cachés persistentes ni copias de respaldo.
* Cuando el usuario cierra el escritorio, termina el lanzador.

Dependencias: solamente Python estandar (Linux + servidor X11 para desktop.py).

Uso:
    python3 app.py
    python3 app.py --intervalo 5
    python3 app.py --diagnostico
"""
from __future__ import annotations

import argparse
import hashlib
import queue
import threading
import re
import xml.etree.ElementTree as ET
import os
from pathlib import Path
import shutil
import signal
import site
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

APP_NAME = "PYRION OS"
APP_VERSION = "0.4.7-commit-check"
DESKTOP_NAME = "desktop.py"
REPOSITORY = "mobatfb/archmoba-dev"
DESKTOP_PATH = "PYRIONOS/desktop.py"
RAW_BASE = "https://raw.githubusercontent.com/" + REPOSITORY + "/"
GITHUB_URL = RAW_BASE + "main/" + DESKTOP_PATH
COMMIT_FEED_URL = (
    "https://github.com/" + REPOSITORY + "/commits/main/" + DESKTOP_PATH + ".atom"
)
MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024
MAX_FEED_BYTES = 512 * 1024
HTTP_TIMEOUT = 4.0
DEFAULT_INTERVAL = 5.0
# El feed de GitHub no es una API oficial: comprobacion adicional contra main.
RAW_VERIFY_INTERVAL = 30.0
MEMORY_FILESYSTEMS = {"tmpfs", "ramfs", "rootfs"}
_STOP = False


def _mount_type(path: Path) -> str | None:
    """Solo acepta almacenamiento que /proc/mounts identifique como RAM."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        target = path.resolve(strict=True)
        best = -1
        detected = None
        with open("/proc/mounts", "r", encoding="utf-8", errors="replace") as file:
            for line in file:
                fields = line.split()
                if len(fields) < 3:
                    continue
                decoded = fields[1]
                for encoded, value in (("\\040", " "), ("\\011", "\t"),
                                       ("\\012", "\n"), ("\\134", "\\")):
                    decoded = decoded.replace(encoded, value)
                mountpoint = Path(decoded)
                if target != mountpoint and mountpoint not in target.parents:
                    continue
                if len(mountpoint.parts) > best:
                    best = len(mountpoint.parts)
                    detected = fields[2].lower()
        return detected
    except OSError:
        return None


def _ram_locations() -> list[tuple[Path, int, str]]:
    """No guarda archivos bajo ext4, FAT32, NTFS ni otros discos fisicos."""
    if not sys.platform.startswith("linux"):
        return []
    candidates = (
        Path("/dev/shm"),
        Path("/run/user") / str(os.getuid()),
        Path("/run"),
        Path("/tmp"),
    )
    found = []
    visited = set()
    for location in candidates:
        try:
            location = location.resolve(strict=True)
            if location in visited or not location.is_dir():
                continue
            visited.add(location)
            kind = _mount_type(location)
            if kind not in MEMORY_FILESYSTEMS:
                continue
            if not os.access(location, os.W_OK | os.X_OK):
                continue
            free = shutil.disk_usage(location).free
            if free >= 12 * 1024 * 1024:
                found.append((location, free, kind))
        except OSError:
            pass
    return sorted(found, key=lambda data: data[1], reverse=True)


def _environment(ram_root: Path) -> dict[str, str]:
    """Ubica temporales, HOME y cachés de PYRION en el mismo volumen RAM."""
    env = os.environ.copy()
    home = ram_root / "home"
    folders = {
        "HOME": home,
        "PYRION_TEST_DATA_DIR": ram_root / "pyrionos",
        "PYRIONOS_DATA_DIR": ram_root / "pyrionos",
        "PYRION_RAM_TEST": ram_root,
        "XDG_CACHE_HOME": ram_root / "cache",
        "XDG_CONFIG_HOME": ram_root / "config",
        "XDG_DATA_HOME": ram_root / "data",
        "TMPDIR": ram_root / "tmp",
        "TMP": ram_root / "tmp",
        "TEMP": ram_root / "tmp",
        "PYTHONPYCACHEPREFIX": ram_root / "cache" / "pyc",
    }
    for name, folder in folders.items():
        folder.mkdir(parents=True, exist_ok=True)
        env[name] = str(folder)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    if not env.get("XAUTHORITY"):
        xauth = Path.home() / ".Xauthority"
        if xauth.is_file():
            env["XAUTHORITY"] = str(xauth)
    # Mantener los modulos preinstalados si el sistema los tiene.
    try:
        user_site = site.getusersitepackages()
        if user_site and Path(user_site).is_dir():
            env["PYTHONPATH"] = os.pathsep.join(
                [user_site] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    except (AttributeError, OSError):
        pass
    return env


def _get_bytes(url: str, max_size: int, accept: str) -> bytes:
    """HTTP sin caches persistentes; limite estricto para cada respuesta."""
    request = urllib.request.Request(url, headers={
        "User-Agent": "PYRION-OS/" + APP_VERSION,
        "Accept": accept,
        "Cache-Control": "no-cache, no-store, max-age=0",
        "Pragma": "no-cache",
    })
    with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT) as response:
        payload = response.read(max_size + 1)
    if not payload or len(payload) > max_size:
        raise ValueError("GitHub devolvio una respuesta vacia o demasiado grande")
    return payload


def _latest_desktop_commit() -> str:
    """Lee el ultimo commit de desktop.py desde el feed Atom de GitHub.

    No usa api.github.com: 5 s por consulta agotarian rapidamente la cuota
    anonima de su API REST. El feed es publico pero no oficial.
    """
    url = COMMIT_FEED_URL + "?pyrion_check=" + str(time.time_ns())
    data = _get_bytes(url, MAX_FEED_BYTES, "application/atom+xml, application/xml")
    root = ET.fromstring(data)
    atom = "{http://www.w3.org/2005/Atom}"
    if root.tag != atom + "feed":
        raise ValueError("La respuesta de GitHub no es un feed Atom")
    item = root.find(atom + "entry")
    if item is None:
        raise ValueError("El feed Atom no contiene commits")
    identifier = item.findtext(atom + "id") or ""
    match = re.search(r"/([0-9a-fA-F]{40})$", identifier.strip())
    if match is None:
        # Compatibilidad con un formato alternativo del feed.
        link = item.find(atom + "link")
        href = link.get("href", "") if link is not None else ""
        match = re.search(r"/commit/([0-9a-fA-F]{40})(?:$|[?#])", href)
    if match is None:
        raise ValueError("No fue posible identificar el SHA del ultimo commit")
    return match.group(1).lower()


def _download_desktop(commit: str | None = None) -> bytes:
    """Descarga un commit inmutable; usa main solo para recuperacion."""
    if commit is None:
        # La rama main solo se consulta cuando el feed falla o para verificarlo.
        url = GITHUB_URL + "?pyrion_live=" + str(time.time_ns())
    else:
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("SHA de commit no valido")
        url = RAW_BASE + commit + "/" + DESKTOP_PATH
    payload = _get_bytes(url, MAX_DOWNLOAD_BYTES, "text/plain")
    source = payload.decode("utf-8-sig")
    compile(source, "PYRIONOS/desktop.py", "exec")
    if "class PyrionDesktop" not in source or "def main()" not in source:
        raise ValueError("El archivo descargado no parece ser desktop.py de PYRION")
    return source.encode("utf-8")


def _check_latest(known_commit: str | None,
                  raw_verification: bool = False) -> tuple[str | None, bytes | None, str]:
    """Devuelve SHA, contenido opcional y origen de la comprobacion.

    Si el commit sigue igual, no vuelve a descargar desktop.py. Cada 30 s
    verifica tambien main por si el feed publico esta atrasado o falla.
    """
    try:
        latest = _latest_desktop_commit()
        if latest != known_commit:
            return latest, _download_desktop(latest), "commit"
        if raw_verification:
            return known_commit, _download_desktop(), "raw"
        return known_commit, None, "sin_cambios"
    except (OSError, UnicodeError, ValueError, SyntaxError,
            ET.ParseError, urllib.error.URLError):
        if raw_verification:
            return known_commit, _download_desktop(), "raw_rescate"
        raise


def _save_desktop(target: Path, contents: bytes) -> None:
    """Actualiza el archivo RAM solo tras validar completamente la descarga."""
    temporary = target.with_suffix(".py.tmp")
    try:
        temporary.write_bytes(contents)
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def _launch(target: Path, root: Path, env: dict[str, str]) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-B", str(target)], cwd=str(root), env=env,
    )


def _stop_child(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)
    except (OSError, ProcessLookupError):
        pass


def _handle_stop(_number, _frame):
    global _STOP
    _STOP = True


def _notice(message: str) -> None:
    print("PYRION: " + message, file=sys.stderr, flush=True)
    if os.environ.get("DISPLAY") and shutil.which("xmessage"):
        try:
            subprocess.Popen(["xmessage", "-center", "-title", "PYRION OS",
                              "-buttons", "Cerrar:0", message],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass


def _session(root: Path, interval: float) -> int:
    """Inicia el desktop y consulta el commit cada 5 s sin bloquear la interfaz."""
    environment = _environment(root)
    destination = root / DESKTOP_NAME
    print("%s %s | modo RAM, solo GitHub" % (APP_NAME, APP_VERSION), flush=True)
    print("Buscando ultimo commit de desktop.py...", flush=True)
    commit_sha = None
    try:
        try:
            commit_sha = _latest_desktop_commit()
            source = _download_desktop(commit_sha)
        except (OSError, UnicodeError, ValueError, SyntaxError,
                ET.ParseError, urllib.error.URLError) as exc:
            print("PYRION: feed no disponible; iniciando desde main: " + str(exc),
                  flush=True)
            source = _download_desktop()
            commit_sha = None
        _save_desktop(destination, source)
    except (OSError, UnicodeError, ValueError, SyntaxError,
            ET.ParseError, urllib.error.URLError) as exc:
        _notice("No se pudo iniciar desde GitHub: " + str(exc))
        return 5
    digest = hashlib.sha256(source).hexdigest()
    print("desktop.py iniciado: SHA-256=" + digest[:16], flush=True)
    try:
        child = _launch(destination, root, environment)
    except OSError as exc:
        _notice("No se pudo ejecutar desktop.py: " + str(exc))
        return 6

    # Una sola consulta simultanea, ejecutada en segundo plano.
    results = queue.Queue(maxsize=1)
    pending = False
    failures = 0
    last_notice = 0.0
    last_raw_verification = time.monotonic()
    next_check = time.monotonic() + interval

    def fetch_worker(previous_commit: str | None, verify_raw: bool):
        try:
            result = (True, _check_latest(previous_commit, verify_raw))
        except (OSError, UnicodeError, ValueError, SyntaxError,
                ET.ParseError, urllib.error.URLError) as exc:
            result = (False, str(exc))
        try:
            results.put_nowait(result)
        except queue.Full:
            pass

    try:
        while not _STOP:
            code = child.poll()
            if code is not None:
                print("desktop.py cerrado; codigo=" + str(code), flush=True)
                return code
            now = time.monotonic()
            if not pending and now >= next_check:
                pending = True
                verify_raw = now - last_raw_verification >= RAW_VERIFY_INTERVAL
                if verify_raw:
                    last_raw_verification = now
                next_check = now + interval
                threading.Thread(target=fetch_worker, args=(commit_sha, verify_raw),
                                 daemon=True, name="pyrion-commit-check").start()
            if pending:
                try:
                    ok, data = results.get_nowait()
                except queue.Empty:
                    pass
                else:
                    pending = False
                    if not ok:
                        failures += 1
                        # Retroceso limitado ante fallos para no saturar GitHub.
                        delay = min(60.0, interval * (2 ** min(failures, 4)))
                        next_check = time.monotonic() + delay
                        if time.monotonic() - last_notice > 20:
                            print("PYRION: GitHub temporalmente inaccesible: " + str(data),
                                  file=sys.stderr, flush=True)
                            last_notice = time.monotonic()
                    else:
                        failures = 0
                        new_commit, candidate, origin = data
                        # En un fallback raw la marca del ultimo commit no cambia:
                        # evita volver a un commit anterior si el feed se retrasa.
                        if origin == "commit":
                            commit_sha = new_commit
                        if candidate is not None:
                            candidate_hash = hashlib.sha256(candidate).hexdigest()
                            if candidate_hash != digest and not _STOP and child.poll() is None:
                                print("PYRION: nueva version detectada (%s)." % origin,
                                      flush=True)
                                _save_desktop(destination, candidate)
                                _stop_child(child)
                                if _STOP:
                                    break
                                child = _launch(destination, root, environment)
                                digest = candidate_hash
                                print("PYRION: desktop actualizado, SHA-256=" +
                                      digest[:16], flush=True)
            # Responder a Cerrar aunque la red este lenta.
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        _stop_child(child)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--intervalo", type=float, default=DEFAULT_INTERVAL,
                        help="segundos entre consultas (predeterminado: 5)")
    parser.add_argument("--diagnostico", action="store_true",
                        help="mostrar carpeta RAM y enlace de descarga")
    options = parser.parse_args(argv)
    if not 1.0 <= options.intervalo <= 300.0:
        parser.error("--intervalo debe estar entre 1 y 300 segundos")
    locations = _ram_locations()
    if options.diagnostico:
        print("PYRION %s | GitHub: %s" % (APP_VERSION, GITHUB_URL))
        print("Feed de commits:", COMMIT_FEED_URL)
        print("Intervalo predeterminado: %.0f segundos" % DEFAULT_INTERVAL)
        for directory, free, kind in locations:
            print("RAM: %s (%s, %.1f MiB libres)" %
                  (directory, kind, free / (1024 * 1024)))
        return 0
    if not locations:
        _notice("No hay espacio RAM temporal disponible. No se usaran discos.")
        return 3
    try:
        signal.signal(signal.SIGTERM, _handle_stop)
        signal.signal(signal.SIGINT, _handle_stop)
    except (ValueError, OSError):
        pass
    # Solo una carpeta efimera. Se elimina al cerrar PYRION.
    for location, _free, _kind in locations:
        try:
            with tempfile.TemporaryDirectory(prefix="pyrion-live-", dir=str(location)) as folder:
                return _session(Path(folder), options.intervalo)
        except OSError as exc:
            print("No se pudo crear RAM en %s: %s" % (location, exc),
                  file=sys.stderr, flush=True)
    return 4


if __name__ == "__main__":
    raise SystemExit(main())