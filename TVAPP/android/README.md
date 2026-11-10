# MINGA TV para Android

Aplicacion Android nativa de MINGA TV (Java + Media3 ExoPlayer), compatible con la estructura TVAPP/providers.json, TVAPP/channels.json y TVAPP/adult.json.

## Compilar APK de prueba

Con Android Studio moderno y JDK 17:
1. Abre la carpeta TVAPP/android.
2. Espera la sincronizacion de Gradle.
3. Selecciona **Build > Build APK(s)** o ejecuta gradle :app:assembleDebug.
4. El resultado queda en app/build/outputs/apk/debug/app-debug.apk.

Desde GitHub, el workflow "MINGA TV Android APK" genera un artefacto **MINGA-TV-Android-debug**.

## Caracteristicas

- Seleccion de proveedor padre -> categorias -> canales.
- Catalogos JSON con playlists, JSON con categories/channels y listas M3U.
- IPTV Xtream Codes: categorias de TV en vivo y transmisiones.
- HLS (.m3u8) y enlaces HTTP de los catalogos actuales.
- Cifrado encv1: (PBKDF2-HMAC-SHA256, Fernet AES-CBC + HMAC), compatible con el generador Python de MINGA TV.
- Favoritos, Papelera, ultimo canal visto, busqueda, pantalla completa y miniatura del canal anterior.
- Preferencias privadas locales para colecciones. Las URLs guardadas de Xtream son referencias virtuales, sin credenciales.
- Confirmacion de acceso a categoria Adultos (18+).
- No se requieren contrasenas para TV en vivo ni Adultos (18+).

**Seguridad:** La guia de descifrado forma parte del cliente, y cualquiera con acceso al APK puede extraerla. No utilizar este mecanismo como unica proteccion de credenciales sensibles. El servidor Premium1 debe utilizar HTTPS y contenido autorizado.

**Nota:** La APK de depuracion esta firmada automaticamente con una clave de desarrollo. Para distribuir en tiendas, crear una clave privada de produccion y configurar la firma de release.
