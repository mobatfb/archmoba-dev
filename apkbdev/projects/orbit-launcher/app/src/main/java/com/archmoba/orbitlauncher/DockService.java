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
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.app.KeyguardManager;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.MotionEvent;
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
    private boolean sleeping;
    private static final String POSITION_PREFS = "orbit_panel_position";
    private static final String OFFSET_KEY = "vertical_offset_dp";
    private boolean dockHiddenForMenu;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private int wakeChecks;
    private final Runnable checkUnlock = new Runnable() {
        @Override public void run() {
            if (stopped || dockHiddenForMenu || !sleeping) return;
            if (isDeviceUnlocked()) {
                wakeChecks = 0;
                sleeping = false;
                OrbitNotificationListener.scanOnUnlock(DockService.this);
                renderDock();
            } else if (++wakeChecks < 20 && isScreenInteractive()) {
                mainHandler.postDelayed(this, 500L);
            }
        }
    };
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
                if (!sleeping) refreshBadges();
                return;
            }
            if (Intent.ACTION_SCREEN_OFF.equals(action)) {
                sleeping = true;
                mainHandler.removeCallbacks(checkUnlock);
                removeDock();
            } else if (Intent.ACTION_SCREEN_ON.equals(action)
                    || Intent.ACTION_USER_PRESENT.equals(action)) {
                if (sleeping) scheduleUnlockCheck();
                else if (dock == null && !dockHiddenForMenu && isDeviceUnlocked()) renderDock();
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
        screenEvents.addAction(Intent.ACTION_USER_PRESENT);
        screenEvents.addAction(NotificationBadgeStore.ACTION_CHANGED);
        // Son broadcasts exclusivos del sistema; registro no exportado.
        if (Build.VERSION.SDK_INT >= 33) {
            registerReceiver(screenStateReceiver, screenEvents,
                    Context.RECEIVER_NOT_EXPORTED);
        } else {
            registerReceiver(screenStateReceiver, screenEvents);
        }
        screenReceiverRegistered = true;

        sleeping = !isDeviceUnlocked();
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
        if (ACTION_HIDE.equals(action)) {
            dockHiddenForMenu = true;
            removeDock();
        } else {
            dockHiddenForMenu = false;
            sleeping = !isDeviceUnlocked();
            if (!sleeping) renderDock();
            else if (isScreenInteractive()) scheduleUnlockCheck();
        }
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

    private boolean isScreenInteractive() {
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        return pm == null || pm.isInteractive();
    }

    private boolean isDeviceUnlocked() {
        KeyguardManager km = (KeyguardManager) getSystemService(KEYGUARD_SERVICE);
        return isScreenInteractive() && (km == null || !km.isKeyguardLocked());
    }

    private void scheduleUnlockCheck() {
        mainHandler.removeCallbacks(checkUnlock);
        wakeChecks = 0;
        mainHandler.post(checkUnlock);
    }

    private void renderDock() {
        removeDock();
        if (stopped || sleeping) return;

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
        // Tirador discreto: desplaza el conjunto completo sin interferir con
        // toques, pulsaciones largas ni el scroll de listas extensas.
        View handle = new View(this);
        GradientDrawable handleShape = new GradientDrawable();
        handleShape.setColor(Color.argb(180, 70, 218, 238));
        handleShape.setCornerRadius(OrbitUtil.dp(this, 4));
        handle.setBackground(handleShape);
        handle.setContentDescription("Arrastrar el panel de Orbit arriba o abajo");
        LinearLayout.LayoutParams handleParams = new LinearLayout.LayoutParams(
                OrbitUtil.dp(this, 26), OrbitUtil.dp(this, 6));
        handleParams.setMargins(0, 0, 0, OrbitUtil.dp(this, 5));
        root.addView(handle, handleParams);

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
        final int baseY = -step; // Referencia original del panel.
        android.content.SharedPreferences positionPrefs =
                getSharedPreferences(POSITION_PREFS, MODE_PRIVATE);
        int savedDp = positionPrefs.getInt(OFFSET_KEY, 0);
        int savedPx = OrbitUtil.dp(this, savedDp);
        params.y = baseY + savedPx;
        // Ajustar dentro de la pantalla, incluso al cambiar orientacion.
        DisplayMetrics bounds = new DisplayMetrics();
        manager.getDefaultDisplay().getMetrics(bounds);
        final int screenHeight = bounds.heightPixels;
        final int estimatedHeight = OrbitUtil.dp(this, visible == 0 ? 60 :
                15 + Math.min(visible * 52, Math.max(52, (int) (screenHeight
                        / getResources().getDisplayMetrics().density) - 182)));
        final int travel = Math.max(0, (screenHeight - estimatedHeight
                - OrbitUtil.dp(this, 24)) / 2);
        params.y = Math.max(-travel, Math.min(travel, params.y));
        final int[] currentY = {params.y};
        final float[] startRawY = {0f};
        final int[] startY = {params.y};
        final boolean[] moving = {false};
        handle.setOnTouchListener((v, event) -> {
            if (dock == null) return false;
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    startRawY[0] = event.getRawY();
                    startY[0] = currentY[0];
                    moving[0] = false;
                    return true;
                case MotionEvent.ACTION_MOVE:
                    int difference = Math.round(event.getRawY() - startRawY[0]);
                    if (Math.abs(difference) > OrbitUtil.dp(this, 3))
                        moving[0] = true;
                    int requested = Math.max(-travel, Math.min(travel,
                            startY[0] + difference));
                    if (requested != currentY[0]) {
                        currentY[0] = requested;
                        params.y = requested;
                        try { manager.updateViewLayout(root, params); }
                        catch (IllegalArgumentException ignored) {}
                    }
                    return true;
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL:
                    if (moving[0]) {
                        int dp = Math.round((currentY[0] - baseY)
                                / getResources().getDisplayMetrics().density);
                        positionPrefs.edit().putInt(OFFSET_KEY, dp).apply();
                    }
                    return true;
                default:
                    return true;
            }
        });
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
        if (dock != null && !stopped && !sleeping) renderDock();
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
        mainHandler.removeCallbacks(checkUnlock);
        removeDock();
        if (screenReceiverRegistered) {
            unregisterReceiver(screenStateReceiver);
            screenReceiverRegistered = false;
        }
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
