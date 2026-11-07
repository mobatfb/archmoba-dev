#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrae PYRION_OS.iso a src, incluidas las imagenes internas de PYRION.

Sin dependencias externas: funciona con Python 3.9+ en Windows y Linux.

Estructura resultante:
  src/BOOT/                       Archivos EXACTOS visibles en la ISO
  src/IMG_EXTRAIDO/PYRION/         Contenido descomprimido de PYRION.IMG (cpio/gzip)
  src/IMG_EXTRAIDO/INITRD/         Contenido descomprimido de INITRD.IMG (cpio/gzip)
  src/IMG_EXTRAIDO/PYTHON/         Contenido descomprimido de PYTHON.IMG (cpio/gzip)
  src/IMG_EXTRAIDO/EFIBOOT/        Contenido del sistema FAT de EFIBOOT.IMG

Los archivos IMG originales no se modifican. Los archivos especiales y enlaces
simbolicos de Linux se representan mediante archivos .symlink.txt / .special.txt
si Windows no puede crearlos con sus atributos originales.

Uso:
  python extraer_pyrion_iso.py
  python extraer_pyrion_iso.py --solo-iso
  python extraer_pyrion_iso.py --iso "otra.iso" --salida "otra_carpeta"
"""

import argparse
import gzip
import os
from pathlib import Path
import re
import struct
import sys

SECTOR = 2048
BLOQUE = 1024 * 1024


def u16(data, pos):
    return struct.unpack_from('<H', data, pos)[0]


def u32(data, pos):
    return struct.unpack_from('<I', data, pos)[0]


def ruta_segura(base, name):
    """Rechaza rutas de archivo peligrosas o incompatibles con Windows."""
    if '\x00' in name or name.startswith(('/', '\\')):
        raise ValueError('Ruta absoluta o invalida: %r' % name)
    pieces = name.replace('\\', '/').split('/')
    pieces = [p for p in pieces if p not in ('', '.')]
    if any(p == '..' or re.search(r'[<>:"|?*\x00-\x1f]', p) or p.endswith((' ', '.'))
           for p in pieces):
        raise ValueError('Nombre de archivo no seguro en Windows: %r' % name)
    if not pieces:
        return base
    if any(p.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL',
                  *(('COM%d' % i) for i in range(1, 10)),
                  *(('LPT%d' % i) for i in range(1, 10))} for p in pieces):
        raise ValueError('Nombre reservado de Windows: %r' % name)
    return base.joinpath(*pieces)


def escribir_bytes(origen, destino, cantidad):
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open('wb') as out:
        restante = cantidad
        while restante:
            bloque = origen.read(min(BLOQUE, restante))
            if not bloque:
                raise EOFError('Archivo truncado al extraer %s' % destino)
            out.write(bloque)
            restante -= len(bloque)


def _nombre_iso(record, joliet):
    length = record[32]
    raw = record[33:33 + length]
    if raw in (b'\x00', b'\x01'):
        return None
    if joliet:
        name = raw.decode('utf-16-be', errors='replace')
    else:
        name = raw.decode('ascii', errors='replace')
        # Rock Ridge: usar NM si esta presente, por encima de los nombres ISO.
        start = 33 + length + (0 if length % 2 else 1)
        chunks = []
        while start + 4 <= len(record):
            sig, size = record[start:start + 2], record[start + 2]
            if size < 4 or start + size > len(record):
                break
            if sig == b'NM' and size >= 5 and record[start + 4] & 6 == 0:
                chunks.append(record[start + 5:start + size])
            start += size
        if chunks:
            name = b''.join(chunks).decode('utf-8', errors='replace')
    return re.sub(r';[0-9]+$', '', name).rstrip('.')


def _registros_dir(fh, extent, length, joliet):
    fh.seek(extent * SECTOR)
    done = 0
    while done < length:
        sector = fh.read(min(SECTOR, length - done))
        if not sector:
            raise EOFError('Directorio ISO truncado')
        done += len(sector)
        offset = 0
        while offset < len(sector):
            entry_len = sector[offset]
            if not entry_len:
                break
            record = sector[offset:offset + entry_len]
            if len(record) < 34 or len(record) < entry_len:
                raise ValueError('Entrada ISO no valida')
            name = _nombre_iso(record, joliet)
            if name:
                yield name, u32(record, 2), u32(record, 10), bool(record[25] & 2), bool(record[25] & 128)
            offset += entry_len


def extraer_iso(iso, destino):
    """Lee ISO9660/Joliet/Rock Ridge sin montar el disco ni instalar 7-Zip."""
    print('\n[1/2] Extrayendo archivos ISO9660 de', iso.name, flush=True)
    destino.mkdir(parents=True, exist_ok=True)
    files = 0
    total = 0
    with iso.open('rb') as fh:
        pvd, joliet_desc = None, None
        for sector_no in range(16, 64):
            fh.seek(sector_no * SECTOR)
            vd = fh.read(SECTOR)
            if len(vd) < SECTOR or vd[1:6] != b'CD001':
                break
            if vd[0] == 1:
                pvd = vd
            if vd[0] == 2 and vd[88:91] in (b'%/@', b'%/C', b'%/E'):
                joliet_desc = vd
            if vd[0] == 255:
                break
        if pvd is None:
            raise ValueError('No se encontro un volumen ISO9660 valido. Archivo no compatible.')
        volume = joliet_desc if joliet_desc is not None else pvd
        joliet = joliet_desc is not None
        root = volume[156:190]
        pendientes = [('', u32(root, 2), u32(root, 10))]
        visitados = set()
        while pendientes:
            carpeta, extent, size = pendientes.pop(0)
            if (extent, size) in visitados:
                continue
            visitados.add((extent, size))
            for name, start, length, es_dir, multi in _registros_dir(fh, extent, size, joliet):
                relative = (carpeta + '/' + name).lstrip('/')
                target = ruta_segura(destino, relative)
                if es_dir:
                    target.mkdir(parents=True, exist_ok=True)
                    pendientes.append((relative, start, length))
                    print('  [DIR] ', relative, flush=True)
                else:
                    # Volver a la posicion de busqueda tras copiar contenido.
                    pointer = fh.tell()
                    fh.seek(start * SECTOR)
                    escribir_bytes(fh, target, length)
                    fh.seek(pointer)
                    files += 1
                    total += length
                    print('  [FILE]', relative, '- %.1f MB' % (length / (1024 * 1024)), flush=True)
                    if multi:
                        print('    Aviso: archivo ISO de multiples extents:', relative)
    print('ISO extraida: %d archivos, %.1f MB' % (files, total / (1024 * 1024)), flush=True)
    return files


def _leer_completo(fh, count):
    value = fh.read(count)
    if len(value) != count:
        raise EOFError('Archivo CPIO truncado')
    return value


def extraer_cpio_gzip(archivo, destino):
    """Extrae gzip + CPIO newc (initramfs), sin cargar todo en memoria."""
    with gzip.open(archivo, 'rb') as gz:
        if gz.read(6) not in (b'070701', b'070702'):
            return None
    print('  [CPIO]', archivo.name, '=>', destino, flush=True)
    contador = 0
    special = 0
    with gzip.open(archivo, 'rb') as gz:
        while True:
            header = gz.read(110)
            if not header:
                break
            if len(header) != 110 or header[:6] not in (b'070701', b'070702'):
                raise ValueError('CPIO corrupto en: ' + archivo.name)
            try:
                mode = int(header[14:22], 16)
                size = int(header[54:62], 16)
                name_size = int(header[94:102], 16)
            except ValueError as exc:
                raise ValueError('Encabezado CPIO invalido') from exc
            if not 0 < name_size <= 32768:
                raise ValueError('Nombre de archivo CPIO invalido')
            name = _leer_completo(gz, name_size).rstrip(b'\x00').decode('utf-8', errors='replace')
            padding = (-(110 + name_size)) % 4
            _leer_completo(gz, padding)
            if name == 'TRAILER!!!':
                break
            dest = ruta_segura(destino, name)
            kind = mode & 0o170000
            if kind == 0o040000:  # Directorio.
                dest.mkdir(parents=True, exist_ok=True)
                if size:
                    _leer_completo(gz, size)
            elif kind == 0o100000:  # Archivo normal.
                escribir_bytes(gz, dest, size)
            elif kind == 0o120000:  # Enlace simbolico; guardamos destino.
                link = _leer_completo(gz, size)
                dest = dest.with_name(dest.name + '.symlink.txt')
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(link.decode('utf-8', errors='replace'), encoding='utf-8')
                special += 1
            else:  # Nodos de dispositivo, sockets, fifo, etc.
                _leer_completo(gz, size)
                dest = dest.with_name(dest.name + '.special.txt')
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text('Tipo CPIO: %s\nModo: %s\n' % (oct(kind), oct(mode)), encoding='utf-8')
                special += 1
            _leer_completo(gz, (-size) % 4)
            contador += 1
            if contador % 500 == 0:
                print('    %d entradas...' % contador, flush=True)
    print('    Completado: %d entradas (%d enlaces/elementos especiales).' % (contador, special), flush=True)
    return contador


class FATImage:
    """Lector FAT12/FAT16/FAT32 de solo lectura para EFIBOOT.IMG."""

    def __init__(self, path):
        self.path = path
        self.fh = path.open('rb')
        boot = self.fh.read(512)
        if len(boot) != 512 or boot[510:512] != b'\x55\xaa':
            raise ValueError('No es un volumen FAT valido')
        self.bps = u16(boot, 11)
        self.spc = boot[13]
        self.reserved = u16(boot, 14)
        self.fats = boot[16]
        self.root_entries = u16(boot, 17)
        total = u16(boot, 19) or u32(boot, 32)
        self.spf = u16(boot, 22) or u32(boot, 36)
        if (self.bps not in (512, 1024, 2048, 4096) or
            self.spc == 0 or (self.spc & (self.spc - 1)) or
            not self.reserved or not self.fats or not self.spf or not total):
            raise ValueError('Parametros FAT invalidos')
        self.root_secs = ((self.root_entries * 32) + self.bps - 1) // self.bps
        self.root_pos = (self.reserved + self.fats * self.spf) * self.bps
        self.data_pos = (self.reserved + self.fats * self.spf + self.root_secs) * self.bps
        clusters = (total - (self.reserved + self.fats * self.spf + self.root_secs)) // self.spc
        self.fat_type = 12 if clusters < 4085 else (16 if clusters < 65525 else 32)
        self.max_cluster = clusters + 1
        self.root_cluster = u32(boot, 44) & 0x0fffffff if self.fat_type == 32 else None
        self.fat_pos = self.reserved * self.bps

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.fh.close()

    def next_cluster(self, n):
        if self.fat_type == 12:
            self.fh.seek(self.fat_pos + n * 3 // 2)
            data = self.fh.read(2)
            val = int.from_bytes(data, 'little')
            val = (val >> 4) if n & 1 else (val & 0xfff)
        else:
            width = 2 if self.fat_type == 16 else 4
            self.fh.seek(self.fat_pos + n * width)
            data = self.fh.read(width)
            val = int.from_bytes(data, 'little')
            if self.fat_type == 32:
                val &= 0x0fffffff
        return val

    def leer_cadena(self, first, size=None):
        seen = set()
        n = first
        remaining = size
        eoc = {12: 0xff8, 16: 0xfff8, 32: 0x0ffffff8}[self.fat_type]
        while 2 <= n <= self.max_cluster and n < eoc:
            if n in seen:
                raise ValueError('Cadena FAT ciclica')
            seen.add(n)
            count = self.bps * self.spc
            if remaining is not None:
                count = min(count, remaining)
                if not count:
                    return
            self.fh.seek(self.data_pos + (n - 2) * self.bps * self.spc)
            part = self.fh.read(count)
            if len(part) != count:
                raise EOFError('Datos FAT incompletos')
            yield part
            if remaining is not None:
                remaining -= count
                if remaining <= 0:
                    return
            n = self.next_cluster(n)
        if remaining is not None and remaining > 0:
            raise EOFError('Cadena FAT mas corta que el archivo')

    def root_data(self):
        if self.fat_type == 32:
            return b''.join(self.leer_cadena(self.root_cluster))
        self.fh.seek(self.root_pos)
        return self.fh.read(self.root_secs * self.bps)

    @staticmethod
    def registros(folder):
        lfn = []
        for pos in range(0, len(folder), 32):
            rec = folder[pos:pos + 32]
            if len(rec) < 32 or rec[0] == 0x00:
                break
            if rec[0] == 0xe5:
                lfn = []
                continue
            if rec[11] == 0x0f:
                txt = rec[1:11] + rec[14:26] + rec[28:32]
                lfn.append(txt.decode('utf-16le', errors='replace').split('\x00')[0].replace('\uffff', ''))
                continue
            attr = rec[11]
            if attr & 0x08:
                lfn = []
                continue
            if lfn:
                name = ''.join(reversed(lfn))
                lfn = []
            else:
                stem = rec[0:8].decode('cp437', errors='replace').rstrip()
                ext = rec[8:11].decode('cp437', errors='replace').rstrip()
                name = stem + ('.' + ext if ext else '')
            if name in ('.', '..'):
                continue
            start = (u16(rec, 20) << 16) | u16(rec, 26)
            yield name, start, u32(rec, 28), bool(attr & 0x10)


def extraer_efi(archivo, destino):
    print('  [FAT] ', archivo.name, '=>', destino, flush=True)
    count = 0
    with FATImage(archivo) as fat:
        pendientes = [('', fat.root_data())]
        seen_dirs = set()
        while pendientes:
            rel, data = pendientes.pop(0)
            for name, start, size, is_dir in fat.registros(data):
                rel_file = (rel + '/' + name).lstrip('/')
                dest = ruta_segura(destino, rel_file)
                if is_dir:
                    dest.mkdir(parents=True, exist_ok=True)
                    if start not in seen_dirs:
                        seen_dirs.add(start)
                        pendientes.append((rel_file, b''.join(fat.leer_cadena(start))))
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with dest.open('wb') as f:
                        if size:
                            for chunk in fat.leer_cadena(start, size):
                                f.write(chunk)
                    count += 1
                    print('    ', rel_file, flush=True)
    print('    EFI: %d archivos.' % count, flush=True)
    return count


def extraer_internas(destino):
    print('\n[2/2] Descomprimiendo imagenes internas (sin alterar los .IMG originales)', flush=True)
    imgs = sorted(p for p in destino.rglob('*') if p.is_file() and p.suffix.upper() == '.IMG'
                  and 'IMG_EXTRAIDO' not in p.parts)
    count = 0
    for img in imgs:
        extracted = destino / 'IMG_EXTRAIDO' / img.stem
        try:
            with img.open('rb') as f:
                head = f.read(2)
            if head == b'\x1f\x8b':
                result = extraer_cpio_gzip(img, extracted)
                if result is not None:
                    count += 1
                else:
                    print('  [OMITIDO] Gzip no CPIO:', img.name, flush=True)
            elif img.name.upper() == 'EFIBOOT.IMG':
                extraer_efi(img, extracted)
                count += 1
            else:
                print('  [ORIGINAL] Sin empaquetado compatible:', img.name, flush=True)
        except (OSError, EOFError, ValueError) as exc:
            print('  [ERROR] %s: %s' % (img.name, exc), file=sys.stderr, flush=True)
            raise
    return count


def main():
    parser = argparse.ArgumentParser(description='Extrae PYRION_OS.iso completo en src/')
    parser.add_argument('--iso', default='PYRION_OS.iso', help='ISO de origen')
    parser.add_argument('--salida', default='src', help='Carpeta de salida')
    parser.add_argument('--solo-iso', action='store_true', help='No descomprimir las imagenes IMG internas')
    options = parser.parse_args()
    base = Path(__file__).resolve().parent
    iso = Path(options.iso)
    if not iso.is_absolute():
        iso = (base / iso) if (base / iso).is_file() else (Path.cwd() / iso)
    if not iso.is_file():
        print('ERROR: No encuentro %s. Coloca PYRION_OS.iso junto a este script.' % iso,
              file=sys.stderr, flush=True)
        return 1
    out = Path(options.salida)
    if not out.is_absolute():
        out = base / out
    if out.resolve() == iso.resolve():
        print('ERROR: La salida no puede ser el archivo ISO.', file=sys.stderr)
        return 1
    print('PYRION OS - extractor de ISO e imagenes internas', flush=True)
    print('Origen: ', iso, flush=True)
    print('Destino:', out, flush=True)
    print('La ISO original sera conservada sin cambios.', flush=True)
    try:
        extraer_iso(iso, out)
        if not options.solo_iso:
            extraer_internas(out)
    except (OSError, EOFError, ValueError, PermissionError) as exc:
        print('\nERROR:', exc, file=sys.stderr, flush=True)
        return 2
    print('\nLISTO. Todo lo extraido esta en: %s' % out, flush=True)
    print('Nota: los datos de arranque El Torito/UEFI de la ISO requieren recreacion al volver a crear una ISO.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
