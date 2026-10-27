# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Piezas multicuerpo como en SOLIDWORKS (etapa B): "Fusionar resultado" y "Alcance de la
operación" en Extruir / Revolución (saliente y corte).

Decisión del usuario (2026-10-26, docs/ESTADO.md "Multicuerpo"): cada sólido de SW es un
Cuerpo de FreeCAD, y el addon es un ASISTENTE: arma objetos nativos al aceptar la operación y
después FreeCAD recalcula solo (el archivo abre y se edita bien sin el addon).

- Fusionar resultado apagado (extruir/revolución de saliente): al aceptar, la operación pasa a
  un Cuerpo nuevo ("Cuerpo2"...). El croquis queda donde se dibujó (con sus referencias); el
  Cuerpo nuevo usa una copia vinculada del croquis (PartDesign::SubShapeBinder). NO se apoya el
  croquis directo en una cara de otro Cuerpo: FreeCAD se traería ese sólido adentro sin avisar.
  Revolución: el eje se lleva al Cuerpo nuevo (eje del origen -> el suyo; eje del croquis ->
  una recta de referencia apoyada en el croquis). Prendido otra vez al editar: vuelve.
- Alcance de la operación (cortes): en cada sólido elegido se crea una copia del corte (copia
  vinculada del croquis + ecuaciones de FreeCAD atadas a las cotas del original, también el
  tipo), marcada con la propiedad SWUI_ScopeOf (nombre estable). Como SW, de fábrica: "Todos
  los sólidos" con "Selección automática" = los sólidos que el corte atraviesa. "Hasta la cara":
  cada copia apunta a una copia vinculada de esa cara. El modo elegido queda en el original
  (SWUI_ScopeMode, nombre estable): con selección automática, si después el corte pasa a
  atravesar otros sólidos (p. ej. por una ecuación), el addon AVISA y ofrece actualizar; no
  cambia nada solo (no es un motor: el archivo sigue siendo nativo).
- Borrar el corte original borra sus copias (en SW es una sola operación): con Supr se suman a
  lo que se borra (un solo paso de deshacer); por otro camino, se borran enseguida después.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

ADDITIVE = ("PartDesign::Pad", "PartDesign::Revolution")
SUBTRACTIVE = ("PartDesign::Pocket", "PartDesign::Groove")
SCOPE_PROP = "SWUI_ScopeOf"  # en las copias de un corte: el corte original (nombre estable)
SCOPE_GROUP = "Alcance"
SCOPE_MODE_PROP = "SWUI_ScopeMode"  # en el corte original: "auto" / "all" / "selected" (nombre estable)
BODY_LABEL = "Cuerpo"
TOUCH_VOLUME = 1e-6  # mm³: el corte "atraviesa" un sólido si le saca más que esto
AUTO_MS = 700  # cada cuánto se recalcula la selección automática con el diálogo abierto
SECTION_NAME = "SWUI_MultibodySection"

# Propiedades que la copia de un corte toma del original con una ecuación de FreeCAD
COPY_PROPS = {
    # Pocket: "Midplane" está obsoleto en 1.1 (lo reemplaza SideType): no se copia
    "PartDesign::Pocket": ("Type", "Length", "Length2", "Offset", "Offset2", "TaperAngle", "TaperAngle2",
                           "Reversed", "Type2", "SideType"),
    "PartDesign::Groove": ("Type", "Angle", "Angle2", "Midplane", "Reversed"),
    "PartDesign::Hole": ("Diameter", "Depth", "HoleCutDiameter", "HoleCutDepth", "HoleCutCountersinkAngle",
                         "DrillPointAngle", "TaperedAngle", "ThreadDepth", "CustomThreadClearance", "Reversed",
                         "Threaded", "ModelThread", "Tapered", "DrillForDepth", "UseCustomThreadClearance",
                         "HoleCutCustomValues"),
}
# Opciones de lista que NO se pueden atar con ecuación (la lista depende de otra: el tamaño de rosca
# según el tipo; con ecuación la copia mostró "M7" en vez de "M8"): se copian por valor, en este
# orden, al crear la copia y cada vez que se acepta el original (sync_copies).
ENUM_PROPS = {
    "PartDesign::Hole": ("ThreadType", "ThreadSize", "ThreadClass", "ThreadFit", "ThreadDirection",
                         "HoleCutType", "DepthType", "DrillPoint", "ThreadDepthType"),
}
SCOPED = SUBTRACTIVE + ("PartDesign::Hole",)  # lo que admite "Alcance de la operación"
NOT_COPYABLE_TYPES = ("UpToShape",)  # "Hasta el sólido": no se lleva a otros sólidos
# (UpToFace sí: cada copia apunta a una copia vinculada de la cara)
SKETCH_AXES = {"V_Axis": "ObjectY", "H_Axis": "ObjectX", "N_Axis": "ObjectZ"}


# --- Cuentas sin FreeCAD (probables en el test) -------------------------------


def next_body_label(used):
    """'Cuerpo2', 'Cuerpo3'... el primero libre (FreeCAD no deja repetir nombres)."""
    n = 2
    while "%s%d" % (BODY_LABEL, n) in used:
        n += 1
    return "%s%d" % (BODY_LABEL, n)


def copy_label(original_label, body_label):
    return "%s (%s)" % (original_label, body_label)


def scope_bodies(mode, auto, own, all_bodies, touched, chosen):
    """
    Sólidos donde va el corte, como SW. mode: "all" / "selected"; auto: "Selección automática".
    own (el Cuerpo del corte) va siempre. Devuelve la lista en el orden de all_bodies.
    """
    if mode == "all":
        wanted = set(touched) if auto else set(all_bodies)
    else:
        wanted = set(chosen)
    wanted.add(own)
    return [b for b in all_bodies if b in wanted]


# --- Cuerpos y operaciones --------------------------------------------------------


def body_of(obj):
    try:
        body = getattr(obj, "_Body", None)
        if body is not None:
            return body
        parent = obj.getParentGeoFeatureGroup()
        return parent if parent is not None and parent.TypeId == "PartDesign::Body" else None
    except Exception:
        return None


def profile_object(feature):
    try:
        prof = feature.Profile
        return prof[0] if isinstance(prof, tuple) else prof
    except Exception:
        return None


def source_sketch(feature):
    """El croquis de verdad (aunque el perfil sea una copia vinculada)."""
    prof = profile_object(feature)
    if prof is not None and prof.TypeId == "PartDesign::SubShapeBinder":
        try:
            return prof.Support[0][0]
        except Exception:
            return prof
    return prof


def is_separated(feature):
    """¿Es una operación con "Fusionar resultado" apagado (su croquis vive en otro Cuerpo)?"""
    prof = profile_object(feature)
    if prof is None or prof.TypeId != "PartDesign::SubShapeBinder":
        return False
    sketch = source_sketch(feature)
    return sketch is not None and body_of(sketch) is not None and body_of(sketch) is not body_of(feature)


def solid_bodies(doc):
    """Los sólidos de la pieza (Cuerpos con algo), sin los consumidos (material.part_objects)."""
    from swui.fork import material

    return [o for o in material.part_objects(doc) if o.TypeId == "PartDesign::Body"]


def has_solid_before(feature):
    base = getattr(feature, "BaseFeature", None)
    try:
        return base is not None and not base.Shape.isNull() and bool(base.Shape.Solids)
    except Exception:
        return False


def copies_of(feature):
    doc = feature.Document
    return [o for o in doc.Objects if getattr(o, SCOPE_PROP, None) is feature]


def original_of(copy):
    return getattr(copy, SCOPE_PROP, None)


def _keep_label(obj, label):
    """
    El original (swui/naming.py) renombra a lo SW toda operación nueva un instante después
    (QTimer 0). Lo que arma el asistente tiene nombre propio: se vuelve a poner después.
    """
    obj.Label = label
    try:
        doc_name, name = obj.Document.Name, obj.Name

        def again():
            doc = FreeCAD.listDocuments().get(doc_name)
            o = doc.getObject(name) if doc else None
            if o is not None and o.Label != label:
                o.Label = label

        QtCore.QTimer.singleShot(0, again)
    except Exception:
        pass


def _binder(body, sketch, label, sub=""):
    """
    Copia vinculada (oculta) dentro de otro Cuerpo: del croquis entero (sub "") o de una cara
    (sub "Face3"). Si ya hay una igual en ese Cuerpo, se reusa.
    """
    for obj in body.Group:
        if obj.TypeId == "PartDesign::SubShapeBinder":
            try:
                support = obj.Support[0] if obj.Support else None
                if support is not None and support[0] is sketch and tuple(support[1] or ("",)) == (sub,):
                    return obj
            except Exception:
                pass
    binder = body.newObject("PartDesign::SubShapeBinder", "Vinculo")
    _keep_label(binder, label)
    binder.Support = [(sketch, (sub,))]
    try:
        binder.Visibility = False
    except Exception:
        pass
    return binder


def _axis_in(body, axis, sketch):
    """
    Eje de una revolución llevado a otro Cuerpo: ejes del origen -> los del Cuerpo; ejes del
    croquis -> recta de referencia apoyada en el croquis. None si no se puede.
    """
    try:
        obj, subs = axis
    except Exception:
        return None
    sub = subs[0] if subs else ""
    if obj.TypeId == "App::Line":
        role = getattr(obj, "Role", "")
        for feat in body.Origin.OriginFeatures:
            if getattr(feat, "Role", None) == role:
                return (feat, [""])
        return None
    if obj is sketch and sub in SKETCH_AXES:
        line = body.newObject("PartDesign::Line", "EjeVinculado")
        _keep_label(line, "Eje de %s" % sketch.Label)
        line.AttachmentSupport = [(sketch, "")]
        line.MapMode = SKETCH_AXES[sub]
        try:
            line.Visibility = False
        except Exception:
            pass
        return (line, [""])
    return None


def _axis_back(axis, owner, sketch):
    """Al volver a fusionar: el eje original en el Cuerpo del croquis."""
    obj, _subs = axis
    if obj.TypeId == "App::Line":
        for feat in owner.Origin.OriginFeatures:
            if getattr(feat, "Role", None) == getattr(obj, "Role", ""):
                return (feat, [""])
    if obj.TypeId == "PartDesign::Line":
        inverse = {v: k for k, v in SKETCH_AXES.items()}
        return (sketch, [inverse.get(obj.MapMode, "V_Axis")])
    return None


def _direction_to(feature, old, new):
    """
    El diálogo nativo deja la dirección de la extrusión apuntando al croquis ("N_Axis", su
    normal). En otro Cuerpo ese vínculo queda afuera y la operación da error: la normal del
    croquis la da igual el perfil, así que se borra; otra referencia del croquis pasa al nuevo.
    """
    try:
        ref = feature.ReferenceAxis
    except Exception:
        return
    if not ref or ref[0] is not old:
        return
    subs = [s for s in (ref[1] or []) if s not in ("N_Axis", "")]
    feature.ReferenceAxis = (new, subs) if subs else None


def _set_tip(body, feature):
    """
    Punta del Cuerpo + visibilidad como la deja FreeCAD: se ve la punta y se esconde la anterior.
    (FreeCAD esconde la punta vieja al crear una operación; si después la operación se va del
    Cuerpo, la punta vuelve a la anterior pero oculta: la placa "desaparecía". Error reportado
    por el usuario, 2026-10-26.)
    """
    old = body.Tip
    body.Tip = feature
    try:
        if old is not None and old is not feature and old in body.Group:
            old.Visibility = False  # la punta vieja sigue en este Cuerpo: oculta, como FreeCAD
        feature.Visibility = True
    except Exception:
        pass


def separate(feature):
    """
    "Fusionar resultado" apagado: pasa la operación a un Cuerpo nuevo. Devuelve el Cuerpo, o
    lanza ValueError con el motivo (la operación queda como estaba).
    """
    doc = feature.Document
    owner = body_of(feature)
    sketch = profile_object(feature)
    if owner is None or sketch is None or is_separated(feature):
        return body_of(feature)
    new = doc.addObject("PartDesign::Body", "Body")
    _keep_label(new, next_body_label(set(o.Label for o in doc.Objects)))
    new.Placement = owner.Placement
    axis = None
    if feature.TypeId == "PartDesign::Revolution":
        axis = _axis_in(new, feature.ReferenceAxis, sketch)
        if axis is None:
            doc.removeObject(new.Name)
            raise ValueError("el eje de la revolución no se puede llevar a otro sólido (usá un eje del "
                             "origen o del croquis)")
    previous = feature.BaseFeature
    was_tip = owner.Tip is feature
    owner.removeObject(feature)
    if was_tip and previous is not None:
        _set_tip(owner, previous)
    binder = _binder(new, sketch, "%s (vínculo)" % sketch.Label)
    new.addObject(feature)
    feature.Profile = binder
    if axis is not None:
        feature.ReferenceAxis = axis
    elif feature.TypeId == "PartDesign::Pad":
        _direction_to(feature, sketch, binder)
    _set_tip(new, feature)
    try:
        sketch.Visibility = False
    except Exception:
        pass
    return new


def rejoin(feature):
    """
    "Fusionar resultado" prendido otra vez: la operación vuelve al Cuerpo de su croquis (al
    final). Solo si su Cuerpo no tiene otras operaciones; si no, ValueError.
    """
    doc = feature.Document
    new = body_of(feature)
    sketch = source_sketch(feature)
    owner = body_of(sketch)
    others = [o for o in new.Group if o is not feature and o.isDerivedFrom("PartDesign::Feature")
              and o.TypeId not in ("PartDesign::SubShapeBinder", "PartDesign::Line", "PartDesign::Plane",
                                   "PartDesign::Point")]
    if others:
        raise ValueError("ese sólido ya tiene otras operaciones (%s): para unirlo usá Combinar"
                         % ", ".join(o.Label for o in others))
    helpers = [o for o in new.Group if o is not feature and o not in others
               and o.TypeId in ("PartDesign::SubShapeBinder", "PartDesign::Line")]
    axis = _axis_back(feature.ReferenceAxis, owner, sketch) if feature.TypeId == "PartDesign::Revolution" else None
    new.removeObject(feature)
    owner.addObject(feature)
    feature.Profile = sketch
    if axis is not None:
        feature.ReferenceAxis = axis
    _set_tip(owner, feature)
    for helper in helpers:
        doc.removeObject(helper.Name)
    if not [o for o in new.Group if o.TypeId != "App::Origin"]:
        origin = new.Origin
        doc.removeObject(new.Name)
        try:
            for feat in list(origin.OriginFeatures):
                doc.removeObject(feat.Name)
            doc.removeObject(origin.Name)
        except Exception:
            pass
    return owner


def touched_bodies(feature):
    """Sólidos que el corte atraviesa (para "Selección automática"), en su estado sin este corte."""
    doc = feature.Document
    owner = body_of(feature)
    try:
        tool = feature.AddSubShape.copy()
        if owner is not None:
            tool.transformShape(owner.Placement.toMatrix())
    except Exception:
        return [owner] if owner else []
    if tool.isNull():
        return [owner] if owner else []
    copies = {body_of(c): c for c in copies_of(feature)}
    out = []
    for body in solid_bodies(doc):
        if body is owner:
            out.append(body)
            continue
        try:
            before = copies[body].BaseFeature.Shape if body in copies else body.Shape
            if before.isNull():
                continue
            if tool.common(before).Volume > TOUCH_VOLUME:
                out.append(body)
        except Exception:
            continue
    return out


def apply_scope(feature, bodies):
    """
    Deja el corte en exactamente esos sólidos (además del suyo): crea las copias que faltan y
    borra las que sobran. Devuelve (creadas, borradas, problemas).
    """
    doc = feature.Document
    owner = body_of(feature)
    sketch = source_sketch(feature)
    wanted = [b for b in bodies if b is not owner]
    existing = {body_of(c): c for c in copies_of(feature)}
    created, removed, problems = [], [], []
    for body, copy in list(existing.items()):
        if body not in wanted:
            _remove_copy(copy)
            removed.append(body)
    if wanted and getattr(feature, "Type", "") in NOT_COPYABLE_TYPES:
        problems.append("un corte «Hasta la cara» no se puede llevar a otro sólido: queda solo en %s"
                        % owner.Label)
        return created, removed, problems
    for body in wanted:
        if body in existing:
            continue
        try:
            created.append(_make_copy(feature, body, sketch))
        except ValueError as exc:
            problems.append("%s: %s" % (body.Label, exc))
    return created, removed, problems


def _make_copy(feature, body, sketch):
    copy_axis = None
    if feature.TypeId == "PartDesign::Groove":
        copy_axis = _axis_in(body, feature.ReferenceAxis, sketch)
        if copy_axis is None:
            raise ValueError("el eje no se puede llevar a este sólido")
    binder = _binder(body, sketch, "%s (vínculo)" % sketch.Label)
    face = _face_for(feature, body)
    copy = body.newObject(feature.TypeId, feature.Name + "_copia")
    _keep_label(copy, copy_label(feature.Label, body.Label))
    copy.Profile = binder
    if face is not None:
        copy.UpToFace = face
    if copy_axis is not None:
        copy.ReferenceAxis = copy_axis
    _copy_enums(feature, copy)
    for prop in COPY_PROPS.get(feature.TypeId, ()):
        if prop in feature.PropertiesList and prop in copy.PropertiesList:
            try:
                setattr(copy, prop, getattr(feature, prop))
                copy.setExpression(prop, "%s.%s" % (feature.Name, prop))
            except Exception:
                pass
    # LinkGlobal: el original vive en otro Cuerpo (un PropertyLink común da aviso de "fuera de alcance")
    copy.addProperty("App::PropertyLinkGlobal", SCOPE_PROP, SCOPE_GROUP,
                     "Corte original (LikeSolidWorks UI): esta es su copia en otro sólido")
    setattr(copy, SCOPE_PROP, feature)
    try:
        copy.setEditorMode(SCOPE_PROP, 1)
    except Exception:
        pass
    return copy


def _face_for(feature, body):
    """"Hasta la cara": la cara del original como copia vinculada dentro del otro sólido, o None."""
    try:
        if getattr(feature, "Type", "") != "UpToFace" or not feature.UpToFace:
            return None
        obj, subs = feature.UpToFace
        sub = subs[0] if subs else ""
    except Exception:
        return None
    if obj is None or not sub:
        return None
    binder = _binder(body, obj, "Cara de %s (vínculo)" % obj.Label, sub)
    return (binder, ["Face1"])


def _copy_enums(feature, copy):
    """Opciones de lista por valor y en orden (cada una arma la lista de la siguiente)."""
    for prop in ENUM_PROPS.get(feature.TypeId, ()):
        if prop in feature.PropertiesList and prop in copy.PropertiesList:
            try:
                if getattr(copy, prop) != getattr(feature, prop):
                    setattr(copy, prop, getattr(feature, prop))
            except Exception:
                pass


def sync_copies(feature):
    """
    Al aceptar una edición del original: lo que no va por ecuación ("Hasta la cara", opciones de
    lista del taladro, nombre) al día.
    """
    for copy in copies_of(feature):
        try:
            _copy_enums(feature, copy)
            face = _face_for(feature, body_of(copy))
            if face is not None and (not copy.UpToFace or copy.UpToFace[0] is not face[0]):
                copy.UpToFace = face
            want = copy_label(feature.Label, body_of(copy).Label)  # si se renombró el original
            if copy.Label != want:
                copy.Label = want
        except Exception:
            pass


def scope_mode(feature):
    return getattr(feature, SCOPE_MODE_PROP, "") or ("selected" if copies_of(feature) else "auto")


def set_scope_mode(feature, mode):
    if SCOPE_MODE_PROP not in feature.PropertiesList:
        feature.addProperty("App::PropertyString", SCOPE_MODE_PROP, SCOPE_GROUP,
                            "Alcance de la operación (LikeSolidWorks UI): auto / all / selected")
        try:
            feature.setEditorMode(SCOPE_MODE_PROP, 2)  # oculta
        except Exception:
            pass
    if getattr(feature, SCOPE_MODE_PROP) != mode:
        setattr(feature, SCOPE_MODE_PROP, mode)


def _remove_copy(copy):
    doc = copy.Document
    body = body_of(copy)
    binder = profile_object(copy)
    helpers = [binder]
    try:
        if copy.UpToFace:
            helpers.append(copy.UpToFace[0])
    except Exception:
        pass
    if copy.TypeId == "PartDesign::Groove":
        try:
            helpers.append(copy.ReferenceAxis[0])
        except Exception:
            pass
    previous = copy.BaseFeature
    was_tip = body is not None and body.Tip is copy
    doc.removeObject(copy.Name)
    if was_tip and previous is not None:
        _set_tip(body, previous)
    for helper in helpers:
        try:
            if helper is not None and helper.TypeId in ("PartDesign::SubShapeBinder", "PartDesign::Line") \
                    and not [o for o in helper.InList if o.TypeId != "PartDesign::Body"]:
                doc.removeObject(helper.Name)
        except Exception:
            pass


# --- Sección dentro del diálogo nativo ----------------------------------------------

_state = {"section": None, "widget": None, "doc": None, "name": None, "accepted": False, "decision": None}


class _Section(QtWidgets.QGroupBox):
    """
    Fusionar resultado (saliente: una casilla, como en "Dirección 1" de SW) o Alcance de la
    operación (corte: un cuadro), dentro del cuadro de parámetros del diálogo nativo.
    """

    def __init__(self, feature):
        super().__init__()
        self.setObjectName(SECTION_NAME)
        self.feature = feature
        self.additive = feature.TypeId in ADDITIVE
        box = QtWidgets.QVBoxLayout(self)
        self.note = QtWidgets.QLabel()
        self.note.setWordWrap(True)
        if self.additive:
            self.setFlat(True)
            self.setStyleSheet("QGroupBox { border: none; margin: 0px; padding: 0px; }")
            box.setContentsMargins(0, 0, 0, 0)
            self.merge = QtWidgets.QCheckBox("Fusionar resultado")
            self.merge.setChecked(not is_separated(feature))
            self.merge.setToolTip("Apagado: la operación queda como un sólido aparte (un Cuerpo nuevo), "
                                  "como en SW. Se aplica al tocar Aceptar.")
            box.addWidget(self.merge)
        else:
            self.setTitle("Alcance de la operación")
            self.all = QtWidgets.QRadioButton("Todos los sólidos", self)
            self.sel = QtWidgets.QRadioButton("Sólidos seleccionados", self)
            self.group = QtWidgets.QButtonGroup(self)  # excluyentes (creados sin dueño no lo son)
            self.group.addButton(self.all)
            self.group.addButton(self.sel)
            self.auto = QtWidgets.QCheckBox("Selección automática")
            self.list = QtWidgets.QListWidget()
            self.list.setMaximumHeight(110)
            copies = copies_of(feature)
            mode = scope_mode(feature)  # al editar: lo que se eligió la última vez
            self.all.setChecked(mode in ("auto", "all"))
            self.sel.setChecked(mode == "selected")
            self.auto.setChecked(mode != "all")
            for w in (self.all, self.sel, self.auto, self.list):
                box.addWidget(w)
            self._fill_list(set(body_of(c) for c in copies))
            for w in (self.all, self.sel, self.auto):
                w.toggled.connect(self._refresh)
            self.timer = QtCore.QTimer(self)
            self.timer.setInterval(AUTO_MS)
            self.timer.timeout.connect(self._refresh)
            self.timer.start()
            self._refresh()
        box.addWidget(self.note)
        if self.additive and is_separated(feature):
            self.note.setText("Este sólido está aparte (%s). Prendé la casilla para volver a fusionarlo."
                              % body_of(feature).Label)

    def _fill_list(self, with_copy):
        own = body_of(self.feature)
        self.list.clear()
        for body in solid_bodies(self.feature.Document):
            item = QtWidgets.QListWidgetItem(body.Label)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, body.Name)
            flags = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            if body is own:
                flags = QtCore.Qt.ItemFlag.ItemIsUserCheckable  # el suyo va siempre
                item.setToolTip("El corte está en este sólido")
            item.setFlags(flags)
            item.setCheckState(QtCore.Qt.CheckState.Checked if body is own or body in with_copy
                               else QtCore.Qt.CheckState.Unchecked)
            self.list.addItem(item)

    def _refresh(self, *_a):
        try:
            mode = "all" if self.all.isChecked() else "selected"
            self.auto.setEnabled(mode == "all")
            manual = mode == "selected"
            if not manual:
                wanted = self.bodies()
                names = set(b.Name for b in wanted)
                for i in range(self.list.count()):
                    item = self.list.item(i)
                    item.setCheckState(QtCore.Qt.CheckState.Checked if item.data(QtCore.Qt.ItemDataRole.UserRole)
                                       in names else QtCore.Qt.CheckState.Unchecked)
            own = body_of(self.feature)
            for i in range(self.list.count()):
                item = self.list.item(i)
                if item.data(QtCore.Qt.ItemDataRole.UserRole) == getattr(own, "Name", None):
                    continue
                flags = QtCore.Qt.ItemFlag.ItemIsUserCheckable
                if manual:
                    flags |= QtCore.Qt.ItemFlag.ItemIsEnabled
                item.setFlags(flags)
        except (RuntimeError, ReferenceError):  # el diálogo se cerró o la operación se borró (Cancelar)
            try:
                self.timer.stop()
            except Exception:
                pass

    def bodies(self):
        """Sólidos elegidos ahora."""
        doc = self.feature.Document
        own = body_of(self.feature)
        all_bodies = solid_bodies(doc)
        chosen = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                obj = doc.getObject(item.data(QtCore.Qt.ItemDataRole.UserRole))
                if obj is not None:
                    chosen.append(obj)
        mode = "all" if self.all.isChecked() else "selected"
        touched = touched_bodies(self.feature) if mode == "all" and self.auto.isChecked() else []
        return scope_bodies(mode, self.auto.isChecked(), own, all_bodies, touched, chosen)

    def decision(self):
        if self.additive:
            return ("merge", self.merge.isChecked())
        if self.sel.isChecked():
            mode = "selected"
        else:
            mode = "auto" if self.auto.isChecked() else "all"
        return ("scope", [b.Name for b in self.bodies()], mode)


def _wanted(feature):
    if hasattr(feature, "SWUI_MoveFace"):
        return False  # Mover cara (move_face.py) tiene su propio panel
    if feature.TypeId in ADDITIVE:
        return has_solid_before(feature) or is_separated(feature)
    if feature.TypeId in SUBTRACTIVE:
        if original_of(feature) is not None:
            return True  # una copia: avisar que se edita el original
        return len(solid_bodies(feature.Document)) > 1 or bool(copies_of(feature))
    return False


def _inject(doc_name, name):
    doc = FreeCAD.listDocuments().get(doc_name)
    feature = doc.getObject(name) if doc else None
    if feature is None or not FreeCADGui.Control.activeDialog():
        return
    mw = FreeCADGui.getMainWindow()
    panel = None
    for w in mw.findChildren(QtWidgets.QWidget):
        if w.metaObject().className() == "Gui::TaskView::TaskPanel" and w.isVisible():
            panel = w
            break
    if panel is None:
        return
    current = _state.get("widget")
    if current is not None and _alive(current) and current.parent() is panel and _state.get("name") == name:
        return  # FreeCAD avisa la edición dos veces: una sola sección
    _remove_widget()  # el panel de tareas se reusa: sacar la de un diálogo anterior
    original = original_of(feature)
    if original is not None:
        label = QtWidgets.QLabel("Esta es la copia de «%s» en otro sólido: sus medidas siguen al original. "
                                 "Para cambiarlas, editá «%s»." % (original.Label, original.Label))
        label.setWordWrap(True)
        section = QtWidgets.QGroupBox("Alcance de la operación")
        section.setObjectName(SECTION_NAME)
        QtWidgets.QVBoxLayout(section).addWidget(label)
        _state.update(section=None)
    else:
        section = _Section(feature)
        _state.update(section=section, doc=doc_name, name=name, accepted=False)
    _place(panel, section, feature)
    _state["widget"] = section
    if original is not None:
        _state["name"] = name
    # "pressed" llega ANTES de que FreeCAD cierre y destruya el diálogo ("accepted" ya no llega);
    # Enter también pasa por acá (aprieta el botón por defecto).
    for box in mw.findChildren(QtWidgets.QDialogButtonBox):
        if box.isVisible():
            try:
                box.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).pressed.connect(_on_accept)
            except Exception:
                pass


def _place(panel, section, feature):
    """
    Adentro del cuadro de parámetros (así se ve sin desplazar en una pantalla de 768 px):
    la casilla de saliente debajo de "Invertir dirección"; el alcance al final del cuadro.
    """
    root = None
    for w in panel.findChildren(QtWidgets.QWidget):
        name = w.objectName()
        if name.startswith(("PartDesignGui__Task", "PartDesignGui::Task")) and name.endswith("Parameters") \
                and w.layout() is not None and w.isVisible():
            root = w
            break
    if root is None:  # otra versión de FreeCAD: al pie del panel
        lay = panel.layout()
        lay.insertWidget(max(0, lay.count() - 1), section)
        return
    reverse = root.findChild(QtWidgets.QCheckBox, "checkBoxReversed")
    if feature.TypeId in ADDITIVE and reverse is not None:
        holder = reverse.parentWidget().layout()
        index = holder.indexOf(reverse) if holder is not None else -1
        if isinstance(holder, QtWidgets.QBoxLayout) and index >= 0:
            holder.insertWidget(index + 1, section)
            return
        if isinstance(holder, QtWidgets.QGridLayout) and index >= 0:
            row = holder.getItemPosition(index)[0]
            holder.addWidget(section, holder.rowCount(), 0, 1, max(1, holder.columnCount()))
            return
    root.layout().addWidget(section)


def _on_accept():
    """Aceptar: leer la decisión YA (al cerrar, FreeCAD destruye el formulario con la sección adentro)."""
    _state["accepted"] = True
    section = _state.get("section")
    try:
        _state["decision"] = section.decision() if section is not None else None
    except (RuntimeError, ReferenceError):
        _state["decision"] = None


def _alive(widget):
    try:
        widget.objectName()
        return True
    except RuntimeError:
        return False


def _remove_widget():
    widget = _state.get("widget")
    _state["widget"] = None
    if widget is not None and _alive(widget):
        try:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        except Exception:
            pass


def _finish():
    """Al cerrar el diálogo: si fue Aceptar y cambió algo, armar los sólidos."""
    decision, accepted = _state.get("decision"), _state.get("accepted")
    doc_name, name = _state.get("doc"), _state.get("name")
    _state.update(section=None, accepted=False, decision=None)
    try:
        if decision is None or not accepted:
            return
        _apply_decision(decision, doc_name, name)
    finally:
        _remove_widget()


def _apply_decision(decision, doc_name, name):
    doc = FreeCAD.listDocuments().get(doc_name)
    feature = doc.getObject(name) if doc else None
    if feature is None:
        return
    try:
        if decision[0] == "merge":
            if decision[1] == (not is_separated(feature)):
                return
            doc.openTransaction("Fusionar resultado")
            if decision[1]:
                rejoin(feature)
            else:
                separate(feature)
            doc.commitTransaction()
        else:
            bodies = [doc.getObject(n) for n in decision[1] if doc.getObject(n) is not None]
            current = sorted([body_of(feature).Name] + [body_of(c).Name for c in copies_of(feature)])
            same = sorted(b.Name for b in bodies) == current
            if same and getattr(feature, SCOPE_MODE_PROP, None) == decision[2] and not copies_of(feature):
                return
            doc.openTransaction("Alcance de la operación")
            problems = apply_scope_decision(feature, decision)
            doc.commitTransaction()
            if problems:
                _tell("\n".join(problems))
        doc.recompute()
    except ValueError as exc:
        doc.abortTransaction()
        _tell("No se pudo: %s." % exc)
    except Exception:
        doc.abortTransaction()
        FreeCAD.Console.PrintError("[SWUI fork] Multicuerpo:\n%s\n" % traceback.format_exc())
        _tell("No se pudo armar los sólidos (detalle en la Vista de informe).")


def apply_scope_decision(feature, decision):
    """
    ("scope", [nombres de Cuerpos], modo) -> copias del corte/taladro al día, DENTRO de la
    transacción que esté abierta (el panel del taladro la usa así: un solo paso de deshacer).
    Devuelve los problemas para avisar.
    """
    doc = feature.Document
    bodies = [doc.getObject(n) for n in decision[1] if doc.getObject(n) is not None]
    current = sorted([body_of(feature).Name] + [body_of(c).Name for c in copies_of(feature)])
    problems = []
    if len(solid_bodies(doc)) > 1 or copies_of(feature):
        set_scope_mode(feature, decision[2])
    if sorted(b.Name for b in bodies) != current:
        _created, _removed, problems = apply_scope(feature, bodies)
    sync_copies(feature)
    return problems


def _tell(text):
    try:
        QtWidgets.QMessageBox.information(FreeCADGui.getMainWindow(), "Multicuerpo", text)
    except Exception:
        FreeCAD.Console.PrintWarning("[SWUI] %s\n" % text)


class _EditObserver:
    def slotInEdit(self, vp):
        try:
            obj = vp.Object
        except Exception:
            return
        if obj.TypeId in ADDITIVE + SUBTRACTIVE and _in_workbench():
            try:
                if not _wanted(obj):
                    return
            except Exception:
                return
            doc_name, name = obj.Document.Name, obj.Name
            QtCore.QTimer.singleShot(300, lambda: _inject(doc_name, name))

    def slotResetEdit(self, vp):
        if _state.get("section") is not None or _state.get("widget") is not None:
            QtCore.QTimer.singleShot(0, _finish)


def _in_workbench():
    try:
        from swui import layout

        return layout.is_active()
    except Exception:
        return True


# --- Borrar el original borra sus copias -----------------------------------------------------


def _helpers(copy):
    """Lo que el asistente armó para una copia: copia vinculada del croquis, de la cara, recta del eje."""
    out = [profile_object(copy)]
    try:
        if copy.UpToFace:
            out.append(copy.UpToFace[0])
    except Exception:
        pass
    if copy.TypeId == "PartDesign::Groove":
        try:
            out.append(copy.ReferenceAxis[0])
        except Exception:
            pass
    return [h for h in out if h is not None and h.TypeId in ("PartDesign::SubShapeBinder", "PartDesign::Line")]


def with_copies(objs):
    """
    Lo que hay que borrar: lo elegido + las copias de los cortes elegidos + lo que el asistente
    armó para ellas y nadie más usa (sin repetir).
    """
    out = list(objs)
    for obj in objs:
        for copy in copies_of(obj):
            if copy not in out:
                out.append(copy)
    for copy in [o for o in out if original_of(o) is not None]:
        for helper in _helpers(copy):
            users = [u for u in helper.InList if u.TypeId != "PartDesign::Body"]
            if helper not in out and all(u in out for u in users):
                out.append(helper)
    return out


class _DeleteKey(QtCore.QObject):
    """Supr sobre el árbol o la vista: suma a la selección las copias de los cortes elegidos,
    así Std_Delete las borra junto con el original (un paso de deshacer, sin aviso de vínculos)."""

    def eventFilter(self, obj, event):
        try:
            # Qt resuelve los atajos (Supr = Std_Delete) con ShortcutOverride, ANTES del KeyPress:
            # hay que sumar las copias ahí, si no Std_Delete ya corrió
            if event.type() not in (QtCore.QEvent.Type.ShortcutOverride, QtCore.QEvent.Type.KeyPress) \
                    or event.key() != QtCore.Qt.Key.Key_Delete:
                return False
            if isinstance(QtWidgets.QApplication.focusWidget(), (QtWidgets.QLineEdit, QtWidgets.QAbstractSpinBox,
                                                                  QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)):
                return False
            if not _in_workbench() or FreeCADGui.Control.activeDialog():
                return False
            sels = FreeCADGui.Selection.getSelection()
            extra = [c for c in with_copies(sels) if c not in sels]
            for copy in extra:
                FreeCADGui.Selection.addSelection(copy)
        except Exception:
            pass
        return False


class _DocObserver:
    """Respaldo (borrado por otro camino: menú, Python) y aviso de la selección automática."""

    def slotDeletedObject(self, obj):
        try:
            doc = obj.Document
            if getattr(doc, "Transacting", False) or getattr(doc, "Restoring", False):
                return
            names = [c.Name for c in copies_of(obj)]
        except Exception:
            return
        if names:
            doc_name = doc.Name
            QtCore.QTimer.singleShot(0, lambda: _drop_orphans(doc_name, names))

    def slotRecomputedDocument(self, doc):
        if _check["busy"] or FreeCADGui.Control.activeDialog():
            return
        doc_name = doc.Name
        QtCore.QTimer.singleShot(0, lambda: _check_auto(doc_name))


def _drop_orphans(doc_name, names):
    doc = FreeCAD.listDocuments().get(doc_name)
    if doc is None:
        return
    copies = [doc.getObject(n) for n in names if doc.getObject(n) is not None]
    if not copies:
        return
    doc.openTransaction("Borrar copias del corte")
    for copy in copies:
        try:
            _remove_copy(copy)
        except Exception:
            pass
    doc.commitTransaction()
    doc.recompute()


_check = {"busy": False, "declined": set()}


def drifted(feature):
    """Con selección automática: (sólidos a sumar, sólidos a sacar) si el corte cambió, o ([], [])."""
    if scope_mode(feature) != "auto" or SCOPE_MODE_PROP not in feature.PropertiesList:
        return [], []
    current = set([body_of(feature)] + [body_of(c) for c in copies_of(feature)])
    touched = set(touched_bodies(feature))
    owner = body_of(feature)
    return ([b for b in touched if b not in current], [b for b in current if b not in touched and b is not owner])


def _check_auto(doc_name):
    doc = FreeCAD.listDocuments().get(doc_name)
    if doc is None or _check["busy"] or FreeCADGui.Control.activeDialog():
        return
    for feature in [o for o in doc.Objects if SCOPE_MODE_PROP in getattr(o, "PropertiesList", [])]:
        try:
            add, drop = drifted(feature)
        except Exception:
            continue
        if not add and not drop:
            continue
        key = (doc_name, feature.Name, tuple(sorted(b.Name for b in add)), tuple(sorted(b.Name for b in drop)))
        if key in _check["declined"]:
            continue
        parts = []
        if add:
            parts.append("ahora también atraviesa %s" % ", ".join(b.Label for b in add))
        if drop:
            parts.append("ya no atraviesa %s" % ", ".join(b.Label for b in drop))
        text = ("«%s» %s (selección automática).\n\n¿Actualizar el alcance de la operación?"
                % (feature.Label, " y ".join(parts)))
        answer = QtWidgets.QMessageBox.question(FreeCADGui.getMainWindow(), "Alcance de la operación", text)
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            _check["declined"].add(key)
            continue
        _check["busy"] = True
        try:
            doc.openTransaction("Alcance de la operación")
            current = [body_of(feature)] + [body_of(c) for c in copies_of(feature)]
            wanted = [b for b in current if b not in drop] + add
            _c, _r, problems = apply_scope(feature, wanted)
            doc.commitTransaction()
            doc.recompute()
            if problems:
                _tell("\n".join(problems))
        except Exception:
            doc.abortTransaction()
            FreeCAD.Console.PrintError("[SWUI fork] Alcance automático:\n%s\n" % traceback.format_exc())
        finally:
            _check["busy"] = False


_observer = None
_doc_observer = None
_delete_key = None


def install():
    global _observer, _doc_observer, _delete_key
    if _observer is None:
        _observer = _EditObserver()
        FreeCADGui.addDocumentObserver(_observer)
    if _doc_observer is None:
        _doc_observer = _DocObserver()
        FreeCAD.addDocumentObserver(_doc_observer)
    if _delete_key is None:
        try:
            app = QtWidgets.QApplication.instance()
            _delete_key = _DeleteKey()
            app.installEventFilter(_delete_key)
        except Exception:
            _delete_key = None
