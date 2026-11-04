package com.archmoba.colibri;

/**
 * Regla determinista para saber si una notificacion es posterior
 * a la ultima pulsacion que el usuario hizo sobre el acceso.
 * Sin dependencias Android para probar con javac.
 */
final class BadgeFreshnessPolicy {
    static boolean isNew(long notificationPostedAt, long lastOpenedAt) {
        return notificationPostedAt > 0L && notificationPostedAt > lastOpenedAt;
    }

    private BadgeFreshnessPolicy() {}
}
