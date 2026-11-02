# Orbit Launcher v0.2 — ARCHMOBA

Versión experimental para Android que organiza accesos en los cuatro bordes.

## Corrección de contenido cortado (v0.2)

En v0.1, los iconos superpuestos tapaban los extremos de la aplicación. v0.2 ofrece dos estrategias:

1. **Ventana central ajustada**: si Android anuncia soporte de `FEATURE_FREEFORM_WINDOW_MANAGEMENT`, el launcher pide abrir la app con límites ajustados al centro (`ActivityOptions.setLaunchBounds`). El fabricante y cada app pueden ignorar la solicitud. **No es una garantía de ventana redimensionable.**
2. **Pantalla completa sin recortes**: en teléfonos que no admiten ventanas libres, Orbit oculta automáticamente las barras al lanzar una app, dejando solo un pequeño botón flotante ◎ en el lateral. Toca ◎ para reabrir los iconos. Así puedes usar la aplicación completa en lugar de verla cortada.

Adicionalmente, **ESPEJO** (Android 14 QPR2 o posterior) permite compartir UNA aplicación mediante MediaProjection, que transmite el contenido redimensionado al panel central. En el cuadro de permiso elige **Una aplicación**, no pantalla completa. La imagen en este modo **no es interactiva**: los toques sobre el visor no se trasladan a la aplicación.

## Instalar

Desinstala Orbit Launcher v0.1 antes de instalar v0.2, porque cada compilación de prueba puede tener distinta firma de depuración. Luego instala el nuevo APK, abre Orbit y concede **Mostrar sobre otras apps**.

En dispositivos con ventanas libres, selecciona una aplicación con APPS para pedir ajuste central. Si no se ajusta, el sistema la está abriendo a pantalla completa: pulsa el control ◁ del dock para ocultar los bordes. En dispositivos sin ventanas libres, los iconos se ocultan automáticamente al abrir aplicaciones.

El modo ESPEJO solicita consentimiento cada vez. Las imágenes no se almacenan ni se transmiten por internet. Algunas apps con protección contra capturas mostrarán negro. Android no ofrece una API pública que permita incrustar universalmente cualquier aplicación en un rectángulo interactivo de terceros.
