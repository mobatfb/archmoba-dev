# Orbit Launcher v0.16 — Novedad hasta abrir la app

## Comportamiento de los indicadores verdes

1. Al llegar una notificación nueva y elegible a una aplicación, se enciende el punto verde.
2. El punto permanece hasta que se toque el icono de Orbit o se retiren las notificaciones pendientes.
3. Al tocar el icono, el punto se apaga inmediatamente y se abre la app.
4. **Las notificaciones antiguas no vuelven a encenderlo**: únicamente una publicación posterior al toque puede activarlo.
5. El reconocimiento se conserva en las preferencias locales. Al reiniciar el servicio no se reactivan avisos antiguos.

La marca es por **aplicación**, no por mensaje. Android puede actualizar notificaciones existentes o entregarlas con tiempos distintos; las actualizaciones se consideran nuevas cuando el sistema les asigna una fecha posterior al toque. Esta implementación no altera ni borra las notificaciones reales.

## Acceso y privacidad

Para detectar automáticamente nuevas notificaciones es imprescindible habilitar el acceso opcional **Orbit - Notificaciones** en ajustes Android. Es un permiso sensible que puede provocar restricciones en APK instaladas fuera de tiendas verificadas. Este código usa solo la identidad de la aplicación y el tiempo de publicación. No extrae ni guarda texto, imágenes o conversaciones, ni transmite datos a servidores.

## Sin cambios visuales

Se conservan la columna a la derecha, los círculos glass al 55% de opacidad, el punto verde con borde blanco, el botón + fijo solo sin apps, el menú de gestión y la rotación suave optimizada de batería.

## Instalación

Android 8+. APK debug experimental, sin firma estable entre compilaciones en CI. Si Android bloquea esta APK por el permiso sensible, respeta la protección; no es necesario desactivar Play Protect para usar la versión manual v0.15. El código se encuentra en apkbdev/projects/orbit-launcher.
