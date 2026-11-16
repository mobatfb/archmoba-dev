#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pruebas de puntuación KOF: equipo 3 vs 3, PERFECT, reinicios y nombres."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from KOF_Anfitrion import HostServer, NullInput, Room, canonical_player_name
from KOF_Diagnostico_Combate import parse_event


def lua_event(kind, frame, l1, l2, hp1=102, hp2=102, timer=0x59, session="S"):
    # Usar el formato TSV exacto que escribe el script Lua actual.
    fields = ["KOF_DIAG_EVT1", str(frame), str(hp1), str(hp2),
              str(l1), str(l2), str(timer), "0", "0", "0", kind]
    fields.extend(["?" * 64] * 5)
    parsed = parse_event("\t".join(fields))
    if parsed is None:
        raise AssertionError("El evento de prueba no respeta el protocolo Lua.")
    state = parsed.reading
    return {"session": session, "event": parsed.kind, "frame": state.frame,
            "hp1": state.hp1, "hp2": state.hp2,
            "lost1": state.lost1, "lost2": state.lost2, "timer": state.timer}


class NameUniquenessTests(unittest.TestCase):
    def test_names_ignore_case_spaces_and_unicode_compat(self):
        room = Room(NullInput())
        one = room.register("   Ana    María  ")
        self.assertEqual(one.name, "Ana María")
        self.assertEqual(canonical_player_name(one.name), "ana maría")
        for duplicate in ("ana MARÍA", " ANA  MARÍA  "):
            with self.subTest(duplicate=duplicate), self.assertRaisesRegex(ValueError, "ya está en uso"):
                room.register(duplicate)
        self.assertEqual(room.snapshot()["total"], 1)
        room.remove(one.uid)
        self.assertEqual(room.register("aNa mArÍa").slot, 1)

    def test_duplicate_names_blocked_in_waiting_list(self):
        room = Room(NullInput())
        room.register("Ana")
        room.register("Beto")
        waiting = room.register("Carlos")
        self.assertEqual(waiting.slot, 0)
        with self.assertRaisesRegex(ValueError, "ya está en uso"):
            room.register("cARLoS")
        self.assertEqual(room.snapshot()["total"], 3)
        room.remove(waiting.uid)
        self.assertEqual(room.register("CARLOS").queued, True)


class LuaScoreTests(unittest.TestCase):
    def setUp(self):
        self.logs = []
        self.host = HostServer(
            port=0, ui_notify=lambda kind, data: self.logs.append((kind, data)),
            device=NullInput(), restore_state=False, process_provider=lambda: None)
        self.p1 = self.host.room.register("Jugador P1")
        self.p2 = self.host.room.register("Jugador P2")
        self.p1.start_pressed = self.p2.start_pressed = True
        self.host.lua_scorer.start_session("S")
        self.tracker = self.host.lua_scorer

    def tearDown(self):
        self.host._health_socket.close()

    def send(self, kind, frame, l1, l2, **kwargs):
        return self.tracker.on_event(lua_event(kind, frame, l1, l2, **kwargs),
                                     self.host.active_player_pair())

    def p2_loses(self, start=100, loser_winner_hp=(102, 102, 102)):
        result = None
        for number in (1, 2, 3):
            frame = start + number * 20
            hp1 = loser_winner_hp[number - 1]
            self.send("P2_PERSONAJE_PERDIDO", frame, 0, number,
                      hp1=hp1, hp2=254)
            if hp1 == 102:
                self.send("PERFECT_P1_KO", frame, 0, number,
                          hp1=102, hp2=254)
            if number == 3:
                result = self.send("POSIBLE_FIN_EQUIPO_P2",
                                   frame, 0, 3, hp1=hp1, hp2=254)
        return result

    def test_team_win_and_multiple_perfects_are_credited_once(self):
        result = self.p2_loses(loser_winner_hp=(102, 91, 102))
        self.assertEqual(result["winner"], 1)
        self.assertEqual(result["perfect_p1"], 2)
        self.assertEqual(self.host.scores[self.p1.uid], 1)
        self.assertEqual(self.host.losses[self.p2.uid], 1)
        self.assertEqual(self.host.perfects[self.p1.uid], 2)
        # 1 victoria de grupo + 2 PERFECT por personaje = 3 puntos.
        self.assertEqual(self.host.scores[self.p1.uid] +
                         self.host.perfects[self.p1.uid], 3)
        for _ in range(3):
            self.assertIsNone(self.send(
                "POSIBLE_FIN_EQUIPO_P2", 160, 0, 3, hp1=102, hp2=254))
        self.assertEqual(self.host.scores[self.p1.uid], 1)

    def test_perfects_for_both_sides_even_if_one_loses_group(self):
        self.send("P1_PERSONAJE_PERDIDO", 10, 1, 0, hp1=254, hp2=102)
        self.send("PERFECT_P2_KO", 10, 1, 0, hp1=254, hp2=102)
        for n in (1, 2, 3):
            self.send("P2_PERSONAJE_PERDIDO", 20 * n, 1, n, hp1=95, hp2=254)
        final = self.send("POSIBLE_FIN_EQUIPO_P2", 61, 1, 3, hp1=95, hp2=254)
        self.assertEqual(final["winner"], 1)
        self.assertEqual(self.host.perfects.get(self.p2.uid), 1)
        self.assertEqual(self.host.scores.get(self.p1.uid), 1)
        self.assertEqual(self.host.losses.get(self.p2.uid), 1)

    def test_no_score_for_partial_missing_or_replayed_losses(self):
        self.send("P2_PERSONAJE_PERDIDO", 15, 0, 1)
        # Sin evento de baja 2, no premiar 1->3.
        self.send("P2_PERSONAJE_PERDIDO", 40, 0, 3)
        self.assertIsNone(self.send("POSIBLE_FIN_EQUIPO_P2", 40, 0, 3))
        self.assertEqual(self.host.scores, {})
        self.tracker.observe_health(SimpleNamespace(
            rounds_lost_p1=0, rounds_lost_p2=0,
            p1=102, p2=102, timer=0x60))
        self.assertEqual(self.p2_loses()["winner"], 1)

    def test_next_team_win_after_new_match_reset(self):
        self.assertEqual(self.p2_loses()["winner"], 1)
        self.assertIsNone(self.send("SECUENCIA_P2_3_A_0", 170, 0, 0))
        self.tracker.observe_health(SimpleNamespace(
            rounds_lost_p1=0, rounds_lost_p2=0,
            p1=102, p2=102, timer=0x60))
        for n in (1, 2, 3):
            self.send("P1_PERSONAJE_PERDIDO", 200 + 20*n,
                      n, 0, hp1=254, hp2=95)
        result = self.send("POSIBLE_FIN_EQUIPO_P1",
                           261, 3, 0, hp1=254, hp2=95)
        self.assertEqual(result["winner"], 2)
        self.assertEqual(self.host.scores[self.p1.uid], 1)
        self.assertEqual(self.host.scores[self.p2.uid], 1)

    def test_no_result_if_player_changes_mid_match(self):
        self.send("P2_PERSONAJE_PERDIDO", 100, 0, 1)
        self.host.room.remove(self.p1.uid)
        other = self.host.room.register("Nuevo jugador")
        self.assertEqual(other.slot, 1)
        other.start_pressed = True
        self.send("P2_PERSONAJE_PERDIDO", 120, 0, 2)
        self.send("P2_PERSONAJE_PERDIDO", 140, 0, 3)
        self.assertIsNone(self.send("POSIBLE_FIN_EQUIPO_P2", 140, 0, 3))
        self.assertEqual(self.host.scores, {})

    def test_no_score_when_missing_start_or_wrong_session(self):
        self.p2.start_pressed = False
        for n in (1, 2, 3):
            self.send("P2_PERSONAJE_PERDIDO", n*30, 0, n)
        self.assertIsNone(self.send("POSIBLE_FIN_EQUIPO_P2", 91, 0, 3))
        self.assertEqual(self.host.scores, {})
        self.p2.start_pressed = True
        self.assertIsNone(self.tracker.on_event(
            lua_event("POSIBLE_FIN_EQUIPO_P2", 200, 0, 3, session="OLD"),
            self.host.active_player_pair()))
        self.assertEqual(self.host.scores, {})

    def test_fake_perfect_does_not_give_points(self):
        self.send("PERFECT_P1_KO", 15, 0, 0, hp1=102, hp2=254)
        for n in (1, 2, 3):
            self.send("P2_PERSONAJE_PERDIDO", 20*n, 0, n, hp1=70, hp2=254)
        result = self.send("POSIBLE_FIN_EQUIPO_P2", 61, 0, 3, hp1=70, hp2=254)
        self.assertEqual(result["perfect_p1"], 0)
        self.assertNotIn(self.p1.uid, self.host.perfects)


if __name__ == "__main__":
    unittest.main(verbosity=2)
