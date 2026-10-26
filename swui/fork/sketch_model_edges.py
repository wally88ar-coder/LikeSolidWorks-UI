# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Aristas y vértices del modelo dentro del croquis, como en SOLIDWORKS.

En SW, con un croquis abierto, al pasar el mouse cerca de una arista o vértice
de la pieza se resalta, y la cota inteligente o la línea se enganchan ahí. En
FreeCAD 1.1.4 el croquis solo ve lo suyo: primero hay que traer la arista con
"Convertir entidades" (Sketcher_Projection). Acá:

- Con una herramienta del croquis activa (cota, relación, línea, círculo...;
  FreeCAD les pone un cursor dibujado: BitmapCursor) o sin herramienta
  (flecha: seleccionando, p. ej. un punto del croquis + una arista del sólido
  para hacerlos coincidentes), al pasar el mouse a menos de SNAP_PX píxeles de
  una arista o vértice del sólido, se resalta en naranja (primero vértices,
  como SW). Arrastrando con un botón apretado no se resalta nada.
- Al hacer clic con algo resaltado: si el croquis no la tiene, se agrega como
  referencia (lo mismo que Convertir entidades: nada propio del addon queda en
  el archivo) y el clic se manda justo sobre ella, así la herramienta la toma
  aunque no se haya apuntado exacto.
- Si hay algo del propio croquis a menos del radio de selección de FreeCAD
  (View/PickRadius, 5 px), manda el croquis (no se resalta nada). Se mide en
  pantalla: la preselección de FreeCAD sin herramienta no siempre está al día.
  Los ejes del croquis no cuentan: una arista del sólido encima de un eje se
  resalta igual (y una vez traída, FreeCAD también la prefiere al eje).
- Candidatas: las aristas de las operaciones visibles del cuerpo del croquis
  y del objeto donde está apoyado. No se traen las de operaciones que dependen
  del croquis (sería una dependencia circular). Entre aristas superpuestas en
  la pantalla gana la que está sobre el plano del croquis.

Las posiciones en pantalla se calculan una vez por posición de cámara.
FreeCAD 26.3 ya permite acotar directo a las aristas del modelo: desde esa
versión esto no se instala (queda lo nativo).
"""

import math
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

VIEW_CLASS = "Gui::View3DInventor"
WB_NAME = "LikeSolidWorksUIWorkbench"
SKETCH = "Sketcher::SketchObject"
NATIVE_FROM = 26
SNAP_PX = 10  # distancia de enganche en píxeles
POINTS_PER_EDGE = 16
HIGHLIGHT = (1.0, 0.55, 0.0)  # naranja (resaltado de look_sw)
LINE_WIDTH = 4

_filter = None
_state = {"sketch": None, "cands": None, "camera": None, "screen": None, "hot": None, "node": None}


def native():
    try:
        return int(FreeCAD.Version()[0]) >= NATIVE_FROM
    except Exception:
        return False


# --- Cuentas (sin FreeCAD, probables en el test) ---------------------


def coin_point(x, y, height, ratio=1.0):
    """Punto del mouse (Qt: y hacia abajo) -> punto de la vista 3D (Coin: y hacia arriba, en píxeles reales)."""
    return (int(round(x * ratio)), int(round((height - y) * ratio)))


def qt_point(cx, cy, height, ratio=1.0):
    """Al revés que coin_point."""
    return (cx / ratio, height - cy / ratio)


def closest_on_segment(p, a, b):
    """(distancia, punto) más cercano a p sobre el segmento a-b (2D)."""
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length2))
    q = (ax + t * dx, ay + t * dy)
    return math.hypot(p[0] - q[0], p[1] - q[1]), q


def closest_on_polyline(p, pts):
    best = None
    for a, b in zip(pts, pts[1:]):
        found = closest_on_segment(p, a, b)
        if best is None or found[0] < best[0]:
            best = found
    return best


def choose(p, vertices, edges, snap=SNAP_PX):
    """
    Lo que se engancha cerca de p (pantalla). vertices = [(clave, (x, y), lejanía_al_plano)],
    edges = [(clave, [(x, y)...], lejanía_al_plano)]. Primero vértices; entre empatados
    (1 px) gana el más cercano al plano del croquis. Devuelve (clave, punto en pantalla) o None.
    """
    for group in ("v", "e"):
        found = []
        if group == "v":
            for key, q, depth in vertices:
                d = math.hypot(p[0] - q[0], p[1] - q[1])
                if d <= snap:
                    found.append((d, depth, key, q))
        else:
            for key, pts, depth in edges:
                hit = closest_on_polyline(p, pts) if len(pts) > 1 else None
                if hit is not None and hit[0] <= snap:
                    found.append((hit[0], depth, key, hit[1]))
        if found:
            best = min(d for d, *_r in found)
            near = [f for f in found if f[0] <= best + 1.0]
            _d, _depth, key, q = min(near, key=lambda f: (f[1], f[0]))
            return key, q
    return None


def already(sketch, obj, sub):
    """¿El croquis ya tiene esa referencia?"""
    for target, subs in getattr(sketch, "ExternalGeometry", []) or []:
        if getattr(target, "Name", target) == obj and sub in subs:
            return True
    return False


def external_index(sketch, obj, sub):
    """Número de la referencia en el croquis (ExternalEdgeN, desde 1), o None."""
    n = 0
    for target, subs in getattr(sketch, "ExternalGeometry", []) or []:
        for s in subs:
            n += 1
            if getattr(target, "Name", target) == obj and s == sub:
                return n
    return None


def depends_on(obj, sketch):
    """¿obj depende del croquis? (traerlo armaría una dependencia circular)"""
    try:
        return sketch in obj.OutListRecursive
    except Exception:
        return True


# --- Candidatas y pantalla --------------------------------------------


def _editing_sketch():
    try:
        vp = FreeCADGui.ActiveDocument.getInEdit()
        obj = vp.Object if vp is not None else None
    except Exception:
        return None
    return obj if obj is not None and getattr(obj, "TypeId", "") == SKETCH else None


def _global_shape(obj):
    """Forma del objeto en coordenadas globales (mismo orden de aristas/vértices)."""
    import Part

    try:
        parents = obj.getParents()
    except Exception:
        parents = []
    if parents:
        root, sub = parents[0]
        return Part.getShape(root, sub)
    return Part.getShape(obj)


def _candidates(sketch):
    """[(objeto, forma global)] cuyas aristas se pueden enganchar."""
    from swui.fork import feature_tree as ft

    objs = []
    body = ft.body_of(sketch)
    if body is not None:
        for f in ft.features(body):
            try:
                if f.ViewObject.Visibility and not depends_on(f, sketch):
                    objs.append(f)
            except Exception:
                pass
    try:
        for target, _subs in sketch.AttachmentSupport:
            if hasattr(target, "Shape") and target not in objs and not depends_on(target, sketch):
                objs.append(target)
    except Exception:
        pass
    out = []
    for obj in objs:
        try:
            shape = _global_shape(obj)
            if shape is not None and not shape.isNull() and shape.Edges:
                out.append((obj, shape))
        except Exception:
            pass
    return out


def _camera_key(view):
    try:
        cam = view.getCameraNode()
        size = tuple(view.getSize())
        fields = [cam.position.getValue().getValue(), cam.orientation.getValue().getValue()]
        for name in ("height", "heightAngle"):
            if hasattr(cam, name):
                fields.append(getattr(cam, name).getValue())
        return (str(fields), size)
    except Exception:
        return None


def _screen(view, sketch, cands):
    """Vértices y aristas en pantalla (Coin), con su lejanía al plano del croquis."""
    plc = sketch.getGlobalPlacement()
    normal = plc.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
    origin = plc.Base

    def depth(pt):
        return abs((pt - origin).dot(normal))

    vertices, edges = [], []
    for obj, shape in cands:
        for i, v in enumerate(shape.Vertexes):
            vertices.append(((obj.Name, "Vertex%d" % (i + 1)), tuple(view.getPointOnViewport(v.Point)),
                             depth(v.Point)))
        for i, e in enumerate(shape.Edges):
            try:
                pts = e.discretize(Number=POINTS_PER_EDGE)
            except Exception:
                continue
            screen = [tuple(view.getPointOnViewport(pt)) for pt in pts]
            edges.append(((obj.Name, "Edge%d" % (i + 1)), screen, max(depth(pt) for pt in pts), pts))
    return vertices, edges


def _find(view, sketch, coin, ratio=1.0):
    """(objeto, sub, punto Coin) enganchable cerca de coin, o None."""
    st = _state
    if st["sketch"] is not sketch:
        st.update(sketch=sketch, cands=_candidates(sketch), camera=None)
    key = _camera_key(view)
    if key is None or key != st["camera"]:
        st["screen"] = _screen(view, sketch, st["cands"])
        st["camera"] = key
    vertices, edges = st["screen"]
    found = choose(coin, vertices, [(k, s, d) for k, s, d, _p in edges], SNAP_PX * ratio)
    if found is None:
        return None
    (obj, sub), q = found
    return obj, sub, q


# --- Resaltado (Coin) ---------------------------------------------------


def _show(view, obj, sub):
    """Resaltar la arista/vértice en naranja, encima de todo."""
    from pivy import coin

    _hide(view)
    shape = None
    for o, s in _state["cands"] or []:
        if o.Name == obj:
            shape = s
    if shape is None:
        return
    sep = coin.SoAnnotation()
    color = coin.SoBaseColor()
    color.rgb = HIGHLIGHT
    style = coin.SoDrawStyle()
    style.lineWidth = LINE_WIDTH
    style.pointSize = 9
    coords = coin.SoCoordinate3()
    if sub.startswith("Vertex"):
        p = shape.Vertexes[int(sub[6:]) - 1].Point
        coords.point.setValues(0, 1, [(p.x, p.y, p.z)])
        mark = coin.SoMarkerSet()
        mark.markerIndex = coin.SoMarkerSet.CIRCLE_FILLED_9_9
    else:
        pts = shape.Edges[int(sub[4:]) - 1].discretize(Number=48)
        coords.point.setValues(0, len(pts), [(p.x, p.y, p.z) for p in pts])
        mark = coin.SoLineSet()
    for node in (color, style, coords, mark):
        sep.addChild(node)
    view.getSceneGraph().addChild(sep)
    _state["node"] = sep


def _hide(view=None):
    node = _state.get("node")
    if node is None:
        return
    try:
        (view or FreeCADGui.ActiveDocument.ActiveView).getSceneGraph().removeChild(node)
    except Exception:
        pass
    _state["node"] = None


def bring(sketch, obj_name, sub):
    """Agregar la referencia (como Convertir entidades). True si se agregó."""
    doc = sketch.Document
    obj = doc.getObject(obj_name)
    if obj is None or already(sketch, obj_name, sub) or depends_on(obj, sketch):
        return False
    doc.openTransaction("Referencia del modelo")
    try:
        sketch.addExternal(obj_name, sub)
        sketch.recompute()
    except Exception:
        doc.abortTransaction()
        FreeCAD.Console.PrintLog("[SWUI fork] Arista del modelo:\n%s\n" % traceback.format_exc())
        return False
    doc.commitTransaction()
    _state["sketch"] = None  # el croquis cambió: recalcular candidatas
    return True


# --- Filtro de eventos ---------------------------------------------------


def _active(viewport):
    """
    Croquis en edición, con una herramienta activa (cursor dibujado) o seleccionando
    (flecha: para elegir la arista y relacionarla con algo del croquis, como en SW).
    """
    if viewport.cursor().shape() not in (QtCore.Qt.CursorShape.BitmapCursor, QtCore.Qt.CursorShape.ArrowCursor):
        return None
    try:
        if FreeCADGui.activeWorkbench().name() != WB_NAME:
            return None
    except Exception:
        return None
    return _editing_sketch()


def _sketch_near(view, sketch, coin, radius):
    """
    ¿Hay algo del croquis (líneas, puntos, referencias ya traídas; no los ejes) a menos
    de radius del mouse? Se mide en pantalla en vez de mirar la preselección de FreeCAD,
    que sin herramienta no siempre está al día.
    """
    plc = sketch.getGlobalPlacement()
    shapes = []
    for geo in list(sketch.Geometry) + list(getattr(sketch, "ExternalGeo", [])[2:]):
        try:
            shapes.append(geo.toShape())
        except Exception:
            pass
    for shape in shapes:
        for v in shape.Vertexes:
            q = view.getPointOnViewport(plc.multVec(v.Point))
            if math.hypot(coin[0] - q[0], coin[1] - q[1]) <= radius:
                return True
        for e in shape.Edges:
            try:
                pts = [tuple(view.getPointOnViewport(plc.multVec(p))) for p in e.discretize(Number=POINTS_PER_EDGE)]
            except Exception:
                continue
            hit = closest_on_polyline(coin, pts)
            if hit is not None and hit[0] <= radius:
                return True
    return False


def _pick_radius():
    try:
        return FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View").GetFloat("PickRadius", 5.0)
    except Exception:
        return 5.0


def _hot_at(viewport, pos):
    """Arista/vértice del modelo enganchable en pos (Qt) del viewport, o None."""
    sketch = _active(viewport)
    if sketch is None:
        _state["sketch"] = None  # al volver al croquis se recalculan las candidatas
        return None
    ratio = viewport.devicePixelRatioF()
    view = FreeCADGui.ActiveDocument.ActiveView
    coin = coin_point(pos.x(), pos.y(), viewport.height(), ratio)
    if _sketch_near(view, sketch, coin, _pick_radius() * ratio):
        return None  # manda el croquis
    return _find(view, sketch, coin, ratio)


def _hover(viewport, pos, dragging):
    """Resaltar (o dejar de resaltar) lo que está cerca del mouse."""
    try:
        hot = None if dragging else _hot_at(viewport, pos)
        old = _state["hot"]
        if (hot and hot[:2]) != (old and old[:2]):
            view = FreeCADGui.ActiveDocument.ActiveView
            if hot is None:
                _hide(view)
            else:
                _show(view, hot[0], hot[1])
        _state["hot"] = hot
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Arista del modelo:\n%s\n" % traceback.format_exc())


def _send(viewport, kind, pos, button, buttons, modifiers):
    ev = QtGui.QMouseEvent(kind, pos, viewport.mapToGlobal(pos), button, buttons, modifiers)
    QtWidgets.QApplication.sendEvent(viewport, ev)


class _Filter(QtCore.QObject):
    def __init__(self):
        super().__init__()
        self.busy = False  # mientras se reenvía el clic
        self.swallow_release = False  # el soltar del clic que ya se atendió

    def eventFilter(self, viewport, event):
        if self.busy:
            return False
        t = event.type()
        if t == QtCore.QEvent.Type.MouseButtonRelease and self.swallow_release:
            self.swallow_release = False
            return True
        if t not in (QtCore.QEvent.Type.MouseMove, QtCore.QEvent.Type.MouseButtonPress):
            if t == QtCore.QEvent.Type.Leave:
                _hide()
                _state["hot"] = None
            return False
        try:
            pos = event.position() if hasattr(event, "position") else QtCore.QPointF(event.pos())
            if t == QtCore.QEvent.Type.MouseMove:
                # Después de que el croquis vea el movimiento (su preselección queda al día)
                dragging = event.buttons() != QtCore.Qt.MouseButton.NoButton
                QtCore.QTimer.singleShot(0, lambda: _hover(viewport, QtCore.QPointF(pos), dragging))
                return False
            # Clic
            if event.button() != QtCore.Qt.MouseButton.LeftButton:
                return False
            hot = _hot_at(viewport, pos)
            if hot is None:
                return False
            view = FreeCADGui.ActiveDocument.ActiveView
            sketch = _editing_sketch()
            ratio = viewport.devicePixelRatioF()
            obj, sub, q = hot
            bring(sketch, obj, sub)
            _hide(view)
            _state["hot"] = None
            if viewport.cursor().shape() == QtCore.Qt.CursorShape.ArrowCursor:
                # Sin herramienta (seleccionando): se suma a la selección, como en SW, para
                # relacionarla con lo ya elegido. El croquis elegiría al soltar el botón lo
                # que tenía bajo el mouse (desactualizado): ese soltar no le llega.
                index = external_index(sketch, obj, sub)
                if index:
                    FreeCADGui.Selection.addSelection(sketch.Document.Name, sketch.Name,
                                                      "ExternalEdge%d" % index)
                self.swallow_release = True
                return True
            x, y = qt_point(q[0], q[1], viewport.height(), ratio)
            snapped = QtCore.QPointF(x, y)
            self.busy = True
            try:
                _send(viewport, QtCore.QEvent.Type.MouseMove, snapped, QtCore.Qt.MouseButton.NoButton,
                      QtCore.Qt.MouseButton.NoButton, event.modifiers())
                _send(viewport, QtCore.QEvent.Type.MouseButtonPress, snapped, event.button(),
                      event.buttons(), event.modifiers())
            finally:
                self.busy = False
            return True  # el clic original no sigue: ya se mandó sobre la arista
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Arista del modelo:\n%s\n" % traceback.format_exc())
            return False


def _attach_all():
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        for sub in mdi.subWindowList():
            view = sub.widget()
            if view is None or view.metaObject().className() != VIEW_CLASS:
                continue
            for gv in view.findChildren(QtWidgets.QGraphicsView):
                vp = gv.viewport()
                if not vp.property("swui_model_edges"):
                    vp.setProperty("swui_model_edges", True)
                    vp.installEventFilter(_filter)
    except Exception:
        pass


def install():
    """Filtro en las vistas 3D (las abiertas y las que se abran). Nada desde FreeCAD 26.3."""
    global _filter
    if _filter is not None or native():
        return
    _filter = _Filter()
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        mdi.subWindowActivated.connect(lambda *_a: _attach_all())
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Aristas del modelo: no se encontró el área de ventanas.\n")
    _attach_all()
