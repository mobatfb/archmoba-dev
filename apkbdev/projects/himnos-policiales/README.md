# Himnos Policiales — APK Android independiente

Proyecto nativo Android **basado en el boceto aprobado**. Paquete `com.archmoba.himnospoliciales` para Android 8.0 o superior. Incluye el **Himno Nacional del Ecuador (2:22)** y el **Himno de la Policía Nacional (1:34)** con los audios originales entregados por el usuario. No utiliza Internet, permisos de red, cuentas ni anuncios.

## Controles únicos

El botón con el **escudo del Ecuador** inicia desde 0:00 ese himno y sube gradualmente de 0 a 100% de volumen durante 2 segundos. El botón con el **escudo policial** hace lo mismo con el otro himno. Si se toca uno mientras suena el otro, el nuevo comienza de inmediato. **STOP** disminuye gradualmente el volumen hasta cero en 2 segundos, detiene totalmente la reproducción y reinicia el progreso a 0:00. No hay botones de siguiente, anterior, pausa ni control manual del volumen. La **barra de progreso se encuentra abajo** y permite buscar una posición.

El fondo, los escudos, el ícono y la cinta inferior fueron preparados a partir del último boceto aprobado. Son gráficos ilustrativos de la aplicación, no acreditan afiliación oficial.

## Compilación con APKBDEV

Los recursos exactos se conservan en 11 partes binarias dentro de `media/`, para garantizar integridad incluso en transferencias por API. Se reconstituyen y validan usando SHA-256 antes de compilar.

```bash
python3 apkbdev/projects/himnos-policiales/unpack_resources.py
python3 apkbdev/tools/build_apk.py --project himnos-policiales
```

También se construye automáticamente al modificar el proyecto, con `.github/workflows/apkbdev-build.yml`. El APK se publica en la sección **Releases**, como `himnos-policiales-debug.apk`.

Archivo fuente principal: `app/src/main/java/com/archmoba/himnospoliciales/MainActivity.java`. Audio sin necesidad de red, compatible con `MediaPlayer` del sistema Android.
