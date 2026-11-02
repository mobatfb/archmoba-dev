# Orbit Launcher v0.3 — Solo dock derecho | ARCHMOBA

## Comportamiento

- **Al abrir por primera vez solo se muestra un botón flotante `+` en el lado derecho.** Ninguna app se añade automáticamente.
- Al pulsar `+`, aparece un listado de aplicaciones instaladas con buscador.
- Al elegir una app, su icono se añade a la columna flotante del borde derecho, **sin abrirla de inmediato**.
- Al tocar el icono, Android abre la aplicación real, normalmente a pantalla completa, y el dock permanece flotando a la derecha.
- **Mantener pulsado un icono** permite quitarlo del panel (no desinstala la aplicación).
- Se conserva el orden de incorporación y la selección persiste tras cerrar la app y reiniciar el servicio.
- Si hay muchos iconos, se pueden deslizar verticalmente, mientras el `+` sigue accesible al final de la columna.
- La notificación del servicio ofrece **Cerrar** para detener el dock, y abrir Orbit nuevamente lo restaura.

## Eliminado respecto de v0.2

Se eliminaron las barras superior, inferior e izquierda, los iconos predeterminados, el fondo, la ventana central, el visor de captura, el modo espejo, y los botones APPS, COMPLETA, ESPEJO, SALIR. Solo queda el panel de accesos elegido por el usuario en la derecha.

## Permisos y compatibilidad

Necesita `SYSTEM_ALERT_WINDOW` (Mostrar sobre otras aplicaciones) para mantener el botón y los iconos flotantes; solicita el permiso en el primer arranque. Usa un servicio en primer plano para conservar el panel visible. No necesita conexión a Internet, acceso a datos privados ni grabación de pantalla.

El sistema Android y algunos fabricantes pueden limitar las ventanas flotantes o el inicio de aplicaciones desde segundo plano. No se redimensionan las apps ni se intercepta el contenido de otras ventanas.

## Instalación

Si el APK anterior se firmó con otra clave debug, desinstala Orbit Launcher v0.2 antes de instalar v0.3. Se perderán las preferencias del Orbit anterior, pero esta versión inicia vacía como se solicitó. Abre Orbit, acepta **Mostrar sobre otras apps**, y toca **+** para elegir los accesos.
