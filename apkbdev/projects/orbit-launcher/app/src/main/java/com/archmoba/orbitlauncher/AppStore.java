package com.archmoba.orbitlauncher;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import org.json.JSONArray;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

/**
 * El usuario controla explicitamente cuales apps aparecen en el dock.
 * Primera instalacion: lista vacia; solo aparece el boton "+".
 */
final class AppStore {
    private static final String PREFS = "orbit_dock_preferences";
    private static final String KEY = "selected_packages";

    static List<String> selected(Context context) {
        String data = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getString(KEY, "[]");
        List<String> values = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        try {
            JSONArray array = new JSONArray(data);
            for (int i = 0; i < array.length(); i++) {
                String item = array.optString(i, "");
                if (!item.isEmpty() && seen.add(item)) values.add(item);
            }
        } catch (Exception ignored) {
            // Si las preferencias se corrompen, mostrar solo "+" en lugar de fallar.
        }
        return values;
    }

    static boolean add(Context context, String packageName) {
        if (packageName == null || packageName.isEmpty()) return false;
        if (context.getPackageManager().getLaunchIntentForPackage(packageName) == null)
            return false;
        List<String> values = selected(context);
        if (values.contains(packageName)) return false;
        values.add(packageName);
        write(context, values);
        return true;
    }

    /** Reordena un icono exactamente una posición: -1 arriba, +1 abajo. */
    static boolean move(Context context, String packageName, int direction) {
        if (direction != -1 && direction != 1) return false;
        List<String> values = selected(context);
        int index = values.indexOf(packageName);
        int destination = index + direction;
        if (index < 0 || destination < 0 || destination >= values.size()) return false;
        Collections.swap(values, index, destination);
        write(context, values);
        return true;
    }

    static void remove(Context context, String packageName) {
        List<String> values = selected(context);
        if (values.remove(packageName)) write(context, values);
    }

    static List<ResolveInfo> available(Context context) {
        PackageManager pm = context.getPackageManager();
        Intent intent = new Intent(Intent.ACTION_MAIN);
        intent.addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> all = pm.queryIntentActivities(intent, 0);
        List<ResolveInfo> result = new ArrayList<>();
        Set<String> seen = new HashSet<>(selected(context));
        seen.add(context.getPackageName());
        for (ResolveInfo info : all) {
            if (info.activityInfo == null) continue;
            String pkg = info.activityInfo.packageName;
            if (seen.add(pkg)) result.add(info);
        }
        Collections.sort(result, (a, b) -> String.valueOf(a.loadLabel(pm))
                .compareToIgnoreCase(String.valueOf(b.loadLabel(pm))));
        return result;
    }

    static String label(Context context, String packageName) {
        try {
            PackageManager pm = context.getPackageManager();
            return pm.getApplicationLabel(pm.getApplicationInfo(packageName, 0))
                    .toString();
        } catch (Exception ignored) {
            return packageName;
        }
    }

    private static void write(Context context, List<String> selected) {
        JSONArray array = new JSONArray();
        for (String pkg : selected) array.put(pkg);
        SharedPreferences preferences = context.getSharedPreferences(
                PREFS, Context.MODE_PRIVATE);
        preferences.edit().putString(KEY, array.toString()).apply();
    }

    private AppStore() {}
}
