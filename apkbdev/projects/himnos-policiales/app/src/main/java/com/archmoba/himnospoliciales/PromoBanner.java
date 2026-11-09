package com.archmoba.himnospoliciales;

import android.content.Context;
import android.content.Intent;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.LinearGradient;
import android.graphics.Paint;
import android.graphics.Path;
import android.graphics.Rect;
import android.graphics.RectF;
import android.graphics.Shader;
import android.graphics.Typeface;
import android.net.Uri;
import android.view.HapticFeedbackConstants;
import android.view.MotionEvent;
import android.view.View;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Small, independently clickable promotional card over the bottom tricolor.
 * Reads the selected advert from pub.pub on GitHub every time the app resumes.
 * Includes bundled JSON and thumbnails for immediate/offline display.
 */
final class PromoBanner extends View {
    private static final String CONFIG_URL =
            "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/"
                    + "apkbdev/projects/himnos-policiales/pub.pub";
    private static final String PREFERENCES = "himnos_promo_cache";
    private static final String CACHE_KEY = "last_valid_pub";
    private static final int MAX_JSON_BYTES = 64 * 1024;
    private static final int MAX_IMAGE_BYTES = 1200 * 1024;

    private final Paint paint = new Paint(Paint.ANTI_ALIAS_FLAG | Paint.FILTER_BITMAP_FLAG);
    private final RectF buttonArea = new RectF();
    private final AtomicBoolean fetching = new AtomicBoolean(false);
    private volatile boolean disposed;
    private Ad current;
    private boolean pressed;

    private static final class Ad {
        final int id;
        final String imageUrl;
        final String description;
        final String buttonText;
        final String buttonUrl;
        Bitmap thumbnail;

        Ad(int id, String imageUrl, String description, String buttonText, String buttonUrl) {
            this.id = id;
            this.imageUrl = imageUrl;
            this.description = description;
            this.buttonText = buttonText;
            this.buttonUrl = buttonUrl;
        }
    }

    PromoBanner(Context context) {
        super(context);
        setLayerType(View.LAYER_TYPE_SOFTWARE, null);
        // Always show the bundled advert immediately, even without network.
        try (InputStream stream = context.getAssets().open("pub.pub")) {
            Ad bundled = parse(new String(readLimited(stream, MAX_JSON_BYTES), StandardCharsets.UTF_8));
            applyLocalAd(bundled);
        } catch (Exception ignored) { }
        // A previously downloaded valid configuration takes precedence offline.
        String cached = context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
                .getString(CACHE_KEY, "");
        if (cached != null && !cached.isEmpty()) {
            try { applyLocalAd(parse(cached)); }
            catch (Exception ignored) { }
        }
    }

    /** Download remote JSON and selected thumbnail without blocking the UI. */
    void refreshFromGithub() {
        if (disposed || !fetching.compareAndSet(false, true)) return;
        Thread worker = new Thread(() -> {
            try {
                String json = new String(fetchBytes(CONFIG_URL, MAX_JSON_BYTES),
                        StandardCharsets.UTF_8);
                Ad selected = parse(json); // Valid JSON may select no advert.
                if (selected != null && !selected.imageUrl.isEmpty()) {
                    try { selected.thumbnail = downloadImage(selected.imageUrl); }
                    catch (Exception ignored) { }
                }
                if (disposed) return;
                getContext().getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
                        .edit().putString(CACHE_KEY, json).apply();
                post(() -> {
                    if (disposed) return;
                    applyLocalAd(selected);
                });
            } catch (Exception ignored) {
                // No Internet/GitHub failure: keep last bundled or cached ad.
            } finally {
                fetching.set(false);
            }
        }, "Himnos-Publicidad");
        worker.setDaemon(true);
        worker.start();
    }

    void dispose() { disposed = true; }

    private void applyLocalAd(Ad selected) {
        if (selected != null && selected.thumbnail == null) {
            String fallback = selected.id == 1 ? "agenda_ad.webp"
                    : selected.id == 2 ? "amo_ad.webp" : "";
            if (!fallback.isEmpty()) {
                try (InputStream in = getContext().getAssets().open(fallback)) {
                    selected.thumbnail = BitmapFactory.decodeStream(in);
                } catch (Exception ignored) { }
            }
        }
        current = selected;
        pressed = false;
        invalidate();
    }

    /** IDs and keys are read from the English JSON schema in pub.pub. */
    private static Ad parse(String text) throws JSONException {
        JSONObject root = new JSONObject(text);
        int selectedId = root.getInt("selected_id");
        JSONArray advertisements = root.getJSONArray("ads");
        for (int i = 0; i < advertisements.length(); i++) {
            JSONObject item = advertisements.getJSONObject(i);
            if (item.optInt("id", -1) != selectedId) continue;
            String url = item.optString("button_url", "").trim();
            if (!isWebUrl(url)) return null;
            return new Ad(
                    selectedId,
                    item.optString("image", "").trim(),
                    item.optString("description", "").trim(),
                    item.optString("button_text", "").trim(),
                    url
            );
        }
        return null;
    }

    private static boolean isWebUrl(String url) {
        try {
            Uri uri = Uri.parse(url);
            return ("https".equalsIgnoreCase(uri.getScheme())
                    || "http".equalsIgnoreCase(uri.getScheme()))
                    && uri.getHost() != null && !uri.getHost().isEmpty();
        } catch (Exception ignored) { return false; }
    }

    private static byte[] readLimited(InputStream stream, int maxBytes) throws IOException {
        ByteArrayOutputStream data = new ByteArrayOutputStream();
        byte[] block = new byte[4096];
        int n;
        while ((n = stream.read(block)) != -1) {
            if (data.size() + n > maxBytes) throw new IOException("Resource too large");
            data.write(block, 0, n);
        }
        return data.toByteArray();
    }

    private static byte[] fetchBytes(String url, int limit) throws IOException {
        URL target = new URL(url);
        if (!"https".equalsIgnoreCase(target.getProtocol())) {
            throw new IOException("HTTPS required for remote images/config");
        }
        HttpURLConnection connection = (HttpURLConnection) target.openConnection();
        connection.setConnectTimeout(5500);
        connection.setReadTimeout(5500);
        connection.setUseCaches(false);
        connection.setRequestProperty("Cache-Control", "no-cache");
        connection.setRequestProperty("User-Agent", "HimnosPolicialesAndroid/1.3.3");
        try {
            if (connection.getResponseCode() != HttpURLConnection.HTTP_OK) {
                throw new IOException("HTTP " + connection.getResponseCode());
            }
            if (connection.getContentLength() > limit) {
                throw new IOException("Resource too large");
            }
            try (InputStream stream = connection.getInputStream()) {
                return readLimited(stream, limit);
            }
        } finally { connection.disconnect(); }
    }

    private static Bitmap downloadImage(String url) throws IOException {
        if (!isWebUrl(url)) return null;
        byte[] bytes = fetchBytes(url, MAX_IMAGE_BYTES);
        BitmapFactory.Options bounds = new BitmapFactory.Options();
        bounds.inJustDecodeBounds = true;
        BitmapFactory.decodeByteArray(bytes, 0, bytes.length, bounds);
        if (bounds.outWidth <= 0 || bounds.outHeight <= 0) return null;
        BitmapFactory.Options scaled = new BitmapFactory.Options();
        scaled.inSampleSize = 1;
        while (bounds.outWidth / scaled.inSampleSize > 512
                || bounds.outHeight / scaled.inSampleSize > 512) {
            scaled.inSampleSize *= 2;
        }
        return BitmapFactory.decodeByteArray(bytes, 0, bytes.length, scaled);
    }

    @Override protected void onDraw(Canvas canvas) {
        super.onDraw(canvas);
        Ad ad = current;
        if (ad == null || getWidth() <= 0 || getHeight() <= 0) {
            buttonArea.setEmpty();
            return;
        }
        final float w = getWidth(), h = getHeight();
        final float cardW = w * .51f;
        final float cardH = Math.min(w * .132f, h * .075f);
        final float x = w * .475f;
        final float bottom = h * .982f;
        final float y = bottom - cardH;
        final float radius = cardH * .18f;
        RectF card = new RectF(x, y, Math.min(w * .988f, x + cardW), bottom);

        // Small navy banner with rounded red contour, as in the reference.
        paint.reset();
        paint.setAntiAlias(true);
        paint.setFilterBitmap(true);
        paint.setStyle(Paint.Style.FILL);
        paint.setColor(0xF0061938);
        paint.setShadowLayer(w * .013f, 0, 0, 0xBB00152A);
        canvas.drawRoundRect(card, radius, radius, paint);
        paint.clearShadowLayer();
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(Math.max(1.5f, w * .0035f));
        paint.setColor(0xFFFF504B);
        canvas.drawRoundRect(card, radius, radius, paint);
        paint.setStyle(Paint.Style.FILL);

        // Square app-like thumbnail on the left of the banner.
        float imageSize = cardH * .79f;
        RectF picture = new RectF(card.left + cardH * .105f,
                card.top + (cardH - imageSize) / 2f,
                card.left + cardH * .105f + imageSize,
                card.top + (cardH + imageSize) / 2f);
        float imageRadius = cardH * .13f;
        paint.setColor(0xFFECF4FF);
        canvas.drawRoundRect(picture, imageRadius, imageRadius, paint);
        Bitmap photo = ad.thumbnail;
        if (photo != null && photo.getWidth() > 0 && photo.getHeight() > 0) {
            canvas.save();
            Path clip = new Path();
            clip.addRoundRect(picture, imageRadius, imageRadius, Path.Direction.CW);
            canvas.clipPath(clip);
            float desiredRatio = picture.width() / picture.height();
            float realRatio = (float) photo.getWidth() / photo.getHeight();
            Rect src;
            if (realRatio > desiredRatio) {
                int centerWidth = Math.max(1, Math.round(photo.getHeight() * desiredRatio));
                int l = (photo.getWidth() - centerWidth) / 2;
                src = new Rect(l, 0, l + centerWidth, photo.getHeight());
            } else {
                int centerHeight = Math.max(1, Math.round(photo.getWidth() / desiredRatio));
                int t = (photo.getHeight() - centerHeight) / 2;
                src = new Rect(0, t, photo.getWidth(), t + centerHeight);
            }
            paint.setColor(Color.WHITE);
            paint.setAlpha(255);
            canvas.drawBitmap(photo, src, picture, paint);
            canvas.restore();
        } else {
            paint.setColor(0xFF154786);
            paint.setTypeface(Typeface.DEFAULT_BOLD);
            paint.setTextAlign(Paint.Align.CENTER);
            paint.setTextSize(imageSize * .40f);
            canvas.drawText(Integer.toString(ad.id), picture.centerX(),
                    picture.centerY() + imageSize * .13f, paint);
        }
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(Math.max(1f, w * .0022f));
        paint.setColor(0xFFE8F4FF);
        canvas.drawRoundRect(picture, imageRadius, imageRadius, paint);
        paint.setStyle(Paint.Style.FILL);

        float contentLeft = picture.right + cardH * .12f;
        float contentRight = card.right - cardH * .105f;
        float available = Math.max(1f, contentRight - contentLeft);

        // Description above the orange call-to-action.
        paint.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        paint.setColor(Color.WHITE);
        paint.setTextAlign(Paint.Align.LEFT);
        float captionSize = Math.min(w * .0186f, 16f);
        paint.setTextSize(captionSize);
        String caption = ad.description;
        while (paint.measureText(caption) > available && captionSize > w * .0135f) {
            captionSize -= .5f;
            paint.setTextSize(captionSize);
        }
        caption = ellipsize(caption, paint, available);
        canvas.drawText(caption, contentLeft, card.top + cardH * .35f, paint);

        // Real click target and link are obtained from pub.pub.
        float buttonWidth = Math.min(available * .76f, cardW * .49f);
        float buttonLeft = contentLeft + (available - buttonWidth) / 2f;
        buttonArea.set(buttonLeft, card.top + cardH * .54f,
                buttonLeft + buttonWidth, card.top + cardH * .89f);
        float buttonRadius = cardH * .085f;
        paint.setShader(new LinearGradient(0, buttonArea.top, 0, buttonArea.bottom,
                pressed ? 0xFFFFB665 : 0xFFFFA343,
                pressed ? 0xFFFF8B18 : 0xFFEF761E, Shader.TileMode.CLAMP));
        canvas.drawRoundRect(buttonArea, buttonRadius, buttonRadius, paint);
        paint.setShader(null);
        paint.setColor(0xB93A1000);
        paint.setStyle(Paint.Style.STROKE);
        paint.setStrokeWidth(Math.max(1f, w * .0015f));
        canvas.drawRoundRect(buttonArea, buttonRadius, buttonRadius, paint);
        paint.setStyle(Paint.Style.FILL);

        paint.setTypeface(Typeface.create("sans-serif-medium", Typeface.NORMAL));
        paint.setColor(0xFF1C1005);
        paint.setTextAlign(Paint.Align.CENTER);
        float textSize = Math.min(w * .026f, cardH * .24f);
        paint.setTextSize(textSize);
        while (paint.measureText(ad.buttonText) > buttonArea.width() * .92f
                && textSize > w * .017f) {
            textSize -= .5f;
            paint.setTextSize(textSize);
        }
        String buttonCaption = ellipsize(ad.buttonText, paint, buttonArea.width() * .92f);
        Paint.FontMetrics metrics = paint.getFontMetrics();
        canvas.drawText(buttonCaption, buttonArea.centerX(),
                buttonArea.centerY() - (metrics.ascent + metrics.descent) / 2f, paint);
    }

    private static String ellipsize(String text, Paint paint, float width) {
        if (paint.measureText(text) <= width) return text;
        final String suffix = "\u2026";
        int end = text.length();
        while (end > 0 && paint.measureText(text.substring(0, end) + suffix) > width) end--;
        return text.substring(0, end) + suffix;
    }

    @Override public boolean onTouchEvent(MotionEvent event) {
        switch (event.getActionMasked()) {
            case MotionEvent.ACTION_DOWN:
                if (current != null && buttonArea.contains(event.getX(), event.getY())) {
                    pressed = true;
                    invalidate();
                    return true;
                }
                // Other taps are delivered to the anthem controls underneath.
                return false;
            case MotionEvent.ACTION_MOVE:
                return pressed;
            case MotionEvent.ACTION_UP:
                if (pressed) {
                    boolean inside = buttonArea.contains(event.getX(), event.getY());
                    pressed = false;
                    invalidate();
                    if (inside) {
                        performHapticFeedback(HapticFeedbackConstants.VIRTUAL_KEY);
                        performClick();
                    }
                    return true;
                }
                return false;
            case MotionEvent.ACTION_CANCEL:
                if (pressed) { pressed = false; invalidate(); return true; }
                return false;
            default:
                return false;
        }
    }

    @Override public boolean performClick() {
        super.performClick();
        Ad ad = current;
        if (ad == null || !isWebUrl(ad.buttonUrl)) return false;
        try {
            Intent browser = new Intent(Intent.ACTION_VIEW, Uri.parse(ad.buttonUrl));
            getContext().startActivity(browser);
            return true;
        } catch (Exception ignored) { return false; }
    }
}
