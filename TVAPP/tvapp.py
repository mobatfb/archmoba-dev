"""Interfaz mostrada dentro de app.py. Cambia VERSION en cada publicacion."""

import tkinter as tk

VERSION = "1.0.2"


def render(parent):
    """Devuelve un widget incrustable en el cuerpo de app.py."""
    pantalla = tk.Frame(parent, bg="white")
    texto = tk.Label(
        pantalla,
        text="Hola rosss",
        bg="white",
        fg="#111827",
        font=("Segoe UI", 28, "bold"),
        wraplength=490,
        justify="center",
    )
    texto.place(relx=0.5, rely=0.5, anchor="center")
    return pantalla
