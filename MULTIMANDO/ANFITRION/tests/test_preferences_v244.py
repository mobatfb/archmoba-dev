#!/usr/bin/env python3
"""Persistent preferences test: real Tk, temporary config file, no HID."""
import importlib
import json
import pathlib
import queue
import sys
import tempfile
import time
import tkinter as tk
from tkinter import ttk, messagebox

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
host = importlib.import_module("MULTIMANDO_FUTUREO_Anfitrion_v2_4_4")
assert host.normalize_preferences({"room": {"port": 99, "players": 100, "lan": "yes"},
    "stream": {"mode": "unknown", "size": "1x1", "fps": 99, "quality": False,
               "source": {"kind": "window", "handle": 123}}}) == host.normalize_preferences({})
assert host.normalize_preferences({"stream":{"source":{"kind":"window","label":"Ventana: KOF","hwnd":123}}})["stream"]["source"] == {"kind":"window","label":"Ventana: KOF"}

def build():
    gui = object.__new__(host.MultimandoGUI)
    gui.tk, gui.ttk, gui.messagebox = tk, ttk, messagebox
    gui.root = tk.Tk()
    gui.root.geometry("600x600")
    gui.root.minsize(600, 600)
    gui.server = gui.streamer = gui.tunnel = None
    gui.public_address = gui.api_published = ""
    gui._stream_photo = gui._dashboard_photo = None
    gui.events = queue.Queue()
    gui.member_rows = {}
    gui._closing = False
    gui.settings = host.load_local_settings()
    gui.slot_configs = {
        n: {"mode":"REMOTO", "device":"", "mapping":{},
            **gui.settings.get("slots",{}).get(str(n),{})}
        for n in range(1, host.MAX_PLAYERS+1)
    }
    gui._theme()
    gui._build()
    gui.root.update()
    return gui

def idle(gui):
    deadline = time.monotonic() + .65
    while time.monotonic() < deadline:
        gui.root.update()
        time.sleep(.02)

def stop(gui):
    gui._save_preferences()
    gui.root.destroy()

with tempfile.TemporaryDirectory() as directory:
    host.CONFIG_FILE = pathlib.Path(directory)/"multimando_config.json"
    # Old config file remains readable; existing device mappings survive.
    mapping = {"buttons":{"button_a":3},"axis_x":0,"axis_y":1,
               "hat":True,"invert_y":False,"deadzone":.15}
    slot = {"mode":"CONTROLADO","device":"Gamepad [test] #1","mapping":mapping}
    host.save_local_settings({"slots":{"2":slot}})
    host.list_sources = lambda: [("Pantalla 1 (1920x1080)","screen",1),
                                 ("Ventana: KOF","window",111)]
    gui = build()
    assert gui.slot_configs[2] == slot
    gui.port_var.set("8770")
    gui.player_count_var.set("4")
    gui.lan_var.set(True)
    gui._stream_fast_preset()
    gui.stream_mode_var.set("FUTUREO SMART STREAM")
    gui.stream_source_var.set("Ventana: KOF")
    gui._remember_stream_source()
    idle(gui)
    expected = {
        "schema_version":2,
        "room":{"port":8770,"players":4,"lan":True},
        "stream":{"mode":"smart","size":"320x180","fps":15,"quality":40,
                  "source":{"kind":"window","label":"Ventana: KOF"}},
        "slots":{"2":slot}
    }
    assert host.load_local_settings() == expected, host.load_local_settings()
    assert not host.CONFIG_FILE.with_suffix(".json.tmp").exists()
    # Incomplete port editing retains the last valid port.
    gui.port_var.set("")
    idle(gui)
    assert host.load_local_settings() == expected
    stop(gui)
    # Same window title, different HWND after restarting the game.
    host.list_sources = lambda: [("Pantalla 1 (1920x1080)","screen",1),
                                 ("Ventana: KOF","window",999)]
    gui = build()
    assert gui.port_var.get() == "8770"
    assert gui.player_count_var.get() == "4"
    assert gui.lan_var.get() is True
    assert gui.stream_mode_var.get() == "FUTUREO SMART STREAM"
    assert (gui.stream_size_var.get(), gui.stream_fps_var.get(),
            gui.stream_quality_var.get()) == ("320x180","15","40")
    assert gui.stream_sources[gui.stream_source_var.get()] == ("window",999)
    assert gui.server is None and gui.streamer is None
    assert gui.slot_configs[2] == slot
    # Missing or ambiguous window must not silently select a screen.
    host.list_sources = lambda: [("Pantalla 1 (1920x1080)","screen",1)]
    gui._stream_refresh_sources()
    assert gui.stream_source_var.get() not in gui.stream_sources
    host.list_sources = lambda: [("Ventana: KOF","window",11),
                                 ("Ventana: KOF","window",22)]
    gui._stream_refresh_sources()
    assert gui.stream_source_var.get() not in gui.stream_sources
    # Save monitor by number, not its current resolution.
    host.list_sources = lambda: [("Pantalla 1 (1920x1080)","screen",1)]
    gui._stream_refresh_sources()
    gui.stream_source_var.set("Pantalla 1 (1920x1080)")
    gui._remember_stream_source()
    stop(gui)
    host.list_sources = lambda: [("Pantalla 1 (1280x720)","screen",1)]
    gui = build()
    assert gui.stream_source_var.get() == "Pantalla 1 (1280x720)"
    assert host.load_local_settings()["stream"]["source"] == {"kind":"screen","monitor":1}
    stop(gui)
    # Bad JSON falls back to defaults, no room starts.
    host.CONFIG_FILE.write_text("{ corrupt",encoding="utf-8")
    gui = build()
    assert gui.port_var.get() == str(host.DEFAULT_PORT)
    assert gui.stream_mode_var.get() == "FUTUREO FULL STREAM"
    assert gui.server is None
    stop(gui)
print("OK: autosave, restore, migration, invalid values, new HWND, missing/duplicate title, monitor and corrupt JSON")
