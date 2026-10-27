# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Chapa metálica (fase 1) sobre el addon SheetMetal: lo que no necesita interfaz.

Por debajo todo es de SheetMetal (no se reimplementa): la Brida base es su BaseBend
(SMBaseBend), la Brida de arista su Bend (SMBendWall) y el desarrollo su Unfold (SMUnfold,
desarrollador nuevo). El fork pone encima los nombres, paneles y flujo de SW:
- Parámetros de chapa en la Brida base (como la operación "Chapa-metálica" de SW): espesor,
  radio de plegado (de fábrica atado al espesor: el usuario usa radio = espesor) y factor K
  (propiedad `SWUI_KFactor`, nombre estable). Las bridas de arista atan su radio al de la
  Brida base con una ecuación ("Usar radio predeterminado") y el desarrollo su factor K.
- Desarrollo: un Unfold por Cuerpo, marcado con `SWUI_FlatOf` (nombre del Cuerpo, nombre
  estable). La cara fija es la cara grande de la Brida base, buscada en la punta del Cuerpo
  cada vez que se usa (así sigue a las bridas que se agregan después).
- DXF: escrito acá (R12, el más compatible): contorno y agujeros en la capa CONTORNO, líneas
  de plegado en PLEGADO con línea de trazos. El exportador de FreeCAD pone las capas según los
  grupos del documento y no lleva el tipo de línea (probado 2026-10-27).

Verificado en FreeCAD 1.1.4 + SheetMetal 0.8.26 sin GUI: placa 100x50x2 con brida de arista de
30 (exterior virtual), radio 2, K 0,5: desarrollo 76,712 = 46 + 26 + π/2·(2 + 0,5·2).
Los croquis del desarrollo los arma SheetMetal solo con interfaz (usa ViewObject).
"""

import math
import re

import FreeCAD

SM_MODULES = ("SheetMetalTools", "SheetMetalBaseCmd", "SheetMetalCmd", "SheetMetalUnfoldCmd")
K_PROP = "SWUI_KFactor"  # factor K de la pieza, en la Brida base (nombre estable)
FLAT_PROP = "SWUI_FlatOf"  # en el desarrollo: Name del Cuerpo (nombre estable)
DEFAULT_K = 0.5  # como SW de fábrica
DEFAULT_THICKNESS = 2.0
DEFAULT_LENGTH = 20.0
PREFS = "User parameter:BaseApp/Preferences/Mod/LikeSolidWorksUI/Chapa"

OUTLINE_LAYER = "CONTORNO"
BEND_LAYER = "PLEGADO"
DASH = (5.0, 2.5)  # trazo y espacio de la línea de plegado (mm)

KINDS = {"SMBaseBend": "base", "SMBendWall": "wall", "SMUnfold": "flat"}
TOL = 1e-6


def available():
    """¿Está instalado el addon SheetMetal?"""
    try:
        for name in SM_MODULES:
            __import__(name)
        return True
    except Exception:
        return False


MISSING_TEXT = ("Para la chapa hace falta el addon SheetMetal (Herramientas > Gestor de complementos > "
                "SheetMetal). Después reiniciá FreeCAD.")


def kind(obj):
    """"base" (Brida base), "wall" (Brida de arista), "flat" (desarrollo) o None."""
    try:
        proxy = obj.Proxy
    except Exception:
        return None
    return KINDS.get(type(proxy).__name__)


def body_of(obj):
    try:
        body = getattr(obj, "_Body", None)
        if body is not None:
            return body
        parent = obj.getParentGeoFeatureGroup()
        return parent if parent is not None and parent.TypeId == "PartDesign::Body" else None
    except Exception:
        return None


def sheet_base(body):
    """La Brida base del Cuerpo (la primera), o None si el Cuerpo no es de chapa."""
    for obj in getattr(body, "Group", []):
        if kind(obj) == "base":
            return obj
    return None


def is_sheet_body(body):
    return body is not None and sheet_base(body) is not None


def sheet_bodies(doc):
    return [o for o in doc.Objects if o.TypeId == "PartDesign::Body" and is_sheet_body(o)]


def ensure_k(base):
    if K_PROP not in base.PropertiesList:
        base.addProperty("App::PropertyFloat", K_PROP, "Chapa", "Factor K (fork de LikeSolidWorks UI)")
        setattr(base, K_PROP, DEFAULT_K)


def k_factor(base):
    return float(getattr(base, K_PROP, DEFAULT_K))


def thickness(body):
    base = sheet_base(body)
    return float(base.Thickness.Value) if base is not None else 0.0


# --- Preferencias (lo último usado, como SW recuerda el espesor) --------------


def last(name, default):
    try:
        return FreeCAD.ParamGet(PREFS).GetFloat(name, default)
    except Exception:
        return default


def remember(name, value):
    try:
        FreeCAD.ParamGet(PREFS).SetFloat(name, float(value))
    except Exception:
        pass


# --- Nombres ------------------------------------------------------------------


def fmt_mm(value):
    """2 -> "2", 1.5 -> "1,5", 0.75 -> "0,75" (coma decimal, sin ceros de más)."""
    text = ("%.3f" % float(value)).rstrip("0").rstrip(".")
    return text.replace(".", ",")


def clean_name(text):
    return re.sub(r'[<>:"/\\|?*]+', "_", (text or "").strip()).strip(". ")


def dxf_filename(part, thick, material=None):
    """("Soporte", 1.5, "SAE 1010") -> "Soporte_1,5mm_SAE 1010.dxf" (pieza + espesor + material)."""
    parts = [clean_name(part) or "Pieza", fmt_mm(thick) + "mm"]
    if material and clean_name(material):
        parts.append(clean_name(material))
    return "_".join(parts) + ".dxf"


def next_label(prefix, used):
    """("Brida-Base", {"Brida-Base1"}) -> "Brida-Base2" (como SW)."""
    n = 1
    while "%s%d" % (prefix, n) in used:
        n += 1
    return "%s%d" % (prefix, n)


# --- DXF (sin FreeCAD) ------------------------------------------------------------


def _num(v):
    text = "%.6f" % v
    text = text.rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def dxf_text(entities):
    """
    Archivo DXF R12 de entidades ("LINE", capa, x1, y1, x2, y2), ("ARC", capa, cx, cy, r,
    ángulo_inicio, ángulo_fin) en grados y antihorario, ("CIRCLE", capa, cx, cy, r).
    Capas CONTORNO (continua) y PLEGADO (trazos); unidades mm.
    """
    out = []

    def put(code, value):
        out.append("%3d" % code)
        out.append(value if isinstance(value, str) else _num(value))

    put(0, "SECTION"); put(2, "HEADER")
    put(9, "$ACADVER"); put(1, "AC1009")
    put(9, "$INSUNITS"); out += [" 70", "4"]
    put(9, "$LTSCALE"); put(40, 1.0)
    put(0, "ENDSEC")
    put(0, "SECTION"); put(2, "TABLES")
    put(0, "TABLE"); put(2, "LTYPE"); out += [" 70", "2"]
    put(0, "LTYPE"); put(2, "CONTINUOUS"); out += [" 70", "0"]; put(3, "Solid line")
    out += [" 72", "65", " 73", "0"]; put(40, 0.0)
    put(0, "LTYPE"); put(2, "DASHED"); out += [" 70", "0"]; put(3, "__ __ __ __")
    out += [" 72", "65", " 73", "2"]; put(40, DASH[0] + DASH[1]); put(49, DASH[0]); put(49, -DASH[1])
    put(0, "ENDTAB")
    put(0, "TABLE"); put(2, "LAYER"); out += [" 70", "2"]
    for name, color, ltype in ((OUTLINE_LAYER, "7", "CONTINUOUS"), (BEND_LAYER, "1", "DASHED")):
        put(0, "LAYER"); put(2, name); out += [" 70", "0", " 62", color]; put(6, ltype)
    put(0, "ENDTAB")
    put(0, "ENDSEC")
    put(0, "SECTION"); put(2, "ENTITIES")
    for ent in entities:
        typ, layer = ent[0], ent[1]
        put(0, typ); put(8, layer)
        if layer == BEND_LAYER:
            put(6, "DASHED")  # también en la entidad: hay programas que no leen el de la capa
        if typ == "LINE":
            put(10, ent[2]); put(20, ent[3]); put(30, 0.0)
            put(11, ent[4]); put(21, ent[5]); put(31, 0.0)
        elif typ == "ARC":
            put(10, ent[2]); put(20, ent[3]); put(30, 0.0); put(40, ent[4])
            put(50, ent[5] % 360.0); put(51, ent[6] % 360.0)
        elif typ == "CIRCLE":
            put(10, ent[2]); put(20, ent[3]); put(30, 0.0); put(40, ent[4])
    put(0, "ENDSEC")
    put(0, "EOF")
    return "\n".join(out) + "\n"


def shift(entities, dx, dy):
    """Correr las entidades (p. ej. para que el desarrollo arranque en 0,0)."""
    out = []
    for ent in entities:
        if ent[0] == "LINE":
            out.append((ent[0], ent[1], ent[2] + dx, ent[3] + dy, ent[4] + dx, ent[5] + dy))
        else:
            out.append((ent[0], ent[1], ent[2] + dx, ent[3] + dy) + tuple(ent[4:]))
    return out


def merge_lines(entities, tol=1e-6):
    """
    Unir rectas seguidas sobre la misma línea (SheetMetal corta el contorno donde empieza y
    termina cada pliegue). Solo se unen dos rectas de la misma capa que comparten una punta a la
    que no llega nada más.
    """
    lines = [list(e) for e in entities if e[0] == "LINE"]
    rest = [e for e in entities if e[0] != "LINE"]

    def key(x, y):
        return (round(x / tol), round(y / tol)) if tol else (x, y)

    changed = True
    while changed:
        changed = False
        ends = {}
        for i, ln in enumerate(lines):
            for x, y in ((ln[2], ln[3]), (ln[4], ln[5])):
                ends.setdefault(key(x, y), []).append(i)
        for e in rest:  # un arco que llega a esa punta impide unir
            if e[0] == "ARC":
                for ang in (e[5], e[6]):
                    x = e[2] + e[4] * math.cos(math.radians(ang))
                    y = e[3] + e[4] * math.sin(math.radians(ang))
                    ends.setdefault(key(x, y), []).append(-1)
        for pt, users in ends.items():
            if len(users) != 2 or -1 in users or users[0] == users[1]:
                continue
            a, b = lines[users[0]], lines[users[1]]
            if a[1] != b[1]:
                continue
            pa = [(a[2], a[3]), (a[4], a[5])]
            pb = [(b[2], b[3]), (b[4], b[5])]
            fa = pa[1] if key(*pa[0]) == pt else pa[0]  # punta libre de cada una
            fb = pb[1] if key(*pb[0]) == pt else pb[0]
            ux, uy = fa[0] - fb[0], fa[1] - fb[1]
            length = math.hypot(ux, uy)
            if length <= tol:
                continue
            # la punta compartida sobre la recta entre las dos puntas libres
            sx, sy = pt[0] * tol, pt[1] * tol
            if abs((sx - fb[0]) * uy - (sy - fb[1]) * ux) / length > 1e-4:
                continue
            lines[users[0]] = ["LINE", a[1], fb[0], fb[1], fa[0], fa[1]]
            del lines[users[1]]
            changed = True
            break
    return [tuple(ln) for ln in lines] + rest


def extent(entities):
    """(xmin, ymin, xmax, ymax) aproximado (los arcos por su caja completa)."""
    xs, ys = [], []
    for ent in entities:
        if ent[0] == "LINE":
            xs += [ent[2], ent[4]]
            ys += [ent[3], ent[5]]
        else:
            xs += [ent[2] - ent[4], ent[2] + ent[4]]
            ys += [ent[3] - ent[4], ent[3] + ent[4]]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, 0.0, 0.0)


# --- Geometría (con FreeCAD) --------------------------------------------------------


def edges_to_entities(edges, layer):
    """Aristas planas (en el plano XY) -> entidades DXF; lo que no es recta o arco va en tramos."""
    out = []
    for edge in edges:
        curve = edge.Curve
        name = type(curve).__name__
        if name in ("Line", "LineSegment"):
            a, b = edge.Vertexes[0].Point, edge.Vertexes[-1].Point
            if a.distanceToPoint(b) > TOL:
                out.append(("LINE", layer, a.x, a.y, b.x, b.y))
            continue
        if name == "Circle":
            c, r = curve.Center, curve.Radius
            if edge.isClosed() or abs(edge.LastParameter - edge.FirstParameter - 2 * math.pi) < 1e-9:
                out.append(("CIRCLE", layer, c.x, c.y, r))
                continue
            p1, p2 = edge.valueAt(edge.FirstParameter), edge.valueAt(edge.LastParameter)
            if curve.Axis.z < 0:
                p1, p2 = p2, p1  # el arco gira al revés: en DXF siempre antihorario
            a1 = math.degrees(math.atan2(p1.y - c.y, p1.x - c.x))
            a2 = math.degrees(math.atan2(p2.y - c.y, p2.x - c.x))
            out.append(("ARC", layer, c.x, c.y, r, a1, a2))
            continue
        pts = edge.discretize(Deflection=0.01)
        for a, b in zip(pts, pts[1:]):
            if a.distanceToPoint(b) > TOL:
                out.append(("LINE", layer, a.x, a.y, b.x, b.y))
    return out


def _is_plane(face):
    try:
        return type(face.Surface).__name__ == "Plane"
    except Exception:
        return False


def fixed_face(body):
    """
    Cara fija del desarrollo (como la "cara fija" de SW): en la punta del Cuerpo, la cara plana
    más grande que está sobre la cara grande de la Brida base. Devuelve "FaceN" o None.
    """
    base, tip = sheet_base(body), body.Tip
    if base is None or tip is None:
        return None
    planes = [f for f in base.Shape.Faces if _is_plane(f)]
    if not planes:
        return None
    # De las dos caras grandes (arriba y abajo), siempre la que mira para el lado del croquis:
    # así el desarrollo no sale espejado de una vez a la otra.
    try:
        up = base.BendSketch.getGlobalPlacement().Rotation.multVec(FreeCAD.Vector(0, 0, 1))
    except Exception:
        up = FreeCAD.Vector(0, 0, 1)
    top = max(f.Area for f in planes)
    ref = max(planes, key=lambda f: (f.Area > top * (1 - 1e-6), f.normalAt(0, 0).dot(up), f.Area))
    n = ref.normalAt(0, 0)
    p = ref.CenterOfMass
    best, area = None, 0.0
    for i, face in enumerate(tip.Shape.Faces):
        if not _is_plane(face):
            continue
        m = face.normalAt(0, 0)
        if abs(abs(m.dot(n)) - 1.0) > 1e-6 or abs((face.CenterOfMass - p).dot(n)) > 1e-4:
            continue
        try:
            overlap = face.common(ref).Area
        except Exception:
            overlap = 0.0
        if overlap > TOL and face.Area > area:
            best, area = "Face%d" % (i + 1), face.Area
    return best


def flat_of(body):
    doc = body.Document
    for obj in doc.Objects:
        if kind(obj) == "flat" and getattr(obj, FLAT_PROP, "") == body.Name:
            return obj
    return None


def flat_label(body):
    doc = body.Document
    others = [b for b in sheet_bodies(doc) if b is not body]
    # sin espacios ni paréntesis: SheetMetal nombra los croquis del desarrollo con el Label
    return "Desarrollo" if not others else "Desarrollo_" + re.sub(r"\W+", "_", body.Label)


def ensure_flat(body, sketches=True):
    """
    El desarrollo del Cuerpo (lo crea si falta), con la cara fija al día y el factor K de la
    Brida base. sketches: que SheetMetal arme los croquis del desarrollo (solo con interfaz).
    """
    import SheetMetalUnfoldCmd

    base, tip = sheet_base(body), body.Tip
    face = fixed_face(body)
    if base is None or face is None:
        raise ValueError("No se encontró la cara de la Brida base para desplegar la chapa.")
    ensure_k(base)
    flat = flat_of(body)
    doc = body.Document
    if flat is None:
        flat = doc.addObject("Part::FeaturePython", "Unfold")
        SheetMetalUnfoldCmd.SMUnfold(flat, tip, [face])
        if FreeCAD.GuiUp:
            SheetMetalUnfoldCmd.SMUnfoldViewProvider(flat.ViewObject)
        flat.addProperty("App::PropertyString", FLAT_PROP, "SWUI", "Desarrollo de (fork de LikeSolidWorks UI)")
        flat.setEditorMode(FLAT_PROP, 2)
        setattr(flat, FLAT_PROP, body.Name)
        flat.Label = flat_label(body)
        flat.Visibility = False
    elif flat.baseObject != (tip, [face]):
        flat.baseObject = (tip, [face])
    expr = "%s.%s" % (base.Name, K_PROP)
    if dict(flat.ExpressionEngine).get("KFactor") != expr:
        flat.setExpression("KFactor", expr)
    if flat.KFactorStandard != "ansi":
        flat.KFactorStandard = "ansi"  # K de SW: posición de la fibra neutra (0,5 = mitad)
    want = bool(sketches and FreeCAD.GuiUp)
    if flat.GenerateSketch != want:
        flat.GenerateSketch = want
    if want and not flat.SeparateSketchLayers:
        flat.SeparateSketchLayers = True
    flat.recompute()
    return flat


def flat_sketches(flat):
    """(croquis de contorno/agujeros, croquis de plegado) del desarrollo."""
    doc = flat.Document
    cut, bends = [], []
    for name in getattr(flat, "UnfoldSketches", []) or []:
        sk = doc.getObject(name)
        if sk is None:
            continue
        if "_Sketch_Bend_Labels" in name:
            continue
        (bends if "_Sketch_Bends" in name else cut).append(sk)
    return cut, bends


def flat_entities(flat):
    """Entidades DXF del desarrollo, corridas para que arranque en 0,0."""
    cut, bends = flat_sketches(flat)
    if not cut:
        raise ValueError("SheetMetal no armó el croquis del desarrollo.")
    inv = cut[0].Placement.inverse().toMatrix()  # todo en el plano del croquis del contorno
    ents = []
    for sketches, layer in ((cut, OUTLINE_LAYER), (bends, BEND_LAYER)):
        for sk in sketches:
            ents += edges_to_entities(sk.Shape.transformed(inv).Edges, layer)
    ents = merge_lines(ents)
    x0, y0, _x1, _y1 = extent([e for e in ents if e[1] == OUTLINE_LAYER] or ents)
    return shift(ents, -x0, -y0)


def part_name(body):
    doc = body.Document
    name = doc.Label or doc.Name
    if len(sheet_bodies(doc)) > 1:
        name += "-" + body.Label
    return name


def material_name(body):
    try:
        from swui.fork import material

        info, _src = material.material_info(body)
        return (info or {}).get("name") or None
    except Exception:
        return None


def write_dxf(body, path):
    flat = ensure_flat(body, sketches=True)
    text = dxf_text(flat_entities(flat))
    with open(path, "w", encoding="ascii", errors="replace", newline="\r\n") as fh:
        fh.write(text)
    return path
