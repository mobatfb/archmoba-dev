MULTIMANDO FUTUREO STREAM v2.2.1 - REPARACION DE CONEXION DEL MANDO
=====================================================================

CORRECCION CRITICA
------------------
- En v2.1/v2.2 se introdujo validacion de ruta WS: solo '/' o
  '/stream'. La web antigua podia añadir rutas o parametros al
  tunel, y el servidor cerraba el socket con codigo 1008.
- v2.2.1 restaura la compatibilidad original con TODAS las rutas del
  mando, conservando la verificacion de 'hello', la validacion del
  nombre, el token de sesion y el control de turnos.
- '/stream' (y '/stream/') sigue siendo un espectador anonimo:
  recibe fotogramas sin nombre, sin reservar mando ni entrar en cola.
- La captura de pantalla y la difusion PUSH de v2.2 siguen iguales.

NUEVO DIAGNOSTICO WEB
---------------------
- control.php descifra private/palanca.enc con la frase que ya tienes
  en private/FRASE_CIFRADO.php (ESTE ARCHIVO NO VA EN EL ZIP).
- Si el descifrado funciona, se publica un indicador de arranque al
  final del JavaScript, sin tocar el modulo original.
- assets/control-health.js muestra un error visible si ese modulo
  no se carga. Esto permite diferenciar un fallo de JS cifrado de
  un fallo de WebSocket o del anfitrion.
- Si hiciste una copia completa de WEB/, NO reemplaces la frase
  privada previa. No se puede recrear la frase cifrada del hosting
  a partir de los archivos publicos del repositorio.
- Asegurate de conservar el par original correcto:
  private/FRASE_CIFRADO.php + private/palanca.enc.
- No publiques la frase privada en GitHub ni en este chat.

INSTALACION
-----------
1. Cierra el anfitrion v2.2 (si esta abierto).
2. Abre FUTUREO VJOY v0.8.4 como antes.
3. Coloca juntos:
   ANFITRION/MULTIMANDO_FUTUREO_Anfitrion_v2_2_1.py
   ANFITRION/futureo_stream_v22.py
4. Ejecuta: py MULTIMANDO_FUTUREO_Anfitrion_v2_2_1.py
5. Abre sala y pulsa PUBLICAR INTERNET.
6. Copia el contenido de WEB/ a la carpeta /multimando/ de tu
   hosting PHP. CONSERVA tu FRASE_CIFRADO.php privada anterior.
7. Recarga totalmente la pagina web con Ctrl+F5 o borra cache.
8. Prueba: escribe un nombre y pulsa CONECTAR. Debe recibirse
   'welcome' y asignarse P1..P8 segun disponibilidad.
9. Sin escribir nombre ni pulsar CONECTAR, cualquier visitante
   puede seguir viendo la imagen si el anfitrion transmite.
10. Si aparece 'MANDO NO DISPONIBLE' en la web, comprobar el par
    cifrado de PHP y que control.php responda sin error 503.

PRUEBAS REALIZADAS EN CI
------------------------
- Sintaxis Python, JavaScript y PHP.
- --selftest de jugador y difusion publica.
- Test real de WebSockets: /ws?game, /control/legacy, /?room y /stream
  sin hardware. Espera 'welcome' para mandos; no crea usuario
  para espectadores.
- Test de visor web: entrega el ultimo fotograma y respeta STOP.

IMPORTANTE
----------
Las pruebas automatizadas no reemplazan una prueba en tu
computadora Windows y tu hosting. Esta actualizacion del repositorio
no se instala sola en tiendavibechic.com.
