# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Chapa (fase 1): paneles SW de Brida base y Brida de arista, Aplanar y Exportar DXF.

Por debajo, los objetos de SheetMetal (ver sheet_metal.py). Flujo como SW:
- Brida base: con un croquis abierto, lo cierra y arma la brida (from_sketch); sin nada
  elegido, primero elegir plano o cara (pick_plane) y al salir del croquis se arma. Panel:
  Dirección 1 (solo perfil abierto), Parámetros de chapa (espesor, invertir, radio) y
  Margen de pliegue (factor K).
- Brida de arista: lista de aristas siempre esperando el clic, ángulo, longitud (exterior
  virtual / interior virtual / tangente), posición de brida y radio predeterminado.
- Editar una brida (clic derecho > Editar operación) abre el mismo panel en lugar del de
  SheetMetal (dress_up_panel.CHOOSERS; SheetMetal la pone en edición y abre su transacción).
- Aplanar muestra el desarrollo y oculta la chapa plegada (otro clic vuelve); Exportar DXF lo
  guarda con un clic al lado del archivo de la pieza, con nombre pieza_espesor_material.
"""

import os
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets
from swui.fork import dress_up_panel as dp
from swui.fork import sheet_metal as sm

BASE_COMMAND = "SWUI_SMBaseFlange"
EDGE_COMMAND = "SWUI_SMEdgeFlange"
HEM_COMMAND = "SWUI_SMHem"
CUT_COMMAND = "SWUI_SMCut"
CONVERT_COMMAND = "SWUI_SMConvert"
FLAT_COMMAND = "SWUI_SMFlatten"
DXF_COMMAND = "SWUI_SMExportDXF"
TITLE = "Chapa"

# (texto SW, valor de SheetMetal) - comprobado sin GUI: placa de 50, brida de 30, espesor 2, radio 2
LENGTH_SPECS = (("Exterior virtual", "Outer Sharp"), ("Interior virtual", "Inner Sharp"),
                ("Tangente al pliegue", "Tangential"))
POSITIONS = (("Material interior", "Material Inside"),  # cara de afuera de la brida en la arista (y 50)
             ("Material exterior", "Thickness Outside"),  # cara de adentro en la arista (y 52)
             ("Pliegue exterior", "Material Outside"))  # el pliegue arranca en la arista (y 54)


def _mw():
    return FreeCADGui.getMainWindow()


def _info(text):
    QtWidgets.QMessageBox.information(_mw(), TITLE, text)


def _icon(form, name):
    from swui import paths

    path = paths.icon(name)
    if path:
        form.setWindowIcon(QtGui.QIcon(path))


def _choice(options, current, on_pick):
    """Lista desplegable (en SW son botones con ícono: así entra en una pantalla de 768)."""
    combo = QtWidgets.QComboBox()
    for text, value in options:
        combo.addItem(text, value)
    values = [v for _t, v in options]
    if current in values:
        combo.setCurrentIndex(values.index(current))
    else:
        combo.setCurrentIndex(-1)  # valor de SheetMetal sin equivalente en SW: no se toca
    combo.currentIndexChanged.connect(lambda i: on_pick(values[i]) if 0 <= i < len(values) else None)
    return combo


def _leave_native_edit(obj):
    """SheetMetal pone la operación en edición (y abre su transacción): salir sin cerrar la transacción."""
    gdoc = FreeCADGui.getDocument(obj.Document.Name)
    if gdoc.getInEdit() is not None:
        gdoc.resetEdit()


def _is_closed(sketch):
    try:
        wires = sketch.Shape.Wires
        return bool(wires) and all(w.isClosed() for w in wires)
    except Exception:
        return False


# --- Brida base --------------------------------------------------------------


class BaseFlangePanel(dp.SwPanel):
    TRANSACTION = "Brida base"
    FAIL = ("SheetMetal no pudo armar la brida con este croquis: el perfil tiene que ser un contorno "
            "cerrado o una sola línea abierta (sin cruces).")

    def __init__(self, obj):
        _leave_native_edit(obj)
        sm.ensure_k(obj)
        super().__init__(obj)

    def _base(self):
        return None

    def _build(self):
        obj = self.obj
        self.closed = _is_closed(obj.BendSketch)
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(obj.Label)
        _icon(self.form, "fork/sm_base_flange")
        box = QtWidgets.QVBoxLayout(self.form)

        d1 = QtWidgets.QGroupBox("Dirección 1")
        f1 = QtWidgets.QFormLayout(d1)
        self.length = self._value_box("Length", " mm", 0.01, 100000.0)
        self.reverse = QtWidgets.QCheckBox("Invertir dirección")
        self.reverse.setChecked(bool(obj.Reverse) and not self.closed)
        self.reverse.toggled.connect(self._changed)
        self.mid = QtWidgets.QCheckBox("Plano medio")
        self.mid.setChecked(bool(obj.MidPlane))
        self.mid.toggled.connect(self._changed)
        f1.addRow("Profundidad:", self.length)
        f1.addRow(self.reverse)
        f1.addRow(self.mid)
        d1.setVisible(not self.closed)  # contorno cerrado: una placa, sin profundidad
        box.addWidget(d1)

        pg = QtWidgets.QGroupBox("Parámetros de chapa")
        fp = QtWidgets.QFormLayout(pg)
        self.thick = self._value_box("Thickness", " mm", 0.01, 1000.0)
        self.flip = QtWidgets.QCheckBox("Invertir dirección")
        self.flip.setToolTip("Lado del croquis hacia el que va el espesor")
        self.flip.setChecked(bool(obj.Reverse) if self.closed else obj.BendSide == "Outside")
        self.flip.toggled.connect(self._changed)
        self.tied = QtWidgets.QCheckBox("Radio = espesor")
        self.tied.setChecked(dict(obj.ExpressionEngine).get("Radius") == "Thickness")
        self.tied.toggled.connect(self._tie)
        self.radius = dp._spin(obj.Radius.Value, " mm", 0.0, 1000.0)
        self.radius.setEnabled(not self.tied.isChecked())
        self.radius.valueChanged.connect(self._changed)
        fp.addRow("Espesor:", self.thick)
        fp.addRow(self.flip)
        fp.addRow(self.tied)
        fp.addRow("Radio de plegado:", self.radius)
        box.addWidget(pg)

        kg = QtWidgets.QGroupBox("Margen de pliegue")
        fk = QtWidgets.QFormLayout(kg)
        self.k = dp._spin(sm.k_factor(obj), "", 0.0, 1.0, decimals=3)
        self.k.setSingleStep(0.01)
        self.k.valueChanged.connect(self._changed)
        fk.addRow("Factor K:", self.k)
        box.addWidget(kg)
        box.addWidget(self._message_label())
        box.addStretch(1)

    def _tie(self, on):
        self.radius.setEnabled(not on)
        self._changed()

    def _apply(self):
        obj = self.obj
        self._set("Thickness", self.thick.value())
        if self.closed:
            self._set("Reverse", self.flip.isChecked())
        else:
            self._set("Length", self.length.value())
            self._set("Reverse", self.reverse.isChecked())
            self._set("MidPlane", self.mid.isChecked())
            self._set("BendSide", "Outside" if self.flip.isChecked() else "Inside")
        expr = dict(obj.ExpressionEngine).get("Radius")
        if self.tied.isChecked():
            if expr != "Thickness":
                obj.setExpression("Radius", "Thickness")
            self.radius.blockSignals(True)
            self.radius.setValue(self.thick.value())
            self.radius.blockSignals(False)
        else:
            if expr is not None:
                obj.setExpression("Radius", None)
            self._set("Radius", self.radius.value())
        if abs(sm.k_factor(obj) - self.k.value()) > 1e-9:
            setattr(obj, sm.K_PROP, self.k.value())
        return ""

    def accept(self):
        ok = super().accept()
        if ok:
            sm.remember("Thickness", self.thick.value())
            if not self.closed:
                sm.remember("BaseLength", self.length.value())
        return ok


# --- Brida de arista -----------------------------------------------------------


class EdgeFlangePanel(dp.SwPanel):
    TRANSACTION = "Brida de arista"
    FAIL = ("SheetMetal no pudo armar la brida así: probá con otra longitud, otro ángulo o "
            "Invertir dirección.")
    NOTHING = "Elegí al menos una arista de la chapa."

    def __init__(self, obj):
        _leave_native_edit(obj)
        link = obj.baseObject
        self.edges = [s for s in (link[1] if link else []) if s]
        self.spec_value = getattr(obj, "LengthSpec", None)  # el dobladillo no tiene
        self.position = obj.BendType
        super().__init__(obj)

    def _base(self):
        link = self.obj.baseObject
        return link[0] if link and link[0] is not None else self.obj.BaseFeature

    def _sheet_base(self):
        body = sm.body_of(self.obj)
        return sm.sheet_base(body) if body is not None else None

    def _build(self):
        obj = self.obj
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(obj.Label)
        _icon(self.form, "fork/sm_edge_flange")
        box = QtWidgets.QVBoxLayout(self.form)

        pg = QtWidgets.QGroupBox("Parámetros de brida")
        pl = QtWidgets.QVBoxLayout(pg)
        pl.addWidget(QtWidgets.QLabel("Aristas (clic en la chapa):"))
        self.list = dp.pick_list(self.remove_current, self.clear, height=50)
        self.list.setMaximumHeight(70)  # que entre todo en una pantalla de 768
        self.list.currentRowChanged.connect(lambda *_a: self._draw())
        self.list.setStyleSheet("QListWidget { %s }" % dp.ACTIVE_QSS)
        pl.addWidget(self.list)
        base = self._sheet_base()
        self.tied = QtWidgets.QCheckBox("Usar radio predeterminado")
        self.tied.setChecked(base is not None and
                             dict(obj.ExpressionEngine).get("radius") == "%s.Radius" % base.Name)
        self.tied.setEnabled(base is not None)
        self.tied.toggled.connect(self._tie)
        pl.addWidget(self.tied)
        rl = QtWidgets.QFormLayout()
        self.radius = dp._spin(obj.radius.Value, " mm", 0.0, 1000.0)
        self.radius.setEnabled(not self.tied.isChecked())
        self.radius.valueChanged.connect(self._changed)
        rl.addRow("Radio de plegado:", self.radius)
        self.angle = self._value_box("angle", "°", 0.01, 180.0)
        rl.addRow("Ángulo:", self.angle)  # en SW va en un recuadro aparte: acá no entraba en 768
        pl.addLayout(rl)
        box.addWidget(pg)

        lg = QtWidgets.QGroupBox("Longitud de brida")
        lf = QtWidgets.QFormLayout(lg)
        self.invert = QtWidgets.QCheckBox("Invertir dirección")
        self.invert.setChecked(bool(obj.invert))
        self.invert.toggled.connect(self._changed)
        lf.addRow(self.invert)
        self.length = self._value_box("length", " mm", 0.01, 100000.0)
        lf.addRow("Longitud:", self.length)
        self.spec_box = _choice(LENGTH_SPECS, self.spec_value, self._spec)
        lf.addRow("Medida hasta:", self.spec_box)
        box.addWidget(lg)

        og = QtWidgets.QGroupBox("Posición de brida")
        of = QtWidgets.QFormLayout(og)
        self.pos_box = _choice(POSITIONS, self.position, self._position)
        of.addRow(self.pos_box)
        box.addWidget(og)
        box.addWidget(self._message_label())
        box.addStretch(1)
        self._refresh()

    def _tie(self, on):
        self.radius.setEnabled(not on)
        self._changed()

    def _spec(self, value):
        self.spec_value = value
        self._changed()

    def _position(self, value):
        self.position = value
        self._changed()

    def _refresh(self):
        row = self.list.currentRow()
        self.list.clear()
        for sub, text in zip(self.edges, dp.sw_names(self.edges)):
            item = QtWidgets.QListWidgetItem(text)
            if self.base is None or dp._element(self.base.Shape, sub) is None:
                item.setText(text + "  (no se encuentra: borrala y elegí otra)")
                item.setForeground(QtGui.QBrush(QtGui.QColor(dp.MISSING_COLOR)))
            self.list.addItem(item)
        if 0 <= row < len(self.edges):
            self.list.setCurrentRow(row)

    def remove_current(self, *_a):
        row = self.list.currentRow()
        if 0 <= row < len(self.edges):
            self.edges = self.edges[:row] + self.edges[row + 1:]
            self._refresh()
            self.preview()

    def clear(self, *_a):
        self.edges = []
        self._refresh()
        self.preview()

    def _pick(self, obj, sub):
        if not sub.startswith("Edge") or self.base is None:
            return False
        if obj.TypeId == "PartDesign::Body":
            obj = self.obj if self.valid else self.base  # lo que se ve
        if obj == self.base:
            name = sub
        elif obj == self.obj and self.valid:
            name = dp.to_base(self.obj.Shape, sub, self.base.Shape)
        else:
            return False
        if not name:
            return False
        self.edges = dp.toggle(self.edges, name)
        return True

    def _apply(self):
        obj = self.obj
        if self.base is None:
            return "No hay chapa antes de esta brida."
        if not self.edges:
            return ""
        link = obj.baseObject
        if not link or link[0] != self.base or [s for s in link[1] if s] != self.edges:
            obj.baseObject = (self.base, list(self.edges))
        base = self._sheet_base()
        expr = dict(obj.ExpressionEngine).get("radius")
        if self.tied.isChecked() and base is not None:
            want = "%s.Radius" % base.Name
            if expr != want:
                obj.setExpression("radius", want)
            self.radius.blockSignals(True)
            self.radius.setValue(base.Radius.Value)
            self.radius.blockSignals(False)
        else:
            if expr is not None:
                obj.setExpression("radius", None)
            self._set("radius", self.radius.value())
        self._set("angle", self.angle.value())
        self._set("length", self.length.value())
        self._set("invert", self.invert.isChecked())
        if self.spec_value in [v for _t, v in LENGTH_SPECS]:
            self._set("LengthSpec", self.spec_value)
        if self.position in [v for _t, v in POSITIONS]:
            self._set("BendType", self.position)
        return ""

    def _ready(self):
        return bool(self.edges)

    def _nothing(self):
        return not self.edges

    def _overlays(self, base, result):
        nodes = super()._overlays(base, result)
        if base is None:
            return nodes
        picked = [dp._element(base, s) for s in self.edges]
        nodes.append(dp._lines_node([p for p in picked if p is not None], dp.PICKED_COLOR, dp.LINE_WIDTH))
        row = self.list.currentRow()
        if 0 <= row < len(self.edges):
            el = dp._element(base, self.edges[row])
            if el is not None:
                nodes.append(dp._lines_node([el], dp.CURRENT_COLOR, dp.LINE_WIDTH + 1))
        return nodes

    def accept(self):
        ok = super().accept()
        if ok:
            sm.remember("FlangeLength", self.length.value())
        return ok


# --- Dobladillo ----------------------------------------------------------------

# (texto SW, HemType de SheetMetal)
HEM_TYPES = (("Cerrado", "Flat"), ("Abierto", "Open"), ("Lágrima", "Teardrop"), ("Laminado", "Rolled"))
# Verificado sin GUI (placa con la arista en y=50): Material Inside no pasa la arista, Material Outside
# sale un espesor; "Thickness Outside" da error en el dobladillo (no se ofrece).
HEM_POSITIONS = (("Material interior", "Material Inside"), ("Pliegue exterior", "Material Outside"))


class HemPanel(EdgeFlangePanel):
    TRANSACTION = "Dobladillo"
    FAIL = "SheetMetal no pudo armar el dobladillo así: probá con otra longitud, radio o Invertir dirección."

    def __init__(self, obj):
        self.hem_type = obj.HemType
        super().__init__(obj)

    def _build(self):
        obj = self.obj
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(obj.Label)
        _icon(self.form, "fork/sm_hem")
        box = QtWidgets.QVBoxLayout(self.form)

        eg = QtWidgets.QGroupBox("Aristas")
        el = QtWidgets.QVBoxLayout(eg)
        el.addWidget(QtWidgets.QLabel("Aristas (clic en la chapa):"))
        self.list = dp.pick_list(self.remove_current, self.clear, height=50)
        self.list.setMaximumHeight(70)
        self.list.currentRowChanged.connect(lambda *_a: self._draw())
        self.list.setStyleSheet("QListWidget { %s }" % dp.ACTIVE_QSS)
        el.addWidget(self.list)
        self.invert = QtWidgets.QCheckBox("Invertir dirección")
        self.invert.setChecked(bool(obj.invert))
        self.invert.toggled.connect(self._changed)
        el.addWidget(self.invert)
        box.addWidget(eg)

        tg = QtWidgets.QGroupBox("Tipo y tamaño")
        self.sizes = QtWidgets.QFormLayout(tg)
        self.type_box = _choice(HEM_TYPES, self.hem_type, self._type)
        self.sizes.addRow(self.type_box)
        self.length = self._value_box("width", " mm", 0.01, 100000.0)
        self.opening = self._value_box("opening", " mm", 0.0, 100000.0)
        self.angle = self._value_box("RollAngle", "°", 1.0, 359.0)
        self.radius = self._value_box("radius", " mm", 0.01, 1000.0)
        self.rows = {}
        for key, text, widget in (("length", "Longitud:", self.length), ("opening", "Separación:", self.opening),
                                  ("angle", "Ángulo:", self.angle), ("radius", "Radio:", self.radius)):
            label = QtWidgets.QLabel(text)
            self.sizes.addRow(label, widget)
            self.rows[key] = (label, widget)
        box.addWidget(tg)

        og = QtWidgets.QGroupBox("Posición")
        of = QtWidgets.QFormLayout(og)
        self.pos_box = _choice(HEM_POSITIONS, self.position, self._position)
        of.addRow(self.pos_box)
        box.addWidget(og)
        box.addWidget(self._message_label())
        box.addStretch(1)
        self._show_rows()
        self._refresh()

    def _type(self, value):
        self.hem_type = value
        self._show_rows()
        self._changed()

    def _show_rows(self):
        show = {"length": self.hem_type != "Rolled", "opening": self.hem_type == "Open",
                "angle": self.hem_type in ("Teardrop", "Rolled"), "radius": self.hem_type in ("Teardrop", "Rolled")}
        for key, (label, widget) in self.rows.items():
            label.setVisible(show[key])
            widget.setVisible(show[key])

    def _apply(self):
        obj = self.obj
        if self.base is None:
            return "No hay chapa antes de este dobladillo."
        if not self.edges:
            return ""
        link = obj.baseObject
        if not link or link[0] != self.base or [s for s in link[1] if s] != self.edges:
            obj.baseObject = (self.base, list(self.edges))
        if self.hem_type in [v for _t, v in HEM_TYPES]:
            self._set("HemType", self.hem_type)
        self._set("width", self.length.value())
        self._set("opening", self.opening.value())
        self._set("RollAngle", self.angle.value())
        self._set("radius", self.radius.value())
        self._set("invert", self.invert.isChecked())
        if self.position in [v for _t, v in HEM_POSITIONS]:
            self._set("BendType", self.position)
        return ""

    def accept(self):
        ok = dp.SwPanel.accept(self)
        if ok:
            sm.remember("HemLength", self.length.value())
        return ok


# --- Convertir en chapa (pieza importada) -------------------------------------------


class ConvertPanel:
    """
    "Convertir en chapa" para una chapa sin historia (STEP de SW): se elige la cara fija; el
    espesor y el radio salen de la pieza; el factor K se elige. Se guarda en SWUI_Sheet del Cuerpo.
    """

    def __init__(self, body, face=None, created=False):
        self.body = body
        self.doc = body.Document
        self.created = created  # el Cuerpo lo armó este comando (Cancelar lo saca)
        self.data = dict(sm.spec(body) or {"k": sm.DEFAULT_K})
        self.busy = False
        self.face = None
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle("Convertir en chapa")
        _icon(self.form, "fork/sm_convert")
        box = QtWidgets.QVBoxLayout(self.form)
        g = QtWidgets.QGroupBox("Parámetros de chapa")
        f = QtWidgets.QFormLayout(g)
        self.face_box = dp.RefBox(lambda _w: None)
        self.face_box.setPlaceholderText("Cara fija (clic en una cara grande)")
        self.face_box.setStyleSheet(dp.ACTIVE_QSS)
        f.addRow("Cara fija:", self.face_box)
        self.thick = QtWidgets.QLabel("-")
        f.addRow("Espesor:", self.thick)
        self.radius = dp._spin(float(self.data.get("radius", 0.0)), " mm", 0.0, 1000.0)
        self.radius.setToolTip("Radio de las bridas que se agreguen; los pliegues de la pieza quedan como vinieron")
        f.addRow("Radio de plegado:", self.radius)
        self.k = dp._spin(float(self.data.get("k", sm.DEFAULT_K)), "", 0.0, 1.0, decimals=3)
        self.k.setSingleStep(0.01)
        f.addRow("Factor K:", self.k)
        box.addWidget(g)
        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: %s;" % dp.MISSING_COLOR)
        self.message.hide()
        box.addWidget(self.message)
        box.addStretch(1)
        if self.data.get("face") and self.body.Tip is not None:
            face = face or sm.face_at(self.body.Tip.Shape, self.data["face"])
        if face:
            self._take(face)
        self.observer = dp._PickObserver(self)
        FreeCADGui.Selection.addObserver(self.observer)
        FreeCADGui.Selection.clearSelection()

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

    def _say(self, text):
        self.message.setText(text)
        self.message.setVisible(bool(text))

    def _take(self, face):
        tip = self.body.Tip
        try:
            geo = tip.Shape.getElement(face)
        except Exception:
            return
        if type(geo.Surface).__name__ != "Plane":
            self._say("La cara fija tiene que ser plana.")
            return
        thick = sm.detect_thickness(tip.Shape, face)
        if not thick:
            self._say("No se pudo medir el espesor desde esa cara: ¿es una chapa (espesor parejo)?")
            return
        self.face = face
        self.data["thickness"] = round(thick, 6)
        self.data["face"] = sm.face_key(geo)
        self.thick.setText(sm.fmt_mm(thick) + " mm")
        r = sm.detect_radius(tip.Shape, thick)
        if "radius" not in self.data or not self.data["radius"]:
            self.radius.setValue(r if r else thick)
        self.face_box.setText("Cara<1>")
        self._say("" if r else "La pieza no tiene pliegues: va a quedar como una placa.")

    def take_selection(self):
        for sel in FreeCADGui.Selection.getSelectionEx():
            obj = sel.Object
            for sub in sel.SubElementNames:
                sub = sub.split(".")[-1]
                if not sub.startswith("Face"):
                    continue
                if obj is self.body.Tip or obj is self.body:
                    self._take(sub)
                elif sm.body_of(obj) is self.body:
                    name = dp.to_base(obj.Shape, sub, self.body.Tip.Shape)
                    if name:
                        self._take(name)
        self.busy = True
        try:
            FreeCADGui.Selection.clearSelection()
        finally:
            self.busy = False

    def _close(self):
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        dp._state["panel"] = None

    def accept(self):
        if not self.face:
            self._say("Elegí la cara fija: una cara grande y plana de la chapa.")
            return False
        self.data["radius"] = self.radius.value()
        self.data["k"] = self.k.value()
        sm.write_spec(self.body, self.data)
        flat = sm.flat_of(self.body)
        if flat is not None:
            sm.ensure_flat(self.body)
        self._close()
        self.doc.recompute()
        self.doc.commitTransaction()
        return True

    def reject(self):
        self._close()
        hidden = list(getattr(self, "hidden", []))
        self.doc.abortTransaction()
        for obj in hidden:
            try:
                obj.Visibility = True
            except Exception:
                pass
        self.doc.recompute()
        return True


def _choose(obj):
    k = sm.kind(obj)
    return {"base": BaseFlangePanel, "wall": EdgeFlangePanel, "hem": HemPanel}.get(k)


# --- Comandos ------------------------------------------------------------------


def _ready_to_start():
    if FreeCAD.ActiveDocument is None:
        return False
    if not sm.available():
        _info(sm.MISSING_TEXT)
        return False
    if FreeCADGui.Control.activeDialog():
        _info("Cerrá primero el panel que está abierto.")
        return False
    return True


def _open(panel_cls, obj):
    panel = panel_cls(obj)
    dp._state["panel"] = panel
    FreeCADGui.Control.showDialog(panel)
    return obj


def _labels(doc):
    return set(o.Label for o in doc.Objects)


def _has_solid(body, besides=None):
    for o in body.Group:
        if o is besides or o.TypeId == "Sketcher::SketchObject":
            continue
        try:
            if o.isDerivedFrom("PartDesign::Feature") and o.Shape.Solids:
                return True
        except Exception:
            pass
    return False


def start_base_flange():
    from swui import from_sketch, pick_plane

    if not _ready_to_start():
        return None
    if from_sketch.handle(BASE_COMMAND):
        pick_plane._disarm()  # como la cinta: la brida ya sale con este croquis
        return None  # croquis abierto: lo cierra y vuelve a llamar con el croquis elegido
    doc = FreeCAD.ActiveDocument
    sels = FreeCADGui.Selection.getSelectionEx(doc.Name)
    sketch = sels[0].Object if len(sels) == 1 and sels[0].Object.TypeId == "Sketcher::SketchObject" else None
    if sketch is None:
        if not pick_plane.handle(BASE_COMMAND):
            _info("Elegí un croquis, un plano o una cara plana (o tocá Brida base sin nada elegido).")
        return None
    body = sm.body_of(sketch)
    if body is None:
        _info("El croquis tiene que estar dentro de un Cuerpo.")
        return None
    if _has_solid(body):
        _info("Esta pieza ya tiene un sólido. La Brida base es la primera operación de una chapa: "
              "hacela en una pieza nueva.")
        return None
    import SheetMetalBaseCmd
    from swui.fork import multibody

    doc.openTransaction("Brida base")
    try:
        obj = doc.addObject("PartDesign::FeaturePython", "BaseBend")
        SheetMetalBaseCmd.SMBaseBend(obj, sketch)
        SheetMetalBaseCmd.SMBaseViewProvider(obj.ViewObject)
        body.addObject(obj)
        sm.ensure_k(obj)
        obj.Thickness = sm.last("Thickness", sm.DEFAULT_THICKNESS)
        obj.setExpression("Radius", "Thickness")  # radio = espesor (como trabaja el usuario)
        obj.Length = sm.last("BaseLength", 100.0)
        obj.BendSide = "Inside"  # el croquis da las medidas de afuera
        obj.Reverse = False
        obj.MidPlane = False
        multibody._keep_label(obj, sm.next_label("Brida-Base", _labels(doc)))
        multibody._set_tip(body, obj)
        sketch.Visibility = False
        FreeCADGui.Selection.clearSelection()
        doc.recompute()
        return _open(BaseFlangePanel, obj)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Brida base:\n%s\n" % traceback.format_exc())
        dp._state["panel"] = None
        if doc.HasPendingTransaction:
            doc.abortTransaction()
        return None


def _active_body():
    try:
        return FreeCADGui.ActiveDocument.ActiveView.getActiveObject("pdbody")
    except Exception:
        return None


def target_body(doc=None, quiet=False):
    """La chapa a usar: la elegida, la del desarrollo elegido, el Cuerpo activo o la única."""
    doc = doc or FreeCAD.ActiveDocument
    for sel in FreeCADGui.Selection.getSelectionEx(doc.Name):
        obj = sel.Object
        if sm.kind(obj) == "flat":
            body = doc.getObject(getattr(obj, sm.FLAT_PROP, ""))
        else:
            body = obj if obj.TypeId == "PartDesign::Body" else sm.body_of(obj)
        if sm.is_sheet_body(body):
            return body
    body = _active_body()
    if sm.is_sheet_body(body):
        return body
    bodies = sm.sheet_bodies(doc)
    if len(bodies) == 1:
        return bodies[0]
    if not quiet:
        _info("Elegí la chapa (o activá su Cuerpo)." if bodies else
              "Esta pieza no tiene chapa: empezá con Brida base.")
    return None


def _picked_edges(sels, body, tip):
    edges = []
    for sel in sels:
        for sub in sel.SubElementNames:
            sub = sub.split(".")[-1]
            if not sub.startswith("Edge"):
                continue
            if sel.Object is tip or sel.Object is body:
                name = sub
            elif sm.body_of(sel.Object) is body:
                name = dp.to_base(sel.Object.Shape, sub, tip.Shape)
            else:
                name = None
            if name and name not in edges:
                edges.append(name)
    return edges


def _start_on_edges(kind):
    """Brida de arista ("wall") o Dobladillo ("hem") sobre las aristas elegidas (o sin elegir)."""
    if not _ready_to_start():
        return None
    doc = FreeCAD.ActiveDocument
    sels = FreeCADGui.Selection.getSelectionEx(doc.Name)
    body = target_body(doc)
    if body is None:
        return None
    tip = body.Tip
    if tip is None:
        _info("La chapa no tiene sólido todavía.")
        return None
    edges = _picked_edges(sels, body, tip)
    from swui.fork import multibody

    label = "Brida de arista" if kind == "wall" else "Dobladillo"
    doc.openTransaction(label)
    try:
        base = sm.sheet_base(body)
        if kind == "wall":
            import SheetMetalCmd

            obj = doc.addObject("PartDesign::FeaturePython", "Bend")
            SheetMetalCmd.SMBendWall(obj, tip, edges)
            SheetMetalCmd.SMViewProviderFlat(obj.ViewObject)
        else:
            import SheetMetalHem

            obj = doc.addObject("PartDesign::FeaturePython", "Hem")
            SheetMetalHem.SMHem(obj, tip, edges)
            SheetMetalHem.SMViewProviderFlat(obj.ViewObject)
        body.addObject(obj)
        obj.invert = False
        if kind == "wall":
            if base is not None:
                obj.setExpression("radius", "%s.Radius" % base.Name)  # Usar radio predeterminado
            else:
                obj.radius = sm.radius(body) or sm.thickness(body)  # pieza convertida: por valor
            obj.length = sm.last("FlangeLength", sm.DEFAULT_LENGTH)
            obj.angle = 90.0
            obj.LengthSpec = "Outer Sharp"
            obj.BendType = "Material Inside"
            prefix, panel_cls = "Brida-Arista", EdgeFlangePanel
        else:
            obj.HemType = "Flat"
            obj.width = sm.last("HemLength", 10.0)
            obj.radius = sm.thickness(body) or 1.0
            obj.opening = sm.thickness(body) or 1.0
            obj.BendType = "Material Inside"
            prefix, panel_cls = "Dobladillo", HemPanel
        multibody._keep_label(obj, sm.next_label(prefix, _labels(doc)))
        multibody._set_tip(body, obj)
        FreeCADGui.Selection.clearSelection()
        if edges:
            doc.recompute()
        return _open(panel_cls, obj)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (label, traceback.format_exc()))
        dp._state["panel"] = None
        if doc.HasPendingTransaction:
            doc.abortTransaction()
        return None


def start_edge_flange():
    return _start_on_edges("wall")


def start_hem():
    return _start_on_edges("hem")


def start_convert():
    """Convertir en chapa una pieza sin historia (STEP): Cuerpo que arranca de ella + cara fija."""
    if not _ready_to_start():
        return None
    doc = FreeCAD.ActiveDocument
    sels = FreeCADGui.Selection.getSelectionEx(doc.Name)
    if not sels:
        _info("Elegí una cara grande y plana de la pieza a convertir (la cara fija).")
        return None
    obj = sels[0].Object
    body = obj if obj.TypeId == "PartDesign::Body" else sm.body_of(obj)
    if body is not None and sm.sheet_base(body) is not None:
        _info("Esta pieza ya es de chapa (tiene Brida base).")
        return None
    from swui.fork import move_face

    doc.openTransaction("Convertir en chapa")
    try:
        created = body is None
        hidden = [obj] if created else []
        body = body or move_face._body_for(doc, obj)
        if body is None or body.Tip is None:
            doc.abortTransaction()
            _info("Elegí una cara de un sólido.")
            return None
        face = None
        subs = [s.split(".")[-1] for s in sels[0].SubElementNames if s.split(".")[-1].startswith("Face")]
        if subs:
            if obj is body.Tip or obj is body or created:
                face = subs[0]  # el FeatureBase del Cuerpo nuevo tiene las mismas caras que el sólido
            else:
                face = dp.to_base(obj.Shape, subs[0], body.Tip.Shape)
        FreeCADGui.Selection.clearSelection()
        panel = ConvertPanel(body, face, created)
        panel.hidden = hidden
        dp._state["panel"] = panel
        FreeCADGui.Control.showDialog(panel)
        return body
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Convertir en chapa:\n%s\n" % traceback.format_exc())
        dp._state["panel"] = None
        if doc.HasPendingTransaction:
            doc.abortTransaction()
        return None


def start_cut():
    """Extruir corte nativo, con el mismo flujo SW de la pestaña Operaciones (plano o cara, croquis)."""
    from swui import ribbon

    # fuera del Activated de este comando (correr un comando adentro de otro: ver NOTAS_TECNICAS)
    QtCore.QTimer.singleShot(0, lambda: ribbon._run("PartDesign_Pocket"))


FLAT_TRANSPARENCY = 60  # el croquis del plegado queda en la cara de abajo: que se vea a través


def _sketches_follow(flat):
    """Los croquis del desarrollo se ven solo con el desarrollo (SheetMetal los crea visibles)."""
    doc = flat.Document
    for name in getattr(flat, "UnfoldSketches", []) or []:
        sk = doc.getObject(name)
        if sk is not None and not flat.Visibility and sk.Visibility:
            sk.Visibility = False
        if sk is not None and flat.Visibility and "_Sketch_Bends" in name:
            sk.Visibility = True  # las líneas de plegado, como SW
    try:
        if flat.Visibility and flat.ViewObject.Transparency != FLAT_TRANSPARENCY:
            flat.ViewObject.Transparency = FLAT_TRANSPARENCY
    except Exception:
        pass


def _flat(body, label):
    doc = body.Document
    new = sm.flat_of(body) is None
    if new:
        doc.openTransaction(label)
    try:
        flat = sm.ensure_flat(body, sketches=True)
        doc.recompute()
    except Exception:
        if new and doc.HasPendingTransaction:
            doc.abortTransaction()
        raise
    if new:
        doc.commitTransaction()
    return flat


def toggle_flat():
    if not _ready_to_start():
        return None
    body = target_body()
    if body is None:
        return None
    flat = sm.flat_of(body)
    if flat is not None and flat.Visibility:
        flat.Visibility = False
        body.Visibility = True
        _sketches_follow(flat)
        return flat
    try:
        flat = _flat(body, "Aplanar")
    except Exception as exc:
        FreeCAD.Console.PrintError("[SWUI fork] Aplanar:\n%s\n" % traceback.format_exc())
        _info("No se pudo desplegar la chapa: %s" % exc)
        return None
    if not flat.isValid():
        _info("SheetMetal no pudo desplegar esta chapa (mirá la Vista de informe).")
        return None
    body.Visibility = False
    flat.Visibility = True
    _sketches_follow(flat)
    FreeCADGui.Selection.clearSelection()
    return flat


def _is_assembly(doc):
    return any(o.TypeId == "Assembly::AssemblyObject" for o in doc.Objects) or (
        not sm.sheet_bodies(doc) and bool(sm.sheet_parts(doc)))


def export_all(doc=None):
    """DXF por lotes: un DXF por pieza de chapa del ensamblaje, en la carpeta del ensamblaje."""
    doc = doc or FreeCAD.ActiveDocument
    bodies = sm.sheet_parts(doc)
    if not bodies:
        _info("El ensamblaje no tiene piezas de chapa.")
        return []
    if doc.FileName:
        folder = os.path.dirname(doc.FileName)
    else:
        folder = QtWidgets.QFileDialog.getExistingDirectory(_mw(), "Carpeta para los DXF")
        if not folder:
            return []
    done, failed = [], []
    for body in bodies:
        name = sm.dxf_filename(sm.part_name(body), sm.thickness(body), sm.material_name(body))
        path = os.path.join(folder, name)
        try:
            flat = _flat(body, "Desarrollo")
            sm.write_dxf(body, path)
            _sketches_follow(flat)
            done.append(name)
        except Exception as exc:
            FreeCAD.Console.PrintError("[SWUI fork] DXF de %s:\n%s\n" % (body.Label, traceback.format_exc()))
            failed.append("%s (%s)" % (sm.part_name(body), exc))
    text = "DXF guardados en %s:\n%s" % (folder, "\n".join(done) or "(ninguno)")
    if failed:
        text += "\n\nNo se pudieron exportar:\n" + "\n".join(failed)
    FreeCAD.Console.PrintMessage("[SWUI fork] %s\n" % text)
    _info(text)
    return done


def export_dxf():
    if not _ready_to_start():
        return None
    if _is_assembly(FreeCAD.ActiveDocument):
        return export_all()
    body = target_body()
    if body is None:
        return None
    doc = body.Document
    name = sm.dxf_filename(sm.part_name(body), sm.thickness(body), sm.material_name(body))
    if doc.FileName:
        path = os.path.join(os.path.dirname(doc.FileName), name)
    else:
        path, _f = QtWidgets.QFileDialog.getSaveFileName(_mw(), "Exportar DXF", name, "DXF (*.dxf)")
        if not path:
            return None
    try:
        flat = _flat(body, "Desarrollo")
        sm.write_dxf(body, path)
        _sketches_follow(flat)
    except Exception as exc:
        FreeCAD.Console.PrintError("[SWUI fork] Exportar DXF:\n%s\n" % traceback.format_exc())
        _info("No se pudo exportar el DXF: %s" % exc)
        return None
    FreeCAD.Console.PrintMessage("[SWUI fork] DXF guardado: %s\n" % path)
    try:
        _mw().statusBar().showMessage("DXF guardado: %s" % path, 15000)
    except Exception:
        pass
    return path


class _Command:
    def __init__(self, text, tip, icon, run):
        self.text, self.tip, self.icon, self.run = text, tip, icon, run

    def GetResources(self):
        from swui import paths

        return {"MenuText": self.text, "ToolTip": self.tip, "Pixmap": paths.icon(self.icon) or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        self.run()


COMMANDS = {
    BASE_COMMAND: ("Brida base", "Primera operación de una chapa: placa o perfil plegado desde un croquis (como SW)",
                   "fork/sm_base_flange", start_base_flange),
    EDGE_COMMAND: ("Brida de arista", "Pared plegada sobre una o más aristas de la chapa (como SW)",
                   "fork/sm_edge_flange", start_edge_flange),
    HEM_COMMAND: ("Dobladillo", "Dobladillo cerrado, abierto, lágrima o laminado sobre aristas de la chapa (como SW)",
                  "fork/sm_hem", start_hem),
    CUT_COMMAND: ("Extruir corte", "Corte extruido sobre la chapa (el de Operaciones; el desarrollo lo lleva)",
                  "sketch/f_pocket", start_cut),
    CONVERT_COMMAND: ("Convertir en chapa", "Chapa sin historia (p. ej. STEP de SW): elegir la cara fija; "
                      "el espesor se mide solo", "fork/sm_convert", start_convert),
    FLAT_COMMAND: ("Aplanar", "Mostrar el desarrollo de la chapa; otro clic la vuelve a plegar",
                   "fork/sm_flatten", toggle_flat),
    DXF_COMMAND: ("Exportar DXF", "Guardar el desarrollo en DXF (contorno y líneas de plegado) al lado de la pieza",
                  "fork/sm_dxf", export_dxf),
}


def install():
    from swui import from_sketch, pick_plane
    from swui.fork import sheet_tab

    for name, (text, tip, icon, run) in COMMANDS.items():
        try:
            FreeCADGui.addCommand(name, _Command(text, tip, icon, run))
        except Exception:
            pass  # ya registrado
    if _choose not in dp.CHOOSERS:
        dp.CHOOSERS.append(_choose)
    if BASE_COMMAND not in pick_plane.FEATURE_COMMANDS:
        pick_plane.FEATURE_COMMANDS = tuple(pick_plane.FEATURE_COMMANDS) + (BASE_COMMAND,)
    if BASE_COMMAND not in from_sketch.PROFILE_FEATURES:
        from_sketch.PROFILE_FEATURES = tuple(from_sketch.PROFILE_FEATURES) + (BASE_COMMAND,)
    sheet_tab.install()
