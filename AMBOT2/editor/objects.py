"""Edicion de objetos del laboratorio sin reconstruir el codigo."""
from pathlib import Path


class ObjectEditor:
    def __init__(self,world,scene_path):
        self.world=world
        self.scene_path=Path(scene_path)
        self.selected=None
        self.kind="cubo"

    def add(self,kind=None,position=None,**kwargs):
        kind=kind or self.kind
        obj=self.world.spawn(kind,pos=position or (0,2,1.1),**kwargs)
        self.selected=obj.oid
        return obj

    def select(self,oid):
        if oid not in self.world.objects:
            return False
        self.selected=oid
        return True

    def object(self):
        return self.world.objects.get(self.selected)

    def delete_selected(self):
        if self.selected is None:
            return False
        if self.world.remove(self.selected):
            self.selected=None
            return True
        return False

    def rename(self,name):
        obj=self.object()
        if not obj:
            raise ValueError("Selecciona primero un objeto")
        name=str(name).strip()
        if not 1<=len(name)<=50:
            raise ValueError("Nombre invalido")
        obj.name=name
        return name

    def move_selected(self,x,y,z):
        obj=self.object()
        if not obj:
            raise ValueError("Selecciona primero un objeto")
        if not (-24<=x<=24 and -24<=y<=24 and .05<=z<=12):
            raise ValueError("Posicion fuera del laboratorio")
        obj.np.setPos(x,y,z)
        obj.np.node().setLinearVelocity((0,0,0))
        obj.np.node().setAngularVelocity((0,0,0))

    def save(self):
        self.world.save_file(self.scene_path)

    def load(self):
        loaded=self.world.load_file(self.scene_path)
        self.selected=None
        return loaded
