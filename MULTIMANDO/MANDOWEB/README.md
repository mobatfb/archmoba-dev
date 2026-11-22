# MULTIMANDO WEB v6.2.0 / Anfitrion Python v1.8.1

Distribucion COMPLETA (no es parche), independiente de otros proyectos. Permite
**1 a 8 joysticks virtuales genericos vJoy / HID / DirectInput**, no Xbox/XInput.
Los puestos se identifican en MULTIMANDO como **VJOY1..VJOY8**, aunque el nombre
PnP que muestra Windows depende del controlador vJoy.

## Instalacion web (WAMP/hosting PHP)

1. Extrae `MULTIMANDO_WEB_COMPLETA_v6_2_0_SIN_CARPETA.zip` dentro de la carpeta `multimando/`
   de tu hosting (sin anidar otra carpeta). Sobrescribe los archivos anteriores.
2. Sirve `index.php` y `palanca.php` desde Apache/PHP, no como `file://`.
3. Requiere PHP 8.1+ con OpenSSL y zlib; configura el servidor HTTPS para el publico.
4. `private/FRASE_CIFRADO.php` es SECRETA. Mantenla protegida con el `.htaccess`
   suministrado, pero lo mas seguro es situarla fuera de la raiz publica.
   NO SUBAS LA CLAVE NI LOS ZIP COMPLETOS A GITHUB PUBLICO.
5. El JavaScript se distribuye cifrado en `private/palanca.enc`; `control.php`
   lo descifra para entregar al navegador. No subas `control_decoded.js` al hosting.
6. La opcion AUTO consulta la API `https://api.isupol.edu.ec/api/geturlmultimando`
   a traves de `sala.php`. MANUAL permite usar un enlace `trycloudflare.com`.

## Anfitrion Windows v1.8.0

- Instala vJoy compatible con tu version de Windows y, en **Configure vJoy**, habilita
  los Device IDs del 1 al 8 que vayas a utilizar, cada uno con ejes X/Y y al menos
  ocho botones. Para cruceta con POV configura un hat continuo si tu juego lo necesita.
- Instala Python 3.10+ y dependencias:

      py -m pip install websockets pyvjoystick pygame

  `pygame` es para leer mandos fisicos USB/Wi-Fi en modo CONTROLADO;
  los puestos REMOTO solo necesitan `websockets` y `pyvjoystick`.
- El anfitrion crea dispositivos vJoy en Windows: **no** necesita ViGEmBus ni
  `vgamepad` para esta distribucion.
- Ejecuta `MULTIMANDO_Anfitrion.py`. Antes de pulsar ABRIR SALA elige **1 a 8
  jugadores** y usa **CONFIGURAR VJOY** para establecer cada puesto como:
  **REMOTO** (P3 = VJOY3 y participa en cola FIFO) o **CONTROLADO** (elige
  mando fisico y utiliza el menu de botones APRENDER para mapearlo a VJOY).
- Boton **IDENTIFICAR VJOY**: pulsa brevemente el boton 8 del dispositivo seleccionado
  para que puedas identificarlo en la pantalla de configuracion del juego.
- ABRIR SALA inicia el WebSocket en 127.0.0.1:8766 por defecto; PUBLICAR INTERNET
  requiere `cloudflared` y publica la URL en la API de MULTIMANDO.
- **Importante:** vJoy es un dispositivo DirectInput/HID generico. Algunos juegos
  solo aceptan XInput y pueden no reconocer estos mandos. Aun no se ha probado
  esta version con 8 vJoy reales simultaneos en Windows.

## Reglas de jugadores y seguridad

- El **nombre tiene 10 caracteres como maximo** (web y servidor), sin truncarlo
  en Python. Los nombres repetidos se bloquean. Reconexion segura con token de
  sesion; no basta con copiar el nombre de otro participante.
- Si eliges 2 puestos REMOTO y se conectan 3 jugadores, el tercero espera.
  Los puestos CONTROLADO no entran en cola y nunca se asignan a visitantes.
- Cuando un visitante recibe un REMOTO: aparece popup **3, 2, 1**, suena una alerta
  breve en el 3, y solo DESPUES dispone de **10 segundos para pulsar o mover**.
  Sin entrada y con cola, el visitante va al final de la fila, entra el siguiente
  y todos los botones/ejes del VJOY desocupado quedan neutros.
- La primera pulsacion valida inicia el turno completo de 600 segundos. Este
  contador **solo descuenta mientras existe cola**; sin cola se congela.
  Al finalizar, el jugador pasa al final y entra el siguiente FIFO.
- La web cuenta **5 minutos mientras se espera** y muestra un popup con aviso
  audible: SEGUIR ESPERANDO / CEDER MI TURNO. Si no responde en 60 segundos,
  envía `q0` al servidor para retirar al usuario de la cola. El servidor NO manda
  los recordatorios: solo acepta la decision del navegador.
- Si se corta el WebSocket, servidor y web liberan botones y analogicos. El host
  reserva el lugar por 35 segundos y la web reintenta hasta 40 segundos.
  El anfitrion puede retirar un mando REMOTO y pasarlo a CONTROLADO;
  el jugador afectado se desconecta sin reconexion automatica.

## Protocolo ligero

- `hello` JSON incluye nombre, token opcional y soporte de latidos.
- `h`: latidos bidireccionales cada ~2 s; se liberan teclas al faltar señal.
- Pulsaciones: 2 caracteres (`a1`, `a0`, `u1`, `u0`, etc.).
- Modo analogico: 3 bytes binarios `A1 XX YY` con ejes firmados.
- Estado individualizado: **6 enteros** `[puesto, posicion_cola, total_cola,
  restantes_juego, restantes_activacion, restantes_popup]`, ejemplo
  `[3,0,1,600,0,3]`. No se envia a Internet la lista de jugadores.
- `q1` confirma seguir esperando y `q0` cede el turno desde la web.
- JavaScript web preexistente en modo ANALOGICO, CRUCETA y MIXTO, teclado
  configurable y diseno adaptable a movil.

## Archivos incluidos

El ZIP web incluye PHP, hojas CSS y `private/palanca.enc` con su frase protegida.
El ZIP completo agrega `ANFITRION/MULTIMANDO_Anfitrion.py` y este README.
La web y Python **se actualizan juntos**, ya que el estado de 6 enteros y el
plazo inicial 3+10 s requieren ambos componentes.

## Historial anterior

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

## Reconexión automática (v6.1.4 / anfitrión v1.5.1)

- Después de una conexión aceptada, el anfitrión entrega un token aleatorio de recuperación por WebSocket.
- Ante un corte involuntario, la web muestra REINTENTANDO y consulta AUTO o URL manual cada 1,4 s durante hasta 40 s.
- El anfitrión reserva el turno/mando durante 35 s después de detectar la desconexión. Suelta los botones de inmediato por seguridad.
- Para recuperar una sesión, el navegador envía `hello` con `name` y `resume_token`. El servidor valida ambos, reconecta al usuario existente y conserva el tiempo restante y la posición en la cola.
- Un nombre duplicado SIN token válido continúa rechazado; no es posible apropiarse de una sesión solo escribiendo el mismo nombre.
- El token queda en `sessionStorage` de la pestaña. SALIR elimina el token y envía `bye` para liberar el mando sin esperar.
- Si se pierde la conexión definitivamente o se cierra el anfitrión, el puesto deja de estar reservado al terminar el margen.
- Actualiza la web y el anfitrión juntos; las versiones anteriores no admiten restauración con token.
- Estos tiempos son márgenes de aplicación y no garantizan que una red inestable pueda reconectar.

## v6.1.6 / Python v1.5.3: mando neutro ante perdida de enlace

- El servidor nunca espera un mensaje de "soltar" para limpiar el mando:
  cuando se cierra el WebSocket, cuando se recupera un socket anterior y cuando
  un navegador deja de confirmar latidos durante 6 segundos, libera TODOS los
  botones, direcciones, temporizadores de pulsacion y stick analogico del P1/P2
  afectado. El otro jugador sigue funcionando normalmente.
- La web y el servidor intercambian un caracter "h" en cada sentido cada 2 s.
  Si no recibe confirmacion durante 7 s, el navegador limpia los controles,
  muestra el reintento y busca recuperar su sesion con su token. Los clientes
  antiguos sin soporte de latidos siguen funcionando mediante ping de WebSocket.
- Un socket sustituido no puede volver a mandar acciones ni cerrar la sesion
  del mismo jugador. Despues de reconectar, el mando comienza neutro.
- El gamepad fisico exige regresar a estado neutral antes de reactivar acciones,
  para no repetir un boton que ya estaba pulsado antes de la caida.
- Se conserva la cola FIFO y el plazo de reserva de 35 s. El pie de pagina
  muestra el credito FUTUREO - RYANEXX conforme a lo solicitado.

## Publicacion GitHub

Esta carpeta MANDOWEB corresponde a la web v6.2.0 y debe utilizarse con
el anfitrion v1.8.1 de la carpeta ANFITRION. Los paquetes ZIP originales
contienen una frase privada para descifrar palanca.enc; esa frase NO esta
en GitHub y debe conservarse en el servidor de despliegue. Para instalar
en el hosting, publica el contenido de esta carpeta en la ruta web actual.
