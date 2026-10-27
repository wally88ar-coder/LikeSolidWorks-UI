# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Simetría de sólidos enteros como sólido aparte ("Sólidos para simetría" con "Fusionar
sólidos" apagado, como SW). Lo usa el panel de Simetría (pattern_panel.MirrorPanel).

Todo nativo (el addon es un asistente, docs/ESTADO.md "Multicuerpo"): por cada sólido, una
Simetría de Part (Part::Mirroring, Source = el Cuerpo) y un Cuerpo nuevo que arranca de ella
(Body.BaseFeature): sigue los cambios del original y admite operaciones propias encima.

El plano, según qué sea (verificado en FreeCAD 1.1.4):
- plano del origen o cara de la pieza: MirrorPlane apuntando A TRAVÉS del Cuerpo
  ((Cuerpo, "Origin.YZ_Plane.") / (Cuerpo, "Pad.Face6")); apuntado directo al objeto de adentro
  da el aviso "fuera de alcance".
- plano de referencia (PartDesign::Plane): Part::Mirroring lo IGNORA en silencio (usa el plano
  por defecto) y tampoco toma una copia vinculada de él; se atan Base y Normal con ecuaciones a
  la posición del plano (Base = Plano.Placement.Base, Normal = Plano.Placement.Rotation * (0,0,1)).
"""

import FreeCAD

PART_MIRROR = "Part::Mirroring"
MIRROR_LABEL = "Simetría de %s"


def _body_of(obj):
    from swui.fork import multibody

    if obj is not None and obj.TypeId == "PartDesign::Body":
        return obj
    return multibody.body_of(obj)


def _origin_body(plane):
    """Cuerpo dueño de un plano del origen (App::Plane), o None."""
    for origin in plane.InList:
        if origin.TypeId == "App::Origin":
            for owner in origin.InList:
                if owner.TypeId == "PartDesign::Body":
                    return owner, origin
    return None, None


def plane_link(ref):
    """
    Cómo poner el plano en la Simetría de Part: ("link", (cuerpo, [subnombre])),
    ("expr", objeto plano) o None si no sirve.
    """
    if not ref:
        return None
    obj, subs = ref
    sub = subs[0] if subs else ""
    if obj.TypeId == "App::Plane":
        body, origin = _origin_body(obj)
        if body is not None:
            return ("link", (body, ["%s.%s." % (origin.Name, obj.Name)]))
        return ("link", (obj, [""]))
    if obj.TypeId == "PartDesign::Plane":
        return ("expr", obj)
    if sub.startswith("Face"):
        body = _body_of(obj)
        if body is not None and obj is not body:
            return ("link", (body, ["%s.%s" % (obj.Name, sub)]))
        return ("link", (obj, [sub]))
    return None


def plane_of(ref):
    """(punto, normal) en coordenadas globales, para la vista previa; None si no sirve."""
    if not ref:
        return None
    obj, subs = ref
    sub = subs[0] if subs else ""
    try:
        if obj.TypeId in ("App::Plane", "PartDesign::Plane"):
            plc = obj.getGlobalPlacement()
            return plc.Base, plc.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
        if sub.startswith("Face"):
            body = _body_of(obj)
            face = body.getSubObject("%s.%s" % (obj.Name, sub)) if body is not None and obj is not body \
                else obj.getSubObject(sub)
            surf = face.Surface
            if type(surf).__name__ != "Plane":
                return None
            return face.CenterOfMass, face.normalAt(0, 0)
    except Exception:
        return None
    return None


def mirrored_shape(body, ref):
    """La forma espejada de un sólido (para dibujar la vista previa), o None."""
    plane = plane_of(ref)
    if plane is None:
        return None
    try:
        shape = body.Shape.copy()
        return shape.mirror(plane[0], plane[1])
    except Exception:
        return None


def make_mirror_body(body, ref):
    """
    Sólido aparte espejado: (Part::Mirroring, Cuerpo nuevo). ValueError si el plano no sirve.
    """
    from swui.fork import multibody

    how = plane_link(ref)
    if how is None:
        raise ValueError("el plano de simetría no sirve (elegí un plano o una cara plana)")
    doc = body.Document
    mirror = doc.addObject(PART_MIRROR, "Simetria")
    multibody._keep_label(mirror, MIRROR_LABEL % body.Label)
    mirror.Source = body
    if how[0] == "link":
        mirror.MirrorPlane = how[1]
    else:
        # Con <<Etiqueta>>: un nombre como "A" es la unidad amperes en las ecuaciones (y FreeCAD
        # mantiene la referencia si se renombra). No se puede tomar ".Base" de un paréntesis.
        plane = how[1]
        owner = _body_of(plane)
        place = "<<%s>>.Placement * " % owner.Label if owner is not None else ""
        turn = "<<%s>>.Placement.Rotation * " % owner.Label if owner is not None else ""
        mirror.setExpression("Base", "%s<<%s>>.Placement.Base" % (place, plane.Label))
        mirror.setExpression("Normal", "%s<<%s>>.Placement.Rotation * vector(0; 0; 1)" % (turn, plane.Label))
    try:
        mirror.Visibility = False
    except Exception:
        pass
    new = doc.addObject("PartDesign::Body", "Body")
    multibody._keep_label(new, multibody.next_body_label(set(o.Label for o in doc.Objects)))
    new.BaseFeature = mirror
    return mirror, new
