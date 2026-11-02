package com.archmoba.orbitlauncher;

public final class BadgeFreshnessTest {
    private static void test(boolean condition, String name) {
        if (!condition) throw new AssertionError(name);
    }

    public static void main(String[] args) {
        test(BadgeFreshnessPolicy.isNew(110L, 100L), "nueva notificacion");
        test(!BadgeFreshnessPolicy.isNew(100L, 100L), "mismo instante");
        test(!BadgeFreshnessPolicy.isNew(99L, 100L), "notificacion anterior");
        test(!BadgeFreshnessPolicy.isNew(0L, 100L), "sin marca de tiempo");
        test(BadgeFreshnessPolicy.isNew(110L, 0L), "primera notificacion");
        System.out.println("OK: 5 pruebas de novedades");
    }
}
