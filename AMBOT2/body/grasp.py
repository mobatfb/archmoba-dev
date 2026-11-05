"""Sensores de yemas y agarre Bullet condicionado a contacto real.

Cada dedo existe como punto de contacto fisico cinematico. La sujecion
usa restricciones esfericas entre las palmas y el objeto solo si los
contactos de pulgar + dos dedos estan presentes al cerrar la mano.

No se teletransportan objetos para simular un agarre.
"""
from panda3d.bullet import BulletRigidBodyNode, BulletSphereShape, BulletSphericalConstraint
from panda3d.core import Vec3, Point3
from .robot import HAND_NAMES


class GraspSystem:
    def __init__(self,lab,robot):
        self.lab=lab
        self.robot=robot
        self.fingers={}
        self.palms={}
        self.grabbed={}  # mano -> (objeto_id, restriccion)
        self.current_contacts={}
        self.log=[]
        for hand in HAND_NAMES:
            palm=BulletRigidBodyNode(f"palma_{hand}_{robot.name}")
            palm.setMass(0)
            palm.addShape(BulletSphereShape(.11))
            palm.setKinematic(True)
            palm.setFriction(2)
            pnp=lab.root.attachNewNode(palm)
            lab.physics.attachRigidBody(palm)
            self.palms[hand]=pnp
            for i in range(5):
                node=BulletRigidBodyNode(f"dedo_{hand}_{i}_{robot.name}")
                node.setMass(0)
                node.addShape(BulletSphereShape(.07))
                node.setKinematic(True)
                node.setFriction(2.1)
                np=lab.root.attachNewNode(node)
                lab.physics.attachRigidBody(node)
                self.fingers[(hand,i)]=np
        self.sync()

    def sync(self):
        for hand in HAND_NAMES:
            self.palms[hand].setPos(self.robot.palm_world(hand))
        for key,position in self.robot.all_fingertips().items():
            self.fingers[key].setPos(position)

    def _overlap(self,tip,obj,radius=.07):
        """Interseccion de esfera de dedo con caja orientada / esfera.

        Usa la misma geometria de colision que los cuerpos Bullet; evita
        perder contactos cuando el broadphase se actualiza un frame despues
        de modificar articulaciones cinematicas.
        """
        from engine.world import ROUND
        local=obj.np.getRelativePoint(self.lab.root,tip)
        if obj.kind in ROUND:
            return local.length_squared() <= (radius+obj.size[0]*.5)**2
        dx=max(0.0,abs(local.x)-obj.size[0]*.5)
        dy=max(0.0,abs(local.y)-obj.size[1]*.5)
        dz=max(0.0,abs(local.z)-obj.size[2]*.5)
        return dx*dx+dy*dy+dz*dz <= radius*radius

    def _contacts(self,hand,obj):
        """Interseccion fisica de yema/cuerpo (Bullet o esfera-caja OBB)."""
        out={}
        for i in range(5):
            finger=self.fingers[(hand,i)]
            bullet=bool(self.lab.physics.contactTestPair(
                finger.node(),obj.np.node()
            ).getNumContacts())
            geom=self._overlap(finger.getPos(self.lab.root),obj)
            out[i]=bullet or geom
        return out

    def inspect(self,hand,obj):
        contacts=self._contacts(hand,obj)
        self.current_contacts[(hand,obj.oid)]=contacts
        curled=self.robot.curls[hand]
        opposite=contacts[0] and sum(contacts[i] for i in range(1,5))>=2
        closed=curled[0]>=.55 and sum(v>=.55 for v in curled[1:])>=2
        return opposite and closed,contacts

    def _capacity(self,hand):
        # Modelo inicial de fuerza máxima que depende de cuantos dedos
        # participan, en lugar de un gancho de sujecion infinito.
        curls=self.robot.curls[hand]
        return 1.4+sum(curls)*.75

    def try_grasp(self,hand,obj):
        if hand in self.grabbed:
            return False,"La mano ya sostiene otro objeto."
        ok,contacts=self.inspect(hand,obj)
        if not ok:
            return False,"No hay apoyo suficiente: necesito pulgar y dos dedos en contacto."
        available=[hand]
        for other in HAND_NAMES:
            if other==hand:
                continue
            if other in self.grabbed:
                if self.grabbed[other][0]==obj.oid:
                    available.append(other)
            elif self.inspect(other,obj)[0]:
                # Ambas manos hacen contacto: la capacidad puede sumarse
                # aunque aun no se haya creado el segundo anclaje.
                available.append(other)
        if obj.mass>sum(self._capacity(h) for h in available):
            return False,"Demasiada masa: hacen falta mas dedos o la otra mano."
        # Dos o mas pivotes independientes al sujetar una tabla con ambas manos.
        palm=self.palms[hand]
        world_point=palm.getPos(self.lab.root)
        pivot_obj=obj.np.getRelativePoint(self.lab.root,world_point)
        cs=BulletSphericalConstraint(
            obj.np.node(),palm.node(),pivot_obj,Point3(0,0,0))
        cs.setBreakingThreshold(max(12.0,min(150.0,obj.mass*65)))
        self.lab.physics.attachConstraint(cs,True)
        self.grabbed[hand]=(obj.oid,cs)
        obj.np.node().setActive(True)
        self.log.append(("agarre",hand,obj.oid))
        return True,f"{hand.capitalize()}: apoyo confirmado, objeto sujeto."

    def auto_acquire(self):
        """Detectar agarre real al cerrar dedos, sin pulsar boton.

        No se activa si faltan contactos opuestos. Un solo objeto puede
        quedar sujeto por dos restricciones, una por cada mano.
        """
        results=[]
        for hand in HAND_NAMES:
            if hand in self.grabbed:
                continue
            for obj in self.lab.objects.values():
                # Una vez que los dedos estan cerrados y tocando suficiente
                # superficie, intentar el anclaje fisico.
                if self.inspect(hand,obj)[0]:
                    ok,msg=self.try_grasp(hand,obj)
                    if ok:
                        results.append(msg)
                        break
        return results

    def auto_check(self):
        """Soltar por apertura, carga excesiva o pérdida de soporte."""
        for hand,(oid,cs) in list(self.grabbed.items()):
            obj=self.lab.objects.get(oid)
            curls=self.robot.curls[hand]
            if obj is None or min(curls[0],max(curls[1:]))<.35:
                self.release(hand)
            elif obj.mass>sum(self._capacity(h) for h,(item,_) in self.grabbed.items()
                              if item==oid):
                self.release(hand)

    def release(self,hand):
        if hand not in self.grabbed:
            return False
        oid,cs=self.grabbed.pop(hand)
        self.lab.physics.removeConstraint(cs)
        self.log.append(("soltar",hand,oid))
        return True

    def release_all(self):
        for hand in list(self.grabbed):
            self.release(hand)

    def held(self):
        return {hand:oid for hand,(oid,_) in self.grabbed.items()}

    def scan(self,hand):
        """Encontrar contactos sin activar automaticamente un agarre."""
        result=[]
        for obj in self.lab.objects.values():
            contacts=self._contacts(hand,obj)
            if sum(contacts.values()):
                result.append((obj,sum(contacts.values())))
        return result

    def try_nearest(self,hand):
        contacted=sorted(self.scan(hand),key=lambda pair:-pair[1])
        for obj,_ in contacted:
            ok,msg=self.try_grasp(hand,obj)
            if ok:
                return msg
        return "Sin agarre: acerca la mano, cierra los dedos y toca el objeto."
