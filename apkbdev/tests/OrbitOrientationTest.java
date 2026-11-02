package com.archmoba.orbitlauncher;

/** Pruebas de sincronizacion de sensor con pantalla, ejecutadas con javac. */
public final class OrbitOrientationTest {
    private static int checks = 0;

    private static void check(String name, float actual, float expected) {
        checks++;
        if (Math.abs(DockOrientation.normalize(actual - expected)) > 0.2f) {
            throw new AssertionError(name + ": esperaba " + expected
                    + " grados, obtenido " + actual);
        }
    }

    private static void checkCondition(String name, boolean actual, boolean expected) {
        checks++;
        if (actual != expected) throw new AssertionError(name
                + ": esperaba " + expected + " obtenido " + actual);
    }

    public static void main(String[] args) {
        // Telefono vertical normal: jamas girar el icono 90 o 180 grados.
        check("vertical natural", DockOrientation.correctedAngle(0f, 9.81f, 0), 0f);
        // Android ha rotado toda la pantalla 90 / 180 / 270 grados.
        check("horizontal izquierda", DockOrientation.correctedAngle(9.81f, 0f, 1), 0f);
        check("cabeza abajo", DockOrientation.correctedAngle(0f, -9.81f, 2), 0f);
        check("horizontal derecha", DockOrientation.correctedAngle(-9.81f, 0f, 3), 0f);
        // Si la pantalla NO gira (bloqueo de rotacion), el icono si compensa la gravedad.
        check("giro fisico sin autorrotacion +90",
                DockOrientation.correctedAngle(9.81f, 0f, 0), 90f);
        check("giro fisico sin autorrotacion -90",
                DockOrientation.correctedAngle(-9.81f, 0f, 0), -90f);
        check("inclinacion positiva de 30",
                DockOrientation.correctedAngle(4.905f, 8.496f, 0), 30f);
        check("inclinacion negativa de 30",
                DockOrientation.correctedAngle(-4.905f, 8.496f, 0), -30f);
        check("cruce de -360 a 0", DockOrientation.normalize(-360f), 0f);
        check("cruce de +360 a 0", DockOrientation.normalize(360f), 0f);
        // Reglas de ahorro: evitar dibujar cuando no hay cambio visible,
        // cuando llega el sensor demasiado rapido o si el angulo cruza 360.
        checkCondition("sin cambio no dibuja", DockMotionPolicy.shouldDraw(0f, 0f, 100L), false);
        checkCondition("microtemblor no dibuja", DockMotionPolicy.shouldDraw(0f, 0.7f, 100L), false);
        checkCondition("frame demasiado frecuente", DockMotionPolicy.shouldDraw(0f, 30f, 20L), false);
        checkCondition("movimiento suficiente", DockMotionPolicy.shouldDraw(0f, 15f, 60L), true);
        checkCondition("normalizacion 360", DockMotionPolicy.shouldDraw(179f, -179f, 60L), true);
        checkCondition("salto de un grado no dibuja", DockMotionPolicy.shouldDraw(180f, 179f, 60L), false);
        checkCondition("tasa solicitada prudente", DockMotionPolicy.SENSOR_PERIOD_US >= 50_000, true);
        System.out.println("OK: " + checks + " pruebas de orientacion y energia aprobadas");
    }
}
