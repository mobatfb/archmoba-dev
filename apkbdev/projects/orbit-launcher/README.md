# COLIBRÍ v0.21 — identificador Android propio

La aplicación usa `applicationId` y `namespace` **`com.archmoba.colibri`** y su código Java se organiza en el paquete `com.archmoba.colibri`. Se conserva el nombre visible **COLIBRÍ** y su icono del colibrí. Android tratará esta versión como una aplicación distinta de las ediciones anteriores; no se migran automáticamente la lista de iconos, la posición ni los permisos. Puede instalarse junto a la aplicación anterior.

# COLIBRÍ v0.20 — icono oficial y nombre de aplicación

Nombre visible: COLIBRÍ by ARCHMOBA. Icono visual: tercer concepto aprobado, colibrí azul eléctrico con halo, integrado como WebP optimizado 192x192 en res/drawable/colibri_icon.webp. En esta versión se conservaba el identificador anterior y todas las funciones previas (puntos verdes, giro, arrastre, reposo).

# Orbit Launcher v0.19 — Panel vertical ajustable

Nueva funcion: un tirador cian pequeno sobre el panel permite arrastrar el conjunto entero hacia arriba o abajo, sin desplazamiento horizontal. La ubicacion se guarda en preferencias y se restaura al volver del bloqueo y al reiniciar el servicio, ajustada a los limites de la pantalla. Los iconos conservan toque, pulsacion larga y desplazamiento interno para listas extensas. Se mantienen los circulos 55%, giro y avisos verdes.

# Orbit Launcher v0.18 — Reposo profundo durante bloqueo

Al apagar la pantalla, Orbit retira el dock flotante, detiene el sensor y no procesa notificaciones. Mantiene solamente el servicio en primer plano y un receptor de desbloqueo para volver a funcionar. No se puede apagar absolutamente todo y reactivarse de manera garantizada.

Al desbloquear (ACTION_USER_PRESENT), consulta una sola vez las notificaciones activas, conserva solo las posteriores al ultimo toque por aplicacion, reconstruye el dock y reactiva los sensores. Al tocar un icono desaparece su punto verde hasta una notificacion posterior. Mientras el telefono esta desbloqueado, los avisos nuevos siguen siendo instantaneos.

Se conserva el estilo de circulos glass con 55 % de opacidad, posicion derecha, + solo en lista vacia, menu Añadir/Subir/Bajar/Quitar, y giro suave con ahorro de bateria.

Importante: el acceso a notificaciones es opcional y sensible; Play Protect puede bloquear la instalacion de APKs de prueba. Android puede suspender servicios por politicas de ahorro de energia. El efecto del ahorro necesita mediciones en un dispositivo real.

## Correccion v0.18: restauracion al desbloquear

El dock ya no depende exclusivamente de ACTION_USER_PRESENT. Atiende tambien ACTION_SCREEN_ON y verifica con KeyguardManager que no aparezca sobre la pantalla de bloqueo. Realiza hasta 20 comprobaciones ligeras espaciadas 500 ms si el sistema todavia muestra bloqueo; al detectar desbloqueo reactiva los iconos y ejecuta un unico analisis de novedades. Cualquier apertura manual tambien reevalua el bloqueo. Mantiene el servicio en primer plano y los sensores apagados mientras la pantalla esta bloqueada. La restauracion depende de que Android mantenga vivo el servicio.
