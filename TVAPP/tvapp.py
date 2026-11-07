"""TVAPP: interfaz movil fija; embebible en app.py o ejecutable por separado."""

import os
import tkinter as tk

VERSION = "1.0.7"
WINDOW_WIDTH = 400
WINDOW_HEIGHT = 800


def lock_mobile_window(window):
    """Impide maximizar, ajustar o cambiar las dimensiones de la ventana."""
    if getattr(window, "_archmoba_mobile_size_locked", False):
        return
    window._archmoba_mobile_size_locked = True
    window.resizable(False, False)
    window.minsize(WINDOW_WIDTH, WINDOW_HEIGHT)
    window.maxsize(WINDOW_WIDTH, WINDOW_HEIGHT)

    def restore_size():
        try:
            state = window.state()
            if state == "zoomed":
                window.state("normal")
            if window.state() == "normal" and (
                window.winfo_width() != WINDOW_WIDTH
                or window.winfo_height() != WINDOW_HEIGHT
            ):
                window.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        except tk.TclError:
            pass

    def on_resize(event):
        if event.widget is window:
            window.after_idle(restore_size)

    window.bind("<Configure>", on_resize, add="+")
    window.after_idle(restore_size)

    if os.name == "nt":
        def disable_maximize():
            """Quita el boton maximizar y el ajuste Snap en Windows."""
            try:
                import ctypes
                from ctypes import wintypes

                user32 = ctypes.WinDLL("user32", use_last_error=True)
                user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
                user32.GetAncestor.restype = wintypes.HWND
                user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
                user32.GetWindowLongW.restype = ctypes.c_long
                user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_long]
                user32.SetWindowLongW.restype = ctypes.c_long
                user32.SetWindowPos.argtypes = [
                    wintypes.HWND, wintypes.HWND,
                    ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                    wintypes.UINT,
                ]
                user32.SetWindowPos.restype = wintypes.BOOL

                hwnd = user32.GetAncestor(wintypes.HWND(window.winfo_id()), 2)
                if hwnd:
                    style = user32.GetWindowLongW(hwnd, -16)
                    # WS_MAXIMIZEBOX | WS_THICKFRAME
                    fixed_style = style & ~0x00050000
                    if fixed_style != style:
                        user32.SetWindowLongW(hwnd, -16, fixed_style)
                        # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_FRAMECHANGED
                        user32.SetWindowPos(hwnd, wintypes.HWND(0), 0, 0, 0, 0, 0x27)
            except (OSError, AttributeError, ValueError):
                pass

        window.after_idle(disable_maximize)


def render(parent):
    """Crea una pantalla negra, sin permitir ampliar la ventana principal."""
    lock_mobile_window(parent.winfo_toplevel())
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
    lock_mobile_window(ventana)
    render(ventana).pack(fill="both", expand=True)
    ventana.mainloop()


if __name__ == "__main__":
    main()
