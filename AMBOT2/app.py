"""AMBOT2: laboratorio nativo con un maestro humano y un robot aprendiz."""
from __future__ import annotations
import json
import math
import os
import subprocess
import sys
from pathlib import Path

VERSION="0.1.0"
APP_DIR=Path(__file__).resolve().parent
DATA_DIR=Path(os.environ.get("LOCALAPPDATA",str(Path.home()/".local"/"share")))/"ARCHMOBA"/"AMBOT2"
SCENE=DATA_DIR/"escena.json"
MOTOR_MEMORY=DATA_DIR/"motor.json"
LANGUAGE_MEMORY=DATA_DIR/"lenguaje.json"


def ensure_panda3d():
    """Instalacion opcional de dependencia en directorio propio del programa."""
    try:
        import panda3d  # noqa: F401
        return
    except ImportError:
        pass
    target=DATA_DIR/"dependencies"
    sys.path.insert(0,str(target))
    try:
        import panda3d  # noqa: F401
        return
    except ImportError:
        pass
    target.mkdir(parents=True,exist_ok=True)
    print("[AMBOT2] Instalando Panda3D por primera vez...")
    subprocess.run([
        sys.executable,"-m","pip","install",
        "--disable-pip-version-check","--target",str(target),
        "panda3d>=1.10.15,<1.12"
    ],check=True,timeout=240)
    import panda3d  # noqa: F401


ensure_panda3d()

from panda3d.bullet import BulletWorld
from panda3d.core import (
    AmbientLight, DirectionalLight, Vec3, Point3, Point2, TextNode,
    WindowProperties, loadPrcFileData, Camera, PerspectiveLens
)
from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import DirectFrame, DirectButton, DirectEntry, DirectSlider, DirectLabel
from direct.gui.OnscreenText import OnscreenText
from engine.world import LabWorld
from body.robot import Humanoid, HAND_NAMES, FINGER_NAMES, clamp
from body.grasp import GraspSystem
from brain.learning import ObservationLearner
from teacher.recorder import DemonstrationRecorder
from editor.objects import ObjectEditor
from language.understanding import LanguageMind


class AMBOT2App(ShowBase):
    def __init__(self,headless=False,data_dir=None):
        self.data_dir=Path(data_dir) if data_dir else DATA_DIR
        if headless:
            loadPrcFileData("","audio-library-name null\nwindow-type none")
        else:
            loadPrcFileData("","window-title AMBOT2 - Laboratorio de aprendizaje\n"
                        "win-size 1380 790\nsync-video true")
        super().__init__(windowType="none" if headless else "onscreen")
        if headless and self.camera is None:
            self.camLens=PerspectiveLens()
            self.camera=self.render.attachNewNode(Camera("camara-sin-monitor"))
            self.camera.node().setLens(self.camLens)
        self.headless=headless
        self.disableMouse()
        self.setBackgroundColor(.043,.07,.105,1)
        self._light()
        self.lab=LabWorld(self.render)
        self.editor=ObjectEditor(self.lab,self.data_dir/"escena.json")
        try:
            loaded=self.editor.load()
        except (OSError,ValueError,TypeError):
            loaded=False
        if not loaded:
            # Objetos iniciales, ninguno pegado al cuerpo de los robots.
            self.lab.spawn("cuadro",name="Cuadro para practicar",
                           pos=(0,2.1,.75))
            self.lab.spawn("cubo",name="Cubo de practica",
                           pos=(-2.0,1.9,.36))
            self.lab.spawn("pelota",name="Pelota de practica",
                           pos=(2.0,2.1,.37))
            self.editor.selected=next(iter(self.lab.objects))
        self.teacher=Humanoid(
            self.render,"MAESTRO",(.30,.81,.94,1),position=(0,0,0),teacher=True)
        self.baby=Humanoid(
            self.render,"AMBOT",(.98,.59,.83,1),position=(2.7,-.2,0),teacher=False)
        self.grasp=GraspSystem(self.lab,self.teacher)
        self.learner=ObservationLearner(self.data_dir/"motor.json")
        self.language=LanguageMind(self.data_dir/"lenguaje.json")
        self.recorder=DemonstrationRecorder()
        self.last_skill=""
        self.last_message="Soy AMBOT. ¿Que vas a ensenarme?"
        self.last_teacher_action="Laboratorio iniciado."
        self.keys=set()
        self.cam_yaw=8
        self.cam_pitch=22
        self.cam_distance=9.5
        self.rotating_camera=False
        self.mouse_prev=None
        self._gui_clock=0.0
        self._camera()
        self._bindings()
        self._ui()
        self.taskMgr.add(self._update,"actualizar-ambot2")

    def _light(self):
        ambient=AmbientLight("luz_ambiente")
        ambient.setColor((.36,.43,.53,1))
        self.render.setLight(self.render.attachNewNode(ambient))
        sunlight=DirectionalLight("sol")
        sunlight.setColor((.88,.91,1,1))
        sun=self.render.attachNewNode(sunlight)
        sun.setHpr(-35,-57,0)
        self.render.setLight(sun)
        self.render.setShaderAuto()

    def _camera(self):
        target=self.teacher.node.getPos(self.render)+Vec3(0,.8,1.3)
        angle=math.radians(self.cam_yaw)
        pitch=math.radians(self.cam_pitch)
        radius=self.cam_distance*math.cos(pitch)
        point=target+Vec3(math.sin(angle)*radius,
                          -math.cos(angle)*radius,
                          self.cam_distance*math.sin(pitch))
        self.camera.setPos(point)
        self.camera.lookAt(target)

    def _hold(self,key,pressed=True):
        if pressed:self.keys.add(key)
        else:self.keys.discard(key)

    def _bindings(self):
        for key in ("w","a","s","d","arrow_up","arrow_down","arrow_left","arrow_right"):
            self.accept(key,self._hold,[key,True])
            self.accept(key+"-up",self._hold,[key,False])
        self.accept("q",self.adjust_finger,[-.1])
        self.accept("e",self.adjust_finger,[.1])
        self.accept("1",self.select_hand,["izquierda"])
        self.accept("2",self.select_hand,["derecha"])
        self.accept("bracketleft",self.select_finger,[-1])
        self.accept("bracketright",self.select_finger,[1])
        self.accept("z",self.adjust_reach,[-.09])
        self.accept("x",self.adjust_reach,[.09])
        self.accept("c",self.adjust_height,[-.09])
        self.accept("v",self.adjust_height,[.09])
        self.accept("r",self.close_hand,[1])
        self.accept("f",self.close_hand,[0])
        self.accept("t",self.try_grasp)
        self.accept("g",self.release)
        self.accept("o",self.begin_demonstration)
        self.accept("p",self.end_demonstration)
        self.accept("h",self.try_imitation)
        self.accept("5",self.create_object,["cubo"])
        self.accept("6",self.create_object,["pelota"])
        self.accept("7",self.create_object,["cuadro"])
        self.accept("8",self.create_object,["caja"])
        self.accept("wheel_up",self._zoom,[-.8])
        self.accept("wheel_down",self._zoom,[.8])
        self.accept("mouse3",self._start_orbit)
        self.accept("mouse3-up",self._stop_orbit)
        self.accept("mouse1",self._pick)
        self.accept("escape",self.release)

    def _zoom(self,delta):
        self.cam_distance=max(3.5,min(38,self.cam_distance+delta))
        self._camera()

    def _start_orbit(self):
        self.rotating_camera=True
        self.mouse_prev=None

    def _stop_orbit(self):
        self.rotating_camera=False
        self.mouse_prev=None

    def _pick(self):
        if not self.mouseWatcherNode.hasMouse():
            return
        mouse=self.mouseWatcherNode.getMouse()
        # El panel de DirectGUI esta superpuesto en la zona derecha.
        if mouse.x>.48:
            return
        near,far=Point3(),Point3()
        if not self.camLens.extrude(mouse,near,far):
            return
        a=self.render.getRelativePoint(self.camera,near)
        b=self.render.getRelativePoint(self.camera,far)
        result=self.lab.physics.rayTestClosest(a,b)
        if not result.hasHit():
            return
        hit=result.getNode()
        for obj in self.lab.objects.values():
            if hit==obj.np.node():
                self.editor.select(obj.oid)
                self.say("Seleccionado: "+obj.name)
                return

    def select_hand(self,hand):
        self.teacher.selected_hand=hand
        if hasattr(self,"slider"):
            self.slider["value"]=self.teacher.curls[hand][self.teacher.selected_digit]
        self.say("Controlando mano "+hand)

    def select_finger(self,delta):
        self.teacher.selected_digit=(self.teacher.selected_digit+delta)%5
        if hasattr(self,"slider"):
            self.slider["value"]=self.teacher.curls[self.teacher.selected_hand][self.teacher.selected_digit]
        self.say("Dedo: "+FINGER_NAMES[self.teacher.selected_digit])

    def adjust_finger(self,delta):
        hand=self.teacher.selected_hand
        i=self.teacher.selected_digit
        self.teacher.finger(hand,i,self.teacher.curls[hand][i]+delta)
        if hasattr(self,"slider"):
            self.slider["value"]=self.teacher.curls[hand][i]

    def set_finger_slider(self):
        if not hasattr(self,"slider"):
            return
        hand=self.teacher.selected_hand
        i=self.teacher.selected_digit
        self.teacher.finger(hand,i,self.slider["value"])

    def close_hand(self,value):
        self.teacher.hand_close(self.teacher.selected_hand,value)
        if hasattr(self,"slider"):
            self.slider["value"]=value
        self.say("Mano "+self.teacher.selected_hand+" "+("cerrada" if value else "abierta"))

    def adjust_reach(self,delta):
        self.teacher.reach=clamp(self.teacher.reach+delta)
        self.teacher.update_visual()

    def adjust_height(self,delta):
        self.teacher.hand_height=clamp(self.teacher.hand_height+delta,-1,1)
        self.teacher.update_visual()

    def try_grasp(self):
        self.grasp.sync()
        self.lab.step(.015)
        result=self.grasp.try_nearest(self.teacher.selected_hand)
        self.say(result)
        return result

    def release(self):
        if self.grasp.release(self.teacher.selected_hand):
            self.say("Abri el agarre. El objeto puede caer.")
        else:
            self.say("La mano no estaba sujetando nada.")

    def create_object(self,kind):
        try:
            # La creacion ocurre delante del maestro, en el espacio de la escena.
            p=self.teacher.node.getPos(self.render)
            offset=Vec3(0,2.5,1.3)
            world_offset=self.render.getRelativeVector(self.teacher.node,offset)
            world_offset.z=1.3
            obj=self.editor.add(kind,position=tuple(p+world_offset))
            self.say("Nuevo objeto: "+obj.oid+". Puedes seleccionarlo y ensenarme su nombre.")
        except ValueError as exc:
            self.say(str(exc))

    def delete_object(self):
        obj=self.editor.object()
        if not obj:return self.say("Selecciona primero un objeto.")
        for hand,oid in list(self.grasp.held().items()):
            if oid==obj.oid:self.grasp.release(hand)
        self.editor.delete_selected()
        self.say("Objeto eliminado.")

    def save_scene(self):
        self.editor.save()
        self.say("Escena guardada correctamente.")

    def begin_demonstration(self,label=None):
        skill=label or "movimiento"
        try:
            self.recorder.begin(skill,self.teacher.pose())
            self.say("Grabando: "+skill+". Mueve tu cuerpo y pulsa P para terminar.")
        except ValueError as exc:
            self.say(str(exc))

    def end_demonstration(self):
        try:
            label,frames=self.recorder.stop(self.teacher.pose())
            answer=self.learner.observe(label,frames)
            self.last_skill=label
            self.say(answer)
        except ValueError as exc:
            self.say(str(exc))

    def try_imitation(self,label=None):
        skill=label or self.last_skill
        if not skill:return self.say("Primero muestra y graba una habilidad.")
        self.last_skill=skill
        self.say(self.learner.try_skill(skill,self.baby))

    def correct(self,positive):
        if not self.last_skill:return self.say("Aun no hay un ensayo que corregir.")
        self.say(self.learner.feedback(self.last_skill,positive))

    def say(self,message):
        self.last_message=str(message)
        if hasattr(self,"feedback_label"):
            self.feedback_label["text"]=self.last_message[:115]
        return message

    def command_enter(self,text):
        self.handle_command(text)
        self.entry.enterText("")

    def handle_command(self,raw):
        raw=str(raw).strip()
        if not raw:return ""
        command=raw.lower()
        parts=raw.split()
        try:
            if command.startswith(("crear ","agregar ","anadir ")):
                kind=parts[-1].lower()
                return self.create_object(kind)
            if command in ("guardar","guardar escena"):
                return self.save_scene()
            if command in ("cargar","cargar escena"):
                self.grasp.release_all()
                self.editor.load()
                return self.say("Escena recuperada.")
            if command in ("borrar","eliminar"):
                return self.delete_object()
            if command.startswith("nombre "):
                return self.say("Nombre del objeto: "+self.editor.rename(raw[7:]))
            if command.startswith("peso "):
                return self.say("El cambio de masa requiere volver a crear el cuerpo fisico.")
            if command.startswith("mover "):
                a=list(map(float,parts[1:]))
                if len(a)!=3:raise ValueError("Uso: mover x y z")
                self.editor.move_selected(*a)
                return self.say("Objeto reposicionado.")
            if command.startswith("enseñar ") or command.startswith("ensenar "):
                return self.begin_demonstration(" ".join(parts[1:]))
            if command in ("fin","fin demostracion","terminar"):
                return self.end_demonstration()
            if command.startswith("practicar "):
                return self.try_imitation(" ".join(parts[1:]))
            if command in ("bien","correcto","muy bien"):
                return self.correct(True)
            if command in ("mal","incorrecto","no"):
                return self.correct(False)
            if command.startswith("dedo "):
                if len(parts)!=4:
                    raise ValueError("Uso: dedo izquierda indice 0.8")
                hand=parts[1].lower()
                from language.understanding import normalize
                name=normalize(parts[2])
                if name not in FINGER_NAMES:
                    raise ValueError("Dedo desconocido")
                self.teacher.finger(hand,FINGER_NAMES.index(name),float(parts[3]))
                return self.say("Articulacion actualizada.")
            if command in ("tomar","agarrar"):
                return self.try_grasp()
            if command in ("soltar","liberar"):
                return self.release()
            if command=="ayuda":
                return self.say("WASD mover | 1/2 mano | [ ] dedo | Q/E flexionar | R/F cerrar/abrir | T agarrar | G soltar | O/P grabar | H practicar | 5-8 objetos | lenguaje en el campo de texto.")
            answer=self.language.hear(raw,self.editor.selected)
            return self.say("AMBOT: "+answer)
        except (ValueError,KeyError,TypeError,OSError) as exc:
            return self.say("No pude ejecutar: "+str(exc))

    def _ui(self):
        self.panel=DirectFrame(
            parent=self.aspect2d,frameColor=(.055,.10,.15,.93),
            frameSize=(-.11,.70,-1,1),pos=(.63,0,0))
        self.header=OnscreenText(
            parent=self.panel,text="AMBOT 2.0  /  MAESTRO",pos=(.02,.92),
            align=TextNode.ALeft,scale=.053,fg=(.55,.9,1,1),mayChange=True)
        self.status=OnscreenText(
            parent=self.panel,text="",pos=(.02,.82),scale=.033,
            align=TextNode.ALeft,fg=(.92,.95,1,1),mayChange=True)
        self.substatus=OnscreenText(
            parent=self.panel,text="",pos=(.02,.70),scale=.032,
            align=TextNode.ALeft,fg=(.72,.81,.9,1),mayChange=True)

        def btn(title,x,y,callback,width=.24):
            return DirectButton(
                parent=self.panel,text=title,scale=.044,
                pos=(x,0,y),frameSize=(-width,width,-.47,.61),
                frameColor=(.15,.28,.37,1),text_fg=(.96,.98,1,1),
                rolloverSound=None,clickSound=None,command=callback)
        btn("MANO IZQ.",.16,.54,lambda:self.select_hand("izquierda"))
        btn("MANO DER.",.46,.54,lambda:self.select_hand("derecha"))
        btn("DEDO -",.16,.44,lambda:self.select_finger(-1))
        btn("DEDO +",.46,.44,lambda:self.select_finger(1))
        self.slider=DirectSlider(
            parent=self.panel,range=(0,1),value=0,
            scale=.29,pos=(.31,0,.32),command=self.set_finger_slider,
            frameColor=(.25,.44,.52,1))
        btn("CERRAR",.16,.22,lambda:self.close_hand(1))
        btn("ABRIR",.46,.22,lambda:self.close_hand(0))
        btn("AGARRAR",.16,.12,self.try_grasp)
        btn("SOLTAR",.46,.12,self.release)
        btn("+ CUBO",.16,.02,lambda:self.create_object("cubo"))
        btn("+ CUADRO",.46,.02,lambda:self.create_object("cuadro"))
        btn("+ PELOTA",.16,-.08,lambda:self.create_object("pelota"))
        btn("+ CAJA",.46,-.08,lambda:self.create_object("caja"))
        btn("GUARDAR",.16,-.18,self.save_scene)
        btn("BORRAR",.46,-.18,self.delete_object)
        btn("GRABAR",.16,-.28,self.begin_demonstration)
        btn("TERMINAR",.46,-.28,self.end_demonstration)
        btn("PRACTICAR",.16,-.38,self.try_imitation)
        btn("BIEN",.46,-.38,lambda:self.correct(True))
        self.feedback_label=DirectLabel(
            parent=self.panel,frameColor=(.06,.16,.22,1),
            text=self.last_message,text_scale=.034,
            text_fg=(.9,.96,.98,1),text_wordwrap=29,
            frameSize=(-.07,.65,-.19,.19),pos=(.29,0,-.55))
        self.entry=DirectEntry(
            parent=self.panel,width=18,scale=.037,
            pos=(-.055,0,-.76),frameColor=(.84,.94,.99,1),
            text_fg=(.06,.11,.18,1),
            initialText="",numLines=1,
            focus=0,command=self.command_enter)
        self.hint=OnscreenText(
            parent=self.panel,text="Escribe: esto es un cuadro / enseñar agarrar",
            pos=(.02,-.85),scale=.029,align=TextNode.ALeft,
            fg=(.68,.78,.84,1))
        self.legend=OnscreenText(
            parent=self.panel,text="WASD mover · T agarrar · G soltar · H practicar",
            pos=(.02,-.93),scale=.026,align=TextNode.ALeft,
            fg=(.54,.69,.77,1))

    def _update_status(self):
        selected=self.editor.object()
        obj_text=selected.name if selected else "ninguno"
        hand=self.teacher.selected_hand
        digit=FINGER_NAMES[self.teacher.selected_digit]
        self.status.setText(
            "OBJETO: "+obj_text[:25]+"\n"+
            "MANO: "+hand+" / "+digit)
        held=self.grasp.held()
        holding=", ".join(f"{k}:{v}" for k,v in held.items()) or "libres"
        self.substatus.setText(
            f"DEDO {self.teacher.curls[hand][self.teacher.selected_digit]:.2f}\n"+
            f"CONTACTOS: {holding}\n"+
            f"DEMOS: {self.learner.episodes} | PRUEBAS: {self.learner.attempts}")

    def _update(self,task):
        dt=max(0,min(.05,self.taskMgr.globalClock.getDt()))
        dx=int("d" in self.keys or "arrow_right" in self.keys)-int(
            "a" in self.keys or "arrow_left" in self.keys)
        dy=int("w" in self.keys or "arrow_up" in self.keys)-int(
            "s" in self.keys or "arrow_down" in self.keys)
        self.teacher.move(dx,dy,dt)
        if self.rotating_camera and self.mouseWatcherNode.hasMouse():
            m=self.mouseWatcherNode.getMouse()
            if self.mouse_prev:
                self.cam_yaw-=(m.x-self.mouse_prev.x)*120
                self.cam_pitch=max(8,min(77,self.cam_pitch+(m.y-self.mouse_prev.y)*95))
            self.mouse_prev=Point2(m)
        self._camera()
        self.grasp.sync()
        self.lab.step(dt)
        self.grasp.auto_check()
        self.recorder.record(self.teacher.pose(),dt)
        self._gui_clock+=dt
        if self._gui_clock>.16:
            self._gui_clock=0
            self._update_status()
        from direct.task.Task import Task
        return Task.cont


def main():
    smoke="--smoke-test" in sys.argv
    app=AMBOT2App(headless=smoke)
    if smoke:
        for _ in range(5):
            app.taskMgr.step()
        app.destroy()
        print("AMBOT2 SMOKE OK: 2 robots, entorno Bullet y GUI")
    else:
        app.run()


if __name__=="__main__":
    main()
