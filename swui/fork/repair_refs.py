# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
"Reparar referencias", como cuando SW pide "Editar plano de croquis" o
reasignar aristas.

Busca en el documento lo que perdió su referencia:
- Croquis o plano apoyado en una cara que ya no existe ("subshape not
  found"): si en el mismo objeto hay UNA cara plana justo donde estaba el
  croquis (mismo plano, tocando su geometría), se reasigna sola ("Reparar").
  Si no, se abre el editor de apoyo de FreeCAD para elegir la cara nueva.
- Redondeo / chaflán con aristas o caras que ya no existen: se abre su
  diálogo para volver a elegirlas.
- Croquis con referencias externas perdidas (aristas traídas del modelo): se
  abre el croquis (FreeCAD las marca) para borrarlas y volver a traerlas.

Se abre desde "¿Qué es incorrecto?" (botón Reparar), el clic derecho de una
operación con error y el menú LikeSolidWorks UI. Todo se puede deshacer.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

COMMAND = "SWUI_RepairReferences"
SUPPORT, DRESS_UP, EXTERNAL = "support", "dressup", "external"
TOL = 1e-4

_open = []


# --- Qué está roto ---------------------------------------------------------


def _missing(obj, subs):
    """Subelementos ("Face6", "Edge3"...) que ya no existen en la forma de obj."""
    out = []
    try:
        shape = obj.Shape
    except Exception:
        return list(subs)
    for sub in subs:
        if not sub:
            continue
        try:
            shape.getElement(sub)
        except Exception:
            out.append(sub)
    return out


def broken_support(obj):
    """[(objeto apoyo, subs perdidos)] de un croquis/plano apoyado en caras que ya no están."""
    if getattr(obj, "MapMode", "Deactivated") == "Deactivated":
        return []
    out = []
    try:
        for target, subs in obj.AttachmentSupport:
            lost = _missing(target, subs)
            if lost:
                out.append((target, lost))
    except Exception:
        return []
    return out


def broken_dress_up(obj):
    try:
        if not obj.isDerivedFrom("PartDesign::DressUp"):
            return []
        base, subs = obj.Base
    except Exception:
        return []
    return _missing(base, subs)


def broken_external(sketch):
    out = []
    try:
        for target, subs in sketch.ExternalGeometry:
            out += ["%s.%s" % (target.Label, s) for s in _missing(target, subs)]
    except Exception:
        return []
    return out


def problems(doc):
    """[(objeto, tipo, texto)] de todo lo que perdió su referencia."""
    out = []
    for obj in doc.Objects:
        lost = broken_support(obj)
        if lost:
            names = ", ".join("%s.%s" % (t.Label, s) for t, subs in lost for s in subs)
            out.append((obj, SUPPORT, "Perdió la cara donde estaba apoyado (%s)." % names))
            continue
        lost = broken_dress_up(obj)
        if lost:
            out.append((obj, DRESS_UP, "Perdió aristas o caras elegidas (%s)." % ", ".join(lost)))
            continue
        if getattr(obj, "TypeId", "") == "Sketcher::SketchObject":
            lost = broken_external(obj)
            if lost:
                out.append((obj, EXTERNAL, "Perdió referencias traídas del modelo (%s)." % ", ".join(lost)))
    return out


# --- Arreglo automático del apoyo ------------------------------------------


def plane_of(obj):
    """(punto, normal) del plano del croquis/plano, en las coordenadas de su cuerpo."""
    plc = obj.Placement
    return plc.Base, plc.Rotation.multVec(FreeCAD.Vector(0, 0, 1))


def coplanar_faces(shape, point, normal, tol=TOL):
    """Índices (desde 1) de las caras planas de shape sobre el plano (point, normal)."""
    out = []
    for i, face in enumerate(shape.Faces):
        try:
            surf = face.Surface
            if type(surf).__name__ != "Plane":
                continue
            n = surf.Axis
            if abs(abs(n.dot(normal)) - 1.0) > tol:
                continue
            if abs((surf.Position - point).dot(normal)) > tol * 100:
                continue
            out.append(i + 1)
        except Exception:
            continue
    return out


def auto_support(obj):
    """Cara nueva para el croquis/plano: (objeto, "FaceN") o None si no hay una sola clara."""
    lost = broken_support(obj)
    if len(lost) != 1:
        return None
    target, _subs = lost[0]
    point, normal = plane_of(obj)
    cands = coplanar_faces(target.Shape, point, normal)
    if len(cands) > 1:
        # Varias caras en ese plano: la que toca la geometría del croquis
        try:
            geom = obj.Shape
            touching = [i for i in cands if not geom.isNull() and
                        target.Shape.Faces[i - 1].distToShape(geom)[0] < TOL * 100]
        except Exception:
            touching = []
        cands = touching
    return (target, "Face%d" % cands[0]) if len(cands) == 1 else None


def fix_support(obj, target, sub):
    obj.AttachmentSupport = [(target, sub)]


# --- Acciones ----------------------------------------------------------------


def repair(obj, kind):
    """Reparar obj: devuelve un texto con lo que pasó."""
    doc = obj.Document
    if kind == SUPPORT:
        found = auto_support(obj)
        if found is not None:
            doc.openTransaction("Reparar referencia")
            try:
                fix_support(obj, *found)
                doc.recompute()
            except Exception:
                doc.abortTransaction()
                FreeCAD.Console.PrintError("[SWUI fork] Reparar:\n%s\n" % traceback.format_exc())
                return "No se pudo reparar %s." % obj.Label
            doc.commitTransaction()
            return "%s quedó apoyado en %s.%s." % (obj.Label, found[0].Label, found[1])
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(obj)
        FreeCADGui.runCommand("Part_EditAttachment")
        return "Elegí en la pieza la cara nueva para %s y aceptá." % obj.Label
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.Selection.addSelection(obj)
    FreeCADGui.getDocument(doc.Name).setEdit(obj)
    if kind == DRESS_UP:
        return "Volvé a elegir las aristas/caras de %s en su diálogo." % obj.Label
    return "En el croquis, borrá las referencias marcadas y volvé a traer las aristas."


def show_dialog(doc=None):
    """Ventana "Reparar referencias"."""
    from swui.fork import tree_dialogs as td

    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return 0
    found = problems(doc)
    dialog = QtWidgets.QDialog(FreeCADGui.getMainWindow())
    dialog.setWindowTitle("Reparar referencias")
    dialog.resize(560, 300)
    box = QtWidgets.QVBoxLayout(dialog)
    lst = QtWidgets.QListWidget()
    lst.setWordWrap(True)
    for obj, kind, text in found:
        auto = kind == SUPPORT and auto_support(obj) is not None
        hint = ("Se puede reparar solo." if auto else
                "Hay que elegir la referencia nueva." if kind != EXTERNAL else "Hay que rehacer las referencias.")
        item = td._item(obj, [obj.Label, text, hint])
        item.setData(QtCore.Qt.ItemDataRole.UserRole + 1, kind)
        lst.addItem(item)
    if not found:
        lst.addItem("No hay referencias perdidas.")
    box.addWidget(lst)
    note = QtWidgets.QLabel("")
    note.setWordWrap(True)
    box.addWidget(note)
    row = QtWidgets.QHBoxLayout()
    fix = QtWidgets.QPushButton("Reparar")
    close = QtWidgets.QPushButton("Cerrar")
    row.addStretch(1)
    row.addWidget(fix)
    row.addWidget(close)
    box.addLayout(row)

    def do_fix(*_a):
        item = lst.currentItem() or (lst.item(0) if found else None)
        name = item.data(QtCore.Qt.ItemDataRole.UserRole) if item is not None else None
        obj = doc.getObject(name) if name else None
        if obj is None:
            return
        note.setText(repair(obj, item.data(QtCore.Qt.ItemDataRole.UserRole + 1)))
        if FreeCADGui.Control.activeDialog():
            dialog.close()  # el usuario sigue en el diálogo de FreeCAD

    fix.setEnabled(bool(found))
    fix.clicked.connect(do_fix)
    lst.itemDoubleClicked.connect(do_fix)
    close.clicked.connect(dialog.close)
    td._keep(dialog)
    return len(found)


class _RepairCommand:
    def GetResources(self):
        return {"MenuText": "Reparar referencias...",
                "ToolTip": "Croquis, planos o redondeos que perdieron la cara o arista donde se apoyaban"}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        show_dialog()


def install():
    try:
        FreeCADGui.addCommand(COMMAND, _RepairCommand())
    except Exception:
        pass  # ya registrado
