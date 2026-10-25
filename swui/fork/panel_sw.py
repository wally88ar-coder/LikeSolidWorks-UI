# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Panel de tareas a la izquierda, como el PropertyManager de SOLIDWORKS.

El original (swui/layout.py, _dock_right) acomoda Tareas arriba y la Vista
de informe abajo, las dos a la derecha. En este fork:
  - Tareas a la IZQUIERDA y visible solo mientras hay una operación abierta
    (extruir, redondeo, croquis...). Sin operación, a la izquierda queda el
    árbol (superposición transparente del original), como en SW.
  - Vista de informe ABAJO y OCULTA (pedido del usuario: molesta). Se abre a
    mano con Ver -> Paneles -> Vista de informe. Mientras se está en
    LikeSolidWorks UI tampoco se abre sola ante avisos o errores (preferencias
    de FreeCAD OutputWindow/checkShowReportViewOn*, se devuelven al salir).

Se engancha reemplazando layout._dock_right: layout.enter() y sus
reintentos (REDOCK_MS) llaman a esta función en lugar de la original.
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

TASK_WIDTH = 320  # ancho inicial del panel, parecido al PropertyManager de SW
REPORT_HEIGHT = 110
POLL_MS = 250  # cada cuánto se mira si hay una operación abierta

OUTPUT_PARAMS = "User parameter:BaseApp/Preferences/OutputWindow"
REPORT_POPUP_KEYS = (
    "checkShowReportViewOnWarning",
    "checkShowReportViewOnError",
    "checkShowReportViewOnCritical",
    "checkShowReportViewOnNormalMessage",
    "checkShowReportViewOnLogMessage",
)

_timer = None
_sized = False
_report_saved = None  # {clave: valor anterior o None si no existía}


def _mute_report():
    """Que FreeCAD no abra la Vista de informe sola (se devuelve con _unmute_report)."""
    global _report_saved
    if _report_saved is not None:
        return
    try:
        grp = FreeCAD.ParamGet(OUTPUT_PARAMS)
        names = list(grp.GetBools()) if hasattr(grp, "GetBools") else []  # FreeCAD: solo los nombres
        _report_saved = {k: (grp.GetBool(k) if k in names else None) for k in REPORT_POPUP_KEYS}
        for k in REPORT_POPUP_KEYS:
            grp.SetBool(k, False)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Vista de informe: preferencias no cambiadas.\n")


def _unmute_report():
    global _report_saved
    if _report_saved is None:
        return
    grp = FreeCAD.ParamGet(OUTPUT_PARAMS)
    for k, old in _report_saved.items():
        if old is None:
            grp.RemBool(k)
        else:
            grp.SetBool(k, old)
    _report_saved = None


def install():
    from swui import layout

    layout._dock_right = dock_left
    if not getattr(layout.leave, "_swui_fork", False):
        original = layout.leave

        def leave(_original=original):
            _unmute_report()  # antes de que FreeCAD guarde sus preferencias al cerrar
            return _original()

        leave._swui_fork = True
        layout.leave = leave


def dock_left(mw):
    """Tareas a la izquierda, Vista de informe abajo (reemplaza a layout._dock_right)."""
    global _sized
    from swui import layout

    docks = {d.objectName(): d for d in mw.findChildren(QtWidgets.QDockWidget)}
    tasks, report = docks.get(layout.TASK_NAME), docks.get(layout.REPORT_NAME)
    if tasks is None:
        FreeCAD.Console.PrintWarning("[SWUI fork] No se encontró el panel de tareas.\n")
        return
    layout._unfloat(tasks)
    mw.addDockWidget(QtCore.Qt.DockWidgetArea.LeftDockWidgetArea, tasks)
    if report is not None:
        layout._unfloat(report)
        mw.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, report)
        report.hide()
    _mute_report()
    if not _sized:
        _sized = True
        try:
            mw.resizeDocks([tasks], [TASK_WIDTH], QtCore.Qt.Orientation.Horizontal)
            if report is not None:
                mw.resizeDocks([report], [REPORT_HEIGHT], QtCore.Qt.Orientation.Vertical)
        except Exception:
            pass
    _update(tasks)
    _start_timer(mw)


def has_task():
    """¿Hay una operación (diálogo de tareas) abierta?"""
    try:
        return bool(FreeCADGui.Control.activeDialog())
    except Exception:
        return False


def _update(tasks):
    want = has_task()
    if tasks.isVisible() != want:
        if want:
            tasks.show()
            tasks.raise_()
        else:
            tasks.hide()


def _start_timer(mw):
    global _timer
    if _timer is None:
        _timer = QtCore.QTimer(mw)
        _timer.setInterval(POLL_MS)
        _timer.timeout.connect(_tick)
    _timer.start()


def _tick():
    """Mostrar/ocultar Tareas según haya operación; fuera del banco SW, parar."""
    from swui import layout

    if not layout.is_active():
        _timer.stop()
        _unmute_report()
        return
    try:
        mw = FreeCADGui.getMainWindow()
        tasks = next((d for d in mw.findChildren(QtWidgets.QDockWidget) if d.objectName() == layout.TASK_NAME), None)
        if tasks is not None:
            _update(tasks)
    except Exception:
        pass
