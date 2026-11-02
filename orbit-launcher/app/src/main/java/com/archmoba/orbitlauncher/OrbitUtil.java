package com.archmoba.orbitlauncher;

import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.view.Gravity;
import android.widget.ImageView;
import android.widget.Toast;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Set;

final class OrbitUtil {
    static final int CYAN = Color.rgb(30, 211, 255);
    static final int BG = Color.rgb(6, 13, 24);
    static final int PANEL = Color.rgb(18, 33, 52);

    static int dp(Context context, float v) {
        return (int) (v * context.getResources().getDisplayMetrics().density + .5f);
    }

    static GradientDrawable background(Context context, int color, int border, float radius) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(context, radius));
        if (border != Color.TRANSPARENT) d.setStroke(dp(context, 2), border);
        return d;
    }

    static List<ResolveInfo> apps(Context context) {
        PackageManager pm = context.getPackageManager();
        Intent intent = new Intent(Intent.ACTION_MAIN);
        intent.addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> all = pm.queryIntentActivities(intent, 0);
        List<ResolveInfo> result = new ArrayList<>();
        Set<String> unique = new HashSet<>();
        for (ResolveInfo ri : all) {
            if (ri.activityInfo == null) continue;
            String pkg = ri.activityInfo.packageName;
            if (!pkg.equals(context.getPackageName()) && unique.add(pkg)) result.add(ri);
        }
        Collections.sort(result, (a, b) -> String.valueOf(a.loadLabel(pm))
                .compareToIgnoreCase(String.valueOf(b.loadLabel(pm))));
        return result;
    }

    static ImageView appIcon(Context c, ResolveInfo ri, int dimension) {
        ImageView iv = new ImageView(c);
        iv.setImageDrawable(ri.loadIcon(c.getPackageManager()));
        iv.setScaleType(ImageView.ScaleType.FIT_CENTER);
        iv.setPadding(dp(c, 8), dp(c, 8), dp(c, 8), dp(c, 8));
        iv.setBackground(background(c, PANEL, CYAN, 15));
        iv.setContentDescription(String.valueOf(ri.loadLabel(c.getPackageManager())));
        iv.setClickable(true);
        return iv;
    }

    static boolean launch(Context c, String pkg) {
        try {
            Intent intent = c.getPackageManager().getLaunchIntentForPackage(pkg);
            if (intent == null) {
                Toast.makeText(c, "No es posible abrir esta app", Toast.LENGTH_SHORT).show();
                return false;
            }
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
            c.startActivity(intent);
            return true;
        } catch (Exception ex) {
            Toast.makeText(c, "Error al abrir la aplicación", Toast.LENGTH_SHORT).show();
            return false;
        }
    }
}
