# ARCHMOBA TVAPP

Nueva aplicacion independiente dentro de archmoba-dev.

- tvapp.py: interfaz embebida. Contiene VERSION = "1.0.0" y render(parent).
- app.py: ventana principal, muestra la version local y permite actualizar desde GitHub.
- iniciar.bat: inicia en Windows y, si no existe Python 3, intenta instalar Python 3.13 mediante winget.

## Uso

En Windows, descarga los archivos de esta carpeta juntos y haz doble clic en iniciar.bat.
Si ya tienes Python 3.10+ con tkinter, tambien puedes ejecutar: python app.py

## Publicar una actualizacion

1. Edita tvapp.py en la rama main de GitHub.
2. Aumenta VERSION, por ejemplo de 1.0.0 a 1.0.1.
3. Conserva la funcion render(parent), que debe devolver un widget tkinter.
4. En app.py, pulsa Actualizar.

La app verifica una version mayor, descarga tvapp.py, instala en segundo plano los
imports externos faltantes mediante pip y recarga el widget en la misma ventana.
El primer inicio puede funcionar sin conexion, si tvapp.py ya esta disponible.

La instalacion de dependencias se realiza unicamente para imports que no sean de
la biblioteca estandar ni modulos locales. Algunos nombres de paquetes PyPI se
ajustan con el diccionario PIP_NAMES en app.py. No ejecuta el codigo actualizado
hasta finalizar la instalacion. Publica codigo solamente desde repositorios confiables.

Nota: ningun archivo .py puede instalar Python si no existe un interprete capaz
de ejecutarlo. Por eso se incluye el iniciador iniciar.bat (Windows).
tkinter forma parte de la distribucion habitual de Python para Windows; no se
instala con pip.

## Iniciador para Windows (.exe)

El archivo `launcher.go` contiene el codigo fuente del iniciador independiente de Windows (64 bits), compilado con Go (sin dependencias externas). Al abrir `TVAPP_Launcher.exe`:

1. Descarga `TVAPP/app.py` de la rama `main` y lo guarda en `%LOCALAPPDATA%\\ARCHMOBA\\TVAPP\\app.py`.
2. Comprueba si Python 3.10+ dispone de `tkinter`. Si no lo encuentra, intenta instalar Python 3.13 con `winget`.
3. Ejecuta `app.py` y cierra el iniciador. `app.py` se encarga de descargar y visualizar `tvapp.py`.
4. Si GitHub no responde y ya existe una copia local de `app.py`, intenta utilizarla.

Para compilar en Windows con Go instalado:

```bat
go build -trimpath -ldflags="-s -w -H=windowsgui" -o TVAPP_Launcher.exe launcher.go
```

El ejecutable es una aplicacion de escritorio (sin consola). Para la instalacion automatica de Python, Windows debe tener winget. No incluye firma digital.

## Actualizacion por commit (v1.1 del iniciador)

- `app.py` consulta la API de GitHub para conocer el commit mas reciente que modifico `TVAPP/tvapp.py`.
- Descarga el archivo asociado exactamente a ese SHA (URL inmutable); no depende del cache de la rama `main` ni de que cambie `VERSION`.
- Guarda la ultima revision aplicada en `.tvapp_update.json` y compara el hash SHA-256 del archivo local antes de decidir si debe descargar otra copia.
- Al abrir la aplicacion muestra la copia local, si existe, y comprueba los commits en segundo plano; al presionar **Actualizar** realiza la misma comprobacion.
- Si la API falla, utiliza una descarga directa con parametro anticache. Si tampoco hay conexion, conserva la ultima interfaz local funcional.
- El iniciador Windows actualizado (`TVAPP_Launcher_v1.1.exe`) tambien consulta el commit mas reciente de `app.py` antes de descargarlo y abrirlo. El ejecutable compilado se distribuye por separado; el fuente permanece en `launcher.go`.

**Importante:** despues de modificar `app.py` en GitHub, cierra la aplicacion y vuelve a abrir el ejecutable para recibir el nuevo mecanismo de actualizacion. Luego los cambios de `tvapp.py` se mostraran desde el propio boton sin recompilar el EXE.

## TVAPP v1.0.11: IPTV-org integrado

`TVAPP/tvapp.py` utiliza listas públicas de IPTV-org y **ya no muestra canales ficticios**. Conserva la interfaz móvil de 380 × 650 px y la barra de navegación flotante.

- **Todos**: `index.m3u`; **Categorías**: `index.category.m3u`
- **Noticias, Deportes, Películas, Música**: listas de `categories/{news,sports,movies,music}.m3u`
- **Países, Idiomas**: `index.country.m3u` y `index.language.m3u`; usa el selector desplegable para elegir un grupo
- **Ecuador, Español, Infantil, Cultura, Documentales**: accesos rápidos a las listas correspondientes
- **Favoritos**: se guardan en `%LOCALAPPDATA%\\ARCHMOBA\\TVAPP\\favorites.json` en Windows
- **Carga**: descargas en hilos secundarios, caché local durante una hora, sin bloquear la interfaz. En caso de error, intenta la última copia local
- **Búsqueda**: filtra por nombre en la categoría actual; el botón de estrella agrega o quita favoritos
- **Logotipos**: se obtienen de `tvg-logo` cuando están disponibles (Pillow es opcional para JPEG/WebP)
- **Reproducción**: al abrir un canal intenta incrustar video con `python-vlc`. Si no está instalado, intenta instalar el módulo en segundo plano. Para reproducir dentro de la ventana **también se necesita VLC Desktop/libVLC** en Windows. El botón «Abrir VLC» ofrece abrir el canal externamente cuando corresponda

Se necesita acceso a Internet para cargar listas no cacheadas y para reproducir transmisiones. Algunos enlaces públicos pueden fallar, estar restringidos por región o no ser compatibles con el reproductor. No se incluyen credenciales ni servicios privados. La sección VOD muestra canales de la categoría Películas; no constituye una biblioteca de video bajo demanda.

La versión de `app.py` y la de `tvapp.py` son independientes. Para recibir los cambios del catálogo M3U, basta con pulsar el icono de actualizar en el `app.py` actual.
