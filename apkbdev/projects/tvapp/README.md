# TVAPP Android | ARCHMOBA APKBDEV

Aplicación Android nativa de prueba basada en la interfaz de `TVAPP/tvapp.py`, sin
Tkinter ni VLC para Windows. Identificador: `com.archmoba.tvapp`. Android 8+.

## Funcionalidad

- Pantalla vertical, cabecera GDX y visor de video donde antes aparecía el logo.
- Listas IPTV-org M3U: Todas, Noticias, Deportes, Películas, Música, por categoría,
  país e idioma, y accesos Ecuador/Español.
- Buscador y paginación de canales, favoritos guardados en el dispositivo.
- Logotipos por `tvg-logo`, obtenidos por red, sin descarga en el hilo principal.
- Video HLS con Media3 ExoPlayer embebido en el visor; pausa, mute, cierre y
  botón para abrir el enlace en un reproductor externo compatible.
- Barra inferior flotante Inicio, Vivo, VOD, Partidos y Cuenta.

La APK no ejecuta `TVAPP/tvapp.py`; es su adaptación nativa. La transmisión
requiere Internet y que cada URL M3U siga funcionando, sin restricciones
geográficas ni de terceros. Algunos formatos/transmisiones no serán compatibles.
No existe inicio de sesión, compras ni servicios de pago. No se incluyen listas
privadas ni credenciales.

## Compilar con el kit existente

```bash
python3 apkbdev/tools/build_apk.py --project tvapp
```

En GitHub Actions: **APKBDEV - Android APK Builder**. Los commits de este
proyecto disparan la construcción automáticamente; como alternativa se puede
usar `Run workflow` con `project=tvapp`. La APK debug firmada para pruebas
queda como artifact `APKBDEV-tvapp` y como release de pruebas.