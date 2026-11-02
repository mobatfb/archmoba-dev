package com.archmoba.orbitlauncher;

import android.app.Notification;
import android.os.PowerManager;
import java.util.HashSet;
import java.util.Set;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

/**
 * Solo nombres de paquetes y marcas de tiempo, nunca texto de notificaciones.
 * Al tocar una app, las notificaciones existentes ya no reactivan su punto.
 */
public final class OrbitNotificationListener extends NotificationListenerService {
    @Override public void onNotificationPosted(StatusBarNotification sbn) {
        if (!eligible(sbn) || !interactive()) return;
        NotificationBadgeStore.mark(this, sbn.getPackageName(), sbn.getPostTime());
    }

    @Override public void onNotificationRemoved(StatusBarNotification sbn) {
        if (sbn == null || !interactive()) return;
        String pkg = sbn.getPackageName();
        try {
            StatusBarNotification[] remaining = getActiveNotifications();
            if (remaining != null) {
                for (StatusBarNotification next : remaining) {
                    if (eligible(next) && pkg.equals(next.getPackageName())
                            && BadgeFreshnessPolicy.isNew(next.getPostTime(),
                                NotificationBadgeStore.lastOpen(this, pkg))) return;
                }
            }
            NotificationBadgeStore.clear(this, pkg);
        } catch (SecurityException | IllegalStateException ignored) {}
    }

    @Override public void onListenerConnected() {
        super.onListenerConnected();
        instance = this;
        // Intencionadamente NO reactivamos los puntos desde notificaciones antiguas.
        // Los nuevos eventos onNotificationPosted se procesan normalmente.
    }

    private boolean interactive() {
        PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
        return pm == null || pm.isInteractive();
    }

    /** Un solo escaneo al desbloquear; nunca reactivar notificaciones viejas. */
    static void scanOnUnlock(android.content.Context context) {
        // La consulta se ejecuta desde el listener conectado.
        synchronized (OrbitNotificationListener.class) {
            if (instance != null) instance.reconcileNow();
        }
    }

    private static volatile OrbitNotificationListener instance;

    @Override public void onDestroy() {
        if (instance == this) instance = null;
        super.onDestroy();
    }

    private void reconcileNow() {
        Set<String> active = new HashSet<>();
        if (!interactive()) return;
        try {
            StatusBarNotification[] notifications = getActiveNotifications();
            if (notifications != null) {
                for (StatusBarNotification sbn : notifications) {
                    if (eligible(sbn)
                            && BadgeFreshnessPolicy.isNew(sbn.getPostTime(),
                                NotificationBadgeStore.lastOpen(this, sbn.getPackageName()))) {
                        active.add(sbn.getPackageName());
                    }
                }
            }
            NotificationBadgeStore.reconcile(this, active);
        } catch (SecurityException | IllegalStateException ignored) {}
    }

    private boolean eligible(StatusBarNotification sbn) {
        if (sbn == null || sbn.getPackageName() == null
                || sbn.getPackageName().equals(getPackageName())) return false;
        Notification n = sbn.getNotification();
        if (n == null) return false;
        int f = n.flags;
        if ((f & (Notification.FLAG_ONGOING_EVENT | Notification.FLAG_GROUP_SUMMARY
                | Notification.FLAG_FOREGROUND_SERVICE)) != 0) return false;
        String c = n.category;
        return !Notification.CATEGORY_SERVICE.equals(c)
                && !Notification.CATEGORY_TRANSPORT.equals(c)
                && !Notification.CATEGORY_CALL.equals(c)
                && !Notification.CATEGORY_PROGRESS.equals(c)
                && !Notification.CATEGORY_NAVIGATION.equals(c);
    }
}
