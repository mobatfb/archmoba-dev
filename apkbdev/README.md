# APKBDEV | ARCHMOBA Android Build Development

**Kit reutilizable de creación, compilación y distribución de APK** del repositorio archmoba-dev.

El entorno incluye herramientas, configuraciones y plantilla Android nativa Java, y el código de **Orbit Launcher v0.14** como proyecto de referencia. El SDK/JDK/Gradle se instalan en el entorno de compilación, no se guardan binarios pesados dentro de git.

| Ruta | Función |
| --- | --- |
| `config/toolchain.json` | Versiones Java 17, Gradle 8.7, AGP 8.5.2, Android SDK 35. |
| `tools/new_app.py` | Generar proyectos nuevos en `projects/`. |
| `tools/build_apk.py` | Compilar APK debug y copiar a `dist/`. |
| `tools/prepare_sdk.py` | Instalar componentes del SDK con `sdkmanager`. |
| `tools/doctor.py` | Validar el entorno y las dependencias. |
| `templates/native-java/` | Plantilla autónoma de nueva app Android. |
| `projects/orbit-launcher/` | Orbit v0.14: indicadores verdes automáticos de notificaciones activas (con permiso opcional) y dock glass al 55% con sensores optimizados. |
| `tests/` | Pruebas automáticas del generador. |
| `docs/` | Guías de compilación, ambiente, CI y firma. |

La automatización está en `.github/workflows/apkbdev-build.yml`, porque GitHub solo detecta workflows en esa ruta. El resto de la construcción usa `apkbdev/`.

## Crear una app nueva

```bash
python3 apkbdev/tools/new_app.py "Mi nueva app" --slug mi-nueva-app --package com.archmoba.minuevaapp
```

Se crea `apkbdev/projects/mi-nueva-app/`. Para compilar:

```bash
python3 apkbdev/tools/prepare_sdk.py
python3 apkbdev/tools/doctor.py --strict
python3 apkbdev/tools/build_apk.py --project mi-nueva-app
```

Requiere JDK 17, Gradle 8.7 y Android Command-line Tools instalados en tu ordenador. El APK se genera en `apkbdev/dist/mi-nueva-app/mi-nueva-app-debug.apk`.

## Compilar en GitHub Actions

En `Actions > APKBDEV - Android APK Builder > Run workflow`, selecciona la app por el nombre de su carpeta `projects`. Se crea un artifact de GitHub y una **Release de pruebas descargable** por ejecución, si la publicación está permitida por GitHub. La APK debug se firma automáticamente; para producción necesitarás una firma privada estable (ver `docs/FIRMAS.md`).

Los commits a `main` dentro de APKBDEV compilan Orbit como comprobación.

## Convenciones

- Crear futuras apps dentro de `apkbdev/projects/<slug>/`.
- Utilizar los scripts compartidos en `apkbdev/tools/`.
- No guardar contraseñas, tokens, keystores, SDKs o archivos APK debug dentro del árbol de código.
- Para producción, publicar APK firmadas por el responsable del proyecto, no builds debug.
- Orbit v0.14 mantiene solo los accesos elegidos por el usuario a la derecha. Si no existen accesos aparece `+`; con iconos añadidos, el menú de pulsación larga permite añadir, subir, bajar o quitar.
