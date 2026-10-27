# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Combinar como en SOLIDWORKS (multicuerpo, etapa C): Agregar / Eliminar / Común.

Panel igual al PropertyManager de SW (capturas del usuario, 2026-10-26):
- Tipo de operación: Agregar / Eliminar / Común.
- Agregar y Común: "Sólidos para combinar" (lista que siempre espera selección).
- Eliminar: "Sólido principal" (casilla) y "Sólidos para substraer" (lista).
Un clic en una cara o en el árbol elige ese sólido (su Cuerpo); otro clic lo saca.

Por debajo, la Booleana nativa de Part Design (PartDesign::Boolean, Fuse / Cut / Common)
dentro del Cuerpo principal, con los otros Cuerpos como herramientas (FreeCAD los oculta y ya
no cuentan como sólidos aparte: material.consumes). Es un objeto nativo: el archivo abre sin
el addon. En Agregar / Común el principal es el primero de la lista (como SW, el sólido que
queda); si se lo saca, pasa a serlo el siguiente y la operación se muda a ese Cuerpo.
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets
from swui.fork import dress_up_panel as dp

COMMAND = "SWUI_Combine"
BOOLEAN = "PartDesign::Boolean"
LABEL = "Combinar"
TYPES = (("Agregar", "Fuse"), ("Eliminar", "Cut"), ("Común", "Common"))


# --- Cuentas sin FreeCAD (probables en el test) -------------------------------


def toggle_body(bodies, body):
    """Clic en un sólido: lo suma a la lista; si ya estaba, lo saca (como SW)."""
    return [b for b in bodies if b is not body] if body in bodies else bodies + [body]


def split_roles(kind, bodies, main):
    """
    (principal, herramientas) según el tipo. Agregar/Común: el primero de la lista es el
    principal. Eliminar: el principal es el de su casilla.
    """
    if kind == "Cut":
        return main, [b for b in bodies if b is not main]
    if not bodies:
        return None, []
    return bodies[0], list(bodies[1:])


def next_label(used):
    n = 1
    while "%s%d" % (LABEL, n) in used:
        n += 1
    return "%s%d" % (LABEL, n)


# --- Panel ---------------------------------------------------------------


def _body_of(obj):
    from swui.fork import multibody

    if obj is not None and obj.TypeId == "PartDesign::Body":
        return obj
    return multibody.body_of(obj)


class CombinePanel(dp.SwPanel):
    TRANSACTION = "Combinar"
    FAIL = "FreeCAD no pudo combinar esos sólidos."
    NOTHING = "Elegí al menos dos sólidos."

    def __init__(self, obj):
        self.host = _body_of(obj)
        tools = [b for b in (obj.Group or []) if b is not None]
        self.kind = obj.Type if obj.Type in ("Fuse", "Cut", "Common") else "Fuse"
        self.main = self.host
        self.bodies = ([self.host] + tools) if self.kind != "Cut" else tools
        self.main_active = False
        doc = obj.Document
        self.body_visible = {b.Name: b.Visibility for b in doc.Objects if b.TypeId == "PartDesign::Body"}
        super().__init__(obj)

    # --- interfaz

    def _build(self):
        from swui import paths
        from swui.compat import QtGui

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(self.obj.Label)
        icon = paths.icon("fork/combine")
        if icon:
            self.form.setWindowIcon(QtGui.QIcon(icon))
        box = QtWidgets.QVBoxLayout(self.form)
        kinds = QtWidgets.QGroupBox("Tipo de operación")
        kl = QtWidgets.QVBoxLayout(kinds)
        self.radios = {}
        self.group = QtWidgets.QButtonGroup(self.form)
        for text, kind in TYPES:
            radio = QtWidgets.QRadioButton(text, kinds)
            radio.setChecked(kind == self.kind)
            radio.toggled.connect(lambda on, k=kind: self._kind(k) if on else None)
            self.group.addButton(radio)
            kl.addWidget(radio)
            self.radios[kind] = radio
        box.addWidget(kinds)
        self.main_group = QtWidgets.QGroupBox("Sólido principal")
        ml = QtWidgets.QVBoxLayout(self.main_group)
        self.main_box = dp.RefBox(self._activate_main)
        ml.addWidget(self.main_box)
        box.addWidget(self.main_group)
        self.list_group = QtWidgets.QGroupBox("Sólidos para combinar")
        ll = QtWidgets.QVBoxLayout(self.list_group)
        self.list = dp.pick_list(self.remove_current, self.clear)
        self.list.itemClicked.connect(lambda *_a: self._activate_list())
        ll.addWidget(self.list)
        box.addWidget(self.list_group)
        box.addWidget(self._message_label())
        box.addStretch(1)
        self._refresh()

    def _kind(self, kind):
        if kind == self.kind:
            return
        old = self.kind
        self.kind = kind
        if kind == "Cut" and old != "Cut":  # el primero pasa a ser el principal
            self.main = self.bodies[0] if self.bodies else self.host
            self.bodies = self.bodies[1:]
        elif kind != "Cut" and old == "Cut":
            self.bodies = ([self.main] if self.main else []) + [b for b in self.bodies if b is not self.main]
        self.main_active = False
        self._refresh()
        self._changed()

    def _activate_main(self, _box):
        self.main_active = True
        self._refresh()

    def _activate_list(self):
        self.main_active = False
        self._refresh()

    def _refresh(self):
        cut = self.kind == "Cut"
        self.main_group.setVisible(cut)
        self.list_group.setTitle("Sólidos para substraer" if cut else "Sólidos para combinar")
        self.main_box.setText(self.main.Label if (cut and self.main is not None) else "")
        self.main_box.setStyleSheet(dp.ACTIVE_QSS if (cut and self.main_active) else "")
        self.list.setStyleSheet("" if (cut and self.main_active) else "QListWidget { %s }" % dp.ACTIVE_QSS)
        self.list.clear()
        for body in self.bodies:
            self.list.addItem(body.Label)

    def remove_current(self, *_a):
        row = self.list.currentRow()
        if 0 <= row < len(self.bodies):
            self.bodies = self.bodies[:row] + self.bodies[row + 1:]
            self._refresh()
            self._changed()

    def clear(self, *_a):
        self.bodies = []
        self._refresh()
        self._changed()

    # --- selección

    def _pick(self, obj, sub):
        from swui.fork import multibody

        body = _body_of(obj)
        if body is None or body not in multibody.solid_bodies(self.doc) and body is not self.host \
                and body not in self.bodies:
            return False
        if self.kind == "Cut" and self.main_active:
            self.main = body
            self.bodies = [b for b in self.bodies if b is not body]
            self.main_active = False
            return True
        if self.kind == "Cut" and body is self.main:
            return False
        self.bodies = toggle_body(self.bodies, body)
        return True

    # --- operación nativa

    def _move_to(self, body):
        """La Booleana vive en el Cuerpo principal: si cambió, se muda."""
        from swui.fork import multibody

        if body is None or body is self.host:
            return
        old = self.host
        previous = self.obj.BaseFeature
        was_tip = old.Tip is self.obj
        old.removeObject(self.obj)
        if was_tip and previous is not None:
            multibody._set_tip(old, previous)
        body.addObject(self.obj)
        multibody._set_tip(body, self.obj)
        self.host = body
        self.base = self.obj.BaseFeature
        for o in body.Group:
            if o.Name not in self.visible:
                try:
                    self.visible[o.Name] = o.Visibility
                except Exception:
                    pass

    def _apply(self):
        main, tools = split_roles(self.kind, self.bodies, self.main)
        if main is None:
            return "Elegí el sólido principal."
        self._move_to(main)
        tools = [t for t in tools if t is not self.host]
        if self.obj.Type != self.kind:
            self.obj.Type = self.kind
        if list(self.obj.Group or []) != tools:
            self.obj.Group = tools
        for body in self.doc.Objects:
            if body.TypeId == "PartDesign::Body" and body is not self.host:
                want = self.body_visible.get(body.Name, body.Visibility) and body not in tools
                if body.Visibility != want:
                    body.Visibility = want
        return ""

    def _ready(self):
        return bool(split_roles(self.kind, self.bodies, self.main)[1])

    def _nothing(self):
        return not self._ready()

    def _overlays(self, base, result):
        return []

    def reject(self):
        result = super().reject()
        for name, vis in self.body_visible.items():
            body = self.doc.getObject(name)
            if body is not None and body.Visibility != vis:
                body.Visibility = vis
        return result


# --- Comando -------------------------------------------------------------------


def start(doc=None):
    """Crear la Booleana en el Cuerpo elegido (o el activo) y abrir el panel."""
    from swui.fork import multibody

    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return None
    bodies = multibody.solid_bodies(doc)
    if len(bodies) < 2:
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Combinar",
                                          "Hacen falta al menos dos sólidos (Cuerpos) en la pieza.")
        return None
    chosen = []
    for sel in FreeCADGui.Selection.getSelectionEx(doc.Name):
        body = _body_of(sel.Object)
        if body in bodies and body not in chosen:
            chosen.append(body)
    host = chosen[0] if chosen else _active_body(doc, bodies)
    doc.openTransaction("Combinar")
    obj = host.newObject(BOOLEAN, "Boolean")
    obj.Label = next_label(set(o.Label for o in doc.Objects))
    obj.Type = "Fuse"
    if len(chosen) > 1:
        obj.Group = chosen[1:]
    multibody._set_tip(host, obj)
    FreeCADGui.Selection.clearSelection()
    FreeCADGui.getDocument(doc.Name).setEdit(obj)  # el panel SW reemplaza al nativo (dress_up_panel)
    return obj


def _active_body(doc, bodies):
    try:
        body = FreeCADGui.ActiveDocument.ActiveView.getActiveObject("pdbody")
        if body in bodies:
            return body
    except Exception:
        pass
    return bodies[0]


class _CombineCommand:
    def GetResources(self):
        from swui import paths

        return {"MenuText": "Combinar", "ToolTip": "Agregar, eliminar o dejar lo común entre sólidos (como SW)",
                "Pixmap": paths.icon("fork/combine") or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        start()


def install():
    dp.PANELS[BOOLEAN] = CombinePanel
    try:
        FreeCADGui.addCommand(COMMAND, _CombineCommand())
    except Exception:
        pass  # ya registrado
