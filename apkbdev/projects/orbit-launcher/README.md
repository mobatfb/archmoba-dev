# Orbit Launcher v0.14 — Notificaciones reales con punto verde

## Diseño aprobado

- Badge pequeño y circular de **13 dp**, verde brillante y con **borde blanco**, ligeramente sobresaliente en la esquina superior derecha de cada app.
- Aparece automáticamente cuando una aplicación seleccionada tiene una **notificación activa** compatible; se retira al desaparecer la última notificación.
- El badge no rota: los iconos conservan el giro suave optimizado en v0.12.
- Se mantiene la forma circular de los contenedores, efecto glass y opacidad global del 55 % en los iconos y su fondo.
- El botón `+` solo aparece si no hay iconos, nunca gira.

## Activación y privacidad

Android **no permite saber las novedades de otras apps sin autorización**. Tras añadir la primera app, Orbit presenta un aviso opcional y abre **Ajustes > Acceso a notificaciones** solamente si el usuario lo decide. Habilita "Orbit - Indicadores de notificacion".

El permiso de Android concede potencialmente acceso amplio a las notificaciones. El código de Orbit utiliza únicamente **el nombre del paquete, la categoría y las banderas de cada notificación** para decidir si muestra el punto. **No extrae ni guarda texto, conversaciones, contenido de mensajes, imágenes ni contactos**, ni los envía a Internet.

Si no concedes el permiso, Orbit conserva todas sus funciones y no muestra puntos automáticos. Puedes abrir el permiso más adelante manteniendo pulsado cualquier icono y eligiendo **Activar indicadores verdes**. Si ya está activo, esa opción permite volver a ajustes.

El indicador significa **notificación activa**, no garantiza que sea un mensaje sin leer. Se excluyen normalmente avisos persistentes, servicios en primer plano, reproducción, llamadas, navegación y progreso.

## Interacción y rendimiento

- Pulsación corta: abrir la aplicación.
- Pulsación larga: **Añadir aplicación / Subir un lugar / Bajar un lugar / Quitar del panel / Configurar indicadores verdes**.
- Los puntos se actualizan sin reconstruir los iconos ni activar más sensores.
- Los sensores siguen optimizados: petición de actualización cada 60 ms, sin repintar microgiros, pausa cuando se apaga la pantalla.
- Selección y orden se conservan localmente.

## Instalación

Android 8.0+. Solo necesitas permiso "Mostrar sobre otras apps" para usar el dock; el permiso de notificaciones es opcional. Este APK es de pruebas y utiliza firma debug. Si no coincide la firma con una versión anterior, quizá tengas que desinstalarla (lo que eliminará las preferencias guardadas).

Proyecto: `apkbdev/projects/orbit-launcher`. Compilación: `.github/workflows/apkbdev-build.yml`.
