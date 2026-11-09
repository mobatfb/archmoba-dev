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
            # La cabecera sin escudo central se conserva como recurso propio
            # del proyecto; los audios y demás iconos se verifican del paquete.
            if name == "assets/cabecera.webp" and destination.is_file():
                print("OK cabecera personalizada", destination.stat().st_size, "bytes")
                continue
            destination.write_bytes(archive.read(name))
            print("OK", name, destination.stat().st_size, "bytes")
    # Adaptacion permanente de la cabecera: borrar el escudo CENTRAL
    # y conservar el titulo HIMNOS POLICIALES, bandera y fondo original.
    # Solo se corrige el recurso original del paquete; no modifica los dos
    # escudos que funcionan como botones de reproduccion.
    from PIL import Image, ImageFilter
    original = ROOT / "app" / "src" / "main" / "assets" / "cabecera.webp"
    current = Image.open(original).convert("RGB")
    if current.size == (1000, 459):
        w, h = current.size
        # Recrear cielo azul a partir del fondo de nubes existente a la
        # derecha del antiguo escudo, sin copiar emblemas ni personas.
        clouds = current.crop((682, 0, 761, 302))
        clouds = clouds.resize((w, 302), Image.Resampling.BICUBIC)
        clouds = clouds.filter(ImageFilter.GaussianBlur(8))
        layer = Image.new("RGB", (w, h), (3, 19, 39))
        layer.paste(clouds, (0, 0))
        mask = Image.new("L", (w, h), 0)
        pixels = mask.load()
        def smooth(value):
            t = max(0.0, min(1.0, value))
            return t * t * (3.0 - 2.0 * t)
        for y in range(0, 306):
            vertical = 1.0 if y <= 287 else (1.0 - smooth((y - 287) / 6.0))
            if vertical <= 0.0:
                continue
            for x in range(180, 812):
                horizontal = smooth((x - 220) / 150.0) * (1.0 - smooth((x - 660) / 130.0))
                pixels[x, y] = int(255.0 * min(1.0, horizontal) * vertical)
        corrected = Image.composite(layer, current, mask)
        corrected.save(original, "WEBP", quality=91, method=6)
        print("Cabecera corregida sin escudo central", original.stat().st_size, "bytes")
    print("Recursos verificados SHA-256", digest)

if __name__ == "__main__":
    main()
