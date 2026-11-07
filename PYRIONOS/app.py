#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - lanzador de PRUEBA en memoria RAM.

Inicia el desktop.py que esta junto a este archivo. No busca discos, no monta,
no formatea, no descarga versiones y no instala dependencias. En Linux utiliza
exclusivamente un sistema de archivos en memoria (tmpfs, ramfs o rootfs).
Elimina los datos temporales al cerrar el escritorio.

En Windows, si no hay una unidad RAM configurada, la opcion explicita
--permitir-temporal-disco permite una prueba con carpeta temporal NO-RAM.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import site
import subprocess
import sys
import tempfile

APP_NAME = "PYRION OS - Prueba RAM"
APP_VERSION = "0.4.3-ram-prueba"
DESKTOP_NAME = "desktop.py"
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--diagnostico", action="store_true",
                        help="mostrar el almacenamiento de RAM disponible")
    parser.add_argument("--permitir-temporal-disco", action="store_true",
                        help="permitir carpeta temporal en disco donde no existe tmpfs (NO es RAM)")
    options = parser.parse_args(argv)
    desktop = Path(__file__).resolve().with_name(DESKTOP_NAME)
    ram = _ram_candidates()

    if options.diagnostico:
        print(f"{APP_NAME} {APP_VERSION}")
        print("Escritorio:", desktop)
        print("Existe:", desktop.is_file())
        for path, free, fs in ram:
            print(f"RAM {path}: {fs}, {free // (1024 * 1024)} MiB libres")
        if not ram:
            print("No se ha detectado una ubicacion RAM de escritura.")
        return 0

    if not desktop.is_file():
        print(f"ERROR: falta {DESKTOP_NAME} junto a app.py: {desktop}", file=sys.stderr)
        return 2

    chosen: Path | None = None
    for path, _free, _kind in ram:
        try:
            with tempfile.TemporaryDirectory(prefix="pyrion-test-", dir=str(path)) as folder:
                return _start_desktop(desktop, Path(folder), in_ram=True)
        except (PermissionError, FileNotFoundError) as exc:
            print(f"No se pudo usar {path}: {exc}", file=sys.stderr)
            continue
        except OSError as exc:
            print(f"Fallo al utilizar {path}: {exc}", file=sys.stderr)
            continue

    if not options.permitir_temporal_disco:
        print("ERROR: no se encontro almacenamiento RAM utilizable. Se detuvo para evitar "
              "escribir datos de PYRION en el disco. Usa --diagnostico para comprobar.",
              file=sys.stderr)
        return 3

    print("AVISO: no hay sistema RAM. Esta prueba usara una carpeta temporal en "
          "DISCO y la eliminara al salir.", file=sys.stderr)
    with tempfile.TemporaryDirectory(prefix="pyrion-test-") as folder:
        return _start_desktop(desktop, Path(folder), in_ram=False)


def _start_desktop(desktop: Path, root: Path, *, in_ram: bool) -> int:
    env = _prepare_environment(root)
    print(f"{APP_NAME} {APP_VERSION}", flush=True)
    print("Almacenamiento:", "RAM" if in_ram else "temporal NO-RAM", flush=True)
    print("Ruta de prueba:", env["PYRION_TEST_DATA_DIR"], flush=True)
    print("Sin busqueda de discos, formato ni actualizaciones.", flush=True)
    try:
        # -B evita generar __pycache__ en el directorio del proyecto.
        result = subprocess.run([sys.executable, "-B", str(desktop)],
                                cwd=str(desktop.parent), env=env, check=False)
        return result.returncode
    except FileNotFoundError as exc:
        print(f"ERROR al iniciar PYRION Desktop: {exc}", file=sys.stderr)
        return 4
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
