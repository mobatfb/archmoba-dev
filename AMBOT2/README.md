# AMBOT 2.0 — Maestro humano y robot aprendiz

Nueva implementación independiente en Python, Panda3D y Bullet. No usa
Tkinter, navegador, servidor ni las rutinas de los tres instructores
de la versión anterior.

## Ejecutar en Windows

Abrir INICIAR_AMBOT2.bat o escribir:

    python AMBOT2/app.py

Si Panda3D no está instalado, app.py intentará instalarlo en su propio
directorio de dependencias. Alternativamente:

    python -m pip install -r AMBOT2/requirements.txt

Los datos persistentes están en:

    %LOCALAPPDATA%\ARCHMOBA\AMBOT2

## Controles

| Tecla | Acción |
| --- | --- |
| WASD / flechas | Caminar con el MAESTRO |
| Ratón derecho + mover | Rotar cámara |
| Rueda de ratón | Zoom |
| Clic sobre objeto | Seleccionar |
| 1 y 2 | Elegir mano izquierda / derecha |
| [ y ] | Cambiar dedo seleccionado |
| Q / E | Flexionar / extender dedo |
| R / F | Cerrar / abrir toda la mano |
| Z / X | Retraer / extender brazos |
| C / V | Bajar / elevar manos |
| T / G | Intentar agarrar / soltar |
| 3 / 4 | Cerrar / abrir ambas manos |
| B / N | Intentar agarre simultáneo / soltar ambas |
| 5, 6, 7, 8 | Crear cubo, pelota, cuadro o caja |
| O / P | Iniciar / finalizar demostración |
| H | Intentar habilidad observada |

Los dos humanoides tienen 5 dedos por mano. El MAESTRO es manejado por el
usuario; AMBOT es aprendiz, sin guías automáticos.

## Agarre físico y objetos

La simulación incluye objetos físicos dinámicos, masa, gravedad, fricción,
rebote y colisiones mediante Bullet. Cada una de las 10 yemas del maestro
es un sensor cinemático de Bullet. Para sujetar un objeto se necesitan
contactos reales de un pulgar y al menos dos dedos flexionados. Al
confirmarse se añade una restricción Bullet entre palma y cuerpo rígido.
Una mano puede sujetar objetos pequeños; un cuadro puede sujetarse con
ambas manos y con dos restricciones. Abrir los dedos libera el soporte.

Para sostener un cuadro con ambas manos, aproxima cada palma al borde,
flexiona dedos hasta tocar la superficie y utiliza T, primero para una
mano, luego para la otra. Si no hay contactos suficientes no se concede
el agarre; NO se pega el objeto mágicamente al avatar. La capacidad de
carga es limitada y debe distribuirse entre las manos.

Los brazos y dedos visibles aún se controlan de forma cinemática; no son
articulaciones dinámicas con músculos o motores Bullet. Este prototipo
ofrece contacto físico y restricciones, pero no precisión biomecánica
total, equilibrio humanoide ni agarre universal garantizado.

## Editor de objetos

Desde el panel lateral o campo de instrucciones:

    agregar cubo
    agregar pelota
    agregar cuadro
    agregar caja
    agregar tabla
    agregar cama
    agregar mesa
    mover 0 3 1.2
    nombre Mi cuadro
    borrar
    guardar
    cargar

Todos los objetos añadidos son potencialmente sujetables bajo
condiciones físicas; el suelo permanece inmóvil. La escena se guarda
en JSON. La importación de modelos externos queda para otra fase.

## Aprendizaje por demostración

    enseñar cerrar mano
    [mover los dedos del maestro]
    fin
    practicar cerrar mano
    bien

AMBOT registra deltas motores de demostraciones observadas, construye
una política incremental y ensaya con su cuerpo propio. No reproduce
animaciones fijas del maestro. La corrección bien/mal aumenta o reduce
la confianza en los ensayos. Es aprendizaje motor básico, no comprensión
visual general ni inteligencia neuronal equivalente a un ser humano.

## Lenguaje y preguntas

Selecciona un objeto y escribe:

    esto es un cuadro
    ¿qué es esto?
    yo
    tú
    nosotros
    vosotros
    ustedes

El sistema relaciona palabras con objetos seleccionados y resuelve
pronombres por el hablante, no como identidades fijas. Si no comprende,
pregunta. No posee un diccionario completo ni comprensión ilimitada.

## Pruebas

    python -m unittest discover -s AMBOT2/tests -p "test_*.py" -v
    python AMBOT2/app.py --smoke-test

Se comprueba cuerpo, 10 dedos, sensores, restricciones físicas,
persistencia de escenas y memorias, aprendizaje, pronombres y arranque
Panda3D sin monitor en Windows/Linux.

## Próximos hitos

- Ajustar interacción con cuadro grande y agarre a dos manos.
- Control articulado físico de hombros, muñecas, dedos y equilibrio.
- Editor visual de dimensiones, transformaciones e importación 3D.
- Aprendizaje sensoriomotor sobre observaciones, sin acceso a IDs.
- Diálogo de mayor cobertura y entrada/salida por voz.

Se comprueba además el agarre simultáneo de un cuadro con dos restricciones Bullet independientes y la liberación de una sola mano.

El cierre espontáneo de los dedos, si forma contacto de pinza válido, activa el agarre sin necesidad de pulsar T. El botón sigue siendo una alternativa.
