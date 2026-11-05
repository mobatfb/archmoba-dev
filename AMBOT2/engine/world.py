"""Plano de 50 x 50 metros, objetos rigidos y editor de escena."""
import json
import math
from dataclasses import dataclass
from pathlib import Path

from panda3d.bullet import (
    BulletWorld, BulletRigidBodyNode, BulletBoxShape, BulletSphereShape
)
from panda3d.core import Vec3, Point3, LineSegs, NodePath
from .primitives import cuboid, sphere

PALETTE = {
    "cubo": (.19, .79, .94, 1),
    "pelota": (.95, .43, .56, 1),
    "cuadro": (.98, .77, .36, 1),
    "caja": (.53, .69, .94, 1),
    "tabla": (.68, .74, .86, 1),
    "cama": (.51, .87, .67, 1),
    "mesa": (.80, .65, .43, 1),
    "esfera": (.95, .43, .56, 1),
}
PRESETS = {
    "cubo": ((.48,.48,.48), 1.0),
    "pelota": ((.46,.46,.46), .9),
    "cuadro": ((1.8,.13,1.25), 1.6),
    "caja": ((.9,.72,.62), 3.0),
    "tabla": ((1.55,.55,.13), 2.8),
    "cama": ((2.0,.9,.38), 13.0),
    "mesa": ((1.25,.85,.60), 11.0),
    "esfera": ((.46,.46,.46), .9),
}
ROUND = {"pelota","esfera"}


@dataclass
class PhysicalObject:
    oid: str
    name: str
    kind: str
    size: tuple
    mass: float
    np: NodePath
    color: tuple


class LabWorld:
    def __init__(self, root):
        self.root = root
        self.physics = BulletWorld()
        self.physics.setGravity(Vec3(0,0,-9.81))
        self.objects = {}
        self._serial = 0
        self._floor()
        self._grid()

    def _floor(self):
        node = BulletRigidBodyNode("terreno")
        node.addShape(BulletBoxShape(Vec3(25,25,.15)))
        node.setMass(0)
        node.setFriction(1.6)
        self.ground = self.root.attachNewNode(node)
        self.ground.setPos(0,0,-.15)
        self.physics.attachRigidBody(node)
        cuboid(self.ground,(50,50,.3),(.085,.135,.18,1),"plano")

    def _grid(self):
        lines=LineSegs("cuadricula")
        lines.setThickness(1)
        lines.setColor(.16,.28,.35,1)
        for i in range(-24,25,2):
            lines.moveTo(i,-25,.005)
            lines.drawTo(i,25,.005)
            lines.moveTo(-25,i,.005)
            lines.drawTo(25,i,.005)
        self.root.attachNewNode(lines.create())

    def _name(self, kind):
        self._serial+=1
        return f"{kind}-{self._serial:03d}"

    def spawn(self,kind="cubo",name=None,size=None,mass=None,pos=None,color=None,oid=None):
        kind=kind.lower().strip()
        if kind not in PRESETS:
            raise ValueError("Forma no disponible: "+kind)
        preset_size,preset_mass=PRESETS[kind]
        dimensions=tuple(float(max(.08,min(5.0,v))) for v in (size or preset_size))
        mass=float(preset_mass if mass is None else mass)
        if not 0<mass<=80:
            raise ValueError("La masa debe ser mayor que 0 y menor que 80 kg.")
        pos=tuple(pos or (0,3,max(.2,dimensions[2]/2+.15)))
        if len(pos)!=3:
            raise ValueError("Posicion 3D invalida")
        if any(abs(v)>24 for v in pos[:2]):
            raise ValueError("Objeto fuera del plano")
        oid=oid or self._name(kind)
        if oid in self.objects:
            raise ValueError("Identificador duplicado")
        node=BulletRigidBodyNode(oid)
        if kind in ROUND:
            node.addShape(BulletSphereShape(dimensions[0]*.5))
        else:
            node.addShape(BulletBoxShape(Vec3(*(v*.5 for v in dimensions))))
        node.setMass(mass)
        node.setFriction(1.25)
        node.setRestitution(.06)
        node.setLinearDamping(.12)
        node.setAngularDamping(.3)
        np=self.root.attachNewNode(node)
        np.setPos(*pos)
        tint=tuple(color or PALETTE[kind])
        if kind in ROUND:
            sphere(np,dimensions[0]*.5,tint,name)
        else:
            cuboid(np,dimensions,tint,name or kind)
        self.physics.attachRigidBody(node)
        obj=PhysicalObject(oid,str(name or kind),kind,dimensions,mass,np,tint)
        self.objects[oid]=obj
        return obj

    def remove(self,oid):
        obj=self.objects.pop(oid,None)
        if obj:
            self.physics.removeRigidBody(obj.np.node())
            obj.np.removeNode()
        return obj

    def nearest(self,position,max_distance=2.5):
        position=Point3(*position)
        options=[(obj.np.getPos(self.root)-position).length(),obj]
        candidates=sorted(
            ((obj.np.getPos(self.root)-position).length(),obj)
            for obj in self.objects.values()
        )
        return candidates[0][1] if candidates and candidates[0][0]<=max_distance else None

    def serialize(self):
        return [{
            "id":o.oid, "name":o.name, "kind":o.kind, "mass":o.mass,
            "size":list(o.size), "color":list(o.color),
            "position":list(o.np.getPos(self.root)),
            "hpr":list(o.np.getHpr(self.root))
        } for o in self.objects.values()]

    def load(self, data):
        if not isinstance(data,list) or len(data)>150:
            raise ValueError("Escena invalida o demasiado grande")
        # Validacion preliminar: no borrar nada antes de comprobar la escena.
        for entry in data:
            if not isinstance(entry,dict) or entry.get("kind") not in PRESETS:
                raise ValueError("Objeto no reconocido en escena")
        for oid in tuple(self.objects):
            self.remove(oid)
        for entry in data:
            o=self.spawn(entry["kind"],entry.get("name"),
                         entry.get("size"),entry.get("mass"),
                         entry.get("position"),entry.get("color"),entry.get("id"))
            o.np.setHpr(*entry.get("hpr",(0,0,0)))

    def save_file(self,path):
        path=Path(path)
        path.parent.mkdir(parents=True,exist_ok=True)
        tmp=path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.serialize(),ensure_ascii=False,indent=2),encoding="utf-8")
        tmp.replace(path)

    def load_file(self,path):
        path=Path(path)
        if path.exists():
            self.load(json.loads(path.read_text(encoding="utf-8")))
            return True
        return False

    def step(self,dt):
        self.physics.doPhysics(max(0.0,min(dt,.05)),4,1/120)
        # La simulacion conserva objetos dentro del laboratorio.
        for item in self.objects.values():
            p=item.np.getPos(self.root)
            if p.z< -7:
                item.np.setPos(p.x,p.y,2)
                item.np.node().setLinearVelocity(Vec3(0,0,0))
