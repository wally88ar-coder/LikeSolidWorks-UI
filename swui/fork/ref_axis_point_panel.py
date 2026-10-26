# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Paneles de Eje y Punto de referencia como el PropertyManager de SOLIDWORKS 2018.

Como en SW: una lista "Selecciones" (clic en la pieza o en el árbol flotante;
otro clic, Supr o clic derecho saca) y los botones de tipo; el tipo se elige
solo según lo tocado, o a mano. Por debajo, PartDesign::Line / PartDesign::Point
de FreeCAD con su adjunción (resolve_axis / resolve_point dan el modo):

Eje:   Una línea/arista/eje   -> TwoPointLine (un eje de FreeCAD: ObjectX)
       Dos planos             -> IntersectionLine
       Dos puntos/vértices    -> TwoPointLine
       Superficie cilíndrica  -> AxisOfInertia1 (cara) / AxisOfCurvature (arista circular)
       Punto y cara/plano     -> FaceNormal (normal a la cara por el punto)
Punto: Centro de arco         -> CenterOfCurvature
       Centro de cara         -> CenterOfMass
       Intersección           -> ProximityPoint1 (dos aristas)
       Proyección             -> ProximityPoint1 (cara primero, después el punto)
       A lo largo de la curva -> OnEdge (porcentaje del largo)
"""

import FreeCAD

from swui.compat import QtWidgets
from swui.fork import dress_up_panel as dp
from swui.fork import ref_plane_panel as rp

LINE = "PartDesign::Line"
POINT = "PartDesign::Point"
ARC_EDGE = "arc"  # tipo extra de lo tocado: arista circular

# Eje: tipo SW -> texto
AXIS_TYPES = [("line", "Una línea/arista/eje"), ("planes", "Dos planos"), ("points", "Dos puntos/vértices"),
              ("cyl", "Superficie cilíndrica/cónica"), ("point_face", "Punto y cara/plano")]
POINT_TYPES = [("arc_center", "Centro de arco"), ("face_center", "Centro de cara"), ("intersection", "Intersección"),
               ("projection", "Proyección"), ("along", "A lo largo de la curva")]


# --- Sin FreeCAD (probables en el test) ---------------------------------


def guess_axis(kinds):
    """Tipo de eje que SW elige solo según lo tocado."""
    if kinds == ["edge"]:
        return "line"
    if kinds in (["cyl"], [ARC_EDGE]):
        return "cyl"
    if kinds == ["plane", "plane"]:
        return "planes"
    if kinds == ["vertex", "vertex"]:
        return "points"
    if sorted(kinds) == ["plane", "vertex"]:
        return "point_face"
    return None


def resolve_axis(kind, kinds, line_object=False):
    """(modo, orden de referencias) o None."""
    if kind == "line" and kinds == ["edge"]:
        return ("ObjectX" if line_object else "TwoPointLine"), [0]
    if kind == "planes" and kinds == ["plane", "plane"]:
        return "IntersectionLine", [0, 1]
    if kind == "points" and kinds == ["vertex", "vertex"]:
        return "TwoPointLine", [0, 1]
    if kind == "cyl" and kinds == ["cyl"]:
        return "AxisOfInertia1", [0]
    if kind == "cyl" and kinds == [ARC_EDGE]:
        return "AxisOfCurvature", [0]
    if kind == "point_face" and sorted(kinds) == ["plane", "vertex"]:
        return "FaceNormal", [kinds.index("plane"), kinds.index("vertex")]
    return None


def guess_point(kinds):
    if kinds == [ARC_EDGE]:
        return "arc_center"
    if kinds in (["plane"], ["cyl"]):
        return "face_center"
    if kinds == ["edge", "edge"]:
        return "intersection"
    if sorted(kinds) == ["plane", "vertex"]:
        return "projection"
    if kinds == ["edge"]:
        return "along"
    return None


def resolve_point(kind, kinds):
    if kind == "arc_center" and kinds == [ARC_EDGE]:
        return "CenterOfCurvature", [0]
    if kind == "face_center" and len(kinds) == 1 and kinds[0] in ("plane", "cyl"):
        return "CenterOfMass", [0]
    if kind == "intersection" and len(kinds) == 2 and all(k in ("edge", ARC_EDGE) for k in kinds):
        return "ProximityPoint1", [0, 1]
    if kind == "projection" and sorted(kinds) == ["plane", "vertex"]:
        return "ProximityPoint1", [kinds.index("plane"), kinds.index("vertex")]
    if kind == "along" and len(kinds) == 1 and kinds[0] in ("edge", ARC_EDGE):
        return "OnEdge", [0]
    return None


def kind_of(obj, sub):
    """Como en el plano, más 'arc' para una arista circular."""
    kind = rp.kind_of(obj, sub)
    if kind == "edge" and sub:
        el = dp._element(obj.Shape, sub)
        if type(getattr(el, "Curve", None)).__name__ in ("Circle", "ArcOfCircle"):
            return ARC_EDGE
    return kind


# --- Panel -------------------------------------------------------------


class _RefTypePanel(dp.SwPanel):
    TYPES = []
    TITLE = ""
    MAX_REFS = 2

    def _base(self):
        return None

    def _remember_visibility(self):
        return {}

    def _tip_or_self(self):
        return True

    def _build(self):
        self.refs = []  # [(obj, sub, kind)]
        self.chosen = None  # tipo elegido a mano
        box = QtWidgets.QWidget()
        box.setWindowTitle(self.TITLE)
        lay = QtWidgets.QVBoxLayout(box)
        lay.addWidget(QtWidgets.QLabel("Selecciones (clic en la pieza o en el árbol):"))
        self.list = dp.pick_list(self.remove_current, self.clear, 60)
        self.list.setStyleSheet(dp.ACTIVE_QSS)
        lay.addWidget(self.list)
        self.buttons = {}
        for key, text in self.TYPES:
            b = QtWidgets.QRadioButton(text)
            b.toggled.connect(lambda on, k=key: on and self._choose(k))
            lay.addWidget(b)
            self.buttons[key] = b
        self._build_extra(lay)
        self.status = QtWidgets.QLabel()
        lay.addWidget(self.status)
        lay.addWidget(self._message_label())
        self.form = box
        self._load()

    def _build_extra(self, lay):
        pass

    def _choose(self, key):
        self.chosen = key
        self._changed()

    def _load(self):
        try:
            support = list(self.obj.AttachmentSupport)
        except Exception:
            support = []
        for ref_obj, subs in support:
            for sub in (subs if isinstance(subs, (list, tuple)) else [subs]) or [""]:
                kind = kind_of(ref_obj, sub)
                if kind:
                    self.refs.append((ref_obj, sub, kind))
        self._fill()

    def _fill(self):
        self.list.clear()
        for obj, sub, _k in self.refs:
            self.list.addItem(rp.PlanePanel._ref_text(self, (obj, sub)))
        kind = self._kind()
        for key, b in self.buttons.items():
            b.blockSignals(True)
            b.setChecked(key == kind)
            b.blockSignals(False)

    def _kinds(self):
        return [k for _o, _s, k in self.refs]

    def _kind(self):
        return self.chosen or self._guess(self._kinds())

    def _pick(self, obj, sub):
        if obj == self.obj or (sub and not sub.startswith(("Face", "Edge", "Vertex"))):
            return False
        kind = kind_of(obj, sub)
        if kind is None:
            return False
        same = [r for r in self.refs if r[0] == obj and r[1] == sub]
        if same:
            self.refs = [r for r in self.refs if r not in same]
        elif len(self.refs) < self.MAX_REFS:
            self.refs = self.refs + [(obj, sub, kind)]
        else:
            return False
        self.chosen = None  # con selecciones nuevas, que SW vuelva a elegir el tipo
        return True

    def _refresh(self):
        self._fill()

    def remove_current(self, *_a):
        row = self.list.currentRow()
        if 0 <= row < len(self.refs):
            self.refs = self.refs[:row] + self.refs[row + 1:]
            self.chosen = None
            self._fill()
            self.preview()

    def clear(self, *_a):
        self.refs = []
        self.chosen = None
        self._fill()
        self.preview()

    def _nothing(self):
        return not self.refs

    def _ready(self):
        return self._plan() is not None

    def _apply(self):
        self._fill()
        plan = self._plan()
        if plan is None:
            self.status.setText("Elegí las selecciones del tipo marcado." if self.refs else "")
            self.status.setStyleSheet("")
            return "Con estas selecciones no se puede hacer este tipo." if self.refs and self._kind() else ""
        mode, order = plan
        obj = self.obj
        support = [(self.refs[i][0], self.refs[i][1]) for i in order]
        mode, support = self._adjust(mode, support)
        if list(obj.AttachmentSupport) != support:
            obj.AttachmentSupport = support
        if obj.MapMode != mode:
            obj.MapMode = mode
        self._apply_extra()
        self.status.setText("Totalmente definido")
        self.status.setStyleSheet("color: %s;" % rp.OK_COLOR)
        return ""

    def _apply_extra(self):
        pass

    def _adjust(self, mode, support):
        return mode, support

    def _overlays(self, base, result):
        shapes = []
        for obj, sub, _k in self.refs:
            if sub:
                try:
                    shapes.append(dp._global_shape(obj).getElement(sub))
                except Exception:
                    pass
        return [dp._lines_node(shapes, dp.PICKED_COLOR, dp.LINE_WIDTH)] if shapes else []


class AxisPanel(_RefTypePanel):
    TITLE = "Selecciones del eje"
    TRANSACTION = "Editar eje"
    FAIL = "FreeCAD no puede ubicar el eje con estas selecciones."
    NOTHING = "Elegí las selecciones del eje."
    TYPES = AXIS_TYPES

    def _guess(self, kinds):
        return guess_axis(kinds)

    def _adjust(self, mode, support):
        """
        Cara cilíndrica: AxisOfInertia1 sale torcido si la cara está cortada (probado);
        un borde circular de la cara da el eje exacto (AxisOfCurvature).
        """
        if mode != "AxisOfInertia1":
            return mode, support
        obj, sub = support[0]
        face = dp._element(obj.Shape, sub)
        for edge in getattr(face, "Edges", []):
            if type(getattr(edge, "Curve", None)).__name__ == "Circle":
                for i, cand in enumerate(obj.Shape.Edges):
                    if cand.isSame(edge):
                        return "AxisOfCurvature", [(obj, "Edge%d" % (i + 1))]
        return mode, support

    def _plan(self):
        # un eje del Origen (App::Line, sin forma) va con ObjectX; lo demás por sus dos puntas
        line_object = len(self.refs) == 1 and self.refs[0][0].TypeId == "App::Line"
        return resolve_axis(self._kind(), self._kinds(), line_object)


class PointPanel(_RefTypePanel):
    TITLE = "Selecciones del punto"
    TRANSACTION = "Editar punto"
    FAIL = "FreeCAD no puede ubicar el punto con estas selecciones."
    NOTHING = "Elegí las selecciones del punto."
    TYPES = POINT_TYPES

    def _build_extra(self, lay):
        form = QtWidgets.QFormLayout()
        value = 50.0
        try:
            value = self.obj.MapPathParameter * 100.0
        except Exception:
            pass
        self.percent = dp._spin(value, " %", 0.0, 100.0)
        self.percent.valueChanged.connect(self._changed)
        self.percent_label = QtWidgets.QLabel("Porcentaje del largo:")
        form.addRow(self.percent_label, self.percent)
        lay.addLayout(form)

    def _guess(self, kinds):
        return guess_point(kinds)

    def _plan(self):
        return resolve_point(self._kind(), self._kinds())

    def _apply_extra(self):
        along = self._kind() == "along"
        if along:
            self._set("MapPathParameter", self.percent.value() / 100.0)

    def _fill(self):
        super()._fill()
        along = self._kind() == "along"
        for w in (self.percent, self.percent_label):
            w.setVisible(along)


def install():
    dp.PANELS[LINE] = AxisPanel
    dp.PANELS[POINT] = PointPanel
