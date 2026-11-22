#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""Diagnostico HID de FUTUREO VJOY: identidades que Windows anuncia realmente.

Solo consulta dispositivos. No requiere administrador y NO modifica Windows,
instala drivers, aplica alias OEM ni envia entradas de joystick.

Uso (Windows): py python\diagnostico_hid.py --count 8
               py python\diagnostico_hid.py --json --count 8

Product String HID != nombre del dispositivo raiz PnP != alias OEM DirectInput.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
import os
import sys

LAB_VENDOR_ID = 0xF7A0  # VID ilustrativo: NO usar para distribucion.
PID_BASE = 0x2100
SLOTS = 8


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("InterfaceClassGuid", GUID),
        ("Flags", wintypes.DWORD),
        ("Reserved", ctypes.c_void_p),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", wintypes.ULONG),
        ("VendorID", wintypes.USHORT),
        ("ProductID", wintypes.USHORT),
        ("VersionNumber", wintypes.USHORT),
    ]


def read_devices() -> list[dict]:
    """Enumerar interfaces HID presentes mediante HID.dll + SetupAPI.dll.

    Un mismo gamepad puede exponer mas de una interfaz/coleccion.
    Los resultados incluyen solo los PID experimentales de FUTUREO.
    """
    if os.name != "nt":
        raise OSError("Solo funciona en Windows; no se han examinado mandos reales.")

    setup = ctypes.WinDLL("setupapi", use_last_error=True)
    hid = ctypes.WinDLL("hid", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)

    hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
    hid.HidD_GetHidGuid.restype = None
    hid.HidD_GetAttributes.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(HIDD_ATTRIBUTES)]
    hid.HidD_GetAttributes.restype = wintypes.BOOLEAN
    hid.HidD_GetProductString.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG]
    hid.HidD_GetProductString.restype = wintypes.BOOLEAN
    hid.HidD_GetManufacturerString.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, wintypes.ULONG]
    hid.HidD_GetManufacturerString.restype = wintypes.BOOLEAN

    setup.SetupDiGetClassDevsW.argtypes = [
        ctypes.POINTER(GUID), wintypes.LPCWSTR, wintypes.HWND,
        wintypes.DWORD]
    setup.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    setup.SetupDiEnumDeviceInterfaces.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(GUID),
        wintypes.DWORD, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA)]
    setup.SetupDiEnumDeviceInterfaces.restype = wintypes.BOOL
    setup.SetupDiGetDeviceInterfaceDetailW.argtypes = [
        ctypes.c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
        ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p]
    setup.SetupDiGetDeviceInterfaceDetailW.restype = wintypes.BOOL
    setup.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
    setup.SetupDiDestroyDeviceInfoList.restype = wintypes.BOOL
    kernel.CreateFileW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = wintypes.BOOL

    guid = GUID()
    hid.HidD_GetHidGuid(ctypes.byref(guid))
    DIGCF_PRESENT, DIGCF_DEVICEINTERFACE = 0x2, 0x10
    info = setup.SetupDiGetClassDevsW(
        ctypes.byref(guid), None, None, DIGCF_PRESENT | DIGCF_DEVICEINTERFACE)
    invalid = ctypes.c_void_p(-1).value
    if info in (None, invalid):
        raise ctypes.WinError(ctypes.get_last_error())

    devices = []
    try:
        index = 0
        while True:
            data = SP_DEVICE_INTERFACE_DATA()
            data.cbSize = ctypes.sizeof(SP_DEVICE_INTERFACE_DATA)
            ok = setup.SetupDiEnumDeviceInterfaces(
                info, None, ctypes.byref(guid), index, ctypes.byref(data))
            if not ok:
                err = ctypes.get_last_error()
                if err == 259:  # ERROR_NO_MORE_ITEMS
                    break
                raise ctypes.WinError(err)
            index += 1

            needed = wintypes.DWORD()
            setup.SetupDiGetDeviceInterfaceDetailW(
                info, ctypes.byref(data), None, 0, ctypes.byref(needed), None)
            if needed.value < 8 or needed.value > 65536:
                continue
            detail = ctypes.create_string_buffer(needed.value)
            # SP_DEVICE_INTERFACE_DETAIL_DATA_W: cbSize 8 en x64, 6 en x86;
            # el campo DevicePath comienza en offset 4 en ambos.
            ctypes.cast(detail, ctypes.POINTER(wintypes.DWORD))[0] = (
                8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6)
            ok = setup.SetupDiGetDeviceInterfaceDetailW(
                info, ctypes.byref(data), detail, needed.value,
                ctypes.byref(needed), None)
            if not ok:
                continue

            device_path = ctypes.wstring_at(ctypes.addressof(detail) + 4)
            # Acceso 0: lectura de informacion HID sin capturar las entradas.
            handle = kernel.CreateFileW(
                device_path, 0, 0x1 | 0x2, None, 3, 0, None)
            if handle in (None, invalid):
                continue
            try:
                attr = HIDD_ATTRIBUTES()
                attr.Size = ctypes.sizeof(attr)
                if not hid.HidD_GetAttributes(handle, ctypes.byref(attr)):
                    continue
                if attr.VendorID != LAB_VENDOR_ID or not (
                        PID_BASE + 1 <= attr.ProductID <= PID_BASE + SLOTS):
                    continue
                name_buffer = ctypes.create_unicode_buffer(256)
                manufacturer_buffer = ctypes.create_unicode_buffer(256)
                product = (
                    name_buffer.value
                    if hid.HidD_GetProductString(
                        handle, name_buffer, ctypes.sizeof(name_buffer))
                    else "")
                manufacturer = (
                    manufacturer_buffer.value
                    if hid.HidD_GetManufacturerString(
                        handle, manufacturer_buffer,
                        ctypes.sizeof(manufacturer_buffer))
                    else "")
                devices.append({
                    "slot": int(attr.ProductID - PID_BASE),
                    "vid": f"{attr.VendorID:04X}",
                    "pid": f"{attr.ProductID:04X}",
                    "product_string": product.strip(),
                    "manufacturer": manufacturer.strip(),
                    "version": f"{attr.VersionNumber:04X}",
                })
            finally:
                kernel.CloseHandle(handle)
    finally:
        setup.SetupDiDestroyDeviceInfoList(info)

    return devices


def summarize(devices: list[dict], count: int = 8) -> dict:
    """Crea una evaluacion comprobable sin acceder a Windows (testable)."""
    if type(count) is not int or not 1 <= count <= SLOTS:
        raise ValueError("count debe estar entre 1 y 8")
    entries = []
    for slot in range(1, count + 1):
        matches = [item for item in devices if item["slot"] == slot]
        products = sorted({item.get("product_string", "").strip()
                           for item in matches
                           if item.get("product_string", "").strip()})
        entries.append({
            "slot": slot,
            "esperado": f"FUTUREO VJOY{slot}",
            "vid_pid": f"{LAB_VENDOR_ID:04X}:{PID_BASE + slot:04X}",
            "detectado": bool(matches),
            "colecciones_hid": len(matches),
            "product_strings": products,
        })
    present = [e for e in entries if e["detectado"]]
    missing = [e["slot"] for e in entries if not e["detectado"]]
    products = [e["product_strings"][0] for e in present
                if len(e["product_strings"]) == 1]
    # Un solo mando detectado NO permite comparar nombres entre dispositivos.
    # Evita informar "distintos" cuando hay un unico Product String.
    unique = (
        count > 1
        and len(present) == count
        and all(len(e["product_strings"]) == 1 for e in present)
        and len(set(products)) == count
    )
    warnings = []
    if missing:
        warnings.append("No se ven dispositivos HID en los puestos: " +
                        ", ".join(f"P{i}" for i in missing))
    if present and not unique:
        if len(present) < 2:
            warnings.append(
                "Se detecto un solo mando: no es posible comprobar si P1..P8 "
                "tienen nombres HID diferentes. Esto no es un error de P1.")
        else:
            warnings.append(
                "No se han confirmado nombres HID Product String distintos "
                "para los puestos detectados; algunos juegos pueden mostrar nombres iguales.")
    if unique:
        warnings.append(
            "Los nombres HID son distintos. Cada juego debe probarse por "
            "separado; algunos muestran alias DirectInput/SDL.")
    return {
        "driver": "FUTUREO VJOY experimental",
        "modo": "LECTURA HID - sin modificar Windows",
        "puestos_solicitados": count,
        "puestos_detectados": len(present),
        "product_strings_diferentes": unique,
        "puestos": entries,
        "advertencias": warnings,
        "nota": (
            "VID/PID de laboratorio; un Product String no equivale a nombre "
            "de dispositivo PnP. Este programa solo consulta Windows: no instala, "
            "firma, desinstala ni modifica controladores."
        ),
    }


def text_report(data: dict) -> str:
    lines = [
        "FUTUREO VJOY | DIAGNOSTICO HID (solo lectura)",
        f"Puestos visibles: {data['puestos_detectados']}/"
        f"{data['puestos_solicitados']}",
    ]
    for row in data["puestos"]:
        names = ", ".join(row["product_strings"]) or "(no disponible)"
        lines.append(
            f"P{row['slot']} | VID:PID={row['vid_pid']} | "
            f"{'DETECTADO' if row['detectado'] else 'NO DETECTADO'} | "
            f"HID Product String: {names}")
    lines.append(
        "Nombres HID diferentes: " +
        ("CONFIRMADOS" if data["product_strings_diferentes"]
         else "NO CONFIRMADOS"))
    lines.extend("AVISO: " + w for w in data["advertencias"])
    lines.append(data["nota"])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, choices=range(1, 9), default=8)
    parser.add_argument("--json", action="store_true",
                        help="Salida estructurada para auditoria")
    parser.add_argument("--require-count", action="store_true",
                        help="Devolver error si faltan puestos")
    args = parser.parse_args()
    try:
        report = summarize(read_devices(), args.count)
    except (OSError, RuntimeError) as exc:
        print("No se pudo enumerar HID: " + str(exc), file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(text_report(report))
    if args.require_count and report["puestos_detectados"] != args.count:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
