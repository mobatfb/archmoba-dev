"""Validacion de AMBOT sin servidor HTTP ni navegador."""
import tempfile
import unittest
from pathlib import Path
import time
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import APP_VERSION, WORLD, Robot, Scene3D, ArduinoBridge, ROOM_NAME, ROOM_CELLS, ROOM_DOOR, ROOM_OBJECTS, FURNITURE_CELLS

class RobotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.robot=Robot(Path(self.tmp.name)/"memoria.json")

    def test_version_y_mapa(self):
        self.assertEqual(APP_VERSION,"0.5.0")
        self.assertTrue(self.robot.free(self.robot.x,self.robot.z))
        self.assertTrue(all(len(r)==len(WORLD[0]) for r in WORLD))

    def test_decision_legal(self):
        self.assertIn(self.robot.decide()[0],{"detener","avanzar","derecha","izquierda"})
        for _ in range(160):
            self.robot.training.update(.07)
            self.robot.explore()
            self.assertTrue(self.robot.free(self.robot.x,self.robot.z))
        self.assertGreater(self.robot.steps,0)

    def test_manual_y_sensores(self):
        self.assertIn("cm",self.robot.command("sensores"))
        self.robot.training.confidence["caminar"]=1.0
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
        self.robot.training.confidence["caminar"]=1.0
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

    def test_tres_guias_y_aprendizaje_observacional(self):
        tr=self.robot.training
        self.assertEqual(len(tr.guides),3)
        self.assertEqual({g.task for g in tr.guides},
                         {"CAMINAR","OBJETOS","DESCANSAR"})
        self.assertTrue(all(v==0 for v in tr.confidence.values()))
        for _ in range(700):
            tr.update(.05)
        self.assertGreater(tr.observations,20)
        for skill in ("caminar","agarrar","transportar","descansar","reconocer"):
            self.assertGreater(tr.confidence[skill],0)
        self.assertIn("cubo",tr.known_names)
        self.assertNotEqual(tr.guides[0].x,tr.guides[1].x)
        self.assertIn(tr.guides[2].posture,{"lying","standing"})

    def test_aprendizaje_persistente_entre_sesiones(self):
        tr=self.robot.training
        tr.update(.05)
        before=tr.observations
        self.assertGreater(before,0)
        next_baby=Robot(self.robot.memory_path)
        self.assertEqual(next_baby.training.observations,before)
        self.assertAlmostEqual(
            next_baby.training.confidence["caminar"],
            tr.confidence["caminar"])

    def test_practica_caida_y_recuperacion(self):
        tr=self.robot.training
        tr.rng.seed(1)
        self.assertIn("tambalee",self.robot.move())
        self.assertEqual(self.robot.posture,"stumble")
        self.assertGreater(tr.falls,0)
        for _ in range(15):
            tr.update(.07)
        self.assertEqual(self.robot.posture,"standing")
        self.assertGreater(tr.confidence["caminar"],0)

    def test_agarre_carga_y_gravedad(self):
        tr=self.robot.training
        tr.confidence["agarrar"]=1.0
        tr.confidence["caminar"]=1.0
        outcome=""
        for _ in range(8):
            outcome=tr.try_grab()
            if self.robot.holding:
                break
        self.assertTrue(self.robot.holding,outcome)
        held=tr.items[self.robot.holding]
        self.assertEqual(held.held_by,"AMBOT")
        self.robot.move()
        tr.update(.05)
        self.assertAlmostEqual(held.x,self.robot.x+.48,places=2)
        self.assertIn("gravedad",tr.try_release())
        self.assertEqual(held.held_by,"")
        for _ in range(140):
            tr.update(.05)
        self.assertAlmostEqual(held.y,held.radius,delta=.04)

    def test_empujar_pelota_ubicacion_con_colisiones(self):
        tr=self.robot.training
        self.robot.facing=0
        ball=tr.items["cubo"]
        self.assertEqual((ball.x,ball.z),(6.0,4.0))
        out=self.robot.move()
        self.assertIn("empujar",out)
        self.assertLess(ball.z,4.0)
        before=ball.z
        for _ in range(5):
            tr.update(.05)
        self.assertLess(ball.z,before)

    def test_aprender_a_acostarse_y_levantarse(self):
        tr=self.robot.training
        self.robot.x,self.robot.z=5,6
        tr.confidence["descansar"]=1.0
        for _ in range(7):
            answer=tr.try_rest()
            if self.robot.posture=="lying":
                break
            tr.update(.07)
        self.assertEqual(self.robot.posture,"lying",answer)
        self.assertIn("incorporarme",self.robot.move())
        self.assertEqual(self.robot.command("levantarse"),
                         "Estoy de pie de nuevo.")
        self.assertEqual(self.robot.posture,"standing")

    def test_fisica_y_tres_personajes_3d(self):
        import pygame
        pygame.init()
        try:
            scene=Scene3D(pygame)
            scene.camera_update(pygame.Rect(0,0,1000,640))
            tr=self.robot.training
            tr.update(.05)
            scene.build_training(tr,0.016)
            self.assertGreater(len(scene.faces),150)
            self.assertEqual(len({guide.color for guide in tr.guides}),3)
            self.assertEqual(len(tr.items),3)
            before=(scene.rx,scene.rz,scene.angle,scene.walk)
            scene.build_training(tr,.017)
            self.assertEqual(before,(scene.rx,scene.rz,scene.angle,scene.walk))
        finally:
            pygame.quit()

    def test_modo_auto_imita_acciones_aprendidas(self):
        tr=self.robot.training
        msg=tr.autonomous_trial()
        self.assertIn("observo",msg.lower())
        self.assertEqual(self.robot.steps,0)
        tr.confidence["caminar"]=1.0
        tr.confidence["agarrar"]=1.0
        for _ in range(9):
            tr.auto_ticks=2
            msg=tr.autonomous_trial()
            if self.robot.holding:
                break
        self.assertTrue(self.robot.holding,msg)
        tr.autonomous_trial()
        tr.autonomous_trial()
        tr.autonomous_trial()
        self.assertIsNone(self.robot.holding)
        self.assertGreater(tr.attempts,0)

    def test_vista_y_botones_entrenamiento(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        try:
            gui.robot.training.update(.05)
            gui.poll_guides()
            gui.draw(.017)
            for key in ("observe","grasp","release","lie"):
                self.assertIn(key,gui.buttons)
            self.assertEqual(len(gui.robot.training.guides),3)
            self.assertIsNotNone(gui.last_portrait_state)
            gui.execute("observar")
            self.assertIn("Observo",gui.bubble_text)
            gui.handle_button("grasp")
            self.assertGreater(gui.robot.training.attempts,0)
            gui.draw(.017)
        finally:
            pygame.quit()

    def test_cerebro_nace_sin_conocimientos_previos(self):
        brain=self.robot.brain
        self.assertEqual(brain.concepts,{})
        self.assertEqual(brain.relations,{})
        self.assertEqual(brain.number_patterns,{})
        self.assertEqual(brain.action_models,{})
        self.assertEqual(brain.questions,[])
        self.assertEqual(list(brain.episodes),[])

    def test_curiosidad_inicia_sin_esperar_ordenes(self):
        brain=self.robot.brain
        self.assertTrue(brain.sense(self.robot.training)["shapes"])
        for _ in range(13):
            brain.autonomous_step()
            self.robot.training.update(.05)
        self.assertGreater(brain.tick_count,0)
        self.assertGreater(len(brain.questions),0)
        self.assertGreater(len(brain.action_models),0)
        self.assertTrue(brain.current_goal)
        self.assertTrue(brain.pending_question())
        self.assertTrue(brain.last_thought)

    def test_preguntas_originales_y_respuestas_guardadas(self):
        brain=self.robot.brain
        question=brain.ask("experimento","¿Por que cambia la forma?")
        self.assertIn("Por que",question)
        n=len(brain.questions)
        brain.ask("experimento","¿Por que cambia la forma?")
        self.assertEqual(len(brain.questions),n)
        answer=self.robot.command("responde la fuerza puede cambiar la posicion")
        self.assertIn("Guarde tu explicacion",answer)
        self.assertFalse(brain.pending_question())
        self.assertIn("fuerza",brain.concepts)
        recovered=Robot(self.robot.memory_path).brain
        self.assertEqual(recovered.relations["respuesta:experimento"],
                         "la fuerza puede cambiar la posicion")
        self.assertEqual(recovered.questions[-1]["answer"],
                         "la fuerza puede cambiar la posicion")

    def test_lectura_y_conceptos_de_materias_nuevas(self):
        brain=self.robot.brain
        self.assertIn("palabras",self.robot.command(
            "leer La fotosintesis convierte energia luminosa en energia quimica."))
        self.assertEqual(brain.concepts["energia"]["n"],2)
        self.assertEqual(brain.concepts["fotosintesis"]["n"],1)
        self.assertGreater(brain.concepts["energia"]["neighbors"].get("quimica",0),0)
        self.assertIn("palabras",self.robot.command(
            "ensename La astronomia estudia los astros y sus movimientos."))
        self.assertIn("astronomia",brain.concepts)
        self.assertIn("experiencias",self.robot.command("cerebro"))
        next_brain=Robot(self.robot.memory_path).brain
        self.assertEqual(next_brain.text_samples,2)

    def test_patrones_numericos_observados(self):
        brain=self.robot.brain
        result=self.robot.command("contar")
        self.assertIn("Juntos cuento 3",result)
        self.assertEqual(brain.number_patterns["2+1=3"],1)
        self.robot.command("matematicas")
        self.assertEqual(brain.number_patterns["2+1=3"],2)

    def test_escucha_a_los_guias_y_conserva_observaciones(self):
        tr=self.robot.training
        tr.update(.05)
        brain=self.robot.brain
        first=tr.messages[0]
        brain.observe_guide(first,tr)
        self.assertGreater(len(brain.concepts),0)
        self.assertGreater(len(brain.episodes),0)
        self.assertIn("voz",brain.episodes[-2]["source"])
        self.assertGreater(len(brain.questions),0)

    def test_puente_serial_se_inicia_fisicamente_bloqueado(self):
        link=ArduinoBridge()
        self.assertFalse(link.armed)
        self.assertFalse(link.connected)
        self.assertFalse(link.send_motion("FORWARD",25,100))
        self.assertIn("desconectado",link.status())

    def test_arduino_solo_actua_con_sensores_reales_y_limites(self):
        class SerialFake:
            is_open=True
            in_waiting=0
            def __init__(self):self.writes=[]
            def write(self,raw):self.writes.append(raw);return len(raw)
            def close(self):self.is_open=False
        fake=SerialFake()
        link=ArduinoBridge()
        link.serial=fake
        link.port="TEST"
        link.ready=True
        link.telemetry={"distance_cm":-1,"battery_pct":-1}
        link.last_rx=time.monotonic()
        self.assertIn("NO habilitado",link.arm())
        self.assertFalse(link.send_motion("FORWARD"))
        link.telemetry={"distance_cm":65,"battery_pct":87}
        link.last_rx=time.monotonic()
        self.assertIn("habilitado",link.arm())
        self.assertTrue(link.send_motion("FORWARD",100,600))
        self.assertIn(b"MOVE FORWARD 35 120\n",fake.writes)
        link.telemetry["distance_cm"]=9
        link.poll()
        self.assertFalse(link.armed)
        self.assertIn(b"STOP\n",fake.writes)
        link.close()
        self.assertFalse(fake.is_open)

    def test_ventana_real_inicia_aprendizaje_automatico(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=False)
        try:
            self.assertTrue(gui.auto)
            gui.toggle_auto()
            self.assertFalse(gui.auto)
            self.assertFalse(gui.hardware.armed)
            gui.toggle_auto()
            self.assertTrue(gui.auto)
            gui.robot.training.update(.05)
            gui.poll_guides()
            gui.robot.brain.autonomous_step()
            gui.draw(.017)
            self.assertIsNotNone(gui.last_portrait_state)
            self.assertGreater(len(gui.robot.brain.action_models),0)
        finally:
            gui.hardware.close()
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
