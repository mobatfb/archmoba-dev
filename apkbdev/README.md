# APKBDEV | ARCHMOBA Android Build Development

**Kit de desarrollo y compilación de APK reutilizable** dentro del repositorio archmoba-dev.

Este directorio contiene las herramientas, versiones fijadas, plantilla Android nativa Java, scripts, guías y **el código fuente completo de Orbit Launcher v0.2** como proyecto funcional de referencia. No contiene componentes Android SDK/Gradle/JDK binarios (son pesados y se instalan en el runner o en el equipo local).

## Mapa

| Carpeta | Función |
| --- | --- |
| config/toolchain.json | Versiones de Java, Gradle, Android SDK, build-tools, AGP y objetivos. |
| tools/new_app.py | Crea una nueva aplicación Android a partir de una plantilla. |
| tools/build_apk.py | Compila una app y guarda su APK en dist (no versionado). |
| tools/doctor.py | Comprueba las dependencias del equipo. |
| tools/prepare_sdk.py | Descarga componentes SDK requeridos mediante sdkmanager. |
| templates/native-java/ | Proyecto base Android nativo, sin frameworks de interfaz externos. |
| projects/orbit-launcher/ | Copia del proyecto Orbit Launcher v0.2, tomada de la rama de pruebas. |
| tests/ | Pruebas básicas del generador. |
| docs/ | Guías para Windows, GitHub Actions y firma. |
| dist/ | Resultado de builds locales (se ignora en git). |

La automatización de GitHub debe vivir fuera de esta carpeta en
`.github/workflows/apkbdev-build.yml` por una restricción de GitHub Actions.
**Toda la lógica de preparación y construcción reside aquí, en apkbdev.**

## 1. Crear una app desde cero

En la raíz del repositorio:

```bash
python3 apkbdev/tools/new_app.py "Mi nueva app" --slug mi-nueva-app --package com.archmoba.minuevaapp
```

La fuente queda en `apkbdev/projects/mi-nueva-app/`. Cada app es independiente y tiene
su propio `app/build.gradle`, manifiesto y código. El generador **no sobrescribe**
un proyecto existente.

## 2. Compilar con GitHub Actions (recomendado)

1. Abre el repositorio > **Actions** > **APKBDEV - Android APK Builder**.
2. Elige **Run workflow**; escribe el nombre de la carpeta del proyecto, por ejemplo `mi-nueva-app`.
3. Descarga el artifact `APKBDEV-mi-nueva-app` cuando termine.

Cada push que cambia apkbdev en `main` también compila `orbit-launcher` para verificar el entorno. Se crea un artifact descargable, sin guardar la APK en el historial git.

## 3. Compilar desde Windows o Linux

Instala primero JDK 17, Gradle 8.7 y Android SDK Command-line Tools mediante Android Studio o los instaladores oficiales.

En Windows PowerShell:

```powershell
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
py -3 apkbdev/tools/prepare_sdk.py
py -3 apkbdev/tools/doctor.py --strict
py -3 apkbdev/tools/build_apk.py --project orbit-launcher
```

En Linux:

```bash
export ANDROID_HOME="$HOME/Android/Sdk"
python3 apkbdev/tools/prepare_sdk.py
python3 apkbdev/tools/doctor.py --strict
python3 apkbdev/tools/build_apk.py --project orbit-launcher
```

El APK aparece en `apkbdev/dist/orbit-launcher/orbit-launcher-debug.apk`. Se admiten otros proyectos:

```bash
python3 apkbdev/tools/build_apk.py --project mi-nueva-app
```

## 4. Reglas para futuras aplicaciones

- Todos los **nuevos proyectos APK** se guardan en `apkbdev/projects/<slug>/`.
- Crear proyecto: `tools/new_app.py`; compilar: `tools/build_apk.py`.
- Respetar las versiones de `config/toolchain.json` o actualizar también la CI y la plantilla.
- Dependencias Android se descargan en cada equipo/runner, **no subir Android SDK ni JDK al repo**.
- No publicar claves privadas, archivos `*.jks`, contraseñas, secretos ni tokens.
- `assembleDebug` genera una APK **de pruebas**. Para distribuir una APK de producción, configurar una firma propia privada (ver `docs/FIRMAS.md`).
- Android puede impedir incrustar apps de terceros en una ventana central. Orbit v0.2 es experimental; su modo de ventana libre depende del dispositivo.

## Archivos y procedencia

Orbit Launcher se copió *sin cambiar su código fuente* desde
`feature/orbit-launcher-apk-20261101/orbit-launcher`, versión 0.2.
El flujo de compilación del proyecto usa Java 17 + Gradle 8.7 + AGP 8.5.2 + Android SDK 35.
