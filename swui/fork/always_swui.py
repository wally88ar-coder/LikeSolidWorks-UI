# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Usar siempre LikeSolidWorks UI (pedido del usuario: "bajo cualquier concepto").

  - FreeCAD arranca en LikeSolidWorks UI (preferencia General/AutoloadModule;
    el valor anterior se guarda para devolverlo si se apaga la opción).
  - Si algo cambia a otro banco (página de Inicio "Cuerpo paramétrico" /
    "Ensamblaje", que lo hacen desde C++ sin pasar por Python; un comando; una
    macro), se vuelve enseguida a LikeSolidWorks UI. Señal
    MainWindow.workbenchActivated(nombre).
  - El selector de bancos (barra "Workbench") queda oculto.

Escape: menú "LikeSolidWorks UI" -> "Usar siempre LikeSolidWorks UI" (tilde).
Desmarcado, FreeCAD vuelve a comportarse como siempre. Parámetro
BaseApp/Preferences/Mod/SWUI/AlwaysSWUI.

Los otros bancos NO se desinstalan: la cinta usa sus comandos por debajo
(Part Design, Sketcher, TechDraw, Assembly, SheetMetal...).
"""

import time

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI"
KEY = "AlwaysSWUI"
BACKUP_KEY = "AutoloadBackup"  # banco de arranque anterior
GENERAL = "User parameter:BaseApp/Preferences/General"
AUTOLOAD = "AutoloadModule"
WB_NAME = "LikeSolidWorksUIWorkbench"
SELECTOR_TOOLBAR = "Workbench"
COMMAND = "SWUI_AlwaysSWUI"
MAX_RETURNS = 5  # vueltas seguidas en RETURN_WINDOW s; más = algo pelea, se deja de insistir
RETURN_WINDOW = 3.0
PLANES_MS = 300  # el cuerpo de la página de Inicio puede aparecer recién después de volver

_connected = False
_returns = []


def enabled():
    try:
        return FreeCAD.ParamGet(PARAMS).GetBool(KEY, True)
    except Exception:
        return True


def should_return(name):
    """¿Hay que volver a LikeSolidWorks UI después de que se activó el banco 'name'?"""
    return enabled() and bool(name) and name != WB_NAME


def install():
    """Comando del menú, banco de arranque y vigilancia de cambios de banco."""
    global _connected
    try:
        FreeCADGui.addCommand(COMMAND, _AlwaysCommand())
    except Exception:
        pass  # ya registrado
    if enabled():
        set_autoload(True)
    if _connected:
        return
    try:
        FreeCADGui.getMainWindow().workbenchActivated.connect(_on_workbench)
        _connected = True
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Usar siempre LikeSolidWorks UI: señal no disponible.\n")
    _hook_layout()


def set_autoload(on):
    """Arranque en LikeSolidWorks UI (on) o devolver el banco de arranque anterior."""
    general, own = FreeCAD.ParamGet(GENERAL), FreeCAD.ParamGet(PARAMS)
    current = general.GetString(AUTOLOAD, "")
    if on:
        if current != WB_NAME:
            own.SetString(BACKUP_KEY, current)
            general.SetString(AUTOLOAD, WB_NAME)
    else:
        backup = own.GetString(BACKUP_KEY, "")
        if current == WB_NAME:
            if backup:
                general.SetString(AUTOLOAD, backup)
            else:
                general.RemString(AUTOLOAD)  # no había uno propio: el de fábrica de FreeCAD
        own.RemString(BACKUP_KEY)


def _on_workbench(name):
    if not should_return(name):
        return
    now = time.monotonic()
    _returns[:] = [t for t in _returns if now - t < RETURN_WINDOW] + [now]
    if len(_returns) > MAX_RETURNS:
        FreeCAD.Console.PrintWarning(
            "[SWUI fork] Otro banco insiste en activarse (%s); no se vuelve a LikeSolidWorks UI.\n" % name)
        return
    QtCore.QTimer.singleShot(0, _go_back)


def _go_back():
    try:
        if should_return(FreeCADGui.activeWorkbench().name()):
            FreeCADGui.activateWorkbench(WB_NAME)
            # La página de Inicio crea el cuerpo en Part Design: sus planos quedan "Plano XY"
            QtCore.QTimer.singleShot(PLANES_MS, _sw_plane_names)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] No se pudo volver a LikeSolidWorks UI.\n")


def _sw_plane_names():
    """Planos de origen con nombre de FreeCAD -> Planta, Alzado, Vista lateral."""
    try:
        from swui import pick_plane

        doc = FreeCAD.ActiveDocument
        if doc is not None:
            pick_plane.rename_default_planes(list(doc.Objects))
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] No se pudieron renombrar los planos.\n")


# --- Selector de bancos ----------------------------------------------


def _hook_layout():
    """Después de cada layout.enter(): ocultar el selector (layout.leave() lo devuelve)."""
    from swui import layout

    if getattr(layout.enter, "_swui_always", False):
        return
    original = layout.enter

    def enter(_original=original):
        result = _original()
        show_selector(not enabled())
        return result

    enter._swui_always = True
    layout.enter = enter


def show_selector(visible):
    try:
        mw = FreeCADGui.getMainWindow()
        for bar in mw.findChildren(QtWidgets.QToolBar):
            if bar.objectName() == SELECTOR_TOOLBAR:
                bar.show() if visible else bar.hide()
    except Exception:
        pass


class _AlwaysCommand:
    """Menú LikeSolidWorks UI -> Usar siempre LikeSolidWorks UI (con tilde)."""

    def GetResources(self):
        return {
            "MenuText": "Usar siempre LikeSolidWorks UI",
            "ToolTip": "Arrancar siempre en LikeSolidWorks UI, volver a él si algo cambia de banco "
                       "y ocultar el selector de bancos. Desmarcar para usar los bancos de FreeCAD.",
            "Checkable": enabled(),
        }

    def IsActive(self):
        return True

    def Activated(self, checked=None):
        on = bool(checked) if checked is not None else not enabled()
        FreeCAD.ParamGet(PARAMS).SetBool(KEY, on)
        set_autoload(on)
        try:
            from swui import layout

            if layout.is_active():
                show_selector(not on)
        except Exception:
            pass
