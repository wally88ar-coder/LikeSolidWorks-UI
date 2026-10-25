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
  - Vista de informe ABAJO, bajita, para no quitarle ancho a la vista 3D.

Se engancha reemplazando layout._dock_right: layout.enter() y sus
reintentos (REDOCK_MS) llaman a esta función en lugar de la original.
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

TASK_WIDTH = 320  # ancho inicial del panel, parecido al PropertyManager de SW
REPORT_HEIGHT = 110
POLL_MS = 250  # cada cuánto se mira si hay una operación abierta

_timer = None
_sized = False


def install():
    from swui import layout

    layout._dock_right = dock_left


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
        report.show()
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
        return
    try:
        mw = FreeCADGui.getMainWindow()
        tasks = next((d for d in mw.findChildren(QtWidgets.QDockWidget) if d.objectName() == layout.TASK_NAME), None)
        if tasks is not None:
            _update(tasks)
    except Exception:
        pass
