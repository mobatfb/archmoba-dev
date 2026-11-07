#!/usr/bin/python3
"""PYRION OS: pantalla de inicio plana, sin motor Engine3D."""
import os
import signal
import tkinter as tk

os.environ.setdefault('DISPLAY', ':0')
root = None

def stop(_signal, _frame):
    try:
        if root is not None:
            root.after(1, root.destroy)
    except Exception:
        raise SystemExit(0)

signal.signal(signal.SIGINT, stop)
signal.signal(signal.SIGTERM, stop)


def main():
    global root
    root = tk.Tk()
    root.configure(bg='#070D18')
    root.overrideredirect(True)
    width, height = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f'{width}x{height}+0+0')
    root.lift()
    canvas = tk.Canvas(root, bg='#070D18', highlightthickness=0, bd=0)
    canvas.pack(fill='both', expand=True)
    cx, cy = width // 2, height // 2
    canvas.create_text(cx, cy - 34, text='PYRION OS', fill='#89E9FF',
                       font=('DejaVu Sans', 34, 'bold'))
    canvas.create_text(cx, cy + 22, text='INICIANDO ESCRITORIO', fill='#BED1E7',
                       font=('DejaVu Sans', 11, 'bold'))
    span = min(300, max(150, width // 3))
    bar_bg = canvas.create_rectangle(cx-span//2, cy+65, cx+span//2, cy+70,
                                     fill='#1C3145', outline='')
    bar = canvas.create_rectangle(cx-span//2, cy+65, cx-span//2+20, cy+70,
                                  fill='#44D7FF', outline='')
    state = {'pos': 0}
    def animate():
        if root is None:
            return
        state['pos'] = (state['pos']+7) % max(1, span - 30)
        x = cx - span//2 + state['pos']
        canvas.coords(bar, x, cy+65, x+30, cy+70)
        root.after(65, animate)
    animate()
    root.mainloop()


if __name__ == '__main__':
    main()
