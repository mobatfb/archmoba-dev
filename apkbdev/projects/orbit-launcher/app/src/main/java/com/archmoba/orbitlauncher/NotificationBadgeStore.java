package com.archmoba.orbitlauncher;

import android.app.NotificationManager;
import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.os.Build;
import android.provider.Settings;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.Set;

/**
 * Estado local de los puntos verdes. Solo almacena nombres de paquetes
 * con al menos una notificacion activa. Nunca almacena mensajes ni texto.
 */
final class NotificationBadgeStore {
    static final String ACTION_CHANGED =
            "com.archmoba.orbitlauncher.NOTIFICATION_BADGES_CHANGED";

    private static final String PREFS = "orbit_notification_indicators";
    private static final String KEY_PACKAGES = "active_packages";
    private static final String KEY_OFFERED = "access_offered";

    static boolean hasAccess(Context context) {
        ComponentName component = new ComponentName(
                context, OrbitNotificationListener.class);
        if (Build.VERSION.SDK_INT >= 27) {
            NotificationManager manager = (NotificationManager)
                    context.getSystemService(Context.NOTIFICATION_SERVICE);
            return manager != null
                    && manager.isNotificationListenerAccessGranted(component);
        }
        String listeners = Settings.Secure.getString(
                context.getContentResolver(), "enabled_notification_listeners");
        return listeners != null
                && Arrays.asList(listeners.split(":"))
                        .contains(component.flattenToString());
    }

    static boolean hasNotifications(Context context, String packageName) {
        if (packageName == null || !hasAccess(context)) return false;
        return preferences(context)
                .getStringSet(KEY_PACKAGES, Collections.emptySet())
                .contains(packageName);
    }

    static boolean shouldOffer(Context context) {
        return !preferences(context).getBoolean(KEY_OFFERED, false);
    }

    static void markOffered(Context context) {
        preferences(context).edit().putBoolean(KEY_OFFERED, true).apply();
    }

    static void update(Context context, Set<String> packages) {
        Set<String> fresh = new HashSet<>(packages);
        SharedPreferences preferences = preferences(context);
        Set<String> previous = preferences.getStringSet(
                KEY_PACKAGES, Collections.emptySet());
        if (fresh.equals(previous)) return;

        preferences.edit().putStringSet(KEY_PACKAGES, fresh).apply();

        // El receptor es dinamico y solo existe dentro de Orbit.
        Intent changed = new Intent(ACTION_CHANGED);
        changed.setPackage(context.getPackageName());
        context.sendBroadcast(changed);
    }

    private static SharedPreferences preferences(Context context) {
        return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE);
    }

    private NotificationBadgeStore() {}
}
