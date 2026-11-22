#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""FUTUREO VJOY LAB: etiquetas PnP reversibles para los hijos HID de VHF.

No cambia el driver, el descriptor HID ni HidD_GetProductString.
Solo prueba SPDRP_FRIENDLYNAME, documentado por Microsoft SetupAPI.
Modo predeterminado: diagnostico, SIN modificar Windows.

Uso: py nombres_pnp.py --status --count 8
     py nombres_pnp.py --apply --count 4
     py nombres_pnp.py --restore
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import sys

BACKUP = (Path(os.environ.get("LOCALAPPDATA") or str(Path.home())) /
          "FUTUREO_VJOY" / "pnp_names_backup.json")
SPDRP_FRIENDLYNAME = 0x0000000C
DIGCF_PRESENT = 0x00000002
DIGCF_ALLCLASSES = 0x00000004
ERROR_NO_MORE_ITEMS = 259
ERROR_NO_PROPERTY = {2, 13, 1168}


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("ClassGuid", GUID),
        ("DevInst", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


def slot_from_id(instance_id: str) -> int | None:
    """Solo hijos HID de los VID/PID asignados al prototipo FUTUREO LAB."""
    match = re.match(r"^HID\\VID_F7A0&PID_210([1-8])(?:[&\\]|$)",
                     instance_id, re.IGNORECASE)
    return int(match.group(1)) if match else None


def label_for_slot(slot: int) -> str:
    if type(slot) is not int or not (1 <= slot <= 8):
        raise ValueError("Puesto no permitido")
    return f"FUTUREO VJOY{slot} - PLAYER {slot}"


def safe_backup_records(raw: object) -> list[dict]:
    """No permitir que un respaldo editado introduzca destinos arbitrarios."""
    if not isinstance(raw, list):
        raise ValueError("Respaldo PnP invalido")
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("Entrada PnP invalida")
        instance_id, previous, intended = (
            item.get("instance_id"), item.get("previous"), item.get("intended"))
        if (not isinstance(instance_id, str) or
                (slot := slot_from_id(instance_id)) is None or
                not isinstance(previous, dict) or
                type(previous.get("exists")) is not bool or
                (previous["exists"] and not isinstance(previous.get("value"), str)) or
                intended != label_for_slot(slot) or
                instance_id.upper() in seen):
            raise ValueError("Respaldo PnP no coincide con FUTUREO LAB")
        seen.add(instance_id.upper())
    return raw


def read_backup() -> list[dict]:
    if not BACKUP.exists():
        return []
    return safe_backup_records(json.loads(BACKUP.read_text(encoding="utf-8")))


def save_backup(rows: list[dict]) -> None:
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    temp = BACKUP.with_suffix(".tmp")
    temp.write_text(json.dumps(rows, indent=2, ensure_ascii=False),
                    encoding="utf-8")
    temp.replace(BACKUP)


def admin() -> bool:
    if os.name != "nt":
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (OSError, AttributeError):
        return False


class WindowsPnP:
    """Operaciones Win32 sobre una lista *presente* de dispositivos, no GUID inventados."""
    def __init__(self):
        if os.name != "nt":
            raise OSError("La API SetupAPI requiere Windows")
        self.setup = ctypes.WinDLL("setupapi", use_last_error=True)
        self.cfg = ctypes.WinDLL("cfgmgr32", use_last_error=True)
        self.setup.SetupDiGetClassDevsW.argtypes = [
            ctypes.c_void_p, wintypes.LPCWSTR, wintypes.HWND, wintypes.DWORD]
        self.setup.SetupDiGetClassDevsW.restype = ctypes.c_void_p
        self.setup.SetupDiEnumDeviceInfo.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(SP_DEVINFO_DATA)]
        self.setup.SetupDiEnumDeviceInfo.restype = wintypes.BOOL
        self.setup.SetupDiGetDeviceInstanceIdW.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA),
            wintypes.LPWSTR, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        self.setup.SetupDiGetDeviceInstanceIdW.restype = wintypes.BOOL
        self.setup.SetupDiGetDeviceRegistryPropertyW.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA),
            wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        self.setup.SetupDiGetDeviceRegistryPropertyW.restype = wintypes.BOOL
        self.setup.SetupDiSetDeviceRegistryPropertyW.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(SP_DEVINFO_DATA),
            wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
        self.setup.SetupDiSetDeviceRegistryPropertyW.restype = wintypes.BOOL
        self.setup.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
        self.setup.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
        self.cfg.CM_Get_Parent.argtypes = [
            ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, wintypes.ULONG]
        self.cfg.CM_Get_Parent.restype = wintypes.ULONG
        self.cfg.CM_Get_Device_IDW.argtypes = [
            wintypes.DWORD, wintypes.LPWSTR, wintypes.ULONG, wintypes.ULONG]
        self.cfg.CM_Get_Device_IDW.restype = wintypes.ULONG
        self.handle = None

    def __enter__(self):
        self.handle = self.setup.SetupDiGetClassDevsW(
            None, None, None, DIGCF_PRESENT | DIGCF_ALLCLASSES)
        if self.handle in (None, ctypes.c_void_p(-1).value):
            raise ctypes.WinError(ctypes.get_last_error())
        return self

    def __exit__(self, *_):
        if self.handle is not None:
            self.setup.SetupDiDestroyDeviceInfoList(self.handle)
            self.handle = None

    def root_ancestor(self, devinst: int, slot: int) -> bool:
        """Un VID/PID por si solo NO prueba que el dispositivo sea FUTUREO."""
        expected = f"ROOT\\FUTJOY{slot:02d}\\"
        node = wintypes.DWORD(devinst)
        visited = set()
        for _ in range(20):
            parent = wintypes.DWORD()
            if self.cfg.CM_Get_Parent(ctypes.byref(parent), node, 0) != 0:
                return False
            if parent.value in visited:
                return False
            visited.add(parent.value)
            path = ctypes.create_unicode_buffer(512)
            if self.cfg.CM_Get_Device_IDW(parent, path, 512, 0) != 0:
                return False
            if path.value.upper().startswith(expected):
                return True
            node = parent
        return False

    def read_name(self, info: SP_DEVINFO_DATA) -> dict:
        regtype = wintypes.DWORD()
        required = wintypes.DWORD()
        value = ctypes.create_unicode_buffer(512)
        found = self.setup.SetupDiGetDeviceRegistryPropertyW(
            self.handle, ctypes.byref(info), SPDRP_FRIENDLYNAME,
            ctypes.byref(regtype), ctypes.byref(value), ctypes.sizeof(value),
            ctypes.byref(required))
        if not found:
            error = ctypes.get_last_error()
            if error in ERROR_NO_PROPERTY:
                return {"exists": False, "value": None}
            raise ctypes.WinError(error)
        if regtype.value != 1:
            raise ValueError("SPDRP_FRIENDLYNAME no es REG_SZ")
        return {"exists": True, "value": value.value}

    def set_name(self, info: SP_DEVINFO_DATA, text: str | None) -> None:
        if text is None:
            data, size = None, 0
        else:
            data = ctypes.create_unicode_buffer(text)
            size = ctypes.sizeof(data)
        if not self.setup.SetupDiSetDeviceRegistryPropertyW(
                self.handle, ctypes.byref(info), SPDRP_FRIENDLYNAME,
                data, size):
            raise ctypes.WinError(ctypes.get_last_error())

    def matched(self, count: int = 8) -> list[dict]:
        results = []
        index = 0
        while True:
            info = SP_DEVINFO_DATA()
            info.cbSize = ctypes.sizeof(SP_DEVINFO_DATA)
            ok = self.setup.SetupDiEnumDeviceInfo(
                self.handle, index, ctypes.byref(info))
            if not ok:
                error = ctypes.get_last_error()
                if error == ERROR_NO_MORE_ITEMS:
                    break
                raise ctypes.WinError(error)
            index += 1
            buf = ctypes.create_unicode_buffer(512)
            needed = wintypes.DWORD()
            ok = self.setup.SetupDiGetDeviceInstanceIdW(
                self.handle, ctypes.byref(info), buf, 512,
                ctypes.byref(needed))
            if not ok:
                raise ctypes.WinError(ctypes.get_last_error())
            identifier = buf.value
            slot = slot_from_id(identifier)
            if slot is None or slot > count:
                continue
            # Verificar ascendencia: nunca alterar dispositivos HID externos.
            if not self.root_ancestor(info.DevInst, slot):
                continue
            results.append({
                "slot": slot,
                "instance_id": identifier,
                "previous": self.read_name(info),
                "info": info,
            })
        return results


def apply(count: int = 8) -> None:
    if not admin():
        raise PermissionError("Se requiere ejecutar como administrador en Windows")
    with WindowsPnP() as pnp:
        matches = pnp.matched(count)
        present = {item["slot"] for item in matches}
        missing = set(range(1, count + 1)) - present
        if missing:
            raise RuntimeError(
                "No se encontraron hijos HID FUTUREO verificados para: " +
                ", ".join(f"P{n}" for n in sorted(missing)) +
                ". No se ha modificado ningun dispositivo.")
        backup = read_backup()
        saved = {row["instance_id"].upper(): row for row in backup}
        pending = []
        for item in matches:
            intended = label_for_slot(item["slot"])
            old = saved.get(item["instance_id"].upper())
            if old:
                current = item["previous"]
                if current != old["previous"] and current != {
                        "exists": True, "value": intended}:
                    raise RuntimeError(
                        "Nombre cambiado por otra app en " + item["instance_id"])
            else:
                pending.append({
                    "instance_id": item["instance_id"],
                    "previous": item["previous"],
                    "intended": intended,
                })
        if pending:
            save_backup(backup + pending)
        for item in matches:
            expected = label_for_slot(item["slot"])
            if item["previous"] != {"exists": True, "value": expected}:
                pnp.set_name(item["info"], expected)
        for item in matches:
            check = pnp.read_name(item["info"])
            if check != {"exists": True, "value": label_for_slot(item["slot"])}:
                raise RuntimeError("Windows no conservo el nombre: " +
                                   item["instance_id"])
        print(f"OK: nombre PnP aplicado a {len(matches)} interfaz(es) HID, P1..P{count}.")
        print("Respaldo guardado:", BACKUP)
        print("Cierra y reabre joy.cpl. Si sigue generico, VHF puede estar")
        print("suministrando directamente ese nombre; NO se modifico el Product String.")


def restore() -> None:
    if not admin():
        raise PermissionError("Se requiere ejecutar como administrador")
    backup = read_backup()
    if not backup:
        print("Sin nombres PnP pendientes de restaurar.")
        return
    remaining = []
    with WindowsPnP() as pnp:
        present = {x["instance_id"].upper(): x for x in pnp.matched(8)}
        for row in backup:
            item = present.get(row["instance_id"].upper())
            if not item:
                remaining.append(row)
                print("No presente o no verificado; pendiente:", row["instance_id"])
                continue
            current = item["previous"]
            if current == row["previous"]:
                continue
            if current != {"exists": True, "value": row["intended"]}:
                remaining.append(row)
                print("Cambio ajeno detectado; no sobrescribir:", row["instance_id"])
                continue
            original = row["previous"]["value"] if row["previous"]["exists"] else None
            pnp.set_name(item["info"], original)
            if pnp.read_name(item["info"]) != row["previous"]:
                remaining.append(row)
                print("No se verifico restauracion:", row["instance_id"])
    if remaining:
        save_backup(remaining)
        print(f"Pendientes: {len(remaining)}. Conservado respaldo {BACKUP}")
    else:
        BACKUP.unlink()
        print("OK: nombres PnP restaurados; respaldo eliminado.")


def status(count: int = 8) -> None:
    with WindowsPnP() as pnp:
        results = pnp.matched(count)
    print("FUTUREO - NOMBRES PnP / SOLO LECTURA")
    for n in range(1, count + 1):
        items = [r for r in results if r["slot"] == n]
        print(f"P{n} | F7A0:{0x2100+n:04X} | {len(items)} interfaz(es) FUTUREO verificada(s)")
        for item in items:
            print("  " + item["instance_id"])
            print("  FriendlyName:", item["previous"]["value"]
                  if item["previous"]["exists"] else "(no definido)")
    print("Nota: FriendlyName PnP, OEMName, HID Product String y joy.cpl")
    print("no siempre usan la misma fuente de nombre.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--apply", action="store_true")
    group.add_argument("--restore", action="store_true")
    group.add_argument("--status", action="store_true")
    parser.add_argument("--count", type=int, choices=range(1, 9), default=8)
    args = parser.parse_args()
    try:
        if args.apply:
            apply(args.count)
        elif args.restore:
            restore()
        else:
            status(args.count)
    except (OSError, ValueError, RuntimeError) as exc:
        print("ERROR:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
