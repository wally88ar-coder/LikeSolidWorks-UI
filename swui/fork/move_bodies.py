# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Mover/Copiar sólido como en SOLIDWORKS (multicuerpo), con los valores numéricos del panel de SW
(capturas del usuario, 2026-10-26): "Sólidos para mover/copiar", Copiar + cantidad, Trasladar
(una arista recta + distancia, o ΔX ΔY ΔZ) y Girar (una arista recta como eje + ángulo, o
centro X Y Z + ángulos X Y Z). "Restricciones" (relaciones de posición) queda para otra etapa.

Todo nativo (el addon es un asistente, docs/ESTADO.md "Multicuerpo"), verificado en 1.1.4:
por cada sólido y cada copia, una copia vinculada del Cuerpo (PartDesign::SubShapeBinder, en la
raíz del documento; su forma está en posición real) y un Cuerpo nuevo que arranca de ella
(Body.BaseFeature) con el desplazamiento en Body.Placement (el Placement de la copia vinculada
se ignora como BaseFeature). Sigue los cambios del original y admite operaciones propias.
Copiar n veces: la copia i lleva el desplazamiento aplicado i veces. Mover (decisión del
usuario, camino b): igual que una copia, pero el original queda oculto y deja de contar como
sólido (material.consumes): lo de antes queda en el original, lo de después va en el nuevo.

De un vértice a otro (dos vértices en Dirección, como SW): un punto de referencia de FreeCAD
(Part::DatumPoint, MapMode "Vertex", marca SWUI_MoveBodyPoint) en cada vértice y la ecuación
Placement.Base = giro + i * (A - De) en cada Cuerpo copia: sigue a los vértices si la pieza cambia.
FreeCAD 1.1.4 pierde el vértice de arriba de una extrusión al cambiar la altura ("?Vertex6"): cada
punto guarda las caras que se juntan en su vértice (SWUI_FromVertex) y se vuelve a apoyar en el
vértice con las mismas caras (repair_point, al recalcular).

Marca: SWUI_MoveBody en cada copia vinculada (texto JSON con lo elegido; "op" agrupa las de
una misma operación). Nombre estable para siempre (docs/ESTADO.md, Decisiones).
"""

import json
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets
from swui.fork import dress_up_panel as dp

COMMAND = "SWUI_MoveBodies"
MARK = "SWUI_MoveBody"
BINDER = "PartDesign::SubShapeBinder"
BODY = "PartDesign::Body"
LABEL = "Mover/Copiar sólido"
POINT_MARK = "SWUI_MoveBodyPoint"  # puntos de "de un vértice a otro": JSON {"op", "role"} (nombre estable)


# --- Cuentas sin FreeCAD (probables en el test) -------------------------------


def read_spec(text):
    spec = {"op": "", "copy": False, "count": 1, "index": 1, "source": "",
            "delta": [0.0, 0.0, 0.0], "dir": None, "distance": 0.0,
            "center": [0.0, 0.0, 0.0], "angles": [0.0, 0.0, 0.0], "axis": None, "angle": 0.0,
            "from": None, "to": None}
    try:
        data = json.loads(text or "{}")
        if isinstance(data, dict):
            spec.update({k: v for k, v in data.items() if k in spec})
    except ValueError:
        pass
    spec["count"] = max(1, int(spec["count"] or 1))
    return spec


def next_label(used):
    n = 1
    while "%s%d" % (LABEL, n) in used:
        n += 1
    return "%s%d" % (LABEL, n)


def binder_label(op, source_label, index, count, sources):
    """'Mover/Copiar sólido1', o con el sólido / número de copia si hay más de uno."""
    extra = []
    if sources > 1:
        extra.append(source_label)
    if count > 1:
        extra.append(str(index))
    return "%s (%s)" % (op, ", ".join(extra)) if extra else op


def is_moved(spec):
    """Mover (no copiar): el original deja de contar como sólido."""
    return not spec.get("copy")


# --- Geometría ------------------------------------------------------------------


def _line_of(root, sub):
    """(punto, dirección) en posición real de una arista recta, o None."""
    try:
        edge = root.getSubObject(sub)
        if type(getattr(edge, "Curve", None)).__name__ not in ("Line", "LineSegment"):
            return None
        a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
        d = b - a
        return (a, d.normalize()) if d.Length > 1e-9 else None
    except Exception:
        return None


def _ref_obj(doc, ref):
    if not ref:
        return None, ""
    return doc.getObject(ref[0]), ref[1]


def _vertex_of(root, sub):
    try:
        shape = root.getSubObject(sub)
        return shape.Point if shape.ShapeType == "Vertex" else None
    except Exception:
        return None


def by_vertices(spec):
    """Trasladar de un vértice a otro (los dos elegidos)."""
    return bool(spec.get("from")) and bool(spec.get("to"))


def rotation_of(spec, doc):
    """La parte de girar del desplazamiento (eje o centro + ángulos)."""
    V = FreeCAD.Vector
    rot = FreeCAD.Placement()
    root, sub = _ref_obj(doc, spec.get("axis"))
    line = _line_of(root, sub) if root is not None else None
    if line is not None:
        if abs(spec["angle"]) > 1e-12:
            rot = FreeCAD.Placement(V(), FreeCAD.Rotation(line[1], spec["angle"]), line[0])
    else:
        ax, ay, az = spec["angles"]
        if any(abs(a) > 1e-12 for a in (ax, ay, az)):
            rot = FreeCAD.Placement(V(), FreeCAD.Rotation(az, ay, ax), V(*spec["center"]))
    return rot


def placement_of(spec, doc):
    """Desplazamiento de UNA copia: girar (eje o centro + ángulos) y después trasladar."""
    V = FreeCAD.Vector
    if by_vertices(spec):
        a, b = _vertex_of(*_ref_obj(doc, spec["from"])), _vertex_of(*_ref_obj(doc, spec["to"]))
        move = (b - a) if a is not None and b is not None else V()
        return FreeCAD.Placement(move, FreeCAD.Rotation()).multiply(rotation_of(spec, doc))
    root, sub = _ref_obj(doc, spec.get("dir"))
    line = _line_of(root, sub) if root is not None else None
    move = line[1] * spec["distance"] if line is not None else V(*spec["delta"])
    return FreeCAD.Placement(move, FreeCAD.Rotation()).multiply(rotation_of(spec, doc))


VERTEX_PROP = "SWUI_FromVertex"  # en el punto: JSON {"root", "sub", "faces"} (nombre estable)


def _vertex_faces(shape, vertex):
    """Firmas de las caras que se juntan en un vértice (para volver a encontrarlo)."""
    import Part
    from swui.fork import mate_refs

    out = []
    for face in shape.ancestorsOfType(vertex, Part.Face):
        try:
            out.append(mate_refs.signature(face))
        except Exception:
            pass
    return out


def vertex_cost(want, faces):
    """Cuánto se parecen las caras de un vértice a las guardadas (None si falta alguna)."""
    from swui.fork import mate_refs

    if not want or not faces:
        return None
    total = 0.0
    for sig in want:
        costs = [c for c in (mate_refs.cost(sig, f) for f in faces) if c is not None]
        if not costs:
            return None
        total += min(costs)
    return total


def _root_shape(root, prefix):
    try:
        return root.getSubObject(prefix) if prefix else root.Shape
    except Exception:
        return None


def _attach_at_vertex(pt, root, sub):
    """
    Punto de referencia en un vértice. FreeCAD 1.1.4 pierde el vértice de arriba de una extrusión
    al cambiar la altura (queda "?Vertex6"; y a veces las aristas verticales: probado 2026-10-30):
    se guardan las caras que se juntan ahí para volver a encontrarlo (repair_points).
    """
    from swui.fork import mate_refs

    pt.AttachmentSupport = [(root, sub)]
    pt.MapMode = "Vertex"
    prefix, name = mate_refs.split_sub(sub)
    shape = _root_shape(root, prefix)
    faces = []
    try:
        faces = _vertex_faces(shape, shape.getElement(name))
    except Exception:
        pass
    if not hasattr(pt, VERTEX_PROP):
        pt.addProperty("App::PropertyString", VERTEX_PROP, "SWUI", "Vértice elegido (fork de LikeSolidWorks UI)")
        pt.setEditorMode(VERTEX_PROP, 2)
    setattr(pt, VERTEX_PROP, json.dumps({"root": root.Name, "sub": sub, "faces": faces}, sort_keys=True))


def _stored_vertex(pt):
    try:
        return json.loads(getattr(pt, VERTEX_PROP, "") or "{}")
    except ValueError:
        return {}


def repair_point(pt):
    """Si FreeCAD perdió el vértice de un punto De / A, buscar el que tiene las mismas caras."""
    from swui.fork import mate_refs

    data = _stored_vertex(pt)
    support = list(pt.AttachmentSupport or [])
    if not data.get("faces") or len(support) != 1:
        return False
    root, subs = support[0]
    sub = subs[0] if subs else ""
    broken = mate_refs.is_broken(sub)
    if not broken:
        try:
            broken = pt.getStatusString() != "Valid"
        except Exception:
            broken = False
    if not broken:
        return False
    prefix, _name = mate_refs.split_sub(sub)
    shape = _root_shape(root, prefix)
    if shape is None:
        return False
    best, best_cost = None, None
    for i, vertex in enumerate(shape.Vertexes, 1):
        c = vertex_cost(data["faces"], _vertex_faces(shape, vertex))
        if c is not None and (best_cost is None or c < best_cost):
            best, best_cost = i, c
    if best is None:
        FreeCAD.Console.PrintWarning("%s: ya no está el vértice elegido.\n" % pt.Label)
        return False
    _attach_at_vertex(pt, root, "%sVertex%d" % (prefix, best))
    return True


class _RepairObserver:
    busy = False

    def slotRecomputedDocument(self, doc):
        if self.busy:
            return
        points = [o for o in doc.Objects if hasattr(o, VERTEX_PROP)]
        if not points:
            return
        self.busy = True
        try:
            fixed = False
            for pt in points:
                try:
                    fixed = repair_point(pt) or fixed
                except Exception:
                    FreeCAD.Console.PrintLog("[SWUI fork] Punto de Mover/Copiar:\n%s\n" % traceback.format_exc())
            if fixed:  # adentro del aviso de recálculo FreeCAD no vuelve a recalcular: después
                name = doc.Name
                QtCore.QTimer.singleShot(0, lambda: FreeCAD.getDocument(name).recompute())
        finally:
            self.busy = False


_repair = {"observer": None}


def vertex_expression(base, index, start, end):
    """
    Ecuación de Placement.Base de la copia `index` con "de un vértice a otro": la parte del giro
    (número) + index veces (vértice A - vértice De), así sigue a los vértices si la pieza cambia.
    start / end: nombres de los puntos de referencia (Part::DatumPoint) en los vértices.
    """
    return "vector(%r; %r; %r) + (%s.Placement.Base - %s.Placement.Base) * %d" % (
        base[0], base[1], base[2], end, start, index)


def power(pl, n):
    out = FreeCAD.Placement()
    for _i in range(n):
        out = pl.multiply(out)
    return out


# --- Objetos de una operación -----------------------------------------------------


def binders_of_op(doc, op):
    return [o for o in doc.Objects if hasattr(o, MARK) and read_spec(getattr(o, MARK)).get("op") == op]


def body_from(binder):
    for user in binder.InList:
        if user.TypeId == BODY and user.BaseFeature is binder:
            return user
    return None


def source_of(binder):
    try:
        return binder.Support[0][0]
    except Exception:
        return None


def _hide(obj):
    try:
        obj.Visibility = False
    except Exception:
        pass


# --- Panel -------------------------------------------------------------------


def _body_of(obj):
    from swui.fork import multibody

    if obj is not None and obj.TypeId == BODY:
        return obj
    return multibody.body_of(obj)


class MoveBodiesPanel:
    """
    Panel SW. Los objetos se arman en vivo (dentro de una transacción) para ver el resultado:
    Aceptar la confirma, Cancelar la deshace entera.
    """

    def __init__(self, binder=None, doc=None, sources=None):
        self.doc = binder.Document if binder is not None else doc
        self.gdoc = FreeCADGui.getDocument(self.doc.Name)
        if binder is not None:
            self.spec = read_spec(getattr(binder, MARK))
            group = binders_of_op(self.doc, self.spec["op"])
            self.sources = []
            for b in sorted(group, key=lambda o: read_spec(getattr(o, MARK))["index"]):
                src = source_of(b)
                if src is not None and src not in self.sources:
                    self.sources.append(src)
        else:
            self.spec = read_spec("")
            # Ojo: las copias vinculadas se llaman "Mover/Copiar sólido1 (2)"...: el nombre de
            # la operación sale de las marcas, no solo de los nombres (si no, se pisaban)
            used = set(o.Label for o in self.doc.Objects)
            used |= set(read_spec(getattr(o, MARK)).get("op") for o in self.doc.Objects if hasattr(o, MARK))
            self.spec["op"] = next_label(used)
            self.sources = list(sources or [])
        if self.gdoc.getInEdit() is not None and not self.doc.HasPendingTransaction:
            self.gdoc.resetEdit()
        self.busy = False
        self.active = None
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.preview)
        self._build()
        if not self.doc.HasPendingTransaction:
            self.doc.openTransaction(LABEL)
        self.observer = dp._PickObserver(self)
        FreeCADGui.Selection.addObserver(self.observer)
        FreeCADGui.Selection.clearSelection()
        self.preview()

    # --- interfaz

    def _build(self):
        from swui import paths
        from swui.compat import QtGui

        s = self.spec
        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(LABEL)
        icon = paths.icon("fork/move_bodies")
        if icon:
            self.form.setWindowIcon(QtGui.QIcon(icon))
        box = QtWidgets.QVBoxLayout(self.form)

        group = QtWidgets.QGroupBox("Sólidos para mover/copiar")
        gl = QtWidgets.QVBoxLayout(group)
        self.list = dp.pick_list(self.remove_current, self.clear, height=60)
        self.list.setMaximumHeight(100)
        self.list.itemClicked.connect(lambda *_a: self._activate(self.list))
        gl.addWidget(self.list)
        row = QtWidgets.QHBoxLayout()
        self.copy = QtWidgets.QCheckBox("Copiar")
        self.copy.setChecked(bool(s["copy"]))
        self.copy.toggled.connect(self._changed)
        self.count = QtWidgets.QSpinBox()
        self.count.setRange(1, 100)
        self.count.setValue(int(s["count"]))
        self.count.setPrefix("Copias: ")
        self.count.setKeyboardTracking(False)
        self.count.valueChanged.connect(self._changed)
        row.addWidget(self.copy)
        row.addWidget(self.count)
        gl.addLayout(row)
        box.addWidget(group)

        move = QtWidgets.QGroupBox("Trasladar")
        self.move_form = QtWidgets.QFormLayout(move)
        self.dir_box = dp.RefBox(self._activate)
        self.dir_box.setPlaceholderText("Arista recta o dos vértices (vacía: ΔX ΔY ΔZ)")
        _clear_action(self.dir_box, lambda: self._clear_ref("dir"))
        self.distance = dp._spin(float(s["distance"]), " mm", -100000.0, 100000.0)
        self.deltas = [dp._spin(float(v), " mm", -100000.0, 100000.0) for v in s["delta"]]
        self.move_rows = {}
        for key, text, w in (("dir", "Dirección:", self.dir_box), ("distance", "Distancia:", self.distance),
                             ("dx", "ΔX:", self.deltas[0]), ("dy", "ΔY:", self.deltas[1]),
                             ("dz", "ΔZ:", self.deltas[2])):
            label = QtWidgets.QLabel(text)
            self.move_form.addRow(label, w)
            self.move_rows[key] = (label, w)
        box.addWidget(move)

        turn = QtWidgets.QGroupBox("Girar")
        self.turn_form = QtWidgets.QFormLayout(turn)
        self.axis_box = dp.RefBox(self._activate)
        self.axis_box.setPlaceholderText("Arista recta (vacía: centro y ángulos)")
        _clear_action(self.axis_box, lambda: self._clear_ref("axis"))
        self.angle = dp._spin(float(s["angle"]), "°", -360.0, 360.0)
        self.center = [dp._spin(float(v), " mm", -100000.0, 100000.0) for v in s["center"]]
        self.angles = [dp._spin(float(v), "°", -360.0, 360.0) for v in s["angles"]]
        self.turn_rows = {}
        for key, text, w in (("axis", "Eje:", self.axis_box), ("angle", "Ángulo:", self.angle),
                             ("cx", "Centro X:", self.center[0]), ("cy", "Centro Y:", self.center[1]),
                             ("cz", "Centro Z:", self.center[2]), ("ax", "Ángulo X:", self.angles[0]),
                             ("ay", "Ángulo Y:", self.angles[1]), ("az", "Ángulo Z:", self.angles[2])):
            label = QtWidgets.QLabel(text)
            self.turn_form.addRow(label, w)
            self.turn_rows[key] = (label, w)
        box.addWidget(turn)
        for spin in [self.distance, self.angle] + self.deltas + self.center + self.angles:
            spin.valueChanged.connect(self._changed)

        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: %s;" % dp.MISSING_COLOR)
        self.message.hide()
        box.addWidget(self.message)
        box.addStretch(1)
        self.active = self.list
        self._refresh()

    def _activate(self, widget):
        self.active = widget
        self._paint_active()

    def _paint_active(self):
        for w in (self.list, self.dir_box, self.axis_box):
            on = w is self.active
            if w is self.list:
                w.setStyleSheet("QListWidget { %s }" % dp.ACTIVE_QSS if on else "")
            else:
                w.setStyleSheet(dp.ACTIVE_QSS if on else "")

    @staticmethod
    def _ref_text(doc, ref):
        root, _sub = _ref_obj(doc, ref)
        return "Arista<1> (%s)" % root.Label if root is not None else ""

    def _dir_text(self):
        s = self.spec
        if by_vertices(s):
            return "Vértice<1>, Vértice<2> (de uno al otro)"
        if s.get("from"):
            return "Vértice<1> (falta el segundo vértice)"
        return self._ref_text(self.doc, s["dir"])

    def _clear_ref(self, key):
        """Clic derecho -> Borrar selecciones en Dirección / Eje: vuelve a los números."""
        self.spec[key] = None
        if key == "dir":
            self.spec["from"] = self.spec["to"] = None
        self._refresh()
        self.preview()

    def _refresh(self):
        s = self.spec
        self.count.setVisible(self.copy.isChecked())
        has_dir, has_axis = bool(s["dir"]), bool(s["axis"])
        vertices = by_vertices(s)
        for key, (label, w) in self.move_rows.items():
            show = key == "dir" or (not vertices and (key == "distance") == has_dir)
            label.setVisible(show)
            w.setVisible(show)
        for key, (label, w) in self.turn_rows.items():
            show = key == "axis" or (key == "angle") == has_axis
            label.setVisible(show)
            w.setVisible(show)
        self.dir_box.setText(self._dir_text())
        self.axis_box.setText(self._ref_text(self.doc, s["axis"]))
        self.list.clear()
        for body in self.sources:
            self.list.addItem(body.Label)
        self._paint_active()

    def _changed(self, *_a):
        self.count.setVisible(self.copy.isChecked())
        self.timer.start(dp.PREVIEW_DELAY_MS)

    def remove_current(self, *_a):
        row = self.list.currentRow()
        if 0 <= row < len(self.sources):
            self.sources = self.sources[:row] + self.sources[row + 1:]
            self._refresh()
            self.preview()

    def clear(self, *_a):
        self.sources = []
        self._refresh()
        self.preview()

    # --- selección (posición real: getSelectionEx sin resolver)

    def take_selection(self):
        try:
            sels = FreeCADGui.Selection.getSelectionEx("", 0)
        except Exception:
            sels = []
        changed = False
        for sel in sels:
            for sub in (sel.SubElementNames or [""]):
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

    def _own(self):
        """Objetos que arma esta operación (no se pueden elegir como sólidos)."""
        out = set()
        for b in binders_of_op(self.doc, self.spec["op"]):
            out.add(b.Name)
            body = body_from(b)
            if body is not None:
                out.add(body.Name)
        return out

    def _pick(self, root, sub):
        element = sub.split(".")[-1]
        if self.active is self.dir_box and element.startswith("Vertex"):
            return self._pick_vertex(root, sub)
        if self.active in (self.dir_box, self.axis_box):
            if not element.startswith("Edge") or _line_of(root, sub) is None:
                return False
            key = "dir" if self.active is self.dir_box else "axis"
            self.spec[key] = [root.Name, sub]
            if key == "dir":
                self.spec["from"] = self.spec["to"] = None
            self.active = self.list
            return True
        leaf = root
        try:
            leaf = root.getSubObject(sub, retType=1) or root
        except Exception:
            pass
        body = _body_of(leaf) or _body_of(root)
        if body is None or body.Name in self._own():
            return False
        from swui.fork import multibody

        if body not in multibody.solid_bodies(self.doc) and body not in self.sources:
            return False
        self.sources = dp.toggle(self.sources, body)
        return True

    def _pick_vertex(self, root, sub):
        """De un vértice a otro, como SW: el primer vértice es De, el segundo A."""
        leaf = root
        try:
            leaf = root.getSubObject(sub, retType=1) or root
        except Exception:
            pass
        body = _body_of(leaf) or _body_of(root)
        if body is not None and body.Name in self._own():
            return False  # un vértice de la propia copia la haría depender de sí misma
        if _vertex_of(root, sub) is None:
            return False
        s = self.spec
        s["dir"] = None
        if not s.get("from") or by_vertices(s):
            s["from"], s["to"] = [root.Name, sub], None
        else:
            s["to"] = [root.Name, sub]
            self.active = self.list
        return True

    def _points(self):
        out = {}
        for o in self.doc.Objects:
            if hasattr(o, POINT_MARK):
                try:
                    data = json.loads(getattr(o, POINT_MARK))
                except ValueError:
                    continue
                if data.get("op") == self.spec["op"]:
                    out[data.get("role")] = o
        return out

    def _sync_points(self):
        """Puntos de referencia en los vértices De y A (o ninguno si no se usan)."""
        from swui.fork import multibody

        points = self._points()
        if not by_vertices(self.spec):
            for o in points.values():
                self.doc.removeObject(o.Name)
            return {}
        for role, text in (("from", "De"), ("to", "A")):
            root_name, sub = self.spec[role]
            root = self.doc.getObject(root_name)
            pt = points.get(role)
            if pt is None:
                pt = self.doc.addObject("Part::DatumPoint", "Punto")
                pt.addProperty("App::PropertyString", POINT_MARK, "SWUI", "Mover/Copiar sólido (fork de LikeSolidWorks UI)")
                pt.setEditorMode(POINT_MARK, 2)
                setattr(pt, POINT_MARK, json.dumps({"op": self.spec["op"], "role": role}, sort_keys=True))
                _hide(pt)
                points[role] = pt
            if _stored_vertex(pt).get("sub") != sub or pt.AttachmentSupport[:1] == []:
                _attach_at_vertex(pt, root, sub)
            multibody._keep_label(pt, "%s (%s)" % (text, self.spec["op"]))
        self.doc.recompute()
        return points

    # --- objetos nativos

    def _read(self):
        s = self.spec
        s.update({"copy": self.copy.isChecked(), "count": self.count.value() if self.copy.isChecked() else 1,
                  "delta": [w.value() for w in self.deltas], "distance": self.distance.value(),
                  "center": [w.value() for w in self.center], "angles": [w.value() for w in self.angles],
                  "angle": self.angle.value()})

    def _apply(self):
        """Dejar los objetos como pide el panel: una copia vinculada + Cuerpo por sólido y copia."""
        from swui.fork import multibody

        s = self.spec
        wanted = [(src, i) for src in self.sources for i in range(1, s["count"] + 1)]
        existing = {}
        for b in binders_of_op(self.doc, s["op"]):
            spec = read_spec(getattr(b, MARK))
            src = source_of(b)
            key = (src.Name if src is not None else "", spec["index"])
            if key in existing or (src, spec["index"]) not in wanted:
                self._remove(b)
            else:
                existing[key] = b
        points = self._sync_points()
        step = placement_of(s, self.doc)
        turn = rotation_of(s, self.doc)
        used = set(o.Label for o in self.doc.Objects)
        for src, i in wanted:
            binder = existing.get((src.Name, i))
            if binder is None:
                binder = self.doc.addObject(BINDER, "Binder")
                binder.addProperty("App::PropertyString", MARK, "SWUI", "Mover/Copiar sólido (fork de LikeSolidWorks UI)")
                binder.setEditorMode(MARK, 2)
                binder.Support = [(src, "")]
                _hide(binder)
                body = self.doc.addObject(BODY, "Body")
                body.BaseFeature = binder
                label = multibody.next_body_label(used)
                used.add(label)
                multibody._keep_label(body, label)
            else:
                body = body_from(binder)
            spec = dict(s, index=i, source=src.Name)
            text = json.dumps(spec, sort_keys=True)
            if getattr(binder, MARK) != text:
                setattr(binder, MARK, text)
            multibody._keep_label(binder, binder_label(s["op"], src.Label, i, s["count"], len(self.sources)))
            if body is not None:
                if points:  # de un vértice a otro: la traslación por ecuación, sigue a los vértices
                    rot = power(turn, i)
                    body.setExpression(".Placement.Base", None)
                    body.Placement = rot
                    body.setExpression(".Placement.Base", vertex_expression(
                        (rot.Base.x, rot.Base.y, rot.Base.z), i, points["from"].Name, points["to"].Name))
                else:
                    body.setExpression(".Placement.Base", None)
                    pl = power(step, i)
                    if not body.Placement.isSame(pl, 1e-9):
                        body.Placement = pl
                body.Visibility = True
        for src in self.sources:  # mover: el original se oculta (sigue en el árbol, "antes de mover")
            src.Visibility = bool(s["copy"])

    def _remove(self, binder):
        body = body_from(binder)
        if body is not None:
            name = body.Name
            body.removeObjectsFromDocument()
            self.doc.removeObject(name)
        self.doc.removeObject(binder.Name)

    def _problem(self):
        if not self.sources:
            return "Elegí al menos un sólido (clic en la pieza o en el árbol)."
        for b in binders_of_op(self.doc, self.spec["op"]):
            body = body_from(b)
            if body is not None and len(body.Group) > 1 and source_of(b) not in self.sources:
                return "El sólido %s ya tiene operaciones propias: no se puede sacar." % body.Label
        return ""

    def preview(self):
        self.timer.stop()
        self._read()
        problem = self._problem()
        if not problem:
            try:
                self._apply()
                self.doc.recompute()
            except Exception:
                FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (LABEL, traceback.format_exc()))
                problem = "No se pudo calcular la vista previa."
        self.message.setText(problem)
        self.message.setVisible(bool(problem))
        return not problem

    # --- cerrar

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

    def _close(self):
        self.timer.stop()
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        dp._state["panel"] = None

    def accept(self):
        if not self.preview():
            return False
        if not binders_of_op(self.doc, self.spec["op"]):
            return False
        self._close()
        self.doc.recompute()
        if self.gdoc.getInEdit() is not None:
            self.gdoc.resetEdit()
        self.doc.commitTransaction()
        return True

    def reject(self):
        self._close()
        self.doc.abortTransaction()
        if self.gdoc.getInEdit() is not None:
            self.gdoc.resetEdit()
        self.doc.recompute()
        return True


def _clear_action(box, clear):
    """Clic derecho en una casilla de referencia: Borrar selecciones (como SW)."""
    from swui.compat import QtGui

    action_cls = getattr(QtGui, "QAction", None) or QtWidgets.QAction
    box.setContextMenuPolicy(QtCore.Qt.ActionsContextMenu)
    act = action_cls("Borrar selecciones", box)
    act.triggered.connect(lambda *_a: clear())
    box.addAction(act)


def _choose(obj):
    return MoveBodiesPanel if hasattr(obj, MARK) and obj.TypeId == BINDER else None


def edit_target(obj):
    """Algo elegido en el árbol que pertenece a un Mover/Copiar sólido: su copia vinculada."""
    if obj is None:
        return None
    if hasattr(obj, MARK):
        return obj
    if obj.TypeId == BODY and hasattr(obj.BaseFeature, MARK):
        return obj.BaseFeature
    if hasattr(obj, POINT_MARK):
        try:
            op = json.loads(getattr(obj, POINT_MARK)).get("op")
        except ValueError:
            return None
        found = binders_of_op(obj.Document, op)
        return found[0] if found else None
    return None


def open_panel(binder):
    if FreeCADGui.Control.activeDialog():
        return None
    panel = MoveBodiesPanel(binder)
    dp._state["panel"] = panel
    FreeCADGui.Control.showDialog(panel)
    return panel


# --- Comando -------------------------------------------------------------------


def start(doc=None):
    from swui.fork import multibody

    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return None
    if FreeCADGui.Control.activeDialog():
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), LABEL, "Cerrá primero el panel que está abierto.")
        return None
    bodies = multibody.solid_bodies(doc)
    if not bodies:
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), LABEL, "No hay sólidos (Cuerpos) en la pieza.")
        return None
    chosen = []
    for sel in FreeCADGui.Selection.getSelectionEx(doc.Name):
        body = _body_of(sel.Object)
        if body in bodies and body not in chosen:
            chosen.append(body)
    try:
        panel = MoveBodiesPanel(doc=doc, sources=chosen)
        dp._state["panel"] = panel
        FreeCADGui.Control.showDialog(panel)
        return panel
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (LABEL, traceback.format_exc()))
        dp._state["panel"] = None
        if doc.HasPendingTransaction:
            doc.abortTransaction()
        return None


class _Command:
    def GetResources(self):
        from swui import paths

        return {"MenuText": LABEL, "ToolTip": "Mover, girar o copiar sólidos enteros (como SW)",
                "Pixmap": paths.icon("fork/move_bodies") or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        start()


def install():
    if _repair["observer"] is None:
        _repair["observer"] = _RepairObserver()
        FreeCAD.addDocumentObserver(_repair["observer"])
    if _choose not in dp.CHOOSERS:
        dp.CHOOSERS.append(_choose)
    if (edit_target, open_panel) not in dp.OPENERS:
        dp.OPENERS.append((edit_target, open_panel))
    try:
        FreeCADGui.addCommand(COMMAND, _Command())
    except Exception:
        pass  # ya registrado
