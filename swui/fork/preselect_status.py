# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Barra de estado como SW al pasar el mouse sobre la pieza: "Longitud: 100mm" en
una arista recta, el radio o el diámetro en un arco o círculo, el área en una
cara. FreeCAD 1.1.4 muestra ahí "Preselected: doc.Body.Pad.Edge4 (x, y, z)",
en inglés: dentro de LikeSolidWorks UI se cambia por lo nuestro (el mensaje de
FreeCAD vuelve a escribirse con cada movimiento del mouse; se reemplaza cada vez).
"""

import traceback

import FreeCAD
import FreeCADGui

PREFIXES = ("Preselected:", "Preseleccionado:")
WB_NAME = "LikeSolidWorksUIWorkbench"

_state = {"text": "", "observer": None, "busy": False}


def describe(shape, decimals=2):
    """Texto de SW para una arista, cara o vértice (o "" si no hay nada que decir)."""
    from swui.fork.measure_sw import fmt

    def f(value, unit="mm"):
        return fmt(value, decimals, unit)

    kind = getattr(shape, "ShapeType", "")
    if kind == "Edge":
        curve = type(getattr(shape, "Curve", None)).__name__
        if curve == "Circle":
            if shape.isClosed():
                return "Diámetro: %s" % f(2 * shape.Curve.Radius)
            return "Radio: %s   Longitud de arco: %s" % (f(shape.Curve.Radius), f(shape.Length))
        return "Longitud: %s" % f(shape.Length)
    if kind == "Face":
        surface = type(getattr(shape, "Surface", None)).__name__
        area = "Área: %s" % f(shape.Area, "mm²")
        if surface == "Cylinder":
            return "Radio: %s   %s" % (f(shape.Surface.Radius), area)
        return area
    if kind == "Vertex":
        return "X: %s   Y: %s   Z: %s" % (f(shape.X), f(shape.Y), f(shape.Z))
    return ""


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


def _status_bar():
    try:
        return FreeCADGui.getMainWindow().statusBar()
    except Exception:
        return None


def _show():
    bar = _status_bar()
    if bar is not None and _state["text"]:
        _state["busy"] = True
        try:
            bar.showMessage(_state["text"])
        finally:
            _state["busy"] = False


def on_message(message):
    """La barra cambió: si es el "Preselected:" de FreeCAD, poner lo nuestro."""
    if _state["busy"] or not _state["text"] or not _in_workbench():
        return
    if message.startswith(PREFIXES):
        _show()


class _Observer:
    def setPreselection(self, doc, obj, sub):
        _state["text"] = ""
        if not sub or not _in_workbench():
            return
        try:
            owner = FreeCAD.getDocument(doc).getObject(obj)
            shape = owner.getSubObject(sub) if owner is not None else None
            if shape is not None and not shape.isNull():
                _state["text"] = describe(shape)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Barra de estado:\n%s\n" % traceback.format_exc())
        _show()

    def removePreselection(self, _doc, _obj, _sub):
        _state["text"] = ""


def install():
    if _state["observer"] is not None:
        return
    _state["observer"] = _Observer()
    FreeCADGui.Selection.addObserver(_state["observer"])
    bar = _status_bar()
    if bar is not None:
        bar.messageChanged.connect(on_message)
