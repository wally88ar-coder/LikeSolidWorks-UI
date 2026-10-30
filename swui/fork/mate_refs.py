# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Relaciones de posición que no saltan cuando cambia una pieza (como SW).

FreeCAD 1.1.4 guarda en cada unión la cara o arista por su número en la pieza terminada
("Pad.Edge15"; el "Pad." no cuenta, UtilsAssembly.getObject se queda con el Cuerpo). Al agregar
una operación a la pieza (un taladro de ensamblaje, por ejemplo) los números cambian y la
relación pasa a tomar otra arista: los componentes saltan (visto con el mouse, 2026-10-30).

Acá cada unión guarda, además, cómo era lo elegido (tipo, centro, eje, normal, radio...) en
coordenadas de la pieza, en la propiedad SWUI_MateGeom (nombre estable, ver docs/ESTADO.md).
Cuando una pieza se recalcula (o antes de recalcular el ensamblaje), si el número guardado ya no
corresponde a esa geometría se busca en la pieza la entidad más parecida y se corrige la
referencia; después se vuelve a resolver el ensamblaje. Si la entidad cambió de verdad (agujero
movido o agrandado) se toma la más parecida y se avisa en la vista de informe; si ya no hay
ninguna del mismo tipo, se avisa y la relación queda como estaba.

Es un asistente: las uniones siguen siendo las nativas y el archivo abre sin el addon (sin la
corrección, como FreeCAD solo).
"""

import json
import math
import traceback

import FreeCAD

PROP = "SWUI_MateGeom"  # nombre estable: no cambiar
REFS = ("Reference1", "Reference2")
SAME = 1e-4  # costo por debajo del cual es la misma entidad
CLOSE = 0.5  # por encima: cambió de verdad, se avisa

_state = {"busy": False, "installed": False}


# --- Cuentas sin FreeCAD (probables en el test) ---------------------------------


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _dot(a, b):
    return sum(a[i] * b[i] for i in range(3))


def _norm(a):
    return math.sqrt(_dot(a, a))


def _dist(a, b):
    return _norm(_sub(a, b))


def _angle(a, b, either_sense=False):
    """Ángulo entre dos direcciones (radianes); con either_sense, sin importar el sentido."""
    na, nb = _norm(a), _norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    c = max(-1.0, min(1.0, _dot(a, b) / (na * nb)))
    if either_sense:
        c = abs(c)
    return math.acos(c)


def _line_gap(p, d, q):
    """Distancia del punto q a la recta (p, d)."""
    v = _sub(q, p)
    n = _norm(d) or 1.0
    t = _dot(v, d) / (n * n)
    return _norm([v[i] - t * d[i] for i in range(3)])


def cost(a, b):
    """
    Cuánto se parecen dos firmas (0 = la misma entidad). None si no son del mismo tipo.
    Pesa primero la orientación y la posición que define a la entidad (plano, eje, centro),
    después el tamaño, y lo último el centro de gravedad (cambia si se agujerea una cara).
    """
    if not a or not b or a.get("t") != b.get("t") or a.get("g") != b.get("g"):
        return None
    g = a["g"]
    if g == "plane":
        offset = abs(_dot(a["n"], a["p"]) - _dot(b["n"], b["p"]))
        return 1000 * _angle(a["n"], b["n"]) + 100 * offset + _dist(a["p"], b["p"]) \
            + abs(a["s"] - b["s"]) / max(a["s"], b["s"], 1e-9)
    if g in ("cylinder", "cone", "circle"):
        return 1000 * _angle(a["d"], b["d"], True) + 100 * _line_gap(a["c"], a["d"], b["c"]) \
            + 100 * abs(a["r"] - b["r"]) + 10 * _dist(a["c"], b["c"]) + 0.1 * _dist(a["p"], b["p"])
    if g == "line":
        return 1000 * _angle(a["d"], b["d"], True) + 100 * _line_gap(a["c"], a["d"], b["c"]) \
            + _dist(a["c"], b["c"]) + abs(a["s"] - b["s"])
    if g == "sphere":
        return 10 * _dist(a["c"], b["c"]) + 100 * abs(a["r"] - b["r"])
    # vértice y cualquier otra forma: posición y tamaño
    return 10 * _dist(a["p"], b["p"]) + abs(a.get("s", 0) - b.get("s", 0))


def best_match(want, candidates):
    """(nombre, costo) de la candidata más parecida a `want`; (None, None) si no hay del mismo tipo."""
    best, best_cost = None, None
    for name, sig in candidates:
        c = cost(want, sig)
        if c is not None and (best_cost is None or c < best_cost - 1e-9):
            best, best_cost = name, c
    return best, best_cost


def split_sub(sub):
    """
    'Pad.Edge15' -> ('Pad.', 'Edge15'); el elemento es lo que va después del último punto. Sin el
    '?' que FreeCAD antepone cuando da la referencia por perdida ('Pad.?Face5').
    """
    if not sub:
        return "", ""
    i = sub.rfind(".")
    prefix, name = (sub[:i + 1], sub[i + 1:]) if i >= 0 else ("", sub)
    return prefix, name.lstrip("?")


def is_broken(sub):
    return "?" in (sub or "")


def element_type(name):
    for t in ("Face", "Edge", "Vertex"):
        if name.startswith(t) and name[len(t):].isdigit():
            return t
    return None


# --- Firmas de la geometría ------------------------------------------------------


def _v(vec):
    return [round(vec.x, 6), round(vec.y, 6), round(vec.z, 6)]


def signature(shape):
    """Firma de una cara, arista o vértice (coordenadas de la pieza)."""
    t = shape.ShapeType
    if t == "Vertex":
        return {"t": "Vertex", "g": "point", "p": _v(shape.Point)}
    if t == "Edge":
        curve = shape.Curve
        kind = curve.TypeId
        mid = shape.valueAt((shape.FirstParameter + shape.LastParameter) / 2)
        if kind in ("Part::GeomCircle", "Part::GeomArcOfCircle") or hasattr(curve, "Radius") \
                and hasattr(curve, "Axis") and hasattr(curve, "Center"):
            return {"t": "Edge", "g": "circle", "c": _v(curve.Center), "d": _v(curve.Axis),
                    "r": round(curve.Radius, 6), "p": _v(mid)}
        if kind in ("Part::GeomLine", "Part::GeomLineSegment"):
            return {"t": "Edge", "g": "line", "c": _v(mid), "d": _v(shape.tangentAt(shape.FirstParameter)),
                    "s": round(shape.Length, 6)}
        return {"t": "Edge", "g": "other", "p": _v(shape.CenterOfMass), "s": round(shape.Length, 6)}
    if t == "Face":
        surf = shape.Surface
        kind = surf.TypeId
        cog = shape.CenterOfGravity if hasattr(shape, "CenterOfGravity") else shape.CenterOfMass
        if kind == "Part::GeomPlane":
            u0, u1, v0, v1 = shape.ParameterRange
            n = shape.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
            return {"t": "Face", "g": "plane", "n": _v(n), "p": _v(cog), "s": round(shape.Area, 6)}
        if kind == "Part::GeomCylinder":
            return {"t": "Face", "g": "cylinder", "c": _v(surf.Center), "d": _v(surf.Axis),
                    "r": round(surf.Radius, 6), "p": _v(cog)}
        if kind == "Part::GeomCone":
            return {"t": "Face", "g": "cone", "c": _v(surf.Apex), "d": _v(surf.Axis),
                    "r": round(math.degrees(surf.SemiAngle), 6), "p": _v(cog)}
        if kind == "Part::GeomSphere":
            return {"t": "Face", "g": "sphere", "c": _v(surf.Center), "r": round(surf.Radius, 6)}
        return {"t": "Face", "g": "other", "p": _v(cog), "s": round(shape.Area, 6)}
    return None


def _target(ref):
    """Objeto cuya forma usa FreeCAD para la referencia (lo mismo que UtilsAssembly.findPlacement)."""
    import UtilsAssembly

    return UtilsAssembly.getObject(ref)


def local_shape(obj):
    """
    Forma del componente en sus propias coordenadas (no cambia cuando el ensamblaje lo mueve).
    Se lee del objeto enlazado: la del vínculo queda vieja hasta que se recalcula el ensamblaje.
    """
    try:
        obj = obj.getLinkedObject(True) or obj
    except Exception:
        pass
    shape = getattr(obj, "Shape", None)
    if shape is None:
        import Part

        shape = Part.getShape(obj)
    if shape is None or shape.isNull():
        return None
    shape = shape.copy()
    shape.Placement = FreeCAD.Placement()
    return shape


def _elements(shape, kind):
    return {"Face": shape.Faces, "Edge": shape.Edges, "Vertex": shape.Vertexes}[kind]


def ref_signatures(ref):
    """[firma del elemento, firma del vértice] de una referencia; None si no se puede leer."""
    if not ref or len(ref) != 2 or len(ref[1]) < 1:
        return None
    obj = _target(ref)
    shape = local_shape(obj) if obj is not None else None
    if shape is None:
        return None
    out = []
    for sub in list(ref[1])[:2]:
        _prefix, name = split_sub(sub)
        if element_type(name) is None:
            out.append(None)
            continue
        try:
            out.append(dict(signature(shape.getElement(name)), name=name))
        except Exception:
            out.append(None)
    return out


# --- Guardar y corregir ----------------------------------------------------------------


def _read(joint):
    try:
        return json.loads(getattr(joint, PROP, "") or "{}")
    except Exception:
        return {}


def _write(joint, data):
    if not hasattr(joint, PROP):
        joint.addProperty("App::PropertyString", PROP, "Relación SW",
                          "Geometría elegida en cada referencia, para volver a encontrarla si la pieza "
                          "cambia (LikeSolidWorks UI)")
        joint.setEditorMode(PROP, 2)  # oculta
    text = json.dumps(data, sort_keys=True)
    if getattr(joint, PROP) != text:
        setattr(joint, PROP, text)


def is_joint(obj):
    return hasattr(obj, "Reference1") and hasattr(obj, "Reference2") and hasattr(obj, "JointType")


def snapshot(joint):
    """Guardar la geometría actual de las dos referencias (al crear o cambiar la relación)."""
    data = {}
    for prop in REFS:
        sigs = ref_signatures(getattr(joint, prop, None))
        if sigs:
            data[prop] = sigs
    if data:
        _write(joint, data)


def check(joint):
    """
    Corregir las referencias de una unión si la pieza renumeró. Devuelve True si cambió algo.
    Una referencia sin firma guardada (archivo anterior al arreglo) se toma como buena y se guarda
    su firma. Los cambios hechos a mano ya guardaron la suya (_Observer); un nombre distinto del
    guardado es un cambio automático de FreeCAD y se corrige con la geometría guardada.
    """
    if not is_joint(joint) or getattr(joint, "Suppressed", False):
        return False
    data = _read(joint)
    changed = False
    fresh = {}
    for prop in REFS:
        ref = getattr(joint, prop, None)
        if not ref or len(ref) != 2 or len(ref[1]) < 1:
            continue
        stored = data.get(prop)
        if not stored:
            if not any(is_broken(s) for s in ref[1]):
                fresh[prop] = ref_signatures(ref)
            continue
        new_ref, sigs = _fix_ref(joint, prop, ref, stored)
        fresh[prop] = sigs
        if new_ref is not None:
            _refresh_link(new_ref)
            setattr(joint, prop, new_ref)  # FreeCAD vuelve a ubicar la unión en el acto
            changed = True
    fresh = {k: v for k, v in fresh.items() if v}
    if fresh:
        _write(joint, dict(data, **fresh))
    return changed


def _refresh_link(ref):
    """
    El vínculo del ensamblaje guarda una copia de la forma de la pieza que se pone al día recién al
    recalcular el ensamblaje: sin esto, FreeCAD busca la arista nueva en la forma vieja (error
    "Shape index out of bound").
    """
    obj = _target(ref)
    try:
        if obj is not None and obj.isDerivedFrom("App::Link"):
            obj.recompute()
    except Exception:
        pass


def _fix_ref(joint, prop, ref, stored):
    """(referencia nueva o None, firmas actualizadas)."""
    obj = _target(ref)
    shape = local_shape(obj) if obj is not None else None
    if shape is None:
        return None, stored
    subs = list(ref[1])
    new_subs = list(subs)
    sigs = []
    for i, sub in enumerate(subs[:2]):
        want = stored[i] if i < len(stored) else None
        prefix, name = split_sub(sub)
        kind = element_type(name)
        if want is None or kind is None:
            sigs.append(want)
            continue
        if i == 1 and sub == subs[0]:  # el vértice es el mismo elemento
            new_subs[1] = new_subs[0]
            sigs.append(sigs[0])
            continue
        try:
            current = None if is_broken(sub) else signature(shape.getElement(name))
        except Exception:
            current = None
        here = cost(want, current)
        if here is not None and here < SAME:
            sigs.append(dict(current, name=name))
            continue
        candidates = []
        for n, element in enumerate(_elements(shape, kind), 1):
            try:
                candidates.append(("%s%d" % (kind, n), signature(element)))
            except Exception:
                pass
        best, best_cost = best_match(want, candidates)
        if best is None:
            _warn(joint, obj, "ya no está la %s elegida; la relación quedó como estaba." % _what(want))
            sigs.append(want)
            continue
        if here is not None and here <= best_cost + 1e-9:
            best = name  # la misma sigue siendo la más parecida: solo cambió de forma
        elif best_cost >= CLOSE:
            _warn(joint, obj, "la %s elegida cambió; se tomó la más parecida (%s). Revisala."
                  % (_what(want), best))
        else:
            FreeCAD.Console.PrintLog("[SWUI fork] %s: %s -> %s\n" % (joint.Label, name, best))
        new_subs[i] = prefix + best
        sigs.append(dict(dict(candidates)[best], name=best))
    if new_subs == subs:
        return None, sigs
    return (ref[0], new_subs), sigs


WHAT = {"plane": "cara plana", "cylinder": "cara cilíndrica", "cone": "cara cónica", "sphere": "cara esférica",
        "circle": "arista circular", "line": "arista recta", "point": "vértice"}


def _what(sig):
    return WHAT.get(sig.get("g"), {"Face": "cara", "Edge": "arista"}.get(sig.get("t"), "entidad"))


def _warn(joint, obj, text):
    FreeCAD.Console.PrintWarning("Relación de posición «%s» (%s): %s\n"
                                 % (joint.Label, getattr(obj, "Label", "?"), text))


# --- Cuándo revisar ------------------------------------------------------------------


def _assemblies():
    for doc in FreeCAD.listDocuments().values():
        for obj in doc.Objects:
            if obj.TypeId == "Assembly::AssemblyObject":
                yield obj


def _joints(asm):
    out = []
    for child in asm.Group:
        if child.TypeId == "Assembly::JointGroup":
            out.extend(j for j in child.Group if is_joint(j))
    return out


def _uses(joint, docs):
    """¿Alguna referencia de la unión toca una pieza de estos documentos?"""
    for prop in REFS:
        ref = getattr(joint, prop, None)
        if not ref:
            continue
        try:
            obj = _target(ref)
            linked = obj.getLinkedObject(True) if obj is not None else None
        except Exception:
            continue
        if linked is not None and linked.Document.Name in docs:
            return True
    return False


def check_assemblies(docs=None, assembly_doc=None):
    """
    Revisar las uniones que usan piezas de `docs` (todas si None), o las de los ensamblajes del
    documento `assembly_doc`; volver a resolver el ensamblaje si hizo falta.
    """
    if _state["busy"]:
        return
    _state["busy"] = True
    try:
        for asm in list(_assemblies()):
            if assembly_doc is not None and asm.Document.Name != assembly_doc:
                continue
            touched = False
            for joint in _joints(asm):
                if docs is not None and not _uses(joint, docs):
                    continue
                try:
                    touched = check(joint) or touched
                except Exception:
                    FreeCAD.Console.PrintLog("[SWUI fork] Revisar relación %s:\n%s\n"
                                             % (joint.Label, traceback.format_exc()))
            if touched:
                _solve_later(asm)
    finally:
        _state["busy"] = False


def _solve_later(asm):
    doc_name, name = asm.Document.Name, asm.Name

    def run():
        try:
            a = FreeCAD.getDocument(doc_name).getObject(name)
            if a is not None:
                a.Document.recompute()  # vínculos y uniones al día antes de resolver
                a.solve()
                a.Document.recompute()
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Resolver ensamblaje:\n%s\n" % traceback.format_exc())

    if FreeCAD.GuiUp:
        from swui.compat import QtCore

        QtCore.QTimer.singleShot(0, run)
    else:
        run()


def _after_open(doc_name):
    try:
        doc = FreeCAD.getDocument(doc_name)
    except Exception:
        return
    if any(o.TypeId == "Assembly::AssemblyObject" for o in doc.Objects):
        check_assemblies(assembly_doc=doc_name)


def _recomputing():
    return any(getattr(d, "Recomputing", False) for d in FreeCAD.listDocuments().values())


class _Observer:
    def slotChangedObject(self, obj, prop):
        # relación nueva o cambiada a mano: lo elegido ahora es lo bueno. Los cambios que hace
        # FreeCAD solo (nombres de elementos al recalcular una pieza, o '?' si los da por perdidos)
        # no cuentan: esos son justamente los que hay que corregir.
        if prop not in REFS or _state["busy"] or not is_joint(obj):
            return
        try:
            if obj.Document.Restoring or FreeCAD.isRestoring() or _recomputing():
                return
            ref = getattr(obj, prop, None)
            if ref and any(is_broken(s) for s in ref[1]):
                return
            snapshot(obj)
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI fork] Guardar relación:\n%s\n" % traceback.format_exc())

    def slotCreatedDocument(self, doc):
        # al abrir: guardar la firma de las relaciones de archivos anteriores, y corregir si una
        # pieza cambió con el ensamblaje cerrado (como SW al abrir el ensamblaje). FreeCAD 1.1.4 no
        # avisa a Python el fin de la carga (slotFinishRestoreDocument no llega): se mira apenas
        # termina de abrir, con la interfaz ya libre.
        if FreeCAD.GuiUp:
            from swui.compat import QtCore

            QtCore.QTimer.singleShot(0, lambda n=doc.Name: _after_open(n))

    def slotRecomputedDocument(self, doc):
        # una pieza recalculada: las uniones que la usan; un ensamblaje: todas las suyas
        if any(o.TypeId == "Assembly::AssemblyObject" for o in doc.Objects):
            check_assemblies(assembly_doc=doc.Name)
        else:
            check_assemblies({doc.Name})


def install():
    if not _state["installed"]:
        _state["installed"] = True
        FreeCAD.addDocumentObserver(_Observer())
