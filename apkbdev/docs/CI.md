# Automatización Android APK

La automatización compartida está en `.github/workflows/apkbdev-build.yml`.
Se activa automáticamente al modificar `apkbdev/**` en `main`, y puede
ejecutarse manualmente seleccionando el nombre del proyecto.

### Para una aplicación nueva

1. Genera un proyecto en `apkbdev/projects/` con `new_app.py`.
2. Trabaja en sus archivos Java/Gradle/Manifest (no necesita depender de Orbit).
3. Haz commit y push.
4. En GitHub > Actions > APKBDEV - Android APK Builder > Run workflow
   selecciona `<slug>` como `project`.
5. Descarga el archivo APK desde **Artifacts**.

La CI valida el nombre de proyecto antes de construir para evitar rutas
externas. Compila una sola app por ejecución. No requiere tokens ni secretos
externos para builds de depuración.

### Si falla la compilación

Revisa la tarea **Compilar APK** y después `gradle`, `JAVA_HOME`,
`ANDROID_HOME` y dependencias. Usa `doctor.py --strict` antes de compilar
en el PC. Todo cambio de versión debe reflejarse en `config/toolchain.json`,
el archivo Gradle raíz y el workflow.

**Nota:** los APK tipo debug de cada ejecución pueden firmarse con un
certificado temporal diferente. Si Android muestra conflicto de firma al
actualizar una prueba anterior, desinstala la anterior o usa una firma
persistente propia configurada fuera del repositorio.
