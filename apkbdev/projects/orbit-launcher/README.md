# Orbit Launcher v0.4 — Dock derecho personalizado | ARCHMOBA

## Novedades de v0.4

- La columna del lado derecho tiene espacio adicional para mostrar **aproximadamente dos iconos más** antes de necesitar desplazamiento, según el tamaño y los límites del dispositivo.
- Los iconos conservan 48 dp, y el espacio vertical por elemento pasa de 56 dp a 52 dp.
- **Mantener pulsado un icono** abre un menú con tres opciones:
  1. **Subir un lugar:** intercambia el icono con el inmediatamente superior.
  2. **Bajar un lugar:** intercambia el icono con el inmediatamente inferior.
  3. **Quitar:** solicita confirmación y retira el acceso del panel; **no desinstala** la app.
- El orden modificado y la lista elegida se guardan en las preferencias locales del teléfono.
- Cuando un icono es el primero o el último, la opción correspondiente muestra un aviso y no cambia el orden.

## Funcionamiento básico

1. Al instalar y abrir por primera vez, solo aparece el botón flotante `+` en el lado derecho.
2. Pulsa `+` para buscar una aplicación instalada y añadirla.
3. Pulsa su icono para abrir la aplicación real.
4. Mantén pulsado el icono para subirlo, bajarlo o quitarlo.
5. Si añades muchos accesos, puedes desplazar la lista verticalmente. El `+` permanece visible al final.
6. La notificación del servicio incluye **Cerrar**; vuelve a abrir Orbit para restaurar los accesos.

No hay fondo, visor central ni barras en la parte superior, inferior o izquierda.

## Requisitos

Android 8.0 o superior. Debes habilitar **Mostrar sobre otras aplicaciones**. El teléfono puede limitar la superposición y el lanzamiento desde segundo plano. Esta app no captura la pantalla, no necesita Internet y no controla ni redimensiona otras aplicaciones.

## Actualización

La versión 0.4 usa el mismo ID de aplicación que v0.3. Si los paquetes de prueba están firmados con certificados distintos, Android puede exigir desinstalar la versión anterior; eso borra las preferencias guardadas. Si la firma es compatible, los accesos y su orden se conservan.

El APK se construye desde `apkbdev/projects/orbit-launcher` usando `.github/workflows/apkbdev-build.yml`.
