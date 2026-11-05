"""Deteccion pasiva de acciones del MAESTRO.

Registra cambios observables del avatar (articulaciones, dedos y
locomocion) y eventos de contacto. No conoce el nombre de las acciones.
Agrupa movimientos consecutivos; tras una pausa devuelve un episodio
SIN ETIQUETA para que AMBOT pregunte al humano.

No confundir observacion con una comprension semantica o un agarre
aprendido: la etiqueta llega solo de la respuesta del maestro.
"""
import copy


def _heading_delta(a,b):
    return abs((float(a)-float(b)+180)%360-180)


def pose_change(a,b):
    """Diferencia maxima en unidades de umbral perceptivo."""
    if not a or not b:
        return 0.0
    ap=a.get("position",(0,0,0))
    bp=b.get("position",(0,0,0))
    score=max(
        abs(float(ap[0])-float(bp[0]))/.045,
        abs(float(ap[1])-float(bp[1]))/.045,
        _heading_delta(a.get("heading",0),b.get("heading",0))/3.0,
        abs(float(a.get("reach",0))-float(b.get("reach",0)))/.065,
        abs(float(a.get("spread",0))-float(b.get("spread",0)))/.065,
        abs(float(a.get("hand_height",0))-float(b.get("hand_height",0)))/.065,
    )
    for joint in set(a.get("joints",{})) | set(b.get("joints",{})):
        score=max(score,abs(float(a.get("joints",{}).get(joint,0))
                            -float(b.get("joints",{}).get(joint,0)))/3.0)
    for hand in ("izquierda","derecha"):
        af=a.get("fingers",{}).get(hand,[0]*5)
        bf=b.get("fingers",{}).get(hand,[0]*5)
        for idx in range(min(len(af),len(bf),5)):
            score=max(score,abs(float(af[idx])-float(bf[idx]))/.065)
    return score


class AutoObserver:
    """Segmentador en tiempo real con antirruido y pausa de finalizacion."""
    def __init__(self,quiet_seconds=1.15,max_seconds=15.0,max_frames=160):
        self.quiet_seconds=float(quiet_seconds)
        self.max_seconds=float(max_seconds)
        self.max_frames=int(max_frames)
        self.baseline=None
        self.motion_reference=None
        self.frames=[]
        self.events=[]
        self.context={}
        self.active=False
        self.elapsed=0.0
        self.quiet=0.0
        self._sample_clock=0.0
        self.movement=0.0

    def reset(self,pose=None):
        self.baseline=copy.deepcopy(pose) if pose else None
        self.motion_reference=self.baseline
        self.frames=[]
        self.events=[]
        self.context={}
        self.active=False
        self.elapsed=self.quiet=self._sample_clock=self.movement=0.0

    def update(self,pose,dt,events=None,context=None):
        """Devuelve episodio al detectar 1.15s de reposo, o None."""
        if not isinstance(pose,dict):
            raise TypeError("La observacion requiere una postura estructurada")
        dt=max(0.0,min(float(dt),.2))
        snapshot=copy.deepcopy(pose)
        new_events=list(events or [])
        if self.baseline is None:
            self.reset(snapshot)
            if not new_events:
                return None

        if not self.active:
            change=pose_change(self.baseline,snapshot)
            if change<1.0 and not new_events:
                self.baseline=snapshot
                return None
            self.active=True
            self.frames=[copy.deepcopy(self.baseline),snapshot]
            self.motion_reference=snapshot
            self.movement=max(change,2.0 if new_events else 0)
            self.events=new_events
            self.context=copy.deepcopy(context or {})
            self.elapsed=self.quiet=self._sample_clock=0.0
            return None

        self.elapsed+=dt
        self.quiet+=dt
        self._sample_clock+=dt
        change=pose_change(self.motion_reference,snapshot)
        if change>=1.0 or new_events:
            self.motion_reference=snapshot
            self.movement+=max(change,1.0 if new_events else 0.0)
            self.quiet=0.0
            if new_events:
                self.events.extend(copy.deepcopy(new_events))
            if context:
                self.context=copy.deepcopy(context)

        # Fotogramas comprimidos (no grabar miles de frames iguales).
        if (self._sample_clock>=.10 or change>=1.0
                or new_events) and len(self.frames)<self.max_frames:
            self.frames.append(snapshot)
            self._sample_clock=0.0

        if self.quiet<self.quiet_seconds and self.elapsed<self.max_seconds:
            return None
        if not self.frames or pose_change(self.frames[-1],snapshot)>0.01:
            self.frames.append(snapshot)
        result={
            "frames":self.frames[:],
            "events":self.events[:],
            "context":copy.deepcopy(self.context),
            "duration":round(self.elapsed,3),
            "movement":round(self.movement,3),
        }
        self.reset(snapshot)
        if result["movement"]<1.0 and not result["events"]:
            return None
        return result
