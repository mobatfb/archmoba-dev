"""Validacion de AMBOT sin servidor HTTP ni navegador."""
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import APP_VERSION, WORLD, Robot, Scene3D, ROOM_NAME, ROOM_CELLS, ROOM_DOOR, ROOM_OBJECTS, FURNITURE_CELLS

class RobotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.robot=Robot(Path(self.tmp.name)/"memoria.json")

    def test_version_y_mapa(self):
        self.assertEqual(APP_VERSION,"0.3.0")
        self.assertTrue(self.robot.free(self.robot.x,self.robot.z))
        self.assertTrue(all(len(r)==len(WORLD[0]) for r in WORLD))

    def test_decision_legal(self):
        self.assertIn(self.robot.decide()[0],{"detener","avanzar","derecha","izquierda"})
        for _ in range(160):
            self.robot.explore()
            self.assertTrue(self.robot.free(self.robot.x,self.robot.z))
        self.assertGreater(self.robot.steps,0)

    def test_manual_y_sensores(self):
        self.assertIn("cm",self.robot.command("sensores"))
        self.assertIn("Movimiento",self.robot.command("avanza"))
        self.assertIn("Gire",self.robot.command("gira derecha"))
        self.assertIn("recargada",self.robot.command("cargar"))

    def test_memoria_persistente(self):
        self.robot.command("recuerda nombre = AMBOT")
        self.assertEqual(Robot(self.robot.memory_path).facts["nombre"],"AMBOT")
        self.assertEqual(self.robot.command("que sabes de nombre"),"AMBOT")
        self.assertEqual(self.robot.command("olvida nombre"),"Dato olvidado.")

    def test_habitacion_puerta_y_muebles(self):
        self.assertEqual(self.robot.state()["lugar"], ROOM_NAME)
        self.assertEqual(len(ROOM_CELLS), 25)
        self.assertEqual(WORLD[ROOM_DOOR[1]][ROOM_DOOR[0]], ".")
        self.assertTrue(self.robot.free(*ROOM_DOOR))
        self.assertEqual(len(FURNITURE_CELLS), 5)
        for xy in FURNITURE_CELLS:
            self.assertFalse(self.robot.free(*xy))
        for label in ("cama", "mesa", "silla", "armario"):
            self.assertIn(label, ROOM_OBJECTS)
        txt = self.robot.command("mapa")
        for symbol in ("C", "M", "S", "A", "P"):
            self.assertIn(symbol, txt)

    def test_robot_sale_al_pasillo_por_la_puerta(self):
        for _ in range(3):
            self.assertIn("Movimiento seguro", self.robot.move())
        self.assertEqual((self.robot.x,self.robot.z),(9,5))
        self.assertEqual(self.robot.location(),"PASILLO")

    def test_muebles_3d(self):
        import pygame
        pygame.init()
        try:
            scene=Scene3D(pygame)
            scene.camera_update(pygame.Rect(0,0,900,550))
            scene.build_room_details()
            self.assertGreater(len(scene.faces), 60)
        finally:
            pygame.quit()

    def test_visor_3d_sincronizado_y_burbuja(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        from app import DesktopApp
        gui = DesktopApp(pygame, smoke=True)
        try:
            gui.draw(0.016)
            self.assertIsNotNone(gui.last_portrait_state)
            self.assertAlmostEqual(gui.scene.angle, gui.portrait_scene.angle)
            self.assertAlmostEqual(gui.scene.walk, gui.portrait_scene.walk)
            self.assertEqual(gui.scene.rx, gui.portrait_scene.rx)
            self.assertEqual(gui.scene.rz, gui.portrait_scene.rz)
            before = gui.scene.angle
            gui.execute("gira derecha", quiet=True)
            gui.draw(0.045)
            self.assertNotEqual(before, gui.scene.angle)
            self.assertAlmostEqual(gui.scene.angle, gui.portrait_scene.angle)
            self.assertTrue(gui.bubble_text)
            self.assertGreater(gui.bubble_until, gui.elapsed)
            gui.toggle_auto()
            self.assertIn("explorando", gui.bubble_text.lower())
            self.assertIs(gui.auto, True)
            gui.draw(0.016)
            self.assertEqual(gui.portrait_scene.walk, gui.scene.walk)
        finally:
            pygame.quit()

    def test_burbuja_texto_largo_no_desborda(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        try:
            font=gui.fonts[13]
            lines=gui.wrap_text("Palabraextremadamentelargasinseparadores"*7,
                                font,180,max_lines=4)
            self.assertLessEqual(len(lines),4)
            for line in lines:
                self.assertLessEqual(font.size(line)[0],180)
            gui.say("¿Qué es este lugar?")
            self.assertIn("lugar", gui.bubble_text)
            gui.draw(0.016)
        finally:
            pygame.quit()

    def test_3d_projection(self):
        import pygame
        pygame.init()
        try:
            camera=Scene3D(pygame)
            camera.camera_update(pygame.Rect(0,0,900,500))
            center=camera.project((0,0,0))
            self.assertIsNotNone(center)
            self.assertGreater(center[2],0)
            self.assertEqual(len(center),3)
            camera.build_world(self.robot)
            camera.build_robot(self.robot,.016,0)
            self.assertGreater(len(camera.faces),100)
        finally:
            pygame.quit()

if __name__=="__main__":
    unittest.main()
