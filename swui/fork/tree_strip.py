# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Franja Ecuaciones / Sólidos / Material arriba del árbol, como las carpetas del
FeatureManager de SOLIDWORKS (fase 3). El árbol de FreeCAD no acepta renglones
inventados, así que es una franja propia encima, en la pestaña Modelo.

- "Ecuaciones" (solo si el documento tiene variables globales o ecuaciones, como en
  SW): clic abre la ventana Ecuaciones.
- "Sólidos(n)": clic despliega la lista de sólidos; clic en uno lo elige (para
  asignarle un material solo a él, por ejemplo).
- "Material <sin especificar>" o el nombre: clic abre la ventana Material; clic
  derecho: Editar material / Quitar material.
Solo en documentos de pieza (en un ensamblaje cada pieza lleva su material). Solo
dentro de LikeSolidWorks UI.
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

STRIP_NAME = "SWUI_TreeStrip"
POLL_MS = 1000
ROW_HEIGHT = 20

_strip = None
_timer = None


def _icon(name):
    from swui import paths

    path = paths.icon("fork/" + name)
    return QtGui.QIcon(path) if path else QtGui.QIcon()


def rows_for(doc):
    """
    Renglones de la franja para un documento: [(clave, texto)] (sin Qt, probable en el test).
    """
    from swui.fork import equations, material

    if doc is None:
        return []
    roots = [o for o in doc.Objects if not o.InList]
    if any(getattr(o, "TypeId", "") == "Assembly::AssemblyObject" for o in roots):
        return []  # ensamblaje: cada pieza tiene su material
    parts = material.part_objects(doc)
    out = []
    try:
        if equations.count(doc):
            out.append(("equations", "Ecuaciones"))
    except Exception:
        pass
    solids = [o for o in parts if _solid_count(o)]
    out.append(("solids", "Sólidos(%d)" % len(solids)))
    out.append(("material", material.summary(doc)))
    return out


def _solid_count(obj):
    try:
        return len(obj.Shape.Solids)
    except Exception:
        return 0


class _Row(QtWidgets.QToolButton):
    def __init__(self, parent, key):
        super().__init__(parent)
        self.key = key
        self.setAutoRaise(True)
        self.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.setIconSize(QtCore.QSize(16, 16))
        self.setFixedHeight(ROW_HEIGHT)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setStyleSheet("QToolButton { text-align: left; border: none; padding-left: 4px; background: transparent; }"
                           "QToolButton:hover { background: #e5eef6; }")


class _Strip(QtWidgets.QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName(STRIP_NAME)
        self.box = QtWidgets.QVBoxLayout(self)
        self.box.setContentsMargins(2, 2, 2, 2)
        self.box.setSpacing(0)
        self.buttons = {}
        for key, icon in (("equations", "equations"), ("solids", "solids"), ("material", "material")):
            b = _Row(self, key)
            b.setIcon(_icon(icon))
            b.clicked.connect(lambda *_a, k=key: self._clicked(k))
            if key == "material":
                b.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
                b.customContextMenuRequested.connect(self._material_menu)
            self.box.addWidget(b)
            self.buttons[key] = b
            if key == "solids":
                self.solid_list = QtWidgets.QListWidget(self)
                self.solid_list.setMaximumHeight(90)
                self.solid_list.hide()
                self.solid_list.itemClicked.connect(self._pick_solid)
                self.box.addWidget(self.solid_list)
        line = QtWidgets.QFrame(self)
        line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        line.setStyleSheet("color: #d4d4d4;")
        self.box.addWidget(line)
        self.last = None

    def refresh(self):
        doc = FreeCAD.ActiveDocument
        try:
            rows = rows_for(doc)
        except Exception:
            rows = []
        state = (doc.Name if doc else None, tuple(rows))
        if state == self.last:
            return
        self.last = state
        shown = dict(rows)
        for key, button in self.buttons.items():
            button.setVisible(key in shown)
            if key in shown:
                button.setText(shown[key])
        self.setVisible(bool(rows))
        if self.solid_list.isVisible():
            self._fill_solids()

    def _clicked(self, key):
        if key == "equations":
            from swui.fork import equations

            equations.show_dialog()
        elif key == "material":
            from swui.fork import material

            material.show_dialog()
        elif key == "solids":
            if self.solid_list.isVisible():
                self.solid_list.hide()
            else:
                self._fill_solids()
                self.solid_list.show()

    def _fill_solids(self):
        from swui.fork import material

        self.solid_list.clear()
        doc = FreeCAD.ActiveDocument
        if doc is None:
            return
        for obj in material.part_objects(doc):
            if not _solid_count(obj):
                continue
            info, _src = material.material_info(obj)
            text = "%s   (%s)" % (obj.Label, info["name"] if info else "sin material")
            item = QtWidgets.QListWidgetItem(text)
            try:
                item.setIcon(obj.ViewObject.Icon)
            except Exception:
                pass
            item.setData(QtCore.Qt.ItemDataRole.UserRole, obj.Name)
            self.solid_list.addItem(item)

    def _pick_solid(self, item):
        doc = FreeCAD.ActiveDocument
        obj = doc.getObject(item.data(QtCore.Qt.ItemDataRole.UserRole)) if doc else None
        if obj is not None:
            FreeCADGui.Selection.clearSelection()
            FreeCADGui.Selection.addSelection(obj)

    def _material_menu(self, pos):
        from swui.fork import material

        menu = QtWidgets.QMenu(self)
        edit = menu.addAction("Editar material")
        remove = menu.addAction("Quitar material")
        chosen = menu.exec(self.buttons["material"].mapToGlobal(pos))
        if chosen is edit:
            material.show_dialog()
        elif chosen is remove:
            doc = FreeCAD.ActiveDocument
            if doc is None:
                return
            doc.openTransaction("Quitar material")
            material.assign(material.targets(doc), None)
            doc.commitTransaction()
            self.last = None
            self.refresh()


def _tree_box(mw):
    """Layout del contenedor del árbol (QVBoxLayout con el Gui::TreeWidget), o None."""
    for dock in mw.findChildren(QtWidgets.QDockWidget):
        if dock.objectName() != "Model":
            continue
        for tree in dock.findChildren(QtWidgets.QTreeWidget):
            if tree.metaObject().className() != "Gui::TreeWidget" and "TreeWidget" not in tree.metaObject().className():
                continue
            parent = tree.parentWidget()
            box = parent.layout() if parent is not None else None
            if isinstance(box, QtWidgets.QBoxLayout):
                return parent, box
    return None


def attach():
    global _strip, _timer
    mw = FreeCADGui.getMainWindow()
    found = _tree_box(mw)
    if found is None:
        return False
    parent, box = found
    if _strip is None or _strip.parent() is not parent:
        _strip = _Strip(parent)
        box.insertWidget(0, _strip)
    _strip.last = None
    _strip.refresh()
    if _timer is None:
        _timer = QtCore.QTimer(mw)
        _timer.setInterval(POLL_MS)
        _timer.timeout.connect(_tick)
    _timer.start()
    return True


def _tick():
    if _strip is not None:
        try:
            _strip.refresh()
        except Exception:
            pass


def refresh_now():
    if _strip is not None:
        _strip.last = None
        _tick()


def detach():
    if _timer is not None:
        _timer.stop()
    if _strip is not None:
        _strip.hide()


def install():
    from swui import layout
    from swui.fork import equations, material

    material.add_listener(refresh_now)
    equations.add_listener(refresh_now)
    if getattr(layout.enter, "_swui_strip", False):
        return
    original_enter, original_leave = layout.enter, layout.leave

    def enter(_original=original_enter):
        result = _original()
        QtCore.QTimer.singleShot(800, attach)  # el árbol ya acomodado (panel_sw)
        return result

    def leave(_original=original_leave):
        detach()
        return _original()

    enter._swui_strip = leave._swui_strip = True
    layout.enter, layout.leave = enter, leave
