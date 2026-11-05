"""Comprobar aprendizaje pasivo: observar, pausar, preguntar y nombrar."""
import tempfile
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from brain.auto_observer import AutoObserver,pose_change
from brain.learning import ObservationLearner


def pose(angle=0.0, finger=0.0, y=0.0):
    return {
        "position":[0.0,y,0.0],
        "heading":0.0,
        "reach":.5,"spread":.2,"hand_height":0.0,
        "joints":{"codo_izq":angle},
        "fingers":{"izquierda":[finger,0,0,0,0],
                   "derecha":[0,0,0,0,0]}
    }


class AutoObserverTests(unittest.TestCase):
    def test_no_pregunta_si_el_maestro_esta_quieto(self):
        tracker=AutoObserver(quiet_seconds=.5)
        for _ in range(40):
            self.assertIsNone(tracker.update(pose(),.1))
        self.assertFalse(tracker.active)

    def test_observa_articulacion_y_pregunta_solo_tras_pausa(self):
        tracker=AutoObserver(quiet_seconds=.5)
        tracker.update(pose(),.1)
        tracker.update(pose(20),.1)
        self.assertTrue(tracker.active)
        for degrees in (30,40,60,80):
            self.assertIsNone(tracker.update(pose(degrees),.1))
        for _ in range(4):
            self.assertIsNone(tracker.update(pose(80),.1))
        episode=tracker.update(pose(80),.1)
        self.assertIsNotNone(episode)
        self.assertEqual(episode["frames"][0]["joints"]["codo_izq"],0.0)
        self.assertEqual(episode["frames"][-1]["joints"]["codo_izq"],80)
        self.assertGreater(episode["movement"],1)
        self.assertFalse(tracker.active)
        for _ in range(20):
            self.assertIsNone(tracker.update(pose(80),.1))

    def test_agrupar_movimiento_seguido_sin_preguntar_por_cada_dedo(self):
        tracker=AutoObserver(quiet_seconds=.6)
        tracker.update(pose(),.1)
        tracker.update(pose(finger=.1),.1)
        for n in range(1,6):
            self.assertIsNone(tracker.update(pose(finger=.1+n*.12),.1))
        for _ in range(6):
            result=tracker.update(pose(finger=.70),.1)
        self.assertIsNotNone(result)
        self.assertGreater(len(result["frames"]),2)
        self.assertEqual(result["events"],[])

    def test_registra_movimiento_ciclico_aunque_termine_igual(self):
        tracker=AutoObserver(quiet_seconds=.4)
        tracker.update(pose(),.1)
        tracker.update(pose(angle=45),.1)
        tracker.update(pose(angle=90),.1)
        tracker.update(pose(angle=0),.1)
        result=None
        for _ in range(6):
            result=tracker.update(pose(),.1) or result
        self.assertIsNotNone(result)
        self.assertEqual(result["frames"][0]["joints"]["codo_izq"],0)
        self.assertEqual(result["frames"][-1]["joints"]["codo_izq"],0)
        with tempfile.TemporaryDirectory() as td:
            learner=ObservationLearner(Path(td)/"motor.json")
            learner.add_unlabeled(result)
            learner.label_next("doblar y estirar codo")
            self.assertGreater(learner.policies["doblar y estirar codo"]["delta"]["joint_codo_izq"],0)

    def test_espera_nombre_y_guarda_la_asociacion_en_disco(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"motor.json"
            learner=ObservationLearner(path)
            self.assertEqual(learner.episodes,0)
            demo={"frames":[pose(0),pose(70)],"duration":.6,
                  "movement":20.0,"events":[],
                  "context":{"selected_object":{"id":"cubo-001","name":"Cubo"}}}
            saved=learner.add_unlabeled(demo)
            self.assertIsNotNone(saved)
            self.assertEqual(learner.episodes,0)
            self.assertEqual(len(learner.unlabeled),1)
            restored=ObservationLearner(path)
            self.assertEqual(len(restored.unlabeled),1)
            answer=restored.label_next("flexionar mi codo")
            self.assertIn("flexionar mi codo",answer)
            self.assertEqual(restored.episodes,1)
            self.assertEqual(len(restored.unlabeled),0)
            self.assertEqual(restored.available(),["flexionar mi codo"])
            example=restored.policies["flexionar mi codo"]["examples"][0]
            self.assertEqual(example["context"]["selected_object"]["name"],"Cubo")

    def test_evento_de_agarre_sin_movimiento_no_finge_habilidad_motora(self):
        tracker=AutoObserver(quiet_seconds=.3)
        tracker.update(pose(),.1)
        tracker.update(pose(),.1,events=[{"type":"agarre","hand":"izquierda",
                                            "object_name":"Cuadro"}])
        episode=None
        for _ in range(5):
            episode=tracker.update(pose(),.1) or episode
        self.assertIsNotNone(episode)
        self.assertEqual(episode["events"][0]["type"],"agarre")
        with tempfile.TemporaryDirectory() as td:
            learner=ObservationLearner(Path(td)/"motor.json")
            learner.add_unlabeled(episode)
            response=learner.label_next("agarrar el cuadro")
            self.assertIn("todavia necesito observar el movimiento",response)
            self.assertFalse(learner.policies["agarrar el cuadro"]["motor_observed"])

    def test_omitir_no_pierde_experiencia(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"motor.json"
            learner=ObservationLearner(path)
            learner.add_unlabeled({"frames":[pose(0),pose(40)],"events":[]})
            self.assertTrue(learner.skip_next())
            self.assertIsNone(learner.next_unlabeled())
            self.assertEqual(len(ObservationLearner(path).unlabeled_archive),1)

    def test_puede_repetir_una_nueva_observacion(self):
        tracker=AutoObserver(quiet_seconds=.3)
        tracker.update(pose(),.1)
        tracker.update(pose(y=.25),.1)
        result=None
        for _ in range(4):
            result=tracker.update(pose(y=.25),.1) or result
        self.assertIsNotNone(result)
        tracker.update(pose(y=.55),.1)
        result2=None
        for _ in range(4):
            result2=tracker.update(pose(y=.55),.1) or result2
        self.assertIsNotNone(result2)
        self.assertNotEqual(result["frames"][-1]["position"],
                            result2["frames"][-1]["position"])


if __name__=="__main__":
    unittest.main()
