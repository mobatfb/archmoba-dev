-- SGA UNEDID: marca de resultados cualitativos por aula.
-- Compatible con MariaDB 10.6 (servidor reportado por el proyecto).
-- Seguro para ejecutar mas de una vez; conserva todas las aulas existentes.
ALTER TABLE `aulas`
    ADD COLUMN IF NOT EXISTS `resultados_cualitativos` TINYINT(1) NOT NULL DEFAULT 0 AFTER `orden`;
