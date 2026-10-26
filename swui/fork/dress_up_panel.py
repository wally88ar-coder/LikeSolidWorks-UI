# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Paneles de Redondeo y Chaflán como el PropertyManager de SOLIDWORKS 2018.

Chaflán: "Ángulo-distancia" o "Distancia-distancia" (con "Distancia igual"),
"Invertir dirección"; por debajo el ChamferType de FreeCAD. Lo que sigue vale
para los dos (el texto habla del redondeo).

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
CHAMFER = "PartDesign::Chamfer"
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
    """Toda selección (vista o árbol) mientras el panel está abierto va al panel."""

    def __init__(self, panel):
        self.panel = panel

    def addSelection(self, _doc, _obj, _sub, _pnt):
        if not self.panel.busy:
            QtCore.QTimer.singleShot(0, self.panel.take_selection)


class _ListKeys(QtCore.QObject):
    """Supr en una lista borra el renglón (le gana al Supr de FreeCAD, que borraría objetos)."""

    def __init__(self, remove):
        super().__init__()
        self.remove = remove

    def eventFilter(self, _watched, event):
        kind = event.type()
        if kind in (QtCore.QEvent.ShortcutOverride, QtCore.QEvent.KeyPress) and \
                event.key() in (QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace):
            event.accept()
            if kind == QtCore.QEvent.KeyPress:
                self.remove()
            return True
        return False


def _spin(value, suffix, low, high, decimals=2):
    box = QtWidgets.QDoubleSpinBox()
    box.setDecimals(decimals)
    box.setRange(low, high)
    box.setSuffix(suffix)
    box.setValue(value)
    box.setKeyboardTracking(False)
    return box


def pick_list(remove, clear, height=90):
    """Lista de selección con Supr y clic derecho Borrar / Borrar selecciones (como SW)."""
    widget = QtWidgets.QListWidget()
    widget.setMinimumHeight(height)
    widget.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
    act = QAction("Borrar", widget)
    act.triggered.connect(lambda *_a: remove())
    widget.addAction(act)
    act = QAction("Borrar selecciones", widget)
    act.triggered.connect(lambda *_a: clear())
    widget.addAction(act)
    widget._swui_keys = _ListKeys(remove)  # que no se lo lleve el recolector
    widget.installEventFilter(widget._swui_keys)
    return widget


class SwPanel:
    """
    Lo común a los paneles SW sobre una operación nativa ya puesta en edición:
    transacción, qué se ve (la operación si sale bien, si no el sólido anterior),
    selección siempre activa, vista previa demorada, Aceptar / Cancelar.
    Cada panel define _build (self.form), _apply (pasa los valores al objeto y
    devuelve un problema o ""), _pick(obj, sub) y, si quiere, _overlays.
    """

    TRANSACTION = ""
    FAIL = ""
    NOTHING = ""  # mensaje si se acepta sin haber elegido nada

    def __init__(self, obj):
        self.obj = obj
        self.doc = obj.Document
        self.gdoc = FreeCADGui.getDocument(self.doc.Name)
        self.busy = False
        self.valid = False
        self.nodes = []
        self.yellow = []
        self.base = self._base()
        self.visible = self._remember_visibility()
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.preview)
        self._build()
        if not self.doc.HasPendingTransaction:
            self.doc.openTransaction(self.TRANSACTION)
        self.observer = _PickObserver(self)
        FreeCADGui.Selection.addObserver(self.observer)
        FreeCADGui.Selection.clearSelection()
        self.preview()

    def _base(self):
        return self.obj.BaseFeature

    # --- qué se ve

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

    # --- interfaz (ayudas)

    def _message_label(self):
        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: %s;" % MISSING_COLOR)
        self.message.hide()
        return self.message

    def _has_expression(self, prop):
        try:
            return any(path == prop for path, _e in self.obj.ExpressionEngine)
        except Exception:
            return False

    def _value_box(self, prop, suffix, low, high, value=None):
        """Casilla para una propiedad del objeto; bloqueada si la controla una ecuación."""
        box = _spin(getattr(self.obj, prop).Value if value is None else value, suffix, low, high)
        if self._has_expression(prop):
            box.setEnabled(False)
            box.setToolTip("Controlado por una ecuación")
        box.valueChanged.connect(self._changed)
        return box

    def _set(self, prop, value):
        """Poner un valor (sin pisar una ecuación ni tocar lo que no cambió)."""
        if self._has_expression(prop):
            return
        old = getattr(self.obj, prop)
        old = getattr(old, "Value", old)
        if isinstance(value, float) and isinstance(old, (int, float)):
            if abs(old - value) <= 1e-9:
                return
        elif old == value:
            return
        setattr(self.obj, prop, value)

    def _changed(self, *_a):
        self.timer.start(PREVIEW_DELAY_MS)

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
            subs = [s.split(".")[-1] for s in sel.SubElementNames] or [""]
            for sub in subs:
                try:
                    changed = self._pick(sel.Object, sub) or changed
                except Exception:
                    FreeCAD.Console.PrintError("[SWUI fork] Selección:\n%s\n" % traceback.format_exc())
        self.busy = True
        try:
            FreeCADGui.Selection.clearSelection()
        finally:
            self.busy = False
        if changed:
            self._refresh()
            self.preview()

    def _pick(self, obj, sub):
        return False

    def _refresh(self):
        pass

    # --- vista previa

    def _apply(self):
        return ""

    def _ready(self):
        return True

    def _new_faces(self):
        return new_faces(self.obj.Shape, self.base.Shape)

    def preview(self):
        self.timer.stop()
        obj = self.obj
        self.valid = False
        self.yellow = []
        problem = ""
        try:
            problem = self._apply()
            if not problem and self._ready():
                obj.recompute()
                self.valid = obj.isValid() and not obj.Shape.isNull()
                if not self.valid:
                    problem = self.FAIL
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (self.TRANSACTION, traceback.format_exc()))
            problem = "No se pudo calcular la vista previa."
        if self.valid and self.base is not None:
            try:
                self.yellow = self._new_faces()
            except Exception:
                self.yellow = []
        self._show_only(obj if self.valid or self.base is None else self.base)
        self.message.setText(problem)
        self.message.setVisible(bool(problem))
        self._draw()

    def _overlays(self, base, result):
        """Nodos a dibujar: por defecto las caras nuevas en amarillo."""
        if result is None:
            return []
        return [_faces_node([result.Faces[i] for i in self.yellow if i < len(result.Faces)], PREVIEW_COLOR)]

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
            base = _global_shape(self.base) if self.base is not None else None
            result = _global_shape(self.obj) if self.valid else None
            for node in self._overlays(base, result):
                graph.addChild(node)
                self.nodes.append(node)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Vista previa:\n%s\n" % traceback.format_exc())

    # --- cerrar

    def _close(self):
        self.timer.stop()
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        self._undraw()
        _restore_native_preview(getattr(self, "old_preview", None))
        _state["panel"] = None

    def _nothing(self):
        return False

    def accept(self):
        if self.timer.isActive():
            self.preview()
        if self._nothing():
            self.message.setText(self.NOTHING)
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
        """La operación queda visible solo si es la punta del cuerpo."""
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


class DressUpPanel(SwPanel):
    """Lo común de Redondeo y Chaflán; cada uno agrega sus valores (_build_values / _apply_values)."""

    TITLE = ""
    NOTHING = "Elegí al menos una arista o cara."

    def __init__(self, obj):
        self.subs = []
        super().__init__(obj)

    def _base(self):
        base = self.obj.BaseFeature or (self.obj.Base[0] if self.obj.Base else None)
        self.subs = self._initial_subs(base)
        return base

    def _initial_subs(self, base):
        try:
            owner, subs = self.obj.Base
        except Exception:
            return []
        subs = list(subs)
        if owner is not None and base is not None and owner != base:
            # FreeCAD a veces apoya el redondeo en la operación de la arista tocada,
            # no en el sólido anterior: pasar los nombres al sólido anterior.
            moved = []
            for sub in subs:
                name = to_base(owner.Shape, sub, base.Shape)
                if name and name not in moved:
                    moved.append(name)
            subs = moved
        return subs

    def _missing(self, sub):
        return self.base is None or _element(self.base.Shape, sub) is None

    # --- interfaz

    def _build(self):
        box = QtWidgets.QWidget()
        box.setWindowTitle(self.TITLE)
        lay = QtWidgets.QVBoxLayout(box)
        self.values = QtWidgets.QFormLayout()
        self._build_values(self.values)
        lay.addLayout(self.values)

        lay.addWidget(QtWidgets.QLabel("Aristas y caras (clic en la pieza):"))
        self.list = pick_list(self.remove_current, self.clear)
        self.list.currentRowChanged.connect(lambda *_a: self._draw())
        lay.addWidget(self.list)

        self.tangent = QtWidgets.QCheckBox("Propagación tangente")
        self.tangent.setChecked(True)
        self.tangent.setEnabled(False)
        self.tangent.setToolTip("FreeCAD siempre sigue las aristas tangentes")
        lay.addWidget(self.tangent)
        lay.addWidget(self._message_label())
        self.form = box
        self._fill_list()

    def _build_values(self, form):
        pass

    def _apply_values(self):
        pass

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

    def _refresh(self):
        self._fill_list()
        self.list.setCurrentRow(-1)

    # --- selección

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

    def _apply(self):
        if self.base is not None:
            self.obj.Base = (self.base, self.subs)
        self._apply_values()
        if any(self._missing(s) for s in self.subs):
            return "Hay referencias que ya no existen (en rojo): borralas y elegí las nuevas."
        return ""

    def _ready(self):
        return bool(self.subs)

    def _nothing(self):
        return not self.subs

    def _overlays(self, base, result):
        nodes = super()._overlays(base, result)
        if result is None and base is not None:
            picked = [_element(base, s) for s in self.subs]
            nodes.append(_lines_node([p for p in picked if p is not None], PICKED_COLOR, LINE_WIDTH))
        row = self.list.currentRow()
        if base is not None and 0 <= row < len(self.subs):
            el = _element(base, self.subs[row])
            if el is not None:
                nodes.append(_lines_node([el], CURRENT_COLOR, LINE_WIDTH + 1))
        return nodes


class FilletPanel(DressUpPanel):
    TITLE = "Elementos a redondear"
    TRANSACTION = "Editar redondeo"
    FAIL = "FreeCAD no puede hacer el redondeo con este radio en estas aristas."

    def _build_values(self, form):
        self.radius = self._value_box("Radius", " mm", 0.01, 100000.0)
        form.addRow("Radio:", self.radius)

    def _apply_values(self):
        self._set("Radius", self.radius.value())


# Tipos de chaflán de SW -> ChamferType de FreeCAD (los nombres internos de 1.1.4)
EQUAL, TWO, ANGLE = "Equal distance", "Two distances", "Distance and Angle"


def chamfer_type(angle_distance, equal):
    """Opciones del panel SW -> ChamferType de FreeCAD."""
    if angle_distance:
        return ANGLE
    return EQUAL if equal else TWO


class ChamferPanel(DressUpPanel):
    TITLE = "Parámetros del chaflán"
    TRANSACTION = "Editar chaflán"
    FAIL = "FreeCAD no puede hacer el chaflán con estas medidas en estas aristas."

    def _build_values(self, form):
        kind = self.obj.ChamferType
        self.by_angle = QtWidgets.QRadioButton("Ángulo-distancia")
        self.by_dist = QtWidgets.QRadioButton("Distancia-distancia")
        (self.by_angle if kind == ANGLE else self.by_dist).setChecked(True)
        types = QtWidgets.QVBoxLayout()
        types.addWidget(self.by_angle)
        types.addWidget(self.by_dist)
        form.addRow(types)
        self.flip = QtWidgets.QCheckBox("Invertir dirección")
        self.flip.setChecked(bool(self.obj.FlipDirection))
        form.addRow(self.flip)
        self.equal = QtWidgets.QCheckBox("Distancia igual")
        self.equal.setChecked(kind == EQUAL)
        form.addRow(self.equal)
        self.size = self._value_box("Size", " mm", 0.01, 100000.0)
        self.size2 = self._value_box("Size2", " mm", 0.01, 100000.0)
        self.angle = self._value_box("Angle", "°", 0.1, 179.9)
        self.size_label = QtWidgets.QLabel("Distancia:")
        self.size2_label = QtWidgets.QLabel("Distancia 2:")
        self.angle_label = QtWidgets.QLabel("Ángulo:")
        form.addRow(self.size_label, self.size)
        form.addRow(self.size2_label, self.size2)
        form.addRow(self.angle_label, self.angle)
        for w in (self.by_angle, self.by_dist, self.flip, self.equal):
            w.toggled.connect(self._changed)
        self._update_rows()

    def _update_rows(self):
        angle = self.by_angle.isChecked()
        two = not angle and not self.equal.isChecked()
        self.equal.setVisible(not angle)
        self.flip.setVisible(angle or two)  # con distancias iguales no cambia nada
        self.size_label.setText("Distancia:" if angle or not two else "Distancia 1:")
        for w in (self.size2, self.size2_label):
            w.setVisible(two)
        for w in (self.angle, self.angle_label):
            w.setVisible(angle)

    def _changed(self, *_a):
        self._update_rows()
        super()._changed()

    def _apply_values(self):
        self._set("ChamferType", chamfer_type(self.by_angle.isChecked(), self.equal.isChecked()))
        self._set("FlipDirection", self.flip.isChecked())
        self._set("Size", self.size.value())
        self._set("Size2", self.size2.value())
        self._set("Angle", self.angle.value())


# --- Enganche ----------------------------------------------------------


PANELS = {FILLET: FilletPanel, CHAMFER: ChamferPanel}  # pattern_panel.py suma los suyos


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
        old_preview = _hide_native_preview()
        FreeCADGui.Control.closeDialog()
        panel = PANELS[obj.TypeId](obj)
        panel.old_preview = old_preview
        _state["panel"] = panel
        FreeCADGui.Control.showDialog(panel)
    except Exception:
        _state["panel"] = None
        FreeCAD.Console.PrintError("[SWUI fork] Panel de operación:\n%s\n" % traceback.format_exc())
        _native(doc_name, obj_name)


PREVIEW_PARAM = "User parameter:BaseApp/Preferences/Mod/PartDesign/Preview"


def _hide_native_preview():
    """
    Apagar la "vista previa superpuesta" de FreeCAD (herramientas en magenta
    transparente; con un corte Por todo, columnas que tapan la pieza): se apaga
    con la casilla de su diálogo, todavía abierto. Devuelve la preferencia vieja
    para devolverla al cerrar (_restore_native_preview).
    """
    try:
        old = FreeCAD.ParamGet(PREVIEW_PARAM).GetBool("ShowTransparentPreview", True)
    except Exception:
        return None
    try:
        for box in FreeCADGui.getMainWindow().findChildren(QtWidgets.QCheckBox, "showTransparentPreviewCheckBox"):
            if box.isChecked():
                box.setChecked(False)
    except Exception:
        pass
    return old


def _restore_native_preview(old):
    if old is not None:
        try:
            FreeCAD.ParamGet(PREVIEW_PARAM).SetBool("ShowTransparentPreview", old)
        except Exception:
            pass


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
        FreeCAD.Console.PrintError("[SWUI fork] Diálogo de FreeCAD:\n%s\n" % traceback.format_exc())
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
