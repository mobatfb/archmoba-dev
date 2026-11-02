# Plantilla Android nativa Java

No ejecutes Gradle desde esta carpeta directamente: contiene marcadores que
el generador sustituye. Crea tu nueva aplicación con:

python3 apkbdev/tools/new_app.py "Mi app" --slug mi-app --package com.archmoba.miapp

El generador copia y personaliza `settings.gradle`, `build.gradle`,
`AndroidManifest.xml`, `MainActivity.java` y `ic_launcher.xml`.
