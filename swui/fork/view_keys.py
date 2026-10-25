# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Teclas N (normal a) y F (ajustar a la ventana), como en SOLIDWORKS.

- F: encuadra y centra todo (Std_ViewFitAll de FreeCAD, que trae "V, F").
- N: "Normal a".
  * Cara plana o plano seleccionado: mira la cara de frente. Apretada otra
    vez, la mira desde el otro lado.
  * Editando un croquis sin selección (o con elementos del croquis): normal al
    croquis, con su eje Y hacia arriba.
  * Sin selección: gira a la vista estándar más cercana (frontal, superior,
    derecha... la que esté más de frente a la pantalla).
  En los tres casos el "arriba" queda derecho: el eje del modelo más parecido
  al arriba actual de la pantalla.

FreeCAD 1.1.4 trae "Alinear a la selección" (sin tecla y solo con selección).
Las teclas son acciones propias en la ventana principal (no cambian los
atajos de FreeCAD) y existen solo dentro de LikeSolidWorks UI. Cuando el
cursor está en un campo de texto, la letra va al campo, no a la vista.
Editando un croquis la vista 3D se queda con las teclas: ahí las atiende un
filtro de eventos en la propia vista.
"""

import math
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

COMMAND = "SWUI_NormalTo"
VIEW_CLASS = "Gui::View3DInventor"
FIT_COMMAND = "Std_ViewFitAll"
KEYS = (("N", COMMAND), ("F", FIT_COMMAND))
AXES = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
SAME = 0.999  # coseno: ya se mira la cara de frente -> darla vuelta
MIN_UP = 0.1  # un eje casi paralelo a la mirada no sirve de "arriba"

_actions = []
_filter = None
_last = None  # última cara/plano de "Normal a" (para darla vuelta si se repite)


# --- Cuentas (sin FreeCAD, probables en el test) ---------------------


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n) if n > 1e-12 else None


def nearest_axis(direction):
    """El eje (±X, ±Y, ±Z) más parecido a la dirección de la mirada."""
    return max(AXES, key=lambda a: _dot(a, direction))


def face_direction(normal, current, again=True):
    """
    Mirada hacia una cara de normal 'normal': de frente. Si ya se la miraba así
    y es la misma cara de la vez anterior (again), del otro lado, como en SW.
    """
    look = _unit((-normal[0], -normal[1], -normal[2]))
    if again and _dot(look, current) > SAME:
        look = (-look[0], -look[1], -look[2])
    return look


def straight_up(direction, current_up):
    """
    "Arriba" derecho para mirar en 'direction': el eje del modelo, proyectado
    sobre la pantalla, más parecido al arriba actual.
    """
    best, best_dot = None, -2.0
    for axis in AXES:
        along = _dot(axis, direction)
        proj = (axis[0] - along * direction[0], axis[1] - along * direction[1], axis[2] - along * direction[2])
        if math.sqrt(_dot(proj, proj)) < MIN_UP:
            continue
        proj = _unit(proj)
        d = _dot(proj, current_up)
        if d > best_dot:
            best, best_dot = proj, d
    return best


def camera_axes(direction, up):
    """Columnas (derecha, arriba, atrás) de la cámara de Coin (mira hacia -Z, arriba +Y)."""
    back = (-direction[0], -direction[1], -direction[2])
    right = _unit(_cross(up, back))
    up = _cross(back, right)
    return right, up, back


# --- FreeCAD ---------------------------------------------------------


def _vec(v):
    return (v.x, v.y, v.z)


def _view():
    try:
        view = FreeCADGui.ActiveDocument.ActiveView
    except Exception:
        return None
    return view if hasattr(view, "setCameraOrientation") else None  # no en hojas de dibujo


def _rotation(direction, up):
    right, up, back = camera_axes(direction, up)
    m = FreeCAD.Matrix(right[0], up[0], back[0], 0,
                       right[1], up[1], back[1], 0,
                       right[2], up[2], back[2], 0,
                       0, 0, 0, 1)
    return FreeCAD.Rotation(m)


def _selected_normal():
    """(normal global, clave) de la cara plana o del plano seleccionado; (None, None) si no hay."""
    try:
        sel = FreeCADGui.Selection.getSelectionEx("", 0)  # ruta completa: coordenadas globales
    except Exception:
        return None, None
    for s in sel:
        for sub in list(s.SubElementNames or []) or [""]:
            normal = _normal_of(s.Object, sub)
            if normal is not None:
                return normal, (s.DocumentName, s.ObjectName, sub)
    return None, None


def _normal_of(root, sub):
    from swui import context_sketch

    element = context_sketch.element_name(sub) if sub else ""
    if element.startswith("Face"):
        try:
            face = root.getSubObject(sub)
            if face is None or not context_sketch.is_planar(face):
                return None
            u0, u1, v0, v1 = face.ParameterRange
            return _vec(face.normalAt((u0 + u1) / 2, (v0 + v1) / 2))
        except Exception:
            return None
    if element:
        return None  # arista o vértice
    try:
        obj, _matrix, _x = root.getSubObject(sub, retType=2)
    except Exception:
        obj = None
    if getattr(obj, "TypeId", "") not in ("App::Plane", "PartDesign::Plane"):
        return None
    try:
        placement = root.getSubObject(sub, retType=3)  # posición global del plano
        return _vec(placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1)))
    except Exception:
        return None


def _editing_sketch():
    try:
        vp = FreeCADGui.ActiveDocument.getInEdit()
        obj = vp.Object if vp is not None else None
    except Exception:
        return None
    return obj if getattr(obj, "TypeId", "") == "Sketcher::SketchObject" else None


def normal_to():
    global _last
    view = _view()
    if view is None:
        return
    ori = view.getCameraOrientation()
    current = _vec(ori.multVec(FreeCAD.Vector(0, 0, -1)))
    current_up = _vec(ori.multVec(FreeCAD.Vector(0, 1, 0)))
    normal, picked = _selected_normal()
    again, _last = picked is not None and picked == _last, picked
    sketch = _editing_sketch() if normal is None else None
    if normal is not None:
        direction = face_direction(normal, current, again)
        up = straight_up(direction, current_up)
    elif sketch is not None:
        rot = sketch.getGlobalPlacement().Rotation
        direction = _vec(rot.multVec(FreeCAD.Vector(0, 0, -1)))
        up = _vec(rot.multVec(FreeCAD.Vector(0, 1, 0)))  # como "Ver croquis" de FreeCAD
    else:
        direction = nearest_axis(current)
        up = straight_up(direction, current_up)
    if up is None:
        return
    view.setCameraOrientation(_rotation(direction, up))


class _NormalToCommand:
    def GetResources(self):
        return {
            "MenuText": "Normal a",
            "ToolTip": "Gira la vista para mirar de frente la cara o plano seleccionado; "
                       "sin selección, a la vista estándar más cercana (tecla N)",
        }

    def IsActive(self):
        return _view() is not None

    def Activated(self):
        try:
            normal_to()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Normal a:\n%s\n" % traceback.format_exc())


# --- Teclas ----------------------------------------------------------


def install():
    """Comando "Normal a" y teclas mientras se está en LikeSolidWorks UI."""
    from swui import layout

    try:
        FreeCADGui.addCommand(COMMAND, _NormalToCommand())
    except Exception:
        pass  # ya registrado
    if getattr(layout.enter, "_swui_keys", False):
        return
    original_enter, original_leave = layout.enter, layout.leave

    def enter(_original=original_enter):
        result = _original()
        add_keys()
        return result

    def leave(_original=original_leave):
        remove_keys()
        return _original()

    enter._swui_keys = leave._swui_keys = True
    layout.enter, layout.leave = enter, leave


def _run(command):
    try:
        FreeCADGui.runCommand(command)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Tecla: %s\n" % traceback.format_exc())


class _KeyFilter(QtCore.QObject):
    """
    Editando un croquis, la vista 3D se queda con las teclas (no llegan los
    atajos de la ventana): ahí N y F se atienden en la propia vista.
    """

    def eventFilter(self, obj, event):
        try:
            if event.type() != QtCore.QEvent.Type.KeyPress or not _actions or event.isAutoRepeat():
                return False
            if event.modifiers() != QtCore.Qt.KeyboardModifier.NoModifier:
                return False
            command = dict(KEYS).get(event.text().upper())
            if command is None:
                return False
            _run(command)
            return True
        except Exception:
            return False


def _attach_all():
    """Poner el filtro en el área de dibujo de cada vista 3D abierta (una sola vez por vista)."""
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        for sub in mdi.subWindowList():
            view = sub.widget()
            if view is None or view.metaObject().className() != VIEW_CLASS:
                continue
            for gv in view.findChildren(QtWidgets.QGraphicsView):
                vp = gv.viewport()
                if not vp.property("swui_keys"):
                    vp.setProperty("swui_keys", True)
                    vp.installEventFilter(_filter)
    except Exception:
        pass


def add_keys():
    global _filter
    if _actions:
        return
    if _filter is None:
        _filter = _KeyFilter()
        try:
            mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
            mdi.subWindowActivated.connect(lambda *_a: _attach_all())
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Teclas N y F: no se encontró el área de ventanas.\n")
    _attach_all()
    try:
        mw = FreeCADGui.getMainWindow()
        for key, command in KEYS:
            action = QtGui.QAction(mw) if hasattr(QtGui, "QAction") else QtWidgets.QAction(mw)  # Qt6 / Qt5
            action.setObjectName("SWUI_Key_" + key)
            action.setShortcut(QtGui.QKeySequence(key))
            action.triggered.connect(lambda *_a, c=command: _run(c))
            mw.addAction(action)
            _actions.append(action)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Teclas N y F no disponibles:\n%s\n" % traceback.format_exc())


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
