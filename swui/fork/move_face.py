# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Mover cara como en SOLIDWORKS (fase 4): Equidistanciar / Trasladar / Girar, solo caras planas.

Panel como el PropertyManager de SW (captura del usuario, 2026-10-26): tipo, caras, y en
Parámetros la dirección (Trasladar), el eje de giro (Girar), Invertir dirección, distancia,
ΔX ΔY ΔZ o ángulo. Sirve en piezas propias y en sólidos importados (STEP): a un sólido suelto
se le arma un Cuerpo que arranca de él.

Todo nativo (el addon es un asistente, docs/ESTADO.md "Análisis: ..."), verificado en 1.1.4:
- Equidistanciar / Trasladar = mover la cara según su normal: Extruir (PartDesign::Pad) con la
  cara misma como perfil si sale, Cortar (PartDesign::Pocket) si entra. De Trasladar cuenta
  solo la componente normal (correr una cara plana dentro de su plano no la cambia). Con caras
  vecinas inclinadas queda un escalón en vez de prolongarlas (límite conocido).
- Girar alrededor de una arista recta de la cara = Ángulo de salida (PartDesign::Draft): plano
  neutro = una cara plana que contiene la arista; dirección de tiro = una arista recta (o la
  normal de una cara plana) perpendicular a la arista dentro de la cara. Prolonga bien las
  vecinas, también inclinadas.
Si cambia el sentido (agregar <-> quitar material) o el tipo, la operación se cambia por la
otra (mientras nada más use sus caras). La distancia o el ángulo se pueden atar a ecuaciones.

Marca: propiedad oculta SWUI_MoveFace (texto JSON con lo elegido en el panel). Nombre estable
para siempre (docs/ESTADO.md, Decisiones): sin el addon el archivo abre y recalcula igual (es
un Pad / Pocket / Draft común); con el addon, editar abre este panel.
"""

import json
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtWidgets
from swui.fork import dress_up_panel as dp

COMMAND = "SWUI_MoveFace"
MARK = "SWUI_MoveFace"
LABEL = "Mover cara"
PAD, POCKET, DRAFT = "PartDesign::Pad", "PartDesign::Pocket", "PartDesign::Draft"
OFFSET, TRANSLATE, ROTATE = "offset", "translate", "rotate"
MODES = (("Equidistanciar", OFFSET), ("Trasladar", TRANSLATE), ("Girar", ROTATE))
TOL = 1e-6


# --- Cuentas sin FreeCAD (probables en el test) -------------------------------


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def normal_move(mode, normal, distance=0.0, flip=False, direction=None, delta=(0.0, 0.0, 0.0)):
    """
    Cuánto se corre la cara según su normal (positivo = hacia afuera, agrega material).
    Equidistanciar: la distancia (Invertir = hacia adentro). Trasladar: la componente normal
    de la distancia sobre la dirección elegida, o de ΔX ΔY ΔZ si no hay dirección.
    """
    sign = -1.0 if flip else 1.0
    if mode == OFFSET:
        return sign * distance
    if direction is not None:
        return sign * distance * dot(direction, normal)
    return dot(delta, normal)


def native_type(mode, move):
    """Operación nativa que hace el trabajo."""
    if mode == ROTATE:
        return DRAFT
    return PAD if move > 0 else POCKET


def next_label(used):
    n = 1
    while "%s%d" % (LABEL, n) in used:
        n += 1
    return "%s%d" % (LABEL, n)


MODE_PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI/MoveFace"


def last_mode():
    """El último modo usado (SW abre Mover cara en ese); la primera vez, Equidistanciar."""
    try:
        mode = FreeCAD.ParamGet(MODE_PARAMS).GetString("Mode", OFFSET)
    except Exception:
        return OFFSET
    return mode if mode in (OFFSET, TRANSLATE, ROTATE) else OFFSET


def remember_mode(mode):
    try:
        FreeCAD.ParamGet(MODE_PARAMS).SetString("Mode", mode)
    except Exception:
        pass


def read_spec(text):
    """Lo guardado en SWUI_MoveFace (JSON) con valores por omisión."""
    spec = {"mode": OFFSET, "flip": False, "distance": 10.0, "delta": [0.0, 0.0, 0.0],
            "dir": None, "hinge": "", "angle": 10.0}
    try:
        data = json.loads(text or "{}")
        if isinstance(data, dict):
            spec.update({k: v for k, v in data.items() if k in spec})
    except ValueError:
        pass
    if spec["mode"] not in (OFFSET, TRANSLATE, ROTATE):
        spec["mode"] = OFFSET
    return spec


# --- Geometría ------------------------------------------------------------------


def is_planar(face):
    try:
        if type(face.Surface).__name__ == "Plane":
            return True
        return face.findPlane() is not None  # plano guardado como spline (STEP)
    except Exception:
        return False


def face_normal(face):
    """Normal hacia afuera del sólido (respeta la orientación de la cara)."""
    u0, u1, v0, v1 = face.ParameterRange
    n = face.normalAt((u0 + u1) / 2.0, (v0 + v1) / 2.0)
    return n.normalize()


def _is_line(edge):
    return type(getattr(edge, "Curve", None)).__name__ in ("Line", "LineSegment")


def _edge_dir(edge):
    d = edge.Vertexes[-1].Point - edge.Vertexes[0].Point
    return d.normalize() if d.Length > TOL else None


def _on_plane(point, origin, normal):
    return abs((point - origin).dot(normal)) < 1e-4


def faces_problem(shape, subs, same_plane=False):
    """Las caras elegidas sirven? (planas, mirando para el mismo lado). "" si sí."""
    first = None
    for sub in subs:
        face = dp._element(shape, sub)
        if face is None:
            return "Hay caras que ya no existen (en rojo): borralas y elegí las nuevas."
        if not is_planar(face):
            return "Solo se pueden mover caras planas."
        n = face_normal(face)
        if first is None:
            first = (face, n)
            continue
        if n.dot(first[1]) < 1 - 1e-6:
            return "Las caras tienen que mirar para el mismo lado (para otras, otro Mover cara)."
        if same_plane and not _on_plane(face.Vertexes[0].Point, first[0].Vertexes[0].Point, first[1]):
            return "Para girar, las caras tienen que estar en el mismo plano."
    return ""


def hinge_refs(shape, subs, hinge):
    """
    Girar alrededor de la arista `hinge` (recta, en el plano de las caras): (plano neutro,
    dirección de tiro, problema). Plano neutro: una cara plana que contiene la arista (mejor la
    vecina). Tiro: una arista recta perpendicular a la arista dentro del plano de la cara, o una
    cara plana con esa normal.
    """
    face = dp._element(shape, subs[0])
    edge = dp._element(shape, hinge)
    if face is None or edge is None or not _is_line(edge):
        return None, None, "Elegí como eje una arista recta de la cara."
    n = face_normal(face)
    h = _edge_dir(edge)
    origin = face.Vertexes[0].Point
    if h is None or abs(h.dot(n)) > 1e-6 or not all(_on_plane(v.Point, origin, n) for v in edge.Vertexes):
        return None, None, "La arista del giro tiene que estar en el plano de la cara."
    chosen = [dp._element(shape, s) for s in subs]
    neutral, best = None, None
    for i, cand in enumerate(shape.Faces):
        if any(c is not None and cand.isSame(c) for c in chosen) or not is_planar(cand):
            continue
        m = face_normal(cand)
        if abs(m.dot(h)) > 1e-6 or abs(m.dot(n)) > 1 - 1e-6:
            continue
        p = cand.Vertexes[0].Point
        if not all(_on_plane(v.Point, p, m) for v in edge.Vertexes):
            continue
        shares = any(e.isSame(edge) for e in cand.Edges)
        if neutral is None or (shares and not best):
            neutral, best = "Face%d" % (i + 1), shares
    if neutral is None:
        return None, None, "No hay una cara plana que pase por esa arista para usar de bisagra."
    pull_dir = n.cross(h).normalize()
    pull = None
    face_edges = [e for c in chosen if c is not None for e in c.Edges]
    for i, cand in enumerate(shape.Edges):
        if not _is_line(cand):
            continue
        d = _edge_dir(cand)
        if d is not None and abs(d.dot(pull_dir)) > 1 - 1e-6:
            own = any(cand.isSame(e) for e in face_edges)
            if pull is None or own:
                pull = "Edge%d" % (i + 1)
                if own:
                    break
    if pull is None:
        for i, cand in enumerate(shape.Faces):
            if is_planar(cand) and abs(face_normal(cand).dot(pull_dir)) > 1 - 1e-6:
                pull = "Face%d" % (i + 1)
                break
    if pull is None:
        return None, None, "No encuentro una arista perpendicular al eje dentro de la cara para girarla."
    return neutral, pull, ""


def direction_of(obj, sub):
    """Dirección de una referencia: arista recta, cara plana, plano o recta de referencia."""
    try:
        if sub:
            el = obj.Shape.getElement(sub)
            if sub.startswith("Edge") and _is_line(el):
                return _edge_dir(el)
            if sub.startswith("Face") and is_planar(el):
                return face_normal(el)
            return None
        rot = obj.Placement.Rotation
        if obj.TypeId in ("App::Plane", "PartDesign::Plane"):
            return rot.multVec(FreeCAD.Vector(0, 0, 1))
        if obj.TypeId == "App::Line":
            return rot.multVec(FreeCAD.Vector(1, 0, 0))
        if obj.TypeId == "PartDesign::Line":
            return rot.multVec(FreeCAD.Vector(0, 0, 1))
    except Exception:
        pass
    return None


def _links_to(user, obj):
    """¿user usa a obj en algo más que su BaseFeature (caras, aristas, croquis apoyados...)?"""
    for prop in user.PropertiesList:
        if prop in ("BaseFeature", "_Body"):
            continue
        try:
            if "Link" not in user.getTypeIdOfProperty(prop):
                continue
            value = getattr(user, prop)
        except Exception:
            continue
        for item in (value if isinstance(value, (list, tuple)) else [value]):
            if item is obj or (isinstance(item, tuple) and item and item[0] is obj):
                return True
    return False


# --- Panel -------------------------------------------------------------------


class MoveFacePanel(dp.SwPanel):
    TRANSACTION = "Mover cara"
    NOTHING = "Elegí al menos una cara plana."

    @property
    def FAIL(self):
        if self.spec["mode"] == ROTATE:
            # p. ej. girada hacia abajo la cara atravesaría la de enfrente
            return "FreeCAD no pudo girar la cara así: probá con Invertir dirección o un ángulo menor."
        return "FreeCAD no pudo mover la cara así: probá con una distancia menor."

    def __init__(self, obj, faces=None):
        self.spec = read_spec(getattr(obj, MARK, ""))
        self.faces = list(faces) if faces is not None else self._initial_faces(obj)
        self.direction = None
        ref = self.spec.get("dir")
        if ref:
            ref_obj = obj.Document.getObject(ref[0])
            if ref_obj is not None:
                self.direction = (ref_obj, ref[1])
        self.hinge = self.spec.get("hinge") or ""
        gdoc = FreeCADGui.getDocument(obj.Document.Name)
        if gdoc.getInEdit() is not None and not obj.Document.HasPendingTransaction:
            # Editar una existente: sin modo edición de FreeCAD, así se puede cambiar Pad <-> Pocket
            gdoc.resetEdit()
        super().__init__(obj)

    @staticmethod
    def _initial_faces(obj):
        try:
            ref = obj.Base if obj.TypeId == DRAFT else obj.Profile
            return list(ref[1]) if ref and ref[0] is not None else []
        except Exception:
            return []

    # --- interfaz

    def _build(self):
        from swui import paths
        from swui.compat import QtGui

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(self.obj.Label)
        icon = paths.icon("fork/move_face")
        if icon:
            self.form.setWindowIcon(QtGui.QIcon(icon))
        box = QtWidgets.QVBoxLayout(self.form)

        top = QtWidgets.QGroupBox("Mover cara")
        tl = QtWidgets.QVBoxLayout(top)
        self.group = QtWidgets.QButtonGroup(self.form)
        self.radios = {}
        for text, mode in MODES:
            radio = QtWidgets.QRadioButton(text, top)
            radio.setChecked(mode == self.spec["mode"])
            radio.toggled.connect(lambda on, m=mode: self._mode(m) if on else None)
            self.group.addButton(radio)
            tl.addWidget(radio)
            self.radios[mode] = radio
        tl.addWidget(QtWidgets.QLabel("Caras (clic en la pieza):"))
        self.list = dp.pick_list(self.remove_current, self.clear, height=70)
        self.list.setMaximumHeight(110)  # que entren los parámetros en una pantalla de 768
        self.list.itemClicked.connect(lambda *_a: self._activate(self.list))
        self.list.currentRowChanged.connect(lambda *_a: self._draw())
        tl.addWidget(self.list)
        box.addWidget(top)

        params = QtWidgets.QGroupBox("Parámetros")
        self.params = QtWidgets.QFormLayout(params)
        self.dir_box = dp.RefBox(self._activate)
        self.dir_box.setPlaceholderText("Arista, cara plana o plano")
        self.dir_box.setToolTip("Vacía: se usan ΔX ΔY ΔZ")
        self.hinge_box = dp.RefBox(self._activate)
        self.hinge_box.setPlaceholderText("Arista recta de la cara")
        self.flip = QtWidgets.QCheckBox("Invertir dirección")
        self.flip.setChecked(bool(self.spec["flip"]))
        self.flip.toggled.connect(self._changed)
        locked = self._locked()
        self.distance = dp._spin(float(self.spec["distance"]), " mm", 0.001, 100000.0)
        self.distance.valueChanged.connect(self._changed)
        self.deltas = []
        for value in self.spec["delta"]:
            spin = dp._spin(float(value), " mm", -100000.0, 100000.0)
            spin.valueChanged.connect(self._changed)
            self.deltas.append(spin)
        self.angle = dp._spin(float(self.spec["angle"]), "°", 0.01, 89.99)
        self.angle.valueChanged.connect(self._changed)
        if locked:
            for spin in (self.distance, self.angle):
                spin.setEnabled(False)
                spin.setToolTip("Controlado por una ecuación")
        self.rows = {}
        for key, text, widget in (("dir", "Dirección:", self.dir_box), ("hinge", "Eje de giro:", self.hinge_box),
                                  ("flip", "", self.flip), ("distance", "Distancia:", self.distance),
                                  ("dx", "ΔX:", self.deltas[0]), ("dy", "ΔY:", self.deltas[1]),
                                  ("dz", "ΔZ:", self.deltas[2]), ("angle", "Ángulo:", self.angle)):
            label = QtWidgets.QLabel(text)
            self.params.addRow(label, widget)
            self.rows[key] = (label, widget)
        box.addWidget(params)
        box.addWidget(self._message_label())
        box.addStretch(1)
        self.active = self.list
        self._refresh()

    def _locked(self):
        """La distancia o el ángulo atados a una ecuación (en la operación nativa)."""
        prop = "Angle" if self.obj.TypeId == DRAFT else "Length"
        return self._has_expression(prop)

    def _mode(self, mode):
        if mode == self.spec["mode"]:
            return
        self.spec["mode"] = mode
        remember_mode(mode)
        self.active = self.list
        self._refresh()
        self._changed()

    def _activate(self, widget):
        self.active = widget
        self._paint_active()

    def _paint_active(self):
        for w in (self.list, self.dir_box, self.hinge_box):
            qss = dp.ACTIVE_QSS if w is self.active else ""
            w.setStyleSheet(("QListWidget { %s }" % qss) if (w is self.list and qss) else qss)

    def _refresh(self):
        mode = self.spec["mode"]
        has_dir = self.direction is not None
        show = {"dir": mode == TRANSLATE, "hinge": mode == ROTATE, "flip": True,
                "distance": mode == OFFSET or (mode == TRANSLATE and has_dir),
                "dx": mode == TRANSLATE and not has_dir, "dy": mode == TRANSLATE and not has_dir,
                "dz": mode == TRANSLATE and not has_dir, "angle": mode == ROTATE}
        for key, (label, widget) in self.rows.items():
            label.setVisible(show[key])
            widget.setVisible(show[key])
        self.dir_box.setText(self._ref_text(self.direction))
        self.hinge_box.setText("Arista<1>" if self.hinge else "")
        row = self.list.currentRow()
        self.list.clear()
        for sub, text in zip(self.faces, dp.sw_names(self.faces)):
            item = QtWidgets.QListWidgetItem(text)
            if self.base is None or dp._element(self.base.Shape, sub) is None:
                from swui.compat import QtGui

                item.setText(text + "  (no se encuentra: borrala y elegí otra)")
                item.setForeground(QtGui.QBrush(QtGui.QColor(dp.MISSING_COLOR)))
            self.list.addItem(item)
        if 0 <= row < len(self.faces):
            self.list.setCurrentRow(row)
        self._paint_active()

    @staticmethod
    def _ref_text(ref):
        if not ref:
            return ""
        obj, sub = ref
        if sub.startswith("Edge"):
            return "Arista<1> (%s)" % obj.Label
        if sub.startswith("Face"):
            return "Cara<1> (%s)" % obj.Label
        return obj.Label

    def remove_current(self, *_a):
        row = self.list.currentRow()
        if 0 <= row < len(self.faces):
            self.faces = self.faces[:row] + self.faces[row + 1:]
            self._refresh()
            self.preview()

    def clear(self, *_a):
        self.faces = []
        self._refresh()
        self.preview()

    # --- selección

    def _to_base(self, obj, sub):
        """Arista/cara tocada (en el sólido anterior o en la vista previa) -> nombre en el anterior."""
        if self.base is None:
            return None
        if obj == self.base:
            return sub
        if obj == self.obj and self.valid:
            return dp.to_base(self.obj.Shape, sub, self.base.Shape)
        return None

    def _pick(self, obj, sub):
        if self.active is self.dir_box:
            ref = None
            if sub and obj in (self.base, self.obj):
                name = self._to_base(obj, sub)
                ref = (self.base, name) if name else None
            elif sub:
                ref = (obj, sub)
            elif obj.TypeId in ("App::Plane", "PartDesign::Plane", "App::Line", "PartDesign::Line"):
                ref = (obj, "")
            if ref is None or direction_of(*ref) is None:
                return False
            self.direction = ref
            self.active = self.list
            return True
        if sub.startswith("Edge"):
            if self.spec["mode"] != ROTATE:
                return False
            name = self._to_base(obj, sub)
            if name is None or not _is_line(dp._element(self.base.Shape, name)):
                return False
            self.hinge = name
            self.active = self.list
            return True
        if not sub.startswith("Face"):
            return False
        if obj == self.obj and self.valid and int(sub[4:]) - 1 in self.yellow:
            geo = dp._element(self.obj.Shape, sub)  # cara amarilla: sacar la cara movida más cercana
            gone = dp.nearest(geo, self.base.Shape, self.faces) if geo is not None else None
            if gone is None:
                return False
            self.faces = [f for f in self.faces if f != gone]
            return True
        name = self._to_base(obj, sub)
        if name is None:
            return False
        if self.active is self.hinge_box:
            self.active = self.list
        self.faces = dp.toggle(self.faces, name)
        return True

    # --- operación nativa

    def _normal(self):
        face = dp._element(self.base.Shape, self.faces[0])
        return face_normal(face)

    def _swap(self, type_id):
        """Cambiar la operación por otra (Pad <-> Pocket <-> Draft), en el mismo lugar del Cuerpo."""
        from swui.fork import feature_tree as ft
        from swui.fork import multibody

        old = self.obj
        body = ft.body_of(old)
        if body is None:
            return "La operación no está en un Cuerpo."
        if any(u is not body and _links_to(u, old) for u in old.InList):
            return ("Otras operaciones usan esta cara movida: para pasar de agregar a quitar material "
                    "(o a girar) hay que hacer otro Mover cara.")
        new = self.doc.addObject(type_id, {PAD: "Pad", POCKET: "Pocket", DRAFT: "Draft"}[type_id])
        body.insertObject(new, old, True)
        new.addProperty("App::PropertyString", MARK, "SWUI", "Mover cara (fork de LikeSolidWorks UI)")
        new.setEditorMode(MARK, 2)
        for path, expr in old.ExpressionEngine:
            if path in new.PropertiesList:
                try:
                    new.setExpression(path, expr)
                except Exception:
                    pass
        label, old_name = old.Label, old.Name
        was_tip = body.Tip is old
        body.removeObject(old)
        self.doc.removeObject(old_name)
        if was_tip:
            multibody._set_tip(body, new)
        multibody._keep_label(new, label)
        self.visible.pop(old_name, None)
        self.visible[new.Name] = False
        self.obj = new
        self.base = new.BaseFeature
        return ""

    def _apply(self):
        mode = self.spec["mode"]
        self.spec.update({"flip": self.flip.isChecked(), "distance": self.distance.value(),
                          "delta": [s.value() for s in self.deltas], "angle": self.angle.value(),
                          "hinge": self.hinge,
                          "dir": [self.direction[0].Name, self.direction[1]] if self.direction else None})
        if self.base is None:
            return "No hay sólido antes de esta operación."
        if not self.faces:
            return ""
        problem = faces_problem(self.base.Shape, self.faces, same_plane=(mode == ROTATE))
        if problem:
            return problem
        if mode == ROTATE:
            if not self.hinge:
                return "Elegí el eje de giro: una arista recta de la cara."
            neutral, pull, problem = hinge_refs(self.base.Shape, self.faces, self.hinge)
            if problem:
                return problem
            problem = self._swap(DRAFT) if self.obj.TypeId != DRAFT else ""
            if problem:
                return problem
            self._write_spec()
            self.obj.Base = (self.base, self.faces)
            if self.obj.NeutralPlane != (self.base, [neutral]):
                self.obj.NeutralPlane = (self.base, [neutral])
            if self.obj.PullDirection != (self.base, [pull]):
                self.obj.PullDirection = (self.base, [pull])
            self._set("Angle", self.angle.value())
            self._set("Reversed", self.flip.isChecked())
            return ""
        direction = direction_of(*self.direction) if (mode == TRANSLATE and self.direction) else None
        n = self._normal()
        move = normal_move(mode, (n.x, n.y, n.z), self.distance.value(), self.flip.isChecked(),
                           (direction.x, direction.y, direction.z) if direction is not None else None,
                           [s.value() for s in self.deltas])
        if abs(move) < TOL:
            return "Ese desplazamiento no mueve la cara (es paralelo a ella o vale cero)."
        wanted = native_type(mode, move)
        if self.obj.TypeId != wanted:
            problem = self._swap(wanted)
            if problem:
                return problem
        self._write_spec()
        if self.obj.Profile != (self.base, self.faces):
            self.obj.Profile = (self.base, self.faces)
        self._set("Type", "Length")
        self._set("Length", abs(move))
        return ""

    def _write_spec(self):
        text = json.dumps(self.spec, sort_keys=True)
        if getattr(self.obj, MARK, None) != text:
            setattr(self.obj, MARK, text)
        remember_mode(self.spec["mode"])

    def _ready(self):
        return bool(self.faces) and (self.spec["mode"] != ROTATE or bool(self.hinge))

    def _nothing(self):
        return not self.faces

    def _overlays(self, base, result):
        nodes = super()._overlays(base, result)
        if base is None:
            return nodes
        if result is None:
            picked = [dp._element(base, s) for s in self.faces]
            nodes.append(dp._faces_node([p for p in picked if p is not None], dp.PICKED_COLOR))
        if self.hinge and self.spec["mode"] == ROTATE:
            el = dp._element(base, self.hinge)
            if el is not None:
                nodes.append(dp._lines_node([el], dp.CURRENT_COLOR, dp.LINE_WIDTH + 1))
        row = self.list.currentRow()
        if 0 <= row < len(self.faces):
            el = dp._element(base, self.faces[row])
            if el is not None:
                nodes.append(dp._lines_node([el], dp.CURRENT_COLOR, dp.LINE_WIDTH + 1))
        return nodes


def _choose(obj):
    return MoveFacePanel if hasattr(obj, MARK) else None


# --- Comando -------------------------------------------------------------------


def _body_for(doc, obj):
    """Cuerpo de lo elegido; a un sólido suelto (STEP) se le arma un Cuerpo que arranca de él."""
    from swui.fork import multibody

    body = obj if obj.TypeId == "PartDesign::Body" else multibody.body_of(obj)
    if body is not None:
        return body
    try:
        solid = obj.isDerivedFrom("Part::Feature") and bool(obj.Shape.Solids)
    except Exception:
        solid = False
    if not solid:
        return None
    body = doc.addObject("PartDesign::Body", "Body")
    body.BaseFeature = obj
    body.Placement = obj.Placement  # el Cuerpo toma la forma SIN la ubicación del sólido (1.1.4)
    obj.Visibility = False
    doc.recompute()  # que el sólido de arranque (BaseFeature del Cuerpo) tenga su forma
    return body


def _active_body(doc):
    try:
        body = FreeCADGui.ActiveDocument.ActiveView.getActiveObject("pdbody")
        if body is not None:
            return body
    except Exception:
        pass
    from swui.fork import multibody

    bodies = multibody.solid_bodies(doc)
    return bodies[0] if len(bodies) == 1 else None


def start(doc=None):
    """Crear el Mover cara (con las caras ya elegidas, si hay) y abrir el panel."""
    from swui.fork import multibody

    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return None
    if FreeCADGui.Control.activeDialog():
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), LABEL,
                                          "Cerrá primero el panel que está abierto.")
        return None
    sels = FreeCADGui.Selection.getSelectionEx(doc.Name)
    doc.openTransaction(LABEL)
    try:
        body = _body_for(doc, sels[0].Object) if sels else _active_body(doc)
        if body is None or (body.Tip is None and body.BaseFeature is None):
            doc.abortTransaction()
            QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), LABEL,
                                              "Elegí una cara plana de la pieza (o activá un Cuerpo con sólido).")
            return None
        obj = body.newObject(PAD, "Pad")
        obj.addProperty("App::PropertyString", MARK, "SWUI", "Mover cara (fork de LikeSolidWorks UI)")
        obj.setEditorMode(MARK, 2)
        start = read_spec("")
        start["mode"] = last_mode()  # como SW: abre en el último modo usado
        setattr(obj, MARK, json.dumps(start, sort_keys=True))
        multibody._keep_label(obj, next_label(set(o.Label for o in doc.Objects)))
        multibody._set_tip(body, obj)
        base = obj.BaseFeature
        faces = []
        for sel in sels:
            for sub in sel.SubElementNames:
                sub = sub.split(".")[-1]
                if not sub.startswith("Face") or base is None:
                    continue
                if sel.Object in (base, body.BaseFeature) or multibody.body_of(sel.Object) is None:
                    name = sub
                else:
                    name = dp.to_base(sel.Object.Shape, sub, base.Shape)
                if name and name not in faces:
                    faces.append(name)
        FreeCADGui.Selection.clearSelection()
        panel = MoveFacePanel(obj, faces)
        dp._state["panel"] = panel
        FreeCADGui.Control.showDialog(panel)
        return obj
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Mover cara:\n%s\n" % traceback.format_exc())
        dp._state["panel"] = None
        if doc.HasPendingTransaction:
            doc.abortTransaction()
        return None


class _MoveFaceCommand:
    def GetResources(self):
        from swui import paths

        return {"MenuText": LABEL, "ToolTip": "Equidistanciar, trasladar o girar caras planas (como SW)",
                "Pixmap": paths.icon("fork/move_face") or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        start()


def install():
    if _choose not in dp.CHOOSERS:
        dp.CHOOSERS.append(_choose)
    try:
        FreeCADGui.addCommand(COMMAND, _MoveFaceCommand())
    except Exception:
        pass  # ya registrado
