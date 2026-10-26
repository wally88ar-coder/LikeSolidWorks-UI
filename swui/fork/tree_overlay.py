# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Dibujo sobre el árbol de operaciones, como el FeatureManager de SOLIDWORKS (etapa B).

- Barra de retroceso: línea amarilla debajo de la "punta" de cada cuerpo. Se
  arrastra con el mouse (manito) entre las operaciones; al soltarla se mueve
  la punta (feature_tree.set_tip, se puede deshacer).
- Lo que queda debajo de la barra se ve en gris, como en SW. Lo suprimido
  también (FreeCAD 26.3 ya lo tacha solo: desde esa versión no se pinta).
- Cara elegida en la vista 3D: un marco naranja en la operación que la creó
  (feature_tree.creator). FreeCAD marca además en azul la última operación
  (la que se ve); eso no se puede cambiar sin tocar FreeCAD.

Cómo: un widget transparente encima del área del árbol (hermano del viewport,
así no se corre al desplazar) que pinta usando visualItemRect de cada renglón,
y un filtro de eventos en el viewport para el arrastre. Los renglones se
relacionan con los objetos por su Label (únicos dentro de un documento).
Solo dentro de LikeSolidWorks UI.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

TREE_CLASS = "Gui::TreeWidget"
GREY = (247, 247, 247, 165)  # fondo del panel (look_sw), semitransparente: atenúa el renglón
BAR_FILL = "#f2c200"
BAR_LINE = "#6b5600"
BAR_HEIGHT = 4
GRAB = 5  # px alrededor de la barra donde se la puede agarrar
MARK = "#ff8c00"
NATIVE_SUPPRESSED_FROM = 26  # FreeCAD 26.3 tacha lo suprimido

_overlays = {}  # tree -> _Overlay
_mark = []  # [objeto] operación que creó la cara elegida
_sel_observer = None
_doc_observer = None


# --- Cuentas (sin Qt, probables en el test) ---------------------------


def gaps(rows):
    """
    Lugares donde puede quedar la barra. rows = [(obj, top, bottom, es_operación)]
    en orden visual. Devuelve [(y, punta)]: arriba de todo (punta None) y debajo de
    cada renglón (punta = última operación hasta ahí).
    """
    if not rows:
        return []
    out, tip = [(rows[0][1], None)], None
    for obj, _top, bottom, is_feat in rows:
        if is_feat:
            tip = obj
        out.append((bottom, tip))
    # Dos huecos seguidos con la misma punta: queda el de más abajo (después de croquis sueltos)
    clean = []
    for y, t in out:
        if clean and clean[-1][1] is t:
            clean[-1] = (y, t)
        else:
            clean.append((y, t))
    return clean


def nearest(gap_list, y):
    """Hueco más cercano a la altura y."""
    return min(gap_list, key=lambda g: abs(g[0] - y)) if gap_list else None


def bar_y(gap_list, tip):
    for y, t in gap_list:
        if t is tip:
            return y
    return None


# --- Renglones del árbol ------------------------------------------------


def _native_suppressed():
    try:
        return int(FreeCAD.Version()[0]) >= NATIVE_SUPPRESSED_FROM
    except Exception:
        return False


def _doc_of(item):
    while item.parent() is not None:
        item = item.parent()
    label = item.text(0)
    for doc in FreeCAD.listDocuments().values():
        if doc.Label == label:
            return doc
    return None


def _obj(doc, item):
    try:
        found = doc.getObjectsByLabel(item.text(0))
    except Exception:
        return None
    return found[0] if found else None


def _last_visible(item):
    while item.isExpanded() and item.childCount():
        item = item.child(item.childCount() - 1)
    return item


def body_rows(tree):
    """
    [(cuerpo, [(obj, (x, y, ancho, alto) del renglón, top, bottom, es_operación)])] de los
    cuerpos abiertos. Se mide todo en el momento: PySide invalida los QTreeWidgetItem de
    FreeCAD si se guardan para después ("Internal C++ object already deleted").
    """
    from swui.fork import feature_tree as ft

    out = []

    def walk(item, doc):
        obj = _obj(doc, item)
        if obj is not None and getattr(obj, "TypeId", "") == ft.BODY:
            if item.isExpanded():
                rows = []
                for i in range(item.childCount()):
                    child = item.child(i)
                    cobj = _obj(doc, child)
                    if cobj is None or getattr(cobj, "TypeId", "") == "App::Origin" or child.isHidden():
                        continue
                    rect = tree.visualItemRect(child)
                    if not rect.isValid():
                        continue
                    bottom = tree.visualItemRect(_last_visible(child)).bottom() + 1
                    box = (rect.x(), rect.y(), rect.width(), rect.height())
                    rows.append((cobj, box, rect.top(), bottom, ft.is_feature(cobj)))
                out.append((obj, rows))
            return  # dentro de un cuerpo no hay otros cuerpos
        if item.isExpanded():
            for i in range(item.childCount()):
                walk(item.child(i), doc)

    for i in range(tree.topLevelItemCount()):
        top = tree.topLevelItem(i)
        doc = _doc_of(top)
        if doc is not None:
            walk(top, doc)
    return out


def _gaps_of(rows):
    return gaps([(o, top, bottom, feat) for o, _i, top, bottom, feat in rows])


def _greyed(body, rows):
    """Renglones a atenuar: los que quedan debajo de la barra, o suprimidos."""
    from swui.fork import feature_tree as ft

    y = bar_y(_gaps_of(rows), body.Tip)
    native = _native_suppressed()
    out = []
    for obj, _box, top, bottom, feat in rows:
        below = y is not None and top >= y
        if below or (feat and not native and ft._suppressed(obj)):
            out.append((top, bottom))
    return out


# --- Widget encima del árbol ------------------------------------------


class _Overlay(QtWidgets.QWidget):
    def __init__(self, tree):
        super().__init__(tree)
        self.tree = tree
        self.drag = None  # (cuerpo, y de vista previa) mientras se arrastra
        self.hover = False
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setObjectName("SWUI_TreeOverlay")
        self.follow()
        self.show()
        self.raise_()

    def follow(self):
        self.setGeometry(self.tree.viewport().geometry())

    def paintEvent(self, _event):
        try:
            self._paint()
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Árbol (dibujo):\n%s\n" % traceback.format_exc())

    def _paint(self):
        p = QtGui.QPainter(self)
        width = self.width()
        grey = QtGui.QColor(*GREY)
        for body, rows in body_rows(self.tree):
            for top, bottom in _greyed(body, rows):
                p.fillRect(0, top, width, bottom - top, grey)
            for obj, (x, y0, w, h), _top, _bottom, _f in rows:
                if obj in _mark:
                    p.setPen(QtGui.QPen(QtGui.QColor(MARK), 2))
                    p.setBrush(QtCore.Qt.BrushStyle.NoBrush)
                    p.drawRect(x + 1, y0 + 1, min(w, width) - 3, h - 3)
            y = self.drag[1] if self.drag and self.drag[0] is body else bar_y(_gaps_of(rows), body.Tip)
            if y is None or not rows:
                continue
            left = rows[0][1][0]
            p.setPen(QtGui.QPen(QtGui.QColor(BAR_LINE), 1))
            p.setBrush(QtGui.QColor(BAR_FILL))
            p.drawRect(left, y - BAR_HEIGHT // 2, width - left - 3, BAR_HEIGHT)
        p.end()


class _DragFilter(QtCore.QObject):
    """Agarrar y soltar la barra de retroceso en el viewport del árbol."""

    def eventFilter(self, viewport, event):
        try:
            overlay = _overlays.get(viewport.parent())
            if overlay is None:
                return False
            t = event.type()
            if t == QtCore.QEvent.Type.Resize:
                overlay.follow()
                return False
            if t not in (QtCore.QEvent.Type.MouseMove, QtCore.QEvent.Type.MouseButtonPress,
                         QtCore.QEvent.Type.MouseButtonRelease):
                return False
            y = event.position().y() if hasattr(event, "position") else event.pos().y()
            if overlay.drag is not None:
                body = overlay.drag[0]
                rows = dict(body_rows(overlay.tree)).get(body, [])
                gap = nearest(_gaps_of(rows), y)
                if t == QtCore.QEvent.Type.MouseMove and gap is not None:
                    overlay.drag = (body, gap[0])
                    overlay.update()
                elif t == QtCore.QEvent.Type.MouseButtonRelease:
                    overlay.drag = None
                    viewport.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
                    overlay.update()
                    if gap is not None and gap[1] is not body.Tip:
                        _roll(body, gap[1])
                return True
            body = _bar_at(overlay.tree, y)
            if t == QtCore.QEvent.Type.MouseMove and not event.buttons():
                if body is not None and not overlay.hover:
                    viewport.setCursor(QtCore.Qt.CursorShape.OpenHandCursor)
                    overlay.hover = True
                elif body is None and overlay.hover:
                    viewport.unsetCursor()
                    overlay.hover = False
                return False
            if (t == QtCore.QEvent.Type.MouseButtonPress and body is not None
                    and event.button() == QtCore.Qt.MouseButton.LeftButton):
                overlay.drag = (body, bar_y(_gaps_of(dict(body_rows(overlay.tree))[body]), body.Tip))
                viewport.setCursor(QtCore.Qt.CursorShape.ClosedHandCursor)
                return True
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Árbol (barra):\n%s\n" % traceback.format_exc())
        return False


def _bar_at(tree, y):
    """Cuerpo cuya barra está a la altura y (o None)."""
    for body, rows in body_rows(tree):
        by = bar_y(_gaps_of(rows), body.Tip)
        if by is not None and abs(by - y) <= GRAB:
            return body
    return None


def _roll(body, tip):
    from swui.fork import feature_tree as ft

    ft._transaction(body.Document, "Mover barra de retroceso", lambda: ft.set_tip(body, tip))


_filter = None


def refresh():
    for overlay in list(_overlays.values()):
        try:
            overlay.update()
        except Exception:
            pass


def _later_refresh():
    QtCore.QTimer.singleShot(0, refresh)


class _DocObserver:
    """Punta, supresión, orden o nombres cambiados: volver a dibujar."""

    def slotChangedObject(self, obj, prop):
        if _overlays and prop in ("Tip", "Suppressed", "Group", "Label"):
            _later_refresh()

    def slotUndoDocument(self, _doc):
        if _overlays:
            _later_refresh()

    def slotRedoDocument(self, _doc):
        if _overlays:
            _later_refresh()


class _SelObserver:
    """Cara elegida en la vista 3D -> marcar la operación que la creó."""

    def addSelection(self, doc, obj, sub, _pnt):
        if _overlays:
            QtCore.QTimer.singleShot(0, _update_mark)

    def removeSelection(self, doc, obj, sub):
        if _overlays:
            QtCore.QTimer.singleShot(0, _update_mark)

    def setSelection(self, doc):
        if _overlays:
            QtCore.QTimer.singleShot(0, _update_mark)

    def clearSelection(self, doc):
        if _mark:
            del _mark[:]
            _later_refresh()


def _update_mark():
    from swui.fork import feature_tree as ft

    new = None
    try:
        sel = FreeCADGui.Selection.getSelectionEx()
        if len(sel) == 1 and len(sel[0].SubElementNames) == 1 and sel[0].SubElementNames[0].startswith("Face"):
            feature = sel[0].Object
            found = ft.creator(feature, sel[0].SubObjects[0])
            if found is not None and found is not feature:
                new = found
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Árbol (cara):\n%s\n" % traceback.format_exc())
    if (_mark[0] if _mark else None) is new:
        return
    del _mark[:]
    if new is not None:
        _mark.append(new)
        _scroll_to(new)
    refresh()


def _scroll_to(obj):
    """Desplazar el árbol hasta el renglón de obj (si está a la vista en un cuerpo abierto)."""
    for tree in _overlays:
        for _body, rows in body_rows(tree):
            for o, (x, y, w, h), *_r in rows:
                if o is obj:
                    height = tree.viewport().height()
                    if 0 <= y and y + h <= height:
                        return  # ya se ve
                    bar = tree.verticalScrollBar()
                    delta = y - height // 2
                    per_pixel = tree.verticalScrollMode() == QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
                    bar.setValue(bar.value() + (delta if per_pixel else delta // max(h, 1)))
                    return


def _trees():
    return [t for t in FreeCADGui.getMainWindow().findChildren(QtWidgets.QTreeWidget)
            if t.metaObject().className() == TREE_CLASS]


def attach():
    """Poner el dibujo sobre los árboles (al entrar a LikeSolidWorks UI)."""
    global _filter, _sel_observer, _doc_observer
    try:
        if _filter is None:
            _filter = _DragFilter()
        for tree in _trees():
            if tree in _overlays:
                continue
            _overlays[tree] = _Overlay(tree)
            tree.viewport().installEventFilter(_filter)
            tree.viewport().setMouseTracking(True)
            for signal in (tree.itemExpanded, tree.itemCollapsed):
                signal.connect(lambda *_a: _later_refresh())
        if _doc_observer is None:
            _doc_observer = _DocObserver()
            FreeCAD.addDocumentObserver(_doc_observer)
        if _sel_observer is None:
            _sel_observer = _SelObserver()
            FreeCADGui.Selection.addObserver(_sel_observer)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Árbol (dibujo) no disponible:\n%s\n" % traceback.format_exc())


def detach():
    """Sacar el dibujo (al salir de LikeSolidWorks UI)."""
    global _sel_observer
    for tree, overlay in list(_overlays.items()):
        try:
            tree.viewport().removeEventFilter(_filter)
            tree.viewport().unsetCursor()
            overlay.hide()
            overlay.deleteLater()
        except Exception:
            pass
    _overlays.clear()
    del _mark[:]
    if _sel_observer is not None:
        try:
            FreeCADGui.Selection.removeObserver(_sel_observer)
        except Exception:
            pass
        _sel_observer = None


def install():
    from swui import layout

    if getattr(layout.enter, "_swui_overlay", False):
        return
    original_enter, original_leave = layout.enter, layout.leave

    def enter(_original=original_enter):
        result = _original()
        attach()
        return result

    def leave(_original=original_leave):
        detach()
        return _original()

    enter._swui_overlay = leave._swui_overlay = True
    layout.enter, layout.leave = enter, leave
