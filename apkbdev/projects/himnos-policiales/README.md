# Himnos Policiales — APK Android independiente

Proyecto nativo Android **basado en el boceto aprobado**, actualizado para retirar el escudo central de la cabecera, dejando el título **HIMNOS POLICIALES**. Paquete `com.archmoba.himnospoliciales` para Android 8.0 o superior. Incluye el **Himno Nacional del Ecuador (2:22)** y el **Himno de la Policía Nacional (1:34)** con los audios originales entregados por el usuario. No utiliza Internet, permisos de red, cuentas ni anuncios.

## Controles únicos

El botón con el **escudo del Ecuador** inicia desde 0:00 ese himno y sube gradualmente de 0 a 100% de volumen durante 2 segundos. El botón con el **escudo policial** hace lo mismo con el otro himno. Si se toca uno mientras suena el otro, el nuevo comienza de inmediato. **STOP** detiene completamente el audio de inmediato, sin transición ni espera, y reinicia el progreso a 0:00. No hay botones de siguiente, anterior, pausa ni control manual del volumen. La **barra de progreso se encuentra abajo** y es solamente visual; no admite adelantar, retroceder ni cambiar la posición de reproducción.

El fondo, los escudos, el ícono y la cinta inferior fueron preparados a partir del último boceto aprobado. Son gráficos ilustrativos de la aplicación, no acreditan afiliación oficial.

## Compilación con APKBDEV

Los recursos exactos se conservan en 11 partes binarias dentro de `media/`, para garantizar integridad incluso en transferencias por API. Se reconstituyen y validan usando SHA-256 antes de compilar.

```bash
python3 apkbdev/projects/himnos-policiales/unpack_resources.py
python3 apkbdev/tools/build_apk.py --project himnos-policiales
```

También se construye automáticamente al modificar el proyecto, con `.github/workflows/apkbdev-build.yml`. El APK se publica en la sección **Releases**, como `himnos-policiales-debug.apk`.

Archivo fuente principal: `app/src/main/java/com/archmoba/himnospoliciales/MainActivity.java`. Audio sin necesidad de red, compatible con `MediaPlayer` del sistema Android.


## Ajustes de interfaz v1.2.0
- **Un solo fondo vertical** generado a partir de la cabecera y cinta originales. Ya no hay áreas ni barras rectangulares oscuras detrás de los controles.
- **Botones flotantes con transparencia**: emblema del Ecuador, STOP y emblema policial, dibujados encima del fondo.
- **STOP inmediato**: al tocar el botón se silencia, se libera el reproductor y se pone el contador a 00:00 sin espera ni disminución gradual. El aumento gradual de volumen durante 2 segundos al pulsar un himno se mantiene.
- **Ícono nuevo aportado por el usuario**: mitad emblema Ecuador y mitad emblema policial, incluido como recurso Android local.
- Barra de tiempo inferior estrictamente informativa; no permite arrastrar, adelantar o retroceder.
- Los dos MP3 permanecen incluidos; funcionamiento sin conexión.

Todos los recursos visuales se preparan en tiempo de compilación mediante Pillow y `unpack_resources.py`, sin enlaces externos.

## Correcciones v1.2.1
- Eliminado el recorte plateado y el marco de las tarjetas antiguas de los escudos; ahora cada silueta se genera con alfa transparente sobre el fondo continuo.
- Barra de progreso de solo lectura: se elimina por completo la llamada a `MediaPlayer.seekTo` y el control deslizante.
- STOP permanece inmediato; Play conserva el aumento de volumen de 2 segundos.
