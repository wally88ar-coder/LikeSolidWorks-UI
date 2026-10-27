# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Eliminar/Conservar sólidos como en SOLIDWORKS (multicuerpo). Panel de SW (captura del usuario,
2026-10-26): Tipo Eliminar sólidos / Conservar sólidos y la lista de sólidos. El usuario lo usa
para sólidos enteros (Cuerpos) y para los pedazos que deja un corte dentro de un Cuerpo.

Todo nativo (el addon es un asistente, docs/ESTADO.md "Multicuerpo"), verificado en 1.1.4:
- La operación es un grupo (App::DocumentObjectGroup) "Eliminar/Conservar sólido1" con la marca
  SWUI_DeleteBodies (texto JSON con lo elegido; nombre estable para siempre). Los Cuerpos
  eliminados van adentro, ocultos, y dejan de contar como sólidos (material.consumes).
- Pedazos de un Cuerpo: por cada pedazo que queda, un punto (Part::Vertex) adentro del pedazo,
  un filtro de FreeCAD (CompoundTools.CompoundFilter, "collision-pass": se queda con el pedazo
  que toca el punto) y un Cuerpo nuevo que arranca del filtro. Elegir por un punto y no por
  número de orden: si un cambio de cotas reordena los pedazos, sigue siendo el mismo (probado).
  El Cuerpo partido queda oculto (lo "consume" el filtro); filtros y puntos van en el grupo.
Editar (clic derecho -> Editar operación) deshace lo armado y lo vuelve a armar con la lista
nueva; con la lista vacía la operación se borra y todo vuelve. Borrarla con Supr también
devuelve los sólidos (como SW), en un paso de deshacer; por otro camino (menú, Python) un
respaldo los devuelve enseguida. Un pedazo que ya tiene operaciones propias no se puede
desarmar: con Supr avisa y no borra; por otro camino ese pedazo se queda (y avisa).
"""

import json
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets
from swui.fork import dress_up_panel as dp

COMMAND = "SWUI_DeleteBodies"
MARK = "SWUI_DeleteBodies"
GROUP = "App::DocumentObjectGroup"
BODY = "PartDesign::Body"
LABEL = "Eliminar/Conservar sólido"
DELETE, KEEP = "delete", "keep"


# --- Cuentas sin FreeCAD (probables en el test) -------------------------------


def read_spec(text):
    spec = {"mode": DELETE, "items": []}
    try:
        data = json.loads(text or "{}")
        if isinstance(data, dict):
            spec.update({k: v for k, v in data.items() if k in spec})
    except ValueError:
        pass
    if spec["mode"] not in (DELETE, KEEP):
        spec["mode"] = DELETE
    return spec


def next_label(used):
    n = 1
    while "%s%d" % (LABEL, n) in used:
        n += 1
    return "%s%d" % (LABEL, n)


def plan(mode, bodies, whole, pieces):
    """
    Qué hacer, sin FreeCAD. bodies: todos los sólidos (nombres); whole: Cuerpos elegidos
    enteros; pieces: {cuerpo: (pedazos elegidos, total de pedazos)} con índices.
    Devuelve (Cuerpos a eliminar, {cuerpo: pedazos que quedan}).
    """
    gone, keep = [], {}
    for body in bodies:
        if body in pieces:
            chosen, total = pieces[body]
            rest = [i for i in range(total) if (i in chosen) == (mode == KEEP)]
            if rest:
                keep[body] = rest
            else:
                gone.append(body)
        elif (body in whole) == (mode == DELETE):
            gone.append(body)
    return gone, keep


# --- Geometría ------------------------------------------------------------------


def _point_on(face):
    """Un punto sobre la cara (centro de un triángulo de su mallado: cae adentro aunque tenga agujeros)."""
    pts, tris = face.tessellate(1.0)
    if not tris:
        return None
    a, b, c = tris[0]
    return (pts[a] + pts[b] + pts[c]) * (1.0 / 3.0)


def inner_point(solid, face=None):
    """Un punto bien adentro del sólido, cerca de la cara (si se da) o de cualquiera de sus caras."""
    for f in ([face] if face is not None else []) + list(solid.Faces):
        try:
            p = _point_on(f)
            if p is None:
                continue
            u, v = f.Surface.parameter(p)
            n = f.normalAt(u, v)
        except Exception:
            continue
        for eps in (0.05, 0.01, 0.2, 0.001):
            q = p - n * eps
            if solid.isInside(q, 1e-7, False):
                return q
    c = solid.CenterOfMass
    return c if solid.isInside(c, 1e-7, False) else None


def piece_of(shape, point):
    """Índice del pedazo (sólido) que contiene el punto, o None."""
    for i, solid in enumerate(shape.Solids):
        if solid.isInside(point, 1e-6, True):
            return i
    return None


# --- Objetos de una operación -----------------------------------------------------


def built_objects(group):
    """Lo que armó la operación: filtros, puntos y Cuerpos nuevos (no los Cuerpos eliminados)."""
    out = []
    for o in group.Group:
        if o.TypeId == BODY:
            continue
        out.append(o)
        for user in o.InList:
            if user.TypeId == BODY and user.BaseFeature is o:
                out.append(user)
    return out


def _busy_pieces(built):
    return [o for o in built if o.TypeId == BODY and len(o.Group) > 1]


def _teardown(doc, group):
    """Deshacer lo armado: sacar los Cuerpos eliminados (visibles) y borrar filtros, puntos y pedazos."""
    built = built_objects(group)
    busy = _busy_pieces(built)
    if busy:
        return "El sólido %s ya tiene operaciones propias: no se puede desarmar." % busy[0].Label
    members = _member_bodies(group)
    for name in members:
        group.removeObject(doc.getObject(name))
    _restore(doc, members, [o.Name for o in built])
    return ""


def _member_bodies(group):
    return [o.Name for o in group.Group if o.TypeId == BODY]


def _restore(doc, bodies, built, keep=()):
    """
    Volver a como estaba (por nombres, sirve también con el grupo ya borrado): mostrar los
    Cuerpos eliminados y los partidos, borrar pedazos, filtros y puntos (menos los de keep).
    """
    objs = [doc.getObject(n) for n in built]
    objs = [o for o in objs if o is not None and o.Name not in keep]
    restore = set(bodies)
    for o in objs:
        if o.TypeId == "Part::FeaturePython" and getattr(o, "Base", None) is not None:
            if not any(u.Name in keep for u in o.InList):
                restore.add(o.Base.Name)
    for o in [o for o in objs if o.TypeId == BODY] + [o for o in objs if o.TypeId != BODY]:
        if any(u.Name in keep for u in o.InList):
            continue  # lo usa un pedazo que se queda
        if o.TypeId == BODY:
            o.removeObjectsFromDocument()
        doc.removeObject(o.Name)
    for name in restore:
        body = doc.getObject(name)
        if body is not None:
            body.Visibility = True


_deleting = {"busy": False}


def delete_operation(group):
    """Borrar la operación como en SW: los sólidos vuelven. Un paso de deshacer. Problema o ""."""
    doc = group.Document
    label = group.Label
    doc.openTransaction("Borrar %s" % label)
    _deleting["busy"] = True
    try:
        problem = _teardown(doc, group)
        if problem:
            doc.abortTransaction()
            return problem
        doc.removeObject(group.Name)
        doc.commitTransaction()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Borrar %s:\n%s\n" % (label, traceback.format_exc()))
        doc.abortTransaction()
        return "No se pudo borrar la operación."
    finally:
        _deleting["busy"] = False
    doc.recompute()
    return ""


class _DeleteKey(QtCore.QObject):
    """
    Supr con solo operaciones Eliminar/Conservar elegidas: las borra el addon (los sólidos
    vuelven) en lugar de Std_Delete, que borraría solo el grupo. Qt resuelve los atajos con
    ShortcutOverride: aceptarlo hace que la tecla llegue como KeyPress y Std_Delete no corra.
    """

    def eventFilter(self, _watched, event):
        try:
            kind = event.type()
            if kind not in (QtCore.QEvent.Type.ShortcutOverride, QtCore.QEvent.Type.KeyPress) \
                    or event.key() != QtCore.Qt.Key.Key_Delete:
                return False
            if isinstance(QtWidgets.QApplication.focusWidget(), (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox,
                                                                  QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
                return False
            if not dp._in_workbench() or FreeCADGui.Control.activeDialog():
                return False
            sels = FreeCADGui.Selection.getSelection()
            if not sels or not all(hasattr(o, MARK) for o in sels):
                return False
            event.accept()
            if kind == QtCore.QEvent.Type.KeyPress:
                FreeCADGui.Selection.clearSelection()
                for group in sels:
                    problem = delete_operation(group)
                    if problem:
                        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), LABEL, problem)
            return True
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Supr:\n%s\n" % traceback.format_exc())
            return False


class _DocObserver:
    """Respaldo: el grupo se borró por otro camino (menú, Python): los sólidos vuelven igual."""

    def slotDeletedObject(self, obj):
        try:
            if not hasattr(obj, MARK) or _deleting["busy"]:
                return
            doc = obj.Document
            if getattr(doc, "Transacting", False) or getattr(doc, "Restoring", False):
                return
            built = built_objects(obj)
            keep = [o.Name for o in _busy_pieces(built)]
            bodies, names = _member_bodies(obj), [o.Name for o in built]
        except Exception:
            return
        doc_name = doc.Name
        QtCore.QTimer.singleShot(0, lambda: _restore_later(doc_name, bodies, names, keep))


def _restore_later(doc_name, bodies, built, keep):
    doc = FreeCAD.listDocuments().get(doc_name)
    if doc is None:
        return
    doc.openTransaction("Devolver sólidos")
    try:
        _restore(doc, bodies, built, keep)
        doc.commitTransaction()
    except Exception:
        doc.abortTransaction()
        FreeCAD.Console.PrintError("[SWUI fork] Devolver sólidos:\n%s\n" % traceback.format_exc())
    doc.recompute()
    if keep:
        QtWidgets.QMessageBox.information(
            FreeCADGui.getMainWindow(), LABEL,
            "Los sólidos volvieron, pero quedaron los pedazos que ya tenían operaciones propias: %s."
            % ", ".join(doc.getObject(n).Label for n in keep if doc.getObject(n) is not None))


def build(doc, group, spec):
    """Armar la operación según spec (dentro de una transacción). Devuelve un problema o ""."""
    from swui.fork import multibody

    bodies = [b for b in multibody.solid_bodies(doc)]
    names = [b.Name for b in bodies]
    whole, pieces = set(), {}
    for item in spec["items"]:
        body = doc.getObject(item["body"])
        if body is None or body.Name not in names:
            continue
        if item.get("point") is None:
            whole.add(body.Name)
            continue
        idx = piece_of(body.Shape, FreeCAD.Vector(*item["point"]))
        if idx is None:
            return "No se encuentra un pedazo de %s: elegilo de nuevo." % body.Label
        chosen, _total = pieces.get(body.Name, (set(), 0))
        chosen.add(idx)
        pieces[body.Name] = (chosen, len(body.Shape.Solids))
    gone, keep = plan(spec["mode"], names, whole, pieces)
    import CompoundTools.CompoundFilter as CF

    used = set(o.Label for o in doc.Objects)
    for name, rest in keep.items():
        body = doc.getObject(name)
        solids = body.Shape.Solids
        for i in rest:
            p = inner_point(solids[i])
            if p is None:
                return "No pude ubicar un pedazo de %s." % body.Label
            pt = doc.addObject("Part::Vertex", "Punto")
            pt.X, pt.Y, pt.Z = p.x, p.y, p.z
            pt.Visibility = False
            multibody._keep_label(pt, "Punto (%s, pedazo<%d>)" % (body.Label, i + 1))
            filt = CF.makeCompoundFilter("Filtro")
            filt.Base = body
            filt.FilterType = "collision-pass"
            filt.Stencil = pt
            filt.Visibility = False
            multibody._keep_label(filt, "Pedazo<%d> de %s" % (i + 1, body.Label))
            group.addObject(pt)
            group.addObject(filt)
            new = doc.addObject(BODY, "Body")
            new.BaseFeature = filt
            label = multibody.next_body_label(used)
            used.add(label)
            multibody._keep_label(new, label)
        body.Visibility = False
    for name in gone:
        body = doc.getObject(name)
        group.addObject(body)
        body.Visibility = False
    return ""


# --- Panel -------------------------------------------------------------------


def _body_of(obj):
    from swui.fork import multibody

    if obj is not None and obj.TypeId == BODY:
        return obj
    return multibody.body_of(obj)


class DeleteBodiesPanel:
    """Panel SW. Se arma al Aceptar (la vista previa marca en amarillo lo elegido)."""

    def __init__(self, group=None, doc=None, items=None):
        self.group = group
        self.doc = group.Document if group is not None else doc
        self.gdoc = FreeCADGui.getDocument(self.doc.Name)
        self.spec = read_spec(getattr(group, MARK, "") if group is not None else "")
        if items is not None:
            self.spec["items"] = items
        self.busy = False
        self.nodes = []
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._draw)
        self.doc.openTransaction(LABEL)
        if group is not None:  # editar: volver al estado anterior y mostrar todo
            problem = _teardown(self.doc, group)
            self.locked = problem
            self.doc.recompute()
        else:
            self.locked = ""
        self._build()
        self.observer = dp._PickObserver(self)
        FreeCADGui.Selection.addObserver(self.observer)
        FreeCADGui.Selection.clearSelection()
        self._refresh()

    def _build(self):
        from swui import paths
        from swui.compat import QtGui

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(LABEL)
        icon = paths.icon("fork/delete_bodies")
        if icon:
            self.form.setWindowIcon(QtGui.QIcon(icon))
        box = QtWidgets.QVBoxLayout(self.form)
        kinds = QtWidgets.QGroupBox("Tipo")
        kl = QtWidgets.QVBoxLayout(kinds)
        self.kind_group = QtWidgets.QButtonGroup(self.form)
        self.radios = {}
        for text, mode in (("Eliminar sólidos", DELETE), ("Conservar sólidos", KEEP)):
            radio = QtWidgets.QRadioButton(text, kinds)
            radio.setChecked(mode == self.spec["mode"])
            radio.toggled.connect(lambda on, m=mode: self._mode(m) if on else None)
            self.kind_group.addButton(radio)
            kl.addWidget(radio)
            self.radios[mode] = radio
        box.addWidget(kinds)
        self.list_group = QtWidgets.QGroupBox()
        ll = QtWidgets.QVBoxLayout(self.list_group)
        self.list = dp.pick_list(self.remove_current, self.clear)
        self.list.setStyleSheet("QListWidget { %s }" % dp.ACTIVE_QSS)
        ll.addWidget(self.list)
        box.addWidget(self.list_group)
        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: %s;" % dp.MISSING_COLOR)
        box.addWidget(self.message)
        box.addStretch(1)

    def _mode(self, mode):
        self.spec["mode"] = mode
        self._refresh()

    def _item_text(self, item):
        body = self.doc.getObject(item["body"])
        if body is None:
            return "(no se encuentra)"
        if item.get("point") is None:
            return body.Label
        idx = piece_of(body.Shape, FreeCAD.Vector(*item["point"]))
        return "%s, pedazo<%s>" % (body.Label, idx + 1 if idx is not None else "?")

    def _refresh(self):
        keep = self.spec["mode"] == KEEP
        self.list_group.setTitle("Sólidos para conservar" if keep else "Sólidos para eliminar")
        self.list.clear()
        for item in self.spec["items"]:
            self.list.addItem(self._item_text(item))
        self.message.setText(self.locked)
        self.message.setVisible(bool(self.locked))
        self._draw()

    def remove_current(self, *_a):
        row = self.list.currentRow()
        if 0 <= row < len(self.spec["items"]):
            del self.spec["items"][row]
            self._refresh()

    def clear(self, *_a):
        self.spec["items"] = []
        self._refresh()

    # --- selección

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

    def _pick(self, root, sub):
        from swui.fork import multibody

        leaf = root
        try:
            leaf = root.getSubObject(sub, retType=1) or root
        except Exception:
            pass
        body = _body_of(leaf) or _body_of(root)
        if body is None or body not in multibody.solid_bodies(self.doc):
            return False
        element = sub.split(".")[-1]
        item = {"body": body.Name, "point": None}
        solids = body.Shape.Solids
        if len(solids) > 1 and element.startswith("Face"):
            face = root.getSubObject(sub)
            p = _point_on(face)
            idx = piece_of(body.Shape, p) if p is not None else None
            if idx is None:
                return False
            q = inner_point(solids[idx], face)
            if q is None:
                return False
            item["point"] = [q.x, q.y, q.z]
            for old in self.spec["items"]:  # otro clic en el mismo pedazo: sacarlo
                if old["body"] == body.Name and old.get("point") is not None and \
                        piece_of(body.Shape, FreeCAD.Vector(*old["point"])) == idx:
                    self.spec["items"].remove(old)
                    return True
        else:
            for old in self.spec["items"]:
                if old["body"] == body.Name and old.get("point") is None:
                    self.spec["items"].remove(old)
                    return True
        self.spec["items"].append(item)
        return True

    # --- vista previa: lo elegido en amarillo

    def _shapes(self):
        out = []
        for item in self.spec["items"]:
            body = self.doc.getObject(item["body"])
            if body is None:
                continue
            if item.get("point") is None:
                out += body.Shape.Faces
            else:
                idx = piece_of(body.Shape, FreeCAD.Vector(*item["point"]))
                if idx is not None:
                    out += body.Shape.Solids[idx].Faces
        return out

    def _undraw(self):
        try:
            graph = self.gdoc.ActiveView.getSceneGraph()
        except Exception:
            graph = None
        for node in self.nodes:
            try:
                graph.removeChild(node)
            except Exception:
                pass
        self.nodes = []

    def _draw(self):
        self._undraw()
        try:
            graph = self.gdoc.ActiveView.getSceneGraph()
            node = dp._faces_node(self._shapes(), dp.PREVIEW_COLOR)
            graph.addChild(node)
            self.nodes.append(node)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] Vista previa:\n%s\n" % traceback.format_exc())

    # --- cerrar

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel

    def _close(self):
        self.timer.stop()
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        self._undraw()
        dp._state["panel"] = None

    def accept(self):
        from swui.fork import multibody

        if self.locked:
            return False
        if not self.spec["items"]:
            if self.group is None:
                self.message.setText("Elegí al menos un sólido (clic en la pieza o en el árbol).")
                self.message.show()
                return False
            _deleting["busy"] = True  # ya se desarmó al abrir el panel
            try:
                self.doc.removeObject(self.group.Name)  # lista vacía: la operación se borra
            finally:
                _deleting["busy"] = False
        else:
            if self.group is None:
                self.group = self.doc.addObject(GROUP, "Group")
                self.group.addProperty("App::PropertyString", MARK, "SWUI",
                                       "Eliminar/Conservar sólidos (fork de LikeSolidWorks UI)")
                self.group.setEditorMode(MARK, 2)
                multibody._keep_label(self.group, next_label(set(o.Label for o in self.doc.Objects)))
            setattr(self.group, MARK, json.dumps(self.spec, sort_keys=True))
            try:
                problem = build(self.doc, self.group, self.spec)
            except Exception:
                FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (LABEL, traceback.format_exc()))
                problem = "FreeCAD no pudo armar la operación."
            if problem:
                self.message.setText(problem)
                self.message.show()
                return False
        self._close()
        self.doc.recompute()
        self.doc.commitTransaction()
        return True

    def reject(self):
        self._close()
        self.doc.abortTransaction()
        self.doc.recompute()
        return True


def edit_target(obj):
    """El grupo de la operación, si obj es el grupo, algo de adentro o un pedazo armado por ella."""
    if obj is None:
        return None
    if hasattr(obj, MARK):
        return obj
    for parent in getattr(obj, "InList", []):
        if hasattr(parent, MARK):
            return parent
    base = getattr(obj, "BaseFeature", None) if obj.TypeId == BODY else None
    if base is not None:
        for parent in base.InList:
            if hasattr(parent, MARK):
                return parent
    return None


def open_panel(group):
    if FreeCADGui.Control.activeDialog():
        return None
    panel = DeleteBodiesPanel(group)
    dp._state["panel"] = panel
    FreeCADGui.Control.showDialog(panel)
    return panel


# --- Comando -------------------------------------------------------------------


def start(doc=None):
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return None
    if FreeCADGui.Control.activeDialog():
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), LABEL, "Cerrá primero el panel que está abierto.")
        return None
    picked = [(sel.Object, sub) for sel in FreeCADGui.Selection.getSelectionEx("", 0)
              for sub in (sel.SubElementNames or [""])]  # antes: el panel limpia la selección
    try:
        panel = DeleteBodiesPanel(doc=doc, items=[])
        dp._state["panel"] = panel
        for root, sub in picked:
            panel._pick(root, sub)
        panel._refresh()
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

        return {"MenuText": LABEL, "ToolTip": "Eliminar sólidos o quedarse solo con algunos (como SW)",
                "Pixmap": paths.icon("fork/delete_bodies") or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        start()


_installed = {}


def install():
    if (edit_target, open_panel) not in dp.OPENERS:
        dp.OPENERS.append((edit_target, open_panel))
    if not _installed:
        _installed["doc"] = _DocObserver()
        FreeCAD.addDocumentObserver(_installed["doc"])
        try:
            _installed["key"] = _DeleteKey()
            QtWidgets.QApplication.instance().installEventFilter(_installed["key"])
        except Exception:
            pass
    try:
        FreeCADGui.addCommand(COMMAND, _Command())
    except Exception:
        pass  # ya registrado
