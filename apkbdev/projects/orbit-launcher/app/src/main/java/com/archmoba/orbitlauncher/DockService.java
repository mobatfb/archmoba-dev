package com.archmoba.orbitlauncher;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.IntentFilter;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.graphics.drawable.GradientDrawable;
import android.os.Build;
import android.os.IBinder;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.ImageView;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.HashMap;

/** Unico elemento permanente de Orbit: columna flotante en el borde derecho. */
public final class DockService extends Service {
    static final String ACTION_ADD = "com.archmoba.orbitlauncher.ADD";
    static final String ACTION_REMOVE = "com.archmoba.orbitlauncher.REMOVE";
    static final String ACTION_MANAGE = "com.archmoba.orbitlauncher.MANAGE";
    static final String ACTION_REFRESH = "com.archmoba.orbitlauncher.REFRESH";
    static final String ACTION_HIDE = "com.archmoba.orbitlauncher.HIDE";
    static final String ACTION_STOP = "com.archmoba.orbitlauncher.STOP";

    private WindowManager manager;
    private LinearLayout dock;
    private boolean stopped;
    private DockMotion motion;
    private boolean screenReceiverRegistered;
    private final Map<String, View> badgeViews = new HashMap<>();

    /**
     * Los broadcasts de pantalla NO se declaran en el manifest:
     * se escuchan dinamicamente durante la vida del servicio.
     */
    private final BroadcastReceiver screenStateReceiver = new BroadcastReceiver() {
        @Override public void onReceive(Context context, Intent intent) {
            if (intent == null) return;
            String action = intent.getAction();
            if (NotificationBadgeStore.ACTION_CHANGED.equals(action)) {
                refreshBadges();
                return;
            }
            if (motion == null) return;
            if (Intent.ACTION_SCREEN_OFF.equals(action)) {
                motion.pause();
            } else if (Intent.ACTION_SCREEN_ON.equals(action) && dock != null) {
                motion.resume();
            }
        }
    };

    @Override public void onCreate() {
        super.onCreate();
        manager = (WindowManager) getSystemService(WINDOW_SERVICE);
        motion = new DockMotion(this);

        IntentFilter screenEvents = new IntentFilter();
        screenEvents.addAction(Intent.ACTION_SCREEN_OFF);
        screenEvents.addAction(Intent.ACTION_SCREEN_ON);
        screenEvents.addAction(NotificationBadgeStore.ACTION_CHANGED);
        // Son broadcasts exclusivos del sistema; registro no exportado.
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(screenStateReceiver, screenEvents,
                    Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(screenStateReceiver, screenEvents);
        }
        screenReceiverRegistered = true;

        startNotification();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        String action = intent == null ? ACTION_REFRESH : intent.getAction();
        if (ACTION_STOP.equals(action)) {
            stopped = true;
            stopSelf();
            return START_NOT_STICKY;
        }
        if (Build.VERSION.SDK_INT >= 23
                && !android.provider.Settings.canDrawOverlays(this)) {
            stopSelf();
            return START_NOT_STICKY;
        }
        if (ACTION_HIDE.equals(action)) removeDock();
        else renderDock();
        return START_STICKY;
    }

    private void startNotification() {
        NotificationManager notifications = (NotificationManager)
                getSystemService(NOTIFICATION_SERVICE);
        if (Build.VERSION.SDK_INT >= 26) {
            notifications.createNotificationChannel(new NotificationChannel(
                    "orbit_right_dock", "Orbit Launcher flotante",
                    NotificationManager.IMPORTANCE_LOW));
        }
        Intent stop = new Intent(this, DockService.class).setAction(ACTION_STOP);
        PendingIntent stopAction = PendingIntent.getService(this, 123, stop,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Intent open = new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        PendingIntent openAction = PendingIntent.getActivity(this, 124, open,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(this, "orbit_right_dock")
                : new Notification.Builder(this);
        Notification notification = builder
                .setSmallIcon(android.R.drawable.ic_menu_add)
                .setContentTitle("Orbit Launcher")
                .setContentText("Accesos flotantes en el lado derecho")
                .setContentIntent(openAction)
                .addAction(android.R.drawable.ic_menu_close_clear_cancel,
                        "Cerrar", stopAction)
                .setOngoing(true)
                .build();
        startForeground(2001, notification);
    }

    private void renderDock() {
        removeDock();
        if (stopped) return;

        List<String> selected = AppStore.selected(this);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        // Sin fondo de barra: flotan solamente los iconos que el usuario eligio.
        root.setBackgroundColor(Color.TRANSPARENT);

        // Mantener el tamaño de los iconos, con menos separación para ver más.
        final int step = OrbitUtil.dp(this, 52);
        // Panel más pegado al borde derecho: iconos 48 dp en una columna de 50 dp.
        final int width = OrbitUtil.dp(this, 50);
        final List<View> rotateTargets = new ArrayList<>();
        LinearLayout icons = new LinearLayout(this);
        icons.setOrientation(LinearLayout.VERTICAL);
        icons.setGravity(Gravity.CENTER_HORIZONTAL);
        int visible = 0;
        for (String pkg : selected) {
            if (getPackageManager().getLaunchIntentForPackage(pkg) == null) continue;
            ImageView icon = new ImageView(this);
            try {
                icon.setImageDrawable(getPackageManager()
                        .getApplicationIcon(pkg));
            } catch (Exception ignored) {
                continue;
            }
            icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
            icon.setContentDescription(AppStore.label(this, pkg));
            int inset = OrbitUtil.dp(this, 8);
            icon.setPadding(inset, inset, inset, inset);
            icon.setBackground(OrbitUtil.bubble(this, false));
            // Recortar siempre el contenido de la imagen al contorno circular.
            icon.setClipToOutline(true);
            // Al 55% se atenúan juntos icono, fondo circular y borde.
            icon.setAlpha(0.55f);
            icon.setElevation(OrbitUtil.dp(this, 4));
            LinearLayout.LayoutParams item = new LinearLayout.LayoutParams(
                    OrbitUtil.dp(this, 48), OrbitUtil.dp(this, 48));
            item.setMargins(0, OrbitUtil.dp(this, 2), 0, OrbitUtil.dp(this, 2));
            // El punto verde queda fijo sobre el icono que responde al giro.
            FrameLayout wrapper = new FrameLayout(this);
            wrapper.addView(icon, new FrameLayout.LayoutParams(-1, -1));
            View dot = new View(this);
            GradientDrawable green = new GradientDrawable();
            green.setShape(GradientDrawable.OVAL);
            green.setColor(Color.rgb(28, 235, 66));
            green.setStroke(OrbitUtil.dp(this, 1.5f), Color.WHITE);
            dot.setBackground(green);
            dot.setElevation(OrbitUtil.dp(this, 5));
            dot.setVisibility(NotificationBadgeStore.pending(this, pkg)
                    ? View.VISIBLE : View.GONE);
            badgeViews.put(pkg, dot);
            FrameLayout.LayoutParams dotParams = new FrameLayout.LayoutParams(
                    OrbitUtil.dp(this, 13), OrbitUtil.dp(this, 13),
                    Gravity.RIGHT | Gravity.TOP);
            wrapper.addView(dot, dotParams);
            icons.addView(wrapper, item);
            rotateTargets.add(icon);
            wrapper.setOnClickListener(v -> {
                NotificationBadgeStore.acknowledge(this, pkg);
                OrbitUtil.launch(this, pkg);
            });
            wrapper.setOnLongClickListener(v -> {
                openPicker(ACTION_MANAGE, pkg);
                return true;
            });
            visible++;
        }

        if (visible > 0) {
            ScrollView scroll = new ScrollView(this);
            scroll.setFillViewport(false);
            scroll.setVerticalScrollBarEnabled(false);
            scroll.setOverScrollMode(View.OVER_SCROLL_NEVER);
            scroll.addView(icons);
            DisplayMetrics display = new DisplayMetrics();
            manager.getDefaultDisplay().getRealMetrics(display);
            DisplayMetrics usableDisplay = new DisplayMetrics();
            manager.getDefaultDisplay().getMetrics(usableDisplay);
            // Extender la columna en dos espacios de iconos respecto de v0.3.
            // Limitar su altura util para no cubrir barras de sistema ni perder "+".
            int desiredHeight = display.heightPixels - OrbitUtil.dp(this, 188)
                    + (2 * step);
            // Como el dock se desplaza 1 icono (52 dp) hacia arriba,
            // dejar margen suficiente para no recortar el primer icono ni el botón +.
            // Reservamos dos veces ese desplazamiento, más el alto del botón + y sus márgenes.
            int safeHeight = usableDisplay.heightPixels - (2 * step)
                    - OrbitUtil.dp(this, 78);
            int availableHeight = Math.max(step, Math.min(desiredHeight, safeHeight));
            int iconsHeight = Math.min(visible * step, availableHeight);
            root.addView(scroll, new LinearLayout.LayoutParams(width, iconsHeight));
        }

        // "+" solo cuando no hay ninguna app visible. Nunca rota.
        // Si hay iconos, "Añadir" queda dentro de su menu de pulsacion larga.
        if (visible == 0) {
            TextView plus = new TextView(this);
            plus.setText("+");
            plus.setTextColor(OrbitUtil.CYAN);
            plus.setTextSize(34);
            plus.setTypeface(null, 1);
            plus.setGravity(Gravity.CENTER);
            plus.setRotation(0f);
            plus.setContentDescription("Añadir aplicación");
            plus.setBackground(OrbitUtil.bubble(this, true));
            plus.setClipToOutline(true);
            // Incluye el simbolo "+" y su contenedor; mantiene el giro fijo.
            plus.setAlpha(0.55f);
            plus.setElevation(OrbitUtil.dp(this, 6));
            LinearLayout.LayoutParams plusParams = new LinearLayout.LayoutParams(
                    OrbitUtil.dp(this, 49), OrbitUtil.dp(this, 49));
            plusParams.setMargins(0, OrbitUtil.dp(this, 4),
                    0, OrbitUtil.dp(this, 4));
            root.addView(plus, plusParams);
            plus.setOnClickListener(v -> openPicker(ACTION_ADD, null));
        }

        WindowManager.LayoutParams params = new WindowManager.LayoutParams(
                width, WindowManager.LayoutParams.WRAP_CONTENT,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
                PixelFormat.TRANSLUCENT);
        params.gravity = Gravity.RIGHT | Gravity.CENTER_VERTICAL;
        // Posicion horizontal de v0.5: completamente visible junto al borde derecho.
        params.x = 0;
        params.y = -step; // Mantener el desplazamiento vertical de v0.5.
        try {
            manager.addView(root, params);
            dock = root;
            // Sin apps no se inicia el sensor, y el "+" permanece recto.
            if (!rotateTargets.isEmpty()) motion.start(rotateTargets);
        } catch (Exception ignored) {
            Toast.makeText(this, "No se pudo mostrar el botón flotante",
                    Toast.LENGTH_LONG).show();
            stopSelf();
        }
    }

    private void openPicker(String action, String packageName) {
        Intent intent = new Intent(this, MainActivity.class);
        intent.setAction(action);
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        if (packageName != null) intent.putExtra("package", packageName);
        try {
            startActivity(intent);
        } catch (Exception ignored) {
            Toast.makeText(this, "No se pudo abrir el selector",
                    Toast.LENGTH_SHORT).show();
        }
    }

    @Override public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
        // La pantalla cambia entre vertical y horizontal mientras otras apps estan abiertas.
        // Reconstruir geometria del dock y recalibrar el sensor sin perder la lista.
        if (dock != null && !stopped) renderDock();
    }

    private void refreshBadges() {
        for (Map.Entry<String, View> entry : badgeViews.entrySet()) {
            entry.getValue().setVisibility(
                    NotificationBadgeStore.pending(this, entry.getKey())
                            ? View.VISIBLE : View.GONE);
        }
    }

    private void removeDock() {
        badgeViews.clear();
        if (motion != null) motion.stop();
        if (dock != null && manager != null) {
            try { manager.removeViewImmediate(dock); } catch (Exception ignored) {}
            dock = null;
        }
    }

    @Override public void onDestroy() {
        removeDock();
        if (screenReceiverRegistered) {
            unregisterReceiver(screenStateReceiver);
            screenReceiverRegistered = false;
        }
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
