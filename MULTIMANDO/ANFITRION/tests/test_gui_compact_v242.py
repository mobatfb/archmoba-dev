#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prueba de interfaz Tkinter v2.3 bajo Xvfb, sin driver FUTUREO ni cloudflared.

Carga el anfitrion, omite intencionalmente __init__ (Windows) y monta
sus widgets reales con un display virtual Linux. Valida cinco paneles,
asignacion de widgets, cola, botones dinamicos y vista previa.
"""
from __future__ import annotations
import importlib
import io
import pathlib
import queue
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
host = importlib.import_module("MULTIMANDO_FUTUREO_Anfitrion_v2_4_2")

# No necesitamos capturar pantalla: es una prueba estructural y de eventos.
host.list_sources = lambda: [("Pantalla simulada (1280x720)", "screen", 1)]

gui = object.__new__(host.MultimandoGUI)
gui.tk, gui.ttk, gui.messagebox = tk, ttk, messagebox
gui.root = tk.Tk()
gui.root.geometry("600x600")
gui.root.minsize(600, 600)
gui.root.title("Smoke FUTUREO v2.4.2")
gui.server = None
gui.tunnel = None
gui.streamer = None
gui.public_address = ""
gui.api_published = ""
gui._stream_photo = None
gui._dashboard_photo = None
gui.events = queue.Queue()
gui.member_rows = {}
gui._closing = True
gui.slot_configs = {
    n: {"mode": "REMOTO", "device": "", "mapping": {}}
    for n in range(1, host.MAX_PLAYERS + 1)
}

try:
    gui._theme()
    gui._build()
    gui.root.update_idletasks()

    # Tecnologias FULL/DELTA/SMART, sin afectar el selector de calidad.
    assert gui.stream_mode_select.instate(["readonly"])
    assert tuple(gui.stream_mode_select.cget("values")) == (
        "FUTUREO FULL STREAM", "FUTUREO DELTA STREAM", "FUTUREO SMART STREAM")
    assert gui.stream_mode_var.get() == "FUTUREO FULL STREAM"
    gui.stream_mode_var.set("FUTUREO DELTA STREAM")
    assert gui.stream_mode_var.get() == "FUTUREO DELTA STREAM"
    gui.stream_mode_var.set("FUTUREO SMART STREAM")
    assert gui.stream_mode_var.get() == "FUTUREO SMART STREAM"
    gui.stream_mode_var.set("FUTUREO FULL STREAM")


    # Los dos perfiles son accesibles por botones independientes.
    gui._stream_fast_preset()
    assert (gui.stream_size_var.get(), gui.stream_fps_var.get(),
            gui.stream_quality_var.get()) == ("320x180", "15", "40")
    gui._stream_balanced_preset()
    assert (gui.stream_size_var.get(), gui.stream_fps_var.get(),
            gui.stream_quality_var.get()) == ("480x270", "15", "50")
    assert "equilibrado" in gui.stream_status_var.get().lower()


    tabs = gui.notebook.tabs()
    titles = [gui.notebook.tab(tab, "text").strip() for tab in tabs]
    expected = ["INICIO", "TRANSMISION", "JUGADORES Y COLA", "CONFIGURACION", "EVENTOS"]
    assert titles == expected, (titles, expected)

    # Verificar que cada grupo vive en su pestana correcta.
    assert gui.stream_preview_label.winfo_toplevel() is gui.root
    assert gui.tab_stream.winfo_id() != gui.tab_home.winfo_id()
    assert gui.table.winfo_parent() != gui.log.winfo_parent()
    assert gui.port_input.winfo_parent() != gui.table.winfo_parent()
    assert gui.dashboard_preview_label.winfo_parent() != gui.stream_preview_label.winfo_parent()
    assert len(gui.rotate_buttons) == host.MAX_PLAYERS
    assert gui.rotate_buttons[1].winfo_manager() == "pack"
    assert gui.rotate_buttons[2].winfo_manager() == "pack"
    assert gui.rotate_buttons[3].winfo_manager() == ""

    gui.player_count_var.set("4")
    gui._refresh_rotate_buttons()
    assert gui.rotate_buttons[3].winfo_manager() == "pack"
    assert gui.rotate_buttons[4].winfo_manager() == "pack"
    assert gui.rotate_buttons[5].winfo_manager() == ""
    gui.player_count_var.set("2")
    gui._refresh_rotate_buttons()
    assert gui.rotate_buttons[3].winfo_manager() == ""

    # Estado de sala y slots, con mesa de jugadores real.
    gui._roster({
        "players": {"1": {
            "name": "Jugador1", "id": 4, "remaining_seconds": 470,
            "activation_pending": False, "timer_running": False
        }, "2": None},
        "queue": [],
        "total": 1,
        "slot_count": 2,
        "remote_count": 2,
        "slot_modes": {"1": "REMOTO", "2": "REMOTO"}
    })
    assert "P1: Jugador1" in gui.dashboard_slots_var.get()
    assert "P2: LIBRE" in gui.dashboard_slots_var.get()
    assert gui.card_players_var.get().startswith("1/2")
    assert len(gui.table.get_children()) == 2

    # La misma vista de captura se visualiza tanto en Inicio como en Stream.
    img = Image.new("RGB", (480, 270), color=(15, 40, 75))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=55)
    gui.notify("stream_preview", buf.getvalue())
    gui._drain()
    assert gui._stream_photo is not None
    assert gui._dashboard_photo is not None
    assert str(gui.stream_preview_label.cget("image"))
    assert str(gui.dashboard_preview_label.cget("image"))

    # Botones de registro siguen presentes en tab Eventos.
    gui._log("Smoke: evento GUI confirmado")
    assert "Smoke: evento" in gui.log.get("1.0", "end")
    gui._clear_event_log()
    assert "Vista del registro limpiada." in gui.log.get("1.0", "end")

    # Maxima carga de texto y controles visibles a 600x600.
    gui.player_count_var.set("8")
    gui._refresh_rotate_buttons()
    gui._roster({
        "players": {str(n): {
            "name": f"Jugador{n:02}", "id": n, "remaining_seconds": 590,
            "activation_pending": False, "timer_running": False
        } for n in range(1, 9)},
        "queue": [], "total": 8, "slot_count": 8, "remote_count": 8,
        "slot_modes": {str(n): "REMOTO" for n in range(1, 9)}
    })
    gui.pad_var.set("8 FUTUREO_VJOY activos: " +
                    ", ".join(f"FUTUREO_VJOY{n}" for n in range(1, 9)))
    gui.url_var.set("PUBLICO: https://calvin-charles-push-andreas.trycloudflare.com")
    gui.api_var.set("API: URL publicada correctamente.")
    gui.status_var.set("Sala abierta - 8 mandos FUTUREO, jugadores/cola conservados")
    gui.stream_status_var.set(
        "SMART | REAL: 15.0 FPS | procesamiento 12.0 ms | v3 0.15 KB/frame "
        "(JPEG 9.1 KB) | ahorro v3 98.4% | espectadores 12")
    gui.root.update()
    assert (gui.root.winfo_width(), gui.root.winfo_height()) == (600, 600)

    def check_geometry(parent):
        """Detect clipped widgets rather than checking construction only."""
        for child in parent.winfo_children():
            if not child.winfo_ismapped():
                continue
            x, y = child.winfo_x(), child.winfo_y()
            w, h = child.winfo_width(), child.winfo_height()
            assert w > 1 and h > 1, (str(child), w, h)
            assert x >= -1 and y >= -1, (str(child), x, y)
            assert x + w <= parent.winfo_width() + 2, (str(child), x, w, parent.winfo_width())
            assert y + h <= parent.winfo_height() + 2, (str(child), y, h, parent.winfo_height())
            if isinstance(child, (ttk.Button, ttk.Label, ttk.Combobox, ttk.Checkbutton)):
                # For a label the configured wrapping is part of its requested size.
                assert w >= child.winfo_reqwidth() - 2, (str(child), str(child.cget("text")) if not isinstance(child, ttk.Combobox) else "combo", w, child.winfo_reqwidth())
                assert h >= child.winfo_reqheight() - 2, (str(child), h, child.winfo_reqheight())
            check_geometry(child)

    # Verify the fifth notebook tab fits and remains reachable.
    visible_tabs = set()
    for y in range(0, 35, 2):
        for x in range(1, gui.notebook.winfo_width(), 3):
            try:
                visible_tabs.add(gui.notebook.index(f"@{x},{y}"))
            except tk.TclError:
                pass
    assert visible_tabs == set(range(5)), visible_tabs

    for page in (gui.tab_home, gui.tab_stream, gui.tab_players,
                 gui.tab_settings, gui.tab_events):
        gui.notebook.select(page)
        gui.root.update()
        gui._render_previews()
        gui.root.update_idletasks()
        check_geometry(gui.root)
        if page is gui.tab_players:
            assert all(b.winfo_ismapped() for b in gui.rotate_buttons.values())
        if page is gui.tab_home:
            assert gui._dashboard_photo.width() <= gui.dashboard_preview_label.winfo_width()
            assert gui._dashboard_photo.height() <= gui.dashboard_preview_label.winfo_height()
        if page is gui.tab_stream:
            assert gui._stream_photo.width() <= gui.stream_preview_label.winfo_width()
            assert gui._stream_photo.height() <= gui.stream_preview_label.winfo_height()
        print("OK layout 600x600:", gui.notebook.tab(page, "text"))
    print("OK: 5 pestanas, modos FULL DELTA SMART, presets, mandos P1-Pn, preview y eventos")
finally:
    gui.root.destroy()
