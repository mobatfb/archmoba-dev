package com.archmoba.mingatv;

import android.app.Activity;
import android.content.Intent;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.Gravity;
import android.widget.FrameLayout;
import android.widget.ImageView;

/**
 * Splash de MINGA TV: usa el PNG ORIGINAL, sin la mascara de iconos de Android 12.
 * Solo este Activity muestra la bienvenida; MainActivity conserva su funcionamiento.
 */
public final class SplashActivity extends Activity {
    private static final long SPLASH_DURATION_MS = 2000L;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean launched = false;
    private final Runnable openApp = () -> {
        if (launched || isFinishing() || isDestroyed()) return;
        launched = true;
        startActivity(new Intent(this, MainActivity.class));
        overridePendingTransition(0, 0);
        finish();
    };

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.BLACK);
        getWindow().setNavigationBarColor(Color.BLACK);

        FrameLayout screen = new FrameLayout(this);
        screen.setBackgroundColor(Color.BLACK);

        ImageView logo = new ImageView(this);
        // FIT_CENTER respeta toda la imagen rectangular (348 x 232, proporcion 3:2).
        // A diferencia del sistema, no aplica ninguna mascara circular ni recorte.
        logo.setImageResource(R.drawable.minga_tv_logo);
        logo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        logo.setAdjustViewBounds(true);

        int width = Math.max(dp(180),
                Math.min(getResources().getDisplayMetrics().widthPixels - dp(36),
                        dp(430)));
        int height = Math.round(width * 232f / 348f);
        FrameLayout.LayoutParams params =
                new FrameLayout.LayoutParams(width, height, Gravity.CENTER);
        screen.addView(logo, params);
        setContentView(screen);

        handler.postDelayed(openApp, SPLASH_DURATION_MS);
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    @Override
    protected void onDestroy() {
        handler.removeCallbacks(openApp);
        super.onDestroy();
    }
}
