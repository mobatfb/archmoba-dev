#!/usr/bin/env python3
"""Identificador de FUTUREO VJOY1-8; requiere driver firmado e instalado."""
import tkinter as tk
from tkinter import ttk
import threading
import time
from futureo_vjoy import FutJoy

class App:
    def __init__(self):
        self.root=tk.Tk()
        self.root.title("FUTUREO VJOY | Identificador")
        self.root.geometry("610x430")
        self.root.configure(bg="#0b1424")
        self.status=tk.StringVar(value="Abre joy.cpl y selecciona el mando para observar la prueba")
        self.busy=False
        tk.Label(self.root,text="FUTUREO VJOY  |  8 DISPOSITIVOS",
                 font=("Segoe UI",16,"bold"),fg="white",bg="#0b1424").pack(pady=17)
        grid=tk.Frame(self.root,bg="#0b1424")
        grid.pack(fill="both",expand=True,padx=20,pady=8)
        self.buttons=[]
        for n in range(1,9):
            b=ttk.Button(grid,text=f"IDENTIFICAR VJOY{n}",command=lambda i=n:self.test(i))
            b.grid(row=(n-1)//2,column=(n-1)%2,padx=6,pady=6,sticky="nsew")
            self.buttons.append(b)
        for c in range(2):grid.grid_columnconfigure(c,weight=1)
        for r in range(4):grid.grid_rowconfigure(r,weight=1)
        tk.Label(self.root,textvariable=self.status,wraplength=560,fg="#70dce9",
                 bg="#0b1424").pack(padx=10,pady=16)

    def test(self,n):
        if self.busy:return
        self.busy=True
        for b in self.buttons:b.configure(state="disabled")
        def worker():
            try:
                with FutJoy(n) as device:
                    for sec in range(5,0,-1):
                        self.root.after(0,lambda s=sec:self.status.set(f"VJOY{n}: prueba en {s}..."))
                        time.sleep(1)
                    for _ in range(3):
                        device.state(x=25000,buttons=1)
                        time.sleep(0.3)
                        device.neutral()
                        time.sleep(0.3)
                    self.root.after(0,lambda:self.status.set(f"VJOY{n}: prueba completa"))
            except Exception as ex:
                msg=str(ex)
                self.root.after(0,lambda:self.status.set("Error: "+msg))
            finally:
                self.root.after(0,self.done)
        threading.Thread(target=worker,daemon=True).start()

    def done(self):
        self.busy=False
        for b in self.buttons:b.configure(state="normal")

if __name__=="__main__":
    App().root.mainloop()
