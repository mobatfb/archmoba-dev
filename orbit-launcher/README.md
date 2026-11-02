# Orbit Launcher v0.1 (ARCHMOBA)

APK de prueba para Android. Interfaz negra con bordes azules neón, iconos de aplicaciones instaladas alrededor y un visor central.

## Dos modalidades

1. **Vista directa (Android 8+):** el servicio superpone cuatro barras con iconos en los bordes. El centro queda libre, por lo que se ve y se puede tocar directamente la aplicación que está detrás. **No redimensiona la app**: los bordes esconden las áreas de la app que queden debajo de ellos.
2. **Modo ESPEJO (Android 14 QPR2+):** usa MediaProjection, previa selección y consentimiento del usuario, para transmitir la ventana de una app al visor central ajustado a escala. **Solo muestra la imagen: el visor no transmite pulsaciones táctiles**. Si eliges capturar toda la pantalla en vez de una sola app, pueden producirse efectos de repetición infinita.

## Permisos

- **Mostrar sobre otras apps:** necesario para mostrar los iconos en los bordes.
- **Compartir la pantalla:** consentimiento de Android en cada sesión de espejo.
- **Servicio en primer plano y notificación:** mantiene activo el dock y permite cerrarlo desde la notificación.

No requiere root, internet, cuentas ni servidor. No graba ni envía las imágenes capturadas. La captura se procesa solamente en memoria. Algunas apps bloquean captura de pantalla por seguridad y se mostrarán en negro.

## Instalar

Abre el APK, autoriza la instalación externa si Android lo solicita, abre Orbit Launcher, concede "Mostrar sobre otras apps" y pulsa un icono. Para transmisión usa **ESPEJO**, elige **Una sola aplicación** en el diálogo de Android y acepta compartir.

**Limitación importante:** este es un prototipo que debe probarse en un teléfono real. No implica que Android permita incrustar todas las aplicaciones con control táctil y escalado simultáneos.
