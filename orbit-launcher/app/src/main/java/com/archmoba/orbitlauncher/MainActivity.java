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
    private String requestedPackage;
    private boolean requestedMirror;

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.BLACK);
        getWindow().setNavigationBarColor(Color.BLACK);
        stopService(new Intent(this, DockService.class));
        stopService(new Intent(this, CaptureService.class));
        apps = OrbitUtil.apps(this);
        render();
        if (getIntent().getBooleanExtra("mirror", false)) {
            new Handler(Looper.getMainLooper()).postDelayed(this::requestMirror, 280);
        }
    }

    private void render() {
        int gap = OrbitUtil.dp(this, 5);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(OrbitUtil.BG);
        root.setPadding(gap, gap, gap, gap);
        setContentView(root);

        TextView heading = new TextView(this);
        heading.setText("◉  ORBIT LAUNCHER   •   ARCHMOBA");
        heading.setTextColor(OrbitUtil.CYAN);
        heading.setTextSize(17);
        heading.setGravity(Gravity.CENTER);
        heading.setTypeface(null, 1);
        root.addView(heading, new LinearLayout.LayoutParams(-1, OrbitUtil.dp(this, 49)));

        LinearLayout top = row();
        top.setGravity(Gravity.CENTER);
        root.addView(top, new LinearLayout.LayoutParams(-1, OrbitUtil.dp(this, 61)));
        addIcons(top, 0, 4);

        LinearLayout middle = row();
        LinearLayout.LayoutParams middleParams = new LinearLayout.LayoutParams(-1, 0, 1);
        root.addView(middle, middleParams);

        LinearLayout left = new LinearLayout(this);
        left.setOrientation(LinearLayout.VERTICAL);
        left.setGravity(Gravity.CENTER);
        middle.addView(left, new LinearLayout.LayoutParams(OrbitUtil.dp(this, 58), -1));
        addIcons(left, 4, 5);

        FrameLayout emptyViewport = new FrameLayout(this);
        emptyViewport.setBackground(OrbitUtil.background(this, Color.WHITE, OrbitUtil.CYAN, 17));
        emptyViewport.setContentDescription("Visor central vacío. Toca para seleccionar una aplicación.");
        emptyViewport.setOnClickListener(v -> showAppPicker());
        LinearLayout.LayoutParams vp = new LinearLayout.LayoutParams(0, -1, 1);
        vp.setMargins(OrbitUtil.dp(this, 3), OrbitUtil.dp(this, 3),
                OrbitUtil.dp(this, 3), OrbitUtil.dp(this, 3));
        middle.addView(emptyViewport, vp);

        LinearLayout right = new LinearLayout(this);
        right.setOrientation(LinearLayout.VERTICAL);
        right.setGravity(Gravity.CENTER);
        middle.addView(right, new LinearLayout.LayoutParams(OrbitUtil.dp(this, 58), -1));
        addIcons(right, 9, 5);

        LinearLayout bottom = row();
        bottom.setGravity(Gravity.CENTER);
        root.addView(bottom, new LinearLayout.LayoutParams(-1, OrbitUtil.dp(this, 58)));
        addIcons(bottom, 14, 3);

        LinearLayout actions = row();
        actions.setGravity(Gravity.CENTER);
        root.addView(actions, new LinearLayout.LayoutParams(-1, OrbitUtil.dp(this, 58)));
        action(actions, "APPS", this::showAppPicker);
        action(actions, "ESPEJO", this::requestMirror);
        action(actions, "SALIR", this::finish);
    }

    private LinearLayout row() {
        LinearLayout ll = new LinearLayout(this);
        ll.setOrientation(LinearLayout.HORIZONTAL);
        return ll;
    }

    private void addIcons(LinearLayout target, int from, int count) {
        for (int i = from; i < Math.min(apps.size(), from + count); i++) {
            ResolveInfo app = apps.get(i);
            ImageView icon = OrbitUtil.appIcon(this, app, 44);
            int size = OrbitUtil.dp(this, 45);
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(size, size);
            int margin = OrbitUtil.dp(this, 3);
            p.setMargins(margin, margin, margin, margin);
            target.addView(icon, p);
            icon.setOnClickListener(v -> openPackage(app.activityInfo.packageName));
            icon.setOnLongClickListener(v -> {
                Toast.makeText(this, icon.getContentDescription(), Toast.LENGTH_SHORT).show();
                return true;
            });
        }
    }

    private void action(LinearLayout parent, String label, Runnable click) {
        TextView b = new TextView(this);
        b.setText(label);
        b.setTextSize(12);
        b.setTypeface(null, 1);
        b.setGravity(Gravity.CENTER);
        b.setTextColor(OrbitUtil.CYAN);
        b.setBackground(OrbitUtil.background(this, OrbitUtil.PANEL, OrbitUtil.CYAN, 13));
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(0, OrbitUtil.dp(this, 46), 1);
        p.setMargins(OrbitUtil.dp(this, 3), 0, OrbitUtil.dp(this, 3), 0);
        parent.addView(b, p);
        b.setOnClickListener(v -> click.run());
    }

    private void showAppPicker() {
        if (apps.isEmpty()) {
            Toast.makeText(this, "No se encontraron aplicaciones visibles", Toast.LENGTH_LONG).show();
            return;
        }
        CharSequence[] names = new CharSequence[apps.size()];
        for (int i = 0; i < apps.size(); i++) {
            names[i] = apps.get(i).loadLabel(getPackageManager());
        }
        new AlertDialog.Builder(this)
                .setTitle("Seleccionar aplicación")
                .setItems(names, (dialog, which) ->
                        openPackage(apps.get(which).activityInfo.packageName))
                .setNegativeButton("Cancelar", null)
                .show();
    }

    private void openPackage(String pkg) {
        requestedPackage = pkg;
        requestedMirror = false;
        verifyOverlay();
    }

    private void requestMirror() {
        if (Build.VERSION.SDK_INT < 34) {
            new AlertDialog.Builder(this)
                    .setTitle("Visor interactivo")
                    .setMessage("En este Android se utiliza la ventana central directa. El modo de transmisión individual requiere Android 14 QPR2 o posterior. Selecciona una app para verla y tocarla en el centro.")
                    .setPositiveButton("Abrir una app", (d, w) -> showAppPicker())
                    .setNegativeButton("Cancelar", null).show();
            return;
        }
        requestedMirror = true;
        requestedPackage = null;
        verifyOverlay();
    }

    private void verifyOverlay() {
        if (Build.VERSION.SDK_INT >= 23 && !Settings.canDrawOverlays(this)) {
            Toast.makeText(this, "Permite mostrar Orbit sobre otras aplicaciones", Toast.LENGTH_LONG).show();
            Intent perm = new Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                    Uri.parse("package:" + getPackageName()));
            startActivityForResult(perm, OVERLAY_REQUEST);
            return;
        }
        afterOverlayPermission();
    }

    private void afterOverlayPermission() {
        if (requestedMirror) {
            MediaProjectionManager pm = (MediaProjectionManager)
                    getSystemService(MEDIA_PROJECTION_SERVICE);
            startActivityForResult(pm.createScreenCaptureIntent(), PROJECTION_REQUEST);
        } else if (requestedPackage != null) {
            startDock();
            if (OrbitUtil.launch(this, requestedPackage)) finish();
        }
    }

    private void startDock() {
        Intent i = new Intent(this, DockService.class);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(i);
        else startService(i);
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == OVERLAY_REQUEST) {
            if (Settings.canDrawOverlays(this)) afterOverlayPermission();
            else Toast.makeText(this, "Orbit necesita el permiso de superposición", Toast.LENGTH_LONG).show();
        } else if (requestCode == PROJECTION_REQUEST && resultCode == RESULT_OK && data != null) {
            startDock();
            Intent capture = new Intent(this, CaptureService.class);
            capture.putExtra("code", resultCode);
            capture.putExtra("data", data);
            if (Build.VERSION.SDK_INT >= 26) startForegroundService(capture);
            else startService(capture);
            finish();
        }
    }
}
