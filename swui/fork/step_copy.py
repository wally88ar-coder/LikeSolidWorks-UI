# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
"Guardar también STEP": al guardar una pieza o ensamblaje, deja al lado un
.step con el mismo nombre (pieza.FCStd -> pieza.step).

Es el resguardo para versiones futuras de FreeCAD: el STEP no tiene historial,
pero la geometría queda siempre, abra o no el .FCStd. Se prende y apaga en el
menú "LikeSolidWorks UI" (apagado de fábrica; parámetro
BaseApp/Preferences/Mod/SWUI/AlsoSaveStep).

Se exportan los objetos de primer nivel que tienen forma (cuerpos, piezas,
ensamblajes, sólidos importados), sin croquis, planos ni hojas de dibujo, con
ImportGui (conserva colores). Si la pieza se guardó retrocedida y se elige
"Avanzar hasta el final y guardar", el STEP sale de esa segunda vez.
"""

import os
import traceback

import FreeCAD
import FreeCADGui

PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI"
KEY = "AlsoSaveStep"
COMMAND = "SWUI_AlsoSaveStep"
SHAPED = ("PartDesign::Body", "App::Part", "Assembly::AssemblyObject", "App::Link")
NOT_SHAPES = ("Sketcher::SketchObject", "TechDraw::DrawPage", "Spreadsheet::Sheet", "App::VarSet")

_observer = None


def enabled():
    try:
        return FreeCAD.ParamGet(PARAMS).GetBool(KEY, False)
    except Exception:
        return False


def set_enabled(on):
    FreeCAD.ParamGet(PARAMS).SetBool(KEY, bool(on))


def step_path(fcstd):
    """pieza.FCStd -> pieza.step (misma carpeta)."""
    return os.path.splitext(fcstd)[0] + ".step"


def exportable(objs):
    """Objetos de primer nivel con forma, sin croquis ni hojas."""
    out = []
    for obj in objs:
        kind = getattr(obj, "TypeId", "")
        if kind in NOT_SHAPES:
            continue
        if kind in SHAPED or (hasattr(obj, "isDerivedFrom") and obj.isDerivedFrom("Part::Feature")
                              and not obj.isDerivedFrom("Part::Part2DObject")):
            out.append(obj)
    return out


def export(doc):
    """Escribir el .step de doc. Devuelve la ruta o None."""
    filename = getattr(doc, "FileName", "")
    objs = exportable(doc.RootObjects)
    if not filename or not objs:
        return None
    path = step_path(filename)
    try:
        import ImportGui

        ImportGui.export(objs, path)
    except Exception:
        import Import

        Import.export(objs, path)
    FreeCAD.Console.PrintLog("[SWUI fork] STEP guardado: %s\n" % path)
    return path


def after_save(name):
    """Llamado al terminar de guardar (desde feature_tree, después del aviso de retroceso)."""
    if not enabled():
        return
    try:
        doc = FreeCAD.getDocument(name)
        mw = FreeCADGui.getMainWindow()
        mw.statusBar().showMessage("Guardando también STEP...")
        path = export(doc)
        mw.statusBar().showMessage("STEP guardado: %s" % path if path else "", 5000)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] No se pudo guardar el STEP:\n%s\n" % traceback.format_exc())


class _AlsoSaveStep:
    """Menú LikeSolidWorks UI -> Guardar también STEP (con tilde)."""

    def GetResources(self):
        return {"MenuText": "Guardar también STEP",
                "ToolTip": "Al guardar, deja al lado un .step con el mismo nombre (resguardo sin historial)",
                "Checkable": enabled()}

    def IsActive(self):
        return True

    def Activated(self, checked=None):
        set_enabled(bool(checked) if checked is not None else not enabled())


def install():
    try:
        FreeCADGui.addCommand(COMMAND, _AlsoSaveStep())
    except Exception:
        pass  # ya registrado
