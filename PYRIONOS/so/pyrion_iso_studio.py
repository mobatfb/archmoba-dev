#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PYRION OS - ISO Studio (GUI + extractor + empaquetador, archivo unico).

Un solo script para Windows con interfaz Tkinter, Python 3.9 o superior.
No requiere 7-Zip, WSL ni bibliotecas externas.

Al extraer PYRION_OS.iso crea src/ con:
  PYRION/, PYTHON/, BIOSBOOT.IMG, EFIBOOT.IMG, INITRD.IMG,
  README.TXT, VMLINUZ, BOOT_CONFIG.json y .pyrion_boot/.

Al empaquetar genera/reemplaza PYRION_OS.iso usando SOLAMENTE src/:
  - reconstruye el contenido editable PYRION.IMG y PYTHON.IMG;
  - mantiene intactos EFIBOOT.IMG e INITRD.IMG;
  - conserva las referencias de arranque BIOS/UEFI (El Torito);
  - valida la nueva ISO antes de sustituir la anterior.

Se recomienda comprobar el arranque con QEMU o VirtualBox. La validacion
estructural no equivale a una prueba de arranque real.

Interfaz:    python pyrion_iso_studio.py
Consola:    python pyrion_iso_studio.py --extraer
            python pyrion_iso_studio.py --extraer --sobrescribir
            python pyrion_iso_studio.py --empaquetar
            python pyrion_iso_studio.py --directorio RUTA --empaquetar
"""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import shutil
import struct
import sys
import tempfile
import threading
import time
import traceback

SECTOR = 2048
BLOQUE = 1024 * 1024
NEEDED = (
    'BIOSBOOT.IMG', 'EFIBOOT.IMG', 'INITRD.IMG',
    'PYTHON.IMG', 'PYRION.IMG', 'VMLINUZ', 'README.TXT'
)
CPIO_NAMES = ('PYTHON', 'PYRION')
META_DIR = '.pyrion_boot'
CONFIG = 'BOOT_CONFIG.json'
MAX_ISO_SECTORS = 0xffffffff
ISO_NAME = 'PYRION_OS.iso'

# ===== MOTOR DE EXTRACCION ISO9660 Y CPIO =====

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



def read_u32(blob, off):
    return struct.unpack_from("<I", blob, off)[0]


def iso_entries(fh, extent, length):
    """Itera registros ISO9660 y devuelve (nombre, sector, tamano, pos, dir)."""
    pos = extent * SECTOR
    limit = pos + length
    while pos < limit:
        fh.seek(pos)
        n = fh.read(1)
        if not n:
            raise EOFError("Directorio ISO truncado")
        size = n[0]
        if not size:
            pos = (pos // SECTOR + 1) * SECTOR
            continue
        rec = n + fh.read(size - 1)
        if len(rec) != size or size < 34:
            raise ValueError("Registro ISO9660 corrupto")
        nm = rec[33:33 + rec[32]]
        if nm not in (b"\x00", b"\x01"):
            yield (nm.decode("ascii").split(";")[0], read_u32(rec, 2),
                   read_u32(rec, 10), pos, bool(rec[25] & 2))
        pos += size


def iso_layout(fh):
    fh.seek(0, os.SEEK_END)
    length = fh.tell()
    if length % SECTOR:
        raise ValueError("La ISO original no esta alineada a sectores ISO9660")
    fh.seek(16 * SECTOR)
    pvd = fh.read(SECTOR)
    if len(pvd) != SECTOR or pvd[:7] != b"\x01CD001\x01":
        raise ValueError("ISO9660 no compatible: falta descriptor principal")
    root_sector = read_u32(pvd, 158)
    root_length = read_u32(pvd, 166)
    folders = list(iso_entries(fh, root_sector, root_length))
    boot_dirs = [r for r in folders if r[0].upper() == "BOOT" and r[4]]
    if len(boot_dirs) != 1:
        raise ValueError("No se encontro un unico directorio BOOT en la ISO")
    bdir = boot_dirs[0]
    items = {e[0].upper(): e for e in iso_entries(fh, bdir[1], bdir[2]) if not e[4]}
    if not all(n in items for n in NEEDED):
        raise ValueError("Faltan componentes PYRION en BOOT/: " + str(sorted(set(NEEDED) - set(items))))
    fh.seek(17 * SECTOR)
    bootrec = fh.read(SECTOR)
    if bootrec[:7] != b"\x00CD001\x01" or b"EL TORITO SPECIFICATION" not in bootrec[:64]:
        raise ValueError("La ISO no contiene registro de arranque El Torito compatible")
    catalog_lba = read_u32(bootrec, 71)
    if catalog_lba < 18 or catalog_lba >= length // SECTOR:
        raise ValueError("Catalogo de arranque El Torito invalido")
    fh.seek(catalog_lba * SECTOR)
    catalog = fh.read(SECTOR)
    if catalog[0] != 1 or catalog[30:32] != b"\x55\xaa":
        raise ValueError("Catalogo de arranque no valido")
    boot_positions = {}
    for name in ("BIOSBOOT.IMG", "EFIBOOT.IMG"):
        old_lba = items[name][1]
        found = [catalog_lba * SECTOR + i + 8 for i in range(32, SECTOR, 32)
                 if catalog[i] == 0x88 and read_u32(catalog, i + 8) == old_lba]
        if len(found) != 1:
            raise ValueError("No se encontro una referencia El Torito unica para " + name)
        boot_positions[name] = found[0]
    # No se gestionan descriptores Joliet, para evitar referencias a archivos obsoletas.
    for sec in range(18, 32):
        fh.seek(sec * SECTOR)
        vd = fh.read(7)
        if vd[1:6] != b"CD001" or vd[0] == 255:
            break
        if vd[0] == 2:
            raise ValueError("ISO con descriptor Joliet: esta version no permite reconstruirla")
    return items, boot_positions



def hash_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as fh:
        for part in iter(lambda: fh.read(BLOQUE), b''):
            digest.update(part)
    return digest.hexdigest()


def guardar_arranque(iso, destino):
    """Captura la cabecera ISO, catalogo El Torito y bytes no indexados.

    La metadata preserva sectores de control y espaciado no visibles en
    ISO9660. El empaquetador puede reconstruir una ISO sin abrir la original.
    """
    private = destino / META_DIR
    private.mkdir(parents=True, exist_ok=False)
    with iso.open('rb') as fh:
        entries, boot_positions = iso_layout(fh)
        fh.seek(0, os.SEEK_END)
        image_size = fh.tell()
        fh.seek(16 * SECTOR)
        pvd = fh.read(SECTOR)
        fh.seek(17 * SECTOR)
        boot_desc = fh.read(SECTOR)
        cat_sector = read_u32(boot_desc, 71)
        fh.seek(cat_sector * SECTOR)
        cat = fh.read(SECTOR)
        fh.seek(0)
        system_area = fh.read(16 * SECTOR)

        root_start, root_size = read_u32(pvd, 158), read_u32(pvd, 166)
        root_items = list(iso_entries(fh, root_start, root_size))
        if [(x[0], x[4]) for x in root_items] != [('BOOT', True)]:
            raise ValueError('Esta ISO tiene contenido fuera de BOOT/; no se omitira silenciosamente')
        bootdir = root_items[0]
        internal_items = list(iso_entries(fh, bootdir[1], bootdir[2]))
        if {e[0].upper() for e in internal_items} != set(NEEDED) or any(e[4] for e in internal_items):
            raise ValueError('La ISO contiene archivos inesperados en BOOT/')

        ordered = sorted(entries.values(), key=lambda e: e[1])
        first_sector = ordered[0][1]
        if first_sector <= cat_sector:
            raise ValueError('Imagen ISO incompatible: archivos superpuestos a catalogo El Torito')
        fh.seek(0)
        prefix = fh.read(first_sector * SECTOR)
        (private / 'layout.bin').write_bytes(prefix)
        prev = first_sector
        file_info = []
        for item in ordered:
            name, sector, size, record_offset, _isdir = item
            gap_sectors = sector - prev
            if gap_sectors < 0:
                raise ValueError('Archivos ISO solapados: ' + name)
            gap_file = None
            if gap_sectors:
                fh.seek(prev * SECTOR)
                gap = fh.read(gap_sectors * SECTOR)
                if len(gap) != gap_sectors * SECTOR:
                    raise EOFError('Truncamiento al leer relleno ISO')
                if any(gap):
                    gap_file = 'gap_antes_' + name + '.bin'
                    (private / gap_file).write_bytes(gap)
            dest_file = destino / name
            if not dest_file.exists():
                raise ValueError('No se extrajo archivo esperado: ' + name)
            file_info.append({
                'name': name,
                'sector_original': sector,
                'size_original': size,
                'record_offset': record_offset,
                'sha256_original': hash_file(dest_file),
                'gap_sectors': gap_sectors,
                'gap_file': gap_file,
            })
            prev = sector + (size + SECTOR - 1) // SECTOR
        trailing_sectors = image_size // SECTOR - prev
        trailing_file = None
        if trailing_sectors < 0:
            raise ValueError('Archivos superpuestos al final de la ISO')
        if trailing_sectors:
            fh.seek(prev * SECTOR)
            tail = fh.read(trailing_sectors * SECTOR)
            if any(tail):
                trailing_file = 'trailing.bin'
                (private / trailing_file).write_bytes(tail)

        el_torito = []
        for name, offset in sorted(boot_positions.items()):
            entry_offset = offset - 8 - cat_sector * SECTOR
            record = cat[entry_offset:entry_offset + 32]
            platform = 0
            for ptr in range(0, entry_offset, 32):
                if cat[ptr] in (0x90, 0x91):
                    platform = cat[ptr + 1]
            el_torito.append({
                'image': name,
                'catalog_lba_field_offset': offset,
                'bootable': record[0] == 0x88,
                'emulation': record[1],
                'load_segment': struct.unpack_from('<H', record, 2)[0],
                'sector_count_512': struct.unpack_from('<H', record, 6)[0],
                'platform_id': platform,
            })
        for name in CPIO_NAMES:
            shutil.copyfile(destino / (name + '.IMG'),
                            private / (name + '.original.img'))

    meta = {
        'schema': 'pyrion-os-iso-boot-v1',
        'original_iso_name': iso.name,
        'original_iso_sha256': hash_file(iso),
        'original_iso_bytes': image_size,
        'sector_bytes': SECTOR,
        'layout_file': META_DIR + '/layout.bin',
        'layout_sha256': hashlib.sha256(prefix).hexdigest(),
        'files_start_sector': first_sector,
        'volume_id': pvd[40:72].decode('ascii', 'replace').strip(),
        'volume_descriptor': {'pvd_lba': 16, 'eltorito_record_lba': 17,
                              'catalog_lba': cat_sector,
                              'root_directory_lba': root_start,
                              'boot_directory_lba': bootdir[1]},
        'bios_uefi': el_torito,
        'system_area': {
            'mbr_signature': system_area[510:512].hex(),
            'nonzero_bytes': sum(b != 0 for b in system_area),
            'sha256': hashlib.sha256(system_area).hexdigest(),
        },
        'files': file_info,
        'trailing_sectors': trailing_sectors,
        'trailing_file': trailing_file,
        'images_originales': {
            name: META_DIR + '/' + name + '.original.img' for name in CPIO_NAMES
        },
        'nota': 'El empaquetador usa src/ y estos metadatos; no necesita la ISO original.',
    }
    (destino / CONFIG).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + '\n',
                                   encoding='utf-8')
    print('  [BOOT] Catalogo El Torito, cabecera, mapas de sectores y datos extra guardados.')
    print('  [CONFIG] src/' + CONFIG)
    print('  [BACKUP CPIO] Fuentes binarias originales en src/' + META_DIR)
    return meta

# ===== MOTOR DE EMPAQUETADO CPIO E ISO9660 =====

def info(message):
    print(message, flush=True)


def set_733(fh, offset, number):
    fh.seek(offset)
    fh.write(struct.pack("<I", number) + struct.pack(">I", number))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get_iso_file(fh, entry):
    _, sector, size, _, _ = entry
    fh.seek(sector * SECTOR)
    data = fh.read(size)
    if len(data) != size:
        raise EOFError("Imagen interna truncada")
    return data


def cpio_iter(payload):
    """Devuelve registros newc, preservando bytes exactos de sus metadatos."""
    pos = 0
    while pos + 110 <= len(payload):
        start = pos
        hdr = payload[pos:pos + 110]
        if hdr[:6] not in (b"070701", b"070702"):
            raise ValueError("CPIO no es formato newc")
        name_len = int(hdr[94:102], 16)
        body_len = int(hdr[54:62], 16)
        if not (0 < name_len <= 32768):
            raise ValueError("CPIO corrupto: longitud de nombre invalida")
        raw = payload[pos + 110:pos + 110 + name_len]
        if len(raw) != name_len or raw[-1:] != b"\0":
            raise ValueError("CPIO corrupto: nombre invalido")
        name = raw[:-1].decode("utf-8")
        body_start = (pos + 110 + name_len + 3) & ~3
        body_end = body_start + body_len
        next_pos = (body_end + 3) & ~3
        if next_pos > len(payload):
            raise ValueError("CPIO truncado: " + name)
        yield name, hdr, payload[body_start:body_end], payload[start:next_pos]
        pos = next_pos
        if name == "TRAILER!!!":
            return
    raise ValueError("CPIO sin TRAILER!!!")


def cpio_record(name, hdr, data):
    name_raw = name.encode("utf-8") + b"\0"
    header = bytearray(hdr)
    header[54:62] = ("%08x" % len(data)).encode("ascii")
    header[94:102] = ("%08x" % len(name_raw)).encode("ascii")
    if header[:6] == b"070702":
        header[102:110] = ("%08x" % (sum(data) & 0xffffffff)).encode("ascii")
    result = bytes(header) + name_raw
    result += b"\0" * (-len(result) % 4)
    result += data + b"\0" * (-len(data) % 4)
    return result


def new_header(mode, body, inode):
    now = int(time.time())
    numbers = (inode, mode, 0, 0, 1, now, len(body), 0, 0, 0, 0, 0, 0)
    # El campo namesize se completa en cpio_record.
    return b"070701" + b"".join(("%08x" % x).encode("ascii") for x in numbers)


def src_tree(directory):
    """Convierte una carpeta Windows en registros CPIO con enlaces restaurados."""
    if not directory.is_dir():
        raise ValueError("No existe la carpeta requerida: " + str(directory))
    data = {}
    for root, dirs, files in os.walk(directory, followlinks=False):
        r = Path(root)
        rel = r.relative_to(directory)
        if rel.parts:
            name = rel.as_posix()
            data[name] = (0o040755, b"")
        for d in dirs[:]:
            p = r / d
            if p.is_symlink():
                link = os.readlink(p).encode("utf-8")
                data[(p.relative_to(directory)).as_posix()] = (0o120777, link)
                dirs.remove(d)
        for filename in files:
            path = r / filename
            name = path.relative_to(directory).as_posix()
            if path.is_symlink():
                data[name] = (0o120777, os.readlink(path).encode("utf-8"))
            elif filename.endswith(".symlink.txt"):
                target = name[:-len(".symlink.txt")]
                data[target] = (0o120777, path.read_bytes())
            elif filename.endswith(".special.txt"):
                # La metadata original (rdev, uid, nlink...) se mantiene desde ISO.
                data[name[:-len(".special.txt")]] = (0, None)
            else:
                mode = 0o100644
                if os.name != "nt" and os.access(path, os.X_OK):
                    mode = 0o100755
                elif name.endswith((".sh", ".so", ".bin")) or name.startswith(("bin/", "sbin/", "usr/bin/", "usr/sbin/")):
                    mode = 0o100755
                data[name] = (mode, path.read_bytes())
    return data


def build_cpio(original, src):
    raw = gzip.decompress(original)
    old = list(cpio_iter(raw))
    nodes = src_tree(src)
    current = bytearray()
    changed = False
    copied = set()
    base_names = {nm for nm, _, _, _ in old}
    for name, hdr, body, record in old:
        if name == "TRAILER!!!":
            continue
        if name in (".", "./"):
            current.extend(record)
            continue
        if name in nodes:
            mode, candidate = nodes[name]
            old_kind = int(hdr[14:22], 16) & 0o170000
            if candidate is None:
                if old_kind in (0o100000, 0o040000, 0o120000):
                    raise ValueError("Marcador .special.txt no corresponde a archivo especial: " + name)
                candidate = body
                mode = int(hdr[14:22], 16)
            elif mode & 0o170000 != old_kind:
                changed = True
                # Cambio de tipo: no usar metadatos del tipo anterior.
                hdr = new_header(mode, candidate, len(copied) + 1)
            if body == candidate and (mode & 0o170000) == old_kind:
                current.extend(record)
            else:
                changed = True
                current.extend(cpio_record(name, hdr, candidate))
            copied.add(name)
        else:
            changed = True  # Eliminacion intencional del archivo.
    for name in sorted(nodes):
        if name in copied or name in base_names:
            continue
        mode, body = nodes[name]
        if body is None:
            raise ValueError("No es posible agregar dispositivo nuevo desde .special.txt: " + name)
        current.extend(cpio_record(name, new_header(mode, body, len(copied) + 100000), body))
        copied.add(name)
        changed = True
    if not changed:
        return None, False
    trailer = next((item for item in old if item[0] == "TRAILER!!!"), None)
    if trailer is None:
        raise ValueError("Archivo CPIO original sin fin")
    current.extend(trailer[3])
    current.extend(b"\0" * (-len(current) % 512))
    rebuilt = gzip.compress(bytes(current), compresslevel=9, mtime=0)
    # Verificacion de que la imagen puede volver a ser leida.
    test = list(cpio_iter(gzip.decompress(rebuilt)))
    expected = set(nodes) | ({"."} if "." in base_names else set()) | \
               ({"./"} if "./" in base_names else set())
    actual = {r[0] for r in test if r[0] != "TRAILER!!!"}
    if actual != expected:
        raise ValueError("Fallo interno: faltan entradas en el CPIO reconstruido. "
                         "Faltan: %s; adicionales: %s" %
                         (sorted(expected - actual)[:5], sorted(actual - expected)[:5]))
    return rebuilt, True



def _need(cond, reason):
    if not cond:
        raise ValueError(reason)


def _copy_gaps(output, base, file_name, sectors):
    length = sectors * SECTOR
    if file_name:
        data = (base / file_name).read_bytes()
        _need(len(data) == length, 'Relleno de arranque alterado: ' + file_name)
        output.write(data)
    else:
        # Los huecos sin contenido se conservaran llenos de cero.
        while length:
            n = min(length, BLOQUE)
            output.write(b'\x00' * n)
            length -= n


def leer_proyecto(src):
    """Comprueba que toda la informacion de arranque reside en src/."""
    wanted = {'PYRION', 'PYTHON', 'BIOSBOOT.IMG', 'EFIBOOT.IMG',
              'INITRD.IMG', 'README.TXT', 'VMLINUZ', CONFIG, META_DIR}
    _need(src.is_dir(), 'No se encontro carpeta src/ junto al script')
    for name in wanted:
        _need((src / name).exists(), 'Falta src/' + name)
    for name in CPIO_NAMES:
        _need((src / name).is_dir(), 'No es directorio: src/' + name)
    for name in ('BIOSBOOT.IMG', 'EFIBOOT.IMG', 'INITRD.IMG', 'README.TXT', 'VMLINUZ'):
        _need((src / name).is_file(), 'No es archivo: src/' + name)
    meta = json.loads((src / CONFIG).read_text(encoding='utf-8'))
    _need(meta.get('schema') == 'pyrion-os-iso-boot-v1',
          'BOOT_CONFIG.json no es compatible; vuelve a extraer con el extractor nuevo')
    _need(meta.get('sector_bytes') == SECTOR, 'Tamano de sector ISO no soportado')
    private = src / META_DIR
    raw = (private / 'layout.bin').read_bytes()
    _need(hashlib.sha256(raw).hexdigest() == meta['layout_sha256'],
          'La plantilla de arranque ha sido alterada')
    _need(len(raw) == meta['files_start_sector'] * SECTOR,
          'Longitud de la plantilla ISO incongruente')
    _need(raw[16 * SECTOR:16 * SECTOR + 7] == b'\x01CD001\x01',
          'No es plantilla de ISO9660 PYRION')
    _need(raw[17 * SECTOR:17 * SECTOR + 7] == b'\x00CD001\x01',
          'Falta registro de arranque El Torito')
    _need(raw[18 * SECTOR:18 * SECTOR + 7] == b'\xffCD001\x01',
          'El descriptor terminador no coincide con PYRION')
    files = meta['files']
    _need(len(files) == len(NEEDED), 'Numero de archivos BOOT incoherente')
    _need(set(e['name'] for e in files) == set(NEEDED),
          'Nombres de archivos BOOT incoherentes')
    offsets = set()
    for entry in files:
        name = entry['name']
        pos = int(entry['record_offset'])
        _need(pos >= 0 and pos + 34 <= len(raw) and pos not in offsets,
              'Registro ISO9660 fuera del area protegida: ' + name)
        offsets.add(pos)
        rec_len = raw[pos]
        _need(pos + rec_len <= len(raw) and rec_len >= 34,
              'Registro ISO9660 invalido: ' + name)
        n = raw[pos + 33:pos + 33 + raw[pos + 32]].decode('ascii').split(';')[0]
        _need(n == name, 'BOOT_CONFIG apunta a otra entrada: ' + name)
        _need(read_u32(raw, pos + 2) == entry['sector_original'],
              'LBA original incompatible con cabecera ISO: ' + name)
        _need(read_u32(raw, pos + 10) == entry['size_original'],
              'Tamano original incompatible con cabecera ISO: ' + name)
        _need(0 <= int(entry['gap_sectors']) < 65536,
              'Cantidad de sectores entre archivos sospechosa: ' + name)
    _need(int(meta['trailing_sectors']) < 65536,
          'Tamano de relleno final sospechoso')
    boot_lba = meta['volume_descriptor']['catalog_lba']
    _need(read_u32(raw, 17 * SECTOR + 71) == boot_lba,
          'El catalogo El Torito difiere del registrado')
    _need({a['image'] for a in meta['bios_uefi']} == {'BIOSBOOT.IMG', 'EFIBOOT.IMG'},
          'Solo se acepta BIOS y UEFI del layout original')
    for boot in meta['bios_uefi']:
        offset = int(boot['catalog_lba_field_offset'])
        _need(boot_lba * SECTOR <= offset < (boot_lba + 1) * SECTOR,
              'Referencia El Torito fuera del catalogo')
        _need(boot['bootable'], 'Entrada de arranque deshabilitada')
        original = next(x for x in files if x['name'] == boot['image'])
        _need(read_u32(raw, offset) == original['sector_original'],
              'Catalogo original difiere de la entrada: ' + boot['image'])
    for name in CPIO_NAMES:
        base_img = private / (name + '.original.img')
        _need(base_img.is_file(), 'Falta imagen original CPIO: ' + str(base_img))
        entry = next(x for x in files if x['name'] == name + '.IMG')
        _need(sha256(base_img) == entry['sha256_original'],
              'CPIO base danado: ' + name)
    for name in ('EFIBOOT.IMG', 'INITRD.IMG'):
        entry = next(x for x in files if x['name'] == name)
        _need(sha256(src / name) == entry['sha256_original'],
              name + ' cambio. Por seguridad, no se permite alterar BIOS/UEFI o INITRD aqui.')
    bios = next(x for x in files if x['name'] == 'BIOSBOOT.IMG')
    _need((src / 'BIOSBOOT.IMG').stat().st_size == bios['size_original'],
          'BIOSBOOT.IMG debe conservar su longitud original')
    return meta, raw


def compilar_imagenes(src):
    """Reempaqueta solo CPIO editables y mantiene intactos los demas."""
    bases = {}
    modifications = []
    for name in CPIO_NAMES:
        base = (src / META_DIR / (name + '.original.img')).read_bytes()
        nuevo, changed = build_cpio(base, src / name)
        bases[name + '.IMG'] = nuevo if changed else base
        print('  [%s] %s.IMG' % ('MODIFICADO' if changed else 'SIN CAMBIOS', name))
        if changed:
            modifications.append(name + '.IMG')
    for name in ('BIOSBOOT.IMG', 'EFIBOOT.IMG', 'INITRD.IMG', 'README.TXT', 'VMLINUZ'):
        bases[name] = (src / name).read_bytes()
    return bases, modifications


def generar_iso(temp, src, meta, layout, contents):
    """Genera ISO9660 desde cero con metadata capturada, no lee vieja ISO."""
    files = meta['files']
    new_positions = {}
    print('\nEscribiendo ISO nueva desde src (sin abrir ISO antigua)...')
    with temp.open('w+b') as out:
        out.write(layout)
        for entry in files:
            name = entry['name']
            _copy_gaps(out, src / META_DIR, entry.get('gap_file'), int(entry['gap_sectors']))
            _need(out.tell() % SECTOR == 0, 'Desalineacion interna al escribir ' + name)
            new_sector = out.tell() // SECTOR
            payload = contents[name]
            _need(len(payload) < 2 ** 32, 'Archivo demasiado grande: ' + name)
            out.write(payload)
            out.write(b'\x00' * (-len(payload) % SECTOR))
            new_positions[name] = (new_sector, len(payload))
            print('  %s: sector %d, %d bytes' % (name, new_sector, len(payload)))
        _copy_gaps(out, src / META_DIR,
                   meta.get('trailing_file'), int(meta['trailing_sectors']))
        sectors = out.tell() // SECTOR
        _need(sectors < MAX_ISO_SECTORS, 'ISO demasiado grande para ISO9660')
        # Directorio BOOT: ubicacion y longitud de cada archivo.
        for entry in files:
            pos = int(entry['record_offset'])
            sector, length = new_positions[entry['name']]
            set_733(out, pos + 2, sector)
            set_733(out, pos + 10, length)
        # Catalogo de arranque El Torito: actualizar LBA BIOS y EFI.
        for boot in meta['bios_uefi']:
            sector, length = new_positions[boot['image']]
            out.seek(int(boot['catalog_lba_field_offset']))
            out.write(struct.pack('<I', sector))
        # Tamano del volumen en los dos endianness de ISO9660.
        set_733(out, 16 * SECTOR + 80, sectors)
        out.flush()
        os.fsync(out.fileno())
    return new_positions


def validar_iso(path, src, contents, meta, new_positions):
    print('\nValidando integridad, directorios y arranque BIOS/UEFI...')
    with path.open('rb') as fh:
        entries, boot_positions = iso_layout(fh)
        _need(path.stat().st_size % SECTOR == 0, 'ISO sin alineacion ISO9660')
        _need(set(entries) == set(NEEDED), 'Directorios ISO9660 incompletos')
        fh.seek(16 * SECTOR + 80)
        _need(read_u32(fh.read(4), 0) == path.stat().st_size // SECTOR,
              'Longitud de volumen incorrecta')
        for entry in meta['files']:
            name = entry['name']
            rec = entries[name]
            expected_sector, expected_size = new_positions[name]
            _need(rec[1] == expected_sector and rec[2] == expected_size,
                  'Ubicacion o tamano incorrectos: ' + name)
            _need(rec[1] * SECTOR + rec[2] <= path.stat().st_size,
                  'El archivo sobrepasa la ISO: ' + name)
            _need(get_iso_file(fh, rec) == contents[name],
                  'Los bytes ISO no coinciden: ' + name)
            if name in ('PYRION.IMG', 'PYTHON.IMG'):
                list(cpio_iter(gzip.decompress(contents[name])))
        for name in ('BIOSBOOT.IMG', 'EFIBOOT.IMG'):
            _need(name in boot_positions, 'Falta entrada El Torito: ' + name)
            fh.seek(boot_positions[name])
            _need(read_u32(fh.read(4), 0) == new_positions[name][0],
                  'Catalogo El Torito con sector incorrecto: ' + name)
    same_hash = sha256(path) == meta['original_iso_sha256']
    print('  Estructura ISO y catalogo El Torito correctos.')
    if same_hash:
        print('  ISO regenerada es IDENTICA bit a bit al original.')
    else:
        print('  ISO nueva diferente del original (cambios incorporados).')
    return same_hash

# ===== OPERACIONES SEGURAS / ATOMICAS =====


def extraer_desde_iso(iso: Path, src: Path, sobrescribir: bool = False) -> None:
    """Extraer a carpeta temporal y sustituir src solo cuando todo resulte bien."""
    iso = iso.expanduser().resolve()
    src = src.expanduser().resolve()
    if not iso.is_file():
        raise FileNotFoundError('No existe la ISO: ' + str(iso))
    if src == iso or src in iso.parents:
        raise ValueError('La ISO original no puede estar dentro de la carpeta src que sera reemplazada')
    if src.exists() and not sobrescribir:
        raise FileExistsError('La carpeta src ya existe. Confirma la sustitucion para extraer nuevamente.')
    if src.exists() and not src.is_dir():
        raise ValueError('Existe un archivo llamado src; se necesita una carpeta.')
    if not src.parent.is_dir():
        raise FileNotFoundError('No existe el directorio de trabajo: ' + str(src.parent))
    if src == src.parent:
        raise ValueError('Selecciona una carpeta src real, no la raiz del disco')
    staged = Path(tempfile.mkdtemp(prefix='.pyrion-extraer-', dir=src.parent))
    backup = None
    terminado = False
    try:
        print('EXTRAYENDO:', iso, '=>', src, flush=True)
        extraer_iso(iso, staged)
        boot = staged / 'BOOT'
        if not boot.is_dir():
            raise ValueError('La ISO no contiene el directorio BOOT/')
        for name in NEEDED:
            fuente = boot / name
            if not fuente.is_file():
                raise ValueError('Falta BOOT/' + name + ' en la ISO')
            shutil.move(str(fuente), str(staged / name))
        boot.rmdir()
        guardar_arranque(iso, staged)
        print('\n[CPIO] Extrayendo carpetas editables PYRION y PYTHON...', flush=True)
        for name in CPIO_NAMES:
            original = staged / (name + '.IMG')
            result = extraer_cpio_gzip(original, staged / name)
            if result is None:
                raise ValueError(name + '.IMG no usa un formato CPIO gzip compatible')
            original.unlink()
        if src.exists():
            backup = Path(tempfile.mkdtemp(prefix='.pyrion-src-anterior-', dir=src.parent))
            backup.rmdir()
            os.replace(src, backup)
        try:
            os.replace(staged, src)
            terminado = True
        except OSError:
            if backup is not None and backup.exists() and not src.exists():
                os.replace(backup, src)
                backup = None
            raise
        print('\nOK: src/ extraida correctamente; se conservaron metadatos BIOS/UEFI.', flush=True)
        print('Puedes modificar src/PYRION y src/PYTHON. No borres BOOT_CONFIG.json ni .pyrion_boot/.', flush=True)
    finally:
        if staged.exists():
            shutil.rmtree(staged, ignore_errors=True)
        if backup is not None and backup.exists() and terminado:
            try:
                shutil.rmtree(backup)
            except OSError as exc:
                print('AVISO: no se pudo limpiar la carpeta anterior: ' + str(exc), flush=True)
        elif backup is not None and backup.exists() and not src.exists():
            os.replace(backup, src)


def empaquetar_desde_src(src: Path, iso: Path) -> None:
    """NO usa la ISO anterior para construir la nueva: solo src + boot metadata."""
    src = src.expanduser().resolve()
    iso = iso.expanduser().resolve()
    if src in iso.parents:
        raise ValueError('La ISO de salida debe estar fuera de src para no alterar los archivos fuente')
    if not iso.parent.is_dir():
        raise FileNotFoundError('No existe el directorio de salida: ' + str(iso.parent))
    print('PYRION OS - reconstruccion autonoma desde src/', flush=True)
    print('La ISO anterior NO se utiliza como fuente.', flush=True)
    meta, layout = leer_proyecto(src)
    contents, changes = compilar_imagenes(src)
    temp = None
    try:
        fd, tempname = tempfile.mkstemp(prefix='.pyrion-iso-nueva-', suffix='.tmp', dir=iso.parent)
        os.close(fd)
        temp = Path(tempname)
        positions = generar_iso(temp, src, meta, layout, contents)
        validar_iso(temp, src, contents, meta, positions)
        os.replace(temp, iso)
        temp = None
        print('\nOK: ISO creada/reemplazada:', iso, flush=True)
        print('Imagenes internas editadas:', ', '.join(changes) if changes else 'ninguna', flush=True)
        print('Tamano: %.2f MiB' % (iso.stat().st_size / 1048576), flush=True)
        print('IMPORTANTE: prueba el arranque real en BIOS y UEFI.', flush=True)
    finally:
        if temp is not None:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass


# ===== INTERFAZ GRAFICA (TKINTER INCLUIDO EN PYTHON) =====


class _SalidaCola:
    def __init__(self, cola):
        self.cola = cola

    def write(self, texto):
        if texto:
            self.cola.put(('log', str(texto)))
        return len(texto)

    def flush(self):
        pass


def iniciar_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    class PyrionStudio:
        BG = '#09131f'
        PANEL = '#101f30'
        PANEL2 = '#15283d'
        FG = '#e6f4ff'
        MUTED = '#93a9bb'
        CYAN = '#40e0ef'
        SUCCESS = '#8cffca'

        def __init__(self, raiz):
            self.raiz = raiz
            raiz.title('PYRION OS  |  ISO STUDIO')
            raiz.configure(bg=self.BG)
            raiz.geometry('865x660')
            raiz.minsize(710, 530)
            self.cola = queue.Queue()
            self.ocupado = False
            self.directorio = tk.StringVar(value=str(Path(__file__).resolve().parent))
            self.info_rutas = tk.StringVar()
            self.estado = tk.StringVar(value='Listo para trabajar')
            self._estilo()
            self._construir()
            self.directorio.trace_add('write', lambda *_: self._actualizar_rutas())
            self._actualizar_rutas()
            raiz.after(80, self._leer_cola)
            raiz.protocol('WM_DELETE_WINDOW', self._cerrar)

        def _estilo(self):
            estilo = ttk.Style(self.raiz)
            estilo.theme_use('clam')
            estilo.configure('Pyrion.Horizontal.TProgressbar', troughcolor=self.PANEL,
                             background=self.CYAN, bordercolor=self.BG,
                             lightcolor=self.CYAN, darkcolor=self.CYAN)

        def _construir(self):
            c = tk.Frame(self.raiz, bg=self.BG)
            c.pack(fill='both', expand=True, padx=23, pady=19)
            tk.Label(c, text='PYRION  /  ISO STUDIO', bg=self.BG, fg=self.CYAN,
                     font=('Segoe UI', 22, 'bold')).pack(anchor='w')
            tk.Label(c, text='Extrae, edita y reconstruye tu ISO con arranque BIOS y UEFI',
                     bg=self.BG, fg=self.MUTED, font=('Segoe UI', 10)).pack(anchor='w', pady=(0, 16))

            tarjeta = tk.Frame(c, bg=self.PANEL, padx=17, pady=15)
            tarjeta.pack(fill='x')
            tk.Label(tarjeta, text='CARPETA DE TRABAJO', bg=self.PANEL, fg=self.CYAN,
                     font=('Segoe UI', 9, 'bold')).pack(anchor='w')
            fila = tk.Frame(tarjeta, bg=self.PANEL)
            fila.pack(fill='x', pady=(7, 7))
            self.entrada = tk.Entry(fila, textvariable=self.directorio, bg=self.PANEL2,
                                    fg=self.FG, insertbackground=self.FG,
                                    relief='flat', highlightthickness=1,
                                    highlightcolor=self.CYAN, highlightbackground='#35516a',
                                    font=('Consolas', 10))
            self.entrada.pack(side='left', fill='x', expand=True, ipady=9)
            self.explorar = self._boton(fila, 'Examinar', self._examinar,
                                      self.PANEL2, self.FG, ancho=11)
            self.explorar.pack(side='left', padx=(10, 0))
            tk.Label(tarjeta, textvariable=self.info_rutas, bg=self.PANEL,
                     fg=self.MUTED, anchor='w', justify='left',
                     font=('Consolas', 9)).pack(fill='x', pady=(5, 0))

            acciones = tk.Frame(c, bg=self.BG)
            acciones.pack(fill='x', pady=(17, 12))
            self.b_extraer = self._boton(acciones, '1  EXTRAER ISO  →  SRC',
                                        self._extraer, '#136a75', 'white', ancho=24)
            self.b_extraer.pack(side='left', fill='x', expand=True, padx=(0, 7))
            self.b_empaquetar = self._boton(acciones, '2  EMPAQUETAR SRC  →  ISO',
                                           self._empaquetar, '#235078', 'white', ancho=27)
            self.b_empaquetar.pack(side='left', fill='x', expand=True, padx=(7, 0))

            herramientas = tk.Frame(c, bg=self.BG)
            herramientas.pack(fill='x', pady=(0, 13))
            self.b_abrir = self._boton(herramientas, 'Abrir carpeta src', self._abrir_src,
                                     self.PANEL, self.FG, ancho=18)
            self.b_abrir.pack(side='left')
            self.b_limpiar = self._boton(herramientas, 'Limpiar registro', self._limpiar,
                                       self.PANEL, self.FG, ancho=18)
            self.b_limpiar.pack(side='left', padx=8)
            tk.Label(herramientas, text='No requiere 7-Zip ni WSL', bg=self.BG,
                     fg=self.MUTED, font=('Segoe UI', 9)).pack(side='right')

            registro = tk.Frame(c, bg=self.PANEL, padx=11, pady=11)
            registro.pack(fill='both', expand=True)
            superior = tk.Frame(registro, bg=self.PANEL)
            superior.pack(fill='x', pady=(0, 6))
            tk.Label(superior, text='REGISTRO DE OPERACIONES', bg=self.PANEL,
                     fg=self.FG, font=('Segoe UI', 9, 'bold')).pack(side='left')
            tk.Label(superior, text='PYRION OS', bg=self.PANEL, fg=self.MUTED,
                     font=('Segoe UI', 9)).pack(side='right')
            frame_texto = tk.Frame(registro, bg=self.PANEL)
            frame_texto.pack(fill='both', expand=True)
            bar = tk.Scrollbar(frame_texto)
            bar.pack(side='right', fill='y')
            self.texto = tk.Text(frame_texto, bg='#08111b', fg='#c7e8f6',
                                 insertbackground=self.CYAN, selectbackground='#1c6477',
                                 font=('Consolas', 9), wrap='word', borderwidth=0,
                                 state='disabled', yscrollcommand=bar.set, padx=9, pady=9)
            self.texto.pack(side='left', fill='both', expand=True)
            bar.config(command=self.texto.yview)
            self.progreso = ttk.Progressbar(c, mode='indeterminate',
                                           style='Pyrion.Horizontal.TProgressbar')
            self.progreso.pack(fill='x', pady=(12, 6))
            tk.Label(c, textvariable=self.estado, bg=self.BG, fg=self.SUCCESS,
                     font=('Segoe UI', 9)).pack(anchor='w')
            self._escribir('Bienvenido a PYRION ISO Studio.\n'
                           'Usa el boton 1 para generar src/ o el boton 2 para crear PYRION_OS.iso.\n'
                           'Los datos del arranque se almacenan dentro de src/.\n\n')

        def _boton(self, padre, texto, comando, fondo, frente, ancho=18):
            return tk.Button(padre, text=texto, command=comando, bg=fondo, fg=frente,
                             activebackground=self.CYAN, activeforeground='#00111f',
                             disabledforeground='#637480', relief='flat', cursor='hand2',
                             font=('Segoe UI', 10, 'bold'), width=ancho, pady=10)

        def _carpeta(self):
            return Path(self.directorio.get().strip().strip('"')).expanduser().resolve()

        def _actualizar_rutas(self):
            try:
                base = self._carpeta()
                self.info_rutas.set('ISO: ' + str(base / ISO_NAME) +
                                    '\nSRC: ' + str(base / 'src'))
                if not self.ocupado:
                    self.b_extraer.config(state='normal' if (base / ISO_NAME).is_file() else 'disabled')
                    self.b_empaquetar.config(state='normal' if (base / 'src' / CONFIG).is_file() else 'disabled')
                    self.b_abrir.config(state='normal' if (base / 'src').is_dir() else 'disabled')
            except Exception:
                self.info_rutas.set('Introduce una carpeta valida')
                for boton in (self.b_extraer, self.b_empaquetar, self.b_abrir):
                    boton.config(state='disabled')

        def _examinar(self):
            carpeta = filedialog.askdirectory(title='Selecciona la carpeta de PYRION OS',
                                              initialdir=str(self._carpeta()))
            if carpeta:
                self.directorio.set(carpeta)

        def _abrir_src(self):
            ruta = self._carpeta() / 'src'
            if not ruta.is_dir():
                messagebox.showwarning('PYRION OS', 'No existe la carpeta src.')
                return
            try:
                if sys.platform == 'win32':
                    os.startfile(str(ruta))
                elif sys.platform == 'darwin':
                    import subprocess
                    subprocess.Popen(['open', str(ruta)])
                else:
                    import subprocess
                    subprocess.Popen(['xdg-open', str(ruta)])
            except OSError as exc:
                messagebox.showerror('PYRION OS', str(exc))

        def _limpiar(self):
            self.texto.config(state='normal')
            self.texto.delete('1.0', 'end')
            self.texto.config(state='disabled')

        def _escribir(self, message):
            self.texto.config(state='normal')
            self.texto.insert('end', message)
            self.texto.see('end')
            self.texto.config(state='disabled')

        def _ocupacion(self, activado, mensaje=None):
            self.ocupado = activado
            for boton in (self.b_extraer, self.b_empaquetar, self.b_abrir,
                          self.explorar, self.entrada):
                boton.config(state='disabled' if activado else 'normal')
            if activado:
                self.progreso.start(11)
                self.estado.set(mensaje or 'Procesando...')
            else:
                self.progreso.stop()
                self._actualizar_rutas()

        def _trabajo(self, titulo, accion):
            if self.ocupado:
                return
            self._escribir('\n' + '=' * 63 + '\n' + titulo + '\n' + '=' * 63 + '\n')
            self._ocupacion(True, titulo)

            def ejecucion():
                destino = _SalidaCola(self.cola)
                try:
                    with contextlib.redirect_stdout(destino), contextlib.redirect_stderr(destino):
                        accion()
                    self.cola.put(('ok', titulo))
                except Exception as exc:
                    self.cola.put(('error', (titulo, str(exc), traceback.format_exc())))

            threading.Thread(target=ejecucion, daemon=True, name='pyrion-iso-trabajo').start()

        def _extraer(self):
            base = self._carpeta()
            iso, src = base / ISO_NAME, base / 'src'
            if not iso.is_file():
                messagebox.showerror('PYRION OS', 'Falta ' + str(iso))
                return
            if src.exists() and not messagebox.askyesno(
                    'Sobrescribir src',
                    'La carpeta src ya existe.\n\n'
                    'Si continuas, se reemplazara completamente y se perderan\n'
                    'las ediciones guardadas alli.\n\n¿Deseas continuar?',
                    icon='warning'):
                return
            self._trabajo('EXTRAER PYRION_OS.iso A src/',
                          lambda: extraer_desde_iso(iso, src, sobrescribir=True))

        def _empaquetar(self):
            base = self._carpeta()
            src, iso = base / 'src', base / ISO_NAME
            if not (src / CONFIG).is_file():
                messagebox.showerror('PYRION OS',
                                     'Falta src/BOOT_CONFIG.json. Extrae primero la ISO con este programa.')
                return
            self._trabajo('EMPAQUETAR src/ A PYRION_OS.iso',
                          lambda: empaquetar_desde_src(src, iso))

        def _leer_cola(self):
            try:
                while True:
                    tipo, valor = self.cola.get_nowait()
                    if tipo == 'log':
                        self._escribir(valor)
                    elif tipo == 'ok':
                        self._ocupacion(False)
                        self.estado.set('Proceso completado correctamente')
                        self._escribir('\n[OK] Operacion terminada.\n')
                        messagebox.showinfo('PYRION OS', 'Operacion completada correctamente.')
                    elif tipo == 'error':
                        self._ocupacion(False)
                        titulo, texto, _detalle = valor
                        self.estado.set('Error: ' + texto)
                        self._escribir('\n[ERROR] ' + texto + '\n')
                        messagebox.showerror('PYRION OS - ' + titulo, texto)
            except queue.Empty:
                pass
            self.raiz.after(80, self._leer_cola)

        def _cerrar(self):
            if self.ocupado:
                messagebox.showwarning('PYRION OS',
                                       'Hay un proceso en curso. Espera a que termine para cerrar el programa.')
                return
            self.raiz.destroy()

    root = tk.Tk()
    PyrionStudio(root)
    root.mainloop()


def main(argv=None):
    parser = argparse.ArgumentParser(description='PYRION ISO Studio - GUI y consola')
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument('--extraer', action='store_true', help='Extraer ISO a src')
    grupo.add_argument('--empaquetar', action='store_true', help='Crear ISO a partir de src')
    parser.add_argument('--sobrescribir', action='store_true', help='Permitir sustituir la carpeta src existente al extraer')
    parser.add_argument('--directorio', default=None, help='Carpeta que contiene PYRION_OS.iso y src/')
    args = parser.parse_args(argv)
    if not (args.extraer or args.empaquetar):
        try:
            iniciar_gui()
            return 0
        except ImportError as exc:
            print('No se pudo abrir la interfaz. Tkinter no esta disponible: ' + str(exc), file=sys.stderr)
            return 4
        except Exception as exc:
            print('No se pudo iniciar la GUI: ' + str(exc), file=sys.stderr)
            return 4
    carpeta = Path(args.directorio).expanduser().resolve() if args.directorio else Path(__file__).resolve().parent
    try:
        if args.extraer:
            extraer_desde_iso(carpeta / ISO_NAME, carpeta / 'src', args.sobrescribir)
        else:
            empaquetar_desde_src(carpeta / 'src', carpeta / ISO_NAME)
        return 0
    except (OSError, EOFError, ValueError, KeyError, TypeError, struct.error,
            MemoryError, json.JSONDecodeError) as exc:
        print('\nERROR:', exc, file=sys.stderr, flush=True)
        return 2


if __name__ == '__main__':
    sys.exit(main())
