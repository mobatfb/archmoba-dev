#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - lanzador de escritorio GitHub, con actualizacion en vivo.

* Comprueba el archivo directo en GitHub cada 5 segundos.
* Revisa tambien el feed de commits y descarga por SHA como respaldo.
* Prepara el nuevo escritorio antes de cerrar el anterior (handoff X11).
* Reutiliza las imagenes temporales en RAM para acelerar la recarga.
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
import ast
import hashlib
import queue
import re
import threading
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
import urllib.request

APP_NAME = "PYRION OS"
APP_VERSION = "0.4.9-live-handoff"
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
FEED_INTERVAL = 10.0
DESKTOP_READY_TIMEOUT = 12.0
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
        "PYRION_RAM_ASSETS_DIR": ram_root / "assets",
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
    """Obtiene el ultimo SHA publicado para desktop.py sin consumir la API REST."""
    url = COMMIT_FEED_URL + "?pyrion_check=" + str(time.time_ns())
    root = ET.fromstring(_get_bytes(url, MAX_FEED_BYTES, "application/atom+xml"))
    ns = "{http://www.w3.org/2005/Atom}"
    if root.tag != ns + "feed":
        raise ValueError("El feed de commits no contiene un Atom valido")
    item = root.find(ns + "entry")
    if item is None:
        raise ValueError("El feed de commits esta vacio")
    identifier = (item.findtext(ns + "id") or "").strip()
    match = re.search(r"/([0-9a-fA-F]{40})$", identifier)
    if match is None:
        link = item.find(ns + "link")
        href = link.get("href", "") if link is not None else ""
        match = re.search(r"/commit/([0-9a-fA-F]{40})(?:$|[?#])", href)
    if match is None:
        raise ValueError("No fue posible leer el SHA del commit")
    return match.group(1).lower()


def _download_desktop(commit: str | None = None) -> bytes:
    """Descarga de main (rapida) o de un SHA inmutable (evita CDN obsoleta)."""
    if commit is None:
        url = GITHUB_URL + "?pyrion_live=" + str(time.time_ns())
    else:
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("Commit SHA invalido")
        url = RAW_BASE + commit + "/" + DESKTOP_PATH
    payload = _get_bytes(url, MAX_DOWNLOAD_BYTES, "text/plain")
    source = payload.decode("utf-8-sig")
    compile(source, "PYRIONOS/desktop.py", "exec")
    if "class PyrionDesktop" not in source or "def main()" not in source:
        raise ValueError("El archivo descargado no parece ser desktop.py de PYRION")
    return source.encode("utf-8")


def _version_tuple(source: bytes) -> tuple[int, ...]:
    """Extrae APP_VERSION sin ejecutar el escritorio remoto."""
    try:
        tree = ast.parse(source.decode("utf-8-sig"))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not any(isinstance(t, ast.Name) and t.id == "APP_VERSION"
                       for t in node.targets):
                continue
            if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                match = re.match(r"^(\d+(?:\.\d+)*)", node.value.value)
                if match:
                    return tuple(int(x) for x in match.group(1).split("."))
    except (SyntaxError, UnicodeError, ValueError):
        pass
    return ()


def _probe_desktop(active_digest: str, last_commit: str | None,
                   verify_commit: bool, ignored_hashes: set[str]):
    """Prioriza el archivo directo, y comprueba el SHA si la CDN no cambio."""
    raw_error = None
    try:
        raw = _download_desktop()
    except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
        raw = None
        raw_error = exc
    else:
        raw_digest = hashlib.sha256(raw).hexdigest()
        if raw_digest != active_digest and raw_digest not in ignored_hashes:
            return raw, "main", None

    if verify_commit:
        try:
            new_commit = _latest_desktop_commit()
            if new_commit != last_commit:
                candidate = _download_desktop(new_commit)
                return candidate, "commit", new_commit
        except (OSError, UnicodeError, ValueError, SyntaxError, ET.ParseError) as exc:
            if raw is None:
                raise OSError("GitHub no responde: " + str(exc)) from exc
    if raw is None:
        raise OSError("No se pudo leer desktop.py: " + str(raw_error))
    return None, "sin_cambios", last_commit


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
    """Actualizacion en vivo: no cierra el desktop viejo hasta que el nuevo pinta."""
    environment = _environment(root)
    destination = root / DESKTOP_NAME
    pending_path = root / "desktop_nuevo.py"
    ready_path = root / "desktop_nuevo.ready"
    print("%s %s | solo RAM | comprobacion cada %.1fs" %
          (APP_NAME, APP_VERSION, interval), flush=True)
    try:
        source = _download_desktop()
        _save_desktop(destination, source)
    except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
        _notice("No se pudo iniciar desde GitHub: " + str(exc))
        return 5
    digest = hashlib.sha256(source).hexdigest()
    print("PYRION: desktop inicial %s, SHA-256=%s" %
          (_version_tuple(source), digest[:16]), flush=True)
    try:
        child = _launch(destination, root, environment)
    except OSError as exc:
        _notice("No se pudo ejecutar desktop.py: " + str(exc))
        return 6

    results = queue.Queue(maxsize=1)
    fetching = False
    stage = None
    last_commit = None
    recent_hashes = {digest}
    rejected_hashes = set()
    last_notice = 0.0
    last_feed = float("-inf")
    next_check = time.monotonic() + interval

    def fetch_worker(prior_digest: str, prior_commit: str | None,
                     use_feed: bool, ignored_hashes: set[str]):
        try:
            data = (True, _probe_desktop(prior_digest, prior_commit,
                                         use_feed, ignored_hashes))
        except (OSError, UnicodeError, ValueError, SyntaxError) as exc:
            data = (False, str(exc))
        try:
            results.put_nowait(data)
        except queue.Full:
            pass

    try:
        while not _STOP:
            code = child.poll()
            if code is not None:
                print("PYRION: desktop.py cerrado; codigo=" + str(code), flush=True)
                return code
            now = time.monotonic()
            if stage is not None:
                updated_child, candidate, new_digest, deadline = stage
                if updated_child.poll() is not None:
                    rejected_hashes.add(new_digest)
                    print("PYRION: la actualizacion fallo al iniciar; sigo con la anterior.",
                          file=sys.stderr, flush=True)
                    stage = None
                elif ready_path.is_file():
                    try:
                        ready_pid = ready_path.read_text(encoding="ascii").strip()
                    except OSError:
                        ready_pid = ""
                    if ready_pid == str(updated_child.pid):
                        try:
                            _save_desktop(destination, candidate)
                        except OSError as exc:
                            rejected_hashes.add(new_digest)
                            _stop_child(updated_child)
                            print("PYRION: fallo al confirmar actualizacion: " + str(exc),
                                  file=sys.stderr, flush=True)
                        else:
                            previous = child
                            child = updated_child
                            source = candidate
                            digest = new_digest
                            recent_hashes.add(digest)
                            print("PYRION: escritorio listo, version %s, SHA-256=%s" %
                                  (_version_tuple(source), digest[:16]), flush=True)
                            _stop_child(previous)
                        stage = None
                elif now >= deadline:
                    rejected_hashes.add(new_digest)
                    _stop_child(updated_child)
                    print("PYRION: escritorio nuevo no aviso que estaba listo; "+
                          "se mantiene la version anterior.", file=sys.stderr, flush=True)
                    stage = None
                if stage is None:
                    pending_path.unlink(missing_ok=True)
                    ready_path.unlink(missing_ok=True)

            if not fetching and stage is None and now >= next_check:
                fetching = True
                next_check = now + interval
                use_feed = now - last_feed >= FEED_INTERVAL
                if use_feed:
                    last_feed = now
                ignored = (recent_hashes | rejected_hashes) - {digest}
                threading.Thread(target=fetch_worker,
                                 args=(digest, last_commit, use_feed, ignored),
                                 daemon=True, name="pyrion-update-check").start()
            if fetching:
                try:
                    ok, result = results.get_nowait()
                except queue.Empty:
                    pass
                else:
                    fetching = False
                    if not ok:
                        if now - last_notice > 20:
                            print("PYRION: actualizacion pospuesta: " + str(result),
                                  file=sys.stderr, flush=True)
                            last_notice = now
                    else:
                        candidate, origin, commit_sha = result
                        if commit_sha:
                            last_commit = commit_sha
                        if candidate is not None and stage is None:
                            next_digest = hashlib.sha256(candidate).hexdigest()
                            previous_version = _version_tuple(source)
                            proposed_version = _version_tuple(candidate)
                            if proposed_version and previous_version and proposed_version < previous_version:
                                print("PYRION: se descarta una respuesta antigua de GitHub (%s)." %
                                      origin, flush=True)
                            elif (next_digest not in recent_hashes and
                                  next_digest not in rejected_hashes):
                                print("PYRION: cambio detectado por %s. Preparando escritorio..." %
                                      origin, flush=True)
                                try:
                                    _save_desktop(pending_path, candidate)
                                    ready_path.unlink(missing_ok=True)
                                    pending_env = environment.copy()
                                    pending_env["PYRION_DESKTOP_READY_FILE"] = str(ready_path)
                                    new_child = _launch(pending_path, root, pending_env)
                                except OSError as exc:
                                    rejected_hashes.add(next_digest)
                                    print("PYRION: actualizacion rechazada: " + str(exc),
                                          file=sys.stderr, flush=True)
                                else:
                                    stage = (new_child, candidate, next_digest,
                                             now + DESKTOP_READY_TIMEOUT)
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
    finally:
        if stage is not None:
            _stop_child(stage[0])
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
        print("Actualizacion: main 5s, feed Atom 10s, traspaso X11 tras renderizar")
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
