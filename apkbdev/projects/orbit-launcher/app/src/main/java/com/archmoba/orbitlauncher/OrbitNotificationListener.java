package com.archmoba.orbitlauncher;

import android.app.Notification;
import android.service.notification.NotificationListenerService;
import android.service.notification.StatusBarNotification;
import java.util.HashSet;
import java.util.Set;

/**
 * Acceso OPCIONAL que Android habilita solo con aprobacion explicita.
 * El punto verde refleja notificaciones activas, no mensajes necesariamente sin leer.
 * Solo almacenamos identificadores de aplicaciones: nunca leemos texto ni extras.
 */
public final class OrbitNotificationListener extends NotificationListenerService {
    @Override public void onListenerConnected() {
        super.onListenerConnected();
        refresh();
    }

    @Override public void onNotificationPosted(StatusBarNotification sbn) {
        refresh();
    }

    @Override public void onNotificationRemoved(StatusBarNotification sbn) {
        refresh();
    }

    @Override public void onListenerDisconnected() {
        NotificationBadgeStore.update(this, new HashSet<>());
        super.onListenerDisconnected();
    }

    private void refresh() {
        Set<String> activePackages = new HashSet<>();
        try {
            StatusBarNotification[] active = getActiveNotifications();
            if (active != null) {
                for (StatusBarNotification sbn : active) {
                    if (sbn == null || sbn.getPackageName() == null) continue;
                    if (getPackageName().equals(sbn.getPackageName())) continue;
                    Notification item = sbn.getNotification();
                    if (item == null) continue;

                    // Evitar "novedades" falsas por servicios persistentes,
                    // reproduccion, llamadas o resumenes de grupos.
                    int flags = item.flags;
                    if ((flags & Notification.FLAG_ONGOING_EVENT) != 0
                            || (flags & Notification.FLAG_GROUP_SUMMARY) != 0
                            || (flags & Notification.FLAG_FOREGROUND_SERVICE) != 0) {
                        continue;
                    }
                    String category = item.category;
                    if (Notification.CATEGORY_SERVICE.equals(category)
                            || Notification.CATEGORY_TRANSPORT.equals(category)
                            || Notification.CATEGORY_CALL.equals(category)
                            || Notification.CATEGORY_PROGRESS.equals(category)
                            || Notification.CATEGORY_NAVIGATION.equals(category)) {
                        continue;
                    }

                    activePackages.add(sbn.getPackageName());
                }
            }
        } catch (SecurityException | IllegalStateException ignored) {
            // Si Android revoca el acceso, el estado se limpiara.
        }
        NotificationBadgeStore.update(this, activePackages);
    }
}
