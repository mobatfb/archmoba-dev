package __APPLICATION_ID__;

import android.app.Activity;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.view.Gravity;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

public final class MainActivity extends Activity {
    private int dp(float n) {
        return (int) (n * getResources().getDisplayMetrics().density + .5f);
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(Color.rgb(4, 9, 20));
        getWindow().setNavigationBarColor(Color.rgb(4, 9, 20));

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(dp(25), dp(25), dp(25), dp(25));
        root.setBackgroundColor(Color.rgb(6, 14, 27));

        TextView title = new TextView(this);
        title.setText("ARCHMOBA · APKBDEV");
        title.setTextColor(Color.rgb(40, 215, 255));
        title.setTypeface(null, 1);
        title.setTextSize(22);
        title.setGravity(Gravity.CENTER);
        root.addView(title, new LinearLayout.LayoutParams(-1, dp(60)));

        TextView caption = new TextView(this);
        caption.setText("Nueva aplicación Android\nPlantilla nativa Java");
        caption.setGravity(Gravity.CENTER);
        caption.setTextColor(Color.WHITE);
        caption.setTextSize(17);
        root.addView(caption, new LinearLayout.LayoutParams(-1, dp(95)));

        TextView button = new TextView(this);
        button.setText("PROBAR APLICACIÓN");
        button.setTextColor(Color.rgb(40, 215, 255));
        button.setTypeface(null, 1);
        button.setGravity(Gravity.CENTER);
        GradientDrawable background = new GradientDrawable();
        background.setColor(Color.rgb(17, 30, 48));
        background.setCornerRadius(dp(14));
        background.setStroke(dp(2), Color.rgb(40, 215, 255));
        button.setBackground(background);
        root.addView(button, new LinearLayout.LayoutParams(-1, dp(54)));
        button.setOnClickListener(v ->
                Toast.makeText(this, "APKBDEV funcionando", Toast.LENGTH_SHORT).show());

        setContentView(root);
    }
}
