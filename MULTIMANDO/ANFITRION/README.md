# MULTIMANDO — ANFITRIONES POR TIPO DE CONTROL

Esta carpeta contiene **dos variantes independientes** del anfitrion. Se han guardado las versiones originales, sin cambios en la logica de sus archivos Python.

| Archivo | Version | Motor virtual | Mandos |
| --- | --- | --- | --- |
| [MULTIMANDO_VXBOX_Anfitrion_v1_5_3.py](MULTIMANDO_VXBOX_Anfitrion_v1_5_3.py) | **VXBOX v1.5.3** | vgamepad + ViGEmBus (XInput / Xbox) | 2 |
| [MULTIMANDO_VJOY_Anfitrion_v1_8_1.py](MULTIMANDO_VJOY_Anfitrion_v1_8_1.py) | **VJOY v1.8.1** | pyvjoystick + vJoy (HID / DirectInput) | 1 a 8 |

## VXBOX (version anterior a MULTI 8)

Ejecutar en Windows:

```powershell
py -m pip install websockets vgamepad
py MULTIMANDO_VXBOX_Anfitrion_v1_5_3.py
```

Requiere el driver ViGEmBus disponible y una web compatible con esta version anterior. **No se debe asumir que la web v6.2.0 conserva compatibilidad con VXBOX v1.5.3.**

## VJOY (version MULTI 8)

Ejecutar en Windows:

```powershell
py MULTIMANDO_VJOY_Anfitrion_v1_8_1.py
```

Usa los dispositivos vJoy configurados en Windows y es la variante destinada a **MANDOWEB v6.2.0**. Los instaladores o dependencias adicionales se gestionan conforme al propio programa.

## Importante

- **VXBOX** y **VJOY** son nombres de las copias Python, no modificaciones del driver del sistema.
- No ejecutar los dos anfitriones a la vez atendiendo a la misma sala web.
- FUTUREO VJOY (driver nuevo experimental) es otro proyecto, en `../FUTUREO_VJOY/`, y no sustituye estas variantes.
- Solo se renombraron y guardaron los dos archivos. No se modifico su codigo fuente.
