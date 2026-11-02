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
    private Handler captureHandler;
    private final Handler mainHandler = new Handler(Looper.getMainLooper());
    private WindowManager manager;
    private View previewWindow;
    private ImageView preview;
    private Bitmap lastShown;
    private int captureW;
    private int captureH;
    private int density;
    private int viewportWidth;
    private volatile long lastFrame;
    private volatile boolean stopping;

    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (projection != null || intent == null) return START_NOT_STICKY;
        if (Build.VERSION.SDK_INT < 34 || !android.provider.Settings.canDrawOverlays(this)) {
            stopSelf();
            return START_NOT_STICKY;
        }
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        nm.createNotificationChannel(new NotificationChannel(
                "orbit_mirror", "Orbit visor en directo", NotificationManager.IMPORTANCE_LOW));
        Notification notification = new Notification.Builder(this, "orbit_mirror")
                .setSmallIcon(android.R.drawable.ic_menu_camera)
                .setContentTitle("Orbit · app compartida")
                .setContentText("Transmisión visible en el recuadro central")
                .setOngoing(true).build();
        try {
            startForeground(1002, notification,
                    ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION);
            MediaProjectionManager pm = (MediaProjectionManager)
                    getSystemService(MEDIA_PROJECTION_SERVICE);
            Intent data = (Intent) intent.getParcelableExtra("data");
            if (data == null) { stopSelf(); return START_NOT_STICKY; }
            projection = pm.getMediaProjection(intent.getIntExtra("code", -1), data);
            if (projection == null) { stopSelf(); return START_NOT_STICKY; }
            projection.registerCallback(new MediaProjection.Callback() {
                @Override public void onStop() { stopSelf(); }

                @Override public void onCapturedContentResize(int width, int height) {
                    if (width > 0 && height > 0 && !stopping) {
                        mainHandler.post(() -> resizeCapture(width, height));
                    }
                }
            }, mainHandler);
            initialize();
        } catch (Exception e) {
            Toast.makeText(this, "No se pudo compartir esta aplicación", Toast.LENGTH_LONG).show();
            stopSelf();
        }
        return START_NOT_STICKY;
    }

    private void initialize() {
        manager = (WindowManager) getSystemService(WINDOW_SERVICE);
        DisplayMetrics dm = new DisplayMetrics();
        manager.getDefaultDisplay().getRealMetrics(dm);
        captureW = dm.widthPixels;
        captureH = dm.heightPixels;
        density = dm.densityDpi;
        int side = OrbitUtil.dp(this, 65);
        int vertical = OrbitUtil.dp(this, 70);
        viewportWidth = Math.max(100, dm.widthPixels - side * 2);
        int viewportHeight = Math.max(200, dm.heightPixels - vertical * 2);

        FrameLayout frame = new FrameLayout(this);
        frame.setBackground(OrbitUtil.background(this, Color.BLACK, OrbitUtil.CYAN, 15));
        ImageView image = new ImageView(this);
        image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setBackgroundColor(Color.BLACK);
        FrameLayout.LayoutParams p = new FrameLayout.LayoutParams(-1, -1);
        int inset = OrbitUtil.dp(this, 3);
        p.setMargins(inset, inset, inset, inset);
        frame.addView(image, p);
        preview = image;

        TextView label = new TextView(this);
        label.setText("● VISOR · TRANSMISIÓN · SIN CONTROL TÁCTIL");
        label.setTextColor(OrbitUtil.CYAN);
        label.setTextSize(9);
        label.setBackgroundColor(0xCC071423);
        label.setPadding(OrbitUtil.dp(this, 6), OrbitUtil.dp(this, 4),
                OrbitUtil.dp(this, 6), OrbitUtil.dp(this, 4));
        frame.addView(label, new FrameLayout.LayoutParams(
                -2, -2, Gravity.TOP | Gravity.CENTER_HORIZONTAL));

        WindowManager.LayoutParams lp = new WindowManager.LayoutParams(
                viewportWidth, viewportHeight,
                WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
                WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                        | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                        | WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
                PixelFormat.TRANSLUCENT);
        lp.gravity = Gravity.TOP | Gravity.LEFT;
        lp.x = side;
        lp.y = vertical;
        manager.addView(frame, lp);
        previewWindow = frame;

        thread = new HandlerThread("orbit-media-projection");
        thread.start();
        captureHandler = new Handler(thread.getLooper());
        createReader(captureW, captureH);
        virtualDisplay = projection.createVirtualDisplay(
                "Orbit selected application", captureW, captureH, density,
                DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
                reader.getSurface(), null, null);
    }

    private void createReader(int width, int height) {
        reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2);
        reader.setOnImageAvailableListener(r -> handleFrame(r), captureHandler);
    }

    private void resizeCapture(int width, int height) {
        if (stopping || width == captureW && height == captureH) return;
        captureW = width;
        captureH = height;
        if (virtualDisplay == null || captureHandler == null) return;
        ImageReader old = reader;
        createReader(width, height);
        virtualDisplay.resize(width, height, density);
        virtualDisplay.setSurface(reader.getSurface());
        if (old != null) {
            old.setOnImageAvailableListener(null, null);
            old.close();
        }
    }

    private void handleFrame(ImageReader source) {
        Image image = null;
        try {
            image = source.acquireLatestImage();
            if (image == null || stopping) return;
            long now = SystemClock.elapsedRealtime();
            if (now - lastFrame < 140) return;
            lastFrame = now;
            Image.Plane plane = image.getPlanes()[0];
            ByteBuffer buffer = plane.getBuffer();
            int pixelStride = plane.getPixelStride();
            if (pixelStride != 4) return;
            int paddedW = plane.getRowStride() / pixelStride;
            int width = image.getWidth();
            int height = image.getHeight();
            Bitmap padded = Bitmap.createBitmap(paddedW, height, Bitmap.Config.ARGB_8888);
            padded.copyPixelsFromBuffer(buffer);
            Bitmap cropped = Bitmap.createBitmap(padded, 0, 0, width, height);
            if (cropped != padded) padded.recycle();
            int thumbW = Math.min(Math.max(viewportWidth, 200), 630);
            int thumbH = Math.max(1, Math.round((float) height * thumbW / width));
            Bitmap small = Bitmap.createScaledBitmap(cropped, thumbW, thumbH, true);
            if (small != cropped) cropped.recycle();
            mainHandler.post(() -> {
                if (stopping || preview == null) {
                    small.recycle();
                } else {
                    Bitmap previous = lastShown;
                    preview.setImageBitmap(small);
                    lastShown = small;
                    if (previous != null && previous != small) {
                        mainHandler.postDelayed(() -> {
                            if (!previous.isRecycled()) previous.recycle();
                        }, 350);
                    }
                }
            });
        } catch (Exception ignored) {
            // Una app puede bloquear la captura por seguridad.
        } finally {
            if (image != null) image.close();
        }
    }

    @Override public void onDestroy() {
        stopping = true;
        if (virtualDisplay != null) {
            virtualDisplay.release();
            virtualDisplay = null;
        }
        if (reader != null) {
            reader.setOnImageAvailableListener(null, null);
            reader.close();
            reader = null;
        }
        if (thread != null) {
            thread.quitSafely();
            thread = null;
        }
        if (manager != null && previewWindow != null) {
            try { manager.removeViewImmediate(previewWindow); } catch (Exception ignored) {}
            previewWindow = null;
            preview = null;
        }
        if (lastShown != null) {
            lastShown.recycle();
            lastShown = null;
        }
        if (projection != null) {
            MediaProjection active = projection;
            projection = null;
            try { active.stop(); } catch (Exception ignored) {}
        }
        super.onDestroy();
    }

    @Override public IBinder onBind(Intent intent) { return null; }
}
