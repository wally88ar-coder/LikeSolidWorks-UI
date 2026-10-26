# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Árbol de operaciones como el FeatureManager de SOLIDWORKS (etapa A).

Clic derecho sobre una operación (en el árbol o sobre una cara en la vista 3D),
arriba de todo, como en SW:
    Editar operación / Editar croquis
    Suprimir / Desactivar supresión / Desactivar supresión con dependientes
    Retroceder / Avanzar / Avanzar hasta el final
    Padre/Hijo...

Por debajo, siempre lo nativo de FreeCAD:
- Retroceder/avanzar = la "punta" (Tip) del cuerpo: lo que queda debajo no se
  calcula y lo nuevo se inserta ahí. "Retroceder" deja la barra justo ANTES de
  la operación elegida, como en SW.
- Suprimir = la propiedad Suppressed de la operación (FreeCAD 1.0+). Como en
  SW, también se suprimen las que dependen de ella (croquis sobre sus caras,
  redondeos de sus aristas...). Un croquis o plano apoyado en una cara
  suprimida perdería su apoyo y daría error: se le apaga el apoyo
  (MapMode "Deactivated", queda donde estaba) y se guarda el modo anterior en
  la propiedad oculta SWUI_SuppressedMapMode para devolverlo al desactivar la
  supresión. NO usar "congelar" (Std_ToggleFreeze): en 1.1.4 cuelga FreeCAD
  al guardar el archivo (probado).
- Las dependencias "de verdad" son los vínculos de la operación MENOS
  BaseFeature (en Part Design cada operación toma el sólido de la anterior:
  eso no la hace hija en el sentido de SW).

Además:
- Al crear un cuerpo, el árbol muestra abiertos el cuerpo y su Origen (los
  planos Alzado/Planta/Vista lateral a la vista, como en SW).
- Al guardar una pieza retrocedida, aviso con "Avanzar hasta el final y guardar".

El menú se agrega con un "manipulador de banco" de FreeCAD (insertar antes de
"Colocación" en el árbol y antes de "Ajustar todo" en la vista); solo actúa
dentro de LikeSolidWorks UI.

NOMBRES INTERNOS ESTABLES: SWUI_SuppressedMapMode queda guardado en los
archivos del usuario. No cambiarlo nunca (ver docs/ESTADO.md, Decisiones).
"""

import traceback

import FreeCAD
import FreeCADGui

WB_NAME = "LikeSolidWorksUIWorkbench"
FEATURE = "PartDesign::Feature"
SKETCH = "Sketcher::SketchObject"
BODY = "PartDesign::Body"
NOT_PARENTS = ("BaseFeature", "_Body")  # vínculos que no son "padre" en el sentido de SW
MAPMODE_PROP = "SWUI_SuppressedMapMode"  # NO CAMBIAR: queda en los archivos
OFF = "Deactivated"

EDIT = "SWUI_EditFeature"
EDIT_SKETCH = "SWUI_EditSketch"
SUPPRESS = "SWUI_Suppress"
UNSUPPRESS = "SWUI_Unsuppress"
UNSUPPRESS_ALL = "SWUI_UnsuppressWithChildren"
ROLLBACK = "SWUI_Rollback"
ROLL_FORWARD = "SWUI_RollForward"
ROLL_END = "SWUI_RollToEnd"
PARENT_CHILD = "SWUI_ParentChild"

# Ancla del menú: lo nuestro va antes de este comando (arriba de todo).
ANCHOR = {"Tree": "Std_Placement", "View": "Std_ViewFitAll"}
FREEZE = "Std_ToggleFreeze"

_menu = None
_menu_show = None
_observer = None


# --- Lógica (sin interfaz, probable en el test) ----------------------


def is_feature(obj):
    """Operación de sólido de Part Design (Extruir, Corte, Redondeo...). Croquis y planos no."""
    try:
        return bool(obj.isDerivedFrom(FEATURE))
    except Exception:
        return False


def is_sketch(obj):
    try:
        return bool(obj.isDerivedFrom(SKETCH))
    except Exception:
        return False


def body_of(obj):
    try:
        group = obj.getParentGeoFeatureGroup()
    except Exception:
        return None
    return group if group is not None and getattr(group, "TypeId", "") == BODY else None


def features(body):
    """Operaciones de sólido del cuerpo, en orden."""
    return [o for o in body.Group if is_feature(o)]


def rollback_target(feats, selected):
    """Retroceder: la punta pasa a la operación anterior a la elegida (None = antes de todo)."""
    i = feats.index(selected)
    return feats[i - 1] if i > 0 else None


def forward_target(feats, tip):
    """Avanzar una operación. None si ya está al final."""
    if not feats:
        return None
    if tip is None:
        return feats[0]
    i = feats.index(tip) if tip in feats else len(feats) - 1
    return feats[i + 1] if i + 1 < len(feats) else None


def rolled_back(feats, tip):
    """¿La barra no está al final?"""
    return bool(feats) and tip is not feats[-1]


def _objects_in(value):
    """Objetos dentro del valor de una propiedad de vínculo (obj, (obj, subs), listas)."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        if len(value) == 2 and hasattr(value[0], "Name") and not hasattr(value[1], "Name"):
            return [value[0]]  # (obj, subs)
        out = []
        for item in value:
            out.extend(_objects_in(item))
        return out
    return [value] if hasattr(value, "Name") else []


def links(obj):
    """Objetos a los que apunta obj, sin BaseFeature ni el cuerpo."""
    out = []
    for name in getattr(obj, "PropertiesList", []):
        if name in NOT_PARENTS:
            continue
        try:
            if "Link" not in obj.getTypeIdOfProperty(name):
                continue
            targets = _objects_in(getattr(obj, name))
        except Exception:
            continue
        for target in targets:
            if target is not obj and target not in out:
                out.append(target)
    return out


def _is_container(obj):
    return getattr(obj, "TypeId", "") in (BODY, "App::Origin", "App::Part")


def parents(obj):
    return [o for o in links(obj) if not _is_container(o)]


def children(obj):
    return [o for o in getattr(obj, "InList", []) if not _is_container(o) and obj in links(o)]


def dependents(obj):
    """Todo lo que depende de obj (hijos, nietos...), sin repetir."""
    seen, todo = [], list(children(obj))
    while todo:
        o = todo.pop(0)
        if o in seen or o is obj:
            continue
        seen.append(o)
        todo.extend(children(o))
    return seen


def _attached_to(obj):
    """Objetos a los que está apoyado un croquis o plano (su AttachmentSupport)."""
    try:
        return _objects_in(obj.AttachmentSupport)
    except Exception:
        return []


def _suppressed(obj):
    return bool(getattr(obj, "Suppressed", False))


def sync_attachments(objs):
    """
    Croquis/planos apoyados en una operación suprimida: apagar el apoyo (y
    guardar el modo). Los que ya no tienen nada suprimido debajo: devolverlo.
    Devuelve (apagados, devueltos).
    """
    off, back = [], []
    for obj in objs:
        if is_feature(obj) or not hasattr(obj, "MapMode"):
            continue
        support_gone = any(_suppressed(t) for t in _attached_to(obj))
        saved = getattr(obj, MAPMODE_PROP, None) if MAPMODE_PROP in getattr(obj, "PropertiesList", []) else None
        if support_gone and saved is None and obj.MapMode != OFF:
            if MAPMODE_PROP not in obj.PropertiesList:
                obj.addProperty("App::PropertyString", MAPMODE_PROP, "SWUI",
                                "Apoyo del croquis antes de suprimir (LikeSolidWorks UI)")
                try:
                    obj.setPropertyStatus(MAPMODE_PROP, "Hidden")
                except Exception:
                    pass
            setattr(obj, MAPMODE_PROP, obj.MapMode)
            obj.MapMode = OFF
            off.append(obj)
        elif not support_gone and saved:
            obj.MapMode = saved
            obj.removeProperty(MAPMODE_PROP)
            back.append(obj)
    return off, back


def suppress(obj):
    """Suprimir obj y lo que depende de él, como SW. Devuelve las operaciones suprimidas."""
    done = []
    for o in [obj] + dependents(obj):
        if is_feature(o) and not _suppressed(o):
            o.Suppressed = True
            done.append(o)
    body = body_of(obj)
    sync_attachments(body.Group if body is not None else [obj] + dependents(obj))
    return done


def unsuppress(obj, with_children=False):
    """Desactivar supresión de obj (y de sus dependientes si with_children)."""
    done = []
    for o in [obj] + (dependents(obj) if with_children else []):
        if is_feature(o) and _suppressed(o):
            o.Suppressed = False
            done.append(o)
    body = body_of(obj)
    sync_attachments(body.Group if body is not None else [obj] + dependents(obj))
    return done


def menu_commands(objs):
    """Comandos del clic derecho para lo seleccionado (vacío si no es de un cuerpo)."""
    objs = [o for o in objs if body_of(o) is not None and (is_feature(o) or is_sketch(o))]
    if not objs:
        return []
    obj = objs[0]
    out = []
    if is_feature(obj):
        out.append(EDIT)
    if is_sketch(obj) or _profile_sketch(obj) is not None:
        out.append(EDIT_SKETCH)
    if is_feature(obj):
        if _suppressed(obj):
            out += [UNSUPPRESS, UNSUPPRESS_ALL]
        else:
            out.append(SUPPRESS)
        out.append(ROLLBACK)
    body = body_of(obj)
    if rolled_back(features(body), body.Tip):
        out += [ROLL_FORWARD, ROLL_END]
    out.append(PARENT_CHILD)
    return out


def _profile_sketch(obj):
    try:
        profile = _objects_in(obj.Profile)
    except Exception:
        return None
    return profile[0] if profile and is_sketch(profile[0]) else None


# --- Acciones sobre el documento --------------------------------------


def _in_workbench():
    try:
        return FreeCADGui.activeWorkbench().name() == WB_NAME
    except Exception:
        return False


def selected():
    """Objetos elegidos (una cara en la vista 3D cuenta como su operación)."""
    try:
        return [s.Object for s in FreeCADGui.Selection.getSelectionEx()]
    except Exception:
        return []


def _first(test):
    for obj in selected():
        if test(obj) and body_of(obj) is not None:
            return obj
    return None


def _transaction(doc, name, fn):
    doc.openTransaction(name)
    try:
        result = fn()
        doc.recompute()
    except Exception:
        doc.abortTransaction()
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (name, traceback.format_exc()))
        return None
    doc.commitTransaction()
    return result


def set_tip(body, tip):
    """Mover la barra: nueva punta del cuerpo; se ve solo la punta, como hace Part Design."""
    body.Tip = tip
    for f in features(body):
        try:
            f.ViewObject.Visibility = f is tip
        except Exception:
            pass


def roll_to(body, where):
    """where: 'end' o 'forward'."""
    feats = features(body)
    target = feats[-1] if where == "end" and feats else forward_target(feats, body.Tip)
    if target is not None:
        _transaction(body.Document, "Avanzar", lambda: set_tip(body, target))


def check_saved(doc):
    """Después de guardar: si alguna pieza quedó retrocedida, ofrecer avanzar y volver a guardar."""
    bodies = [o for o in doc.Objects if getattr(o, "TypeId", "") == BODY and rolled_back(features(o), o.Tip)]
    if not bodies or not _in_workbench():
        return
    from swui.compat import QtWidgets

    names = ", ".join(b.Label for b in bodies)
    box = QtWidgets.QMessageBox(FreeCADGui.getMainWindow())
    box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
    box.setWindowTitle("Pieza retrocedida")
    box.setText("Se guardó con la barra de retroceso a mitad del árbol (%s).\n"
                "Al abrirla, las operaciones de abajo van a seguir sin calcular." % names)
    go = box.addButton("Avanzar hasta el final y guardar", QtWidgets.QMessageBox.ButtonRole.AcceptRole)
    box.addButton("Dejar así", QtWidgets.QMessageBox.ButtonRole.RejectRole)
    box.exec()
    if box.clickedButton() is go:
        for body in bodies:
            roll_to(body, "end")
        doc.save()


def expand_body(doc_name, body_name):
    """Abrir en el árbol el cuerpo y su Origen (los planos a la vista, como en SW)."""
    try:
        doc = FreeCAD.getDocument(doc_name)
        body = doc.getObject(body_name)
        gdoc = FreeCADGui.getDocument(doc_name)
        gdoc.toggleTreeItem(body, 2)  # 2 = abrir
        if getattr(body, "Origin", None) is not None:
            gdoc.toggleTreeItem(body.Origin, 2)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Árbol: no se pudo abrir el cuerpo.\n")


class _Observer:
    """Cuerpos nuevos (abrir en el árbol) y documentos guardados (aviso de retroceso)."""

    def slotCreatedObject(self, obj):
        if getattr(obj, "TypeId", "") != BODY or not _in_workbench():
            return
        from swui.compat import QtCore

        doc_name, name = obj.Document.Name, obj.Name
        QtCore.QTimer.singleShot(300, lambda: expand_body(doc_name, name))

    def slotFinishSaveDocument(self, doc, filename):
        from swui.compat import QtCore

        name = doc.Name
        QtCore.QTimer.singleShot(0, lambda: _check_saved_later(name))


def _check_saved_later(name):
    try:
        check_saved(FreeCAD.getDocument(name))
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Aviso de retroceso:\n%s\n" % traceback.format_exc())


def arrange_menu(menu):
    """
    FreeCAD pone arriba del menú del árbol las opciones propias de la operación
    ("Editar vaciado", "Suprimido", "Toggle Freeze"...). Lo nuestro sube arriba
    de todo, como en SW, y se oculta "Toggle Freeze" (cuelga FreeCAD 1.1.4 al
    guardar). Devuelve True si cambió algo.
    """
    actions = menu.actions()
    names = [n for n, _c in COMMANDS]
    ours = [a for a in actions if a.objectName() in names]
    changed = False
    for action in actions:
        if action.objectName() == FREEZE and action.isVisible():
            action.setVisible(False)
            changed = True
    if not ours or actions[0] is ours[0]:
        return changed
    after = actions.index(ours[-1]) + 1
    move = ours + ([actions[after]] if after < len(actions) and actions[after].isSeparator() else [])
    menu.insertActions(actions[0], move)
    return True


class _MenuShow:
    """Filtro de la aplicación: arreglar cada menú contextual al mostrarse."""

    def __init__(self):
        from swui.compat import QtCore, QtWidgets

        class Filter(QtCore.QObject):
            def eventFilter(self, obj, event):
                try:
                    if event.type() == QtCore.QEvent.Type.Show and isinstance(obj, QtWidgets.QMenu):
                        if arrange_menu(obj):
                            obj.adjustSize()
                except Exception:
                    pass
                return False

        self.filter = Filter()
        self.on = False

    def set(self, on):
        from swui.compat import QtWidgets

        if on != self.on:
            app = QtWidgets.QApplication.instance()
            (app.installEventFilter if on else app.removeEventFilter)(self.filter)
            self.on = on


class _MenuManipulator:
    """Agrega lo nuestro arriba del clic derecho (solo dentro de LikeSolidWorks UI)."""

    def modifyContextMenu(self, recipient):
        try:
            if recipient not in ANCHOR or not _in_workbench():
                return []
            commands = menu_commands(selected())
            if not commands:
                return []
            anchor = ANCHOR[recipient]
            return [{"insert": c, "menuItem": anchor} for c in commands + ["Separator"]]
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Menú del árbol:\n%s\n" % traceback.format_exc())
            return []


# --- Comandos ----------------------------------------------------------


class _Command:
    menu = ""
    tip = ""

    def GetResources(self):
        return {"MenuText": self.menu, "ToolTip": self.tip}

    def IsActive(self):
        return self.target() is not None

    def target(self):
        return None


class _EditFeature(_Command):
    menu = "Editar operación"
    tip = "Abre el diálogo de la operación para cambiar sus valores"

    def target(self):
        return _first(is_feature)

    def Activated(self):
        FreeCADGui.ActiveDocument.setEdit(self.target())


class _EditSketch(_Command):
    menu = "Editar croquis"
    tip = "Abre el croquis de la operación"

    def target(self):
        obj = _first(lambda o: is_sketch(o) or is_feature(o))
        if obj is None or is_sketch(obj):
            return obj
        return _profile_sketch(obj)

    def Activated(self):
        FreeCADGui.ActiveDocument.setEdit(self.target())


class _Suppress(_Command):
    menu = "Suprimir"
    tip = "Deja de calcular la operación y las que dependen de ella (siguen en el árbol)"

    def target(self):
        objs = [o for o in selected() if is_feature(o) and body_of(o) is not None and not _suppressed(o)]
        return objs or None

    def Activated(self):
        objs = self.target()
        _transaction(objs[0].Document, "Suprimir", lambda: [suppress(o) for o in objs])


class _Unsuppress(_Command):
    menu = "Desactivar supresión"
    tip = "Vuelve a calcular la operación (las que dependen de ella siguen suprimidas)"
    with_children = False

    def target(self):
        objs = [o for o in selected() if is_feature(o) and body_of(o) is not None and _suppressed(o)]
        return objs or None

    def Activated(self):
        objs = self.target()
        _transaction(objs[0].Document, self.menu,
                     lambda: [unsuppress(o, self.with_children) for o in objs])


class _UnsuppressAll(_Unsuppress):
    menu = "Desactivar supresión con dependientes"
    tip = "Vuelve a calcular la operación y las que dependen de ella"
    with_children = True


class _Rollback(_Command):
    menu = "Retroceder"
    tip = "Lleva la barra de retroceso justo antes de esta operación"

    def target(self):
        return _first(is_feature)

    def Activated(self):
        obj = self.target()
        body = body_of(obj)
        _transaction(obj.Document, "Retroceder", lambda: set_tip(body, rollback_target(features(body), obj)))


class _RollForward(_Command):
    menu = "Avanzar"
    tip = "Lleva la barra de retroceso una operación más abajo"
    where = "forward"

    def target(self):
        for obj in selected():
            body = obj if getattr(obj, "TypeId", "") == BODY else body_of(obj)
            if body is not None and rolled_back(features(body), body.Tip):
                return body
        return None

    def Activated(self):
        roll_to(self.target(), self.where)


class _RollToEnd(_RollForward):
    menu = "Avanzar hasta el final"
    tip = "Lleva la barra de retroceso al final del árbol"
    where = "end"


class _ParentChild(_Command):
    menu = "Padre/Hijo..."
    tip = "De qué depende esta operación y qué depende de ella"

    def target(self):
        return _first(lambda o: is_feature(o) or is_sketch(o))

    def Activated(self):
        from swui.fork import tree_dialogs

        tree_dialogs.show_parent_child(self.target())


COMMANDS = (
    (EDIT, _EditFeature), (EDIT_SKETCH, _EditSketch),
    (SUPPRESS, _Suppress), (UNSUPPRESS, _Unsuppress), (UNSUPPRESS_ALL, _UnsuppressAll),
    (ROLLBACK, _Rollback), (ROLL_FORWARD, _RollForward), (ROLL_END, _RollToEnd),
    (PARENT_CHILD, _ParentChild),
)


def install():
    """Comandos, menú del clic derecho y observador de documentos."""
    global _menu, _observer
    for name, cls in COMMANDS:
        try:
            FreeCADGui.addCommand(name, cls())
        except Exception:
            pass  # ya registrado
    if _menu is None and hasattr(FreeCADGui, "addWorkbenchManipulator"):
        _menu = _MenuManipulator()
        FreeCADGui.addWorkbenchManipulator(_menu)
    if _observer is None:
        _observer = _Observer()
        FreeCAD.addDocumentObserver(_observer)
    from swui import layout

    if getattr(layout.enter, "_swui_tree", False):
        return
    original_enter, original_leave = layout.enter, layout.leave

    def enter(_original=original_enter):
        result = _original()
        _menu_order(True)
        return result

    def leave(_original=original_leave):
        _menu_order(False)
        return _original()

    enter._swui_tree = leave._swui_tree = True
    layout.enter, layout.leave = enter, leave


def _menu_order(on):
    """Ordenar los menús contextuales solo dentro de LikeSolidWorks UI."""
    global _menu_show
    try:
        if _menu_show is None:
            _menu_show = _MenuShow()
        _menu_show.set(on)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Orden del menú:\n%s\n" % traceback.format_exc())
