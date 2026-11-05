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
APP_VERSION = "0.3.4"
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


def start_desktop(store: PersistentStore, name: str, desktop: Path, state: dict) -> int:
    env = os.environ.copy()
    env["PYRIONOS_DATA_DIR"] = str(store.root)
    announce(store, f"Iniciando escritorio desde {desktop}")
    try:
        result = subprocess.run([sys.executable, str(desktop)], cwd=str(desktop.parent), env=env, check=False)
        code = result.returncode
    except OSError as exc:
        announce(store, f"No se pudo iniciar escritorio: {exc}")
        code = 1
    if code == 0:
        return 0
    if code == 20:
        announce(store, "Fallo de instalacion de PySide6; la version persistente sigue siendo valida.")
        announce(store, "Revisa " + str(store.root / "logs" / "desktop_setup.log"))
        return code

    system_dir = store.root / "system"
    announce(store, f"Escritorio termino con error ({code}); buscando recuperacion")
    previous = cached_release(system_dir, state, "previous")
    if previous and previous[0] != name:
        save_state(system_dir, {
            **state, "current": previous[0], "previous": name, "failed_release": name
        })
        announce(store, f"Restaurada version previa: {previous[0]}")
        try:
            return subprocess.run([sys.executable, str(previous[1])], cwd=str(previous[1].parent), env=env, check=False).returncode
        except OSError as exc:
            announce(store, f"No fue posible abrir la version previa: {exc}")
    return code or 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    offline = "--offline" in args or os.environ.get("PYRIONOS_OFFLINE") == "1"
    try:
        store = PersistentStore()
    except StorageError as exc:
        fail_dialog(f"PYRION OS: no se pudo acceder al almacenamiento persistente.\n\n{exc}")
        return 1
    try:
        name, path, state = select_release(store, offline=offline)
        if "--check-only" in args:
            announce(store, f"Version preparada: {name}, ruta: {path}")
            return 0
        return start_desktop(store, name, path, state)
    except Exception as exc:
        announce(store, f"No se pudo iniciar PYRION: {type(exc).__name__}: {exc}")
        fail_dialog(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
