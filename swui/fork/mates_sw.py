# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Relaciones de posición como el PropertyManager de SW 2018 (fase 5, etapa 2).

- Panel "Relación de posición" que queda abierto: se eligen dos entidades, la relación que
  corresponde se aplica sola (vista previa), "Agregar" la confirma y el panel espera las dos
  siguientes. Aceptar (OK) confirma la que esté pendiente y cierra; Cancelar descarta solo la
  pendiente (las ya agregadas quedan).
- Relaciones estándar: Coincidente, Paralela, Perpendicular, Tangente, Concéntrica, Bloquear,
  Distancia y Ángulo; Alineada / Antialineada; límites de distancia y ángulo en la concéntrica.
- Doble clic en una relación hecha con estas (o con las uniones equivalentes) abre el mismo panel.
- Clic derecho sobre un componente: Fijar / Flotar y Ver relaciones de posición.

Por debajo, las uniones nativas del banco Ensamblaje de FreeCAD (Assembly, JointObject):
Coincidente / Tangente / Distancia = unión "Distance" (0 o el valor), Concéntrica =
"Cylindrical", Bloquear = "Fixed". El archivo abre sin el addon. La relación SW elegida se
guarda en la propiedad SWUI_MateType de la unión (nombre estable, ver docs/ESTADO.md).
Los nombres SW de componentes ("(f) Placa<1>") y de relaciones los pone el original (naming.py).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

COMMAND = "SWUI_Mate"
FIX = "SWUI_FixComponent"
FLOAT = "SWUI_FloatComponent"
VIEW_MATES = "SWUI_ViewMates"
LABEL = "Relación de posición"
PROP = "SWUI_MateType"  # nombre estable: no cambiar

# clave -> (texto SW, ícono, tipo de unión de FreeCAD)
MATES = {
    "coincident": ("Coincidente", "sketch/m_coincident", "Distance"),
    "parallel": ("Paralela", "sketch/m_parallel", "Parallel"),
    "perpendicular": ("Perpendicular", "sketch/m_perpendicular", "Perpendicular"),
    "tangent": ("Tangente", "sketch/rel_tangent", "Distance"),
    "concentric": ("Concéntrica", "sketch/m_concentric", "Cylindrical"),
    "lock": ("Bloquear", "sketch/m_fixed", "Fixed"),
    "distance": ("Distancia", "sketch/dimension", "Distance"),
    "angle": ("Ángulo", "sketch/m_angle", "Angle"),
}
ORDER = ("coincident", "parallel", "perpendicular", "tangent", "concentric", "lock", "distance", "angle")
# las que se pueden dar vuelta (Alineada / Antialineada)
FLIPPABLE = ("coincident", "parallel", "tangent", "concentric", "lock", "distance")

AXIS = ("cylinder", "cone", "circle")
ROUND = ("cylinder", "sphere", "cone")

KIND_NAMES = {
    "plane": "Cara plana", "cylinder": "Cara cilíndrica", "cone": "Cara cónica",
    "sphere": "Cara esférica", "face": "Cara", "line": "Arista recta", "circle": "Arista circular",
    "edge": "Arista", "point": "Vértice", "part": "Componente", "attached": "Plano/eje apoyado en una pieza",
}

_panel = None
_installed = False


# --- Cuentas sin FreeCAD (probables en el test) ---------------------------------


def applicable(kinds):
    """Relaciones posibles para dos entidades (claves de MATES), la de por defecto primero."""
    if len(kinds) != 2:
        return []
    pair = set(kinds)
    a, b = kinds
    if "attached" in pair:
        return []
    if "part" in pair:
        return ["lock"]
    out = []
    if "point" in pair:
        out = ["coincident", "distance"]
    elif pair == {"plane"}:
        out = ["coincident", "parallel", "perpendicular", "distance", "angle"]
    elif "plane" in pair and pair & set(ROUND):
        other = b if a == "plane" else a
        out = ["tangent", "distance"] + (["parallel", "perpendicular"] if other in AXIS else [])
    elif a in AXIS and b in AXIS:
        out = ["concentric"] + (["tangent"] if pair <= {"cylinder"} else []) + \
            ["parallel", "perpendicular", "distance"]
    elif pair == {"sphere"}:
        out = ["tangent", "distance"]
    elif pair & set(AXIS) and "line" in pair:
        out = ["concentric", "coincident", "parallel", "perpendicular", "distance"]
    elif pair & set(AXIS) and "sphere" in pair:
        out = ["tangent", "distance"]
    elif pair <= {"line", "plane"}:
        out = ["coincident", "parallel", "perpendicular", "distance"] + (["angle"] if pair == {"line"} else [])
    else:
        out = ["coincident", "parallel", "perpendicular", "distance", "angle"]
    return out + ["lock"]


def next_label(used, base):
    """'Coincidente1', 'Coincidente2'... el primer número libre."""
    n = 1
    while "%s%d" % (base, n) in used:
        n += 1
    return "%s%d" % (base, n)


def key_of(joint):
    """Relación SW de una unión existente (o None si no tiene equivalente en el panel)."""
    key = getattr(joint, PROP, "") or ""
    if key in MATES:
        return key
    jtype = getattr(joint, "JointType", "")
    if jtype == "Distance":
        try:
            value = float(getattr(joint, "Distance", 0))
        except Exception:
            value = 0.0
        return "coincident" if abs(value) < 1e-9 else "distance"
    for k in ORDER:
        if MATES[k][2] == jtype and k not in ("coincident", "tangent", "distance"):
            return k
    return None


def describe(kind, component):
    return "%s – %s" % (KIND_NAMES.get(kind, kind), component) if component else KIND_NAMES.get(kind, kind)


# --- FreeCAD ---------------------------------------------------------------


def _assembly_modules():
    import JointObject
    import UtilsAssembly

    return JointObject, UtilsAssembly


def active_assembly():
    try:
        return _assembly_modules()[1].activeAssembly()
    except Exception:
        return None


def _assemblies(doc):
    return [o for o in (doc.Objects if doc else []) if o.TypeId == "Assembly::AssemblyObject"]


def ensure_active():
    """El ensamblaje activo; si el documento tiene uno solo, lo activa (como abrirlo en SW)."""
    asm = active_assembly()
    if asm is not None:
        return asm
    doc = FreeCAD.ActiveDocument
    found = _assemblies(doc)
    if len(found) != 1:
        return None
    try:
        FreeCADGui.ActiveDocument.setEdit(found[0])
    except Exception:
        return None
    return active_assembly()


def kind_of(shape):
    from swui import assembly_mates

    return assembly_mates.kind_of_shape(shape)


def entities_from_selection(asm):
    """[(componente, sub relativo al componente, tipo de entidad, forma global)] de lo elegido."""
    _jo, ua = _assembly_modules()
    out = []
    try:
        sels = FreeCADGui.Selection.getSelectionEx("", 0)
    except Exception:
        return out
    for sel in sels:
        for sub in list(getattr(sel, "SubElementNames", []) or []):
            try:
                comp, rel = ua.getComponentReference(asm, sel.Object, sub)
            except Exception:
                comp, rel = None, ""
            if comp is None:
                continue
            leaf = sub.rsplit(".", 1)[-1]
            shape = None
            try:
                shape = sel.Object.getSubObject(sub)
            except Exception:
                pass
            kind = kind_of(shape) if leaf else "part"
            if not leaf:
                kind = _datum_kind(sel.Object, sub) or kind
            out.append((comp, rel, kind, shape))
    return out


DATUM_KINDS = {"App::Plane": "plane", "Part::DatumPlane": "plane", "App::Line": "line",
               "Part::DatumLine": "line", "App::Point": "point", "Part::DatumPoint": "point"}


def _datum_kind(root, sub):
    """Plano/eje/punto del ensamblaje o del origen; 'attached' si está apoyado en una pieza."""
    try:
        obj = root.getSubObject(sub, 1)
    except Exception:
        return None
    kind = DATUM_KINDS.get(getattr(obj, "TypeId", ""))
    if kind and obj.TypeId.startswith("Part::Datum") and getattr(obj, "MapMode", "Deactivated") != "Deactivated":
        return "attached"  # el motor de FreeCAD no lo toma (probado en 1.1.4)
    return kind


def joints_of(asm):
    try:
        jg = _assembly_modules()[1].getJointGroup(asm)
    except Exception:
        return []
    return [j for j in (jg.Group if jg else []) if hasattr(j, "JointType")]


def mates_of(asm, comp):
    """Relaciones (uniones) que tocan a un componente."""
    out = []
    for j in joints_of(asm):
        for prop in ("Reference1", "Reference2"):
            ref = getattr(j, prop, None)
            if ref and ref[0] is comp:
                out.append(j)
                break
    return out


def grounded_joint(asm, comp):
    try:
        jg = _assembly_modules()[1].getJointGroup(asm)
    except Exception:
        return None
    for j in (jg.Group if jg else []):
        if getattr(j, "ObjectToGround", None) is comp:
            return j
    return None


def _global(comp, sub, shape=None):
    if shape is not None:
        return shape
    try:
        return comp.getSubObject(sub) if sub else comp.Shape
    except Exception:
        return None


def current_value(key, shapes):
    """Valor inicial de Distancia / Ángulo: lo que hay ahora entre las dos entidades (como SW)."""
    try:
        a, b = shapes
        if key == "distance":
            return round(a.distToShape(b)[0], 3)
        if key == "angle":
            na = a.normalAt(0, 0) if a.ShapeType == "Face" else a.tangentAt(a.FirstParameter)
            nb = b.normalAt(0, 0) if b.ShapeType == "Face" else b.tangentAt(b.FirstParameter)
            import math

            return round(math.degrees(na.getAngle(nb)), 3)
    except Exception:
        pass
    return 10.0 if key == "distance" else 90.0


def create_joint(asm, key, refs, value=None, label=None):
    """Una unión nativa para la relación SW `key` entre refs = [(comp, sub), (comp, sub)]."""
    jo, ua = _assembly_modules()
    jg = ua.getJointGroup(asm)
    jtype = MATES[key][2]
    joint = jg.newObject("App::FeaturePython", "Joint")
    jo.Joint(joint, jo.JointTypes.index(jtype))
    if FreeCAD.GuiUp and joint.ViewObject is not None:
        jo.ViewProviderJoint(joint.ViewObject)
    joint.addProperty("App::PropertyString", PROP, "Relación SW",
                      "Relación de posición de SW que representa esta unión (LikeSolidWorks UI)")
    setattr(joint, PROP, key)
    joint.Label = label or next_label({j.Label for j in joints_of(asm)}, MATES[key][0])
    if key == "distance" and value is not None:
        joint.Distance = value
    elif key == "angle" and value is not None:
        joint.Angle = value
    from swui.fork import mate_refs

    # sin el nombre de la operación: así FreeCAD sigue a la cara cuando la pieza cambia (mate_refs)
    connectors = [mate_refs.plain_ref([comp, [sub, sub]]) for comp, sub in refs]
    if key == "lock":
        _keep_position(joint, connectors)
    joint.Proxy.setJointConnectors(joint, connectors)
    return joint


def _keep_position(joint, connectors):
    """Bloquear deja las piezas donde están (SW): el segundo sistema se corre a la posición actual."""
    _jo, ua = _assembly_modules()
    try:
        (c1, s1), (c2, s2) = [(c[0], c[1]) for c in connectors]
        p1 = ua.findPlacement([c1, s1], False)
        p2 = ua.findPlacement([c2, s2], False)
        g1, g2 = c1.Placement, c2.Placement
        joint.Offset2 = p2.inverse().multiply(g2.inverse()).multiply(g1).multiply(p1)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Bloquear: %s\n" % traceback.format_exc())


def solve(asm):
    try:
        return asm.solve()
    except Exception:
        return -1


# --- Panel ---------------------------------------------------------------


class _SelObserver:
    def __init__(self, panel):
        self.panel = panel

    def addSelection(self, *_a):
        self.panel.schedule()

    def removeSelection(self, *_a):
        self.panel.schedule()

    def setSelection(self, *_a):
        self.panel.schedule()

    def clearSelection(self, *_a):
        self.panel.schedule()


class MatePanel:
    """PropertyManager 'Relación de posición'."""

    def __init__(self, asm, key=None, joint=None):
        self.asm = asm
        self.doc = asm.Document
        self.key = key
        self.joint = joint
        self.editing = joint is not None
        self.follow = not self.editing  # en edición, la selección no cambia las entidades
        self.entities = []  # [(comp, sub, kind, shape)]
        self.added = []
        self.flipped = False
        self.busy = False
        self.value = {"distance": None, "angle": None}
        if self.editing:
            for prop in ("Reference1", "Reference2"):
                ref = getattr(joint, prop)
                sub = ref[1][0] if ref[1] else ""
                shape = _global(ref[0], sub)
                self.entities.append((ref[0], sub, kind_of(shape) if sub.rsplit(".", 1)[-1] else "part", shape))
            self.key = key_of(joint) or "coincident"
            if self.key == "distance":
                self.value["distance"] = float(joint.Distance)
            elif self.key == "angle":
                self.value["angle"] = float(joint.Angle)
            self.doc.openTransaction("Editar relación de posición")
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self._selection_changed)
        self._build()
        self.observer = _SelObserver(self)
        try:
            FreeCADGui.Selection.addObserver(self.observer, FreeCADGui.Selection.ResolveMode.NoResolve)
        except Exception:
            FreeCADGui.Selection.addObserver(self.observer)
        try:
            FreeCADGui.Selection.setSelectionStyle(FreeCADGui.Selection.SelectionStyle.GreedySelection)
        except Exception:
            pass
        if self.follow:
            self._selection_changed()
        self._refresh()

    # --- interfaz

    def _build(self):
        from swui import paths
        from swui.compat import QtGui

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(self.joint.Label if self.editing else LABEL)
        icon = paths.icon("sketch/m_coincident")
        if icon:
            self.form.setWindowIcon(QtGui.QIcon(icon))
        box = QtWidgets.QVBoxLayout(self.form)

        sel = QtWidgets.QGroupBox("Selecciones de relaciones de posición")
        sl = QtWidgets.QVBoxLayout(sel)
        from swui.fork import dress_up_panel as dp

        self.list = dp.pick_list(self.remove_current, self.clear, 44)
        self.list.setMaximumHeight(48)
        sl.addWidget(self.list)
        # arriba, a la vista (en SW el ✓ aparece junto al mouse)
        self.add_button = QtWidgets.QPushButton("Agregar relación (✓)")
        self.add_button.clicked.connect(self.add)
        sl.addWidget(self.add_button)
        box.addWidget(sel)

        std = QtWidgets.QGroupBox("Relaciones de posición estándar")
        # la elegida se ve hundida y celeste, como el botón apretado de SW
        std.setStyleSheet("QToolButton:checked { background: #cfe3f6; border: 1px solid #5b9bd5; }")
        grid = QtWidgets.QGridLayout(std)
        grid.setVerticalSpacing(1)
        self.buttons = {}
        for row, key in enumerate(ORDER):
            text, svg, _jt = MATES[key]
            b = QtWidgets.QToolButton()
            b.setText(text)
            b.setCheckable(True)
            b.setAutoRaise(True)
            b.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            b.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
            path = paths.icon(svg)
            if path:
                b.setIcon(QtGui.QIcon(path))
            b.clicked.connect(lambda _on=False, k=key: self.set_key(k))
            grid.addWidget(b, row, 0)
            self.buttons[key] = b
        self.dist = self._spin(" mm", 0, 1e6)
        self.dist.valueChanged.connect(lambda v: self._value("distance", v))
        grid.addWidget(self.dist, ORDER.index("distance"), 1)
        self.angle = self._spin(" °", 0, 180)
        self.angle.valueChanged.connect(lambda v: self._value("angle", v))
        grid.addWidget(self.angle, ORDER.index("angle"), 1)
        box.addWidget(std)

        align = QtWidgets.QHBoxLayout()
        align.addWidget(QtWidgets.QLabel("Alineación:"))
        self.aligned = QtWidgets.QToolButton()
        self.aligned.setText("Alineada")
        self.anti = QtWidgets.QToolButton()
        self.anti.setText("Antialineada")
        for b, flip in ((self.aligned, False), (self.anti, True)):
            b.setCheckable(True)
            b.clicked.connect(lambda _on=False, f=flip: self.set_flipped(f))
            align.addWidget(b)
        align.addStretch(1)
        self.align_row = QtWidgets.QWidget()
        self.align_row.setLayout(align)
        box.addWidget(self.align_row)

        self.limits = QtWidgets.QGroupBox("Límites (concéntrica)")
        ll = QtWidgets.QGridLayout(self.limits)
        self.limit_boxes = {}
        rows = (("EnableLengthMin", "LengthMin", "Distancia mínima", " mm", -1e6, 1e6),
                ("EnableLengthMax", "LengthMax", "Distancia máxima", " mm", -1e6, 1e6),
                ("EnableAngleMin", "AngleMin", "Ángulo mínimo", " °", -360, 360),
                ("EnableAngleMax", "AngleMax", "Ángulo máximo", " °", -360, 360))
        for r, (enable, prop, text, suffix, low, high) in enumerate(rows):
            check = QtWidgets.QCheckBox(text)
            spin = self._spin(suffix, low, high)
            check.toggled.connect(lambda on, e=enable, p=prop, s=spin: self._limit(e, p, s, on))
            spin.valueChanged.connect(lambda v, e=enable, p=prop, c=check: self._limit(e, p, None, c.isChecked(), v))
            ll.addWidget(check, r, 0)
            ll.addWidget(spin, r, 1)
            self.limit_boxes[prop] = (check, spin, enable)
        box.addWidget(self.limits)

        done = QtWidgets.QGroupBox("Relaciones de posición agregadas")
        dl = QtWidgets.QVBoxLayout(done)
        self.done_list = QtWidgets.QListWidget()
        self.done_list.setMinimumHeight(40)
        dl.addWidget(self.done_list)
        self.done_group = done
        box.addWidget(done)

        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        box.addWidget(self.message)
        box.addStretch(1)

    @staticmethod
    def _spin(suffix, low, high):
        s = QtWidgets.QDoubleSpinBox()
        s.setDecimals(2)
        s.setRange(low, high)
        s.setSuffix(suffix)
        s.setKeyboardTracking(False)
        return s

    def _refresh(self):
        kinds = [e[2] for e in self.entities]
        keys = applicable(kinds) if len(self.entities) == 2 else []
        self.list.clear()
        for comp, _sub, kind, _shape in self.entities:
            self.list.addItem(describe(kind, comp.Label))
        for key, b in self.buttons.items():
            b.setEnabled(key in keys)
            b.setChecked(key == self.key and self.joint is not None)
        self._quiet(self.dist, self.value["distance"] if self.value["distance"] is not None else 0)
        self._quiet(self.angle, self.value["angle"] if self.value["angle"] is not None else 0)
        self.dist.setEnabled(self.key == "distance" and self.joint is not None)
        self.angle.setEnabled(self.key == "angle" and self.joint is not None)
        flip = self.joint is not None and self.key in FLIPPABLE
        self.align_row.setVisible(flip)
        self.aligned.setChecked(not self.flipped)
        self.anti.setChecked(self.flipped)
        self.limits.setVisible(self.joint is not None and self.key == "concentric")
        if self.joint is not None and self.key == "concentric":
            for prop, (check, spin, enable) in self.limit_boxes.items():
                check.blockSignals(True)
                check.setChecked(bool(getattr(self.joint, enable, False)))
                check.blockSignals(False)
                try:
                    self._quiet(spin, float(getattr(self.joint, prop)))
                except Exception:
                    pass
        self.add_button.setVisible(not self.editing)
        self.add_button.setEnabled(self.joint is not None)
        self.done_group.setVisible(bool(self.added))
        self.done_list.clear()
        self.done_list.addItems(self.added)
        self._hint(kinds)

    @staticmethod
    def _quiet(spin, value):
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)

    def _hint(self, kinds, problem=""):
        if problem:
            text = problem
        elif not self.entities:
            text = "Elegí dos caras, aristas o vértices de dos componentes distintos."
        elif len(self.entities) == 1:
            text = "Elegí la segunda entidad, en otro componente."
        elif len(self.entities) > 2:
            text = "Hay más de dos entidades elegidas: sacá las que sobran."
        elif self.entities[0][0] is self.entities[1][0]:
            text = "Las dos entidades son del mismo componente: elegí una de otro."
        elif "attached" in kinds:
            text = ("Ese plano/eje está apoyado en una pieza y FreeCAD no lo toma en relaciones: elegí la "
                    "cara de la pieza y usá Distancia (o un plano hecho sobre el origen del ensamblaje).")
        elif self.joint is not None and not self.editing:
            text = "Revisá la vista y apretá Agregar (o elegí otra relación)."
        else:
            text = ""
        self.message.setText(text)
        self.message.setVisible(bool(text))

    # --- selección

    def schedule(self):
        if not self.busy:
            self.timer.start()

    def _selection_changed(self):
        if self.busy or not self.follow:
            return
        entities = entities_from_selection(self.asm)
        same = [(e[0].Name, e[1]) for e in entities] == [(e[0].Name, e[1]) for e in self.entities]
        if same:
            return
        if self.joint is not None:
            self._discard()
        self.entities = entities
        self.flipped = False
        self.value = {"distance": None, "angle": None}
        if self.key is not None and len(entities) == 2:
            keys = applicable([e[2] for e in entities])
            if self.key not in keys:
                self.key = None
        self._try_build()
        self._refresh()

    def _ready(self):
        return len(self.entities) == 2 and self.entities[0][0] is not self.entities[1][0]

    def _try_build(self):
        if not self._ready():
            return
        keys = applicable([e[2] for e in self.entities])
        if not keys:
            return
        if self.key not in keys:
            self.key = keys[0]
        self._build_joint()

    def _build_joint(self, label=None):
        key = self.key
        if key in ("distance", "angle") and self.value[key] is None:
            self.value[key] = current_value(key, [e[3] for e in self.entities])
        self.busy = True
        problem = ""
        try:
            if not self.editing:
                self.doc.openTransaction(LABEL)
            self.joint = create_joint(self.asm, key, [(e[0], e[1]) for e in self.entities],
                                      self.value.get(key), label)
            if self.flipped and key in FLIPPABLE:
                self.joint.Proxy.flipOnePart(self.joint)
            if solve(self.asm) != 0:
                problem = "FreeCAD no puede resolver esta relación (choca con otra o la pieza está fija)."
            self.doc.recompute()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Relación de posición:\n%s\n" % traceback.format_exc())
            problem = "No se pudo crear la relación."
        finally:
            self.busy = False
        self._hint([e[2] for e in self.entities], problem)

    def _discard(self):
        """Saca la relación pendiente (en edición: la reemplazada se recupera al cancelar)."""
        self.busy = True
        try:
            if self.editing:
                if self.joint is not None and self.doc.getObject(self.joint.Name) is not None:
                    self.doc.removeObject(self.joint.Name)
            elif self.doc.HasPendingTransaction:
                self.doc.abortTransaction()
        finally:
            self.joint = None
            self.busy = False

    # --- botones

    def set_key(self, key):
        if not self._ready() or key == self.key and self.joint is not None:
            self._refresh()
            return
        label = self.joint.Label if (self.editing and self.joint is not None) else None
        if label and key != self.key:
            label = next_label({j.Label for j in joints_of(self.asm) if j is not self.joint}, MATES[key][0])
        self._discard()
        self.key = key
        self._build_joint(label)
        self._refresh()

    def set_flipped(self, flipped):
        if self.joint is None or flipped == self.flipped:
            self._refresh()
            return
        self.flipped = flipped
        try:
            self.joint.Proxy.flipOnePart(self.joint)
            solve(self.asm)
            self.doc.recompute()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Alineación:\n%s\n" % traceback.format_exc())
        self._refresh()

    def _value(self, key, value):
        self.value[key] = value
        if self.joint is None or self.key != key:
            return
        try:
            setattr(self.joint, "Distance" if key == "distance" else "Angle", value)
            problem = "" if solve(self.asm) == 0 else "FreeCAD no puede resolver ese valor."
            self.doc.recompute()
            self._hint([e[2] for e in self.entities], problem)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Valor de la relación:\n%s\n" % traceback.format_exc())

    def _limit(self, enable, prop, spin, on, value=None):
        if self.joint is None:
            return
        try:
            setattr(self.joint, enable, bool(on))
            if value is not None:
                setattr(self.joint, prop, value)
            elif spin is not None and on:
                setattr(self.joint, prop, spin.value())
            solve(self.asm)
            self.doc.recompute()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Límites:\n%s\n" % traceback.format_exc())

    def remove_current(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.entities):
            comp, sub = self.entities[row][0], self.entities[row][1]
            self._start_following()
            try:
                FreeCADGui.Selection.removeSelection(self.doc.Name, self.asm.Name, "%s.%s" % (comp.Name, sub))
            except Exception:
                pass
            self.schedule()

    def clear(self):
        self._start_following()
        FreeCADGui.Selection.clearSelection()
        self.schedule()

    def _start_following(self):
        """En edición, borrar las selecciones deja elegir entidades nuevas."""
        if not self.follow:
            self.follow = True
            self._discard()
            self.entities = []

    def add(self):
        """✓: confirma la pendiente y deja el panel listo para la siguiente."""
        if self.joint is None or self.editing:
            return
        self.busy = True
        try:
            self.doc.commitTransaction()
            self.added.append(self.joint.Label)
            self.joint = None
            self.entities = []
            self.key = None
            self.flipped = False
            self.value = {"distance": None, "angle": None}
            FreeCADGui.Selection.clearSelection()
        finally:
            self.busy = False
        self._refresh()

    # --- diálogo de tareas

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel

    def accept(self):
        self.busy = True
        if self.joint is not None and not self._ready():
            self._discard()
        if self.doc.HasPendingTransaction:
            self.doc.commitTransaction()
        self._close()
        return True

    def reject(self):
        self.busy = True
        if self.editing:
            if self.doc.HasPendingTransaction:
                self.doc.abortTransaction()
        else:
            self._discard()
        self._close()
        return True

    def _close(self):
        global _panel
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        try:
            FreeCADGui.Selection.setSelectionStyle(FreeCADGui.Selection.SelectionStyle.NormalSelection)
        except Exception:
            pass
        try:
            self.asm.recompute(True)
        except Exception:
            pass
        FreeCADGui.Control.closeDialog()
        FreeCADGui.Selection.clearSelection()
        _panel = None


def start(key=None, joint=None):
    """Abre el panel (key: relación elegida de antemano, joint: relación a editar)."""
    global _panel
    asm = ensure_active()
    if asm is None:
        FreeCAD.Console.PrintWarning("[SWUI] Relación de posición: abrí o activá un ensamblaje primero.\n")
        return None
    try:
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
    except Exception:
        pass
    try:
        _panel = MatePanel(asm, key, joint)
        FreeCADGui.Control.showDialog(_panel)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Panel de relaciones:\n%s\n" % traceback.format_exc())
        _panel = None
    return _panel


# --- Doble clic sobre una relación y botones del panel del original ---------------


def _wrap_double_click():
    try:
        jo, _ua = _assembly_modules()
    except Exception:
        return
    vp = jo.ViewProviderJoint
    if getattr(vp.doubleClicked, "_swui_mates", False):
        return
    original = vp.doubleClicked

    def doubleClicked(self, vobj, _original=original):
        try:
            joint = vobj.Object
            if key_of(joint) is not None and _in_swui():
                # cerrar sin cancelar: cancelar deshacía también lo pendiente de antes (al salir de
                # un croquis del que dependen piezas, FreeCAD las vuelve a mostrar; cancelando,
                # quedaban ocultas: visto 2026-10-30 con el croquis de un taladro de ensamblaje)
                FreeCAD.closeActiveTransaction()
                asm = joint.Proxy.getAssembly(joint)
                if asm is not None and active_assembly() != asm:
                    vobj.Document.setEdit(asm)
                if start(joint=joint) is not None:
                    return True
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Editar relación:\n%s\n" % traceback.format_exc())
        return _original(self, vobj)

    doubleClicked._swui_mates = True
    vp.doubleClicked = doubleClicked


# claves del panel del original -> las nuestras (las demás siguen con el diálogo de FreeCAD)
ORIGINAL_KEYS = {"coincident": "coincident", "parallel": "parallel", "perpendicular": "perpendicular",
                 "concentric": "concentric", "distance": "distance", "angle": "angle", "tangent": "tangent"}


def _wrap_original_panel():
    from swui import assembly_mates as am

    if getattr(am.run_mate, "_swui_mates", False):
        return
    # (el test lee las tuplas "Comando", "texto" como botones de la cinta: esta va armada aparte)
    am.MATES.setdefault("tangent", tuple(["Assembly_CreateJointDistance", "Tangente", "sketch/rel_tangent"]))
    original_run, original_suggest = am.run_mate, am.suggest

    def run_mate(key, _original=original_run):
        if key in ORIGINAL_KEYS and _in_swui():
            start(ORIGINAL_KEYS[key])
            return
        _original(key)

    def suggest(elements, _original=original_suggest):
        keys = _original(elements)
        if len(elements) == 2 and "tangent" in applicable([e.kind for e in elements]) and "tangent" not in keys:
            keys = list(keys)
            keys.insert(1 if keys and keys[0] == "concentric" else 0, "tangent")
            if "coincident" in keys and "plane" in {e.kind for e in elements}:
                keys.remove("coincident")  # cara plana con cilindro: coincidente no existe en SW
        return keys

    run_mate._swui_mates = suggest._swui_mates = True
    am.run_mate, am.suggest = run_mate, suggest


def _in_swui():
    try:
        from swui.fork import feature_tree

        return feature_tree._in_workbench()
    except Exception:
        return True


# --- Clic derecho: Fijar / Flotar / Ver relaciones ----------------------------------


def selected_component():
    """(ensamblaje, componente) si lo elegido es un componente del ensamblaje activo."""
    asm = active_assembly()
    if asm is None:
        return None, None
    try:
        sels = FreeCADGui.Selection.getSelectionEx("", 0)
    except Exception:
        return asm, None
    _jo, ua = _assembly_modules()
    for sel in sels:
        subs = list(sel.SubElementNames or []) or [""]
        for sub in subs:
            try:
                comp, _rel = ua.getComponentReference(asm, sel.Object, sub)
            except Exception:
                comp = None
            if comp is None and sel.Object in asm.Group and hasattr(sel.Object, "LinkedObject"):
                comp = sel.Object
            if comp is not None and comp.TypeId != "App::FeaturePython":
                return asm, comp
    return asm, None


class _CompCommand:
    menu = ""
    tip = ""

    def GetResources(self):
        return {"MenuText": self.menu, "ToolTip": self.tip}

    def IsActive(self):
        return self.applies()

    def applies(self):
        asm, comp = selected_component()
        return comp is not None


class _FixCommand(_CompCommand):
    menu = "Fijar"
    tip = "Fija el componente en su lugar (como Fijar de SW)"

    def applies(self):
        asm, comp = selected_component()
        return comp is not None and grounded_joint(asm, comp) is None

    def Activated(self):
        FreeCADGui.runCommand("Assembly_ToggleGrounded")


class _FloatCommand(_CompCommand):
    menu = "Flotar"
    tip = "Libera el componente fijo para que se mueva con sus relaciones (como Flotar de SW)"

    def applies(self):
        asm, comp = selected_component()
        return comp is not None and grounded_joint(asm, comp) is not None

    def Activated(self):
        FreeCADGui.runCommand("Assembly_ToggleGrounded")


class _ViewMatesCommand(_CompCommand):
    menu = "Ver relaciones de posición"
    tip = "Selecciona en el árbol las relaciones de posición del componente"

    def Activated(self):
        asm, comp = selected_component()
        if comp is None:
            return
        found = mates_of(asm, comp)
        FreeCADGui.Selection.clearSelection()
        for j in found:
            FreeCADGui.Selection.addSelection(j)
        if not found:
            FreeCAD.Console.PrintMessage("[SWUI] %s no tiene relaciones de posición.\n" % comp.Label)


class _MateCommand:
    def GetResources(self):
        from swui import paths

        return {"MenuText": "Relación de posición",
                "ToolTip": "Relaciones de posición como SW: elegí dos entidades, revisá y Agregar; "
                           "el panel queda abierto para la siguiente",
                "Pixmap": paths.icon("sketch/m_coincident") or ""}

    def IsActive(self):
        doc = FreeCAD.ActiveDocument
        return doc is not None and bool(_assemblies(doc))

    def Activated(self):
        start()


class _Manipulator:
    def modifyContextMenu(self, recipient):
        try:
            if recipient not in ("Tree", "View") or not _in_swui():
                return []
            asm, comp = selected_component()
            if comp is None:
                return []
            commands = [FLOAT if grounded_joint(asm, comp) is not None else FIX, VIEW_MATES, "Separator"]
            anchor = "Std_Placement" if recipient == "Tree" else "Std_ViewFitAll"
            return [{"insert": c, "menuItem": anchor} for c in commands]
        except Exception:
            return []


# --- Cinta ----------------------------------------------------------------


def install_ribbon():
    """Botón grande 'Relación de posición' y las uniones de FreeCAD en un menú al lado."""
    from swui import ribbon_layout

    groups = ribbon_layout.BAUGRUPPE[1]
    for group in groups:
        if any(isinstance(e, tuple) and e[0] == COMMAND for e in group):
            return
    for gi, group in enumerate(groups):
        natives = [e for e in group if isinstance(e, tuple) and e[0].startswith("Assembly_CreateJoint")]
        if not natives:
            continue
        rest = [e for e in group if e not in natives]
        flyouts = [e for e in rest if isinstance(e, dict) and "flyout" in e]
        first = flyouts[0]["flyout"] if flyouts else []
        merged = {"flyout": natives + [e for e in first if e not in natives]}
        groups[gi] = [("SWUI_Mate", "Relación de\nposición", {"svg": "sketch/m_coincident"}), merged] + flyouts[1:]
        return


def install():
    global _installed
    if _installed:
        return
    for name, cmd in ((COMMAND, _MateCommand()), (FIX, _FixCommand()), (FLOAT, _FloatCommand()),
                      (VIEW_MATES, _ViewMatesCommand())):
        try:
            FreeCADGui.addCommand(name, cmd)
        except Exception:
            pass  # ya registrado
    install_ribbon()
    try:
        _wrap_original_panel()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Panel de relaciones del original:\n%s\n" % traceback.format_exc())
    _wrap_double_click()
    if hasattr(FreeCADGui, "addWorkbenchManipulator"):
        FreeCADGui.addWorkbenchManipulator(_Manipulator())
    _installed = True
