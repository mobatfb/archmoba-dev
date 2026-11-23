package com.archmoba.himnospoliciales;

import android.app.Activity;
import android.content.ClipData;
import android.content.Intent;
import android.net.Uri;
import android.util.Log;
import android.widget.TextView;
import android.widget.Toast;
import androidx.core.content.FileProvider;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.StandardCopyOption;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Copia la APK universal ya instalada y abre el selector para enviar el archivo real.
 * No requiere Internet ni añade una APK desactualizada dentro del propio paquete.
 */
final class ApkSharer {
    private static final String TAG = "HimnosApkSharer";
    private static final AtomicBoolean BUSY = new AtomicBoolean(false);

    private ApkSharer() { }

    static void share(Activity activity, TextView button) {
        if (!BUSY.compareAndSet(false, true)) return;
        button.setEnabled(false);
        button.setText("Preparando APK...");

        new Thread(() -> {
            try {
                // sourceDir es la APK base instalada; APKBDEV produce un APK universal.
                File installedApk = new File(activity.getApplicationInfo().sourceDir);
                if (!installedApk.isFile() || installedApk.length() == 0) {
                    throw new IOException("No se encontró el APK instalado");
                }

                File sharedDir = new File(activity.getCacheDir(), "shared-apk");
                if (!sharedDir.isDirectory() && !sharedDir.mkdirs()) {
                    throw new IOException("No se pudo crear la carpeta temporal");
                }
                String version = activity.getPackageManager()
                        .getPackageInfo(activity.getPackageName(), 0).versionName;
                if (version == null || !version.matches("[a-zA-Z0-9._-]+")) {
                    version = "actual";
                }
                File sharedApk = new File(sharedDir, "Himnos_Policiales_v" + version + ".apk");

                // Evita modificar un fichero que otra app pueda estar recibiendo.
                if (!sharedApk.isFile() || sharedApk.length() != installedApk.length()) {
                    File partial = new File(sharedDir, ".copia-temporal.apk");
                    try {
                        Files.copy(installedApk.toPath(), partial.toPath(),
                                StandardCopyOption.REPLACE_EXISTING);
                        if (partial.length() != installedApk.length()) {
                            throw new IOException("La copia del APK no está completa");
                        }
                        Files.move(partial.toPath(), sharedApk.toPath(),
                                StandardCopyOption.REPLACE_EXISTING);
                    } finally {
                        if (partial.exists() && !partial.delete()) {
                            Log.w(TAG, "No se pudo limpiar el archivo temporal");
                        }
                    }
                }
                if (!sharedApk.isFile() || sharedApk.length() != installedApk.length()) {
                    throw new IOException("El archivo APK no está listo para compartir");
                }

                activity.runOnUiThread(() -> {
                    try {
                        Uri uri = FileProvider.getUriForFile(activity,
                                activity.getPackageName() + ".fileprovider", sharedApk);
                        Intent send = new Intent(Intent.ACTION_SEND);
                        send.setType("application/vnd.android.package-archive");
                        send.putExtra(Intent.EXTRA_STREAM, uri);
                        send.setClipData(ClipData.newUri(
                                activity.getContentResolver(), "APK Himnos Policiales", uri));
                        send.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                        activity.startActivity(Intent.createChooser(
                                send, "Compartir APK con un amigo"));
                    } catch (Exception error) {
                        Log.e(TAG, "No se pudo compartir el APK", error);
                        Toast.makeText(activity, "No se pudo abrir el selector para enviar APK",
                                Toast.LENGTH_LONG).show();
                    } finally {
                        reset(button);
                    }
                });
            } catch (Exception error) {
                Log.e(TAG, "No se pudo preparar el APK", error);
                activity.runOnUiThread(() -> {
                    Toast.makeText(activity, "No se pudo preparar el APK para compartir",
                            Toast.LENGTH_LONG).show();
                    reset(button);
                });
            }
        }, "himnos-apk-sharing").start();
    }

    private static void reset(TextView button) {
        BUSY.set(false);
        button.setEnabled(true);
        button.setText("Compartir con un amigo");
    }
}
