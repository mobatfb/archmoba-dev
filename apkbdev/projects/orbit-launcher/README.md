# Orbit Launcher v0.9 — Círculos, transparencia y menú único | ARCHMOBA

## Cambios solicitados

- **Círculos reales obligatorios:** el fondo de cada app y el del botón `+` usan `GradientDrawable.OVAL`. No se utilizan rectángulos con esquinas redondas. Los iconos se recortan al contorno con `setClipToOutline(true)`.
- **Transparencia:** relleno oscuro con **75 % de opacidad**, borde cian semitransparente, icono de aplicación al 93 % de opacidad.
- **`+` sin giro:** no se añade al grupo de vistas que rotan con el sensor; se define `setRotation(0)`. El sensor no se activa si la lista está vacía.
- **`+` solo cuando no hay iconos:** una vez que el usuario añade la primera app, desaparece el `+`; al quitar la última vuelve a aparecer.
- **Un solo menú para administrar:** mantener pulsado cualquier icono de aplicación abre `Añadir aplicación`, `Subir un lugar`, `Bajar un lugar`, `Quitar del panel`. `Añadir` abre el mismo buscador de apps que el `+` inicial.
- El orden y las aplicaciones elegidas siguen almacenados localmente entre sesiones.

## Uso

1. Instala y abre Orbit. Concede **Mostrar sobre otras aplicaciones**.
2. Si la lista está vacía, aparece solo el círculo `+` a la derecha; púlsalo para añadir tu primera app.
3. Cuando existe al menos una app, **ya no aparece `+`**.
4. Mantén pulsado cualquier icono para añadir más, moverlo hacia arriba/abajo o quitarlo.
5. Al borrar el último icono reaparece `+`.

## Se conserva de v0.8

- Iconos completamente visibles junto al borde derecho, posición vertical desplazada -52 dp.
- Movimiento de los iconos por sensor de gravedad/acelerómetro, sincronizado con la orientación visible de Android. Solo los iconos de apps rotan, no el botón `+`.
- Scroll vertical cuando el usuario añade muchas aplicaciones.
- Servicio flotante en primer plano y opción de detenerlo en la notificación.
- Compatible con Android 8.0+.

## Instalación

APK debug de pruebas. Si la firma de v0.8 difiere de la nueva, Android puede pedir desinstalar la versión anterior, lo que borraría los accesos seleccionados. La compilación por CI comprueba la compilación nativa y las pruebas de orientación; la interacción debe verificarse en un teléfono real.

Código: `apkbdev/projects/orbit-launcher`. Build: `.github/workflows/apkbdev-build.yml`.
