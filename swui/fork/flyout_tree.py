# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Árbol flotante sobre la vista mientras un panel SW está abierto (el
"FeatureManager desplegable" de SOLIDWORKS).

Con un panel abierto, el panel izquierdo muestra Tareas y el árbol queda en la
pestaña Modelo. Como en SW, arriba a la izquierda de la vista aparece el árbol
de la pieza (Origen con planos y ejes, y las operaciones): un clic en un
renglón elige ese objeto, igual que tocarlo en el árbol (el panel lo toma:
operación para la matriz, plano para la simetría, etc.). El triángulo del
título lo pliega. Se va solo al cerrar el panel.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

VIEW_CLASS = "Gui::View3DInventor"
QSS = ("QTreeWidget { background: rgba(247,247,247,225); border: 1px solid #C8C8C8; }"
       "QTreeWidget::item:hover { color: #ff8000; }")
WIDTH = 230
MAX_HEIGHT_RATIO = 0.6
MARGIN = 8

_state = {"tree": None}


def _viewport():
    try:
        sub = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea).activeSubWindow()
        view = sub.widget() if sub is not None else None
        if view is None or view.metaObject().className() != VIEW_CLASS:
            return None
        return view.findChildren(QtWidgets.QGraphicsView)[0].viewport()
    except Exception:
        return None


def _icon(obj):
    try:
        return obj.ViewObject.Icon
    except Exception:
        return None


def rows(body):
    """[(objeto, [hijos])] para el árbol: Origen con sus planos/ejes, después lo del cuerpo."""
    out = []
    try:
        origin = body.Origin
        out.append((origin, list(origin.OriginFeatures)))
    except Exception:
        pass
    for obj in body.Group:
        if obj.TypeId == "App::Origin":
            continue
        if obj.TypeId == "Sketcher::SketchObject" and _consumed(obj):
            continue  # el croquis de una operación va colgado de ella
        out.append((obj, _sketches_of(obj)))
    return out


def _consumed(sketch):
    try:
        return any(getattr(o, "Profile", None) and o.Profile[0] == sketch for o in sketch.InList)
    except Exception:
        return False


def _sketches_of(obj):
    try:
        prof = obj.Profile[0] if getattr(obj, "Profile", None) else None
    except Exception:
        prof = None
    return [prof] if prof is not None and prof.TypeId == "Sketcher::SketchObject" else []


def _item(obj):
    item = QtWidgets.QTreeWidgetItem(["Origen" if obj.TypeId == "App::Origin" else obj.Label])
    icon = _icon(obj)
    if icon is not None:
        item.setIcon(0, icon)
    item.setData(0, QtCore.Qt.UserRole, obj.Name)
    return item


def show(doc, body):
    hide()
    vp = _viewport()
    if vp is None or body is None:
        return
    try:
        tree = QtWidgets.QTreeWidget(vp)
        tree.setObjectName("SWUI_FlyoutTree")
        tree.setHeaderLabels([doc.Label])  # como SW: el nombre de la pieza
        tree.setStyleSheet(QSS)
        tree.setRootIsDecorated(True)
        for obj, kids in rows(body):
            item = _item(obj)
            for kid in kids:
                item.addChild(_item(kid))
            tree.addTopLevelItem(item)
        tree.header().setSectionsClickable(True)
        tree.header().sectionClicked.connect(lambda *_a: _fold(tree))
        tree.itemClicked.connect(lambda item, _c: _pick(doc.Name, item))
        tree.itemExpanded.connect(lambda *_a: _place(tree, vp))
        tree.itemCollapsed.connect(lambda *_a: _place(tree, vp))
        tree.setProperty("swui_folded", False)
        _place(tree, vp)
        tree.show()
        tree.raise_()
        _state["tree"] = tree
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Árbol flotante:\n%s\n" % traceback.format_exc())


def _visible_rows(tree):
    count = 0
    for i in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(i)
        count += 1
        if item.isExpanded():
            count += item.childCount()
    return count


def _place(tree, vp):
    rows_h = max(tree.sizeHintForRow(0) if tree.topLevelItemCount() else 18, 18)
    height = min(int(vp.height() * MAX_HEIGHT_RATIO), tree.header().height() + _visible_rows(tree) * rows_h + 6)
    if tree.property("swui_folded"):
        height = tree.header().height() + 4
    tree.setGeometry(MARGIN, MARGIN, WIDTH, height)


def _fold(tree):
    """Clic en el título: plegar / desplegar (como la flecha del árbol desplegable de SW)."""
    tree.setProperty("swui_folded", not tree.property("swui_folded"))
    _place(tree, tree.parentWidget())


def _pick(doc_name, item):
    name = item.data(0, QtCore.Qt.UserRole)
    try:
        FreeCADGui.Selection.addSelection(doc_name, name)
    except Exception:
        pass
    try:
        item.treeWidget().clearSelection()
    except Exception:
        pass


def hide():
    tree = _state["tree"]
    _state["tree"] = None
    if tree is not None:
        try:
            tree.hide()
            tree.deleteLater()
        except Exception:
            pass
