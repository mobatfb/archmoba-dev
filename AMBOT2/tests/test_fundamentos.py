"""Pruebas de AMBOT2: cuerpo, dedos, fisica, lenguaje y aprendizaje."""
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from panda3d.core import NodePath
from body.robot import Humanoid, FINGER_NAMES
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
        lab.step(.015)
        ok,contacts=grasp.inspect("izquierda",obj)
        self.assertTrue(ok,contacts)
        success,msg=grasp.try_grasp("izquierda",obj)
        self.assertTrue(success,msg)
        self.assertIn("izquierda",grasp.held())
        grasp.release("izquierda")
        self.assertEqual(grasp.held(),{})
        self.assertEqual(len(lab.physics.constraints),0)

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
