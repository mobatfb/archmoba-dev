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
APP_VERSION = "0.3.0"
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
        self.last_decision = "Estoy en una habitacion nueva. Puedo explorarla sin chocar."

    def free(self, x, z):
        return (
            0 <= z < len(WORLD)
            and 0 <= x < len(WORLD[z])
            and WORLD[z][x] == "."
            and (x, z) not in FURNITURE_CELLS
        )

    def location(self):
        if (self.x, self.z) in ROOM_CELLS:
            return ROOM_NAME
        return "PUERTA" if (self.x, self.z) == ROOM_DOOR else "PASILLO"
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
            "lugar": self.location(),
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
        marks = {"cama": "C", "mesa": "M", "silla": "S", "armario": "A"}
        for z, row in enumerate(WORLD):
            chars = list(row)
            for name, cells in ROOM_OBJECTS.items():
                for x, object_z in cells:
                    if object_z == z:
                        chars[x] = marks[name]
            if z == ROOM_DOOR[1]:
                chars[ROOM_DOOR[0]] = "P"
            if z == self.z:
                chars[self.x] = symbols[self.facing]
            rows.append("".join(chars))
        return "\n".join(rows) + "\nC=cama M=mesa S=silla A=armario P=puerta"
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
        self.pitch = 0.88
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

    def build_room_details(self):
        """Muebles de dormitorio y marco de puerta para la nueva habitacion."""
        # Alfombra central y costuras neon.
        x, z = self.world(5.8, 5.5)
        rx, rz = TILE*1.20, TILE*.82
        self.quad(((x-rx,.020,z-rz),(x-rx,.020,z+rz),
                   (x+rx,.020,z+rz),(x+rx,.020,z-rz)), COLOR["rug"])
        for q in range(4):
            sx=x-rx+(2*rx)*q/3
            self.line((sx,.027,z-rz),(sx,.027,z+rz),COLOR["blue"],.024)

        # Cama y almohadas en la esquina inferior izquierda.
        bx,bz=self.world(4.5,7)
        self.box(bx,.10,bz,TILE*1.95,.21,TILE*.86,COLOR["wood"],neon=True)
        self.box(bx,.33,bz,TILE*1.83,.26,TILE*.77,COLOR["bed"])
        self.box(bx-TILE*.64,.60,bz,TILE*.35,.11,TILE*.49,COLOR["ink"])
        self.box(bx+TILE*.58,.58,bz,TILE*.38,.08,TILE*.49,COLOR["cyan"])
        self.box(bx-TILE*.96,.08,bz,.09,.83,TILE*.87,COLOR["wood"])

        # Mesa con libro, lampara y cuatro patas.
        tx,tz=self.world(4,4)
        for dx in (-.49,.49):
            for dz in (-.31,.31):
                self.box(tx+dx,0,tz+dz,.07,.74,.07,COLOR["wood"])
        self.box(tx,.74,tz,1.18,.12,.82,COLOR["wood"],neon=True)
        self.box(tx+.11,.89,tz-.10,.34,.04,.23,COLOR["cyan"])
        self.line((tx-.36,.89,tz+.11),(tx-.36,1.20,tz+.11),COLOR["ink"],.065)
        self.box(tx-.36,1.18,tz+.11,.26,.09,.25,COLOR["window"])

        # Silla delante de la mesa.
        cx,cz=self.world(4,5)
        self.box(cx,.43,cz,.74,.11,.68,COLOR["wood"],neon=True)
        self.box(cx,.54,cz+.29,.74,.72,.11,COLOR["room_wall"])
        for dx in (-.27,.27):
            for dz in (-.23,.23):
                self.box(cx+dx,0,cz+dz,.07,.42,.07,COLOR["blue"])

        # Armario con dos puertas y tiradores.
        ax,az=self.world(7,3)
        self.box(ax,0,az,TILE*.83,2.12,TILE*.66,COLOR["room_wall"])
        self.box(ax-.27,.15,az+.46,.45,1.77,.045,COLOR["wood"])
        self.box(ax+.27,.15,az+.46,.45,1.77,.045,COLOR["wood"])
        self.line((ax,.19,az+.49),(ax,1.93,az+.49),COLOR["cyan"],.035)
        self.ball((ax-.06,1.09,az+.52),.050,COLOR["pink"])
        self.ball((ax+.06,1.09,az+.52),.050,COLOR["pink"])

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
        self.build_room_details()
        # Sensor virtual orientado: detecta la siguiente pared.
        dx,dz=DIRECTIONS[robot.facing]
        bx,bz=self.world(self.rx,self.rz)
        d=min(3.0,robot.front_distance()/40.0)*TILE
        self.line((bx,.08,bz),(bx+dx*d,.08,bz+dz*d),COLOR["cyan"],.04)
        self.ball((bx+dx*d,.08,bz+dz*d),.09,COLOR["pink"])

    def build_robot(self, robot, dt, elapsed, force_moving=None):
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
        self.build_world(robot)
        self.build_robot(robot,dt,elapsed)
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
        self.scene=Scene3D(pg)
        self.portrait_scene=Scene3D(pg)
        self.auto=False
        self.auto_clock=0.0
        self.elapsed=0.0
        self.bubble_text="Hola, estoy listo para conocer este mundo."
        self.bubble_until=float("inf")
        self.bubble_kind="hello"
        self.input_focus=False
        self.input_value=""
        self.messages=deque(maxlen=24)
        self.messages.append(("SISTEMA","AMBOT listo. Cerebro local y cuerpo 3D.",COLOR["green"]))
        self.messages.append(("AYUDA","W/A/S/D mover · E explorar · ESPACIO auto",COLOR["muted"]))
        self.dragging=False
        self.mouse=(0,0)
        self.buttons={}
        self.input_rect=pg.Rect(0,0,1,1)
        self.view=pg.Rect(290,83,650,565)
        self.portrait_view=pg.Rect(20,83,250,565)
        self.last_portrait_state=None

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
        status="AUTO" if self.auto else ("EN MOVIMIENTO" if self.scene.is_moving else "EN ESPERA")
        self.text((rect.x+14,rect.y+36),"● "+status,13,COLOR["green"] if self.auto else COLOR["muted"])

        # Reservar franja superior para la burbuja sin tapar al stickman.
        camera=pg.Rect(rect.x+12,rect.y+124,rect.width-24,
                       max(190,rect.height-201))
        self.portrait_scene.render_portrait(
            self.screen,camera,self.robot,self.scene,self.elapsed)
        self.last_portrait_state=(
            self.portrait_scene.rx,self.portrait_scene.rz,
            self.portrait_scene.angle,self.portrait_scene.walk)
        self.text((rect.x+18,rect.bottom-63),"CÁMARA / SEGUIMIENTO",13,COLOR["muted"])
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
        if answer:
            mood="alert" if "SEGURIDAD" in answer.upper() else "normal"
            self.say(answer,5.5 if not quiet else 3.4,mood)
        if not quiet:self.add_log("AMBOT",answer,COLOR["green"])

    def toggle_auto(self):
        self.auto=not self.auto
        self.auto_clock=.45
        message="Estoy explorando por mi cuenta." if self.auto else "He detenido mi exploración."
        self.add_log("SISTEMA","Autonomo " + ("activado" if self.auto else "detenido") + ".",
                     COLOR["green"] if self.auto else COLOR["yellow"])
        self.say(message,duration=4.0)

    def handle_button(self,key):
        if key=="auto":
            self.toggle_auto()
        elif key=="stop":
            self.auto=False
            self.add_log("SISTEMA","Robot en pausa.",COLOR["yellow"])
            self.say("Me detengo. Espero nuevas instrucciones.",4.0)
        elif key=="reset":
            self.auto=False
            self.robot.reset()
            self.add_log("SISTEMA","Robot reiniciado. Memoria conservada.",COLOR["green"])
            self.say("He vuelto al inicio. ¡Vamos a descubrir!",5.0)
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
                self.screen=pg.display.set_mode((max(1120,e.w),max(650,e.h)),pg.RESIZABLE)
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
        self.portrait_view=left
        self.draw_character_viewer(left)
        self.draw_speech_bubble(left)
        # Vista e indicadores superpuestos.
        stamp=pg.Rect(self.view.x+13,self.view.y+12,262,29)
        pg.draw.rect(surf,COLOR["panel"],stamp,border_radius=7)
        label = ("●  HABITACION INICIAL | 3D" if self.robot.location() == ROOM_NAME
                 else "●  PASILLO | ENTORNO 3D")
        self.text((stamp.x+10,stamp.y+6),label,14,COLOR["cyan"])
        self.text((self.view.x+15,self.view.bottom-30),"ARRASTRA: GIRAR CÁMARA    ·    RUEDA: ZOOM",13,COLOR["muted"])
        self.panel(side)
        x=side.x+17
        inner=side.width-34
        self.text((x,side.y+14),"CEREBRO / AMBOT",20,COLOR["ink"])
        self.text((x,side.y+44),"●  "+self.robot.location()+"  •  SENSOR ACTIVO",13,COLOR["green"])
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
        self.text((23,h-45),"W/A/S/D · E EXPLORAR · ESPACIO AUTO · R REINICIAR · TAB ESCRIBIR",
                  14,COLOR["muted"])
        self.text((w-222,h-45),"ARCHMOBA  /  AMBOT "+APP_VERSION,14,COLOR["cyan"])
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
                    self.say(self.robot.last_decision,duration=2.5,
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
