"""Validacion de AMBOT sin servidor HTTP ni navegador."""
import tempfile
import unittest
from pathlib import Path
import time
import math
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import APP_VERSION, DIRECTIONS, WORLD, Robot, Scene3D, ArduinoBridge, CHAIR_STYLES, ADD_CATALOG, HUMAN_JOINTS, VALIDATED_INTENTS, ROOM_NAME, ROOM_CELLS, ROOM_DOOR, ROOM_OBJECTS, FURNITURE_CELLS

class RobotTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.robot=Robot(Path(self.tmp.name)/"memoria.json")

    def test_version_y_mapa(self):
        self.assertEqual(APP_VERSION,"0.9.0")
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
        self.assertTrue(any(e["source"].startswith("voz:") for e in brain.episodes))
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

    def test_sillas_nuevas_iniciales_y_persistencia(self):
        furniture=self.robot.furniture
        self.assertEqual(len(furniture.chairs),3)
        self.assertEqual(set(CHAIR_STYLES),{"clasica","oficina","alta"})
        for item in furniture.chairs:
            self.assertFalse(self.robot.free(item["x"],item["z"]))
            self.assertEqual(self.robot.map_text().splitlines()[item["z"]][item["x"]],"S")
        loaded=Robot(self.robot.memory_path)
        self.assertEqual(loaded.furniture.chairs,furniture.chairs)
        self.robot.reset()
        self.assertEqual(self.robot.furniture.chairs,furniture.chairs)
        self.assertTrue(self.robot.free(self.robot.x,self.robot.z))

    def test_colocar_sillas_solo_en_suelo_disponible(self):
        editor=self.robot.furniture
        self.assertEqual(len(editor.chairs),3)
        for x,z in ((4,4),(4,5),(4,7),(7,3),(8,5),(6,5),
                    (5,3),(7,7),(3,3),(6,4),(-1,2),(6,2)):
            valid,_=editor.can_place(x,z)
            self.assertFalse(valid,(x,z))
        self.assertFalse(editor.can_place(True,3)[0])
        self.assertFalse(editor.place("mesa",5,4)[0])
        self.assertFalse(editor.place("clasica",5,4,7)[0])
        ok,message=editor.place("oficina",5,4,1)
        self.assertTrue(ok,message)
        self.assertFalse(self.robot.free(5,4))
        self.assertFalse(editor.place("clasica",5,4)[0])
        self.assertEqual(Robot(self.robot.memory_path).furniture.chairs[-1],
                         {"style":"oficina","x":5,"z":4,"orientation":1})
        result,message=editor.undo()
        self.assertTrue(result)
        self.assertIn("Quite",message)
        self.assertTrue(self.robot.free(5,4))
        self.assertEqual(len(Robot(self.robot.memory_path).furniture.chairs),3)

    def test_silla_no_bloquea_unica_puerta(self):
        valid,reason=self.robot.furniture.can_place(7,5)
        self.assertFalse(valid)
        self.assertIn("salida",reason)
        self.assertTrue(self.robot.free(*ROOM_DOOR))
        self.assertTrue(self.robot.furniture._route_exists(
            self.robot.furniture.occupied()))

    def test_click_3d_recupera_celda_del_suelo(self):
        import pygame
        pygame.init()
        try:
            scene=Scene3D(pygame)
            rect=pygame.Rect(260,83,625,530)
            scene.camera_update(rect)
            for cell in ((5,4),(6,5),(7,7),(8,5),(9,4)):
                x,z=scene.world(*cell)
                projected=scene.project((x,.02,z))
                self.assertIsNotNone(projected)
                screen=(round(projected[0]),round(projected[1]))
                self.assertTrue(rect.collidepoint(screen))
                self.assertEqual(scene.pick_floor(screen),cell)
            self.assertIsNone(scene.pick_floor((-100,-100)))
        finally:
            pygame.quit()

    def test_sillas_de_tres_modelos_en_entorno_3d(self):
        import pygame
        pygame.init()
        try:
            scene=Scene3D(pygame)
            scene.camera_update(pygame.Rect(0,0,900,580))
            before=len(scene.faces)
            scene.build_user_chairs(self.robot.furniture)
            self.assertGreater(len(scene.faces),before+45)
        finally:
            pygame.quit()

    def test_interfaz_boton_anadir_elige_tipo_y_clic_pone_silla(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        gui.robot=self.robot
        try:
            gui.draw(.016)
            self.assertIn("editor_toggle",gui.buttons)
            gui.handle_button("editor_toggle")
            self.assertTrue(gui.editor_mode)
            self.assertFalse(gui.auto)
            gui.draw(.017)
            for name in ("editor_style_clasica","editor_style_oficina",
                         "editor_style_alta","editor_rotate",
                         "editor_undo","editor_done"):
                self.assertIn(name,gui.buttons)
            gui.handle_button("editor_style_oficina")
            gui.handle_button("editor_rotate")
            x,z=gui.scene.world(5,4)
            p=gui.scene.project((x,.02,z))
            click=(round(p[0]),round(p[1]))
            self.assertTrue(gui.view.collidepoint(click))
            self.assertFalse(gui.editor_rect.colliderect(gui.view))
            self.assertFalse(gui.editor_rect.collidepoint(click))
            self.assertFalse(gui.training_rect.collidepoint(click))
            pygame.event.post(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,button=1,pos=click))
            pygame.event.post(pygame.event.Event(
                pygame.MOUSEBUTTONUP,button=1,pos=click))
            self.assertTrue(gui.events())
            self.assertFalse(gui.dragging)
            self.assertTrue(gui.robot.furniture.blocks(5,4))
            self.assertEqual(gui.robot.furniture.chairs[-1]["style"],"oficina")
            gui.handle_button("editor_done")
            self.assertFalse(gui.editor_mode)
            gui.draw(.017)
        finally:
            gui.hardware.close()
            pygame.quit()

    def test_editor_suspende_y_reanuda_autonomia(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        try:
            gui.auto=True
            gui.handle_button("editor_toggle")
            self.assertTrue(gui.editor_mode)
            self.assertFalse(gui.auto)
            gui.handle_button("editor_done")
            self.assertFalse(gui.editor_mode)
            self.assertTrue(gui.auto)
            gui.handle_button("editor_toggle")
            gui.handle_button("stop")
            gui.handle_button("editor_done")
            self.assertFalse(gui.auto)
        finally:
            gui.hardware.close()
            pygame.quit()

    def test_quitar_silla_por_clic_logico_y_deshacer(self):
        furniture=self.robot.furniture
        at=(5,3)
        self.assertTrue(furniture.blocks(*at))
        ok,message=furniture.remove("chair",at)
        self.assertTrue(ok,message)
        self.assertFalse(furniture.blocks(*at))
        self.assertTrue(self.robot.free(*at))
        self.assertEqual(len(furniture.chairs),2)
        self.assertFalse(furniture.remove("chair",at)[0])
        ok,message=furniture.undo()
        self.assertTrue(ok,message)
        self.assertTrue(furniture.blocks(*at))
        self.assertEqual(len(furniture.chairs),3)

    def test_quitar_muebles_originales_libera_colisiones(self):
        f=self.robot.furniture
        self.assertFalse(self.robot.free(4,4))
        self.assertFalse(self.robot.free(4,7))
        self.assertTrue(f.remove("fixture","mesa")[0])
        self.assertTrue(f.remove("fixture","cama")[0])
        self.assertTrue(self.robot.free(4,4))
        self.assertTrue(self.robot.free(4,7))
        self.assertIn("No hay cama",self.robot.training.try_rest())
        self.assertTrue(f.undo()[0])
        self.assertFalse(self.robot.free(4,7))
        self.assertTrue(f.undo()[0])
        self.assertFalse(self.robot.free(4,4))
        self.assertFalse(f.remove("fixture","pared")[0])
        self.assertFalse(f.remove("protected","AMBOT")[0])

    def test_quitar_cubo_que_robot_sujeta_y_restaurar(self):
        training=self.robot.training
        box=training.items["cubo"]
        box.held_by="AMBOT"
        self.robot.holding="cubo"
        ok,msg=self.robot.furniture.remove("movable","cubo")
        self.assertTrue(ok,msg)
        self.assertIsNone(self.robot.holding)
        self.assertNotIn("cubo",training.items)
        self.assertTrue(self.robot.furniture.undo()[0])
        self.assertIn("cubo",training.items)
        self.assertEqual(training.items["cubo"].held_by,"")
        self.assertFalse(self.robot.furniture.remove("movable","robot")[0])

    def test_quitar_objetos_moviles_no_deja_referencias_invalidas(self):
        f=self.robot.furniture
        for name in ("cubo","pelota","bloque"):
            self.assertTrue(f.remove("movable",name)[0])
        self.assertEqual(self.robot.training.items,{})
        self.assertEqual(self.robot.brain.sense(self.robot.training)["shapes"],{})
        self.assertIn("Aun no veo",self.robot.brain.compare_quantities(
            self.robot.training))
        for _ in range(25):
            self.robot.training.update(.05)
            self.robot.brain.autonomous_step()
        self.assertEqual(self.robot.training.items,{})
        self.assertTrue(f.undo()[0])
        self.assertIn("bloque",self.robot.training.items)

    def test_remocion_persistente_de_objetos_y_deshacer_despues_de_reabrir(self):
        f=self.robot.furniture
        self.assertTrue(f.remove("fixture","armario")[0])
        self.assertTrue(f.remove("fixture","ventana")[0])
        self.assertTrue(f.remove("fixture","alfombra")[0])
        self.assertTrue(f.remove("chair",(7,7))[0])
        self.assertTrue(f.remove("movable","pelota")[0])
        loaded=Robot(self.robot.memory_path)
        self.assertEqual(loaded.furniture.removed_fixed,
                         {"armario","ventana","alfombra"})
        self.assertEqual(loaded.furniture.removed_movables,{"pelota"})
        self.assertNotIn("pelota",loaded.training.items)
        self.assertTrue(loaded.free(7,3))
        self.assertTrue(loaded.free(7,7))
        self.assertTrue(loaded.furniture.undo()[0])
        self.assertIn("pelota",loaded.training.items)
        loaded2=Robot(self.robot.memory_path)
        self.assertIn("pelota",loaded2.training.items)
        self.assertEqual(loaded2.furniture.removed_movables,set())
        self.assertTrue(loaded2.furniture.undo()[0])
        self.assertTrue(loaded2.furniture.blocks(7,7))

    def test_no_restaurar_mueble_encima_de_robot(self):
        self.assertTrue(self.robot.furniture.remove("fixture","mesa")[0])
        self.robot.x,self.robot.z=4,4
        result,info=self.robot.furniture.undo()
        self.assertFalse(result)
        self.assertIn("Libera",info)
        self.robot.x,self.robot.z=6,5
        self.assertTrue(self.robot.furniture.undo()[0])
        self.assertFalse(self.robot.free(4,4))

    def test_quitar_silla_recien_agregada_no_afecta_contenido_anterior(self):
        f=self.robot.furniture
        self.assertTrue(f.place("alta",5,4,1)[0])
        self.assertTrue(f.remove("chair",(5,4))[0])
        self.assertTrue(f.undo()[0])
        self.assertEqual(f.chairs[-1]["style"],"alta")
        self.assertTrue(f.undo()[0])
        self.assertFalse(f.blocks(5,4))
        self.assertEqual(len(f.chairs),3)

    def test_deteccion_3d_no_permite_borrar_robot(self):
        import pygame
        pygame.init()
        try:
            scene=Scene3D(pygame)
            scene.camera_update(pygame.Rect(260,83,625,530))
            wx,wz=scene.world(self.robot.x,self.robot.z)
            center=scene.project((wx,1.65,wz))
            pick=scene.pick_object((int(center[0]),int(center[1])),self.robot)
            self.assertIsNotNone(pick)
            self.assertEqual(pick["kind"],"protected")
            self.assertIsNone(scene.pick_object((-500,-500),self.robot))
        finally:
            pygame.quit()

    def test_deteccion_directa_de_mueble_en_3d(self):
        import pygame
        pygame.init()
        try:
            scene=Scene3D(pygame)
            scene.camera_update(pygame.Rect(260,83,625,530))
            wx,wz=scene.world(4,4)
            target=scene.project((wx,1.04,wz))
            self.assertIsNotNone(target)
            pick=scene.pick_object((int(target[0]),int(target[1])),self.robot)
            self.assertIsNotNone(pick)
            self.assertEqual((pick["kind"],pick["key"]),("fixture","mesa"))
            self.assertTrue(self.robot.furniture.remove("fixture","mesa")[0])
            after=scene.pick_object((int(target[0]),int(target[1])),self.robot)
            self.assertNotEqual(after and after["key"],"mesa")
        finally:
            pygame.quit()

    def test_render_muebles_eliminados_desaparecen(self):
        import pygame
        pygame.init()
        try:
            scene=Scene3D(pygame)
            scene.camera_update(pygame.Rect(0,0,900,600))
            f=self.robot.furniture
            scene.build_room_details(f)
            before=len(scene.faces)
            self.assertTrue(f.remove("fixture","cama")[0])
            self.assertTrue(f.remove("fixture","mesa")[0])
            self.assertTrue(f.remove("fixture","armario")[0])
            scene.faces=[]
            scene.build_room_details(f)
            self.assertLess(len(scene.faces),before-15)
        finally:
            pygame.quit()

    def test_boton_quitar_conserva_autonomia_y_deshacer(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        gui.robot=self.robot
        try:
            gui.auto=True
            gui.draw(.016)
            self.assertIn("editor_remove",gui.buttons)
            gui.handle_button("editor_remove")
            self.assertTrue(gui.editor_mode)
            self.assertEqual(gui.editor_action,"remove")
            self.assertFalse(gui.auto)
            gui.draw(.016)
            for key in ("editor_mode_add","editor_mode_remove",
                        "editor_undo","editor_done"):
                self.assertIn(key,gui.buttons)
            gui.handle_button("editor_mode_add")
            self.assertEqual(gui.editor_action,"add")
            gui.handle_button("editor_mode_remove")
            self.assertEqual(gui.editor_action,"remove")
            self.assertFalse(gui.robot.furniture.remove("protected","ANDA")[0])
            gui.handle_button("editor_done")
            self.assertTrue(gui.auto)
        finally:
            gui.hardware.close()
            pygame.quit()

    def test_click_quitar_mesa_en_interfaz_y_deshacer(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        gui.robot=self.robot
        try:
            gui.draw(.016)
            gui.handle_button("editor_remove")
            gui.draw(.016)
            px,pz=gui.scene.world(4,4)
            p=gui.scene.project((px,1.04,pz))
            point=(int(p[0]),int(p[1]))
            self.assertTrue(gui.view.collidepoint(point))
            target=gui.scene.pick_object(point,gui.robot)
            self.assertEqual(target["key"],"mesa")
            pygame.event.post(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,button=1,pos=point))
            pygame.event.post(pygame.event.Event(
                pygame.MOUSEBUTTONUP,button=1,pos=point))
            gui.events()
            self.assertIn("mesa",gui.robot.furniture.removed_fixed)
            self.assertTrue(gui.robot.free(4,4))
            self.assertTrue(any(
                e["source"]=="cambio_entorno"
                for e in gui.robot.brain.episodes))
            gui.draw(.016)
            gui.handle_button("editor_undo")
            self.assertNotIn("mesa",gui.robot.furniture.removed_fixed)
            self.assertFalse(gui.robot.free(4,4))
            gui.handle_button("editor_done")
            self.assertFalse(gui.editor_mode)
        finally:
            gui.hardware.close()
            pygame.quit()

    def test_avatar_manual_con_flechas_y_colisiones(self):
        human=self.robot.human
        self.assertEqual((human.x,human.z),(10,5))
        self.assertEqual((self.robot.x,self.robot.z),(6,5))
        self.assertIn("moviste",human.move(3))
        self.assertEqual((human.x,human.z),(9,5))
        self.assertIn("moviste",human.move(3))
        self.assertEqual((human.x,human.z),ROOM_DOOR)
        self.assertIn("moviste",human.move(3))
        self.assertEqual((human.x,human.z),(7,5))
        self.assertIn("No puedes",human.move(3))
        self.assertEqual((human.x,human.z),(7,5))
        self.assertEqual((self.robot.x,self.robot.z),(6,5))
        self.assertEqual((Robot(self.robot.memory_path).human.x,
                          Robot(self.robot.memory_path).human.z),(7,5))

    def test_avatar_se_sienta_en_silla_y_se_levanta(self):
        human=self.robot.human
        self.assertIn("Acercate",human.sit())
        human.x,human.z=6,3
        self.assertIn("sentaste",human.sit())
        self.assertTrue(human.seated)
        self.assertEqual(human.seat,(5,3))
        self.assertIn("Primero",human.move(1))
        self.assertFalse(self.robot.furniture.remove("chair",(5,3))[0])
        self.assertTrue(Robot(self.robot.memory_path).human.seated)
        self.assertIn("levantaste",human.stand())
        self.assertEqual((human.x,human.z),(6,3))
        self.assertFalse(human.seated)
        self.assertTrue(self.robot.furniture.remove("chair",(5,3))[0])

    def test_articulaciones_libres_y_posturas_del_avatar(self):
        human=self.robot.human
        self.assertEqual(set(human.joints),set(HUMAN_JOINTS))
        self.assertIn("85",human.change_joint("brazo_der",150))
        self.assertIn("75",human.change_joint("brazo_der",-10))
        self.assertIn("saludar",human.pose("saludar"))
        self.assertEqual(human.joints["codo_der"],35)
        self.assertIn("agacharse",human.pose("agacharse"))
        self.assertEqual(human.joints["torso"],35)
        self.assertIn("reposo",human.pose("reposo"))
        self.assertTrue(all(v==0 for v in human.joints.values()))
        self.assertEqual(Robot(self.robot.memory_path).human.joints,human.joints)

    def test_avatar_dibujado_es_independiente_de_ambot(self):
        import pygame
        pygame.init()
        try:
            scene=Scene3D(pygame)
            scene.camera_update(pygame.Rect(0,0,900,550))
            old=(scene.rx,scene.rz,scene.angle,scene.walk)
            scene.build_human(self.robot.human)
            self.assertGreater(len(scene.faces),40)
            self.assertEqual((scene.rx,scene.rz,scene.angle,scene.walk),old)
            targets=scene.object_bounds(self.robot)
            self.assertTrue(any(o["key"]=="TU PERSONAJE" and
                                o["kind"]=="protected" for o in targets))
        finally:
            pygame.quit()

    def test_maestros_pueden_quitarse_y_reponerse(self):
        f=self.robot.furniture
        self.assertTrue(f.remove("guide","DEX")[0])
        self.assertEqual([g.name for g in self.robot.training.guides],
                         ["ANDA","SOMA"])
        self.assertIn("DEX",f.removed_guides)
        self.assertTrue(f.undo()[0])
        self.assertEqual([g.name for g in self.robot.training.guides],
                         ["ANDA","DEX","SOMA"])
        self.assertFalse(f.remove("guide","AMBOT")[0])

    def test_sin_maestros_ambot_explora_y_no_se_cae(self):
        f=self.robot.furniture
        for name in ("ANDA","DEX","SOMA"):
            self.assertTrue(f.remove("guide",name)[0])
        self.assertEqual(len(self.robot.training.guides),0)
        self.assertIn("No hay",self.robot.training.focus_guide())
        self.assertIn("No hay",self.robot.command("guia 1"))
        for _ in range(32):
            self.robot.training.update(.05)
            result=self.robot.brain.autonomous_step()
            self.assertTrue(result)
        restored=Robot(self.robot.memory_path)
        self.assertEqual(restored.training.guides,[])
        self.assertTrue(restored.furniture.undo()[0])
        self.assertEqual([g.name for g in restored.training.guides],["SOMA"])
        self.assertIn("ANDA",restored.furniture.removed_guides)

    def test_agregar_camas_mesas_armarios_persistentes(self):
        f=self.robot.furniture
        self.assertEqual(len(ADD_CATALOG),9)
        self.assertTrue(f.place_object("cama",10,3,2)[0])
        self.assertFalse(self.robot.free(10,3))
        self.assertFalse(self.robot.free(11,3))
        self.assertFalse(f.place_object("mesa",10,3)[0])
        self.assertTrue(f.place_object("mesa",10,4)[0])
        self.assertTrue(f.place_object("armario",12,5)[0])
        self.assertEqual(len(f.extra_fixtures),3)
        loaded=Robot(self.robot.memory_path)
        self.assertEqual(len(loaded.furniture.extra_fixtures),3)
        self.assertFalse(loaded.free(10,3))
        self.assertFalse(loaded.free(11,3))
        self.assertFalse(loaded.free(10,4))
        self.assertFalse(loaded.free(12,5))
        self.assertTrue(f.undo()[0])
        self.assertTrue(self.robot.free(12,5))

    def test_pelotas_cubos_y_bloques_adicionales(self):
        f=self.robot.furniture
        self.assertTrue(f.place_object("pelota",9,3)[0])
        self.assertTrue(f.place_object("cubo",10,4)[0])
        self.assertTrue(f.place_object("bloque",12,5)[0])
        names=[key for key in self.robot.training.items
               if "_" in key]
        self.assertEqual(len(names),3)
        self.assertEqual(self.robot.training.items[names[0]].shape,"ball")
        self.assertIn(names[0],Robot(self.robot.memory_path).training.items)
        self.assertTrue(f.remove("movable",names[0])[0])
        self.assertNotIn(names[0],self.robot.training.items)
        self.assertNotIn(names[0],f.extra_objects)
        self.assertTrue(f.undo()[0])
        self.assertIn(names[0],self.robot.training.items)

    def test_muebles_anadidos_se_dibujan_y_se_quitan(self):
        import pygame
        pygame.init()
        try:
            f=self.robot.furniture
            self.assertTrue(f.place_object("cama",10,3)[0])
            self.assertTrue(f.place_object("mesa",10,4)[0])
            self.assertTrue(f.place_object("armario",12,5)[0])
            scene=Scene3D(pygame)
            scene.camera_update(pygame.Rect(0,0,900,550))
            scene.build_custom_fixtures(f)
            self.assertGreater(len(scene.faces),50)
            choices=scene.object_bounds(self.robot)
            added=[o for o in choices if o["kind"]=="fixture_added"]
            self.assertEqual(len(added),3)
            self.assertTrue(f.remove("fixture_added",added[0]["key"])[0])
            self.assertEqual(len(f.extra_fixtures),2)
            self.assertTrue(f.undo()[0])
            self.assertEqual(len(f.extra_fixtures),3)
        finally:
            pygame.quit()

    def test_editor_catalogo_y_boton_de_avatar(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        gui.robot=self.robot
        try:
            gui.draw(.016)
            self.assertIn("avatar_toggle",gui.buttons)
            self.assertIn("avatar_sit",gui.buttons)
            self.assertIn("avatar_plus",gui.buttons)
            before=gui.robot.human.joints["brazo_der"]
            gui.handle_button("avatar_plus")
            self.assertEqual(gui.robot.human.joints["brazo_der"],before+10)
            gui.handle_button("editor_toggle")
            gui.draw(.016)
            for name in ("editor_category_sillas","editor_category_muebles",
                         "editor_category_objetos"):
                self.assertIn(name,gui.buttons)
            gui.handle_button("editor_category_muebles")
            gui.draw(.016)
            self.assertIn("editor_kind_cama",gui.buttons)
            gui.handle_button("editor_kind_armario")
            self.assertEqual(gui.editor_choice,"armario")
            gui.handle_button("editor_category_objetos")
            gui.draw(.016)
            self.assertIn("editor_kind_pelota",gui.buttons)
            gui.handle_button("editor_kind_pelota")
            self.assertEqual(gui.editor_choice,"pelota")
            gui.handle_button("editor_done")
            self.assertFalse(gui.editor_mode)
        finally:
            gui.hardware.close()
            pygame.quit()

    def test_flechas_controlan_usuario_y_wasd_ambot(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        gui.robot=self.robot
        try:
            e=pygame.event.Event(pygame.KEYDOWN,key=pygame.K_LEFT,unicode="")
            gui.keydown(e)
            self.assertEqual((self.robot.human.x,self.robot.human.z),(10,5))
            self.assertEqual(self.robot.human.facing,2)
            gui.keydown(pygame.event.Event(
                pygame.KEYDOWN,key=pygame.K_UP,unicode=""))
            self.assertEqual((self.robot.human.x,self.robot.human.z),(10,6))
            self.assertEqual((self.robot.x,self.robot.z),(6,5))
            gui.handle_button("avatar_sit")
            self.assertFalse(gui.robot.human.seated)
            gui.draw(.016)
            self.assertIn("avatar_stand",gui.buttons)
        finally:
            gui.hardware.close()
            pygame.quit()

    def test_validacion_solo_aprende_si_usuario_confirma(self):
        lang=self.robot.language
        question=lang.propose("La luna gira alrededor de la Tierra")
        self.assertIn("ENTENDI BIEN",question)
        self.assertNotIn("luna",self.robot.brain.concepts)
        self.assertNotIn("la luna gira alrededor de la tierra",lang.confirmed)
        answer=lang.confirm()
        self.assertIn("VALIDADA POR TI",answer)
        self.assertIn("luna",self.robot.brain.concepts)
        self.assertIn("la luna gira alrededor de la tierra",lang.confirmed)
        next_lang=Robot(self.robot.memory_path).language
        self.assertIn("la luna gira alrededor de la tierra",next_lang.confirmed)
        self.assertIsNone(next_lang.pending)

    def test_correcion_ensenar_frase_previamente_incorrecta(self):
        lang=self.robot.language
        self.assertIn("ENTENDI BIEN",lang.propose("Haz una cosa distinta"))
        self.assertIn("No memorizare",lang.reject())
        self.assertEqual(lang.confirmed,{})
        self.assertIn("Postura",lang.correct("saludar"))
        self.assertEqual(lang.confirmed["haz una cosa distinta"]["intent"],
                         "saludar")
        self.assertIn("Postura",lang.propose("Haz una cosa distinta"))

    def test_pregunta_validada_respuesta_y_reutilizacion(self):
        lang=self.robot.language
        text="¿Por qué existe la gravedad?"
        self.assertIn("ENTENDI BIEN",lang.propose(text))
        answer=lang.confirm()
        self.assertIn("No conozco",answer)
        self.assertIn("Guarde",self.robot.command(
            "responde La gravedad curva el espacio-tiempo."))
        self.assertIn("Me explicaste:",lang.propose(text))
        next_lang=Robot(self.robot.memory_path).language
        self.assertIn("Me explicaste:",next_lang.propose(text))

    def test_validacion_interfaz_si_no_corregir(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        gui.robot=self.robot
        try:
            gui.execute("hablar la astronomia estudia estrellas",quiet=False)
            self.assertIsNotNone(gui.robot.language.pending)
            gui.draw(.016)
            for key in ("validation_yes","validation_no","validation_correct"):
                self.assertIn(key,gui.buttons)
            gui.handle_button("validation_no")
            self.assertTrue(gui.robot.language.wait_correction)
            gui.handle_button("validation_correct")
            self.assertTrue(gui.input_focus)
            self.assertEqual(gui.input_value,"corrige ")
            gui.execute("corrige dato")
            self.assertIsNone(gui.robot.language.pending)
            self.assertIn("astronomia",gui.robot.brain.concepts)
        finally:
            gui.hardware.close()
            pygame.quit()

    def test_ambot_observa_al_humano_al_moverse_y_sentarse(self):
        human=self.robot.human
        brain=self.robot.brain
        self.assertEqual(self.robot.training.confidence["caminar"],0.0)
        self.assertIn("moviste",human.move(3))
        self.assertGreater(self.robot.training.confidence["caminar"],0)
        self.assertTrue(any(
            e["source"]=="observacion_humano"
            for e in brain.episodes))
        human.x,human.z=6,3
        self.assertIn("sentaste",human.sit())
        self.assertTrue(any(
            q["topic"]=="demostracion:sentarse"
            for q in brain.questions))
        self.assertTrue(any(
            e["source"]=="observacion_humano"
            for e in Robot(self.robot.memory_path).brain.episodes))

    def test_control_tanque_avatar_gira_sin_deslizar(self):
        h=self.robot.human
        start=(h.x,h.z)
        self.assertEqual(h.facing,3)
        msg=h.turn("derecha")
        self.assertIn("Giraste",msg)
        self.assertEqual((h.x,h.z),start)
        self.assertEqual(h.facing,0)
        msg=h.turn("izquierda")
        self.assertIn("Giraste",msg)
        self.assertEqual((h.x,h.z),start)
        self.assertEqual(h.facing,3)
        self.assertIn("moviste",h.advance())
        self.assertEqual((h.x,h.z),(9,5))
        self.assertEqual(h.facing,3)
        self.assertIn("moviste",h.advance(reverse=True))
        self.assertEqual((h.x,h.z),start)
        self.assertEqual(h.facing,3)
        self.assertEqual(Robot(self.robot.memory_path).human.facing,3)

    def test_control_tanque_avatar_no_depende_de_camara(self):
        import pygame
        pygame.init()
        try:
            camera=Scene3D(pygame)
            camera.yaw=math.pi
            camera.pitch=.65
            h=self.robot.human
            facing=h.facing
            self.assertEqual(facing,3)
            self.assertIn("moviste",h.advance(reverse=True))
            self.assertEqual((h.x,h.z),(11,5))
            self.assertEqual(h.facing,facing)
            camera.yaw=-math.pi/2
            self.assertIn("moviste",h.advance())
            self.assertEqual((h.x,h.z),(10,5))
            self.assertEqual(h.facing,facing)
        finally:
            pygame.quit()

    def test_control_tanque_avatar_sentado_bloquea_conduccion(self):
        h=self.robot.human
        h.x,h.z=6,3
        self.assertIn("sentaste",h.sit())
        old=(h.x,h.z,h.facing)
        self.assertIn("sentado",h.turn("derecha"))
        self.assertIn("sentado",h.advance())
        self.assertIn("sentado",h.advance(reverse=True))
        self.assertEqual((h.x,h.z,h.facing),old)
        self.assertIn("levantaste",h.stand())

    def test_controles_tanque_en_teclado_y_repeticion(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        gui.robot=self.robot
        try:
            human=gui.robot.human
            gui.keydown(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_LEFT,
                                           unicode=""))
            self.assertEqual((human.x,human.z),(10,5))
            self.assertEqual(human.facing,2)
            self.assertEqual(len(gui._tank_held),1)
            for _ in range(8):
                gui.update_tank_controls(.05)
            self.assertEqual(human.facing,1)
            self.assertEqual((human.x,human.z),(10,5))
            gui.events()
            pygame.event.post(pygame.event.Event(pygame.KEYUP,
                                                  key=pygame.K_LEFT))
            gui.events()
            self.assertNotIn(pygame.K_LEFT,gui._tank_held)
            gui.update_tank_controls(.5)
            self.assertEqual(human.facing,1)
            gui.keydown(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_UP,
                                           unicode=""))
            self.assertEqual((human.x,human.z),(11,5))
            for _ in range(8):
                gui.update_tank_controls(.05)
            self.assertEqual((human.x,human.z),(12,5))
            pygame.event.post(pygame.event.Event(pygame.KEYUP,
                                                  key=pygame.K_UP))
            gui.events()
            gui.update_tank_controls(1)
            self.assertEqual((human.x,human.z),(12,5))
        finally:
            gui.hardware.close()
            pygame.quit()

    def test_controles_tanque_wasd_ambot_sin_strafe(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        gui.robot=self.robot
        gui.robot.training.confidence["caminar"]=1.0
        try:
            robot=gui.robot
            gui.keydown(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_a,
                                           unicode=""))
            self.assertEqual((robot.x,robot.z),(6,5))
            self.assertEqual(robot.facing,0)
            pygame.event.post(pygame.event.Event(pygame.KEYUP,key=pygame.K_a))
            gui.events()
            gui.keydown(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_d,
                                           unicode=""))
            self.assertEqual((robot.x,robot.z),(6,5))
            self.assertEqual(robot.facing,1)
            pygame.event.post(pygame.event.Event(pygame.KEYUP,key=pygame.K_d))
            gui.events()
            gui.keydown(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_w,
                                           unicode=""))
            self.assertEqual((robot.x,robot.z),(7,5))
            self.assertEqual(robot.facing,1)
            pygame.event.post(pygame.event.Event(pygame.KEYUP,key=pygame.K_w))
            gui.events()
            gui.keydown(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_s,
                                           unicode=""))
            self.assertEqual((robot.x,robot.z),(6,5))
            self.assertEqual(robot.facing,1)
        finally:
            gui.hardware.close()
            pygame.quit()

    def test_teachers_tank_giran_antes_de_moverse_sin_diagonal(self):
        from app import facing_radians, TANK_ROTATION_RATE
        tr=self.robot.training
        guide=tr.guides[0]
        guide.x,guide.z=5.0,5.0
        guide.facing=0
        guide.heading=facing_radians(0)
        self.assertFalse(tr._tank_guide_step(guide,(7.0,6.0),.05))
        self.assertAlmostEqual(guide.x,5.0)
        self.assertAlmostEqual(guide.z,5.0)
        self.assertTrue(guide.turning)
        self.assertAlmostEqual(guide.heading,TANK_ROTATION_RATE*.05)
        history=[]
        for _ in range(240):
            prior=(guide.x,guide.z)
            done=tr._tank_guide_step(guide,(7.0,6.0),.05)
            moved_x=abs(guide.x-prior[0])>1e-8
            moved_z=abs(guide.z-prior[1])>1e-8
            self.assertFalse(moved_x and moved_z)
            if moved_x or moved_z:
                self.assertFalse(guide.turning)
                vector=(guide.x-prior[0],guide.z-prior[1])
                facing=DIRECTIONS[guide.facing]
                self.assertGreater(vector[0]*facing[0]+vector[1]*facing[1],0)
            history.append((guide.x,guide.z))
            if done:break
        self.assertTrue(done)
        self.assertAlmostEqual(guide.x,7.0)
        self.assertAlmostEqual(guide.z,6.0)
        self.assertEqual(guide.facing,2)

    def test_tres_maestros_marchan_sin_movimientos_laterales(self):
        training=self.robot.training
        previous={g.name:(g.x,g.z) for g in training.guides}
        for _ in range(750):
            training.update(.05)
            for guide in training.guides:
                x,z=previous[guide.name]
                dx,dz=guide.x-x,guide.z-z
                self.assertFalse(abs(dx)>.001 and abs(dz)>.001,
                                 (guide.name,dx,dz))
                if abs(dx)+abs(dz)>.00001:
                    orient=DIRECTIONS[guide.facing]
                    self.assertGreaterEqual(dx*orient[0]+dz*orient[1],-1e-6)
                previous[guide.name]=(guide.x,guide.z)
        self.assertGreater(training.observations,8)

    def test_teclas_de_tanque_se_detienen_al_abrir_chat_o_editor(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
        import pygame
        from app import DesktopApp
        gui=DesktopApp(pygame,smoke=True)
        gui.robot=self.robot
        try:
            gui.keydown(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_UP,
                                           unicode=""))
            self.assertEqual(len(gui._tank_held),1)
            gui.input_focus=True
            gui.update_tank_controls(.5)
            self.assertEqual(gui._tank_held,{})
            gui.input_focus=False
            gui.keydown(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_RIGHT,
                                           unicode=""))
            self.assertEqual(len(gui._tank_held),1)
            gui.toggle_editor()
            self.assertEqual(gui._tank_held,{})
            before=self.robot.human.facing
            gui.keydown(pygame.event.Event(pygame.KEYDOWN,key=pygame.K_RIGHT,
                                           unicode=""))
            self.assertEqual(self.robot.human.facing,before)
            self.assertEqual(gui._tank_held,{})
            gui.toggle_editor()
        finally:
            gui.hardware.close()
            pygame.quit()

    def test_render_tank_orientacion_del_avatar_y_maestro(self):
        import pygame
        pygame.init()
        try:
            camera=Scene3D(pygame)
            camera.camera_update(pygame.Rect(0,0,900,550))
            human=self.robot.human
            camera.build_human(human)
            angle=camera.human_angle
            human.turn("derecha")
            camera.frame_dt=.05
            camera.build_human(human)
            self.assertNotEqual(camera.human_angle,angle)
            self.assertNotEqual(camera.human_angle,
                                camera.orient(human.facing))
            guide=self.robot.training.guides[0]
            guide.heading=.45
            camera.rx,camera.rz=guide.x,guide.z
            camera.build_robot(guide,0,0,tint=guide.color)
            self.assertAlmostEqual(camera.angle,guide.heading)
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
