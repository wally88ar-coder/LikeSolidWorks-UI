# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Matriz de componente lineal / circular y Simetría de componentes, como SW 2018 (fase 5, etapa 3).

Todo con objetos nativos (el archivo abre sin el addon):
- Datos de cada operación en un App::VarSet del ensamblaje ("MatrizLineal1", "MatrizCircular1",
  "SimetríaDeComponentes1"): espaciado, instancias, ángulo... y vínculos a la dirección, las
  semillas y las copias (propiedades SWUI_*, nombres estables).
- Matriz: por cada componente semilla, un App::Link con varias copias (ShowElement, ElementCount);
  cada copia (App::LinkElement) tiene una expresión de posición que parte de la semilla y de la
  dirección: `Dir.Placement * translationm(0; 0; i * Datos.Espaciado) * minvert(Dir.Placement) *
  Semilla.Placement` (circular: rotationz). La dirección es un eje o plano de referencia nativo
  apoyado en lo que se eligió (arista, cara, eje), así que sigue a la pieza.
- Simetría, misma pieza: App::Link con expresión de espejo (dos espejos = posición rígida):
  `Plano * F * Plano^-1 * Semilla * S` (S = espejo propio de la pieza simétrica).
- Simetría, versión opuesta: archivo nuevo "<pieza>-opuesta.FCStd" con un SubShapeBinder de la
  pieza original + Part::Mirroring + Cuerpo; se reconstruye solo al abrirlo si la original cambió.
- El motor de cálculo del ensamblaje mueve las piezas sin avisar a quien depende de ellas: un
  observador avisa (touch) a las copias y a los ejes/planos apoyados (decisión del usuario,
  2026-10-27).
"""

import os
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

LINEAR = "SWUI_ComponentLinearPattern"
CIRCULAR = "SWUI_ComponentCircularPattern"
MIRROR = "SWUI_MirrorComponents"

KIND = "SWUI_Pattern"  # "linear" / "circular" / "mirror" en el VarSet (nombre estable)
SEEDS = "SWUI_Seeds"
COPIES = "SWUI_Copies"
DIR1 = "SWUI_Direction"
DIR2 = "SWUI_Direction2"
PLANE = "SWUI_Plane"
OPPOSITE = "SWUI_Opposite"  # nombres de las semillas con versión opuesta
OPPOSITE_MARK = "SWUI_OppositeOf"  # en el binder del archivo opuesto

TITLES = {"linear": "MatrizLineal", "circular": "MatrizCircular", "mirror": "SimetríaDeComponentes"}
LABELS = {"linear": "Matriz de componente lineal", "circular": "Matriz de componente circular",
          "mirror": "Simetría de componentes"}
ICONS = {"linear": "sketch/f_pattern_linear", "circular": "sketch/f_pattern_polar", "mirror": "sketch/f_mirror"}

FMAT = "matrix(1;0;0;0; 0;1;0;0; 0;0;-1;0; 0;0;0;1)"  # espejo en Z

_installed = False


# --- Cuentas sin FreeCAD (probables en el test) ---------------------------------


def grid_indices(n1, n2=1):
    """Posiciones (i, j) de las copias de una matriz de n1 x n2 instancias, sin la semilla (0, 0)."""
    return [(i, j) for j in range(max(1, n2)) for i in range(max(1, n1)) if (i, j) != (0, 0)]


def linear_expression(seed, data, dir1, i, sign1=1, dir2=None, j=0, sign2=1):
    """Expresión de posición de la copia (i, j) de una matriz lineal."""
    parts = []
    if i:
        parts.append("%s.Placement * translationm(0; 0; %d * %s.Espaciado) * minvert(%s.Placement)"
                     % (dir1, sign1 * i, data, dir1))
    if j and dir2:
        parts.append("%s.Placement * translationm(0; 0; %d * %s.Espaciado2) * minvert(%s.Placement)"
                     % (dir2, sign2 * j, data, dir2))
    parts.append("%s.Placement" % seed)
    return " * ".join(parts)


def circular_expression(seed, data, axis, i, sign=1):
    return ("%s.Placement * rotationz(%d * %s.Angulo) * minvert(%s.Placement) * %s.Placement"
            % (axis, sign * i, data, axis, seed))


def step_angle(total, count, equal):
    """Ángulo entre copias: con 'Separación igual' el total se reparte (360 / n, como SW)."""
    count = max(1, int(count))
    if equal:
        if abs(total - 360.0) < 1e-9:
            return total / count
        return total / max(1, count - 1)
    return total


def mat_literal(m):
    return "matrix(" + "; ".join("%.12g" % x for x in m.A) + ")"


def mirror_expression(plane, seed, s_literal):
    return ("%s.Placement.Matrix * %s * minvert(%s.Placement.Matrix) * %s.Placement.Matrix * %s"
            % (plane, FMAT, plane, seed, s_literal))


def opposite_name(base, existing):
    """'Soporte-opuesta', y si ya hay otro archivo con ese nombre: 'Soporte-opuesta2'..."""
    name = "%s-opuesta" % base
    n = 2
    while name in existing:
        name = "%s-opuesta%d" % (base, n)
        n += 1
    return name


def next_title(used, kind):
    base = TITLES[kind]
    n = 1
    while "%s%d" % (base, n) in used:
        n += 1
    return "%s%d" % (base, n)


# --- FreeCAD: referencias ------------------------------------------------------


def _ua():
    import UtilsAssembly

    return UtilsAssembly


def reflection(plc):
    """Matriz de espejo respecto del plano XY de plc."""
    f = FreeCAD.Matrix()
    f.scale(1, 1, -1)
    m = plc.toMatrix()
    m = m.multiply(f)
    return m.multiply(plc.inverse().toMatrix())


def own_symmetry(shape):
    """(error, matriz S) del mejor plano de simetría propio de la pieza (por su CDG)."""
    solid = shape.Solids[0] if shape.Solids else shape
    com = solid.CenterOfMass
    best = None
    for n in (FreeCAD.Vector(1, 0, 0), FreeCAD.Vector(0, 1, 0), FreeCAD.Vector(0, 0, 1)):
        try:
            mirrored = shape.mirror(com, n)
            err = abs(shape.common(mirrored).Volume - shape.Volume) / max(shape.Volume, 1e-9)
        except Exception:
            continue
        if best is None or err < best[0]:
            best = (err, n)
    if best is None:
        return 1.0, reflection(FreeCAD.Placement(com, FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1),
                                                                         FreeCAD.Vector(1, 0, 0))))
    rot = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), best[1])
    return best[0], reflection(FreeCAD.Placement(com, rot))


def clean_sub(sub):
    """'Body.;Face14;:Hda2,F.Face14' (nombre topológico de FreeCAD 1.x) -> 'Body.Face14'."""
    try:
        import Part

        path, _mapped, element = Part.splitSubname(sub)
        return path + element
    except Exception:
        return ".".join(p for p in sub.split(".") if not p.startswith(";"))


def pick_from_selection(asm):
    """[(objeto, sub, tipo)] de lo elegido: componente + sub, o un plano/eje del ensamblaje."""
    from swui.fork import mates_sw

    out = []
    try:
        sels = FreeCADGui.Selection.getSelectionEx("", 0)
    except Exception:
        return out
    ua = _ua()
    for sel in sels:
        for sub in list(sel.SubElementNames or []) or [""]:
            leaf_obj = None
            try:
                leaf_obj = sel.Object.getSubObject(sub, 1)
            except Exception:
                pass
            if leaf_obj is not None and leaf_obj.TypeId in ("App::Line", "App::Plane", "Part::DatumLine",
                                                            "Part::DatumPlane") and not sub.rsplit(".", 1)[-1]:
                kind = "datum_line" if "Line" in leaf_obj.TypeId else "datum_plane"
                if leaf_obj.TypeId == "App::Line":
                    kind = "origin_axis"
                out.append((leaf_obj, "", kind))
                continue
            try:
                comp, rel = ua.getComponentReference(asm, sel.Object, sub)
            except Exception:
                comp, rel = None, ""
            if comp is None:
                continue
            shape = None
            try:
                shape = sel.Object.getSubObject(sub)
            except Exception:
                pass
            kind = mates_sw.kind_of(shape) if rel.rsplit(".", 1)[-1] else "part"
            out.append((comp, clean_sub(rel), kind))
    return out


def describe(ref):
    from swui.fork import mates_sw

    obj, _sub, kind = ref
    if kind in ("origin_axis", "datum_line", "datum_plane"):
        return obj.Label
    return mates_sw.describe(kind, obj.Label)


def _circle_edge_of(comp, sub):
    """Para una cara cilíndrica: el nombre (con prefijo) de una de sus aristas circulares."""
    face = comp.getSubObject(sub)
    prefix = sub.rsplit(".", 1)[0] if "." in sub else ""
    # isSame no sirve entre la forma del vínculo y la de getSubObject (copias distintas): por geometría
    circles = [fe.Curve for fe in face.Edges if type(fe.Curve).__name__ == "Circle"]
    for i, e in enumerate(comp.Shape.Edges, 1):
        if type(e.Curve).__name__ != "Circle":
            continue
        if any(abs(e.Curve.Radius - c.Radius) < 1e-7 and (e.Curve.Center - c.Center).Length < 1e-7
               for c in circles):
            return (prefix + "." if prefix else "") + "Edge%d" % i
    return None


def direction_object(asm, ref, name, axis=False):
    """
    Objeto nativo cuyo eje Z es la dirección (o el eje de giro) pedida: un plano o eje de
    referencia ya existente, o uno nuevo apoyado en lo elegido (oculto).
    """
    obj, sub, kind = ref
    if kind in ("datum_line", "datum_plane") or (kind == "datum_plane" and obj.TypeId == "App::Plane"):
        return obj, False
    doc = asm.Document
    if kind == "plane" and not axis:
        d = asm.newObject("Part::DatumPlane", name)
        d.AttachmentSupport = [(obj, sub)]
        d.MapMode = "FlatFace"
    else:
        d = asm.newObject("Part::DatumLine", name)
        if kind == "origin_axis":
            d.AttachmentSupport = [(obj, "")]
            d.MapMode = "ObjectX"
        elif kind == "line":
            d.AttachmentSupport = [(obj, sub)]
            d.MapMode = "TwoPointLine"
        elif kind == "circle":
            d.AttachmentSupport = [(obj, sub)]
            d.MapMode = "AxisOfCurvature"
        elif kind in ("cylinder", "cone"):
            edge = _circle_edge_of(obj, sub)
            if edge is None:
                doc.removeObject(d.Name)
                return None, False
            d.AttachmentSupport = [(obj, edge)]
            d.MapMode = "AxisOfCurvature"
        else:
            doc.removeObject(d.Name)
            return None, False
    d.Visibility = False
    d.recompute()
    return d, True


def _linked_shape(comp):
    target = comp.getLinkedObject(True) if hasattr(comp, "getLinkedObject") else comp
    return target.Shape


# --- FreeCAD: crear -----------------------------------------------------------


def _data(asm, kind, label):
    v = asm.newObject("App::VarSet", "VarSet")
    v.Label = label
    v.addProperty("App::PropertyString", KIND, "SW", "Tipo de operación de LikeSolidWorks UI")
    setattr(v, KIND, kind)
    v.addProperty("App::PropertyLinkListHidden", SEEDS, "SW", "Componentes semilla")
    # nombres, no vínculos: las copias leen este VarSet (un vínculo de vuelta sería un ciclo)
    v.addProperty("App::PropertyStringList", COPIES, "SW", "Copias creadas (nombres)")
    v.setEditorMode(KIND, 1)
    return v


def make_linear(asm, seeds, dir1, count1, spacing1, flip1=False, dir2=None, count2=1, spacing2=10.0,
                flip2=False, label=None, data=None):
    """Matriz lineal: devuelve el VarSet con los datos."""
    v = data or _data(asm, "linear", label or next_title({o.Label for o in asm.Document.Objects}, "linear"))
    for prop, typ in (("Espaciado", "App::PropertyLength"), ("Instancias", "App::PropertyInteger"),
                      ("Invertir", "App::PropertyBool"), ("Espaciado2", "App::PropertyLength"),
                      ("Instancias2", "App::PropertyInteger"), ("Invertir2", "App::PropertyBool")):
        if not hasattr(v, prop):
            v.addProperty(typ, prop, "Matriz")
    for prop in (DIR1, DIR2):
        if not hasattr(v, prop):
            v.addProperty("App::PropertyLinkHidden", prop, "SW")
    v.Espaciado, v.Instancias, v.Invertir = spacing1, int(count1), bool(flip1)
    v.Espaciado2, v.Instancias2, v.Invertir2 = spacing2, int(count2 if dir2 else 1), bool(flip2)
    setattr(v, DIR1, dir1)
    setattr(v, DIR2, dir2)
    _make_arrays(asm, v, seeds, grid_indices(count1, count2 if dir2 else 1),
                 lambda seed, ij: linear_expression(seed, v.Name, dir1.Name, ij[0], -1 if flip1 else 1,
                                                    dir2.Name if dir2 else None, ij[1], -1 if flip2 else 1))
    return v


def make_circular(asm, seeds, axis, count, total, equal=True, flip=False, label=None, data=None):
    v = data or _data(asm, "circular", label or next_title({o.Label for o in asm.Document.Objects}, "circular"))
    for prop, typ in (("Angulo", "App::PropertyAngle"), ("AnguloTotal", "App::PropertyAngle"),
                      ("Instancias", "App::PropertyInteger"), ("SeparacionIgual", "App::PropertyBool"),
                      ("Invertir", "App::PropertyBool")):
        if not hasattr(v, prop):
            v.addProperty(typ, prop, "Matriz")
    if not hasattr(v, DIR1):
        v.addProperty("App::PropertyLinkHidden", DIR1, "SW")
    v.AnguloTotal, v.Instancias, v.SeparacionIgual, v.Invertir = total, int(count), bool(equal), bool(flip)
    v.Angulo = step_angle(total, count, equal)
    setattr(v, DIR1, axis)
    _make_arrays(asm, v, seeds, [(i, 0) for i in range(1, max(1, int(count)))],
                 lambda seed, ij: circular_expression(seed, v.Name, axis.Name, ij[0], -1 if flip else 1))
    return v


def _make_arrays(asm, v, seeds, cells, expression):
    copies = []
    for seed in seeds:
        arr = asm.newObject("App::Link", "Matriz")
        arr.LinkedObject = seed.LinkedObject
        arr.ShowElement = True
        arr.ElementCount = len(cells)
        arr.recompute()
        for el, ij in zip(arr.ElementList, cells):
            el.setExpression("Placement", expression(seed.Name, ij))
        copies.append(arr)
    QtCore.QTimer.singleShot(0, lambda: _label_arrays(asm.Document.Name, v.Name))
    setattr(v, SEEDS, list(seeds))
    setattr(v, COPIES, [c.Name for c in copies])


def copies_of(v):
    doc = v.Document
    return [o for o in (doc.getObject(n) for n in (getattr(v, COPIES, []) or [])) if o is not None]


def _label_arrays(doc_name, data_name):
    """Después del nombre de componente que pone el original: 'MatrizLineal1 Tornillo'."""
    try:
        v = FreeCAD.getDocument(doc_name).getObject(data_name)
        from swui import naming

        for seed, arr in zip(getattr(v, SEEDS), copies_of(v)):
            arr.Label = "%s %s" % (v.Label, naming.strip_instance(seed.Label))
    except Exception:
        pass


def make_mirror(asm, seeds, plane, opposite=(), label=None, data=None, folder=None):
    """Simetría de componentes: copias (misma pieza) o versiones opuestas (archivo nuevo)."""
    v = data or _data(asm, "mirror", label or next_title({o.Label for o in asm.Document.Objects}, "mirror"))
    for prop in (PLANE,):
        if not hasattr(v, prop):
            v.addProperty("App::PropertyLinkHidden", prop, "SW")
    if not hasattr(v, OPPOSITE):
        v.addProperty("App::PropertyStringList", OPPOSITE, "SW")
    setattr(v, PLANE, plane)
    setattr(v, OPPOSITE, [s.Name for s in seeds if s in opposite])
    copies, warnings = [], []
    for seed in seeds:
        if seed in opposite:
            target = opposite_part(seed, folder)
            s_mat = reflection(FreeCAD.Placement(FreeCAD.Vector(), FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1),
                                                                                      FreeCAD.Vector(1, 0, 0))))
        else:
            target = seed.LinkedObject
            err, s_mat = own_symmetry(_linked_shape(seed))
            if err > 1e-6:
                warnings.append(seed.Label)
        _back_to(asm)
        link = asm.newObject("App::Link", "Simetria")
        link.LinkedObject = target
        link.setExpression("Placement", mirror_expression(plane.Name, seed.Name, mat_literal(s_mat)))
        copies.append(link)
    setattr(v, SEEDS, list(seeds))
    setattr(v, COPIES, [c.Name for c in copies])
    return v, warnings


def _back_to(asm):
    """Crear el archivo opuesto lo deja activo: volver al ensamblaje (y a editarlo)."""
    if not FreeCAD.GuiUp:
        return
    try:
        if FreeCAD.ActiveDocument is not asm.Document:
            FreeCADGui.setActiveDocument(asm.Document.Name)
            FreeCAD.setActiveDocument(asm.Document.Name)
        from swui.fork import mates_sw

        if mates_sw.active_assembly() is None:
            FreeCADGui.ActiveDocument.setEdit(asm)
    except Exception:
        pass


def opposite_part(seed, folder=None):
    """Body del archivo '<pieza>-opuesta' (lo crea si no existe): espejo nativo atado a la original."""
    source = seed.LinkedObject
    src_doc = source.Document
    folder = folder or os.path.dirname(src_doc.FileName or "") or os.path.dirname(seed.Document.FileName or "")
    base = src_doc.Label if src_doc is not seed.Document else source.Label
    # ¿ya hay un opuesto de esta pieza abierto o en la carpeta?
    for d in FreeCAD.listDocuments().values():
        for o in d.Objects:
            if getattr(o, OPPOSITE_MARK, None) and getattr(o, "Support", None) and \
                    o.Support[0][0] is source:
                body = next((b for b in d.Objects if b.TypeId == "PartDesign::Body"), None)
                if body is not None:
                    return body
    existing = {os.path.splitext(f)[0] for f in os.listdir(folder)} if os.path.isdir(folder) else set()
    name = opposite_name(base, existing)
    doc = FreeCAD.newDocument(name)
    doc.saveAs(os.path.join(folder, name + ".FCStd"))  # antes del binder: "Owner document not saved"
    binder = doc.addObject("PartDesign::SubShapeBinder", "Original")
    binder.Support = [(source, ("",))]
    binder.addProperty("App::PropertyBool", OPPOSITE_MARK, "SW", "Versión opuesta de LikeSolidWorks UI")
    setattr(binder, OPPOSITE_MARK, True)
    mirror = doc.addObject("Part::Mirroring", "Espejo")
    mirror.Source = binder
    mirror.Base = FreeCAD.Vector(0, 0, 0)
    mirror.Normal = FreeCAD.Vector(1, 0, 0)
    body = doc.addObject("PartDesign::Body", "Body")
    body.BaseFeature = mirror
    binder.Visibility = mirror.Visibility = False
    doc.recompute()
    doc.save()
    return body


def remove_operation(v):
    """Borra copias, ejes/planos propios y el VarSet (para rehacer o eliminar)."""
    doc = v.Document
    for arr in copies_of(v):
        if getattr(arr, "ElementCount", 0):
            arr.ElementCount = 0
        doc.removeObject(arr.Name)
    for prop in (DIR1, DIR2, PLANE):
        d = getattr(v, prop, None)
        if d is not None and getattr(d, "SWUI_Own", False) and doc.getObject(d.Name) is not None:
            doc.removeObject(d.Name)
    doc.removeObject(v.Name)


def mark_own(obj):
    if obj is not None and not hasattr(obj, "SWUI_Own"):
        obj.addProperty("App::PropertyBool", "SWUI_Own", "SW", "Creado por la operación (se borra con ella)")
        obj.SWUI_Own = True
        obj.setEditorMode("SWUI_Own", 2)


def operation_of(obj):
    """El VarSet de la operación a la que pertenece obj (copia, matriz o los propios datos)."""
    if obj is None:
        return None
    if hasattr(obj, KIND):
        return obj
    if obj.TypeId == "App::LinkElement":
        obj = next((p for p in obj.InList if p.TypeId == "App::Link" and obj in (p.ElementList or [])), obj)
    for o in obj.Document.Objects:
        if hasattr(o, KIND) and obj.Name in (getattr(o, COPIES, []) or []):
            return o
    return None


# --- Observador: el motor mueve piezas sin avisar -------------------------------------


class _Observer:
    def slotChangedObject(self, obj, prop):
        if prop != "Placement":
            return
        try:
            if obj.TypeId not in ("App::Link", "Assembly::AssemblyLink") or obj.Document.Restoring:
                return
            for o in obj.InList:
                if o.TypeId in ("App::LinkElement", "App::Link") and any(
                        p == "Placement" or p == ".Placement" for p, _e in o.ExpressionEngine):
                    o.touch()
                elif getattr(o, "MapMode", "Deactivated") != "Deactivated" and o.TypeId.startswith("Part::Datum"):
                    o.touch()
        except Exception:
            pass

    def slotCreatedDocument(self, doc):
        """
        Versión opuesta: reconstruir al abrir si la original cambió (decisión del usuario).
        FreeCAD 1.1 no avisa a Python el fin de la carga: se mira apenas termina (QTimer 0).
        """
        try:
            QtCore.QTimer.singleShot(0, lambda d=doc.Name: _check_opposites(d))
        except Exception:
            pass


def _check_opposites(doc_name):
    try:
        doc = FreeCAD.getDocument(doc_name)
    except Exception:
        return
    for o in doc.Objects:
        if getattr(o, OPPOSITE_MARK, False):
            _refresh_opposite(doc_name, o.Name)


def _refresh_opposite(doc_name, binder_name):
    try:
        doc = FreeCAD.getDocument(doc_name)
        b = doc.getObject(binder_name)
        src = b.Support[0][0]
        a, c = b.Shape, src.Shape
        same = (abs(a.Volume - c.Volume) < 1e-6 and abs(a.Area - c.Area) < 1e-6
                and str(a.BoundBox) == str(c.BoundBox))
        if not same:
            b.touch()
            doc.recompute()
            FreeCAD.Console.PrintMessage("[SWUI] %s: la pieza original cambió, versión opuesta reconstruida.\n"
                                         % doc.Label)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Versión opuesta:\n%s\n" % traceback.format_exc())


# --- Panel ---------------------------------------------------------------------


class PatternPanel:
    """PropertyManager de Matriz lineal / circular y Simetría de componentes."""

    def __init__(self, asm, kind, data=None):
        self.asm, self.kind, self.doc = asm, kind, asm.Document
        self.data = data
        self.editing = data is not None
        self.seeds, self.opposite = [], set()
        self.dir1 = self.dir2 = None  # (obj, sub, tipo) o un objeto existente
        self.active = "seeds" if data is not None else "dir1"  # como SW: primero la dirección
        self.busy = False
        self.problem = ""
        self.old = {}
        if data is not None:
            self._load(data)
        self.doc.openTransaction(LABELS[kind])
        self._build()
        self.timer = QtCore.QTimer()
        self.timer.setSingleShot(True)
        self.timer.setInterval(0)
        self.timer.timeout.connect(self._picked)
        from swui.fork import mates_sw

        self.observer = mates_sw._SelObserver(self)
        try:
            FreeCADGui.Selection.addObserver(self.observer, FreeCADGui.Selection.ResolveMode.NoResolve)
        except Exception:
            FreeCADGui.Selection.addObserver(self.observer)
        FreeCADGui.Selection.clearSelection()
        self._refresh()

    def _load(self, v):
        self.seeds = list(getattr(v, SEEDS, []) or [])
        self.label = v.Label
        if self.kind == "mirror":
            self.dir1 = _existing_ref(getattr(v, PLANE, None))
            self.opposite = {s for s in self.seeds if s.Name in (getattr(v, OPPOSITE, []) or [])}
        else:
            self.dir1 = _existing_ref(getattr(v, DIR1, None))
            self.dir2 = _existing_ref(getattr(v, DIR2, None))

    # --- interfaz

    def _build(self):
        from swui import paths
        from swui.compat import QtGui
        from swui.fork import dress_up_panel as dp

        self.form = QtWidgets.QWidget()
        self.form.setWindowTitle(self.data.Label if self.editing else LABELS[self.kind])
        icon = paths.icon(ICONS[self.kind])
        if icon:
            self.form.setWindowIcon(QtGui.QIcon(icon))
        box = QtWidgets.QVBoxLayout(self.form)
        v = self.data
        if self.kind == "mirror":
            g = QtWidgets.QGroupBox("Plano de simetría")
            gl = QtWidgets.QVBoxLayout(g)
            self.dir1_box = dp.RefBox(lambda _b: self._activate("dir1"))
            gl.addWidget(self.dir1_box)
            box.addWidget(g)
        else:
            g = QtWidgets.QGroupBox("Dirección 1" if self.kind == "linear" else "Parámetros")
            gl = QtWidgets.QFormLayout(g)
            self.dir1_box = dp.RefBox(lambda _b: self._activate("dir1"))
            gl.addRow("Eje:" if self.kind == "circular" else "Dirección:", self.dir1_box)
            self.flip1 = QtWidgets.QCheckBox("Invertir dirección")
            self.flip1.setChecked(bool(getattr(v, "Invertir", False)))
            gl.addRow(self.flip1)
            if self.kind == "linear":
                self.spacing1 = _spin(" mm", 0.01, 1e6, float(getattr(v, "Espaciado", 20)) if v else 20.0)
                gl.addRow("Espaciado:", self.spacing1)
            else:
                self.total = _spin(" °", 0.01, 360, float(getattr(v, "AnguloTotal", 360)) if v else 360.0)
                gl.addRow("Ángulo:", self.total)
                self.equal = QtWidgets.QCheckBox("Separación igual")
                self.equal.setChecked(bool(getattr(v, "SeparacionIgual", True)) if v else True)
                gl.addRow(self.equal)
            self.count1 = _count(int(getattr(v, "Instancias", 3)) if v else 3)
            gl.addRow("Instancias:", self.count1)
            box.addWidget(g)
            if self.kind == "linear":
                self.dir2_group = QtWidgets.QGroupBox("Dirección 2")
                self.dir2_group.setCheckable(True)
                self.dir2_group.setChecked(self.dir2 is not None)
                g2 = QtWidgets.QFormLayout(self.dir2_group)
                self.dir2_box = dp.RefBox(lambda _b: self._activate("dir2"))
                g2.addRow("Dirección:", self.dir2_box)
                self.flip2 = QtWidgets.QCheckBox("Invertir dirección")
                self.flip2.setChecked(bool(getattr(v, "Invertir2", False)))
                g2.addRow(self.flip2)
                self.spacing2 = _spin(" mm", 0.01, 1e6, float(getattr(v, "Espaciado2", 20)) if v else 20.0)
                g2.addRow("Espaciado:", self.spacing2)
                self.count2 = _count(int(getattr(v, "Instancias2", 2)) if v and self.dir2 else 2)
                g2.addRow("Instancias:", self.count2)
                self.dir2_group.toggled.connect(lambda *_a: self._changed())
                box.addWidget(self.dir2_group)
        seeds = QtWidgets.QGroupBox("Componentes para la simetría" if self.kind == "mirror"
                                    else "Componentes a repetir")
        sl = QtWidgets.QVBoxLayout(seeds)
        self.list = dp.pick_list(self.remove_current, self.clear_seeds, 60)
        self.list.itemClicked.connect(lambda *_a: self._activate("seeds"))
        sl.addWidget(self.list)
        if self.kind == "mirror":
            self.opp = QtWidgets.QCheckBox("Versión opuesta (pieza nueva espejada)")
            self.opp.setToolTip("Para piezas que no son simétricas: crea '<pieza>-opuesta.FCStd' atada a la original")
            self.opp.toggled.connect(self._toggle_opposite)
            self.list.currentRowChanged.connect(lambda *_a: self._show_opposite())
            sl.addWidget(self.opp)
        box.addWidget(seeds)
        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        box.addWidget(self.message)
        box.addStretch(1)
        for w in self._value_widgets():
            sig = w.toggled if isinstance(w, QtWidgets.QCheckBox) else w.valueChanged
            sig.connect(lambda *_a: self._changed())

    def _value_widgets(self):
        names = ("flip1", "spacing1", "total", "equal", "count1", "flip2", "spacing2", "count2")
        return [getattr(self, n) for n in names if hasattr(self, n)]

    def _activate(self, which):
        self.active = which
        self._refresh()

    def _refresh(self):
        ok_style = "background: #cfe3f6;"
        for which, box in (("dir1", getattr(self, "dir1_box", None)), ("dir2", getattr(self, "dir2_box", None))):
            if box is None:
                continue
            ref = getattr(self, which)
            box.setText(describe(ref) if ref else "")
            box.setStyleSheet(ok_style if self.active == which else "")
        self.list.setStyleSheet(ok_style if self.active == "seeds" else "")
        row = self.list.currentRow()  # rearmar la lista no debe perder la fila elegida (Versión opuesta)
        self.list.blockSignals(True)
        self.list.clear()
        for s in self.seeds:
            extra = "  (opuesta)" if s in self.opposite else ""
            self.list.addItem(s.Label + extra)
        if self.seeds:
            self.list.setCurrentRow(row if 0 <= row < len(self.seeds) else len(self.seeds) - 1)
        self.list.blockSignals(False)
        if self.kind == "mirror":
            self._show_opposite()
        if self.problem:
            text = self.problem
        elif not self.dir1:
            text = {"linear": "Elegí una arista, cara o eje para la dirección.",
                    "circular": "Elegí el eje: una arista circular, una cara cilíndrica o un eje.",
                    "mirror": "Elegí el plano de simetría: una cara plana o un plano."}[self.kind]
        elif not self.seeds:
            text = "Elegí los componentes en la vista o en el árbol."
        else:
            text = ""
        self.message.setText(text)
        self.message.setVisible(bool(text))

    def _show_opposite(self):
        row = self.list.currentRow()
        self.opp.blockSignals(True)
        self.opp.setEnabled(0 <= row < len(self.seeds))
        self.opp.setChecked(0 <= row < len(self.seeds) and self.seeds[row] in self.opposite)
        self.opp.blockSignals(False)

    def _toggle_opposite(self, on):
        row = self.list.currentRow()
        if not 0 <= row < len(self.seeds):
            return
        seed = self.seeds[row]
        (self.opposite.add if on else self.opposite.discard)(seed)
        self._changed()
        self.list.setCurrentRow(row)

    # --- selección

    def schedule(self):
        if not self.busy:
            self.timer.start()

    def _picked(self):
        if self.busy:
            return
        refs = pick_from_selection(self.asm)
        if not refs:
            return
        self.busy = True
        try:
            FreeCADGui.Selection.clearSelection()
        finally:
            self.busy = False
        own = set(self._own_objects())
        for ref in refs:
            obj, _sub, kind = ref
            if obj in own:
                continue
            if self.kind == "mirror" and kind not in ("part", "plane", "datum_plane"):
                # el plano de simetría es una cara plana o un plano (SW no toma vértices ni aristas)
                self.problem = "Para el plano de simetría elegí una cara plana o un plano."
                self._refresh()
                return
            if self.active in ("dir1", "dir2") and kind != "part":
                setattr(self, self.active, ref)
                self.active = "seeds"
            elif obj.TypeId in ("App::Link", "Assembly::AssemblyLink") and not getattr(obj, "ElementCount", 0):
                if obj in self.seeds:
                    self.seeds.remove(obj)
                    self.opposite.discard(obj)
                else:
                    self.seeds.append(obj)
            elif not self.dir1 and kind != "part":
                self.dir1 = ref
        self._changed()

    def _own_objects(self):
        if self.data is None:
            return []
        return copies_of(self.data)

    def remove_current(self):
        row = self.list.currentRow()
        if 0 <= row < len(self.seeds):
            self.opposite.discard(self.seeds.pop(row))
            self._changed()

    def clear_seeds(self):
        self.seeds, self.opposite = [], set()
        self._changed()

    # --- vista previa: rehacer todo dentro de la transacción

    def _changed(self, *_a):
        if self.busy:
            return
        self.busy = True
        self.problem = ""
        try:
            label = self.data.Label if self.data is not None else None
            if self.data is not None:
                self._remove_keeping_refs()
            self.data = None
            if self.dir1 and self.seeds and (self.kind == "mirror" or self.kind != "linear" or not self._dir2_on()
                                             or self.dir2):
                self.data = self._create(label)
            self.doc.recompute()
        except Exception:
            # el panel ya lo dice en castellano: el detalle va al registro, no a una ventana de error
            FreeCAD.Console.PrintLog("[SWUI fork] %s:\n%s\n" % (LABELS[self.kind], traceback.format_exc()))
            self.problem = "FreeCAD no pudo armar la operación con esas referencias."
        finally:
            self.busy = False
        self._refresh()

    def _dir2_on(self):
        return self.kind == "linear" and self.dir2_group.isChecked()

    def _remove_keeping_refs(self):
        """Borra la operación; si un eje/plano propio se va con ella, se vuelve a crear desde su apoyo."""
        for which in ("dir1", "dir2"):
            ref = getattr(self, which)
            if ref and isinstance(ref, tuple) and ref[2] == "own":
                setattr(self, which, _support_ref(ref[0]))
        remove_operation(self.data)

    def _direction(self, ref, name, axis):
        obj, sub, kind = ref
        if kind == "existing":
            return obj
        d, own = direction_object(self.asm, ref, name, axis)
        if d is None:
            raise ValueError("referencia no apta")
        if own:
            mark_own(d)
        return d

    def _create(self, label):
        kind = self.kind
        title = label or next_title({o.Label for o in self.doc.Objects}, kind)
        if kind == "mirror":
            plane = self._direction(self.dir1, "PlanoSimetria", False)
            # el archivo opuesto se crea recién al Aceptar; la vista previa usa la misma pieza
            v, warn = make_mirror(self.asm, self.seeds, plane, (), title)
            if [s for s in warn if s not in [o.Label for o in self.opposite]]:
                self.problem = ("No es simétrica: %s. Marcá 'Versión opuesta' para que quede espejada de verdad."
                                % ", ".join(warn))
            return v
        if kind == "linear":
            d1 = self._direction(self.dir1, "DireccionMatriz", False)
            d2 = self._direction(self.dir2, "DireccionMatriz2", False) if self._dir2_on() and self.dir2 else None
            return make_linear(self.asm, self.seeds, d1, self.count1.value(), self.spacing1.value(),
                               self.flip1.isChecked(), d2, self.count2.value(), self.spacing2.value(),
                               self.flip2.isChecked(), title)
        axis = self._direction(self.dir1, "EjeMatriz", True)
        return make_circular(self.asm, self.seeds, axis, self.count1.value(), self.total.value(),
                             self.equal.isChecked(), self.flip1.isChecked(), title)

    # --- diálogo

    def getStandardButtons(self):
        return QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel

    def accept(self):
        if self.data is None:
            self.message.setText("Falta elegir la dirección o los componentes.")
            self.message.setVisible(True)
            return False
        self.busy = True
        try:
            if self.kind == "mirror" and self.opposite:
                label, plane = self.data.Label, getattr(self.data, PLANE)
                for c in copies_of(self.data):
                    self.doc.removeObject(c.Name)
                self.doc.removeObject(self.data.Name)
                self.data, _w = make_mirror(self.asm, self.seeds, plane, self.opposite, label)
            self.doc.recompute()
            self.doc.commitTransaction()
        except Exception:
            FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (LABELS[self.kind], traceback.format_exc()))
            self.doc.abortTransaction()
        self._close()
        return True

    def reject(self):
        self.busy = True
        if self.doc.HasPendingTransaction:
            self.doc.abortTransaction()
        self._close()
        return True

    def _close(self):
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        FreeCADGui.Control.closeDialog()
        FreeCADGui.Selection.clearSelection()
        try:
            self.asm.recompute(True)
        except Exception:
            pass


def _existing_ref(obj):
    """Un eje/plano ya guardado en la operación: propio (se rehace desde su apoyo) o ajeno."""
    if obj is None:
        return None
    if getattr(obj, "SWUI_Own", False):
        return (obj, "", "own")
    return (obj, "", "existing")


def _support_ref(datum):
    """(objeto, sub, tipo) de lo que apoya a un eje/plano propio, para rehacerlo."""
    from swui.fork import mates_sw

    try:
        obj, subs = datum.AttachmentSupport[0]
        sub = subs[0] if isinstance(subs, (list, tuple)) else subs
    except Exception:
        return None
    if obj.TypeId == "App::Line":
        return (obj, "", "origin_axis")
    try:
        shape = obj.getSubObject(sub)
        kind = mates_sw.kind_of(shape)
    except Exception:
        kind = "line"
    if datum.MapMode == "AxisOfCurvature":
        kind = "circle"
    return (obj, sub, kind)


def _spin(suffix, low, high, value):
    s = QtWidgets.QDoubleSpinBox()
    s.setDecimals(2)
    s.setRange(low, high)
    s.setSuffix(suffix)
    s.setValue(value)
    s.setKeyboardTracking(False)
    return s


def _count(value):
    s = QtWidgets.QSpinBox()
    s.setRange(1, 1000)
    s.setValue(value)
    s.setKeyboardTracking(False)
    return s


_panel = None


def start(kind, data=None):
    global _panel
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
    try:
        _panel = PatternPanel(asm, kind, data)
        FreeCADGui.Control.showDialog(_panel)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] %s:\n%s\n" % (LABELS[kind], traceback.format_exc()))
        _panel = None
    return _panel


def open_panel(v):
    return start(getattr(v, KIND), v)


# --- Comandos y cinta ---------------------------------------------------------------


class _Command:
    def __init__(self, kind):
        self.kind = kind

    def GetResources(self):
        from swui import paths

        tips = {"linear": "Repite componentes a lo largo de una o dos direcciones (como SW)",
                "circular": "Repite componentes alrededor de un eje (como SW)",
                "mirror": "Copia componentes simétricos respecto de un plano, o crea la versión opuesta"}
        return {"MenuText": LABELS[self.kind], "ToolTip": tips[self.kind],
                "Pixmap": paths.icon(ICONS[self.kind]) or ""}

    def IsActive(self):
        from swui.fork import mates_sw

        doc = FreeCAD.ActiveDocument
        return doc is not None and bool(mates_sw._assemblies(doc))

    def Activated(self):
        start(self.kind)


FLYOUT = [
    ("SWUI_ComponentLinearPattern", "Matriz de compo-\nnente lineal", {"svg": "sketch/f_pattern_linear"}),
    ("SWUI_ComponentCircularPattern", "Matriz de compo-\nnente circular", {"svg": "sketch/f_pattern_polar"}),
    ("SWUI_MirrorComponents", "Simetría de\ncomponentes", {"svg": "sketch/f_mirror"}),
]


def install_ribbon():
    from swui import ribbon_layout

    groups = ribbon_layout.BAUGRUPPE[1]
    for group in groups:
        if any(isinstance(e, dict) and e.get("flyout") == FLYOUT for e in group):
            return
    for group in groups:
        for i, e in enumerate(group):
            if isinstance(e, tuple) and e[0] == "Assembly_InsertLink":
                group.insert(i + 1, {"flyout": list(FLYOUT)})
                return
    groups[0].append({"flyout": list(FLYOUT)})


def install():
    global _installed
    if _installed:
        return
    for cmd, kind in ((LINEAR, "linear"), (CIRCULAR, "circular"), (MIRROR, "mirror")):
        try:
            FreeCADGui.addCommand(cmd, _Command(kind))
        except Exception:
            pass  # ya registrado
    install_ribbon()
    from swui.fork import dress_up_panel as dp

    if (operation_of, open_panel) not in dp.OPENERS:
        dp.OPENERS.append((operation_of, open_panel))
    FreeCAD.addDocumentObserver(_Observer())
    _installed = True
