#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Alias reversibles para nombres joy.cpl/DirectInput de FUTUREO VJOY.

No cambia cadenas HID ni instala drivers. Solo ajusta las claves OEM de
VID F7A0 + PID 2101-2108, despues de comprobar dispositivos presentes.
El modo por defecto es diagnostico (sin modificar el Registro).
"""
from __future__ import annotations

import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys

try:
    import winreg
except ImportError:
    winreg = None

VID = 0xF7A0  # ID SOLO DE LABORATORIO: sustituir para distribucion.
PRODUCT_BASE = 0x2100
BASE = r"System\CurrentControlSet\Control\MediaProperties\PrivateProperties"
BACKUP = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FUTUREO_VJOY" / "oem_names_backup.json"


def product_key(slot: int) -> str:
    if type(slot) is not int or slot not in range(1, 9):
        raise ValueError("Puesto invalido")
    return f"VID_{VID:04X}&PID_{PRODUCT_BASE + slot:04X}"


def changes_for_slot(slot: int) -> list[dict]:
    device = product_key(slot)
    label = f"FUTUREO VJOY{slot}"
    return [
        {"hive": "HKCU", "path": rf"{BASE}\Joystick\OEM\{device}",
         "name": "OEMName", "value": label},
        {"hive": "HKLM", "path": rf"{BASE}\Joystick\OEM\{device}",
         "name": "OEMName", "value": label},
        {"hive": "HKLM", "path": rf"{BASE}\DirectInput\{device}\OEM",
         "name": "OEM Name", "value": label},
    ]


def installed_slots() -> set[int]:
    """Solo examina controladores realmente presentes, no claves obsoletas."""
    if os.name != "nt":
        return set()
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
         "Get-PnpDevice -PresentOnly | Select-Object -ExpandProperty InstanceId"],
        capture_output=True, text=True, timeout=30, errors="replace")
    if result.returncode:
        raise RuntimeError("Get-PnpDevice fallo: " + result.stderr.strip()[:300])
    entries = result.stdout.upper().splitlines()
    hid = set()
    for match in re.finditer(r"VID_F7A0&PID_210([1-8])\b", result.stdout.upper()):
        hid.add(int(match.group(1)))
    # Un VID de ejemplo puede coincidir con hardware ajeno. Exigir tambien
    # que este presente la instancia root FUTJOY correspondiente.
    return {n for n in hid if any(
        rf"ROOT\FUTJOY{n:02d}" in entry for entry in entries
    )}


def is_admin() -> bool:
    try:
        return os.name == "nt" and bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _open_hive(name: str):
    return winreg.HKEY_CURRENT_USER if name == "HKCU" else winreg.HKEY_LOCAL_MACHINE


def read_value(change: dict) -> dict:
    try:
        with winreg.OpenKey(_open_hive(change["hive"]), change["path"],
                            0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as key:
            val, kind = winreg.QueryValueEx(key, change["name"])
            if kind != winreg.REG_SZ:
                raise RuntimeError("Tipo OEM no compatible en " + change["path"])
            return {"exists": True, "value": val}
    except FileNotFoundError:
        return {"exists": False, "value": None}


def put_value(change: dict, value: str) -> None:
    with winreg.CreateKeyEx(_open_hive(change["hive"]), change["path"],
                            0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
        winreg.SetValueEx(key, change["name"], 0, winreg.REG_SZ, value)


def delete_value(change: dict) -> None:
    try:
        with winreg.OpenKey(_open_hive(change["hive"]), change["path"],
                            0, winreg.KEY_SET_VALUE | winreg.KEY_WOW64_64KEY) as key:
            winreg.DeleteValue(key, change["name"])
    except FileNotFoundError:
        pass


def _identity(change: dict) -> tuple[str, str, str]:
    return change["hive"], change["path"], change["name"]


def load_backup() -> list[dict]:
    """Respaldo de nuestras claves exactas, nunca rutas arbitrarias."""
    if not BACKUP.is_file():
        return []
    data = json.loads(BACKUP.read_text(encoding="utf-8"))
    allowed = {_identity(c): c for n in range(1, 9)
               for c in changes_for_slot(n)}
    if not isinstance(data, list):
        raise ValueError("Formato de respaldo no valido")
    keys = set()
    for item in data:
        if not isinstance(item, dict) or not isinstance(item.get("target"), dict):
            raise ValueError("Elemento de respaldo invalido")
        target, previous = item["target"], item.get("previous")
        identity = _identity(target)
        if (identity not in allowed or target != allowed[identity]
                or identity in keys or not isinstance(previous, dict)
                or type(previous.get("exists")) is not bool
                or (previous["exists"] and
                    not isinstance(previous.get("value"), str))):
            raise ValueError("Respaldo inconsistente: no modificar Registro")
        keys.add(identity)
    return data


def save_backup(saved: list[dict]) -> None:
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    # Guardar antes de escribir; es posible restaurar incluso tras interrupcion.
    temp = BACKUP.with_suffix(".tmp")
    temp.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
    temp.replace(BACKUP)


def apply(count: int) -> None:
    if type(count) is not int or not 1 <= count <= 8:
        raise ValueError("Cantidad invalida")
    if winreg is None or not is_admin():
        raise RuntimeError("Ejecuta como administrador en Windows para modificar OEMName")
    wanted = set(range(1, count + 1))
    found = installed_slots()
    if not wanted.issubset(found):
        raise RuntimeError("No se detectaron todos los FUTUREO HID: faltan " +
                           ", ".join(str(x) for x in sorted(wanted - found)) +
                           ". No modifiques el Registro hasta instalar el driver")
    plan = [change for slot in sorted(wanted) for change in changes_for_slot(slot)]
    saved = load_backup()
    by_key = {_identity(item["target"]): item for item in saved}
    additions = []
    # Detectar conflicto con cambios ajenos antes de escribir un solo valor.
    for target in plan:
        old = by_key.get(_identity(target))
        current = read_value(target)
        if old:
            if current != old["previous"] and not (
                    current["exists"] and current["value"] == target["value"]):
                raise RuntimeError("Otra aplicacion cambio la etiqueta en " +
                                   target["path"] + "; se conserva el respaldo")
        else:
            additions.append({"target": target, "previous": current})
    if additions:
        save_backup(saved + additions)
    for target in plan:
        current = read_value(target)
        if not (current["exists"] and current["value"] == target["value"]):
            put_value(target, target["value"])
    print(f"Nombres OEM aplicados P1..P{count}; conservado respaldo: {BACKUP}")
    print("Cierra TODAS las ventanas joy.cpl y vuelve a abrirlas.")
    print("Importante: el HID Product String de VHF NO se modifica.")


def restore() -> None:
    if winreg is None or not is_admin():
        raise RuntimeError("Ejecuta como administrador en Windows")
    if not BACKUP.is_file():
        raise FileNotFoundError("No existe respaldo: " + str(BACKUP))
    saved = load_backup()
    conflicts = []
    for item in saved:
        target, previous = item["target"], item["previous"]
        current = read_value(target)
        # No pisar nombres modificados por otra aplicacion desde nuestro cambio.
        if current == previous:
            continue  # Ya estaba restaurado (o no se llego a modificar).
        if current["exists"] and current["value"] != target["value"]:
            conflicts.append(target["path"])
            continue
        if previous["exists"]:
            put_value(target, previous["value"])
        else:
            delete_value(target)
    if conflicts:
        raise RuntimeError("Existen modificaciones ajenas; respaldo conservado: " +
                           ", ".join(conflicts))
    BACKUP.unlink()
    print("Nombres anteriores restaurados. Respaldo retirado.")


def main():
    parser = argparse.ArgumentParser(
        description="Alias reversibles para joy.cpl/DirectInput; NO modifica HID Product String")
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument("--apply", action="store_true", help="Aplicar alias con respaldo")
    actions.add_argument("--restore", action="store_true", help="Revertir usando respaldo")
    actions.add_argument("--status", action="store_true", help="Consultar etiquetas actuales")
    parser.add_argument("--count", type=int, choices=range(1, 9), default=8)
    args = parser.parse_args()
    if args.restore:
        restore()
    elif args.apply:
        apply(args.count)
    else:
        print("ETIQUETAS OEM - SOLO LECTURA (no modifica el Registro)")
        for n in range(1, args.count + 1):
            print(f"P{n} / {product_key(n)} -> FUTUREO VJOY{n}")
            if os.name == "nt" and winreg is not None:
                for target in changes_for_slot(n):
                    current = read_value(target)
                    observed = current["value"] if current["exists"] else "(sin etiqueta)"
                    print(f"  {target['hive']} {target['name']}: {observed}")
        print("El HID Product String de VHF puede continuar siendo generico.")
        if os.name == "nt":
            print("Dispositivos FUTUREO detectados:", sorted(installed_slots()))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print("ERROR:", error, file=sys.stderr)
        sys.exit(1)
