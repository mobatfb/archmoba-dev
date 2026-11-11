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

## Icono de la APK (v1.0.1)

El icono del lanzador utiliza exactamente el logo del splash de Windows:
`TVAPP/assets/minga_tv_logo.png`.
La misma imagen se reutiliza dentro de Android (sin transformaciones del archivo original),
centrada sobre fondo negro en una mascara adaptativa, para soportar lanzadores modernos.

La compilacion de pruebas usa firma debug generada por GitHub Actions. Si tenias una
compilacion anterior instalada y Android indica un conflicto de firmas, desinstala
esa version antes de instalar la nueva (guarda cualquier preferencia que necesites).


## Icono corregido (v1.0.2)

El splash permanece separado y usa exactamente `@drawable/minga_tv_logo`, copia
del archivo original `TVAPP/assets/minga_tv_logo.png`, sin ninguna edicion.

El icono se genera como **PNG opaco y cuadrado de 512 x 512 pixeles** a
partir del mismo logo original. La figura y las letras mantienen sus proporciones.
Se rellenan los espacios laterales con un fondo oscuro azulado (sin bandas
transparentes) para que el lanzador de Android aplique su mascara de icono
(redondeado, cuadrado redondeado, circular segun el dispositivo). El archivo se
genera antes de Gradle mediante `tools/GenerateIcon.java`, que utiliza
unicamente Java 17 y no modifica el PNG del splash.

## Splash completo restaurado (v1.0.3)

En Android 12+ el icono de la pantalla de lanzamiento del sistema se recorta
con una mascara, por eso el logotipo rectangular aparecia ampliado y cortado.
No debe asignarse `@drawable/minga_tv_logo` a
`android:windowSplashScreenAnimatedIcon`.

Ahora `SplashActivity` dibuja el **PNG original completo**, con
`ImageView.ScaleType.FIT_CENTER`, proporcion original, centrado y margenes
horizontales. El splash se muestra 2 segundos sobre fondo negro y luego abre
`MainActivity`. Se conserva el icono cuadrado separado para el launcher.
