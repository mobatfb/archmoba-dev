package com.archmoba.orbitlauncher;

import android.content.Context;
import android.content.Intent;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.widget.Toast;

final class OrbitUtil {
    static final int CYAN = Color.rgb(27, 207, 255);
    static final int SURFACE = Color.rgb(7, 16, 32);

    static int dp(Context context, float size) {
        return (int) (size * context.getResources().getDisplayMetrics().density + 0.5f);
    }

    static GradientDrawable bubble(Context context, boolean plus) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(SURFACE);
        shape.setCornerRadius(dp(context, plus ? 28 : 18));
        shape.setStroke(dp(context, 2), CYAN);
        return shape;
    }

    static boolean launch(Context context, String packageName) {
        try {
            Intent intent = context.getPackageManager()
                    .getLaunchIntentForPackage(packageName);
            if (intent == null) {
                Toast.makeText(context, "La app ya no está disponible",
                        Toast.LENGTH_SHORT).show();
                return false;
            }
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK
                    | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
            context.startActivity(intent);
            return true;
        } catch (Exception ignored) {
            Toast.makeText(context, "Android no permitió abrir la app",
                    Toast.LENGTH_SHORT).show();
            return false;
        }
    }

    private OrbitUtil() {}
}
