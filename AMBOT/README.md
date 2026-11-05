# AMBOT — ARCHMOBA Robotics

**AMBOT 0.9.0** es una aplicación de escritorio **Python**, no un sitio web.

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


## v0.6.0 - Boton AÑADIR sillas y elegir su ubicacion en 3D

El entorno inicia con **tres sillas adicionales** (clasica, de oficina
y alta), ademas de la silla existente junto a la mesa.

Para agregar otras, abrir AMBOT y:

1. Pulsar **+ AÑADIR** en la esquina superior derecha del escenario 3D.
2. En el panel izquierdo, seleccionar **SILLA CLASICA**, **SILLA DE OFICINA** o **SILLA ALTA**.
3. Si se desea, usar **GIRAR 90°** para orientar el respaldo.
4. Mover el raton sobre el suelo: **verde** significa ubicacion libre y
   **rosa** significa ubicacion prohibida.
5. Hacer **clic en el suelo 3D** para colocar tantas sillas como se desee
   (hasta 30 adicionales), o usar **DESHACER** para quitar la ultima.
6. Pulsar **LISTO** o **ESC** para salir del editor y reanudar el
   aprendizaje autonomo si estaba activo antes.

**Solo se pueden agregar sillas** en esta version. La ubicacion se elige
visual y directamente sobre el escenario: no hace falta editar codigo.

El robot no podra cruzar las sillas nuevas, y el editor evita colocar
sillas en paredes, objetos, robots, muebles fijos, junto al punto de
inicio, en la puerta o cuando corten la salida del cuarto.
El modo de colocacion **pausa la autonomia y bloquea Arduino** para
no mover el cuerpo fisico mientras se modifica el escenario.

Las sillas se guardan automaticamente en
\`%LOCALAPPDATA%\ARCHMOBA\AMBOT\muebles.json\`. Se recuperan al reiniciar
la aplicacion, incluso al presionar **REINICIAR** (no borra el mobiliario).
La memoria y el cerebro continuan en sus archivos independientes.

Comandos opcionales: \`sillas\` consulta cuantas sillas se han anadido y
\`deshacer silla\` quita la ultima colocada.


## v0.7.0 - QUITAR cualquier objeto del entorno

El editor de AMBOT ahora tiene botones **+ AÑADIR** y **− QUITAR**.
Pulsar **− QUITAR** pausa temporalmente el aprendizaje y abre el
selector de objetos. **Haz clic directamente en el objeto 3D** para
eliminarlo; el contorno rosa muestra el objetivo. Tambien se puede
alternar entre **AÑADIR** y **QUITAR** dentro del panel izquierdo.

Se pueden quitar y restaurar:

- **Sillas adicionales** (clasica, de oficina o alta).
- **Muebles originales:** cama, mesa, silla inicial y armario.
- **Objetos de practica:** cubo, pelota y bloque.
- **Decoraciones:** ventana y alfombra.

El **suelo, las paredes, la puerta y los cuatro robots** no se pueden
eliminar. Para impedir errores, el programa ignora pulsaciones fuera
de un objeto seleccionable e indica los robots protegidos.

**DESHACER** revierte la ultima accion realizada (anadir o quitar).
Las modificaciones y las ultimas 24 acciones deshacibles se guardan
en \`%LOCALAPPDATA%\ARCHMOBA\AMBOT\muebles.json\`, junto con las sillas.
El formato anterior de ese archivo sigue siendo compatible.

**LISTO** cierra el editor y reanuda el aprendizaje autonomo si estaba
activo. Mientras se edita, Arduino permanece bloqueado. El cerebro
sigue conservando sus experiencias en archivos separados.

Nota: eliminar la cama deshabilita los intentos de AMBOT de
recostarse sobre ella; se puede recuperar con **DESHACER**.


## v0.8.0 - Mi personaje, maestros editables, mas objetos y chat validado

### Mi personaje y articulaciones

AMBOT muestra un **avatar humanoide adicional** identificado como **TÚ**,
separado de AMBOT bebe. Las **flechas del teclado** mueven al usuario
(Arriba/Norte, Abajo/Sur, Izquierda/Oeste, Derecha/Este). **WASD**
continua controlando a AMBOT manualmente y no cancela su autonomia.

Abrir el boton **MI CUERPO / PANEL** para ver las articulaciones de
**cabeza, torso, dos brazos, dos codos, dos piernas y dos rodillas**.
Selecciona la articulacion y usa **+10°** o **-10°**. Incluye posturas
**SENTARSE**, **LEVANTARSE**, **SALUDAR**, **AGACHARSE** y
**RESTAURAR POSTURA**. Para sentarte, acercate primero a una silla
existente. No puedes caminar sentado ni atravesar muebles/robots.
Tu posicion y posturas se guardan en
\`%LOCALAPPDATA%\ARCHMOBA\AMBOT\avatar.json\`.

### Añadir mas objetos al escenario

El boton **+ AÑADIR** incluye ahora tres pestañas:

- **SILLAS:** clasica, de oficina o alta.
- **MUEBLES:** cama, mesa y armario.
- **OBJETOS:** cubo, pelota y bloque.

Selecciona el modelo y haz clic en una casilla libre del suelo 3D.
Las camas ocupan dos casillas en la orientacion elegida. Puedes
añadir multiples objetos del mismo tipo; los nuevos cubos, pelotas
y bloques participan en la fisica y observacion de AMBOT.
Las ubicaciones se guardan en \`muebles.json\` y admiten
**QUITAR** y **DESHACER**.

### Quitar a los robots maestros

Con **− QUITAR**, puedes retirar individualmente a
**ANDA, DEX y SOMA**, y recuperarlos con **DESHACER**.
AMBOT sigue investigando cuando no queda ninguno.
Los maestros desaparecidos siguen ausentes al reiniciar, pero
no borran ni alteran las experiencias que AMBOT ha guardado.
Ni AMBOT ni el avatar humano pueden eliminarse.

### Escribir frases, validar y corregir

La caja de chat permite enviar una frase nueva. AMBOT intentara
interpretarla y pedira **¿ENTENDI BIEN?**. El usuario puede:

- **SI** para confirmar y aprender el significado.
- **NO** para rechazar sin guardar la interpretacion.
- **CORREGIR** y escribir \`corrige sentarme\`, \`corrige dato\`,
  \`corrige observar\`, \`corrige contar\`, etc., para indicar
  que quiso decir realmente.

Las frases confirmadas se recuerdan y al repetirse utilizan
la interpretacion validada sin tener que enseñarla de nuevo.
Tambien se pueden guardar declaraciones y preguntas; las
explicaciones se pueden facilitar mediante \`responde ...\`.
La memoria de asociaciones validadas esta en
\`%LOCALAPPDATA%\ARCHMOBA\AMBOT\validaciones.json\` y los conceptos
aprendidos permanecen en \`cerebro.json\`.

**Alcance:** es aprendizaje supervisado de frases e intenciones
admitidas, con memoria y correcciones del usuario. No es
comprension universal del lenguaje natural, ni valida la veracidad
externa de lo enseñado.

### Seguridad y compatibilidad

El editor pausa el movimiento autonomo y bloquea Arduino hasta
cerrarlo. Conservar los archivos JSON de versiones anteriores.
La ventana y el cerebro se ejecutan enteramente en el mismo
programa Python de PC; Arduino sigue siendo opcional.


**Observar al usuario:** AMBOT registra las acciones del avatar
(movimiento, articulaciones, sentarse y posturas) como experiencias
corporales en \`cerebro.json\`. Al verte caminar recibe una señal
basica para practicar; si te ve sentarte puede formularte una
pregunta. Este mecanismo es una primera simulacion de observacion,
**no significa que sepa copiar cualquier movimiento articulado**.


## v0.9.0 - Movimiento tipo tanque al estilo Resident Evil 1 (PC)

Los controles son **relativos a la direccion que mira cada personaje**,
y no a la camara. Se puede mantener pulsada la tecla para repetir el
movimiento con una cadencia controlada. **No existe movimiento lateral
(strafe)**: a izquierda y derecha se gira sobre el propio eje.

| Accion | Tu avatar | AMBOT bebe |
|---|---|---|
| Avanzar hacia donde mira | Flecha **ARRIBA** | **W** |
| Retroceder sin cambiar su mirada | Flecha **ABAJO** | **S** |
| Girar en su sitio a la izquierda | Flecha **IZQUIERDA** | **A** |
| Girar en su sitio a la derecha | Flecha **DERECHA** | **D** |

El giro es de 90 grados por pulsacion, con **interpolacion visual** de
la orientacion al estilo tanque. Mientras la tecla se mantenga presionada,
los giros y pasos se repiten automaticamente. El desplazamiento sigue
empleando las casillas y colisiones del simulador (en lugar de una fisica
de animacion libre o de motor de juego AAA). La camara gira con el raton
independientemente del cuerpo. El modo de editor y la caja de chat
desactivan los controles sostenidos para evitar movimientos accidentales.

**ANDA, DEX y SOMA** tambien han cambiado su mecanica de locomocion:
antes de ir a cada destino, giran sin avanzar hasta orientarse; despues
caminan de frente por tramos en los ejes X/Z. No se deslizan lateralmente
ni interpolan en diagonal. Sus demostraciones siguen siendo automaticas
y se pueden eliminar/restaurar desde el editor.

Sigue funcionando la autonomia del bebe, su memoria y el puente Arduino
con bloqueo fisico por defecto. Los controles de tanque en esta version
son una simulacion en el PC; no habilitan los motores reales.
