# Herramientas necesarias

## Versiones verificadas previamente en Orbit Launcher

- **JDK 17** para ejecutar Gradle y compilar Java.
- **Gradle 8.7** como herramienta de construcción.
- **Android Gradle Plugin 8.5.2**, descargado por Gradle/Maven.
- **Android SDK Platform 35** (`platforms;android-35`).
- **Android Build Tools 35.0.0** (`build-tools;35.0.0`).
- **Android SDK Command-line Tools**, incluye `sdkmanager`.
- Python 3.9+ para scripts APKBDEV; no se incorpora a la APK.

Los valores están en `config/toolchain.json`. No almacenes JDK, Gradle,
Android Studio, el SDK ni el APK compilado dentro de git: ocupan mucho y
pueden incluir licencias o componentes específicos por plataforma.

## Configuración en Windows

1. Instala Android Studio (incluye el SDK Manager) y habilita **Android SDK Command-line Tools (latest)**.
2. Instala JDK 17 y Gradle 8.7; añade sus carpetas `bin` a `PATH`.
3. Define `JAVA_HOME` apuntando al JDK 17; `ANDROID_HOME` normalmente está en `%LOCALAPPDATA%\Android\Sdk`.
4. Ejecuta `py -3 apkbdev/tools/prepare_sdk.py` para instalar platform 35 y Build Tools.
5. Comprueba: `py -3 apkbdev/tools/doctor.py --strict`.
6. Compila: `py -3 apkbdev/tools/build_apk.py --project orbit-launcher`.

Si `prepare_sdk.py` exige aceptar licencias, en una consola utiliza
`sdkmanager --licenses`; acepta solo si estás conforme con los términos.

## Configuración en Ubuntu/GitHub Actions

GitHub Actions preinstala Android SDK y cuenta con `sdkmanager`.
La automatización usa `actions/setup-java@v4` y
`gradle/actions/setup-gradle@v4`. **No se utiliza** `android-actions/setup-android@v3`
porque una compilación anterior falló al intentar instalar el paquete
antiguo `tools` (ya no disponible).

La ejecución automática instala los paquetes desde `config/toolchain.json`.

## Resultado y compatibilidad

`assembleDebug` produce `app/build/outputs/apk/debug/app-debug.apk`.
El script mueve una copia a `apkbdev/dist/<proyecto>/<proyecto>-debug.apk`.

El soporte mínimo por defecto es Android 8.0 (API 26). Cada proyecto
puede requerir otra API, permisos o capacidades del equipo.
