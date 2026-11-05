"""Aprendizaje incremental: rasgos observados -> acciones motoras tentativas.

No se copian programas ni animaciones del maestro. Los ejemplos enseñan
deltas motoras; el aprendiz mantiene una politica promedio y la corrige con
retroalimentacion explicita. El movimiento es todavia cinematico.
"""
import json
import math
import copy
import re
from pathlib import Path
from body.robot import JOINT_NAMES, JOINT_LIMITS, clamp

CHANNELS=(
    "dx","dy","forward","heading","reach","spread","altura",
    "izquierda_0","izquierda_1","izquierda_2","izquierda_3","izquierda_4",
    "derecha_0","derecha_1","derecha_2","derecha_3","derecha_4",
    *(f"joint_{name}" for name in JOINT_NAMES)
)


def channels(p):
    pos=p.get("position",(0,0,0))
    out={"dx":float(pos[0]),"dy":float(pos[1]),
         "reach":float(p.get("reach",0)),
         "spread":float(p.get("spread",0)),
         "altura":float(p.get("hand_height",0)),
         "heading":float(p.get("heading",0)),
         "forward":0.0}
    for hand in ("izquierda","derecha"):
        for i,v in enumerate(p["fingers"][hand]):
            out[f"{hand}_{i}"]=float(v)
    angles=p.get("joints",{})
    for name in JOINT_NAMES:
        out[f"joint_{name}"]=float(angles.get(name,0.0))
    return out


class ObservationLearner:
    """Modelo motor sencillo entrenado mediante deltas, no por playback."""
    def __init__(self,path):
        self.path=Path(path)
        self.policies={}
        self.episodes=0
        self.attempts=0
        self.corrections=0
        self.history=[]
        self.unlabeled=[]
        self.unlabeled_archive=[]
        self.next_observation_id=1
        self._load()

    def _load(self):
        try:
            data=json.loads(self.path.read_text(encoding="utf-8"))
            self.policies=dict(data.get("policies",{}))
            self.episodes=int(data.get("episodes",0))
            self.attempts=int(data.get("attempts",0))
            self.corrections=int(data.get("corrections",0))
            self.history=list(data.get("history",[]))[-100:]
            self.unlabeled=list(data.get("unlabeled",[]))[-12:]
            self.unlabeled_archive=list(data.get("unlabeled_archive",[]))[-30:]
            self.next_observation_id=max(1,int(data.get("next_observation_id",1)))
        except (OSError,ValueError,TypeError,AttributeError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({
            "policies":self.policies,"episodes":self.episodes,
            "attempts":self.attempts,"corrections":self.corrections,
            "history":self.history[-100:],
            "unlabeled":self.unlabeled[-12:],
            "unlabeled_archive":self.unlabeled_archive[-30:],
            "next_observation_id":self.next_observation_id,
        },ensure_ascii=False,indent=2),encoding="utf-8")
        temp.replace(self.path)

    @staticmethod
    def _motor_delta(first,last):
        """Extrae cambio relativo y avance segun rumbo inicial."""
        signal={k:last[k]-first[k] for k in CHANNELS}
        signal["heading"]=(signal["heading"]+180)%360-180
        angle=math.radians(first["heading"])
        signal["forward"]=(-math.sin(angle)*signal["dx"]
                           +math.cos(angle)*signal["dy"])
        return signal

    @staticmethod
    def _amplitude(delta):
        return math.sqrt(sum(float(value)**2 for value in delta.values()))

    def add_unlabeled(self,episode):
        """Guardar inmediatamente una accion observada sin inventar su nombre."""
        if len(self.unlabeled)>=12:
            return None
        if not isinstance(episode,dict) or len(episode.get("frames",[]))<2:
            raise ValueError("No hay una accion observable")
        frames=episode["frames"]
        # Conservar muestras de la trayectoria completa con tamano limitado.
        skip=max(1,(len(frames)+63)//64)
        reduced=frames[::skip]
        if reduced[-1] is not frames[-1]:
            reduced.append(frames[-1])
        record={
            "id":self.next_observation_id,
            "frames":copy.deepcopy(reduced),
            "events":copy.deepcopy(episode.get("events",[]))[-30:],
            "context":copy.deepcopy(episode.get("context",{})),
            "duration":round(float(episode.get("duration",0)),3),
            "movement":round(float(episode.get("movement",0)),3),
        }
        self.next_observation_id+=1
        self.unlabeled.append(record)
        self.history.append({"event":"sin_nombre","id":record["id"]})
        self.save()
        return record

    def next_unlabeled(self):
        return self.unlabeled[0] if self.unlabeled else None

    def label_next(self,label):
        """El MAESTRO nombra una accion posterior a la observacion."""
        if not self.unlabeled:
            raise ValueError("No tengo una accion pendiente de identificar")
        label=re.sub(r"\s+"," ",str(label).strip().lower().strip(" .!?¿¡,;:"))
        if not 1<=len(label)<=64 or not re.search(r"\w",label):
            raise ValueError("El nombre de la accion debe tener entre 1 y 64 caracteres")
        episode=self.unlabeled[0]
        answer=self.observe(label,episode["frames"],
                            events=episode.get("events",[]),
                            context=episode.get("context",{}))
        self.unlabeled.pop(0)
        self.history.append({"event":"nombrada","id":episode["id"],"skill":label})
        self.save()
        return answer

    def skip_next(self):
        """Omitir una pregunta conservando la experiencia sin etiqueta."""
        if not self.unlabeled:
            return False
        old=self.unlabeled.pop(0)
        self.unlabeled_archive.append(old)
        self.unlabeled_archive=self.unlabeled_archive[-30:]
        self.history.append({"event":"sin_respuesta","id":old["id"]})
        self.save()
        return True

    def observe(self,label,frames,events=None,context=None):
        """Aprende tendencias motoras, guarda trayectorias y eventos observados.

        La trayectoria sin etiqueta no equivale a ejecutar una accion:
        almacenar nombre, registros y variaciones es aprendizaje
        observacional basico, no vision ni planificacion completas.
        """
        label=str(label).strip().lower()
        if not label or len(label)>64 or len(frames)<2:
            raise ValueError("Necesito una demostracion con movimiento observable.")
        first=channels(frames[0])
        traces=[channels(frame) for frame in frames]
        signal=self._motor_delta(first,traces[-1])
        magnitude=self._amplitude(signal)
        # Una accion puede volver a la postura inicial (abrir/cerrar).
        # Conservar tambien su pico y el recorrido intermedio.
        path=0.0
        peak_delta=signal
        peak_magnitude=magnitude
        for index in range(1,len(traces)):
            step=self._motor_delta(traces[index-1],traces[index])
            path+=self._amplitude(step)
            offset=self._motor_delta(first,traces[index])
            strength=self._amplitude(offset)
            if strength>peak_magnitude:
                peak_magnitude=strength
                peak_delta=offset
        motor_observed=magnitude>=.02 or peak_magnitude>=.02
        if not motor_observed and not events:
            raise ValueError("No hubo movimientos suficientes para aprender.")
        if magnitude<.02 and peak_magnitude>=.02:
            # Politica inicial para una accion ciclica: aprender la fase
            # de mayor cambio, sin afirmar que ya ejecuta todo el ciclo.
            signal=peak_delta
        old=self.policies.get(label)
        if old:
            count=int(old["seen"])+1
            old["delta"]={
                k:round(old["delta"].get(k,0.0)+.24*(signal[k]-old["delta"].get(k,0.0)),6)
                for k in CHANNELS
            }
            old["seen"]=count
        else:
            old={"delta":{k:round(v,6) for k,v in signal.items()},
                 "seen":1,"feedback":0,"score":0.15}
            self.policies[label]=old
        # Hasta 3 ejemplos: claves para futuras politicas por fases.
        old.setdefault("examples",[])
        skip=max(1,(len(frames)+23)//24)
        reduced=copy.deepcopy(frames[::skip])
        if reduced[-1]!=frames[-1]:
            reduced.append(copy.deepcopy(frames[-1]))
        old["examples"].append({
            "frames":reduced,
            "events":copy.deepcopy(events or [])[-20:],
            "context":copy.deepcopy(context or {}),
            "path":round(path,3)
        })
        old["examples"]=old["examples"][-3:]
        old["motor_observed"]=bool(motor_observed or old.get("motor_observed"))
        self.episodes+=1
        self.history.append({"event":"observacion","skill":label,
                             "magnitude":round(max(peak_magnitude,path),3),
                             "event_count":len(events or [])})
        self.save()
        if not motor_observed:
            return (f"Asocie el nombre '{label}' con lo ocurrido, pero "
                    "todavia necesito observar el movimiento para ejecutarlo.")
        return (f"Ahora se que lo que observe se llama '{label}'. "
                "Guarde tus movimientos para intentar aprenderlos.")

    def available(self):
        return sorted(self.policies)

    def try_skill(self,label,robot):
        label=label.lower().strip()
        data=self.policies.get(label)
        if not data:
            return "Todavia no observe una demostracion de '"+label+"'. ¿Puedes ensenarme?"
        if data.get("motor_observed") is False:
            return ("Recuerdo el nombre de \'"+label+"\', pero todavia no se " \
                    "ejecutarlo: necesito ver como mueves tu cuerpo.")
        d=data["delta"]
        # Imitacion por politica agregada: una fraccion del cambio predicho,
        # separada de los fotogramas originales.
        factor=max(.2,min(.85,.33+float(data["score"])*.5))
        p=robot.pose()
        for hand in ("izquierda","derecha"):
            p["fingers"][hand]=[
                max(0,min(1,p["fingers"][hand][i]+d[f"{hand}_{i}"]*factor))
                for i in range(5)
            ]
        for name in JOINT_NAMES:
            key=f"joint_{name}"
            low,high=JOINT_LIMITS[name]
            p.setdefault("joints",{})[name]=clamp(
                p.get("joints",{}).get(name,0.0)+d.get(key,0.0)*factor,
                low,high)
        p["reach"]=max(0,min(1,p["reach"]+d["reach"]*factor))
        p["spread"]=max(0,min(1,p["spread"]+d["spread"]*factor))
        p["hand_height"]=max(-1,min(1,p["hand_height"]+d["altura"]*factor))
        # La imitacion mantiene las reglas de locomocion del maestro:
        # giro y desplazamiento sobre el eje frontal, sin strafe.
        old_heading=p["heading"]
        p["heading"]=(old_heading+d.get("heading",0.0)*factor)%360
        angle=math.radians(p["heading"])
        if "forward" in d:
            forward=d["forward"]
        else:
            # Memorias v0.1.0 sin campos de giro y avance frontal.
            original_angle=math.radians(old_heading)
            forward=(-math.sin(original_angle)*d.get("dx",0.0)
                     +math.cos(original_angle)*d.get("dy",0.0))
        step=max(-.7,min(.7,forward*factor))
        p["position"][0]=max(-24.5,min(24.5,p["position"][0]-math.sin(angle)*step))
        p["position"][1]=max(-24.5,min(24.5,p["position"][1]+math.cos(angle)*step))
        robot.set_pose(p)
        self.attempts+=1
        self.history.append({"event":"ensayo","skill":label,"factor":round(factor,3)})
        self.save()
        return f"Estoy probando '{label}' a partir de lo que observe. ¿Lo hice bien?"

    def feedback(self,label,positive):
        label=label.lower().strip()
        if label not in self.policies:
            return "No se a que aprendizaje te refieres."
        data=self.policies[label]
        data["feedback"]=int(data.get("feedback",0))+1
        rate=.14 if positive else -.18
        data["score"]=max(0,min(1,round(data["score"]+rate,4)))
        self.corrections+=1
        self.history.append({"event":"correccion","skill":label,"positive":bool(positive)})
        self.save()
        return "Recuerdo tu correccion. "+("Reforzare este intento." if positive else
                "Debo cambiar mi proxima prueba.")
