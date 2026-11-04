package com.archmoba.colibri;

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

    /**
     * Esfera de vidrio: siempre OVAL, con un gradiente translucido de
     * blanco-azul en la parte superior a azul marino en la inferior.
     *
     * La opacidad del contenido completo (incluido el icono o el signo "+")
     * se aplica en DockService mediante View.setAlpha(0.55f).
     */
    static GradientDrawable bubble(Context context, boolean plus) {
        GradientDrawable shape = new GradientDrawable(
                GradientDrawable.Orientation.TL_BR,
                new int[] {
                    Color.argb(140, 54, 82, 107),
                    Color.argb(160, 7, 16, 32)
                });
        shape.setShape(GradientDrawable.OVAL);
        shape.setStroke(dp(context, 2), Color.argb(190, 27, 207, 255));
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
