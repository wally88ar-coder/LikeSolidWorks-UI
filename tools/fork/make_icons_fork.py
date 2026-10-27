# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Íconos propios del fork (resources/icons/fork/), con los mismos bloques y colores que
tools/make_icons.py del original (solo blanco, gris, rojo y azul). Diseños propios: nada
de íconos de SOLIDWORKS ni de FreeCAD.

Uso (en la carpeta del repositorio):
    D:/Freecad/bin/python.exe tools/fork/make_icons_fork.py
Para cambiar un ícono se cambia ACÁ y se vuelve a correr (no editar los SVG a mano).
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import make_icons as mk  # noqa: E402

TARGET = os.path.join(os.path.dirname(os.path.dirname(HERE)), "resources", "icons", "fork")

ICONS = {}


def icon(name, title):
    def deco(fn):
        ICONS[name] = (title, fn)
        return fn
    return deco


def _face(d, color):
    return '<path d="%s" fill="%s" stroke="%s" stroke-width="2.2" stroke-linejoin="round"/>' % (
        d, color, mk.OUTLINE)


@icon("material", "Material")
def _():
    # bloque de material: cubo con la cara de arriba veteada en azul
    top = "M32 8 L56 20 L32 32 L8 20 Z"
    left = "M8 20 L32 32 V58 L8 46 Z"
    right = "M56 20 L32 32 V58 L56 46 Z"
    parts = [_face(left, mk.PLANE), _face(right, mk.OLD), _face(top, mk.GEO)]
    for k in range(3):
        y = 14 + 4 * k
        parts.append(mk.thin("M%d %d L%d %d" % (20 + 2 * k, y + 2, 38 + 2 * k, y + 11), mk.NEW, 2.2))
    return parts


@icon("mass", "Propiedades físicas")
def _():
    # pesa con manija y "kg"
    body = "M14 26 H50 L58 58 H6 Z"
    parts = ['<circle cx="32" cy="15" r="8" fill="none" stroke="%s" stroke-width="7"/>' % mk.OUTLINE,
             '<circle cx="32" cy="15" r="8" fill="none" stroke="%s" stroke-width="3.6"/>' % mk.GEO,
             _face(body, mk.GEO), mk.label(32, 51, "kg", mk.NEW, 18)]
    return parts


@icon("equations", "Ecuaciones")
def _():
    # Σ dibujada como geometría (blanco con contorno) y "= x" en azul
    return [mk.geo("M38 10 H8 L24 32 L8 54 H38"), mk.label(51, 32, "=", mk.NEW, 22), mk.label(51, 54, "x", mk.NEW, 20)]


@icon("measure", "Medir")
def _():
    # regla con marcas y la cota azul encima
    parts = [_face("M6 40 H58 V56 H6 Z", mk.GEO)]
    for k, x in enumerate(range(12, 58, 6)):
        h = 9 if k % 2 == 0 else 5
        parts.append(mk.thin("M%d 40 V%d" % (x, 40 + h), mk.OUTLINE, 1.8))
    parts += [mk.thin("M8 14 V34 M56 14 V34", mk.NEW, 2.4),
              mk.arrow(32, 22, 9, 22, mk.NEW, 6.5, 2.6), mk.arrow(32, 22, 55, 22, mk.NEW, 6.5, 2.6)]
    return parts


@icon("solids", "Sólidos")
def _():
    # carpeta de sólidos: cubo blanco
    top = "M32 12 L52 22 L32 32 L12 22 Z"
    left = "M12 22 L32 32 V54 L12 44 Z"
    right = "M52 22 L32 32 V54 L52 44 Z"
    return [_face(left, mk.GEO), _face(right, mk.PLANE), _face(top, mk.GEO)]


@icon("combine", "Combinar")
def _():
    # dos sólidos que se superponen y el contorno azul del resultado
    a = "M8 22 H36 V50 H8 Z"
    b = "M26 12 H54 V40 H26 Z"
    return [_face(a, mk.GEO), _face(b, mk.PLANE),
            mk.new("M8 22 H26 V12 H54 V40 H36 V50 H8 Z")]


@icon("split", "Dividir")
def _():
    # un bloque partido en dos por un plano (línea roja punteada) que se separan
    left = "M6 18 L28 18 L28 52 L6 52 Z"
    right = "M36 12 L58 12 L58 46 L36 46 Z"
    return [_face(left, mk.GEO), _face(right, mk.GEO),
            '<path d="M32 4 V60" stroke="%s" stroke-width="3" stroke-dasharray="5 3"/>' % mk.RED]


def build(target=TARGET):
    os.makedirs(target, exist_ok=True)
    written = []
    for name, (title, fn) in ICONS.items():
        path = os.path.join(target, name + ".svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(mk.svg(title, *fn()))
        written.append(path)
    return written


if __name__ == "__main__":
    out = build(sys.argv[1] if len(sys.argv) > 1 else TARGET)
    print("%d íconos escritos en %s" % (len(out), os.path.dirname(out[0])))
