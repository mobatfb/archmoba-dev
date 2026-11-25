#!/usr/bin/env python3
"""Mapeo fisico: pruebas de ejes, hats, botones, aprendizaje y GUI real."""
import importlib
import pathlib
import sys
import types
import tkinter as tk
from tkinter import ttk, messagebox

sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
h = importlib.import_module("MULTIMANDO_FUTUREO_Anfitrion_v2_4_5")

class Joy:
    def __init__(self):
        self.axes = [0.,0.,-1.]
        self.hats = [(0,0)]
        self.buttons = [False]*12
        self.online = True
    def get_init(self): return self.online
    def get_numaxes(self): return len(self.axes)
    def get_numhats(self): return len(self.hats)
    def get_numbuttons(self): return len(self.buttons)
    def get_axis(self,i): return self.axes[i]
    def get_hat(self,i): return self.hats[i]
    def get_button(self,i): return self.buttons[i]

class Transport:
    def __init__(self): self.history=[]; self.fail=False
    def health(self): return {"engine":"FUTUREO_VJOY"}
    def resize(self,count): pass
    def input(self,packet):
        if self.fail: raise OSError("test")
        self.history.append(packet)

joy = Joy()
bridge = h.LocalControllerBridge(lambda *_:None)
bridge.pygame = types.SimpleNamespace(event=types.SimpleNamespace(pump=lambda:None))
bridge.physical = {"Gamepad":{"joy":joy}}
transport = Transport()
pads = h.VirtualFutureoPads(2,transport)
room = h.Room(pads,slot_modes={1:"CONTROLADO",2:"REMOTO"})
cfg = {"device":"Gamepad","mapping":{"mapping_version":2,
       "axis_x":0,"axis_y":1,"invert_y":True,"deadzone":.20,
       "directions":dict(h.LOCAL_DEFAULT_DPAD),"analog_to_dpad":False}}
assignments = {1:cfg}
def poll():
    bridge.poll(room,assignments)
    return [p for p in transport.history if p["slot"]==1][-1]
def neutral(packet):
    assert packet["axes"] == [0.,0.] and packet["hat"]==0 and not any(packet["buttons"]), packet

neutral(poll())
joy.axes[0]=1.
p=poll(); assert p["axes"]==[1.,0.] and p["hat"]==0,p
joy.hats[0]=(0,1)
p=poll(); assert p["hat"]==1 and p["axes"]==[1.,0.],p
joy.axes[0]=0.
p=poll(); assert p["axes"]==[0.,0.] and p["hat"]==1,p
joy.hats[0]=(0,0); neutral(poll())
cfg["mapping"]["analog_to_dpad"]=True
joy.axes[:2]=[1.,-1.]
p=poll(); assert p["hat"]==2 and p["axes"]==[1.,-1.],p
joy.axes[:2]=[.5,0.]
p=poll(); assert p["hat"]==3,p
joy.axes[:2]=[.39,0.]
p=poll(); assert p["hat"]==0,p
joy.axes[:2]=[.1,-.1]; neutral(poll())
joy.axes[:2]=[1.,0.]
joy.hats[0]=(-1,0)
p=poll(); assert p["hat"]==0 and p["axes"]==[1.,0.],p
joy.axes[:2]=[0.,0.]
joy.hats[0]=(0,0)
cfg["mapping"]["analog_to_dpad"]=False
cfg["mapping"]["directions"]["de"]="button:10"
cfg["mapping"]["directions"]["ar"]="axis:1:-1"
joy.buttons[10]=True
p=poll(); assert p["hat"]==3 and p["axes"]==[0.,0.],p
joy.buttons[10]=False
joy.axes[1]=-1.
p=poll(); assert p["hat"]==1 and p["axes"]==[0.,-1.],p
joy.axes[1]=0.; neutral(poll())
# A failure cannot cache an unconfirmed state; next poll retries.
joy.axes[0]=1.
transport.fail=True
poll()
assert 1 not in bridge.old_snapshot
transport.fail=False
p=poll(); assert p["axes"]==[1.,0.]
joy.online=False
neutral(poll())
joy.online=True; joy.axes[0]=0.
neutral(poll())
# The legacy profile keeps its original hat->analog behavior.
cfg["mapping"]={"axis_x":0,"axis_y":1,"hat":True}
joy.hats[0]=(1,0)
p=poll(); assert p["hat"]==0 and p["axes"]==[1.,0.],p
joy.hats[0]=(0,0); neutral(poll())
# Remote mode remains independent.
pads.set_mode(2,"dpad")
pads.apply(2,"de",True)
p=transport.history[-1]; assert p["slot"]==2 and p["hat"]==3 and p["axes"]==[0.,0.]
room.set_slot_mode(1,"REMOTO")
assert pads.mode[1]=="dpad"
neutral([p for p in transport.history if p["slot"]==1][-1])
room.close()

# Learning transitions: signed axes, buttons and hats; no held/idle trigger.
initial=h.read_local_inputs(joy)
assert h.learn_local_input(initial,initial,"axis") is None
joy.axes[1]=-1.
assert h.learn_local_input(initial,h.read_local_inputs(joy),"axis")=="axis:1:-1"
joy.axes[1]=0.;joy.hats[0]=(1,0)
assert h.learn_local_input(initial,h.read_local_inputs(joy),"direction")=="hat:0:0:1"
joy.hats[0]=(0,0);joy.buttons[11]=True
assert h.learn_local_input(initial,h.read_local_inputs(joy),"direction")=="button:11"
joy.buttons[11]=False

# Actual modal Tk dialog: learn X by motion and one direction by physical hat.
root=tk.Tk();root.geometry("600x600")
gui=object.__new__(h.MultimandoGUI)
gui.root=root;gui.tk=tk;gui.ttk=ttk;gui.messagebox=messagebox
gui.server=None;gui.local_bridge=bridge
gui._theme()
cfg={"mapping":{}}
errors=[]
def walk(w):
    for child in w.winfo_children():
        yield child
        yield from walk(child)
def pick(w, cls, text):
    return next(x for x in walk(w) if isinstance(x,cls) and str(x.cget("text"))==text)
def drive():
    try:
        dlg=next(w for w in root.winfo_children() if isinstance(w,tk.Toplevel))
        tabs=next(w for w in walk(dlg) if isinstance(w,ttk.Notebook))
        assert [tabs.tab(t,"text") for t in tabs.tabs()]==["BOTONES","ANALÓGICO","DIRECCIONALES"]
        tabs.select(1)
        root.update_idletasks()
        root.update()
        page=root.nametowidget(tabs.tabs()[1])
        learns=[w for w in walk(page) if isinstance(w,ttk.Button) and str(w.cget("text"))=="APRENDER"]
        learns[0].invoke()
        joy.axes[0]=-1.
        def finish_axis():
            try:
                joy.axes[0]=0.
                checks=[w for w in walk(page) if isinstance(w,ttk.Checkbutton)]
                assert checks[0].instate(["selected"]), "negative X learned, invert enabled"
                checks[-1].invoke()
                tabs.select(2);root.update()
                dp=root.nametowidget(tabs.tabs()[2])
                learns2=[w for w in walk(dp) if isinstance(w,ttk.Button) and str(w.cget("text"))=="APRENDER"]
                # Learn right using a physical button, not the analog.
                learns2[-1].invoke();joy.buttons[10]=True
                def finish_dpad():
                    try:
                        joy.buttons[10]=False
                        pick(dlg,ttk.Button,"GUARDAR MAPEO").invoke()
                    except Exception as exc:
                        errors.append(exc);dlg.destroy()
                root.after(150,finish_dpad)
            except Exception as exc:
                errors.append(exc);dlg.destroy()
        root.after(150,finish_axis)
    except Exception as exc:
        errors.append(exc)
        for w in root.winfo_children():
            if isinstance(w,tk.Toplevel): w.destroy()
root.after(100,drive)
gui._edit_local_mapping(root,1,cfg,"Gamepad")
assert not errors, errors
assert cfg["mapping"]["mapping_version"]==2
assert cfg["mapping"]["invert_x"] is True
assert cfg["mapping"]["directions"]["de"]=="button:10"
assert cfg["mapping"]["analog_to_dpad"] is True
assert not bridge.suspended
root.destroy()
print("OK: axes and D-pad independent, mirror, diagonals, hysteresis, neutral, legacy, remote, learning and GUI")
