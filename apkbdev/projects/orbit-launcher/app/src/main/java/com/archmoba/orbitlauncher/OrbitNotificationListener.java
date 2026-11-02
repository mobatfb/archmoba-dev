package com.archmoba.orbitlauncher;

import android.app.Notification;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;

/**
 * Solo nombres de paquetes y marcas de tiempo, nunca texto de notificaciones.
 * Al tocar una app, las notificaciones existentes ya no reactivan su punto.
 */
public final class OrbitNotificationListener extends NotificationListenerService {
    @Override public void onNotificationPosted(StatusBarNotification sbn) {
        if (!eligible(sbn)) return;
        NotificationBadgeStore.mark(this, sbn.getPackageName(), sbn.getPostTime());
    }

    @Override public void onNotificationRemoved(StatusBarNotification sbn) {
        if (sbn == null) return;
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
        // Intencionadamente NO reactivamos los puntos desde notificaciones antiguas.
        // Los nuevos eventos onNotificationPosted se procesan normalmente.
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
