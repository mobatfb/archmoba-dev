# ARCHMOBA TVAPP Android — 1.0.17-test

Aplicación Android nativa creada con `apkbdev`, tomando como referencia funcional `TVAPP/tvapp.py` **v1.0.17**. No ejecuta Tkinter de Windows ni VLC para escritorio: utiliza componentes Android y Media3 ExoPlayer.

## Acceso y catálogo

Al abrir la APK aparece una pantalla con dos opciones:

- **Modo local multirregión**: listas M3U de IPTV-org. Categorías `Todos`, `Categorías`, `Noticias`, `Deportes`, `Películas`, `Música`, `Países`, `Idiomas`, `Ecuador`, `Español`, `Infantil`, `Cultura`, `Documentales` y `Favoritos`.
- **Modo servidor externo**: formulario Xtream Codes con **servidor, usuario y contraseña vacíos**. El servidor sólo muestra un ejemplo (`Ej. http://servidor:puerto`). La app consulta `player_api.php` para autenticar y cargar `Xtream TV`, `Xtream Cine`, `Xtream Series`; permite explorar episodios de series.

Los menús laterales y los favoritos se filtran según el modo elegido, sin mezclar ambas fuentes. Desde la pestaña **Cuenta** se puede cambiar de modo. La app conserva la cabecera GDX, logo cuando no hay reproducción, visor de video superior, barra inferior flotante, logos de canales, búsqueda y paginación.

## Seguridad de credenciales y limitaciones

No se incluyen servidores DDNS ni cuentas privadas en la APK o repositorio. Los datos se introducen en el teléfono y la contraseña no se persiste en preferencias; los favoritos Xtream guardan sólo identificadores de contenido y un identificador derivado de servidor/usuario. Los enlaces Xtream se construyen en memoria al reproducir. Si el servidor usa **HTTP**, puede enviar credenciales en texto claro; usar HTTPS cuando esté disponible.

Se necesita Internet; no todos los canales o formatos funcionan necesariamente ni está garantizada la disponibilidad o legalidad de transmisiones de terceros. La APK requiere Android 8.0+; reproducción con Media3 ExoPlayer, compatible con HLS y ciertos streams progresivos. No sustituye la comprobación manual en un dispositivo físico.

## Construcción APKBDEV

```bash
python3 apkbdev/tools/build_apk.py --project tvapp
```

Automatización: `.github/workflows/apkbdev-build.yml`. Produce una APK debug firmada para pruebas, publicada como artifact `APKBDEV-tvapp` y GitHub Release de pruebas. Si el teléfono rechaza actualizar una APK debug anterior por firma diferente, puede requerir desinstalar la versión de prueba previa (esto elimina datos locales).
