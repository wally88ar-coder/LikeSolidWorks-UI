# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Medir como en SOLIDWORKS (fase 3, pestaña Evaluar; barra espaciadora).

Ventanita flotante "Medir": cada clic en la vista SUMA un elemento (como SW, sin
Ctrl); un clic sobre uno ya elegido lo saca; clic en el vacío borra todo. Mide en
la posición real (también en ensamblajes):
- un vértice: X, Y, Z;  una arista: longitud (círculo/arco: diámetro, radio, centro);
- una cara: área y perímetro (cilindro: diámetro);  varias aristas/caras: totales;
- dos elementos: distancia mínima con dX/dY/dZ (o centro a centro si son círculos o
  cilindros, como SW), distancia normal entre caras planas paralelas y ángulo entre
  rectas/planos. La distancia se dibuja en la vista mientras la ventana está abierta, con
  la escalera de proyecciones dX (roja), dY (verde) y dZ (azul) y sus recuadros, como SW.
- distancia máxima (tercera opción): entre bordes de agujeros como SW, y entre cualquier
  otra cosa la máxima real (max_distance.py: FreeCAD no la trae).
Reemplaza al Medir de FreeCAD (Std_Measure, que en 1.1.4 sale en inglés) en la cinta
y en la barra espaciadora.
"""

import math

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

COMMAND = "SWUI_Measure"
PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI/Measure"
DEFAULT_DECIMALS = 2  # como SW
CLEAR_MS = 60  # espera para saber si un "borrar selección" fue un clic en el vacío
TOL = 1e-7
MAIN_COLOR = (0.05, 0.05, 0.05)  # línea de la distancia: negra, como SW
AXIS_COLORS = {"x": (0.88, 0.1, 0.05), "y": (0.0, 0.55, 0.0), "z": (0.05, 0.25, 0.9)}  # dX rojo, dY verde, dZ azul
TAG_COLORS = {"dist": "#000000", "x": "#e0261b", "y": "#108a10", "z": "#1f4fe0"}
LABEL_QSS = "QLabel { background: #ffffff; border: 1px solid #808080; padding: 0px; font-size: 9pt; }"
FOLLOW_MS = 40  # cada cuánto se reubican los recuadros si se movió la cámara

_window = None


# --- Cuentas (con formas de Part; las de vectores se prueban sin FreeCAD) -----


def fmt(value, decimals=DEFAULT_DECIMALS, unit="mm"):
    from swui.fork.mass_props import fmt as number

    return number(value, decimals) + (unit and " " + unit or "")


def _v(p):
    return FreeCAD.Vector(p[0], p[1], p[2]) if not hasattr(p, "x") else p


def angle_between(d1, d2, lines=True):
    """Ángulo en grados entre dos direcciones (rectas: 0-90 como SW muestra entre aristas)."""
    a = math.degrees(_v(d1).getAngle(_v(d2)))
    if lines and a > 90:
        a = 180 - a
    return a


def kind_of(shape):
    """'vertex', 'line', 'circle', 'edge', 'plane', 'cylinder', 'face', 'solid' u 'other'."""
    st = shape.ShapeType
    if st == "Vertex":
        return "vertex"
    if st == "Edge":
        try:
            name = type(shape.Curve).__name__
        except Exception:  # arista degenerada (polo de una esfera)
            return "other"
        if name in ("Line", "LineSegment"):
            return "line"
        if name in ("Circle", "ArcOfCircle"):
            return "circle"
        return "edge"
    if st == "Face":
        name = type(shape.Surface).__name__
        if name == "Plane":
            return "plane"
        if name == "Cylinder":
            return "cylinder"
        return "face"
    if shape.Solids:
        return "solid"
    return "other"


CIRCULAR = ("point", "axis")  # lo que sale de un círculo, cilindro o esfera


def _center_item(shape, kind):
    """
    Para centro a centro (como SW): de lo circular, su centro o eje; de lo demás, con qué se
    mide desde ese centro. ('point', p) círculo/esfera/vértice, ('axis', p, dir) cilindro,
    ('line', p, dir) arista recta, ('plane', p, normal) cara plana. (tipo, es_circular) o None.
    """
    if kind == "circle":
        return ("point", shape.Curve.Center), True
    if kind == "cylinder":
        return ("axis", shape.Surface.Center, shape.Surface.Axis), True
    if kind == "face" and type(shape.Surface).__name__ == "Sphere":
        return ("point", shape.Surface.Center), True
    if kind == "vertex":
        return ("point", shape.Point), False
    if kind == "line":
        return ("line", shape.Curve.Location, shape.Curve.Direction), False
    if kind == "plane":
        return ("plane", shape.Surface.Position, shape.Surface.Axis), False
    return None


def _point_line(p, base, d):
    d = _v(d).normalize()
    w = _v(p) - _v(base)
    foot = _v(base) + d * w.dot(d)
    return (_v(p) - foot).Length, foot


def _point_plane(p, origin, normal):
    n = _v(normal).normalize()
    h = (_v(p) - _v(origin)).dot(n)
    return abs(h), _v(p) - n * h


RANK = {"point": 0, "axis": 1, "line": 1, "plane": 2}


def center_distance(a, b):
    """
    (distancia, punto1, punto2) entre centros/ejes, o desde un centro/eje hasta una recta o
    plano; None si no hay una distancia única (ejes que se cruzan, eje que corta el plano).
    a, b: ('point', p) / ('axis', p, dir) / ('line', p, dir) / ('plane', p, normal).
    """
    if RANK[a[0]] > RANK[b[0]]:  # el más "chico" primero; los puntos se devuelven en orden
        found = center_distance(b, a)
        return None if found is None else (found[0], found[2], found[1])
    ka, kb = a[0], b[0]
    if kb == "plane":
        if ka == "plane":
            return None
        if ka != "point" and abs(_v(a[2]).normalize().dot(_v(b[2]).normalize())) > 1e-9:
            return None  # eje que corta el plano
        dist, foot = _point_plane(a[1], b[1], b[2])
        return dist, a[1], foot
    if ka == "point" and kb == "point":
        return (_v(b[1]) - _v(a[1])).Length, a[1], b[1]
    if ka == "point":  # punto con eje o recta
        dist, foot = _point_line(a[1], b[1], b[2])
        return dist, a[1], foot
    if angle_between(a[2], b[2]) < 1e-6:  # ejes / rectas paralelas
        dist, foot = _point_line(a[1], b[1], b[2])
        return dist, a[1], foot
    return None


def measure(shapes, mode="center", decimals=DEFAULT_DECIMALS):
    """
    shapes = formas globales elegidas. Devuelve (renglones [(texto, valor)], línea a dibujar
    (p1, p2) o None). mode: "center" (centro a centro para círculos, como SW), "min" o "max";
    decimals: decimales.
    """
    rows, line = [], None

    def f(value, unit="mm"):
        return fmt(value, decimals, unit)

    if not shapes:
        return [("Elegí vértices, aristas o caras en la vista.", "")], None
    kinds = [kind_of(s) for s in shapes]
    if len(shapes) == 1:
        s, k = shapes[0], kinds[0]
        if k == "vertex":
            p = s.Point
            rows += [("X", f(p.x)), ("Y", f(p.y)), ("Z", f(p.z))]
        elif k in ("line", "edge"):
            rows.append(("Longitud", f(s.Length)))
        elif k == "circle":
            c = s.Curve
            closed = s.isClosed()
            rows += [("Diámetro", f(2 * c.Radius)), ("Radio", f(c.Radius))]
            if not closed:
                rows += [("Longitud del arco", f(s.Length)),
                         ("Ángulo", f(math.degrees(s.LastParameter - s.FirstParameter), unit="°"))]
            else:
                rows.append(("Perímetro", f(s.Length)))
            rows.append(("Centro", "%s; %s; %s" % (f(c.Center.x, unit=""), f(c.Center.y, unit=""),
                                                   f(c.Center.z, unit=""))))
        elif k in ("plane", "cylinder", "face"):
            rows.append(("Área", f(s.Area, unit="mm²")))
            if k == "cylinder":
                rows.insert(0, ("Diámetro", f(2 * s.Surface.Radius)))
            else:  # todos los bordes, también los de los agujeros (como SW)
                rows.append(("Perímetro", f(sum(e.Length for e in s.Edges if not e.isSeam(s)))))
        elif k == "solid":
            rows += [("Volumen", f(s.Volume, unit="mm³")), ("Área de superficie", f(s.Area, unit="mm²"))]
        else:
            rows.append(("No se puede medir este elemento.", ""))
        return rows, None
    if len(shapes) > 2:
        if all(k in ("line", "circle", "edge") for k in kinds):
            return [("Longitud total", f(sum(s.Length for s in shapes)))], None
        if all(k in ("plane", "cylinder", "face") for k in kinds):
            return [("Área total", f(sum(s.Area for s in shapes), unit="mm²"))], None
        return [("Para medir distancias, elegí dos elementos.", "")], None
    a, b = shapes
    ka, kb = kinds
    if mode == "max":
        from swui.fork import max_distance

        found = max_distance.max_distance(a, b)
        if found:
            dist, p1, p2 = found
            rows.append(("Distancia máxima", f(dist)))
            line = (_v(p1), _v(p2))
    if mode == "center":
        ca, cb = _center_item(a, ka), _center_item(b, kb)
        if ca and cb and (ca[1] or cb[1]):  # al menos uno circular (si no, la mínima, como SW)
            found = center_distance(ca[0], cb[0])
            if found:
                dist, p1, p2 = found
                both = ca[1] and cb[1]
                rows.append(("Distancia centro a centro" if both else "Distancia desde el centro", f(dist)))
                line = (_v(p1), _v(p2))
    if not rows:
        dist, pairs, _info = a.distToShape(b)
        p1, p2 = pairs[0]
        rows.append(("Distancia" if dist > TOL else "Distancia (se tocan)", f(dist)))
        line = (p1, p2) if dist > TOL else None
        if ka == kb == "plane" and mode != "max":
            na, nb = a.Surface.Axis, b.Surface.Axis
            if angle_between(na, nb) < 1e-6:
                normal = abs((_v(b.Surface.Position) - _v(a.Surface.Position)).dot(_v(na).normalize()))
                rows.append(("Distancia normal", f(normal)))
    if line is not None:
        d = _v(line[1]) - _v(line[0])
        rows += [("dX", f(abs(d.x))), ("dY", f(abs(d.y))), ("dZ", f(abs(d.z)))]
    dirs = []
    for s, k in ((a, ka), (b, kb)):
        if k == "line":
            dirs.append((s.Curve.Direction, True))
        elif k == "plane":
            dirs.append((s.Surface.Axis, False))
    if len(dirs) == 2:
        (d1, l1), (d2, l2) = dirs
        if l1 and l2:
            ang = angle_between(d1, d2)
        elif not l1 and not l2:
            ang = angle_between(d1, d2)
        else:
            ang = abs(90 - angle_between(d1, d2))  # recta con plano
        if ang > 1e-6 or not any(r[0] == "Distancia normal" for r in rows):
            rows.append(("Ángulo", f(ang, unit="°")))
    return rows, line


# --- Selección que suma (como SW) -------------------------------------------


def projections(p1, p2, tol=TOL):
    """
    Escalera de proyecciones como SW: desde p1, dX (paralela a X), después dY, después dZ hasta
    p2. [(eje, desde, hasta)] sin los tramos nulos. p1, p2: (x, y, z).
    """
    a, out = tuple(p1), []
    for k, axis in enumerate("xyz"):
        b = list(a)
        b[k] = p2[k]
        b = tuple(b)
        if abs(b[k] - a[k]) > tol:
            out.append((axis, a, b))
        a = b
    return out


def toggle_pick(picks, pick):
    """Clic: suma el elemento; si ya estaba, lo saca (como SW)."""
    if pick in picks:
        return [p for p in picks if p != pick]
    return picks + [pick]


class _SelObserver:
    def __init__(self, window):
        self.w = window

    def addSelection(self, doc, obj, sub, _pnt):
        self.w.on_add(doc, obj, sub)

    def removeSelection(self, doc, obj, sub):
        self.w.on_remove(doc, obj, sub)

    def setSelection(self, doc):
        pass

    def clearSelection(self, doc):
        self.w.on_clear()


class _MeasureWindow(QtWidgets.QDialog):
    def __init__(self):
        mw = FreeCADGui.getMainWindow()
        super().__init__(mw)
        self.setWindowFlags(QtCore.Qt.WindowType.Tool | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle("Medir")
        # que no se quede con el teclado: la barra espaciadora tiene que seguir cerrándola
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.picks = []  # [(documento, objeto raíz, subnombre completo)]
        self.busy = False
        self.pending_clear = False
        self.node = None
        self.labels = []  # [(QLabel, punto 3D donde se ancla, tramo)]
        self.camera = None
        self.follow = QtCore.QTimer(self)
        self.follow.setInterval(FOLLOW_MS)
        self.follow.timeout.connect(self._follow)
        box = QtWidgets.QVBoxLayout(self)
        box.setContentsMargins(6, 6, 6, 6)
        bar = QtWidgets.QHBoxLayout()
        self.cb_mode = QtWidgets.QComboBox()
        self.cb_mode.addItems(["Centro a centro (arcos/círculos)", "Distancia mínima", "Distancia máxima"])
        self.cb_mode.setCurrentIndex(FreeCAD.ParamGet(PARAMS).GetInt("Mode", 0))
        self.cb_mode.currentIndexChanged.connect(self._mode)
        self.sp_dec = QtWidgets.QSpinBox()
        self.sp_dec.setRange(0, 6)
        self.sp_dec.setValue(FreeCAD.ParamGet(PARAMS).GetInt("Decimals", DEFAULT_DECIMALS))
        self.sp_dec.setToolTip("Decimales")
        self.sp_dec.valueChanged.connect(self._decimals)
        bar.addWidget(self.cb_mode, 1)
        bar.addWidget(QtWidgets.QLabel("Dec.:"))
        bar.addWidget(self.sp_dec)
        box.addLayout(bar)
        self.cb_xyz = QtWidgets.QCheckBox("Mostrar dX, dY, dZ en la vista")
        self.cb_xyz.setChecked(FreeCAD.ParamGet(PARAMS).GetBool("ShowXYZ", True))
        self.cb_xyz.toggled.connect(self._xyz)
        box.addWidget(self.cb_xyz)
        self.lb_sel = QtWidgets.QLabel()
        self.lb_sel.setWordWrap(True)
        box.addWidget(self.lb_sel)
        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.horizontalHeader().setVisible(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(20)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        box.addWidget(self.table, 1)
        row = QtWidgets.QHBoxLayout()
        b_clear = QtWidgets.QPushButton("Borrar selecciones")
        b_copy = QtWidgets.QPushButton("Copiar")
        b_clear.clicked.connect(lambda *_a: self.clear())
        b_copy.clicked.connect(self._copy)
        row.addWidget(b_clear)
        row.addWidget(b_copy)
        box.addLayout(row)
        for w in (self.cb_mode, self.sp_dec, self.cb_xyz, self.table, b_clear, b_copy):
            w.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        self.resize(300, 260)
        self._place(mw)
        self.observer = _SelObserver(self)
        FreeCADGui.Selection.addObserver(self.observer)
        self._take_current()

    def _place(self, mw):
        """Arriba a la izquierda de la vista 3D, como aparece la de SW."""
        try:
            area = mw.findChild(QtWidgets.QMdiArea)
            if area is not None:
                top_left = area.mapToGlobal(QtCore.QPoint(20, 20))
                self.move(top_left)
        except Exception:
            pass

    # --- selección

    def _take_current(self):
        try:
            for sel in FreeCADGui.Selection.getSelectionEx("", 0):
                for sub in (sel.SubElementNames or [""]):
                    self.picks = toggle_pick(self.picks, (sel.DocumentName, sel.ObjectName, sub))
        except Exception:
            pass
        self.update_result()

    def on_add(self, doc, obj, sub):
        if self.busy:
            return
        self.pending_clear = False
        QtCore.QTimer.singleShot(0, lambda: self._absorb(doc, obj, sub))

    def _absorb(self, doc, obj, sub):
        """
        Lo que llegó al observador es la cara resuelta (objeto interno, sin la posición en el
        ensamblaje): se busca en la selección la ruta completa desde la raíz y se suma esa.
        """
        pick = None
        try:
            for sel in FreeCADGui.Selection.getSelectionEx("", 0):
                for full in (sel.SubElementNames or [""]):
                    if sel.DocumentName == doc and (full == sub or full.endswith("." + sub) or
                                                    (not sub and sel.ObjectName == obj)):
                        pick = (sel.DocumentName, sel.ObjectName, full)
        except Exception:
            pass
        if pick is None:
            pick = (doc, obj, sub)
        self.picks = toggle_pick(self.picks, pick)
        self._reselect()

    def on_remove(self, doc, obj, sub):
        if self.busy:
            return
        self.picks = [p for p in self.picks if p != (doc, obj, sub)]
        QtCore.QTimer.singleShot(0, self.update_result)

    def on_clear(self):
        if self.busy:
            return
        self.pending_clear = True
        QtCore.QTimer.singleShot(CLEAR_MS, self._maybe_clear)

    def _maybe_clear(self):
        if self.pending_clear:  # nadie sumó nada: fue un clic en el vacío
            self.pending_clear = False
            self.picks = []
            self.update_result()

    def _reselect(self):
        """Vuelve a marcar en la vista todo lo elegido (FreeCAD borró lo anterior al hacer clic)."""
        self.busy = True
        try:
            FreeCADGui.Selection.clearSelection()
            for doc, obj, sub in self.picks:
                try:
                    FreeCADGui.Selection.addSelection(doc, obj, sub)
                except Exception:
                    pass
        finally:
            self.busy = False
        self.update_result()

    def clear(self):
        self.picks = []
        self.busy = True
        try:
            FreeCADGui.Selection.clearSelection()
        finally:
            self.busy = False
        self.update_result()

    # --- resultado

    def _shapes(self):
        out, names = [], []
        for doc, obj, sub in self.picks:
            try:
                root = FreeCAD.getDocument(doc).getObject(obj)
                shape = root.getSubObject(sub) if sub else root.Shape
                if shape is None or shape.isNull():
                    continue
                out.append(shape)
                element = sub.split(".")[-1] if sub else ""
                names.append("%s de %s" % (_element_name(element), _owner_label(root, sub)) if element
                             else root.Label)
            except Exception:
                continue
        return out, names

    def update_result(self):
        shapes, names = self._shapes()
        mode = ("center", "min", "max")[max(0, min(2, self.cb_mode.currentIndex()))]
        try:
            rows, line = measure(shapes, mode, self.sp_dec.value())
        except Exception as exc:
            rows, line = [("No se pudo medir: %s" % exc, "")], None
        self.lb_sel.setText("\n".join(names) if names else "Clic en vértices, aristas o caras (clic en el vacío borra).")
        self.table.setRowCount(len(rows))
        for i, (label, value) in enumerate(rows):
            self.table.setItem(i, 0, QtWidgets.QTableWidgetItem(label))
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(value))
        self.table.resizeColumnToContents(0)
        main = rows[0][1] if rows and line is not None else ""
        self._draw(line, main, dict(rows))

    def _copy(self, *_a):
        lines = ["%s: %s" % (self.table.item(i, 0).text(), self.table.item(i, 1).text())
                 for i in range(self.table.rowCount())]
        QtWidgets.QApplication.clipboard().setText("\n".join(lines))

    def _mode(self, i):
        FreeCAD.ParamGet(PARAMS).SetInt("Mode", int(i))
        self.update_result()

    def _decimals(self, value):
        FreeCAD.ParamGet(PARAMS).SetInt("Decimals", int(value))
        self.update_result()

    def _xyz(self, on):
        FreeCAD.ParamGet(PARAMS).SetBool("ShowXYZ", bool(on))
        self.update_result()

    # --- línea en la vista (como SW: distancia negra y escalera dX roja, dY verde, dZ azul)

    def _draw(self, line, main_text="", values=None):
        self._undraw()
        if line is None:
            return
        values = values or {}
        p1, p2 = (line[0].x, line[0].y, line[0].z), (line[1].x, line[1].y, line[1].z)
        segments = [("dist", p1, p2)]
        if self.cb_xyz.isChecked():
            segments += projections(p1, p2)
        try:
            from pivy import coin

            view = FreeCADGui.ActiveDocument.ActiveView
            node = coin.SoAnnotation()
            for kind, a, b in segments:
                part = coin.SoSeparator()
                color = coin.SoBaseColor()
                color.rgb = MAIN_COLOR if kind == "dist" else AXIS_COLORS[kind]
                style = coin.SoDrawStyle()
                style.lineWidth = 2
                coords = coin.SoCoordinate3()
                coords.point.setValues(0, 2, [a, b])
                for child in (color, style, coords, coin.SoLineSet()):
                    part.addChild(child)
                if kind == "dist":
                    marks = coin.SoMarkerSet()
                    marks.markerIndex = coin.SoMarkerSet.CIRCLE_FILLED_7_7
                    part.addChild(marks)
                node.addChild(part)
            view.getSceneGraph().addChild(node)
            self.node = (view, node)
        except Exception:
            self.node = None
            return
        texts = {"dist": ("Dist.", main_text), "x": ("dX", values.get("dX", "")),
                 "y": ("dY", values.get("dY", "")), "z": ("dZ", values.get("dZ", ""))}
        self._make_labels([(kind, a, b) + texts[kind] for kind, a, b in segments])

    def _make_labels(self, items):
        """Recuadros como SW (rótulo de color + valor), encima de la vista, que no tapan los clics."""
        from swui.fork import instant_dims

        vp = instant_dims._viewport()
        if vp is None:
            return
        for kind, a, b, tag, value in items:
            if not value:
                continue
            label = QtWidgets.QLabel(vp)
            label.setTextFormat(QtCore.Qt.TextFormat.RichText)
            label.setText('<span style="background:%s; color:#ffffff;">&nbsp;%s&nbsp;</span>'
                          '<span>&nbsp;%s&nbsp;</span>' % (TAG_COLORS[kind], tag, value))
            label.setStyleSheet(LABEL_QSS)
            label.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            label.adjustSize()
            label.show()
            mid = tuple((a[k] + b[k]) / 2 for k in range(3))
            self.labels.append((label, mid, kind))
        self.camera = None
        self._follow()
        self.follow.start()

    def _follow(self):
        """Reubica los recuadros si se movió la cámara (giro, zoom, encuadre)."""
        if not self.labels or self.node is None:
            return
        try:
            from swui.fork import instant_dims, sketch_model_edges

            view, vp = self.node[0], instant_dims._viewport()
            key = (sketch_model_edges._camera_key(view), vp.size().width(), vp.size().height())
            if key == self.camera:
                return
            self.camera = key
            ratio = vp.devicePixelRatioF()
            placed = []
            for label, mid, kind in self.labels:
                x, y = view.getPointOnViewport(FreeCAD.Vector(*mid))
                if kind == "dist":  # arriba del medio de la línea
                    dx, dy = -label.width() / 2, -label.height() - 6
                else:  # al costado del tramo
                    dx, dy = 8, 6
                rect = QtCore.QRect(int(x / ratio + dx), int(vp.height() - y / ratio + dy),
                                    label.width(), label.height())
                for _try in range(len(placed)):  # si pisa a otro recuadro, un renglón más abajo
                    if not any(rect.intersects(r) for r in placed):
                        break
                    rect.translate(0, label.height() + 2)
                placed.append(rect)
                label.move(rect.x(), rect.y())
        except Exception:
            pass

    def _undraw(self):
        self.follow.stop()
        for label, _mid, _kind in self.labels:
            try:
                label.hide()
                label.deleteLater()
            except Exception:
                pass
        self.labels = []
        if self.node is not None:
            view, node = self.node
            try:
                view.getSceneGraph().removeChild(node)
            except Exception:
                pass
        self.node = None

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def shutdown(self):
        """Borrar lo dibujado y soltar la selección (se puede llamar más de una vez)."""
        self._undraw()
        if self.observer is not None:
            try:
                FreeCADGui.Selection.removeObserver(self.observer)
            except Exception:
                pass
            self.observer = None

    def closeEvent(self, event):
        global _window
        self.shutdown()
        if _window is self:
            _window = None
        super().closeEvent(event)


def _owner_label(root, sub):
    """A quién pertenece: en un ensamblaje el componente (Pieza1), en una pieza la operación."""
    tokens = sub.split(".")[:-1]
    if not tokens:
        return root.Label
    try:
        if root.TypeId in ("Assembly::AssemblyObject", "App::Part"):
            return root.getSubObject(tokens[0] + ".", retType=1).Label
        return root.getSubObject(".".join(tokens) + ".", retType=1).Label
    except Exception:
        return root.Label


def _element_name(element):
    for prefix, name in (("Vertex", "Vértice"), ("Edge", "Arista"), ("Face", "Cara")):
        if element.startswith(prefix):
            return "%s<%s>" % (name, element[len(prefix):])
    return element


def toggle():
    """
    Abrir la ventana Medir (o cerrarla si ya está abierta: barra espaciadora).
    Una ventana que quedó abierta pero sin verse se cierra limpiando lo dibujado
    (close() de Qt no avisa a una ventana oculta y la línea quedaba pegada) y se
    abre otra: la barra pide verla.
    """
    global _window
    if _window is not None:
        old, _window = _window, None
        visible = old.isVisible()
        try:
            old.shutdown()
            old.close()
        except Exception:
            pass
        if visible:
            return None
    _window = _MeasureWindow()
    _window.show()
    _window.raise_()
    return _window


class _MeasureCommand:
    def GetResources(self):
        from swui import paths

        return {"MenuText": "Medir", "ToolTip": "Medir distancias, ángulos, longitudes y áreas (como SW). "
                "Cada clic suma un elemento; clic en el vacío borra.", "Pixmap": paths.icon("fork/measure") or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        toggle()


def install():
    try:
        FreeCADGui.addCommand(COMMAND, _MeasureCommand())
    except Exception:
        pass  # ya registrado
