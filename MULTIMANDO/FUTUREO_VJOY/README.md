# FUTUREO VJOY - Controlador HID propio para MULTIMANDO

**Estado: v0.4 experimental; fuente .sys compilable y .inf validado. Sin firma ni prueba fisica en Windows.**

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
- python/diagnostico_hid.py: consulta HID REAL (SetupAPI/HidD) para determinar si Windows publica nombres y PID independientes; solo lectura, no requiere administrador.
- python/futureo_vjoy_manager.py: GUI para seleccionar 1-8, pedir instalacion en modo laboratorio, detectar y probar.
- python/identificar_futureo.py: GUI de identificacion de mandos.
- python/nombres_windows.py: alias numerados de joy.cpl/DirectInput con respaldo y restauracion.
- tools/compilar_driver.ps1: verificacion y compilacion WDK local, sin instalar el driver.
- tests/test_protocol.py y tests/test_diagnostico_hid.py: contratos, nombres y simulaciones sin hardware.

## Importante: requisitos y limitaciones

1. Compilar el driver con Visual Studio 2022 y Windows Driver Kit (WDK) en Windows x64.
2. Generar catalogo y firma de driver validos para el Windows de destino.
   - Visual Studio 2026 con SDK+WDK 28000, o Visual Studio 2022 con SDK+WDK 26100.
   - El SDK y WDK deben corresponder al mismo numero de compilacion. No se incluye .sys, .cat, .exe ni driver firmado.
3. Para crear las instancias root es necesario DevCon del WDK (o herramienta PnP equivalente) y permisos de administrador. La GUI **no** crea dispositivos antes de instalar correctamente el driver firmado.
4. Probar primero en una maquina virtual de laboratorio. Un driver kernel experimental puede causar fallos del sistema.
   - El INF ya declara Vhf.sys como LowerFilters (antes faltaba).
   - El driver solicita enviar estado neutro cuando se cierra el cliente Python.
   - Se limita a un unico proceso escritor por puesto (WdfDeviceInitSetExclusive).
   - La compilacion WDK ya fue comprobada para el codigo anterior; falta el resultado del ultimo cambio y todas las pruebas de hardware en VM.
5. El VID 0xF7A0 es SOLO ilustrativo: antes de distribuir usar identificadores de proveedor autorizados.
6. FutJoy.sys YA COMPILA en GitHub Actions (Windows x64, 0 errores/0 advertencias). FutJoy.inf paso InfVerif /w. No esta firmado ni probado como hardware HID ni integrado con MULTIMANDO Anfitrion v1.8.1.
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

Pendiente: firma valida, pruebas en VM,
enumeracion en joy.cpl, nombres por juego y estabilidad del controlador.

## Resultados efectivos de CI - 22 noviembre 2026

- Compilacion Windows x64 **exitosa**, 0 errores y 0 advertencias:
  https://github.com/mobatfb/archmoba-dev/actions/runs/45004213793
- Fuente C compilada y enlazada: FutJoy.sys de 23040 bytes.
- Validacion independiente de FutJoy.inf **exitosa** con `InfVerif /w`:
  https://github.com/mobatfb/archmoba-dev/actions/runs/45004213766
- Artefacto `FUTUREO-VJOY-SYS-EXPERIMENTAL-SIN-FIRMA` en la ejecucion
  de GitHub Actions; caduca aproximadamente siete dias despues del build.
- La compilacion CI omite ApiValidator por ausencia de la herramienta en
  el NuGet WDK; el destino CI se ajusta a `DriverTargetPlatform=Desktop`.
- El `.sys` NO ESTA FIRMADO. No es instalable normalmente en Windows 10/11
  con las politicas de integridad del kernel activadas.
- **Sin pruebas de ejecucion del driver**, sin confirmacion de nombres
  en `joy.cpl`, sin prueba con juegos y sin sello de Microsoft.

### Siguiente requisito ineludible

1. Usar un identificador VID autorizado antes de distribucion publica.
2. Completar pruebas de hardware HID y estabilidad en Windows de laboratorio.
3. Preparar catalogo `.cat` y gestionar una firma de Microsoft a traves del
   Hardware Dev Center. Esto requiere cuenta de desarrollador de hardware
   y certificado EV. Para distribucion general, preparar pruebas HLK/WHCP.
4. Solo tras una firma confiable, instalar y verificar ocho instancias PnP
   en `joy.cpl` y su identidad visual en los juegos de interes.

Referencias:
- https://learn.microsoft.com/en-us/windows-hardware/drivers/dashboard/driver-signing-offerings
- https://learn.microsoft.com/en-us/windows-hardware/drivers/dashboard/code-signing-reqs

## Nuevo en v0.4: diagnostico HID de identidad REAL (solo lectura)

El objetivo es comprobar exactamente lo que los juegos pueden encontrar,
no solamente los nombres establecidos en el INF. Despues de instalar
de forma valida en un equipo Windows de laboratorio:

    py python\diagnostico_hid.py --count 8

Para generar un resultado estructurado que se pueda compartir:

    py python\diagnostico_hid.py --count 8 --json

Tambien esta integrado en la GUI: boton **VER IDENTIDAD HID**.

El diagnostico enumera interfaces HID presentes utilizando SetupAPI y
HidD_GetAttributes/HidD_GetProductString. Para cada puesto muestra:
- VID:PID hexadecimal (de laboratorio)
- si hay una coleccion HID presente
- el Product String HID REAL, si Windows lo devuelve
- si los ocho Product Strings son diferentes

Este analisis es estrictamente de lectura, no modifica el Registro,
no requiere administrador, no instala drivers y no crea joysticks.
Si no se detecta nada, NO significa que el driver no compile;
significa que ese Windows no expone interfaces HID FUTUREO accesibles.

IMPORTANTE: el protocolo VHF puede entregar nombres HID genericos;
un nombre numerado en el INF o un alias OEM DirectInput NO garantiza
el mismo nombre en el desplegable de un juego. No anunciar como logro
esa funcion hasta contrastarla en juegos reales.

### Seguridad del manejo de dispositivos

Cada FUTUREO VJOY solo permite un escritor al mismo tiempo. El puente
Python abre el control con uso exclusivo, de forma que no existan dos
anfitriones mandando ordenes contradictorias a un mismo slot.
Al cerrar el cliente, el driver intenta neutralizar ejes y botones.

Pendiente de implementacion: seguridad por usuario de los enlaces
de dispositivo, watchdog de actividad, cierre seguro ante fallos
de energia, pruebas de Windows con Driver Verifier y firma del driver.

Pruebas simuladas de nombres y exclusividad se ejecutan en GitHub Actions,
pero NO constituyen prueba de un dispositivo instalado ni de su nombre
real anunciado a los juegos.

### Rutas de trabajo

- Anfitrion estable con vJoy convencional: `../ANFITRION/`.
- Prototipo FUTUREO (sin integrar al anfitrion estable): esta carpeta.
- Nueva interfaz de diagnostico: `python/diagnostico_hid.py`.

## Paquete de instalacion experimental para PC secundaria (LAB)

Se agrego `instalador_windows/` con los archivos `.bat`, el instalador
PowerShell, comprobaciones de hashes SHA-256, consulta HID y desinstalador.

Compilacion y firma de laboratorio comprobadas en GitHub Actions:
https://github.com/mobatfb/archmoba-dev/actions/runs/45006833196

El flujo firmado contiene `FutJoy.sys` x64 con firma de prueba incrustada,
`FutJoy.cat` firmado, `FutJoy.inf`, `FUTUREO_VJOY_PRUEBA.cer` (solo parte
publica), Python GUI, diagnostico y fuente de desarrollo. El instalador
requiere modo de firma de prueba ACTIVADO conscientemente y reinicio,
confianza explicita en el certificado y un Windows 10/11 x64 secundario.
NO desactiva automaticamente Secure Boot, BitLocker o HVCI.

Secuencia de prueba: extraer paquete ZIP completo, abrir `INSTALAR.bat`,
elegir PREPARAR MODO PRUEBA, reiniciar y luego INSTALAR SOLO 1 MANDO.
Antes de crear 8 mandos, verificar P1 en `joy.cpl` y su entrada HID.
El controlador puede fallar: NO hay pruebas de enumeracion real en la PC
secundaria ni certificacion de seguridad, y no sustituye una firma oficial.

Los `.bat` y `HERRAMIENTAS/instalador.ps1` pasaron validacion sintactica
en Windows con `Add-Type` C# para las API SetupAPI, sin crear devnodes en
las maquinas de integracion. Se incluye DESINSTALAR y VOLVER MODO NORMAL.

NOTA: las builds de laboratorio usan un certificado de prueba efimero
y no incluyen claves privadas. No distribuir como software de produccion.
