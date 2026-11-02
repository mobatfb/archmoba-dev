# Orbit Launcher v0.5 — Dock derecho elevado | ARCHMOBA

## Cambios en v0.5

- **Más a la derecha:** la columna flotante se pega al borde derecho del dispositivo. Se ha reducido el ancho del panel de 56 dp a 50 dp, manteniendo cada icono de 48 dp.
- **Un icono más arriba:** el panel completo (iconos seleccionados y botón `+`) sube 52 dp, el equivalente a un espacio de icono. Se ajusta el límite de altura para no recortar los controles cuando hay muchas apps.
- Se conserva todo lo incorporado en v0.4: botón **+** como único elemento inicial, apps elegidas manualmente, iconos flotantes únicamente a la derecha, guardado del orden y gestión mediante pulsación larga (**Subir un lugar / Bajar un lugar / Quitar**).

## Funcionamiento

1. Abre Orbit y concede **Mostrar sobre otras apps** si Android lo solicita.
2. Al principio solo aparece el `+` a la derecha, ahora más cerca del borde y un icono más alto.
3. Pulsa `+` para seleccionar una app instalada.
4. Pulsa un icono para abrirla. Mantén pulsado para cambiar su orden o quitarlo.
5. Cuando los accesos excedan la altura disponible, desliza la columna verticalmente.

## Compatibilidad

Android 8.0 o posterior. La ubicación puede variar ligeramente según la barra de estado/navegación y la personalización del fabricante. No graba ni transmite la pantalla.

## Actualización

El ID de paquete sigue siendo `com.archmoba.orbitlauncher`. Los datos se conservan al actualizar si las firmas APK coinciden. Los APK debug generados en distintos entornos pueden tener firmas diferentes; en ese caso Android puede requerir desinstalar la versión anterior y se perderán los iconos elegidos.

Código fuente: `apkbdev/projects/orbit-launcher`; compilación: `.github/workflows/apkbdev-build.yml`.
