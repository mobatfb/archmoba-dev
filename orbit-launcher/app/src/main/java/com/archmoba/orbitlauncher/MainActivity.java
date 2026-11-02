package com.archmoba.orbitlauncher;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.media.projection.MediaProjectionManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.view.Gravity;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;
import java.util.List;

public final class MainActivity extends Activity {
    private static final int OVERLAY_REQUEST = 41;
    private static final int PROJECTION_REQUEST = 42;
    private List<ResolveInfo> apps;
    private String selectedPackage;
    private boolean preferWindow = true;
    private boolean requestMirrorMode = false;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.BLACK);
        getWindow().setNavigationBarColor(Color.BLACK);
        stopService(new Intent(this, DockService.class));
        stopService(new Intent(this, CaptureService.class));
        apps = OrbitUtil.apps(this);
        render();
        if (getIntent().getBooleanExtra("mirror", false)) {
            new Handler(Looper.getMainLooper()).postDelayed(this::mirrorMode, 250);
        }
    }

    private void render() {
        int gap = OrbitUtil.dp(this, 4);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(OrbitUtil.BG);
        root.setPadding(gap, gap, gap, gap);
        setContentView(root);

        TextView title = new TextView(this);
        title.setText("◉  ORBIT LAUNCHER · 0.2");
        title.setTextColor(OrbitUtil.CYAN);
        title.setTextSize(17);
        title.setTypeface(null, 1);
        title.setGravity(Gravity.CENTER);
        root.addView(title, new LinearLayout.LayoutParams(-1, OrbitUtil.dp(this, 43)));

        LinearLayout top = row(true);
        root.addView(top, new LinearLayout.LayoutParams(-1, OrbitUtil.dp(this, 56)));
        addIcons(top, 0, 4, true);

        LinearLayout middle = row(true);
        root.addView(middle, new LinearLayout.LayoutParams(-1, 0, 1));

        LinearLayout left = row(false);
        middle.addView(left, new LinearLayout.LayoutParams(OrbitUtil.dp(this, 52), -1));
        addIcons(left, 4, 5, false);

        FrameLayout viewport = new FrameLayout(this);
        viewport.setBackground(OrbitUtil.background(this, Color.WHITE, OrbitUtil.CYAN, 17));
        viewport.setContentDescription("Visor central. Selecciona una aplicación.");
        viewport.setOnClickListener(v -> picker(true));
        LinearLayout.LayoutParams center = new LinearLayout.LayoutParams(0, -1, 1);
        center.setMargins(gap, gap, gap, gap);
        middle.addView(viewport, center);

        LinearLayout right = row(false);
        middle.addView(right, new LinearLayout.LayoutParams(OrbitUtil.dp(this, 52), -1));
        addIcons(right, 9, 5, false);

        LinearLayout bottom = row(true);
        root.addView(bottom, new LinearLayout.LayoutParams(-1, OrbitUtil.dp(this, 55)));
        addIcons(bottom, 14, 3, true);

        TextView status = new TextView(this);
        boolean freeform = OrbitUtil.supportsFreeform(this);
        status.setText(freeform
                ? "Ventana ajustada disponible según compatibilidad de cada app."
                : "Sin ventana libre: ORBIT ocultará los bordes para mostrar la app completa.");
        status.setTextColor(0xFF9CB1CA);
        status.setTextSize(10);
        status.setGravity(Gravity.CENTER);
        root.addView(status, new LinearLayout.LayoutParams(-1, OrbitUtil.dp(this, 36)));

        LinearLayout actions = row(true);
        root.addView(actions, new LinearLayout.LayoutParams(-1, OrbitUtil.dp(this, 54)));
        action(actions, "APPS", () -> picker(true));
        action(actions, "COMPLETA", () -> picker(false));
        action(actions, "ESPEJO", this::mirrorMode);
        action(actions, "SALIR", this::finish);
    }

    private LinearLayout row(boolean horizontal) {
        LinearLayout bar = new LinearLayout(this);
        bar.setOrientation(horizontal ? LinearLayout.HORIZONTAL : LinearLayout.VERTICAL);
        bar.setGravity(Gravity.CENTER);
        return bar;
    }

    private void addIcons(LinearLayout bar, int first, int count, boolean horizontal) {
        int size = OrbitUtil.dp(this, 42);
        if (horizontal) {
            int available = getResources().getDisplayMetrics().widthPixels - OrbitUtil.dp(this, 14);
            size = Math.min(size, Math.max(OrbitUtil.dp(this, 27),
                    available / Math.max(4, count) - OrbitUtil.dp(this, 7)));
        }
        for (int i = first; i < Math.min(first + count, apps.size()); i++) {
            ResolveInfo app = apps.get(i);
            ImageView iv = OrbitUtil.appIcon(this, app);
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(size, size);
            p.setMargins(OrbitUtil.dp(this, 3), OrbitUtil.dp(this, 3),
                    OrbitUtil.dp(this, 3), OrbitUtil.dp(this, 3));
            bar.addView(iv, p);
            iv.setOnClickListener(v -> launch(app.activityInfo.packageName, true));
            iv.setOnLongClickListener(v -> {
                Toast.makeText(this, iv.getContentDescription(), Toast.LENGTH_SHORT).show();
                return true;
            });
        }
    }

    private void action(LinearLayout parent, String label, Runnable callback) {
        TextView view = new TextView(this);
        view.setText(label);
        view.setGravity(Gravity.CENTER);
        view.setTextSize(10);
        view.setTypeface(null, 1);
        view.setTextColor(OrbitUtil.CYAN);
        view.setBackground(OrbitUtil.background(this, OrbitUtil.PANEL, OrbitUtil.CYAN, 12));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, OrbitUtil.dp(this, 43), 1);
        p.setMargins(OrbitUtil.dp(this, 2), 0, OrbitUtil.dp(this, 2), 0);
        parent.addView(view, p);
        view.setOnClickListener(v -> callback.run());
    }

    private void picker(boolean adjusted) {
        if (apps.isEmpty()) {
            Toast.makeText(this, "No se encontraron aplicaciones", Toast.LENGTH_LONG).show();
            return;
        }
        CharSequence[] names = new CharSequence[apps.size()];
        for (int i = 0; i < apps.size(); i++)
            names[i] = apps.get(i).loadLabel(getPackageManager());
        new AlertDialog.Builder(this)
                .setTitle(adjusted ? "Aplicación en ventana central" : "Aplicación a pantalla completa")
                .setItems(names, (dialog, which) ->
                        launch(apps.get(which).activityInfo.packageName, adjusted))
                .setNegativeButton("Cancelar", null).show();
    }

    private void launch(String pkg, boolean adjusted) {
        selectedPackage = pkg;
        preferWindow = adjusted;
        requestMirrorMode = false;
        ensureOverlay();
    }

    private void mirrorMode() {
        if (Build.VERSION.SDK_INT < 34) {
            new AlertDialog.Builder(this)
                    .setTitle("Espejo de una aplicación")
                    .setMessage("La captura individual de apps requiere Android 14 QPR2 o posterior. En este teléfono puedes usar COMPLETA para verla sin recortes o intentar ventanas libres si tu sistema las admite.")
                    .setPositiveButton("COMPLETA", (d, w) -> picker(false))
                    .setNegativeButton("Cerrar", null).show();
            return;
        }
        new AlertDialog.Builder(this)
                .setTitle("Transmisión al centro")
                .setMessage("En el permiso de Android selecciona «Una aplicación», NO «Toda la pantalla». La imagen se ajustará dentro del rectángulo. Esta transmisión es visual; los toques en el visor no controlan la app.")
                .setPositiveButton("Continuar", (d, w) -> {
                    selectedPackage = null;
                    requestMirrorMode = true;
                    ensureOverlay();
                }).setNegativeButton("Cancelar", null).show();
    }

    private void ensureOverlay() {
        if (Build.VERSION.SDK_INT >= 23 && !Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "Activa «Mostrar sobre otras aplicaciones»", Toast.LENGTH_LONG).show();
            startActivityForResult(new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName())), OVERLAY_REQUEST);
        } else proceed();
    }

    private void proceed() {
        if (requestMirrorMode) {
            MediaProjectionManager pm = (MediaProjectionManager)
                    getSystemService(MEDIA_PROJECTION_SERVICE);
            startActivityForResult(pm.createScreenCaptureIntent(), PROJECTION_REQUEST);
        } else if (selectedPackage != null) {
            boolean fit = preferWindow && OrbitUtil.supportsFreeform(this);
            startDock(!fit);
            if (OrbitUtil.launch(this, selectedPackage, fit)) finish();
        }
    }

    private void startDock(boolean compact) {
        Intent intent = new Intent(this, DockService.class);
        intent.putExtra("compact", compact);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent);
        else startService(intent);
    }

    @Override protected void onActivityResult(int requestCode, int code, Intent data) {
        super.onActivityResult(requestCode, code, data);
        if (requestCode == OVERLAY_REQUEST) {
            if (Settings.canDrawOverlays(this)) proceed();
            else Toast.makeText(this, "Falta permiso para mostrar los iconos", Toast.LENGTH_LONG).show();
        } else if (requestCode == PROJECTION_REQUEST && code == RESULT_OK && data != null) {
            startDock(false);
            Intent intent = new Intent(this, CaptureService.class);
            intent.putExtra("code", code);
            intent.putExtra("data", data);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent);
            else startService(intent);
            finish();
        }
    }
}
