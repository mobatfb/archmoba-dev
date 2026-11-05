"""Verifica el arranque nativo Panda3D en modo sin monitor."""
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


class NativeAppTests(unittest.TestCase):
    def test_aplicacion_nativa_y_maestro(self):
        from app import AMBOT2App,VERSION
        self.assertEqual(VERSION,"0.1.0")
        with tempfile.TemporaryDirectory() as td:
            app=AMBOT2App(headless=True,data_dir=td)
            try:
                self.assertEqual(app.teacher.name,"MAESTRO")
                self.assertEqual(app.baby.name,"AMBOT")
                self.assertEqual(len(app.grasp.fingers),10)
                self.assertEqual(len(app.lab.objects),3)
                self.assertIsNotNone(app.panel)
                app.handle_command("esto es un cuadro")
                self.assertIn("cuadro",app.language.labels.values())
                app.handle_command("enseñar agarrar")
                app.teacher.hand_close("izquierda",1)
                app.handle_command("fin")
                self.assertEqual(app.learner.episodes,1)
                app.handle_command("practicar agarrar")
                self.assertEqual(app.learner.attempts,1)
                app.create_object("cubo")
                self.assertEqual(len(app.lab.objects),4)
                app.save_scene()
                self.assertTrue((Path(td)/"escena.json").exists())
                for _ in range(3):
                    app.taskMgr.step()
            finally:
                app.destroy()


if __name__=="__main__":
    unittest.main()
