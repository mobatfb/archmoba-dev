package com.archmoba.orbitlauncher;

import android.app.ActivityOptions;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.content.pm.ResolveInfo;
import android.graphics.Color;
import android.graphics.Rect;
import android.graphics.drawable.GradientDrawable;
import android.util.DisplayMetrics;
import android.view.WindowManager;
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

    static int dp(Context context, float value) {
        return (int) (value * context.getResources().getDisplayMetrics().density + .5f);
    }

    static GradientDrawable background(Context c, int color, int border, float radius) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(c, radius));
        if (border != Color.TRANSPARENT) d.setStroke(dp(c, 2), border);
        return d;
    }

    static List<ResolveInfo> apps(Context context) {
        PackageManager pm = context.getPackageManager();
        Intent intent = new Intent(Intent.ACTION_MAIN);
        intent.addCategory(Intent.CATEGORY_LAUNCHER);
        List<ResolveInfo> all = pm.queryIntentActivities(intent, 0);
        List<ResolveInfo> result = new ArrayList<>();
        Set<String> unique = new HashSet<>();
        for (ResolveInfo app : all) {
            if (app.activityInfo == null) continue;
            String pkg = app.activityInfo.packageName;
            if (!pkg.equals(context.getPackageName()) && unique.add(pkg)) result.add(app);
        }
        Collections.sort(result, (a, b) -> String.valueOf(a.loadLabel(pm))
                .compareToIgnoreCase(String.valueOf(b.loadLabel(pm))));
        return result;
    }

    static boolean supportsFreeform(Context c) {
        return c.getPackageManager().hasSystemFeature(
                PackageManager.FEATURE_FREEFORM_WINDOW_MANAGEMENT);
    }

    static ImageView appIcon(Context c, ResolveInfo app) {
        ImageView icon = new ImageView(c);
        icon.setImageDrawable(app.loadIcon(c.getPackageManager()));
        icon.setScaleType(ImageView.ScaleType.FIT_CENTER);
        icon.setPadding(dp(c, 6), dp(c, 6), dp(c, 6), dp(c, 6));
        icon.setBackground(background(c, PANEL, CYAN, 13));
        icon.setContentDescription(String.valueOf(app.loadLabel(c.getPackageManager())));
        icon.setClickable(true);
        return icon;
    }

    static boolean launch(Context c, String pkg, boolean preferCentralWindow) {
        try {
            Intent app = c.getPackageManager().getLaunchIntentForPackage(pkg);
            if (app == null) {
                Toast.makeText(c, "No se pudo encontrar esta app", Toast.LENGTH_SHORT).show();
                return false;
            }
            app.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_RESET_TASK_IF_NEEDED);
            if (preferCentralWindow && supportsFreeform(c)) {
                WindowManager wm = (WindowManager) c.getSystemService(Context.WINDOW_SERVICE);
                DisplayMetrics dm = new DisplayMetrics();
                wm.getDefaultDisplay().getRealMetrics(dm);
                int side = dp(c, 70);
                int top = dp(c, 85);
                int bottom = dp(c, 86);
                Rect bounds = new Rect(side, top, dm.widthPixels - side, dm.heightPixels - bottom);
                if (bounds.width() > dp(c, 170) && bounds.height() > dp(c, 250)) {
                    ActivityOptions options = ActivityOptions.makeBasic();
                    options.setLaunchBounds(bounds);
                    app.addFlags(Intent.FLAG_ACTIVITY_MULTIPLE_TASK);
                    c.startActivity(app, options.toBundle());
                    return true;
                }
            }
            c.startActivity(app);
            return true;
        } catch (Exception error) {
            Toast.makeText(c, "No se pudo iniciar la aplicación", Toast.LENGTH_LONG).show();
            return false;
        }
    }
}
