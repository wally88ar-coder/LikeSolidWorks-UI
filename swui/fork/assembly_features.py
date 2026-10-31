# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Operaciones de ensamblaje como SW 2018 (fase 5, etapa 4): Asistente para taladro y Extruir
corte que agujerean varias piezas de una vez, atados a un croquis del ensamblaje.

Flujo como SW: se elige la cara plana en el ensamblaje, se abre un croquis ahí (posiciones de
los agujeros o el perfil del corte), al salir del croquis el panel muestra el tipo de taladro (el
mismo de la fase 2) o la profundidad del corte, y la lista "Piezas afectadas" (arranca con las
piezas que el agujero o el corte atraviesan; un clic en una pieza la suma o la saca).

Por debajo, como "Propagar operación a piezas" de SW: en cada pieza afectada, dentro de su
Cuerpo, un SubShapeBinder del croquis del ensamblaje (posición = inversa de la del componente)
y un Taladro (PartDesign::Hole) o Vaciado (PartDesign::Pocket) nativo con ese perfil. El agujero
queda en la pieza (planos, DXF) y sigue al croquis. El croquis del ensamblaje queda suelto
(apoyado en la cara de una pieza que se agujerea sería un ciclo). Si la pieza se mueve en el
ensamblaje, un observador pone al día la posición del binder (decisión del usuario, 2026-10-27).
Los datos de cada operación van en un App::VarSet del ensamblaje (SWUI_AsmFeature).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

HOLE_CMD = "SWUI_AssemblyHole"
CUT_CMD = "SWUI_AssemblyCut"
KIND = "SWUI_AsmFeature"  # "hole" / "cut" en el VarSet (nombre estable)
SKETCH = "SWUI_Sketch"
ENTRIES = "SWUI_Entries"  # "componente|documento|binder|operación" por pieza
BINDER_MARK = "SWUI_AsmBinder"  # en el binder dentro de la pieza: "<documento del ensamblaje>"
TITLES = {"hole": "TaladroEnsamblaje", "cut": "CorteEnsamblaje"}
LABELS = {"hole": "Asistente para taladro (ensamblaje)", "cut": "Extruir corte (ensamblaje)"}
MARKER_RADIUS = 0.5  # círculo chico en cada punto de posición (el taladro toma círculos del binder)

_state = {"pending": None, "panel": None}
_installed = False


# --- Cuentas sin FreeCAD (probables en el test) ---------------------------------


def entry_text(link_name, doc_name, binder_name, feature_name):
    return "|".join((link_name, doc_name, binder_name, feature_name))


def parse_entry(text):
    parts = (text or "").split("|")
    return tuple(parts) if len(parts) == 4 else None


def unique_parts(links):
    """Una sola vez cada pieza (dos instancias del mismo archivo = una sola operación en la pieza)."""
    seen, out, repeated = set(), [], []
    for link in links:
        key = id(link.LinkedObject) if hasattr(link, "LinkedObject") else id(link)
        target = getattr(link, "LinkedObject", None)
        key = (target.Document.Name, target.Name) if target is not None else key
        if key in seen:
            repeated.append(link)
            continue
        seen.add(key)
        out.append(link)
    return out, repeated


def next_title(used, kind):
    n = 1
    while "%s%d" % (TITLES[kind], n) in used:
        n += 1
    return "%s%d" % (TITLES[kind], n)


# --- FreeCAD -------------------------------------------------------------------


def _components(asm):
    return [o for o in asm.Group if o.TypeId == "App::Link" and not getattr(o, "ElementCount", 0)
            and getattr(o, "LinkedObject", None) is not None
            and getattr(o.LinkedObject, "TypeId", "") == "PartDesign::Body"]


def sketch_normal(sk):
    return sk.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))


def centers(sk):
    """Centros globales: puntos y círculos del croquis (sin los de construcción)."""
    out = []
    for i, g in enumerate(sk.Geometry):
        try:
            if sk.getConstruction(i):
                continue
        except Exception:
            pass
        name = type(g).__name__
        if name == "Point":
            p = FreeCAD.Vector(g.X, g.Y, g.Z)
        elif name in ("Circle", "ArcOfCircle"):
            p = g.Center
        else:
            continue
        out.append(sk.Placement.multVec(p))
    return out


def hit_by_holes(asm, sk):
    """
    Componentes que atraviesan los ejes de los agujeros (hacia adentro de la cara). No se suma
    solo el que está metido en el eje (perno, pasador): el agujero pasa a cada pieza, y en uno de
    esos se comería el perno entero y sus relaciones quedarían sin caras (en SW el taladro queda en
    el ensamblaje y no lo rompe). Se puede sumar a mano con un clic.
    """
    import Part

    n = sketch_normal(sk)
    points = _unique(centers(sk))
    out = []
    for comp in _components(asm):
        try:
            shape = comp.Shape
            hits = [c for c in points
                    if Part.LineSegment(c + n * 0.01, c - n * 1e4).toShape().distToShape(shape)[0] < 1e-6]
            if hits and not all(_shaft_on_axis(shape, c, n) for c in hits):
                out.append(comp)
        except Exception:
            pass
    return out


def _shaft_on_axis(shape, center, n, tol=1e-3):
    """¿La pieza tiene un cilindro EXTERIOR (no un agujero) sobre el eje que pasa por center?"""
    for face in shape.Faces:
        surf = face.Surface
        if type(surf).__name__ != "Cylinder":
            continue
        axis = surf.Axis
        if axis.cross(n).Length > tol:
            continue
        gap = center - surf.Center
        if (gap - axis * gap.dot(axis)).Length > tol:
            continue
        u0, u1, v0, v1 = face.ParameterRange
        u, v = (u0 + u1) / 2, (v0 + v1) / 2
        p = face.valueAt(u, v)
        radial = p - surf.Center
        radial = radial - axis * radial.dot(axis)
        if face.normalAt(u, v).dot(radial) > 0:  # la normal sale del eje: el sólido está adentro
            return True
    return False


def _unique(points):
    out = []
    for p in points:
        if all((p - q).Length > 1e-6 for q in out):
            out.append(p)
    return out


def hit_by_cut(asm, sk, both=False):
    """Componentes que toca el perfil extruido hacia adentro (o a los dos lados)."""
    import Part

    try:
        faces = Part.makeFace(sk.Shape.Wires, "Part::FaceMakerBullseye")
    except Exception:
        return []
    n = sketch_normal(sk)
    tool = faces.extrude(n * -1e4)
    if both:
        tool = tool.fuse(faces.extrude(n * 1e4))
    out = []
    for comp in _components(asm):
        try:
            if tool.common(comp.Shape).Volume > 1e-6:
                out.append(comp)
        except Exception:
            pass
    return out


def add_markers(sk):
    """Un círculo chico atado a cada punto de posición (el taladro toma los círculos del binder)."""
    import Part
    import Sketcher

    points = []
    for i, g in enumerate(sk.Geometry):
        if type(g).__name__ == "Point" and not sk.getConstruction(i):
            points.append((i, FreeCAD.Vector(g.X, g.Y, g.Z)))
    circles = [g.Center for g in sk.Geometry if type(g).__name__ == "Circle"]
    added = 0
    for i, p in points:
        if any((p - c).Length < 1e-6 for c in circles):
            continue
        k = sk.addGeometry(Part.Circle(p, FreeCAD.Vector(0, 0, 1), MARKER_RADIUS), False)
        sk.addConstraint(Sketcher.Constraint("Coincident", k, 3, i, 1))
        sk.addConstraint(Sketcher.Constraint("Radius", k, MARKER_RADIUS))
        added += 1
    if added:
        sk.recompute()
    return added


def make_sketch(asm, comp, sub):
    """Croquis suelto del ensamblaje, ubicado sobre la cara elegida (no queda apoyado: sería un ciclo)."""
    sk = asm.newObject("Sketcher::SketchObject", "Croquis")
    sk.AttachmentSupport = [(comp, sub)]
    sk.MapMode = "FlatFace"
    sk.recompute()
    plc = sk.Placement
    sk.MapMode = "Deactivated"
    sk.AttachmentSupport = None
    sk.Placement = plc
    return sk


def add_to_part(link, sk, kind, title):
    """Binder del croquis + taladro / vaciado nativo en el Cuerpo de la pieza."""
    body = link.LinkedObject
    pdoc = body.Document
    if not pdoc.HasPendingTransaction:
        pdoc.openTransaction(LABELS[kind])
    binder = body.newObject("PartDesign::SubShapeBinder", "CroquisEnsamblaje")
    # No relativo y con la posición puesta a mano: el modo relativo de FreeCAD recalcula la
    # posición según el contexto y en un ensamblaje llegó a aplicarla dos veces (probado en 1.1.4)
    binder.Relative = False
    binder.Support = [(sk, ("",))]
    binder.Placement = binder_placement(link, sk)
    binder.addProperty("App::PropertyString", BINDER_MARK, "SW", "Operación de ensamblaje de LikeSolidWorks UI")
    setattr(binder, BINDER_MARK, sk.Document.Name)
    binder.Label = "Croquis de %s (%s)" % (title, sk.Document.Label)
    binder.Visibility = False
    if kind == "hole":
        feat = body.newObject("PartDesign::Hole", "Taladro")
        feat.Profile = binder
        from swui.fork import hole_panel

        hole_panel._defaults(feat)  # como el taladro de la fase 2: ISO, M6, agujero normal
        feat.DepthType = "ThroughAll"
    else:
        feat = body.newObject("PartDesign::Pocket", "Corte")
        feat.Profile = binder
        feat.Type = "ThroughAll"
    label = "%s (%s)" % (title, sk.Document.Label)
    feat.Label = label
    if FreeCAD.GuiUp:  # después del nombre SW que pone el original (naming.py, también con QTimer 0)
        QtCore.QTimer.singleShot(0, lambda d=pdoc.Name, n=feat.Name: _relabel(d, n, label))
    body.Tip = feat
    return binder, feat


def _relabel(doc_name, name, label):
    try:
        obj = FreeCAD.getDocument(doc_name).getObject(name)
        if obj is not None:
            obj.Label = label
    except Exception:
        pass


def binder_placement(link, sk):
    """Croquis del ensamblaje llevado a las coordenadas de la pieza."""
    return link.Placement.inverse().multiply(sk.Placement)


def remove_from_part(binder, feat):
    for obj in (feat, binder):
        try:
            body = obj.getParentGeoFeatureGroup()
            if body is not None:
                body.removeObject(obj)
            obj.Document.removeObject(obj.Name)
        except Exception:
            pass


def entries_of(v):
    """[(componente, binder, operación)] de una operación guardada."""
    out = []
    asm_doc = v.Document
    for text in getattr(v, ENTRIES, []) or []:
        e = parse_entry(text)
        if e is None:
            continue
        link_name, doc_name, binder_name, feat_name = e
        try:
            pdoc = FreeCAD.getDocument(doc_name)
        except Exception:
            continue
        link, binder, feat = asm_doc.getObject(link_name), pdoc.getObject(binder_name), pdoc.getObject(feat_name)
        if link is not None and binder is not None and feat is not None:
            out.append((link, binder, feat))
    return out


def record(asm, kind, sk, entries, data=None, title=None):
    v = data
    if v is None:
        v = asm.newObject("App::VarSet", "VarSet")
        v.Label = title or next_title({o.Label for o in asm.Document.Objects}, kind)
        v.addProperty("App::PropertyString", KIND, "SW", "Operación de ensamblaje de LikeSolidWorks UI")
        v.addProperty("App::PropertyLinkHidden", SKETCH, "SW", "Croquis del ensamblaje")
        v.addProperty("App::PropertyStringList", ENTRIES, "SW", "componente|documento|binder|operación")
        setattr(v, KIND, kind)
        setattr(v, SKETCH, sk)
    setattr(v, ENTRIES, [entry_text(l.Name, f.Document.Name, b.Name, f.Name) for l, b, f in entries])
    return v


def operation_of(obj):
    """VarSet de la operación (desde el VarSet, el croquis, o el binder/operación en una pieza)."""
    if obj is None:
        return None
    if hasattr(obj, KIND):
        return obj
    for doc in FreeCAD.listDocuments().values():
        for v in doc.Objects:
            if not hasattr(v, KIND):
                continue
            if getattr(v, SKETCH, None) is obj:
                return v
            for text in getattr(v, ENTRIES, []) or []:
                e = parse_entry(text)
                if e and e[1] == obj.Document.Name and obj.Name in (e[2], e[3]):
                    return v
    return None


def _recompute_later(docs):
    names = sorted({d.Name for d in docs})

    def run():
        for n in names:
            try:
                FreeCAD.getDocument(n).recompute()
            except Exception:
                pass
    QtCore.QTimer.singleShot(0, run)


# --- Observador: piezas que se mueven, croquis editado, pieza abierta sola -------------


class _Observer:
    def slotChangedObject(self, obj, prop):
        try:
            if prop != "Placement" or obj.TypeId not in ("App::Link", "Sketcher::SketchObject")                     or obj.Document.Restoring:
                return
            touched = []
            for v in obj.Document.Objects:
                if not hasattr(v, KIND):
                    continue
                sk = getattr(v, SKETCH, None)
                for link, binder, _feat in entries_of(v):
                    if link is obj or sk is obj:
                        want = binder_placement(link, sk)
                        if not binder.Placement.isSame(want, 1e-9):
                            binder.Placement = want
                            touched.append(binder.Document)
            if touched:
                _recompute_later(touched + [obj.Document])
        except Exception:
            pass

    def slotCreatedDocument(self, doc):
        QtCore.QTimer.singleShot(0, lambda n=doc.Name: _tell_if_from_assembly(n))


def _tell_if_from_assembly(doc_name):
    try:
        doc = FreeCAD.getDocument(doc_name)
    except Exception:
        return
    sources = sorted({getattr(o, BINDER_MARK) for o in doc.Objects if hasattr(o, BINDER_MARK)})
    if sources:
        names = []
        for s in sources:
            try:
                names.append(FreeCAD.getDocument(s).Label)
            except Exception:
                names.append(s)
        FreeCAD.Console.PrintMessage(
            "[SWUI] %s tiene agujeros o cortes hechos desde el ensamblaje %s: se editan desde ahí "
            "(clic derecho > Editar operación en el ensamblaje).\n" % (doc.Label, ", ".join(names)))


class _GuiObserver:
    """Al salir del croquis: seguir con el panel (operación nueva) o poner al día las piezas."""

    def slotResetEdit(self, vp):
        try:
            obj = vp.Object
        except Exception:
            return
        pending = _state["pending"]
        if pending is not None and obj is pending["sketch"]:
            QtCore.QTimer.singleShot(0, _after_sketch)
            return
        v = operation_of(obj) if obj.TypeId == "Sketcher::SketchObject" else None
        if v is not None:
            QtCore.QTimer.singleShot(0, lambda: _sketch_edited(v))


def _sketch_edited(v):
    try:
        sk = getattr(v, SKETCH)
        if getattr(v, KIND) == "hole" and add_markers(sk):
            sk.Document.recompute()
        _recompute_later([b.Document for _l, b, _f in entries_of(v)] + [v.Document])
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Croquis de ensamblaje:\n%s\n" % traceback.format_exc())


# --- Flujo: cara -> croquis -> panel ----------------------------------------------


def start(kind):
    from swui.fork import mates_sw

    asm = mates_sw.ensure_active()
    if asm is None:
        FreeCAD.Console.PrintWarning("[SWUI] %s: abrí o activá un ensamblaje primero.\n" % LABELS[kind])
        return
    face = _picked_face(asm)
    if face is not None:
        _open_sketch(asm, kind, *face)
        return
    try:
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
    except Exception:
        pass
    _state["panel"] = _FacePanel(asm, kind)
    FreeCADGui.Control.showDialog(_state["panel"])


def _picked_face(asm):
    from swui.fork import component_patterns as cp

    for obj, sub, kind in cp.pick_from_selection(asm):
        if kind == "plane" and obj.TypeId == "App::Link":
            return obj, sub
    return None


class _FacePanel:
    """'Elegí la cara plana' (como el primer paso del taladro de SW en un ensamblaje)."""

    def __init__(self, asm, kind):
        from swui.fork import mates_sw

        self.asm, self.kind = asm, kind
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(LABELS[kind])
        box = QtWidgets.QVBoxLayout(self.form)
        text = QtWidgets.QLabel("Elegí la cara plana donde empieza el %s. Se abre un croquis ahí: %s"
                                % ("taladro" if kind == "hole" else "corte",
                                   "marcá los centros con puntos." if kind == "hole" else "dibujá el perfil."))
        text.setWordWrap(True)
        box.addWidget(text)
        box.addStretch(1)
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._check)
        self.observer = mates_sw._SelObserver(self)
        try:
            FreeCADGui.Selection.addObserver(self.observer, FreeCADGui.Selection.ResolveMode.NoResolve)
        except Exception:
            FreeCADGui.Selection.addObserver(self.observer)
        FreeCADGui.Selection.clearSelection()

    def schedule(self):
        self.timer.start(0)

    def _check(self):
        face = _picked_face(self.asm)
        if face is None:
            return
        self._close()
        FreeCADGui.Control.closeDialog()
        QtCore.QTimer.singleShot(0, lambda: _open_sketch(self.asm, self.kind, *face))

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.StandardButton.Cancel

    def reject(self):
        self._close()
        FreeCADGui.Control.closeDialog()
        return True

    def _close(self):
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        _state["panel"] = None


def _open_sketch(asm, kind, comp, sub):
    try:
        FreeCADGui.Selection.clearSelection()
        doc = asm.Document
        doc.openTransaction(LABELS[kind])
        sk = make_sketch(asm, comp, sub)
        doc.commitTransaction()
        _state["pending"] = {"kind": kind, "asm": asm, "sketch": sk}
        FreeCADGui.ActiveDocument.setEdit(sk)
        if kind == "hole":
            from swui.fork import hole_panel

            QtCore.QTimer.singleShot(hole_panel.POINT_TOOL_DELAY_MS, lambda: hole_panel._point_tool(sk))
    except Exception:
        _state["pending"] = None
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (LABELS[kind], traceback.format_exc()))


def _after_sketch():
    pending, _state["pending"] = _state["pending"], None
    if pending is None:
        return
    asm, kind, sk = pending["asm"], pending["kind"], pending["sketch"]
    try:
        if kind == "hole":
            add_markers(sk)
        empty = not centers(sk) if kind == "hole" else not sk.Shape.Wires
        if empty:
            asm.Document.removeObject(sk.Name)
            FreeCAD.Console.PrintWarning("[SWUI] %s: el croquis quedó vacío, no se hizo nada.\n" % LABELS[kind])
            return
        FreeCADGui.ActiveDocument.setEdit(asm)  # volver a editar el ensamblaje
        FreeCADGui.Selection.clearSelection()  # si no, el panel de relaciones del original toma el croquis
        open_panel_new(asm, kind, sk)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (LABELS[kind], traceback.format_exc()))


def open_panel_new(asm, kind, sk):
    hits = hit_by_holes(asm, sk) if kind == "hole" else hit_by_cut(asm, sk)
    parts, repeated = unique_parts(hits)
    title = next_title({o.Label for o in asm.Document.Objects}, kind)
    entries = []
    for link in parts:
        binder, feat = add_to_part(link, sk, kind, title)
        entries.append((link, binder, feat))
    if kind == "hole" and not entries:
        FreeCAD.Console.PrintWarning("[SWUI] El taladro no atraviesa ninguna pieza: elegí las piezas en el panel.\n")
    _show(asm, kind, sk, entries, None, title, repeated)


def open_panel(v):
    asm = next((p for p in v.InList if p.TypeId == "Assembly::AssemblyObject"), None)
    if asm is None:
        return None
    for _l, b, _f in entries_of(v):
        if not b.Document.HasPendingTransaction:
            b.Document.openTransaction("Editar " + v.Label)
    return _show(asm, getattr(v, KIND), getattr(v, SKETCH), entries_of(v), v, v.Label, [])


def _show(asm, kind, sk, entries, data, title, repeated):
    try:
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
    except Exception:
        pass
    if kind == "hole" and entries:
        panel = make_hole_panel()(entries, asm, sk, data, title, repeated)
    else:
        panel = CutPanel(entries, asm, sk, data, title, repeated, kind)
    _state["panel"] = panel
    FreeCADGui.Control.showDialog(panel)
    return panel


# --- Lo común de los dos paneles -----------------------------------------------------


class _Scope:
    """'Piezas afectadas': lista + clic en una pieza la suma o la saca; guarda la operación."""

    def _scope_init(self, entries, asm, sk, data, title, repeated, kind):
        self.entries = list(entries)
        self.asm, self.sketch, self.data, self.title, self.op_kind = asm, sk, data, title, kind
        self.repeated = repeated
        self.part_docs = {b.Document.Name: b.Document for _l, b, _f in entries}

    def _scope_group(self):
        from swui.fork import dress_up_panel as dp

        g = QtWidgets.QGroupBox("Piezas afectadas")
        gl = QtWidgets.QVBoxLayout(g)
        self.parts_list = dp.pick_list(self._remove_current_part, self._clear_parts, 44)
        self.parts_list.setMaximumHeight(70)
        gl.addWidget(self.parts_list)
        hint = QtWidgets.QLabel("Un clic en una pieza la suma o la saca. Cada agujero queda dentro de su pieza "
                                "(sale en sus planos y en el DXF) y sigue al croquis del ensamblaje.")
        hint.setWordWrap(True)
        gl.addWidget(hint)
        if self.repeated:
            warn = QtWidgets.QLabel("Pieza repetida en el ensamblaje: %s. La operación queda en la pieza "
                                    "y sigue a la primera instancia." % ", ".join(l.Label for l in self.repeated))
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #b05000;")
            gl.addWidget(warn)
        self._fill_parts()
        return g

    def _fill_parts(self):
        self.parts_list.clear()
        for link, _b, _f in self.entries:
            self.parts_list.addItem(link.Label)

    def _toggle_part(self, link):
        for e in self.entries:
            if e[0] is link:
                self._drop(e)
                return True
        if any(e[0].LinkedObject is link.LinkedObject for e in self.entries):
            return False  # misma pieza, otra instancia
        binder, feat = add_to_part(link, self.sketch, self.op_kind, self.title)
        self.part_docs[binder.Document.Name] = binder.Document
        self.entries.append((link, binder, feat))
        self._copy_to_others()
        binder.Document.recompute()
        return True

    def _drop(self, entry):
        self.entries.remove(entry)
        remove_from_part(entry[1], entry[2])
        _recompute_later([d for d in self.part_docs.values()])

    def _remove_current_part(self):
        row = self.parts_list.currentRow()
        if 0 <= row < len(self.entries):
            self._drop(self.entries[row])
            self._parts_changed()

    def _clear_parts(self):
        for e in list(self.entries):
            self._drop(e)
        self._parts_changed()

    def _parts_changed(self):
        self._fill_parts()

    def _copy_to_others(self):
        pass

    def _link_of(self, obj):
        """Componente del ensamblaje al que pertenece algo elegido (resuelto a la pieza)."""
        from swui.fork import feature_tree as ft

        body = obj if obj.TypeId == "PartDesign::Body" else ft.body_of(obj)
        for link in _components(self.asm):
            if link.LinkedObject is body:
                return link
        return None

    def _save(self):
        doc = self.asm.Document
        if not doc.HasPendingTransaction:
            doc.openTransaction(LABELS[self.op_kind])
        if not self.entries:
            if self.data is not None:
                doc.removeObject(self.data.Name)
            doc.removeObject(self.sketch.Name)
        else:
            self.data = record(self.asm, self.op_kind, self.sketch, self.entries, self.data, self.title)
        doc.commitTransaction()
        for d in self.part_docs.values():
            if d.HasPendingTransaction:
                d.commitTransaction()
        _recompute_later(list(self.part_docs.values()) + [doc])
        self._back()

    def _back(self):
        from swui.fork import component_patterns

        QtCore.QTimer.singleShot(0, lambda: component_patterns._back_to(self.asm))

    def _cancel(self):
        for d in self.part_docs.values():
            if d.HasPendingTransaction:
                d.abortTransaction()
            d.recompute()
        if self.data is None:  # operación nueva: se va también el croquis
            doc = self.asm.Document
            if doc.getObject(self.sketch.Name) is not None:
                doc.openTransaction(LABELS[self.op_kind])
                doc.removeObject(self.sketch.Name)
                doc.commitTransaction()
        self._back()


# --- Taladro: el panel de la fase 2 sobre el taladro de la primera pieza ---------------

HOLE_PROPS = ("Threaded", "ModelThread", "ThreadType", "ThreadSize", "ThreadClass", "ThreadFit", "Diameter",
              "ThreadDirection", "HoleCutType", "HoleCutCustomValues", "HoleCutDiameter", "HoleCutDepth",
              "HoleCutCountersinkAngle", "DepthType", "Depth", "DrillPoint", "DrillPointAngle",
              "DrillForDepth", "Tapered", "TaperedAngle", "ThreadDepthType", "ThreadDepth", "UseCustomThreadClearance",
              "CustomThreadClearance")

_hole_class = None


def make_hole_panel():
    global _hole_class
    if _hole_class is not None:
        return _hole_class
    from swui.fork import hole_panel

    class AsmHolePanel(hole_panel.HolePanel, _Scope):
        TRANSACTION = LABELS["hole"]

        def __init__(self, entries, asm, sk, data, title, repeated):
            self._scope_init(entries, asm, sk, data, title, repeated, "hole")
            super().__init__(entries[0][2])
            self.form.setWindowTitle(title)
            self.form.layout().insertWidget(0, self._scope_group())

        def _sketch(self):
            return self.sketch

        def centers(self):
            return len(_unique(centers(self.sketch)))  # punto + su círculo chico = un centro

        def _apply(self):
            problem = super()._apply()
            self._copy_to_others()
            return problem

        def _copy_to_others(self):
            src = self.obj
            for _l, _b, feat in self.entries:
                if feat is src:
                    continue
                for prop in HOLE_PROPS:
                    if not hasattr(src, prop):
                        continue
                    try:
                        if prop == "ThreadSize":  # depende de ThreadType: después de él
                            continue
                        setattr(feat, prop, getattr(src, prop))
                    except Exception:
                        pass
                try:
                    feat.ThreadSize = src.ThreadSize
                    feat.Diameter = src.Diameter
                except Exception:
                    pass
                feat.Document.recompute()

        def _pick(self, obj, sub):
            link = self._link_of(obj)
            if link is None:
                return False
            if link is self.entries[0][0] and len(self.entries) > 1:
                self._switch_main()
            changed = self._toggle_part(link)
            if changed:
                self._fill_parts()
            return changed

        def _switch_main(self):
            """Se saca la primera pieza: el panel pasa a mostrar el taladro de la siguiente."""
            nxt = self.entries[1][2]
            self._copy_to_others()
            self._restore_visibility()
            self.obj, self.doc = nxt, nxt.Document
            self.gdoc = FreeCADGui.getDocument(self.doc.Name)
            self.base = self._base()
            self.visible = self._remember_visibility()

        def _nothing(self):
            return not self.entries or super()._nothing()

        def accept(self):
            self._copy_to_others()
            done = super().accept()
            if done:
                self._save()
            return done

        def reject(self):
            super().reject()
            self._cancel()
            return True

        def edit_positions(self, *_a):
            if not self.accept():
                return
            FreeCADGui.Control.closeDialog()
            QtCore.QTimer.singleShot(100, lambda: FreeCADGui.ActiveDocument.setEdit(self.sketch))

    _hole_class = AsmHolePanel
    return AsmHolePanel


# --- Corte ------------------------------------------------------------------------


class CutPanel(_Scope):
    """Extruir corte de ensamblaje: condición final, profundidad, piezas afectadas."""

    ENDS = (("ThroughAll", "Por todo"), ("TwoSides", "Por todo - ambas direcciones"), ("Length", "Hasta profundidad especificada"))

    def __init__(self, entries, asm, sk, data, title, repeated, kind="cut"):
        self._scope_init(entries, asm, sk, data, title, repeated, kind)
        first = entries[0][2] if entries else None
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(title)
        box = QtWidgets.QVBoxLayout(self.form)
        g = QtWidgets.QGroupBox("Dirección 1")
        gl = QtWidgets.QFormLayout(g)
        self.end = QtWidgets.QComboBox()
        for key, text in self.ENDS:
            self.end.addItem(text, key)
        current = "ThroughAll"
        if first is not None:
            current = "TwoSides" if first.Type == "ThroughAll" and first.Midplane else first.Type
        keys = [k for k, _t in self.ENDS]
        self.end.setCurrentIndex(keys.index(current) if current in keys else 0)
        gl.addRow(self.end)
        self.depth = QtWidgets.QDoubleSpinBox()
        self.depth.setRange(0.01, 1e6)
        self.depth.setSuffix(" mm")
        self.depth.setValue(float(first.Length) if first is not None else 10.0)
        gl.addRow("Profundidad:", self.depth)
        self.flip = QtWidgets.QCheckBox("Invertir lado")
        self.flip.setChecked(bool(first.Reversed) if first is not None else False)
        gl.addRow(self.flip)
        box.addWidget(g)
        box.addWidget(self._scope_group())
        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        box.addWidget(self.message)
        box.addStretch(1)
        self.end.currentIndexChanged.connect(lambda *_a: self._changed())
        self.depth.valueChanged.connect(lambda *_a: self._changed())
        self.flip.toggled.connect(lambda *_a: self._changed())
        from swui.fork import mates_sw

        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._picked)
        self.observer = mates_sw._SelObserver(self)
        FreeCADGui.Selection.addObserver(self.observer)
        FreeCADGui.Selection.clearSelection()
        self.busy = False
        self._changed()

    def schedule(self):
        if not self.busy:
            self.timer.start(0)

    def _picked(self):
        try:
            sels = FreeCADGui.Selection.getSelectionEx()
        except Exception:
            sels = []
        self.busy = True
        try:
            FreeCADGui.Selection.clearSelection()
        finally:
            self.busy = False
        changed = False
        for sel in sels:
            link = self._link_of(sel.Object)
            if link is not None:
                changed = self._toggle_part(link) or changed
        if changed:
            self._fill_parts()
            self._changed()

    def _copy_to_others(self):
        self._apply_all()

    def _apply_all(self):
        end = self.end.currentData()
        for _l, _b, feat in self.entries:
            feat.Type = "ThroughAll" if end == "TwoSides" else end
            feat.Midplane = end == "TwoSides"
            feat.Length = self.depth.value()
            feat.Reversed = self.flip.isChecked()

    def _changed(self):
        self.depth.setEnabled(self.end.currentData() == "Length")
        problem = ""
        try:
            self._apply_all()
            for d in self.part_docs.values():
                d.recompute()
            bad = [l.Label for l, _b, f in self.entries if not f.isValid()]
            if bad:
                problem = "FreeCAD no pudo cortar: %s." % ", ".join(bad)
            elif not self.entries:
                problem = "El corte no toca ninguna pieza: elegí las piezas (clic en la vista)."
        except Exception:
            problem = "No se pudo calcular el corte."
            FreeCAD.Console.PrintError("[SWUI fork] Corte de ensamblaje:\n%s\n" % traceback.format_exc())
        self.message.setText(problem)
        self.message.setVisible(bool(problem))

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel

    def accept(self):
        self._close()
        self._save()
        FreeCADGui.Control.closeDialog()
        return True

    def reject(self):
        self._close()
        self._cancel()
        FreeCADGui.Control.closeDialog()
        return True

    def _close(self):
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        _state["panel"] = None


# --- Comandos y cinta ----------------------------------------------------------------


class _Command:
    def __init__(self, kind):
        self.kind = kind

    def GetResources(self):
        from swui import paths

        tips = {"hole": "Taladro en varias piezas de una vez, desde el ensamblaje (queda dentro de cada pieza)",
                "cut": "Corte en varias piezas de una vez, desde el ensamblaje (queda dentro de cada pieza)"}
        icon = "sketch/f_hole" if self.kind == "hole" else "sketch/f_pocket"
        return {"MenuText": LABELS[self.kind], "ToolTip": tips[self.kind], "Pixmap": paths.icon(icon) or ""}

    def IsActive(self):
        from swui.fork import mates_sw

        doc = FreeCAD.ActiveDocument
        return doc is not None and bool(mates_sw._assemblies(doc))

    def Activated(self):
        start(self.kind)


FLYOUT = [
    ("SWUI_AssemblyHole", "Asistente para\ntaladro", {"svg": "sketch/f_hole"}),
    ("SWUI_AssemblyCut", "Extruir\ncorte", {"svg": "sketch/f_pocket"}),
]


def install_ribbon():
    from swui import ribbon_layout

    groups = ribbon_layout.BAUGRUPPE[1]
    for group in groups:
        if any(isinstance(e, dict) and e.get("flyout") == FLYOUT for e in group):
            return
    for group in groups:
        for i, e in enumerate(group):
            if isinstance(e, tuple) and e[0] == "Assembly_CreateView":
                group.insert(i, {"flyout": list(FLYOUT)})
                return
    groups.append([{"flyout": list(FLYOUT)}])


def install():
    global _installed
    if _installed:
        return
    for cmd, kind in ((HOLE_CMD, "hole"), (CUT_CMD, "cut")):
        try:
            FreeCADGui.addCommand(cmd, _Command(kind))
        except Exception:
            pass  # ya registrado
    install_ribbon()
    from swui.fork import dress_up_panel as dp

    if (operation_of, open_panel) not in dp.OPENERS:
        dp.OPENERS.append((operation_of, open_panel))
    FreeCAD.addDocumentObserver(_Observer())
    FreeCADGui.addDocumentObserver(_GuiObserver())
    _installed = True
