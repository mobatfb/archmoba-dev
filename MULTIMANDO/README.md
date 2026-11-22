# MULTIMANDO WEB v6.0 / Anfitrion Python v1.5.0

Esta es la distribucion COMPLETA, no un parche. MULTIMANDO es independiente de KOFMULTI.

## Instalacion completa de la WEB (WAMP o hosting PHP)

1. Extrae `MULTIMANDO_WEB_COMPLETA_v6_0.zip` respetando la carpeta MULTIMANDO.
2. Coloca toda la carpeta `MULTIMANDO/` en el directorio publico del servidor PHP (ej.: `C:\wamp64\www\MULTIMANDO\`).
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
