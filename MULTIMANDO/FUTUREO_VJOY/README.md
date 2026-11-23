## FUTUREO VJOY v0.8.0 - Portable con INICIAR, PROBAR y MONITOR

**[Descargar EXE portable v0.8.0](instalador_windows/FUTUREO_VJOY_PORTABLE_v0_8_0_WIN64.exe)**

**[Descargar ZIP completo v0.8.0](instalador_windows/FUTUREO_VJOY_PORTABLE_v0_8_0_WIN64.zip)**

Se agrego una interfaz gamer de **3 secciones**, manteniendo la v0.7.0 como respaldo:

- **INICIAR:** seleccion de 1..8 controladores `FUTUREO_VJOY1` a
  `FUTUREO_VJOY8`, instalacion UMDF2 consentida y lista de activos.
- **PROBAR:** tira de seleccion de mandos, mando virtual clicable con
  **16 botones**, **analogico izquierdo de dos ejes X/Y** y **D-Pad
  de ocho direcciones**; modos ANALOGICO, CRUCETA y MIXTO.
  Opcion MANTENER BOTONES para configurar juegos y soltar entradas.
- **MONITOR:** tira de mandos activos, luces de los 16 botones,
  estado de D-Pad y ejes, contador de transmisiones y
  registro cronologico por mando. Incluye **AUTO PRUEBA** para
  visualizar pulsaciones sin abandonar la seccion.

El descriptor HID contiene **X/Y de 16 bits, 16 botones y Hat Switch
de 8 posiciones**. El SDK HIDMaestro 2.3.0 actualiza etiquetas OEM
de forma reversible. El ejecutable es autocontenido (Windows x64),
aunque el controlador debe instalarse en Windows con UAC.
No se cambia TESTSIGNING y no se eliminan drivers previos.

**Limitaciones:** el MONITOR muestra las señales que esta aplicacion
envia a los mandos virtuales, no una lectura independiente desde
Windows. El D-Pad no garantiza por si solo que el navegador clasifique
el mando como `mapping: "standard"`; la compatibilidad con KOF2022
requiere verificarse. Para utilizar el mando visual con juegos en
navegador, el foco de la ventana puede influir en la recepcion.

[Codigo fuente v0.8.0 y manual](portable_v080/).

## FUTUREO VJOY v0.7.0 - instalador PORTABLE de un solo ejecutable

**[Descargar EXE portable v0.7.0](instalador_windows/FUTUREO_VJOY_PORTABLE_v0_7_0_WIN64.exe)**

**[Descargar ZIP v0.7.0 (mismo EXE, licencia y manual)](instalador_windows/FUTUREO_VJOY_PORTABLE_v0_7_0_WIN64.zip)**

Compilacion Windows 10/11 x64 `self-contained`, `PublishSingleFile`,
`EnableCompressionInSingleFile`, sin instalador MSI ni .NET externo.
**El EXE es portable; el controlador HIDMaestro SI se instala en Windows**
bajo consentimiento UAC (el modo prueba de Windows no se modifica).
Puede extraer librerias nativas temporalmente a su cache de .NET.

Crea 1..8 mandos independientes con nombres EXACTOS
`FUTUREO_VJOY1` a `FUTUREO_VJOY8`, con guion bajo y sin PLAYER.
Cada mando conserva 16 botones y los ejes X/Y.
El motor es HIDMaestro UMDF2 (VID F7A0 / PID 2201..2208);
el controlador VHF antiguo no se altera.

La aplicacion crea los mandos en un solo flujo: selecciona cantidad,
acepta la instalacion del driver, pulsa **INSTALAR Y CREAR MANDOS**.
Para evitar nombres viejos en `joy.cpl`, usa la API reversible
`HMOemNameOverride` del SDK y define
`Name`, `DeviceDescription` y `ProductString` iguales.
Cierra/reabre `joy.cpl` y Steam para actualizar su cache.

El EXE incluye una **autoprueba aislada del bundle** que confirma la
presencia de recursos UMDF2 x64 y de la API de etiquetas OEM sin
instalar controladores en GitHub Actions. Esto NO sustituye una prueba
real de instalacion y reconocimiento en un PC.
Los mandos virtuales se retiran al cerrar el EXE; el motor instalado
permanece hasta que se desinstale por separado.

**Compatibilidad:** conserva los ZIP anteriores y el limpiador
v1.0 para recuperar el entorno de laboratorio. No integra todavia
la conexion remota MULTIMANDO.
[Fuentes del portable](instalador_portable/).

## FUTUREO VJOY - limpiador total LAB v1.0

**[DESCARGAR ZIP DEL LIMPIADOR](instalador_windows/FUTUREO_VJOY_LIMPIADOR_TOTAL_v1_0_0_LAB.zip)**

Ejecutable de Windows para empezar desde cero antes de reinstalar la
version v0.6.0 (HIDMaestro), que fue la version funcional confirmada.

El programa muestra primero una **vista previa que no elimina nada**.
Luego permite elegir si se retiran los dispositivos y paquetes
**FUTJOY/VHF** (ROOT\\FUTJOY01..08) y/o **TODO HIDMaestro**.
Esta ultima opcion usa el desinstalador oficial v2.3.0 y afectara
tambien a otras aplicaciones que compartan HIDMaestro. Hay doble
confirmacion y una frase obligatoria. No elimina mandos fisicos,
no borra controladores genericos de Windows ni cambia TESTSIGNING.
Conserva registro detallado, ayuda de uso y enlace al ZIP v0.6.0.

**Importante:** la comprobacion automatica valida compilacion/sintaxis,
no ejecuta el borrado de controladores de tu PC. Escanea antes de
eliminar, cierra las aplicaciones que los usen y reinicia al terminar.

[Codigo fuente y auditoria](limpiador_total/).

## FUTUREO VJOY v0.6.1 LAB - nombres limpios

**[Descarga directa del ZIP v0.6.1](instalador_windows/FUTUREO_VJOY_v0_6_1_LAB_NOMBRES_LIMPIOS.zip)**

El usuario confirmo que v0.6.0 funciona y los 4 mandos aparecen en Windows
con nombres propios. Esta actualizacion **solo elimina el sufijo
`- PLAYER n` del nombre visible**. Quedan
`FUTUREO VJOY1`, `FUTUREO VJOY2`, ... `FUTUREO VJOY8`.

Se mantienen 8 controles independientes, 16 botones y 2 ejes por control.
Se conserva el motor HIDMaestro UMDF2 (VID F7A0, PID 2201..2208);
no se borra, instala ni modifica ningun dispositivo VHF anterior.
Se cambia la clave de identidad de instancia de este prototipo a `v061`
para reducir la reutilizacion del nombre anterior por la cache PnP de Windows.

**Uso:** cierra por completo la aplicacion v0.6.0, extrae el ZIP v0.6.1
en otra carpeta, ejecuta `FUTUREO_NOMBRES_REALES.exe` y crea los mandos
como en la version anterior. El boton PREPARAR MOTOR sigue mostrando el
consentimiento para el controlador externo; no elude UAC ni protecciones.
Comprueba los nombres en `joy.cpl` o Steam. No se garantiza la
actualizacion del nombre que haya quedado guardado en algun juego;
el ZIP v0.6.0 permanece disponible como respaldo.

## FUTUREO VJOY v0.6.0 LAB: motor alternativo con nombres HID reales

**[Descargar ZIP LAB v0.6.0 (despues de publicacion de GitHub Actions)](instalador_windows/FUTUREO_VJOY_v0_6_0_LAB_NOMBRES_REALES_UMDF2.zip)**

Los alias OEM y PnP de v0.5.1/v0.5.2 no consiguieron cambiar el nombre
generico VHF en joy.cpl. Microsoft documenta que VHF controla
`IOCTL_HID_GET_STRING` y que la configuracion `VHF_CONFIG` no permite
suministrar un nombre de producto propio, aunque si VID/PID.

Este prototipo **no usa FutJoy.sys**. Es un motor opcional, separado, basado
en **HIDMaestro v2.3.0 (MIT)**, con un minidriver UMDF2 que permite asignar
un Product String HID distinto por mando:

- P1: FUTUREO VJOY1 - PLAYER 1 | VID F7A0 / PID 2201
- P2: FUTUREO VJOY2 - PLAYER 2 | VID F7A0 / PID 2202
- P3: FUTUREO VJOY3 - PLAYER 3 | VID F7A0 / PID 2203
- P4: FUTUREO VJOY4 - PLAYER 4 | VID F7A0 / PID 2204
- P5..P8: mismo esquema, hasta PID 2208.

Cada control tiene dos ejes (X/Y) y 16 botones. El paquete incluye una
aplicacion independiente WinForms `FUTUREO_NOMBRES_REALES.exe`; no
sustituye la GUI Python existente, no borra los mandos P1-P8 ya instalados
y todavia **no incluye integracion MULTIMANDO**. El usuario debe confirmar
la instalacion opcional del nuevo motor y ejecutarla con privilegios UAC.
Solo equipo secundario, no equipo principal.

**IMPORTANTE:** la compilacion automatizada y la firma proporcionada por
HIDMaestro no prueban el resultado en el equipo del usuario. Instalar el
motor de terceros modifica el almacen de controladores y la confianza en
un certificado local; cerrar la aplicacion elimina sus mandos, pero no
desinstala automaticamente ese controlador. Para retirarlo, usar la
herramienta oficial HIDMaestroUninstall, revisando primero `--preview`.

Se mantienen todas las versiones v0.5.x intactas. Fuentes de referencia:
[Microsoft VHF](https://learn.microsoft.com/en-us/windows-hardware/drivers/hid/virtual-hid-framework--vhf-),
[HIDMaestro (MIT)](https://github.com/hifihedgehog/HIDMaestro).

## FUTUREO VJOY v0.5.2 LAB - prueba de nombres PnP sin cambiar el SYS

**[ZIP v0.5.2: prueba de nombres PnP (publicado por GitHub Actions)](instalador_windows/FUTUREO_VJOY_v0_5_2_LAB_NOMBRES_PNP.zip)**

La captura del usuario confirmo **4 mandos HID** en `joy.cpl`,
pero Windows muestra el mismo nombre de VHF en los cuatro. No convertimos
los mandos en un solo control: se mantienen P1..P8 como dispositivos
separados con VID/PID distintos.

- **PROBAR NOMBRES PnP** (nuevo): usa
  `SetupDiSetDeviceRegistryPropertyW` / `SPDRP_FRIENDLYNAME`
  sobre los hijos HID de FUTUREO verificados por **ascendencia PnP
  `ROOT\\FUTJOY01..08`**. Requiere UAC y confirmacion explicita.
- **VER NOMBRES PnP**: consulta el `FriendlyName` sin modificar Windows.
- **RESTAURAR PnP**: revierte solamente los nombres que la prueba modifico;
  el respaldo esta en `%LOCALAPPDATA%\\FUTUREO_VJOY\\pnp_names_backup.json`.
- La opcion anterior **ETIQUETAR OEM (DirectInput)** permanece disponible y
  conserva respaldos independientes. Para usarla en P1..P4,
  seleccionar Cantidad=4, aceptar UAC, y cerrar/reabrir `joy.cpl`.
- **No se cambia FutJoy.sys, FutJoy.cat, certificados, INF, reportes HID,
  ni se instala/desinstala el driver al probar nombres PnP.**
- `SPDRP_FRIENDLYNAME` es un nombre PnP, no el `HID Product String`.
  **No esta demostrado que `joy.cpl` lo respete** con VHF.
  Windows puede seguir mostrando el nombre generico; si ocurre,
  restaurar PnP y documentar la prueba en lugar de modificar el SYS.

Prueba recomendada: instalar la GUI del ZIP sin ejecutar INSTALAR.bat,
verificar primero en **VER NOMBRES PnP**, usar PROBAR para 4 puestos,
cerrar/reabrir `joy.cpl`; si no cambia, usar RESTAURAR PnP.
Se preserva v0.5.1 funcional como rollback.

## FUTUREO VJOY v0.5.1 - identificacion visual P1-P8 (LAB)

**[Descargar paquete v0.5.1 tras publicacion de GitHub Actions](instalador_windows/FUTUREO_VJOY_v0_5_1_LAB_IDENTIFICACION_P1_P8.zip)**

La captura en Windows confirma cuatro mandos reconocidos, pero `joy.cpl`
muestra el mismo nombre "Dispositivo HID de marco de HID virtual (VHF)" en
todos. Eso no significa que sean el mismo dispositivo: este driver de LAB
ya asigna VID:PID diferentes `F7A0:2101` (P1), `F7A0:2102` (P2),
`F7A0:2103` (P3) y `F7A0:2104` (P4). La v0.5.1 **no modifica
ni vuelve a firmar** el controlador SYS/CAT existente.

- La GUI presenta **DETECTADO / NO DETECTADO** para P1...P8 consultando
  las interfaces HID realmente presentes. Refrescar no requiere UAC.
- Selecciona P1, P2, P3 o P4, abre `joy.cpl` > Propiedades y pulsa
  **IDENTIFICAR P SELECCIONADO**: observaras el eje X y boton 1 moverse
  para **ese** mando (5 s para cambiar de ventana, 5 pulsos).
- Para intentar diferenciar nombres en `joy.cpl`, selecciona
  **Cantidad=4** y pulsa **ETIQUETAR EN WINDOWS**. Acepta UAC,
  confirma la escritura reversible, cierra `joy.cpl` por completo y
  vuelve a abrir. Usa **VER ETIQUETAS** para diagnosticar los valores.
- Los alias se pueden ampliar de P1..P2 a P1..P4, hasta P1..P8,
  conservando el respaldo original. **RESTAURAR NOMBRES** revierte todo.
- Si `joy.cpl` o un juego sigue mostrando "HID VHF Driver", el alias
  OEM no sustituye el `HidD_GetProductString` interno que controla VHF.
  Comprueba identidad con VID:PID y movimiento del dispositivo.

Se conserva el paquete v0.5.0 anterior. La v0.5.1 no sustituye la
validacion manual de P2-P8 en Windows ni transforma HID en XInput.

## Correccion para instalar P2 tras P1 (codigo PnPUtil 259)

**Hotfix del instalador, 22-nov-2026.** En el ZIP v0.5.0 el boton
CREAR DISPOSITIVOS se detenía al recibir `259` de `pnputil /add-driver /install`,
aunque Windows ya tuviera `FutJoy.inf` en su almacen (por ejemplo, `oem15.inf` en P1).
Segun Microsoft, `259 / ERROR_NO_MORE_ITEMS` indica que no hay dispositivo
compatible para actualizar o ya hay un controlador adecuado; no prueba por si
mismo un error de firma.

**Para quienes ya extrajeron el ZIP v0.5.0:**
1. Con la GUI cerrada, obtener la [version corregida de instalador.ps1](instalador_windows/HERRAMIENTAS/instalador.ps1).
2. Reemplazar **unicamente** `HERRAMIENTAS/instalador.ps1` dentro de la
   carpeta descomprimida. No cambiar el SYS/CAT/INF/cer ni la lista SHA256.
3. Abrir `ABRIR_GUI.bat`, seleccionar Cantidad=2 y CREAR DISPOSITIVOS;
   confirmar UAC y las preguntas en consola. El instalador conserva P1 y
   crea solamente los puestos que falten.
4. Abrir `joy.cpl` y verificar P1 y P2 por separado. Si no aparece P2,
   ejecutar DIAGNOSTICAR e inspeccionar el registro de SetupAPI.

El ZIP publicado de v0.5.0 se conserva intacto como referencia de laboratorio;
**para corregir el error 259 en una copia ya descargada hay que sustituir el PS1**.
Este cambio no certifica la instalacion o funcionamiento de P2 hasta probarlo
en Windows. Tampoco convierte el driver en uno oficialmente firmado.

## FUTUREO VJOY v0.5.0 - GUI sin DevCon y nombres DirectInput

**[Descargar ZIP v0.5.0 del GUI corregido](instalador_windows/FUTUREO_VJOY_v0_5_0_LAB_GUI_SIN_DEVCON.zip)**

El primer mando P1 fue comprobado en Windows: joy.cpl mostro 2 ejes
X/Y y 16 botones; la prueba del eje X y boton 1 funciono.

CREAR DISPOSITIVOS en el GUI ya NO usa devcon.exe. Llama al mismo
instalador PowerShell que funciona con SetupAPI/pnputil de Windows,
para 1..8 puestos y con permisos UAC cuando sea necesario.
QUITAR SELECCIONADO solo elimina el puesto escogido y conserva
el controlador y los otros puestos.

ETIQUETAR EN WINDOWS aplica opcionalmente alias OEM en joy.cpl/DirectInput
con copia de seguridad y RESTAURAR NOMBRES. Se debe cerrar y reabrir
joy.cpl para comprobarlo. Esto NO cambia la cadena HID interna que VHF
anuncia como HID VHF Driver; algunos juegos pueden seguir mostrando
ese nombre generico.

El driver SYS/CAT no se recompilo para esta version; se reutiliza el
paquete test-signed que ya funciono con P1. No reinstalar P1 si ya
funciona; extraer el ZIP v0.5.0, ejecutar ABRIR_GUI.bat y probar P2
con Cantidad=2. Los 8 mandos independientes siguen por validar.
## Prueba funcional de P1 - FUTUREO VJOY v0.4.3

**Windows ya detecto P1 en un equipo secundario de laboratorio:** ROOT\\FUTJOY01\\0000, estado PnP OK, dispositivo HID F7A0:2101. El HID Product String aparece como `HID VHF Driver`. Este dato confirma enumeracion HID, **no** todavia entrada funcional como gamepad ni nombres HID individuales.

**[Descargar ZIP v0.4.3 para probar P1](instalador_windows/FUTUREO_VJOY_v0_4_3_LAB_PRUEBA_MANDO_P1.zip)**. Incluye el nuevo `PROBAR_MANDO_1.bat` y el diagnostico corregido. El driver SYS/CAT y certificado de prueba reutilizan la compilacion de laboratorio anterior; no se modifico el binario kernel.

Para usarlo: descomprimir ZIP completo, ejecutar `PROBAR_MANDO_1.bat`, abrir las propiedades del gamepad en `joy.cpl` y observar el boton 1 y el eje X mientras corre la prueba. **No es necesario reinstalar el driver ya instalado** para probar los controles. Solo despues de confirmar P1 deberiamos probar P2-P8.

La cadena de producto HID generica es una limitacion de VHF; su configuracion publica no tiene un campo para cambiar libremente esa cadena. Las etiquetas PnP y los alias DirectInput no sustituyen el Product String HID.

## FUTUREO VJOY v0.4.2 - diagnostico del error E_ACCESSDENIED

**ZIP actualizado del instalador para computadora secundaria:**

[Descargar instalador v0.4.2 (con diagnostico del certificado)](instalador_windows/FUTUREO_VJOY_v0_4_2_LAB_DIAGNOSTICO_CERTIFICADOS.zip)

Se identifico que `Import-Certificate` devolvia 0x80070005 incluso
despues de elevar el menu mediante UAC. Esta version indica si falla
`LocalMachine\Root` o `LocalMachine\TrustedPublisher`; prueba
`certutil -addstore` como alternativa oficial y **no intenta eludir**
directivas o controles de seguridad. Incluye
`DIAGNOSTICAR_CERTIFICADO.bat` de solo lectura y retira los certificados
introducidos por el intento actual si se produce un error.

El paquete y la sintaxis de los scripts pasaron las pruebas Windows de
GitHub Actions, pero **no se ha verificado su instalacion real** en el
equipo secundario. Empezar con un mando y enviar la salida del
diagnostico si vuelve a fallar. No desactivar Windows Defender,
Secure Boot ni modificar las ACL de los almacenes para forzar la
instalacion de un driver experimental.
# FUTUREO VJOY - Controlador HID propio para MULTIMANDO

**Estado: v0.5.0 de laboratorio. P1 instalado y probado en Windows; requiere firma oficial para distribucion general.**

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
3. Para crear instancias root se usa SetupAPI y pnputil integrados en Windows (sin DevCon), con confirmacion UAC y el paquete de laboratorio firmado.
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

## Instalador corregido v0.4.1 — error 0x80070005

El ZIP de laboratorio **v0.4.1** corrige el error de permisos cuando
se elegia INSTALAR desde el menu: la ventana pide UAC al abrirse,
antes de importar el certificado en `LocalMachine`.

[Descargar FUTUREO VJOY v0.4.1 (ZIP instalador)](instalador_windows/FUTUREO_VJOY_v0_4_1_LAB_INSTALADOR_PERMISOS_CORREGIDOS.zip)

Ejecuta `INSTALAR.bat`, autoriza la solicitud de administrador y prueba
**un solo mando** antes de crear ocho. El ZIP conserva el controlador
firmado para pruebas, no para distribucion normal. No se ha confirmado
su instalacion real en Windows; si alguna directiva de Windows bloquea
la importacion, el instalador ahora presenta una explicacion.

## ZIP de instalacion para computadora secundaria (laboratorio)

**Paquete descargable desde el repositorio:**

[Descargar FUTUREO_VJOY_v0_4_LAB_INSTALADOR_TEST_FIRMADO.zip](instalador_windows/FUTUREO_VJOY_v0_4_LAB_INSTALADOR_TEST_FIRMADO.zip)

- Contenido: `FutJoy.sys`, `FutJoy.inf`, catalogo `.cat`, certificado de prueba `.cer`, scripts `.bat`, administrador Python y desinstalador.
- Compilado y firmado para **TESTSIGNING** de laboratorio, no con firma oficial de Microsoft.
- Extraer todo el ZIP; leer `LEEME_PRIMERO.txt` antes de ejecutar `INSTALAR.bat`.
- Empezar con `INSTALAR_1_MANDO.bat`; comprobar en `joy.cpl` antes de intentar ocho mandos.
- No instalar en la computadora principal. La enumeracion y el funcionamiento reales del driver siguen sin verificarse.
