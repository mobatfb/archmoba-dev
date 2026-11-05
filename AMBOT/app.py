# -*- coding: utf-8 -*-
"""AMBOT - ARCHMOBA ROBOTICS. Aplicacion Python nativa: robot y entorno 3D.

Sin servidor HTTP, navegador, Tkinter, archivos JavaScript ni HTML.
El motor 3D de perspectiva, interfaz, stickman y cerebro viven en este .py.
Usa pygame-ce (SDL) para abrir una ventana de escritorio en Windows/Linux.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
from dataclasses import dataclass, asdict
import os
import subprocess
import sys
import time
import traceback
import unicodedata
from collections import deque
from pathlib import Path

APP_NAME = "AMBOT"
APP_VERSION = "0.9.0"
APP_UPDATE_DATE = "05/11/2026"
APP_UPDATE_TIME = "01:55"
TITLE = "AMBOT | ARCHMOBA ROBOTICS"
ROOT = Path(__file__).resolve().parent
USER_ROOT = (Path(os.environ["LOCALAPPDATA"]) / "ARCHMOBA" / "AMBOT"
             if os.environ.get("LOCALAPPDATA") else Path.home() / ".archmoba" / "ambot")
MEMORY_PATH = USER_ROOT / "memoria.json"
LOG_PATH = USER_ROOT / "launch.log"
DEPENDENCIES = USER_ROOT / "dependencies"

# La primera habitacion tiene cuatro paredes y una salida hacia el pasillo.
# El robot comienza dentro. El espacio se ve sin techo para mover la camara.
WORLD = (
    "##############",
    "#............#",
    "#.#######....#",
    "#.#.....#....#",
    "#.#.....#....#",
    "#.#..........#",
    "#.#.....#....#",
    "#.#.....#....#",
    "#.#######....#",
    "#............#",
    "##############",
)
ROOM_NAME = "HABITACION INICIAL"
ROOM_CELLS = frozenset((x, z) for z in range(3, 8) for x in range(3, 8))
ROOM_DOOR = (8, 5)
ROOM_WALL_CELLS = frozenset(
    {(x, 2) for x in range(2, 9)}
    | {(x, 8) for x in range(2, 9)}
    | {(2, z) for z in range(3, 8)}
    | {(8, z) for z in range(3, 8) if z != 5}
)
# La geometria es descriptiva, no un conocimiento aprendido por AMBOT.
ROOM_OBJECTS = {
    "cama": ((4, 7), (5, 7)),
    "mesa": ((4, 4),),
    "silla": ((4, 5),),
    "armario": ((7, 3),),
}
FURNITURE_CELLS = frozenset(cell for cells in ROOM_OBJECTS.values() for cell in cells)
TILE = 1.35
DIRECTIONS = ((0, -1), (1, 0), (0, 1), (-1, 0))

# Movimiento de tanque al estilo del Resident Evil clasico: no hay strafe.
# La orientacion del personaje, NO la camara, determina el avance/retroceso.
TANK_ROTATION_RATE=math.radians(200)
TANK_GUIDE_SPEED=1.7  # casillas por segundo
TANK_HOLD_INTERVALS={
    "forward":.26, "back":.35, "left":.45, "right":.45
}


def facing_radians(facing):
    return (0.0,math.pi/2,math.pi,-math.pi/2)[facing % 4]


def rotate_towards(current,target,max_step):
    """Giro angular menor, sin trasladar el cuerpo."""
    difference=(target-current+math.pi) % (2*math.pi)-math.pi
    if abs(difference)<=max_step:
        return target
    return current+math.copysign(max_step,difference)

ORIENTATIONS = ("NORTE", "ESTE", "SUR", "OESTE")
COLOR = {
    "bg": (5, 13, 25),
    "panel": (10, 25, 40),
    "panel2": (14, 34, 52),
    "line": (35, 76, 103),
    "ink": (226, 247, 255),
    "muted": (129, 170, 194),
    "cyan": (92, 233, 250),
    "blue": (27, 162, 223),
    "pink": (255, 112, 182),
    "green": (105, 232, 186),
    "yellow": (249, 200, 121),
    "ground": (9, 27, 43),
    "floor1": (14, 39, 58),
    "floor2": (12, 34, 53),
    "wall": (30, 68, 95),
    "inner": (42, 86, 121),
    "room_floor": (30, 66, 83),
    "room_floor2": (26, 56, 75),
    "room_wall": (45, 91, 120),
    "rug": (18, 91, 119),
    "wood": (70, 118, 146),
    "bed": (80, 164, 197),
    "window": (81, 205, 245),
}


def normalize(text):
    text = unicodedata.normalize("NFD", str(text).strip().lower())
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


def ensure_pygame(no_install=False):
    """Carga pygame-ce o lo instala en una carpeta privada de AMBOT."""
    def import_pygame():
        import pygame
        return pygame

    try:
        return import_pygame()
    except ImportError:
        pass
    if DEPENDENCIES.is_dir():
        sys.path.insert(0, str(DEPENDENCIES))
        try:
            return import_pygame()
        except ImportError:
            pass
    if no_install or os.environ.get("AMBOT_NO_AUTO_INSTALL") == "1":
        raise RuntimeError("Falta pygame-ce. Instala con: python -m pip install pygame-ce")
    DEPENDENCIES.mkdir(parents=True, exist_ok=True)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    cmd = [
        sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
        "--no-input", "--only-binary=:all:", "--target", str(DEPENDENCIES),
        "pygame-ce>=2.5.7,<3",
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, timeout=150, creationflags=flags)
    if result.returncode:
        raise RuntimeError(
            "No se pudo instalar pygame-ce para Python " + sys.version.split()[0]
            + ".\n" + result.stdout[-2500:]
        )
    if str(DEPENDENCIES) not in sys.path:
        sys.path.insert(0, str(DEPENDENCIES))
    return import_pygame()



# ---- Entorno de aprendizaje basado en observacion y consecuencia fisica ----
# Estas etiquetas describen la simulacion para los robots guia. AMBOT bebe
# NO recibe los nombres ni las acciones correctas como conocimiento inicial.
SKILL_NAMES = ("caminar", "agarrar", "transportar", "descansar", "reconocer")


@dataclass
class Movable:
    name: str
    x: float
    z: float
    shape: str
    color: tuple
    radius: float = .22
    y: float = .22
    vy: float = 0.0
    vx: float = 0.0
    vz: float = 0.0
    mass: float = 1.0
    held_by: str = ""
    moved: float = 0.0


class Guide:
    """Actor demostrador: sabe la tarea, a diferencia del bebe."""
    def __init__(self, name, task, x, z, facing, color, program):
        self.name, self.task = name, task
        self.x, self.z, self.facing = float(x), float(z), facing
        self.color = color
        self.program = program
        self.index = -1
        self.elapsed = 0.0
        self.walk = 0.0
        self.moving = False
        self.posture = "standing"
        self.reach = 0.0
        self.holding = None
        self.message = ""
        self.target = (self.x, self.z)
        self.start = (self.x, self.z)
        self.action = "esperar"
        self.heading=facing_radians(self.facing)
        self.turning=False
        self.motion_distance=0.0

    def current(self):
        return self.program[self.index % len(self.program)]


class TrainingLab:
    """Aprendizaje de habilidades por observaciones parciales y ensayos.

    Las tres demostraciones estan preprogramadas SOLO para los guias.
    AMBOT acumula asociaciones entre observaciones y consecuencias, aprende
    tasas de exito y practica con fallos, sin recibir el mapa secreto de guias.
    Se simulan gravedad, rebote, colision y agarre; no es fisica de rigid bodies.
    """
    GUIDE_PROGRAMS = (
        (
            ("walk", (3, 4), 1.3, "Paso lento: primero apoyo un pie."),
            ("walk", (3, 5), 1.3, "Un paso mas: ajusto mi equilibrio."),
            ("walk", (3, 6), 1.3, "Ahora cambio el peso de mi cuerpo."),
            ("walk", (3, 5), 1.3, "Puedo caminar hacia atras."),
            ("walk", (3, 4), 1.3, "Practico para mantener el equilibrio."),
            ("pause", None, 1.0, "Repite despacio lo que acabas de ver."),
        ),
        (
            ("identify", "cubo", 1.6, "Esto se llama cubo. Mira sus caras."),
            ("grasp", "cubo", 1.6, "Cierro mis manos y sujeto el cubo."),
            ("carry", (7, 5), 1.8, "Llevo el cubo conmigo."),
            ("release", "cubo", 1.5, "Ahora suelto el cubo: cae al suelo."),
            ("identify", "pelota", 1.6, "Esto se llama pelota. Su forma es redonda."),
            ("pause", None, 1.0, "Tambien puedes experimentar con objetos."),
        ),
        (
            ("approach", (5.5, 6.1), 1.6, "Me acerco a la cama."),
            ("lie", (4.5, 7.0), 2.5, "Me recuesto sobre la cama."),
            ("rest", None, 1.8, "Mi cuerpo descansa apoyado en ella."),
            ("rise", (5.5, 6.1), 1.4, "Me incorporo y vuelvo a estar de pie."),
            ("pause", None, 1.1, "Acostarse requiere controlar el cuerpo."),
        ),
    )

    def __init__(self, baby, path):
        self.baby = baby
        self.path = Path(path)
        self.rng = random.Random(2091)
        self.confidence = {name: 0.0 for name in SKILL_NAMES}
        self.observations = 0
        self.attempts = 0
        self.falls = 0
        self.drops = 0
        self.name_heard = {}
        self.known_names = set()
        self.last_seen = {}
        self.demo_sequence = 0
        self.messages = deque(maxlen=30)
        self.focus = 0
        self.focus_boost = False
        self.items = {
            "cubo": Movable("cubo", 6.0, 4.0, "box", (252, 119, 143)),
            "pelota": Movable("pelota", 6.0, 6.0, "ball", (89, 176, 254)),
            "bloque": Movable("bloque", 7.0, 6.0, "box", (244, 198, 117),mass=1.7),
        }
        self.guides = [
            Guide("ANDA", "CAMINAR", 3, 3, 2, (106, 230, 190),
                  self.GUIDE_PROGRAMS[0]),
            Guide("DEX", "OBJETOS", 7, 4, 2, (255, 175, 90),
                  self.GUIDE_PROGRAMS[1]),
            Guide("SOMA", "DESCANSAR", 5.5, 6.1, 0, (184, 155, 251),
                  self.GUIDE_PROGRAMS[2]),
        ]
        self.all_guide_specs={
            g.name:(g.task,g.x,g.z,g.facing,g.color,g.program)
            for g in self.guides
        }
        self._load()

    def restore_guide(self,name):
        spec=self.all_guide_specs.get(name)
        if not spec or any(g.name==name for g in self.guides):
            return False
        self.guides.append(Guide(name,*spec))
        self.guides.sort(key=lambda g:list(self.all_guide_specs).index(g.name))
        self.focus=min(self.focus,len(self.guides)-1)
        return True

    def _load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            rates = data.get("confidence", {})
            for name in SKILL_NAMES:
                self.confidence[name] = max(0.0, min(1.0, float(rates.get(name, 0.0))))
            self.observations = max(0, int(data.get("observations", 0)))
            self.attempts = max(0, int(data.get("attempts", 0)))
            self.falls = max(0, int(data.get("falls", 0)))
            self.drops = max(0, int(data.get("drops", 0)))
            self.name_heard = {str(k): int(v) for k,v in data.get("name_heard", {}).items()}
            self.known_names = set(map(str, data.get("known_names", [])))
        except (OSError, TypeError, ValueError, AttributeError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        path = self.path.with_name(self.path.name + ".tmp")
        path.write_text(json.dumps({
            "version": 1, "confidence": self.confidence,
            "observations": self.observations, "attempts": self.attempts,
            "falls": self.falls, "drops": self.drops,
            "name_heard": self.name_heard,
            "known_names": sorted(self.known_names)
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        path.replace(self.path)

    def lesson(self, skill, amount, source="observar"):
        if skill not in self.confidence:
            return
        old = self.confidence[skill]
        self.confidence[skill] = round(min(1.0, old + amount*(1.0-old*.32)), 4)
        self.save()

    def practice(self, skill, success):
        self.attempts += 1
        self.lesson(skill, .095 if success else .043, "practicar")

    def distance(self, x1, z1, x2, z2):
        return math.hypot(x1-x2,z1-z2)

    def within_sight(self, guide):
        # Campo de observacion simulado; la habitacion no suministra etiquetas
        # de objetos ni las decisiones privadas de los guias al bebe.
        return self.distance(self.baby.x,self.baby.z,guide.x,guide.z) < 6.4

    def witness(self, guide, kind, label=None):
        self.demo_sequence += 1
        if not self.within_sight(guide):
            return
        skill = {
            "walk": "caminar", "identify": "reconocer", "grasp": "agarrar",
            "carry": "transportar", "release": "agarrar",
            "lie": "descansar", "rest": "descansar", "rise": "descansar",
        }.get(kind)
        if skill:
            self.observations += 1
            self.lesson(skill, .075 if kind!="rest" else .045)
        if kind=="identify" and label in self.items:
            # La palabra pronunciada es un indicio sensorial; varias
            # apariciones son necesarias para formar la asociacion.
            self.name_heard[label] = self.name_heard.get(label,0)+1
            if self.name_heard[label] >= 3:
                self.known_names.add(label)
            self.save()
        self.last_seen[guide.name] = (kind,self.demo_sequence)
        baby_text = {
            "walk": "Vi cambiar de lugar sus piernas...",
            "identify": "Escuche un sonido mientras senalaba un objeto.",
            "grasp": "Las manos se cerraron y el objeto se movio.",
            "carry": "El objeto siguio a las manos.",
            "release": "El objeto dejo de seguirlas y cayo.",
            "lie": "Su cuerpo cambio de vertical a horizontal.",
            "rest": "Sigue apoyado, sin desplazarse.",
            "rise": "Se levanto otra vez.",
        }.get(kind)
        if baby_text:
            self.baby.last_decision = baby_text
        self.messages.append({
            "teacher": guide.name, "action": kind,
            "message": guide.message,
            "baby": baby_text or "...",
            "serial": self.demo_sequence,
        })

    def _new_step(self, guide):
        guide.index=(guide.index+1)%len(guide.program)
        guide.elapsed=0.0
        action,target,seconds,message=guide.current()
        guide.start=(guide.x,guide.z)
        guide.target=target if isinstance(target, tuple) else guide.start
        guide.action=action
        guide.message=message
        guide.moving=False
        guide.turning=False
        guide.reach=1.0 if action in ("identify","grasp","carry","release") else 0.0
        if action=="rest":
            guide.posture="lying"
        elif action in ("rise","walk","approach","lie","pause","identify"):
            guide.posture="standing"
        if action=="grasp":
            item=self.items.get(str(target))
            if item and not item.held_by:
                item.held_by=guide.name
                guide.holding=item.name
                item.y=1.12
                item.vy=0
        if action=="release":
            self.release_owner(guide.name)
        if action in ("walk","identify","grasp","carry","release","lie","rest","rise"):
            self.witness(guide,action,target if isinstance(target,str) else None)

    def release_owner(self, owner):
        for item in self.items.values():
            if item.held_by==owner:
                item.held_by=""
                item.vy=-.65
                item.y=max(item.radius+.6,item.y)
                if owner=="AMBOT":
                    self.baby.holding=None
                else:
                    for guide in self.guides:
                        if guide.name==owner: guide.holding=None
                return item
        return None

    def _tank_guide_step(self,guide,target,dt):
        """Primero gira; luego camina SOLO por el eje hacia el que apunta.

        Ruta ortogonal por tramos: prohibido interpolar en diagonal o deslizar.
        """
        dx=target[0]-guide.x
        dz=target[1]-guide.z
        if abs(dx)<.015 and abs(dz)<.015:
            guide.x,guide.z=target
            guide.moving=False
            guide.turning=False
            return True
        # Tramos en X y luego Z. El giro debe terminar antes de trasladarse.
        if abs(dx)>.015:
            direction=1 if dx>0 else 3
            remaining=abs(dx)
        else:
            direction=2 if dz>0 else 0
            remaining=abs(dz)
        desired=facing_radians(direction)
        guide.heading=rotate_towards(
            guide.heading,desired,TANK_ROTATION_RATE*dt)
        error=abs((desired-guide.heading+math.pi)%(2*math.pi)-math.pi)
        guide.turning=error>.015
        if guide.turning:
            guide.moving=False
            return False
        guide.facing=direction
        travel=min(remaining,TANK_GUIDE_SPEED*dt)
        x,z=DIRECTIONS[direction]
        guide.x+=x*travel
        guide.z+=z*travel
        guide.motion_distance+=travel
        guide.moving=travel>0
        return False

    def _guide_update(self, guide, dt):
        if guide.index<0:
            self._new_step(guide)
        guide.elapsed+=dt
        action,target,duration,_=guide.current()
        has_destination=(action in ("walk","approach","carry","rise","lie")
                         and isinstance(target,tuple))
        reached=True
        if has_destination:
            reached=self._tank_guide_step(guide,target,dt)
            if action=="lie":
                guide.posture="lying" if reached else "standing"
        else:
            guide.turning=False
            guide.moving=False
        guide.walk+=dt*(8.0 if guide.moving else 1.2)
        # Nunca saltar a la siguiente demostracion durante el giro.
        if guide.elapsed>=duration and reached:
            self._new_step(guide)

    def update(self,dt):
        dt=max(0.0,min(.07,float(dt)))
        for guide in self.guides:
            self._guide_update(guide,dt)
        for item in self.items.values():
            if item.held_by:
                holder=self.baby if item.held_by=="AMBOT" else next(
                    (g for g in self.guides if g.name==item.held_by),None)
                if holder:
                    facing=DIRECTIONS[holder.facing]
                    item.x=holder.x+facing[0]*.48
                    item.z=holder.z+facing[1]*.48
                    item.y=1.10
                    item.vy=0
                    item.vx=item.vz=0.0
                    continue
                item.held_by=""
            # Fisica horizontal con friccion y limites del espacio.
            if abs(item.vx)+abs(item.vz)>.008:
                nx=item.x+item.vx*dt
                nz=item.z+item.vz*dt
                ix,iz=int(round(nx)),int(round(nz))
                if self.baby.free(ix,iz):
                    item.moved+=math.hypot(nx-item.x,nz-item.z)
                    item.x,item.z=nx,nz
                else:
                    item.vx*=-.25
                    item.vz*=-.25
                drag=max(.0,1.0-3.4*dt)
                item.vx*=drag
                item.vz*=drag
            # Fisica vertical sencilla: gravedad, suelo y pequeno rebote.
            if item.y>item.radius or item.vy!=0:
                item.vy-=9.81*dt
                item.y+=item.vy*dt
                if item.y<=item.radius:
                    item.y=item.radius
                    item.vy=-item.vy*.18 if item.vy<-.7 else 0.0
        if self.baby.stumble>0:
            self.baby.stumble=max(0.0,self.baby.stumble-dt)
            if self.baby.stumble<=0 and self.baby.posture=="stumble":
                self.baby.posture="standing"

    def motor_feedback(self,success):
        self.practice("caminar",success)
        if not success:
            self.falls+=1
            self.baby.stumble=.7
            self.baby.posture="stumble"
            self.baby.last_decision="Perdi el equilibrio. Debo ajustar el movimiento."
            self.save()

    def object_in_cell(self,x,z):
        """Colision con objeto movil apoyado en el suelo."""
        for item in self.items.values():
            if not item.held_by and self.distance(x,z,item.x,item.z)<.57:
                return item
        return None

    def push(self,object_item,dx,dz):
        """Empujar produce desplazamiento horizontal, limitado por muros."""
        baby=self.baby
        nx,nz=object_item.x+dx*.87,object_item.z+dz*.87
        # El bebe no conoce el mapa: solo se utiliza para fisica externa.
        if not baby.free(int(round(nx)),int(round(nz))):
            self.attempts+=1
            self.save()
            return "Empujo, pero el objeto no puede avanzar: hay una barrera."
        if self.object_in_cell(nx,nz):
            return "El objeto choca con otro objeto."
        object_item.x=nx
        object_item.z=nz
        force=.87/max(.65,object_item.mass)
        object_item.vx=dx*force
        object_item.vz=dz*force
        object_item.moved+=abs(force)
        self.practice("transportar",True)
        baby.last_decision="Al tocar algo, pude cambiar su posicion."
        return "Siento resistencia y consigo empujar algo."

    def try_grab(self):
        baby=self.baby
        if baby.holding:
            return "Siento algo sujeto en mis manos. Puedo moverlo o soltarlo."
        nearby=[o for o in self.items.values()
                if not o.held_by and self.distance(baby.x,baby.z,o.x,o.z)<1.75]
        if not nearby:
            return "Extiendo la mano, pero no alcanzo ningun objeto."
        item=min(nearby,key=lambda o:self.distance(baby.x,baby.z,o.x,o.z))
        baby.reach=1.0
        success=self.rng.random()<.22+.73*self.confidence["agarrar"]
        self.practice("agarrar",success)
        if not success:
            self.drops+=1
            item.y=max(item.radius,item.y+.30)
            item.vy=.5
            baby.last_decision="El objeto se escapo. Intentare cerrar mejor las manos."
            self.save()
            return "Mis dedos resbalaron y el objeto cayo. Voy a intentarlo otra vez."
        item.held_by="AMBOT"
        baby.holding=item.name
        baby.last_decision="El objeto acompana ahora el movimiento de mi mano."
        return "Siento contacto y puedo sostener algo. Ahora puedo transportarlo."

    def try_release(self):
        item=self.release_owner("AMBOT")
        if not item:
            return "Mis manos estan vacias."
        self.practice("agarrar",True)
        self.baby.reach=0.0
        return "Abro las manos. El objeto cae por la gravedad."

    def try_rest(self):
        baby=self.baby
        if baby.posture=="lying":
            baby.posture="standing"
            return "Estoy volviendo a incorporarme."
        if (hasattr(baby,"furniture") and
                "cama" in baby.furniture.removed_fixed):
            return "No hay cama para practicar el descanso."
        if self.distance(baby.x,baby.z,4.5,7)>2.6:
            return "No encuentro una superficie cercana donde acostarme."
        success=self.rng.random()<.16+.80*self.confidence["descansar"]
        self.practice("descansar",success)
        if not success:
            baby.posture="stumble"
            baby.stumble=.9
            self.falls+=1
            baby.last_decision="Mi cuerpo se desestabilizo al intentar acostarme."
            self.save()
            return "Intente recostarme, pero perdi el equilibrio."
        baby.posture="lying"
        baby.last_decision="Mi cuerpo puede permanecer horizontal sobre la cama."
        return "Descubro una postura horizontal. Estoy apoyado sobre la cama."

    def identify(self):
        baby=self.baby
        nearby=[o for o in self.items.values()
                if self.distance(baby.x,baby.z,o.x,o.z)<2.3]
        if not nearby:
            return "Veo formas lejanas, aun sin nombre."
        item=min(nearby,key=lambda o:self.distance(baby.x,baby.z,o.x,o.z))
        if item.name in self.known_names:
            return "Creo reconocer la palabra " + item.name + " asociada a esta forma."
        return "Percibo un objeto con forma "+("redonda" if item.shape=="ball" else "angular")+". Aun no se como llamarlo."

    def focus_guide(self,index=None):
        if not self.guides:
            return "No hay robots maestros presentes. Continuo aprendiendo por exploracion."
        if index is not None:
            self.focus=int(index)%len(self.guides)
        guide=self.guides[self.focus]
        return ("Observo a "+guide.name+" ("+guide.task+"). "+guide.message+
                " Espero descubrir las consecuencias de sus movimientos.")

    def autonomous_trial(self):
        """Explorar, observar e intentar imitar habilidades con experiencia.

        El bebe no recibe el programa de los guias. Usa el progreso aprendido
        de observaciones y ensayos para decidir qué tipo de accion probar.
        """
        baby=self.baby
        self.auto_ticks=getattr(self,"auto_ticks",0)+1
        if baby.stumble>0:
            baby.last_decision="Debo recuperar el equilibrio antes de repetir."
            return "Me estabilizo antes de volver a intentarlo."
        if baby.posture=="lying":
            self.auto_rest_ticks=getattr(self,"auto_rest_ticks",0)+1
            if self.auto_rest_ticks>=3:
                self.auto_rest_ticks=0
                baby.posture="standing"
                return "He observado cómo incorporarme. Vuelvo a estar de pie."
            return "Pruebo a mantener mi cuerpo apoyado."
        self.auto_rest_ticks=0

        if self.confidence["caminar"]<.20:
            baby.last_decision="Observo pasos antes de intentar desplazamientos."
            return "Primero observo a ANDA para explorar mis movimientos."

        # Una vez que sostuvo algo, prueba a moverlo y luego soltarlo.
        if baby.holding:
            self.auto_hold_ticks=getattr(self,"auto_hold_ticks",0)+1
            if self.auto_hold_ticks>=3:
                self.auto_hold_ticks=0
                return self.try_release()
            return baby.explore()
        self.auto_hold_ticks=0

        nearby=any(
            not obj.held_by and self.distance(baby.x,baby.z,obj.x,obj.z)<1.75
            for obj in self.items.values()
        )
        if self.confidence["agarrar"]>=.22 and nearby and self.auto_ticks%3==0:
            return self.try_grab()

        if (self.confidence["descansar"]>=.35
                and self.distance(baby.x,baby.z,4.5,7)<2.6
                and self.auto_ticks%9==0):
            return self.try_rest()

        if self.confidence["reconocer"]>=.26 and nearby and self.auto_ticks%11==0:
            return self.identify()

        return baby.explore()

    def report(self):
        parts=["%s %d%%"%(k.upper(),round(v*100))
               for k,v in self.confidence.items()]
        return ("Observo "+str(self.observations)+" acciones. "+", ".join(parts)+
                ". Ensayos "+str(self.attempts)+", caidas "+str(self.falls)+
                ", objetos caidos "+str(self.drops)+".")

    def all_guide_status(self):
        return [(g.name,g.task,g.action,g.message) for g in self.guides]



class LearningBrain:
    """Cerebro experimental autonomo: memoria de episodios y preguntas propias.

    Nace sin vocabulario, relaciones, preguntas ni ejemplos numericos.
    La programacion implementa mecanismos de aprendizaje y sensores basicos;
    no implementa inteligencia general ni comprension irrestricta del lenguaje.
    """
    def __init__(self, robot, path):
        self.robot = robot
        self.path = Path(path)
        self.concepts = {}
        self.relations = {}
        self.episodes = deque(maxlen=180)
        self.questions = []
        self.number_patterns = {}
        self.action_models = {}
        self.tick_count = 0
        self.current_goal = "Explorar lo desconocido"
        self.last_thought = "Todavia no tengo experiencias."
        self.last_question = ""
        self.last_action = ""
        self.object_shapes = set()
        self.text_samples = 0
        self._rng = random.Random(707)
        self._load()

    def _load(self):
        try:
            data=json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data,dict): return
            self.concepts={str(k):v for k,v in data.get("concepts",{}).items()
                           if isinstance(v,dict)}
            self.relations={str(k):str(v) for k,v in data.get("relations",{}).items()}
            self.episodes=deque((e for e in data.get("episodes",[])
                                if isinstance(e,dict)),maxlen=180)
            self.questions=[q for q in data.get("questions",[])
                            if isinstance(q,dict) and "text" in q][-45:]
            self.number_patterns={str(k):int(v) for k,v in
                                  data.get("number_patterns",{}).items()}
            self.action_models={str(k):v for k,v in data.get("action_models",{}).items()
                                if isinstance(v,dict)}
            self.tick_count=max(0,int(data.get("ticks",0)))
            self.object_shapes=set(str(x) for x in data.get("object_shapes",[]))
            self.text_samples=max(0,int(data.get("text_samples",0)))
        except (OSError,ValueError,TypeError,AttributeError,OverflowError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_name(self.path.name+".tmp")
        tmp.write_text(json.dumps({
            "version":1, "concepts":self.concepts,
            "relations":self.relations,
            "episodes":list(self.episodes),
            "questions":self.questions[-45:],
            "number_patterns":self.number_patterns,
            "action_models":self.action_models,
            "ticks":self.tick_count,
            "object_shapes":sorted(self.object_shapes),
            "text_samples":self.text_samples
        },ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(self.path)

    def episode(self, source, observation, outcome=""):
        self.episodes.append({
            "n":self.tick_count,
            "source":str(source)[:35],
            "observation":str(observation)[:200],
            "outcome":str(outcome)[:160],
        })

    def ask(self,topic,text):
        topic=normalize(topic)[:68]
        text=str(text).strip()[:175]
        if not topic or not text:
            return ""
        for q in self.questions:
            if q.get("topic")==topic and q.get("text")==text:
                return q["text"]
        self.questions.append({"topic":topic,"text":text,"answer":""})
        self.questions=self.questions[-45:]
        self.last_question=text
        self.episode("pregunta",text)
        self.save()
        return text

    def pending_question(self):
        for q in reversed(self.questions):
            if not q.get("answer"):
                return q["text"]
        return ""

    def answer(self, response):
        response=str(response).strip()
        if not response or len(response)>400:
            return "Necesito una respuesta de 1 a 400 caracteres."
        for q in reversed(self.questions):
            if not q.get("answer"):
                q["answer"]=response
                self.relations["respuesta:"+q["topic"]]=response
                self.learn_text(response,"explicacion",persist=False)
                self.episode("respuesta",q["text"],response)
                self.save()
                return "Guarde tu explicacion y la relacionare con mis experiencias."
        return "No tengo preguntas pendientes por ahora."

    def learn_text(self, message, source="texto", persist=True):
        """Aprender frecuencias y asociaciones a partir de texto arbitrario.

        No se asume que leer caracteres sea comprender sus significados.
        """
        message=str(message).strip()[:600]
        if not message: return "No observe texto."
        words=re.findall(r"[a-z0-9ñ]+",normalize(message))
        if not words: return "No encuentro simbolos legibles."
        self.text_samples+=1
        unique=set(words)
        for word in words:
            if len(word)>54: continue
            if word not in self.concepts and len(self.concepts)>=300:
                continue
            datum=self.concepts.setdefault(word,{"n":0,"neighbors":{}})
            datum["n"]=min(100000,int(datum.get("n",0))+1)
            neighbors=datum.setdefault("neighbors",{})
            for other in unique:
                if other!=word and len(other)>1 and len(other)<55:
                    if other not in neighbors and len(neighbors)>=10:continue
                    neighbors[other]=min(10000,int(neighbors.get(other,0))+1)
        self.episode(source,message)
        if persist:self.save()
        return "Observe "+str(len(words))+" palabras y "+str(len(unique))+" formas diferentes."

    def observe_guide(self, event, training):
        """Solo escucha lo pronunciado y registra eventos observables.

        El programa interno del guia no se traspasa al cerebro del bebe.
        """
        utterance=str(event.get("message",""))[:300]
        signal=str(event.get("action",""))[:40]
        self.learn_text(utterance,"voz:"+str(event.get("teacher","")),persist=False)
        sensed=self.sense(training)
        self.episode("observacion",signal,
                     "formas:"+str(sensed["shapes"])+" / sonido:"+utterance)
        if signal in ("grasp","release","carry","lie","walk"):
            self.ask("causa:"+signal,
                     "¿Por que cambio el movimiento al ver "+signal+"?")
        # Las etiquetas solo se enlazan cuando la exposicion repetida
        # produjo una asociacion en la percepcion del bebe.
        for known in training.known_names:
            if known in normalize(utterance):
                item=training.items.get(known)
                if item is not None:
                    self.relations["palabra:"+known]="forma:"+item.shape
        self.save()

    def sense(self, training):
        """Observacion perceptual sin entregar nombre/identidad secreta."""
        shapes={}
        close=[]
        for obj in training.items.values():
            if training.distance(self.robot.x,self.robot.z,obj.x,obj.z)>6.4:
                continue
            shapes[obj.shape]=shapes.get(obj.shape,0)+1
            if training.distance(self.robot.x,self.robot.z,obj.x,obj.z)<1.75:
                close.append(obj.shape)
        return {
            "shapes":shapes,
            "nearby":close,
            "front_cm":self.robot.front_distance(),
            "touch":bool(self.robot.holding),
            "posture":self.robot.posture,
        }

    def compare_quantities(self, training):
        """Registrar evidencia de cardinalidad al observar dos grupos."""
        perception=self.sense(training)
        shapes=perception["shapes"]
        total=sum(shapes.values())
        if not total:
            return "Aun no veo objetos para comparar."
        counts=sorted(shapes.values(),reverse=True)
        if len(counts)>=2:
            a,b=counts[0],sum(counts[1:])
            relation=str(a)+"+"+str(b)+"="+str(total)
            self.number_patterns[relation]=min(10000,self.number_patterns.get(relation,0)+1)
            self.episode("cantidades","grupos "+str(counts),"total "+str(total))
            self.save()
            return ("Comparo "+str(a)+" y "+str(b)+" objetos. Juntos cuento "
                    +str(total)+".")
        self.episode("cantidades","grupo "+str(counts[0]))
        self.save()
        return "Detecto un grupo con "+str(total)+" objetos."

    def study_new_shapes(self,training):
        perception=self.sense(training)
        shapes=perception["shapes"]
        unfamiliar=[shape for shape in shapes if shape not in self.object_shapes]
        for shape in unfamiliar:
            self.object_shapes.add(shape)
            self.ask("forma:"+shape,
                     "¿Que propiedades tiene esta forma "+shape+"?")
        return bool(unfamiliar)

    def record_trial(self,action,before,after,experience):
        datum=self.action_models.setdefault(action,{"n":0,"changes":0,"effects":{}})
        datum["n"]=min(100000,int(datum.get("n",0))+1)
        changed=bool(before!=after)
        if changed:datum["changes"]=min(100000,int(datum.get("changes",0))+1)
        effect=("cambio" if changed else "sin_cambio")
        effects=datum.setdefault("effects",{})
        effects[effect]=min(100000,int(effects.get(effect,0))+1)
        self.episode("ensayo:"+action,experience,effect)
        if datum["n"]==2 and not changed:
            self.ask("error:"+action,
                     "¿Por que la accion "+action+" no produjo el cambio esperado?")
        self.save()

    def _candidate_scores(self, training, sensed):
        """Curiosidad: explorar acciones nuevas, variedad y posibilidad de probar."""
        robot=self.robot
        options=["observar","caminar","contar"]
        if sensed["nearby"]:
            options.extend(["agarrar","reconocer"])
        if robot.holding:
            options=["transportar","soltar","observar"]
        if training.distance(robot.x,robot.z,4.5,7)<2.6:
            options.append("acostarse")
        if robot.stumble>0:
            return ["observar"]
        if robot.posture=="lying":
            return ["incorporarse"]
        scored=[]
        for name in options:
            n=self.action_models.get(name,{}).get("n",0)
            surprise=1.2/(1.0+n*.23)
            if name=="observar":
                surprise+= .4 if sum(training.confidence.values())<.6 else .1
            if name=="agarrar" and training.confidence["agarrar"]<.4:
                surprise+=.42
            if name=="caminar" and training.confidence["caminar"]<.3:
                surprise+=.25
            if name=="contar" and not self.number_patterns:
                surprise+=.3
            scored.append((surprise+self._rng.random()*.16,name))
        scored.sort(reverse=True)
        return [name for _,name in scored]

    def autonomous_step(self):
        """Ciclo espontaneo de curiosidad; no depende del usuario ni de Arduino."""
        training=self.robot.training
        self.tick_count+=1
        sensed=self.sense(training)
        new=self.study_new_shapes(training)
        if new:
            self.current_goal="Investigar formas desconocidas"
        if self.tick_count%6==0:
            unknown=self.pending_question()
            if unknown:
                self.last_thought="Me pregunto: "+unknown
                self.last_action="preguntar"
                self.episode("curiosidad",self.last_thought)
                self.save()
                return self.last_thought
        if self.robot.battery<12.0:
            # La recarga es una convencion del simulador, NO un acto fisico.
            self.robot.battery=min(100.0,self.robot.battery+14.0)
            self.last_thought="Necesito energia. Recargo la bateria VIRTUAL."
            self.last_action="descansar"
            self.save()
            return self.last_thought
        choice=self._candidate_scores(training,sensed)[0]
        before=(self.robot.x,self.robot.z,self.robot.holding,self.robot.posture,
                tuple((shape,n) for shape,n in sorted(sensed["shapes"].items())))
        self.current_goal={
            "observar":"Comprender a los robots guia",
            "caminar":"Experimentar con mi cuerpo",
            "agarrar":"Investigar el contacto",
            "transportar":"Investigar objetos sujetos",
            "soltar":"Probar la gravedad",
            "contar":"Comparar cantidades",
            "reconocer":"Relacionar palabras y formas",
            "acostarse":"Probar nuevas posturas",
            "incorporarse":"Recuperar la postura",
        }.get(choice,"Explorar")
        if choice=="observar":
            result=training.focus_guide()
            if training.guides:
                training.focus=(training.focus+1)%len(training.guides)
        elif choice=="caminar":
            result=self.robot.explore()
        elif choice=="agarrar":
            result=training.try_grab()
        elif choice=="transportar":
            result=self.robot.explore()
        elif choice=="soltar":
            result=training.try_release()
        elif choice=="contar":
            result=self.compare_quantities(training)
        elif choice=="reconocer":
            result=training.identify()
        elif choice=="acostarse":
            result=training.try_rest()
        elif choice=="incorporarse":
            result=self.robot.command("levantarse")
        else:
            result=training.focus_guide()
        after_sensed=self.sense(training)
        after=(self.robot.x,self.robot.z,self.robot.holding,self.robot.posture,
               tuple((shape,n) for shape,n in sorted(after_sensed["shapes"].items())))
        self.record_trial(choice,before,after,result)
        self.last_action=choice
        self.last_thought=result
        self.robot.last_decision=("META: "+self.current_goal)[:100]
        return result

    def summary(self):
        learned=len(self.concepts)
        answered=sum(bool(q.get("answer")) for q in self.questions)
        return (f"Cerebro: {learned} simbolos observados, "
                f"{len(self.episodes)} experiencias recientes, "
                f"{len(self.number_patterns)} patrones numericos, "
                f"{len(self.questions)} preguntas propias ({answered} respondidas). "
                f"Meta: {self.current_goal}.")


class ArduinoBridge:
    """Puente USB optativo con bloqueo fisico y telemetria comprobable.

    Nunca enciende motores al iniciar AMBOT. Exige conexion, telemetria
    reciente de sensores reales y orden EXPLICITA de habilitacion fisica.
    """
    def __init__(self):
        self.serial = None
        self.port = ""
        self.armed = False
        self.ready = False
        self.last_rx = 0.0
        self.telemetry = {}
        self.last_error = ""
        self.sent_commands = 0

    @property
    def connected(self):
        return self.serial is not None and bool(getattr(self.serial,"is_open",True))

    def available_ports(self):
        try:
            from serial.tools import list_ports
        except ImportError:
            return "pyserial no instalado. Conecta Arduino cuando lo tengas."
        return ", ".join(p.device for p in list_ports.comports()) or "No se detectaron puertos serie."

    def _ensure_driver(self):
        try:
            import serial
            return serial
        except ImportError:
            if str(DEPENDENCIES) not in sys.path:
                sys.path.insert(0,str(DEPENDENCIES))
            try:
                import serial
                return serial
            except ImportError:
                pass
        DEPENDENCIES.mkdir(parents=True,exist_ok=True)
        flags=getattr(subprocess,"CREATE_NO_WINDOW",0)
        result=subprocess.run([
            sys.executable,"-m","pip","install","--disable-pip-version-check",
            "--no-input","--only-binary=:all:","--target",str(DEPENDENCIES),
            "pyserial>=3.5,<4",
        ],capture_output=True,text=True,timeout=90,creationflags=flags)
        if result.returncode:
            raise RuntimeError("No pude instalar pyserial: "+result.stdout[-400:])
        import importlib
        importlib.invalidate_caches()
        return importlib.import_module("serial")

    def connect(self, port):
        port=str(port).strip()
        if not port or len(port)>90 or any(x in port for x in ("\n","\r","\0")):
            return "Indica un puerto serie valido, por ejemplo COM4."
        if self.connected:self.close()
        self.armed=False
        self.ready=False
        self.telemetry={}
        try:
            serial=self._ensure_driver()
            self.serial=serial.Serial(port,baudrate=115200,
                                      timeout=0,write_timeout=.2)
            self.port=port
            self.last_rx=0.0
            self._write("STOP\n")
            self._write("PING\n")
            return "Arduino conectado en "+port+". Motores BLOQUEADOS."
        except (Exception,) as exc:
            self.serial=None
            self.port=""
            self.last_error=str(exc)[:160]
            return "No pude conectar Arduino: "+self.last_error

    def _write(self, line):
        if not self.connected:
            return False
        try:
            self.serial.write(line.encode("ascii"))
            return True
        except (OSError,ValueError,Exception) as exc:
            self.last_error=str(exc)[:160]
            self.armed=False
            return False

    def stop(self):
        self.armed=False
        self._write("STOP\n")
        return "PARADA DE SEGURIDAD: motores fisicos bloqueados."

    def close(self):
        self.stop()
        if self.serial:
            try:self.serial.close()
            except Exception:pass
        self.serial=None
        self.ready=False
        self.telemetry={}
        self.port=""

    def poll(self):
        if not self.connected: return
        try:
            for _ in range(4):
                if getattr(self.serial,"in_waiting",0)<=0:break
                line=self.serial.readline()[:350].decode("utf-8","replace").strip()
                if not line or len(line)>300:continue
                try:payload=json.loads(line)
                except (ValueError,TypeError):continue
                if not isinstance(payload,dict):continue
                self.ready=payload.get("ready") is True
                clean={}
                for name in ("distance_cm","battery_pct","touch"):
                    value=payload.get(name)
                    if type(value) in (int,float,bool) and math.isfinite(float(value)):
                        clean[name]=value
                self.telemetry=clean
                self.last_rx=time.monotonic()
            if self.armed and not self.sensors_safe():
                self.stop()
        except (Exception,) as exc:
            self.last_error=str(exc)[:160]
            self.stop()
            self.close()

    def sensors_safe(self):
        if not self.connected or not self.ready:
            return False
        if time.monotonic()-self.last_rx>.8:
            return False
        distance=self.telemetry.get("distance_cm",-1)
        battery=self.telemetry.get("battery_pct",-1)
        return (type(distance) in (int,float) and 25<=distance<=1000 and
                type(battery) in (int,float) and 20<=battery<=100)

    def arm(self):
        self.poll()
        if not self.sensors_safe():
            self.armed=False
            return ("Motor fisico NO habilitado: necesito telemetria REAL "
                    "de distancia y bateria y conexion reciente.")
        self.armed=True
        return "Control fisico habilitado temporalmente, con limite de velocidad y parada."

    def send_motion(self, direction, power=25, duration_ms=100):
        if not self.armed or not self.sensors_safe():
            self.stop()
            return False
        if direction not in ("FORWARD","BACK","LEFT","RIGHT"):
            return False
        power=max(0,min(35,int(power)))
        duration_ms=max(20,min(120,int(duration_ms)))
        if self._write("MOVE "+direction+" "+str(power)+" "+str(duration_ms)+"\n"):
            self.sent_commands+=1
            return True
        return False

    def status(self):
        if not self.connected:return "Arduino: desconectado; simulacion autonoma activa."
        state="HABILITADO" if self.armed else "BLOQUEADO"
        return ("Arduino "+self.port+" / motores "+state+
                " / sensores "+str(self.telemetry))


# Catalogo editable: por ahora SOLO sillas, sin otros tipos de muebles.
CHAIR_STYLES = {
    "clasica": "SILLA CLASICA",
    "oficina": "SILLA DE OFICINA",
    "alta": "SILLA ALTA",
}
ADD_CATALOG = {
    "silla_clasica":"SILLA CLASICA",
    "silla_oficina":"SILLA DE OFICINA",
    "silla_alta":"SILLA ALTA",
    "cama":"CAMA",
    "mesa":"MESA",
    "armario":"ARMARIO",
    "cubo":"CUBO",
    "pelota":"PELOTA",
    "bloque":"BLOQUE",
}
MOVABLE_COLORS = {
    "cubo":(252,119,143),
    "pelota":(89,176,254),
    "bloque":(244,198,117),
}


class FurnitureEditor:
    """Muebles y objetos editables, con eliminacion reversible y persistente."""
    MAX_CHAIRS = 30

    def __init__(self, robot, path):
        self.robot = robot
        self.path = Path(path)
        self.chairs = []
        self.removed_fixed = set()
        self.removed_movables = set()
        self.removed_guides = set()
        self.extra_fixtures = []
        self.extra_objects = {}
        self.next_id = 1
        self.history = []
        if self.path.exists():
            self._load()
        else:
            # Tres sillas nuevas, ademas de la silla fija de la mesa.
            for style,x,z,orientation in (
                ("clasica",5,3,2),("oficina",7,7,0),("alta",5,5,1)
            ):
                valid,_=self.can_place(x,z)
                if valid:
                    self.chairs.append({
                        "style":style,"x":x,"z":z,"orientation":orientation
                    })
            self.save()

    @staticmethod
    def occupied_cells(kind,x,z,orientation=0):
        if kind=="cama":
            return ((x,z),(x+1,z)) if orientation%2==0 else ((x,z),(x,z+1))
        return ((x,z),)

    def fixture_blocks(self,x,z):
        return (any(name not in self.removed_fixed and (x,z) in cells
                    for name,cells in ROOM_OBJECTS.items())
                or any((x,z) in self.occupied_cells(
                    item["kind"],item["x"],item["z"],item["orientation"])
                    for item in self.extra_fixtures))

    def _open_floor(self,x,z,occupied):
        return (0<=z<len(WORLD) and 0<=x<len(WORLD[z])
                and WORLD[z][x]=="." and not self.fixture_blocks(x,z)
                and (x,z) not in occupied)

    def _route_exists(self,occupied,origin=(6,5),target=ROOM_DOOR):
        if not self._open_floor(*origin,occupied):
            return False
        if not self._open_floor(*target,occupied):
            return False
        seen={origin}
        pending=deque([origin])
        while pending:
            x,z=pending.popleft()
            if (x,z)==target:return True
            for dx,dz in DIRECTIONS:
                cell=x+dx,z+dz
                if cell not in seen and self._open_floor(*cell,occupied):
                    seen.add(cell)
                    pending.append(cell)
        return False

    def occupied(self):
        return {(chair["x"],chair["z"]) for chair in self.chairs}

    def blocks(self,x,z):
        return (x,z) in self.occupied()

    def can_place(self,x,z):
        if type(x) is not int or type(z) is not int:
            return False,"Selecciona una casilla del suelo."
        if len(self.chairs)>=self.MAX_CHAIRS:
            return False,"Maximo de 30 sillas adicionales."
        used=self.occupied()
        if not self._open_floor(x,z,used):
            return False,"No se puede colocar en una pared, mueble u otra silla."
        if (x,z) in ((6,5),ROOM_DOOR,(self.robot.x,self.robot.z)):
            return False,"Reserva la entrada y el espacio de AMBOT."
        if (hasattr(self.robot,"human") and not self.robot.human.seated
                and (self.robot.human.x,self.robot.human.z)==(x,z)):
            return False,"Tu personaje ocupa esa casilla."
        if hasattr(self.robot,"training"):
            tr=self.robot.training
            if any(tr.distance(x,z,item.x,item.z)<.69
                   for item in tr.items.values() if not item.held_by):
                return False,"Hay un objeto movil en esa casilla."
            if any(tr.distance(x,z,guide.x,guide.z)<.75
                   for guide in tr.guides):
                return False,"Un robot guia ocupa ese lugar."
        blocked=used|{(x,z)}
        if not self._route_exists(blocked):
            return False,"Esta silla bloquearia la salida de la habitacion."
        if not self._route_exists(blocked,(self.robot.x,self.robot.z)):
            return False,"AMBOT quedaria encerrado."
        return True,"Lugar disponible."

    def place(self,style,x,z,orientation=2):
        if style not in CHAIR_STYLES:
            return False,"Tipo no disponible: por ahora solo hay sillas."
        valid,msg=self.can_place(x,z)
        if not valid:return False,msg
        if type(orientation) is not int or orientation not in range(4):
            return False,"Direccion de la silla no valida."
        chair={"style":style,"x":x,"z":z,"orientation":orientation}
        self.chairs.append(chair)
        self._push_history({"kind":"place_chair","chair":dict(chair)})
        self.save()
        return True,CHAIR_STYLES[style]+" colocada en X="+str(x)+" Z="+str(z)+"."

    def next_extra_name(self,base):
        while True:
            name=base+"_"+str(self.next_id)
            self.next_id+=1
            if (name not in self.robot.training.items
                    and not any(p["id"]==name for p in self.extra_fixtures)):
                return name

    def can_place_object(self,kind,x,z,orientation=2):
        if kind in ("silla_clasica","silla_oficina","silla_alta"):
            return self.can_place(x,z)
        if kind not in ADD_CATALOG:
            return False,"Solo se puede anadir un objeto del catalogo."
        if type(x) is not int or type(z) is not int:
            return False,"Selecciona una casilla del suelo."
        if type(orientation) is not int or orientation not in range(4):
            return False,"Orientacion invalida."
        if len(self.extra_fixtures)+len(self.extra_objects)>=70:
            return False,"Maximo de 70 objetos adicionales."
        cells=self.occupied_cells(kind,x,z,orientation)
        if kind in ("cama","mesa","armario"):
            if len(self.extra_fixtures)>=25:
                return False,"Maximo de 25 muebles adicionales."
        for cx,cz in cells:
            if not self._open_floor(cx,cz,self.occupied()):
                return False,"El sitio esta ocupado o fuera del suelo disponible."
            if (cx,cz) in ((self.robot.x,self.robot.z),(6,5),ROOM_DOOR):
                return False,"Reserva la salida y el espacio del robot."
            if any(math.hypot(g.x-cx,g.z-cz)<.7
                   for g in self.robot.training.guides):
                return False,"Un maestro esta en ese sitio."
            if any(math.hypot(o.x-cx,o.z-cz)<.65
                   for o in self.robot.training.items.values()):
                return False,"Ya hay un objeto en ese lugar."
            if (hasattr(self.robot,"human") and not self.robot.human.seated
                    and (self.robot.human.x,self.robot.human.z)==(cx,cz)):
                return False,"Tu personaje ocupa esa casilla."
        if kind in ("cama","mesa","armario"):
            occupied=self.occupied()|set(cells)
            if not self._route_exists(occupied):
                return False,"El mueble bloquearia la salida."
            if not self._route_exists(occupied,(self.robot.x,self.robot.z)):
                return False,"AMBOT quedaria encerrado."
        return True,"Posicion disponible."

    def place_object(self,kind,x,z,orientation=2):
        if kind in ("silla_clasica","silla_oficina","silla_alta"):
            return self.place(kind.split("_",1)[1],x,z,orientation)
        allowed,why=self.can_place_object(kind,x,z,orientation)
        if not allowed:return False,why
        identifier=self.next_extra_name(kind)
        if kind in ("cama","mesa","armario"):
            item={"id":identifier,"kind":kind,
                  "x":x,"z":z,"orientation":orientation}
            self.extra_fixtures.append(item)
            self._push_history({"kind":"create_fixture","id":identifier})
        else:
            shape="ball" if kind=="pelota" else "box"
            radius=.24 if kind=="pelota" else .22
            obj=Movable(identifier,float(x),float(z),shape,
                        MOVABLE_COLORS[kind],radius=radius,y=radius*TILE)
            self.robot.training.items[identifier]=obj
            self.extra_objects[identifier]=asdict(obj)
            self._push_history({"kind":"create_movable","id":identifier})
        self.save()
        return True,ADD_CATALOG[kind]+" colocado en X="+str(x)+" Z="+str(z)+"."

    def _push_history(self, action):
        self.history.append(action)
        self.history=self.history[-24:]

    def remove(self, kind, key):
        """Quitar un elemento existente, sin permitir borrar robots/estructura."""
        if kind=="chair":
            if (hasattr(self.robot,"human") and self.robot.human.seated
                    and self.robot.human.seat==key):
                return False,"Levantate antes de quitar la silla ocupada."
            for index,chair in enumerate(self.chairs):
                if (chair["x"],chair["z"])==key:
                    gone=self.chairs.pop(index)
                    self._push_history({
                        "kind":"remove_chair","index":index,"chair":dict(gone)
                    })
                    self.save()
                    return True,"Silla eliminada en X="+str(gone["x"])+" Z="+str(gone["z"])+"."
            return False,"No hay una silla en ese lugar."
        if kind=="fixture_added":
            item=next((f for f in self.extra_fixtures if f["id"]==key),None)
            if item is None:return False,"Ese mueble no existe."
            index=self.extra_fixtures.index(item)
            self.extra_fixtures.remove(item)
            self._push_history({
                "kind":"remove_fixture_added","item":dict(item),"index":index
            })
            self.save()
            return True,"Mueble retirado: "+item["kind"]+"."
        if kind=="fixture":
            if (key=="silla" and hasattr(self.robot,"human")
                    and self.robot.human.seated
                    and self.robot.human.seat==(4,5)):
                return False,"Levantate antes de quitar la silla ocupada."
            if key not in tuple(ROOM_OBJECTS)+("ventana","alfombra"):
                return False,"Solo puedes quitar objetos del entorno."
            if key in self.removed_fixed:
                return False,"Ese objeto ya se quito."
            self.removed_fixed.add(key)
            if key=="cama" and self.robot.posture=="lying":
                self.robot.posture="standing"
            self._push_history({"kind":"remove_fixture","name":key})
            self.save()
            return True,"Objeto eliminado: "+str(key)+"."
        if kind=="guide":
            if key not in self.robot.training.all_guide_specs:
                return False,"Ese robot maestro no existe."
            guide=next((g for g in self.robot.training.guides
                        if g.name==key),None)
            if guide is None:
                return False,"Ese robot maestro ya no esta."
            self.robot.training.release_owner(key)
            self.robot.training.guides.remove(guide)
            self.robot.training.focus=(self.robot.training.focus %
                                       max(1,len(self.robot.training.guides)))
            self.removed_guides.add(key)
            self._push_history({"kind":"remove_guide","name":key})
            self.save()
            return True,"Maestro retirado: "+key+". AMBOT conserva lo aprendido."
        if kind=="movable":
            if key not in self.robot.training.items:
                return False,"Ese objeto no se puede quitar."
            item=self.robot.training.items.pop(key,None)
            if item is None:
                return False,"Ese objeto ya se quito."
            if item.held_by=="AMBOT":
                self.robot.holding=None
                self.robot.reach=0.0
            for guide in self.robot.training.guides:
                if guide.holding==key:guide.holding=None
            snapshot=asdict(item)
            snapshot["held_by"]=""
            extra=key in self.extra_objects
            if extra:
                self.extra_objects.pop(key,None)
            else:
                self.removed_movables.add(key)
            self._push_history({
                "kind":"remove_movable","item":snapshot,"extra":extra
            })
            self.save()
            return True,"Objeto eliminado: "+str(key)+"."
        return False,"Solo se pueden quitar objetos, no paredes ni robots."

    def undo(self):
        """Deshacer la ultima modificacion; sigue disponible tras reiniciar."""
        if not self.history:
            return False,"No hay modificaciones por deshacer."
        action=self.history[-1]
        kind=action.get("kind")
        if kind=="place_chair":
            chair=action["chair"]
            for idx,c in enumerate(self.chairs):
                if (c["x"],c["z"])==(chair["x"],chair["z"]):
                    self.chairs.pop(idx)
                    self.history.pop()
                    self.save()
                    return True,"Quite la silla agregada: deshice su colocacion."
            return False,"La silla ya no esta en esa posicion."
        if kind=="remove_chair":
            chair=action["chair"]
            allowed,reason=self.can_place(chair["x"],chair["z"])
            if not allowed:return False,"No puedo restaurar la silla: "+reason
            index=max(0,min(len(self.chairs),int(action.get("index",len(self.chairs)))))
            self.chairs.insert(index,dict(chair))
            self.history.pop()
            self.save()
            return True,"Silla restaurada."
        if kind=="remove_fixture":
            name=action.get("name")
            if name not in self.removed_fixed:
                return False,"Ese mueble ya esta presente."
            cells=ROOM_OBJECTS.get(name,())
            if any((x,z)==(self.robot.x,self.robot.z) or (x,z) in self.occupied()
                   for x,z in cells):
                return False,"Libera el lugar para restaurar el mueble."
            self.removed_fixed.discard(name)
            self.history.pop()
            self.save()
            return True,"Restaure: "+str(name)+"."
        if kind=="create_fixture":
            identifier=action.get("id")
            item=next((f for f in self.extra_fixtures if f["id"]==identifier),None)
            if item is None:return False,"El mueble ya no esta."
            self.extra_fixtures.remove(item)
            self.history.pop()
            self.save()
            return True,"Deshice la adicion del mueble."
        if kind=="remove_fixture_added":
            item=dict(action["item"])
            ok,why=self.can_place_object(
                item["kind"],item["x"],item["z"],item["orientation"])
            if not ok:return False,"No se puede restaurar: "+why
            idx=max(0,min(len(self.extra_fixtures),int(action.get("index",0))))
            self.extra_fixtures.insert(idx,item)
            self.history.pop()
            self.save()
            return True,"Mueble adicional restaurado."
        if kind=="create_movable":
            name=action.get("id")
            if name not in self.extra_objects:
                return False,"Ese objeto ya no esta."
            self.robot.training.items.pop(name,None)
            self.extra_objects.pop(name,None)
            self.history.pop()
            self.save()
            return True,"Deshice la adicion del objeto."
        if kind=="remove_guide":
            name=action.get("name")
            if name not in self.removed_guides:
                return False,"El maestro ya esta presente."
            if not self.robot.training.restore_guide(name):
                return False,"No pude restaurar al maestro."
            self.removed_guides.discard(name)
            self.history.pop()
            self.save()
            return True,"Maestro restaurado: "+name+"."
        if kind=="remove_movable":
            snapshot=action["item"]
            name=snapshot.get("name")
            if action.get("extra"):
                if name in self.extra_objects or name in self.robot.training.items:
                    return False,"El objeto adicional ya esta presente."
            elif name not in self.removed_movables:
                return False,"El objeto ya esta presente."
            x,z=float(snapshot.get("x",0)),float(snapshot.get("z",0))
            if (not self.robot.free(round(x),round(z))
                    or any(math.hypot(item.x-x,item.z-z)<.6
                           for item in self.robot.training.items.values())):
                return False,"Libera el espacio para restaurar el objeto."
            restored=dict(snapshot)
            restored["color"]=tuple(restored["color"])
            restored["held_by"]=""
            self.robot.training.items[name]=Movable(**restored)
            if action.get("extra"):
                self.extra_objects[name]=asdict(self.robot.training.items[name])
            else:
                self.removed_movables.discard(name)
            self.history.pop()
            self.save()
            return True,"Restaure: "+str(name)+"."
        return False,"No reconozco esa modificacion."

    def _load(self):
        try:
            data=json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data,dict) or not isinstance(data.get("chairs"),list):
                return
            allowed=set(ROOM_OBJECTS)|{"ventana","alfombra"}
            self.removed_fixed=set(str(n) for n in data.get("removed_fixed",[])
                                   if str(n) in allowed)
            self.removed_movables=set(str(n) for n in data.get("removed_movables",[])
                                      if str(n) in ("cubo","pelota","bloque"))
            for n in self.removed_movables:
                self.robot.training.items.pop(n,None)
            self.removed_guides=set(str(n) for n in data.get("removed_guides",[])
                                    if str(n) in self.robot.training.all_guide_specs)
            self.robot.training.guides=[
                g for g in self.robot.training.guides
                if g.name not in self.removed_guides]
            self.robot.training.focus=(self.robot.training.focus %
                                       max(1,len(self.robot.training.guides)))
            try:self.next_id=max(1,int(data.get("next_id",1)))
            except (TypeError,ValueError):self.next_id=1
            entries=data.get("history",[])
            if isinstance(entries,list):
                self.history=[record for record in entries[-24:]
                              if isinstance(record,dict)
                              and record.get("kind") in (
                                  "place_chair","remove_chair","remove_fixture",
                                  "remove_movable","remove_guide",
                                  "create_fixture","remove_fixture_added",
                                  "create_movable")]
            for item in data["chairs"][:self.MAX_CHAIRS]:
                if not isinstance(item,dict):continue
                style,x,z,rot=(item.get("style"),item.get("x"),item.get("z"),
                               item.get("orientation",2))
                if style not in CHAIR_STYLES:continue
                if type(x) is not int or type(z) is not int:continue
                if type(rot) is not int or rot not in range(4):continue
                valid,_=self.can_place(x,z)
                if valid:
                    self.chairs.append({
                        "style":style,"x":x,"z":z,"orientation":rot
                    })
            for entry in data.get("extra_fixtures",[])[:25]:
                if not isinstance(entry,dict):continue
                name,kind=entry.get("id"),entry.get("kind")
                x,z,rot=entry.get("x"),entry.get("z"),entry.get("orientation",2)
                if not isinstance(name,str) or not re.fullmatch(r"(cama|mesa|armario)_\d+",name):
                    continue
                if kind not in ("cama","mesa","armario"):continue
                valid,_=self.can_place_object(kind,x,z,rot)
                if valid and not any(f["id"]==name for f in self.extra_fixtures):
                    self.extra_fixtures.append({
                        "id":name,"kind":kind,"x":x,"z":z,"orientation":rot
                    })
            data_objects=data.get("extra_objects",{})
            if isinstance(data_objects,dict):
                for name,state in list(data_objects.items())[:45]:
                    if (not isinstance(name,str) or not isinstance(state,dict)
                            or not re.fullmatch(r"(cubo|pelota|bloque)_\d+",name)):
                        continue
                    try:
                        kind=name.split("_",1)[0]
                        x,z=float(state["x"]),float(state["z"])
                        if not math.isfinite(x) or not math.isfinite(z):
                            continue
                        if not self._open_floor(round(x),round(z),self.occupied()):
                            continue
                        obj=Movable(name,x,z,"ball" if kind=="pelota" else "box",
                                    MOVABLE_COLORS[kind])
                        obj.radius=.24 if kind=="pelota" else .22
                        obj.y=obj.radius*TILE
                        self.robot.training.items[name]=obj
                        self.extra_objects[name]=asdict(obj)
                    except (KeyError,TypeError,ValueError):
                        continue
        except (OSError,ValueError,TypeError,AttributeError):
            pass

    def save(self):
        for key in list(self.extra_objects):
            item=self.robot.training.items.get(key)
            if item:
                snapshot=asdict(item)
                snapshot["held_by"]=""
                self.extra_objects[key]=snapshot
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_name(self.path.name+".tmp")
        tmp.write_text(json.dumps({
            "version":3,"chairs":self.chairs,
            "removed_fixed":sorted(self.removed_fixed),
            "removed_movables":sorted(self.removed_movables),
            "removed_guides":sorted(self.removed_guides),
            "extra_fixtures":self.extra_fixtures,
            "extra_objects":self.extra_objects,
            "next_id":self.next_id,
            "history":self.history[-24:]
        },ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(self.path)


VALIDATED_INTENTS={
    "sentarme":"Sentar a mi personaje",
    "levantarme":"Levantar a mi personaje",
    "saludar":"Hacer que mi personaje salude",
    "agacharme":"Agachar a mi personaje",
    "observar":"Pedir a AMBOT que observe",
    "contar":"Pedir a AMBOT comparar cantidades",
    "explorar":"Pedir a AMBOT que explore",
    "preguntas":"Ver las preguntas de AMBOT",
    "progreso":"Ver que ha aprendido AMBOT",
    "dato":"Guardar como dato aportado por ti",
    "pregunta":"Guardar una pregunta para investigar",
}


class ValidatedLanguage:
    """Interpretacion inicial con aprendizaje supervisado por el usuario.

    Solo aprende frases confirmadas/corregidas; nunca ejecuta codigo arbitrario
    ni convierte una conjetura sobre un texto en conocimiento validado.
    """
    def __init__(self,robot,path):
        self.robot=robot
        self.path=Path(path)
        self.confirmed={}
        self.pending=None
        self.wait_correction=False
        self._load()

    def _load(self):
        try:
            data=json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data,dict):return
            examples=data.get("confirmed",{})
            if not isinstance(examples,dict):return
            for phrase,item in list(examples.items())[:800]:
                if (isinstance(phrase,str) and isinstance(item,dict)
                        and item.get("intent") in VALIDATED_INTENTS):
                    self.confirmed[phrase]={"intent":item["intent"],
                                            "text":str(item.get("text",phrase))[:300]}
        except (OSError,ValueError,TypeError,AttributeError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_name(self.path.name+".tmp")
        tmp.write_text(json.dumps({
            "version":1,"confirmed":self.confirmed
        },ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(self.path)

    def guess(self,phrase):
        words=set(re.findall(r"[a-z]+",normalize(phrase)))
        text=normalize(phrase)
        if any(token in text for token in ("sient","sentar","sentarme","sentado")):
            return "sentarme"
        if any(token in text for token in ("levant","ponme de pie","pararme")):
            return "levantarme"
        if "saluda" in text or "hola" in words:
            return "saludar"
        if any(token in text for token in ("agacha","inclina mi cuerpo")):
            return "agacharme"
        if any(token in text for token in ("cuanto","cuantos","cuenta","sumar")):
            return "contar"
        if "observa" in text or "mira" in words:
            return "observar"
        if any(token in text for token in ("explora","investiga","camina")):
            return "explorar"
        if "pregunta" in text:
            return "preguntas"
        if any(token in text for token in ("aprendiste","sabes","progreso")):
            return "progreso"
        if "?" in phrase or "¿" in phrase:
            return "pregunta"
        return "dato"

    def propose(self,phrase):
        phrase=str(phrase).strip()[:300]
        key=normalize(phrase)
        if not key:return "Escribe lo que quieres comunicarme."
        if key in self.confirmed:
            entry=self.confirmed[key]
            return self.perform(entry["intent"],phrase,already=True)
        intent=self.guess(phrase)
        self.pending={"text":phrase,"key":key,"intent":intent}
        self.wait_correction=False
        return ("Creo que quieres: "+VALIDATED_INTENTS[intent]+
                ". ¿ENTENDI BIEN? Pulsa SI, NO o CORREGIR.")

    def perform(self,intent,phrase,already=False):
        if intent=="sentarme":
            return self.robot.human.sit()
        if intent=="levantarme":
            return self.robot.human.stand()
        if intent=="saludar":
            return self.robot.human.pose("saludar")
        if intent=="agacharme":
            return self.robot.human.pose("agacharse")
        if intent=="observar":
            return self.robot.command("observar")
        if intent=="contar":
            return self.robot.command("contar")
        if intent=="explorar":
            return self.robot.command("explora")
        if intent=="preguntas":
            return self.robot.command("pregunta")
        if intent=="progreso":
            return self.robot.command("cerebro")
        if intent=="pregunta":
            key="respuesta:usuario:"+normalize(phrase)[:60]
            stored=self.robot.brain.relations.get(key)
            if stored:
                return "Me explicaste: "+stored
            self.robot.brain.ask("usuario:"+normalize(phrase)[:60],phrase)
            return ("No conozco una respuesta comprobada todavia. "
                    "Puedes enseñarme escribiendo RESPONDE seguido de tu explicacion.")
        if intent=="dato":
            learned=self.robot.brain.learn_text(phrase,"texto_validado")
            self.robot.brain.relations["dato_validado:"+normalize(phrase)[:80]]=phrase
            self.robot.brain.save()
            return ("Lo he guardado como informacion VALIDADA POR TI, "
                    "no como un hecho verificado externamente. "+learned)
        return "No encontre una accion permitida."

    def confirm(self):
        if not self.pending:return "No tengo ninguna interpretacion pendiente."
        if self.wait_correction:
            return "Indica CORRIGE seguido de la accion correcta."
        record=self.pending
        self.pending=None
        if len(self.confirmed)>=800 and record["key"] not in self.confirmed:
            first=next(iter(self.confirmed))
            self.confirmed.pop(first,None)
        self.confirmed[record["key"]]={
            "intent":record["intent"],"text":record["text"]
        }
        self.save()
        self.robot.brain.episode("validacion_usuario",record["text"],
                                 record["intent"])
        self.robot.brain.save()
        return "Confirmado. Aprendi la frase. "+self.perform(
            record["intent"],record["text"])

    def reject(self):
        if not self.pending:return "No tengo ninguna interpretacion pendiente."
        self.wait_correction=True
        return ("No memorizare esa interpretacion. Escribe CORRIGE seguido de: "+
                ", ".join(VALIDATED_INTENTS)+".")

    def correct(self,meaning):
        if not self.pending:return "No hay una frase pendiente para corregir."
        intent=normalize(meaning).strip()
        aliases={"sentar":"sentarme","sentarse":"sentarme",
                 "levantar":"levantarme","levantarme":"levantarme",
                 "saludo":"saludar","dato nuevo":"dato",
                 "ensenar":"dato","enseñar":"dato","explicacion":"dato",
                 "preguntar":"pregunta","consultar":"pregunta",
                 "observar":"observar","cuenta":"contar"}
        intent=aliases.get(intent,intent)
        if intent not in VALIDATED_INTENTS:
            return "No reconozco esa accion. Opciones: "+", ".join(VALIDATED_INTENTS)+"."
        self.pending["intent"]=intent
        self.wait_correction=False
        return self.confirm()

# Tu personaje tiene control manual y es independiente del cerebro de AMBOT.
HUMAN_JOINTS={
    "cabeza":"CABEZA", "torso":"TORSO",
    "brazo_izq":"BRAZO IZQ.", "brazo_der":"BRAZO DER.",
    "codo_izq":"CODO IZQ.", "codo_der":"CODO DER.",
    "pierna_izq":"PIERNA IZQ.", "pierna_der":"PIERNA DER.",
    "rodilla_izq":"RODILLA IZQ.", "rodilla_der":"RODILLA DER.",
}


class HumanAvatar:
    """Avatar humanoide manual con articulaciones, locomocion y silla real."""
    def __init__(self, robot, path):
        self.robot=robot
        self.path=Path(path)
        self.x,self.z=10,5
        self.facing=3
        self.seated=False
        self.seat=None
        self.previous=(10,5)
        self.steps=0
        self.joints={name:0 for name in HUMAN_JOINTS}
        self._load()

    def _valid_floor(self,x,z):
        return (type(x) is int and type(z) is int and
                self.robot.free(x,z) and (x,z)!=(self.robot.x,self.robot.z)
                and all(math.hypot(g.x-x,g.z-z)>.75
                        for g in self.robot.training.guides)
                and all(math.hypot(o.x-x,o.z-z)>.55
                        for o in self.robot.training.items.values()))

    def _seats(self):
        f=self.robot.furniture
        chairs=[(c["x"],c["z"]) for c in f.chairs]
        if "silla" not in f.removed_fixed:
            chairs.append((4,5))
        return chairs

    def _notify(self,action):
        """Simular una observacion corporal del usuario desde AMBOT."""
        brain=self.robot.brain
        observation=("x="+str(self.x)+" z="+str(self.z)+
                     " sentado="+str(self.seated)+
                     " articulaciones="+str(self.joints))
        brain.episode("observacion_humano",action,observation)
        if action.startswith("mover"):
            self.robot.training.lesson("caminar",.013,"observacion_humano")
        if action=="sentarse":
            brain.ask("demostracion:sentarse",
                      "¿Como puedo flexionar mis piernas y sentarme como tu?")
        brain.save()

    def turn(self,direction):
        """Tank control: izquierda/derecha solo orientan el cuerpo."""
        if direction not in ("izquierda","derecha"):
            return "Giro no valido."
        if self.seated:
            return "Estas sentado. Levantate antes de girar el cuerpo."
        difference=-1 if direction=="izquierda" else 1
        self.facing=(self.facing+difference)%4
        self.save()
        self._notify("girar "+direction)
        return "Giraste a la "+direction+". Ahora miras al "+ORIENTATIONS[self.facing]+"."

    def advance(self,reverse=False):
        """Tank control: desplazamiento segun la orientacion, sin strafe.

        Retroceder conserva la direccion a la que esta mirando.
        """
        direction=(self.facing+2)%4 if reverse else self.facing
        return self.move(direction,keep_facing=True)

    def move(self,direction,keep_facing=False):
        if type(direction) is not int or direction not in range(4):
            return "Direccion no valida."
        if self.seated:
            return "Estas sentado. Primero pulsa LEVANTARSE."
        if not keep_facing:
            self.facing=direction
        dx,dz=DIRECTIONS[direction]
        if not self._valid_floor(self.x+dx,self.z+dz):
            return "No puedes atravesar muebles, paredes, objetos ni robots."
        self.x+=dx
        self.z+=dz
        self.steps+=1
        self.save()
        self._notify("mover "+("atras" if keep_facing and direction!=(self.facing) else "adelante"))
        return "Te moviste a X="+str(self.x)+" Z="+str(self.z)+"."

    def sit(self):
        if self.seated:
            return "Ya estas sentado."
        nearby=[pos for pos in self._seats()
                if math.hypot(pos[0]-self.x,pos[1]-self.z)<=1.55]
        if not nearby:
            return "Acercate a una silla antes de sentarte."
        self.seat=min(nearby,
                      key=lambda pos:math.hypot(pos[0]-self.x,pos[1]-self.z))
        self.previous=(self.x,self.z)
        self.x,self.z=self.seat
        self.seated=True
        self.save()
        self._notify("sentarse")
        return "Te sentaste en la silla. Usa LEVANTARSE para salir."

    def stand(self):
        if not self.seated:
            return "Ya estas de pie."
        candidates=[self.previous]+[
            (self.x+dx,self.z+dz) for dx,dz in DIRECTIONS]
        valid=next((p for p in candidates if self._valid_floor(*p)),None)
        if valid is None:
            return "No hay espacio libre para levantarte."
        self.x,self.z=valid
        self.seat=None
        self.seated=False
        self.save()
        self._notify("levantarse")
        return "Te levantaste de la silla."

    def change_joint(self,name,delta):
        if name not in self.joints:
            return "Esa articulacion no existe."
        self.joints[name]=max(-85,min(85,self.joints[name]+int(delta)))
        self.save()
        self._notify("articular "+name)
        return HUMAN_JOINTS[name]+": "+str(self.joints[name])+" grados."

    def pose(self,name):
        if name=="reposo":
            self.joints={name:0 for name in HUMAN_JOINTS}
        elif name=="saludar":
            self.joints["brazo_der"]=75
            self.joints["codo_der"]=35
            self.joints["cabeza"]=15
        elif name=="agacharse":
            if self.seated:
                return "Levantate antes de agacharte."
            self.joints["torso"]=35
            self.joints["rodilla_izq"]=40
            self.joints["rodilla_der"]=40
        else:
            return "Postura no reconocida."
        self.save()
        self._notify("postura "+name)
        return "Postura aplicada: "+name+"."

    def _load(self):
        try:
            data=json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data,dict):return
            joints=data.get("joints",{})
            if isinstance(joints,dict):
                for name in self.joints:
                    if type(joints.get(name)) in (int,float):
                        self.joints[name]=max(-85,min(85,int(joints[name])))
            x,z=data.get("x",10),data.get("z",5)
            face=data.get("facing",3)
            self.facing=face if type(face) is int and face in range(4) else 3
            seated=data.get("seated") is True
            seat=data.get("seat")
            old=data.get("previous",[10,5])
            if seated and isinstance(seat,list) and len(seat)==2:
                cell=(int(seat[0]),int(seat[1]))
                if cell in self._seats():
                    self.x,self.z=cell
                    self.seat=cell
                    self.seated=True
                    if (isinstance(old,list) and len(old)==2 and
                            self._valid_floor(int(old[0]),int(old[1]))):
                        self.previous=(int(old[0]),int(old[1]))
                    return
            if self._valid_floor(x,z):
                self.x,self.z=x,z
        except (OSError,ValueError,TypeError,OverflowError,AttributeError):
            pass

    def save(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        tmp=self.path.with_name(self.path.name+".tmp")
        tmp.write_text(json.dumps({
            "version":1,"x":self.x,"z":self.z,"facing":self.facing,
            "seated":self.seated,"seat":list(self.seat) if self.seat else None,
            "previous":list(self.previous),"joints":self.joints,
        },ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(self.path)


class Robot:
    """Cerebro con mapa, percepcion, navegacion, decisiones y memoria."""
    def __init__(self, memory_path=MEMORY_PATH):
        self.memory_path = Path(memory_path)
        self.facts = {}
        try:
            if self.memory_path.exists():
                data = json.loads(self.memory_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self.facts = {str(k): str(v) for k, v in data.items()}
        except (OSError, ValueError, TypeError):
            self.facts = {}
        self.reset()
        self.training = TrainingLab(self, self.memory_path.with_name("aprendizaje.json"))
        self.brain = LearningBrain(self,self.memory_path.with_name("cerebro.json"))
        self.furniture = FurnitureEditor(self,self.memory_path.with_name("muebles.json"))
        self.human = HumanAvatar(self,self.memory_path.with_name("avatar.json"))
        self.language = ValidatedLanguage(
            self,self.memory_path.with_name("validaciones.json"))

    def reset(self):
        if hasattr(self,"training"):
            self.training.release_owner("AMBOT")
        self.x, self.z = 6, 5
        self.facing = 1
        self.battery = 100.0
        self.steps = 0
        self.visits = {(self.x, self.z): 1}
        self.last_decision = "Tengo sensaciones nuevas. Aun no entiendo mi cuerpo."
        self.posture = "standing"
        self.stumble = 0.0
        self.reach = 0.0
        self.holding = None

    def free(self, x, z):
        return (
            0 <= z < len(WORLD)
            and 0 <= x < len(WORLD[z])
            and WORLD[z][x] == "."
            and (not hasattr(self,"furniture")
                 and (x,z) not in FURNITURE_CELLS
                 or hasattr(self,"furniture")
                 and not self.furniture.fixture_blocks(x,z))
            and (not hasattr(self,"furniture") or not self.furniture.blocks(x,z))
            and (not hasattr(self,"human") or self.human.seated
                 or (x,z)!=(self.human.x,self.human.z))
        )

    def location(self):
        if (self.x, self.z) in ROOM_CELLS:
            return ROOM_NAME
        return "PUERTA" if (self.x, self.z) == ROOM_DOOR else "PASILLO"
    def sense_distance(self, direction):
        """Sensor virtual: distancia, no acceso del bebe al mapa secreto."""
        dx,dz=DIRECTIONS[direction]
        x,z=self.x+dx,self.z+dz
        distance=0
        while self.free(x,z):
            distance+=1
            x,z=x+dx,z+dz
        return distance*40+10

    def front_distance(self):
        return self.sense_distance(self.facing)

    def state(self):
        return {
            "posicion": (self.x, self.z),
            "orientacion": ORIENTATIONS[self.facing],
            "bateria": round(self.battery, 1),
            "pasos": self.steps,
            "sensor_cm": self.front_distance(),
            "memoria": len(self.facts),
            "lugar": self.location(),
            "postura": self.posture,
            "sujetando": self.holding,
            "aprendizaje": dict(self.training.confidence) if hasattr(self,"training") else {},
        }

    def _save(self):
        self.memory_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.memory_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.facts, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.memory_path)

    def turn(self, direction):
        if self.battery <= 0.3:
            return "Bateria agotada. No puedo girar."
        self.facing = (self.facing + (1 if direction == "derecha" else -1)) % 4
        self.battery = max(0.0, round(self.battery - 0.3, 2))
        return "Gire a la " + direction + ". Direccion: " + ORIENTATIONS[self.facing] + "."

    def move(self, reverse=False):
        if self.posture=="lying":
            return "Primero debo incorporarme antes de caminar."
        if self.stumble>0:
            return "Estoy recuperando el equilibrio."
        if self.battery < 1.5:
            return "SEGURIDAD: bateria baja. Movimiento bloqueado."
        dx, dz = DIRECTIONS[self.facing]
        if reverse:
            dx, dz = -dx, -dz
        if not self.free(self.x + dx, self.z + dz):
            return "SEGURIDAD: hay un obstaculo. No avanzo."
        if hasattr(self,"training"):
            object_item=self.training.object_in_cell(self.x+dx,self.z+dz)
            if object_item:
                return self.training.push(object_item,dx,dz)
        if hasattr(self,"training"):
            stability=self.training.confidence["caminar"]
            if self.training.rng.random()<.28*(1-stability):
                self.training.motor_feedback(False)
                return "Me tambalee y cai. Estoy aprendiendo a caminar."
        self.x += dx
        self.z += dz
        self.steps += 1
        self.battery = max(0.0, round(self.battery - 1.5, 2))
        self.visits[(self.x, self.z)] = self.visits.get((self.x, self.z), 0) + 1
        if hasattr(self, "training"):
            self.training.motor_feedback(True)
            if self.holding:
                self.training.practice("transportar",True)
        return "Movimiento seguro. Posicion: X=" + str(self.x) + " Z=" + str(self.z) + "."

    def decide(self):
        """Elegir mediante distancias sensoriales y experiencia, sin leer WORLD."""
        if self.battery < 1.5:
            return "detener", "Bateria insuficiente: debo detenerme."
        sensed=[]
        for direction,(dx,dz) in enumerate(DIRECTIONS):
            distancia=self.sense_distance(direction)
            if distancia>25:
                turn=(direction-self.facing)%4
                turn_cost=0 if turn==0 else (1 if turn in (1,3) else 2)
                sensed.append((
                    self.visits.get((self.x+dx,self.z+dz),0),
                    turn_cost,turn==3,direction
                ))
        if not sensed:
            return "detener", "No encuentro una zona libre cerca."
        _,_,_,direction=min(sensed)
        if direction==self.facing:
            return "avanzar","La senal de proximidad me permite ensayar un paso."
        rotation=(direction-self.facing)%4
        if rotation==3:
            return "izquierda","El sensor muestra espacio a la izquierda."
        return "derecha","El sensor muestra espacio en otra direccion."

    def think(self):
        _, reason = self.decide()
        self.last_decision = reason
        return reason

    def explore(self):
        action, reason = self.decide()
        self.last_decision = reason
        if action == "avanzar":
            return self.move()
        if action in ("izquierda", "derecha"):
            return self.turn(action)
        return "Detenido por seguridad."

    def map_text(self):
        rows = []
        symbols = "^>v<"
        marks = {"cama": "C", "mesa": "M", "silla": "S", "armario": "A"}
        for z, row in enumerate(WORLD):
            chars = list(row)
            for name, cells in ROOM_OBJECTS.items():
                if hasattr(self,"furniture") and name in self.furniture.removed_fixed:
                    continue
                for x, object_z in cells:
                    if object_z == z:
                        chars[x] = marks[name]
            if z == ROOM_DOOR[1]:
                chars[ROOM_DOOR[0]] = "P"
            if hasattr(self,"furniture"):
                for item in self.furniture.extra_fixtures:
                    for xx,zz in self.furniture.occupied_cells(
                        item["kind"],item["x"],item["z"],item["orientation"]):
                        if zz==z:
                            chars[xx]={"cama":"C","mesa":"M","armario":"A"}[
                                item["kind"]]
                for chair in self.furniture.chairs:
                    if chair["z"] == z:
                        chars[chair["x"]] = "S"
            if hasattr(self,"human") and z==self.human.z:
                chars[self.human.x]="H"
            if z == self.z:
                chars[self.x] = symbols[self.facing]
            rows.append("".join(chars))
        return "\n".join(rows) + "\nC=cama M=mesa S=silla A=armario H=humano P=puerta"
    def command(self, raw):
        raw = str(raw).strip()
        cmd = normalize(raw)
        if not cmd:
            return ""
        if cmd in ("estado", "sensores", "sensor"):
            st = self.state()
            return "Bateria {bateria}% | Frente {sensor_cm} cm | X={posicion[0]} Z={posicion[1]} | {orientacion}".format(**st)
        if cmd in ("adelante", "avanzar", "avanza", "w"):
            return self.move()
        if cmd in ("retroceder", "retrocede", "atras", "s"):
            return self.move(reverse=True)
        if cmd in ("izquierda", "gira izquierda", "a"):
            return self.turn("izquierda")
        if cmd in ("derecha", "gira derecha", "d"):
            return self.turn("derecha")
        if cmd in ("pensar", "piensa", "plan", "que piensas"):
            return self.think()
        if cmd in ("explorar", "explora", "decide", "e"):
            return self.explore()
        if cmd in ("observar","mirar","q","guia","guias"):
            return self.training.focus_guide()
        if cmd in ("guia 1","guia 2","guia 3"):
            return self.training.focus_guide(int(cmd[-1])-1)
        if cmd in ("agarrar","sujetar","tomar","interactuar","f"):
            return self.training.try_grab()
        if cmd in ("soltar","dejar","liberar","v"):
            return self.training.try_release()
        if cmd in ("acostarse","acostar","recostarse","l"):
            return self.training.try_rest()
        if cmd in ("levantarse","incorporarse"):
            self.posture="standing"
            self.stumble=0
            return "Estoy de pie de nuevo."
        if cmd in ("identificar","reconocer","que es esto","i"):
            return self.training.identify()
        if cmd in ("aprender","progreso","habilidades"):
            return self.training.report()
        if cmd in ("cerebro","mente","conciencia","conocimientos"):
            return self.brain.summary()
        if cmd in ("pregunta","preguntas","que te preguntas"):
            return self.brain.pending_question() or "Aun no se me ocurrio una pregunta."
        if cmd.startswith("responde "):
            return self.brain.answer(raw[len("responde "):])
        if cmd.startswith("respuesta "):
            return self.brain.answer(raw[len("respuesta "):])
        if cmd.startswith("leer ") or cmd.startswith("lee "):
            start=5 if cmd.startswith("leer ") else 4
            return self.brain.learn_text(raw[start:],"lectura")
        if cmd.startswith("ensename ") or cmd.startswith("aprende "):
            start=9 if cmd.startswith("ensename ") else 8
            return self.brain.learn_text(raw[start:],"ensenanza")
        if cmd in ("contar","cuantos","matematicas"):
            return self.brain.compare_quantities(self.training)
        if cmd in ("curiosidad","investiga","que descubres"):
            return self.brain.autonomous_step()
        if cmd in ("detener", "detente", "stop", "alto"):
            return "Movimiento autonomo detenido."
        if cmd in ("reiniciar", "reset"):
            self.reset()
            return "Cuerpo y bateria reiniciados. Conservo mi memoria."
        if cmd in ("cargar", "recargar"):
            self.battery = 100.0
            return "Bateria simulada recargada al 100%."
        if cmd in ("mapa", "ver mapa"):
            return self.map_text()
        if cmd in ("muebles","sillas"):
            return ("Sillas adicionales: "+str(len(self.furniture.chairs))+
                    ". Usa el boton + AÑADIR.")
        if cmd in ("deshacer silla","quitar ultima silla","deshacer objeto","deshacer cambio"):
            return self.furniture.undo()[1]
        if cmd == "memoria":
            return ", ".join(k + "=" + v for k, v in self.facts.items()) or "No tengo recuerdos guardados."
        if cmd.startswith("recuerda ") and "=" in raw:
            pair = raw[len("recuerda "):].split("=", 1)
            key, value = pair[0].strip(), pair[1].strip()
            if not key or not value or len(key) > 80 or len(value) > 500:
                return "Usa: recuerda nombre = AMBOT (maximo 80 y 500 caracteres)."
            self.facts[normalize(key)] = value
            self._save()
            return "He aprendido: " + key + " = " + value
        if cmd.startswith("que sabes de "):
            key = normalize(raw[len("que sabes de "):].strip(" ?"))
            return self.facts.get(key, "No recuerdo ese dato.")
        if cmd.startswith("olvida "):
            key = normalize(raw[len("olvida "):].strip())
            if key not in self.facts:
                return "No encontre ese dato."
            del self.facts[key]
            self._save()
            return "Dato olvidado."
        if cmd in ("ayuda", "help", "?"):
            return ("TANQUE estilo RE1: FLECHAS para ti, WASD para AMBOT; "
                    "arriba/W avanza, abajo/S retrocede mirando al frente, "
                    "izquierda/A y derecha/D giran en el sitio. "
                    "Mantener pulsado repite. MI CUERPO para sentarse; "
                    "AÑADIR/QUITAR editor; chat: SI NO CORREGIR.")
        return "No entiendo ese comando aun. Escribe AYUDA."


def vadd(a, b):
    return (a[0]+b[0], a[1]+b[1], a[2]+b[2])


def vsub(a, b):
    return (a[0]-b[0], a[1]-b[1], a[2]-b[2])


def vmul(a, n):
    return (a[0]*n, a[1]*n, a[2]*n)


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def unit(a):
    m = math.sqrt(dot(a, a)) or 1.0
    return vmul(a, 1.0/m)


def tone(c, amount):
    return tuple(max(0, min(255, int(x*amount))) for x in c)


class Scene3D:
    """Motor 3D de proyeccion en perspectiva y caras ordenadas por profundidad.

    Emite poligonos de un espacio XYZ real; pygame dibuja la proyeccion en
    una ventana nativa. Sin navegador, WebGL ni servidor.
    """
    def __init__(self, pg):
        self.pg = pg
        self.yaw = 0.72
        self.pitch = 0.88
        self.human_angle=None
        self.human_rx=None
        self.human_rz=None
        self.frame_dt=.016
        self.distance = 18.2
        self.rx, self.rz = 6.0, 5.0
        self.angle = math.pi/2
        self.walk = 0.0
        center_x, center_z = self.world(5, 5)
        self.target = (center_x, .75, center_z)
        self.camera = (0, 0, 0)
        self.forward = (0, 0, 0)
        self.right = (0, 0, 0)
        self.up = (0, 0, 0)
        self.focal = 1
        self.rect = pg.Rect(0, 0, 960, 600)
        self.faces = []
        self.is_moving = False

    @staticmethod
    def world(x, z):
        return ((x-(len(WORLD[0])-1)/2)*TILE, (z-(len(WORLD)-1)/2)*TILE)

    def orient(self, facing):
        return facing_radians(facing)

    def camera_update(self, rect):
        self.rect = rect
        self.camera = (
            self.target[0] + math.sin(self.yaw)*math.cos(self.pitch)*self.distance,
            self.target[1] + math.sin(self.pitch)*self.distance,
            self.target[2] + math.cos(self.yaw)*math.cos(self.pitch)*self.distance,
        )
        self.forward = unit(vsub(self.target, self.camera))
        self.right = unit(cross(self.forward, (0, 1, 0)))
        self.up = cross(self.right, self.forward)
        self.focal = rect.height/(2*math.tan(math.radians(24)))

    def project(self, p):
        v = vsub(p, self.camera)
        depth = dot(v, self.forward)
        if depth < 0.1:
            return None
        return (
            self.rect.centerx + dot(v, self.right)*self.focal/depth,
            self.rect.centery - dot(v, self.up)*self.focal/depth,
            depth
        )

    def pick_floor(self, screen_pos):
        """Invertir la perspectiva para elegir una celda del suelo 3D."""
        if not self.rect.collidepoint(screen_pos):
            return None
        nx=(screen_pos[0]-self.rect.centerx)/self.focal
        ny=-(screen_pos[1]-self.rect.centery)/self.focal
        ray=unit(vadd(self.forward,vadd(vmul(self.right,nx),
                                       vmul(self.up,ny))))
        if ray[1]>=-1e-6:
            return None
        distance=(.02-self.camera[1])/ray[1]
        if distance<=0:
            return None
        point=vadd(self.camera,vmul(ray,distance))
        cell_x=round(point[0]/TILE+(len(WORLD[0])-1)/2)
        cell_z=round(point[2]/TILE+(len(WORLD)-1)/2)
        if 0<=cell_z<len(WORLD) and 0<=cell_x<len(WORLD[0]):
            return (cell_x,cell_z)
        return None

    def object_bounds(self, robot):
        """Volumenes de seleccion para muebles y objetos; excluye la estructura."""
        result=[]
        furniture=getattr(robot,"furniture",None)
        if furniture:
            fixtures=[
                ("cama",4.5,7.0,1.34,.68,0.0,.94),
                ("mesa",4.0,4.0,.67,.55,0.0,1.34),
                ("silla",4.0,5.0,.45,.46,0.0,1.40),
                ("armario",7.0,3.0,.63,.58,0.0,2.20),
                ("ventana",5.5,2.0,.96,.065,1.38,2.28),
                ("alfombra",5.8,5.5,TILE*1.2,TILE*.82,.018,.066),
            ]
            for name,x,z,hx,hz,ylo,yhi in fixtures:
                if name in furniture.removed_fixed:continue
                wx,wz=self.world(x,z)
                if name=="ventana":wz+=TILE*.49
                result.append({
                    "kind":"fixture","key":name,"label":name.upper(),
                    "bounds":(wx-hx,wx+hx,ylo,yhi,wz-hz,wz+hz),
                })
            for added in furniture.extra_fixtures:
                x,z=added["x"],added["z"]
                if added["kind"]=="cama":
                    if added["orientation"]%2==0:
                        x+=.5
                        hx,hz=1.34,.69
                    else:
                        z+=.5
                        hx,hz=.69,1.34
                    height=.95
                elif added["kind"]=="mesa":
                    hx,hz,height=.67,.55,1.0
                else:
                    hx,hz,height=.62,.58,2.25
                wx,wz=self.world(x,z)
                result.append({
                    "kind":"fixture_added","key":added["id"],
                    "label":ADD_CATALOG[added["kind"]],
                    "bounds":(wx-hx,wx+hx,0,height,wz-hz,wz+hz),
                })
            for chair in furniture.chairs:
                wx,wz=self.world(chair["x"],chair["z"])
                height=1.72 if chair["style"]=="alta" else 1.46
                result.append({
                    "kind":"chair","key":(chair["x"],chair["z"]),
                    "label":CHAIR_STYLES[chair["style"]],
                    "bounds":(wx-.55,wx+.55,0,height,wz-.55,wz+.55),
                })
        if hasattr(robot,"training"):
            for name,item in robot.training.items.items():
                wx,wz=self.world(item.x,item.z)
                radius=max(.22,item.radius*TILE*1.1)
                result.append({
                    "kind":"movable","key":name,"label":name.upper(),
                    "bounds":(wx-radius,wx+radius,
                              max(0,item.y-radius),item.y+radius,
                              wz-radius,wz+radius),
                })
            for guide in robot.training.guides:
                wx,wz=self.world(guide.x,guide.z)
                result.append({
                    "kind":"guide","key":guide.name,
                    "label":"ROBOT "+guide.name,
                    "bounds":(wx-.30,wx+.30,.05,3.0,wz-.30,wz+.30),
                })
        if hasattr(robot,"human"):
            wx,wz=self.world(robot.human.x,robot.human.z)
            result.append({
                "kind":"protected","key":"TU PERSONAJE",
                "label":"HUMANO CONTROLADO",
                "bounds":(wx-.38,wx+.38,.03,2.65,wz-.38,wz+.38),
            })
        wx,wz=self.world(robot.x,robot.z)
        result.append({
            "kind":"protected","key":"AMBOT","label":"ROBOT AMBOT",
            "bounds":(wx-.30,wx+.30,.05,3.0,wz-.30,wz+.30),
        })
        return result

    def pick_object(self, screen_pos, robot):
        """Rayo 3D exacto contra cajas de seleccion, ordenado por profundidad."""
        furniture=getattr(robot,"furniture",None)
        if not self.rect.collidepoint(screen_pos):
            return None
        nx=(screen_pos[0]-self.rect.centerx)/self.focal
        ny=-(screen_pos[1]-self.rect.centery)/self.focal
        ray=unit(vadd(self.forward,vadd(vmul(self.right,nx),
                                       vmul(self.up,ny))))
        closest=None
        closest_t=float("inf")
        for obj in self.object_bounds(robot):
            left,right,low,high,back,front=obj["bounds"]
            minimum=-float("inf")
            maximum=float("inf")
            valid=True
            for o,d,lo,hi in zip(self.camera,ray,
                                  (left,low,back),(right,high,front)):
                if abs(d)<1e-9:
                    if not lo<=o<=hi:
                        valid=False
                        break
                    continue
                near=(lo-o)/d
                far=(hi-o)/d
                if near>far:near,far=far,near
                minimum=max(minimum,near)
                maximum=min(maximum,far)
                if maximum<minimum:
                    valid=False
                    break
            if not valid or maximum<=0:
                continue
            distance=minimum if minimum>0 else maximum
            if distance<closest_t:
                closest,closest_t=obj,distance
        if closest is not None:
            return closest
        # Una pulsacion cerca de la base del mueble tambien sirve.
        cell=self.pick_floor(screen_pos)
        if cell is None or furniture is None:
            return None
        x,z=cell
        for item in self.object_bounds(robot):
            if item["kind"]=="protected":
                continue
            if item["kind"]=="chair" and item["key"]==(x,z):
                return item
            if item["kind"]=="fixture" and item["key"] in ROOM_OBJECTS:
                if (x,z) in ROOM_OBJECTS[item["key"]]:
                    return item
        return None

    def quad(self, pts, c):
        projected = [self.project(pt) for pt in pts]
        if any(x is None for x in projected):
            return
        depth = sum(p[2] for p in projected)/4
        self.faces.append((depth, "poly", [(int(x),int(y)) for x,y,_ in projected], c, 0))

    def line(self, a, b, c, width=0.06):
        aa = self.project(a)
        bb = self.project(b)
        if aa is None or bb is None:
            return
        depth = (aa[2]+bb[2])/2
        pxwidth = min(22, max(1, round(self.focal*width/depth)))
        self.faces.append((depth, "line", [(int(aa[0]),int(aa[1])),(int(bb[0]),int(bb[1]))], c, pxwidth))

    def ball(self, center, radius, c):
        p = self.project(center)
        if p is None:
            return
        size = max(2, min(45, round(self.focal*radius/p[2])))
        self.faces.append((p[2], "ball", (int(p[0]), int(p[1])), c, size))

    def box(self, x, y, z, sx, sy, sz, c, neon=False):
        xl,xr=x-sx/2,x+sx/2
        zb,zf=z-sz/2,z+sz/2
        low,high=y,y+sy
        sides=[
            ([(xl,low,zb),(xl,low,zf),(xl,high,zf),(xl,high,zb)],.74),
            ([(xr,low,zf),(xr,low,zb),(xr,high,zb),(xr,high,zf)],.80),
            ([(xl,low,zf),(xr,low,zf),(xr,high,zf),(xl,high,zf)],.91),
            ([(xr,low,zb),(xl,low,zb),(xl,high,zb),(xr,high,zb)],.66),
            ([(xl,high,zb),(xl,high,zf),(xr,high,zf),(xr,high,zb)],1.11),
        ]
        for pts,mult in sides:
            self.quad(pts,tone(c,mult))
        if neon:
            h=high+.015
            self.line((xl,h,zb),(xr,h,zb),COLOR["blue"],.035)
            self.line((xr,h,zb),(xr,h,zf),COLOR["cyan"],.035)

    def build_room_details(self, furniture=None):
        """Dibujar solo los muebles y accesorios que siguen presentes."""
        hidden=furniture.removed_fixed if furniture is not None else set()
        if "alfombra" not in hidden:
            # Alfombra central y costuras neon.
            x, z = self.world(5.8, 5.5)
            rx, rz = TILE*1.20, TILE*.82
            self.quad(((x-rx,.020,z-rz),(x-rx,.020,z+rz),
                       (x+rx,.020,z+rz),(x+rx,.020,z-rz)), COLOR["rug"])
            for q in range(4):
                sx=x-rx+(2*rx)*q/3
                self.line((sx,.027,z-rz),(sx,.027,z+rz),COLOR["blue"],.024)

        if "cama" not in hidden:
            # Cama y almohadas en la esquina inferior izquierda.
            bx,bz=self.world(4.5,7)
            self.box(bx,.10,bz,TILE*1.95,.21,TILE*.86,COLOR["wood"],neon=True)
            self.box(bx,.33,bz,TILE*1.83,.26,TILE*.77,COLOR["bed"])
            self.box(bx-TILE*.64,.60,bz,TILE*.35,.11,TILE*.49,COLOR["ink"])
            self.box(bx+TILE*.58,.58,bz,TILE*.38,.08,TILE*.49,COLOR["cyan"])
            self.box(bx-TILE*.96,.08,bz,.09,.83,TILE*.87,COLOR["wood"])

        if "mesa" not in hidden:
            # Mesa con libro, lampara y cuatro patas.
            tx,tz=self.world(4,4)
            for dx in (-.49,.49):
                for dz in (-.31,.31):
                    self.box(tx+dx,0,tz+dz,.07,.74,.07,COLOR["wood"])
            self.box(tx,.74,tz,1.18,.12,.82,COLOR["wood"],neon=True)
            self.box(tx+.11,.89,tz-.10,.34,.04,.23,COLOR["cyan"])
            self.line((tx-.36,.89,tz+.11),(tx-.36,1.20,tz+.11),COLOR["ink"],.065)
            self.box(tx-.36,1.18,tz+.11,.26,.09,.25,COLOR["window"])

        if "silla" not in hidden:
            # Silla delante de la mesa.
            cx,cz=self.world(4,5)
            self.box(cx,.43,cz,.74,.11,.68,COLOR["wood"],neon=True)
            self.box(cx,.54,cz+.29,.74,.72,.11,COLOR["room_wall"])
            for dx in (-.27,.27):
                for dz in (-.23,.23):
                    self.box(cx+dx,0,cz+dz,.07,.42,.07,COLOR["blue"])

        if "armario" not in hidden:
            # Armario con dos puertas y tiradores.
            ax,az=self.world(7,3)
            self.box(ax,0,az,TILE*.83,2.12,TILE*.66,COLOR["room_wall"])
            self.box(ax-.27,.15,az+.46,.45,1.77,.045,COLOR["wood"])
            self.box(ax+.27,.15,az+.46,.45,1.77,.045,COLOR["wood"])
            self.line((ax,.19,az+.49),(ax,1.93,az+.49),COLOR["cyan"],.035)
            self.ball((ax-.06,1.09,az+.52),.050,COLOR["pink"])
            self.ball((ax+.06,1.09,az+.52),.050,COLOR["pink"])

        if "ventana" not in hidden:
            # Ventana luminosa: marco en la pared norte de la habitacion.
            wx,wz=self.world(5.5,2)
            front=wz+TILE*.49
            self.box(wx,1.46,front,1.58,.70,.045,COLOR["window"])
            for yy in (1.43,2.18):
                self.line((wx-.84,yy,front+.04),(wx+.84,yy,front+.04),
                          COLOR["ink"],.05)
            for xx in (-.84,0,.84):
                self.line((wx+xx,1.43,front+.04),(wx+xx,2.18,front+.04),
                          COLOR["ink"],.05)

        # Entrada abierta: dos postes y dintel sin bloquear el paso.
        dx,dz=self.world(*ROOM_DOOR)
        for offset in (-TILE*.52,TILE*.52):
            self.box(dx,0,dz+offset,.11,2.24,.12,COLOR["blue"])
        self.box(dx,2.18,dz,.14,.14,TILE*1.08,COLOR["cyan"])
        self.box(dx,.012,dz,TILE*.94,.035,TILE*.86,COLOR["rug"])

    def build_user_chairs(self, furniture):
        """Dibujar los tres modelos de silla orientados en el plano XZ."""
        for chair in furniture.chairs:
            center_x,center_z=self.world(chair["x"],chair["z"])
            style=chair["style"]
            orientation=chair["orientation"]
            def position(dx,dz):
                if orientation==0:return center_x+dx,center_z+dz
                if orientation==1:return center_x-dz,center_z+dx
                if orientation==2:return center_x-dx,center_z-dz
                return center_x+dz,center_z-dx

            def part(dx,y,dz,sx,sy,sz,color,neon=False):
                px,pz=position(dx,dz)
                if orientation%2:
                    sx,sz=sz,sx
                self.box(px,y,pz,sx,sy,sz,color,neon=neon)

            if style=="alta":
                seat_y=.87
                color=COLOR["yellow"]
                back=COLOR["wood"]
            elif style=="oficina":
                seat_y=.57
                color=COLOR["window"]
                back=COLOR["room_wall"]
            else:
                seat_y=.43
                color=COLOR["wood"]
                back=COLOR["room_wall"]

            part(0,seat_y,0,.77,.12,.70,color,neon=True)
            part(0,seat_y+.12,.30,.76,.65,.12,back)
            for dx in (-.28,.28):
                for dz in (-.25,.25):
                    if style=="oficina":
                        continue
                    part(dx,0,dz,.065,seat_y,.065,COLOR["blue"])
            if style=="alta":
                for z in (-.25,.25):
                    part(0,.28,z,.53,.045,.045,COLOR["cyan"])
            if style=="oficina":
                part(0,.07,0,.09,.49,.09,COLOR["blue"])
                for dx,dz in ((-.42,0),(.42,0),(0,-.35),(0,.35)):
                    px,pz=position(dx,dz)
                    center=position(0,0)
                    self.line((center[0],.09,center[1]),(px,.09,pz),
                              COLOR["cyan"],.055)
                    self.ball((px,.072,pz),.075,COLOR["wood"])
                for dx in (-.39,.39):
                    part(dx,.67,-.02,.055,.09,.44,COLOR["cyan"])
                part(0,seat_y+.23,.35,.52,.21,.10,COLOR["blue"])

    def build_custom_fixtures(self,furniture):
        """Muebles adicionales del editor, con la misma geometria que los base."""
        for item in furniture.extra_fixtures:
            kind=item["kind"]
            x,z=item["x"],item["z"]
            orientation=item["orientation"]
            px,pz=self.world(x,z)
            if kind=="cama":
                if orientation%2==0: px+=TILE*.5
                else: pz+=TILE*.5
                sx,sz=(TILE*1.90,TILE*.86) if orientation%2==0 else (
                    TILE*.86,TILE*1.90)
                self.box(px,.10,pz,sx,.20,sz,COLOR["wood"],neon=True)
                self.box(px,.33,pz,sx*.94,.26,sz*.89,COLOR["bed"])
                head_x=px-sx*.36 if orientation%2==0 else px
                head_z=pz if orientation%2==0 else pz-sz*.36
                pillow_sx=.35 if orientation%2==0 else .49
                pillow_sz=.49 if orientation%2==0 else .35
                self.box(head_x,.62,head_z,pillow_sx,.10,pillow_sz,
                         COLOR["ink"])
            elif kind=="mesa":
                for dx in (-.45,.45):
                    for dz in (-.30,.30):
                        self.box(px+dx,0,pz+dz,.08,.75,.08,COLOR["wood"])
                self.box(px,.75,pz,1.15,.13,.84,COLOR["wood"],neon=True)
                self.box(px+.16,.90,pz-.12,.27,.04,.27,COLOR["cyan"])
            elif kind=="armario":
                self.box(px,0,pz,TILE*.78,2.08,TILE*.69,
                         COLOR["room_wall"],neon=True)
                self.box(px-.23,.14,pz+.47,.41,1.74,.04,COLOR["wood"])
                self.box(px+.23,.14,pz+.47,.41,1.74,.04,COLOR["wood"])
                self.ball((px-.08,1.12,pz+.50),.045,COLOR["pink"])
                self.ball((px+.08,1.12,pz+.50),.045,COLOR["pink"])

    def build_world(self, robot):
        for z,row in enumerate(WORLD):
            for x,c in enumerate(row):
                px,pz=self.world(x,z)
                gap=.025
                l=px-TILE/2+gap
                r=px+TILE/2-gap
                back=pz-TILE/2+gap
                front=pz+TILE/2-gap
                if c == ".":
                    if (x,z) in ROOM_CELLS:
                        floor=COLOR["room_floor"] if (x+z)%2 else COLOR["room_floor2"]
                    elif (x,z) == ROOM_DOOR:
                        floor=COLOR["rug"]
                    else:
                        floor=COLOR["floor1"] if (x+z)%2 else COLOR["floor2"]
                    self.quad(((l,0,back),(l,0,front),(r,0,front),(r,0,back)),floor)
                    if (x,z) not in ROOM_CELLS and (x+3*z)%13==0:
                        self.line((px-.12,.013,pz),(px+.12,.013,pz),COLOR["blue"],.025)
                else:
                    edge = x in (0,len(row)-1) or z in (0,len(WORLD)-1)
                    is_room_wall = (x,z) in ROOM_WALL_CELLS
                    if is_room_wall:
                        # La habitacion queda abierta a la vista en su cara frontal.
                        height = 2.53 if z==2 or x==2 else (.70 if z==8 else .93)
                    else:
                        height=.66 if edge else 1.35
                    cwall=COLOR["room_wall"] if is_room_wall else (COLOR["wall"] if edge else COLOR["inner"])
                    self.box(px,0,pz,TILE-.04,height,TILE-.04,cwall,neon=True)
                    if not edge and not is_room_wall:
                        self.box(px,height,pz,.13,.05,.13,COLOR["pink"])
        self.build_room_details(getattr(robot,"furniture",None))
        if hasattr(robot,"furniture"):
            self.build_user_chairs(robot.furniture)
            self.build_custom_fixtures(robot.furniture)
        # Sensor virtual orientado: detecta la siguiente pared.
        dx,dz=DIRECTIONS[robot.facing]
        bx,bz=self.world(self.rx,self.rz)
        d=min(3.0,robot.front_distance()/40.0)*TILE
        self.line((bx,.08,bz),(bx+dx*d,.08,bz+dz*d),COLOR["cyan"],.04)
        self.ball((bx+dx*d,.08,bz+dz*d),.09,COLOR["pink"])

    def build_robot(self, robot, dt, elapsed, force_moving=None, tint=None):
        ink=COLOR["ink"] if tint is None else tone(tint,1.15)
        cyan=COLOR["cyan"] if tint is None else tint
        blue=COLOR["blue"] if tint is None else tone(tint,.78)
        pink=COLOR["pink"] if tint is None else tone(tint,1.08)
        posture=getattr(robot,"posture","standing")
        reach=max(0.0,min(1.0,float(getattr(robot,"reach",0))))
        speed=min(1,dt*9)
        oldx,oldz=self.rx,self.rz
        self.rx+=(robot.x-self.rx)*speed
        self.rz+=(robot.z-self.rz)*speed
        moved=abs(oldx-self.rx)+abs(oldz-self.rz)>.001
        if force_moving is not None:
            moved=bool(force_moving)
        self.is_moving=moved
        self.walk+=dt*(12 if moved else 2.5)
        target=self.orient(robot.facing)
        if tint is not None and hasattr(robot,"heading"):
            self.angle=robot.heading
        else:
            self.angle=rotate_towards(self.angle,target,TANK_ROTATION_RATE*dt)
        bx,bz=self.world(self.rx,self.rz)
        if posture=="lying" and tint is None:
            # Al acostarse, el bebe se apoya en la cama sin desplazar su
            # posicion logica a una celda de mueble no transitable.
            bx,bz=self.world(4.5,7.0)
        dx,dz=DIRECTIONS[robot.facing]
        fwd=(math.sin(self.angle),-math.cos(self.angle))
        side=(-fwd[1],fwd[0])
        bob=abs(math.sin(self.walk))*.04 if moved else math.sin(elapsed*1.6)*.012
        def p(sideways,height,forward=0):
            if posture=="lying":
                # La longitud vertical se convierte en eje horizontal.
                axis=(height-1.4)*.78
                return (
                    bx+side[0]*sideways+fwd[0]*axis,
                    .74+forward*.18,
                    bz+side[1]*sideways+fwd[1]*axis,
                )
            if posture=="stumble":
                lean=max(.0,(height-.42))*.42
                return (
                    bx+side[0]*sideways+fwd[0]*(forward+lean),
                    height*.70+bob,
                    bz+side[1]*sideways+fwd[1]*(forward+lean),
                )
            return (bx+side[0]*sideways+fwd[0]*forward, height+bob,
                    bz+side[1]*sideways+fwd[1]*forward)
        def bone(a,b,color,width=.085):
            self.line(p(*a),p(*b),color,width)
        def node(loc,r,color):
            self.ball(p(*loc),r,color)
        # Halo holografico alrededor de los pies.
        for j in range(28):
            a,b=j*math.tau/28,(j+1)*math.tau/28
            self.line((bx+math.cos(a)*.55,.025,bz+math.sin(a)*.55),
                      (bx+math.cos(b)*.55,.025,bz+math.sin(b)*.55),
                      blue,.029)
        swing=math.sin(self.walk)*(.29 if moved else .025)
        for sign in (-1,1):
            hip=(sign*.15,1.0,0)
            knee=(sign*.20,.55,-swing*sign*.45)
            foot=(sign*.22,.11,-swing*sign*.70)
            bone(hip,knee,ink,.11)
            bone(knee,foot,cyan,.095)
            node(knee,.1,blue)
            node(foot,.12,ink)
        bone((0,1.0,0),(0,1.78,0),ink,.19)
        bone((-.29,1.77,0),(.29,1.77,0),cyan,.105)
        for sign in (-1,1):
            shoulder=(sign*.29,1.77,0)
            elbow=(sign*(.47-.10*reach),1.36,swing*sign*.5+reach*.24)
            hand=(sign*(.52-.24*reach),1.02+.16*reach,
                  swing*sign*.7+reach*.48)
            bone(shoulder,elbow,cyan,.095)
            bone(elbow,hand,ink,.09)
            node(elbow,.1,blue)
            node(hand,.1,ink)
        node((0,1.48,-.13),.13,pink)
        bone((0,1.78,0),(0,2.02,0),cyan,.075)
        node((0,2.31,0),.28,ink)
        node((-.105,2.33,.23),.053,blue)
        node((.105,2.33,.23),.053,blue)
        bone((0,2.58,0),(0,2.78,0),cyan,.035)
        node((0,2.81,0),.066,pink)
        if getattr(robot,"holding",None):
            node((0,1.13,.56),.08,pink)

    def build_human(self, person, elapsed=0):
        """Esqueleto 3D articulado del USUARIO, distinto a AMBOT y a maestros."""
        dt=max(0.0,min(.05,getattr(self,"frame_dt",.016)))
        if self.human_angle is None:
            self.human_angle=facing_radians(person.facing)
        else:
            self.human_angle=rotate_towards(
                self.human_angle,facing_radians(person.facing),
                TANK_ROTATION_RATE*dt)
        if self.human_rx is None:
            self.human_rx=float(person.x)
            self.human_rz=float(person.z)
        else:
            speed=min(1.0,dt*9)
            self.human_rx+=(person.x-self.human_rx)*speed
            self.human_rz+=(person.z-self.human_rz)*speed
        bx,bz=self.world(self.human_rx,self.human_rz)
        dx,dz=math.sin(self.human_angle),-math.cos(self.human_angle)
        side=(-dz,dx)
        selected=person.joints
        def pt(s,y,front=0):
            return (bx+side[0]*s+dx*front,y,bz+side[1]*s+dz*front)
        def bone(start,end,color,width=.10):
            self.line(start,end,color,width)
        def joint(at,r=.08,color=None):
            self.ball(at,r,color or COLOR["pink"])
        tint=(248,186,98)
        shade=(97,192,223)
        white=(230,240,246)
        seated=person.seated
        hip_y=.90 if seated else 1.06
        chest_y=1.64 if seated else 1.80
        lean=math.sin(math.radians(selected["torso"]))*.42
        neck=pt(0,chest_y+.20,lean)
        belly=pt(0,hip_y+.25,lean*.28)
        pelvis=pt(0,hip_y)
        bone(pelvis,belly,tint,.20)
        bone(belly,neck,white,.21)
        joint(pelvis,.14,shade)
        shoulder_points={}
        for sign in (-1,1):
            key="izq" if sign<0 else "der"
            shoulder=pt(sign*.32,chest_y+.07,lean*.92)
            shoulder_points[sign]=shoulder
            arm=math.radians(selected["brazo_"+key])
            elbow_angle=math.radians(selected["codo_"+key])
            elbow=pt(sign*.49,
                     chest_y-.43+math.sin(arm)*.45,
                     lean+.10+math.cos(arm)*.23)
            hand=pt(sign*.56,
                    chest_y-.88+math.sin(arm)*.72+math.sin(elbow_angle)*.19,
                    lean+.20+math.cos(arm)*.24+math.cos(elbow_angle)*.17)
            bone(shoulder,elbow,tint,.115)
            bone(elbow,hand,shade,.105)
            joint(shoulder,.09,shade)
            joint(elbow,.105,white)
            joint(hand,.09,white)
            hip=pt(sign*.19,hip_y)
            hip_angle=math.radians(selected["pierna_"+key])
            knee_angle=math.radians(selected["rodilla_"+key])
            knee_front=(.51 if seated else .04)+math.sin(hip_angle)*.35
            knee_y=(.54 if seated else .57)+math.sin(hip_angle)*.12
            knee=pt(sign*.22,knee_y,knee_front)
            ankle=pt(sign*.23,.12,
                     knee_front+(.23 if seated else .03)+math.sin(knee_angle)*.27)
            bone(hip,knee,white,.145)
            bone(knee,ankle,tint,.12)
            joint(knee,.105,shade)
            bone(ankle,pt(sign*.23,.10,
                           knee_front+(.40 if seated else .20)
                           +math.sin(knee_angle)*.27),shade,.09)
            joint(ankle,.10,white)
        bone(shoulder_points[-1],shoulder_points[1],shade,.12)
        head_shift=math.sin(math.radians(selected["cabeza"]))*.25
        head=pt(head_shift, chest_y+.54,lean+.06)
        bone(neck,head,white,.09)
        self.ball(head,.29,white)
        for offset in (-.095,.095):
            eye=pt(head_shift+offset,chest_y+.57,lean+.31)
            joint(eye,.045,tint)
        self.line(pt(head_shift-.10,chest_y+.43,lean+.28),
                  pt(head_shift+.10,chest_y+.43,lean+.28),shade,.035)
        # Halo naranja identifica al humano controlado por el teclado.
        for i in range(16):
            a,b=i*math.tau/16,(i+1)*math.tau/16
            self.line((bx+math.cos(a)*.49,.022,bz+math.sin(a)*.49),
                      (bx+math.cos(b)*.49,.022,bz+math.sin(b)*.49),
                      tint,.038)

    def build_training(self, training, elapsed):
        """Geometria de los tres robots guia y objetos con estado fisico."""
        for item in training.items.values():
            ix,iz=self.world(item.x,item.z)
            if item.shape=="ball":
                self.ball((ix,item.y,iz),item.radius*TILE,item.color)
                self.ball((ix-.055,item.y+.08,iz+.10),.055,COLOR["ink"])
            else:
                self.box(ix,item.y-item.radius*TILE,iz,
                         item.radius*2.1*TILE,item.radius*2.1*TILE,
                         item.radius*2.1*TILE,item.color,neon=True)
            if item.held_by:
                self.line((ix,.03,iz),(ix,item.y-.2,iz),COLOR["blue"],.026)

        # Las animaciones de los guias no deben modificar el estado de la
        # camara o la animacion del bebe que se usara en el visor izquierdo.
        old=(self.rx,self.rz,self.angle,self.walk,self.is_moving)
        for guide in training.guides:
            self.rx,self.rz=guide.x,guide.z
            self.angle=guide.heading
            self.walk=guide.walk
            self.is_moving=guide.moving
            self.build_robot(guide,0,elapsed,force_moving=guide.moving,tint=guide.color)
            gx,gz=self.world(guide.x,guide.z)
            # Indicador luminoso de tutor, distinto del brillo del bebe.
            self.line((gx,3.02,gz),(gx,3.30,gz),guide.color,.045)
            self.ball((gx,3.36,gz),.09,guide.color)
        self.rx,self.rz,self.angle,self.walk,self.is_moving=old

    def paint_faces(self, surface, rect):
        """Compartir el pintor de poligonos entre las dos camaras 3D."""
        pg=self.pg
        self.faces.sort(key=lambda face:face[0],reverse=True)
        clip=surface.get_clip()
        surface.set_clip(rect)
        for _,kind,pts,c,size in self.faces:
            if kind=="poly":
                pg.draw.polygon(surface,c,pts)
            elif kind=="line":
                pg.draw.line(surface,c,*pts,size)
            else:
                pg.draw.circle(surface,c,pts,size)
        surface.set_clip(clip)

    def render(self, surface, rect, robot, dt, elapsed):
        pg=self.pg
        pg.draw.rect(surface,(5,16,29),rect,border_radius=12)
        self.camera_update(rect)
        self.faces=[]
        self.frame_dt=dt
        self.build_world(robot)
        self.build_robot(robot,dt,elapsed)
        if hasattr(robot,"training"):
            self.build_training(robot.training,elapsed)
        if hasattr(robot,"human"):
            self.build_human(robot.human,elapsed)
        self.paint_faces(surface,rect)
        pg.draw.rect(surface,COLOR["line"],rect,2,border_radius=12)

    def render_portrait(self, surface, rect, robot, source_scene, elapsed):
        """Otra camara del MISMO stickman: pose, giro y ciclo de marcha compartidos.

        No aplica un segundo movimiento ni incrementa la animacion: recibe
        las coordenadas interpoladas y el reloj de la escena principal.
        """
        pg=self.pg
        self.rx,self.rz=source_scene.rx,source_scene.rz
        self.angle=source_scene.angle
        self.walk=source_scene.walk
        self.is_moving=source_scene.is_moving
        x,z=self.world(self.rx,self.rz)
        self.target=(x,1.42,z)
        self.yaw=1.31
        self.pitch=.12
        self.distance=4.9
        pg.draw.rect(surface,(5,20,34),rect,border_radius=10)
        clip=surface.get_clip()
        surface.set_clip(rect)
        # Luz ambiental y marca sobre el suelo del escenario de retrato.
        pg.draw.ellipse(surface,(13,46,65),
                        (rect.centerx-rect.width*.34,rect.bottom-49,rect.width*.68,33),1)
        for i in range(5):
            py=rect.y+40+i*(rect.height-80)/5
            pg.draw.line(surface,(12,37,54),
                         (rect.x+4,int(py)),(rect.right-4,int(py)),1)
        surface.set_clip(clip)
        self.camera_update(rect)
        self.faces=[]
        self.build_robot(robot,0,elapsed,force_moving=source_scene.is_moving)
        self.paint_faces(surface,rect)
        pg.draw.rect(surface,COLOR["line"],rect,1,border_radius=10)


class DesktopApp:
    def __init__(self, pg, smoke=False):
        self.pg=pg
        self.smoke=smoke
        pg.init()
        if smoke:
            self.screen=pg.display.set_mode((1120,690))
        else:
            self.screen=pg.display.set_mode((1320,760),pg.RESIZABLE)
        pg.display.set_caption(TITLE + " v" + APP_VERSION)
        self.clock=pg.time.Clock()
        self.fonts={i:pg.font.SysFont("Segoe UI",i) for i in (13,14,16,17,18,20,23,27)}
        self.robot=Robot()
        self.hardware=ArduinoBridge()
        self.scene=Scene3D(pg)
        self.portrait_scene=Scene3D(pg)
        self.auto=not smoke
        self.auto_clock=0.0
        self.elapsed=0.0
        self.bubble_text="¿Qué son esos movimientos? Quiero aprender."
        self.bubble_until=float("inf")
        self.bubble_kind="hello"
        self.input_focus=False
        self.input_value=""
        self.messages=deque(maxlen=24)
        self.messages.append(("SISTEMA","AMBOT aprende solo; ESPACIO pausa/reanuda.",COLOR["green"]))
        self.messages.append(("SISTEMA","Tres robots guia inician demostraciones.",COLOR["cyan"]))
        self.messages.append(("AYUDA","TANQUE: flechas TÚ / WASD AMBOT; arriba avanza, izquierda gira.",COLOR["muted"]))
        self.dragging=False
        self.mouse=(0,0)
        self.buttons={}
        self.input_rect=pg.Rect(0,0,1,1)
        self.view=pg.Rect(290,83,650,565)
        self.portrait_view=pg.Rect(20,83,250,565)
        self.last_portrait_state=None
        self.last_guide_event=0
        self.selected_guide=0
        self.editor_mode=False
        self.editor_resume_auto=False
        self.editor_style="clasica"
        self.editor_choice="silla_clasica"
        self.editor_category="sillas"
        self.avatar_panel=True
        self.avatar_joint="brazo_der"
        self.editor_action="add"
        self.editor_orientation=2
        self.editor_rect=pg.Rect(0,0,1,1)
        self.training_rect=pg.Rect(0,0,1,1)
        self.editor_hint="Elige una silla y su posicion."
        self._tank_held={}
        self._tank_initial_delay=.33

    def text(self,pos,value,size=16,color=None,max_width=None):
        font=self.fonts.get(size,self.fonts[16])
        value=str(value).replace("\n"," ")
        if max_width is not None:
            while value and font.size(value)[0]>max_width:
                value=value[:-1]
            if len(value)==0:
                return
        self.screen.blit(font.render(value,True,color or COLOR["ink"]),pos)

    def panel(self,rect,fill=None,border=None,radius=13):
        self.pg.draw.rect(self.screen,fill or COLOR["panel"],rect,border_radius=radius)
        self.pg.draw.rect(self.screen,border or COLOR["line"],rect,1,border_radius=radius)

    def button(self,key,label,x,y,w,h,accent=False):
        pg=self.pg
        r=pg.Rect(x,y,w,h)
        hovered=r.collidepoint(pg.mouse.get_pos())
        fill=(20,96,124) if accent else ((30,65,86) if hovered else COLOR["panel2"])
        pg.draw.rect(self.screen,fill,r,border_radius=8)
        pg.draw.rect(self.screen,COLOR["cyan"] if accent else COLOR["line"],r,1,border_radius=8)
        f=self.fonts[14]
        label=f.render(label,True,COLOR["ink"])
        self.screen.blit(label,label.get_rect(center=r.center))
        self.buttons[key]=r

    def say(self, text, duration=5.0, kind="normal"):
        """Presenta una respuesta del cerebro sin modificar la logica del robot."""
        self.bubble_text=str(text).strip() or "..."
        self.bubble_until=self.elapsed+max(1.0,float(duration))
        self.bubble_kind=kind

    def wrap_text(self, text, font, max_width, max_lines=4):
        """Envuelve texto por anchura, recortando palabras largas sin desbordes."""
        lines=[]
        current=""
        for word in str(text).replace("\n"," ").split():
            proposed=(current+" "+word).strip()
            if font.size(proposed)[0]<=max_width:
                current=proposed
                continue
            if current:
                lines.append(current)
                current=""
            while word and font.size(word)[0]>max_width:
                piece=""
                for char in word:
                    if font.size(piece+char)[0]>max_width:
                        break
                    piece+=char
                if not piece:
                    break
                lines.append(piece)
                word=word[len(piece):]
            current=word
        if current:
            lines.append(current)
        if not lines:
            lines=["..."]
        if len(lines)>max_lines:
            lines=lines[:max_lines]
            tail=lines[-1]
            while tail and font.size(tail+"...")[0]>max_width:
                tail=tail[:-1]
            lines[-1]=tail+"..."
        return lines

    def draw_character_viewer(self, rect):
        """Visor 3D de primer plano enlazado al cuerpo de la escena central."""
        pg=self.pg
        self.panel(rect)
        self.text((rect.x+14,rect.y+12),"PERSONAJE / EN VIVO",16,COLOR["cyan"])
        status=("IMITANDO" if self.auto else
                ("ACOSTADO" if self.robot.posture=="lying" else
                 ("APRENDIENDO" if self.scene.is_moving else "OBSERVANDO")))
        self.text((rect.x+14,rect.y+36),"● "+status,13,COLOR["green"] if self.auto else COLOR["muted"])

        # Reservar franja superior para la burbuja sin tapar al stickman.
        camera=pg.Rect(rect.x+12,rect.y+124,rect.width-24,
                       max(190,rect.height-201))
        self.portrait_scene.render_portrait(
            self.screen,camera,self.robot,self.scene,self.elapsed)
        self.last_portrait_state=(
            self.portrait_scene.rx,self.portrait_scene.rz,
            self.portrait_scene.angle,self.portrait_scene.walk)
        self.text((rect.x+18,rect.bottom-63),"VISOR DEL BEBÉ / EN VIVO",13,COLOR["muted"])
        self.text((rect.x+18,rect.bottom-40),
                  "DIRECCIÓN: "+ORIENTATIONS[self.robot.facing],14,COLOR["ink"])
        self.text((rect.x+18,rect.bottom-22),
                  "BATERÍA "+str(round(self.robot.battery))+"%",13,
                  COLOR["yellow"] if self.robot.battery<15 else COLOR["cyan"])

    def draw_speech_bubble(self, left):
        """Burbuja en el panel del personaje, con cola hacia su cámara."""
        if not self.bubble_text or self.elapsed>=self.bubble_until:
            return
        pg=self.pg
        font=self.fonts[13]
        padding=12
        width=left.width-24
        lines=self.wrap_text(self.bubble_text,font,width-2*padding,4)
        line_height=17
        bubble_h=max(36,len(lines)*line_height+19)
        rect=pg.Rect(left.x+12,left.y+60,width,bubble_h)
        if rect.bottom>left.y+138:
            rect.y=left.y+138-bubble_h
        fill=(235,248,255)
        outline=COLOR["pink"] if self.bubble_kind=="alert" else COLOR["cyan"]
        pg.draw.rect(self.screen,fill,rect,border_radius=11)
        pg.draw.rect(self.screen,outline,rect,1,border_radius=11)
        tip=(left.centerx,rect.bottom+8)
        pg.draw.polygon(self.screen,fill,[
            (left.centerx-9,rect.bottom-1),
            (left.centerx+9,rect.bottom-1),tip,
        ])
        for i,line in enumerate(lines):
            self.screen.blit(
                font.render(line,True,(25,46,63)),
                (rect.x+padding,rect.y+9+i*line_height))

    def draw_avatar_panel(self,rect):
        """Panel manual de articulaciones. Se dibuja sobre el visor del bebe."""
        if not self.avatar_panel or self.editor_mode:return
        pg=self.pg
        self.panel(rect,fill=(9,26,44),border=COLOR["yellow"])
        person=self.robot.human
        x=rect.x+12
        width=rect.width-24
        gap=5
        col=(width-gap)//2
        self.text((x,rect.y+11),"TU PERSONAJE / HUMANO",16,COLOR["yellow"])
        self.button("avatar_close","✕",rect.right-38,rect.y+7,26,26)
        self.text((x,rect.y+46),
                  "↑ AVANZA  ↓ RETROCEDE",13,COLOR["cyan"],width)
        self.text((x,rect.y+64),"← GIRA IZQ.  → GIRA DER.",13,COLOR["cyan"],width)
        self.text((x,rect.y+82),
                  "X="+str(person.x)+" Z="+str(person.z)+" · "+
                  ("SENTADO" if person.seated else "DE PIE"),
                  13,COLOR["ink"],width)
        self.text((x,rect.y+94),"ARTICULACIONES",14,COLOR["muted"])
        names=list(HUMAN_JOINTS)
        for i,name in enumerate(names):
            xx=x+(i%2)*(col+gap)
            yy=rect.y+117+(i//2)*30
            title=HUMAN_JOINTS[name]
            self.button("avatar_joint_"+name,title,xx,yy,col,26,
                        self.avatar_joint==name)
        angle=person.joints[self.avatar_joint]
        self.text((x,rect.y+273),
                  HUMAN_JOINTS[self.avatar_joint]+" · "+str(angle)+"°",
                  14,COLOR["yellow"],width)
        self.button("avatar_minus","− 10°",x,rect.y+298,col,31)
        self.button("avatar_plus","+ 10°",x+col+gap,rect.y+298,col,31)
        self.text((x,rect.y+345),"POSTURAS",14,COLOR["muted"])
        self.button("avatar_sit","SENTARSE",x,rect.y+370,col,32,person.seated)
        self.button("avatar_stand","LEVANTARSE",x+col+gap,rect.y+370,col,32)
        self.button("avatar_wave","SALUDAR",x,rect.y+408,col,32)
        self.button("avatar_squat","AGACHARSE",x+col+gap,rect.y+408,col,32)
        self.button("avatar_reset","RESTAURAR POSTURA",
                    x,rect.y+451,width,32)
        self.text((x,rect.bottom-52),"TANQUE: ←/→ GIRA · ↑/↓ AVANZA",
                  13,COLOR["muted"],width)
        self.text((x,rect.bottom-34),"AMBOT aprende mientras te mueves",
                  13,COLOR["green"],width)

    def draw_avatar_label(self):
        human=self.robot.human
        wx,wz=self.scene.world(human.x,human.z)
        pos=self.scene.project((wx,3.10,wz))
        if pos is None:return
        sx,sy=int(pos[0]),int(pos[1])
        if not self.view.collidepoint((sx,sy)):return
        title="TÚ · SENTADO" if human.seated else "TÚ · CONTROL"
        font=self.fonts[13]
        width=font.size(title)[0]+13
        rect=self.pg.Rect(sx-width//2,sy-15,width,22)
        self.pg.draw.rect(self.screen,(32,36,41),rect,border_radius=6)
        self.pg.draw.rect(self.screen,COLOR["yellow"],rect,1,border_radius=6)
        self.text((rect.x+6,rect.y+4),title,13,COLOR["yellow"])

    def draw_guides_and_skills(self, rect):
        """HUD de entrenamiento superpuesto sin ocultar el mundo completo."""
        pg=self.pg
        tr=self.robot.training
        x,y=rect.x+10,rect.bottom-137
        w=max(230,rect.width-20)
        h=125
        outer=pg.Rect(x,y,w,h)
        self.training_rect=outer
        pg.draw.rect(self.screen,(9,28,43),outer,border_radius=10)
        pg.draw.rect(self.screen,COLOR["line"],outer,1,border_radius=10)
        self.text((x+10,y+6),"GUIAS  1 ANDA · 2 DEX · 3 SOMA",13,COLOR["cyan"])
        focus=tr.guides[tr.focus] if tr.guides else None
        focus_status=(f"OBSERVANDO: {focus.name} / {focus.task}" if focus
                      else "SIN MAESTROS / EXPLORACION LIBRE")
        self.text((x+10,y+26),focus_status,13,COLOR["muted"],w-16)
        # Barras de aprendizaje: la memoria se actualiza por observacion
        # y practica, no por copiar el codigo de los profesores.
        keys=["caminar","agarrar","transportar","descansar","reconocer"]
        col_width=(w-20)/len(keys)
        for i,key in enumerate(keys):
            xx=int(x+10+i*col_width)
            label={"caminar":"MOVER","agarrar":"TOMAR","transportar":"LLEVAR",
                   "descansar":"REPOSAR","reconocer":"NOMBRES"}[key]
            value=tr.confidence[key]
            self.text((xx,y+47),label,13,COLOR["muted"],int(col_width-3))
            bg=pg.Rect(xx,y+67,max(12,int(col_width-8)),6)
            pg.draw.rect(self.screen,(29,58,77),bg,border_radius=3)
            fg=bg.copy()
            fg.width=int(bg.width*value)
            if fg.width>0:
                pg.draw.rect(self.screen,COLOR["cyan"] if value<.70 else COLOR["green"],
                             fg,border_radius=3)
            self.text((xx,y+76),str(int(value*100))+"%",13,COLOR["ink"])
        buttons=[("observe","Q MIRAR"),("grasp","F TOMAR"),
                 ("release","V SOLTAR"),("lie","L CAMA")]
        bh=24; by=y+96; gap=5
        bw=int((w-20-gap*3)/4)
        for i,(key,title) in enumerate(buttons):
            bx=x+10+i*(bw+gap)
            self.button(key,title,bx,by,bw,bh,key=="observe")

    def draw_guide_labels(self, rect):
        """Etiquetas ancladas a la posicion 3D de cada instructor."""
        pg=self.pg
        training=self.robot.training
        for idx,guide in enumerate(training.guides):
            wx,wz=self.scene.world(guide.x,guide.z)
            at=self.scene.project((wx,3.46,wz))
            if not at:
                continue
            px,py=int(at[0]),int(at[1])
            if not rect.collidepoint(px,py):
                continue
            name=f"{idx+1} {guide.name}"
            font=self.fonts[13]
            ww=font.size(name)[0]+12
            bubble=pg.Rect(px-ww//2,py-14,ww,21)
            pg.draw.rect(self.screen,(10,32,45),bubble,border_radius=6)
            pg.draw.rect(self.screen,guide.color,bubble,1,border_radius=6)
            self.text((bubble.x+6,bubble.y+3),name,13,guide.color)

    def poll_guides(self):
        """Reflejar demostraciones en las burbujas y el registro."""
        for event in list(self.robot.training.messages):
            if event["serial"]<=self.last_guide_event:
                continue
            self.last_guide_event=event["serial"]
            self.robot.brain.observe_guide(event,self.robot.training)
            self.add_log(event["teacher"],event["message"],COLOR["cyan"])
            guides=self.robot.training.guides
            if guides and event["teacher"]==guides[self.robot.training.focus].name:
                # La burbuja representa la interpretacion embrionaria del
                # bebe. El mensaje del profesor permanece en el registro.
                self.say("VI: "+event["baby"],duration=3.3)

    def add_log(self,who,text,color=None):
        for part in str(text).splitlines():
            if not part:
                continue
            self.messages.append((who,part,color or COLOR["muted"]))

    def execute(self,command,quiet=False):
        command=command.strip()
        if not command:return
        clean=normalize(command)
        if clean.startswith("arduino"):
            if clean in ("arduino","arduino estado"):
                answer=self.hardware.status()
            elif clean in ("arduino puertos","arduino buscar"):
                answer=self.hardware.available_ports()
            elif clean.startswith("arduino conectar "):
                answer=self.hardware.connect(command[len("arduino conectar "):])
            elif clean=="arduino desconectar":
                self.hardware.close()
                answer="Arduino desconectado. El cerebro continua simulando."
            elif clean in ("arduino bloquear","arduino stop","arduino emergencia"):
                answer=self.hardware.stop()
            elif clean=="arduino habilitar":
                answer=self.hardware.arm()
            else:
                answer=("Arduino: ESTADO, PUERTOS, CONECTAR COM4, "
                        "HABILITAR, BLOQUEAR, DESCONECTAR.")
            self.add_log("ARDUINO",answer,COLOR["yellow"])
            self.say(answer,5.0)
            return
        if clean in ("auto","automatico","modo automatico"):
            self.toggle_auto()
            return
        if clean in ("detener","alto","detente","stop"):
            self.auto=False
            self.hardware.stop()
        if not quiet:self.add_log("TU",command,COLOR["ink"])
        language=self.robot.language
        if clean in ("si","sí","correcto","confirmar","validar"):
            answer=language.confirm()
        elif clean in ("no","incorrecto","rechazar"):
            answer=language.reject()
        elif clean.startswith("corrige "):
            answer=language.correct(command[len("corrige "):])
        elif clean=="corrige":
            answer=language.reject()
        elif clean.startswith("hablar "):
            answer=language.propose(command[len("hablar "):])
        else:
            answer=self.robot.command(command)
            if answer.startswith("No entiendo ese comando"):
                answer=language.propose(command)
        if answer:
            mood="alert" if "SEGURIDAD" in answer.upper() else "normal"
            self.say(answer,5.5 if not quiet else 3.4,mood)
        if not quiet:self.add_log("AMBOT",answer,COLOR["green"])

    def toggle_editor(self, action="add"):
        if self.editor_mode:
            self.editor_mode=False
            self.auto=self.editor_resume_auto
            self.add_log("ENTORNO","Editor cerrado. Cambios guardados.",
                COLOR["green"])
            self.say("Distribucion guardada. "+(
                "Continuo aprendiendo." if self.auto else "Modo pausado."),4.2)
            return
        self.editor_resume_auto=self.auto
        self.auto=False
        self.hardware.stop()
        self._tank_held.clear()
        self.editor_mode=True
        self.editor_action=action if action in ("add","remove") else "add"
        self.dragging=False
        self.editor_hint=("Haz clic sobre el objeto que quieras quitar."
                          if self.editor_action=="remove"
                          else "Elige silla y haz clic en una casilla libre.")
        self.add_log("ENTORNO",self.editor_hint,COLOR["cyan"])
        self.say(self.editor_hint,5.8)

    def place_chair_at(self, screen_pos):
        if not self.editor_mode:
            return False
        if self.editor_action=="remove":
            target=self.scene.pick_object(screen_pos,self.robot)
            if target is None:
                ok,message=False,"Haz clic directamente sobre un objeto."
            elif target["kind"]=="protected":
                ok,message=False,"No puedes quitar a AMBOT ni su estructura."
            else:
                ok,message=self.robot.furniture.remove(target["kind"],target["key"])
            self.editor_hint=message
            if ok:
                self.robot.brain.episode("cambio_entorno",
                                         "Objeto retirado",message)
                self.robot.brain.save()
            self.add_log("ENTORNO",message,
                         COLOR["green"] if ok else COLOR["yellow"])
            self.say(message,4.4,"normal" if ok else "alert")
            return ok
        cell=self.scene.pick_floor(screen_pos)
        if cell is None:
            self.editor_hint="Haz clic en una casilla visible del suelo."
            return False
        ok,message=self.robot.furniture.place_object(
            self.editor_choice,*cell,self.editor_orientation)
        self.editor_hint=message
        self.add_log("ENTORNO",message,COLOR["green"] if ok else COLOR["yellow"])
        self.say(message,4.4,"normal" if ok else "alert")
        return ok

    def draw_editor_preview(self):
        if not self.editor_mode:
            return
        pg=self.pg
        mouse=pg.mouse.get_pos()
        if (not self.view.collidepoint(mouse)
                or self.editor_rect.collidepoint(mouse)
                or self.training_rect.collidepoint(mouse)
                or ("editor_toggle" in self.buttons
                    and self.buttons["editor_toggle"].collidepoint(mouse))):
            return
        if self.editor_action=="remove":
            target=self.scene.pick_object(mouse,self.robot)
            if target is None:return
            l,r,b,t,z0,z1=target["bounds"]
            coords=[self.scene.project((x,y,z))
                    for x in (l,r) for y in (b,t) for z in (z0,z1)]
            coords=[p for p in coords if p is not None]
            if coords:
                xs=[p[0] for p in coords]
                ys=[p[1] for p in coords]
                left=max(self.view.x+2,int(min(xs))-5)
                right=min(self.view.right-2,int(max(xs))+5)
                top=max(self.view.y+2,int(min(ys))-5)
                bottom=min(self.view.bottom-2,int(max(ys))+5)
                color=(COLOR["muted"] if target["kind"]=="protected"
                       else COLOR["pink"])
                if right>left+4 and bottom>top+4:
                    pg.draw.rect(self.screen,color,
                                 pg.Rect(left,top,right-left,bottom-top),
                                 2,border_radius=5)
                self.text((max(self.view.x+10,left),max(self.view.y+115,top-21)),
                          ("PROTEGIDO: " if target["kind"]=="protected"
                           else "QUITAR: ")+target["label"],13,color,
                          max(60,self.view.right-left-10))
            return
        cell=self.scene.pick_floor(mouse)
        if cell is None:return
        x,z=cell
        wx,wz=self.scene.world(x,z)
        span=TILE*.42
        pts=[self.scene.project((wx+dx,.045,wz+dz))
             for dx,dz in ((-span,-span),(-span,span),
                           (span,span),(span,-span))]
        if any(pt is None for pt in pts):return
        ok,reason=self.robot.furniture.can_place_object(
            self.editor_choice,x,z,self.editor_orientation)
        color=COLOR["green"] if ok else COLOR["pink"]
        pg.draw.polygon(self.screen,color,
                        [(int(p[0]),int(p[1])) for p in pts],3)
        center=self.scene.project((wx,.07,wz))
        if center:
            cx,cy=int(center[0]),int(center[1])
            pg.draw.circle(self.screen,color,(cx,cy),7,2)
            pg.draw.line(self.screen,color,(cx-10,cy),(cx+10,cy),2)
            pg.draw.line(self.screen,color,(cx,cy-10),(cx,cy+10),2)
            caption=("X"+str(x)+" Z"+str(z)+" · "+("LIBRE" if ok else "OCUPADO"))
            self.text((cx+11,cy-16),caption,13,color,
                      max(70,self.view.right-cx-15))

    def draw_editor_palette(self):
        pg=self.pg
        self.button("editor_toggle","✕ CERRAR" if self.editor_mode else "＋ AÑADIR",
                    self.view.right-302,self.view.y+12,142,29,
                    self.editor_mode and self.editor_action=="add")
        self.button("editor_remove","− QUITAR",self.view.right-152,
                    self.view.y+12,139,29,
                    self.editor_mode and self.editor_action=="remove")
        if not self.editor_mode:
            self.editor_rect=pg.Rect(0,0,1,1)
            return
        w=self.portrait_view.width-20
        r=pg.Rect(self.portrait_view.x+10,self.portrait_view.y+140,w,311)
        self.editor_rect=r
        self.panel(r,fill=(6,26,43),border=COLOR["cyan"],radius=11)
        self.text((r.x+12,r.y+8),"EDITOR DEL ENTORNO",16,COLOR["cyan"])
        half=(r.width-29)//2
        self.button("editor_mode_add","+ AÑADIR",r.x+10,r.y+34,half,29,
                    self.editor_action=="add")
        self.button("editor_mode_remove","− QUITAR",
                    r.x+19+half,r.y+34,half,29,
                    self.editor_action=="remove")
        if self.editor_action=="add":
            tabs=(("sillas","SILLAS"),("muebles","MUEBLES"),("objetos","OBJETOS"))
            tab_w=(r.width-26)//3
            for i,(name,label) in enumerate(tabs):
                self.button("editor_category_"+name,label,
                            r.x+10+i*(tab_w+3),r.y+72,tab_w,27,
                            self.editor_category==name)
            self.text((r.x+12,r.y+106),"Elige modelo y lugar en el suelo",13,
                      COLOR["muted"],r.width-20)
            if self.editor_category=="sillas":
                opts=(("silla_clasica","SILLA CLASICA","editor_style_clasica"),
                      ("silla_oficina","SILLA DE OFICINA","editor_style_oficina"),
                      ("silla_alta","SILLA ALTA","editor_style_alta"))
            elif self.editor_category=="muebles":
                opts=(("cama","CAMA","editor_kind_cama"),
                      ("mesa","MESA","editor_kind_mesa"),
                      ("armario","ARMARIO","editor_kind_armario"))
            else:
                opts=(("cubo","CUBO","editor_kind_cubo"),
                      ("pelota","PELOTA","editor_kind_pelota"),
                      ("bloque","BLOQUE","editor_kind_bloque"))
            for i,(kind,label,key) in enumerate(opts):
                self.button(key,
                            ("✓ " if self.editor_choice==kind else "  ")+label,
                            r.x+10,r.y+125+i*29,r.width-20,26,
                            self.editor_choice==kind)
            self.button("editor_rotate",
                        "↻ GIRAR 90° · "+ORIENTATIONS[self.editor_orientation],
                        r.x+10,r.y+219,r.width-20,28)
        else:
            self.text((r.x+12,r.y+80),"Clic en objeto 3D para quitarlo",13,
                      COLOR["pink"],r.width-24)
            self.text((r.x+12,r.y+111),"Sillas, camas, mesas, armarios",13,
                      COLOR["muted"],r.width-24)
            self.text((r.x+12,r.y+139),"Cubos, pelotas y bloques",13,
                      COLOR["muted"],r.width-24)
            self.text((r.x+12,r.y+165),"Maestros ANDA · DEX · SOMA",13,
                      COLOR["yellow"],r.width-24)
            self.text((r.x+12,r.y+193),"AMBOT y tu avatar protegidos",13,
                      COLOR["green"],r.width-24)
            self.text((r.x+12,r.y+223),"DESHACER recupera cambios",13,
                      COLOR["muted"],r.width-24)
        half=(r.width-30)//2
        self.button("editor_undo","↶ DESHACER",
                    r.x+10,r.y+269,half,32)
        self.button("editor_done","✓ LISTO",
                    r.x+20+half,r.y+269,half,32,True)
        self.text((self.view.x+15,self.view.bottom-160),
                  self.editor_hint or "Selecciona un objeto.",13,
                  COLOR["yellow"],self.view.width-30)

    def toggle_auto(self):
        if self.editor_mode:
            self.say("Cierra el editor para reanudar el aprendizaje.",3.5)
            return
        self.auto=not self.auto
        self.auto_clock=.45
        if not self.auto:self.hardware.stop()
        message="Estoy explorando por mi cuenta." if self.auto else "He detenido mi exploración."
        self.add_log("SISTEMA","Autonomo " + ("activado" if self.auto else "detenido") + ".",
                     COLOR["green"] if self.auto else COLOR["yellow"])
        self.say(message,duration=4.0)

    def handle_button(self,key):
        if key=="validation_yes":
            self.execute("si")
        elif key=="validation_no":
            self.execute("no")
        elif key=="validation_correct":
            self.input_focus=True
            self.input_value="corrige "
            self.say("Escribe CORRIGE y una de las acciones del mensaje.",5.0)
        elif key in ("avatar_toggle","avatar_close"):
            self.avatar_panel=not self.avatar_panel
        elif key.startswith("avatar_joint_"):
            joint=key[len("avatar_joint_"):]
            if joint in HUMAN_JOINTS:
                self.avatar_joint=joint
        elif key in ("avatar_plus","avatar_minus"):
            amount=10 if key=="avatar_plus" else -10
            message=self.robot.human.change_joint(self.avatar_joint,amount)
            self.add_log("TU CUERPO",message,COLOR["yellow"])
        elif key in ("avatar_sit","avatar_stand"):
            message=(self.robot.human.sit() if key=="avatar_sit"
                     else self.robot.human.stand())
            self.add_log("TU CUERPO",message,COLOR["yellow"])
            self.say(message,4.2)
        elif key in ("avatar_wave","avatar_squat","avatar_reset"):
            pose={"avatar_wave":"saludar","avatar_squat":"agacharse",
                  "avatar_reset":"reposo"}[key]
            message=self.robot.human.pose(pose)
            self.add_log("TU CUERPO",message,COLOR["yellow"])
        elif key=="editor_toggle":
            self.toggle_editor() if self.editor_mode else self.toggle_editor("add")
        elif key=="editor_done":
            self.toggle_editor()
        elif key=="editor_remove":
            if not self.editor_mode:
                self.toggle_editor("remove")
            else:
                self.editor_action="remove"
                self.editor_hint="Haz clic directamente sobre el objeto para quitarlo."
        elif key in ("editor_mode_add","editor_mode_remove"):
            self.editor_action="add" if key.endswith("add") else "remove"
            self.editor_hint=("Elige un objeto y haz clic en el suelo."
                              if self.editor_action=="add"
                              else "Haz clic directamente sobre el objeto que quieras quitar.")
        elif key.startswith("editor_category_"):
            self.editor_action="add"
            self.editor_category=key[len("editor_category_"):]
            self.editor_choice={"sillas":"silla_clasica","muebles":"cama",
                                "objetos":"pelota"}.get(
                                    self.editor_category,"silla_clasica")
            self.editor_hint="Selecciona modelo y haz clic en el suelo."
        elif key.startswith("editor_kind_"):
            choice=key[len("editor_kind_"):]
            if choice in ADD_CATALOG:
                self.editor_action="add"
                self.editor_choice=choice
                self.editor_hint="Haz clic en el suelo para anadir "+ADD_CATALOG[choice]+"."
        elif key.startswith("editor_style_"):
            self.editor_action="add"
            self.editor_category="sillas"
            self.editor_style=key[len("editor_style_"):]
            self.editor_choice="silla_"+self.editor_style
            self.editor_hint="Haz clic en el suelo para colocar "+CHAIR_STYLES[self.editor_style]+"."
        elif key=="editor_rotate":
            self.editor_action="add"
            self.editor_orientation=(self.editor_orientation+1)%4
            self.editor_hint="Orientacion: "+ORIENTATIONS[self.editor_orientation]+"."
        elif key=="editor_undo":
            ok,message=self.robot.furniture.undo()
            self.editor_hint=message
            self.say(message,4.0,"normal" if ok else "alert")
            self.add_log("ENTORNO",message,COLOR["green"] if ok else COLOR["yellow"])
        elif key=="auto":
            self.toggle_auto()
        elif key=="observe":
            self.execute("observar",False)
        elif key=="grasp":
            self.execute("agarrar",False)
        elif key=="release":
            self.execute("soltar",False)
        elif key=="lie":
            self.execute("acostarse",False)
        elif key=="stop":
            self._tank_held.clear()
            self.auto=False
            self.editor_resume_auto=False
            self.hardware.stop()
            self.add_log("SISTEMA","Robot en pausa.",COLOR["yellow"])
            self.say("Me detengo. Espero nuevas instrucciones.",4.0)
        elif key=="reset":
            self._tank_held.clear()
            self.editor_mode=False
            self.hardware.stop()
            self.robot.reset()
            self.auto=not self.smoke
            self.add_log("SISTEMA","Robot reiniciado. Memoria conservada.",COLOR["green"])
            self.say("He vuelto al inicio. ¡Vamos a descubrir!",5.0)
        else:
            actions={
                "forward":"avanza","left":"gira izquierda","right":"gira derecha",
                "back":"retrocede","explore":"explora","think":"piensa",
            }
            self.execute(actions.get(key,""),True)

    def drive_tank_key(self,key):
        """Control tipo RE1: delante/detras en rumbo; lados giran sin strafe."""
        pg=self.pg
        if key in (pg.K_UP,pg.K_DOWN,pg.K_LEFT,pg.K_RIGHT):
            human=self.robot.human
            if key==pg.K_UP:
                answer=human.advance()
            elif key==pg.K_DOWN:
                answer=human.advance(reverse=True)
            elif key==pg.K_LEFT:
                answer=human.turn("izquierda")
            else:
                answer=human.turn("derecha")
            # Los movimientos sostenidos no llenan el registro.
            if "No puedes" in answer or "sentado" in answer:
                self.add_log("TÚ",answer,COLOR["yellow"])
            return answer
        commands={
            pg.K_w:"avanza",pg.K_s:"retrocede",
            pg.K_a:"gira izquierda",pg.K_d:"gira derecha",
        }
        if key in commands:
            self.execute(commands[key],quiet=True)
            return self.robot.last_decision
        return ""

    def update_tank_controls(self,dt):
        """Repeticion temporal de teclas mantenidas; sin depender del SO."""
        if self.input_focus or self.editor_mode:
            self._tank_held.clear()
            return
        pg=self.pg
        actions={
            pg.K_UP:"forward",pg.K_DOWN:"back",
            pg.K_LEFT:"left",pg.K_RIGHT:"right",
            pg.K_w:"forward",pg.K_s:"back",
            pg.K_a:"left",pg.K_d:"right",
        }
        for key,state in list(self._tank_held.items()):
            if key not in actions:
                self._tank_held.pop(key,None)
                continue
            state["elapsed"]+=max(0.0,min(.07,dt))
            if state["elapsed"]>=state["delay"]:
                self.drive_tank_key(key)
                state["elapsed"]-=state["delay"]
                state["delay"]=TANK_HOLD_INTERVALS[actions[key]]

    def keydown(self,e):
        pg=self.pg
        if self.input_focus:
            if e.key==pg.K_RETURN or e.key==pg.K_KP_ENTER:
                if self.input_value.strip():
                    self.execute(self.input_value)
                self.input_value=""
            elif e.key==pg.K_ESCAPE:
                self.input_focus=False
            elif e.key==pg.K_BACKSPACE:
                self.input_value=self.input_value[:-1]
            elif e.unicode and e.unicode.isprintable() and len(self.input_value)<600:
                self.input_value+=e.unicode
            return
        if self.editor_mode and e.key==pg.K_ESCAPE:
            self._tank_held.clear()
            self.toggle_editor()
            return
        tank_keys=(pg.K_UP,pg.K_DOWN,pg.K_LEFT,pg.K_RIGHT,
                   pg.K_w,pg.K_s,pg.K_a,pg.K_d)
        if e.key in tank_keys:
            if self.editor_mode:
                self.add_log("SISTEMA","Cierra el editor para moverte.",
                             COLOR["yellow"])
            elif e.key not in self._tank_held:
                self._tank_held[e.key]={
                    "elapsed":0.0,"delay":self._tank_initial_delay
                }
                self.drive_tank_key(e.key)
            return
        if e.key==pg.K_e:
            self.execute("explora",True)
        elif e.key in (pg.K_q,pg.K_f,pg.K_v,pg.K_l,pg.K_i,pg.K_p):
            self.execute({
                pg.K_q:"observar",pg.K_f:"agarrar",pg.K_v:"soltar",
                pg.K_l:"acostarse",pg.K_i:"identificar",pg.K_p:"progreso",
            }[e.key],quiet=False)
        elif e.key in (pg.K_1,pg.K_2,pg.K_3):
            index=e.key-pg.K_1
            self.robot.training.focus=index
            self.execute("guia "+str(index+1),quiet=False)
        elif e.key==pg.K_SPACE:
            self.toggle_auto()
        elif e.key==pg.K_r:
            self.handle_button("reset")
        elif e.key==pg.K_TAB:
            self.input_focus=True

    def events(self):
        pg=self.pg
        for e in pg.event.get():
            if e.type==pg.QUIT:return False
            if e.type==pg.VIDEORESIZE:
                self.screen=pg.display.set_mode((max(1120,e.w),max(650,e.h)),pg.RESIZABLE)
            if e.type==pg.KEYDOWN:self.keydown(e)
            if e.type==pg.KEYUP:
                self._tank_held.pop(e.key,None)
            if e.type==getattr(pg,"WINDOWFOCUSLOST",-987654):
                self._tank_held.clear()
            if e.type==pg.MOUSEBUTTONDOWN and e.button==1:
                if self.input_rect.collidepoint(e.pos):
                    self._tank_held.clear()
                    self.input_focus=True
                    continue
                self.input_focus=False
                key=next((name for name,rect in self.buttons.items() if rect.collidepoint(e.pos)),None)
                if key:
                    self.handle_button(key)
                elif self.editor_mode:
                    if (not self.editor_rect.collidepoint(e.pos)
                            and not self.training_rect.collidepoint(e.pos)
                            and self.view.collidepoint(e.pos)):
                        self.place_chair_at(e.pos)
                elif self.view.collidepoint(e.pos):
                    self.dragging=True
                    self.mouse=e.pos
            if e.type==pg.MOUSEBUTTONUP and e.button==1:self.dragging=False
            if e.type==pg.MOUSEMOTION and self.dragging:
                dx=e.pos[0]-self.mouse[0]
                dy=e.pos[1]-self.mouse[1]
                self.scene.yaw-=dx*.008
                self.scene.pitch=max(.18,min(1.37,self.scene.pitch+dy*.007))
                self.mouse=e.pos
            if e.type==pg.MOUSEWHEEL:
                self.scene.distance=max(8,min(34,self.scene.distance-e.y*1.2))
        return True

    def draw(self,dt):
        pg=self.pg
        surf=self.screen
        w,h=surf.get_size()
        surf.fill(COLOR["bg"])
        self.text((23,22),"AMBOT",27,COLOR["ink"])
        self.text((132,30),"ARCHMOBA ROBOTICS  /  LABORATORIO 3D",14,COLOR["muted"])
        self.text((w-200,30),"PYTHON NATIVO  ·  v"+APP_VERSION,14,COLOR["cyan"])
        # Tres paneles: visor de personaje / mundo 3D / cerebro.
        gap=13
        left_w=max(225,min(265,int(w*.205)))
        right_w=max(315,min(355,int(w*.27)))
        left=pg.Rect(20,83,left_w,h-146)
        center_x=left.right+gap
        center_w=w-center_x-right_w-gap-20
        self.view=pg.Rect(center_x,83,center_w,h-146)
        side=pg.Rect(self.view.right+gap,83,right_w,h-146)
        self.scene.render(surf,self.view,self.robot,dt,self.elapsed)
        self.draw_editor_preview()
        self.draw_guide_labels(self.view)
        self.draw_avatar_label()
        self.portrait_view=left
        self.draw_character_viewer(left)
        self.draw_speech_bubble(left)
        # Vista e indicadores superpuestos.
        stamp=pg.Rect(self.view.x+13,self.view.y+12,262,29)
        pg.draw.rect(surf,COLOR["panel"],stamp,border_radius=7)
        label = ("●  HABITACION INICIAL | 3D" if self.robot.location() == ROOM_NAME
                 else "●  PASILLO | ENTORNO 3D")
        self.text((stamp.x+10,stamp.y+6),label,14,COLOR["cyan"])
        self.text((self.view.x+15,self.view.y+46),"RATÓN: GIRAR CÁMARA · RUEDA: ZOOM",13,COLOR["muted"])
        self.text((self.view.x+15,self.view.y+67),
                  "CURIOSIDAD: "+self.robot.brain.current_goal,13,COLOR["cyan"],
                  self.view.width-30)
        question=self.robot.brain.pending_question()
        if question:
            self.text((self.view.x+15,self.view.y+86),
                      "PREGUNTA: "+question,13,COLOR["yellow"],
                      self.view.width-30)
        self.panel(side)
        x=side.x+17
        inner=side.width-34
        self.text((x,side.y+14),"CEREBRO / AMBOT BEBÉ",20,COLOR["ink"])
        self.text((x,side.y+44),"●  "+self.robot.location()+"  •  SENSOR ACTIVO",13,COLOR["green"])
        hw="ARDUINO: CONECTADO" if self.hardware.connected else "ARDUINO: SIN CONEXION"
        self.text((self.view.x+15,self.view.y+105),hw,13,
                  COLOR["yellow"] if self.hardware.connected else COLOR["muted"],
                  self.view.width-30)
        s=self.robot.state()
        self.text((x,side.y+72),"BATERÍA",14,COLOR["muted"])
        self.text((side.right-69,side.y+72),str(s["bateria"])+"%",14,COLOR["ink"])
        bar=pg.Rect(x,side.y+94,inner,9)
        pg.draw.rect(surf,(27,51,72),bar,border_radius=5)
        filled=bar.copy();filled.width=int(inner*s["bateria"]/100)
        if filled.width>0:
            pg.draw.rect(surf,COLOR["green"] if s["bateria"]>15 else COLOR["pink"],filled,border_radius=5)
        stat_y=side.y+119
        self.text((x,stat_y),"DISTANCIA FRONTAL",13,COLOR["muted"])
        self.text((side.right-89,stat_y),str(s["sensor_cm"])+" cm",16,COLOR["cyan"])
        self.text((x,stat_y+29),"POSICIÓN",13,COLOR["muted"])
        self.text((side.right-110,stat_y+29),f'X{s["posicion"][0]} / Z{s["posicion"][1]}',16,COLOR["ink"])
        self.text((x,stat_y+58),"ORIENTACIÓN",13,COLOR["muted"])
        self.text((side.right-98,stat_y+58),s["orientacion"],16,COLOR["cyan"])
        pg.draw.line(surf,COLOR["line"],(x,stat_y+89),(side.right-17,stat_y+89),1)
        self.text((x,stat_y+101),"META / PENSAMIENTO",13,COLOR["muted"])
        thought=self.robot.brain.current_goal+" | "+self.robot.last_decision
        if len(thought)>75:thought=thought[:74]+"…"
        self.text((x,stat_y+122),thought[:45],14,COLOR["ink"],inner)
        self.text((x,stat_y+141),thought[45:90],14,COLOR["ink"],inner)
        button_top=stat_y+171
        gap=8
        bw=(inner-gap)//2
        self.buttons={}
        self.button("forward","↑ AVANZAR",x,button_top,bw,35,True)
        self.button("left","↶ IZQUIERDA",x+bw+gap,button_top,bw,35)
        self.button("right","↷ DERECHA",x,button_top+42,bw,35)
        self.button("back","↓ RETROCEDER",x+bw+gap,button_top+42,bw,35)
        self.button("explore","◆ EXPLORAR",x,button_top+84,bw,35)
        self.button("think","◉ PENSAR",x+bw+gap,button_top+84,bw,35)
        self.button("auto","Ⅱ PAUSAR" if self.auto else "▶ AUTO",x,button_top+126,bw,35,self.auto)
        self.button("stop","■ DETENER",x+bw+gap,button_top+126,bw,35)
        self.button("reset","↻ REINICIAR",x,button_top+168,inner,32)
        logy=button_top+209
        inputy=side.bottom-56
        if self.robot.language.pending:
            keys=(("validation_yes","✓ SI"),
                  ("validation_no","✗ NO"),
                  ("validation_correct","✎ CORREGIR"))
            gap=5
            segment=(inner-gap*2)//3
            for idx,(key,label) in enumerate(keys):
                self.button(key,label,x+idx*(segment+gap),inputy-33,
                            segment,27,key=="validation_yes")
        if inputy>logy+24:
            self.text((x,logy),"REGISTRO DE ACTIVIDAD",13,COLOR["muted"])
            log_end=inputy-38 if self.robot.language.pending else inputy
            available=max(0,(log_end-logy-18)//19)
            for idx,(who,msg,col) in enumerate(list(self.messages)[-available:]):
                self.text((x,logy+20+idx*19),who+": "+msg,13,col,inner)
        self.input_rect=pg.Rect(x,inputy,inner,41)
        pg.draw.rect(surf,COLOR["panel2"],self.input_rect,border_radius=8)
        pg.draw.rect(surf,COLOR["cyan"] if self.input_focus else COLOR["line"],
                     self.input_rect,2 if self.input_focus else 1,border_radius=8)
        value=self.input_value
        if len(value)>38:value="…"+value[-37:]
        if not value:value="Escribe un comando y pulsa ENTER"
        self.text((x+9,inputy+12),value,13,COLOR["ink"] if self.input_value else COLOR["muted"],inner-20)
        self.draw_guides_and_skills(self.view)
        self.button("avatar_toggle",
                    "VISOR AMBOT" if self.avatar_panel else "MI CUERPO · PANEL",
                    self.view.x+15,self.view.y+130,176,30,
                    self.avatar_panel)
        self.draw_avatar_panel(left)
        self.draw_editor_palette()
        self.text((23,h-45),"TANQUE: FLECHAS TÚ · WASD AMBOT · IZQ/DER GIRA · ARRIBA/ABAJO AVANZA/RETROCEDE",
                  14,COLOR["muted"])
        self.text((w-220,h-45),"ARCHMOBA / AMBOT "+APP_VERSION,14,COLOR["cyan"])
        pg.display.flip()

    def run(self,frames=0):
        count=0
        running=True
        while running:
            dt=min(.05,self.clock.tick(60)/1000.0)
            self.elapsed+=dt
            running=self.events()
            self.update_tank_controls(dt)
            self.hardware.poll()
            self.robot.training.update(dt)
            self.poll_guides()
            if self.auto:
                self.auto_clock+=dt
                if self.auto_clock>=.57:
                    self.auto_clock=0
                    action=self.robot.brain.autonomous_step()
                    if self.hardware.armed:
                        motor={"caminar":"FORWARD","transportar":"FORWARD"}.get(
                            self.robot.brain.last_action)
                        if motor:
                            self.hardware.send_motion(motor)
                    self.say(self.robot.brain.last_thought,duration=2.5,
                             kind="alert" if "bateria" in self.robot.last_decision.lower() else "normal")
                    if self.robot.battery<1.5:
                        self.auto=False
                        self.say("Batería baja, necesito detenerme.",duration=6.0,kind="alert")
                    if self.robot.steps%4==0:
                        self.add_log("AUTO",action,COLOR["cyan"])
            self.draw(dt)
            count+=1
            if frames and count>=frames:
                running=False
        self.robot.brain.save()
        self.robot.human.save()
        self.robot.furniture.save()
        self.hardware.close()
        self.pg.quit()


def main(argv=None):
    parser=argparse.ArgumentParser(description="AMBOT - laboratorio 3D en Python")
    parser.add_argument("--smoke",action="store_true",help="Prueba de ventana sin interacción")
    parser.add_argument("--frames",type=int,default=12,help="Fotogramas en prueba")
    parser.add_argument("--no-install",action="store_true",help="No instalar pygame-ce")
    parser.add_argument("--train-steps",type=int,default=0,
                        help="Practicar sin ventana durante N pasos de simulacion")
    args=parser.parse_args(argv)
    if args.train_steps>0:
        robot=Robot()
        last=0
        steps=min(args.train_steps,100000)
        for i in range(steps):
            robot.training.update(.05)
            for event in list(robot.training.messages):
                if event["serial"]>last:
                    last=event["serial"]
                    robot.brain.observe_guide(event,robot.training)
            if i%10==0:
                robot.brain.autonomous_step()
        robot.brain.save()
        print("AMBOT / entrenamiento autonomo: "+str(steps)+" pasos. "
              +robot.brain.summary())
        return
    if args.smoke:
        os.environ.setdefault("SDL_VIDEODRIVER","dummy")
        os.environ.setdefault("SDL_AUDIODRIVER","dummy")
    pygame=ensure_pygame(no_install=args.no_install)
    app=DesktopApp(pygame,smoke=args.smoke)
    app.run(frames=max(1,args.frames) if args.smoke else 0)


def _show_failure(details):
    try:
        if os.name=="nt":
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,details[-2400:],"AMBOT - Error de inicio",0x10)
        else:
            print(details,file=sys.stderr)
    except Exception:
        print(details,file=sys.stderr)


if __name__=="__main__":
    try:
        main()
    except BaseException:
        message=traceback.format_exc()
        try:
            LOG_PATH.parent.mkdir(parents=True,exist_ok=True)
            LOG_PATH.write_text("AMBOT v"+APP_VERSION+" - fallo\n"+message,encoding="utf-8")
        except OSError:
            pass
        _show_failure(message)
        sys.exit(1)
