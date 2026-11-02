package com.archmoba.orbitlauncher;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.SystemClock;
import android.view.View;
import android.view.WindowManager;
import java.util.ArrayList;
import java.util.List;

/**
 * Mantiene cada acceso alineado con la orientacion visible de Android.
 * La gravedad es absoluta; NO tomamos la primera lectura como "vertical".
 * De esa manera, una app que arranca con el movil girado no se queda al reves.
 */
final class DockMotion implements SensorEventListener {
    private static final float MIN_XY_SQUARED = 16f;
    private static final float DEAD_ZONE_DEGREES = 7f;
    private static final float SMOOTHING = 0.40f;
    private static final long ROTATION_SETTLE_MS = 250;

    private final SensorManager sensorManager;
    private final Sensor gravitySensor;
    private final WindowManager windowManager;
    private final List<View> targets = new ArrayList<>();

    private boolean listening;
    private float displayedAngle = 0f;
    private int displayRotation = -1;
    private long lastRotationChangeMs = 0L;

    DockMotion(Context context) {
        sensorManager = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        windowManager = (WindowManager) context.getSystemService(Context.WINDOW_SERVICE);
        Sensor found = null;
        if (sensorManager != null) {
            found = sensorManager.getDefaultSensor(Sensor.TYPE_GRAVITY);
            if (found == null) {
                found = sensorManager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER);
            }
        }
        gravitySensor = found;
    }

    void start(List<View> views) {
        stop();
        targets.addAll(views);
        displayedAngle = 0f;
        displayRotation = currentDisplayRotation();
        // Se inicia derecho de inmediato, antes de la primera lectura.
        applyAngle(0f);
        if (sensorManager != null && gravitySensor != null) {
            listening = sensorManager.registerListener(
                    this, gravitySensor, SensorManager.SENSOR_DELAY_GAME);
        }
    }

    void stop() {
        if (listening && sensorManager != null) {
            sensorManager.unregisterListener(this);
        }
        listening = false;
        targets.clear();
        displayedAngle = 0f;
        displayRotation = -1;
        lastRotationChangeMs = 0L;
    }

    private int currentDisplayRotation() {
        if (windowManager == null) return 0;
        return windowManager.getDefaultDisplay().getRotation();
    }

    private void applyAngle(float value) {
        for (View view : targets) {
            if (view != null) view.setRotation(value);
        }
    }

    @Override public void onSensorChanged(SensorEvent event) {
        if (!listening || gravitySensor == null || targets.isEmpty() || event == null
                || event.sensor.getType() != gravitySensor.getType()) return;

        int nowRotation = currentDisplayRotation();
        if (nowRotation != displayRotation) {
            // Android acaba de rotar su interfaz: no repetir ese giro en los iconos.
            displayRotation = nowRotation;
            displayedAngle = 0f;
            lastRotationChangeMs = SystemClock.elapsedRealtime();
            applyAngle(0f);
            return;
        }

        if (SystemClock.elapsedRealtime() - lastRotationChangeMs
                < ROTATION_SETTLE_MS) return;

        float x = event.values[0], y = event.values[1];
        if (x * x + y * y < MIN_XY_SQUARED) {
            // Telefonos apoyados casi planos: no forzar giros de datos ambiguos.
            if (Math.abs(displayedAngle) > 0.1f) {
                displayedAngle = 0f;
                applyAngle(0f);
            }
            return;
        }

        float target = DockOrientation.correctedAngle(x, y, nowRotation);
        // "Telefono derecho" = iconos 100% derechos, sin vibracion +/- 1 grado.
        if (Math.abs(target) < DEAD_ZONE_DEGREES) target = 0f;

        float difference = DockOrientation.normalize(target - displayedAngle);
        if (Math.abs(difference) < 0.4f) {
            if (target == 0f && displayedAngle != 0f) {
                displayedAngle = 0f;
                applyAngle(0f);
            }
            return;
        }

        displayedAngle = DockOrientation.normalize(
                displayedAngle + difference * SMOOTHING);

        if (target == 0f && Math.abs(displayedAngle) <= 1.5f) {
            displayedAngle = 0f;
        }
        applyAngle(displayedAngle);
    }

    @Override public void onAccuracyChanged(Sensor sensor, int accuracy) {}
}
