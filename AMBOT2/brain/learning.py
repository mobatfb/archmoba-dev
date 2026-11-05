"""Aprendizaje incremental: rasgos observados -> acciones motoras tentativas.

No se copian programas ni animaciones del maestro. Los ejemplos enseñan
deltas motoras; el aprendiz mantiene una politica promedio y la corrige con
retroalimentacion explicita. El movimiento es todavia cinematico.
"""
import json
import math
from pathlib import Path

CHANNELS=(
    "dx","dy","reach","spread","altura",
    "izquierda_0","izquierda_1","izquierda_2","izquierda_3","izquierda_4",
    "derecha_0","derecha_1","derecha_2","derecha_3","derecha_4"
)


def channels(p):
    pos=p.get("position",(0,0,0))
    out={"dx":float(pos[0]),"dy":float(pos[1]),
         "reach":float(p.get("reach",0)),
         "spread":float(p.get("spread",0)),
         "altura":float(p.get("hand_height",0))}
    for hand in ("izquierda","derecha"):
        for i,v in enumerate(p["fingers"][hand]):
            out[f"{hand}_{i}"]=float(v)
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
        self._load()

    def _load(self):
        try:
            data=json.loads(self.path.read_text(encoding="utf-8"))
            self.policies=dict(data.get("policies",{}))
            self.episodes=int(data.get("episodes",0))
            self.attempts=int(data.get("attempts",0))
            self.corrections=int(data.get("corrections",0))
            self.history=list(data.get("history",[]))[-100:]
        except (OSError,ValueError,TypeError,AttributeError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_suffix(".tmp")
        temp.write_text(json.dumps({
            "policies":self.policies,"episodes":self.episodes,
            "attempts":self.attempts,"corrections":self.corrections,
            "history":self.history[-100:],
        },ensure_ascii=False,indent=2),encoding="utf-8")
        temp.replace(self.path)

    def observe(self,label,frames):
        """Aprende el cambio entre estado inicial/final, sin conocer guion."""
        label=str(label).strip().lower()
        if not label or len(label)>64 or len(frames)<2:
            raise ValueError("Necesito una demostracion con movimiento observable.")
        first,last=channels(frames[0]),channels(frames[-1])
        signal={k:last[k]-first[k] for k in CHANNELS}
        magnitude=math.sqrt(sum(v*v for v in signal.values()))
        if magnitude<.02:
            raise ValueError("No hubo movimientos suficientes para aprender.")
        old=self.policies.get(label)
        if old:
            count=int(old["seen"])+1
            old["delta"]={
                k:round(old["delta"][k]+.24*(signal[k]-old["delta"][k]),6)
                for k in CHANNELS
            }
            old["seen"]=count
        else:
            self.policies[label]={
                "delta":{k:round(v,6) for k,v in signal.items()},
                "seen":1,"feedback":0,
                "score":0.15
            }
        self.episodes+=1
        self.history.append({"event":"observacion","skill":label,"magnitude":round(magnitude,3)})
        self.save()
        return f"Observe movimientos relacionados con '{label}'. Tengo que probarlos."

    def available(self):
        return sorted(self.policies)

    def try_skill(self,label,robot):
        label=label.lower().strip()
        data=self.policies.get(label)
        if not data:
            return "Todavia no observe una demostracion de '"+label+"'. ¿Puedes ensenarme?"
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
        p["reach"]=max(0,min(1,p["reach"]+d["reach"]*factor))
        p["spread"]=max(0,min(1,p["spread"]+d["spread"]*factor))
        p["hand_height"]=max(-1,min(1,p["hand_height"]+d["altura"]*factor))
        p["position"][0]+=max(-.7,min(.7,d["dx"]*factor))
        p["position"][1]+=max(-.7,min(.7,d["dy"]*factor))
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
