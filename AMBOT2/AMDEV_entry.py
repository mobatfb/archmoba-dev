"""Entrada compatible con AMDEV para AMBOT 2.0.

AMDEV puede descargar un solo app.py. Este archivo trae los modulos
oficiales de AMBOT2 desde un commit inmutable antes de arrancar
la aplicacion nativa. En modo local usa los archivos del repositorio.
"""
APP_VERSION = "0.1.1"

import json
import re
import runpy
import sys
import urllib.request
from pathlib import Path

REPOSITORY = "mobatfb/archmoba-dev"
MODULE_FILES = (
    "engine/__init__.py",
    "engine/primitives.py",
    "engine/world.py",
    "body/__init__.py",
    "body/robot.py",
    "body/grasp.py",
    "brain/__init__.py",
    "brain/learning.py",
    "language/__init__.py",
    "language/understanding.py",
    "teacher/__init__.py",
    "teacher/recorder.py",
    "editor/__init__.py",
    "editor/objects.py",
)


def _release_sha(base):
    config_file = base / "config.json"
    if not config_file.is_file():
        raise RuntimeError("Falta AMBOT2/config.json. Reinstala o actualiza desde AMDEV.")
    config = json.loads(config_file.read_text(encoding="utf-8-sig"))
    commit = str(config.get("release_commit", "")).strip()
    if not re.fullmatch(r"[a-fA-F0-9]{40}", commit):
        raise RuntimeError("AMBOT2/config.json no tiene release_commit valido.")
    return commit


def _fetch_source(base, sha, path):
    url = (
        f"https://raw.githubusercontent.com/{REPOSITORY}/"
        f"{sha}/AMBOT2/{path}"
    )
    request = urllib.request.Request(
        url, headers={"User-Agent": "ARCHMOBA-AMBOT2/0.1"}
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        source = response.read().decode("utf-8-sig")
    if not source and not path.endswith("/__init__.py"):
        raise RuntimeError("Archivo vacio en release AMBOT2: " + path)
    if path.endswith(".py"):
        compile(source, path, "exec")
    return source


def prepare_runtime(base=None):
    """Retorna ruta de app real, sin depender del CWD del proceso."""
    base = Path(base).resolve() if base else Path(__file__).resolve().parent
    original = base / "app.py"
    # En modo local, esta entrada tiene nombre distinto de app.py; los
    # modulos pertenecen al mismo checkout. No hace falta descargar nada.
    if (Path(__file__).name != "app.py" and original.is_file()
            and all((base / path).is_file() for path in MODULE_FILES)):
        return original

    sha = _release_sha(base)
    entry = base / "ambot2_main.py"
    marker = base / ".ambot2_support_commit"
    required = tuple(MODULE_FILES) + ("app.py",)
    if (marker.is_file() and marker.read_text(encoding="ascii").strip() == sha
            and entry.is_file()
            and all((base / path).is_file() for path in MODULE_FILES)):
        return entry

    # Primero obtener y validar TODOS los archivos. No publicar un estado
    # marcado como completo hasta finalizar las escrituras.
    sources = {path: _fetch_source(base, sha, path) for path in required}
    for path, source in sources.items():
        destination = entry if path == "app.py" else base / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(source, encoding="utf-8")
        temporary.replace(destination)
    marker_tmp = marker.with_suffix(".tmp")
    marker_tmp.write_text(sha + "\n", encoding="ascii")
    marker_tmp.replace(marker)
    return entry


def main():
    target = prepare_runtime()
    base = target.parent
    if str(base) not in sys.path:
        sys.path.insert(0, str(base))
    runpy.run_path(str(target), run_name="__main__")


if __name__ == "__main__":
    main()
