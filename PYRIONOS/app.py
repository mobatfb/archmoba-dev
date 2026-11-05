#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS — lanzador y actualizador automatico.

Solo utiliza bibliotecas estandar. Al iniciar consulta el manifiesto de
GitHub, descarga el escritorio verificando SHA-256 y lo ejecuta desde la
carpeta persistente pyrionos. Si no hay Internet, usa la ultima version
validada, conservando versiones anteriores para recuperacion.

No instala paquetes ni modifica el Python global.
"""
from __future__ import annotations

import base64
import queue
import threading
import traceback
import ctypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any

APP_NAME = "PYRION OS"
APP_VERSION = "0.4.1"
DIR_NAME = "pyrionos"
SUBFOLDERS = ("apps", "config", "data", "cache", "logs", "downloads", "envs", "runtime", "system")


class StorageError(RuntimeError):
    """El almacenamiento persistente no esta disponible o es inseguro."""


def write_json_atomic(path: Path, obj: Any) -> None:
    """Guardar un JSON sin reemplazar el archivo previo a medio escribir."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=str(path.parent),
            prefix=".pyrion-", suffix=".tmp", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(obj, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)


def read_json_strict(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise StorageError(f"No se pudo leer {path}: {exc}") from exc


def mounted_volumes() -> list[Path]:
    """Obtiene discos/volumenes montados sin pedir privilegios de administrador."""
    volumes: list[Path] = []
    if os.name == "nt":
        # Win32 GetDriveTypeW: 3 = unidad fija. Evita pendrives y red por defecto.
        import ctypes
        get_drives = ctypes.windll.kernel32.GetLogicalDrives
        get_type = ctypes.windll.kernel32.GetDriveTypeW
        bits = get_drives()
        for index in range(26):
            if (bits >> index) & 1:
                root = Path(chr(65 + index) + ":\\")
                if get_type(str(root)) == 3:
                    volumes.append(root)
    else:
        # psutil es opcional. Si no esta, usamos los montajes de Linux.
        try:
            import psutil
            for part in psutil.disk_partitions(all=False):
                if part.fstype.lower() in {
                    "proc", "sysfs", "devtmpfs", "tmpfs", "squashfs",
                    "cgroup", "cgroup2", "autofs", "devpts", "overlay"
                }:
                    continue
                volumes.append(Path(part.mountpoint))
        except ImportError:
            if sys.platform.startswith("linux") and Path("/proc/mounts").exists():
                ignored = {
                    "proc", "sysfs", "devtmpfs", "tmpfs", "squashfs",
                    "cgroup", "cgroup2", "autofs", "devpts", "overlay"
                }
                for line in Path("/proc/mounts").read_text(errors="replace").splitlines():
                    fields = line.split()
                    if len(fields) >= 3 and fields[2] not in ignored:
                        volumes.append(Path(fields[1].replace("\\040", " ")))
        volumes.append(Path("/"))

    # Siempre incluir el disco donde se encuentra el directorio personal.
    home = Path.home()
    result = [home]
    result.extend(volumes)
    unique: list[Path] = []
    seen = set()
    for path in result:
        try:
            canonical = path.resolve(strict=True)
        except OSError:
            continue
        key = os.path.normcase(str(canonical))
        if key not in seen and canonical.is_dir():
            seen.add(key)
            unique.append(canonical)
    return unique


# PYRION OS - discovery and safe provisioning of Linux persistent disks.
# This block is embedded in app.py and desktop.py so the first boot works
# even before extra modules have been downloaded from GitHub.
STORAGE_MIN_FREE = 700 * 1024 * 1024
STORAGE_MOUNT_BASE = Path('/mnt/pyrion-volumes')
STORAGE_LINUX_FS = {'ext4', 'ext3', 'ext2', 'vfat', 'fat', 'exfat', 'ntfs', 'ntfs3', 'xfs', 'btrfs'}


def _storage_note(message: str) -> None:
    try:
        logpath = Path.home() / '.cache' / 'pyrionos' / 'storage_scan.log'
        logpath.parent.mkdir(parents=True, exist_ok=True)
        with logpath.open('a', encoding='utf-8') as fp:
            fp.write(f'[{datetime.now(timezone.utc).isoformat()}] {message}\n')
    except OSError:
        pass
    out = getattr(sys, 'stderr', None)
    if out:
        try:
            out.write('PYRION STORAGE: ' + message + '\n')
            out.flush()
        except (OSError, ValueError):
            pass
    observer = globals().get('BOOT_OBSERVER')
    if observer is not None:
        try:
            observer.log('Almacenamiento: ' + message)
        except Exception:
            pass


def _linux_mounts() -> list[dict]:
    result = []
    try:
        with open('/proc/mounts', encoding='utf-8', errors='replace') as fp:
            for line in fp:
                fields = line.strip().split()
                if len(fields) >= 4:
                    def decode(part: str) -> str:
                        return (part.replace('\\040', ' ').replace('\\011', '\t')
                                    .replace('\\012', '\n').replace('\\134', '\\'))
                    result.append({'device': decode(fields[0]), 'path': Path(decode(fields[1])),
                                   'fs': fields[2], 'options': fields[3].split(',')})
    except OSError as exc:
        _storage_note('No se pudo leer /proc/mounts: ' + str(exc))
    return result


def _linux_disks() -> list[dict]:
    """Consult /sys instead of relying on lsblk, blkid or udev."""
    result = []
    base = Path('/sys/block')
    if not base.is_dir():
        return result
    try:
        disk_dirs = list(base.iterdir())
    except OSError:
        return result
    for disk in disk_dirs:
        name = disk.name
        if not re.fullmatch(r'(?:sd[a-z]+|hd[a-z]+|vd[a-z]+|xvd[a-z]+|nvme\d+n\d+|mmcblk\d+)', name):
            continue
        def number(path: Path, default: int = 0) -> int:
            try:
                return int(path.read_text().strip())
            except (OSError, ValueError):
                return default
        disk_bytes = number(disk / 'size') * 512
        if disk_bytes < 512 * 1024 * 1024:
            continue
        rotational = number(disk / 'queue' / 'rotational', 1)
        removable = number(disk / 'removable', 0)
        partitions = []
        try:
            parts = list(disk.iterdir())
        except OSError:
            parts = []
        for entry in parts:
            if (entry / 'partition').is_file():
                partitions.append(entry.name)
        result.append({'name': name, 'device': Path('/dev') / name, 'bytes': disk_bytes,
                       'ssd': rotational == 0, 'removable': removable != 0,
                       'partitions': sorted(partitions)})
    return result


def _linux_filesystem_type(device: Path) -> str:
    """Read-only checks; blkid is optional in small live Linux systems."""
    blkid = shutil.which('blkid')
    if blkid:
        try:
            result = subprocess.run([blkid, '-p', '-o', 'value', '-s', 'TYPE', str(device)],
                                    capture_output=True, text=True, timeout=5, check=False)
            if result.returncode == 0 and result.stdout.strip().lower() in STORAGE_LINUX_FS:
                return result.stdout.strip().lower()
        except (OSError, subprocess.TimeoutExpired):
            pass
    try:
        with device.open('rb', buffering=0) as fp:
            head = fp.read(131072)
        if len(head) >= 1082 and head[1080:1082] == b'\x53\xef':
            return 'ext4'
        if head[:4] == b'XFSB':
            return 'xfs'
        if head[65536 + 64:65536 + 72] == b'_BHRfS_M':
            return 'btrfs'
        if head[3:11] == b'NTFS    ':
            return 'ntfs'
        if head[3:11] == b'EXFAT   ':
            return 'exfat'
        if head[54:62] in (b'FAT12   ', b'FAT16   ') or head[82:90] == b'FAT32   ':
            return 'vfat'
    except OSError as exc:
        _storage_note('No se puede inspeccionar ' + str(device) + ': ' + str(exc))
    return ''


def _linux_existing_old_pyrion_ext2(device: Path) -> bool:
    """Read-only identification of the old Mini Linux EXT2 test volume."""
    try:
        with device.open('rb', buffering=0) as handle:
            header = handle.read(2048)
        # ext2/ext3/ext4 magic and superblock name (1024+120).
        return (header[1080:1082] == b'\x53\xef' and
                header[1144:1160].split(b'\0', 1)[0] == b'PYRIONDATA')
    except OSError:
        return False


def _linux_disk_blank(device: Path, size: int) -> bool:
    """Strict safety check: no partitions and all-zero sampled ends."""
    if size < 512 * 1024 * 1024 or size > 64 * 1024 ** 4:
        return False
    try:
        import stat
        if not stat.S_ISBLK(device.stat().st_mode):
            return False
        with device.open('rb', buffering=0) as fp:
            first = fp.read(min(2 * 1024 * 1024, size))
            fp.seek(max(0, size - 2 * 1024 * 1024))
            last = fp.read(min(2 * 1024 * 1024, size))
        return (len(first) >= 512 and len(last) >= 512
                and not any(first) and not any(last))
    except (OSError, ValueError):
        return False


def _linux_confirm_format(device: Path, size: int, filesystem: str = "fat32", existing: bool = False) -> bool:
    """Require a typed confirmation; no destructive action during unattended boot."""
    mib = size // (1024 * 1024)
    expected = 'FORMATEAR ' + str(device)
    _storage_note("Formato solicitado: " + filesystem.upper())
    _storage_note(f'Disco candidato: {device}, {mib} MiB; FAT32; existente={existing}; esperando autorizacion')
    if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
        script = '''import sys
try:
 import tkinter as tk
 from tkinter import simpledialog, messagebox
 root=tk.Tk(); root.withdraw(); root.attributes('-topmost', True)
 device,size,expected,filesystem,existing=sys.argv[1:]
 ok=messagebox.askyesno('PYRION OS - FORMATEO DEL DISCO',
     'Disco candidato: '+device+' ('+size+' MiB).\\n'
     +('ATENCION: ya contiene EXT2 de una prueba anterior.\\n' if existing=='1' else 'Disco detectado sin formato.\\n')
     +'Convertir a '+filesystem.upper()+' BORRARA TODOS LOS DATOS DE ESE DISCO.\\n'
     'No se modificara si cancelas.\\n\\nDeseas continuar?', parent=root)
 if not ok: sys.exit(1)
 answer=simpledialog.askstring('Confirmacion irreversible',
     'Escribe exactamente: '+expected, parent=root)
 sys.exit(0 if answer==expected else 1)
except Exception:
 sys.exit(2)
'''
        try:
            result = subprocess.run([sys.executable, '-c', script, str(device), str(mib), expected, filesystem, '1' if existing else '0'],
                                    timeout=180, check=False,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            if result.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass
    if getattr(sys.stdin, 'isatty', lambda: False)():
        try:
            print(f'ADVERTENCIA: BORRADO IRREVERSIBLE del disco {device} ({mib} MiB), formato {filesystem.upper()}. Disco ya formateado: {existing}')
            return input('Escribe exactamente ' + expected + ': ').strip() == expected
        except (OSError, EOFError, KeyboardInterrupt):
            return False
    return False


class _LinuxStorageFinder:
    """Prioritize existing installations, default to FAT32 for new storage."""

    def __init__(self, is_installation, recorded: dict):
        self.is_installation = is_installation
        self.recorded = recorded if isinstance(recorded, dict) else {}
        self.probe_mounts: list[Path] = []
        self.mount_tool = shutil.which('mount')
        self.umount_tool = shutil.which('umount')

    def _existing_mount(self, device: Path) -> tuple[Path, bool] | None:
        for item in _linux_mounts():
            raw = item['device']
            if raw == str(device):
                return item['path'], 'rw' in item['options']
            if raw.startswith('/dev/'):
                try:
                    if Path(raw).resolve() == device.resolve():
                        return item['path'], 'rw' in item['options']
                except OSError:
                    pass
        return None

    def _run_mount(self, device: Path, directory: Path, fstype: str, rw: bool) -> bool:
        if not self.mount_tool:
            return False
        kinds = ['ext4', 'ext2'] if fstype == 'ext2' else [fstype]
        if fstype == 'ntfs':
            kinds = ['ntfs3', 'ntfs', 'ntfs-3g']
        if fstype in ('fat', 'vfat'):
            kinds = ['vfat']
        for kind in kinds:
            if kind == 'ntfs-3g' and not shutil.which('mount.ntfs-3g'):
                continue
            flags = ('rw,nosuid,nodev,umask=022' if kind == 'vfat' else 'rw,nosuid,nodev') if rw else 'ro,nosuid,nodev'
            try:
                run = subprocess.run([self.mount_tool, '-t', kind, '-o', flags,
                                      str(device), str(directory)],
                                     capture_output=True, text=True, timeout=12, check=False)
            except (OSError, subprocess.TimeoutExpired):
                continue
            if run.returncode != 0:
                _storage_note("Error mount " + kind + " " + str(device) + ": " + ((run.stderr or run.stdout or str(run.returncode)).strip())[-500:])
            if run.returncode == 0 and directory.is_mount():
                _storage_note(f'{device} montado en {directory} ({kind}, {"rw" if rw else "ro"})')
                return True
        return False

    def _unmount_probe(self, mountpoint: Path) -> None:
        if mountpoint not in self.probe_mounts:
            return
        if self.umount_tool:
            try:
                result = subprocess.run([self.umount_tool, str(mountpoint)], timeout=12,
                                        capture_output=True, check=False)
                if result.returncode == 0:
                    self.probe_mounts.remove(mountpoint)
            except (OSError, subprocess.TimeoutExpired):
                pass

    def _candidate_location(self, device: Path, filesystem: str) -> dict | None:
        mounted = self._existing_mount(device)
        if mounted:
            path, rw = mounted
            if not path.is_dir():
                return None
            return {'device': device, 'path': path, 'rw': rw, 'temporary': False, 'fs': filesystem}
        if not self.mount_tool or not self.umount_tool or os.geteuid() != 0:
            _storage_note(f'{device} no esta montado; se necesitan permisos y mount/umount')
            return None
        STORAGE_MOUNT_BASE.mkdir(parents=True, exist_ok=True)
        path = STORAGE_MOUNT_BASE / device.name
        path.mkdir(parents=True, exist_ok=True)
        if not self._run_mount(device, path, filesystem, rw=False):
            _storage_note(f'No se pudo montar {device} ({filesystem}). Falta controlador o utilidad de montaje.')
            return None
        self.probe_mounts.append(path)
        return {'device': device, 'path': path, 'rw': False, 'temporary': True, 'fs': filesystem}

    @staticmethod
    def _installation_at(directory: Path, checker) -> Path | None:
        for candidate in (directory / 'pyrionos', directory / 'PYRIONOS',
                          directory / 'data' / 'pyrionos', directory / 'home' / 'pyrionos'):
            try:
                if checker(candidate):
                    return candidate
            except OSError:
                pass
        return None

    def _make_writable(self, candidate: dict) -> Path:
        mountpoint = candidate['path']
        if candidate['rw']:
            return mountpoint
        if not candidate['temporary']:
            raise StorageError(f'El disco {candidate["device"]} ya esta montado en solo lectura: {mountpoint}')
        self._unmount_probe(mountpoint)
        if mountpoint in self.probe_mounts:
            raise StorageError(f'No se pudo desmontar temporalmente {mountpoint} para escribir')
        if not self._run_mount(candidate['device'], mountpoint, candidate['fs'], rw=True):
            raise StorageError(f'No se pudo montar {candidate["device"]} en lectura/escritura')
        return mountpoint

    def _select_installation(self, installed: list[dict]) -> dict:
        saved = str(self.recorded.get('id') or '')
        if saved:
            matches = []
            for entry in installed:
                try:
                    meta = read_json_strict(entry['folder'] / 'config' / 'instalacion.json', {})
                    if meta.get('id') == saved:
                        matches.append(entry)
                except StorageError:
                    pass
            if matches:
                return matches[0]
            raise StorageError(
                'La instalacion encontrada en el disco tiene un ID diferente al '
                'registrado previamente. No se cambiara a otro usuario o disco '
                'sin seleccionar explicitamente su ubicacion.'
            )
        if len(installed) == 1:
            return installed[0]
        raise StorageError('Hay varias instalaciones PYRION en discos diferentes; selecciona una ubicacion manualmente.')

    def _format_unique_blank(self, item: dict, *, convert_existing: bool = False) -> dict:
        """Make FAT32 on an entire disk only after explicit typed authorization.

        A single unmountable older PYRIONDATA EXT2 disk may be converted, but
        never silently, and only after an additional signature/label check.
        """
        device = item['device']
        if not self.mount_tool or not self.umount_tool or os.geteuid() != 0:
            raise StorageError(f'Faltan mount/umount o permisos para preparar {device}.')
        mkfs = shutil.which('mkdosfs') or shutil.which('mkfs.fat') or shutil.which('mkfs.vfat')
        if not mkfs:
            raise StorageError('Falta mkdosfs o mkfs.fat en Mini Linux. No se modifico el disco.')
        if item['partitions'] or self._existing_mount(device):
            raise StorageError('El disco tiene particiones o esta montado. No se formateara.')
        if convert_existing:
            if not _linux_existing_old_pyrion_ext2(device):
                raise StorageError('El disco no tiene la firma EXT2 PYRIONDATA esperada. Se cancelo el formateo.')
            _storage_note('Disco EXT2 PYRIONDATA anterior encontrado sin poderse montar: conversion FAT32 disponible con confirmacion.')
        elif not _linux_disk_blank(device, item['bytes']):
            raise StorageError('No se puede garantizar que el disco este vacio; no se formateo.')
        if not _linux_confirm_format(device, item['bytes'], 'fat32', existing=convert_existing):
            raise StorageError('Formato FAT32 cancelado por el usuario. Ningun archivo fue borrado por PYRION.')
        fresh = {d['name']: d for d in _linux_disks()}.get(item['name'])
        if not fresh or fresh['partitions'] or fresh['bytes'] != item['bytes'] or self._existing_mount(device):
            raise StorageError('El hardware cambio durante la confirmacion. Formateo cancelado.')
        if convert_existing:
            if not _linux_existing_old_pyrion_ext2(device):
                raise StorageError('La firma del disco cambio. Formateo cancelado.')
        elif not _linux_disk_blank(device, item['bytes']):
            raise StorageError('El disco dejo de estar vacio. Formateo cancelado.')
        _storage_note('Formateando exclusivamente ' + str(device) + ' en FAT32 (BORRADO CONFIRMADO).')
        # BusyBox mkdosfs creates FAT32 and accepts -n LABEL; no partitioning.
        command = [mkfs, '-n', 'PYRIONDATA', str(device)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=240, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise StorageError('No se pudo ejecutar mkdosfs: ' + str(exc)) from exc
        if result.returncode != 0:
            raise StorageError('Falló mkdosfs: ' + ((result.stderr or result.stdout) or '')[-800:])
        if _linux_filesystem_type(device) != 'vfat':
            raise StorageError('mkdosfs termino pero FAT32 no fue reconocido. Revisa el disco.')
        directory = STORAGE_MOUNT_BASE / device.name
        directory.mkdir(parents=True, exist_ok=True)
        if not self._run_mount(device, directory, 'vfat', rw=True):
            raise StorageError('FAT32 creado, pero no se pudo montar. Verifica /var/log/modules-cd.log, /proc/filesystems y dmesg; NO vuelvas a formatear.')
        return {'device': device, 'path': directory, 'rw': True, 'temporary': False, 'fs': 'vfat'}

    def _copy_ram_installation(self, target: Path) -> None:
        """Move an ephemeral live-session installation without deleting the original."""
        sources = []
        raw = self.recorded.get('ruta')
        if isinstance(raw, str) and raw.strip():
            sources.append(Path(raw).expanduser())
        sources.append(Path.home() / 'pyrionos')
        for src in dict.fromkeys(sources):
            if not self.is_installation(src) or src == target:
                continue
            if target.exists() and any(target.iterdir()):
                return
            # No migration from a real existing disk that might not be the
            # user's selected installation. Only migrate the rootfs/tmpfs copy.
            try:
                root_dev = os.stat('/').st_dev
                if os.stat(src).st_dev != root_dev:
                    continue
                bytes_required = sum(p.stat().st_size for p in src.rglob('*') if p.is_file() and not p.is_symlink())
                if shutil.disk_usage(target.parent).free < bytes_required + 40 * 1024 * 1024:
                    raise StorageError('No hay espacio para trasladar la copia anterior de PYRION.')
                _storage_note(f'Copiando instalacion temporal {src} a disco persistente {target}')
                shutil.copytree(src, target, dirs_exist_ok=True, symlinks=False)  # FAT32 no admite enlaces simbolicos
                if not self.is_installation(target):
                    raise StorageError('La copia no fue validada; se conserva la original sin cambios.')
                _storage_note('Instalacion anterior copiada correctamente; original preservado.')
                return
            except StorageError:
                raise
            except OSError as exc:
                raise StorageError(f'No se pudo migrar {src} al disco persistente: {exc}') from exc

    def discover(self) -> Path | None:
        disks = _linux_disks()
        if not disks:
            _storage_note('El kernel no detecta ningun disco fisico con capacidad suficiente.')
            return None
        _storage_note('Discos encontrados: ' + ', '.join(
            f"{d['device']} ({d['bytes'] // (1024 * 1024)} MiB, "
            f"{'SSD' if d['ssd'] else 'HDD'}, {len(d['partitions'])} particiones)" for d in disks
        ))
        installed, available, blank, old_unmounted = [], [], [], []
        try:
            for disk in disks:
                if not disk['partitions'] and _linux_disk_blank(disk['device'], disk['bytes']):
                    blank.append(disk)
                for partition in disk['partitions'] or [disk['name']]:
                    device = Path('/dev') / partition
                    filesystem = _linux_filesystem_type(device)
                    if not filesystem:
                        continue
                    volume = self._candidate_location(device, filesystem)
                    if volume is None:
                        if (not disk['partitions'] and device == disk['device']
                                and _linux_existing_old_pyrion_ext2(device)):
                            old_unmounted.append(disk)
                        continue
                    volume['disk'] = disk
                    folder = self._installation_at(volume['path'], self.is_installation)
                    if folder:
                        volume['folder'] = folder
                        installed.append(volume)
                        continue
                    if filesystem not in STORAGE_LINUX_FS:
                        continue
                    dest = volume['path'] / DIR_NAME
                    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
                        continue
                    free = shutil.disk_usage(volume['path']).free
                    if free < STORAGE_MIN_FREE:
                        _storage_note(f'{device} tiene {free // (1024 * 1024)} MiB; se requieren 700 MiB libres.')
                        continue
                    score = (100 if disk['ssd'] else 0) + (65 if filesystem in ('vfat', 'fat') else 50 if filesystem in ('ext4', 'ext3', 'ext2') else 20 if filesystem == 'exfat' else 10) + min(free // (1024**3), 25)
                    if disk['removable']:
                        score -= 40
                    volume['score'] = score
                    available.append(volume)
            if installed:
                chosen = self._select_installation(installed)
                folder = chosen['folder']
                self._make_writable(chosen)
                _storage_note('Instalacion existente reutilizada: ' + str(folder))
                return folder
            # An offline/stale pointer to a missing durable installation must
            # not be silently replaced by a brand-new empty installation.
            saved = str(self.recorded.get('id') or '')
            prior = self.recorded.get('ruta')
            if saved and isinstance(prior, str) and not self.is_installation(Path(prior)):
                raise StorageError(
                    'Se recordaba una instalacion PYRION anterior que no se encontro '
                    'en ningun disco. Conecta el disco original. No se creara '
                    'una instalacion paralela con datos vacios.'
                )
            if available:
                errors = []
                for chosen in sorted(available, key=lambda v: (v['score'], v['path'].as_posix()), reverse=True):
                    try:
                        self._make_writable(chosen)
                    except StorageError as exc:
                        errors.append(str(exc))
                        _storage_note('Candidato descartado: ' + str(exc))
                        continue
                    folder = chosen['path'] / DIR_NAME
                    if chosen['fs'] in ('vfat', 'fat', 'exfat', 'ntfs', 'ntfs3'):
                        _storage_note('Usando ' + chosen['fs'] + '. Para librerias Qt con '
                                      'enlaces simbolicos y permisos Unix se recomienda ext4.')
                    self._copy_ram_installation(folder)
                    _storage_note('Almacenamiento persistente seleccionado: ' + str(folder))
                    return folder
                raise StorageError('Ningun disco pudo montarse en lectura/escritura: ' + '; '.join(errors[-3:]))
            if len(blank) == 1 and len(disks) == 1:
                item = self._format_unique_blank(blank[0])
                folder = item['path'] / DIR_NAME
                self._copy_ram_installation(folder)
                _storage_note('Disco inicializado para PYRION: ' + str(folder))
                return folder
            if len(disks) == 1 and len(old_unmounted) == 1 and not blank:
                item = self._format_unique_blank(old_unmounted[0], convert_existing=True)
                folder = item['path'] / DIR_NAME
                self._copy_ram_installation(folder)
                return folder
            if blank:
                raise StorageError('Existen varios dispositivos o candidatos dudosos. Discos vacios: ' + ', '.join(str(d['device']) for d in blank)
                                   + '. No se formateara ninguno automaticamente.')
            raise StorageError('Se detectaron discos pero ninguno admite almacenamiento PYRION. '
                               'Comprueba permisos, sistemas de archivos y herramientas mount.')
        finally:
            for mountpoint in list(self.probe_mounts):
                self._unmount_probe(mountpoint)


def _linux_find_storage(checker, pointer: Path) -> Path | None:
    """Search real disks before any rootfs or /root RAM fallback."""
    recorded = read_json_strict(pointer, {})
    if isinstance(recorded, dict) and recorded.get('ruta'):
        try:
            known = Path(recorded['ruta'])
            if checker(known) and os.stat(known).st_dev != os.stat('/').st_dev:
                # Still scan real disks: known device may be a stale mount.
                pass
        except OSError:
            pass
    return _LinuxStorageFinder(checker, recorded).discover()


def _linux_ram_root() -> bool:
    root_mount = next((m for m in _linux_mounts() if m['path'] == Path('/')), None)
    if root_mount is None:
        return True
    return root_mount['fs'].lower() in ('rootfs', 'tmpfs', 'ramfs', 'overlay', 'squashfs')



def _linux_ram_root() -> bool:
    root_mount = next((m for m in _linux_mounts() if m['path'] == Path('/')), None)
    if root_mount is None:
        return True
    return root_mount['fs'].lower() in ('rootfs', 'tmpfs', 'ramfs', 'overlay', 'squashfs')



def _linux_ram_root() -> bool:
    root_mount = next((m for m in _linux_mounts() if m['path'] == Path('/')), None)
    if root_mount is None:
        return True
    return root_mount['fs'].lower() in ('rootfs', 'tmpfs', 'ramfs', 'overlay', 'squashfs')


class PersistentStore:
    """Descubre o crea UN almacenamiento estable y recuerda su ubicacion."""

    def __init__(self, preferred_parent: Path | None = None):
        if os.name == "nt":
            config_base = Path(os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        else:
            config_base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
        # Este archivo contiene solamente una referencia: los datos estan en el disco.
        self.pointer = config_base / "pyrionos" / "ubicacion.json"
        self.root = self._discover(preferred_parent)
        self._prepare()

    @staticmethod
    def _is_installation(path: Path) -> bool:
        if not path.is_dir() or path.is_symlink():
            return False
        marker = path / "config" / "instalacion.json"
        if not marker.is_file():
            return False
        try:
            data = read_json_strict(marker, {})
            return isinstance(data, dict) and data.get("producto") == "pyrionos"
        except StorageError:
            return False

    @staticmethod
    def _is_empty(path: Path) -> bool:
        return path.is_dir() and not any(path.iterdir())

    def _candidate_paths(self) -> list[Path]:
        result: list[Path] = []
        for volume in mounted_volumes():
            result.append(volume / DIR_NAME)
        result.append(Path.home() / DIR_NAME)
        # Duplicados preservando orden.
        return list(dict.fromkeys(result))

    def _discover(self, preferred_parent: Path | None) -> Path:
        # Ruta explicita util para instalar en un disco elegido por el usuario.
        env_dir = os.environ.get("PYRIONOS_DATA_DIR", "").strip()
        if env_dir and preferred_parent is None:
            preferred_parent = Path(env_dir).expanduser()

        if preferred_parent is not None:
            selected = Path(preferred_parent).expanduser().resolve()
            target = selected if selected.name.lower() == DIR_NAME else selected / DIR_NAME
            if target.is_symlink():
                raise StorageError("La ruta seleccionada es un enlace simbolico no permitido.")
            if target.exists() and not (self._is_installation(target) or self._is_empty(target)):
                raise StorageError(f"La carpeta ya contiene datos ajenos a PYRION: {target}")
            return target

        # Real volumes are discovered before the legacy /root fallback.
        # Essential: the live ISO rootfs is RAM and cannot store PySide6.
        if sys.platform.startswith('linux'):
            chosen = _linux_find_storage(self._is_installation, self.pointer)
            if chosen is not None:
                return chosen
            if _linux_ram_root():
                raise StorageError(
                    'PYRION esta ejecutandose desde rootfs/overlay temporal y no '
                    'ha encontrado un disco persistente. No se instalaran paquetes '
                    'en RAM. Diagnostico: ~/.cache/pyrionos/storage_scan.log'
                )

        recorded = read_json_strict(self.pointer, {})
        recorded_path = recorded.get("ruta") if isinstance(recorded, dict) else None
        recorded_id = recorded.get("id") if isinstance(recorded, dict) else None
        if recorded_path:
            target = Path(recorded_path).expanduser()
            if self._is_installation(target):
                if recorded_id:
                    identity = read_json_strict(target / "config" / "instalacion.json", {})
                    if identity.get("id") != recorded_id:
                        raise StorageError("La carpeta encontrada no coincide con la instalacion anterior.")
                return target

        # Escanear todos los discos en cada arranque para encontrar un PYRION existente.
        candidates = self._candidate_paths()
        installations = [p for p in candidates if self._is_installation(p)]
        if recorded_id:
            for p in installations:
                meta = read_json_strict(p / "config" / "instalacion.json", {})
                if meta.get("id") == recorded_id:
                    return p
            raise StorageError(
                "No se encontro el disco que contiene tus datos de PYRION. "
                "Conecta el disco original y vuelve a iniciar, o selecciona "
                "manualmente una ubicacion. No se creara una instalacion vacia."
            )
        if recorded_path:
            raise StorageError(
                "No se encontro la carpeta persistente de PYRION. "
                "No se creara otra para evitar aparentar que se perdieron tus datos."
            )
        if installations:
            # Preferir la del disco personal, si existe.
            return installations[0]

        # Primer arranque: crear en el disco de usuario. En Windows probar la raiz
        # de la unidad fija personal; si no tenemos permisos, usar la carpeta HOME.
        preferred: list[Path] = []
        if os.name == "nt":
            preferred.append(Path(Path.home().anchor) / DIR_NAME)
        preferred.append(Path.home() / DIR_NAME)
        for path in preferred:
            if path.exists() and not self._is_empty(path):
                continue
            try:
                path.mkdir(parents=True, exist_ok=True)
                # Verificar escritura real en lugar de confiar solo en os.access().
                probe = path / (".escritura-" + uuid.uuid4().hex)
                probe.write_text("ok", encoding="utf-8")
                probe.unlink()
                return path
            except OSError:
                continue
        raise StorageError("No se encontro un disco local escribible para crear 'pyrionos'.")

    def _prepare(self) -> None:
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            for name in SUBFOLDERS:
                (self.root / name).mkdir(parents=True, exist_ok=True)
            marker = self.root / "config" / "instalacion.json"
            existing = read_json_strict(marker, {})
            if not existing:
                existing = {
                    "producto": "pyrionos",
                    "id": str(uuid.uuid4()),
                    "creado": datetime.now(timezone.utc).isoformat(),
                    "version_inicial": APP_VERSION,
                }
                write_json_atomic(marker, existing)
            if existing.get("producto") != "pyrionos":
                raise StorageError("La carpeta de datos no pertenece a PYRION.")
            self.installation_id = existing["id"]
            # Archivos vacios de datos: nunca reemplazar si ya existen.
            for filename in ("historial.json", "solicitudes.json"):
                path = self.root / "data" / filename
                if not path.exists():
                    write_json_atomic(path, [])
            if not (self.root / "config" / "preferencias.json").exists():
                write_json_atomic(self.root / "config" / "preferencias.json", {"tema": "oscuro"})
            write_json_atomic(self.pointer, {
                "ruta": str(self.root.resolve()),
                "id": self.installation_id,
            })
        except (OSError, KeyError) as exc:
            raise StorageError(f"No fue posible preparar el almacenamiento: {exc}") from exc

    def load_list(self, name: str) -> list:
        if name not in ("historial", "solicitudes"):
            raise ValueError("Nombre de coleccion no permitido")
        data = read_json_strict(self.root / "data" / f"{name}.json", [])
        if not isinstance(data, list):
            raise StorageError(f"El archivo {name}.json no contiene una lista valida.")
        return data

    def append(self, name: str, entry: dict) -> None:
        events = self.load_list(name)
        events.insert(0, entry)
        # Historial acotado para evitar crecer indefinidamente.
        write_json_atomic(self.root / "data" / f"{name}.json", events[:2000])

    def record(self, title: str, status: str) -> None:
        self.append("historial", {
            "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
            "accion": title,
            "estado": status,
        })

    def check(self) -> tuple[bool, str]:
        try:
            if not self._is_installation(self.root):
                return False, "No se reconoce la instalacion."
            for name in ("historial", "solicitudes"):
                self.load_list(name)
            probe = self.root / "cache" / (".prueba-" + uuid.uuid4().hex)
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            return True, "Carpeta localizada, datos legibles y disco escribible."
        except (OSError, StorageError) as exc:
            return False, str(exc)


REPO = "mobatfb/archmoba-dev"
REMOTE_MANIFEST = f"https://raw.githubusercontent.com/{REPO}/main/PYRIONOS/config.json"
DOWNLOAD_LIMIT = 12 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
VERSION_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:[.\-][A-Za-z0-9.]+)?$")
RELEASE_ID_RE = re.compile(r"^[0-9A-Za-z.\-]+-[0-9a-f]{16}$")


def _safe_console_write(message: str, *, error: bool = False) -> None:
    """Un pythonw.exe de Windows puede carecer de stdout/stderr validos.

    El arranque no debe fallar por intentar registrar un mensaje en una
    consola inexistente. Escribir en el registro persistente es prioritario.
    """
    stream = getattr(sys, "stderr" if error else "stdout", None)
    if stream is None:
        return
    try:
        stream.write(str(message) + "\n")
        stream.flush()
    except (OSError, ValueError, AttributeError):
        # En pythonw.exe suelen ser None; tambien pueden existir pero estar
        # cerrados (OSError EBADF / Errno 9).
        pass


BOOT_OBSERVER = None


class BootObserver:
    """Thread-safe stream of boot events, also usable without a GUI."""

    def __init__(self):
        self.events = queue.Queue()
        self.store = None
        self.output = Path.home() / ".cache" / "pyrionos" / "bootstrap-start.log"
        self._lock = threading.Lock()
        self._write_to_file("Inicio de PYRION OS " + APP_VERSION)
        details = (
            "session: DISPLAY=" + repr(os.environ.get("DISPLAY", ""))
            + "; WAYLAND_DISPLAY=" + repr(os.environ.get("WAYLAND_DISPLAY", ""))
            + "; XDG_SESSION_TYPE=" + repr(os.environ.get("XDG_SESSION_TYPE", ""))
            + "; XDG_RUNTIME_DIR=" + repr(os.environ.get("XDG_RUNTIME_DIR", ""))
            + "; python=" + sys.executable
        )
        self._write_to_file(details)

    def _write_to_file(self, message):
        try:
            with self._lock:
                self.output.parent.mkdir(parents=True, exist_ok=True)
                with self.output.open("a", encoding="utf-8") as fp:
                    fp.write("[" + datetime.now().astimezone().isoformat(timespec="seconds") + "] " + message + "\n")
        except (OSError, ValueError):
            pass

    def log(self, message):
        message = str(message)
        self._write_to_file(message)
        self.events.put(("log", message))

    def stage(self, key, message):
        self._write_to_file(message)
        self.events.put(("stage", key, message))

    def data_folder(self, store):
        self.store = store
        self.events.put(("storage", str(store.root / "logs" / "autoupdate.log")))

    def done(self, success, message):
        self._write_to_file(("OK: " if success else "ERROR: ") + str(message))
        self.events.put(("done", bool(success), str(message)))


def announce(store: PersistentStore | None, message: str) -> None:
    line = f"[{datetime.now().astimezone().isoformat(timespec='seconds')}] PYRION: {message}"
    if store is not None:
        try:
            destination = store.root / "logs" / "autoupdate.log"
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("a", encoding="utf-8") as log:
                log.write(line + "\n")
        except (OSError, ValueError):
            pass
    _safe_console_write(line)
    if BOOT_OBSERVER is not None:
        BOOT_OBSERVER.log(message)


def fail_dialog(message: str) -> None:
    _safe_console_write(message, error=True)
    if os.name == "nt":
        try:
            ctypes.windll.user32.MessageBoxW(None, message, "PYRION OS", 0x10)
        except Exception:
            pass


def fetch_bytes(url: str, limit: int = DOWNLOAD_LIMIT) -> bytes:
    """Descarga acotada: evita cambios del Python global y respuestas gigantes."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "PYRION-OS-bootstrap/1.1",
        "Accept": "application/vnd.github+json" if "api.github.com" in url else "*/*",
        "Cache-Control": "no-cache",
    })
    with urllib.request.urlopen(req, timeout=12) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError("La descarga excede el limite autorizado")
    return body


def fetch_github_api_file(path: str, ref: str, limit: int = DOWNLOAD_LIMIT) -> bytes:
    """Ruta alternativa cuando raw.githubusercontent.com falla o queda bloqueado."""
    safe_parts = [urllib.parse.quote(p, safe="") for p in path.split("/")]
    api_path = "/".join(safe_parts)
    api_url = (
        f"https://api.github.com/repos/{REPO}/contents/{api_path}"
        f"?ref={urllib.parse.quote(ref, safe='')}"
    )
    # El API devuelve Base64 y metadatos, por ello necesita un margen adicional.
    payload = fetch_bytes(api_url, int(limit * 1.5) + 65536)
    response = json.loads(payload.decode("utf-8-sig"))
    if not isinstance(response, dict) or response.get("encoding") != "base64":
        raise ValueError(f"GitHub API no devolvio el archivo {path} codificado en Base64")
    encoded = response.get("content", "")
    if not isinstance(encoded, str):
        raise ValueError(f"Respuesta invalida de GitHub API para {path}")
    data = base64.b64decode(encoded, validate=False)
    if len(data) > limit:
        raise ValueError(f"El archivo {path} excede el limite autorizado")
    return data


def download_manifest() -> dict[str, str]:
    """Consulta Github RAW y, si falla, su API; reporta la causa real."""
    failures = []
    urls = (
        ("GitHub RAW", lambda: fetch_bytes(REMOTE_MANIFEST + f"?check={time.time_ns()}", 32768)),
        ("GitHub API", lambda: fetch_github_api_file("PYRIONOS/config.json", "main", 32768)),
    )
    for channel, getter in urls:
        try:
            return parse_remote_manifest(getter())
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError, RuntimeError) as exc:
            failures.append(f"{channel}: {type(exc).__name__}: {exc}")
    raise RuntimeError("No se pudo consultar config.json. " + " | ".join(failures))


def download_verified_release_file(commit: str, filename: str, checksum: str) -> bytes:
    """Nunca utiliza contenido recibido si no coincide con el SHA-256 publicado."""
    path = f"PYRIONOS/{filename}"
    failures = []
    methods = (
        ("GitHub RAW", lambda: fetch_bytes(f"https://raw.githubusercontent.com/{REPO}/{commit}/{path}")),
        ("GitHub API", lambda: fetch_github_api_file(path, commit)),
    )
    for channel, getter in methods:
        try:
            data = getter()
            if hashlib.sha256(data).hexdigest() != checksum:
                raise ValueError("SHA-256 no coincide con config.json")
            return data
        except (OSError, ValueError, UnicodeError, RuntimeError) as exc:
            failures.append(f"{channel}: {type(exc).__name__}: {exc}")
    raise RuntimeError(f"Fallo al descargar {filename}. " + " | ".join(failures))


def parse_remote_manifest(data: bytes) -> dict[str, str]:
    if len(data) > 32768:
        raise ValueError("Manifiesto remoto demasiado grande")
    item = json.loads(data.decode("utf-8-sig"))
    if not isinstance(item, dict):
        raise ValueError("Formato de manifiesto invalido")
    version = item.get("version", "")
    commit = item.get("release_commit", "")
    desktop_path = item.get("desktop_path", "")
    catalog_path = item.get("catalog_path", "")
    desktop_hash = item.get("desktop_sha256", "")
    catalog_hash = item.get("catalog_sha256", "")
    if not (isinstance(version, str) and VERSION_RE.fullmatch(version)):
        raise ValueError("Version de escritorio invalida")
    if not (isinstance(commit, str) and COMMIT_RE.fullmatch(commit)):
        raise ValueError("Commit de lanzamiento invalido")
    if desktop_path != "PYRIONOS/desktop.py" or catalog_path != "PYRIONOS/guide.csv":
        raise ValueError("El manifiesto contiene rutas no autorizadas")
    if not (isinstance(desktop_hash, str) and SHA256_RE.fullmatch(desktop_hash)):
        raise ValueError("Falta checksum de desktop.py")
    if not (isinstance(catalog_hash, str) and SHA256_RE.fullmatch(catalog_hash)):
        raise ValueError("Falta checksum de guide.csv")
    if item.get("maintenance") is True:
        raise ValueError("La version remota se encuentra en mantenimiento")
    return {
        "version": version,
        "release_commit": commit,
        "desktop_sha256": desktop_hash,
        "catalog_sha256": catalog_hash,
    }


def release_id(manifest: dict[str, str]) -> str:
    return f"{manifest['version']}-{manifest['desktop_sha256'][:16]}"


def hash_ok(file: Path, digest: str) -> bool:
    if not file.is_file() or file.is_symlink():
        return False
    sha = hashlib.sha256()
    try:
        with file.open("rb") as fd:
            for chunk in iter(lambda: fd.read(1024 * 1024), b""):
                sha.update(chunk)
        return sha.hexdigest() == digest
    except OSError:
        return False


def release_info(system_dir: Path, name: str) -> tuple[Path, dict[str, str]] | None:
    """Nunca ejecutar un .py cacheado si el checksum no coincide."""
    if not isinstance(name, str) or not RELEASE_ID_RE.fullmatch(name):
        return None
    directory = system_dir / "releases" / name
    if not directory.is_dir() or directory.is_symlink():
        return None
    meta = directory / "release.json"
    try:
        manifest = parse_remote_manifest(meta.read_bytes())
    except (OSError, UnicodeError, ValueError, KeyError):
        # El release.json guarda tambien las rutas para validar de la misma manera.
        return None
    if release_id(manifest) != name:
        return None
    desktop = directory / "desktop.py"
    guide = directory / "guide.csv"
    if hash_ok(desktop, manifest["desktop_sha256"]) and hash_ok(guide, manifest["catalog_sha256"]):
        return desktop, manifest
    return None


def safe_state(system_dir: Path) -> dict[str, str]:
    state = system_dir / "state.json"
    try:
        data = read_json_strict(state, {})
        if isinstance(data, dict):
            return data
    except StorageError:
        pass
    return {}


def save_state(system_dir: Path, state: dict[str, str]) -> None:
    write_json_atomic(system_dir / "state.json", state)


def cached_release(system_dir: Path, state: dict, field: str) -> tuple[str, Path] | None:
    name = state.get(field)
    info = release_info(system_dir, name)
    if info:
        return name, info[0]
    return None


def find_verified_release(system_dir: Path, skip: str = "") -> tuple[str, Path] | None:
    """Recupera releases intactos aunque state.json haya quedado sin guardar."""
    folder = system_dir / "releases"
    if not folder.is_dir() or folder.is_symlink():
        return None
    valid = []
    for path in folder.iterdir():
        if path.name == skip or not RELEASE_ID_RE.fullmatch(path.name):
            continue
        info = release_info(system_dir, path.name)
        if not info:
            continue
        version = info[1]["version"]
        numbers = tuple(int(x) for x in version.split("-")[0].split(".")[:3])
        valid.append((numbers, path.name, info[0]))
    if not valid:
        return None
    _, name, desktop = max(valid)
    return name, desktop


def install_release(system_dir: Path, manifest: dict[str, str], notify, source_dir: Path | None = None) -> str:
    """Descarga staging + SHA-256 + verificacion de sintaxis antes de publicar."""
    name = release_id(manifest)
    if release_info(system_dir, name):
        notify("Version actual verificada; no necesita descarga.")
        return name
    base = system_dir / "releases"
    base.mkdir(parents=True, exist_ok=True)
    stage = base / (".staging-" + uuid.uuid4().hex)
    stage.mkdir(mode=0o700)
    try:
        commit = manifest["release_commit"]
        for filename, checksum in (
            ("desktop.py", manifest["desktop_sha256"]),
            ("guide.csv", manifest["catalog_sha256"]),
        ):
            if source_dir is not None:
                notify(f"Validando copia local de {filename}...")
                data = (source_dir / filename).read_bytes()
                if hashlib.sha256(data).hexdigest() != checksum:
                    raise ValueError(f"SHA-256 invalido para la copia local de {filename}")
            else:
                notify(f"Descargando {filename}...")
                data = download_verified_release_file(commit, filename, checksum)
            if filename == "desktop.py":
                compile(data.decode("utf-8-sig"), filename, "exec")
            target = stage / filename
            # En Windows os.fsync() requiere un descriptor con permiso de
            # escritura. Abrir en 'rb' devuelve EBADF (Errno 9). Nunca
            # reabrir un archivo en modo lectura para sincronizarlo.
            with target.open("wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
        release_meta = {
            **manifest,
            "desktop_path": "PYRIONOS/desktop.py",
            "catalog_path": "PYRIONOS/guide.csv",
            "maintenance": False,
        }
        write_json_atomic(stage / "release.json", release_meta)
        published = base / name
        if published.exists():
            if published.is_symlink():
                raise ValueError("Carpeta de lanzamiento manipulada")
            if release_info(system_dir, name):
                return name
            # Retener copia corrupta para auditoria, sin ejecutarla.
            published.rename(base / (".invalid-" + uuid.uuid4().hex))
        os.replace(stage, published)
        if not release_info(system_dir, name):
            raise ValueError("La nueva version no supera la validacion posterior")
        notify(f"Escritorio {manifest['version']} guardado en el disco persistente")
        return name
    finally:
        if stage.exists():
            shutil.rmtree(stage, ignore_errors=True)


def seed_local_release(store: PersistentStore, notify) -> str | None:
    """Permite primer arranque offline desde copia completa/clon del repositorio.

    Solo acepta una copia cuando desktop.py y guide.csv coinciden exactamente
    con las huellas SHA-256 indicadas en config.json del mismo directorio.
    """
    candidates = [Path(__file__).resolve().parent]
    from_amdev = os.environ.get("AMDEV_LOCAL_ROOT", "").strip()
    if from_amdev:
        candidates.append(Path(from_amdev).expanduser() / "PYRIONOS")
    for directory in dict.fromkeys(candidates):
        try:
            if not all((directory / p).is_file() for p in ("desktop.py", "guide.csv", "config.json")):
                continue
            manifest = parse_remote_manifest((directory / "config.json").read_bytes())
            if not hash_ok(directory / "desktop.py", manifest["desktop_sha256"]):
                continue
            if not hash_ok(directory / "guide.csv", manifest["catalog_sha256"]):
                continue
            notify("Copia local completa encontrada; preparando primer inicio offline...")
            return install_release(store.root / "system", manifest, notify, source_dir=directory)
        except (OSError, ValueError, UnicodeError, RuntimeError) as exc:
            notify(f"Copia local descartada ({type(exc).__name__}: {exc})")
    return None


def select_release(store: PersistentStore, offline: bool = False) -> tuple[str, Path, dict]:
    """Actualiza si es posible; ante fallo usa la version persistente valida."""
    system_dir = store.root / "system"
    system_dir.mkdir(parents=True, exist_ok=True)
    state = safe_state(system_dir)
    active = cached_release(system_dir, state, "current")
    backup = cached_release(system_dir, state, "previous")
    last_error = "Modo sin conexion: no se consulto el repositorio" if offline else ""
    if not offline:
        try:
            announce(store, "Buscando version actual en el repositorio...")
            manifest = download_manifest()
            name = release_id(manifest)
            if name == state.get("failed_release") and active:
                announce(store, "Actualizacion previamente fallida; manteniendo version estable")
            else:
                installed = install_release(system_dir, manifest, lambda msg: announce(store, msg))
                if not active or active[0] != installed:
                    state = {
                        **state,
                        "previous": active[0] if active else "",
                        "current": installed,
                    }
                    state.pop("failed_release", None)
                    save_state(system_dir, state)
                    active = cached_release(system_dir, state, "current")
                    backup = cached_release(system_dir, state, "previous")
        except (OSError, TimeoutError, ValueError, UnicodeError, json.JSONDecodeError,
                urllib.error.URLError, RuntimeError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            announce(store, f"Actualizacion no disponible ({last_error})")
    if active:
        return active[0], active[1], state
    if backup:
        announce(store, "La version principal no es valida; usando respaldo")
        return backup[0], backup[1], state
    recovered = find_verified_release(system_dir, state.get("failed_release", ""))
    if recovered:
        announce(store, f"Recuperada copia persistente verificada: {recovered[0]}")
        state = {**state, "current": recovered[0]}
        save_state(system_dir, state)
        return recovered[0], recovered[1], state

    # Si alguien inicia desde un checkout local del repositorio, puede comenzar
    # offline sin necesitar un primer download (con los 3 archivos verificados).
    try:
        seeded = seed_local_release(store, lambda msg: announce(store, msg))
        if seeded:
            state = {**state, "current": seeded}
            save_state(system_dir, state)
            active = cached_release(system_dir, state, "current")
            if active:
                return active[0], active[1], state
    except (OSError, ValueError, RuntimeError) as exc:
        announce(store, f"No fue posible importar escritorio local: {exc}")
    reason = (last_error or "No hay datos remotos suficientes")[-900:]
    log_file = store.root / "logs" / "autoupdate.log"
    raise RuntimeError(
        "PYRION no tiene una version valida guardada en el disco. "
        "Tampoco fue posible preparar la descarga.\n\n"
        f"Motivo tecnico: {reason}\n\n"
        f"Registro de diagnostico: {log_file}\n\n"
        "Comprueba el motivo tecnico y el registro indicado. Si el fallo es "
        "de conexion, verifica el acceso HTTPS a GitHub y vuelve a abrir PYRION. "
        "Para el primer inicio sin Internet se requiere una copia local "
        "verificada de desktop.py, guide.csv y config.json."
    )


def _desktop_log_tail(path: Path, lines: int = 12) -> str:
    try:
        data = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(data.splitlines()[-lines:])[-2600:]


def _run_desktop_process(store: PersistentStore, desktop: Path, observer=None,
                         requires_ready: bool = True) -> int:
    """Observe startup, redirect stdout/stderr and wait for the Qt ready marker.

    The updater returns only after Qt reports that its window was shown.
    It does not wait for the desktop window to be closed by the user.
    """
    env = os.environ.copy()
    env["PYRIONOS_DATA_DIR"] = str(store.root)
    marker = store.root / "system" / ("boot-ready-" + uuid.uuid4().hex + ".json")
    env["PYRIONOS_READY_FILE"] = str(marker)
    setup_log = store.root / "logs" / "desktop_setup.log"
    launch_log = store.root / "logs" / "desktop_launch.log"
    launch_log.parent.mkdir(parents=True, exist_ok=True)
    start_size = setup_log.stat().st_size if setup_log.exists() else 0
    announce(store, "Abriendo desktop.py: " + str(desktop))
    if observer is not None:
        observer.stage("qt", "Comprobando librerias Qt y dependencias...")
    try:
        with launch_log.open("a", encoding="utf-8") as output:
            output.write("\n-- Inicio " + datetime.now().isoformat() + " --\n")
            output.flush()
            proc = subprocess.Popen(
                [sys.executable, str(desktop)], cwd=str(desktop.parent),
                env=env, stdout=output, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
            )
    except OSError as exc:
        announce(store, "No se pudo crear proceso de escritorio: " + str(exc))
        return 1

    start = time.monotonic()
    setup_offset = start_size
    last_status = ""
    last_heartbeat = 0
    try:
        while time.monotonic() - start < 1080:
            elapsed = time.monotonic() - start
            if observer is not None and elapsed >= last_heartbeat + 15:
                last_heartbeat = int(elapsed)
                observer.stage("qt", "Esperando la preparacion de Qt: " + str(int(elapsed)) + " s transcurridos")
            # Follow new setup messages while packages install in a subprocess.
            try:
                if setup_log.exists():
                    with setup_log.open("rb") as fp:
                        size = fp.seek(0, os.SEEK_END)
                        if size < setup_offset:
                            setup_offset = 0
                        if size > setup_offset:
                            fp.seek(setup_offset)
                            chunk = fp.read(min(size - setup_offset, 32768))
                            setup_offset = fp.tell()
                            for line in chunk.decode("utf-8", errors="replace").splitlines()[-10:]:
                                if line and line != last_status:
                                    last_status = line
                                    if observer is not None:
                                        observer.stage("qt", line[-210:])
            except OSError:
                pass

            if marker.is_file():
                try:
                    info = json.loads(marker.read_text(encoding="utf-8"))
                    if info.get("ready") is True and info.get("pid") == proc.pid:
                        # Ensure the window survives the initial event loop startup.
                        time.sleep(0.65)
                        if proc.poll() is not None:
                            announce(store, "El escritorio se cerro justo despues de crear la ventana.")
                            return proc.returncode or 1
                        announce(store, "Ventana del escritorio confirmada (pid=" + str(proc.pid) + ")")
                        if observer is not None:
                            observer.stage("desktop", "Escritorio abierto correctamente")
                        return 0
                except (OSError, ValueError, json.JSONDecodeError):
                    pass
            exit_code = proc.poll()
            if exit_code is not None:
                detail = _desktop_log_tail(launch_log)
                announce(store, "El escritorio termino antes de abrir la ventana: codigo " + str(exit_code))
                if detail:
                    announce(store, "Ultimas lineas del proceso:\n" + detail)
                if exit_code == 0:
                    return 1
                return exit_code
            # Compatibility with an older persistent desktop without ready markers.
            if not requires_ready and time.monotonic() - start >= 12:
                announce(store, "Version anterior en ejecucion (no tiene senal de ventana).")
                return 0
            time.sleep(0.20)
        announce(store, "Tiempo de arranque agotado; revisa los registros de Qt.")
        return 21
    finally:
        try:
            marker.unlink(missing_ok=True)
        except OSError:
            pass


def start_desktop(store: PersistentStore, name: str, desktop: Path, state: dict,
                  observer=None) -> int:
    if observer is not None:
        observer.stage("qt", "Verificando pip y PySide6 (primera instalacion puede tardar varios minutos)...")
    code = _run_desktop_process(store, desktop, observer=observer, requires_ready=True)
    if code == 0:
        return 0
    if code == 20:
        announce(store, "Fallo instalando PySide6; la version persistente sigue siendo valida.")
        announce(store, "Registro: " + str(store.root / "logs" / "desktop_setup.log"))
        return code

    system_dir = store.root / "system"
    announce(store, "Error en el arranque (codigo " + str(code) + "); buscando recuperacion")
    previous = cached_release(system_dir, state, "previous")
    if previous and previous[0] != name:
        save_state(system_dir, {
            **state, "current": previous[0], "previous": name, "failed_release": name,
        })
        announce(store, "Restaurando escritorio previo: " + previous[0])
        if observer is not None:
            observer.stage("desktop", "Probando la version anterior del escritorio...")
        return _run_desktop_process(store, previous[1], observer=observer,
                                    requires_ready=False)
    return code or 1


def _run_boot_sequence(args: list[str], observer: BootObserver) -> int:
    global BOOT_OBSERVER
    BOOT_OBSERVER = observer
    offline = "--offline" in args or os.environ.get("PYRIONOS_OFFLINE") == "1"
    try:
        observer.stage("storage", "Buscando el disco y la carpeta persistente...")
        store = PersistentStore()
        observer.data_folder(store)
        observer.log('Disco seleccionado para PYRION: ' + str(store.root))
        announce(store, "Carpeta persistente: " + str(store.root))
        observer.stage("storage", "Almacenamiento verificado: " + str(store.root))
        observer.stage("network", "Modo sin conexion; comprobando copia local..." if offline else "Consultando actualizaciones en GitHub...")
        name, path, state = select_release(store, offline=offline)
        observer.stage("download", "Version verificada: " + name)
        if "--check-only" in args:
            observer.stage("desktop", "Verificacion terminada (sin iniciar escritorio)")
            observer.done(True, "Version lista: " + name)
            return 0
        code = start_desktop(store, name, path, state, observer=observer)
        if code == 0:
            observer.done(True, "Escritorio PYRION abierto")
        else:
            summary = _desktop_log_tail(store.root / "logs" / "desktop_launch.log", 8)
            setup = _desktop_log_tail(store.root / "logs" / "desktop_setup.log", 8)
            msg = (
                "El escritorio no pudo abrirse (codigo " + str(code) + ").\n"
                + ("Proceso:\n" + summary + "\n" if summary else "")
                + ("Dependencias:\n" + setup + "\n" if setup else "")
                + "Registros: " + str(store.root / "logs")
            )
            observer.done(False, msg)
        return code
    except Exception as exc:
        details = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        observer.log("Error inesperado:\n" + details[-3500:])
        observer.done(False, type(exc).__name__ + ": " + str(exc))
        return 1
    finally:
        BOOT_OBSERVER = None


def _run_tk_boot(observer: BootObserver, args: list[str]) -> int | None:
    """Create a verification window with tkinter, before any network or pip.

    None means Tk could not create a window, so another frontend may be used.
    """
    try:
        import tkinter as tk
        from tkinter import ttk
        root = tk.Tk()
    except Exception as exc:
        observer.log("Interfaz Tk no disponible: " + type(exc).__name__ + ": " + str(exc))
        return None

    root.title("PYRION OS | Verificacion de inicio")
    root.geometry("760x585")
    root.minsize(680, 525)
    root.configure(bg="#0B1424")
    try:
        root.attributes("-topmost", True)
        root.after(2000, lambda: root.attributes("-topmost", False))
    except tk.TclError:
        pass
    try:
        w, h = 760, 585
        x = max(0, (root.winfo_screenwidth() - w) // 2)
        y = max(0, (root.winfo_screenheight() - h) // 2)
        root.geometry(f"{w}x{h}+{x}+{y}")
    except tk.TclError:
        pass

    def ui_label(parent, text, font=("DejaVu Sans", 10), fg="#D8E6F5", **kw):
        return tk.Label(parent, text=text, font=font, fg=fg, bg="#0B1424", **kw)

    bar = tk.Frame(root, bg="#102238", height=68)
    bar.pack(fill="x")
    tk.Label(bar, text="◈  PYRION  OS", font=("DejaVu Sans", 18, "bold"),
             bg="#102238", fg="#67D8FF").pack(side="left", padx=21, pady=17)
    tk.Label(bar, text="INICIO INTELIGENTE  |  v" + APP_VERSION,
             font=("DejaVu Sans", 9), bg="#102238", fg="#A0B7CC").pack(side="right", padx=18)
    ui_label(root, "Verificando el entorno de PYRION", ("DejaVu Sans", 16, "bold"),
             fg="#F5FBFF", anchor="w").pack(fill="x", padx=22, pady=(19, 3))
    status = tk.StringVar(value="Preparando comprobaciones...")
    ui_label(root, "", ("DejaVu Sans", 10), fg="#ACBED5", anchor="w", textvariable=status,
             wraplength=700, justify="left").pack(fill="x", padx=23, pady=(0, 10))

    steps = [
        ("session", "Sesion grafica"),
        ("storage", "Datos persistentes"),
        ("network", "Repositorio y actualizaciones"),
        ("download", "Version descargada y verificada"),
        ("qt", "Dependencias Python / PySide6"),
        ("desktop", "Apertura del escritorio"),
    ]
    step_frame = tk.Frame(root, bg="#13253B", highlightbackground="#294966", highlightthickness=1)
    step_frame.pack(fill="x", padx=22, pady=(0, 12))
    step_labels = {}
    for i, (key, caption) in enumerate(steps):
        inner = tk.Frame(step_frame, bg="#13253B")
        inner.pack(fill="x", padx=15, pady=(8 if i == 0 else 3, 8 if i == len(steps)-1 else 3))
        badge = tk.Label(inner, text="○", width=3, anchor="w", font=("DejaVu Sans", 11, "bold"),
                         bg="#13253B", fg="#6685A3")
        badge.pack(side="left")
        caption_lbl = tk.Label(inner, text=caption, anchor="w", font=("DejaVu Sans", 10),
                               bg="#13253B", fg="#B6CEE2")
        caption_lbl.pack(side="left", fill="x")
        step_labels[key] = (badge, caption_lbl)

    style = ttk.Style(root)
    try:
        style.theme_use("clam")
        style.configure("PYRION.Horizontal.TProgressbar", troughcolor="#14273B", background="#42B8EE", thickness=8)
    except tk.TclError:
        pass
    progress = ttk.Progressbar(root, orient="horizontal", mode="indeterminate", style="PYRION.Horizontal.TProgressbar")
    progress.pack(fill="x", padx=23, pady=(0, 12))
    progress.start(16)

    log_frame = tk.Frame(root, bg="#0E1A2B")
    log_frame.pack(fill="both", expand=True, padx=22, pady=(0, 10))
    tk.Label(log_frame, text="DIAGNOSTICO EN TIEMPO REAL", font=("DejaVu Sans", 9, "bold"),
             bg="#0E1A2B", fg="#79B9E2", anchor="w").pack(fill="x", padx=12, pady=(9, 3))
    output = tk.Text(log_frame, height=7, bg="#0E1A2B", fg="#D1E3F3", insertbackground="white",
                     selectbackground="#1F6189", font=("DejaVu Sans Mono", 9),
                     relief="flat", borderwidth=0, wrap="word")
    output.pack(fill="both", expand=True, padx=12, pady=(0, 10))
    output.configure(state="disabled")

    bottom = tk.Frame(root, bg="#0B1424")
    bottom.pack(fill="x", padx=22, pady=(0, 14))
    log_path = tk.StringVar(value="Registro inicial: " + str(observer.output))
    tk.Label(bottom, textvariable=log_path, bg="#0B1424", fg="#819BB8",
             anchor="w", font=("DejaVu Sans", 8), wraplength=520, justify="left").pack(side="left", fill="x", expand=True)
    close_btn = tk.Button(bottom, text="Cerrar", bg="#203C58", fg="#F2FAFF",
                          activebackground="#31577B", relief="flat", padx=15, pady=7, command=root.destroy)
    close_btn.pack(side="right")
    close_btn.configure(state="disabled")

    def copy_report():
        try:
            root.clipboard_clear()
            root.clipboard_append(output.get("1.0", "end-1c") + "\n" + log_path.get())
            root.update_idletasks()
            status.set("Diagnostico copiado al portapapeles.")
        except tk.TclError:
            pass

    copy_btn = tk.Button(bottom, text="Copiar diagnostico", bg="#183754",
                         fg="#BFEAFF", activebackground="#2B5473",
                         relief="flat", padx=12, pady=7, command=copy_report)
    copy_btn.pack(side="right", padx=(0, 9))

    state = {"active": None, "finished": False, "result": 1}

    def append_log(message):
        output.configure(state="normal")
        output.insert("end", str(message) + "\n")
        if int(output.index("end-1c").split(".")[0]) > 250:
            output.delete("1.0", "45.0")
        output.see("end")
        output.configure(state="disabled")

    def mark(key):
        ordered = [x[0] for x in steps]
        if key not in ordered:
            return
        i = ordered.index(key)
        state["active"] = key
        for pos, (k, _) in enumerate(steps):
            badge, caption = step_labels[k]
            if pos < i:
                badge.configure(text="✓", fg="#61CDA6")
                caption.configure(fg="#D6EAF5")
            elif pos == i:
                badge.configure(text="●", fg="#63D1FF")
                caption.configure(fg="#F3FAFF")
            else:
                badge.configure(text="○", fg="#6685A3")
                caption.configure(fg="#9AB2CB")

    def poll_events():
        try:
            while True:
                event = observer.events.get_nowait()
                kind = event[0]
                if kind == "log":
                    append_log(event[1])
                elif kind == "stage":
                    mark(event[1])
                    status.set(str(event[2])[-340:])
                    append_log(event[2])
                elif kind == "storage":
                    log_path.set("Registro persistente: " + event[1])
                elif kind == "done":
                    state["finished"] = True
                    state["result"] = 0 if event[1] else 1
                    progress.stop()
                    close_btn.configure(state="normal")
                    if event[1]:
                        status.set("Verificacion completada. Abriendo escritorio...")
                        for badge, caption in step_labels.values():
                            badge.configure(text="✓", fg="#61CDA6")
                            caption.configure(fg="#D6EAF5")
                        root.after(900, root.destroy)
                    else:
                        status.set("No se pudo iniciar PYRION. Revisa el diagnostico y el registro.")
                        append_log(event[2])
                        if state["active"]:
                            step_labels[state["active"]][0].configure(text="!", fg="#F18F75")
        except queue.Empty:
            pass
        if root.winfo_exists():
            root.after(90, poll_events)

    def start_worker():
        def job():
            _run_boot_sequence(args, observer)
        threading.Thread(target=job, daemon=True, name="PYRION-startup").start()

    observer.stage("session", "Sesion grafica disponible; mostrando verificacion...")
    root.after(100, poll_events)
    root.after(120, start_worker)
    root.mainloop()
    return state["result"]


def _run_zenity_boot(observer: BootObserver, args: list[str]) -> int | None:
    """Fallback for lightweight Linux desktops without python3-tk."""
    if os.name == "nt":
        return None
    command = next((shutil.which(name) for name in ("zenity", "yad") if shutil.which(name)), None)
    if not command:
        return None
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        return None
    try:
        progress = subprocess.Popen(
            [command, "--progress", "--pulsate", "--auto-close", "--no-cancel",
             "--title=PYRION OS - Verificacion de inicio", "--text=Preparando PYRION OS...",
             "--width=600"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, text=True,
        )
    except OSError:
        return None
    if progress.poll() is not None:
        return None

    def send(message):
        try:
            if progress.stdin and progress.poll() is None:
                progress.stdin.write("#" + str(message).replace("\n", " ")[-180:] + "\n")
                progress.stdin.flush()
        except (OSError, ValueError, BrokenPipeError):
            pass

    worker = threading.Thread(target=lambda: _run_boot_sequence(args, observer), daemon=True)
    worker.start()
    result = 1
    while True:
        event = observer.events.get()
        if event[0] in ("log", "stage"):
            send(event[-1])
        elif event[0] == "done":
            result = 0 if event[1] else 1
            send(event[2])
            try:
                if progress.stdin:
                    if event[1]:
                        progress.stdin.write("100\n")
                    progress.stdin.close()
            except (OSError, ValueError):
                pass
            if not event[1]:
                # Without this termination the progress window remains stuck.
                try:
                    progress.terminate()
                    progress.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
                try:
                    subprocess.run([command, "--error", "--title=PYRION OS",
                                    "--text=" + str(event[2])[-1300:]],
                                   timeout=120, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            break
    return result


def install_user_autostart(script_path: Path) -> Path:
    """Install a user-session autostart entry, never a boot-time root service."""
    if not sys.platform.startswith("linux"):
        raise RuntimeError("El autoinicio de usuario solo esta disponible en Linux")
    home = Path.home()
    autostart = home / ".config" / "autostart"
    autostart.mkdir(parents=True, exist_ok=True)
    def quote(path):
        return '"' + str(path).replace("\\", "\\\\").replace('"', '\\"') + '"'
    desktop_file = autostart / "pyrion-os.desktop"
    contents = (
        "[Desktop Entry]\nType=Application\nName=PYRION OS\n"
        "Comment=Comprobacion y actualizacion del escritorio PYRION\n"
        "Exec=" + quote(sys.executable) + " " + quote(script_path.resolve()) + "\n"
        "Terminal=false\nX-GNOME-Autostart-enabled=true\n"
    )
    desktop_file.write_text(contents, encoding="utf-8")
    return desktop_file


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--install-autostart" in args:
        try:
            path = install_user_autostart(Path(__file__))
            _safe_console_write("Autoarranque de sesion configurado: " + str(path))
            return 0
        except (OSError, RuntimeError) as exc:
            fail_dialog("No se pudo configurar el autoinicio: " + str(exc))
            return 1

    observer = BootObserver()
    if "--no-ui" in args:
        return _run_boot_sequence(args, observer)
    rendered = _run_tk_boot(observer, args)
    if rendered is not None:
        return rendered
    rendered = _run_zenity_boot(observer, args)
    if rendered is not None:
        return rendered

    # A root boot service/rc.local runs before the user's X11/Wayland session.
    # Do not hide the cause: save it to a predictable, writable log file.
    hint = (
        "No se pudo abrir una pantalla de verificacion. "
        "Comprueba si X11/Wayland esta iniciado y si existe Tk o Zenity. "
        "Si ejecutas PYRION antes del login grafico, configurarlo en la sesion "
        "de usuario: python3 app.py --install-autostart. "
        "Registro: " + str(observer.output)
    )
    observer.log(hint)
    _safe_console_write(hint, error=True)
    # Last-resort graphical notice when only xmessage is installed.
    if os.name != "nt" and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        xmessage = shutil.which("xmessage")
        if xmessage:
            try:
                subprocess.Popen(
                    [xmessage, "-center", "-title", "PYRION OS - diagnostico",
                     "-buttons", "Aceptar:0", hint],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            except OSError:
                pass
    return 22


if __name__ == "__main__":
    raise SystemExit(main())
