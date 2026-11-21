# MULTIMANDO | Palanca Web v1.0

Proyecto **independiente** de KOFMULTI. Palanca web táctil y compatible con teclado y mandos USB/Bluetooth que envía acciones a un anfitrión Python mediante WebSocket. No utiliza la API de KOF.

## Requisitos e instalación

1. Usar hosting **HTTPS**, **PHP 8.1 o superior**, **OpenSSL y zlib**. Para el proxy de API, cURL (preferido) o `allow_url_fopen` con HTTPS.
2. Extraer el **ZIP privado completo**, incluida la carpeta `private/FRASE_CIFRADO.php` y `private/palanca.enc`. Subirlo a una ruta como `https://tusitio.com/MULTIMANDO/`.
3. Abrir `index.php` o `palanca.php`. Escribir el nombre del jugador y pulsar **CONECTAR**. El servidor PHP consulta `https://api.isupol.edu.ec/api/geturlmultimando` a través de `sala.php` para evitar CORS.
4. Si lo necesitas, puedes configurar una URL de sala HTTPS en `config.php` (`manual_room_url`) o pegar un enlace directo seguro en la pantalla de conexión. Se permiten únicamente subdominios `*.trycloudflare.com`.
5. Cuando el anfitrión Python esté operativo y publique su URL a `https://api.isupol.edu.ec/api/posturlmultimando`, el mando podrá conectarse sin copiar enlaces.

**Importante:** Esta entrega contiene el **cliente web**. Para administrar conexiones y controlar físicamente un dispositivo es necesario crear y ejecutar el **anfitrión Python independiente de MULTIMANDO**. Sin un anfitrión activo el cliente mostrará la interfaz, pero no podrá mover un control remoto ni gestionar turnos. El PHP no maneja temporizadores reales ni ocupa P1/P2: eso corresponde al Python.

## Archivos

- `palanca.php`: página principal (HTML accesible con PHP).
- `index.php`: abre `palanca.php`.
- `assets/palanca.css`: estilo visual y diseño responsive.
- `sala.php`: proxy seguro para consultar la URL mediante la API de MULTIMANDO.
- `config.php`: configuración, nombre de la API, identificador fijo de registro, URL directa opcional.
- `control.php`: descifra y entrega el JavaScript al navegador.
- `private/palanca.enc`: código del mando cifrado con AES-256-GCM y comprimido con gzip.
- `private/FRASE_CIFRADO.php`: **privado, solo dentro del ZIP de instalación**, no disponible en el repositorio público.
- `private/.htaccess`: prohíbe acceder por HTTP a los archivos privados en Apache.

## API Laravel y tabla

La tabla única será `amo_multimando`, con el ID `multimandoremoteryanexx`. Las rutas Laravel deberían operar sobre esa tabla:

```php
// Ejemplo de GET (requiere importar Route, Request y DB en routes/api.php)
Route::get('/geturlmultimando', function () {
    $room = DB::table('amo_multimando')
        ->where('id', 'multimandoremoteryanexx')->first();
    return response()->json(['status' => 'success', 'url' => $room->url ?? null]);
});
```

La ruta `POST /posturlmultimando` deberá validar la URL Cloudflare, contar con **autenticación de anfitrión** (por ejemplo, token de API), y actualizar la columna `url` de `amo_multimando`. No usar `amo_users` ni guardar contraseñas en este proyecto.

## Protocolo que deberá implementar el anfitrión Python

El navegador envía inicialmente:

```json
{"type":"hello","name":"Jugador 01"}
```

El anfitrión responde:

```json
{"type":"welcome","you":1,"room_id":"ABCD12"}
```

El anfitrión envía estados actualizados al conectar, al cambiar la cola, al asignar puestos y periódicamente (recomendado cada segundo mientras se ejecuta un turno):

```json
{
  "type":"state",
  "room_id":"ABCD12",
  "slot":1,
  "waiting_position":0,
  "timer_remaining":588,
  "timer_running":true,
  "players":{
    "1":{"id":1,"name":"Jugador 01","remaining_seconds":588,"timer_running":true},
    "2":{"id":2,"name":"Jugador 02","remaining_seconds":594,"timer_running":true}
  },
  "queue":[{"id":3,"name":"Jugador 03"}]
}
```

La palanca envía entradas de presión y liberación (la misma acción sirve para P1 o P2, el anfitrión hace la asignación):

```json
{"type":"input","action":"UP","down":true}
{"type":"input","action":"UP","down":false}
```

Acciones admitidas: `UP`, `DOWN`, `LEFT`, `RIGHT`, `A`, `B`, `C`, `D`, `START`, `SELECT`. También puede enviar `{"type":"yield"}` para ceder y `{"type":"request"}` para pedir turno. Respuestas opcionales: `notice`, `error`, `input_ack`.

**Reglas de turnos requeridas en Python:** dos puestos P1/P2, lista FIFO, 600 s por nuevo turno, **el contador solo descuenta cuando la cola no está vacía**, se pausa al vaciarse, conserva el saldo al reanudarse, y al llegar a cero libera el puesto al siguiente de la cola. Python debe ser la fuente de verdad del saldo, no el reloj local del navegador.

## Controles

- Palanca: arrastre táctil/mouse/pen de 8 direcciones; puede enviar diagonales simultáneas.
- Teclado: flechas para direcciones; A/S/Z/X -> acciones A/C/B/D; `Enter` -> START; tecla `5` -> SELECT.
- Gamepad estándar: cruceta, joystick izquierdo, 4 botones, Start y Select/Back.
- El navegador suelta teclas y direcciones al perder el foco para evitar comandos bloqueados.

## Cifrado y seguridad

El JavaScript se almacena cifrado mediante **AES-256-GCM + gzip** en `private/palanca.enc` y PHP lo descifra con `private/FRASE_CIFRADO.php` al servir `control.php`. **No es posible impedir completamente que un visitante copie el JavaScript que ejecuta su navegador**; el cifrado protege el archivo guardado y evita publicar el código original en el repositorio. No subir nunca el archivo `FRASE_CIFRADO.php` a GitHub público.

En Apache, el directorio `private/` queda bloqueado por `.htaccess`. Si usas Nginx, configura explícitamente `location /MULTIMANDO/private/ { deny all; }` o guarda `private/` fuera de la raíz pública. No expongas la frase ni los archivos fuente.