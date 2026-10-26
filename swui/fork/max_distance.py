# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Distancia máxima entre dos geometrías cualesquiera (para Medir, measure_sw.py).

FreeCAD (OpenCASCADE) trae la distancia mínima (distToShape) pero no la máxima. Método:

1. Reducir: la distancia a un punto fijo crece hacia afuera, así que el máximo nunca cae en
   el medio de una recta ni de una cara plana. Una arista recta se cambia por sus dos
   puntas, una cara plana por su contorno; solo lo curvo (arcos, cilindros, superficies
   libres) queda como curva o superficie con sus parámetros.
2. Barrido grueso: puntos sobre lo curvo (FreeCAD da cada punto exacto con valueAt), con un
   tope de puntos por lado; se buscan los pares más alejados.
3. Afinado: los mejores candidatos (varios, para no quedarse en un máximo local) se mueven
   por su curva/superficie mientras la distancia crezca, con pasos cada vez más chicos,
   hasta la millonésima del tamaño. Sobre la geometría exacta, no sobre la malla.
4. Casos con fórmula exacta: solo vértices (todos contra todos), punto-círculo y dos
   círculos completos en el mismo plano. El test compara el método general con ellos.

La parte de cuentas (Item, max_between, fórmulas) no usa FreeCAD: se prueba en
tools/test_load.py con curvas armadas a mano.
"""

import math

SAMPLES_1D = 64  # puntos por curva en el barrido
SAMPLES_2D = 24  # por lado de la grilla de una superficie
BUDGET = 2500  # tope de puntos por lado (piezas con muchas caras curvas: menos por cara)
CANDIDATES = 8  # pares que se afinan
REL_TOL = 1e-9  # paso final relativo al rango del parámetro
MAX_ITER = 4000


# --- Vectores como tuplas -------------------------------------------------


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def dist(a, b):
    return _norm(_sub(a, b))


def _unit(a):
    n = _norm(a)
    return _mul(a, 1.0 / n) if n > 1e-15 else None


def _any_perp(n):
    """Una dirección perpendicular a n."""
    t = (1.0, 0.0, 0.0) if abs(n[0]) < 0.9 else (0.0, 1.0, 0.0)
    c = (n[1] * t[2] - n[2] * t[1], n[2] * t[0] - n[0] * t[2], n[0] * t[1] - n[1] * t[0])
    return _unit(c)


# --- Fórmulas exactas -------------------------------------------------------


def max_point_circle(p, center, normal, radius):
    """Distancia máxima de un punto a un círculo completo: (d, punto del círculo)."""
    n = _unit(normal)
    w = _sub(p, center)
    h = _dot(w, n)
    radial = _sub(w, _mul(n, h))
    u = _unit(radial) or _any_perp(n)  # punto sobre el eje: cualquier punto del círculo
    far = _sub(center, _mul(u, radius))
    return dist(p, far), far


def max_coplanar_circles(c1, r1, c2, r2, normal):
    """Dos círculos completos en el mismo plano: centros + radios. (d, punto1, punto2)."""
    u = _unit(_sub(c2, c1)) or _any_perp(_unit(normal))  # concéntricos: cualquier dirección
    p1 = _sub(c1, _mul(u, r1))
    p2 = _add(c2, _mul(u, r2))
    return dist(p1, p2), p1, p2


# --- Método general ----------------------------------------------------------


class Item:
    """
    Un punto, una curva o una superficie: pos(parámetros) -> (x, y, z).
    lo/hi: límites de los parámetros (vacíos para un punto); valid(parámetros) -> bool
    para superficies recortadas (agujeros, bordes).
    """

    def __init__(self, pos, lo=(), hi=(), valid=None):
        self.pos, self.lo, self.hi, self.valid = pos, tuple(lo), tuple(hi), valid

    @classmethod
    def point(cls, p):
        p = tuple(p)
        return cls(lambda _params, p=p: p)

    def dims(self):
        return len(self.lo)

    def ok(self, params):
        return self.valid is None or self.valid(params)

    def samples(self, n1=SAMPLES_1D, n2=SAMPLES_2D):
        if self.dims() == 0:
            return [()]
        if self.dims() == 1:
            (a,), (b,) = self.lo, self.hi
            return [(a + (b - a) * i / n1,) for i in range(n1 + 1)]
        (a, c), (b, d) = self.lo, self.hi
        out = []
        for i in range(n2 + 1):
            for j in range(n2 + 1):
                params = (a + (b - a) * i / n2, c + (d - c) * j / n2)
                if self.ok(params):
                    out.append(params)
        return out


def _cloud(items, budget=BUDGET):
    """[(índice de item, parámetros, punto)] con un tope de puntos (menos por item si hay muchos)."""
    curved = [it for it in items if it.dims()]
    n1, n2 = SAMPLES_1D, SAMPLES_2D
    while True:
        total = sum(1 for it in items if not it.dims())
        total += sum((n1 + 1) if it.dims() == 1 else (n2 + 1) ** 2 for it in curved)
        if total <= budget or (n1 <= 8 and n2 <= 4):
            break
        n1, n2 = max(8, n1 // 2), max(4, n2 // 2)
    out = []
    for k, it in enumerate(items):
        for params in it.samples(n1, n2):
            try:
                out.append((k, params, tuple(it.pos(params))))
            except Exception:
                continue
    return out, n1, n2


def _top_pairs(A, B, count):
    """Los pares más alejados (índices en A y B), sin repetir el mismo par de items primero."""
    try:
        import numpy

        pa = numpy.array([p for _k, _q, p in A], dtype=float)
        pb = numpy.array([p for _k, _q, p in B], dtype=float)
        d2 = ((pa[:, None, :] - pb[None, :, :]) ** 2).sum(axis=2)
        flat = numpy.argsort(d2, axis=None)[::-1][: max(count * 20, count)]
        ranked = [divmod(int(f), len(B)) for f in flat]
    except ImportError:  # sin numpy (no pasa en FreeCAD)
        scored = [(dist(a[2], b[2]), i, j) for i, a in enumerate(A) for j, b in enumerate(B)]
        scored.sort(reverse=True)
        ranked = [(i, j) for _d, i, j in scored[: count * 20]]
    chosen, seen = [], set()
    for i, j in ranked:  # primero uno por cada par de items distinto
        key = (A[i][0], B[j][0])
        if key not in seen:
            seen.add(key)
            chosen.append((i, j))
        if len(chosen) >= count:
            return chosen
    for pair in ranked:
        if pair not in chosen:
            chosen.append(pair)
        if len(chosen) >= count:
            break
    return chosen


def refine(ia, pa, ib, pb, steps_a=None, steps_b=None):
    """
    Afinado: mueve los parámetros de los dos lados mientras la distancia crezca (búsqueda por
    patrones, pasos que se achican a la mitad). Devuelve (d, pa, pb, punto a, punto b).
    """
    na, nb = ia.dims(), ib.dims()
    lo = ia.lo + ib.lo
    hi = ia.hi + ib.hi
    x = list(pa) + list(pb)
    span = [h - l for l, h in zip(lo, hi)]
    step = list(steps_a or [s / SAMPLES_1D for s in span[:na]]) + list(steps_b or [s / SAMPLES_1D for s in span[na:]])

    def value(params):
        a, b = tuple(params[:na]), tuple(params[na:])
        if not ia.ok(a) or not ib.ok(b):
            return None
        try:
            return dist(ia.pos(a), ib.pos(b))
        except Exception:
            return None

    best = value(x)
    if best is None or not x:
        pa_, pb_ = tuple(pa), tuple(pb)
        p, q = ia.pos(pa_), ib.pos(pb_)
        return dist(p, q), pa_, pb_, p, q
    for _it in range(MAX_ITER):
        improved = False
        for k in range(len(x)):
            for sign in (1.0, -1.0):
                trial = list(x)
                trial[k] = min(hi[k], max(lo[k], x[k] + sign * step[k]))
                if trial[k] == x[k]:
                    continue
                v = value(trial)
                if v is not None and v > best + 1e-13:
                    x, best, improved = trial, v, True
        if not improved:
            step = [s * 0.5 for s in step]
            if all(s <= max(sp, 1e-12) * REL_TOL for s, sp in zip(step, span)):
                break
    a, b = tuple(x[:na]), tuple(x[na:])
    p, q = tuple(ia.pos(a)), tuple(ib.pos(b))
    return dist(p, q), a, b, p, q


def max_between(items_a, items_b):
    """Distancia máxima entre dos grupos de Item: (d, punto a, punto b)."""
    A, n1a, n2a = _cloud(items_a)
    B, n1b, n2b = _cloud(items_b)
    if not A or not B:
        return None
    best = None
    for i, j in _top_pairs(A, B, CANDIDATES):
        ka, pa, _p = A[i]
        kb, pb, _q = B[j]
        ia, ib = items_a[ka], items_b[kb]
        sa = [(h - l) / (n1a if ia.dims() == 1 else n2a) for l, h in zip(ia.lo, ia.hi)]
        sb = [(h - l) / (n1b if ib.dims() == 1 else n2b) for l, h in zip(ib.lo, ib.hi)]
        found = refine(ia, pa, ib, pb, sa, sb)
        if best is None or found[0] > best[0]:
            best = found
    return best[0], best[3], best[4]


# --- Formas de FreeCAD -> Item --------------------------------------------------


def _vec(v):
    return (v.x, v.y, v.z)


def _is_line(edge):
    try:
        return type(edge.Curve).__name__ in ("Line", "LineSegment")
    except Exception:  # curva sin definir
        return True


def _is_plane(face):
    return type(face.Surface).__name__ == "Plane"


def _edge_items(edge, points, items):
    if getattr(edge, "Degenerated", False):  # polo de una esfera: arista de largo cero
        for v in edge.Vertexes:
            points.append(_vec(v.Point))
        return
    for v in edge.Vertexes:
        points.append(_vec(v.Point))
    if not _is_line(edge):
        items.append(Item(lambda p, e=edge: _vec(e.valueAt(p[0])), (edge.FirstParameter,), (edge.LastParameter,)))


def _face_items(face, points, items, tol=1e-7):
    for edge in face.Edges:
        _edge_items(edge, points, items)
    if not _is_plane(face):
        u0, u1, v0, v1 = face.ParameterRange

        def inside(p, f=face):
            return f.isInside(f.valueAt(p[0], p[1]), tol, True)

        items.append(Item(lambda p, f=face: _vec(f.valueAt(p[0], p[1])), (u0, v0), (u1, v1), inside))


def items_of(shape):
    """Lo que puede tener el máximo: vértices + curvas y superficies curvas."""
    points, items = [], []
    st = shape.ShapeType
    if st == "Vertex":
        points.append(_vec(shape.Point))
    elif st == "Edge":
        _edge_items(shape, points, items)
    elif st == "Face":
        _face_items(shape, points, items)
    else:
        if shape.Faces:
            for face in shape.Faces:
                _face_items(face, points, items)
        elif shape.Edges:
            for edge in shape.Edges:
                _edge_items(edge, points, items)
        else:
            points += [_vec(v.Point) for v in shape.Vertexes]
    unique = {tuple(round(c, 9) for c in p): p for p in points}
    return [Item.point(p) for p in unique.values()] + items


def _full_circle(shape):
    """(centro, normal, radio) si es un círculo completo, si no None."""
    if shape.ShapeType != "Edge" or type(shape.Curve).__name__ not in ("Circle", "ArcOfCircle"):
        return None
    if not shape.isClosed():
        return None
    c = shape.Curve
    return _vec(c.Center), _vec(c.Axis), c.Radius


def max_distance(a, b):
    """Distancia máxima entre dos formas de FreeCAD (en su posición real): (d, punto a, punto b)."""
    ca, cb = _full_circle(a), _full_circle(b)
    if a.ShapeType == "Vertex" and cb:
        d, far = max_point_circle(_vec(a.Point), *cb)
        return d, _vec(a.Point), far
    if b.ShapeType == "Vertex" and ca:
        d, far = max_point_circle(_vec(b.Point), *ca)
        return d, far, _vec(b.Point)
    if ca and cb:
        n1, n2 = _unit(ca[1]), _unit(cb[1])
        same_plane = abs(abs(_dot(n1, n2)) - 1) < 1e-9 and abs(_dot(_sub(cb[0], ca[0]), n1)) < 1e-7
        if same_plane:
            return max_coplanar_circles(ca[0], ca[2], cb[0], cb[2], n1)
    return max_between(items_of(a), items_of(b))
