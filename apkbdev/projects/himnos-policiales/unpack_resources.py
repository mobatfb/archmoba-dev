#!/usr/bin/env python3
"""Reconstituir y verificar los recursos locales originales de Himnos Policiales."""
from pathlib import Path
import hashlib
import zipfile

ROOT = Path(__file__).resolve().parent
PARTS = ROOT / "media"
EXPECTED_SHA256 = "d9e7719bd456f7fb4f6d86407cd0a1a7f757f187c4afb117e2e2280af1f276b3"
EXPECTED = {
    "assets/cabecera.webp",
    "assets/cinta.webp",
    "assets/ecuador.webp",
    "assets/policia.webp",
    "assets/stop.webp",
    "res/raw/himno_ecuador.mp3",
    "res/raw/himno_policia.mp3",
    "res/drawable-nodpi/launcher_himnos.webp",
}


def main():
    parts = sorted(PARTS.glob("part-*.bin"))
    if len(parts) != 11:
        raise RuntimeError(f"Se esperaban 11 partes de audio/imágenes; encontradas: {len(parts)}")
    binary = b"".join(p.read_bytes() for p in parts)
    digest = hashlib.sha256(binary).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError("Error de integridad: la música o el fondo no coinciden con los originales.")
    import io
    with zipfile.ZipFile(io.BytesIO(binary)) as archive:
        names = set(archive.namelist())
        if names != EXPECTED:
            raise RuntimeError("Recursos incompletos o inesperados: " + repr(names ^ EXPECTED))
        root = ROOT / "app" / "src" / "main"
        for name in sorted(EXPECTED):
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
            print("OK", name, destination.stat().st_size, "bytes")
    print("Recursos verificados SHA-256", digest)

if __name__ == "__main__":
    main()
