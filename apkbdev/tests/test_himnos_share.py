"""Comprobaciones estructurales del envío de APK en Himnos Policiales."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "projects" / "himnos-policiales"
APP = ROOT / "app" / "src" / "main"
JAVA = APP / "java" / "com" / "archmoba" / "himnospoliciales"


class HimnosShareTests(unittest.TestCase):
    def test_boton_compartir_arriba_izquierda(self):
        code = (JAVA / "MainActivity.java").read_text(encoding="utf-8")
        self.assertIn('shareButton.setText("Compartir con un amigo")', code)
        self.assertIn("Gravity.TOP | Gravity.START", code)
        self.assertIn("ApkSharer.share(this, shareButton)", code)

    def test_envia_apk_instalada_sin_url(self):
        code = (JAVA / "ApkSharer.java").read_text(encoding="utf-8")
        self.assertIn("getApplicationInfo().sourceDir", code)
        self.assertIn("Files.copy(installedApk.toPath()", code)
        self.assertIn("Intent.ACTION_SEND", code)
        self.assertIn("Intent.EXTRA_STREAM", code)
        self.assertIn("application/vnd.android.package-archive", code)

    def test_uri_temporal_segura(self):
        code = (JAVA / "ApkSharer.java").read_text(encoding="utf-8")
        self.assertIn("FileProvider.getUriForFile", code)
        self.assertIn("Intent.FLAG_GRANT_READ_URI_PERMISSION", code)
        self.assertIn("getCacheDir()", code)
        manifest = (APP / "AndroidManifest.xml").read_text(encoding="utf-8")
        self.assertIn('android:name=".ApkFileProvider"', manifest)
        self.assertIn('android:exported="false"', manifest)
        self.assertIn('android:grantUriPermissions="true"', manifest)
        paths = (APP / "res" / "xml" / "apk_share_paths.xml").read_text(encoding="utf-8")
        self.assertIn('path="shared-apk/"', paths)
        self.assertNotIn("<root-path", paths)

    def test_nueva_version(self):
        config = (ROOT / "app" / "build.gradle").read_text(encoding="utf-8")
        self.assertIn("versionCode 14", config)
        self.assertIn("versionName '1.3.8'", config)


if __name__ == "__main__":
    unittest.main()
