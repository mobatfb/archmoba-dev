# MULTIMANDO

Repositorio de desarrollo de MULTIMANDO. La web se ha trasladado a una carpeta dedicada.

## Estructura del proyecto

- [`MANDOWEB/`](MANDOWEB/) - Sitio PHP, estilos y recursos web. Codigo actual del repositorio: v6.1.3.
- [`ANFITRION/`](ANFITRION/) - Aplicacion Python del anfitrion para Windows.
- [`FUTUREO_VJOY/`](FUTUREO_VJOY/) - Driver HID experimental y herramientas de administracion.

## Publicar la web

Sube **el contenido de `MULTIMANDO/MANDOWEB/`**, no la carpeta completa,
a la raiz web que usaba anteriormente MULTIMANDO (por ejemplo, `/multimando/`).
Los PHP mantienen rutas relativas entre `index.php`, `palanca.php`, `control.php`,
`sala.php`, `config.php`, `assets/` y `private/`.

El sitio necesita PHP con OpenSSL y zlib; consulta [`MANDOWEB/README.md`](MANDOWEB/README.md)
para instrucciones de despliegue e historial. El archivo privado
`MANDOWEB/private/FRASE_CIFRADO.php` **no se almacena en GitHub** y debe
conservarse de forma segura en el servidor (con la frase correspondiente
al JavaScript cifrado). No publiques la frase ni la incrustes en el repositorio.

El traslado reorganiza los archivos del repositorio, pero **no realiza un
despliegue automático en el hosting** ni actualiza el contenido a una versión
web posterior a la que ya estaba publicada aquí.

Los archivos de protección `.htaccess` y `.gitignore` siguen existiendo
en `MULTIMANDO/`; `MANDOWEB/` también tiene sus propias copias.
