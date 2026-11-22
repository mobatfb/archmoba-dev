# MULTIMANDO WEB v6.1.0 / Anfitrion Python v1.5.0

Esta es la distribucion COMPLETA, no un parche. MULTIMANDO es independiente de KOFMULTI.

## Instalacion completa de la WEB (WAMP o hosting PHP)

1. Extrae `MULTIMANDO_WEB_COMPLETA_v6_0_3_SIN_CARPETA.zip` SIN carpeta contenedora.
2. Crea una carpeta `multimando/` en el hosting o WAMP y sube A SU INTERIOR
   directamente `index.php`, `palanca.php`, `control.php`, `config.php`, `sala.php`,
   `.htaccess`, y las carpetas `assets/` y `private/`. En WAMP, por ejemplo:
   `C:\wamp64\www\multimando\index.php`.
   Nunca dejes una carpeta `MULTIMANDO/` anidada dentro de `multimando/`.
   Si actualizas sobre archivos anteriores, sobrescribe TODO el contenido.
3. Abre `http://localhost/MULTIMANDO/` en WAMP, o `https://tudominio/MULTIMANDO/` en HTTPS publico.
4. Requisitos: PHP 8.1+ con OpenSSL y zlib; cURL (preferible) y HTTPS con certificados CA configurados.
5. El ZIP completo incluye `private/FRASE_CIFRADO.php` con la MISMA frase de la instalacion anterior.
   ¡MANTEN ESTA FRASE PRIVADA! No la subas a GitHub ni compartas el ZIP publico.
6. No abras los archivos PHP desde `file:///`; deben ejecutarse mediante Apache/PHP.
7. Si WAMP muestra `No fue posible consultar la API`, comprueba PHP cURL/certificados CA; la
   opcion AUTO usa `sala.php` para GET `/api/geturlmultimando`. El modo MANUAL evita la API.

## Anfitrion Windows

El archivo `MULTIMANDO_Anfitrion.py` v1.5.0 acompana esta version de la web.
Copia el .py a la PC anfitriona y ejecutalo con Windows. Dependencias:

    py -m pip install websockets vgamepad

ViGEmBus es necesario para los dos joysticks Xbox virtuales; `cloudflared` permite
un WSS publico. En la ventana del anfitrion: ABRIR SALA y PUBLICAR INTERNET.
El anfitrion gestiona P1/P2, cola FIFO y 600 s individuales, descontados solo con cola.
No cambies `geturlmultimando` ni `posturlmultimando`; la API se usa para encontrar la URL.

## Controles visibles: X Y L / A B R

    X = tecla U  = boton Xbox X       Y = tecla I = boton Xbox Y
    L = tecla O  = boton Xbox LB      A = tecla J = boton Xbox A
    B = tecla K  = boton Xbox B       R = tecla L = boton Xbox RB

    ARRIBA W    ABAJO S    IZQUIERDA A    DERECHA D
    START Enter    SELECT Retroceso/Backspace

La palanca tactil tiene 8 direcciones. Se admiten raton, pantalla tactil, teclado,
cruceta y analogico del gamepad fisico. `TECLAS` personaliza las asignaciones,
las guarda en el navegador y respeta las preferencias anteriores durante migracion.

## Protocolo WebSocket (ligero)

- Conexión inicial: JSON hello, una sola vez: `{"type":"hello","name":"Bryan"}`.
- Pulsaciones: 2 caracteres, por ejemplo `x1` (presiona X), `x0` (suelta X),
  `u1` (arriba), `e0` (libera derecha), `t1` (START).
- Estados: array JSON de 4 numeros:

      [1,0,1,587]

  Orden: `[puesto, posicion_en_espera, total_en_espera, segundos_restantes]`.
  `puesto` 0=cola, 1=P1, 2=P2; segundo valor 0 cuando tiene mando.
  Si espera, el tiempo se envia como 0; el navegador muestra `--:--`.
  El contador corre cuando hay un P1/P2 y al menos un usuario en cola.
  Una vez en P1/P2 y sin cola el tiempo queda congelado; no se gastan segundos.
- La longitud de `[1,0,1,587]` es **11 bytes UTF-8**: 11 BYTES, NO 11 bits.
  El tamano varia si crecen los numeros (p. ej. posicion de dos cifras).
- El anfitrion envia actualizaciones al cambiar de asignacion o cola; cuando
  el tiempo corre, sincroniza cada 10 s; sin cola, como mucho cada 60 s.
- El navegador actualiza el contador localmente entre sincronizaciones.
- Bienvenida y mensajes excepcionales siguen siendo JSON por legibilidad.
- Python registra las pulsaciones en consola, con nombre del usuario y P1/P2.

## Archivos incluidos

- index.php / palanca.php / control.php / sala.php / config.php
- assets/palanca.css
- private/palanca.enc, FRASE_CIFRADO.php, proteccion .htaccess y nota de seguridad
- .htaccess y .gitignore de la raiz

## Seguridad

No publiques `private/FRASE_CIFRADO.php` en GitHub ni lo coloques en una carpeta
servida sin reglas de denegacion. La opcion AUTO consulta la API fija por PHP.
El JavaScript entregado al navegador puede inspeccionarse (cifrado en reposo).
No se transmiten imagenes ni audio de la PC. El host no ejecuta instrucciones arbitrarias.

## v6.0: interruptor ANALOGICO / CRUCETA

- El mando incluye un interruptor que alterna ANALOGICO (por defecto) y CRUCETA.
  Se recuerda la preferencia de cada usuario en localStorage.
- ANALOGICO REAL: la posicion de la palanca envia la deflexion proporcional.
  Zona muerta radial 14% en pantalla tactil y 17% en gamepad fisico,
  curva suave 1.12, diagonales normalizadas y retorno exacto a (0,0).
- En este modo el navegador envia 3 bytes BINARIOS por cambio de eje:
  `A1 XX YY`, cabecera 0xA1 y ejes X/Y con signo de -127 a +127.
  El eje Y positivo significa ARRIBA, el X positivo DERECHA. Envios
  limitados a 30 por segundo; el centro se comunica inmediatamente.
- CRUCETA: cuatro botones de direcciones, admite arrastre y diagonales.
  Sigue usando las pulsaciones de DOS caracteres: u1/u0, d1/d0,
  i1/i0, e1/e0. El mando virtual desactiva el stick izquierdo en este modo.
- El navegador avisa una vez por seleccion con `m1` (analogico)
  o `m0` (cruceta), sin modificar la API ni el array de estado.
- TECLAS sigue igual (WASD, UIO/JKL, Enter, Backspace), pero las
  DIRECCIONES actuan sobre el tipo de control que esta seleccionado.
- Los seis botones X Y L / A B R no cambian, ni las asignaciones locales,
  la conexion AUTO, P1/P2, cola FIFO o los 10 minutos con pausa sin cola.
- El anfitrion anterior 1.4 no acepta ejes binarios. Es obligatorio
  actualizar el Python a 1.5 para usar la palanca analogica.
- Clientes web antiguos sin selector mantienen el modo heredado en Python.

## v6.0.1: solucion a pagina sin estilos en hosting

Si ves HTML plano (fuente Times, botones grises y sin fondo), significa que
`assets/palanca.css` no se estaba aplicando (archivo ausente, ruta, reescritura
WordPress o MIME incorrecto). Esta version incorpora el CSS de manera directa
en `palanca.php`, con un nonce CSP, de modo que el diseño no depende de una
peticion HTTP a `assets/palanca.css`. Si el archivo CSS se encuentra, se usa
la version local mas reciente. Si no esta, se usa una copia completa incorporada.
La politica CSP mantiene `script-src 'self'`, y las acciones WebSocket siguen igual.

La ruta publica del CSS es opcional para que la pagina tenga estilo, pero debe
conservarse `assets/palanca.css` para facilitar el mantenimiento. Esta actualizacion
NO cambia el JS cifrado, las teclas, el modo analogico/cruceta, P1/P2 ni Python.

DIAGNOSTICO: abre en el navegador `/multimando/assets/palanca.css?v=6.0.0`;
si devuelve HTML o 404, faltan archivos o hay una reescritura del hosting.
Con v6.0.1 esto ya no deja el mando sin formato.

## v6.0.3: controles equilibrados en móviles

- En móviles en orientación vertical los mandos permanecen lado a lado, también en pantallas altas (sin pasar a una columna).
- La palanca/cruceta se desplaza ligeramente arriba y las seis acciones X Y L / A B R ligeramente abajo, conforme a la referencia.
- Joystick y cruceta conservan proporción cuadrada en teléfonos estrechos; SELECT/START siguen accesibles.
- El CSS está embebido en palanca.php como respaldo: el diseño sigue funcionando aunque el hosting no sirva assets/palanca.css.
- Misma configuración de teclas, perfiles guardados, conexión AUTO, WebSocket, Python 1.5, temporizadores y API. No hay cambios de protocolo.
- ZIP completo sin carpeta contenedora MULTIMANDO/. Instalar directamente en la carpeta multimando de WAMP/hosting.


## v6.1.0 - tres modos de movimiento

Selector del mando: **ANALÓGICO / CRUCETA / MIXTO**.

- ANALÓGICO: palanca circular proporcional; transmite ejes calibrados en paquetes binarios de 3 bytes (sin cambios).
- CRUCETA: cuatro botones direccionales, permite diagonales por arrastre; utiliza u1/u0, d1/d0, i1/i0, e1/e0.
- MIXTO: palanca circular con zona muerta (14 % en táctil), pero genera las mismas ocho direcciones DIGITALES de la cruceta; no transmite fuerza proporcional ni paquetes analógicos. Permite diagonales al arrastrar.
- El anfitrión Python v1.5.0 recibe m1 en ANALÓGICO y m0 en CRUCETA o MIXTO; no se modifica Python ni Laravel.
- La selección se recuerda localmente; versiones anteriores con modo CRUCETA o ANALÓGICO guardado siguen respetándose.
- WASD + U/I/O (X/Y/L) + J/K/L (A/B/R) + Enter (START) + Retroceso (SELECT) no cambian.
- Se conservan AUTO/manual, P1/P2, cola, temporizadores, joystick USB/Bluetooth, personalización y estilos integrados en palanca.php.
- WEB COMPLETA: los 13 archivos están en la RAÍZ del ZIP, sin carpeta MULTIMANDO/.


## v6.1.1 - ajuste exclusivo para movil en horizontal

- Se ajusta SOLO la vista de telefonos girados (orientacion horizontal, pantalla de poca altura y entrada tactil).
- Se oculta la cabecera duplicada y el pie informativo durante el juego horizontal para liberar espacio. La conexion, AUTO, estado P1/P2, tiempo, cola, selector de modo, botones, START/SELECT y TECLAS siguen visibles.
- Se compactan las franjas de conexion y de estado, aumentando el espacio util para palanca/cruceta y seis botones.
- START y SELECT se desplazan unos pixeles hacia abajo y quedan separados de la fila A/B/R para evitar pulsaciones accidentales.
- El tamaño de las zonas de control se adapta a la altura real util del navegador, incluso con sus barras visibles.
- NO cambia la vista vertical ni la de escritorio con raton. Tampoco cambia el JavaScript cifrado, mandos, perfiles, WebSocket, API, Python o temporizadores.
- ZIP de web completa con los 13 archivos en la raiz, sin carpeta MULTIMANDO/.


## v6.1.2 - MIXTO octagonal, botones auxiliares y credito

- MIXTO: marco octagonal, 8 flechas alrededor y mando interior cuadrado con centro en diamante. La direccion activa se ilumina. Visualmente distinto del ANALOGICO redondo y de la CRUCETA de cuatro teclas.
- MIXTO sigue enviando los mismos eventos digitales de dos caracteres; ANALOGICO conserva la intensidad binaria de tres bytes. El Python 1.5 no cambia.
- START y SELECT: una separacion tactil adicional en movil vertical y horizontal para que no interfieran con A/B/R. La vista PC permanece igual.
- Credito final: Idea por: por Bryan Paredes Gracia (FORTUNEO - RYANEXX)
- Contenido web completo, 13 archivos directamente en la raiz del ZIP, sin carpeta contenedora.
- El JavaScript se cifra con la MISMA frase AES-GCM de versiones anteriores, que permanece privada y no se sube al repositorio.

## v6.1.3: MIXTO con cruceta y mini palanca

- El modo MIXTO cambia exclusivamente de aspecto: cruceta física en cruz y mini joystick móvil en el centro; desaparecen el octágono y los ocho botones flotantes anteriores.
- Las cuatro direcciones principales y diagonales mantienen su indicador de pulsación iluminado. MIXTO sigue enviando comandos digitales de 2 caracteres y admite ocho direcciones; el ANALÓGICO conserva su movimiento proporcional.
- Se mantienen el diseño vertical y horizontal, los botones START/SELECT separados, el crédito de autoría, la conexión AUTO, las teclas configurables y toda la lógica Python.
- El JavaScript cifrado es exactamente el de v6.1.2; no requiere una nueva frase.
