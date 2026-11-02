#!/usr/bin/env python3
"""Generador seguro de nuevos proyectos Android APKBDEV (sin dependencias pip)."""
import argparse
import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
PACKAGE = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*){1,}$")


def generate(name, slug, package, projects_dir=None, template_dir=None):
    if not name or not name.strip() or len(name) > 80:
        raise ValueError("El nombre de la app debe tener entre 1 y 80 caracteres.")
    if not SLUG.fullmatch(slug):
        raise ValueError("Slug inválido: usa minúsculas, números y guiones; empieza con letra.")
    if not PACKAGE.fullmatch(package):
        raise ValueError("Paquete inválido: ejemplo com.archmoba.miapp.")

    template = Path(template_dir) if template_dir else ROOT / "templates" / "native-java"
    projects = Path(projects_dir) if projects_dir else ROOT / "projects"
    config = json.loads((ROOT / "config" / "toolchain.json").read_text(encoding="utf-8"))
    target = projects / slug
    if target.exists():
        raise FileExistsError("El proyecto ya existe: " + str(target))
    source_files = [file for file in template.rglob("*") if file.is_file()]
    if not source_files:
        raise FileNotFoundError("No se encontró la plantilla en " + str(template))
    tokens = {
        "__APP_GRADLE_NAME__": name.replace("\\", "\\\\").replace("'", "\\'"),
        "__APP_LABEL_XML__": escape(name, {'"': "&quot;"}),
        "__APPLICATION_ID__": package,
        "__AGP_VERSION__": str(config["android_gradle_plugin"]),
        "__COMPILE_SDK__": str(config["compile_sdk"]),
        "__MIN_SDK__": str(config["min_sdk"]),
        "__TARGET_SDK__": str(config["target_sdk"]),
    }
    for source in source_files:
        relative = source.relative_to(template)
        if relative.name == "MainActivity.java.tpl":
            relative = Path("app/src/main/java", *package.split("."), "MainActivity.java")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        content = source.read_text(encoding="utf-8")
        for key, value in tokens.items():
            content = content.replace(key, value)
        destination.write_text(content, encoding="utf-8")
    return target


def main():
    parser = argparse.ArgumentParser(description="Crear un proyecto APK Android en apkbdev/projects.")
    parser.add_argument("name", help="Nombre visible de la aplicación.")
    parser.add_argument("--slug", required=True, help="Nombre de carpeta; ej.: mi-app.")
    parser.add_argument("--package", help="Identificador Android; ej.: com.archmoba.miapp.")
    args = parser.parse_args()
    package = args.package or ("com.archmoba." + args.slug.replace("-", ""))
    try:
        path = generate(args.name, args.slug, package)
    except (ValueError, FileExistsError, FileNotFoundError) as error:
        parser.error(str(error))
    print("Aplicación creada:", path)
    print("Compilar: python3 apkbdev/tools/build_apk.py --project", args.slug)


if __name__ == "__main__":
    main()
