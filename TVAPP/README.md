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
