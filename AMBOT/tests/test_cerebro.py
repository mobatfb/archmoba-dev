"""Validacion de AMBOT sin servidor HTTP ni navegador."""
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import APP_VERSION, WORLD, Robot, Scene3D

class RobotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.robot=Robot(Path(self.tmp.name)/"memoria.json")

    def test_version_y_mapa(self):
        self.assertEqual(APP_VERSION,"0.2.0")
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
