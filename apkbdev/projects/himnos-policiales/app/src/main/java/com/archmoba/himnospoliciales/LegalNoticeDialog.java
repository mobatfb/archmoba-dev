package com.archmoba.himnospoliciales;

import android.app.Activity;
import android.app.Dialog;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.ColorDrawable;
import android.graphics.drawable.GradientDrawable;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.Window;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

/** Aviso legal local e independiente de la publicidad. */
final class LegalNoticeDialog {
    private static final String TITLE = "HIMNOS POLICIALES — AVISO LEGAL";
    private static final String BODY =
            "Aplicación gratuita e independiente, desarrollada para facilitar el acceso a himnos utilizados durante ceremonias, formaciones y eventos protocolarios.\n\n"
            + "Los derechos correspondientes a las composiciones, interpretaciones y grabaciones musicales pertenecen a sus respectivos titulares.\n\n"
            + "Esta aplicación no representa ni implica respaldo oficial de la Policía Nacional del Ecuador. Cualquier consulta o reclamación relacionada con los contenidos podrá remitirse al correo de contacto del desarrollador para su revisión y atención.";

    private LegalNoticeDialog() { }

    static void show(Activity activity) {
        if (activity.isFinishing() || activity.isDestroyed()) return;
        Dialog dialog = new Dialog(activity);
        dialog.setCancelable(true);

        LinearLayout panel = new LinearLayout(activity);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(activity, 20), dp(activity, 20),
                dp(activity, 20), dp(activity, 16));
        GradientDrawable panelBackground = new GradientDrawable(
                GradientDrawable.Orientation.TOP_BOTTOM,
                new int[]{0xFF103B65, 0xFF061B34});
        panelBackground.setCornerRadius(dp(activity, 18));
        panelBackground.setStroke(dp(activity, 2), 0xFFDABB67);
        panel.setBackground(panelBackground);

        TextView title = new TextView(activity);
        title.setText(TITLE);
        title.setTextColor(0xFFFFE4A0);
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 18);
        title.setTypeface(Typeface.create("sans-serif", Typeface.BOLD));
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 0, 0, dp(activity, 14));
        panel.addView(title, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT));

        ScrollView scroll = new ScrollView(activity);
        scroll.setVerticalScrollBarEnabled(true);
        TextView text = new TextView(activity);
        text.setText(BODY);
        text.setTextColor(Color.WHITE);
        text.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        text.setLineSpacing(dp(activity, 3), 1.0f);
        text.setTextIsSelectable(true);
        scroll.addView(text, new ScrollView.LayoutParams(
                ScrollView.LayoutParams.MATCH_PARENT, ScrollView.LayoutParams.WRAP_CONTENT));
        // Solo el cuerpo se desplaza: el título y CERRAR siempre permanecen visibles.
        int height = Math.min(dp(activity, 370),
                Math.round(activity.getResources().getDisplayMetrics().heightPixels * .48f));
        panel.addView(scroll, new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, height));

        TextView close = new TextView(activity);
        close.setText("CERRAR");
        close.setContentDescription("Cerrar aviso legal");
        close.setGravity(Gravity.CENTER);
        close.setTextSize(TypedValue.COMPLEX_UNIT_SP, 14);
        close.setTextColor(0xFF0B2649);
        close.setTypeface(Typeface.create("sans-serif-medium", Typeface.BOLD));
        close.setMinHeight(dp(activity, 48));
        GradientDrawable closeBackground = new GradientDrawable();
        closeBackground.setColor(0xFFE8C878);
        closeBackground.setCornerRadius(dp(activity, 12));
        close.setBackground(closeBackground);
        LinearLayout.LayoutParams closePosition = new LinearLayout.LayoutParams(
                LinearLayout.LayoutParams.MATCH_PARENT, LinearLayout.LayoutParams.WRAP_CONTENT);
        closePosition.topMargin = dp(activity, 17);
        panel.addView(close, closePosition);
        close.setOnClickListener(v -> dialog.dismiss());

        dialog.setContentView(panel);
        Window win = dialog.getWindow();
        if (win != null) {
            win.setBackgroundDrawable(new ColorDrawable(Color.TRANSPARENT));
            win.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
            win.setDimAmount(.70f);
            win.setGravity(Gravity.CENTER);
        }
        dialog.show();
        win = dialog.getWindow();
        if (win != null) {
            int width = Math.min(dp(activity, 520),
                    Math.round(activity.getResources().getDisplayMetrics().widthPixels * .92f));
            win.setLayout(width, WindowManager.LayoutParams.WRAP_CONTENT);
        }
    }

    private static int dp(Activity activity, int amount) {
        return Math.round(amount * activity.getResources().getDisplayMetrics().density);
    }
}
