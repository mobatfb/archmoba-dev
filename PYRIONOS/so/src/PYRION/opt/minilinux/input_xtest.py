#!/usr/bin/python3
import ctypes
import fcntl
import glob
import os
import select
import struct
import sys
import time

# Linux input-event constants
EV_SYN=0x00; EV_KEY=0x01; EV_REL=0x02; EV_ABS=0x03
SYN_REPORT=0
REL_X=0x00; REL_Y=0x01; REL_HWHEEL=0x06; REL_WHEEL=0x08
ABS_X=0x00; ABS_Y=0x01
BTN_LEFT=0x110; BTN_RIGHT=0x111; BTN_MIDDLE=0x112
BTN_SIDE=0x113; BTN_EXTRA=0x114; BTN_FORWARD=0x115; BTN_BACK=0x116
KEY_A=30; KEY_ENTER=28; KEY_SPACE=57
EVENT=struct.Struct('llHHi')

# Linux ioctl helpers: _IOR('E', nr, size)
def ior(nr,size):
    return 0x80000000 | ((size & 0x3fff) << 16) | (ord('E') << 8) | nr

def bit(buf,n):
    i=n >> 3
    return i < len(buf) and bool(buf[i] & (1 << (n & 7)))

def ioctl_bits(fd, ev, size):
    buf=bytearray(size)
    try:
        fcntl.ioctl(fd, ior(0x20+ev,size), buf, True)
    except OSError:
        return bytearray(size)
    return buf

def device_name(fd):
    b=bytearray(256)
    try:
        fcntl.ioctl(fd, ior(0x06,len(b)), b, True)
        return bytes(b).split(b'\0',1)[0].decode('utf-8','replace') or 'desconocido'
    except OSError:
        return 'desconocido'

def query_abs(fd, code):
    try:
        buf=bytearray(24)
        fcntl.ioctl(fd, 0x80184540 + code, buf, True)
        value, mn, mx, fuzz, flat, res = struct.unpack('iiiiii', buf)
        return (mn,mx)
    except OSError:
        return (0,65535)

def inspect(path):
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NONBLOCK)
    except OSError:
        return None
    types=ioctl_bits(fd,0,16)
    keys=ioctl_bits(fd,EV_KEY,96) if bit(types,EV_KEY) else bytearray(96)
    rels=ioctl_bits(fd,EV_REL,16) if bit(types,EV_REL) else bytearray(16)
    abss=ioctl_bits(fd,EV_ABS,16) if bit(types,EV_ABS) else bytearray(16)
    d={
        'path':path, 'fd':fd, 'name':device_name(fd),
        'keyboard': bit(keys,KEY_A) and bit(keys,KEY_ENTER) and bit(keys,KEY_SPACE),
        'relptr': bit(rels,REL_X) and bit(rels,REL_Y) and bit(keys,BTN_LEFT),
        'absptr': bit(abss,ABS_X) and bit(abss,ABS_Y) and bit(keys,BTN_LEFT),
    }
    d['xrng']=query_abs(fd,ABS_X) if d['absptr'] else (0,65535)
    d['yrng']=query_abs(fd,ABS_Y) if d['absptr'] else (0,65535)
    return d

def scan_devices():
    devs=[]
    for p in sorted(glob.glob('/dev/input/event*')):
        d=inspect(p)
        if d:
            devs.append(d)
    return devs

def choose_devices(devs):
    rel=[d for d in devs if d['relptr']]
    ab=[d for d in devs if d['absptr']]

    def abs_score(d):
        n=d['name'].lower()
        score=0
        # Debian's in-kernel vboxguest integration device is the preferred
        # movement source. Opening it tells VirtualBox that the guest accepts
        # absolute coordinates and enables seamless pointer integration.
        if 'virtualbox mouse integration' in n: score += 1000
        if 'mouse integration' in n: score += 300
        if 'virtualbox' in n: score += 100
        if 'tablet' in n: score += 80
        if 'usb' in n: score += 30
        return score

    abs_sorted=sorted(ab,key=abs_score,reverse=True)
    move=abs_sorted[0] if abs_sorted else (rel[0] if rel else None)
    move_mode='absolute' if move in ab else ('relative' if move else None)

    # vboxguest provides the absolute position, while the ordinary emulated
    # PS/2/USB mouse remains the most reliable source for buttons and wheel.
    # This also prevents a second device from contributing motion deltas.
    button=None
    if move:
        n=move['name'].lower()
        native=('virtualbox mouse integration' in n or 'mouse integration' in n)
        if native:
            other_rel=[d for d in rel if d is not move]
            other_abs=[d for d in abs_sorted if d is not move]
            button=other_rel[0] if other_rel else (other_abs[0] if other_abs else move)
        else:
            button=move

    keyboards=[d for d in devs if d['keyboard'] and d is not move and d is not button]
    return move,move_mode,button,keyboards

class XTest:
    def __init__(self, display_name=None):
        self.x11=ctypes.CDLL('libX11.so.6')
        self.xt=ctypes.CDLL('libXtst.so.6')
        self.x11.XOpenDisplay.argtypes=[ctypes.c_char_p]
        self.x11.XOpenDisplay.restype=ctypes.c_void_p
        self.x11.XDefaultScreen.argtypes=[ctypes.c_void_p]
        self.x11.XDefaultScreen.restype=ctypes.c_int
        self.x11.XDisplayWidth.argtypes=[ctypes.c_void_p,ctypes.c_int]
        self.x11.XDisplayWidth.restype=ctypes.c_int
        self.x11.XDisplayHeight.argtypes=[ctypes.c_void_p,ctypes.c_int]
        self.x11.XDisplayHeight.restype=ctypes.c_int
        self.x11.XRootWindow.argtypes=[ctypes.c_void_p,ctypes.c_int]
        self.x11.XRootWindow.restype=ctypes.c_ulong
        self.x11.XQueryPointer.argtypes=[ctypes.c_void_p,ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_int),ctypes.POINTER(ctypes.c_uint)]
        self.x11.XQueryPointer.restype=ctypes.c_int
        self.x11.XFlush.argtypes=[ctypes.c_void_p]
        self.x11.XFlush.restype=ctypes.c_int
        self.xt.XTestFakeMotionEvent.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_ulong]
        self.xt.XTestFakeMotionEvent.restype=ctypes.c_int
        self.xt.XTestFakeRelativeMotionEvent.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_ulong]
        self.xt.XTestFakeRelativeMotionEvent.restype=ctypes.c_int
        self.xt.XTestFakeButtonEvent.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_int,ctypes.c_ulong]
        self.xt.XTestFakeButtonEvent.restype=ctypes.c_int
        self.xt.XTestFakeKeyEvent.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_int,ctypes.c_ulong]
        self.xt.XTestFakeKeyEvent.restype=ctypes.c_int
        name=(display_name or os.environ.get('DISPLAY') or ':0').encode()
        self.dpy=None
        for _ in range(100):
            self.dpy=self.x11.XOpenDisplay(name)
            if self.dpy:
                break
            time.sleep(.05)
        if not self.dpy:
            raise RuntimeError('XOpenDisplay fallo para %r' % name.decode(errors='replace'))
        self.screen=self.x11.XDefaultScreen(self.dpy)
        self.width=self.x11.XDisplayWidth(self.dpy,self.screen)
        self.height=self.x11.XDisplayHeight(self.dpy,self.screen)
        if self.width < 2 or self.height < 2:
            raise RuntimeError('tamano X invalido: %dx%d' % (self.width,self.height))

    def flush(self):
        self.x11.XFlush(self.dpy)

    def motion_abs(self,x,y):
        x=max(0,min(self.width-1,int(x)))
        y=max(0,min(self.height-1,int(y)))
        self.xt.XTestFakeMotionEvent(self.dpy,self.screen,x,y,0)

    def motion_rel(self,dx,dy):
        self.xt.XTestFakeRelativeMotionEvent(self.dpy,int(dx),int(dy),0)

    def button(self,b,down):
        self.xt.XTestFakeButtonEvent(self.dpy,int(b),1 if down else 0,0)

    def key(self,keycode,down):
        # Xorg's standard evdev keycode convention is Linux keycode + 8.
        self.xt.XTestFakeKeyEvent(self.dpy,int(keycode)+8,1 if down else 0,0)

    def pointer_xy(self):
        root=self.x11.XRootWindow(self.dpy,self.screen)
        rr=ctypes.c_ulong(); cr=ctypes.c_ulong(); rx=ctypes.c_int(); ry=ctypes.c_int()
        wx=ctypes.c_int(); wy=ctypes.c_int(); mask=ctypes.c_uint()
        self.x11.XQueryPointer(self.dpy,root,ctypes.byref(rr),ctypes.byref(cr),
            ctypes.byref(rx),ctypes.byref(ry),ctypes.byref(wx),ctypes.byref(wy),ctypes.byref(mask))
        return rx.value,ry.value

def scale_abs(v,rng,outmax):
    mn,mx=rng
    if mx <= mn:
        return max(0,min(outmax,int(v)))
    return max(0,min(outmax,int(round((v-mn)*float(outmax)/(mx-mn)))))

def selftest():
    x=XTest()
    points=[(1,1),(x.width//2,x.height//2),(x.width-2,x.height-2)]
    ok=True
    for px,py in points:
        x.motion_abs(px,py); x.flush(); time.sleep(.03)
        got=x.pointer_xy()
        print('XTEST',px,py,'->',got)
        if abs(got[0]-px)>1 or abs(got[1]-py)>1:
            ok=False
    x.motion_rel(-10,-10); x.flush(); time.sleep(.03)
    print('XTEST relative ->',x.pointer_xy())
    return 0 if ok else 2

def main():
    x=XTest()
    devs=[]; move=None; mode=None; button=None; keyboards=[]
    for _ in range(80):
        devs=scan_devices(); move,mode,button,keyboards=choose_devices(devs)
        if move and keyboards:
            break
        for d in devs:
            try: os.close(d['fd'])
            except OSError: pass
        time.sleep(.1)

    print('MiniLinux VirtualBox native input -> XTest bridge 1.8',flush=True)
    print('X screen: %dx%d' % (x.width,x.height),flush=True)
    for d in devs:
        print('  %s name=%r keyboard=%s relptr=%s absptr=%s xrange=%s yrange=%s' % (
            d['path'],d['name'],d['keyboard'],d['relptr'],d['absptr'],d['xrng'],d['yrng']),flush=True)
    if not move:
        raise RuntimeError('no se encontro fuente de movimiento REL_X/REL_Y ni ABS_X/ABS_Y')

    print('MOVIMIENTO: %s (%s) modo=%s' % (move['path'],move['name'],mode),flush=True)
    if button:
        print('BOTONES/RUEDA: %s (%s)' % (button['path'],button['name']),flush=True)
    for k in keyboards:
        print('TECLADO: %s (%s)'%(k['path'],k['name']),flush=True)
    if not keyboards:
        print('AVISO: no se encontro teclado completo; continuando solo con mouse',flush=True)

    native_vbox='mouse integration' in move['name'].lower()
    if native_vbox:
        print('VBOX_NATIVE=1: VirtualBox debe liberar la captura al abrir este dispositivo.',flush=True)
    else:
        print('VBOX_NATIVE=0: usando fallback de dispositivo emulado.',flush=True)

    active={}
    active[move['fd']]=('move',move)
    if button is not None:
        if button['fd']==move['fd']:
            active[move['fd']]=('movebuttons',move)
        else:
            active[button['fd']]=('buttons',button)
    for k in keyboards:
        active[k['fd']]=('keyboard',k)
    fds=list(active)

    btnmap={BTN_LEFT:1,BTN_MIDDLE:2,BTN_RIGHT:3,BTN_SIDE:8,BTN_EXTRA:9,BTN_FORWARD:10,BTN_BACK:11}
    relx=rely=0
    last_abs_x=last_abs_y=None
    changed_abs=False

    while True:
        rd,_,_=select.select(fds,[],[],1.0)
        for fd in rd:
            role,d=active.get(fd,(None,None))
            while True:
                try:
                    data=os.read(fd,EVENT.size*64)
                except BlockingIOError:
                    break
                except OSError as e:
                    print('input cerrado:',d['path'] if d else fd,repr(e),flush=True)
                    if fd in fds:
                        fds.remove(fd)
                    break
                if not data:
                    break
                for off in range(0,len(data)-EVENT.size+1,EVENT.size):
                    _,_,typ,code,val=EVENT.unpack_from(data,off)
                    if role=='keyboard':
                        if typ==EV_KEY and code < 256 and val in (0,1):
                            x.key(code,val==1); x.flush()
                        continue

                    # Buttons may come from a separate PS/2/USB pointer while
                    # movement comes from the native VirtualBox integration device.
                    if role in ('buttons','movebuttons'):
                        if typ==EV_KEY and code in btnmap and val in (0,1):
                            x.button(btnmap[code],val==1); x.flush()
                            continue
                        if typ==EV_REL and code==REL_WHEEL and val:
                            b=4 if val>0 else 5
                            for _ in range(abs(val)):
                                x.button(b,True); x.button(b,False)
                            x.flush(); continue
                        if typ==EV_REL and code==REL_HWHEEL and val:
                            b=7 if val>0 else 6
                            for _ in range(abs(val)):
                                x.button(b,True); x.button(b,False)
                            x.flush(); continue

                    if role not in ('move','movebuttons'):
                        continue

                    if typ==EV_REL and mode=='relative':
                        if code==REL_X: relx += val
                        elif code==REL_Y: rely += val
                    elif typ==EV_ABS and mode=='absolute':
                        if code==ABS_X:
                            last_abs_x=scale_abs(val,d['xrng'],x.width-1); changed_abs=True
                        elif code==ABS_Y:
                            last_abs_y=scale_abs(val,d['yrng'],x.height-1); changed_abs=True
                    elif typ==EV_SYN and code==SYN_REPORT:
                        if mode=='relative' and (relx or rely):
                            x.motion_rel(relx,rely); relx=rely=0; x.flush()
                        elif mode=='absolute' and changed_abs and last_abs_x is not None and last_abs_y is not None:
                            x.motion_abs(last_abs_x,last_abs_y); changed_abs=False; x.flush()
        if not fds:
            raise RuntimeError('todos los dispositivos de entrada se cerraron')

if __name__=='__main__':
    if '--selftest' in sys.argv:
        raise SystemExit(selftest())
    try:
        main()
    except Exception as e:
        print('ERROR:',repr(e),flush=True)
        raise
