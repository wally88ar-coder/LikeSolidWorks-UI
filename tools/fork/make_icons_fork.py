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


@icon("move_face", "Mover cara")
def _():
    # bloque con la cara de arriba corrida hacia arriba (contorno azul) y la flecha
    top = "M30 28 L54 36 L34 46 L10 38 Z"
    left = "M10 38 L34 46 V60 L10 52 Z"
    right = "M54 36 L34 46 V60 L54 50 Z"
    return [_face(left, mk.GEO), _face(right, mk.PLANE), _face(top, mk.GEO),
            mk.new("M30 10 L54 18 L34 28 L10 20 Z"), mk.arrow(32, 37, 32, 16, mk.NEW, 7.0, 3.2)]


@icon("move_bodies", "Mover/Copiar sólido")
def _():
    # bloque gris (antes) y el mismo bloque blanco corrido, con la flecha azul
    def block(x, y, color):
        top = "M%d %d L%d %d L%d %d L%d %d Z" % (x + 12, y, x + 26, y + 7, x + 14, y + 13, x, y + 6)
        left = "M%d %d L%d %d V%d L%d %d Z" % (x, y + 6, x + 14, y + 13, y + 27, x, y + 20)
        right = "M%d %d L%d %d V%d L%d %d Z" % (x + 26, y + 7, x + 14, y + 13, y + 27, x + 26, y + 21)
        return [_face(left, color), _face(right, mk.PLANE if color == mk.GEO else mk.OLD), _face(top, color)]
    return block(4, 30, mk.OLD) + block(34, 6, mk.GEO) + [mk.arrow(20, 34, 40, 22, mk.NEW, 7.0, 3.2)]


@icon("delete_bodies", "Eliminar/Conservar sólido")
def _():
    # dos bloques: uno blanco que queda y uno gris tachado con la cruz roja
    keep_top = "M14 22 L30 30 L16 37 L2 29 Z"
    keep_left = "M2 29 L16 37 V54 L2 46 Z"
    keep_right = "M30 30 L16 37 V54 L30 47 Z"
    gone_top = "M46 8 L62 16 L48 23 L34 15 Z"
    gone_left = "M34 15 L48 23 V40 L34 32 Z"
    gone_right = "M62 16 L48 23 V40 L62 33 Z"
    return [_face(keep_left, mk.GEO), _face(keep_right, mk.PLANE), _face(keep_top, mk.GEO),
            _face(gone_left, mk.OLD), _face(gone_right, mk.OLD), _face(gone_top, mk.OLD),
            mk.thin("M38 12 L60 38 M60 12 L38 38", mk.RED, 4.0)]


@icon("split", "Dividir")
def _():
    # un bloque partido en dos por un plano (línea roja punteada) que se separan
    left = "M6 18 L28 18 L28 52 L6 52 Z"
    right = "M36 12 L58 12 L58 46 L36 46 Z"
    return [_face(left, mk.GEO), _face(right, mk.GEO),
            '<path d="M32 4 V60" stroke="%s" stroke-width="3" stroke-dasharray="5 3"/>' % mk.RED]


@icon("sm_base_flange", "Brida base")
def _():
    # placa fina en perspectiva (blanca) con el canto en gris y el croquis azul encima
    top = "M6 34 L38 18 L58 28 L26 44 Z"
    front = "M6 34 L26 44 V50 L6 40 Z"
    side = "M26 44 L58 28 V34 L26 50 Z"
    return [_face(front, mk.PLANE), _face(side, mk.OLD), _face(top, mk.GEO),
            mk.new("M14 33 L38 21 L50 27 L26 39 Z")]


@icon("sm_edge_flange", "Brida de arista")
def _():
    # placa con una pared plegada hacia arriba en el borde de atrás, y la arista azul
    floor = "M6 40 L34 26 L58 38 L30 52 Z"
    floor_edge = "M6 40 L30 52 V57 L6 45 Z"
    wall = "M34 26 L58 38 V14 L34 2 Z"
    return [_face(floor_edge, mk.OLD), _face(floor, mk.GEO), _face(wall, mk.PLANE),
            mk.thin("M34 26 L58 38", mk.NEW, 4.0)]


@icon("sm_hem", "Dobladillo")
def _():
    # chapa vista de costado con el borde doblado sobre sí misma, y el pliegue azul
    lower = "M6 46 H50 V40 H6 Z"
    upper = "M22 34 H50 V28 H22 Z"
    return [_face(lower, mk.GEO), _face(upper, mk.GEO),
            '<path d="M50 40 A6 6 0 0 0 50 28" fill="none" stroke="%s" stroke-width="7"/>' % mk.OUTLINE,
            '<path d="M50 40 A6 6 0 0 0 50 28" fill="none" stroke="%s" stroke-width="3.6"/>' % mk.NEW]


@icon("sm_convert", "Convertir en chapa")
def _():
    # bloque gris (pieza importada) -> flecha -> perfil en L blanco de chapa
    block = "M4 22 H22 V44 H4 Z"
    l_shape = "M38 12 H44 V40 H60 V46 H38 Z"
    return [_face(block, mk.OLD), mk.arrow(24, 33, 36, 33, mk.NEW, 6.0, 3.0), _face(l_shape, mk.GEO)]


@icon("sm_flatten", "Aplanar")
def _():
    # pieza en U abierta en plano: placa blanca con dos líneas de plegado rojas de trazos
    plate = "M4 22 H60 V42 H4 Z"
    dash = '<path d="%s" stroke="%s" stroke-width="2.6" stroke-dasharray="4 3" fill="none"/>'
    return [_face(plate, mk.GEO), dash % ("M20 22 V42", mk.RED), dash % ("M44 22 V42", mk.RED),
            mk.arrow(32, 58, 32, 46, mk.NEW, 6.0, 2.8)]


@icon("sm_unfold", "Desdoblar")
def _():
    # perfil en L gris (plegado) que se abre en una placa blanca con la flecha
    l_shape = "M6 8 H12 V34 H26 V40 H6 Z"
    plate = "M32 34 H60 V40 H32 Z"
    return [_face(l_shape, mk.OLD), _face(plate, mk.GEO), mk.arrow(18, 22, 40, 26, mk.NEW, 6.0, 3.0)]


@icon("sm_fold", "Doblar")
def _():
    # placa blanca con un corte azul que vuelve a plegarse en L (flecha)
    plate = "M4 40 H32 V46 H4 Z"
    l_shape = "M40 10 H46 V40 H60 V46 H40 Z"
    return [_face(plate, mk.GEO), mk.new("M12 40 H22"), _face(l_shape, mk.GEO),
            mk.arrow(26, 34, 38, 22, mk.NEW, 6.0, 3.0)]


@icon("sm_dxf", "Exportar DXF")
def _():
    # hoja con el contorno azul y la línea de plegado roja, "DXF" abajo
    sheet = "M12 4 H42 L52 14 V60 H12 Z"
    dash = '<path d="M32 12 V36" stroke="%s" stroke-width="2.4" stroke-dasharray="4 3" fill="none"/>' % mk.RED
    return [_face(sheet, mk.GEO), mk.new("M20 12 H44 V36 H20 Z"), dash,
            mk.label(32, 54, "DXF", mk.NEW, 13)]


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
