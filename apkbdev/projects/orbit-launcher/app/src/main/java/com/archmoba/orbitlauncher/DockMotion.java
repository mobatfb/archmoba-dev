package com.archmoba.orbitlauncher;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.view.View;
import java.util.ArrayList;
import java.util.List;

/**
 * Movimiento continuo y ligero usando gravedad o acelerometro.
 * Compensa la inclinacion del telefono sin rotar toda la columna.
 * En giro de pantalla Android, DockService reconstruye el dock y se recalibra.
 */
final class DockMotion implements SensorEventListener {
    private final SensorManager manager;
    private final Sensor sensor;
    private final List<View> targets = new ArrayList<>();
    private boolean listening;
    private boolean calibrated;
    private float baselineAngle;
    private float displayedAngle;

    DockMotion(Context context) {
        manager = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        Sensor preferred = null;
        if (manager != null) {
            preferred = manager.getDefaultSensor(Sensor.TYPE_GRAVITY);
            if (preferred == null) {
                preferred = manager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
            }
        }
        sensor = preferred;
    }

    void start(List<View> views) {
        stop();
        targets.addAll(views);
        if (sensor != null && manager != null) {
            listening = manager.registerListener(this, sensor,
                    SensorManager.SENSOR_DELAY_GAME);
        }
    }

    void stop() {
        if (listening && manager != null) manager.unregisterListener(this);
        listening = false;
        calibrated = false;
        displayedAngle = 0f;
        targets.clear();
    }

    private static float shortest(float angle) {
        while (angle > 180f) angle -= 360f;
        while (angle < -180f) angle += 360f;
        return angle;
    }

    @Override public void onSensorChanged(SensorEvent event) {
        if (!listening || targets.isEmpty() || event.sensor.getType() != sensor.getType())
            return;
        float x = event.values[0], y = event.values[1];
        // Cerca de la posicion horizontal no hay direccion gravitacional fiable en XY.
        if (x * x + y * y < 12f) return;
        float angle = (float) Math.toDegrees(Math.atan2(-x, y));
        if (!calibrated) {
            baselineAngle = angle;
            calibrated = true;
            return;
        }
        // Giro inverso suave: los logos responden en tiempo real a la inclinacion.
        float target = shortest(baselineAngle - angle);
        float difference = shortest(target - displayedAngle);
        if (Math.abs(difference) < 0.5f) return;
        displayedAngle = shortest(displayedAngle + difference * 0.32f);
        for (View view : targets) view.setRotation(displayedAngle);
    }

    @Override public void onAccuracyChanged(Sensor sensor, int accuracy) {}
}
