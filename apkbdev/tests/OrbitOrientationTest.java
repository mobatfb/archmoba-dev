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
        System.out.println("OK: " + checks + " pruebas de orientacion aprobadas");
    }
}
