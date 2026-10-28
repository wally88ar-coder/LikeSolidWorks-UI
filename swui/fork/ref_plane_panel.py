# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Panel de Plano de referencia como el PropertyManager de SOLIDWORKS 2018.

Primera, segunda y tercera referencia; cada una con sus relaciones según lo
que se tocó (como SW): un plano o cara plana -> Coincidente, Paralelo,
Perpendicular, Distancia (con Invertir), Ángulo, Punto medio; una arista o eje
-> Coincidente, Perpendicular; un vértice -> Coincidente; una cara cilíndrica
-> Tangente. Arriba, el estado: "Totalmente definido" o qué falta.

Por debajo es el plano de referencia de FreeCAD (PartDesign::Plane) con su
"adjunción" (MapMode + AttachmentSupport + AttachmentOffset). resolve() pasa
las referencias y relaciones de SW a eso:
  plano + Coincidente/Distancia      -> FlatFace (desfase en Z)
  plano Paralelo + vértice           -> ParallelPlane / TangentPlane
  plano Ángulo/Perpendicular + arista-> FlatFace + giro alrededor de la arista
                                        (calculado al aceptar: la arista queda
                                        fija dentro del marco de la cara)
  plano + plano, Punto medio         -> FlatFace + mitad de la distancia
                                        (calculada: no sigue si se mueve la 2.ª)
  arista Perpendicular (+ vértice)   -> NormalToEdge
  arista + vértice Coincidentes      -> ThreePointsPlane
  tres vértices                      -> ThreePointsPlane
  cilindro Tangente + vértice        -> TangentPlane
Lo elegido en el panel se guarda en la propiedad SWUI_PlaneSpec (texto JSON;
nombre estable: queda en los archivos) para volver a mostrarlo al editar.
No está: "Número de planos" de SW (varios planos de una vez) y "Proyectar".
"""

import json
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtWidgets
from swui.fork import dress_up_panel as dp

PLANE = "PartDesign::Plane"
SPEC_PROP = "SWUI_PlaneSpec"  # NO CAMBIAR: queda en los archivos
PLANE_TYPES = ("App::Plane", "PartDesign::Plane", "Part::DatumPlane")
LINE_TYPES = ("App::Line", "PartDesign::Line", "Part::DatumLine")
POINT_TYPES = ("App::Point", "PartDesign::Point", "Part::DatumPoint")

# Relaciones de SW (clave interna -> texto del botón)
COINCIDENT, PARALLEL, PERPENDICULAR, DISTANCE, ANGLE, MIDPLANE, TANGENT = (
    "coincident", "parallel", "perpendicular", "distance", "angle", "midplane", "tangent")
TEXTS = {COINCIDENT: "Coincidente", PARALLEL: "Paralelo", PERPENDICULAR: "Perpendicular",
         DISTANCE: "Distancia", ANGLE: "Ángulo", MIDPLANE: "Punto medio", TANGENT: "Tangente"}
# Qué relaciones se ofrecen según lo que se tocó
OFFERS = {
    "plane": (COINCIDENT, PARALLEL, PERPENDICULAR, DISTANCE, ANGLE, MIDPLANE),
    "edge": (COINCIDENT, PERPENDICULAR),
    "vertex": (COINCIDENT,),
    "cyl": (TANGENT,),
}
DEFAULT = {"plane": DISTANCE, "edge": COINCIDENT, "vertex": COINCIDENT, "cyl": TANGENT}
DEFAULT_DISTANCE = 10.0
DEFAULT_ANGLE = 45.0
OK_COLOR = "#007A00"


# --- Sin FreeCAD (probables en el test) ---------------------------------


def resolve(items):
    """
    items: [(tipo, relación)] por referencia, en orden ("plane", "distance")...
    Devuelve (modo, orden de referencias, extra) o None si falta algo:
      extra = "offset" (distancia), "angle" (giro alrededor de la arista), "mid" (punto medio).
    """
    kinds = [k for k, _r in items]
    rels = [r for _k, r in items]
    n = len(items)
    pos = {k: [i for i, kk in enumerate(kinds) if kk == k] for k in ("plane", "edge", "vertex", "cyl")}
    if n == 1:
        if kinds[0] == "plane" and rels[0] in (COINCIDENT, DISTANCE):
            return "FlatFace", [0], "offset"
        if kinds[0] == "edge" and rels[0] == PERPENDICULAR:
            return "NormalToEdge", [0], None
        return None
    if n == 2:
        if len(pos["plane"]) == 1 and len(pos["vertex"]) == 1:
            p, v = pos["plane"][0], pos["vertex"][0]
            if rels[p] == PARALLEL:
                return "ParallelPlane", [p, v], None
        if len(pos["plane"]) == 1 and len(pos["edge"]) == 1:
            p, e = pos["plane"][0], pos["edge"][0]
            if rels[p] in (ANGLE, PERPENDICULAR) and rels[e] == COINCIDENT:
                return "FlatFace", [p, e], "angle"
        if len(pos["plane"]) == 2 and rels[0] == MIDPLANE and rels[1] == MIDPLANE:
            return "FlatFace", [0, 1], "mid"
        if len(pos["edge"]) == 1 and len(pos["vertex"]) == 1:
            e, v = pos["edge"][0], pos["vertex"][0]
            if rels[e] == PERPENDICULAR:
                return "NormalToEdge", [e, v], None
            if rels[e] == COINCIDENT:
                return "ThreePointsPlane", [e, v], None
        if len(pos["cyl"]) == 1 and len(pos["vertex"]) == 1:
            return "TangentPlane", [pos["cyl"][0], pos["vertex"][0]], None
        return None
    if n == 3 and len(pos["vertex"]) == 3:
        return "ThreePointsPlane", [0, 1, 2], None
    return None


def offer(kind, previous_rels=()):
    """Relaciones que se ofrecen para una referencia, y la que se elige sola."""
    out = list(OFFERS.get(kind, ()))
    default = DEFAULT.get(kind)
    if kind == "plane" and MIDPLANE in previous_rels:
        default = MIDPLANE  # segundo plano de un Punto medio
    elif kind == "plane" and previous_rels:
        default = COINCIDENT if PARALLEL not in previous_rels else PARALLEL
    return out, default


# Modos de FreeCAD que sirven de reemplazo si el primero no aplica a estas referencias
ALTERNATIVES = {"ParallelPlane": ("ParallelPlane", "TangentPlane")}


def pick_mode(mode, allowed):
    """El modo pedido o su reemplazo, entre los que FreeCAD acepta (None si ninguno)."""
    for m in ALTERNATIVES.get(mode, (mode,)):
        if m in allowed:
            return m
    return None


# --- Geometría ----------------------------------------------------------


def element(obj, sub):
    """
    Cara/arista/vértice tocado. En un ensamblaje el subnombre pasa por el componente
    ('Body.Face7' de un vínculo): ahí se toma con getSubObject (coordenadas del ensamblaje).
    """
    if "." in sub:
        try:
            return obj.getSubObject(sub)
        except Exception:
            return None
    return dp._element(obj.Shape, sub)


def leaf(sub):
    return sub.rsplit(".", 1)[-1]


def kind_of(obj, sub):
    """Qué es lo tocado: 'plane', 'edge', 'vertex', 'cyl' o None."""
    if not sub:
        if obj.TypeId in PLANE_TYPES:
            return "plane"
        if obj.TypeId in LINE_TYPES:
            return "edge"
        if obj.TypeId in POINT_TYPES:
            return "vertex"
        return None
    el = element(obj, sub)
    if el is None:
        return None
    if leaf(sub).startswith("Vertex"):
        return "vertex"
    if leaf(sub).startswith("Edge"):
        return "edge"
    surf = type(getattr(el, "Surface", None)).__name__
    if surf == "Plane":
        return "plane"
    if surf in ("Cylinder", "Cone"):
        return "cyl"
    return None


def _plane_geo(obj, sub):
    """(punto, normal) de un plano/cara, en coordenadas del cuerpo."""
    if sub:
        face = element(obj, sub)
        n = face.normalAt(*face.Surface.parameter(face.CenterOfMass))
        return face.CenterOfMass, n
    pl = obj.Placement
    return pl.Base, pl.Rotation.multVec(FreeCAD.Vector(0, 0, 1))


def _line_geo(obj, sub):
    """(punto, dirección) de una arista recta o eje."""
    if sub:
        edge = element(obj, sub)
    elif hasattr(obj, "Shape") and not obj.Shape.isNull() and obj.Shape.Edges:
        edge = obj.Shape.Edges[0]
    else:
        pl = obj.Placement
        return pl.Base, pl.Rotation.multVec(FreeCAD.Vector(1, 0, 0))
    a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
    return a, (b - a)


def angle_offset(frame, point, direction, degrees):
    """
    Desfase (en el marco de la cara) para un plano que pasa por la arista
    (point, direction) formando 'degrees' con la cara. None si la arista no es
    paralela a la cara.
    """
    inv = frame.inverse()
    p = inv.multVec(point)
    d = inv.Rotation.multVec(direction)
    if d.Length < 1e-9 or abs(d.normalize().z) > 1e-6:
        return None
    rot = FreeCAD.Rotation(d, degrees)
    base = p + rot.multVec(FreeCAD.Vector(0, 0, p.z) - p)
    return FreeCAD.Placement(base, rot)


def _allowed(support):
    """Modos de plano que FreeCAD acepta para estas referencias (su propio 'sugerir modos')."""
    import Part

    try:
        engine = Part.AttachEngine("Attacher::AttachEnginePlane")
        engine.References = support
        return engine.suggestModes().get("allApplicableModes", [])
    except Exception:
        return []


# --- Ubicar el plano (lo usan el panel y el recálculo al reconstruir) ---

# Si una versión futura de FreeCAD trae estos modos, se usan los de FreeCAD (nombres probables:
# no existen en 1.1.4 ni hay pedido abierto al 2026-10-27; revisar al actualizar).
NATIVE_MODES = {"angle": ("AngleToFace", "PlaneAtAngle"), "mid": ("MidPlane", "Midplane", "MiddlePlane")}


def _entry_ref(doc, entry):
    ref = entry.get("ref")
    if ref is None:
        obj = doc.getObject(entry.get("obj", ""))
        ref = (obj, entry.get("sub", "")) if obj is not None else None
    return ref


def _frame(obj):
    """Marco de la adjunción sin el desfase (Placement = marco * desfase)."""
    return obj.Placement.multiply(obj.AttachmentOffset.inverse())


def moving_offset(obj, extra, entries, refs):
    """Desfase de un plano En ángulo / Punto medio según la geometría de ahora (o un problema)."""
    first = entries[0]
    frame = _frame(obj)
    if extra == "angle":
        deg = 90.0 if first["rel"] == PERPENDICULAR else first["value"]
        if first.get("flip"):
            deg = -deg
        p, d = _line_geo(*refs[1])
        offset = angle_offset(frame, p, d, deg)
        return offset if offset is not None else "La arista tiene que ser paralela al plano para el ángulo."
    p2, _n2 = _plane_geo(*refs[1])
    z = frame.inverse().multVec(p2).z / 2.0
    return FreeCAD.Placement(FreeCAD.Vector(0, 0, z), FreeCAD.Rotation())


def place(obj, entries):
    """
    Ubicar el plano según lo elegido. entries: [{ref|obj+sub, kind, rel, value, flip}].
    Devuelve "" o el problema.
    """
    plan = resolve([(e["kind"], e["rel"]) for e in entries])
    if plan is None:
        return "Faltan referencias o relaciones para ubicar el plano."
    mode, order, extra = plan
    refs = [_entry_ref(obj.Document, entries[i]) for i in order]
    if None in refs:
        return "Una referencia ya no existe."
    ordered = [entries[i] for i in order]
    allowed_all = _allowed(refs)
    native = next((m for m in NATIVE_MODES.get(extra, ()) if m in allowed_all), None)
    if native:  # FreeCAD ya lo sabe hacer: usar lo suyo (sigue la pieza sin el addon)
        obj.AttachmentSupport = refs
        obj.MapMode = native
        return ""
    support = [refs[0]] if extra in ("angle", "mid") else refs
    mode = pick_mode(mode, _allowed(support))
    if mode is None:
        return "FreeCAD no acepta esa combinación de referencias para un plano."
    obj.AttachmentSupport = support
    obj.MapMode = mode
    offset = FreeCAD.Placement()
    first = ordered[0]
    if extra == "offset" and first["rel"] == DISTANCE:
        z = first["value"] * (-1 if first.get("flip") else 1)
        offset = FreeCAD.Placement(FreeCAD.Vector(0, 0, z), FreeCAD.Rotation())
    elif extra in ("angle", "mid"):
        obj.AttachmentOffset = FreeCAD.Placement()
        obj.recompute()
        offset = moving_offset(obj, extra, ordered, refs)
        if isinstance(offset, str):
            return offset
    obj.AttachmentOffset = offset
    return ""


# --- Recalcular al reconstruir (En ángulo / Punto medio siguen a la pieza) ---

TOL = 1e-7
_resync = {"busy": False}


def _same(a, b):
    return (a.Base - b.Base).Length < TOL and a.Rotation.isSame(b.Rotation, TOL)


def resync(doc):
    """
    Planos En ángulo / Punto medio hechos con el panel: si la arista o la segunda cara se
    movieron, nuevo desfase. Devuelve los planos cambiados.
    """
    changed = []
    for obj in doc.Objects:
        if obj.TypeId != PLANE or SPEC_PROP not in obj.PropertiesList or obj.MapMode == "Deactivated":
            continue
        try:
            entries = json.loads(getattr(obj, SPEC_PROP) or "[]")
            plan = resolve([(e["kind"], e["rel"]) for e in entries])
            if plan is None or plan[2] not in ("angle", "mid") or obj.MapMode in sum(NATIVE_MODES.values(), ()):
                continue
            mode, order, extra = plan
            refs = [_entry_ref(doc, entries[i]) for i in order]
            if None in refs:
                continue
            offset = moving_offset(obj, extra, [entries[i] for i in order], refs)
            if isinstance(offset, str) or _same(offset, obj.AttachmentOffset):
                continue
            obj.AttachmentOffset = offset
            changed.append(obj)
        except Exception:
            FreeCAD.Console.PrintWarning("[SWUI fork] Plano %s: no se pudo recalcular.\n" % obj.Label)
    return changed


def _after_recompute(doc_name):
    if _resync["busy"] or dp._state.get("panel") is not None:
        return
    try:
        doc = FreeCAD.getDocument(doc_name)
    except Exception:
        return
    _resync["busy"] = True
    try:
        for _i in range(2):  # una pasada más para lo que cuelga del plano (y otra si encadena)
            if not resync(doc):
                break
            doc.recompute()
    finally:
        _resync["busy"] = False


class _RecomputeObserver:
    def slotRecomputedDocument(self, doc):
        if _resync["busy"]:
            return
        from swui.compat import QtCore

        name = doc.Name
        QtCore.QTimer.singleShot(0, lambda: _after_recompute(name))


# --- Panel -------------------------------------------------------------


class _RefGroup:
    """Una referencia de SW: casilla, botones de relación, valor e Invertir."""

    def __init__(self, panel, n):
        self.panel = panel
        self.ref = None  # (obj, sub)
        self.kind = None
        self.rel = None
        self.box = QtWidgets.QWidget()
        self.box.setWindowTitle(("Primera", "Segunda", "Tercera")[n] + " referencia")
        lay = QtWidgets.QVBoxLayout(self.box)
        self.field = dp.RefBox(panel._activate)
        self.field.setPlaceholderText("Plano, cara, arista, eje o vértice")
        lay.addWidget(self.field)
        self.buttons = {}
        grid = QtWidgets.QGridLayout()
        for i, rel in enumerate((COINCIDENT, PARALLEL, PERPENDICULAR, DISTANCE, ANGLE, MIDPLANE, TANGENT)):
            b = QtWidgets.QPushButton(TEXTS[rel])
            b.setCheckable(True)
            b.clicked.connect(lambda _c=False, r=rel: self.choose(r))
            grid.addWidget(b, i // 3, i % 3)
            self.buttons[rel] = b
        lay.addLayout(grid)
        form = QtWidgets.QFormLayout()
        self.value = dp._spin(DEFAULT_DISTANCE, " mm", 0.0, 1e6)
        self.value.valueChanged.connect(panel._changed)
        self.value_label = QtWidgets.QLabel("Distancia:")
        form.addRow(self.value_label, self.value)
        self.flip = QtWidgets.QCheckBox("Invertir")
        self.flip.toggled.connect(panel._changed)
        form.addRow(self.flip)
        lay.addLayout(form)
        self.update()

    def _before(self):
        groups = self.panel.groups
        return [g.rel for g in groups[:groups.index(self)] if g.ref] if self in groups else []

    def set(self, ref, kind, rel=None, value=None, flip=False):
        self.ref, self.kind = ref, kind
        offers, default = offer(kind, self._before()) if kind else ([], None)
        self.rel = rel if rel in offers else default
        if value is not None:
            self.value.blockSignals(True)
            self.value.setValue(value)
            self.value.blockSignals(False)
        self.flip.blockSignals(True)
        self.flip.setChecked(bool(flip))
        self.flip.blockSignals(False)
        self.update()

    def choose(self, rel):
        self.rel = rel
        if rel == ANGLE and self.value_label.text() != "Ángulo:":
            self.value.setValue(DEFAULT_ANGLE)
        elif rel == DISTANCE and self.value_label.text() != "Distancia:":
            self.value.setValue(DEFAULT_DISTANCE)
        self.update()
        self.panel._changed()

    def update(self):
        offers = offer(self.kind)[0] if self.kind else []
        for rel, b in self.buttons.items():
            b.setVisible(rel in offers)
            b.setChecked(rel == self.rel)
        angle = self.rel == ANGLE
        self.value_label.setText("Ángulo:" if angle else "Distancia:")
        self.value.setSuffix("°" if angle else " mm")
        for w in (self.value, self.value_label):
            w.setVisible(self.rel in (DISTANCE, ANGLE))
        self.flip.setVisible(self.rel in (DISTANCE, ANGLE))
        self.field.setText(self.panel._ref_text(self.ref) if self.ref else "")

    def spec(self):
        if not self.ref:
            return None
        return {"obj": self.ref[0].Name, "sub": self.ref[1], "kind": self.kind, "rel": self.rel,
                "value": self.value.value(), "flip": self.flip.isChecked()}


class PlanePanel(dp.SwPanel):
    TRANSACTION = "Editar plano"
    FAIL = "FreeCAD no puede ubicar el plano con estas referencias."
    NOTHING = "Elegí las referencias del plano."

    def _base(self):
        return None

    def _remember_visibility(self):
        return {}  # un plano no cambia lo que se ve de la pieza

    def _tip_or_self(self):
        return True

    def _build(self):
        self.groups = []
        self.groups = [_RefGroup(self, i) for i in range(3)]
        self.status = QtWidgets.QLabel()
        self.status.setWordWrap(True)
        head = QtWidgets.QWidget()
        head.setWindowTitle("Mensaje")
        hl = QtWidgets.QVBoxLayout(head)
        hl.addWidget(self.status)
        hl.addWidget(self._message_label())
        self.form = [head] + [g.box for g in self.groups]
        self._load()
        self._activate(next((g.field for g in self.groups if not g.ref), self.groups[0].field))

    def _activate(self, widget):
        self.active = widget
        for g in self.groups:
            g.field.setStyleSheet(dp.ACTIVE_QSS if g.field is widget else "")

    def _ref_text(self, ref):
        obj, sub = ref
        if not sub:
            return obj.Label
        kind = {"F": "Cara", "E": "Arista", "V": "Vértice"}.get(sub[0], sub)
        return "%s (%s)" % (kind, obj.Label)

    def _load(self):
        """Lo guardado por este panel (SWUI_PlaneSpec) o, si no hay, lo que tenga el plano."""
        obj = self.obj
        spec = []
        try:
            spec = json.loads(getattr(obj, SPEC_PROP, "") or "[]")
        except Exception:
            spec = []
        if spec:
            for g, s in zip(self.groups, spec):
                ref_obj = self.doc.getObject(s.get("obj", ""))
                if ref_obj is None:
                    continue
                g.set((ref_obj, s.get("sub", "")), s.get("kind"), s.get("rel"), s.get("value"), s.get("flip"))
            return
        try:
            support = list(obj.AttachmentSupport)
        except Exception:
            support = []
        for g, (ref_obj, subs) in zip(self.groups, support):
            for sub in (subs if isinstance(subs, (list, tuple)) else [subs]) or [""]:
                kind = kind_of(ref_obj, sub)
                if kind:
                    rel = None
                    if kind == "plane" and obj.MapMode == "FlatFace":
                        rel = DISTANCE if abs(obj.AttachmentOffset.Base.z) > 1e-9 else COINCIDENT
                    g.set((ref_obj, sub), kind, rel, abs(obj.AttachmentOffset.Base.z) or None,
                          obj.AttachmentOffset.Base.z < 0)
                break

    # --- selección

    def _pick(self, obj, sub):
        if obj == self.obj:
            return False
        if sub and not leaf(sub).startswith(("Face", "Edge", "Vertex")):
            return False
        kind = kind_of(obj, sub)
        if kind is None:
            return False
        group = next((g for g in self.groups if g.field is self.active), None) or \
            next((g for g in self.groups if not g.ref), None)
        if group is None:
            return False
        if group.ref and group.ref[0] == obj and group.ref[1] == sub:
            group.set(None, None)  # otro clic en lo mismo: se saca
        else:
            group.set((obj, sub), kind)
            nxt = next((g for g in self.groups if not g.ref), None)
            if nxt is not None:
                self._activate(nxt.field)
        for g in self.groups:
            g.update()
        return True

    def _refresh(self):
        for g in self.groups:
            g.update()

    # --- aplicar

    def _items(self):
        return [(g.kind, g.rel) for g in self.groups if g.ref]

    def _ready(self):
        return resolve(self._items()) is not None

    def _nothing(self):
        return not any(g.ref for g in self.groups)

    def _apply(self):
        entries = [g.spec() for g in self.groups if g.ref]
        if resolve([(e["kind"], e["rel"]) for e in entries]) is None:
            self._status(False)
            return "" if not entries else "Faltan referencias o relaciones para ubicar el plano."
        problem = place(self.obj, entries)
        self._status(not problem)
        if not problem:
            self._save_spec()
        return problem

    def _save_spec(self):
        obj = self.obj
        if SPEC_PROP not in obj.PropertiesList:
            obj.addProperty("App::PropertyString", SPEC_PROP, "SWUI",
                            "Referencias y relaciones del panel SW (para volver a editarlo)")
            obj.setEditorMode(SPEC_PROP, 2)  # oculta en Datos
        text = json.dumps([g.spec() for g in self.groups if g.ref])
        if getattr(obj, SPEC_PROP) != text:
            setattr(obj, SPEC_PROP, text)

    def _status(self, ok):
        if ok:
            self.status.setText("Totalmente definido")
            self.status.setStyleSheet("color: %s;" % OK_COLOR)
        else:
            self.status.setText("Elegí referencias y relaciones hasta que el plano quede definido.")
            self.status.setStyleSheet("")

    def _overlays(self, base, result):
        shapes = []
        for g in self.groups:
            if g.ref and g.ref[1]:
                try:
                    shapes.append(dp._global_shape(g.ref[0]).getElement(g.ref[1]))
                except Exception:
                    pass
        return [dp._lines_node(shapes, dp.PICKED_COLOR, dp.LINE_WIDTH)] if shapes else []


_observer = None


def install():
    global _observer
    dp.PANELS[PLANE] = PlanePanel
    if _observer is None:
        _observer = _RecomputeObserver()
        FreeCAD.addDocumentObserver(_observer)
