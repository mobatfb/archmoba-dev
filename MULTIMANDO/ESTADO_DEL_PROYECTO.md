# MULTIMANDO - Estado verificado y siguientes pasos

Fecha: 22 de noviembre de 2026. Actualizar tras cada cambio.

## Estructura de GitHub

- `MANDOWEB/`: web PHP v6.2.0 (actualizada en GitHub).
- `ANFITRION/`: Python anfitrion v1.8.1 (actualizado en GitHub); vJoy, de 1 a 8 mandos.
- `FUTUREO_VJOY/`: codigo C/KMDF con VHF, GUI Python, pruebas y herramientas Windows.

## Publicacion verificada de versiones

- Web MULTIMANDO v6.2.0 (1-8 jugadores), ya publicada en `MANDOWEB/`.
- Anfitrion MULTIMANDO v1.8.1, con vJoy y autoinstalacion de dependencias, ya publicado en `ANFITRION/`.
- Ambas versiones nuevas deben actualizarse juntas en el entorno de despliegue; no mezclar con la pareja antigua v6.1.3/v1.5.0.
- El `FRASE_CIFRADO.php` es un secreto de despliegue, no debe subirse a GitHub.

## Lo que ya ha sido verificado en GitHub Actions

- Compilacion de `FutJoy.sys` para Windows x64: 0 errores, 0 advertencias.
  https://github.com/mobatfb/archmoba-dev/actions/runs/45004213793
- `FutJoy.inf` verificado con InfVerif `/w`: exitoso.
  https://github.com/mobatfb/archmoba-dev/actions/runs/45004213766
- Pruebas de protocolo y adaptador Python: exitosas en Windows y Linux.
- Estos resultados NO demuestran que el driver arranque ni que Windows lo haya reconocido como dispositivo.

## Prioridades ordenadas

1. **Sincronizacion COMPLETADA**: web v6.2.0 y anfitrion v1.8.1 actualizados en GitHub sin la frase secreta. Pendiente desplegar en hosting y PC.
2. **Preparar paquete de driver**: FutJoy.sys + FutJoy.inf + sumas SHA-256, sin publicar secretos ni prometer instalacion.
3. **Pruebas en Windows aislado**: comprobar los 8 hijos HID en el administrador de dispositivos y en `joy.cpl`, controles independientes, ejes, botones, cierre y desconexion.
4. **Nombres en el juego**: herramienta `FUTUREO_VJOY/python/diagnostico_hid.py` añadida para consultar Product String HID real (solo lectura). Pendiente ejecutarla con un controlador instalado y comparar nombres OEM/DirectInput dentro de los juegos. IDs PnP y VID/PID distintos NO garantizan nombres visibles distintos.
5. **Seguridad del controlador**: se añadió escritor exclusivo por puesto y neutralizacion al cierre. Pendientes auditoria de permisos de `DeviceIoControl`, pruebas de concurrencia reales y watchdog para evitar botones pegados.
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

## FUTUREO VJOY v0.4 - desarrollo verificado

- El programa `python/diagnostico_hid.py` enumera HID presentes con SetupAPI y
  consulta el Product String de cada PID 0x2101-0x2108 en solo lectura.
- La GUI `futureo_vjoy_manager.py` incorpora **VER IDENTIDAD HID**.
- El driver KMDF exige escritor exclusivo por puesto con
  `WdfDeviceInitSetExclusive`. Python abre el control con comparticion 0.
- Se pasaron **26 pruebas en Windows y Linux** de protocolo, simulaciones
  de nombres HID y contratos de exclusividad.
- Compilacion x64 del driver actualizada con exito:
  https://github.com/mobatfb/archmoba-dev/actions/runs/45005850131
- El nuevo artefacto sin firma se almacena en esa ejecucion y caduca
  aproximadamente 7 dias despues de su creacion.
- Sin pruebas en hardware HID instalado. No instalar en el PC principal.
