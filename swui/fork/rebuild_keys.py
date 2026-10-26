# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Teclas de SOLIDWORKS para reconstruir y medir.

- Ctrl+B: reconstruir (lo que cambió). Ctrl+Q: forzar la reconstrucción de
  todo. Si quedan errores se abre "¿Qué es incorrecto?". En FreeCAD, Ctrl+B
  es "Zoom de ventana" (Std_ViewBoxZoom): ese atajo se quita mientras se está
  en LikeSolidWorks UI y se devuelve al salir.
- Barra espaciadora: Medir (Std_Measure), como la tiene configurada el
  usuario en su SW. En FreeCAD la barra es "Alternar visibilidad"
  (Std_ToggleVisibility): ese atajo se quita mientras tanto (ocultar sigue en
  el clic derecho).

Las teclas son acciones propias en la ventana principal (como N y F en
view_keys.py) y existen solo dentro de LikeSolidWorks UI.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtGui, QtWidgets

REBUILD = "SWUI_Rebuild"
FORCE_REBUILD = "SWUI_ForceRebuild"
WHATS_WRONG = "SWUI_WhatsWrong"
MEASURE = "Std_Measure"

_actions = []
_hidden = []  # (QAction, atajos) de FreeCAD quitados mientras tanto


def keys():
    """(tecla, comando)."""
    return [("Ctrl+B", REBUILD), ("Ctrl+Q", FORCE_REBUILD), ("Space", MEASURE)]


def rebuild(force=False):
    """Reconstruir el documento activo; si quedan errores, abrir "¿Qué es incorrecto?"."""
    doc = FreeCAD.ActiveDocument
    if doc is None:
        return
    if force:
        for obj in doc.Objects:
            try:
                obj.touch()
            except Exception:
                pass
    doc.recompute()
    from swui.fork import tree_dialogs

    if tree_dialogs.problems(doc):
        tree_dialogs.show_whats_wrong(doc)


class _Rebuild:
    force = False
    menu = "Reconstruir"
    tip = "Reconstruye lo que cambió (Ctrl+B)"

    def GetResources(self):
        return {"MenuText": self.menu, "ToolTip": self.tip, "Pixmap": "view-refresh"}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        rebuild(self.force)


class _ForceRebuild(_Rebuild):
    force = True
    menu = "Forzar reconstrucción"
    tip = "Reconstruye todas las operaciones, hayan cambiado o no (Ctrl+Q)"


class _WhatsWrong:
    def GetResources(self):
        return {"MenuText": "¿Qué es incorrecto?",
                "ToolTip": "Lista las operaciones con error y explica qué les pasa"}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        from swui.fork import tree_dialogs

        tree_dialogs.show_whats_wrong()


def install():
    """Comandos y teclas mientras se está en LikeSolidWorks UI."""
    from swui import layout

    for name, command in ((REBUILD, _Rebuild()), (FORCE_REBUILD, _ForceRebuild()),
                          (WHATS_WRONG, _WhatsWrong())):
        try:
            FreeCADGui.addCommand(name, command)
        except Exception:
            pass  # ya registrado
    if getattr(layout.enter, "_swui_rebuild", False):
        return
    original_enter, original_leave = layout.enter, layout.leave

    def enter(_original=original_enter):
        result = _original()
        add_keys()
        return result

    def leave(_original=original_leave):
        remove_keys()
        return _original()

    enter._swui_rebuild = leave._swui_rebuild = True
    layout.enter, layout.leave = enter, leave


def _run(command):
    try:
        FreeCADGui.runCommand(command)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Tecla: %s\n" % traceback.format_exc())


def _action_class():
    return QtGui.QAction if hasattr(QtGui, "QAction") else QtWidgets.QAction  # Qt6 / Qt5


def _hide_clashes(mw, taken):
    """Quitar a las acciones de FreeCAD nuestras teclas (se devuelven al salir)."""
    for action in mw.findChildren(_action_class()):
        if action in _actions:
            continue
        shortcuts = list(action.shortcuts())
        keep = [s for s in shortcuts if s.toString() not in taken]
        if len(keep) != len(shortcuts):
            _hidden.append((action, shortcuts))
            action.setShortcuts(keep)


def add_keys():
    if _actions:
        return
    try:
        mw = FreeCADGui.getMainWindow()
        wanted = keys()
        _hide_clashes(mw, [key for key, _c in wanted])
        for key, command in wanted:
            action = _action_class()(mw)
            action.setObjectName("SWUI_Key_" + key.replace("+", "_"))
            action.setShortcut(QtGui.QKeySequence(key))
            action.triggered.connect(lambda *_a, c=command: _run(c))
            mw.addAction(action)
            _actions.append(action)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Teclas de reconstruir no disponibles:\n%s\n"
                                 % traceback.format_exc())


def remove_keys():
    try:
        mw = FreeCADGui.getMainWindow()
    except Exception:
        mw = None
    for action in _actions:
        try:
            if mw is not None:
                mw.removeAction(action)
            action.deleteLater()
        except Exception:
            pass
    del _actions[:]
    for action, shortcuts in _hidden:
        try:
            action.setShortcuts(shortcuts)
        except Exception:
            pass  # la acción ya no existe
    del _hidden[:]
