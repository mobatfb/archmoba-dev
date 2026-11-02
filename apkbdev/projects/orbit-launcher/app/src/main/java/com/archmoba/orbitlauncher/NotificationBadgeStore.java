package com.archmoba.orbitlauncher;

import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import org.json.JSONObject;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/** Solo almacena paquetes, fechas de apertura y un estado booleano local. */
final class NotificationBadgeStore {
    static final String ACTION_CHANGED = "com.archmoba.orbitlauncher.BADGE_CHANGED";
    private static final String PREFS = "orbit_live_notification_badges";
    private static final String PENDING = "pending_packages";
    private static final String LAST_OPEN = "last_open_by_package";

    static boolean pending(Context context, String pkg) {
        return preferences(context).getStringSet(PENDING, Collections.emptySet()).contains(pkg);
    }

    static synchronized long lastOpen(Context context, String pkg) {
        try {
            JSONObject data = new JSONObject(preferences(context).getString(LAST_OPEN, "{}"));
            return data.optLong(pkg, 0L);
        } catch (Exception ignored) {
            return 0L;
        }
    }

    /** Tocar el icono apaga el punto sin borrar la notificacion real de Android. */
    static synchronized void acknowledge(Context context, String pkg) {
        if (pkg == null || pkg.isEmpty()) return;
        SharedPreferences prefs = preferences(context);
        JSONObject json;
        try { json = new JSONObject(prefs.getString(LAST_OPEN, "{}")); }
        catch (Exception ignored) { json = new JSONObject(); }
        try { json.put(pkg, System.currentTimeMillis()); }
        catch (Exception ignored) {}
        Set<String> set = new HashSet<>(prefs.getStringSet(PENDING, Collections.emptySet()));
        set.remove(pkg);
        // apply() actualiza inmediatamente el estado en memoria y guarda a disco
        // sin bloquear el toque que abre la aplicacion.
        prefs.edit().putString(LAST_OPEN, json.toString()).putStringSet(PENDING, set).apply();
        notifyDock(context);
    }

    static synchronized void mark(Context context, String pkg, long postedAt) {
        if (pkg == null || !BadgeFreshnessPolicy.isNew(postedAt, lastOpen(context, pkg))) return;
        SharedPreferences prefs = preferences(context);
        Set<String> set = new HashSet<>(prefs.getStringSet(PENDING, Collections.emptySet()));
        if (set.add(pkg)) {
            prefs.edit().putStringSet(PENDING, set).apply();
            notifyDock(context);
        }
    }

    /**
     * Actualizacion unica del estado tras el desbloqueo.
     * Solo conserva apps con notificaciones activas POSTERIORES al ultimo toque.
     * Un mensaje anterior no puede volver a encender el indicador.
     */
    static synchronized void reconcile(Context context, Set<String> activeNewPackages) {
        SharedPreferences prefs = preferences(context);
        Set<String> updated = new HashSet<>(activeNewPackages);
        Set<String> current = prefs.getStringSet(PENDING, Collections.emptySet());
        if (current.equals(updated)) return;
        prefs.edit().putStringSet(PENDING, updated).apply();
        notifyDock(context);
    }

    /** Se utiliza al retirarse la ultima notificacion nueva de una app. */
    static synchronized void clear(Context context, String pkg) {
        SharedPreferences prefs = preferences(context);
        Set<String> set = new HashSet<>(prefs.getStringSet(PENDING, Collections.emptySet()));
        if (set.remove(pkg)) {
            prefs.edit().putStringSet(PENDING, set).apply();
            notifyDock(context);
        }
    }

    private static SharedPreferences preferences(Context c) {
        return c.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private static void notifyDock(Context c) {
        Intent changed = new Intent(ACTION_CHANGED).setPackage(c.getPackageName());
        c.sendBroadcast(changed);
    }

    private NotificationBadgeStore() {}
}
