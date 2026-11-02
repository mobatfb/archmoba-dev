package com.archmoba.orbitlauncher;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.graphics.PixelFormat;
import android.hardware.display.DisplayManager;
import android.hardware.display.VirtualDisplay;
import android.media.Image;
import android.media.ImageReader;
import android.media.projection.MediaProjection;
import android.media.projection.MediaProjectionManager;
import android.os.Build;
import android.os.Handler;
import android.os.HandlerThread;
import android.os.IBinder;
import android.os.Looper;
import android.os.SystemClock;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.widget.ImageView;
import android.widget.TextView;
import android.widget.Toast;
import java.nio.ByteBuffer;

public final class CaptureService extends Service {
    private MediaProjection projection;
    private VirtualDisplay virtualDisplay;
    private ImageReader reader;
    private HandlerThread thread;
    private Handler mainHandler = new Handler(Looper.getMainLooper());
    private WindowManager windowManager;
    private View previewWindow;
    private ImageView preview;
    private volatile long lastFrame = 0;
    private volatile boolean stopping = false;

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (projection != null || intent == null) return START_NOT_STICKY;
        if (Build.VERSION.SDK_INT < 34 || !android.provider.Settings.canDrawOverlays(this)) {
            stopSelf();
            return START_NOT_STICKY;
        }
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        nm.createNotificationChannel(new NotificationChannel(
                "orbit_mirror", "Orbit transmisión de pantalla", NotificationManager.IMPORTANCE_LOW));
        Notification notification = new Notification.Builder(this, "orbit_mirror")
                .setSmallIcon(android.R.drawable.ic_menu_camera)
                .setContentTitle("Orbit · transmisión en directo")
                .setContentText("La app seleccionada se muestra en el visor central")
                .setOngoing(true).build();

        try {
            if (Build.VERSION.SDK_INT >= 29) {
                startForeground(1002, notification,
                        ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
            } else startForeground(1002, notification);

            MediaProjectionManager pm = (MediaProjectionManager)
                    getSystemService(MEDIA_PROJECTION_SERVICE);
            Intent data = (Intent) intent.getParcelableExtra("data");
            if (data == null) { stopSelf(); return START_NOT_STICKY; }
            projection = pm.getMediaProjection(intent.getIntExtra("code", -1), data);
            if (projection == null) { stopSelf(); return START_NOT_STICKY; }
            projection.registerCallback(new MediaProjection.Callback() {
                @Override public void onStop() { stopSelf(); }
            }, mainHandler);
            initialize();
        } catch (Exception e) {
            Toast.makeText(this, "No se pudo iniciar la transmisión", Toast.LENGTH_LONG).show();
            stopSelf();
        }
        return START_NOT_STICKY;
    }

    private void initialize() {
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
        DisplayMetrics dm = new DisplayMetrics();
        windowManager.getDefaultDisplay().getRealMetrics(dm);
        int fullW = dm.widthPixels;
        int fullH = dm.heightPixels;
        int marginX = OrbitUtil.dp(this, 68);
        int marginY = OrbitUtil.dp(this, 79);
        int viewportW = Math.max(100, fullW - 2 * marginX);
        int viewportH = Math.max(200, fullH - 2 * marginY);

        FrameLayout frame = new FrameLayout(this);
        frame.setBackground(OrbitUtil.background(this, Color.BLACK, OrbitUtil.CYAN, 16));
        ImageView image = new ImageView(this);
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setBackgroundColor(Color.BLACK);
        FrameLayout.LayoutParams ivp = new FrameLayout.LayoutParams(-1, -1);
        int inset = OrbitUtil.dp(this, 3);
        ivp.setMargins(inset, inset, inset, inset);
        frame.addView(image, ivp);
        preview = image;

        TextView label = new TextView(this);
        label.setText("● EN VIVO · SOLO VISUALIZACIÓN");
        label.setTextColor(OrbitUtil.CYAN);
        label.setBackgroundColor(0xCC071423);
        label.setTextSize(10);
        label.setPadding(OrbitUtil.dp(this, 8), OrbitUtil.dp(this, 5),
                OrbitUtil.dp(this, 8), OrbitUtil.dp(this, 5));
        FrameLayout.LayoutParams labelp = new FrameLayout.LayoutParams(-2, -2,
                Gravity.TOP | Gravity.CENTER_HORIZONTAL);
        frame.addView(label, labelp);

        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                viewportW, viewportH, WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.LEFT;
        lp.x = marginX;
        lp.y = marginY;
        windowManager.addView(frame, lp);
        previewWindow = frame;

        thread = new HandlerThread("orbit-projection-reader");
        thread.start();
        reader = ImageReader.newInstance(fullW, fullH, PixelFormat.RGBA_8888, 2);
        reader.setOnImageAvailableListener(r -> handleFrame(r, viewportW), new Handler(thread.getLooper()));
        virtualDisplay = projection.createVirtualDisplay("OrbitLive", fullW, fullH,
                dm.densityDpi, DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                reader.getSurface(), null, null);
    }

    private void handleFrame(ImageReader source, int vw) {
        Image image = null;
        try {
            image = source.acquireLatestImage();
            if (image == null) return;
            long now = SystemClock.elapsedRealtime();
            if (now - lastFrame < 180 || stopping) return;
            lastFrame = now;
            Image.Plane plane = image.getPlanes()[0];
            ByteBuffer buffer = plane.getBuffer();
            int rowStride = plane.getRowStride();
            int pixelStride = plane.getPixelStride();
            int w = image.getWidth();
            int h = image.getHeight();
            int paddedW = rowStride / pixelStride;
            Bitmap padded = Bitmap.createBitmap(paddedW, h, Bitmap.Config.ARGB_8888);
            padded.copyPixelsFromBuffer(buffer);
            Bitmap cropped = Bitmap.createBitmap(padded, 0, 0, w, h);
            if (cropped != padded) padded.recycle();
            int thumbW = Math.min(Math.max(vw, 200), 720);
            int thumbH = Math.max(1, (int) ((float) h * thumbW / w));
            Bitmap scaled = Bitmap.createScaledBitmap(cropped, thumbW, thumbH, true);
            if (scaled != cropped) cropped.recycle();
            mainHandler.post(() -> {
                if (!stopping && preview != null) preview.setImageBitmap(scaled);
                else scaled.recycle();
            });
        } catch (Exception ignored) {
        } finally {
            if (image != null) image.close();
        }
    }

    @Override public void onDestroy() {
        stopping = true;
        if (virtualDisplay != null) { virtualDisplay.release(); virtualDisplay = null; }
        if (reader != null) { reader.close(); reader = null; }
        if (thread != null) { thread.quitSafely(); thread = null; }
        if (windowManager != null && previewWindow != null) {
            try { windowManager.removeViewImmediate(previewWindow); } catch (Exception ignored) {}
            previewWindow = null;
            preview = null;
        }
        if (projection != null) {
            MediaProjection p = projection;
            projection = null;
            try { p.stop(); } catch (Exception ignored) {}
        }
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
