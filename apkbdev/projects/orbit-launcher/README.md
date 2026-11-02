# Orbit Launcher v0.11 — Glass extra transparente | ARCHMOBA

## Novedad de v0.11

- **55 % de opacidad global** en cada elemento flotante, incluyendo iconos, simbolo `+`, borde y contenedor circular. Los elementos se atenúan juntos mediante `setAlpha(0.55f)`.
- **Efecto glass más transparente**: gradiente circular de tonos azul-gris y azul oscuro con transparencias internas de 140/255 y 160/255, y contorno cian translúcido de 190/255, antes de aplicar la opacidad global.
- Fondo resultante **más transparente que los propios iconos**, pero los contornos siguen siendo distinguibles.
- **Todos los contenedores son círculos reales** (`GradientDrawable.OVAL`), con recorte del icono interno al círculo.

## Se conserva exactamente

- Al instalar sin accesos, solo aparece `+`. No gira con los sensores.
- Al añadir la primera app, desaparece `+`; mantener pulsado cualquier icono abre **Añadir aplicación / Subir un lugar / Bajar un lugar / Quitar del panel**.
- Los iconos se mantienen al borde derecho, con desplazamiento vertical -52 dp.
- Movimiento mediante sensores corregido según orientación visible de Android, exclusivamente para iconos de aplicaciones.
- Selección y orden guardados localmente; scroll de accesos cuando hace falta.
- Servicio flotante; sin pantalla grabada ni Internet.

## Instalación

APK debug de prueba para Android 8 o posterior. Si la firma debug difiere, puede ser necesario desinstalar la versión anterior, perdiendo las preferencias guardadas. Se debe validar el aspecto visual directamente en el móvil.

Fuente en `apkbdev/projects/orbit-launcher`. GitHub Actions genera el APK.
