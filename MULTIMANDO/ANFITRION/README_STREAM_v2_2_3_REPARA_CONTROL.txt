MULTIMANDO WEB v2.2.3 - REPARAR ERROR 404 DEL MANDO
===================================================

SINTOMA VERIFICADO POR EL USUARIO:
  https://tiendavibechic.com/multimando/control.php
  -> 404 Not Found

Esto significa que el servidor NO entrega control.php en esa URL.
No prueba un fallo de la clave de cifrado ni de Cloudflare.
La imagen funciona aparte porque assets/futureo-stream.js tiene
otro canal WebSocket publico /stream y no carga el mando.

CAUSA DE LA REGRESION DE EMPAQUETADO:
- El paquete v2.2.2 excluia por exceso de precaucion control.php.
- Pero la pagina palanca.php v6.2 lo necesita para generar el
  JavaScript del mando: <script src="control.php?v=6.2.0" defer>.
- Si control.php falta, CONECTAR no tiene codigo que lo atienda.

SOLUCION MINIMA SIN AFECTAR STREAM:
1. Descarga MULTIMANDO_WEB_v2_2_3_REPARA_CONTROL_PHP.zip.
2. Extrae y sube WEB/control.php al MISMO directorio publico
   que WEB/palanca.php e index.php.
   Si tu web apunta a /multimando/, la ruta deberia ser:
       public_html/multimando/control.php
   (ajusta public_html si tu document root es diferente).
3. Conserva sin sobrescribir:
       private/FRASE_CIFRADO.php
       private/palanca.enc
   Estos archivos son PRIVADOS y NO estan en los ZIP nuevos.
4. Si quieres actualizar la interfaz completa, sube tambien:
       WEB/palanca.php
       WEB/assets/futureo-stream.js
   No es necesario cambiar el anfitrion si la imagen ya llega.
5. Abre /multimando/control.php directamente:
   - HTTP 200 con JavaScript largo: control.php ya es accesible
     y pudo descifrar el modulo cifrado. NO compartas el codigo.
   - HTTP 503 con mensaje de error: control.php existe, pero
     falta el secreto, el archivo enc o no se pudo descifrar.
     Restaura AMBOS archivos privados de la misma copia de
     seguridad del hosting y prueba de nuevo.
   - HTTP 404: control.php aun esta en una ruta distinta,
     el host no tiene un archivo en esa URL o WordPress/
     las reglas del servidor interceptan la ruta. Comprueba
     la ruta FISICA y que el archivo sea accesible (644).
6. Reabre https://tiendavibechic.com/multimando/, escribe
   un nombre, marca AUTO y pulsa CONECTAR. Verifica que
   el anfitrion tiene la sala abierta y el tunel activo.
7. No cambies ni desactives la ruta /stream: la imagen publica
   sigue funcionando sin entrar en la cola o tener un mando.

NO PUBLICAR:
- private/FRASE_CIFRADO.php, claves, ni copias del JavaScript
  descifrado de control.php.
- No mezclar palanca.enc de una version con FRASE_CIFRADO.php
  de otra version.

PROTECCION EN ZIP v2.2.3:
- Ambos ZIP contienen control.php porque es codigo PHP publico
  y no tiene la clave secreta.
- Ninguno incluye WEB/private/ ni control_decoded.js.
- Los test de GitHub validan los contenidos del ZIP.
- Se conserva el anfitrion v2.2.1 + futureo_stream_v22.py.

LIMITACION:
No tenemos acceso al sistema de archivos ni a las reglas efectivas
del hosting tiendavibechic.com, asi que el repositorio no puede
corregir automaticamente un 404 de su servidor. Se requiere subir
el archivo a la ruta real que sirve la web.
