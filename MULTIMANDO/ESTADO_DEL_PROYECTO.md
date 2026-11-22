# MULTIMANDO - Estado verificado y siguientes pasos

Fecha: 22 de noviembre de 2026. Actualizar tras cada cambio.

## Estructura de GitHub

- `MANDOWEB/`: web PHP dentro de su carpeta propia. En GitHub sigue publicada v6.1.3.
- `ANFITRION/`: Python anfitrion que figura en GitHub v1.5.0, con ViGEmBus y solo 2 mandos Xbox.
- `FUTUREO_VJOY/`: codigo C/KMDF con VHF, GUI Python, pruebas y herramientas Windows.

## Fuera del repositorio (archivos ya generados previamente)

- Web MULTIMANDO v6.2.0 (1-8 jugadores), pendiente de publicar en `MANDOWEB/`.
- Anfitrion MULTIMANDO v1.8.1, con vJoy y autoinstalacion de dependencias, pendiente de publicar en `ANFITRION/`.
- ADVERTENCIA: estas dos versiones no se deben mezclar con la pareja antigua v6.1.3/v1.5.0.
- El `FRASE_CIFRADO.php` es un secreto de despliegue, no debe subirse a GitHub.

## Lo que ya ha sido verificado en GitHub Actions

- Compilacion de `FutJoy.sys` para Windows x64: 0 errores, 0 advertencias.
  https://github.com/mobatfb/archmoba-dev/actions/runs/45004213793
- `FutJoy.inf` verificado con InfVerif `/w`: exitoso.
  https://github.com/mobatfb/archmoba-dev/actions/runs/45004213766
- Pruebas de protocolo y adaptador Python: exitosas en Windows y Linux.
- Estos resultados NO demuestran que el driver arranque ni que Windows lo haya reconocido como dispositivo.

## Prioridades ordenadas

1. **Sincronizar web y anfitrion**: trasladar las versiones v6.2.0 y v1.8.1 al repo sin la frase secreta. Revisar los nuevos formatos de comunicacion y las rutas PHP.
2. **Preparar paquete de driver**: FutJoy.sys + FutJoy.inf + sumas SHA-256, sin publicar secretos ni prometer instalacion.
3. **Pruebas en Windows aislado**: comprobar los 8 hijos HID en el administrador de dispositivos y en `joy.cpl`, controles independientes, ejes, botones, cierre y desconexion.
4. **Nombres en el juego**: comprobar el Product String HID y los nombres OEM/DirectInput por separado. IDs PnP y VID/PID distintos NO garantizan nombres visibles distintos.
5. **Seguridad del controlador**: auditar acceso a `DeviceIoControl`, concurrencia y watchdog de seguridad para evitar botones pegados.
6. **Identificadores legales**: cambiar VID/PID de desarrollo por identificadores autorizados antes de distribuir.
7. **Firma**: tramitar firma valida de Microsoft para kernel de Windows 10/11 a traves de Hardware Dev Center; la cuenta requiere certificado EV.
8. **Integracion**: adaptar el anfitrion v1.8.1 para seleccionar motor `vJoy` / `FUTUREO VJOY` sin alterar FIFO, turnos ni CONTROLADO/REMOTO.
9. **Prueba final**: dos a ocho jugadores por web; comparar al menos dos juegos de PC, uno DirectInput y otro de entrada XInput (el HID actual no es un mando Xbox).

## Limites importantes

- Esta version de FUTUREO VJOY NO esta firmada ni instalada; no usar `FutJoy.sys` en el PC principal.
- InfVerif valido el INF, pero falta su catalogo `.cat` firmado y las pruebas reales de instalacion.
- El identificador VID 0xF7A0 es de ejemplo para laboratorio; no distribuir como si fuera un VID concedido al proyecto.
- No desactivar Secure Boot para saltarse la politica de firmas.
- El driver usa dispositivos HID/DirectInput, no proporciona XInput de forma nativa.

Fuentes oficiales de firma:
- https://learn.microsoft.com/en-us/windows-hardware/drivers/dashboard/code-signing-reqs
- https://learn.microsoft.com/en-us/windows-hardware/drivers/dashboard/driver-signing-offerings
