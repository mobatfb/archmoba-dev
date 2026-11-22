"""Contratos del GUI y del instalador (sin tocar dispositivos ni Windows)."""
import ast
import pathlib
import unittest

PROJECT = pathlib.Path(__file__).resolve().parents[1]
GUI = PROJECT / "python" / "futureo_vjoy_manager.py"
INSTALLER = PROJECT / "instalador_windows" / "HERRAMIENTAS" / "instalador.ps1"


class GUIInstallerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = GUI.read_text(encoding="utf-8")
        cls.tree = ast.parse(cls.source)
        cls.installer = INSTALLER.read_text(encoding="utf-8")

    def test_gui_no_longer_requires_devcon(self):
        self.assertNotIn("self.devcon", self.source)
        self.assertNotIn("shutil.which", self.source)
        self.assertIn('INSTALLER = BASE / "HERRAMIENTAS" / "instalador.ps1"', self.source)
        self.assertIn('INF = BASE / "DRIVER" / "FutJoy.inf"', self.source)
        self.assertIn('"-Accion", action', self.source)
        self.assertIn('"-Cantidad", str(quantity)', self.source)

    def test_powershell_supports_one_to_eight(self):
        for token in ("'InstalarN'", "'QuitarN'", "function RemovePad",
                      "function InstallPads", "[ValidateRange(1,8)]",
                      "FutureoRootDevice", "pnputil.exe /remove-device"):
            self.assertIn(token, self.installer)

    def test_gui_creation_is_interactive_and_uses_uac(self):
        self.assertIn("CREATE_NEW_CONSOLE", self.source)
        self.assertIn('"cmd.exe", "/d", "/v:on", "/c"', self.source)
        self.assertIn("Read-Host", self.installer)
        self.assertIn("Elevate $Accion", self.installer)
        self.assertIn("'InstalarN'", self.installer)
        self.assertIn("'QuitarN'", self.installer)

    def test_removing_one_does_not_remove_all_drivers(self):
        block = self.installer.split("function RemovePad", 1)[1].split(
            "function UninstallPads", 1)[0]
        self.assertIn("pnputil.exe /remove-device", block)
        self.assertNotIn("/delete-driver", block)
        self.assertIn("StartsWith", block)

    def test_naming_is_opt_in_and_reversible(self):
        self.assertIn('ETIQUETAR EN WINDOWS', self.source)
        self.assertIn('"--restore"', self.source)
        self.assertIn('ask_elevation_for_labels()', self.source)
        self.assertIn('No cambia las cadenas HID internas', self.source)
        self.assertIn("return False  # No intentar escribir", self.source)


    def test_pnputil_259_is_not_treated_as_driver_failure(self):
        # /add-driver registra el INF; los ROOT se crean despues con SetupAPI.
        block = self.installer.split("function InstallPads", 1)[1].split(
            "function RemovePad", 1)[0]
        self.assertIn("& pnputil.exe /add-driver $Inf", block)
        self.assertNotIn("& pnputil.exe /add-driver $Inf /install", block)
        self.assertIn("$pnputilExitCode = $LASTEXITCODE", block)
        self.assertIn("if($pnputilExitCode -eq 259)", block)
        self.assertIn("$pnputilExitCode -ne 0", block)
        self.assertIn("$pnputilExitCode -eq 3010", block)
        self.assertIn("$pnputilExitCode -eq 1641", block)
        self.assertIn("BuildRootClass", block)
        self.assertIn("for($slot=1;$slot -le $quantity;$slot++)", block)
        self.assertIn('ya existe; no se crea duplicado.', block)


    def test_gui_shows_real_hid_status_per_slot(self):
        self.assertIn("def refresh_slots", self.source)
        self.assertIn('"--json", "--count", "8"', self.source)
        self.assertIn("self.results.put((\"slots\", slots))", self.source)
        self.assertIn("textvariable=self.slot_labels[n]", self.source)
        self.assertIn("ACTUALIZAR ESTADO", self.source)
        self.assertIn("DETECTADO", self.source)
        self.assertIn("NO DETECTADO", self.source)
        self.assertIn("F7A0:{0x2100+n:04X}", self.source)

    def test_gui_provides_label_check_and_identification(self):
        self.assertIn("VER ETIQUETAS", self.source)
        self.assertIn('["--status", "--count", "8"]', self.source)
        self.assertIn("IDENTIFICAR P SELECCIONADO", self.source)
        self.assertIn("dev.state(x=26000,buttons=1)", self.source)
        self.assertIn("No cambia las cadenas HID internas", self.source)


    def test_gui_can_try_pnp_names_without_driver_reinstall(self):
        self.assertIn("PROBAR NOMBRES PnP", self.source)
        self.assertIn("VER NOMBRES PnP", self.source)
        self.assertIn("RESTAURAR PnP", self.source)
        self.assertIn('with_name("nombres_pnp.py")', self.source)
        self.assertIn('["--apply", "--count", str(quantity)]', self.source)
        self.assertIn('["--restore"]', self.source)
        self.assertIn('["--status", "--count", "8"]', self.source)
        self.assertIn("No esta garantizado que joy.cpl adopte este nombre", self.source)



if __name__ == "__main__":
    unittest.main()
