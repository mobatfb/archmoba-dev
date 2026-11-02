# Orbit Launcher v0.6 — Semicírculos sensibles al giro | ARCHMOBA

## Novedades

- Solo la **mitad de cada círculo** queda visible: el panel flotante se desplaza 25 dp fuera del borde derecho de la pantalla.
- Los iconos responden en vivo a la inclinación física del móvil usando el sensor de gravedad (o acelerómetro de respaldo), con filtrado de movimiento para evitar saltos.
- Al cambiar la orientación del teléfono entre vertical y horizontal, el servicio reconstruye el panel en el lado derecho, ajusta su altura y recalibra los sensores.
- Se conservan la posición vertical de v0.5 (52 dp por encima del centro) y la lista elegida por el usuario.

## Funciones

1. Al iniciar por primera vez, se muestra únicamente el botón `+` medio oculto en el borde derecho.
2. Pulsa el lado visible de `+` para elegir las apps que quieres añadir.
3. Pulsa un icono para abrir la aplicación.
4. Mantén pulsado el icono para **Subir un lugar**, **Bajar un lugar** o **Quitar**. El orden se guarda.
5. Con muchas apps puedes desplazar la columna verticalmente.

## Compatibilidad

Android 8.0+. Requiere el permiso de superposición. Los sensores no necesitan permisos especiales. Android puede impedir que algunas ventanas de superposición se extiendan fuera de la pantalla, de modo que **el recorte exacto de media circunferencia depende del fabricante**. El giro de pantalla depende de la rotación que permita Android/la aplicación activa.

El launcher no graba pantalla, no requiere Internet, no redimensiona apps ajenas. El servicio se detiene desde su notificación.

## Instalación

El ID de paquete sigue siendo `com.archmoba.orbitlauncher`. Una APK debug firmada con certificado diferente puede requerir desinstalar la versión anterior, lo que borra las preferencias guardadas. Fuente en `apkbdev/projects/orbit-launcher`.
