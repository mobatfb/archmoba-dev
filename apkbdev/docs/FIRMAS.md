# Firma y distribución de APK

El flujo APKBDEV construye **APK debug** para pruebas. No equivale a una
distribución de producción o a una publicación en Google Play.

Para una APK release:

1. Genera un keystore propio y protégelo; **no lo subas al repositorio**.
2. Configura el bloque `signingConfigs.release` en el Gradle de tu app.
3. Guarda contraseñas y archivo de firma en un almacenamiento seguro o en
   GitHub Actions Secrets (para uso en CI).
4. Compila `assembleRelease`, comprueba la firma y prueba la actualización
   sobre una instalación anterior con el mismo certificado.

El script genérico `build_apk.py` no ofrece `release` sin un sistema de
firma explícitamente configurado. Nunca almacenar contraseñas, claves privadas
ni valores sensibles dentro de `apkbdev`.

Si se necesita una firma persistente para APKs de pruebas, conserva el
keystore en un lugar privado y usa una configuración de firma propia. El
keystore de depuración auto-generado por cada runner puede cambiar.
