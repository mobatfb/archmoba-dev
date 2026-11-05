# AMBOT — ARCHMOBA Robotics

**AMBOT 0.5.0** es una aplicación de escritorio **Python**, no un sitio web.

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


### Modo automatico: observar y practicar

Al activar **ESPACIO / AUTO**, AMBOT comienza observando los pasos del
instructor ANDA. Cuando su confianza supera un umbral inicial, ensaya
movimientos. Tras observar agarres de DEX, intenta manipular y transportar
objetos cercanos de forma autonoma y luego soltarlos. Tambien puede probar
a recostarse cuando esta junto a la cama y ya ha visto demostraciones
suficientes. Cada ensayo puede fallar; las consecuencias y el progreso
quedan guardados. Las rutinas de los guias permanecen independientes del
cerebro del bebe.


## v0.5.0 - Cerebro autonomo en el PC (Python)

**AMBOT inicia su aprendizaje automaticamente al abrir la ventana.** No
espera una orden para observar, intentar movimientos, investigar formas,
contar objetos o preguntarse por lo desconocido. ESPACIO pausa/reanuda.
Los tres robots guia siguen activos, pero el bebe elige experiencias
mediante un criterio simple de curiosidad y diversidad de ensayos.

- **Percepcion:** distancias, formas de objetos cercanos y consecuencias
  basicas de movimientos, contacto y equilibrio.
- **Memoria:** experiencias recientes, asociaciones de palabras,
  modelos de resultados de acciones y preguntas, con persistencia en
  \`%LOCALAPPDATA%\ARCHMOBA\AMBOT\cerebro.json\`.
- **Curiosidad:** elige acciones poco exploradas y plantea preguntas
  sin recibir instrucciones; tambien escucha las demostraciones.
- **Lenguaje/lectura inicial:** observa texto proporcionado por el usuario
  o los guias, detecta palabras y asociaciones frecuentes. Esto **no**
  constituye comprension general, lectura audiovisual ni habla real.
- **Matematica inicial:** distingue grupos visibles por forma y registra
  ejemplos observados de cantidades, como 2+1=3. No generaliza
  automaticamente toda la aritmetica.
- **Conversacion:** permite que una persona responda preguntas y aporte
  ejemplos de materias no previstas, como astronomia o biologia.
  Las explicaciones son aportes del interlocutor, no hechos verificados.
- **Experiencia:** registra si las acciones cambiaron el estado percibido,
  para orientar futuras exploraciones. Los movimientos y la fisica siguen
  siendo una simulacion simplificada.

### Comandos del cerebro

| Comando | Accion |
|---|---|
| \`cerebro\` | Resumen de experiencias, conceptos y preguntas |
| \`pregunta\` | Ver una pregunta que AMBOT genero por su cuenta |
| \`responde [explicacion]\` | Contestar la pregunta pendiente |
| \`leer [texto]\` | Presentar material escrito para observar |
| \`ensename [texto]\` | Aportar un ejemplo, de cualquier materia |
| \`contar\` o \`matematicas\` | Comparar grupos de objetos visibles |
| \`curiosidad\` | Provocar otro ensayo autonomo |

### Entrenamiento autonomo sin ventana

\`python AMBOT/app.py --train-steps 1000 --no-install\`

Ejecuta 1.000 pasos de simulacion sin abrir una ventana y guarda
lo aprendido. **No se ejecuta si el programa esta cerrado**: para
practicar de forma continua, el proceso de Python debe permanecer activo.

## Puente Arduino fisico, preparado para conexion USB

El **cerebro y las memorias permanecen en \`AMBOT/app.py\` en el PC**.
El Arduino actuaria como un controlador de motores y sensores.
La conexion serie USB usa **115200 baudios** y el paquete \`pyserial\`,
que se instala en una carpeta privada cuando el usuario pide conectar
una placa si no esta disponible.

| Comando | Accion |
|---|---|
| \`arduino puertos\` | Ver puertos disponibles |
| \`arduino conectar COM4\` | Conectar por USB (cambiar COM4) |
| \`arduino estado\` | Consultar estado y sensores |
| \`arduino habilitar\` | Solicitar permiso de movimiento fisico |
| \`arduino bloquear\` | Orden de parada de emergencia por serie |
| \`arduino desconectar\` | Bloquear y desconectar |

**Seguridad:** los motores estan bloqueados por defecto. Incluso tras
conectar la placa, el cerebro requiere habilitacion explicita y
telemetria valida y reciente (distancia >=25 cm, bateria >=20%).
Los comandos motores estan acotados a potencia <=35% y pulsos
<=120 ms; las perdidas de telemetria causan bloqueo. La parada por
serie **no sustituye** un interruptor de emergencia cableado.

El boceto de Arduino
\`AMBOT/arduino/AMBOT_Puente_Seguro.ino\` admite USB, PING y STOP,
pero **no acciona ningun motor**: reporta valores de sensores -1,
ya que los pines y los dispositivos fisicos todavia no estan definidos.
Por tanto, no permite el movimiento fisico hasta adaptar
controladores, sensores, bateria, frenos, watchdog y un boton de
parada al hardware real. Nunca sustituir lecturas reales por
valores inventados para habilitar movimientos.

**Alcance real:** aprendizaje incremental basado en reglas
de exploracion y asociacion, no una inteligencia artificial general
ni un modelo multimodal entrenado desde cero. Para aprender lenguaje,
matematica avanzada, imagenes de camara, voz o manipulacion fisica
real se necesitaran mecanismos y entrenamientos adicionales.
