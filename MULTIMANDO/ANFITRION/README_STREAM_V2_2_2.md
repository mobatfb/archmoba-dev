MULTIMANDO WEB + FUTUREO STREAM v2.2.2 - PAQUETE SEGURO / RESCATE DEL MANDO
============================================================================

POR QUE DEJO DE FUNCIONAR EL MANDO
----------------------------------
En los ZIP v2.1, v2.2 y v2.2.1 INCLUI por error el archivo
WEB/private/palanca.enc, pero NO su clave privada FRASE_CIFRADO.php.
Si se subio el ZIP sobre el sitio que ya funcionaba, se pudo
sobrescribir la palanca cifrada original sin su clave correspondiente.
Cuando control.php no puede descifrar el modulo, la transmision
publica funciona (porque es otro JavaScript), pero CONECTAR no inicia
el mando. Esto concuerda con el aviso rojo anterior; para confirmar
la causa hay que consultar la respuesta real de control.php.

QUE ESTA CORREGIDO EN V2.2.2
----------------------------
- Los nuevos ZIP NO contienen NADA de WEB/private/.
- Los ZIP tampoco incluyen WEB/control.php: se conserva el archivo
  del hosting, pues NO necesita cambiar para usar el mini-stream.
- Se restauro en el repositorio el control.php de v6.2 sin codigo
  de diagnostico que se habia anadido.
- Se retiro de palanca.php el falso aviso 'MANDO NO DISPONIBLE' que
  tapaba la web; no es prueba de la causa exacta de un fallo.
- Se conservan los controles de jugadores, cola FIFO y mandos P1-P8.
- La imagen se transmite por /stream como antes, sin entrar a la cola.
- Se conserva el anfitrion v2.2.1 y futureo_stream_v22.py.

RECUPERAR EL MANDO SI YA SUBISTE EL ZIP ANTERIOR
------------------------------------------------
1. ABRE EL ADMINISTRADOR DE ARCHIVOS DE TU HOSTING.
2. En /multimando/private/ localiza:
       FRASE_CIFRADO.php
       palanca.enc
   NO compartas la frase con terceros ni la publiques en GitHub.
3. Si tienes una copia de la WEB ANTERIOR QUE SI FUNCIONABA,
   restaura SOLO el antiguo private/palanca.enc.
   Debe pertenecer a la MISMA version/clave que FRASE_CIFRADO.php.
4. Si eso no funciona, restaura AMBOS archivos COMO PAREJA desde
   la MISMA copia de seguridad que funcionaba:
       private/FRASE_CIFRADO.php
       private/palanca.enc
   No copies un archivo cifrado de una version y la clave de otra.
5. Conserva tu .htaccess de proteccion. No dejes el directorio
   private/ accesible publicamente.
6. Prueba /multimando/control.php en el navegador (NO publiques
   el contenido JavaScript completo). Si la respuesta es 503 y
   muestra 'No se pudo descifrar. Revisa la frase', la pareja
   de cifrado no coincide. Si falta el archivo privado, el
   mensaje indicara ese problema.
7. Refresca /multimando/ en el movil y pulsa CONECTAR.
8. Si el modulo descifra pero el mando no se conecta, comprueba
   ABRIR SALA y PUBLICAR INTERNET en anfitrion v2.2.1 y que el
   enlace AUTO de la API corresponda al tunel Cloudflare actual.

IMPORTANTE: Si se sobrescribio palanca.enc y no tienes respaldo,
NO ES POSIBLE recrearlo con certeza solo desde el archivo del repo
sin conocer la clave compatible. Recupera la pareja cifrada
anterior con el sistema de respaldos de tu hosting.

INSTALAR PARCHE WEB - NO TOCAR EL MODULO CIFRADO
------------------------------------------------
Descarga:
MULTIMANDO_WEB_v2_2_2_PARChe_SIN_PRIVADOS.zip

Sube SOLO estas rutas al directorio /multimando/ del hosting:
       WEB/palanca.php
       WEB/assets/futureo-stream.js

El ZIP incluye LEEME_PRIMERO_REPARAR_MANDO.txt.
No contiene control.php, FRASE_CIFRADO.php ni palanca.enc.

INSTALAR PAQUETE COMPLETO SEGURO
--------------------------------
Descarga:
MULTIMANDO_FUTUREO_STREAM_v2_2_2_SEGURO.zip

ANFITRION:
       MULTIMANDO_FUTUREO_Anfitrion_v2_2_1.py
       futureo_stream_v22.py
Mantener los dos .py juntos. FUTUREO VJOY v0.8.4 sigue igual.

WEB:
       Contiene los archivos nuevos de la web EXCEPTO control.php
       y toda la carpeta private/. Se conservan en tu hosting.
Es obligatorio que existan y funcionen esos archivos originales.

PRUEBAS AUTOMATICAS
-------------------
GitHub Actions valida sintaxis Python/PHP/JS, pruebas del mando por
WebSocket con respuesta welcome, stream anonimo y los dos ZIP.
Ademas verifica explicitamente que NO se empaquete contenido
cifrado, privado o control.php.

No se accede ni instala automaticamente en tiendavibechic.com.
