#!/usr/bin/env python3
"""Compila una aplicación apkbdev/projects/<slug> y copia su APK debug a dist."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from new_app import ROOT, SLUG


def build(project, clean=False, output=None):
    if not SLUG.fullmatch(project):
        raise ValueError("Nombre de proyecto inválido: " + project)
    source = ROOT / "projects" / project
    if not source.is_dir() or not (source / "app" / "build.gradle").is_file():
        raise FileNotFoundError("Proyecto Android no encontrado: " + str(source))
    gradle = shutil.which("gradle") or shutil.which("gradle.bat")
    if not gradle:
        raise RuntimeError("Gradle no está instalado o falta en PATH (requiere Gradle 8.7).")
    if clean:
        subprocess.run([gradle, "--no-daemon", "--project-dir", str(source), "clean"], check=True)
    subprocess.run([gradle, "--no-daemon", "--project-dir", str(source), "assembleDebug"], check=True)
    candidate = source / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
    if not candidate.is_file():
        raise FileNotFoundError("Gradle no generó el APK esperado: " + str(candidate))
    destination_dir = Path(output) if output else ROOT / "dist" / project
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / (project + "-debug.apk")
    shutil.copyfile(candidate, destination)
    print("APK compilado:", destination.resolve())
    print("Tamaño:", destination.stat().st_size, "bytes")
    return destination


def main():
    parser = argparse.ArgumentParser(description="Compilar proyectos Android de APKBDEV.")
    parser.add_argument("--project", required=True, help="Nombre en apkbdev/projects.")
    parser.add_argument("--clean", action="store_true", help="Limpiar antes de compilar.")
    parser.add_argument("--output", help="Carpeta de destino opcional para el APK.")
    args = parser.parse_args()
    try:
        build(args.project, args.clean, args.output)
    except (ValueError, FileNotFoundError, RuntimeError, subprocess.CalledProcessError) as error:
        print("Error:", error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
