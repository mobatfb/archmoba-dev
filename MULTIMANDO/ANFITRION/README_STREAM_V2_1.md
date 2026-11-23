MULTIMANDO FUTUREO STREAM v2.1
===============================
CAPTURA PARA TODOS, SIN CONECTARSE NI ENTRAR A LA COLA

REQUISITOS:
- Windows 10/11 x64, FUTUREO VJOY v0.8.4 ya instalado/ejecutandose.
- Python 3.10+ con soporte Tkinter.
- Internet para descargar dependencias y cloudflared la primera vez.
- Hosting PHP 8.1+ funcionando con MULTIMANDO WEB v6.2.0.
- Conserva EN TU HOSTING el archivo privado private/FRASE_CIFRADO.php:
  no se incluye ni se debe publicar en GitHub.

INSTALACION:
1. Descomprime el ZIP.
2. En Windows, conserva juntos:
   ANFITRION/MULTIMANDO_FUTUREO_Anfitrion_v2_1_0.py
   ANFITRION/futureo_stream.py
3. En tu hosting sube el CONTENIDO de WEB/ a /multimando/,
   conservando private/FRASE_CIFRADO.php del sitio original.
   Esta entrega contiene private/palanca.enc del repositorio, pero NO
   el secreto: si cambiaste esa pieza, conserva tu version compatible.
4. Ejecuta: py MULTIMANDO_FUTUREO_Anfitrion_v2_1_0.py
   Se instalara Pillow y mss si faltan, ademas de websockets y pygame.
5. Abre FUTUREO v0.8.4, crea tus mandos y ABRE SALA en Python.
6. PUBLICAR INTERNET abre el tunnel Cloudflare actual, puerto 8766.
7. En TRANSMISION pulsa BUSCAR, elige pantalla o ventana visible.
   Elige 320x180, 480x270 o 640x360; FPS 1,2,5,10,15; calidad JPEG.
8. Pulsa INICIAR TRANSMISION. Puedes DETENER sin cerrar la sala.
9. Quien visita https://tu-dominio/multimando/ ve la imagen automaticamente.
   No tiene que indicar nombre, pulsar CONECTAR ni esperar turno.

ARQUITECTURA:
- Canal jugador: WebSocket /; conserva autenticacion de identidad,
  FIFO, 10 minutos, reconexion, 1-8 controles y 64 invitados.
- Canal espectador: WebSocket /stream, unidireccional y publico.
  NO crea usuario, NO asigna P1..P8, NO modifica turnos ni cola.
- Cloudflare Quick Tunnel publica ambos caminos EN UN MISMO PUERTO.
- Captura de 1 JPEG por frame en el anfitrion, distribuido PUSH
  como binario a los espectadores. Ninguna consulta por fotograma.
- WEB/assets/futureo-stream.js crea el enlace solo lectura incluso
  si la persona nunca pulsa CONECTAR. La pagina funciona en movil y PC.
- Cada espectador necesita una unica conexion WebSocket a Cloudflare
  (la red no puede enviar bytes al navegador sin esa conexion).
- La emision es PUBLICA: cualquiera con acceso a la pagina puede verla.
  Nunca selecciones ventanas con contrasenas o informacion sensible.
- La captura de ventana visible usa el rectangulo cliente de Windows;
  ventanas minimizadas, tapadas y juegos exclusivos pueden dar negro
  o capturar otras ventanas delante. Prueba modo ventana/sin bordes.
- SOLO IMAGEN (sin audio). Es un mini-stream de fotogramas JPEG,
  no video H.264, y no garantiza una latencia concreta.
- Para maximizar privacidad se cierra el canal al cambiar de pestaña.
- Se limita la imagen a 180 KB por fotograma por seguridad.
- Usar JPEG 320x180 a 2-5 FPS para ancho de banda muy limitado.
- El gasto externo crece con cantidad de espectadores:
  25 KB/fotograma x 5 FPS x 20 espectadores = 2.5 MB/segundo
  de salida aproximada a nivel de aplicacion (antes del overhead).

PRUEBA SIN WINDOWS:
  py MULTIMANDO_FUTUREO_Anfitrion_v2_1_0.py --selftest

ATENCION:
- No reemplaces el FUTUREO HID original ni actualices drivers.
- Para conservar respaldo, el anfitrion v2.0.0 original sigue publicado.
- Esta version requiere pruebas reales de captura y tunel en Windows.
