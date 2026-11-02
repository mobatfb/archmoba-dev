package com.archmoba.orbitlauncher;

/**
 * Reglas del consumo de recursos del sensor. Independiente del Android SDK
 * para poder probarlas con javac durante la compilacion automatica.
 */
final class DockMotionPolicy {
    /** Solicitar 1 lectura cada 60ms (~16.7Hz), en vez de SENSOR_DELAY_GAME. */
    static final int SENSOR_PERIOD_US = 60_000;

    /** Limitar los redibujados aunque el fabricante entregue eventos mas rapido. */
    static final long MIN_DRAW_INTERVAL_MS = 55L;

    /** Cambios menores son imperceptibles y no justifican repintar N iconos. */
    static final float MIN_VISUAL_DELTA_DEG = 1.25f;

    static boolean shouldDraw(float previousAngle, float nextAngle, long sinceDrawMs) {
        return sinceDrawMs >= MIN_DRAW_INTERVAL_MS
                && Math.abs(DockOrientation.normalize(nextAngle - previousAngle))
                        >= MIN_VISUAL_DELTA_DEG;
    }

    private DockMotionPolicy() {}
}
