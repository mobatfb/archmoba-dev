#!/usr/bin/env python3
"""Verifica audios originales y prepara la interfaz sin fondos opacos (v1.2)."""
from __future__ import annotations

from pathlib import Path
import hashlib
import io
import math
import zipfile

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
PARTS = ROOT / "media"
EXPECTED_SHA256 = "d9e7719bd456f7fb4f6d86407cd0a1a7f757f187c4afb117e2e2280af1f276b3"
ICON_SHA256 = "ad2d275e279e5096b5ded2dc451db2db15949b06542d2e1fd18a45fbeb101102"
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


def _smooth(value: float) -> float:
    x = max(0.0, min(1.0, value))
    return x * x * (3.0 - 2.0 * x)


def remove_central_crest(assets: Path) -> Image.Image:
    """Limpia solo el emblema central; conserva bandera, policía y el título."""
    file = assets / "cabecera.webp"
    current = Image.open(file).convert("RGB")
    if current.size != (1000, 459):
        raise RuntimeError(f"Tamaño inesperado de cabecera: {current.size!r}")
    w, h = current.size
    clouds = current.crop((682, 0, 761, 302))
    clouds = clouds.resize((w, 302), Image.Resampling.BICUBIC)
    clouds = clouds.filter(ImageFilter.GaussianBlur(8))
    layer = Image.new("RGB", (w, h), (3, 19, 39))
    layer.paste(clouds, (0, 0))
    mask = Image.new("L", (w, h), 0)
    pixels = mask.load()
    for y in range(306):
        vertical = 1.0 if y <= 287 else 1.0 - _smooth((y - 287) / 6.0)
        if vertical <= 0:
            continue
        for x in range(180, 812):
            horizontal = _smooth((x - 220) / 150.0) * (
                1.0 - _smooth((x - 660) / 130.0)
            )
            pixels[x, y] = int(255.0 * min(1.0, horizontal) * vertical)
    corrected = Image.composite(layer, current, mask)
    corrected.save(file, "WEBP", quality=92, method=6)
    return corrected


def make_full_background(assets: Path, header: Image.Image) -> None:
    """Crea un fondo UNICO de pantalla completa; no contiene botones."""
    w, h = 720, 1440
    bg = Image.new("RGB", (w, h), (4, 22, 49))
    draw = ImageDraw.Draw(bg)
    for y in range(h):
        t = y / h
        if t < .45:
            rgb = (3 + 3*t, 22 + 19*t, 48 + 35*t)
        elif t < .77:
            u = (t - .45) / .32
            rgb = (5 + 3*u, 38 + 6*u, 76 + 9*u)
        else:
            u = (t - .77) / .23
            rgb = (8 - 4*u, 44 - 30*u, 85 - 50*u)
        glow = math.exp(-((t - .57) / .18) ** 2)
        c = tuple(int(max(0, min(255, v + a*glow))) for v, a in zip(rgb, (3,9,24)))
        draw.line((0,y,w,y), fill=c)
    bg = bg.convert("RGBA")

    # Luz ambiental difusa: no hay paneles sólidos detrás de los botones.
    light = Image.new("RGBA",(w,h),(0,0,0,0))
    ImageDraw.Draw(light).ellipse((20,640,700,1090),fill=(0,147,252,23))
    bg.alpha_composite(light.filter(ImageFilter.GaussianBlur(65)))

    head = header.resize((w,670),Image.Resampling.LANCZOS).convert("RGBA")
    hm = Image.new("L",head.size,255)
    hd = ImageDraw.Draw(hm)
    for y in range(586,670):
        opacity = int(255 * (1-((y-586)/84)**2))
        hd.line((0,y,w,y),fill=opacity)
    head.putalpha(hm)
    bg.alpha_composite(head,(0,0))

    # Cinta tricolor sin corte horizontal perceptible.
    ribbon = Image.open(assets / "cinta.webp").convert("RGBA")
    ribbon = ribbon.resize((w,125), Image.Resampling.LANCZOS)
    mask = Image.new("L",(w,125),255)
    md = ImageDraw.Draw(mask)
    for y in range(32):
        md.line((0,y,w,y),fill=int(255 * (y/32)**1.3))
    ribbon.putalpha(mask)
    bg.alpha_composite(ribbon,(0,h-125))
    out = assets / "fondo.webp"
    bg.convert("RGB").save(out,"WEBP",quality=88,method=6)
    print("OK wallpaper vertical continuo", out.stat().st_size, "bytes")


def make_floating_buttons(assets: Path) -> None:
    """Elimina los recuadros exteriores y conserva el emblema visible."""
    for name in ("ecuador", "policia", "stop"):
        file = assets / (name + ".webp")
        source = Image.open(file).convert("RGBA")
        w,h = source.size
        mask = Image.new("L",(w,h),0)
        md = ImageDraw.Draw(mask)
        if name == "stop":
            md.ellipse((w*.05,h*.02,w*.95,h*.99),fill=255)
            blur = 3.3
        else:
            md.rounded_rectangle((w*.012,h*.012,w*.988,h*.988),
                                 radius=int(min(w,h)*.17), fill=255)
            blur = 2.0
        source.putalpha(mask.filter(ImageFilter.GaussianBlur(blur)))
        source.save(file,"WEBP",quality=92,method=6)
        print("OK botón flotante",name,file.stat().st_size,"bytes")


def main() -> None:
    parts = sorted(PARTS.glob("part-*.bin"))
    if len(parts) != 11:
        raise RuntimeError(f"Se esperaban 11 partes; encontradas: {len(parts)}")
    binary = b"".join(p.read_bytes() for p in parts)
    digest = hashlib.sha256(binary).hexdigest()
    if digest != EXPECTED_SHA256:
        raise RuntimeError("Error de integridad de los himnos/recursos originales")
    main_root = ROOT / "app" / "src" / "main"
    custom_launcher = main_root / "res" / "drawable-nodpi" / "launcher_himnos.webp"
    if (not custom_launcher.exists() or
        hashlib.sha256(custom_launcher.read_bytes()).hexdigest() != ICON_SHA256):
        raise RuntimeError("No se encontró el ícono personalizado que envió el usuario")
    with zipfile.ZipFile(io.BytesIO(binary)) as archive:
        if set(archive.namelist()) != EXPECTED:
            raise RuntimeError("Paquete original de recursos inesperado")
        for name in sorted(EXPECTED):
            if name == "res/drawable-nodpi/launcher_himnos.webp":
                print("OK ícono del usuario",custom_launcher.stat().st_size,"bytes")
                continue
            path = main_root / name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(archive.read(name))
    assets = main_root / "assets"
    header = remove_central_crest(assets)
    make_full_background(assets,header)
    make_floating_buttons(assets)
    print("OK recursos originales verificados SHA-256", digest)

if __name__ == "__main__":
    main()