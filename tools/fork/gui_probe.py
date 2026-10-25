# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Plantilla de prueba en FreeCAD REAL (con interfaz), sin tocar la configuración del usuario.

Uso (ver docs/NOTAS_TECNICAS.md):
    copiar este archivo y user.cfg a una carpeta temporal, editar PASOS y OUT, y correr
    timeout 90 D:/Freecad/bin/freecad.exe -u <tmp>/user.cfg <tmp>/gui_probe.py

Cada paso es (demora_ms, función). El resultado queda en OUT/res.json (se vuelca después de cada
paso) y las capturas en OUT/*.png. Al final se cierran los documentos y FreeCAD.
"""

import json
import os
import traceback

import FreeCAD
import FreeCADGui
from PySide import QtCore

OUT = os.path.dirname(os.path.abspath(__file__))
res = {"log": []}


def dump():
    with open(os.path.join(OUT, "res.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, ensure_ascii=False, default=str)


def shot(name):
    FreeCADGui.getMainWindow().grab().save(os.path.join(OUT, name + ".png"))


def note(tag, **extra):
    res["log"].append(dict(tag=tag, banco=FreeCADGui.activeWorkbench().name(),
                           dialogo=bool(FreeCADGui.Control.activeDialog()), **extra))


# --- Pasos de ejemplo: completar ---------------------------------------


def entrar():
    FreeCADGui.activateWorkbench("LikeSolidWorksUIWorkbench")
    FreeCAD.newDocument("Prueba")
    mw = FreeCADGui.getMainWindow()
    mw.showNormal()
    mw.setGeometry(0, 23, 1366, 705)  # pantalla del usuario


def mirar():
    note("inicio")
    shot("inicio")


PASOS = [(4000, entrar), (2500, mirar)]


# --- Motor ---------------------------------------------------------------


def _run(i=0):
    if i >= len(PASOS):
        for name in list(FreeCAD.listDocuments()):
            FreeCAD.closeDocument(name)  # si no, FreeCAD pregunta "¿guardar?" y se cuelga
        QtCore.QTimer.singleShot(300, lambda: FreeCADGui.getMainWindow().close())
        return
    delay, fn = PASOS[i]

    def step():
        try:
            fn()
        except Exception:
            res.setdefault("err", []).append(traceback.format_exc())
        dump()
        _run(i + 1)

    QtCore.QTimer.singleShot(delay, step)


_run()
