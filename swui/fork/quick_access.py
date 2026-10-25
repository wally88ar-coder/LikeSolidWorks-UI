# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Íconos de acceso rápido en la barra de menú, como en la barra de título de SW 2018:
Nuevo, Abrir, Guardar, Deshacer y Reconstruir (en FreeCAD "Recalcular", F5).

Reemplazan a las barras Archivo y Editar que look_sw.py oculta. Cada botón usa
la acción del propio comando de FreeCAD (Std_New, Std_Open, Std_Save,
Std_Undo, Std_Refresh): ícono, atajo, tooltip y activo/inactivo los maneja
FreeCAD. Van en el área derecha que FreeCAD 1.1 reserva en la barra de menú
("MenuBarRightArea"); se ponen al entrar a LikeSolidWorks UI y se sacan al salir.
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

COMMANDS = ("Std_New", "Std_Open", "Std_Save", "Std_Undo", "Std_Refresh")
ICON_SIZE = 16
OBJECT_NAME = "SWUI_QuickAccess"

_box = None


def install():
    """Enganchar a layout.enter() / layout.leave() del original."""
    from swui import layout

    if getattr(layout.enter, "_swui_quick", False):
        return
    original_enter, original_leave = layout.enter, layout.leave

    def enter(_original=original_enter):
        result = _original()
        show()
        return result

    def leave(_original=original_leave):
        hide()
        return _original()

    enter._swui_quick = leave._swui_quick = True
    layout.enter, layout.leave = enter, leave


def actions():
    """[(comando, QAction)] de los comandos que existen en esta versión de FreeCAD."""
    out = []
    for name in COMMANDS:
        try:
            acts = FreeCADGui.Command.get(name).getAction()
            if acts:
                out.append((name, acts[0]))
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Acceso rápido: falta %s\n" % name)
    return out


def show():
    global _box
    if _box is not None:
        return
    try:
        bar = FreeCADGui.getMainWindow().menuBar()
        area = bar.cornerWidget(QtCore.Qt.Corner.TopRightCorner)
        if area is None:
            area = QtWidgets.QWidget(bar)
            area.setLayout(QtWidgets.QHBoxLayout())
            bar.setCornerWidget(area, QtCore.Qt.Corner.TopRightCorner)
        box = QtWidgets.QWidget(area)
        box.setObjectName(OBJECT_NAME)
        row = QtWidgets.QHBoxLayout(box)
        row.setContentsMargins(0, 0, 8, 0)
        row.setSpacing(2)
        for name, action in actions():
            button = QtWidgets.QToolButton(box)
            button.setObjectName("SWUI_Quick_" + name)
            button.setDefaultAction(action)
            button.setAutoRaise(True)
            button.setIconSize(QtCore.QSize(ICON_SIZE, ICON_SIZE))
            row.addWidget(button)
        lay = area.layout()
        if lay is None:
            lay = QtWidgets.QHBoxLayout(area)
        lay.insertWidget(0, box)
        box.show()
        _box = box
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Acceso rápido no disponible.\n")


def hide():
    global _box
    if _box is None:
        return
    try:
        _box.hide()
        _box.setParent(None)
        _box.deleteLater()
    except Exception:
        pass
    _box = None
