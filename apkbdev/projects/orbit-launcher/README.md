# Orbit Launcher v0.8 — Sensor sincronizado con pantalla | ARCHMOBA

## Correccion del problema de iconos invertidos

En v0.7 `DockMotion` tomaba la **primera lectura del sensor** como calibracion y calculaba giros relativos, sin considerar `Display.getRotation()`. Al iniciar la app con el movil inclinado, abrir otras apps o pasar de vertical a horizontal, un icono podia quedar girado aunque la pantalla ya estuviera derecha.

La version 0.8 aplica:
1. Gravedad o acelerometro con orientacion **absoluta** en los ejes naturales del dispositivo.
2. Compensacion de rotacion de pantalla mediante `Display.getRotation()` (0/90/180/270).
3. El angulo 0 representa **movil recto e iconos derechos**, sin calibracion inicial arbitraria.
4. Zona muerta de 7 grados para evitar temblores de sensor al sostener el telefono derecho.
5. Filtro suave de giro; cuando Android cambia de orientacion, se evita aplicar la rotacion dos veces.
6. Ante telefono casi plano (gravedad XY poco fiable), se deja el icono derecho en vez de inventar angulos.
7. Pruebas Java en `apkbdev/tests/OrbitOrientationTest.java` para vertical, horizontal en ambos sentidos, invertida, inclinaciones, pantalla bloqueada y modulo 360.

## Se conserva

- Los iconos **totalmente visibles** al lado derecho, horizontal v0.5/v0.7, no medio ocultos.
- El panel elevado 52 dp.
- Primera apertura: solo boton `+`; seleccionar apps desde lista de instaladas.
- Pulsacion larga: **Subir un lugar**, **Bajar un lugar** y **Quitar**.
- Seleccion y orden persistentes; lista con desplazamiento vertical.
- No necesita acceso a pantalla ni Internet.

## Instalacion

Android 8+. Si el certificado de la APK debug difiere de la version anterior, Android puede exigir desinstalar la anterior (se perderian las preferencias). Es una version de prueba: revisar la respuesta de los sensores en un telefono real.

Compilacion GitHub Actions: `.github/workflows/apkbdev-build.yml`.
