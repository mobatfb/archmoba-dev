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

    @Override public void onCreate() {
        super.onCreate();
        foreground();
        manager = (WindowManager) getSystemService(WINDOW_SERVICE);
        apps = OrbitUtil.apps(this);
        if (!android.provider.Settings.canDrawOverlays(this)) {
            stopSelf();
            return;
        }
        showDock();
    }

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && STOP.equals(intent.getAction())) {
            stopService(new Intent(this, CaptureService.class));
            stopSelf();
        }
        return START_NOT_STICKY;
    }

    private void foreground() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        nm.createNotificationChannel(new NotificationChannel(
                "orbit_dock", "Orbit Launcher activo", NotificationManager.IMPORTANCE_LOW));
        Intent stop = new Intent(this, DockService.class).setAction(STOP);
        PendingIntent pending = PendingIntent.getService(this, 100, stop,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification notice = new Notification.Builder(this, "orbit_dock")
                .setSmallIcon(android.R.drawable.ic_menu_view)
                .setContentTitle("Orbit Launcher")
                .setContentText("Iconos laterales activos. Pulsa para detener.")
                .setContentIntent(pending).setOngoing(true).build();
        startForeground(1001, notice);
    }

    private LinearLayout bar(boolean horizontal) {
        LinearLayout ll = new LinearLayout(this);
        ll.setOrientation(horizontal ? LinearLayout.HORIZONTAL : LinearLayout.VERTICAL);
        ll.setGravity(Gravity.CENTER);
        ll.setBackgroundColor(OrbitUtil.BG);
        return ll;
    }

    private void showDock() {
        LinearLayout top = bar(true);
        control(top, "◉", this::home);
        addIcons(top, 0, 4);
        control(top, "▦", this::home);
        addWindow(top, -1, OrbitUtil.dp(this, 73), Gravity.TOP);

        LinearLayout left = bar(false);
        addIcons(left, 4, 5);
        addWindow(left, OrbitUtil.dp(this, 65), -1, Gravity.LEFT);

        LinearLayout right = bar(false);
        addIcons(right, 9, 5);
        addWindow(right, OrbitUtil.dp(this, 65), -1, Gravity.RIGHT);

        LinearLayout bottom = bar(true);
        control(bottom, "⌂", this::home);
        addIcons(bottom, 14, 2);
        control(bottom, "▣", this::mirror);
        control(bottom, "×", this::closeDock);
        addWindow(bottom, -1, OrbitUtil.dp(this, 72), Gravity.BOTTOM);
    }

    private void addIcons(LinearLayout bar, int start, int count) {
        for (int i = start; i < Math.min(start + count, apps.size()); i++) {
            ResolveInfo app = apps.get(i);
            ImageView iv = OrbitUtil.appIcon(this, app, 44);
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                    OrbitUtil.dp(this, 44), OrbitUtil.dp(this, 44));
            p.setMargins(OrbitUtil.dp(this, 3), OrbitUtil.dp(this, 4),
                    OrbitUtil.dp(this, 3), OrbitUtil.dp(this, 4));
            bar.addView(iv, p);
            iv.setOnClickListener(v -> open(app.activityInfo.packageName));
            iv.setOnLongClickListener(v -> {
                Toast.makeText(this, iv.getContentDescription(), Toast.LENGTH_SHORT).show();
                return true;
            });
        }
    }

    private void control(LinearLayout bar, String symbol, Runnable onClick) {
        TextView t = new TextView(this);
        t.setText(symbol);
        t.setTextColor(OrbitUtil.CYAN);
        t.setTextSize(24);
        t.setGravity(Gravity.CENTER);
        t.setBackground(OrbitUtil.background(this, OrbitUtil.PANEL, OrbitUtil.CYAN, 12));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(
                OrbitUtil.dp(this, 44), OrbitUtil.dp(this, 44));
        p.setMargins(OrbitUtil.dp(this, 3), OrbitUtil.dp(this, 4),
                OrbitUtil.dp(this, 3), OrbitUtil.dp(this, 4));
        bar.addView(t, p);
        t.setOnClickListener(v -> onClick.run());
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
        } catch (Exception e) {
            Toast.makeText(this, "No se pudo mostrar el dock", Toast.LENGTH_SHORT).show();
        }
    }

    private void open(String pkg) {
        stopService(new Intent(this, CaptureService.class));
        OrbitUtil.launch(this, pkg);
    }

    private void mirror() {
        stopService(new Intent(this, CaptureService.class));
        Intent i = new Intent(this, MainActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_SINGLE_TOP);
        i.putExtra("mirror", true);
        startActivity(i);
        stopSelf();
    }

    private void home() {
        stopService(new Intent(this, CaptureService.class));
        Intent i = new Intent(this, MainActivity.class);
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        startActivity(i);
        stopSelf();
    }

    private void closeDock() {
        stopService(new Intent(this, CaptureService.class));
        stopSelf();
    }

    @Override public void onDestroy() {
        if (manager != null) {
            for (View view : windows) {
                try { manager.removeViewImmediate(view); } catch (Exception ignored) {}
            }
        }
        windows.clear();
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
