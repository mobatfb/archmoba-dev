"""TVAPP: interfaz movil; embebible en app.py o ejecutable por separado."""

import tkinter as tk

VERSION = "1.0.6"
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 800


def render(parent):
    """Crea una pantalla adaptable al espacio disponible."""
    pantalla = tk.Frame(parent, bg="black")
    texto = tk.Label(
        pantalla,
        text="Hola rosss",
        bg="black",
        fg="white",
        font=("Segoe UI", 28, "bold"),
        wraplength=340,
        justify="center",
    )
    texto.place(relx=0.5, rely=0.5, anchor="center")
    pantalla.bind(
        "<Configure>",
        lambda event: texto.configure(wraplength=max(240, event.width - 32)),
    )
    return pantalla


def main():
    """Abre tvapp.py como una aplicacion movil independiente en Windows."""
    ventana = tk.Tk()
    ventana.title(f"TVAPP - v{VERSION}")
    ventana.configure(bg="black")
    ventana.minsize(360, 640)
    ventana.update_idletasks()
    x = max(0, (ventana.winfo_screenwidth() - WINDOW_WIDTH) // 2)
    y = max(0, (ventana.winfo_screenheight() - WINDOW_HEIGHT) // 2)
    ventana.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x}+{y}")
    ventana.resizable(False, False)
    render(ventana).pack(fill="both", expand=True)
    ventana.mainloop()


if __name__ == "__main__":
    main()
