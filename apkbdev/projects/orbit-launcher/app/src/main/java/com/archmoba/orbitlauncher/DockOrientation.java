package com.archmoba.orbitlauncher;

/**
 * Correccion geometrica del sensor (en ejes fisicos del dispositivo)
 * con respecto a la orientacion que Android ya dibuja en la pantalla.
 *
 * El sensor TYPE_GRAVITY y el acelerometro devuelven aproximadamente
 * (0,+9.81) en un movil vertical, con el borde superior apuntando arriba.
 * Display.getRotation() vale 0, 1, 2 o 3 (ROTATION_0, 90, 180, 270).
 *
 * Este archivo no depende del SDK y puede verificarse con javac en CI.
 */
final class DockOrientation {
    static float normalize(float degrees) {
        while (degrees > 180f) degrees -= 360f;
        while (degrees < -180f) degrees += 360f;
        return degrees;
    }

    static float correctedAngle(float gravityX, float gravityY, int displayRotation) {
        // atan2(x, y) = 0 cuando se sostiene derecho; no hay calibracion subjetiva.
        float deviceAngle = (float) Math.toDegrees(Math.atan2(gravityX, gravityY));
        int rotation = ((displayRotation % 4) + 4) % 4;
        return normalize(deviceAngle - rotation * 90f);
    }

    private DockOrientation() {}
}
