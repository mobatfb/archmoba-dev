# MULTIMANDO FUTUREO - ANFITRION v2.3.1

Esta version mantiene los cinco paneles del anfitrion v2.3.0:
**Inicio**, **Transmision**, **Jugadores y cola**, **Configuracion** y **Eventos**.

## NOVEDAD: DOS MODOS DE CAPTURA RAPIDOS

En la pestana **TRANSMISION**, justo al lado de MODO RAPIDO, aparece
el nuevo boton **MODO EQUILIBRADO**:

| Perfil | Tamano maximo | Fotogramas/s | JPEG |
|---|---|---:|---:|
| MODO RAPIDO | 320 x 180 | 15 FPS | 40 |
| MODO EQUILIBRADO (NUEVO) | 480 x 270 | 15 FPS | 50 |

- Los perfiles son accesos directos: al pulsarlos se actualizan los
  selectores TAMAÑO, FPS y JPEG del anfitrion.
- Al utilizar MODO EQUILIBRADO se aplican exactamente
  480x270, 15 FPS y JPEG 50 (valores solicitados).
- Si ya esta transmitiendo, pulsa DETENER antes de cambiar de perfil;
  despues vuelve a pulsar INICIAR TRANSMISION.
- Se conserva la configuracion manual de todos los valores existentes.
- El FPS elegido es el FPS objetivo: el FPS real depende del equipo,
  de la captura y de la conexion.
- El selector 480x270 es el tamaño maximo conservando proporcion
  de imagen. Si la fuente no es 16:9, no se deforma la imagen.

## INSTALACION

1. Cierra el anfitrion de la version anterior.
2. Extrae el ZIP de esta version.
3. Conserva juntos:
   - `MULTIMANDO_FUTUREO_Anfitrion_v2_3_1.py`
   - `futureo_stream_v22.py`
4. Ejecuta en Windows con Python 3.10+:

```bat
py MULTIMANDO_FUTUREO_Anfitrion_v2_3_1.py
```

No se modifica la WEB ni es necesario reinstalar FUTUREO VJOY v0.8.4.
Los canales WebSocket, el tunel Cloudflare, los turnos FIFO, la
transmision para espectadores anonimos y los 1-8 mandos son los mismos
que en la version v2.3.0.

## PRUEBAS

```bat
py MULTIMANDO_FUTUREO_Anfitrion_v2_3_1.py --selftest
```

GitHub Actions valida la sintaxis, --selftest del anfitrion y el montaje
real de la GUI Tkinter en pantalla virtual con ambos presets. Las pruebas
CI no sustituyen una comprobacion de la imagen en tu PC Windows.
