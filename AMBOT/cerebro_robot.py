#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cerebro AMBOT 0.1: percepcion, decisiones, memoria y cuerpo simulados."""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

VERSION = "0.1"
CELDA_CM = 40
UMBRAL_OBSTACULO_CM = 30
ORIENTACIONES = ["N", "E", "S", "O"]
FLECHAS = {"N": "^", "E": ">", "S": "v", "O": "<"}
PASOS = {"N": (0, -1), "E": (1, 0), "S": (0, 1), "O": (-1, 0)}
MAPA_INICIAL = (
    "###########",
    "#.........#",
    "#...##....#",
    "#.........#",
    "#..#......#",
    "#......#..#",
    "#.........#",
    "###########",
)

def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower().strip())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")

class Memoria:
    """Hechos persistentes administrados mediante comandos explícitos."""
    def __init__(self, archivo: Path):
        self.archivo = archivo
        self.hechos: dict[str, str] = {}
        if self.archivo.is_file():
            try:
                datos = json.loads(self.archivo.read_text(encoding="utf-8"))
                if isinstance(datos, dict) and isinstance(datos.get("hechos"), dict):
                    self.hechos = {
                        str(k): str(v) for k, v in datos["hechos"].items()
                        if isinstance(k, str) and isinstance(v, str)
                    }
            except (OSError, ValueError):
                print("[AMBOT] No se pudo leer la memoria; iniciando vacia.")

    def guardar(self) -> None:
        self.archivo.parent.mkdir(parents=True, exist_ok=True)
        temporal = self.archivo.with_name(self.archivo.name + ".tmp")
        temporal.write_text(json.dumps(
            {"version": 1, "hechos": self.hechos},
            ensure_ascii=False, indent=2
        ), encoding="utf-8")
        temporal.replace(self.archivo)

    def recordar(self, clave: str, valor: str) -> None:
        self.hechos[normalizar(clave)] = valor.strip()
        self.guardar()

    def consultar(self, clave: str) -> Optional[str]:
        return self.hechos.get(normalizar(clave))

    def olvidar(self, clave: str) -> bool:
        clave = normalizar(clave)
        if clave not in self.hechos:
            return False
        del self.hechos[clave]
        self.guardar()
        return True

@dataclass
class Sensores:
    distancia_frontal_cm: int
    bateria_pct: float
    posicion: tuple[int, int]
    orientacion: str

class CuerpoSimulado:
    """Cuerpo digital seguro; no envia señales a hardware real."""
    def __init__(self):
        self.mapa = MAPA_INICIAL
        self.x, self.y = 5, 3
        self.orientacion = "E"
        self.bateria = 100.0
        self.pasos = 0

    def libre(self, x: int, y: int) -> bool:
        return (
            0 <= y < len(self.mapa)
            and 0 <= x < len(self.mapa[y])
            and self.mapa[y][x] != "#"
        )

    def percibir(self) -> Sensores:
        dx, dy = PASOS[self.orientacion]
        x, y = self.x + dx, self.y + dy
        libres = 0
        while self.libre(x, y):
            libres += 1
            x, y = x + dx, y + dy
        return Sensores(
            libres * CELDA_CM + 10, round(self.bateria, 1),
            (self.x, self.y), self.orientacion
        )

    def girar(self, sentido: str) -> str:
        if self.bateria < .3:
            return "Bateria insuficiente: robot detenido."
        idx = ORIENTACIONES.index(self.orientacion)
        self.orientacion = ORIENTACIONES[(idx + (1 if sentido == "derecha" else -1)) % 4]
        self.bateria = max(0., round(self.bateria - .3, 1))
        return f"Giro a la {sentido}. Ahora miro hacia {self.orientacion}."

    def avanzar(self) -> str:
        s = self.percibir()
        if self.bateria < 1.5:
            return "SEGURIDAD: bateria demasiado baja. Movimiento cancelado."
        if s.distancia_frontal_cm < UMBRAL_OBSTACULO_CM:
            return f"SEGURIDAD: obstaculo a {s.distancia_frontal_cm} cm. No avanzo."
        dx, dy = PASOS[self.orientacion]
        if not self.libre(self.x + dx, self.y + dy):
            return "SEGURIDAD: paso ocupado. No avanzo."
        self.x += dx
        self.y += dy
        self.pasos += 1
        self.bateria = max(0., round(self.bateria - 1.5, 1))
        return f"Avance seguro. Nueva posicion: ({self.x}, {self.y})."

    def retroceder(self) -> str:
        if self.bateria < 1.5:
            return "SEGURIDAD: bateria demasiado baja. Movimiento cancelado."
        dx, dy = PASOS[self.orientacion]
        if not self.libre(self.x - dx, self.y - dy):
            return "SEGURIDAD: obstaculo detras. No retrocedo."
        self.x -= dx
        self.y -= dy
        self.pasos += 1
        self.bateria = max(0., round(self.bateria - 1.5, 1))
        return f"Retroceso seguro. Nueva posicion: ({self.x}, {self.y})."

    def ver_mapa(self) -> str:
        filas = []
        for y, fila in enumerate(self.mapa):
            if y == self.y:
                fila = fila[:self.x] + FLECHAS[self.orientacion] + fila[self.x + 1:]
            filas.append(fila)
        return "\n".join(filas) + "\n# = pared; ^ > v < = orientacion"

class Cerebro:
    def __init__(self, cuerpo: CuerpoSimulado, memoria: Memoria):
        self.cuerpo = cuerpo
        self.memoria = memoria

    def decidir(self) -> tuple[str, str]:
        s = self.cuerpo.percibir()
        if s.bateria_pct < 1.5:
            return "parar", "Bateria baja: prioridad de seguridad."
        if s.distancia_frontal_cm < UMBRAL_OBSTACULO_CM:
            return "girar", f"Veo un obstaculo a {s.distancia_frontal_cm} cm; decido girar a la derecha."
        return "avanzar", f"Veo {s.distancia_frontal_cm} cm libres al frente; decido avanzar una celda."

    def ciclo(self) -> str:
        accion, motivo = self.decidir()
        if accion == "parar":
            return "PIENSO: " + motivo + "\nACTUO: me detengo."
        resultado = self.cuerpo.girar("derecha") if accion == "girar" else self.cuerpo.avanzar()
        return f"PIENSO: {motivo}\nACTUO: {resultado}"

    def ejecutar(self, comando: str) -> tuple[str, bool]:
        original = comando.strip()
        limpio = normalizar(original)
        if not original:
            return "", False
        if limpio in {"salir", "exit", "cerrar"}:
            return "Cerebro apagado. Hasta pronto.", True
        if limpio in {"ayuda", "help", "?"}:
            return AYUDA, False
        if limpio in {"mapa", "ver mapa"}:
            return self.cuerpo.ver_mapa(), False
        if limpio in {"estado", "sensores", "sensor", "donde estoy"}:
            s = self.cuerpo.percibir()
            return (f"Posicion: {s.posicion} | Orientacion: {s.orientacion} | "
                    f"Distancia frontal: {s.distancia_frontal_cm} cm | "
                    f"Bateria: {s.bateria_pct}% | Pasos: {self.cuerpo.pasos}"), False
        if limpio in {"avanza", "avanzar", "adelante"}:
            return self.cuerpo.avanzar(), False
        if limpio in {"retrocede", "retroceder", "atras"}:
            return self.cuerpo.retroceder(), False
        if limpio in {"gira izquierda", "girar izquierda", "izquierda"}:
            return self.cuerpo.girar("izquierda"), False
        if limpio in {"gira derecha", "girar derecha", "derecha"}:
            return self.cuerpo.girar("derecha"), False
        if limpio in {"alto", "detente", "stop", "para", "parar"}:
            return "Detenido: no se enviaran movimientos.", False
        if limpio in {"plan", "que harias", "que piensas"}:
            return "PIENSO: " + self.decidir()[1], False
        if limpio in {"explora", "explorar", "piensa y actua"}:
            return self.ciclo(), False
        auto = re.fullmatch(r"auto(?:\s+(\d+))?", limpio)
        if auto:
            cantidad = int(auto.group(1) or "5")
            if not 1 <= cantidad <= 25:
                return "Usa 'auto 1' hasta 'auto 25'.", False
            registros = []
            for i in range(cantidad):
                registros.append(f"[{i + 1}/{cantidad}] {self.ciclo()}")
                if self.cuerpo.bateria < 1.5:
                    break
            return "\n".join(registros), False
        if limpio == "memoria":
            if not self.memoria.hechos:
                return "Mi memoria aun no tiene hechos guardados.", False
            return "MEMORIA:\n" + "\n".join(
                f"- {k}: {v}" for k, v in sorted(self.memoria.hechos.items())
            ), False
        if limpio.startswith("recuerda "):
            contenido = original[len("recuerda "):]
            if "=" not in contenido:
                return "Formato: recuerda nombre = Robot Uno", False
            clave, valor = (trozo.strip() for trozo in contenido.split("=", 1))
            if not clave or not valor or len(clave) > 80 or len(valor) > 500:
                return "La clave y el valor deben tener contenido y longitud moderada.", False
            try:
                self.memoria.recordar(clave, valor)
                return f"He aprendido '{clave}' = '{valor}'. Lo recordare al reiniciar.", False
            except OSError as exc:
                return f"No pude guardar la memoria: {exc}", False
        for prefijo in ("que sabes de ", "que recuerdas de ", "recuerdas "):
            if limpio.startswith(prefijo):
                clave = original[len(prefijo):].strip().rstrip("?")
                valor = self.memoria.consultar(clave)
                return ((f"Recuerdo que '{clave}' = '{valor}'." if valor is not None
                         else f"No tengo un recuerdo sobre '{clave}'."), False)
        if limpio.startswith("olvida "):
            clave = original[len("olvida "):].strip()
            try:
                ok = self.memoria.olvidar(clave)
                return (f"He olvidado '{clave}'." if ok
                        else f"No encontre '{clave}' en la memoria."), False)
            except OSError as exc:
                return f"No pude actualizar la memoria: {exc}", False
        return ("No reconozco esa instruccion todavia. Escribe 'ayuda'. "
                "Mi lenguaje es limitado en la version 0.1."), False

AYUDA = """COMANDOS DISPONIBLES:
  estado                Ver sensores, posicion y bateria
  mapa                  Mostrar mundo simulado
  plan                  Explicar la proxima decision
  explora               Percibir, decidir y actuar una vez
  auto 5                Explorar autonomamente 5 ciclos (maximo 25)
  avanza                Avanzar una celda, si es seguro
  retrocede             Retroceder una celda, si es seguro
  gira izquierda        Girar 90 grados a la izquierda
  gira derecha          Girar 90 grados a la derecha
  detente               Orden de parada
  recuerda clave = dato Guardar un conocimiento persistente
  que sabes de clave    Consultar un conocimiento guardado
  memoria               Mostrar conocimientos guardados
  olvida clave          Borrar un conocimiento
  salir                 Cerrar el programa
IMPORTANTE: Los sensores, los motores y el mundo son SIMULADOS."""

def main() -> None:
    parser = argparse.ArgumentParser(description="Cerebro robotico simulado AMBOT")
    parser.add_argument("--memoria", type=Path,
                        default=Path.home() / ".archmoba_robot" / "memoria.json")
    args = parser.parse_args()
    cerebro = Cerebro(CuerpoSimulado(), Memoria(args.memoria))
    print(f"ARCHMOBA | AMBOT BRAIN v{VERSION}")
    print(cerebro.cuerpo.ver_mapa())
    while True:
        try:
            mensaje = input("\nTU > ")
        except (KeyboardInterrupt, EOFError):
            break
        respuesta, salir = cerebro.ejecutar(mensaje)
        if respuesta:
            print("ROBOT > " + respuesta)
        if salir:
            break

if __name__ == "__main__":
    main()
