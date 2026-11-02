# Orbit Launcher v0.17 — Reposo profundo durante bloqueo

Al apagar la pantalla, Orbit retira el dock flotante, detiene el sensor y no procesa notificaciones. Mantiene solamente el servicio en primer plano y un receptor de desbloqueo para volver a funcionar. No se puede apagar absolutamente todo y reactivarse de manera garantizada.

Al desbloquear (ACTION_USER_PRESENT), consulta una sola vez las notificaciones activas, conserva solo las posteriores al ultimo toque por aplicacion, reconstruye el dock y reactiva los sensores. Al tocar un icono desaparece su punto verde hasta una notificacion posterior. Mientras el telefono esta desbloqueado, los avisos nuevos siguen siendo instantaneos.

Se conserva el estilo de circulos glass con 55 % de opacidad, posicion derecha, + solo en lista vacia, menu Añadir/Subir/Bajar/Quitar, y giro suave con ahorro de bateria.

Importante: el acceso a notificaciones es opcional y sensible; Play Protect puede bloquear la instalacion de APKs de prueba. Android puede suspender servicios por politicas de ahorro de energia. El efecto del ahorro necesita mediciones en un dispositivo real.
