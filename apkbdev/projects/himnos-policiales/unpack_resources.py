#!/usr/bin/env python3
"""Prepara Himnos Policiales v1.3.0 con el arte exacto aprobado por el usuario.

Reconstituye solo los dos audios originales del paquete verificado.
Los controles tipo app y el fondo completo ya están versionados como
archivos WEBP independientes, sin descargar imágenes externas.
"""
from pathlib import Path
import hashlib
import io
import zipfile
from PIL import Image

ROOT = Path(__file__).resolve().parent
APP_MAIN = ROOT / "app" / "src" / "main"
EXPECTED_ZIP_SHA256 = "d9e7719bd456f7fb4f6d86407cd0a1a7f757f187c4afb117e2e2280af1f276b3"
EXPECTED_ZIP = {
    "assets/cabecera.webp", "assets/cinta.webp",
    "assets/ecuador.webp", "assets/policia.webp", "assets/stop.webp",
    "res/raw/himno_ecuador.mp3", "res/raw/himno_policia.mp3",
    "res/drawable-nodpi/launcher_himnos.webp",
}
CUSTOM_LAUNCHER_SHA256 = "ad2d275e279e5096b5ded2dc451db2db15949b06542d2e1fd18a45fbeb101102"
ARTWORK_SHA256 = {
    "fondo.webp": "c6069f7c6c147da2f71bb7049e5685a5e8ee6d92f407078643f974e12f13d1fe",
    "ecuador.webp": "75236cc975ab5a6c2bffbe0a83ee0c4d4f9ec68d041aae01de19217d62f893d9",
    "policia.webp": "5fc415b6e75ed034fd3b8f28ed3061617a29edb001b9c336c74e468a3fca13db",
    "stop.webp": "3a535a20cbd3900c22dafd564dca061962446553670fff794fac7f8d38505b23",
}

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> None:
    parts = sorted((ROOT / "media").glob("part-*.bin"))
    if len(parts) != 11:
        raise RuntimeError("Faltan archivos originales de audio: se esperaban 11 partes")
    packed = b"".join(part.read_bytes() for part in parts)
    if sha256(packed) != EXPECTED_ZIP_SHA256:
        raise RuntimeError("Los audios originales no coinciden con SHA-256")
    with zipfile.ZipFile(io.BytesIO(packed)) as archive:
        if set(archive.namelist()) != EXPECTED_ZIP:
            raise RuntimeError("Contenido del paquete original inesperado")
        for name in ("res/raw/himno_ecuador.mp3", "res/raw/himno_policia.mp3"):
            target = APP_MAIN / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
            print("Audio verificado", name, target.stat().st_size, "bytes")

    # No sobrescribir el icono personalizado de la APK que envió el usuario.
    launcher = APP_MAIN / "res" / "drawable-nodpi" / "launcher_himnos.webp"
    if not launcher.is_file() or sha256(launcher.read_bytes()) != CUSTOM_LAUNCHER_SHA256:
        raise RuntimeError("Falta el ícono personalizado de Himnos Policiales")

    # Usar el fondo vertical continuo y botones completos redondeados del
    # último boceto aprobado. No crear máscaras que recorten el escudo.
    assets = APP_MAIN / "assets"
    for name, expected in ARTWORK_SHA256.items():
        path = assets / name
        if not path.is_file() or sha256(path.read_bytes()) != expected:
            raise RuntimeError(f"Falta o cambió el recurso visual: {name}")
        with Image.open(path) as im:
            im.load()
            if im.size[0] < 200 or im.size[1] < 200:
                raise RuntimeError(f"Imagen demasiado pequeña: {name}")
            if name != "fondo.webp" and im.mode != "RGBA":
                raise RuntimeError(f"El botón debe conservar transparencia: {name}")
            if name != "fondo.webp" and im.getpixel((0, 0))[3] != 0:
                raise RuntimeError(f"El botón contiene fondo rectangular: {name}")
        print("Arte aprobado", name, path.stat().st_size, "bytes")
    print("OK: audios, fondo completo, icono y botones originales verificados")

if __name__ == "__main__":
    main()
