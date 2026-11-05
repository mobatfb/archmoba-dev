"""Geometria 3D procedural; ninguna textura ni modelo externo obligatorio."""
import math
from panda3d.core import (
    Geom, GeomNode, GeomTriangles, GeomVertexData,
    GeomVertexFormat, GeomVertexWriter, Vec3, NodePath
)


def cuboid(parent, size, color, name="pieza"):
    """Cubo centrado en su origen, con normales por cara."""
    sx, sy, sz = (float(v) for v in size)
    faces = (
        ((1, 0, 0), ((.5,-.5,-.5),(.5,.5,-.5),(.5,.5,.5),(.5,-.5,.5))),
        ((-1,0, 0), ((-.5,.5,-.5),(-.5,-.5,-.5),(-.5,-.5,.5),(-.5,.5,.5))),
        ((0, 1, 0), ((.5,.5,-.5),(-.5,.5,-.5),(-.5,.5,.5),(.5,.5,.5))),
        ((0,-1, 0), ((-.5,-.5,-.5),(.5,-.5,-.5),(.5,-.5,.5),(-.5,-.5,.5))),
        ((0, 0, 1), ((-.5,-.5,.5),(.5,-.5,.5),(.5,.5,.5),(-.5,.5,.5))),
        ((0, 0,-1), ((-.5,.5,-.5),(.5,.5,-.5),(.5,-.5,-.5),(-.5,-.5,-.5))),
    )
    data = GeomVertexData(name, GeomVertexFormat.getV3n3(), Geom.UHStatic)
    v = GeomVertexWriter(data, "vertex")
    n = GeomVertexWriter(data, "normal")
    idx = GeomTriangles(Geom.UHStatic)
    for normal, points in faces:
        base = v.getWriteRow()
        for xx, yy, zz in points:
            v.addData3(xx*sx, yy*sy, zz*sz)
            n.addData3(*normal)
        idx.addVertices(base, base+1, base+2)
        idx.closePrimitive()
        idx.addVertices(base, base+2, base+3)
        idx.closePrimitive()
    geom = Geom(data)
    geom.addPrimitive(idx)
    node = GeomNode(name)
    node.addGeom(geom)
    out = parent.attachNewNode(node)
    out.setColor(*color)
    out.setTwoSided(False)
    return out


def sphere(parent, radius, color, name="esfera", slices=12, stacks=8):
    data = GeomVertexData(name, GeomVertexFormat.getV3n3(), Geom.UHStatic)
    v = GeomVertexWriter(data, "vertex")
    n = GeomVertexWriter(data, "normal")
    for row in range(stacks+1):
        phi = math.pi*row/stacks
        for col in range(slices+1):
            theta = 2*math.pi*col/slices
            point = Vec3(math.sin(phi)*math.cos(theta),
                         math.sin(phi)*math.sin(theta),math.cos(phi))
            v.addData3(*(point*radius))
            n.addData3(*point)
    idx = GeomTriangles(Geom.UHStatic)
    for row in range(stacks):
        for col in range(slices):
            a = row*(slices+1)+col
            b = a+slices+1
            idx.addVertices(a,b,a+1)
            idx.closePrimitive()
            idx.addVertices(a+1,b,b+1)
            idx.closePrimitive()
    geom = Geom(data)
    geom.addPrimitive(idx)
    node = GeomNode(name)
    node.addGeom(geom)
    out = parent.attachNewNode(node)
    out.setColor(*color)
    out.setTwoSided(True)
    return out


def limb(parent, a, b, width, color, name="segmento"):
    start, end = Vec3(*a), Vec3(*b)
    middle = (start+end)*.5
    visual = cuboid(parent, (width, (end-start).length(), width), color, name)
    visual.setPos(middle)
    if (end-start).length() > 1e-5:
        visual.lookAt(end)
    return visual
