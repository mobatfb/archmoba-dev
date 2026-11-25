# Sistema de Gestión Académica UNEDID

## Estructura lógica

Periodo académico anual
→ Aulas/Paralelos habilitados en ese periodo
→ Asignaturas reutilizadas del catálogo
→ Un docente responsable por asignatura/aula/periodo
→ Estudiantes matriculados en el aula del periodo
→ Calificaciones trimestrales y nota final anual

## Roles

- **Superadministrador**: global, administra catálogos, periodos, matrículas, asignaciones, reportes y certificaciones.
- **Docente**: rol con alcance al periodo. Solo puede gestionar las ofertas académicas donde figura como docente responsable.
- **Estudiante**: rol con alcance al periodo. Consulta las asignaturas del paralelo donde está matriculado y sus resultados.

Los usuarios pueden existir sin roles. La matrícula asigna automáticamente el rol estudiante del periodo y la asignación docente asigna automáticamente el rol docente del periodo.

## Módulos

1. Usuarios: creación individual y CSV masivo sin roles.
2. Periodos académicos: planificación, activación y cierre anual.
3. Aulas y paralelos: catálogo reutilizable.
4. Asignaturas: catálogo reutilizable.
5. Gestión académica: habilitación de aulas por periodo, matrículas, asignaturas y docente.
6. Calificaciones: matriz 70/30, AP por naturaleza, candados, tres trimestres, supletorio y reporte Excel.
7. Reportes globales: consolidado por paralelo y certificación PDF por estudiante.
8. Asistencia: registro por asignatura y fecha, disponible para superadministrador y docente según sus asignaciones.
9. Estudiante: consulta de resultados del periodo activo.

## Reglas de calificaciones conservadas

- AP activo vacío = 0.00 y participa.
- AP bloqueado = no utilizado y no participa.
- Si los tres AP de una naturaleza están bloqueados, la naturaleza vale 10.00.
- Ponderación por defecto: aportes 70%, evaluación sumativa 30%.
- Promedio anual = promedio truncado de los tres trimestres.
- Supletorio de acuerdo con la configuración del periodo.


## Módulo de asistencia

La asistencia se registra sobre una oferta académica, por lo que conserva el contexto completo de periodo, aula/paralelo, asignatura y docente. Cada sesión se identifica por oferta + fecha y almacena el tema/actividad y una observación general. Para cada matrícula se registra uno de cuatro estados: presente, ausente, atraso o justificado. El docente únicamente puede gestionar sus propias ofertas; el superadministrador tiene acceso global.

## Auditoría de actividades
La tabla `auditoria_actividades` conserva trazabilidad de acciones sensibles con actor, usuario afectado, acción, módulo, entidad, detalle, valores antes/después, resultado, criticidad, ruta HTTP, agente de usuario, huella de sesión e información de red. Los eventos masivos comparten `grupo_evento` para reconstruir una sola operación (por ejemplo, guardar las calificaciones de todo un paralelo).

El módulo `modulos/auditoria/` es de solo lectura y está restringido al Superadministrador. No se exponen operaciones de edición o borrado de registros de auditoría.

## Módulo de votaciones

El proceso electoral es anual y está ligado a `periodos_academicos`. `elecciones.periodo_id` es único, por lo que no puede existir más de una elección en un mismo periodo. La elección se configura primero, se activa una sola vez y luego se cierra.

La población electoral se deriva de las matrículas activas, sin importar participantes externos. El superadministrador asigna cada `aula_periodo` a una sección electoral (`matutina` o `vespertina`) en `eleccion_aulas`. Los estudiantes de esas aulas quedan habilitados automáticamente.

Los candidatos se almacenan en `eleccion_candidatos` con nombre, fotografía, propuesta/slogan y sección. El estudiante accede con su cuenta institucional y solo ve candidatos de la sección correspondiente a su aula. `eleccion_votos` contiene una restricción única por `eleccion_id + estudiante_id`, garantizando un solo voto por estudiante y periodo.

La interfaz de administración incluye configuración, aulas/secciones, candidatos y resultados con exportación PDF. Las acciones administrativas y la participación electoral se integran con Auditoría; el detalle de auditoría registra que el estudiante participó, sin incluir el candidato seleccionado.


## Excel nominal electoral
- Solo Superadministrador.
- Exporta en un único XLSX la población habilitada del proceso electoral.
- Incluye sección, curso, cédula, nombres, estado VOTÓ/NO VOTÓ, candidato elegido y fecha/hora del voto.
- Respeta el filtro Todos/Matutina/Vespertina.
- La descarga se registra en Auditoría sin copiar allí el voto individual.


## Gestión CRUD y conservación de historial (v10)
Los módulos administrativos ofrecen edición, activación/desactivación y eliminación controlada. Los registros con historial académico se conservan mediante estados (inactivo, retirado, cerrado). La eliminación física solo se permite cuando no existen dependencias. Auditoría y votos emitidos permanecen inmutables.
