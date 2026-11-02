# Orbit Launcher v0.12 — Rendimiento y batería optimizados | ARCHMOBA

## Optimizaciones

1. **Menos lecturas del sensor:** el intervalo solicitado pasa de `SENSOR_DELAY_GAME` (rápido) a `60 000 µs` (aproximadamente 16,7 muestras/s). Android lo trata como una preferencia: la frecuencia real varía según el fabricante.
2. **Redibujado condicional:** no se recalculan las rotaciones visuales si el cambio de ángulo es menor a `1,25°`; limitación de 55 ms entre actualizaciones gráficas.
3. **Pantalla apagada:** el servicio escucha `ACTION_SCREEN_OFF` y llama a `SensorManager.unregisterListener`; el sensor deja de funcionar para Orbit durante el bloqueo. Con `ACTION_SCREEN_ON` vuelve a registrarse automáticamente si hay accesos.
4. **Sin iconos, sin sensor:** cuando solo aparece `+`, el sensor no se registra. El botón `+` permanece inmóvil.
5. **Sin lecturas o dibujados innecesarios:** se comprueba `PowerManager.isInteractive` y, si está inactivo, se suspende el sensor. Al volver se restablece el estado inicial derecho.
6. **Gestión de recursos:** si el panel se oculta, recrea o detiene, el sensor se desregistra y los receptores dinámicos se limpian al destruir el servicio.

## Diseño conservado de v0.11

- Círculos verdaderos con efecto `glass`, iconos, contenedores y bordes con 55 % de opacidad global.
- Iconos completos en el borde derecho, 52 dp más arriba que el centro.
- `+` solo cuando la lista está vacía, nunca gira.
- Pulsación larga con **Añadir / Subir / Bajar / Quitar**.
- Giro continuo y suave para las aplicaciones, respetando la orientación actual de Android. **No** se restringe a la cruceta de cuatro ángulos.
- Selección y orden guardados entre sesiones; lista desplazable.

## Notas de uso

Android 8 o superior. Se requiere `Mostrar sobre otras aplicaciones`. No se necesita Internet ni grabación de pantalla. Las optimizaciones reducen la carga solicitada, pero el ahorro real de batería depende del hardware y debe comprobarse en un teléfono real (no está medido en un dispositivo).

La compilación en `apkbdev` ejecuta pruebas Java de orientación y de la política de actualización gráfica.

**Instalación:** si la firma debug no coincide con la de la versión anterior, Android puede exigir desinstalarla, con pérdida de los accesos guardados.
