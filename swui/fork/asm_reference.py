# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Geometría de referencia en el ensamblaje (fase 5, etapa 5): Plano, Eje y Punto con los mismos
paneles SW de la pieza (ref_plane_panel / ref_axis_point_panel), sobre los planos, ejes y puntos
de referencia de Part (Part::DatumPlane / DatumLine / DatumPoint) en la raíz del ensamblaje.

Diferencias con la pieza:
- Lo que se toca en la vista pasa por el componente: la referencia queda (Placa<1>, "Body.Face7"),
  así el plano sigue a la pieza aunque se mueva en el ensamblaje.
- El motor de cálculo del ensamblaje no toma un plano apoyado en algo (FreeCAD 1.1.4 los rechaza
  en sus uniones y el motor los ignora: probado). Si todas las referencias son del origen del
  ensamblaje (o de otros planos fijos), al aceptar el plano queda fijo en su lugar (sin apoyo) y
  sirve para relaciones de posición; editarlo lo vuelve a armar desde lo guardado. Apoyado en una
  pieza sirve para matrices y simetría de componentes.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore

PLANE_CMD = "SWUI_AssemblyPlane"
AXIS_CMD = "SWUI_AssemblyAxis"
POINT_CMD = "SWUI_AssemblyPoint"
TYPES = {"plane": "Part::DatumPlane", "axis": "Part::DatumLine", "point": "Part::DatumPoint"}
LABELS = {"plane": "Plano", "axis": "Eje", "point": "Punto"}
FIXED_TYPES = ("App::Origin", "App::Plane", "App::Line", "App::Point")

_installed = False


def fixed_only(support):
    """True si todas las referencias son del origen o planos/ejes ya fijos (no siguen a ninguna pieza)."""
    if not support:
        return False
    for obj, _subs in support:
        if obj.TypeId in FIXED_TYPES:
            continue
        if obj.TypeId.startswith("Part::Datum") and getattr(obj, "MapMode", "") == "Deactivated":
            continue
        return False
    return True


def in_assembly(obj):
    return any(p.TypeId == "Assembly::AssemblyObject" for p in getattr(obj, "InList", []))


def assembly_of(obj):
    return next((p for p in obj.InList if p.TypeId == "Assembly::AssemblyObject"), None)


def _refs_from_selection(asm):
    """[(objeto, sub)] de lo elegido: (componente, 'Body.FaceN') o un plano/eje/punto del ensamblaje."""
    from swui.fork import component_patterns as cp

    out = []
    try:
        sels = FreeCADGui.Selection.getSelectionEx("", 0)
    except Exception:
        return out
    import UtilsAssembly as ua

    for sel in sels:
        for sub in list(sel.SubElementNames or []) or [""]:
            try:
                leaf_obj = sel.Object.getSubObject(sub, 1)
            except Exception:
                leaf_obj = None
            if leaf_obj is not None and (leaf_obj.TypeId in FIXED_TYPES or leaf_obj.TypeId.startswith("Part::Datum")) \
                    and not sub.rsplit(".", 1)[-1]:
                out.append((leaf_obj, ""))
                continue
            try:
                comp, rel = ua.getComponentReference(asm, sel.Object, sub)
            except Exception:
                comp, rel = None, ""
            if comp is not None and rel.rsplit(".", 1)[-1]:
                out.append((comp, cp.clean_sub(rel)))
    return out


class _AsmMixin:
    """Selección a través de los componentes; al cerrar, fijo si va al origen y volver al ensamblaje."""

    def take_selection(self):
        refs = _refs_from_selection(self.asm)
        self.busy = True
        try:
            FreeCADGui.Selection.clearSelection()
        finally:
            self.busy = False
        changed = False
        for obj, sub in refs:
            try:
                changed = self._pick(obj, sub) or changed
            except Exception:
                FreeCAD.Console.PrintError("[SWUI fork] Selección:\n%s\n" % traceback.format_exc())
        if changed:
            self._refresh()
            self.preview()

    def _flyout(self, on):
        pass  # sin Cuerpo: no hay árbol flotante de la pieza

    def accept(self):
        done = super().accept()
        if done:
            self._fix_if_origin()
            self._back()
        return done

    def reject(self):
        done = super().reject()
        self._back()
        return done

    def _fix_if_origin(self):
        obj = self.obj
        try:
            if obj.MapMode != "Deactivated" and fixed_only(list(obj.AttachmentSupport)):
                plc = obj.Placement
                doc = obj.Document
                doc.openTransaction("Fijar " + obj.Label)
                obj.MapMode = "Deactivated"
                obj.AttachmentSupport = None
                obj.Placement = plc
                doc.commitTransaction()
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Referencia fija:\n%s\n" % traceback.format_exc())

    def _back(self):
        from swui.fork import component_patterns

        QtCore.QTimer.singleShot(0, lambda: component_patterns._back_to(self.asm))


_classes = {}


def panel_class(kind):
    if kind in _classes:
        return _classes[kind]
    from swui.fork import ref_axis_point_panel as rap
    from swui.fork import ref_plane_panel as rp

    base = {"plane": rp.PlanePanel, "axis": rap.AxisPanel, "point": rap.PointPanel}[kind]

    class Panel(_AsmMixin, base):
        def __init__(self, obj):
            self.asm = assembly_of(obj)
            super().__init__(obj)

    Panel.__name__ = "Asm%sPanel" % kind.capitalize()
    _classes[kind] = Panel
    return Panel


def kind_of_obj(obj):
    for kind, type_id in TYPES.items():
        if obj.TypeId == type_id:
            return kind
    return None


def _choose(obj):
    """Editar (doble clic o clic derecho) un plano/eje/punto del ensamblaje: el panel SW."""
    kind = kind_of_obj(obj)
    if kind is None or not in_assembly(obj) or getattr(obj, "SWUI_Own", False):
        return None
    return panel_class(kind)


def edit_target(obj):
    """Clic derecho 'Editar operación' sobre un plano/eje/punto del ensamblaje."""
    return obj if _choose(obj) is not None else None


def open_editor(obj):
    try:
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
    except Exception:
        pass
    try:
        panel = _choose(obj)(obj)
        FreeCADGui.Control.showDialog(panel)
        return panel
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Editar referencia:\n%s\n" % traceback.format_exc())
        return None


def start(kind):
    from swui.fork import mates_sw

    asm = mates_sw.ensure_active()
    if asm is None:
        FreeCAD.Console.PrintWarning("[SWUI] %s: abrí o activá un ensamblaje primero.\n" % LABELS[kind])
        return None
    try:
        if FreeCADGui.Control.activeDialog():
            FreeCADGui.Control.closeDialog()
    except Exception:
        pass
    doc = asm.Document
    picked = _refs_from_selection(asm)
    doc.openTransaction(LABELS[kind])
    obj = asm.newObject(TYPES[kind], {"plane": "Plano", "axis": "Eje", "point": "Punto"}[kind])
    obj.MapMode = "Deactivated"
    try:
        panel = panel_class(kind)(obj)
        FreeCADGui.Control.showDialog(panel)
        for ref_obj, sub in picked:  # lo elegido antes del comando entra como primeras referencias
            panel._pick(ref_obj, sub)
        if picked:
            panel._refresh()
            panel.preview()
        return panel
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] %s de referencia:\n%s\n" % (LABELS[kind], traceback.format_exc()))
        doc.abortTransaction()
        return None


class _Command:
    def __init__(self, kind):
        self.kind = kind

    def GetResources(self):
        from swui import paths

        icons = {"plane": "sketch/f_plane", "axis": "sketch/f_axis", "point": "sketch/f_point"}
        return {"MenuText": LABELS[self.kind] + " (ensamblaje)",
                "ToolTip": "%s de referencia en el ensamblaje (como SW): sirve para relaciones, matrices "
                           "y simetría" % LABELS[self.kind],
                "Pixmap": paths.icon(icons[self.kind]) or ""}

    def IsActive(self):
        from swui.fork import mates_sw

        doc = FreeCAD.ActiveDocument
        return doc is not None and bool(mates_sw._assemblies(doc))

    def Activated(self):
        start(self.kind)


FLYOUT = [
    ("SWUI_AssemblyPlane", "Plano", {"svg": "sketch/f_plane"}),
    ("SWUI_AssemblyAxis", "Eje", {"svg": "sketch/f_axis"}),
    ("SWUI_AssemblyPoint", "Punto", {"svg": "sketch/f_point"}),
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
    for cmd, kind in ((PLANE_CMD, "plane"), (AXIS_CMD, "axis"), (POINT_CMD, "point")):
        try:
            FreeCADGui.addCommand(cmd, _Command(kind))
        except Exception:
            pass  # ya registrado
    install_ribbon()
    from swui.fork import dress_up_panel as dp

    if _choose not in dp.CHOOSERS:
        dp.CHOOSERS.append(_choose)
    if (edit_target, open_editor) not in dp.OPENERS:
        dp.OPENERS.append((edit_target, open_editor))
    _installed = True
