# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 Dominik Ladewig
"""
sketch_edit.py - Skizzen in der Workbench "LikeSolidWorks UI" bearbeiten,
statt automatisch in den FreeCAD-Sketcher zu springen.

Hintergrund (FreeCAD 1.1.4, ViewProviderSketch.cpp, setEdit):
Jede Skizze hat die Eigenschaft ViewObject.EditingWorkbench, Standard
"SketcherWorkbench". Beim Oeffnen einer Skizze ruft FreeCAD

    tv = Show.TempoVis(...)
    tv.activateWorkbench(ActiveSketch.ViewObject.EditingWorkbench)

auf; beim Schliessen stellt TempoVis die vorherige Workbench wieder her.
Nur der Sketcher nutzt diesen Mechanismus.

Loesung: Wir haengen uns in TempoVis.activateWorkbench ein. Ist gerade
"LikeSolidWorks UI" aktiv, wird der Wechsel uebersprungen - TempoVis merkt
sich dann auch nichts und stellt beim Schliessen nichts zurueck. In
jeder anderen Workbench (z.B. Part Design) laeuft alles wie gewohnt.

Warum nicht EditingWorkbench der Skizzen aendern: Das ist eine
gespeicherte Eigenschaft - sie wuerde Dominiks Dateien veraendern und
auch das Verhalten in Part Design.

Feature-Dialoge (Linear austragen, Verrundung, ...): Part Design wechselt
beim Oeffnen JEDES Feature-Dialogs selbst zur Workbench Part Design
(FreeCAD 1.1.4: Gui::Command::assureWorkbench -> doCommand
"Gui.activateWorkbench('PartDesignWorkbench')") und beim Schliessen
zurueck - mitten in LikeSolidWorks UI verschwand dann das Ribbon und der
Dialog kam ohne SW-Begriffe (unter Windows gemeldet, 25.10.). Diese
Aufrufe kommen als Python-Text aus FreeCADs C++ (Dateiname "<string>");
nur sie werden in LikeSolidWorks UI uebersprungen. Die Workbench-Auswahl
in der Leiste und Makros wechseln weiter wie gewohnt.
"""

import sys

import FreeCAD
import FreeCADGui
from swui.i18n import N_, tr  # noqa: F401

WB_NAME = "LikeSolidWorksUIWorkbench"


def install():
    """Einhaken. Mehrfacher Aufruf ist unschaedlich."""
    _hook_feature_dialogs()  # unabhaengig vom Show-Modul
    try:
        from Show import mTempoVis
    except Exception as exc:
        FreeCAD.Console.PrintWarning(
            tr("[SWUI] Skizzen-Workbenchwechsel nicht abfangbar (Show-Modul fehlt): %s\n") % exc
        )
        return False

    cls = mTempoVis.TempoVis
    current = cls.activateWorkbench
    if getattr(current, "_swui_original", None) is not None:
        return True  # schon eingehakt

    def activateWorkbench(self, wb_name, _original=current):
        if _swui_active():
            FreeCAD.Console.PrintLog(
                "[SWUI] Skizze bleibt in LikeSolidWorks UI (statt %s).\n" % wb_name
            )
            return None
        return _original(self, wb_name)

    activateWorkbench._swui_original = current
    activateWorkbench.__doc__ = current.__doc__
    cls.activateWorkbench = activateWorkbench
    FreeCAD.Console.PrintLog("[SWUI] Skizzen bleiben in LikeSolidWorks UI.\n")
    return True


# Workbenches, zu denen FreeCAD beim Oeffnen eines Feature-Dialogs selbst wechselt
FEATURE_WORKBENCHES = ("PartDesignWorkbench",)


def _hook_feature_dialogs():
    """FreeCADGui.activateWorkbench einhaken (siehe Modulkopf: Feature-Dialoge)."""
    current = getattr(FreeCADGui, "activateWorkbench", None)
    if current is None or getattr(current, "_swui_original", None) is not None:
        return

    def activateWorkbench(name, *args, _original=current):
        if name in FEATURE_WORKBENCHES and _swui_active() and _from_freecad():
            FreeCAD.Console.PrintLog("[SWUI] Feature-Dialog bleibt in LikeSolidWorks UI (statt %s).\n" % name)
            return True
        return _original(name, *args)

    activateWorkbench._swui_original = current
    FreeCADGui.activateWorkbench = activateWorkbench


def _from_freecad(depth=2):
    """Kommt der Aufruf als Python-Text aus FreeCADs C++ (doCommand)? depth 2 = Aufrufer des Hakens."""
    try:
        return sys._getframe(depth).f_code.co_filename == "<string>"
    except ValueError:
        return False


def uninstall():
    """Originalverhalten wiederherstellen (fuer Tests und Notfaelle)."""
    try:
        from Show import mTempoVis
    except Exception:
        return
    cls = mTempoVis.TempoVis
    original = getattr(cls.activateWorkbench, "_swui_original", None)
    if original is not None:
        cls.activateWorkbench = original
    original = getattr(getattr(FreeCADGui, "activateWorkbench", None), "_swui_original", None)
    if original is not None:
        FreeCADGui.activateWorkbench = original


def _swui_active():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False
