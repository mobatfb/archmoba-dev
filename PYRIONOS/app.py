#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - inicio del escritorio remoto desde GitHub, solo RAM.

Descarga PYRIONOS/desktop.py en el RAM filesystem del sistema, comprueba
la sintaxis, lo ejecuta y elimina sus datos cuando termina. Una copia del
escritorio en la ISO permite iniciar sin Internet; se prefiere GitHub.
No busca discos, no los monta y nunca formatea.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
import os
from pathlib import Path
import shutil
import site
import subprocess
import sys
import tempfile

APP_NAME = "PYRION OS - Prueba RAM"
APP_VERSION = "0.4.4-ram-github"
DESKTOP_NAME = "desktop.py"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/PYRIONOS/desktop.py"
GITHUB_API_URL = "https://api.github.com/repos/mobatfb/archmoba-dev/contents/PYRIONOS/desktop.py?ref=main"
DOWNLOAD_LIMIT = 2 * 1024 * 1024
MEMORY_FILESYSTEMS = {"tmpfs", "ramfs", "rootfs"}


def _mount_type(path: Path) -> str | None:
    """Obtener el filesystem real del punto de montaje mas especifico."""
    if not sys.platform.startswith("linux"):
        return None
    try:
        target = path.resolve(strict=True)
        best_len = -1
        kind = None
        with open("/proc/mounts", encoding="utf-8", errors="replace") as handle:
            for row in handle:
                fields = row.split()
                if len(fields) < 3:
                    continue
                escaped = fields[1]
                # /proc/mounts codifica espacios y barras invertidas con octales.
                for encoded, char in (("\\040", " "), ("\\011", "\t"),
                                      ("\\012", "\n"), ("\\134", "\\")):
                    escaped = escaped.replace(encoded, char)
                mountpoint = Path(escaped)
                if target != mountpoint and mountpoint not in target.parents:
                    continue
                if len(mountpoint.parts) > best_len:
                    best_len = len(mountpoint.parts)
                    kind = fields[2].lower()
        return kind
    except OSError:
        return None


def _ram_candidates() -> list[tuple[Path, int, str]]:
    """No acepta discos normales aunque sean rutas dentro de /tmp."""
    if not sys.platform.startswith("linux"):
        return []
    candidates = [Path("/dev/shm"), Path(f"/run/user/{os.getuid()}"),
                  Path("/run"), Path("/tmp")]
    found: list[tuple[Path, int, str]] = []
    visited: set[Path] = set()
    for candidate in candidates:
        try:
            candidate = candidate.resolve(strict=True)
            if candidate in visited or not candidate.is_dir():
                continue
            visited.add(candidate)
            kind = _mount_type(candidate)
            if kind not in MEMORY_FILESYSTEMS:
                continue
            if not os.access(candidate, os.W_OK | os.X_OK):
                continue
            free = shutil.disk_usage(candidate).free
            if free >= 8 * 1024 * 1024:
                found.append((candidate, free, kind))
        except OSError:
            continue
    return sorted(found, key=lambda row: row[1], reverse=True)


def _prepare_environment(root: Path) -> dict[str, str]:
    env = os.environ.copy()
    data = root / "pyrionos"
    home = root / "home"
    folders = {
        "PYRION_TEST_DATA_DIR": data,
        "PYRIONOS_DATA_DIR": data,
        "PYRION_RAM_TEST": root,
        "TMPDIR": root / "tmp",
        "TMP": root / "tmp",
        "TEMP": root / "tmp",
        "XDG_CACHE_HOME": root / "cache",
        "XDG_CONFIG_HOME": root / "config",
        "XDG_DATA_HOME": root / "data",
        "PIP_CACHE_DIR": root / "cache" / "pip",
        "PYTHONPYCACHEPREFIX": root / "cache" / "pyc",
        "MPLCONFIGDIR": root / "config" / "matplotlib",
    }
    for key, path in folders.items():
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    home.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("linux"):
        # Conservar el acceso al servidor X11 aunque HOME apunte a RAM.
        original_home = Path.home()
        if not env.get("XAUTHORITY") and (original_home / ".Xauthority").exists():
            env["XAUTHORITY"] = str(original_home / ".Xauthority")
        try:
            user_site = site.getusersitepackages()
            if isinstance(user_site, str) and Path(user_site).is_dir():
                env["PYTHONPATH"] = os.pathsep.join(
                    [user_site] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        except (AttributeError, OSError):
            pass
        env["HOME"] = str(home)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return env



def _validate_source(raw: bytes, origin: str) -> bytes:
    if not raw or len(raw) > DOWNLOAD_LIMIT:
        raise ValueError('El escritorio supera el limite de 2 MiB o esta vacio: ' + origin)
    source = raw.decode('utf-8-sig')
    compile(source, 'PYRIONOS/desktop.py', 'exec')
    # Restrict accidental downloads of GitHub error pages or other Python scripts.
    if 'class PyrionDesktop' not in source or 'def main()' not in source:
        raise ValueError('El archivo recibido no es PYRIONOS/desktop.py: ' + origin)
    return source.encode('utf-8')


def _fetch_github() -> tuple[bytes, str]:
    errors = []
    for url, via_api in ((GITHUB_RAW_URL, False), (GITHUB_API_URL, True)):
        for attempt in range(2):
            try:
                req = urllib.request.Request(url, headers={
                    'User-Agent': 'PYRIONOS/' + APP_VERSION,
                    'Accept': 'application/vnd.github+json' if via_api else 'text/plain',
                    'Cache-Control': 'no-cache',
                })
                with urllib.request.urlopen(req, timeout=13) as response:
                    raw = response.read(DOWNLOAD_LIMIT * 2 + 1)
                if via_api:
                    data = json.loads(raw.decode('utf-8'))
                    if data.get('encoding') != 'base64':
                        raise ValueError('Respuesta de GitHub sin codigo base64')
                    raw = base64.b64decode(data['content'], validate=False)
                return _validate_source(raw, url), url
            except (OSError, ValueError, KeyError, TypeError, UnicodeError,
                    SyntaxError, json.JSONDecodeError) as exc:
                errors.append(type(exc).__name__ + ': ' + str(exc))
                if attempt == 0:
                    time.sleep(1)
    raise RuntimeError('No se pudo descargar desktop.py desde GitHub. ' + ' | '.join(errors)[-800:])


def _offline_copy() -> tuple[bytes, str] | None:
    script_dir = Path(__file__).resolve().parent
    for candidate in (script_dir / 'desktop_offline.py',
                      script_dir / 'desktop.py',
                      Path('/opt/pyrionos/desktop_offline.py')):
        try:
            if candidate.is_file():
                return _validate_source(candidate.read_bytes(), str(candidate)), str(candidate)
        except (OSError, ValueError, UnicodeError, SyntaxError) as exc:
            print('Copia local no valida:', candidate, exc, file=sys.stderr, flush=True)
    return None


def _notice(title: str, message: str) -> None:
    print('\n' + title + ': ' + message, file=sys.stderr, flush=True)
    if not (os.getenv('DISPLAY') or os.getenv('WAYLAND_DISPLAY')):
        return
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(title, message, parent=root)
        root.destroy()
    except Exception as exc:
        print('Aviso grafico no disponible:', exc, file=sys.stderr, flush=True)


def _start_desktop(root: Path, *, in_ram: bool, offline_allowed: bool) -> int:
    env = _prepare_environment(root)
    desktop = root / DESKTOP_NAME
    print(f'{APP_NAME} {APP_VERSION}', flush=True)
    print('Almacenamiento:', 'RAM' if in_ram else 'temporal NO-RAM', flush=True)
    print('Ruta temporal:', root, flush=True)
    print('Descargando PYRIONOS/desktop.py desde GitHub...', flush=True)
    try:
        source, origin = _fetch_github()
        print('Descarga correcta desde:', origin, flush=True)
    except Exception as exc:
        print('GitHub no disponible:', exc, file=sys.stderr, flush=True)
        local = _offline_copy() if offline_allowed else None
        if local is None:
            _notice('PYRION OS', 'No se pudo descargar desktop.py desde GitHub.\n' + str(exc))
            return 5
        source, origin = local
        print('Iniciando con copia local de respaldo:', origin, flush=True)

    # Make no writes to the mounted ISO or a physical disk.
    temp = root / 'desktop.py.tmp'
    try:
        with temp.open('wb') as handle:
            handle.write(source)
        temp.replace(desktop)
    except OSError as exc:
        _notice('PYRION OS', 'No se pudo guardar desktop.py en RAM: ' + str(exc))
        return 6
    digest = hashlib.sha256(source).hexdigest()
    print('desktop.py: ' + str(len(source)) + ' bytes; SHA-256: ' + digest, flush=True)

    try:
        result = subprocess.run([sys.executable, '-B', str(desktop)],
                                cwd=str(root), env=env, check=False)
    except (OSError, KeyboardInterrupt) as exc:
        _notice('PYRION OS', 'Fallo al iniciar el escritorio: ' + str(exc))
        return 7
    if result.returncode == 2:
        _notice('PYRION OS: falta PySide6',
                'desktop.py se obtuvo desde GitHub, pero el interprete Linux '
                'necesita PySide6-Essentials para mostrar la interfaz. '
                'El lanzador no instala librerias grandes automaticamente en RAM.')
    elif result.returncode != 0:
        _notice('PYRION OS', 'desktop.py termino con codigo ' + str(result.returncode))
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument('--diagnostico', action='store_true',
                        help='mostrar los sistemas de archivos RAM disponibles')
    parser.add_argument('--solo-github', action='store_true',
                        help='no utilizar la copia del escritorio incluida en la ISO')
    parser.add_argument('--permitir-temporal-disco', action='store_true',
                        help='permitir temporal no-RAM en Windows u otros sistemas')
    options = parser.parse_args(argv)
    ram = _ram_candidates()
    if options.diagnostico:
        print(f'{APP_NAME} {APP_VERSION}')
        print('Descarga:', GITHUB_RAW_URL)
        for path, free, fs in ram:
            print(f'RAM {path}: {fs}; {free // (1024 * 1024)} MiB libres')
        if not ram:
            print('No se ha detectado una ubicacion RAM de escritura.')
        return 0

    for path, _free, _kind in ram:
        try:
            with tempfile.TemporaryDirectory(prefix='pyrion-github-', dir=str(path)) as folder:
                return _start_desktop(Path(folder), in_ram=True,
                                      offline_allowed=not options.solo_github)
        except (OSError, PermissionError) as exc:
            print('No se pudo iniciar en ' + str(path) + ': ' + str(exc),
                  file=sys.stderr, flush=True)

    if not options.permitir_temporal_disco:
        _notice('PYRION OS', 'No hay un sistema RAM escribible; no se utilizaran discos. '
                'Ejecuta app.py --diagnostico o amplia la memoria de la VM.')
        return 3

    print('AVISO: usando almacenamiento temporal NO-RAM por solicitud explicita.',
          file=sys.stderr, flush=True)
    with tempfile.TemporaryDirectory(prefix='pyrion-github-') as folder:
        return _start_desktop(Path(folder), in_ram=False,
                              offline_allowed=not options.solo_github)


if __name__ == '__main__':
    raise SystemExit(main())
