# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Diálogos del árbol de operaciones, como en SOLIDWORKS:

- "¿Qué es incorrecto?": lista las operaciones con error después de
  reconstruir, con el mensaje de FreeCAD explicado en palabras simples (el
  original queda abajo, por si hace falta buscarlo). Doble clic o "Editar"
  abre la operación. Se abre solo si Ctrl+B / Ctrl+Q terminan con errores.
- "Padre/Hijo": de qué depende la operación y qué depende de ella (sin contar
  el "sólido anterior" de Part Design, que no es padre en el sentido de SW).

Los dos son ventanas no modales: se puede seguir trabajando con ellas abiertas.
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

ERROR = "error"
WAITING = "waiting"

# (texto que aparece en el mensaje de FreeCAD, explicación). Se busca en orden.
EXPLAIN = (
    ("subshape not found", "Perdió la cara o arista donde estaba apoyado (cambió o desapareció). "
                           "Usá «Reparar referencias...»: si puede, la vuelve a encontrar sola."),
    ("total length of zero", "La profundidad es cero."),
    ("Base feature's TopoShape is invalid", "No hay sólido antes de esta operación (lo de arriba está "
                                            "suprimido, vacío o con error): no tiene sobre qué trabajar."),
    ("not a solid", "El resultado no es un sólido cerrado."),
    ("multiple solids", "El resultado quedó partido en varios sólidos separados."),
    ("Resulting shape is empty", "La operación no deja nada: el resultado quedó vacío."),
    ("BRep_API: command not done", "El motor de geometría no pudo hacerla. En redondeos y chaflanes suele "
                                   "ser un radio o distancia demasiado grande para esa arista."),
    ("conflicting constraints", "El croquis tiene relaciones o cotas que se contradicen."),
    ("redundant constraints", "El croquis tiene relaciones o cotas de más (repetidas)."),
    ("Wire is not closed", "El contorno del croquis no está cerrado."),
    ("not closed", "El contorno del croquis no está cerrado."),
    ("does not intersect", "La operación no toca el sólido."),
    ("intersect", "El contorno del croquis se cruza consigo mismo."),
    ("external geometry", "Una referencia externa del croquis (arista o punto de la pieza) se perdió."),
    ("Missing", "Falta un elemento al que hace referencia."),
    ("cannot be used", "Lo seleccionado no sirve para esta operación."),
)
WAITING_TEXT = "No se reconstruyó porque depende de una operación con error."
UNKNOWN_TEXT = "FreeCAD no pudo reconstruirla."

_open = []  # ventanas abiertas (para que Python no las borre)


def explain(message):
    """Mensaje de FreeCAD -> explicación en palabras simples."""
    low = (message or "").lower()
    for key, text in EXPLAIN:
        if key.lower() in low:
            return text
    return UNKNOWN_TEXT


def _skip(obj):
    return getattr(obj, "TypeId", "") in ("App::Origin", "App::Line", "App::Plane", "App::Point")


def problems(doc):
    """[(objeto, ERROR o WAITING, mensaje de FreeCAD)] del documento."""
    out = []
    for obj in doc.Objects:
        if _skip(obj):
            continue
        state = list(getattr(obj, "State", []))
        try:
            message = obj.getStatusString()
        except Exception:
            message = ""
        if "Invalid" in state or "Error" in state:
            out.append((obj, ERROR, message))
        elif "Touched" in state:
            out.append((obj, WAITING, message))
    return out


def _icon(obj):
    try:
        return obj.ViewObject.Icon
    except Exception:
        return None


def _select(obj):
    try:
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addSelection(obj)
    except Exception:
        pass


def _keep(dialog):
    _open.append(dialog)
    dialog.finished.connect(lambda *_a: _open.remove(dialog) if dialog in _open else None)
    dialog.show()
    dialog.raise_()


def _item(obj, lines):
    item = QtWidgets.QListWidgetItem("\n".join(lines))
    icon = _icon(obj)
    if icon is not None:
        item.setIcon(icon)
    item.setData(QtCore.Qt.ItemDataRole.UserRole, obj.Name)
    return item


def show_whats_wrong(doc=None):
    """Ventana "¿Qué es incorrecto?". Devuelve la cantidad de problemas."""
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return 0
    found = problems(doc)
    dialog = QtWidgets.QDialog(FreeCADGui.getMainWindow())
    dialog.setWindowTitle("¿Qué es incorrecto?")
    dialog.resize(560, 320)
    box = QtWidgets.QVBoxLayout(dialog)
    lst = QtWidgets.QListWidget()
    lst.setWordWrap(True)
    for obj, kind, message in found:
        if kind == ERROR:
            lines = ["Error: " + obj.Label, explain(message)]
            if message and message not in ("Error", "Invalid"):
                lines.append("(FreeCAD: %s)" % message)
        else:
            lines = ["Sin reconstruir: " + obj.Label, WAITING_TEXT]
        lst.addItem(_item(obj, lines))
    if not found:
        lst.addItem("No hay errores.")
    box.addWidget(lst)
    row = QtWidgets.QHBoxLayout()
    repair = QtWidgets.QPushButton("Reparar referencias...")
    edit = QtWidgets.QPushButton("Editar")
    close = QtWidgets.QPushButton("Cerrar")
    row.addWidget(repair)
    row.addStretch(1)
    row.addWidget(edit)
    row.addWidget(close)
    box.addLayout(row)

    def do_repair(*_a):
        from swui.fork import repair_refs

        dialog.close()
        repair_refs.show_dialog(doc)

    repair.clicked.connect(do_repair)

    def chosen():
        item = lst.currentItem()
        name = item.data(QtCore.Qt.ItemDataRole.UserRole) if item is not None else None
        return doc.getObject(name) if name else None

    def do_edit(*_a):
        obj = chosen()
        if obj is not None:
            _select(obj)
            FreeCADGui.getDocument(doc.Name).setEdit(obj)
            dialog.close()

    lst.currentItemChanged.connect(lambda *_a: _select(chosen()) if chosen() is not None else None)
    lst.itemDoubleClicked.connect(do_edit)
    edit.clicked.connect(do_edit)
    close.clicked.connect(dialog.close)
    _keep(dialog)
    return len(found)


def show_parent_child(obj):
    """Ventana Padre/Hijo de la operación o croquis."""
    from swui.fork import feature_tree as ft

    dialog = QtWidgets.QDialog(FreeCADGui.getMainWindow())
    dialog.setWindowTitle("Padre/Hijo: " + obj.Label)
    dialog.resize(420, 360)
    box = QtWidgets.QVBoxLayout(dialog)
    for title, objs in (("Padres (de qué depende)", ft.parents(obj)),
                        ("Hijos (qué depende de esta)", ft.children(obj))):
        box.addWidget(QtWidgets.QLabel(title))
        lst = QtWidgets.QListWidget()
        for o in objs:
            lst.addItem(_item(o, [o.Label]))
        if not objs:
            lst.addItem("(ninguno)")
        lst.currentItemChanged.connect(
            lambda item, *_a: _select(obj.Document.getObject(item.data(QtCore.Qt.ItemDataRole.UserRole)))
            if item is not None and item.data(QtCore.Qt.ItemDataRole.UserRole) else None)
        box.addWidget(lst)
    close = QtWidgets.QPushButton("Cerrar")
    close.clicked.connect(dialog.close)
    box.addWidget(close, 0, QtCore.Qt.AlignmentFlag.AlignRight)
    _keep(dialog)
