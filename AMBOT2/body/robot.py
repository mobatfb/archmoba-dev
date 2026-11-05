"""Humanoides de AMBOT2: cuerpo y 10 dedos por personaje."""
from dataclasses import dataclass
from panda3d.core import Vec3, Point3
from engine.primitives import cuboid, sphere


FINGER_NAMES=("pulgar","indice","medio","anular","menique")
HAND_NAMES=("izquierda","derecha")


def clamp(value,minimum=0.0,maximum=1.0):
    return max(minimum,min(maximum,float(value)))


class Humanoid:
    """Rig visual editable. El maestro es un avatar, NO un agente automatico.

    Por ahora cuerpo/cadera son cinematicos, mientras que el mundo y los
    objetos SI se simulan con Bullet. Los dedos proporcionan puntos de
    contacto para cuerpos cinematicos de Bullet en el modulo grasp.
    """
    def __init__(self,root,name,color,position=(0,0,0),teacher=False):
        self.name=name
        self.teacher=bool(teacher)
        self.color=color
        self.root=root
        self.node=root.attachNewNode(name)
        self.node.setPos(*position)
        self.heading=0.0
        self.reach=0.74 if teacher else 0.15
        self.spread=.24
        self.hand_height=0.05
        self.curls={h:[.0]*5 for h in HAND_NAMES}
        self.selected_hand="izquierda"
        self.selected_digit=0
        self.walk_time=0.0
        self.walking=False
        self._segments={}
        self._joints={}
        self._make_rig()
        self.update_visual()

    def _piece(self,name,color=None):
        p=cuboid(self.node,(1,1,1),color or self.color,name)
        self._segments[name]=p
        return p

    def _joint(self,name,radius=.08,color=None):
        p=sphere(self.node,radius,color or self.color,name)
        self._joints[name]=p
        return p

    def _make_rig(self):
        self.torso=cuboid(self.node,(.47,.28,.70),self.color,"torso")
        self.torso.setPos(0,0,1.32)
        self._joint("cabeza",.24,(.95,.98,1,1) if self.teacher
                    else (.69,.90,1,1))
        self._joint("cuello",.10)
        for h in HAND_NAMES:
            self._joint(h+"_hombro",.12)
            self._joint(h+"_codo",.095)
            self._joint(h+"_muneca",.08)
            self._piece(h+"_biceps")
            self._piece(h+"_antebrazo")
            self._piece(h+"_palma")
            for i in range(5):
                self._piece(f"{h}_{i}_falange1")
                self._piece(f"{h}_{i}_falange2")
                self._joint(f"{h}_{i}_punta",.032,(.95,.85,.57,1))
        for side in ("pierna_izquierda","pierna_derecha"):
            self._piece(side+"_muslo")
            self._piece(side+"_pantorrilla")
            self._piece(side+"_pie")
            self._joint(side+"_rodilla",.10)
        self._joint("ojo_izquierdo",.05,(.08,.55,.80,1))
        self._joint("ojo_derecho",.05,(.08,.55,.80,1))

    def _line(self,name,a,b,width):
        a,b=Vec3(*a),Vec3(*b)
        seg=self._segments[name]
        seg.setPos((a+b)*.5)
        diff=b-a
        seg.setScale(width,max(.01,diff.length()),width)
        if diff.length()>.0001:
            seg.lookAt(b)

    def _side(self,hand):
        return -1 if hand=="izquierda" else 1

    def hand_points(self,hand):
        side=self._side(hand)
        shoulder=Vec3(.33*side,0,1.68)
        elbow=Vec3((.51+.05*self.spread)*side,
                   .20+.22*self.reach,1.42+self.hand_height*.40)
        wrist=Vec3((.58+.37*self.spread)*side,
                   .40+.68*self.reach,1.21+self.hand_height)
        palm=Vec3(wrist.x,wrist.y+.17,wrist.z)
        return shoulder,elbow,wrist,palm

    def _finger_points(self,hand,index):
        side=self._side(hand)
        shoulder,elbow,wrist,palm=self.hand_points(hand)
        curl=self.curls[hand][index]
        xoffset=side*((index-2)*.055)
        zoffset=(2-index)*.045
        base=palm+Vec3(xoffset,0,zoffset)
        if index==0:
            base=palm+Vec3(side*.11,.01,-.06)
            mid=base+Vec3(-side*(.03+.05*curl),.085+.05*curl,.035)
            tip=mid+Vec3(-side*(.07+.03*curl),.10+.045*curl,
                         .045+.025*curl)
        else:
            mid=base+Vec3(0,.13+.03*(1-curl),-.04*curl)
            tip=mid+Vec3(-side*.025*curl,.12+.035*(1-curl),-.105*curl)
        return base,mid,tip

    def all_fingertips(self):
        """10 puntos sensoriales del mismo rig visual; en mundo fisico."""
        out={}
        for hand in HAND_NAMES:
            for index in range(5):
                local=self._finger_points(hand,index)[-1]
                out[(hand,index)]=self.root.getRelativePoint(self.node,Point3(local))
        return out

    def palm_world(self,hand):
        palm=self.hand_points(hand)[-1]
        return self.root.getRelativePoint(self.node,Point3(palm))

    def _leg(self,side,phase):
        direction=-1 if side=="pierna_izquierda" else 1
        swing=.20*phase
        hip=Vec3(direction*.16,0,.99)
        knee=Vec3(direction*.16,.10+swing,.52)
        ankle=Vec3(direction*.16,.01+swing*.65,.12)
        foot=Vec3(direction*.16,.19+swing*.65,.09)
        self._line(side+"_muslo",hip,knee,.17)
        self._line(side+"_pantorrilla",knee,ankle,.13)
        self._line(side+"_pie",ankle,foot,.17)
        self._joints[side+"_rodilla"].setPos(knee)

    def update_visual(self):
        self.node.setH(self.heading)
        self._joints["cabeza"].setPos(0,.045,2.00)
        self._joints["cuello"].setPos(0,0,1.77)
        for hand in HAND_NAMES:
            shoulder,elbow,wrist,palm=self.hand_points(hand)
            self._joints[hand+"_hombro"].setPos(shoulder)
            self._joints[hand+"_codo"].setPos(elbow)
            self._joints[hand+"_muneca"].setPos(wrist)
            self._line(hand+"_biceps",shoulder,elbow,.14)
            self._line(hand+"_antebrazo",elbow,wrist,.12)
            self._line(hand+"_palma",wrist,palm,.18)
            for i in range(5):
                base,mid,tip=self._finger_points(hand,i)
                self._line(f"{hand}_{i}_falange1",base,mid,.055)
                self._line(f"{hand}_{i}_falange2",mid,tip,.043)
                self._joints[f"{hand}_{i}_punta"].setPos(tip)
        self._joints["ojo_izquierdo"].setPos(-.085,.20,2.04)
        self._joints["ojo_derecho"].setPos(.085,.20,2.04)
        phase=__import__("math").sin(self.walk_time*9) if self.walking else 0.0
        self._leg("pierna_izquierda",phase)
        self._leg("pierna_derecha",-phase)

    def move(self,x,y,dt=1/60):
        if not x and not y:
            self.walking=False
            self.update_visual()
            return
        from math import radians, sin, cos
        theta=radians(self.heading)
        dx=x*cos(theta)-y*sin(theta)
        dy=x*sin(theta)+y*cos(theta)
        self.node.setPos(self.node.getPos()+Vec3(dx*dt*2.15,dy*dt*2.15,0))
        self.walk_time+=dt
        self.walking=True
        self.update_visual()

    def turn(self,delta):
        self.heading=(self.heading+delta)%360
        self.update_visual()

    def finger(self,hand,index,value):
        if hand not in HAND_NAMES or index not in range(5):
            raise ValueError("Articulacion desconocida")
        self.curls[hand][index]=clamp(value)
        self.update_visual()

    def hand_close(self,hand,value):
        if hand not in HAND_NAMES:
            raise ValueError("Mano desconocida")
        for i in range(5):
            self.curls[hand][i]=clamp(value)
        self.update_visual()

    def pose(self):
        return {
            "position":list(self.node.getPos(self.root)),
            "heading":self.heading,"reach":self.reach,
            "spread":self.spread,"hand_height":self.hand_height,
            "fingers":{h:list(values) for h,values in self.curls.items()}
        }

    def set_pose(self,p):
        if not isinstance(p,dict):
            raise ValueError("Pose invalida")
        self.node.setPos(*p.get("position",self.node.getPos()))
        self.heading=float(p.get("heading",self.heading))
        self.reach=clamp(p.get("reach",self.reach))
        self.spread=clamp(p.get("spread",self.spread))
        self.hand_height=clamp(p.get("hand_height",self.hand_height),-1,1)
        fingers=p.get("fingers",{})
        for hand in HAND_NAMES:
            if hand in fingers and len(fingers[hand])==5:
                self.curls[hand]=[clamp(v) for v in fingers[hand]]
        self.update_visual()
