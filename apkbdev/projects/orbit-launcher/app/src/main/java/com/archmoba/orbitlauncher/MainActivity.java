package com.archmoba.orbitlauncher;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.provider.Settings;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ArrayAdapter;
import android.widget.EditText;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;
import android.widget.Toast;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

/**
 * Actividad efimera: no abre ninguna pantalla principal.
 * La interfaz permanente es unicamente el dock flotante en el lado derecho.
 */
public final class MainActivity extends Activity {
    private static final int REQUEST_OVERLAY = 101;
    private boolean restored;

    @Override public void onCreate(Bundle savedState) {
        super.onCreate(savedState);
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Color.TRANSPARENT);
        if (Build.VERSION.SDK_INT >= 23 && !Settings.canDrawOverlays(this)) {
            new AlertDialog.Builder(this)
                    .setTitle("Permitir botón flotante")
                    .setMessage("Orbit necesita permiso para mostrar únicamente el botón + y tus aplicaciones elegidas al lado derecho.")
                    .setPositiveButton("Conceder permiso", (dialog, which) -> {
                        Intent settings = new Intent(
                                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                                Uri.parse("package:" + getPackageName()));
                        startActivityForResult(settings, REQUEST_OVERLAY);
                    })
                    .setNegativeButton("Cancelar", (dialog, which) -> finish())
                    .setOnCancelListener(dialog -> finish())
                    .show();
        } else {
            handleAction();
        }
    }

    @Override protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);
        if (requestCode == REQUEST_OVERLAY) {
            if (Settings.canDrawOverlays(this)) handleAction();
            else {
                Toast.makeText(this, "Se necesita el permiso para mostrar el botón +",
                        Toast.LENGTH_LONG).show();
                finish();
            }
        }
    }

    private void handleAction() {
        String action = getIntent().getAction();
        if (DockService.ACTION_ADD.equals(action)) {
            command(DockService.ACTION_HIDE);
            showPicker();
        } else if (DockService.ACTION_MANAGE.equals(action)) {
            command(DockService.ACTION_HIDE);
            showManageDialog(getIntent().getStringExtra("package"));
        } else if (DockService.ACTION_REMOVE.equals(action)) {
            command(DockService.ACTION_HIDE);
            showRemoveDialog(getIntent().getStringExtra("package"));
        } else {
            // Primera apertura: servicio inicia con lista vacia => solo "+".
            command(DockService.ACTION_REFRESH);
            finish();
        }
    }

    private void command(String action) {
        Intent intent = new Intent(this, DockService.class);
        intent.setAction(action);
        if (Build.VERSION.SDK_INT >= 26) startForegroundService(intent);
        else startService(intent);
    }

    private void restoreAndFinish() {
        if (restored) return;
        restored = true;
        command(DockService.ACTION_REFRESH);
        finish();
    }

    private void showPicker() {
        final List<ResolveInfo> installed = AppStore.available(this);
        if (installed.isEmpty()) {
            new AlertDialog.Builder(this)
                    .setTitle("Añadir aplicación")
                    .setMessage("No quedan aplicaciones para añadir al panel.")
                    .setPositiveButton("Aceptar", null)
                    .setOnDismissListener(d -> restoreAndFinish())
                    .show();
            return;
        }

        final PackageManager pm = getPackageManager();
        final List<ResolveInfo> filtered = new ArrayList<>(installed);
        LinearLayout content = new LinearLayout(this);
        content.setOrientation(LinearLayout.VERTICAL);
        int padding = OrbitUtil.dp(this, 12);
        content.setPadding(padding, padding, padding, padding);

        EditText search = new EditText(this);
        search.setSingleLine(true);
        search.setTextSize(16);
        search.setHint("Buscar aplicación instalada");
        search.setCompoundDrawablesWithIntrinsicBounds(
                android.R.drawable.ic_menu_search, 0, 0, 0);
        content.addView(search, new LinearLayout.LayoutParams(-1,
                OrbitUtil.dp(this, 52)));

        ListView list = new ListView(this);
        list.setDividerHeight(0);
        final ArrayAdapter<ResolveInfo> adapter = new ArrayAdapter<ResolveInfo>(
                this, android.R.layout.simple_list_item_1, filtered) {
            @Override public View getView(int position, View convertView, ViewGroup parent) {
                ResolveInfo item = getItem(position);
                LinearLayout row = new LinearLayout(MainActivity.this);
                row.setGravity(Gravity.CENTER_VERTICAL);
                row.setPadding(OrbitUtil.dp(MainActivity.this, 9),
                        OrbitUtil.dp(MainActivity.this, 5),
                        OrbitUtil.dp(MainActivity.this, 9),
                        OrbitUtil.dp(MainActivity.this, 5));

                ImageView icon = new ImageView(MainActivity.this);
                icon.setImageDrawable(item.loadIcon(pm));
                row.addView(icon, new LinearLayout.LayoutParams(
                        OrbitUtil.dp(MainActivity.this, 40),
                        OrbitUtil.dp(MainActivity.this, 40)));

                TextView label = new TextView(MainActivity.this);
                label.setText(String.valueOf(item.loadLabel(pm)));
                label.setTextSize(16);
                label.setTextColor(Color.WHITE);
                label.setGravity(Gravity.CENTER_VERTICAL);
                LinearLayout.LayoutParams lp = new LinearLayout.LayoutParams(
                        0, OrbitUtil.dp(MainActivity.this, 55), 1);
                lp.leftMargin = OrbitUtil.dp(MainActivity.this, 12);
                row.addView(label, lp);
                return row;
            }
        };
        list.setAdapter(adapter);
        content.addView(list, new LinearLayout.LayoutParams(-1,
                OrbitUtil.dp(this, 390)));

        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence text, int start,
                                                    int count, int after) {}
            @Override public void onTextChanged(CharSequence text, int start,
                                                int before, int count) {
                String query = text.toString().trim().toLowerCase(Locale.ROOT);
                adapter.clear();
                for (ResolveInfo app : installed) {
                    String name = String.valueOf(app.loadLabel(pm))
                            .toLowerCase(Locale.ROOT);
                    if (name.contains(query)
                            || app.activityInfo.packageName.toLowerCase(Locale.ROOT)
                                .contains(query)) adapter.add(app);
                }
                adapter.notifyDataSetChanged();
            }
            @Override public void afterTextChanged(Editable edit) {}
        });

        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle("Añadir al lado derecho")
                .setView(content)
                .setNegativeButton("Cancelar", null)
                .setOnDismissListener(d -> restoreAndFinish())
                .create();
        list.setOnItemClickListener((parent, view, position, id) -> {
            ResolveInfo app = adapter.getItem(position);
            if (app != null && AppStore.add(this, app.activityInfo.packageName)) {
                Toast.makeText(this,
                        "Añadida: " + app.loadLabel(pm) + ". Mantén pulsado un icono para añadir más.",
                        Toast.LENGTH_LONG).show();
            }
            dialog.dismiss();
        });
        dialog.show();
    }

    private void showManageDialog(String packageName) {
        if (packageName == null || packageName.trim().isEmpty()) {
            restoreAndFinish();
            return;
        }
        List<String> selected = AppStore.selected(this);
        int index = selected.indexOf(packageName);
        if (index < 0) {
            restoreAndFinish();
            return;
        }

        String[] choices = {
            "+ Añadir aplicación",
            index == 0 ? "↑ Subir un lugar (ya está primero)" : "↑ Subir un lugar",
            index == selected.size() - 1 ? "↓ Bajar un lugar (ya está último)"
                    : "↓ Bajar un lugar",
            "✕ Quitar del panel"
        };
        // Los formularios secundarios reponen el dock al cerrar. El menu
        // principal no debe cerrarlos prematuramente desde su OnDismissListener.
        final boolean[] openingChild = {false};
        AlertDialog dialog = new AlertDialog.Builder(this)
                .setTitle(AppStore.label(this, packageName))
                .setItems(choices, (d, option) -> {
                    if (option == 0) {
                        openingChild[0] = true;
                        showPicker();
                    } else if (option == 3) {
                        openingChild[0] = true;
                        showRemoveDialog(packageName);
                    } else {
                        int direction = option == 1 ? -1 : 1;
                        if (!AppStore.move(this, packageName, direction)) {
                            Toast.makeText(this,
                                    direction == -1 ? "Ya está en el primer lugar"
                                            : "Ya está en el último lugar",
                                    Toast.LENGTH_SHORT).show();
                        }
                        restoreAndFinish();
                    }
                })
                .setNegativeButton("Cancelar", null)
                .create();
        dialog.setOnDismissListener(d -> {
            if (!openingChild[0]) restoreAndFinish();
        });
        dialog.show();
    }

    private void showRemoveDialog(String packageName) {
        if (packageName == null || packageName.trim().isEmpty()) {
            restoreAndFinish();
            return;
        }
        String label = AppStore.label(this, packageName);
        new AlertDialog.Builder(this)
                .setTitle("Quitar del panel")
                .setMessage("¿Quitar " + label + " del lado derecho? La aplicación no se desinstalará.")
                .setPositiveButton("Quitar", (dialog, which) ->
                        AppStore.remove(this, packageName))
                .setNegativeButton("Cancelar", null)
                .setOnDismissListener(dialog -> restoreAndFinish())
                .show();
    }
}
