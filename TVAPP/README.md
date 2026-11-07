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
