# Orbit Launcher v0.10 — Glass 80% | ARCHMOBA

## Novedad

- Toda la interfaz flotante usa **80% de opacidad**, incluyendo el icono de la app, el texto del botón `+`, el fondo circular y el borde, mediante `setAlpha(0.80f)` en cada vista.
- El círculo mantiene su forma **OVAL real** con `GradientDrawable.OVAL`. No es un rectángulo de esquinas redondeadas.
- Nuevo acabado **glass**: gradiente diagonal azul grisáceo hacia azul marino, relleno translúcido y contorno cian semitransparente.
- El relleno parte de una transparencia adicional, por lo que el resultado final puede verse más ligero que un 80% opaco puro.

## Funciones preservadas

- **`+` no gira**. Solo aparece cuando no existe ninguna aplicación añadida.
- Con apps agregadas, mantener pulsado cualquier icono abre **Añadir aplicación**, **Subir un lugar**, **Bajar un lugar**, **Quitar del panel**.
- Iconos alineados con el borde derecho y desplazados 52 dp por encima del centro.
- Los iconos de apps siguen respondiendo al sensor de gravedad, con corrección según orientación de pantalla. El `+` nunca entra en la lista de vistas que giran.
- Orden y selección persistentes; lista desplazable verticalmente.
- Servicio flotante sin grabación de pantalla ni Internet.

## Instalación

Android 8+. Permiso **Mostrar sobre otras aplicaciones** necesario. El archivo es una APK debug, no una versión publicada para producción. Si la firma difiere de una versión anterior, Android podría exigir desinstalarla (borrando los accesos elegidos). Compilar desde `apkbdev/projects/orbit-launcher` con GitHub Actions.
