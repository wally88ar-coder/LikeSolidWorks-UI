# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Panel de Redondeo como el PropertyManager de SOLIDWORKS 2018.

El diálogo de FreeCAD pide prender un botón "Seleccionar" antes de tocar las
aristas (el usuario no lo encontró al reparar un redondeo). Acá, como en SW:
- la lista "Elementos a redondear" siempre espera selección: un clic en una
  arista o cara la agrega, otro clic la saca (también Supr o clic derecho);
- radio y vista previa al momento (caras nuevas en amarillo, como SW);
- una referencia perdida queda en rojo en la lista para sacarla y elegir otra.

Por debajo sigue siendo el PartDesign::Fillet de FreeCAD (el archivo guarda
un redondeo común: abre sin el addon y en versiones nuevas). Cómo se engancha:
el comando de FreeCAD crea la operación y la pone en edición; un observador
(slotInEdit) cierra el diálogo nativo (Control.closeDialog deja la operación,
el modo edición y la transacción abiertos) y abre este panel. Así sirve igual
desde la cinta, el menú, "Editar operación" o "Reparar referencias".
Aceptar confirma la transacción; Cancelar la deshace (un redondeo nuevo
desaparece, uno editado vuelve a como estaba).

FreeCAD (OpenCASCADE) siempre propaga el redondeo a las aristas tangentes:
"Propagación tangente" se muestra marcada y fija.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

QAction = getattr(QtGui, "QAction", None) or QtWidgets.QAction  # Qt6 / Qt5

WB_NAME = "LikeSolidWorksUIWorkbench"
FILLET = "PartDesign::Fillet"
PREVIEW_COLOR = (1.0, 0.86, 0.0)  # amarillo de la vista previa de SW
PICKED_COLOR = (0.26, 0.53, 0.71)  # celeste SW (#4288B5, igual que look_sw)
CURRENT_COLOR = (1.0, 0.55, 0.0)  # naranja: renglón elegido en la lista
LINE_WIDTH = 3
PREVIEW_DELAY_MS = 250
MISSING_COLOR = "#C00000"

_state = {"panel": None, "native": False}  # native: dejar el diálogo de FreeCAD (si el panel falló)


# --- Nombres (sin FreeCAD, probables en el test) -----------------------


def sw_names(subs):
    """["Edge3", "Face1", "Edge7"] -> ["Arista<1>", "Cara<1>", "Arista<2>"] (como SW)."""
    count = {"Edge": 0, "Face": 0}
    out = []
    for sub in subs:
        kind = "Edge" if sub.startswith("Edge") else "Face" if sub.startswith("Face") else None
        if kind is None:
            out.append(sub)
            continue
        count[kind] += 1
        out.append("%s<%d>" % ("Arista" if kind == "Edge" else "Cara", count[kind]))
    return out


def toggle(subs, sub):
    """Agregar sub a la lista o sacarlo si ya estaba (clic en algo ya elegido)."""
    return [s for s in subs if s != sub] if sub in subs else subs + [sub]


# --- Geometría ---------------------------------------------------------


def _element(shape, sub):
    try:
        return shape.getElement(sub)
    except Exception:
        return None


def _global_shape(obj):
    from swui.fork import sketch_model_edges as sme

    return sme._global_shape(obj)


def new_faces(result, base):
    """Índices de las caras del resultado que no estaban en el sólido anterior (el redondeo)."""
    from swui.fork import feature_tree as ft

    old = base.Faces
    return [i for i, f in enumerate(result.Faces) if not any(ft.same_surface(f, g) for g in old)]


def to_base(shape, sub, base):
    """Arista/cara tocada en la vista previa -> su nombre en el sólido anterior (o None)."""
    from swui.fork import feature_tree as ft

    geo = _element(shape, sub)
    if geo is None:
        return None
    found = ft.remap([(sub, geo)], base)
    return found[0] if found else None


def nearest(geo, base, subs):
    """De los elementos elegidos, el más cercano a geo (una cara amarilla tocada)."""
    best, dist = None, None
    for sub in subs:
        el = _element(base, sub)
        if el is None:
            continue
        try:
            d = geo.distToShape(el)[0]
        except Exception:
            continue
        if dist is None or d < dist:
            best, dist = sub, d
    return best


# --- Dibujo sobre la vista ----------------------------------------------


def _lines_node(shapes, color, width):
    from pivy import coin

    sep = coin.SoSeparator()
    mat = coin.SoBaseColor()
    mat.rgb = color
    style = coin.SoDrawStyle()
    style.lineWidth = width
    sep.addChild(mat)
    sep.addChild(style)
    for shape in shapes:
        for edge in shape.Edges:
            try:
                pts = edge.discretize(Number=48)
            except Exception:
                continue
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, len(pts), [(p.x, p.y, p.z) for p in pts])
            sep.addChild(coords)
            sep.addChild(coin.SoLineSet())
    return sep


def _faces_node(faces, color):
    from pivy import coin

    sep = coin.SoSeparator()
    mat = coin.SoMaterial()
    mat.diffuseColor = color
    mat.emissiveColor = tuple(c * 0.35 for c in color)
    offset = coin.SoPolygonOffset()  # por delante de las caras iguales del sólido
    offset.factor = -1.0
    offset.units = -1.0
    sep.addChild(mat)
    sep.addChild(offset)
    for face in faces:
        try:
            pts, tris = face.tessellate(0.05)
        except Exception:
            continue
        if not tris:
            continue
        coords = coin.SoCoordinate3()
        coords.point.setValues(0, len(pts), [(p.x, p.y, p.z) for p in pts])
        index = []
        for a, b, c in tris:
            index += [a, b, c, -1]
        fs = coin.SoIndexedFaceSet()
        fs.coordIndex.setValues(0, len(index), index)
        sep.addChild(coords)
        sep.addChild(fs)
    return sep


# --- Panel -------------------------------------------------------------


class _PickObserver:
    """Toda selección en la vista mientras el panel está abierto va a la lista."""

    def __init__(self, panel):
        self.panel = panel

    def addSelection(self, _doc, _obj, _sub, _pnt):
        if not self.panel.busy:
            QtCore.QTimer.singleShot(0, self.panel.take_selection)


class _ListKeys(QtCore.QObject):
    """Supr en la lista borra el renglón (le gana al Supr de FreeCAD, que borraría objetos)."""

    def __init__(self, panel):
        super().__init__()
        self.panel = panel

    def eventFilter(self, _watched, event):
        kind = event.type()
        if kind in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress) and \
                event.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
            event.accept()
            if kind == QtCore.QEvent.KeyPress:
                self.panel.remove_current()
            return True
        return False


class FilletPanel:
    def __init__(self, obj):
        self.obj = obj
        self.doc = obj.Document
        self.gdoc = FreeCADGui.getDocument(self.doc.Name)
        self.busy = False
        self.valid = False
        self.nodes = []
        self.base = obj.BaseFeature or (obj.Base[0] if obj.Base else None)
        self.subs = self._initial_subs()
        self.visible = self._remember_visibility()
        self._build()
        if not self.doc.HasPendingTransaction:
            self.doc.openTransaction("Editar redondeo")
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.preview)
        self.observer = _PickObserver(self)
        FreeCADGui.Selection.addObserver(self.observer)
        FreeCADGui.Selection.clearSelection()
        self.preview()

    # --- datos

    def _initial_subs(self):
        try:
            owner, subs = self.obj.Base
        except Exception:
            return []
        subs = list(subs)
        if owner is not None and self.base is not None and owner != self.base:
            # FreeCAD a veces apoya el redondeo en la operación de la arista tocada,
            # no en el sólido anterior: pasar los nombres al sólido anterior.
            moved = []
            for sub in subs:
                name = to_base(owner.Shape, sub, self.base.Shape)
                if name and name not in moved:
                    moved.append(name)
            subs = moved
        return subs

    def _missing(self, sub):
        return self.base is None or _element(self.base.Shape, sub) is None

    def _remember_visibility(self):
        from swui.fork import feature_tree as ft

        body = ft.body_of(self.obj)
        objs = ft.features(body) if body is not None else [self.obj]
        out = {}
        for o in objs:
            try:
                out[o.Name] = o.Visibility
            except Exception:
                pass
        return out

    def _restore_visibility(self):
        for name, vis in self.visible.items():
            o = self.doc.getObject(name)
            if o is not None and o.Visibility != vis:
                o.Visibility = vis

    def _show_only(self, shown):
        for name in self.visible:
            o = self.doc.getObject(name)
            if o is not None:
                want = o == shown
                if o.Visibility != want:
                    o.Visibility = want

    # --- interfaz

    def _build(self):
        box = QtWidgets.QWidget()
        box.setWindowTitle("Elementos a redondear")
        lay = QtWidgets.QVBoxLayout(box)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Radio:"))
        self.radius = QtWidgets.QDoubleSpinBox()
        self.radius.setDecimals(2)
        self.radius.setRange(0.01, 100000.0)
        self.radius.setSuffix(" mm")
        self.radius.setValue(self.obj.Radius.Value)
        self.radius.setKeyboardTracking(False)
        if self._has_expression("Radius"):
            self.radius.setEnabled(False)
            self.radius.setToolTip("El radio está controlado por una ecuación")
        self.radius.valueChanged.connect(lambda *_a: self.timer.start(PREVIEW_DELAY_MS))
        row.addWidget(self.radius, 1)
        lay.addLayout(row)

        lay.addWidget(QtWidgets.QLabel("Aristas y caras (clic en la pieza):"))
        self.list = QtWidgets.QListWidget()
        self.list.setMinimumHeight(90)
        self.list.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
        act = QAction("Borrar", self.list)
        act.triggered.connect(self.remove_current)
        self.list.addAction(act)
        act = QAction("Borrar selecciones", self.list)
        act.triggered.connect(self.clear)
        self.list.addAction(act)
        self.keys = _ListKeys(self)
        self.list.installEventFilter(self.keys)
        self.list.currentRowChanged.connect(lambda *_a: self._draw())
        lay.addWidget(self.list)

        self.tangent = QtWidgets.QCheckBox("Propagación tangente")
        self.tangent.setChecked(True)
        self.tangent.setEnabled(False)
        self.tangent.setToolTip("FreeCAD siempre sigue las aristas tangentes")
        lay.addWidget(self.tangent)

        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: %s;" % MISSING_COLOR)
        self.message.hide()
        lay.addWidget(self.message)
        self.form = box
        self._fill_list()

    def _has_expression(self, prop):
        try:
            return any(path == prop for path, _e in self.obj.ExpressionEngine)
        except Exception:
            return False

    def _fill_list(self):
        row = self.list.currentRow()
        self.list.clear()
        for sub, text in zip(self.subs, sw_names(self.subs)):
            item = QtWidgets.QListWidgetItem(text)
            if self._missing(sub):
                item.setText(text + "  (no se encuentra: borrala y elegí otra)")
                item.setForeground(QtGui.QBrush(QtGui.QColor(MISSING_COLOR)))
            self.list.addItem(item)
        if self.subs:
            self.list.setCurrentRow(min(max(row, 0), len(self.subs) - 1) if row >= 0 else -1)

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

    # --- selección

    def take_selection(self):
        try:
            sels = FreeCADGui.Selection.getSelectionEx()
        except Exception:
            sels = []
        changed = False
        for sel in sels:
            for sub in sel.SubElementNames:
                changed = self._pick(sel.Object, sub.split(".")[-1]) or changed
        self.busy = True
        try:
            FreeCADGui.Selection.clearSelection()
        finally:
            self.busy = False
        if changed:
            self._fill_list()
            self.list.setCurrentRow(-1)
            self.preview()

    def _pick(self, obj, sub):
        if self.base is None or not (sub.startswith("Edge") or sub.startswith("Face")):
            return False
        if obj == self.base:
            name = sub
        elif obj == self.obj and self.valid:
            shape = self.obj.Shape
            geo = _element(shape, sub)
            if geo is None:
                return False
            if sub.startswith("Face") and int(sub[4:]) - 1 in self.yellow:
                gone = nearest(geo, self.base.Shape, self.subs)  # cara amarilla: sacar su arista
                if gone is None:
                    return False
                self.subs = [s for s in self.subs if s != gone]
                return True
            name = to_base(shape, sub, self.base.Shape)
            if name is None:
                return False
        else:
            return False
        self.subs = toggle(self.subs, name)
        return True

    def remove_current(self, *_a):
        row = self.list.currentRow()
        if 0 <= row < len(self.subs):
            self.subs = self.subs[:row] + self.subs[row + 1:]
            self._fill_list()
            self.preview()

    def clear(self, *_a):
        self.subs = []
        self._fill_list()
        self.preview()

    # --- vista previa

    def preview(self):
        obj = self.obj
        self.valid = False
        self.yellow = []
        problem = ""
        try:
            if self.base is not None:
                obj.Base = (self.base, self.subs)
            if not self._has_expression("Radius"):
                obj.Radius = self.radius.value()
            if any(self._missing(s) for s in self.subs):
                problem = "Hay referencias que ya no existen (en rojo): borralas y elegí las nuevas."
            elif self.subs:
                obj.recompute()
                self.valid = obj.isValid() and not obj.Shape.isNull()
                if not self.valid:
                    problem = "FreeCAD no puede hacer el redondeo con este radio en estas aristas."
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Redondeo:\n%s\n" % traceback.format_exc())
            problem = "No se pudo calcular la vista previa."
        if self.valid:
            try:
                self.yellow = new_faces(obj.Shape, self.base.Shape)
            except Exception:
                self.yellow = []
        self._show_only(obj if self.valid else self.base)
        self.message.setText(problem)
        self.message.setVisible(bool(problem))
        self._draw()

    def _undraw(self):
        try:
            graph = self.gdoc.ActiveView.getSceneGraph()
        except Exception:
            graph = None
        for node in self.nodes:
            try:
                graph.removeChild(node)
            except Exception:
                pass
        self.nodes = []

    def _draw(self):
        self._undraw()
        try:
            graph = self.gdoc.ActiveView.getSceneGraph()
        except Exception:
            return
        try:
            nodes = []
            base = _global_shape(self.base) if self.base is not None else None
            if self.valid:
                result = _global_shape(self.obj)
                faces = [result.Faces[i] for i in self.yellow if i < len(result.Faces)]
                nodes.append(_faces_node(faces, PREVIEW_COLOR))
            elif base is not None:
                picked = [_element(base, s) for s in self.subs]
                nodes.append(_lines_node([p for p in picked if p is not None], PICKED_COLOR, LINE_WIDTH))
            row = self.list.currentRow()
            if base is not None and 0 <= row < len(self.subs):
                el = _element(base, self.subs[row])
                if el is not None:
                    nodes.append(_lines_node([el], CURRENT_COLOR, LINE_WIDTH + 1))
            for node in nodes:
                graph.addChild(node)
                self.nodes.append(node)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Redondeo (dibujo):\n%s\n" % traceback.format_exc())

    # --- cerrar

    def _close(self):
        self.timer.stop()
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        self._undraw()
        _state["panel"] = None

    def accept(self):
        if self.timer.isActive():
            self.timer.stop()
            self.preview()
        if not self.subs:
            self.message.setText("Elegí al menos una arista o cara.")
            self.message.show()
            return False
        if not self.valid:
            return False  # el mensaje ya dice por qué
        self._close()
        self._restore_visibility()
        self.obj.Visibility = self._tip_or_self()
        self.doc.recompute()
        self.gdoc.resetEdit()
        self.doc.commitTransaction()
        return True

    def _tip_or_self(self):
        """El redondeo queda visible solo si es la punta del cuerpo."""
        from swui.fork import feature_tree as ft

        body = ft.body_of(self.obj)
        return body is None or body.Tip == self.obj

    def reject(self):
        self._close()
        self._restore_visibility()
        # Primero deshacer: resetEdit confirma la transacción abierta (probado en 1.1.4)
        self.doc.abortTransaction()
        if self.gdoc.getInEdit() is not None:
            self.gdoc.resetEdit()
        self.doc.recompute()
        return True


# --- Enganche ----------------------------------------------------------


PANELS = {FILLET: FilletPanel}


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


def _take_over(doc_name, obj_name):
    """Cambiar el diálogo nativo por el panel SW (ya fuera del slotInEdit)."""
    try:
        doc = FreeCAD.getDocument(doc_name)
        obj = doc.getObject(obj_name)
        vp = FreeCADGui.getDocument(doc_name).getInEdit()
        if obj is None or vp is None or vp.Object != obj or _state["panel"] is not None:
            return
        FreeCADGui.Control.closeDialog()
        panel = PANELS[obj.TypeId](obj)
        _state["panel"] = panel
        FreeCADGui.Control.showDialog(panel)
    except Exception:
        _state["panel"] = None
        FreeCAD.Console.PrintError("[SWUI fork] Panel de redondeo:\n%s\n" % traceback.format_exc())
        _native(doc_name, obj_name)


def _native(doc_name, obj_name):
    """Si el panel falla, volver a abrir el diálogo de FreeCAD (mejor eso que nada)."""
    try:
        gdoc = FreeCADGui.getDocument(doc_name)
        obj = FreeCAD.getDocument(doc_name).getObject(obj_name)
        if obj is None or FreeCADGui.Control.activeDialog():
            return
        _state["native"] = True
        gdoc.resetEdit()
        gdoc.setEdit(obj)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Diálogo de redondeo:\n%s\n" % traceback.format_exc())
    finally:
        _state["native"] = False


class _EditObserver:
    def slotInEdit(self, vp):
        try:
            obj = vp.Object
        except Exception:
            return
        if obj.TypeId in PANELS and _state["panel"] is None and not _state["native"] and _in_workbench():
            QtCore.QTimer.singleShot(0, lambda: _take_over(obj.Document.Name, obj.Name))


_observer = None


def install():
    global _observer
    if _observer is None:
        _observer = _EditObserver()
        FreeCADGui.addDocumentObserver(_observer)
