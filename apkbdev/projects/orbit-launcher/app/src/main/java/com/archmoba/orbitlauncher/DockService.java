package com.archmoba.orbitlauncher;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ResolveInfo;
import android.graphics.PixelFormat;
import android.os.Build;
import android.os.IBinder;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import java.util.ArrayList;
import java.util.List;

public final class DockService extends Service {
    static final String STOP = "com.archmoba.orbitlauncher.STOP";
    private final List<View> windows = new ArrayList<>();
    private WindowManager manager;
    private List<ResolveInfo> apps;
    private boolean expanded;

    @Override public void onCreate() {
        super.onCreate();
        foreground();
        manager = (WindowManager) getSystemService(WINDOW_SERVICE);
        apps = OrbitUtil.apps(this);
        if (!android.provider.Settings.canDrawOverlays(this)) stopSelf();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && STOP.equals(intent.getAction())) {
            stopService(new Intent(this, CaptureService.class));
            stopSelf();
            return START_NOT_STICKY;
        }
        if (!android.provider.Settings.canDrawOverlays(this)) {
            stopSelf();
            return START_NOT_STICKY;
        }
        boolean compact = intent != null && intent.getBooleanExtra("compact", false);
        updateDock(!compact);
        return START_NOT_STICKY;
    }

    private void foreground() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        nm.createNotificationChannel(new NotificationChannel(
                "orbit_dock", "Orbit en pantalla", NotificationManager.IMPORTANCE_LOW));
        Intent stop = new Intent(this, DockService.class).setAction(STOP);
        PendingIntent pending = PendingIntent.getService(this, 100, stop,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification notice = new Notification.Builder(this, "orbit_dock")
                .setSmallIcon(android.R.drawable.ic_menu_view)
                .setContentTitle("Orbit Launcher")
                .setContentText("Dock en pantalla. Pulsa para detener.")
                .setContentIntent(pending).setOngoing(true).build();
        startForeground(1001, notice);
    }

    private LinearLayout bar(boolean horizontal) {
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(horizontal ? LinearLayout.HORIZONTAL : LinearLayout.VERTICAL);
        bar.setGravity(Gravity.CENTER);
        bar.setBackgroundColor(OrbitUtil.BG);
        return bar;
    }

    private int horizontalIconSize() {
        DisplayMetrics dm = new DisplayMetrics();
        manager.getDefaultDisplay().getRealMetrics(dm);
        return Math.min(OrbitUtil.dp(this, 43),
                Math.max(OrbitUtil.dp(this, 27),
                        (dm.widthPixels - OrbitUtil.dp(this, 14)) / 6 - OrbitUtil.dp(this, 6)));
    }

    private void updateDock(boolean showExpanded) {
        clearWindows();
        expanded = showExpanded;
        if (showExpanded) showExpandedDock();
        else showHandle();
    }

    private void showHandle() {
        TextView bubble = new TextView(this);
        bubble.setText("◎");
        bubble.setTextColor(OrbitUtil.CYAN);
        bubble.setTextSize(30);
        bubble.setGravity(Gravity.CENTER);
        bubble.setBackground(OrbitUtil.background(this, OrbitUtil.PANEL, OrbitUtil.CYAN, 20));
        bubble.setOnClickListener(v -> updateDock(true));
        addWindow(bubble, OrbitUtil.dp(this, 43), OrbitUtil.dp(this, 48), Gravity.LEFT | Gravity.CENTER_VERTICAL);
    }

    private void showExpandedDock() {
        int topSize = horizontalIconSize();
        LinearLayout top = bar(true);
        control(top, "◉", this::home, topSize);
        addIcons(top, 0, 4, topSize);
        control(top, "▦", this::home, topSize);
        addWindow(top, -1, topSize + OrbitUtil.dp(this, 12), Gravity.TOP);

        LinearLayout left = bar(false);
        addIcons(left, 4, 5, OrbitUtil.dp(this, 44));
        addWindow(left, OrbitUtil.dp(this, 61), -1, Gravity.LEFT);

        LinearLayout right = bar(false);
        addIcons(right, 9, 5, OrbitUtil.dp(this, 44));
        addWindow(right, OrbitUtil.dp(this, 61), -1, Gravity.RIGHT);

        LinearLayout bottom = bar(true);
        control(bottom, "⌂", this::home, topSize);
        addIcons(bottom, 14, 2, topSize);
        control(bottom, "▣", this::mirror, topSize);
        control(bottom, "◁", () -> updateDock(false), topSize);
        control(bottom, "×", this::closeDock, topSize);
        addWindow(bottom, -1, topSize + OrbitUtil.dp(this, 13), Gravity.BOTTOM);
    }

    private void addIcons(LinearLayout bar, int from, int count, int iconSize) {
        for (int i = from; i < Math.min(from + count, apps.size()); i++) {
            ResolveInfo app = apps.get(i);
            ImageView icon = OrbitUtil.appIcon(this, app);
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(iconSize, iconSize);
            p.setMargins(OrbitUtil.dp(this, 2), OrbitUtil.dp(this, 3),
                    OrbitUtil.dp(this, 2), OrbitUtil.dp(this, 3));
            bar.addView(icon, p);
            icon.setOnClickListener(v -> open(app.activityInfo.packageName));
            icon.setOnLongClickListener(v -> {
                Toast.makeText(this, icon.getContentDescription(), Toast.LENGTH_SHORT).show();
                return true;
            });
        }
    }

    private void control(LinearLayout bar, String label, Runnable click, int iconSize) {
        TextView control = new TextView(this);
        control.setText(label);
        control.setTextColor(OrbitUtil.CYAN);
        control.setTextSize(22);
        control.setGravity(Gravity.CENTER);
        control.setBackground(OrbitUtil.background(this, OrbitUtil.PANEL, OrbitUtil.CYAN, 12));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(iconSize, iconSize);
        p.setMargins(OrbitUtil.dp(this, 2), OrbitUtil.dp(this, 3),
                OrbitUtil.dp(this, 2), OrbitUtil.dp(this, 3));
        bar.addView(control, p);
        control.setOnClickListener(v -> click.run());
    }

    private void addWindow(View view, int width, int height, int gravity) {
        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                width, height, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        lp.gravity = gravity;
        try {
            manager.addView(view, lp);
            windows.add(view);
        } catch (Exception ignored) {
            Toast.makeText(this, "No se pudo mostrar el dock", Toast.LENGTH_SHORT).show();
        }
    }

    private void open(String pkg) {
        stopService(new Intent(this, CaptureService.class));
        boolean fit = OrbitUtil.supportsFreeform(this);
        if (!fit) updateDock(false);
        OrbitUtil.launch(this, pkg, fit);
    }

    private void mirror() {
        stopService(new Intent(this, CaptureService.class));
        Intent intent = new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP)
                .putExtra("mirror", true);
        startActivity(intent);
        stopSelf();
    }

    private void home() {
        stopService(new Intent(this, CaptureService.class));
        Intent intent = new Intent(this, MainActivity.class)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        startActivity(intent);
        stopSelf();
    }

    private void closeDock() {
        stopService(new Intent(this, CaptureService.class));
        stopSelf();
    }

    private void clearWindows() {
        for (View view : windows) {
            try { manager.removeViewImmediate(view); } catch (Exception ignored) {}
        }
        windows.clear();
    }

    @Override public void onDestroy() {
        if (manager != null) clearWindows();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
