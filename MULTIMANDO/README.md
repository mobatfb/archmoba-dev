# MULTIMANDO v5.8 / Anfitrion 1.3.0 - Estado WebSocket optimizado

Parche SOLO de archivos modificados, independiente de KOFMULTI.

## Por que cambiamos

Antes el servidor enviaba a CADA jugador, dos veces por segundo, un JSON grande que repetia:
los datos de ambos jugadores, sus nombres, IDs, lista completa de cola, tiempos y estados.
La API no participa en esos mensajes y NO necesita cambios.

## Protocolo de estados nuevo

El anfitrion envia el estado PERSONAL del usuario, por ejemplo:

`{"type":"s","s":1,"p":0,"q":1,"t":587,"r":1}`

- `s`: puesto (0=cola, 1=P1, 2=P2).
- `p`: lugar en cola; 0 si se tiene mando.
- `q`: cantidad total esperando.
- `t`: segundos restantes; `null` si espera.
- `r`: 1=el reloj corre porque hay cola; 0=el reloj esta en pausa.

No se incluyen nombres de otros usuarios, lista de cola, ni room_id en cada estado.
El room_id se envia en `welcome`, una sola vez.

**Frecuencia:** estado al conectar y cada vez que cambian asignaciones, lugares o cola.
Si el reloj corre, sincroniza como maximo cada 10 s; si esta pausado, cada 60 s.
El navegador anima el contador localmente sin solicitar nada.
La asignacion P1/P2 y el tiempo real siguen siendo controlados SOLO por Python.

## Sin cambios

- Entradas de 2 bytes: `x1`, `x0`, `a1`, `a0`, `u1`, `u0` ...
- Botones X Y L / A B R, teclas WASD+UIO/JKL, SELECT y START.
- Backend Laravel `geturlmultimando` / `posturlmultimando`, MySQL, casilla AUTO, Cloudflare.
- Cola FIFO y 10 minutos solo cuando hay espera; mandos Xbox virtuales P1/P2.
- La ventana local de Python sigue mostrando el listado completo sin enviarlo por Internet.
- Compatibilidad de la web con mensajes `type:"state"` del anfitrion anterior.

## Instalacion incremental

1. En hosting WAMP/PHP sustituye `MULTIMANDO/palanca.php` y `MULTIMANDO/private/palanca.enc`.
2. En Windows sustituye `MULTIMANDO/ANFITRION/MULTIMANDO_Anfitrion.py` y reinicia el anfitrion/sala.
3. Conserva `MULTIMANDO/private/FRASE_CIFRADO.php`; el `.enc` usa la MISMA clave y no se incluye la frase.
4. En el navegador recarga con Ctrl+F5; el CSS no necesita cambios.
5. No actualices PHP sin Python ni Python sin PHP (nuevo estado requiere nueva palanca).

El protocolo `hello` sigue siendo JSON y las pulsaciones siguen siendo textos de 2 caracteres.
Los frames WebSocket tambien tienen cabeceras y trafico de transporte, aparte del JSON.
