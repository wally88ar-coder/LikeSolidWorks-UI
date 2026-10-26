# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Paneles de Matriz lineal, Matriz circular y Simetría como el PropertyManager de SW 2018.

Mismo enganche que el redondeo (dress_up_panel.py): el comando de FreeCAD crea
la operación nativa (LinearPattern / PolarPattern / Mirrored) y este panel
reemplaza a su diálogo. Como en SW:
- casillas de selección (dirección, eje, plano): la activa se ve rosada; un
  clic en la casilla la activa. Una arista, eje o plano tocado va a la casilla
  activa; una cara plana también (dirección normal / plano de simetría);
- "Operaciones y caras": un clic en una cara de la pieza suma (o saca) la
  operación que la creó; también un clic en una operación del árbol;
- "Sólidos": copiar la pieza entera (TransformMode "Whole shape" de FreeCAD);
- espaciado e instancias (las instancias cuentan el original, como en SW);
- vista previa con las copias en amarillo.

Matriz lineal: SW 2018 usa "Espaciado" entre copias; FreeCAD guarda también
"Longitud total" (Mode Extent). Una matriz vieja en Extent pasa a Spacing con
el mismo resultado, salvo que la longitud tenga ecuación (entonces se respeta).
Matriz circular: "Separación igual" = el ángulo es el total (Extent); sin
tildar, es el ángulo entre copias (Spacing).
FreeCAD 1.1.4 no tiene "Instancias a omitir": no está.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets
from swui.fork import dress_up_panel as dp

LINEAR = "PartDesign::LinearPattern"
POLAR = "PartDesign::PolarPattern"
MIRRORED = "PartDesign::Mirrored"
ACTIVE_QSS = "background: #FCE0F0;"  # casilla de selección activa (rosado, como SW)
REF_TYPES = ("App::Line", "App::Plane", "PartDesign::Line", "PartDesign::Plane")
MAX_COMPARE = 40000  # caras x caras: más que esto, sin amarillo (piezas grandes)


# --- Sin FreeCAD (probables en el test) ---------------------------------


def spacing_from_extent(length, occurrences):
    """Longitud total de FreeCAD -> espaciado entre copias de SW."""
    return length / (occurrences - 1) if occurrences > 1 else length


def sub_name(sub):
    """'Edge4' -> 'Arista', 'Face2' -> 'Cara', 'H_Axis' -> 'eje H'..."""
    if sub.startswith("Edge"):
        return "Arista"
    if sub.startswith("Face"):
        return "Cara"
    return {"H_Axis": "eje H", "V_Axis": "eje V", "N_Axis": "normal"}.get(sub, sub)


# --- Casilla de selección ----------------------------------------------


class _RefBox(QtWidgets.QLineEdit):
    """Casilla de una referencia (dirección, eje, plano): un clic la activa."""

    def __init__(self, on_click):
        super().__init__()
        self.setReadOnly(True)
        self._on_click = on_click

    def mousePressEvent(self, event):
        self._on_click(self)
        super().mousePressEvent(event)


class _ListClick(QtCore.QObject):
    def __init__(self, on_click, widget):
        super().__init__()
        self.on_click = on_click
        self.widget = widget

    def eventFilter(self, _watched, event):
        if event.type() == QtCore.QEvent.MouseButtonPress:
            self.on_click(self.widget)
        return False


# --- Panel común -------------------------------------------------------


class TransformedPanel(dp.SwPanel):
    FAIL = "FreeCAD no puede hacer la operación así: revisá la dirección y las medidas."
    NOTHING = "Elegí al menos una operación (o tildá Sólidos)."
    REFS = ()  # [(propiedad, etiqueta, ayuda)]

    def __init__(self, obj):
        self.originals = list(obj.Originals)
        self.refs = {}
        self.ref_boxes = {}
        self.active = None
        super().__init__(obj)

    # --- interfaz

    def _ref_box(self, prop, label, form, tip):
        box = _RefBox(self._activate)
        box.setToolTip(tip)
        box.setPlaceholderText(tip)
        self.ref_boxes[prop] = box
        try:
            self.refs[prop] = getattr(self.obj, prop)
        except Exception:
            self.refs[prop] = None
        form.addRow(label, box)
        return box

    def _features_box(self):
        box = QtWidgets.QWidget()
        box.setWindowTitle("Operaciones y caras")
        lay = QtWidgets.QVBoxLayout(box)
        lay.addWidget(QtWidgets.QLabel("Clic en una cara de la operación o en el árbol:"))
        self.list = dp.pick_list(self.remove_current, self.clear, 70)
        self.list._swui_click = _ListClick(self._activate, self.list)
        self.list.viewport().installEventFilter(self.list._swui_click)
        lay.addWidget(self.list)
        self.whole = QtWidgets.QCheckBox("Sólidos: repetir toda la pieza")
        self.whole.setChecked(self.obj.TransformMode == "Whole shape")
        self.whole.toggled.connect(self._whole_toggled)
        lay.addWidget(self.whole)
        lay.addWidget(self._message_label())
        return box

    def _whole_toggled(self, *_a):
        self.list.setEnabled(not self.whole.isChecked())
        if not self.whole.isChecked():
            self._activate(self.list)
        self._changed()

    def _activate(self, widget):
        self.active = widget
        for w in list(self.ref_boxes.values()) + [self.list]:
            w.setStyleSheet(ACTIVE_QSS if w is widget else "")

    def _fill(self):
        for prop, box in self.ref_boxes.items():
            box.setText(self._ref_text(self.refs.get(prop)))
        self.list.clear()
        for f in self.originals:
            self.list.addItem(f.Label)
        self.list.setEnabled(not self.whole.isChecked())

    def _ref_text(self, ref):
        if not ref:
            return ""
        obj, subs = ref
        sub = subs[0] if subs else ""
        if obj.TypeId in REF_TYPES or not sub:
            return obj.Label
        return "%s (%s)" % (sub_name(sub), obj.Label)

    def _refresh(self):
        self._fill()

    def _start(self):
        """Al abrir: llenar y activar la primera casilla (como SW)."""
        self._fill()
        first = next(iter(self.ref_boxes.values()), None)
        self._activate(first if first is not None else self.list)

    # --- selección

    def _active_ref(self):
        for prop, box in self.ref_boxes.items():
            if box is self.active:
                return prop
        return None

    def _set_ref(self, prop, ref):
        self.refs[prop] = ref
        # después de la dirección, a "Operaciones" si todavía no hay ninguna (lo siguiente en SW)
        if not self.originals and not self.whole.isChecked():
            self._activate(self.list)
        return True

    def _accepts_face(self, face):
        """¿Esta cara sirve como referencia (dirección/plano)? Las planas sí."""
        try:
            return type(face.Surface).__name__ == "Plane"
        except Exception:
            return False

    def _pick(self, obj, sub):
        from swui.fork import feature_tree as ft

        target = self._active_ref() or (next(iter(self.ref_boxes), None))
        if obj.TypeId in REF_TYPES or (ft.is_sketch(obj) and sub.endswith("_Axis")):
            return self._set_ref(target, (obj, [sub] if sub else [""])) if target else False
        if not sub:
            return self._toggle_feature(obj)
        if obj not in (self.obj, self.base):
            return False
        shape = obj.Shape
        geo = dp._element(shape, sub)
        if geo is None:
            return False
        if sub.startswith("Edge") or (sub.startswith("Face") and self._active_ref() and self._accepts_face(geo)):
            if not target:
                return False
            if obj == self.obj:  # no apoyarse en la propia matriz: la misma arista en el sólido anterior
                name = dp.to_base(shape, sub, self.base.Shape) if self.base is not None else None
                if name is None:
                    return False
                return self._set_ref(target, (self.base, [name]))
            return self._set_ref(target, (obj, [sub]))
        if sub.startswith("Face"):
            maker = ft.creator(obj, geo)
            return self._toggle_feature(maker)
        return False

    def _toggle_feature(self, feature):
        from swui.fork import feature_tree as ft

        if feature is None or feature == self.obj or not ft.is_feature(feature):
            return False
        body = ft.body_of(self.obj)
        feats = ft.features(body) if body is not None else []
        if feature not in feats or feats.index(feature) > feats.index(self.obj):
            return False
        self.originals = [f for f in self.originals if f != feature] if feature in self.originals \
            else self.originals + [feature]
        if self.whole.isChecked() and self.originals:
            self.whole.blockSignals(True)
            self.whole.setChecked(False)
            self.whole.blockSignals(False)
        return True

    def remove_current(self, *_a):
        row = self.list.currentRow()
        if 0 <= row < len(self.originals):
            self.originals = self.originals[:row] + self.originals[row + 1:]
            self._fill()
            self.preview()

    def clear(self, *_a):
        self.originals = []
        self._fill()
        self.preview()

    # --- vista previa

    def _apply(self):
        whole = self.whole.isChecked()
        self._set("TransformMode", "Whole shape" if whole else "Features")
        if not whole and list(self.obj.Originals) != self.originals:
            self.obj.Originals = self.originals
        for prop, ref in self.refs.items():
            if prop in self._unused_refs():
                continue
            if ref and getattr(self.obj, prop) != ref:
                setattr(self.obj, prop, ref)
        self._apply_values()
        return ""

    def _apply_values(self):
        pass

    def _unused_refs(self):
        return ()

    def _ready(self):
        return self.whole.isChecked() or bool(self.originals)

    def _nothing(self):
        return not self._ready()

    def _new_faces(self):
        from swui.fork import feature_tree as ft

        old = self.base.Shape.Faces
        new = self.obj.Shape.Faces
        if len(old) * len(new) > MAX_COMPARE:
            return []
        def shared(f, g):  # ¿la cara nueva pisa la vieja? (la tapa con agujeros nuevos: sí)
            try:
                return f.common(g).Area > 1e-6
            except Exception:
                return ft._overlap(f, g)

        return [i for i, f in enumerate(new) if not any(ft.same_surface(f, g) and shared(f, g) for g in old)]

    def _overlays(self, base, result):
        nodes = super()._overlays(base, result)
        shapes = []
        for ref in self.refs.values():
            if not ref or not ref[1] or not ref[1][0].startswith(("Edge", "Face")):
                continue
            try:
                el = dp._global_shape(ref[0]).getElement(ref[1][0])
            except Exception:
                continue
            shapes.append(el)
        if shapes:
            nodes.append(dp._lines_node(shapes, dp.PICKED_COLOR, dp.LINE_WIDTH))
        return nodes


# --- Matriz lineal -----------------------------------------------------


class LinearPanel(TransformedPanel):
    TRANSACTION = "Editar matriz lineal"

    def _build(self):
        obj = self.obj
        self.extent = obj.Mode == "Extent" and self._has_expression("Length")
        boxes = []
        for n, suffix in ((1, ""), (2, "2")):
            box = QtWidgets.QWidget()
            box.setWindowTitle("Dirección %d" % n)
            form = QtWidgets.QFormLayout(box)
            if n == 2:
                self.use2 = QtWidgets.QCheckBox("Usar dirección 2")
                self.use2.setChecked(obj.Occurrences2 > 1)
                self.use2.toggled.connect(self._changed)
                form.addRow(self.use2)
            self._ref_box("Direction" + suffix, "Dirección:", form, "Arista, eje o cara plana")
            flip = QtWidgets.QCheckBox("Invertir dirección")
            flip.setChecked(bool(getattr(obj, "Reversed" + suffix)))
            flip.toggled.connect(self._changed)
            form.addRow(flip)
            occ = getattr(obj, "Occurrences" + suffix)
            if n == 1 and self.extent:
                dist = self._value_box("Length", " mm", 0.001, 1e6)
                label = "Longitud total:"
            else:
                value = getattr(obj, "Offset" + suffix).Value
                if getattr(obj, "Mode" + suffix) == "Extent":
                    value = spacing_from_extent(getattr(obj, "Length" + suffix).Value, occ)
                dist = self._value_box("Offset" + suffix, " mm", 0.001, 1e6, value)
                label = "Espaciado:"
            form.addRow(label, dist)
            count = QtWidgets.QSpinBox()
            count.setRange(1 if n == 2 else 2, 10000)
            count.setValue(max(occ, 2) if n == 2 and occ < 2 else occ)
            count.setKeyboardTracking(False)
            if self._has_expression("Occurrences" + suffix):
                count.setEnabled(False)
            count.valueChanged.connect(self._changed)
            form.addRow("Instancias:", count)
            setattr(self, "flip%d" % n, flip)
            setattr(self, "dist%d" % n, dist)
            setattr(self, "count%d" % n, count)
            boxes.append(box)
        self.form = boxes + [self._features_box()]
        self._start()
        self._show_dir2()

    def _show_dir2(self):
        on = self.use2.isChecked()
        for w in (self.ref_boxes["Direction2"], self.flip2, self.dist2, self.count2):
            w.setEnabled(on)

    def _changed(self, *_a):
        self._show_dir2()
        super()._changed()

    def _unused_refs(self):
        return () if self.use2.isChecked() else ("Direction2",)  # apagada: no se toca

    def _apply(self):
        problem = super()._apply()
        if not problem and self.use2.isChecked() and not self.refs.get("Direction2"):
            problem = "Elegí la dirección 2 (una arista, eje o cara plana)."
        return problem

    def _apply_values(self):
        self._set("Reversed", self.flip1.isChecked())
        if self.extent:
            self._set("Length", self.dist1.value())
        else:
            self._set("Mode", "Spacing")
            self._set("Offset", self.dist1.value())
        self._set("Occurrences", self.count1.value())
        if self.use2.isChecked():
            self._set("Reversed2", self.flip2.isChecked())
            self._set("Mode2", "Spacing")
            self._set("Offset2", self.dist2.value())
            self._set("Occurrences2", self.count2.value())
        else:
            self._set("Occurrences2", 1)


# --- Matriz circular ---------------------------------------------------


class PolarPanel(TransformedPanel):
    TRANSACTION = "Editar matriz circular"

    def _accepts_face(self, face):
        return False  # FreeCAD pide una arista; la cara cilíndrica se cambia por su borde (_pick)

    def _pick(self, obj, sub):
        # Cara cilíndrica = su eje (eje temporal de SW): FreeCAD quiere una arista,
        # se usa un borde circular de la cara, que tiene el mismo eje.
        if sub.startswith("Face") and self._active_ref() == "Axis" and obj in (self.obj, self.base):
            shape = obj.Shape
            face = dp._element(shape, sub)
            try:
                round_face = type(face.Surface).__name__ in ("Cylinder", "Cone")
            except Exception:
                round_face = False
            if round_face:
                for edge in face.Edges:
                    if type(getattr(edge, "Curve", None)).__name__ == "Circle":
                        for i, cand in enumerate(shape.Edges):
                            if cand.isSame(edge):
                                return super()._pick(obj, "Edge%d" % (i + 1))
        return super()._pick(obj, sub)

    def _build(self):
        obj = self.obj
        box = QtWidgets.QWidget()
        box.setWindowTitle("Parámetros")
        form = QtWidgets.QFormLayout(box)
        self._ref_box("Axis", "Eje:", form, "Eje, arista recta o circular, o cara cilíndrica")
        self.flip = QtWidgets.QCheckBox("Invertir dirección")
        self.flip.setChecked(bool(obj.Reversed))
        self.flip.toggled.connect(self._changed)
        form.addRow(self.flip)
        self.equal = QtWidgets.QCheckBox("Separación igual")
        self.equal.setChecked(obj.Mode == "Extent")
        self.equal.toggled.connect(self._changed)
        form.addRow(self.equal)
        value = obj.Angle.Value if obj.Mode == "Extent" else obj.Offset.Value
        self.angle = dp._spin(value, "°", 0.01, 360.0)
        self.angle.valueChanged.connect(self._changed)
        if self._has_expression("Angle" if obj.Mode == "Extent" else "Offset"):
            self.angle.setEnabled(False)
        self.angle_label = QtWidgets.QLabel()
        form.addRow(self.angle_label, self.angle)
        self.count = QtWidgets.QSpinBox()
        self.count.setRange(2, 10000)
        self.count.setValue(max(obj.Occurrences, 2))
        self.count.setKeyboardTracking(False)
        if self._has_expression("Occurrences"):
            self.count.setEnabled(False)
        self.count.valueChanged.connect(self._changed)
        form.addRow("Instancias:", self.count)
        self._label()
        self.form = [box, self._features_box()]
        self._start()

    def _label(self):
        self.angle_label.setText("Ángulo total:" if self.equal.isChecked() else "Ángulo entre copias:")

    def _changed(self, *_a):
        self._label()  # como SW: el número queda, cambia qué significa
        super()._changed()

    def _apply_values(self):
        self._set("Reversed", self.flip.isChecked())
        if self.equal.isChecked():
            self._set("Mode", "Extent")
            self._set("Angle", self.angle.value())
        else:
            self._set("Mode", "Spacing")
            self._set("Offset", self.angle.value())
        self._set("Occurrences", self.count.value())


# --- Simetría ----------------------------------------------------------


class MirrorPanel(TransformedPanel):
    TRANSACTION = "Editar simetría"
    FAIL = "FreeCAD no puede hacer la simetría así: revisá el plano."

    def _build(self):
        box = QtWidgets.QWidget()
        box.setWindowTitle("Cara/Plano de simetría")
        form = QtWidgets.QFormLayout(box)
        self._ref_box("MirrorPlane", "Plano:", form, "Plano o cara plana")
        self.form = [box, self._features_box()]
        self._start()

    def _pick(self, obj, sub):
        # una arista no define un plano de simetría
        if sub.startswith("Edge"):
            return False
        return super()._pick(obj, sub)


def install():
    dp.PANELS.update({LINEAR: LinearPanel, POLAR: PolarPanel, MIRRORED: MirrorPanel})
