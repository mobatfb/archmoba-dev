# FUTUREO VJOY - Controlador HID propio para MULTIMANDO

**Estado: prototipo de codigo fuente v0.2 (NO instalador final).**

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
- python/adapter_multimando.py: motor opcional con interfaz compatible con Room de MULTIMANDO, no integrado aun.
- python/futureo_vjoy_manager.py: GUI para seleccionar 1-8, pedir instalacion en modo laboratorio, detectar y probar.
- python/identificar_futureo.py: GUI de identificacion de mandos.
- python/nombres_windows.py: alias numerados de joy.cpl/DirectInput con respaldo y restauracion.
- tools/compilar_driver.ps1: verificacion y compilacion WDK local, sin instalar el driver.
- tests/test_protocol.py: pruebas del protocolo sin Windows.

## Importante: requisitos y limitaciones

1. Compilar el driver con Visual Studio 2022 y Windows Driver Kit (WDK) en Windows x64.
2. Generar catalogo y firma de driver validos para el Windows de destino.
   - Visual Studio 2026 con SDK+WDK 28000, o Visual Studio 2022 con SDK+WDK 26100.
   - El SDK y WDK deben corresponder al mismo numero de compilacion. No se incluye .sys, .cat, .exe ni driver firmado.
3. Para crear las instancias root es necesario DevCon del WDK (o herramienta PnP equivalente) y permisos de administrador. La GUI **no** crea dispositivos antes de instalar correctamente el driver firmado.
4. Probar primero en una maquina virtual de laboratorio. Un driver kernel experimental puede causar fallos del sistema.
   - El INF ya declara Vhf.sys como LowerFilters (antes faltaba).
   - El driver solicita enviar estado neutro cuando se cierra el cliente Python.
   - La compilacion WDK y las pruebas reales aun estan PENDIENTES.
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

### Compilacion de prueba (sin instalar nada)

En Windows con Visual Studio y WDK instalados:

    powershell -NoProfile -File tools\compilar_driver.ps1

Este script no firma ni instala el driver, y no cambia opciones de seguridad de Windows.

### Nombres diferenciados en joy.cpl / DirectInput

El INF anuncia ocho nombres PnP distintos y cada VHF usa un PID diferente.
**VHF NO permite asignar libremente la cadena HID Product String**, por lo
que algunos juegos pueden continuar mostrando un nombre generico.
Para los que utilizan los alias OEM de Windows se proporciona una herramienta:

    py python\nombres_windows.py --count 2

El comando anterior es SOLO LECTURA y muestra el plan. Tras compilar,
firmar, instalar el driver y comprobar que Windows detecta los HID
FUTUREO, puedes elegir en la GUI **ETIQUETAR EN WINDOWS** (requiere
administrador) o ejecutar:

    py python\nombres_windows.py --apply --count 2

Se guardan los valores anteriores en LOCALAPPDATA/FUTUREO_VJOY.
Para volver a los nombres originales:

    py python\nombres_windows.py --restore

La herramienta no modifica vJoy ajeno, no se aplica a mandos que no
sean FUTUREO y nunca cambia los descriptores HID originales.


## Arquitectura y objetivos pendientes

Cada instancia ROOT\FUTJOY0N expone un hijo HID virtual creado por VHF, con ProductID propio y enlace de control \\.\FUTJOYN. El puente envia un estado de 6 bytes: X (int16), Y (int16), botones (uint16). El controlador lo publica como reporte HID de 7 bytes (ReportID=1).

Pendiente: verificar compilacion WDK, firma, enumeracion y nombres del juego;
auditar permisos de acceso y desarrollar watchdog de entradas para procesos
que sigan abiertos pero dejen de enviar actividad, e integrar MULTIMANDO
(P1-P8, FIFO, desconexion y modos CONTROLADO/REMOTO).

## Cambios v0.2 (22-nov-2026)

- Se agrego el filtro inferior Vhf.sys obligatorio al INF.
- El driver envia estado neutro en el cierre del cliente (EvtFileCleanup).
- La GUI integra etiquetado reversible de 1 a 8 dispositivos para joy.cpl/DirectInput.
- Se incluye script WDK de compilacion sin instalacion.
- Pruebas automaticas Python/INF/contratos mediante GitHub Actions en Windows y Linux.
- Adaptador P1-P8 para MULTIMANDO, con botones, ejes, desasignacion, identificacion y pruebas simuladas.
- **Ningun SYS/CAT compilado ni firmado; no es una version lista para uso diario**.

Documentacion:
- https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/virtual-hid-framework--vhf-
- https://learn.microsoft.com/en-us/windows-hardware/drivers/install/windows-driver-signing-tutorial
- https://github.com/microsoft/Windows-driver-samples/tree/main/hid/vhidmini2

## Conexion futura con MULTIMANDO

El modulo `python/adapter_multimando.py` expone `FutureoPads(count=2)`, con
los metodos `apply`, `analog`, `set_mode`, `release_slot`, `identify` y `close`.
Permite P1-P8 y libera todos los botones cuando se cede el mando. El modo
`dpad` se traduce por ahora a ejes X/Y: el descriptor experimental aun NO
tiene una entrada POV Hat nativa. La sala MULTIMANDO v1.8.1 sigue utilizando
vJoy y NO importa automaticamente este modulo.

En Windows, despues de instalar y validar el driver FUTUREO firmado, se podra
integrar el adaptador como opcion de motor sin alterar el arbitro de turnos.
No uses el driver no firmado en tu PC de juegos.

## Compilacion Windows en GitHub Actions (sin instalar)

El flujo .github/workflows/futureo-vjoy-driver.yml intenta compilar un
FutJoy.sys x64 Release usando runner windows-2025-vs2026 y WDK/SDK
NuGet 10.0.28000.2526, sin firmar ni instalar un driver.

Ver estado: https://github.com/mobatfb/archmoba-dev/actions/workflows/futureo-vjoy-driver.yml

Si compila, GitHub Actions almacenara temporalmente
FUTUREO-VJOY-SYS-EXPERIMENTAL-SIN-FIRMA. Un .sys sin catalogo ni firma
valida NO se puede instalar normalmente en Windows 10/11.

## Diagnostico en Windows (solo lectura)

    powershell -NoProfile -File tools\diagnosticar_windows.ps1

Permite comparar el identificador ROOT/FUTJOY, el HID
VID_F7A0&PID_2101..2108, estado PnP y los nombres OEM de DirectInput.
Las cadenas reales que muestran los juegos deben comprobarse en ellos;
la herramienta no modifica el Registro ni vJoy.

Pendiente: compilacion WDK verificada, firma valida, pruebas en VM,
enumeracion en joy.cpl, nombres por juego y estabilidad del controlador.
