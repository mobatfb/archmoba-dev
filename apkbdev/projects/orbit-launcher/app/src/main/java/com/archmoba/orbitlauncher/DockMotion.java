package com.archmoba.orbitlauncher;

import android.content.Context;
import android.hardware.Sensor;
import android.hardware.SensorEvent;
import android.hardware.SensorEventListener;
import android.hardware.SensorManager;
import android.os.PowerManager;
import android.os.SystemClock;
import android.view.View;
import android.view.WindowManager;
import java.util.ArrayList;
import java.util.List;

/**
 * Giro fluido de los iconos con gestion de bateria.
 * No cambia su posicion, forma, opacidad ni su interaccion.
 *
 * - 60ms entre lecturas solicitadas (~16Hz; el fabricante puede variar).
 * - Sin redibujar si la rotacion visual es menor que 1.25 grados.
 * - Sin dibujar mas de una vez cada 55ms.
 * - Sin sensor cuando la pantalla esta apagada o no quedan iconos.
 * - El boton "+" nunca forma parte de la lista de vistas que giran.
 */
final class DockMotion implements SensorEventListener {
    private static final float MIN_XY_SQUARED = 16f;
    private static final float DEAD_ZONE_DEGREES = 7f;
    private static final float SMOOTHING = 0.40f;
    private static final long ROTATION_SETTLE_MS = 250L;

    private final SensorManager sensorManager;
    private final Sensor gravitySensor;
    private final WindowManager windowManager;
    private final PowerManager powerManager;
    private final List<View> targets = new ArrayList<>();

    private boolean listening;
    private float displayedAngle;
    private int displayRotation = -1;
    private long lastRotationChangeMs;
    private long lastDrawMs;

    DockMotion(Context context) {
        sensorManager = (SensorManager) context.getSystemService(Context.SENSOR_SERVICE);
        windowManager = (WindowManager) context.getSystemService(Context.WINDOW_SERVICE);
        powerManager = (PowerManager) context.getSystemService(Context.POWER_SERVICE);

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
        resume();
    }

    /** Desactivar lectura al apagar la pantalla; conservar iconos para reanudar. */
    void pause() {
        if (listening && sensorManager != null) {
            sensorManager.unregisterListener(this);
        }
        listening = false;
    }

    /** Reanudar solo si la pantalla esta activa y hay iconos reales. */
    void resume() {
        if (listening || targets.isEmpty() || sensorManager == null
                || gravitySensor == null || !isScreenInteractive()) return;

        displayedAngle = 0f;
        displayRotation = currentDisplayRotation();
        lastRotationChangeMs = SystemClock.elapsedRealtime();
        lastDrawMs = lastRotationChangeMs;
        applyAngle(0f);
        listening = sensorManager.registerListener(this, gravitySensor,
                DockMotionPolicy.SENSOR_PERIOD_US);
    }

    void stop() {
        pause();
        targets.clear();
        displayedAngle = 0f;
        displayRotation = -1;
        lastRotationChangeMs = 0L;
        lastDrawMs = 0L;
    }

    private boolean isScreenInteractive() {
        return powerManager == null || powerManager.isInteractive();
    }

    private int currentDisplayRotation() {
        return windowManager == null ? 0 :
                windowManager.getDefaultDisplay().getRotation();
    }

    private void applyAngle(float angle) {
        for (View view : targets) {
            if (view != null) view.setRotation(angle);
        }
    }

    @Override public void onSensorChanged(SensorEvent event) {
        if (!listening || gravitySensor == null || targets.isEmpty() || event == null
                || event.sensor.getType() != gravitySensor.getType()) return;

        // Respaldo ante broadcasts perdidos o cambios de estado de pantalla.
        if (!isScreenInteractive()) {
            pause();
            return;
        }

        final long now = SystemClock.elapsedRealtime();
        final int nowRotation = currentDisplayRotation();
        if (nowRotation != displayRotation) {
            // Android ya giro la interfaz: no aplicar ese giro dos veces.
            displayRotation = nowRotation;
            displayedAngle = 0f;
            lastRotationChangeMs = now;
            lastDrawMs = now;
            applyAngle(0f);
            return;
        }

        // Saltar procesamientos y frames frecuentes. La tasa real del sensor
        // es indicativa, por eso limitamos adicionalmente la frecuencia visual.
        if (now - lastRotationChangeMs < ROTATION_SETTLE_MS
                || now - lastDrawMs < DockMotionPolicy.MIN_DRAW_INTERVAL_MS) return;

        final float x = event.values[0];
        final float y = event.values[1];

        if (x*x + y*y < MIN_XY_SQUARED) {
            // Movil casi horizontal: la direccion XY no es confiable.
            if (Math.abs(displayedAngle) > 0.01f) {
                displayedAngle = 0f;
                lastDrawMs = now;
                applyAngle(0f);
            }
            return;
        }

        float target = DockOrientation.correctedAngle(x, y, nowRotation);
        if (Math.abs(target) < DEAD_ZONE_DEGREES) target = 0f;

        float difference = DockOrientation.normalize(target - displayedAngle);
        // Si el telefono volvio a estar derecho, dejar exactamente 0 grados.
        if (target == 0f && Math.abs(difference) < 1.5f) {
            if (displayedAngle != 0f) {
                displayedAngle = 0f;
                lastDrawMs = now;
                applyAngle(0f);
            }
            return;
        }

        if (Math.abs(difference) < 1.5f) return;

        float next = DockOrientation.normalize(displayedAngle + difference * SMOOTHING);
        if (target == 0f && Math.abs(next) < 1.5f) next = 0f;

        if (!DockMotionPolicy.shouldDraw(displayedAngle, next, now - lastDrawMs))
            return;

        displayedAngle = next;
        lastDrawMs = now;
        applyAngle(next);
    }

    @Override public void onAccuracyChanged(Sensor sensor, int accuracy) {}
}
