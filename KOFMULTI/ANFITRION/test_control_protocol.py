#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Verificación del protocolo CONTROL -> WebSocket -> anfitrión -> P1/P2.

No requiere MAME, ViGEmBus ni conexión pública; emplea un dispositivo simulado.
No demuestra que la ROM reciba XInput: eso se comprueba en MAME_XINPUT.log.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys
import threading
import time
import unittest

from websockets.sync.client import connect

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from KOF_Anfitrion import HostServer, NullInput, ACTIONS  # noqa: E402


def control_actions():
    source = (HERE.parent / "CONTROL" / "KOF_Control.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for statement in tree.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "ACTION_MAP"
            for target in statement.targets
        ):
            return ast.literal_eval(statement.value)
    raise AssertionError("CONTROL no contiene ACTION_MAP")


def recv_kind(socket, wanted, tries=15):
    for _ in range(tries):
        message = json.loads(socket.recv(timeout=2))
        if message.get("type") == wanted:
            return message
    raise AssertionError(f"No se recibió {wanted}")


class ControlNetworkTests(unittest.TestCase):
    def setUp(self):
        self.device = NullInput()
        self.logs = []
        self.host = HostServer(
            port=0, ui_notify=lambda kind, value: self.logs.append((kind, value)),
            device=self.device, process_provider=lambda: None,
            restore_state=False)
        self.host.start()
        self.port = self.host.server.socket.getsockname()[1]

    def tearDown(self):
        self.host.stop()

    def connected(self, name):
        ws = connect(f"ws://127.0.0.1:{self.port}", open_timeout=5, close_timeout=2)
        ws.send(json.dumps({"type": "hello", "name": name}))
        welcome = recv_kind(ws, "welcome")
        self.assertEqual(welcome["version"], "1.16.12")
        state = recv_kind(ws, "state")
        return ws, state

    def test_input_reaches_host_and_virtual_adapter(self):
        action_map = control_actions()
        self.assertTrue(set(action_map.values()) <= ACTIONS)
        ws, state = self.connected("Control original")
        try:
            self.assertEqual(state["slot"], 1)
            ws.send(json.dumps({"type": "input", "action": action_map["A"], "down": True}))
            ack = recv_kind(ws, "input_ack")
            self.assertEqual(ack["slot"], 1)
            self.assertEqual(ack["action"], "A")
            ws.send(json.dumps({"type": "input", "action": action_map["A"], "down": False}))
            deadline = time.monotonic() + 2.0
            while not any(event == (1, "A", False) for event in self.device.events):
                self.assertLess(time.monotonic(), deadline, "P1 no liberó A")
                threading.Event().wait(0.02)
            self.assertIn((1, "A", True), self.device.events)
            self.assertIn((1, "A", False), self.device.events)
        finally:
            ws.close()

    def test_both_players_are_assigned_independently(self):
        ws1, state1 = self.connected("Jugador 1")
        ws2, state2 = self.connected("Jugador 2")
        try:
            self.assertEqual((state1["slot"], state2["slot"]), (1, 2))
            ws2.send(json.dumps({"type": "input", "action": "B", "down": True}))
            ack = recv_kind(ws2, "input_ack")
            self.assertEqual((ack["slot"], ack["action"]), (2, "B"))
            self.assertIn((2, "B", True), self.device.events)
        finally:
            ws2.close()
            ws1.close()

    def test_control_start_uses_coin_then_start(self):
        action_map = control_actions()
        ws, state = self.connected("Control Inicio")
        try:
            self.assertEqual(state["slot"], 1)
            ws.send(json.dumps({
                "type": "input", "action": action_map["START"], "down": True}))
            ack = recv_kind(ws, "input_ack")
            self.assertEqual(ack["action"], "COIN_START")
            deadline = time.monotonic() + 3.0
            while (1, "START", True) not in self.device.events:
                self.assertLess(time.monotonic(), deadline, "No llegó COIN+START")
                threading.Event().wait(0.02)
            self.assertIn((1, "COIN", True), self.device.events)
            self.assertIn((1, "START", True), self.device.events)
        finally:
            ws.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
