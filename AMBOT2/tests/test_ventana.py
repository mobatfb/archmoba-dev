"""Verifica el arranque nativo Panda3D en modo sin monitor."""
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


class NativeAppTests(unittest.TestCase):
    def test_aplicacion_nativa_y_maestro(self):
        from app import AMBOT2App,VERSION
        self.assertEqual(VERSION,"0.3.0")
        with tempfile.TemporaryDirectory() as td:
            app=AMBOT2App(headless=True,data_dir=td)
            try:
                self.assertEqual(app.teacher.name,"MAESTRO")
                self.assertEqual(app.baby.name,"AMBOT")
                self.assertEqual(len(app.grasp.fingers),10)
                self.assertEqual(len(app.lab.objects),3)
                self.assertTrue(app.auto_watch)
                self.assertIn("OBSERVACION AUTOMATICA",app.menu_order)
                self.assertTrue(app.menu_state["OBSERVACION AUTOMATICA"])
                # Observar sin grabar: mover el codo y dejar de moverse.
                app._observe_teacher(.1)
                app.teacher.set_joint("codo_izq",65)
                self.assertIsNone(app._observe_teacher(.1))
                for _ in range(13):
                    app._observe_teacher(.1)
                self.assertEqual(len(app.learner.unlabeled),1)
                self.assertEqual(app.learner.episodes,0)
                self.assertIn("Como se llama",app.question_label.getText())
                app.handle_command("estoy flexionando mi codo")
                self.assertEqual(app.learner.episodes,1)
                self.assertIn("flexionando mi codo",app.learner.available())
                self.assertIsNone(app.learner.next_unlabeled())
                self.assertEqual(app.last_skill,"flexionando mi codo")
                app.set_auto_watch(False)
                app.teacher.set_joint("codo_izq",90)
                for _ in range(15):
                    app._observe_teacher(.1)
                self.assertIsNone(app.learner.next_unlabeled())
                app.set_auto_watch(True)
                app.handle_command("habilidades")
                self.assertIn("flexionando mi codo",app.last_message)

                self.assertIsNotNone(app.panel)
                # Secciones expandibles que conservan angulos al cerrarse.
                self.assertIn("BRAZO IZQUIERDO",app.menu_order)
                self.assertIn("CABEZA Y TRONCO",app.menu_order)
                self.assertTrue(app.menu_state["CABEZA Y TRONCO"])
                self.assertFalse(app.menu_state["BRAZO IZQUIERDO"])
                self.assertTrue(app.toggle_section("BRAZO IZQUIERDO"))
                self.assertIn("codo_izq",app.joint_sliders)
                app.joint_sliders["codo_izq"]["value"]=38
                app._on_joint_slider("codo_izq")
                self.assertEqual(app.teacher.joints["codo_izq"],38)
                self.assertFalse(app.toggle_section("BRAZO IZQUIERDO"))
                self.assertNotIn("codo_izq",app.joint_sliders)
                self.assertTrue(app.toggle_section("BRAZO IZQUIERDO"))
                self.assertEqual(app.joint_sliders["codo_izq"]["value"],38)
                self.assertTrue(app.toggle_section("MANOS Y DEDOS"))
                self.assertEqual(len(app.finger_sliders),5)
                app.handle_command("articulacion rodilla_der 80")
                self.assertEqual(app.teacher.joints["rodilla_der"],80)
                app.handle_command("postura neutra")
                self.assertEqual(app.teacher.joints["rodilla_der"],0)
                self.assertEqual(app.teacher.joints["codo_izq"],0)
                app.handle_command("esto es un cuadro")
                self.assertIn("cuadro",app.language.labels.values())
                app.handle_command("enseñar agarrar")
                app.teacher.hand_close("izquierda",1)
                app.handle_command("fin")
                # Una accion ya fue aprendida AUTOMATICAMENTE antes;
                # ahora debe sumarse la demostracion manual, sin duplicar.
                self.assertEqual(app.learner.episodes,2)
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
