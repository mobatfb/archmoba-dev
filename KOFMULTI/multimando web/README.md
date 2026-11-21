# KOFMULTI · Multimando Web

Control web compatible con `KOF_Anfitrion.py` (P1/P2, nombres únicos, lista de espera, COIN+START), hecho con PHP, HTML, CSS y JavaScript. Detecta teclado, controles táctiles y gamepads estándar mediante Gamepad API.

## Instalación

1. Requiere **hosting HTTPS, PHP 8.1+ con OpenSSL y zlib**. Se recomienda Apache con `.htaccess` habilitado.
2. Subir **el contenido completo del ZIP privado** a una ruta como `/multimando/`, incluyendo `private/FRASE_CIFRADO.php` y `private/control.enc`.
3. Abrir `https://tusitio.com/multimando/`.
4. Escribir un nombre único y conectar. El PHP consulta la URL publicada en `https://api.isupol.edu.ec/api/geturlkof`; si la API está desactualizada, pegar el enlace directo de Cloudflare en el campo opcional.
5. Si se queda en espera, aguardar la asignación de P1/P2. Usa Enter o START para ingresar a KOF.

## Controles

Teclado: flechas, A/S/Z/X, Enter (COIN+START), 5 (COIN). Táctil: cruceta, 4 botones y COIN/START. Gamepad estándar: cruceta/analog izquierdo, botones A/B/X/Y y Start/Back.

## Cifrado y frase

- El JavaScript se guarda cifrado **AES-256-GCM + gzip** en `private/control.enc`.
- PHP lo descifra **en el servidor** con `private/FRASE_CIFRADO.php` y entrega JavaScript al navegador.
- La **frase real solo está en el ZIP privado de instalación**, no se ha subido a este repositorio público. El archivo `.gitignore` evita subirla por accidente. Para poder instalar desde una clonación de GitHub, debes añadir el archivo privado desde tu copia segura.
- `private/FRASE_CIFRADO.php` debe seguir siendo privado. Contiene una cadena y un bloqueo PHP: si alguien visita su URL directamente, no se muestra.
- **Limitación importante**: cualquier JavaScript que se ejecuta en un navegador puede inspeccionarse o copiarse en las herramientas del navegador. El cifrado protege el archivo **en reposo** y dificulta obtener el código original del repositorio, pero **no impide al 100 % la copia por parte de un visitante**.

## Seguridad

El PHP solo consulta una API fija, valida que el host termine exactamente en `.trycloudflare.com` y no permite que el visitante indique a qué URL debe conectar el servidor PHP. El WebSocket sí se abre directamente desde el navegador del usuario hacia el anfitrión. No almacena contraseñas ni nombre del jugador en el servidor. El nombre único lo valida el anfitrión.

En Apache, `private/.htaccess` bloquea el acceso web a todo el directorio. En Nginx, configura una regla equivalente (`location /multimando/private/ { deny all; }`). En ambos casos, protege la frase con el PHP de ejecución directa.

**No altera** `KOF_Anfitrion.py`, `KOF_Control.py` ni la lógica del marcador.
