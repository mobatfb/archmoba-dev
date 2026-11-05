"""Dos humanoides editables: articulaciones cinematicas + manos de cinco dedos.

La fisica de los objetos se mantiene en Bullet. Las articulaciones de
ambos robots son cinematicas; la movilidad del cuerpo, la postura y los
sensores de las yemas son reales dentro del rig tridimensional.
"""
import math
from panda3d.core import Vec3, Point3
from engine.primitives import cuboid, sphere


FINGER_NAMES=("pulgar","indice","medio","anular","menique")
HAND_NAMES=("izquierda","derecha")
WALK_SPEED=2.15
TURN_SPEED=125.0

# Nombre del control, titulo mostrado, limite minimo, limite maximo.
# Cada valor representa grados de movimiento de una articulacion.
JOINT_GROUPS={
    "CABEZA Y TRONCO": (
        ("cuello_giro","Cuello girar",-80,80),
        ("cuello_flex","Cuello inclinar",-50,50),
        ("cuello_lateral","Cuello lateral",-35,35),
        ("tronco_giro","Torso girar",-50,50),
        ("tronco_flex","Torso inclinar",-45,45),
        ("tronco_lateral","Torso lateral",-35,35),
    ),
    "BRAZO IZQUIERDO": (
        ("hombro_izq_elev","Hombro elevar",-110,110),
        ("hombro_izq_abre","Hombro abrir",-90,90),
        ("hombro_izq_giro","Hombro girar",-90,90),
        ("codo_izq","Codo flexionar",0,145),
        ("muneca_izq_flex","Muneca doblar",-75,75),
        ("muneca_izq_giro","Muneca girar",-80,80),
    ),
    "BRAZO DERECHO": (
        ("hombro_der_elev","Hombro elevar",-110,110),
        ("hombro_der_abre","Hombro abrir",-90,90),
        ("hombro_der_giro","Hombro girar",-90,90),
        ("codo_der","Codo flexionar",0,145),
        ("muneca_der_flex","Muneca doblar",-75,75),
        ("muneca_der_giro","Muneca girar",-80,80),
    ),
    "PIERNA IZQUIERDA": (
        ("cadera_izq_flex","Cadera flexionar",-80,90),
        ("cadera_izq_abre","Cadera abrir",-45,45),
        ("cadera_izq_giro","Cadera girar",-50,50),
        ("rodilla_izq","Rodilla flexionar",0,145),
        ("tobillo_izq_flex","Tobillo doblar",-45,45),
        ("tobillo_izq_lateral","Tobillo lateral",-30,30),
    ),
    "PIERNA DERECHA": (
        ("cadera_der_flex","Cadera flexionar",-80,90),
        ("cadera_der_abre","Cadera abrir",-45,45),
        ("cadera_der_giro","Cadera girar",-50,50),
        ("rodilla_der","Rodilla flexionar",0,145),
        ("tobillo_der_flex","Tobillo doblar",-45,45),
        ("tobillo_der_lateral","Tobillo lateral",-30,30),
    ),
}
JOINT_LIMITS={
    name:(float(low),float(high))
    for values in JOINT_GROUPS.values() for name,_,low,high in values
}
JOINT_NAMES=tuple(JOINT_LIMITS)
JOINT_LABELS={
    name:label for values in JOINT_GROUPS.values()
    for name,label,_,_ in values
}


def tank_inputs(keys):
    """W/S y flechas verticales avanzan; A/D giran sobre el eje."""
    keys=set(keys)
    forward=int(bool({"w","arrow_up"} & keys))-int(bool({"s","arrow_down"} & keys))
    turn=int(bool({"a","arrow_left"} & keys))-int(bool({"d","arrow_right"} & keys))
    return forward,turn


def clamp(value,minimum=0.0,maximum=1.0):
    return max(minimum,min(maximum,float(value)))


def rotate(vec,yaw=0.0,pitch=0.0,roll=0.0):
    """Giro de un vector: Z (yaw), X (pitch), Y (roll); Z es arriba."""
    v=Vec3(*vec)
    a=math.radians(float(roll))
    cs,sn=math.cos(a),math.sin(a)
    v=Vec3(v.x*cs+v.z*sn,v.y,-v.x*sn+v.z*cs)
    a=math.radians(float(pitch))
    cs,sn=math.cos(a),math.sin(a)
    v=Vec3(v.x,v.y*cs-v.z*sn,v.y*sn+v.z*cs)
    a=math.radians(float(yaw))
    cs,sn=math.cos(a),math.sin(a)
    return Vec3(v.x*cs-v.y*sn,v.x*sn+v.y*cs,v.z)


class Humanoid:
    """Avatar cinematico con 30 grados de libertad y 10 dedos.

    Los controles de los dedos siguen una cadena de dos falanges con
    una flexion acoplada por dedo. Las articulaciones son editables
    y respetan limites; este rig NO es un robot biomecanico Bullet.
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
        self.hand_height=.05
        self.curls={h:[0.0]*5 for h in HAND_NAMES}
        self.joints={name:0.0 for name in JOINT_NAMES}
        self.selected_hand="izquierda"
        self.selected_digit=0
        self.walk_time=0.0
        self.walking=False
        self._segments={}
        self._joints={}
        self._make_rig()
        self.update_visual()

    def _piece(self,name,color=None):
        node=cuboid(self.node,(1,1,1),color or self.color,name)
        self._segments[name]=node
        return node

    def _joint(self,name,radius=.08,color=None):
        node=sphere(self.node,radius,color or self.color,name)
        self._joints[name]=node
        return node

    def _make_rig(self):
        self.torso=self._piece("torso")
        self._joint("cabeza",.24,(.95,.98,1,1) if self.teacher else (.69,.9,1,1))
        self._joint("cuello",.09)
        self._joint("cintura",.14)
        for hand in HAND_NAMES:
            self._joint(hand+"_hombro",.11)
            self._joint(hand+"_codo",.09)
            self._joint(hand+"_muneca",.075)
            self._piece(hand+"_biceps")
            self._piece(hand+"_antebrazo")
            self._piece(hand+"_palma")
            for index in range(5):
                self._piece(f"{hand}_{index}_falange1")
                self._piece(f"{hand}_{index}_falange2")
                self._joint(f"{hand}_{index}_punta",.029,(.95,.85,.57,1))
        for side in ("pierna_izquierda","pierna_derecha"):
            self._joint(side+"_cadera",.105)
            self._joint(side+"_rodilla",.09)
            self._joint(side+"_tobillo",.072)
            self._piece(side+"_muslo")
            self._piece(side+"_pantorrilla")
            self._piece(side+"_pie")
        self._joint("ojo_izquierdo",.045,(.08,.55,.80,1))
        self._joint("ojo_derecho",.045,(.08,.55,.80,1))

    def _line(self,name,a,b,width):
        a,b=Vec3(*a),Vec3(*b)
        piece=self._segments[name]
        piece.setPos((a+b)*.5)
        direction=b-a
        piece.setScale(width,max(.01,direction.length()),width)
        if direction.length()>.0001:
            piece.lookAt(b)

    def _torso(self,vector):
        j=self.joints
        return rotate(vector,j["tronco_giro"],j["tronco_flex"],j["tronco_lateral"])

    @staticmethod
    def _side(hand):
        return -1 if hand=="izquierda" else 1

    @staticmethod
    def _code(hand):
        return "izq" if hand=="izquierda" else "der"

    def _arm_rotate(self,vector,hand,elbow=False,wrist=False):
        code=self._code(hand)
        j=self.joints
        yaw=j[f"hombro_{code}_giro"]
        pitch=j[f"hombro_{code}_elev"]
        roll=j[f"hombro_{code}_abre"]
        if elbow:
            pitch+=j[f"codo_{code}"]*.9
        if wrist:
            yaw+=j[f"muneca_{code}_giro"]
            pitch+=j[f"muneca_{code}_flex"]
        return self._torso(rotate(vector,yaw,pitch,roll))

    def hand_points(self,hand):
        if hand not in HAND_NAMES:
            raise ValueError("Mano no reconocida")
        side=self._side(hand)
        waist=Vec3(0,0,1.03)
        shoulder=waist+self._torso(Vec3(side*.33,0,.65))
        upper=Vec3(side*(.14+.05*self.spread),
                   .20+.22*self.reach,-.25+.1*self.hand_height)
        elbow=shoulder+self._arm_rotate(upper,hand)
        forearm=Vec3(side*.10,.20+.32*self.reach,
                     -.22+.6*self.hand_height)
        wrist=elbow+self._arm_rotate(forearm,hand,elbow=True)
        palm=wrist+self._arm_rotate(Vec3(0,.17,0),hand,elbow=True,wrist=True)
        return shoulder,elbow,wrist,palm

    def _finger_points(self,hand,index):
        if hand not in HAND_NAMES or index not in range(5):
            raise ValueError("Dedo no reconocido")
        _,_,_,palm=self.hand_points(hand)
        curl=self.curls[hand][index]
        side=self._side(hand)
        def direction(vector):
            return self._arm_rotate(vector,hand,elbow=True,wrist=True)
        if index==0:
            start=palm+direction(Vec3(side*.115,.025,-.065))
            middle=start+direction(Vec3(-side*(.07+.05*curl),.075,.035))
            tip=middle+direction(Vec3(-side*(.065+.06*curl),
                                      .085-.045*curl,.03-.045*curl))
        else:
            base=palm+direction(Vec3(side*(index-2)*.048,0,(2-index)*.037))
            first=math.radians(curl*77)
            second=math.radians(curl*140)
            middle=base+direction(Vec3(0,.145*math.cos(first),-.145*math.sin(first)))
            tip=middle+direction(Vec3(0,.12*math.cos(second),-.12*math.sin(second)))
            start=base
        return start,middle,tip

    def all_fingertips(self):
        """Yemas de las dos manos en coordenadas de mundo, para Bullet."""
        out={}
        for hand in HAND_NAMES:
            for index in range(5):
                local=self._finger_points(hand,index)[-1]
                out[(hand,index)]=self.root.getRelativePoint(self.node,Point3(local))
        return out

    def palm_world(self,hand):
        return self.root.getRelativePoint(
            self.node,Point3(self.hand_points(hand)[-1])
        )

    def _leg(self,side,phase):
        code="izq" if side=="pierna_izquierda" else "der"
        sign=-1 if code=="izq" else 1
        j=self.joints
        hip=Vec3(sign*.16,0,.99)
        hip_yaw=j[f"cadera_{code}_giro"]
        hip_pitch=j[f"cadera_{code}_flex"]+phase*14
        hip_roll=j[f"cadera_{code}_abre"]
        knee=hip+rotate(Vec3(0,.10,-.47),hip_yaw,hip_pitch,hip_roll)
        knee_angle=j[f"rodilla_{code}"]
        ankle=knee+rotate(Vec3(0,-.085,-.41),hip_yaw,
                          hip_pitch+knee_angle*.85,hip_roll)
        foot=ankle+rotate(Vec3(0,.19,-.032),hip_yaw,
                          hip_pitch+knee_angle*.85-j[f"tobillo_{code}_flex"],
                          hip_roll+j[f"tobillo_{code}_lateral"])
        self._line(side+"_muslo",hip,knee,.17)
        self._line(side+"_pantorrilla",knee,ankle,.13)
        self._line(side+"_pie",ankle,foot,.17)
        self._joints[side+"_cadera"].setPos(hip)
        self._joints[side+"_rodilla"].setPos(knee)
        self._joints[side+"_tobillo"].setPos(ankle)

    def update_visual(self):
        self.node.setH(self.heading)
        waist=Vec3(0,0,1.03)
        chest=waist+self._torso(Vec3(0,0,.68))
        self._line("torso",waist,chest,.44)
        self._joints["cintura"].setPos(waist)
        neck=waist+self._torso(Vec3(0,0,.79))
        self._joints["cuello"].setPos(neck)
        j=self.joints
        def head_rot(vec):
            return self._torso(
                rotate(vec,j["cuello_giro"],j["cuello_flex"],j["cuello_lateral"])
            )
        head=neck+head_rot(Vec3(0,.045,.18))
        self._joints["cabeza"].setPos(head)
        self._joints["ojo_izquierdo"].setPos(head+head_rot(Vec3(-.084,.198,.045)))
        self._joints["ojo_derecho"].setPos(head+head_rot(Vec3(.084,.198,.045)))
        for hand in HAND_NAMES:
            shoulder,elbow,wrist,palm=self.hand_points(hand)
            self._joints[hand+"_hombro"].setPos(shoulder)
            self._joints[hand+"_codo"].setPos(elbow)
            self._joints[hand+"_muneca"].setPos(wrist)
            self._line(hand+"_biceps",shoulder,elbow,.14)
            self._line(hand+"_antebrazo",elbow,wrist,.12)
            self._line(hand+"_palma",wrist,palm,.18)
            for index in range(5):
                base,mid,tip=self._finger_points(hand,index)
                self._line(f"{hand}_{index}_falange1",base,mid,.051)
                self._line(f"{hand}_{index}_falange2",mid,tip,.043)
                self._joints[f"{hand}_{index}_punta"].setPos(tip)
        phase=math.sin(self.walk_time*9) if self.walking else 0
        self._leg("pierna_izquierda",phase)
        self._leg("pierna_derecha",-phase)

    def set_joint(self,name,angle):
        """Modificar articulacion comprobando sus limites mecanicos."""
        if name not in JOINT_LIMITS:
            raise ValueError("Articulacion desconocida: "+str(name))
        low,high=JOINT_LIMITS[name]
        value=clamp(angle,low,high)
        self.joints[name]=value
        self.update_visual()
        return value

    def reset_joints(self):
        for name in JOINT_NAMES:
            self.joints[name]=0.0
        self.update_visual()

    def drive(self,forward=0,turn=0,dt=1/60):
        """Conduccion tipo tanque: sin desplazamiento lateral."""
        dt=max(0.0,min(.05,float(dt)))
        forward=max(-1.0,min(1.0,float(forward)))
        turn=max(-1.0,min(1.0,float(turn)))
        if turn:
            self.heading=(self.heading+turn*TURN_SPEED*dt)%360
        self.walking=bool(forward)
        if forward:
            angle=math.radians(self.heading)
            distance=forward*WALK_SPEED*dt
            current=self.node.getPos(self.root)
            x=max(-24.5,min(24.5,current.x-math.sin(angle)*distance))
            y=max(-24.5,min(24.5,current.y+math.cos(angle)*distance))
            self.node.setPos(x,y,current.z)
            self.walk_time+=dt
        self.update_visual()

    def turn(self,delta):
        self.heading=(self.heading+float(delta))%360
        self.update_visual()

    def finger(self,hand,index,value):
        if hand not in HAND_NAMES or index not in range(5):
            raise ValueError("Articulacion de dedo desconocida")
        self.curls[hand][index]=clamp(value)
        self.update_visual()

    def hand_close(self,hand,value):
        if hand not in HAND_NAMES:
            raise ValueError("Mano desconocida")
        for index in range(5):
            self.curls[hand][index]=clamp(value)
        self.update_visual()

    def pose(self):
        return {
            "position":list(self.node.getPos(self.root)),
            "heading":self.heading,
            "reach":self.reach,
            "spread":self.spread,
            "hand_height":self.hand_height,
            "joints":dict(self.joints),
            "fingers":{hand:list(values) for hand,values in self.curls.items()}
        }

    def set_pose(self,pose):
        if not isinstance(pose,dict):
            raise ValueError("Pose invalida")
        if "position" in pose:
            self.node.setPos(*pose["position"])
        self.heading=float(pose.get("heading",self.heading))%360
        self.reach=clamp(pose.get("reach",self.reach))
        self.spread=clamp(pose.get("spread",self.spread))
        self.hand_height=clamp(pose.get("hand_height",self.hand_height),-1,1)
        angles=pose.get("joints",{})
        if isinstance(angles,dict):
            for name in JOINT_NAMES:
                if name in angles:
                    low,high=JOINT_LIMITS[name]
                    self.joints[name]=clamp(angles[name],low,high)
        fingers=pose.get("fingers",{})
        for hand in HAND_NAMES:
            if hand in fingers and len(fingers[hand])==5:
                self.curls[hand]=[clamp(v) for v in fingers[hand]]
        self.update_visual()
