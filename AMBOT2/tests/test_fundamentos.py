"""Pruebas de AMBOT2: cuerpo, dedos, fisica, lenguaje y aprendizaje."""
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from panda3d.core import NodePath
from body.robot import Humanoid, FINGER_NAMES, WALK_SPEED, TURN_SPEED, tank_inputs, JOINT_GROUPS, JOINT_LIMITS, JOINT_NAMES
from body.grasp import GraspSystem
from engine.world import LabWorld
from brain.learning import ObservationLearner
from language.understanding import Pronouns, LanguageMind
from teacher.recorder import DemonstrationRecorder
from editor.objects import ObjectEditor


class BasisTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.data=Path(self.temporary.name)

    def test_cuerpo_tiene_30_articulaciones_con_limites(self):
        self.assertEqual(len(JOINT_NAMES),30)
        self.assertEqual(len(JOINT_GROUPS),5)
        self.assertEqual(len(set(JOINT_NAMES)),30)
        root=NodePath("cuerpo")
        maestro=Humanoid(root,"MAESTRO",(.3,.7,.9,1),teacher=True)
        aprendiz=Humanoid(root,"AMBOT",(.9,.5,.7,1),position=(3,0,0))
        self.assertEqual(set(maestro.joints),set(JOINT_NAMES))
        self.assertEqual(set(aprendiz.joints),set(JOINT_NAMES))
        self.assertIn("cuello_flex",maestro.joints)
        self.assertIn("codo_izq",maestro.joints)
        self.assertIn("rodilla_der",maestro.joints)
        self.assertIn("tobillo_izq_lateral",maestro.joints)
        self.assertEqual(maestro.set_joint("codo_izq",1000),145)
        self.assertEqual(maestro.set_joint("tobillo_izq_lateral",-1000),-30)
        with self.assertRaises(ValueError):
            maestro.set_joint("articulacion_inventada",10)
        maestro.reset_joints()
        self.assertTrue(all(value==0 for value in maestro.joints.values()))

    def test_movimientos_articulados_mueven_segmentos_y_sensores(self):
        root=NodePath("cuerpo")
        robot=Humanoid(root,"MAESTRO",(.2,.7,.9,1),teacher=True)
        head=robot._joints["cabeza"].getPos()
        arm=robot.hand_points("izquierda")[-1]
        hand=robot.all_fingertips()[("izquierda",1)]
        right=robot.hand_points("derecha")[-1]
        ankle=robot._joints["pierna_izquierda_tobillo"].getPos()
        robot.set_joint("cuello_flex",35)
        self.assertNotEqual(robot._joints["cabeza"].getPos(),head)
        robot.set_joint("hombro_izq_elev",55)
        self.assertNotEqual(robot.hand_points("izquierda")[-1],arm)
        self.assertNotEqual(robot.all_fingertips()[("izquierda",1)],hand)
        self.assertEqual(robot.hand_points("derecha")[-1],right)
        robot.set_joint("cadera_izq_flex",40)
        self.assertNotEqual(robot._joints["pierna_izquierda_tobillo"].getPos(),ankle)
        robot.set_joint("muneca_izq_giro",38)
        self.assertNotEqual(robot.all_fingertips()[("izquierda",1)],hand)
        self.assertEqual(len(robot.all_fingertips()),10)

    def test_pose_articulaciones_serializable_y_retrocompatible(self):
        root=NodePath("cuerpo")
        a=Humanoid(root,"MAESTRO",(.3,.8,.9,1),teacher=True)
        a.set_joint("hombro_der_giro",-43)
        a.set_joint("rodilla_izq",100)
        a.finger("izquierda",3,.7)
        position=a.pose()
        self.assertEqual(position["joints"]["hombro_der_giro"],-43)
        b=Humanoid(root,"AMBOT",(.8,.4,.7,1))
        b.set_pose(position)
        self.assertEqual(b.joints["rodilla_izq"],100)
        self.assertEqual(b.joints["hombro_der_giro"],-43)
        self.assertAlmostEqual(b.curls["izquierda"][3],.7)
        b.set_pose({"heading":20,"fingers":{"derecha":[0,0,0,0,0]}})
        self.assertEqual(b.joints["rodilla_izq"],100)

    def test_aprendiz_observa_articulaciones_individuales(self):
        root=NodePath("aprendizaje")
        maestro=Humanoid(root,"MAESTRO",(.3,.8,.9,1),teacher=True)
        ambot=Humanoid(root,"AMBOT",(.8,.4,.7,1))
        mind=ObservationLearner(self.data/"motor-joints.json")
        before=maestro.pose()
        maestro.set_joint("codo_izq",82)
        maestro.set_joint("hombro_der_elev",48)
        mind.observe("flexionar brazos",[before,maestro.pose()])
        self.assertEqual(mind.episodes,1)
        mind.try_skill("flexionar brazos",ambot)
        self.assertGreater(ambot.joints["codo_izq"],0)
        self.assertGreater(ambot.joints["hombro_der_elev"],0)
        self.assertEqual(ambot.joints["rodilla_izq"],0)
        mind.save()
        self.assertIn("joint_codo_izq",ObservationLearner(mind.path).policies["flexionar brazos"]["delta"])

    def test_controles_tanque_y_flechas(self):
        self.assertEqual(tank_inputs({"w"}),(1,0))
        self.assertEqual(tank_inputs({"s"}),(-1,0))
        self.assertEqual(tank_inputs({"a"}),(0,1))
        self.assertEqual(tank_inputs({"d"}),(0,-1))
        self.assertEqual(tank_inputs({"arrow_up","arrow_left"}),(1,1))
        self.assertEqual(tank_inputs({"arrow_down","arrow_right"}),(-1,-1))
        self.assertEqual(tank_inputs({"w","s","a","d"}),(0,0))
        self.assertEqual(tank_inputs(set()),(0,0))

    def test_girar_sobre_eje_sin_traslacion(self):
        root=NodePath("laboratorio")
        teacher=Humanoid(root,"MAESTRO",(.1,.7,.9,1),teacher=True)
        origin=teacher.node.getPos(root)
        for _ in range(10):
            teacher.drive(0,1,.05)  # A: gira a la izquierda.
        self.assertAlmostEqual(teacher.heading,TURN_SPEED*.5,places=3)
        self.assertEqual(teacher.node.getPos(root),origin)
        self.assertFalse(teacher.walking)
        for _ in range(10):
            teacher.drive(0,-1,.05)  # D: gira a la derecha.
        self.assertAlmostEqual(teacher.heading,0,places=5)
        self.assertEqual(teacher.node.getPos(root),origin)

    def test_avance_retroceso_y_sin_desplazamiento_lateral(self):
        import math
        root=NodePath("laboratorio")
        teacher=Humanoid(root,"MAESTRO",(.1,.7,.9,1),teacher=True)
        teacher.drive(1,0,.05)
        self.assertAlmostEqual(teacher.node.getX(root),0)
        self.assertAlmostEqual(teacher.node.getY(root),WALK_SPEED*.05)
        teacher.drive(-1,0,.05)
        self.assertAlmostEqual(teacher.node.getX(root),0)
        self.assertAlmostEqual(teacher.node.getY(root),0)
        teacher.turn(90)
        before=teacher.node.getPos(root)
        teacher.drive(1,0,.05)
        after=teacher.node.getPos(root)
        self.assertLess(after.x,before.x)
        self.assertAlmostEqual(after.y,before.y)
        theta=math.radians(teacher.heading)
        side=(after.x-before.x)*math.cos(theta)+(after.y-before.y)*math.sin(theta)
        self.assertAlmostEqual(side,0,places=5)
        before=after
        teacher.drive(1,-1,.05)  # W+D: avance curvo.
        after=teacher.node.getPos(root)
        theta=math.radians(teacher.heading)
        side=(after.x-before.x)*math.cos(theta)+(after.y-before.y)*math.sin(theta)
        self.assertAlmostEqual(side,0,places=5)

    def test_ambot_imita_rotacion_y_avance_frontal(self):
        root=NodePath("laboratorio")
        teacher=Humanoid(root,"MAESTRO",(.1,.7,.9,1),teacher=True)
        baby=Humanoid(root,"AMBOT",(.9,.4,.8,1),position=(3,0,0))
        learner=ObservationLearner(self.data/"giro-tanque.json")
        start=teacher.pose()
        for _ in range(8):
            teacher.drive(0,1,.05)
        learner.observe("girar izquierda",[start,teacher.pose()])
        previous=baby.node.getPos(root)
        self.assertIn("probando",learner.try_skill("girar izquierda",baby))
        self.assertGreater(baby.heading,0)
        self.assertEqual(baby.node.getPos(root),previous)
        teacher.turn(-teacher.heading)
        start=teacher.pose()
        for _ in range(8):
            teacher.drive(1,0,.05)
        learner.observe("avanzar",[start,teacher.pose()])
        baby.turn(90-baby.heading)
        before=baby.node.getPos(root)
        learner.try_skill("avanzar",baby)
        after=baby.node.getPos(root)
        self.assertLess(after.x,before.x)
        self.assertAlmostEqual(after.y,before.y,places=5)

    def test_dos_personajes_diez_dedos_por_robot(self):
        root=NodePath("laboratorio")
        teacher=Humanoid(root,"MAESTRO",(.1,.7,.9,1),teacher=True)
        baby=Humanoid(root,"AMBOT",(.9,.4,.8,1),position=(3,0,0))
        self.assertEqual({teacher.name,baby.name},{"MAESTRO","AMBOT"})
        self.assertTrue(teacher.teacher)
        self.assertFalse(baby.teacher)
        self.assertEqual(len(FINGER_NAMES),5)
        self.assertEqual(len(teacher.all_fingertips()),10)
        self.assertEqual(len(baby.all_fingertips()),10)
        old=teacher.all_fingertips()[("izquierda",1)]
        teacher.finger("izquierda",1,.95)
        self.assertNotEqual(old,teacher.all_fingertips()[("izquierda",1)])

    def test_mundo_bullet_gravedad_y_editor(self):
        root=NodePath("mundo")
        lab=LabWorld(root)
        obj=lab.spawn("cubo",name="Mi cubo",pos=(0,0,2))
        self.assertEqual(obj.mass,1.0)
        for _ in range(200):
            lab.step(1/120)
        self.assertLess(obj.np.getZ(),1)
        self.assertGreater(obj.np.getZ(),.1)
        editor=ObjectEditor(lab,self.data/"escena.json")
        new=editor.add("cuadro",position=(1,2,1))
        self.assertEqual(editor.selected,new.oid)
        editor.rename("Marco grande")
        editor.save()
        editor.delete_selected()
        self.assertTrue(editor.load())
        self.assertEqual(len(lab.objects),2)
        self.assertIn("Marco grande",[o.name for o in lab.objects.values()])

    def test_colisiones_dedos_y_restriccion_fisica(self):
        root=NodePath("mundo")
        lab=LabWorld(root)
        teacher=Humanoid(root,"MAESTRO",(.3,.8,.9,1),teacher=True)
        grasp=GraspSystem(lab,teacher)
        self.assertEqual(len(grasp.fingers),10)
        self.assertEqual(len(grasp.palms),2)
        teacher.hand_close("izquierda",1)
        grasp.sync()
        point=teacher.all_fingertips()[("izquierda",1)]
        obj=lab.spawn("caja",pos=tuple(point),size=(1.0,1.0,1.0),mass=.5)
        ok,contacts=grasp.inspect("izquierda",obj)
        self.assertTrue(ok,contacts)
        obj.np.setPos(5,5,3)
        no_touch,_=grasp.inspect("izquierda",obj)
        self.assertFalse(no_touch)
        obj.np.setPos(point)
        success,msg=grasp.try_grasp("izquierda",obj)
        self.assertTrue(success,msg)
        self.assertIn("izquierda",grasp.held())
        grasp.release("izquierda")
        self.assertEqual(grasp.held(),{})
        self.assertEqual(len(lab.physics.constraints),0)

    def test_cuadro_sostenido_con_dos_manos(self):
        root=NodePath("mundo")
        lab=LabWorld(root)
        teacher=Humanoid(root,"MAESTRO",(.3,.8,.9,1),teacher=True)
        grasp=GraspSystem(lab,teacher)
        teacher.hand_close("izquierda",1)
        teacher.hand_close("derecha",1)
        grasp.sync()
        tips=teacher.all_fingertips()
        left=tips[("izquierda",1)]
        right=tips[("derecha",1)]
        center=(left+right)*.5
        board=lab.spawn("cuadro",name="Cuadro a dos manos",
                        pos=tuple(center),size=(2.0,.19,1.0),mass=1.8)
        contact_left,detail_left=grasp.inspect("izquierda",board)
        contact_right,detail_right=grasp.inspect("derecha",board)
        self.assertTrue(contact_left,detail_left)
        self.assertTrue(contact_right,detail_right)
        self.assertTrue(grasp.try_grasp("izquierda",board)[0])
        self.assertTrue(grasp.try_grasp("derecha",board)[0])
        self.assertEqual(len(lab.physics.constraints),2)
        self.assertEqual(set(grasp.held()),{"izquierda","derecha"})
        teacher.hand_close("izquierda",0)
        grasp.auto_check()
        self.assertEqual(set(grasp.held()),{"derecha"})
        self.assertEqual(len(lab.physics.constraints),1)
        grasp.release_all()
        self.assertEqual(len(lab.physics.constraints),0)

    def test_agarre_por_cerrar_dedos_sin_boton(self):
        root=NodePath("plano")
        lab=LabWorld(root)
        teacher=Humanoid(root,"MAESTRO",(.3,.8,.9,1),teacher=True)
        grasp=GraspSystem(lab,teacher)
        finger=teacher.all_fingertips()[("izquierda",1)]
        item=lab.spawn("caja",pos=tuple(finger),size=(1,1,1),mass=1)
        grasp.sync()
        self.assertEqual(grasp.auto_acquire(),[])
        teacher.hand_close("izquierda",1)
        grasp.sync()
        acquired=grasp.auto_acquire()
        self.assertTrue(acquired,"Al tocar y cerrar los dedos debe sujetar")
        self.assertIn("izquierda",grasp.held())
        teacher.hand_close("izquierda",0)
        grasp.auto_check()
        self.assertEqual(grasp.held(),{})

    def test_pronombres_contextuales(self):
        roles=Pronouns()
        self.assertEqual(roles.resolve("yo","maestro","ambot"),["maestro"])
        self.assertEqual(roles.resolve("tú","maestro","ambot"),["ambot"])
        self.assertEqual(roles.resolve("yo","ambot","maestro"),["ambot"])
        self.assertEqual(roles.resolve("tú","ambot","maestro"),["maestro"])
        self.assertEqual(roles.resolve("nosotros","maestro","ambot"),["ambot","maestro"])
        self.assertEqual(roles.resolve("vosotros","maestro","ambot"),["ambot"])

    def test_palabras_y_preguntas_persistentes(self):
        l=LanguageMind(self.data/"lenguaje.json")
        self.assertIn("no se",l.hear("¿Qué es esto?","cuadro-001"))
        self.assertIn("cuadro",l.hear("Esto es un cuadro","cuadro-001"))
        self.assertIn("cuadro",l.hear("¿Qué es esto?","cuadro-001"))
        self.assertIn("maestro",l.hear("yo","cuadro-001"))
        self.assertEqual(LanguageMind(l.path).labels["cuadro-001"],"cuadro")
        self.assertIn("que significa",l.hear("¿Cómo flotar?","cuadro-001").lower())

    def test_demostracion_aprendizaje_y_correccion(self):
        root=NodePath("laboratorio")
        teacher=Humanoid(root,"MAESTRO",(.3,.8,.9,1),teacher=True)
        baby=Humanoid(root,"AMBOT",(.9,.4,.8,1),position=(3,0,0))
        recorder=DemonstrationRecorder()
        mind=ObservationLearner(self.data/"motor.json")
        recorder.begin("cerrar mano",teacher.pose())
        teacher.finger("izquierda",1,.85)
        teacher.finger("izquierda",0,.75)
        recorder.record(teacher.pose(),.1)
        name,frames=recorder.stop(teacher.pose())
        self.assertIn("Observe",mind.observe(name,frames))
        self.assertEqual(mind.episodes,1)
        reply=mind.try_skill("cerrar mano",baby)
        self.assertIn("probando",reply)
        self.assertGreater(baby.curls["izquierda"][1],0)
        before=mind.policies["cerrar mano"]["score"]
        mind.feedback("cerrar mano",True)
        self.assertGreater(mind.policies["cerrar mano"]["score"],before)
        self.assertEqual(ObservationLearner(mind.path).attempts,1)

    def test_no_aprende_sin_demostracion(self):
        mind=ObservationLearner(self.data/"motor.json")
        self.assertIn("no observe",mind.try_skill("saltar",None).lower())
        with self.assertRaises(ValueError):
            mind.observe("saltar",[{"position":[0,0,0]}])


if __name__=="__main__":
    unittest.main()
