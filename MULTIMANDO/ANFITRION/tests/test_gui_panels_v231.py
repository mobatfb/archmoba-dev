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
host = importlib.import_module("MULTIMANDO_FUTUREO_Anfitrion_v2_3_1")

# No necesitamos capturar pantalla: es una prueba estructural y de eventos.
host.list_sources = lambda: [("Pantalla simulada (1280x720)", "screen", 1)]

gui = object.__new__(host.MultimandoGUI)
gui.tk, gui.ttk, gui.messagebox = tk, ttk, messagebox
gui.root = tk.Tk()
gui.root.withdraw()
gui.root.title("Smoke FUTUREO v2.3.1")
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

    for page in (gui.tab_home, gui.tab_stream, gui.tab_players,
                 gui.tab_settings, gui.tab_events):
        gui.notebook.select(page)
        gui.root.update_idletasks()
    print("OK: 5 pestanas, presets rapido/equilibrado, mandos P1-Pn, cola, preview y eventos")
finally:
    gui.root.destroy()
