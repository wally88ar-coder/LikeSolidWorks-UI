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
        self.spec_value = obj.LengthSpec
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


def _choose(obj):
    k = sm.kind(obj)
    return BaseFlangePanel if k == "base" else EdgeFlangePanel if k == "wall" else None


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


def start_edge_flange():
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
    import SheetMetalCmd
    from swui.fork import multibody

    doc.openTransaction("Brida de arista")
    try:
        base = sm.sheet_base(body)
        obj = doc.addObject("PartDesign::FeaturePython", "Bend")
        SheetMetalCmd.SMBendWall(obj, tip, edges)
        SheetMetalCmd.SMViewProviderFlat(obj.ViewObject)
        body.addObject(obj)
        obj.setExpression("radius", "%s.Radius" % base.Name)  # Usar radio predeterminado
        obj.length = sm.last("FlangeLength", sm.DEFAULT_LENGTH)
        obj.angle = 90.0
        obj.invert = False
        obj.LengthSpec = "Outer Sharp"
        obj.BendType = "Material Inside"
        multibody._keep_label(obj, sm.next_label("Brida-Arista", _labels(doc)))
        multibody._set_tip(body, obj)
        FreeCADGui.Selection.clearSelection()
        if edges:
            doc.recompute()
        return _open(EdgeFlangePanel, obj)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Brida de arista:\n%s\n" % traceback.format_exc())
        dp._state["panel"] = None
        if doc.HasPendingTransaction:
            doc.abortTransaction()
        return None


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


def export_dxf():
    if not _ready_to_start():
        return None
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
