# FUTUREO STREAM v3.0 - FULL, DELTA y SMART

Version anfitrion: MULTIMANDO FUTUREO v2.4.0.
Version web: visor futureo-stream-v3.js.
Ruta publica SIN CAMBIOS: wss://NOMBRE.trycloudflare.com/stream.
La web sigue consultando la misma URL publicada en sala.php.

## MODOS DISPONIBLES EN TRANSMISION

| Tecnologia GUI | Modo | Funcionamiento |
| --- | --- | --- |
| FUTUREO FULL STREAM | full | JPEG completo por fotograma; compatibilidad FJ22 |
| FUTUREO DELTA STREAM | delta | Pixel RGB o rectangulo JPEG frente a keyframe de referencia |
| FUTUREO SMART STREAM | smart | Pixel con paleta 256, RGB exacto cuando no cabe en paleta, rectangulo JPEG o imagen completa segun bytes |

- Conservamos seleccion de pantalla/ventana, resolucion, FPS y
  calidad JPEG, ademas de MODO RAPIDO y MODO EQUILIBRADO.
- MODO RAPIDO: 320x180, 15 FPS, JPEG 40.
- MODO EQUILIBRADO: 480x270, 15 FPS, JPEG 50.
- La tecnologia se selecciona INDEPENDIENTEMENTE del perfil.
- Si ya transmite, pulsa DETENER antes de cambiar tecnologia o preset
  y despues INICIAR TRANSMISION.
- FPS objetivo: depende del rendimiento de captura, compresion y red.
- Ninguna modalidad modifica los turnos, Cloudflare, el puerto o mandos.

## PALETA 256 EXACTA

En SMART, al generar un fotograma clave se seleccionan hasta 256
colores RGB EXACTOS mas frecuentes del fotograma base.
Los indices se comunican a la web en el propio keyframe.
No hay que descargar un archivo de paleta.

Si el color cambiado NO aparece en la paleta se conserva
EXACTAMENTE mediante PIXEL_RGB, o se utiliza JPEG de region /
fotograma completo segun tamaño. La compresion sin perdida aplica
solo a los pixeles indexados; JPEG siempre es con perdida.

Posiciones: 2 bytes para resoluciones de hasta 65535 pixeles y
3 bytes para resoluciones mayores. Un pixel lleva 1 byte de indice
de paleta (SMART) o 3 bytes RGB (DELTA/respaldo SMART).

## PROTOCOLO FS30

Solo los navegadores actualizados que envien FV3 al entrar a
/stream reciben el nuevo protocolo.

Cabecera binaria de 32 bytes, endian big:
magic[4]='FS30', kind:u8, flags:u8, width:u16, height:u16,
seq:u32, base_seq:u32, timestamp_ms:u64, processing_ms:u16,
fps:u16, count:u16.

- flags: 0 FULL, 1 DELTA, 2 SMART.
- kind=0 FULL: palette_count:u16 + colores RGB + JPEG completo.
- kind=1 PIXEL_RGB: count veces (pos:u16/u24 + R G B).
- kind=2 PIXEL_PALETTE: count veces (pos:u16/u24 + indice:u8).
- kind=3 REGION_JPEG: x,y,w,h u16 mas JPEG de la region.
- kind=4 HOLD: cuerpo vacio, restaurar imagen base.

Los DELTA son INDEPENDIENTES del delta inmediatamente anterior:
todos describen el estado actual frente a base_seq. El navegador
redibuja la imagen base y aplica el delta; por ello, si descarta
fotogramas intermedios por baja latencia, no pierde sincronizacion.
Se envia keyframe cada 3 s aproximadamente, cuando conviene
por costo de bytes, y al conectarse un nuevo espectador.

Quienes usan la WEB ANTIGUA y no envian FV3 siguen recibiendo
FJ22 + JPEG completo incluso si el anfitrion esta en DELTA/SMART.
En ese caso no aprovechan el ahorro diferencial. El anfitrion
mantiene un JPEG completo por captura para compatibilidad.

## INSTALACION WINDOWS

Extrae el ZIP del anfitrion v2.4.0 con estos 3 archivos juntos:
- MULTIMANDO_FUTUREO_Anfitrion_v2_4_0.py
- futureo_stream_v30.py
- futureo_stream_v22.py

Cierra el anfitrion anterior. Ejecuta:
    py MULTIMANDO_FUTUREO_Anfitrion_v2_4_0.py

No reinstales FUTUREO VJOY v0.8.4. Websockets, Pillow y mss
son dependencias del stream como antes.

## INSTALACION WEB

Extrae ZIP web v2.3.0 en /multimando/; sobrescribe archivos
publicos. palanca.php ahora incluye:
    <script src="assets/futureo-stream-v3.js?v=3.0.0" defer></script>

El visor inicia automaticamente. control.php y los scripts de
recuperacion del mando se conservan sin cambios. El ZIP no
incluye ni reemplaza los archivos secretos
private/FRASE_CIFRADO.php ni private/palanca.enc.

El control via WebSocket usa / y la pantalla usa /stream, igual
que antes. Para activar los 3 modos hay que subir ambos ZIP.

## PRUEBAS Y LIMITES

GitHub Actions verifica sintaxis, tests del motor antiguo,
tests del motor v3 (paleta, pixel RGB, viewer nuevo y viewer
antiguo), Tkinter con Xvfb, tests de visor JS y PHP.
La calidad real, ahorro de datos, CPU, estabilidad y FPS
deben verificarse despues en Windows.

El porcentaje de ahorro v3 indicado en la GUI compara bytes
del payload FS30 con bytes del payload FJ22 de la captura.
No considera TCP, TLS, Cloudflare ni fan-out por espectador.
