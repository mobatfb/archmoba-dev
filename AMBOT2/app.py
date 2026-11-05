"""AMBOT2: laboratorio nativo con un maestro humano y un robot aprendiz."""
from __future__ import annotations
import json
import math
import os
import subprocess
import sys
from pathlib import Path

VERSION="0.2.0"
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
from direct.gui.DirectGui import DirectFrame, DirectButton, DirectEntry, DirectSlider, DirectLabel, DirectScrolledFrame
from direct.gui.OnscreenText import OnscreenText
from engine.world import LabWorld
from body.robot import Humanoid, HAND_NAMES, FINGER_NAMES, JOINT_GROUPS, JOINT_LIMITS, JOINT_LABELS, clamp, tank_inputs
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
        self.demo_recorder=DemonstrationRecorder()
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
        self.accept("3",self.close_both,[1])
        self.accept("4",self.close_both,[0])
        self.accept("b",self.grab_both)
        self.accept("n",self.release_both)
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
        if hand not in HAND_NAMES:
            raise ValueError("Mano desconocida")
        self.teacher.selected_hand=hand
        if getattr(self,"menu_state",{}).get("MANOS Y DEDOS",False):
            self._rebuild_menu()
        self.say("Controlando mano "+hand)

    def select_finger(self,delta):
        self.teacher.selected_digit=(self.teacher.selected_digit+delta)%5
        self._refresh_control_sliders()
        self.say("Dedo: "+FINGER_NAMES[self.teacher.selected_digit])

    def adjust_finger(self,delta):
        hand=self.teacher.selected_hand
        i=self.teacher.selected_digit
        self.teacher.finger(hand,i,self.teacher.curls[hand][i]+delta)
        self._refresh_control_sliders()

    def set_finger_slider(self):
        """Compatibilidad con el control de dedo seleccionado anterior."""
        slider=getattr(self,"slider",None)
        if slider is not None:
            self.teacher.finger(
                self.teacher.selected_hand,self.teacher.selected_digit,slider["value"])

    def close_hand(self,value):
        self.teacher.hand_close(self.teacher.selected_hand,value)
        self._refresh_control_sliders()
        self.say("Mano "+self.teacher.selected_hand+
                 (" cerrada" if value else " abierta"))

    def adjust_reach(self,delta):
        self.teacher.reach=clamp(self.teacher.reach+delta)
        self.teacher.update_visual()

    def adjust_height(self,delta):
        self.teacher.hand_height=clamp(self.teacher.hand_height+delta,-1,1)
        self.teacher.update_visual()

    def close_both(self,value):
        for hand in HAND_NAMES:
            self.teacher.hand_close(hand,value)
        self._refresh_control_sliders()
        self.say("Ambas manos "+("cerradas" if value else "abiertas")+".")
        self.grasp.auto_check()

    def grab_both(self):
        self.grasp.sync()
        answers=[]
        for hand in HAND_NAMES:
            answers.append(self.grasp.try_nearest(hand))
        self.say(" | ".join(answers))
        return answers

    def release_both(self):
        self.grasp.release_all()
        self.say("He soltado los apoyos de ambas manos.")

    def try_grasp(self):
        self.grasp.sync()
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
            self.demo_recorder.begin(skill,self.teacher.pose())
            self.say("Grabando: "+skill+". Mueve tu cuerpo y pulsa P para terminar.")
        except ValueError as exc:
            self.say(str(exc))

    def end_demonstration(self):
        try:
            label,frames=self.demo_recorder.stop(self.teacher.pose())
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
            if command.startswith(("articulacion ","articulación ")):
                from language.understanding import normalize
                command_parts=normalize(raw).split()
                if len(command_parts)!=3:
                    raise ValueError("Uso: articulacion codo_izq 45")
                name=command_parts[1]
                degrees=float(command_parts[2])
                actual=self.teacher.set_joint(name,degrees)
                self._refresh_control_sliders()
                return self.say(
                    "Articulacion "+JOINT_LABELS[name]+f": {actual:+.0f} grados.")
            if command in ("postura neutra","reiniciar articulaciones"):
                return self._reset_all_joints()
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
            if command in ("agarrar ambos","tomar ambos","agarrar dos manos"):
                return self.grab_both()
            if command in ("abrir ambas","abrir ambas manos"):
                return self.close_both(0)
            if command in ("cerrar ambas","cerrar ambas manos"):
                return self.close_both(1)
            if command in ("soltar ambos","soltar las dos"):
                return self.release_both()
            if command in ("tomar","agarrar"):
                return self.try_grasp()
            if command in ("soltar","liberar"):
                return self.release()
            if command=="ayuda":
                return self.say("TANQUE: W/S avance-retroceso, A/D giro sobre eje; flechas equivalentes | 1/2 mano | [ ] dedo | Q/E flexionar | 3/4 ambas manos | B agarrar ambas | N soltar ambas | O/P grabar | H practicar | 5-8 objetos | lenguaje en el campo de texto.")
            answer=self.language.hear(raw,self.editor.selected)
            return self.say("AMBOT: "+answer)
        except (ValueError,KeyError,TypeError,OSError) as exc:
            return self.say("No pude ejecutar: "+str(exc))

    def _ui(self):
        """Panel fijo + acordeon vertical desplazable de secciones editables."""
        self.panel=DirectFrame(
            parent=self.aspect2d,frameColor=(.045,.085,.13,.96),
            frameSize=(-.10,.76,-.995,.995),pos=(.60,0,0))
        self.header=OnscreenText(
            parent=self.panel,text="AMBOT 2.0  /  MAESTRO",pos=(0,.92),
            align=TextNode.ALeft,scale=.052,fg=(.54,.9,1,1))
        self.subtitle=OnscreenText(
            parent=self.panel,text="Articulaciones · manos · objetos · aprendizaje",
            pos=(0,.855),align=TextNode.ALeft,scale=.027,
            fg=(.54,.70,.79,1))
        self.status=OnscreenText(
            parent=self.panel,text="",pos=(0,.79),scale=.029,
            align=TextNode.ALeft,fg=(.93,.98,1,1),mayChange=True)
        self.substatus=OnscreenText(
            parent=self.panel,text="",pos=(0,.675),scale=.026,
            align=TextNode.ALeft,fg=(.70,.83,.89,1),mayChange=True)

        self.menu_order=list(JOINT_GROUPS)+[
            "MANOS Y DEDOS","AGARRE","OBJETOS","APRENDIZAJE","AYUDA"]
        self.menu_state={
            section:section=="CABEZA Y TRONCO" for section in self.menu_order
        }
        self.joint_sliders={}
        self.joint_values={}
        self.finger_sliders={}
        self.slider=None
        self._menu_sync=False
        self.menu_scroll=DirectScrolledFrame(
            parent=self.panel,pos=(0,0,0),
            frameSize=(-.078,.710,-.515,.585),
            canvasSize=(-.060,.640,-2.7,.02),
            frameColor=(.065,.125,.18,.95),
            scrollBarWidth=.042,
            autoHideScrollBars=False,
            manageScrollBars=True,
            verticalScroll_frameColor=(.18,.30,.38,1),
            horizontalScroll_frameColor=(.18,.30,.38,1))
        self.menu_content=None
        self._rebuild_menu()

        self.feedback_label=DirectLabel(
            parent=self.panel,text=self.last_message,
            text_scale=.029,text_fg=(.90,.97,1,1),
            text_wordwrap=40,
            frameColor=(.075,.17,.23,1),
            frameSize=(-.07,.66,-.085,.08),
            pos=(.293,0,-.624))
        self.entry=DirectEntry(
            parent=self.panel,width=19,scale=.035,
            pos=(-.04,0,-.792),
            frameColor=(.87,.94,1,1),text_fg=(.05,.10,.16,1),
            initialText="",numLines=1,focus=0,command=self.command_enter)
        self.hint=OnscreenText(
            parent=self.panel,text="Habla con AMBOT o escribe: articulacion codo_izq 45",
            pos=(-.04,-.86),scale=.026,align=TextNode.ALeft,
            fg=(.67,.80,.87,1))
        self.legend=OnscreenText(
            parent=self.panel,text="W/S AVANZAR · A/D GIRAR · SCROLL EN MENU",
            pos=(-.04,-.932),scale=.025,align=TextNode.ALeft,
            fg=(.55,.70,.78,1))
        self._update_status()

    def toggle_section(self,section):
        """Abrir/cerrar secciones independientemente sin perder sus valores."""
        if section not in self.menu_state:
            raise ValueError("Seccion desconocida")
        self.menu_state[section]=not self.menu_state[section]
        self._rebuild_menu()
        return self.menu_state[section]

    def _menu_button(self,text,x,y,callback):
        return DirectButton(
            parent=self.menu_content,text=text,scale=.036,
            pos=(x,0,y),frameSize=(-4.2,4.2,-1.07,1.10),
            frameColor=(.16,.32,.43,1),
            text_fg=(.95,.99,1,1),
            rolloverSound=None,clickSound=None,command=callback)

    def _menu_label(self,text,y,size=.028):
        return OnscreenText(
            parent=self.menu_content,text=text,
            pos=(-.035,y),scale=size,
            align=TextNode.ALeft,fg=(.81,.90,.96,1))

    def _on_joint_slider(self,name):
        if getattr(self,"_menu_sync",False):
            return
        widget=self.joint_sliders.get(name)
        if widget is None:
            return
        value=self.teacher.set_joint(name,widget["value"])
        label=self.joint_values.get(name)
        if label is not None:
            label.setText(f"{value:+.0f}°")
        self.current_joint=name

    def _on_finger_slider(self,hand,index):
        if getattr(self,"_menu_sync",False):
            return
        widget=self.finger_sliders.get((hand,index))
        if widget is None:
            return
        self.teacher.selected_hand=hand
        self.teacher.selected_digit=index
        self.teacher.finger(hand,index,widget["value"])
        self.slider=widget

    def _refresh_control_sliders(self):
        if not hasattr(self,"finger_sliders"):
            return
        self._menu_sync=True
        try:
            for (hand,index),slider in self.finger_sliders.items():
                slider["value"]=self.teacher.curls[hand][index]
            for name,slider in self.joint_sliders.items():
                slider["value"]=self.teacher.joints[name]
                if name in self.joint_values:
                    self.joint_values[name].setText(
                        f"{self.teacher.joints[name]:+.0f}°")
            self.slider=self.finger_sliders.get(
                (self.teacher.selected_hand,self.teacher.selected_digit))
        finally:
            self._menu_sync=False

    def _reset_group(self,section):
        for name,*_ in JOINT_GROUPS[section]:
            self.teacher.joints[name]=0.0
        self.teacher.update_visual()
        self._refresh_control_sliders()
        self.say("Articulaciones de "+section.lower()+" en posicion neutra.")

    def _reset_all_joints(self):
        self.teacher.reset_joints()
        self._refresh_control_sliders()
        self.say("Todas las articulaciones vuelven a cero.")

    def _rebuild_menu(self):
        """Construir solo los contenidos de las secciones desplegadas."""
        previous_scroll=0.0
        if getattr(self,"menu_scroll",None) is not None:
            try:
                previous_scroll=float(self.menu_scroll.verticalScroll["value"])
            except (KeyError,TypeError,AttributeError):
                pass
        if self.menu_content is not None:
            self.menu_content.destroy()
        self.menu_content=DirectFrame(
            parent=self.menu_scroll.getCanvas(),
            frameSize=(-.06,.64,-5,0),
            frameColor=(0,0,0,0))
        self.joint_sliders={}
        self.joint_values={}
        self.finger_sliders={}
        self.slider=None
        self._menu_sync=True
        y=-.065
        for title in self.menu_order:
            opened=self.menu_state[title]
            DirectButton(
                parent=self.menu_content,
                text=("[ - ] " if opened else "[ + ] ")+title,
                text_align=TextNode.ALeft,text_pos=(-7.7,0),
                pos=(.285,0,y),scale=.037,
                frameSize=(-8.25,8.25,-1.13,1.17),
                frameColor=(.16,.31,.40,1) if opened
                           else (.105,.21,.28,1),
                text_fg=(.95,.99,1,1),
                rolloverSound=None,clickSound=None,
                command=lambda name=title:self.toggle_section(name))
            y-=.112
            if not opened:
                continue
            if title in JOINT_GROUPS:
                for name,label,minimum,maximum in JOINT_GROUPS[title]:
                    self._menu_label(label,y+.006,size=.026)
                    bar=DirectSlider(
                        parent=self.menu_content,
                        pos=(.405,0,y),scale=.115,
                        range=(minimum,maximum),
                        value=self.teacher.joints[name],
                        frameColor=(.18,.35,.45,1),
                        command=self._on_joint_slider,extraArgs=[name])
                    self.joint_sliders[name]=bar
                    self.joint_values[name]=OnscreenText(
                        parent=self.menu_content,
                        text=f"{self.teacher.joints[name]:+.0f}°",
                        pos=(.58,y+.003),scale=.026,
                        fg=(.65,.93,.96,1))
                    y-=.105
                self._menu_button("NEUTRO",.13,y,
                                  lambda group=title:self._reset_group(group))
                self._menu_button("RESET TOTAL",.45,y,self._reset_all_joints)
                y-=.105
            elif title=="MANOS Y DEDOS":
                self._menu_button("IZQUIERDA",.13,y,
                                  lambda:self.select_hand("izquierda"))
                self._menu_button("DERECHA",.45,y,
                                  lambda:self.select_hand("derecha"))
                y-=.11
                hand=self.teacher.selected_hand
                self._menu_label("Mano: "+hand.upper(),y)
                y-=.085
                for index,name in enumerate(FINGER_NAMES):
                    self._menu_label(name.upper(),y+.007,size=.026)
                    bar=DirectSlider(
                        parent=self.menu_content,
                        pos=(.40,0,y),scale=.133,
                        range=(0,1),
                        value=self.teacher.curls[hand][index],
                        frameColor=(.18,.35,.45,1),
                        command=self._on_finger_slider,
                        extraArgs=[hand,index])
                    self.finger_sliders[(hand,index)]=bar
                    y-=.10
                self.slider=self.finger_sliders.get(
                    (hand,self.teacher.selected_digit))
                self._menu_button("CERRAR MANO",.13,y,
                                  lambda:self.close_hand(1))
                self._menu_button("ABRIR MANO",.45,y,
                                  lambda:self.close_hand(0))
                y-=.105
                self._menu_button("CERRAR 2",.13,y,
                                  lambda:self.close_both(1))
                self._menu_button("ABRIR 2",.45,y,
                                  lambda:self.close_both(0))
                y-=.105
            elif title=="AGARRE":
                self._menu_label("Sujecion: contacto real con los dedos.",y)
                y-=.085
                self._menu_button("AGARRAR MANO",.13,y,self.try_grasp)
                self._menu_button("SOLTAR MANO",.45,y,self.release)
                y-=.105
                self._menu_button("AGARRAR 2",.13,y,self.grab_both)
                self._menu_button("SOLTAR 2",.45,y,self.release_both)
                y-=.11
                self._menu_label("Se activa al cerrar sobre un objeto.",y)
                y-=.09
            elif title=="OBJETOS":
                for left,right in (("cubo","cuadro"),
                                   ("pelota","caja"),
                                   ("tabla","cama")):
                    self._menu_button("+ "+left.upper(),.13,y,
                                      lambda kind=left:self.create_object(kind))
                    self._menu_button("+ "+right.upper(),.45,y,
                                      lambda kind=right:self.create_object(kind))
                    y-=.105
                self._menu_button("+ MESA",.13,y,
                                  lambda:self.create_object("mesa"))
                self._menu_button("BORRAR",.45,y,self.delete_object)
                y-=.105
                self._menu_button("GUARDAR",.13,y,self.save_scene)
                self._menu_button("CARGAR",.45,y,self.load_scene)
                y-=.11
            elif title=="APRENDIZAJE":
                self._menu_label("Enseñar nombre: enseñar flexionar codo",y)
                y-=.082
                self._menu_button("GRABAR",.13,y,self.begin_demonstration)
                self._menu_button("FINALIZAR",.45,y,self.end_demonstration)
                y-=.105
                self._menu_button("PRACTICAR",.13,y,self.try_imitation)
                self._menu_button("BIEN",.45,y,lambda:self.correct(True))
                y-=.105
                self._menu_button("MAL",.13,y,lambda:self.correct(False))
                self._menu_button("NEUTRO",.45,y,self._reset_all_joints)
                y-=.11
            elif title=="AYUDA":
                for msg in (
                    "W/S avanzar-retroceder, A/D girar.",
                    "Arrastra el deslizador de cada articulacion.",
                    "Cada articulacion tiene limites en grados.",
                    "1/2 mano, [ ] dedo, Q/E flexionar.",
                    "T/G agarre, B/N agarrar/soltar dos.",
                    "Habla con AMBOT en el campo inferior.",
                ):
                    self._menu_label(msg,y,size=.025)
                    y-=.078
            y-=.035

        self.menu_scroll["canvasSize"]=(
            -.06,.64,min(-1.45,y-.10),.02)
        try:
            self.menu_scroll.verticalScroll["value"]=previous_scroll
        except (KeyError,AttributeError,TypeError):
            pass
        self._menu_sync=False

    def load_scene(self):
        self.grasp.release_all()
        self.editor.load()
        self.say("Escena recuperada.")

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
        touched={"izquierda":0,"derecha":0}
        if selected:
            for which in HAND_NAMES:
                touched[which]=sum(self.grasp._contacts(which,selected).values())
        self.substatus.setText(
            f"AGARRE: {holding}\n"+
            f"CONTACTOS I/D: {touched['izquierda']} / {touched['derecha']}\n"+
            f"DEMOS: {self.learner.episodes} | ENSAYOS: {self.learner.attempts}")

    def _update(self,task):
        dt=max(0,min(.05,self.taskMgr.globalClock.getDt()))
        # No mover el avatar mientras se escriben instrucciones al aprendiz.
        if self.entry["focus"]:
            self.keys.clear()
        forward,turn=tank_inputs(self.keys)
        self.teacher.drive(forward,turn,dt)
        if self.rotating_camera and self.mouseWatcherNode.hasMouse():
            m=self.mouseWatcherNode.getMouse()
            if self.mouse_prev:
                self.cam_yaw-=(m.x-self.mouse_prev.x)*120
                self.cam_pitch=max(8,min(77,self.cam_pitch+(m.y-self.mouse_prev.y)*95))
            self.mouse_prev=Point2(m)
        self._camera()
        self.grasp.sync()
        acquired=self.grasp.auto_acquire()
        if acquired and not self.headless:
            self.say("Contacto confirmado: "+" / ".join(acquired))
        self.lab.step(dt)
        self.grasp.auto_check()
        self.demo_recorder.record(self.teacher.pose(),dt)
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
