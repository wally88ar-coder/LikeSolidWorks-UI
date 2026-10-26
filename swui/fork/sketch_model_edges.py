# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Aristas y vértices del modelo dentro del croquis, como en SOLIDWORKS.

En SW, con un croquis abierto, la cota inteligente o la línea se enganchan
directo en las aristas y vértices de la pieza. En FreeCAD 1.1.4 el croquis
solo ve lo suyo: primero hay que traer la arista con "Convertir entidades"
(Sketcher_Projection). Acá se hace solo: si con una herramienta activa (cota,
relación, línea, círculo...) se hace clic sobre una arista o vértice del
modelo que el croquis todavía no tiene, se agrega como referencia (lo mismo
que Convertir entidades, nada propio del addon queda en el archivo) y el clic
sigue como si la referencia ya hubiera estado ahí.

Cómo:
- Filtro de eventos en la vista 3D; solo editando un croquis, con una
  herramienta activa (FreeCAD les pone un cursor dibujado: BitmapCursor) y
  sin nada del croquis bajo el mouse (la preselección no es del croquis).
- Lo que hay bajo el mouse: view.getObjectsInfo(getCursorPos()) devuelve
  también las aristas cercanas; se prefiere un vértice.
- No se trae nada que dependa del croquis (operaciones posteriores): sería
  una dependencia circular.
- Después de agregarla se manda un movimiento del mouse en el mismo lugar
  para que el croquis la preseleccione, y el clic sigue su curso.

FreeCAD 26.3 ya permite acotar directo a las aristas del modelo: desde esa
versión esto no se instala (queda lo nativo).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

VIEW_CLASS = "Gui::View3DInventor"
WB_NAME = "LikeSolidWorksUIWorkbench"
SKETCH = "Sketcher::SketchObject"
NATIVE_FROM = 26

_filter = None


def native():
    try:
        return int(FreeCAD.Version()[0]) >= NATIVE_FROM
    except Exception:
        return False


def coin_point(x, y, height, ratio=1.0):
    """Punto del mouse (Qt: y hacia abajo) -> punto de la vista 3D (Coin: y hacia arriba, en píxeles reales)."""
    return (int(round(x * ratio)), int(round((height - y) * ratio)))


def pick(hits, sketch_name):
    """
    De lo que hay bajo el mouse, la arista o vértice del modelo a traer:
    (objeto, "VertexN"/"EdgeN") o None. Primero vértices, después aristas.
    """
    found = [(h.get("Object"), h.get("Component", "")) for h in hits or []
             if h.get("Object") and h.get("Object") != sketch_name]
    for prefix in ("Vertex", "Edge"):
        for obj, comp in found:
            if comp.startswith(prefix):
                return obj, comp
    return None


def already(sketch, obj, sub):
    """¿El croquis ya tiene esa referencia?"""
    for target, subs in getattr(sketch, "ExternalGeometry", []) or []:
        if getattr(target, "Name", target) == obj and sub in subs:
            return True
    return False


def depends_on(obj, sketch):
    """¿obj depende del croquis? (traerlo armaría una dependencia circular)"""
    try:
        return sketch in obj.OutListRecursive
    except Exception:
        return True


def _editing_sketch():
    try:
        vp = FreeCADGui.ActiveDocument.getInEdit()
        obj = vp.Object if vp is not None else None
    except Exception:
        return None
    return obj if obj is not None and getattr(obj, "TypeId", "") == SKETCH else None


def _sketch_preselected(sketch):
    try:
        pre = FreeCADGui.Selection.getPreselection()
        return pre is not None and pre.Object is not None and pre.Object.Name == sketch.Name
    except Exception:
        return False


def bring(sketch, obj_name, sub):
    """Agregar la referencia (como Convertir entidades). True si se agregó."""
    doc = sketch.Document
    obj = doc.getObject(obj_name)
    if obj is None or already(sketch, obj_name, sub):
        return False
    if depends_on(obj, sketch):
        FreeCADGui.getMainWindow().statusBar().showMessage(
            "Esa arista es de una operación posterior al croquis: no se puede usar.", 5000)
        return False
    doc.openTransaction("Referencia del modelo")
    try:
        sketch.addExternal(obj_name, sub)
        sketch.recompute()
    except Exception:
        doc.abortTransaction()
        FreeCAD.Console.PrintLog("[SWUI fork] Arista del modelo:\n%s\n" % traceback.format_exc())
        return False
    doc.commitTransaction()
    FreeCADGui.getMainWindow().statusBar().showMessage("Arista del modelo agregada como referencia.", 3000)
    return True


class _Filter(QtCore.QObject):
    def eventFilter(self, viewport, event):
        try:
            if (event.type() != QtCore.QEvent.Type.MouseButtonPress
                    or event.button() != QtCore.Qt.MouseButton.LeftButton
                    or viewport.cursor().shape() != QtCore.Qt.CursorShape.BitmapCursor):
                return False
            if FreeCADGui.activeWorkbench().name() != WB_NAME:
                return False
            sketch = _editing_sketch()
            if sketch is None or _sketch_preselected(sketch):
                return False
            view = FreeCADGui.ActiveDocument.ActiveView
            pos = event.position() if hasattr(event, "position") else QtCore.QPointF(event.pos())
            hit = pick(view.getObjectsInfo(coin_point(pos.x(), pos.y(), viewport.height(),
                                                      viewport.devicePixelRatioF())), sketch.Name)
            if hit is None or not bring(sketch, *hit):
                return False
            # Que el croquis preseleccione la referencia nueva antes de que llegue el clic
            move = QtGui.QMouseEvent(QtCore.QEvent.Type.MouseMove, pos, viewport.mapToGlobal(pos),
                                     QtCore.Qt.MouseButton.NoButton, QtCore.Qt.MouseButton.NoButton,
                                     event.modifiers())
            QtWidgets.QApplication.sendEvent(viewport, move)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Arista del modelo:\n%s\n" % traceback.format_exc())
        return False  # el clic sigue su curso


def _attach_all():
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        for sub in mdi.subWindowList():
            view = sub.widget()
            if view is None or view.metaObject().className() != VIEW_CLASS:
                continue
            for gv in view.findChildren(QtWidgets.QGraphicsView):
                vp = gv.viewport()
                if not vp.property("swui_model_edges"):
                    vp.setProperty("swui_model_edges", True)
                    vp.installEventFilter(_filter)
    except Exception:
        pass


def install():
    """Filtro en las vistas 3D (las abiertas y las que se abran). Nada desde FreeCAD 26.3."""
    global _filter
    if _filter is not None or native():
        return
    _filter = _Filter()
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        mdi.subWindowActivated.connect(lambda *_a: _attach_all())
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Aristas del modelo: no se encontró el área de ventanas.\n")
    _attach_all()
