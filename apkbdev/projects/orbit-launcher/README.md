# Orbit Launcher v0.15 — Indicador verde sin acceso sensible

Esta versión responde al bloqueo mostrado por Google Play Protect en la v0.14.

- Se eliminó **NotificationListenerService** y cualquier petición de acceso a notificaciones.
- El indicador verde sigue siendo un pequeño círculo con borde blanco en la esquina superior derecha, ahora activable manualmente manteniendo pulsado un icono.
- Menú contextual: **Añadir / Subir / Bajar / Quitar / Activar o quitar indicador verde**.
- No intenta leer mensajes, ni notificaciones ni su contenido.
- Se mantiene el dock derecho, círculos, 55 % de opacidad, botón + solo sin iconos y sensor optimizado.

## Compatibilidad

Android 8+. Necesita exclusivamente el permiso de superposición para el dock y el servicio en primer plano. **No se garantiza que Play Protect permita la instalación**: la evaluación también considera firma, reputación y otras señales. No desactives Play Protect para instalar Orbit.

En el futuro, las notificaciones automáticas pueden requerir revisión del modelo de permisos y una distribución confiable. El proyecto de prueba se compila en `apkbdev` con GitHub Actions.
