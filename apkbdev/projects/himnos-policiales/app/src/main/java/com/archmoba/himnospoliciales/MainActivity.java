package com.archmoba.himnospoliciales;

import android.app.Activity;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.media.MediaPlayer;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.MotionEvent;
import android.view.HapticFeedbackConstants;
import android.view.View;
import android.view.WindowManager;
import android.widget.FrameLayout;
import android.content.res.AssetFileDescriptor;
import java.io.InputStream;
import java.util.Locale;

/**
 * Himnos Policiales: tres controles de audio local y publicidad opcional.
 * Los himnos funcionan sin Internet; el anuncio solo aparece con red.
 */
public final class MainActivity extends Activity {
    private static final long FADE_MS = 2000L;
    private static final int ECUADOR = 0;
    private static final int POLICIA = 1;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private MediaPlayer media;
    private int selectedTrack = -1;
    private int operation = 0;
    private boolean fadingOut = false;
    private PlayerArtwork view;
    private PromoBanner promotion;

    @Override public void onCreate(Bundle bundle) {
        super.onCreate(bundle);
        getWindow().setStatusBarColor(Color.rgb(3, 15, 32));
        getWindow().setNavigationBarColor(Color.rgb(2, 9, 22));
        view = new PlayerArtwork();
        promotion = new PromoBanner(this);
        FrameLayout layers = new FrameLayout(this);
        FrameLayout.LayoutParams full = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT);
        layers.addView(view, full);
        layers.addView(promotion, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT));
        setContentView(layers);
    }

    @Override protected void onResume() {
        super.onResume();
        // Solo publicidad de Internet; comienza oculta en cada regreso a la app.
        if (promotion != null) promotion.refreshFromGithub();
    }

    @Override protected void onPause() {
        // Olvidar el anuncio y rechazar respuestas pendientes al salir.
        if (promotion != null) promotion.hideAndCancel();
        super.onPause();
    }

    private void play(int track) {
        // Un nuevo toque cancela cualquier fundido anterior.
        int id = ++operation;
        releaseCurrent();
        selectedTrack = track;
        fadingOut = false;
        final MediaPlayer candidate = new MediaPlayer();
        media = candidate;
        try (AssetFileDescriptor fd = getResources().openRawResourceFd(
                track == ECUADOR ? R.raw.himno_ecuador : R.raw.himno_policia)) {
            if (fd == null) throw new IllegalStateException("Audio no disponible");
            candidate.setDataSource(fd.getFileDescriptor(), fd.getStartOffset(), fd.getLength());
            candidate.setVolume(0f, 0f);
            candidate.setOnPreparedListener(mp -> {
                if (id != operation || media != mp) return;
                mp.start();
                getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
                fade(id, 0f, 1f, false);
                view.invalidate();
            });
            candidate.setOnCompletionListener(mp -> {
                if (id != operation || media != mp) return;
                operation++;
                releaseCurrent();
                selectedTrack = -1;
                view.invalidate();
            });
            candidate.setOnErrorListener((mp, what, extra) -> {
                if (id == operation && media == mp) {
                    operation++;
                    releaseCurrent();
                    selectedTrack = -1;
                    view.invalidate();
                }
                return true;
            });
            candidate.prepareAsync();
        } catch (Exception error) {
            if (id == operation) {
                operation++;
                releaseCurrent();
                selectedTrack = -1;
                view.invalidate();
            }
        }
    }

    /** STOP inmediato: silencia y libera el audio sin fundido ni retardo. */
    private void stopImmediately() {
        ++operation;
        handler.removeCallbacksAndMessages(null);
        if (media != null) {
            try { media.setVolume(0f, 0f); }
            catch (IllegalStateException ignored) { }
        }
        releaseCurrent();
        selectedTrack = -1;
        fadingOut = false;
        if (view != null) view.invalidate();
    }

    private float currentVolume = 0f;

    private void fade(final int id, final float from, final float to, final boolean stopAtEnd) {
        final long started = android.os.SystemClock.uptimeMillis();
        final Runnable step = new Runnable() {
            @Override public void run() {
                if (id != operation || media == null) return;
                float t = Math.min(1f, (android.os.SystemClock.uptimeMillis() - started) / (float) FADE_MS);
                currentVolume = Math.max(0f, Math.min(1f, from + (to - from) * t));
                try { media.setVolume(currentVolume, currentVolume); }
                catch (IllegalStateException error) { return; }
                if (t >= 1f) {
                    if (stopAtEnd) {
                        operation++;
                        releaseCurrent();
                        selectedTrack = -1;
                        fadingOut = false;
                    }
                    view.invalidate();
                } else {
                    handler.postDelayed(this, 25L);
                }
            }
        };
        handler.post(step);
    }

    private void releaseCurrent() {
        if (media != null) {
            try { media.setOnCompletionListener(null); media.setOnPreparedListener(null);
                  media.setOnErrorListener(null); media.reset(); media.release(); }
            catch (Exception ignored) { }
            media = null;
        }
        currentVolume = 0f;
        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private int position() {
        if (media == null) return 0;
        try { return Math.max(0, media.getCurrentPosition()); }
        catch (IllegalStateException ignored) { return 0; }
    }
    private int duration() {
        if (media == null) return selectedTrack == ECUADOR ? 142000 :
                selectedTrack == POLICIA ? 94284 : 0;
        try { return Math.max(0, media.getDuration()); }
        catch (IllegalStateException ignored) { return 0; }
    }
    private static String time(int millis) {
        int s = Math.max(0, millis) / 1000;
        return String.format(Locale.ROOT, "%02d:%02d", s / 60, s % 60);
    }

    @Override protected void onStop() {
        super.onStop();
        // No reproducir de forma oculta y sin controles al dejar la aplicación.
        operation++;
        releaseCurrent();
        selectedTrack = -1;
        fadingOut = false;
    }
    @Override protected void onDestroy() {
        if (promotion != null) promotion.dispose();
        operation++;
        releaseCurrent();
        handler.removeCallbacksAndMessages(null);
        super.onDestroy();
    }

    private final class PlayerArtwork extends View {
        private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
        private final Bitmap wallpaper = asset("fondo.webp");
        private final Bitmap ecu = asset("ecuador.webp");
        private final Bitmap ecuSelected = asset("ecuador_activo.webp");
        private final Bitmap stop = asset("stop.webp");
        private final Bitmap police = asset("policia.webp");
        private final Bitmap policeSelected = asset("policia_activo.webp");
        // Cinta tricolor y cabecera están integradas en el único fondo vertical.
        private final RectF[] touchRects = {new RectF(), new RectF(), new RectF()};
        private int activeTouch = -1;
        private long stopTouchedAt = 0L;

        PlayerArtwork() { super(MainActivity.this); setLayerType(View.LAYER_TYPE_SOFTWARE, null); }

        private Bitmap asset(String file) {
            try (InputStream in = getAssets().open(file)) {
                return BitmapFactory.decodeStream(in);
            } catch (Exception ignored) { return null; }
        }
        private void bitmap(Canvas canvas, Bitmap b, RectF at) {
            if (b != null) {
                paint.setStyle(Paint.Style.FILL);
                paint.setColor(Color.WHITE);
                paint.setAlpha(255);
                paint.clearShadowLayer();
                canvas.drawBitmap(b, new Rect(0, 0, b.getWidth(), b.getHeight()), at, paint);
            }
        }
        private void rounded(Canvas canvas, RectF rectangle, float radius, int color) {
            paint.setStyle(Paint.Style.FILL);
            paint.clearShadowLayer();
            paint.setColor(color);
            canvas.drawRoundRect(rectangle, radius, radius, paint);
        }
        @Override protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            final float w = getWidth(), h = getHeight();
            // Fondo único a pantalla completa; nada tapa el paisaje detrás.
            if (wallpaper != null) {
                bitmap(canvas, wallpaper, new RectF(0, 0, w, h));
            } else {
                paint.setShader(new LinearGradient(0, 0, 0, h, 0xFF020D20,
                        0xFF052A54, Shader.TileMode.CLAMP));
                canvas.drawRect(0, 0, w, h, paint);
                paint.setShader(null);
            }
            // Dos botones completos tipo app y STOP circular entre ambos.
            // Los WEBP ya tienen esquinas redondeadas y canal alfa.
            float buttonsTop = h * .51f;
            float buttonH = Math.min(h * .22f, w * .34f);
            float margin = w * .01f;
            float leftW = w * .34f;
            float middleW = w * .29f;
            touchRects[0].set(margin, buttonsTop,
                    margin + leftW, buttonsTop + buttonH);
            float stopH = middleW * .93f;
            touchRects[1].set((w - middleW) / 2f,
                    buttonsTop + (buttonH - stopH) / 2f,
                    (w + middleW) / 2f,
                    buttonsTop + (buttonH + stopH) / 2f);
            touchRects[2].set(w - margin - leftW, buttonsTop,
                    w - margin, buttonsTop + buttonH);
            // El brillo seleccionado está integrado en el contorno real
            // del WEBP: evita marcos geométricos separados y espacios falsos.
            boolean selectingEcuador = media != null && selectedTrack == ECUADOR;
            boolean selectingPolice = media != null && selectedTrack == POLICIA;
            bitmap(canvas, selectingEcuador && ecuSelected != null ? ecuSelected : ecu,
                    touchRects[0]);
            bitmap(canvas, stop, touchRects[1]);
            bitmap(canvas, selectingPolice && policeSelected != null ? policeSelected : police,
                    touchRects[2]);
            if (android.os.SystemClock.uptimeMillis() - stopTouchedAt < 550L) {
                paint.setStyle(Paint.Style.STROKE);
                paint.setStrokeWidth(w * .012f);
                paint.setColor(0xFFFFD8D8);
                canvas.drawRoundRect(touchRects[1], w * .14f, w * .14f, paint);
                paint.setStyle(Paint.Style.FILL);
                postInvalidateDelayed(550);
            }
            // Sin rectángulos extra: el botón seleccionado reemplaza su propio
            // WEBP y la selección termina al liberar el reproductor.
            float barY = h * .82f;
            float barLeft = w * .07f, barRight = w * .93f;
            rounded(canvas, new RectF(barLeft, barY - h * .004f,
                    barRight, barY + h * .004f), h * .004f, 0xFF7696B6);
            int total = duration();
            int now = position();
            float fraction = total > 0 ? Math.min(1f, (float) now / total) : 0f;
            if (fraction > 0f) {
                rounded(canvas, new RectF(barLeft, barY - h * .005f,
                        barLeft + (barRight - barLeft) * fraction, barY + h * .005f),
                        h * .004f, 0xFF00D9FF);
            }
            // Barra de progreso informativa: sin deslizador ni control táctil.
            paint.setColor(Color.WHITE);
            paint.setTextSize(w * .047f);
            paint.setTypeface(android.graphics.Typeface.create("sans-serif", android.graphics.Typeface.NORMAL));
            paint.setTextAlign(Paint.Align.LEFT);
            canvas.drawText(time(now), barLeft, barY + h * .043f, paint);
            paint.setTextAlign(Paint.Align.RIGHT);
            canvas.drawText(time(total), barRight, barY + h * .043f, paint);
            // Pie tricolor ya incorporado al fondo de pantalla completo.
            if (media != null) postInvalidateDelayed(100L);
        }
        private int hit(float x, float y) {
            final float slop = Math.max(12f, getWidth() * .012f);
            // Evitar superposición entre las áreas táctiles de los tres botones.
            // Primero probar el rectángulo real; después, el más cercano.
            for (int index = 0; index < 3; index++) {
                if (touchRects[index].contains(x, y)) return index;
            }
            int best = -1;
            float distance = Float.MAX_VALUE;
            for (int index = 0; index < 3; index++) {
                RectF rect = touchRects[index];
                if (containsExpanded(rect, x, y, slop)) {
                    float d = Math.abs(x - rect.centerX());
                    if (d < distance) { distance = d; best = index; }
                }
            }
            return best;
        }

        private boolean containsExpanded(RectF r, float x, float y, float s) {
            return x >= r.left - s && x <= r.right + s
                    && y >= r.top - s && y <= r.bottom + s;
        }

        @Override public boolean onTouchEvent(MotionEvent event) {
            final float x = event.getX(), y = event.getY();
            switch (event.getActionMasked()) {
                case MotionEvent.ACTION_DOWN:
                    activeTouch = hit(x, y);
                    if (activeTouch >= 0) {
                        performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);
                        if (activeTouch == 0) play(ECUADOR);
                        else if (activeTouch == 1) {
                            stopTouchedAt = android.os.SystemClock.uptimeMillis();
                            stopImmediately();
                        } else play(POLICIA);
                        invalidate(); // respuesta visible inmediatamente al tocar
                        performClick();
                        return true;
                    }
                    // Los toques fuera de los tres botones NO alteran la reproducción.
                    return true;
                case MotionEvent.ACTION_MOVE:
                    return true;
                case MotionEvent.ACTION_UP:
                case MotionEvent.ACTION_CANCEL:
                    activeTouch = -1;
                    return true;
                default: return true;
            }
        }

        @Override public boolean performClick() {
            super.performClick();
            return true;
        }
    }
}
