# FUTUREO VJOY - Controlador HID propio para MULTIMANDO

**Estado: prototipo de codigo fuente v0.1 (NO instalador final).**

Proyecto experimental para crear hasta 8 gamepads HID independientes en Windows 10/11 x64. No reemplaza ni modifica vJoy o ViGEmBus instalados.

## Identidades del prototipo

| Puesto | Identidad PnP (root device) | ProductID experimental |
|---|---|---|
| P1 | ROOT\FUTJOY01 | 0x2101 |
| P2 | ROOT\FUTJOY02 | 0x2102 |
| P3 | ROOT\FUTJOY03 | 0x2103 |
| P4 | ROOT\FUTJOY04 | 0x2104 |
| P5 | ROOT\FUTJOY05 | 0x2105 |
| P6 | ROOT\FUTJOY06 | 0x2106 |
| P7 | ROOT\FUTJOY07 | 0x2107 |
| P8 | ROOT\FUTJOY08 | 0x2108 |

El INF declara etiquetas PnP "FUTUREO VJOY1 - PLAYER 1" hasta "FUTUREO VJOY8 - PLAYER 8". **Un nombre PnP NO garantiza que el juego lo muestre como HID Product String:** VHF no permite configurar libremente el texto de producto desde VHF_CONFIG. Debe verificarse el nombre en cada juego antes de prometer ese resultado; si es necesario, usar un HID minidriver que gestione IOCTL_HID_GET_STRING.

## Estructura

- driver/FutJoy.c y driver/FutJoy.h: fuente del driver KMDF / VHF, ejes X/Y y 16 botones.
- driver/FutJoy.inf: ocho IDs PnP root distintos.
- driver/FutJoy.vcxproj: proyecto base para Visual Studio + WDK.
- python/futureo_vjoy.py: puente de estados por DeviceIoControl.
- python/futureo_vjoy_manager.py: GUI para seleccionar 1-8, pedir instalacion en modo laboratorio, detectar y probar.
- python/identificar_futureo.py: GUI de identificacion de mandos.
- tests/test_protocol.py: pruebas del protocolo sin Windows.

## Importante: requisitos y limitaciones

1. Compilar el driver con Visual Studio 2022 y Windows Driver Kit (WDK) en Windows x64.
2. Generar catalogo y firma de driver validos para el Windows de destino. No se incluye .sys, .cat, .exe ni driver firmado.
3. Para crear las instancias root es necesario DevCon del WDK (o herramienta PnP equivalente) y permisos de administrador. La GUI **no** crea dispositivos antes de instalar correctamente el driver firmado.
4. Probar primero en una maquina virtual de laboratorio. Un driver kernel experimental puede causar fallos del sistema.
5. El VID 0xF7A0 es SOLO ilustrativo: antes de distribuir usar identificadores de proveedor autorizados.
6. Aun NO se ha compilado, firmado ni probado con gamepads reales en Windows; tampoco esta integrado con MULTIMANDO Anfitrion v1.8.1.
7. No desactivar Secure Boot o protecciones del sistema para forzar la instalacion.

## Uso de Python

Para validar el protocolo sin driver:

    py python\futureo_vjoy.py --selftest
    py -m unittest discover -s tests -v

Para abrir la ventana de desarrollo (funciona sin driver, pero crear/probar requiere instalarlo):

    py python\futureo_vjoy_manager.py

Cuando el driver este compilado y firmado, ubicar FutJoy.sys y FutJoy.cat junto al INF, y seleccionar devcon.exe en la GUI; ejecutar el administrador como usuario elevado. La instalacion se solicita de forma explicita para evitar cambios accidentales en Windows.

Para identificar un dispositivo instalado:

    py python\identificar_futureo.py

## Arquitectura y objetivos pendientes

Cada instancia ROOT\FUTJOY0N expone un hijo HID virtual creado por VHF, con ProductID propio y enlace de control \\.\FUTJOYN. El puente envia un estado de 6 bytes: X (int16), Y (int16), botones (uint16). El controlador lo publica como reporte HID de 7 bytes (ReportID=1).

Pendiente: verificar compilacion WDK, firma, enumeracion, cadena de producto HID, permisos de acceso y watchdog de teclas, e integrar el backend con MULTIMANDO manteniendo desconexiones seguras, P1-P8 y cola FIFO.

Documentacion:
- https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/virtual-hid-framework--vhf-
- https://learn.microsoft.com/en-us/windows-hardware/drivers/install/windows-driver-signing-tutorial
- https://github.com/microsoft/Windows-driver-samples/tree/main/hid/vhidmini2
