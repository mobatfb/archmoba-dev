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
import os
import subprocess
import sys
import time
import traceback
import unicodedata
from collections import deque
from pathlib import Path

APP_NAME = "AMBOT"
APP_VERSION = "0.2.0"
APP_UPDATE_DATE = "05/11/2026"
APP_UPDATE_TIME = "01:40"
TITLE = "AMBOT | ARCHMOBA ROBOTICS"
ROOT = Path(__file__).resolve().parent
USER_ROOT = (Path(os.environ["LOCALAPPDATA"]) / "ARCHMOBA" / "AMBOT"
             if os.environ.get("LOCALAPPDATA") else Path.home() / ".archmoba" / "ambot")
MEMORY_PATH = USER_ROOT / "memoria.json"
LOG_PATH = USER_ROOT / "launch.log"
DEPENDENCIES = USER_ROOT / "dependencies"

WORLD = (
    "##############",
    "#............#",
    "#..##........#",
    "#............#",
    "#......#.....#",
    "#............#",
    "#..#.........#",
    "#........##..#",
    "#............#",
    "#............#",
    "##############",
)
TILE = 1.35
DIRECTIONS = ((0, -1), (1, 0), (0, 1), (-1, 0))
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

    def reset(self):
        self.x, self.z = 6, 5
        self.facing = 1
        self.battery = 100.0
        self.steps = 0
        self.visits = {(self.x, self.z): 1}
        self.last_decision = "Estoy observando el entorno. Mis movimientos son simulados."

    def free(self, x, z):
        return 0 <= z < len(WORLD) and 0 <= x < len(WORLD[z]) and WORLD[z][x] == "."

    def front_distance(self):
        dx, dz = DIRECTIONS[self.facing]
        x, z = self.x + dx, self.z + dz
        free = 0
        while self.free(x, z):
            free += 1
            x, z = x + dx, z + dz
        return free * 40 + 10

    def state(self):
        return {
            "posicion": (self.x, self.z),
            "orientacion": ORIENTATIONS[self.facing],
            "bateria": round(self.battery, 1),
            "pasos": self.steps,
            "sensor_cm": self.front_distance(),
            "memoria": len(self.facts),
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
        if self.battery < 1.5:
            return "SEGURIDAD: bateria baja. Movimiento bloqueado."
        dx, dz = DIRECTIONS[self.facing]
        if reverse:
            dx, dz = -dx, -dz
        if not self.free(self.x + dx, self.z + dz):
            return "SEGURIDAD: hay un obstaculo. No avanzo."
        self.x += dx
        self.z += dz
        self.steps += 1
        self.battery = max(0.0, round(self.battery - 1.5, 2))
        self.visits[(self.x, self.z)] = self.visits.get((self.x, self.z), 0) + 1
        return "Movimiento seguro. Posicion: X=" + str(self.x) + " Z=" + str(self.z) + "."

    def decide(self):
        if self.battery < 1.5:
            return "detener", "Bateria insuficiente: debo detenerme."
        options = []
        for direction, (dx, dz) in enumerate(DIRECTIONS):
            x, z = self.x + dx, self.z + dz
            if self.free(x, z):
                turn = (direction - self.facing) % 4
                turn_cost = 0 if turn == 0 else (1 if turn in (1, 3) else 2)
                options.append((self.visits.get((x, z), 0), turn_cost, turn == 3, direction))
        if not options:
            return "detener", "No encuentro ninguna salida segura."
        _, _, _, direction = min(options)
        if direction == self.facing:
            return "avanzar", "Hay paso libre y prefiero recorrer una celda poco visitada."
        rotation = (direction - self.facing) % 4
        if rotation == 3:
            return "izquierda", "Detecto un recorrido menos visitado a la izquierda."
        return "derecha", "Cambio de direccion para explorar sin chocar."

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
        for z, row in enumerate(WORLD):
            if z == self.z:
                row = row[:self.x] + symbols[self.facing] + row[self.x + 1:]
            rows.append(row)
        return "\n".join(rows)

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
            return "W avanzar, S retroceder, A/D girar, E explorar, ESPACIO auto, R reiniciar; recuerda clave = valor."
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
        self.pitch = 0.79
        self.distance = 21.0
        self.rx, self.rz = 6.0, 5.0
        self.angle = math.pi/2
        self.walk = 0.0
        self.target = (0, .5, 0)
        self.camera = (0, 0, 0)
        self.forward = (0, 0, 0)
        self.right = (0, 0, 0)
        self.up = (0, 0, 0)
        self.focal = 1
        self.rect = pg.Rect(0, 0, 960, 600)
        self.faces = []

    @staticmethod
    def world(x, z):
        return ((x-(len(WORLD[0])-1)/2)*TILE, (z-(len(WORLD)-1)/2)*TILE)

    def orient(self, facing):
        return ((0, math.pi/2, math.pi, -math.pi/2)[facing])

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
                    self.quad(((l,0,back),(l,0,front),(r,0,front),(r,0,back)),
                              COLOR["floor1"] if (x+z)%2 else COLOR["floor2"])
                    if (x+3*z)%13==0:
                        self.line((px-.12,.013,pz),(px+.12,.013,pz),COLOR["blue"],.025)
                else:
                    edge = x in (0,len(row)-1) or z in (0,len(WORLD)-1)
                    height = .66 if edge else 1.35
                    self.box(px,0,pz,TILE-.04,height,TILE-.04,
                             COLOR["wall"] if edge else COLOR["inner"],neon=True)
                    if not edge:
                        self.box(px,height,pz,.13,.05,.13,COLOR["pink"])
        # Sensor virtual orientado: detecta la siguiente pared.
        dx,dz=DIRECTIONS[robot.facing]
        bx,bz=self.world(self.rx,self.rz)
        d=min(3.0,robot.front_distance()/40.0)*TILE
        self.line((bx,.08,bz),(bx+dx*d,.08,bz+dz*d),COLOR["cyan"],.04)
        self.ball((bx+dx*d,.08,bz+dz*d),.09,COLOR["pink"])

    def build_robot(self, robot, dt, elapsed):
        speed=min(1,dt*9)
        oldx,oldz=self.rx,self.rz
        self.rx+=(robot.x-self.rx)*speed
        self.rz+=(robot.z-self.rz)*speed
        moved=abs(oldx-self.rx)+abs(oldz-self.rz)>.001
        self.walk+=dt*(12 if moved else 2.5)
        target=self.orient(robot.facing)
        diff=(target-self.angle+math.pi)%(2*math.pi)-math.pi
        self.angle+=diff*speed
        bx,bz=self.world(self.rx,self.rz)
        dx,dz=DIRECTIONS[robot.facing]
        fwd=(math.sin(self.angle),-math.cos(self.angle))
        side=(-fwd[1],fwd[0])
        bob=abs(math.sin(self.walk))*.04 if moved else math.sin(elapsed*1.6)*.012
        def p(sideways,height,forward=0):
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
                      COLOR["blue"],.029)
        swing=math.sin(self.walk)*(.29 if moved else .025)
        for sign in (-1,1):
            hip=(sign*.15,1.0,0)
            knee=(sign*.20,.55,-swing*sign*.45)
            foot=(sign*.22,.11,-swing*sign*.70)
            bone(hip,knee,COLOR["ink"],.11)
            bone(knee,foot,COLOR["cyan"],.095)
            node(knee,.1,COLOR["blue"])
            node(foot,.12,COLOR["ink"])
        bone((0,1.0,0),(0,1.78,0),COLOR["ink"],.19)
        bone((-.29,1.77,0),(.29,1.77,0),COLOR["cyan"],.105)
        for sign in (-1,1):
            shoulder=(sign*.29,1.77,0)
            elbow=(sign*.47,1.36,swing*sign*.5)
            hand=(sign*.52,1.02,swing*sign*.7)
            bone(shoulder,elbow,COLOR["cyan"],.095)
            bone(elbow,hand,COLOR["ink"],.09)
            node(elbow,.1,COLOR["blue"])
            node(hand,.1,COLOR["ink"])
        node((0,1.48,-.13),.13,COLOR["pink"])
        bone((0,1.78,0),(0,2.02,0),COLOR["cyan"],.075)
        node((0,2.31,0),.28,COLOR["ink"])
        node((-.105,2.33,.23),.053,COLOR["blue"])
        node((.105,2.33,.23),.053,COLOR["blue"])
        bone((0,2.58,0),(0,2.78,0),COLOR["cyan"],.035)
        node((0,2.81,0),.066,COLOR["pink"])

    def render(self, surface, rect, robot, dt, elapsed):
        pg=self.pg
        pg.draw.rect(surface,(5,16,29),rect,border_radius=12)
        self.camera_update(rect)
        self.faces=[]
        self.build_world(robot)
        self.build_robot(robot,dt,elapsed)
        # Dibujo de atras hacia delante: perspectiva de camara orbital.
        self.faces.sort(key=lambda x:x[0],reverse=True)
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
        pg.draw.rect(surface,COLOR["line"],rect,2,border_radius=12)


class DesktopApp:
    def __init__(self, pg, smoke=False):
        self.pg=pg
        self.smoke=smoke
        pg.init()
        if smoke:
            self.screen=pg.display.set_mode((1120,690))
        else:
            self.screen=pg.display.set_mode((1220,735),pg.RESIZABLE)
        pg.display.set_caption(TITLE + " v" + APP_VERSION)
        self.clock=pg.time.Clock()
        self.fonts={i:pg.font.SysFont("Segoe UI",i) for i in (13,14,16,17,18,20,23,27)}
        self.robot=Robot()
        self.scene=Scene3D(pg)
        self.auto=False
        self.auto_clock=0.0
        self.elapsed=0.0
        self.input_focus=False
        self.input_value=""
        self.messages=deque(maxlen=24)
        self.messages.append(("SISTEMA","AMBOT listo. Cerebro local y cuerpo 3D.",COLOR["green"]))
        self.messages.append(("AYUDA","W/A/S/D mover · E explorar · ESPACIO auto",COLOR["muted"]))
        self.dragging=False
        self.mouse=(0,0)
        self.buttons={}
        self.input_rect=pg.Rect(0,0,1,1)
        self.view=pg.Rect(20,84,800,500)

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

    def add_log(self,who,text,color=None):
        for part in str(text).splitlines():
            if not part:
                continue
            self.messages.append((who,part,color or COLOR["muted"]))

    def execute(self,command,quiet=False):
        command=command.strip()
        if not command:return
        clean=normalize(command)
        if clean in ("auto","automatico","modo automatico"):
            self.toggle_auto()
            return
        if clean in ("detener","alto","detente","stop"):
            self.auto=False
        if not quiet:self.add_log("TU",command,COLOR["ink"])
        answer=self.robot.command(command)
        if not quiet:self.add_log("AMBOT",answer,COLOR["green"])
        self.scene.walk=self.scene.walk

    def toggle_auto(self):
        self.auto=not self.auto
        self.auto_clock=.45
        self.add_log("SISTEMA","Autonomo " + ("activado" if self.auto else "detenido") + ".",
                     COLOR["green"] if self.auto else COLOR["yellow"])

    def handle_button(self,key):
        if key=="auto":
            self.toggle_auto()
        elif key=="stop":
            self.auto=False
            self.add_log("SISTEMA","Robot en pausa.",COLOR["yellow"])
        elif key=="reset":
            self.auto=False
            self.robot.reset()
            self.add_log("SISTEMA","Robot reiniciado. Memoria conservada.",COLOR["green"])
        else:
            actions={
                "forward":"avanza","left":"gira izquierda","right":"gira derecha",
                "back":"retrocede","explore":"explora","think":"piensa",
            }
            self.execute(actions.get(key,""),True)

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
            elif e.unicode and e.unicode.isprintable() and len(self.input_value)<150:
                self.input_value+=e.unicode
            return
        actions={
            pg.K_w:"avanza", pg.K_UP:"avanza", pg.K_s:"retrocede", pg.K_DOWN:"retrocede",
            pg.K_a:"gira izquierda", pg.K_LEFT:"gira izquierda",
            pg.K_d:"gira derecha", pg.K_RIGHT:"gira derecha",
            pg.K_e:"explora",
        }
        if e.key in actions:
            self.execute(actions[e.key],True)
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
                self.screen=pg.display.set_mode((max(980,e.w),max(650,e.h)),pg.RESIZABLE)
            if e.type==pg.KEYDOWN:self.keydown(e)
            if e.type==pg.MOUSEBUTTONDOWN and e.button==1:
                if self.input_rect.collidepoint(e.pos):
                    self.input_focus=True
                    continue
                self.input_focus=False
                key=next((name for name,rect in self.buttons.items() if rect.collidepoint(e.pos)),None)
                if key:
                    self.handle_button(key)
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
        side_w=max(320,min(355,w//3))
        self.view=pg.Rect(20,83,w-side_w-53,h-146)
        side=pg.Rect(self.view.right+15,83,w-self.view.right-35,h-146)
        self.scene.render(surf,self.view,self.robot,dt,self.elapsed)
        # Vista e indicadores superpuestos.
        stamp=pg.Rect(self.view.x+13,self.view.y+12,206,29)
        pg.draw.rect(surf,COLOR["panel"],stamp,border_radius=7)
        self.text((stamp.x+10,stamp.y+6),"●  ENTORNO SIMULADO 3D",14,COLOR["cyan"])
        self.text((self.view.x+15,self.view.bottom-30),"ARRASTRA: GIRAR CÁMARA    ·    RUEDA: ZOOM",13,COLOR["muted"])
        self.panel(side)
        x=side.x+17
        inner=side.width-34
        self.text((x,side.y+14),"CEREBRO / AMBOT",20,COLOR["ink"])
        self.text((x,side.y+44),"●  ACTIVO     •     SENSOR VIRTUAL",13,COLOR["green"])
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
        self.text((x,stat_y+101),"ÚLTIMA DECISIÓN",13,COLOR["muted"])
        thought=self.robot.last_decision
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
        if inputy>logy+24:
            self.text((x,logy),"REGISTRO DE ACTIVIDAD",13,COLOR["muted"])
            available=max(0,(inputy-logy-18)//19)
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
        self.text((23,h-45),"W / A / S / D  ·  E EXPLORAR  ·  ESPACIO AUTO  ·  R REINICIAR  ·  TAB ESCRIBIR",
                  14,COLOR["muted"])
        self.text((w-230,h-45),"ARCHMOBA  /  AMBOT 0.2",14,COLOR["cyan"])
        pg.display.flip()

    def run(self,frames=0):
        count=0
        running=True
        while running:
            dt=min(.05,self.clock.tick(60)/1000.0)
            self.elapsed+=dt
            running=self.events()
            if self.auto:
                self.auto_clock+=dt
                if self.auto_clock>=.57:
                    self.auto_clock=0
                    action=self.robot.explore()
                    if self.robot.battery<1.5:
                        self.auto=False
                    if self.robot.steps%4==0:
                        self.add_log("AUTO",action,COLOR["cyan"])
            self.draw(dt)
            count+=1
            if frames and count>=frames:
                running=False
        self.pg.quit()


def main(argv=None):
    parser=argparse.ArgumentParser(description="AMBOT - laboratorio 3D en Python")
    parser.add_argument("--smoke",action="store_true",help="Prueba de ventana sin interacción")
    parser.add_argument("--frames",type=int,default=12,help="Fotogramas en prueba")
    parser.add_argument("--no-install",action="store_true",help="No instalar pygame-ce")
    args=parser.parse_args(argv)
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
