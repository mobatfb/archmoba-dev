MULTIMANDO FUTUREO STREAM v2.2.0 - BAJA LATENCIA
================================================

CAMBIOS FRENTE A v2.1
- Captura BGRA->RGB con Pillow sin convertir antes con MSS a RGB.
- Programacion de FPS sin recuperar capturas atrasadas (sin backlog).
- Cada imagen lleva secuencia, hora de captura y tiempo de procesamiento
  (cabecera binaria FJ22 de 20 bytes, mas JPEG).
- Web responsive dibuja en canvas; solo conserva el fotograma pendiente mas
  reciente y descarta fotogramas anteriores si llega uno nuevo.
- En conexiones lentas se evita ENVIAR capturas antiguas (>450 ms en el host).
- La web detecta acumulacion adicional en el transporte y puede reiniciar
  solamente su canal de imagen para evitar arrastrar frames obsoletos.
- Metricas del anfitrion: FPS obtenidos, ms de captura, KB/frame,
  numero de espectadores actuales.
- Perfil predeterminado 480x270, 10 FPS, JPEG 50.
- Boton MODO RAPIDO: 320x180, 15 FPS, JPEG 40. Primero DETENER para cambiar.
- Opciones manuales FPS: 1, 2, 5, 10, 15, 20. Mas FPS NO siempre significa
  menos retraso; depende de la PC y la capacidad de subida.
- Compatible con imagenes JPEG antiguas del host v2.1 (modo respaldo web).
- Sin audio. No es WebRTC ni codificacion H264.

VER SIN CONECTARSE
La web establece un WebSocket unidireccional a /stream mediante el MISMO
tunnel Cloudflare de la sala (puerto 8766). Toda persona que abre la web
puede MIRAR, incluso sin escribir nombre, sin hacer clic en CONECTAR o
sin tener turno. Espectadores NO ocupan mandos ni afectan a la cola.
El anfitrion captura UNA VEZ por fotograma y lo distribuye PUSH,
sin peticiones independientes de JPEG a Cloudflare. Se necesita mantener
la conexion WebSocket de cada espectador, como en cualquier stream.

INSTALAR ANFITRION
1. Cierra el anfitrion anterior.
2. En Windows conserva en la misma carpeta:
    MULTIMANDO_FUTUREO_Anfitrion_v2_2_0.py
    futureo_stream_v22.py
3. Abre FUTUREO VJOY v0.8.4 (motor HID), crea 1..8 mandos.
4. Ejecuta: py MULTIMANDO_FUTUREO_Anfitrion_v2_2_0.py
5. Si hace falta, Python instala websockets, pygame, Pillow y mss.
6. Abre sala y PUBLICAR INTERNET (mismo Cloudflare que en v2.1).
7. En TRANSMISION selecciona pantalla o ventana visible.
8. Configura FPS/calidad/tamano, pulsa INICIAR TRANSMISION.
9. Observa fps real y tiempo de captura. Si se atrasa, baja tamano
   y/o FPS para evitar saturacion.
10. Los cambios de FPS requieren detener e iniciar el mini-stream;
    no hace falta cerrar sala ni desconectar jugadores.

INSTALAR WEB
- Copia el CONTENIDO de WEB/ a tu servidor PHP /multimando/.
- No borres tu private/FRASE_CIFRADO.php. Ese secreto NO esta en GitHub
  ni en el ZIP, por seguridad. Conserva su palanca.enc compatible.
- Se mantienen private/.htaccess y .htaccess para proteger rutas.
- Recarga el navegador para obtener futureo-stream.js?v=2.2.0.
- PC: video al lado del mando; movil: video arriba de mandos.
- No debes pulsar CONECTAR para visualizar imagen.
- La telemetria WEB de 'edad aprox' usa los relojes de host y cliente;
  puede ser inexacta si sus horas no estan sincronizadas.
- 'Cola adicional' es una comparacion RELATIVA con el minimo reciente
  del transporte, no una medicion exacta del ping total.
- Protocolo / no cambia el control, FIFO, 600 segundos, turnos,
  reconexion de jugadores, asignacion de mandos y cola.
- Solamente transmite imagen; no comparte audio.

PRUEBAS
Sin driver:
  py MULTIMANDO_FUTUREO_Anfitrion_v2_2_0.py --selftest
En CI:
  python -m py_compile ...
  node --check ...
  node MULTIMANDO/MANDOWEB/tests/test_futureo_stream_v22.js
  php -l ...
Limitaciones:
- Captura de ventana con MSS toma pixeles visibles; si minimizas la
  ventana o el juego exclusivo bloquea captura pueden verse negros.
- A mayor cantidad de espectadores, mas trafico de salida desde el PC.
- Si necesitas latencias realmente sub-100ms de forma consistente,
  se podria migrar en otra version a WebRTC con encoder apropiado.
- El flujo publicado es PUBLICO; no compartas documentos privados.
- No instalar controladores adicionales ni desactivar protecciones.

REPO
https://github.com/mobatfb/archmoba-dev/tree/main/MULTIMANDO
