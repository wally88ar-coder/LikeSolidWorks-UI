# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Panel izquierdo como en SOLIDWORKS: FeatureManager y PropertyManager.

El original (swui/layout.py, _dock_right) acomoda Tareas arriba y la Vista
de informe abajo, las dos a la derecha, con el árbol transparente sobre la
vista 3D. En este fork:
  - Árbol (Modelo) y Tareas son PESTAÑAS del mismo panel a la izquierda, sobre
    fondo gris claro (look_sw.py quita la superposición). Al abrir una
    operación (extruir, redondeo, croquis...) se pasa sola a Tareas; al
    cerrarla vuelve al árbol. La vista 3D no se corre.
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

TASK_WIDTH = 360  # ancho inicial: lo minimo del panel de croquis de FreeCAD (asi la vista no se corre)
REPORT_HEIGHT = 110
POLL_MS = 250  # cada cuánto se mira si hay una operación abierta
MODEL_NAME = "Model"  # panel del árbol en FreeCAD 1.1
SIZE_DELAY_MS = 400

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
_last_task = None  # último estado visto (para cambiar de pestaña solo al abrir/cerrar)


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
            _restore_titles()
            return _original()

        leave._swui_fork = True
        layout.leave = leave


def dock_left(mw):
    """Árbol y Tareas en pestañas a la izquierda, informe abajo (reemplaza a layout._dock_right)."""
    global _sized, _last_task
    from swui import layout

    docks = {d.objectName(): d for d in mw.findChildren(QtWidgets.QDockWidget)}
    tasks, report = docks.get(layout.TASK_NAME), docks.get(layout.REPORT_NAME)
    model = docks.get(MODEL_NAME)
    if tasks is None:
        FreeCAD.Console.PrintWarning("[SWUI fork] No se encontró el panel de tareas.\n")
        return
    left = QtCore.Qt.DockWidgetArea.LeftDockWidgetArea
    for dock in (model, tasks):
        if dock is not None:
            layout._unfloat(dock)
            mw.addDockWidget(left, dock)
            dock.show()
    if model is not None:
        try:
            mw.setTabPosition(left, QtWidgets.QTabWidget.TabPosition.North)  # pestañas arriba, como SW
        except Exception:
            pass
        mw.tabifyDockWidget(model, tasks)
        _hide_titles((model, tasks))
        QtCore.QTimer.singleShot(0, lambda: _hide_empty_tabbars(mw))
    if report is not None:
        layout._unfloat(report)
        mw.addDockWidget(QtCore.Qt.DockWidgetArea.BottomDockWidgetArea, report)
        report.hide()
    _mute_report()
    if not _sized:
        _sized = True
        # con demora: recién armado, Qt todavía no respeta el ancho pedido
        QtCore.QTimer.singleShot(SIZE_DELAY_MS, lambda: _resize(mw, model or tasks))
    _last_task = None  # elegir la pestaña según el estado actual
    _update(tasks, model)
    _start_timer(mw)


def _resize(mw, dock):
    try:
        mw.resizeDocks([dock], [TASK_WIDTH], QtCore.Qt.Orientation.Horizontal)
    except Exception:
        pass


_titles = []  # (panel, barra de título anterior)


def _hide_titles(docks):
    """Sin barra de título "Modelo"/"Tareas" debajo de las pestañas (como SW).
    FreeCAD la vuelve a poner al abrir una operación: se repite en cada _tick."""
    for dock in docks:
        if dock is None:
            continue
        try:
            current = dock.titleBarWidget()
            if current is not None and current.property("swui_blank"):
                continue
            if not any(d is dock for d, _old in _titles):
                _titles.append((dock, current))
            blank = QtWidgets.QWidget(dock)
            blank.setProperty("swui_blank", True)
            dock.setTitleBarWidget(blank)
        except Exception:
            pass


def _restore_titles():
    while _titles:
        dock, old = _titles.pop()
        try:
            dock.setTitleBarWidget(old)
        except Exception:
            pass


def _hide_empty_tabbars(mw):
    """Qt deja barras de pestañas vacías encima de la buena ("Modelo | Tareas"): ocultarlas."""
    try:
        for bar in mw.findChildren(QtWidgets.QTabBar):
            if bar.parent() is mw and bar.count() == 0:
                bar.hide()
    except Exception:
        pass


def has_task():
    """¿Hay una operación (diálogo de tareas) abierta?"""
    try:
        return bool(FreeCADGui.Control.activeDialog())
    except Exception:
        return False


def _update(tasks, model=None):
    """Al abrir una operación, pestaña Tareas; al cerrarla, el árbol (solo en el cambio)."""
    global _last_task
    want = has_task()
    if want == _last_task:
        return
    _last_task = want
    if model is None:  # sin árbol en pestañas: mostrar/ocultar como antes
        tasks.show() if want else tasks.hide()
        return
    (tasks if want else model).raise_()


def _start_timer(mw):
    global _timer
    if _timer is None:
        _timer = QtCore.QTimer(mw)
        _timer.setInterval(POLL_MS)
        _timer.timeout.connect(_tick)
    _timer.start()


def _tick():
    """Pestaña según haya operación; fuera del banco SW, parar."""
    from swui import layout

    if not layout.is_active():
        _timer.stop()
        _unmute_report()
        return
    try:
        mw = FreeCADGui.getMainWindow()
        docks = {d.objectName(): d for d in mw.findChildren(QtWidgets.QDockWidget)}
        if docks.get(layout.TASK_NAME) is not None:
            _update(docks[layout.TASK_NAME], docks.get(MODEL_NAME))
            if docks.get(MODEL_NAME) is not None:
                _hide_titles((docks[MODEL_NAME], docks[layout.TASK_NAME]))
    except Exception:
        pass
