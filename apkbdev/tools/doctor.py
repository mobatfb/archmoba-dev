#!/usr/bin/env python3
"""Verifica dependencias y versiones configuradas para compilar APK."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

from prepare_sdk import find_sdkmanager, get_sdk, ROOT


def main():
    parser = argparse.ArgumentParser(description="Comprobar entorno de compilación APKBDEV.")
    parser.add_argument("--strict", action="store_true",
                        help="Retorna código 1 si faltan dependencias esenciales.")
    args = parser.parse_args()
    config = json.loads((ROOT / "config" / "toolchain.json").read_text(encoding="utf-8"))
    sdk = get_sdk()

    def version(command):
        try:
            p = subprocess.run(command, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, timeout=20)
            return (p.stdout or "").splitlines()[:4]
        except (OSError, subprocess.TimeoutExpired):
            return []

    checks = {
        "JDK / java": shutil.which("java") is not None,
        "Gradle": shutil.which("gradle") is not None,
        "SDK root": sdk.is_dir(),
        "sdkmanager": find_sdkmanager(sdk) is not None,
        "Android platform": (sdk / "platforms" / ("android-" + str(config["compile_sdk"]))).is_dir(),
        "Android build-tools": (sdk / "build-tools" / str(config["build_tools"])).is_dir(),
    }
    for name, valid in checks.items():
        print(("[OK] " if valid else "[FALTA] ") + name)
    for command in (["java", "-version"], ["gradle", "--version"]):
        details = version(command)
        if details:
            print("  " + command[0] + ": " + " | ".join(details[:2]))
    print("Requerido:", "Java", config["java_version"],
          "Gradle", config["gradle_version"], "AGP", config["android_gradle_plugin"],
          "SDK", config["compile_sdk"], "build-tools", config["build_tools"])
    if args.strict and not all(checks.values()):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
