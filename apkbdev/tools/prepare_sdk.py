#!/usr/bin/env python3
"""Instala plataformas Android listadas en toolchain.json, sin ejecutar 'sdkmanager tools'."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def get_sdk():
    value = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if value:
        return Path(value).expanduser().resolve()
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk"
    return Path.home() / "Android" / "Sdk"


def find_sdkmanager(sdk):
    candidate = shutil.which("sdkmanager") or shutil.which("sdkmanager.bat")
    if candidate:
        return str(candidate)
    extension = ".bat" if sys.platform == "win32" else ""
    paths = [sdk / "cmdline-tools" / "latest" / "bin" / ("sdkmanager" + extension)]
    paths += sorted((sdk / "cmdline-tools").glob("*/bin/sdkmanager" + extension), reverse=True)
    for path in paths:
        if path.is_file():
            return str(path)
    return None


def main():
    config = json.loads((ROOT / "config" / "toolchain.json").read_text(encoding="utf-8"))
    sdk = get_sdk()
    manager = find_sdkmanager(sdk)
    if not manager:
        sys.exit("No se encontró sdkmanager. Instala Android SDK Command-line Tools y configura ANDROID_HOME.")
    packages = [
        "platforms;android-" + str(config["compile_sdk"]),
        "build-tools;" + str(config["build_tools"]),
    ]
    print("SDK:", sdk)
    print("Instalando:", ", ".join(packages), flush=True)
    subprocess.run([manager, "--sdk_root=" + str(sdk), *packages], check=True)
    print("Paquetes Android listos.")


if __name__ == "__main__":
    main()
