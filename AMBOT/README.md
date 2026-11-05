# AMBOT — laboratorio de stickman 3D

Proyecto experimental ARCHMOBA ROBOTICS (v0.1). Incluye un entorno WebGL 3D, un personaje stickman articulado, cerebro Python con sensores simulados, control manual y exploración autónoma. No hay conexión con hardware real.

## Cómo ejecutarlo en Windows

1. Instala Python 3.9 o posterior (si no lo tienes).
2. Descomprime la carpeta `AMBOT`.
3. Haz doble clic en `INICIAR_AMBOT.bat`.
4. El navegador abrirá `http://127.0.0.1:8765`. Mantén abierta la ventana de la consola.
5. Para cerrar por completo, pulsa `Ctrl+C` en la consola de Python.

**No necesita Tkinter, pip ni internet.** Se usa WebGL cuando está disponible; si no lo está, se activa un renderizador 3D por software integrado (Canvas 2D).

Si el navegador no se abre solo, visita la dirección anterior manualmente. Si el puerto está ocupado: `python servidor.py --puerto 8766`.

## Controles

- **W / ↑:** avanzar según la orientación del robot.
- **A / ←:** girar a la izquierda.
- **D / →:** girar a la derecha.
- **S / ↓:** también permite retroceder de forma segura mediante giro, avance y giro; consume batería simulada.
- **E:** un ciclo de percepción, decisión y acción.
- **Espacio:** encender/apagar exploración autónoma.
- **Ratón:** arrastrar para orbitar la cámara, rueda para acercar/alejar.
- Botones laterales y consola: órdenes `estado`, `mapa`, `plan`, `explora`, `recuerda nombre = dato`, `memoria`, etc.

## Estructura

```text
AMBOT/
├── INICIAR_AMBOT.bat         # lanzamiento en Windows
├── servidor.py               # HTTP local y API JSON
├── cerebro_robot.py          # lógica de percepción/decisión/memoria
├── index.html                # interfaz
├── js/
│   ├── motor3d.js            # escena y renderizado WebGL sin bibliotecas
│   └── control.js            # controles y conexión con Python
├── data/
│   └── .gitkeep              # aquí se generará memoria.json
└── README.md
```

### Arquitectura

`WebGL / stickman ← API HTTP local → cerebro Python ← mapa y sensores simulados`

El mapa del cerebro determina paredes, obstáculos, posición del robot y dirección. El movimiento está sujeto a reglas de seguridad. `memoria.json` guarda los hechos aprendidos cuando se usa el comando `recuerda`.

En esta primera versión el 3D es un simulador para el cerebro: no se trata de una IA conversacional avanzada, no escucha ni usa sensores físicos. La API queda lista para evolucionar hacia esos módulos.
## Integración con AMDEV

- Entrada de la aplicación: `AMBOT/app.py` (APP_VERSION 0.1.0).
- Registro: `AMDEV/apps.json` y `apps.json` del repositorio.
- Configuración: `AMBOT/config.json`.
- En modo repositorio, AMDEV descarga `app.py` y `config.json`. El lanzador recupera únicamente los recursos faltantes usando un `release_commit` fijo.
- En modo local, `python AMBOT/app.py` utiliza directamente los recursos del repositorio sin descargar nada.
- Para iniciar de forma independiente también funciona `python AMBOT/servidor.py`.

Los archivos de prueba, imágenes temporales y la memoria `data/memoria.json` no se publican.
