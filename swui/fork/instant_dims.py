# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Cotas con doble clic, como en SOLIDWORKS (versión liviana de Instant3D).

- Doble clic en una operación del árbol, o en una cara de la pieza (la
  operación que la creó), muestra sobre el modelo sus cotas: las del croquis
  (distancias, Ø, R, ángulos) y las de la operación (profundidad de
  Extruir/Cortar, radio de Redondeo, distancia de Chaflán, ángulo de
  Revolución). Como en SW, el doble clic ya no abre el diálogo de FreeCAD:
  para eso está clic derecho -> Editar operación.
- Croquis, como en SW 2018: UN clic en el árbol (también los de adentro de
  una operación) muestra sus cotas; el doble clic lo abre (lo de FreeCAD).
- Clic en un valor abre la cajita "Modificar" (valor, ✓, ✗ y reconstruir);
  acepta "12,5", "12.5", "1/2 in"... (unidades de FreeCAD; sin unidad: mm o °).
  Se puede deshacer.
- Una cota atada a una ecuación se muestra con Σ y no se cambia desde acá.
- Esc, un clic en otro lado de la vista o cambiar de documento las esconde.

Dibujo: líneas de cota en la escena 3D (pivy, encima de todo) y los valores
como botones planos encima de la vista, que siguen a la cámara.
"""

import math
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

VIEW_CLASS = "Gui::View3DInventor"
WB_NAME = "LikeSolidWorksUIWorkbench"
UNDEF = -2000  # Sketcher::GeoEnum::GeoUndef
LINE_COLOR = (0.15, 0.15, 0.15)
LABEL_QSS = ("QPushButton { color: #000000; background: rgba(247,247,247,170); border: none;"
             " padding: 0px 2px; font-size: 10pt; min-width: 0px; }"  # el tema pone un ancho mínimo
             "QPushButton:hover { color: #ff8000; }")
SKETCH_DIMS = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")

_state = {"obj": None, "dims": [], "labels": [], "node": None, "view": None, "camera": None, "timer": None,
          "by_click": False}  # by_click: mostradas por un clic en un croquis (se van al elegir otra cosa)
_filters = {}


# --- Formato y entrada (sin FreeCAD, probables en el test) -------------


def fmt(value, kind="length"):
    """12.5 -> '12,5'; 100.0 -> '100'; ángulos con °."""
    text = ("%.3f" % value).rstrip("0").rstrip(".").replace(".", ",")
    if text in ("-0", ""):
        text = "0"
    return text + ("°" if kind == "angle" else "")


def parse(text, kind="length"):
    """Texto del usuario -> número en mm (o grados). None si no se entiende."""
    raw = (text or "").strip().replace(",", ".").replace("°", " deg")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        pass
    try:
        q = FreeCAD.Units.parseQuantity(raw)
        if kind == "angle":
            return float(q.getValueAs("deg"))
        return float(q.getValueAs("mm"))
    except Exception:
        return None


def perpendicular_away(a, b, center):
    """Vector 2D unitario perpendicular a a-b que se aleja de center (para ubicar la cota)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy) or 1.0
    px, py = -dy / n, dx / n
    mx, my = (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0
    if (mx - center[0]) * px + (my - center[1]) * py < 0:
        px, py = -px, -py
    return px, py


# --- Qué cotas tiene cada cosa ---------------------------------------------


class Dim:
    """Una cota: dibujo (puntos globales), texto y a qué valor está atada."""

    def __init__(self, text, value, kind, setter, lines, label_at, arrows=(), locked=False):
        self.text, self.value, self.kind = text, value, kind
        self.setter = setter  # ("sketch", croquis, índice) o ("prop", objeto, propiedad)
        self.lines = lines  # [(p, q)] en coordenadas globales
        self.label_at = label_at
        self.arrows = arrows  # [(punta, dirección)]
        self.locked = locked  # atada a una ecuación


def _v(x, y=0.0, z=0.0):
    return FreeCAD.Vector(x, y, z)


def _expressions(obj):
    try:
        return [path for path, _e in obj.ExpressionEngine]
    except Exception:
        return []


def _constraint_locked(sketch, index, name):
    wanted = [".Constraints[%d]" % index] + ([".Constraints.%s" % name] if name else [])
    return any(p in wanted for p in _expressions(sketch))


def _sketch_center(sketch):
    try:
        bb = sketch.Shape.BoundBox
        plc = sketch.getGlobalPlacement().inverse()
        c = plc.multVec(bb.Center)
        return (c.x, c.y), max(bb.DiagonalLength, 1.0)
    except Exception:
        return (0.0, 0.0), 10.0


def _point(sketch, geo, pos):
    p = sketch.getPoint(geo, pos)
    return (p.x, p.y)


def _line_ends(sketch, geo):
    return _point(sketch, geo, 1), _point(sketch, geo, 2)


def _projection_on_line(sketch, geo, p):
    a, b = _line_ends(sketch, geo)
    dx, dy = b[0] - a[0], b[1] - a[1]
    n2 = dx * dx + dy * dy or 1.0
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n2
    return (a[0] + t * dx, a[1] + t * dy)


def _is_line(sketch, geo):
    try:
        g = sketch.Geometry[geo] if geo >= 0 else sketch.ExternalGeo[-geo - 1]
        return type(g).__name__ == "LineSegment"
    except Exception:
        return False


def sketch_dims(sketch):
    """Cotas de un croquis (las que mandan, no las de referencia)."""
    plc = sketch.getGlobalPlacement()
    center, size = _sketch_center(sketch)
    off = max(2.0, 0.08 * size)
    out = []
    for i, c in enumerate(sketch.Constraints):
        if c.Type not in SKETCH_DIMS or not getattr(c, "Driving", True):
            continue
        try:
            out.append(_sketch_dim(sketch, plc, i, c, center, off))
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Cota %d:\n%s\n" % (i, traceback.format_exc()))
    return [d for d in out if d is not None]


def _sketch_dim(sketch, plc, i, c, center, off):
    g = lambda p: plc.multVec(_v(p[0], p[1]))  # noqa: E731
    locked = _constraint_locked(sketch, i, c.Name)
    setter = ("sketch", sketch, i)
    if c.Type in ("Radius", "Diameter"):
        geo = sketch.Geometry[c.First]
        cen = _point(sketch, c.First, 3)
        r = geo.Radius
        ang = math.radians(45)
        rim = (cen[0] + r * math.cos(ang), cen[1] + r * math.sin(ang))
        out = (cen[0] + (r + off) * math.cos(ang), cen[1] + (r + off) * math.sin(ang))
        # Diámetro: de lado a lado; radio: desde el centro
        start = (cen[0] - r * math.cos(ang), cen[1] - r * math.sin(ang)) if c.Type == "Diameter" else cen
        prefix = "Ø" if c.Type == "Diameter" else "R"
        d = (rim[0] - start[0], rim[1] - start[1])
        n = math.hypot(*d) or 1.0
        return Dim(prefix + fmt(c.Value), c.Value, "length", setter,
                   [(g(start), g(out))], g(out), [(g(rim), plc.Rotation.multVec(_v(d[0] / n, d[1] / n)))], locked)
    if c.Type == "Angle":
        at = _point(sketch, c.First, 1) if c.Second == UNDEF else _line_ends(sketch, c.First)[0]
        deg = math.degrees(c.Value)
        return Dim(fmt(deg, "angle"), deg, "angle", setter, [], g((at[0] + off, at[1] + off)), (), locked)
    # Distancias
    if c.Second == UNDEF:
        if c.FirstPos == 0:
            a, b = _line_ends(sketch, c.First)
        else:
            a, b = (0.0, 0.0), _point(sketch, c.First, c.FirstPos)
    else:
        a = _point(sketch, c.First, c.FirstPos) if c.FirstPos else _line_ends(sketch, c.First)[0]
        if c.SecondPos == 0 and _is_line(sketch, c.Second):
            b = _projection_on_line(sketch, c.Second, a)
        else:
            b = _point(sketch, c.Second, c.SecondPos)
    if c.Type == "DistanceX":
        y = min(a[1], b[1]) if (a[1] + b[1]) / 2.0 <= center[1] else max(a[1], b[1])
        a2, b2 = (a[0], y), (b[0], y)
    elif c.Type == "DistanceY":
        x = min(a[0], b[0]) if (a[0] + b[0]) / 2.0 <= center[0] else max(a[0], b[0])
        a2, b2 = (x, a[1]), (x, b[1])
    else:
        a2, b2 = a, b
    px, py = perpendicular_away(a2, b2, center)
    if (a2[0] - b2[0]) ** 2 + (a2[1] - b2[1]) ** 2 < 1e-12:
        px, py = 0.0, 1.0
    a3 = (a2[0] + px * off, a2[1] + py * off)
    b3 = (b2[0] + px * off, b2[1] + py * off)
    lines = [(g(a), g(a3)), (g(b), g(b3)), (g(a3), g(b3))]
    d = (b3[0] - a3[0], b3[1] - a3[1])
    n = math.hypot(*d) or 1.0
    u = plc.Rotation.multVec(_v(d[0] / n, d[1] / n))
    mid = ((a3[0] + b3[0]) / 2.0, (a3[1] + b3[1]) / 2.0)
    return Dim(fmt(abs(c.Value)), c.Value, "length", setter, lines, g(mid), [(g(b3), u), (g(a3), -u)], locked)


def _profile(obj):
    from swui.fork import feature_tree as ft

    return ft._profile_sketch(obj)


def feature_dims(obj):
    """Cotas propias de la operación (profundidad, radio...)."""
    out = []
    kind = getattr(obj, "TypeId", "")
    locked = lambda prop: any(p in ("." + prop, prop) for p in _expressions(obj))  # noqa: E731
    sketch = _profile(obj)
    if kind in ("PartDesign::Pad", "PartDesign::Pocket") and sketch is not None:
        if getattr(obj, "Type", "") in ("Length", "TwoLengths"):
            plc = sketch.getGlobalPlacement()
            normal = plc.Rotation.multVec(_v(0, 0, 1))
            sign = 1.0 if kind == "PartDesign::Pad" else -1.0
            if getattr(obj, "Reversed", False):
                sign = -sign
            length = obj.Length.Value
            (cx, cy), size = _sketch_center(sketch)
            side = plc.Rotation.multVec(_v(1, 0, 0)) * max(2.0, 0.08 * size)
            base = plc.multVec(_v(cx, cy)) + side
            if getattr(obj, "Midplane", False):
                base = base - normal * (sign * length / 2.0)
            tip = base + normal * (sign * length)
            u = normal * sign
            out.append(Dim(fmt(length), length, "length", ("prop", obj, "Length"),
                           [(base, tip)], (base + tip) * 0.5, [(tip, u), (base, -u)], locked("Length")))
    elif kind in ("PartDesign::Fillet", "PartDesign::Chamfer"):
        prop = "Radius" if kind == "PartDesign::Fillet" else "Size"
        at = _first_edge_mid(obj)
        if at is not None:
            value = getattr(obj, prop).Value
            text = ("R" if prop == "Radius" else "") + fmt(value)
            out.append(Dim(text, value, "length", ("prop", obj, prop), [], at, (), locked(prop)))
    elif kind in ("PartDesign::Revolution", "PartDesign::Groove") and sketch is not None:
        (cx, cy), _size = _sketch_center(sketch)
        at = sketch.getGlobalPlacement().multVec(_v(cx, cy))
        value = obj.Angle.Value
        out.append(Dim(fmt(value, "angle"), value, "angle", ("prop", obj, "Angle"), [], at, (), locked("Angle")))
    return out


def _first_edge_mid(obj):
    try:
        from swui.fork import sketch_model_edges as me

        base, subs = obj.Base
        shape = me._global_shape(base)
        edge = shape.getElement(subs[0])
        return edge.valueAt((edge.FirstParameter + edge.LastParameter) / 2.0)
    except Exception:
        return None


def dims_of(obj):
    from swui.fork import feature_tree as ft

    if ft.is_sketch(obj):
        return sketch_dims(obj)
    out = feature_dims(obj)
    sketch = _profile(obj)
    if sketch is not None:
        out = sketch_dims(sketch) + out
    return out


# --- Mostrar / esconder -------------------------------------------------


def _viewport():
    try:
        sub = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea).activeSubWindow()
        view = sub.widget() if sub is not None else None
        if view is None or view.metaObject().className() != VIEW_CLASS:
            return None
        return view.findChildren(QtWidgets.QGraphicsView)[0].viewport()
    except Exception:
        return None


def show(obj):
    """Mostrar las cotas de obj (operación o croquis)."""
    hide()
    vp = _viewport()
    if vp is None:
        return 0
    dims = dims_of(obj)
    if not dims:
        FreeCADGui.getMainWindow().statusBar().showMessage("%s no tiene cotas para mostrar." % obj.Label, 4000)
        return 0
    view = FreeCADGui.ActiveDocument.ActiveView
    _state.update(obj=obj, dims=dims, view=view, camera=None)
    _draw_lines(view, dims)
    for dim in dims:
        button = QtWidgets.QPushButton(("Σ " if dim.locked else "") + dim.text, vp)
        button.setFlat(True)
        button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        button.setStyleSheet(LABEL_QSS)
        button.setToolTip("Atada a una ecuación: se cambia en Ecuaciones" if dim.locked else "Clic para modificar")
        button.adjustSize()
        button.setFixedWidth(button.fontMetrics().horizontalAdvance(button.text()) + 8)  # no el ancho mínimo de botón
        button.clicked.connect(lambda *_a, d=dim, b=button: _clicked(d, b))
        button.show()
        _state["labels"].append((button, dim))
    _place()
    timer = QtCore.QTimer()
    timer.timeout.connect(_follow)
    timer.start(40)
    _state["timer"] = timer
    return len(dims)


def hide():
    timer = _state.get("timer")
    if timer is not None:
        timer.stop()
    for button, _d in _state["labels"]:
        try:
            button.hide()
            button.deleteLater()
        except Exception:
            pass
    node, view = _state.get("node"), _state.get("view")
    if node is not None and view is not None:
        try:
            view.getSceneGraph().removeChild(node)
        except Exception:
            pass
    _state.update(obj=None, dims=[], labels=[], node=None, view=None, camera=None, timer=None)


def shown():
    return _state["obj"] is not None


def _draw_lines(view, dims):
    from pivy import coin

    sep = coin.SoAnnotation()
    color = coin.SoBaseColor()
    color.rgb = LINE_COLOR
    style = coin.SoDrawStyle()
    style.lineWidth = 1
    sep.addChild(color)
    sep.addChild(style)
    segs = []
    for dim in dims:
        segs += dim.lines
        for tip, u in dim.arrows:
            size = max(0.6, min(3.0, _span(dim) / 8.0))
            side = _side(u)
            segs.append((tip, tip - u * size + side * (size * 0.35)))
            segs.append((tip, tip - u * size - side * (size * 0.35)))
    if segs:
        coords = coin.SoCoordinate3()
        pts = []
        for p, q in segs:
            pts += [(p.x, p.y, p.z), (q.x, q.y, q.z)]
        coords.point.setValues(0, len(pts), pts)
        lines = coin.SoLineSet()
        lines.numVertices.setValues(0, len(segs), [2] * len(segs))
        sep.addChild(coords)
        sep.addChild(lines)
    view.getSceneGraph().addChild(sep)
    _state["node"] = sep


def _span(dim):
    if dim.lines:
        p, q = dim.lines[-1]
        return (q - p).Length
    return 10.0


def _side(u):
    """Una perpendicular a u (para las alitas de la flecha)."""
    ref = _v(0, 0, 1) if abs(u.z) < 0.9 else _v(1, 0, 0)
    s = u.cross(ref)
    return s * (1.0 / s.Length) if s.Length > 1e-9 else _v(1, 0, 0)


def _place():
    view, vp = _state["view"], _viewport()
    if view is None or vp is None:
        return
    ratio = vp.devicePixelRatioF()
    for button, dim in _state["labels"]:
        x, y = view.getPointOnViewport(dim.label_at)
        button.move(int(x / ratio - button.width() / 2), int(vp.height() - y / ratio - button.height() / 2))


def _follow():
    try:
        if (FreeCAD.ActiveDocument is None or _state["obj"] is None
                or _state["obj"].Document is not FreeCAD.ActiveDocument or _editing()):
            hide()  # otro documento, o se abrió el croquis/la operación
            return
        from swui.fork import sketch_model_edges as me

        key = (me._camera_key(_state["view"]), _viewport().size().width(), _viewport().size().height())
        if key != _state["camera"]:
            _state["camera"] = key
            _place()
    except Exception:
        hide()


# --- Modificar ---------------------------------------------------------------


def apply_value(dim, value):
    """Poner el valor nuevo (con deshacer) y reconstruir."""
    kind, obj, which = dim.setter
    doc = obj.Document
    doc.openTransaction("Modificar cota")
    try:
        if kind == "sketch":
            unit = "deg" if dim.kind == "angle" else "mm"
            obj.setDatum(which, FreeCAD.Units.Quantity("%r %s" % (value, unit)))
        else:
            setattr(obj, which, value)
        doc.recompute()
    except Exception:
        doc.abortTransaction()
        FreeCAD.Console.PrintError("[SWUI fork] No se pudo cambiar la cota:\n%s\n" % traceback.format_exc())
        return False
    doc.commitTransaction()
    return True


def _clicked(dim, button):
    """
    Clic o doble clic en la cota: "Modificar" una sola vez. En SW se hace doble clic;
    sin esta espera el segundo clic caía fuera de la ventanita y la cerraba (probado
    con el mouse, 2026-10-28). Se espera lo que dura un doble clic y se abre.
    """
    if _state.get("pending"):
        return  # segundo clic del doble clic
    _state["pending"] = True

    def run():
        _state["pending"] = False
        try:
            if button.isVisible():
                _modify(dim, button)
        except RuntimeError:
            pass  # las cotas se escondieron mientras tanto

    QtCore.QTimer.singleShot(QtWidgets.QApplication.doubleClickInterval() + 30, run)


def _modify(dim, button):
    if dim.locked:
        FreeCADGui.getMainWindow().statusBar().showMessage(
            "Esta cota está atada a una ecuación: se cambia desde las ecuaciones.", 5000)
        try:
            from swui.fork import equations

            equations.show_dialog()
        except Exception:
            pass
        return
    box = QtWidgets.QFrame(FreeCADGui.getMainWindow(), QtCore.Qt.WindowType.Popup)
    box.setObjectName("SWUI_Modificar")
    lay = QtWidgets.QVBoxLayout(box)
    lay.setContentsMargins(6, 4, 6, 6)
    lay.addWidget(QtWidgets.QLabel("Modificar"))
    edit = QtWidgets.QLineEdit(fmt(dim.value if dim.kind == "angle" else abs(dim.value), dim.kind).rstrip("°"))
    edit.selectAll()
    lay.addWidget(edit)
    row = QtWidgets.QHBoxLayout()
    ok, cancel, rebuild = (QtWidgets.QToolButton() for _i in range(3))
    for b, text, tip in ((ok, "✓", "Aceptar"), (cancel, "✗", "Cancelar"), (rebuild, "↻", "Reconstruir sin cerrar")):
        b.setText(text)
        b.setToolTip(tip)
        row.addWidget(b)
    lay.addLayout(row)

    def commit(close):
        value = parse(edit.text(), dim.kind)
        if value is None:
            edit.setStyleSheet("background: #ffd6d6;")
            return
        obj = _state["obj"]
        if apply_value(dim, value) and obj is not None:
            if close:
                box.close()
            show(obj)  # posiciones y valores nuevos

    ok.clicked.connect(lambda *_a: commit(True))
    rebuild.clicked.connect(lambda *_a: commit(False))
    cancel.clicked.connect(box.close)
    edit.returnPressed.connect(lambda: commit(True))
    box.adjustSize()
    box.move(button.mapToGlobal(QtCore.QPoint(0, button.height())))
    box.show()
    edit.setFocus()


# --- Doble clic ------------------------------------------------------------


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


def _editing():
    try:
        return FreeCADGui.ActiveDocument is not None and FreeCADGui.ActiveDocument.getInEdit() is not None
    except Exception:
        return False


def _target(obj):
    from swui.fork import feature_tree as ft

    if obj is None or ft.body_of(obj) is None:
        return None
    return obj if (ft.is_feature(obj) or ft.is_sketch(obj)) else None


class _ViewFilter(QtCore.QObject):
    """Vista 3D: doble clic en una cara muestra las cotas; Esc o clic en otro lado las esconde."""

    def eventFilter(self, viewport, event):
        try:
            t = event.type()
            if t == QtCore.QEvent.Type.KeyPress and event.key() == QtCore.Qt.Key.Key_Escape and shown():
                hide()
                return False
            if t == QtCore.QEvent.Type.MouseButtonPress and shown():
                hide()
                return False
            if (t != QtCore.QEvent.Type.MouseButtonDblClick or event.button() != QtCore.Qt.MouseButton.LeftButton
                    or not _in_workbench() or _editing()):
                return False
            pos = event.position() if hasattr(event, "position") else QtCore.QPointF(event.pos())
            from swui.fork import feature_tree as ft
            from swui.fork import sketch_model_edges as me

            view = FreeCADGui.ActiveDocument.ActiveView
            ratio = viewport.devicePixelRatioF()
            info = view.getObjectInfo(me.coin_point(pos.x(), pos.y(), viewport.height(), ratio))
            if not info:
                return False
            obj = FreeCAD.ActiveDocument.getObject(info.get("Object"))
            if _target(obj) is None:
                return False
            comp = info.get("Component", "")
            if comp.startswith("Face"):
                try:
                    obj = ft.creator(obj, obj.Shape.getElement(comp)) or obj
                except Exception:
                    pass
            show(obj)
            return True
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Cotas (vista):\n%s\n" % traceback.format_exc())
            return False


def row_at(tree, y):
    """
    Objeto del renglón de un cuerpo a la altura y. Por posición y no con itemAt: PySide
    da por borrados los renglones de FreeCAD apenas se los toca (ver tree_overlay).
    """
    from swui.fork import tree_overlay as to

    for _body, rows in to.body_rows(tree):
        for obj, box, *_rest in rows:
            if box[1] <= y < box[1] + box[3]:
                return obj
    return None


class _TreeFilter(QtCore.QObject):
    """Árbol: doble clic en una operación o croquis muestra sus cotas (no abre el diálogo)."""

    def eventFilter(self, viewport, event):
        try:
            if (event.type() != QtCore.QEvent.Type.MouseButtonDblClick
                    or event.button() != QtCore.Qt.MouseButton.LeftButton or not _in_workbench() or _editing()):
                return False
            tree = viewport.parent()
            while tree is not None and not isinstance(tree, QtWidgets.QTreeWidget):
                tree = tree.parent()
            if tree is None:
                return False
            pos = event.position() if hasattr(event, "position") else QtCore.QPointF(event.pos())
            obj = _target(row_at(tree, pos.y()))
            from swui.fork import feature_tree as ft

            if obj is None or ft.is_sketch(obj):
                return False  # croquis: el doble clic lo abre (las cotas salen con un clic)
            show(obj)
            return True
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Cotas (árbol):\n%s\n" % traceback.format_exc())
            return False


def _attach():
    try:
        mw = FreeCADGui.getMainWindow()
        mdi = mw.findChild(QtWidgets.QMdiArea)
        for sub in mdi.subWindowList():
            view = sub.widget()
            if view is None or view.metaObject().className() != VIEW_CLASS:
                continue
            for gv in view.findChildren(QtWidgets.QGraphicsView):
                vp = gv.viewport()
                if not vp.property("swui_dims"):
                    vp.setProperty("swui_dims", True)
                    vp.installEventFilter(_filters["view"])
        for tree in mw.findChildren(QtWidgets.QTreeWidget):
            if tree.metaObject().className() == "Gui::TreeWidget" and not tree.viewport().property("swui_dims"):
                tree.viewport().setProperty("swui_dims", True)
                tree.viewport().installEventFilter(_filters["tree"])
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Cotas:\n%s\n" % traceback.format_exc())


def sketch_to_show(selection):
    """
    Croquis cuyas cotas mostrar con un clic, como en SW 2018: uno solo elegido entero
    (desde el árbol, sin aristas ni puntos) y de un cuerpo. None si no.
    """
    from swui.fork import feature_tree as ft

    if len(selection) != 1 or selection[0].SubElementNames:
        return None
    obj = selection[0].Object
    return obj if ft.is_sketch(obj) and ft.body_of(obj) is not None else None


def _on_selection():
    try:
        if not _in_workbench() or _editing():
            return
        sketch = sketch_to_show(FreeCADGui.Selection.getSelectionEx())
        if sketch is not None:
            if _state["obj"] is not sketch:
                show(sketch)
        elif _state["obj"] is not None and _state.get("by_click"):
            hide()  # se eligió otra cosa: las cotas del croquis se van, como en SW
        _state["by_click"] = sketch is not None
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Cotas (selección):\n%s\n" % traceback.format_exc())


class _SelectionObserver:
    """Un clic en un croquis del árbol (también los de adentro de una operación) muestra sus cotas."""

    def addSelection(self, *_a):
        QtCore.QTimer.singleShot(0, _on_selection)

    def setSelection(self, *_a):
        QtCore.QTimer.singleShot(0, _on_selection)

    def removeSelection(self, *_a):
        QtCore.QTimer.singleShot(0, _on_selection)

    def clearSelection(self, *_a):
        QtCore.QTimer.singleShot(0, _on_selection)


def install():
    """Filtros de doble clic en la vista 3D y en el árbol (también al entrar al banco)."""
    if _filters:
        return
    _filters["view"] = _ViewFilter()
    _filters["tree"] = _TreeFilter()
    _filters["selection"] = _SelectionObserver()
    try:
        FreeCADGui.Selection.addObserver(_filters["selection"])
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Cotas: sin observador de selección.\n")
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        mdi.subWindowActivated.connect(lambda *_a: (_attach(), hide()))
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Cotas: no se encontró el área de ventanas.\n")
    _attach()
    from swui import layout

    if getattr(layout.enter, "_swui_dims", False):
        return
    original_enter, original_leave = layout.enter, layout.leave

    def enter(_original=original_enter):
        result = _original()
        _attach()
        return result

    def leave(_original=original_leave):
        hide()
        return _original()

    enter._swui_dims = leave._swui_dims = True
    layout.enter, layout.leave = enter, leave
