# Orbit Launcher v0.7 — Restaurar posición horizontal | ARCHMOBA

## Cambio solicitado

- **Posición horizontal restaurada a v0.5:** los iconos y el círculo + vuelven a ser **completamente visibles**, alineados con el borde derecho (`params.x = 0`).
- No se modificó la altura del panel: continúa subido un espacio de icono respecto del centro (`params.y = -step`, 52 dp).
- Se quitó `FLAG_LAYOUT_NO_LIMITS` porque ya no hace falta sacar el círculo fuera de la pantalla.

## Funcionalidad conservada

- Al comenzar por primera vez solo aparece el botón `+`.
- El usuario escoge qué aplicaciones aparecen en la columna derecha.
- Pulsación larga: **Subir un lugar / Bajar un lugar / Quitar**.
- Lista desplazable y orden persistente.
- Sensor de gravedad o acelerómetro para reaccionar suavemente a la inclinación del teléfono.
- Actualización del dock al cambiar entre vertical y horizontal si el sistema comunica el giro.
- Permiso **Mostrar sobre otras aplicaciones** y servicio en primer plano con notificación.

## Compatibilidad

Android 8.0 o posterior. Según el fabricante, Android puede limitar superposiciones o la rotación de pantalla.

Para instalar una APK debug firmada con una clave distinta de la anterior, puede ser necesario desinstalar la versión previa (se perderán las preferencias). El código se guarda en `apkbdev/projects/orbit-launcher` y la compilación se realiza con GitHub Actions.
