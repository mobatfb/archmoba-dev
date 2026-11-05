# AMBOT — ARCHMOBA Robotics

**AMBOT 0.2.1** es una aplicación de escritorio **Python**, no un sitio web.

## Cómo iniciarlo
- Desde **AMDEV**: elegir **AMBOT**. AMDEV ejecuta \`AMBOT/app.py\` directamente.
- En Windows: doble clic en \`INICIAR_AMBOT.bat\`.
- También: \`python AMBOT/app.py\`.

Se abre una **ventana nativa** mediante \`pygame-ce\`; **no levanta servidores HTTP, no utiliza navegador, Tkinter, HTML ni JavaScript**. Al primer inicio, cuando falte la librería, el lanzador la instala automáticamente en \`%LOCALAPPDATA%\\ARCHMOBA\\AMBOT\\dependencies\` sin modificar la instalación global de Python. Requiere Internet solo para esa instalación inicial.

La escena tridimensional está construida con geometría XYZ, proyección en perspectiva y una cámara orbital. El robot stickman se mueve, gira, evita obstáculos y puede explorar por sí mismo. Todo el código de interfaz, entorno 3D y cerebro se encuentra en el único archivo \`AMBOT/app.py\`.

## Controles
| Control | Función |
| --- | --- |
| W / ↑ | Avanzar |
| S / ↓ | Retroceder |
| A / ← | Girar izquierda |
| D / → | Girar derecha |
| E | Explorar un paso |
| Espacio | Explorar automáticamente / pausar |
| R | Reiniciar cuerpo |
| Tab | Escribir un comando |
| Ratón arrastrando | Girar la cámara |
| Rueda | Acercar o alejar |

Puedes escribir \`estado\`, \`sensores\`, \`pensar\`, \`explora\`, \`recuerda nombre = AMBOT\`, \`que sabes de nombre\`, \`olvida nombre\`, \`memoria\`, \`cargar\` y \`ayuda\`.

## Archivos y diagnóstico
- Aplicación: \`AMBOT/app.py\`
- Configuración para AMDEV: \`AMBOT/config.json\`
- Memoria persistente: \`%LOCALAPPDATA%\\ARCHMOBA\\AMBOT\\memoria.json\`
- Errores de AMBOT: \`%LOCALAPPDATA%\\ARCHMOBA\\AMBOT\\launch.log\`
- Dependencia: \`pygame-ce>=2.5.7\`. Compatible con Python 3.14 en Windows.

Los sensores y movimientos son **simulados**; no controla hardware real.

## Habitación inicial

AMBOT comienza dentro de una **habitación 3D**, sin techo para que la cámara orbital permita verla. Tiene paredes, **puerta abierta** conectada al pasillo, cama, mesa con lámpara, silla, armario, alfombra y ventana. Los muebles ocupan espacio y bloquean el desplazamiento; la puerta se puede atravesar. Los muros cercanos a la cámara son bajos para mostrar el interior.

En el mapa de texto: `C` cama, `M` mesa, `S` silla, `A` armario, `P` puerta. Esto prepara el entorno físico para enseñar a AMBOT. **El reconocimiento y aprendizaje autónomo de los objetos aún no están implementados.**
