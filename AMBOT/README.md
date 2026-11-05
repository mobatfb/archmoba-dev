# AMBOT — ARCHMOBA Robotics

**AMBOT 0.4.0** es una aplicación de escritorio **Python**, no un sitio web.

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

## Visor en primer plano y burbuja (v0.3.0)

La ventana ahora se divide en **tres columnas**: visor del stickman a la izquierda, habitación/mundo 3D en el centro y cerebro/controles a la derecha. El visor izquierdo usa una **segunda cámara del mismo modelo 3D** (no un sprite separado): refleja exactamente el ángulo, posición interpolada, fase de marcha y giro del cuerpo principal. Permanece enfocado en el personaje aunque este cambie de habitación.

Una **burbuja de conversación** sobre el visor muestra las respuestas a comandos, pensamientos y mensajes de exploración autónoma. Al moverse, girar, reiniciarse o detenerse, el avatar permanece sincronizado con el escenario central. Los sensores y el pensamiento siguen siendo simulados; no hay voz sintetizada ni un modelo de lenguaje externo en esta versión.


## AMBOT bebe y tres robots guia (v0.4.0)

AMBOT aparece como **aprendiz sin habilidades dominadas**. En la habitacion hay **tres
robots instructores** con diferentes colores y rutinas programadas:

- **ANDA** (verde): muestra pasos, marcha y equilibrio.
- **DEX** (naranja): senala, nombra, agarra, transporta y suelta objetos.
- **SOMA** (morado): se acerca a la cama, se acuesta, descansa y se levanta.

Los instructores repiten sus demostraciones. El bebe **observa** acciones a
distancia limitada (sensor simulado), acumula experiencias y **practica** sin
reproducir automaticamente las rutinas de los guias. Las probabilidades de
exito cambian con los ensayos y la experiencia observacional.

### Controles de entrenamiento

- **1 / 2 / 3**: atender a ANDA, DEX o SOMA.
- **Q**: observar al instructor seleccionado.
- **F**: intentar sujetar un objeto cercano.
- **V**: soltar lo que lleve en las manos (cae).
- **L**: intentar acostarse en la cama cercana.
- **I**: intentar identificar un objeto observado.
- **P**: consultar los progresos aprendidos.
- **W/A/S/D**: experimentar con el desplazamiento, el equilibrio
  y el empuje de objetos.

Los 3 objetos moviles son **cubo, pelota y bloque**. Se simulan empuje,
sujecion, gravedad, rebote y friccion, asi como caidas, agarres fallidos y
recuperacion del equilibrio. Los guias conocen previamente las demostraciones;
AMBOT necesita escuchar repetidas veces sus palabras para asociarlas con
los objetos. Sus habilidades y etiquetas aprendidas se conservan en:

\`%LOCALAPPDATA%\\ARCHMOBA\\AMBOT\\aprendizaje.json\`

Al reiniciar el cuerpo (R), los conocimientos adquiridos **no se borran**.

La escena muestra **cuatro robots**: tres instructores y el bebe. La camara
izquierda sigue solamente a este ultimo, pero refleja sus mismas posturas
y movimientos. El panel central muestra guias, objetos y progreso.

**Alcance:** motor de aprendizaje **simulado** con refuerzo probabilistico,
no aprendizaje neuronal por imagen ni una inteligencia general. Los guias
estan programados y la fisica es simplificada; el bebe aprende valores de
confianza y asociaciones, no destrezas roboticas transferibles a hardware.
No requiere navegador ni servicio HTTP.
