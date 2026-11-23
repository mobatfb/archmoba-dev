"""Pruebas de integración para aviso legal en Himnos Policiales."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1] / "projects" / "himnos-policiales"
MAIN = ROOT / "app" / "src" / "main" / "java" / "com" / "archmoba" / "himnospoliciales"
EXPECTED = (
    "HIMNOS POLICIALES — AVISO LEGAL",
    "Aplicación gratuita e independiente, desarrollada para facilitar el acceso a himnos utilizados durante ceremonias, formaciones y eventos protocolarios.",
    "Los derechos correspondientes a las composiciones, interpretaciones y grabaciones musicales pertenecen a sus respectivos titulares.",
    "Esta aplicación no representa ni implica respaldo oficial de la Policía Nacional del Ecuador.",
)


class LegalNoticeTests(unittest.TestCase):
    def test_boton_esquina_inferior_izquierda(self):
        code = (MAIN / "MainActivity.java").read_text(encoding="utf-8")
        self.assertIn('legalButton.setText("Aviso legal")', code)
        self.assertIn("Gravity.BOTTOM | Gravity.START", code)
        self.assertIn("LegalNoticeDialog.show(this)", code)
        self.assertIn('shareButton.setText("Compartir con un amigo")', code)

    def test_aviso_exacto_y_desplazable(self):
        code = (MAIN / "LegalNoticeDialog.java").read_text(encoding="utf-8")
        for paragraph in EXPECTED:
            self.assertIn(paragraph, code)
        self.assertIn("ScrollView", code)
        self.assertIn('close.setText("CERRAR")', code)
        self.assertIn("dialog.dismiss()", code)
        self.assertNotIn("Cualquier consulta o reclamación", code)

    def test_version(self):
        code = (ROOT / "app" / "build.gradle").read_text(encoding="utf-8")
        self.assertIn("versionCode 15", code)
        self.assertIn("versionName '1.3.9'", code)


if __name__ == "__main__":
    unittest.main()
