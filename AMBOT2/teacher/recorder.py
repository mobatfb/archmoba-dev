"""Registro de demostraciones del maestro humano (muestreo de su cuerpo)."""


class DemonstrationRecorder:
    def __init__(self):
        self.active=False
        self.label=""
        self.frames=[]
        self._clock=0.0

    def begin(self,label,pose):
        if self.active:
            raise ValueError("Termina antes la demostracion anterior")
        label=str(label).strip().lower()
        if not 1<=len(label)<=64:
            raise ValueError("Escribe el nombre de la habilidad")
        self.active=True
        self.label=label
        self.frames=[pose]
        self._clock=0.0

    def record(self,pose,dt):
        if not self.active:
            return
        self._clock+=max(0,min(dt,.08))
        if self._clock>=.07:
            self._clock=0.0
            if len(self.frames)<2000:
                self.frames.append(pose)

    def stop(self,pose):
        if not self.active:
            raise ValueError("No hay demostracion iniciada")
        self.frames.append(pose)
        label,frames=self.label,self.frames[:]
        self.active=False
        self.label=""
        self.frames=[]
        return label,frames
