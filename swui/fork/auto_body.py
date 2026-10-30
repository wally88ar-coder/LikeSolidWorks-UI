# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Sin "Cuerpo activo" a la vista, como SW. En Part Design cada sólido es un Cuerpo y las
operaciones van al Cuerpo activo: con dos sólidos y ninguno activo (por ejemplo al abrir
el archivo), Extruir pedía en inglés "Cuerpo Activo Requerido"; con un croquis de otro
sólido daba error ("debe pertenecer al cuerpo activo"). SW no tiene ese concepto: se elige
el croquis o la cara y listo.

Acá, al elegir algo que está dentro de un Cuerpo (en la vista o en el árbol, sin ningún
panel abierto), ese Cuerpo pasa a ser el activo. Es lo mismo que el doble clic de FreeCAD
sobre el Cuerpo, hecho solo; no guarda nada propio en el archivo.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore

WB_NAME = "LikeSolidWorksUIWorkbench"
BODY = "PartDesign::Body"

_state = {"observer": None}


def body_of(obj):
    """El Cuerpo que contiene a obj (o obj mismo si es un Cuerpo); None si no hay."""
    seen = 0
    while obj is not None and seen < 20:
        if obj.TypeId == BODY:
            return obj
        try:
            obj = obj.getParentGeoFeatureGroup()
        except Exception:
            return None
        seen += 1
    return None


def _busy(gdoc):
    try:
        if FreeCADGui.Control.activeDialog():
            return True
        return gdoc.getInEdit() is not None
    except Exception:
        return True


def _activate(doc_name, obj_name):
    try:
        if FreeCADGui.activeWorkbench().name() != WB_NAME:
            return
        doc = FreeCAD.getDocument(doc_name)
        gdoc = FreeCADGui.getDocument(doc_name)
        obj = doc.getObject(obj_name)
        body = body_of(obj)
        if body is None or _busy(gdoc):
            return
        view = gdoc.ActiveView
        if view is None or view.getActiveObject("pdbody") is body:
            return
        view.setActiveObject("pdbody", body)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Cuerpo activo:\n%s\n" % traceback.format_exc())


class _Observer:
    def addSelection(self, doc, obj, sub, pnt):
        # después de la selección (cambiar el Cuerpo activo adentro del aviso confunde a FreeCAD)
        QtCore.QTimer.singleShot(0, lambda: _activate(doc, obj))


def install():
    if _state["observer"] is None:
        _state["observer"] = _Observer()
        FreeCADGui.Selection.addObserver(_state["observer"])
