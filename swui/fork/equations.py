# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Ecuaciones como en SOLIDWORKS: "Ecuaciones, variables globales y cotas" (fase 3).

Una tabla con dos partes, como SW:
- Variables globales: "Largo" = 100, "Ala" = "Largo" / 4 ... (con comentario).
- Ecuaciones: "D1@Croquis1" = "Largo" * 2, "D1@Extruir1" = "Espesor" ...
Columnas Nombre / Valor o ecuación / Se evalúa en / Comentarios. A la derecha, las
cotas del modelo: doble clic las inserta en la celda (o arma una ecuación nueva).
Aceptar guarda todo como un solo paso de deshacer; Cancelar deja todo como estaba.

Por debajo, todo es nativo de FreeCAD (abre sin el addon):
- las variables globales son propiedades de un VarSet (App::VarSet) llamado
  "Variables globales" (nombre interno VARSET_NAME, estable); el comentario es la
  documentación de la propiedad. Se muestran también las de otros VarSet del documento.
- cada ecuación es una expresión de FreeCAD (la f(x) de la casilla).
- nombres de cotas como SW: "D1@Croquis1" (D1, D2... en el orden de las cotas del
  croquis; una cota con nombre propio se llama así). Al usar una cota sin nombre en
  una ecuación se le pone ese nombre (renameConstraint), así la ecuación no se corre
  si se borran cotas. Cotas de operaciones: D1@Extruir1 = profundidad, etc. (FEATURE_DIMS).
- funciones de SW: sqr -> sqrt, atn -> atan, arcsin/arccos, int -> trunc,
  iif(cond; sí; no) -> (cond ? sí : no). Coma decimal como en Argentina.
"""

import re

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

COMMAND = "SWUI_Equations"
VARSET_NAME = "VariablesGlobales"  # nombre interno del VarSet que crea el addon (estable)
VARSET_LABEL = "Variables globales"
VAR_GROUP = "Variables"
SKETCH_DIMS = ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle")
VARSET_BASE = ("ExpressionEngine", "Label", "Label2", "Visibility", "Placement")

# Cotas de operaciones en el orden D1, D2... como las numera SW (propiedades de FreeCAD 1.1.4)
FEATURE_DIMS = {
    "PartDesign::Pad": ("Length", "Length2", "TaperAngle", "TaperAngle2", "Offset"),
    "PartDesign::Pocket": ("Length", "Length2", "TaperAngle", "TaperAngle2", "Offset"),
    "PartDesign::Revolution": ("Angle", "Angle2"),
    "PartDesign::Groove": ("Angle", "Angle2"),
    "PartDesign::Fillet": ("Radius",),
    "PartDesign::Chamfer": ("Size", "Size2", "Angle"),
    "PartDesign::Draft": ("Angle",),
    "PartDesign::Thickness": ("Value",),
    "PartDesign::Hole": ("Diameter", "Depth", "CounterboreDiameter", "CounterboreDepth",
                         "CountersinkAngle", "DrillPointAngle"),
    "PartDesign::LinearPattern": ("Length", "Occurrences", "Offset", "Length2", "Occurrences2", "Offset2"),
    "PartDesign::PolarPattern": ("Angle", "Occurrences", "Offset"),
    "PartDesign::Helix": ("Pitch", "Height", "Turns", "Angle"),
    "PartDesign::AdditiveHelix": ("Pitch", "Height", "Turns", "Angle"),
    "PartDesign::SubtractiveHelix": ("Pitch", "Height", "Turns", "Angle"),
    "PartDesign::AdditiveBox": ("Length", "Width", "Height"),
    "PartDesign::AdditiveCylinder": ("Radius", "Height"),
    "Part::Box": ("Length", "Width", "Height"),
    "Part::Cylinder": ("Radius", "Height"),
}
ANGLE_PROPS = ("Angle", "Angle2", "TaperAngle", "TaperAngle2", "CountersinkAngle", "DrillPointAngle")
COUNT_PROPS = ("Occurrences", "Occurrences2", "Turns")

SW_FUNCTIONS = {"sqr": "sqrt", "atn": "atan", "arcsin": "asin", "arccos": "acos", "int": "trunc"}

# Referencia de FreeCAD: Objeto.prop / <<Etiqueta>>.prop / Objeto.Constraints.D1 / ...[3]
REF_RE = re.compile(r"(<<[^>]+>>|[A-Za-z_][A-Za-z0-9_]*)((?:\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])+)")
QUOTED_RE = re.compile(r'"([^"]+)"')

_open = []


# --- Nombres de cotas como SW ---------------------------------------------


def sketch_dim_names(constraints):
    """
    {índice: nombre SW} de las cotas de un croquis. constraints = [(Tipo, Nombre)].
    Las cotas con nombre lo conservan; las otras son D1, D2... en orden, sin repetir nombres.
    """
    used = set(n for t, n in constraints if n)
    out, k = {}, 0
    for i, (kind, name) in enumerate(constraints):
        if kind not in SKETCH_DIMS:
            continue
        if name:
            out[i] = name
            continue
        k += 1
        while "D%d" % k in used:
            k += 1
        out[i] = "D%d" % k
        used.add(out[i])
    return out


def feature_dim_names(type_id, props):
    """{propiedad: 'D1'...} de una operación (solo las propiedades que tiene)."""
    names = [p for p in FEATURE_DIMS.get(type_id, ()) if p in props]
    return {p: "D%d" % (i + 1) for i, p in enumerate(names)}


def sw_function_names(text):
    """sqr( -> sqrt( etc. (palabras enteras)."""
    def repl(m):
        return SW_FUNCTIONS[m.group(1).lower()] + "("
    return re.sub(r"\b(sqr|atn|arcsin|arccos|int)\s*\(", repl, text, flags=re.IGNORECASE)


def _split_args(inner):
    """Argumentos de iif separados por ';' (o ',' si no hay ';'), respetando paréntesis."""
    sep = ";" if ";" in inner else ","
    out, depth, cur = [], 0, ""
    for ch in inner:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == sep and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [a.strip() for a in out]


def convert_iif(text):
    """iif(cond; a; b) de SW -> ((cond) ? (a) : (b)) de FreeCAD (también anidados)."""
    while True:
        m = re.search(r"\biif\s*\(", text, flags=re.IGNORECASE)
        if not m:
            return text
        start, i, depth = m.start(), m.end(), 1
        while i < len(text) and depth:
            depth += {"(": 1, ")": -1}.get(text[i], 0)
            i += 1
        if depth:
            return text  # paréntesis sin cerrar: que lo diga FreeCAD
        args = _split_args(text[m.end():i - 1])
        if len(args) != 3:
            return text
        args = [convert_iif(a) for a in args]
        text = text[:start] + "((%s) ? (%s) : (%s))" % tuple(args) + text[i:]


def decimal_points(text):
    """'2,5' -> '2.5' (coma decimal entre dígitos; fuera de comillas)."""
    parts = re.split(r'("[^"]*")', text)
    return "".join(p if p.startswith('"') else re.sub(r"(\d),(\d)", r"\1.\2", p) for p in parts)


def to_freecad(text, resolve):
    """
    Ecuación como en SW -> expresión de FreeCAD. resolve(nombre) -> referencia de FreeCAD
    o None. Devuelve (expresión, [nombres que no existen]).
    """
    unknown = []
    body = decimal_points(text.strip().lstrip("="))

    def repl(m):
        ref = resolve(m.group(1).strip())
        if ref is None:
            unknown.append(m.group(1))
            return m.group(0)
        return ref

    body = QUOTED_RE.sub(repl, body)
    body = convert_iif(sw_function_names(body))
    return body.strip(), unknown


def to_sw(expr, name_of, local=None):
    """
    Expresión de FreeCAD -> como en SW. name_of(objeto, ruta) -> nombre SW o None.
    local = {propiedad: nombre SW} para las referencias sin objeto (FreeCAD escribe "Largo"
    en vez de "VariablesGlobales.Largo" dentro del mismo VarSet).
    """
    def repl(m):
        name = name_of(m.group(1), m.group(2))
        return '"%s"' % name if name else m.group(0)

    text = REF_RE.sub(repl, expr or "")
    if local:
        parts = re.split(r'("[^"]*")', text)
        word = re.compile(r"(?<![\w.])([A-Za-z_][A-Za-z0-9_]*)(?![\w(.])")
        parts = [p if p.startswith('"') else word.sub(lambda m: '"%s"' % local[m.group(1)]
                                                       if m.group(1) in local else m.group(0), p)
                 for p in parts]
        text = "".join(parts)
    # 2.5 -> 2,5 fuera de las comillas
    parts = re.split(r'("[^"]*")', text)
    return "".join(p if p.startswith('"') else re.sub(r"(\d)\.(\d)", r"\1,\2", p) for p in parts)


def fmt(value, unit=""):
    if value is None:
        return ""
    text = ("%.6f" % value).rstrip("0").rstrip(".").replace(".", ",")
    if text == "-0":
        text = "0"
    return text + (" " + unit if unit else "")


# --- Documento ----------------------------------------------------------


class Model:
    """Variables globales, cotas y ecuaciones de un documento, con nombres SW."""

    def __init__(self, doc):
        self.doc = doc

    # objetos y nombres

    def varsets(self):
        return [o for o in self.doc.Objects if o.TypeId == "App::VarSet"]

    def main_varset(self, create=False):
        for vs in self.varsets():
            if vs.Name == VARSET_NAME or vs.Label == VARSET_LABEL:
                return vs
        if not create:
            return self.varsets()[0] if self.varsets() else None
        vs = self.doc.addObject("App::VarSet", VARSET_NAME)
        vs.Label = VARSET_LABEL
        return vs

    def variables(self):
        """[(varset, propiedad)] de todas las variables globales."""
        out = []
        for vs in self.varsets():
            for prop in vs.PropertiesList:
                if prop in VARSET_BASE or vs.getGroupOfProperty(prop) == "Base":
                    continue
                out.append((vs, prop))
        return out

    def var_display(self, vs, prop):
        main = self.main_varset()
        return prop if vs is main else "%s@%s" % (prop, vs.Label)

    def _object(self, token, owner=None):
        if token.startswith("<<") and token.endswith(">>"):
            found = self.doc.getObjectsByLabel(token[2:-2])
            return found[0] if found else None
        return self.doc.getObject(token)

    def name_of(self, obj, path):
        """(objeto, ruta de FreeCAD) -> nombre SW ('D1@Croquis1', 'Largo') o None."""
        path = path if path.startswith((".", "[")) else "." + path
        if obj.TypeId == "App::VarSet":
            prop = path.lstrip(".")
            return self.var_display(obj, prop) if prop in obj.PropertiesList else None
        if obj.TypeId == "Sketcher::SketchObject":
            index = self._constraint_index(obj, path)
            if index is None:
                return None
            names = sketch_dim_names([(c.Type, c.Name) for c in obj.Constraints])
            name = names.get(index)
            return "%s@%s" % (name, obj.Label) if name else None
        prop = path.lstrip(".")
        names = feature_dim_names(obj.TypeId, obj.PropertiesList)
        if prop in names:
            return "%s@%s" % (names[prop], obj.Label)
        return "%s@%s" % (prop, obj.Label) if prop in obj.PropertiesList else None

    def _constraint_index(self, sketch, path):
        m = re.match(r"^\.Constraints(?:\.([A-Za-z_][A-Za-z0-9_]*)|\[(\d+)\])$", path)
        if not m:
            return None
        if m.group(2) is not None:
            i = int(m.group(2))
            return i if i < len(sketch.Constraints) else None
        for i, c in enumerate(sketch.Constraints):
            if c.Name == m.group(1):
                return i
        return None

    def name_of_ref(self, token, path, owner=None):
        obj = self._object(token)
        if obj is None and owner is not None:  # referencia local: Constraints.D1 del mismo objeto
            obj, path = owner, "." + token + path
        return self.name_of(obj, path) if obj is not None else None

    def resolve(self, name, rename=True):
        """Nombre SW -> referencia de FreeCAD ('Sketch.Constraints.D1', 'VariablesGlobales.Largo')."""
        target = self.target(name, rename)
        if target is None:
            return None
        obj, path = target
        return obj.Name + (path if path.startswith((".", "[")) else "." + path)

    def target(self, name, rename=False):
        """Nombre SW -> (objeto, ruta de FreeCAD) o None. Con rename, pone nombre a la cota."""
        if "@" not in name:
            for vs, prop in self.variables():
                if self.var_display(vs, prop) == name:
                    return vs, prop
            return None
        short, label = name.split("@", 1)
        found = self.doc.getObjectsByLabel(label)
        if not found:
            return None
        obj = found[0]
        if obj.TypeId == "App::VarSet":
            return (obj, short) if short in obj.PropertiesList else None
        if obj.TypeId == "Sketcher::SketchObject":
            names = sketch_dim_names([(c.Type, c.Name) for c in obj.Constraints])
            for index, n in names.items():
                if n == short:
                    if not obj.Constraints[index].Name:
                        if not rename:
                            return obj, ".Constraints[%d]" % index
                        obj.renameConstraint(index, short)
                    return obj, ".Constraints." + short
            return None
        names = feature_dim_names(obj.TypeId, obj.PropertiesList)
        for prop, n in names.items():
            if n == short:
                return obj, prop
        return (obj, short) if short in obj.PropertiesList else None

    # valores

    def value(self, obj, path):
        """(valor, unidad) actual de una cota o variable."""
        try:
            if obj.TypeId == "Sketcher::SketchObject":
                index = self._constraint_index(obj, path if path.startswith(".") else "." + path)
                c = obj.Constraints[index]
                if c.Type == "Angle":
                    import math

                    return math.degrees(c.Value), "°"
                return c.Value, "mm"
            prop = path.lstrip(".")
            v = getattr(obj, prop)
        except Exception:
            return None, ""
        if hasattr(v, "Value") and hasattr(v, "Unit"):
            text = str(v.Unit)
            if prop in ANGLE_PROPS or "Angle" in text:
                return v.getValueAs("deg").Value, "°"
            if "Length" in text:
                return v.getValueAs("mm").Value, "mm"
            return v.Value, ""
        if isinstance(v, (int, float)):
            return float(v), ""
        return None, ""

    def expressions(self):
        """[(objeto, ruta, expresión)] de todo el documento, salvo las de las variables globales."""
        out = []
        for obj in self.doc.Objects:
            if obj.TypeId == "App::VarSet" or hasattr(obj, "SWUI_ScopeOf"):
                continue  # las copias de un corte en otro sólido (multibody.py) siguen al original solas
            for path, expr in getattr(obj, "ExpressionEngine", []):
                out.append((obj, path, expr))
        return out

    def expression_of(self, obj, path):
        for p, e in getattr(obj, "ExpressionEngine", []):
            if p == path or p == "." + path.lstrip(".") or p.lstrip(".") == path.lstrip("."):
                return e
        return None

    def sw_expr(self, obj, expr):
        local = None
        if obj.TypeId == "App::VarSet":
            local = {p: self.var_display(obj, p) for p in obj.PropertiesList if p not in VARSET_BASE}
        return to_sw(expr, lambda tok, path: self.name_of_ref(tok, path, obj), local)

    def all_dims(self):
        """[(nombre SW, objeto, ruta, valor, unidad)] de las cotas del modelo (para insertar)."""
        out = []
        for obj in self.doc.Objects:
            if obj.TypeId == "Sketcher::SketchObject":
                names = sketch_dim_names([(c.Type, c.Name) for c in obj.Constraints])
                for index, n in names.items():
                    path = ".Constraints[%d]" % index
                    value, unit = self.value(obj, path)
                    out.append(("%s@%s" % (n, obj.Label), obj, path, value, unit))
            else:
                names = feature_dim_names(obj.TypeId, obj.PropertiesList)
                for prop, n in sorted(names.items(), key=lambda p: int(p[1][1:])):
                    value, unit = self.value(obj, prop)
                    if value is not None and self._relevant(obj, prop, value, n):
                        out.append(("%s@%s" % (n, obj.Label), obj, prop, value, unit))
        return out

    def _relevant(self, obj, prop, value, name):
        """¿Mostrar esta cota de operación? (los números D1, D2... no cambian aunque no se muestre)."""
        if name == "D1" or self.expression_of(obj, prop):
            return True
        if prop in ("Length2", "Angle2"):
            return getattr(obj, "Type", "") in ("TwoLengths", "TwoAngles")
        return bool(value)

    # cambios

    def set_variable(self, name, text, comment=None):
        """Crea o cambia una variable global. text: '100', '2,5' o '= "Largo" / 2'."""
        if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            raise ValueError("El nombre «%s» no sirve: solo letras sin acento, números y _, "
                             "empezando con letra." % name)
        target = self.target(name)
        if target is None:
            vs = self.main_varset(create=True)
            vs.addProperty("App::PropertyFloat", name, VAR_GROUP, comment or "")
            target = (vs, name)
        vs, prop = target
        text = (text or "").strip()
        if text.startswith("="):
            expr, unknown = to_freecad(text, lambda n: self.resolve(n))
            if unknown:
                raise ValueError("No existe: %s" % ", ".join('"%s"' % u for u in unknown))
            vs.setExpression(prop, expr)
        else:
            from swui.fork.material import parse_number

            number = parse_number(text)
            if number is None:
                raise ValueError("«%s» no es un número (para una fórmula, empezá con =)." % text)
            vs.setExpression(prop, None)
            setattr(vs, prop, number)
        if comment is not None:
            vs.setDocumentationOfProperty(prop, comment)
        return vs, prop

    def set_equation(self, name, text):
        """Ecuación sobre una cota: '"D1@Croquis1"' = text. text vacío la borra."""
        target = self.target(name, rename=True)
        if target is None:
            raise ValueError("No existe la cota «%s»." % name)
        obj, path = target
        if not (text or "").strip().lstrip("="):
            obj.setExpression(path, None)
            return obj, path
        expr, unknown = to_freecad(text, lambda n: self.resolve(n))
        if unknown:
            raise ValueError("No existe: %s" % ", ".join('"%s"' % u for u in unknown))
        obj.setExpression(path, expr)
        return obj, path

    def remove_variable(self, vs, prop):
        users = [o.Label for o in self.doc.Objects for _p, e in getattr(o, "ExpressionEngine", [])
                 if re.search(r"\b%s\.%s\b" % (re.escape(vs.Name), re.escape(prop)), e)
                 or ("<<%s>>.%s" % (vs.Label, prop)) in e]
        if users:
            raise ValueError("La usan: %s. Sacala primero de esas ecuaciones." % ", ".join(sorted(set(users))))
        vs.removeProperty(prop)


def count(doc):
    """Cantidad de variables globales + ecuaciones (para la franja del árbol)."""
    model = Model(doc)
    return len(model.variables()) + len(model.expressions())


# --- Ventana ------------------------------------------------------------

HEAD, VAR, NEW_VAR, EQ, NEW_EQ = "head", "var", "new_var", "eq", "new_eq"


def show_dialog(doc=None):
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return None
    for d in list(_open):
        d.reject()
    dialog = _EquationsDialog(doc)
    _open.append(dialog)
    dialog.finished.connect(lambda *_a: _open.remove(dialog) if dialog in _open else None)
    dialog.show()
    dialog.raise_()
    return dialog


class _EquationsDialog(QtWidgets.QDialog):
    def __init__(self, doc):
        super().__init__(FreeCADGui.getMainWindow())
        self.doc = doc
        self.model = Model(doc)
        self.rows = []  # [(tipo, datos)] por renglón de la tabla
        self.filling = False
        self.setWindowTitle("Ecuaciones, variables globales y cotas")
        self.setModal(True)  # un solo paso de deshacer: mientras está abierta no se toca otra cosa
        self.resize(900, 460)
        doc.openTransaction("Ecuaciones")
        box = QtWidgets.QVBoxLayout(self)
        split = QtWidgets.QHBoxLayout()
        box.addLayout(split, 1)
        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Nombre", "Valor / Ecuación", "Se evalúa en", "Comentarios"])
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 170)
        self.table.setColumnWidth(1, 260)
        self.table.setColumnWidth(2, 110)
        self.table.itemChanged.connect(self._edited)
        self.table.installEventFilter(self)
        split.addWidget(self.table, 3)
        right = QtWidgets.QVBoxLayout()
        right.addWidget(QtWidgets.QLabel("Cotas del modelo (doble clic: insertar)"))
        self.dims = QtWidgets.QListWidget()
        self.dims.itemDoubleClicked.connect(self._insert_dim)
        right.addWidget(self.dims, 1)
        split.addLayout(right, 1)
        self.msg = QtWidgets.QLabel("Valor: un número (100 o 2,5). Ecuación: empieza con =, por ejemplo "
                                    '= "Largo" / 2. Supr borra el renglón elegido.')
        self.msg.setWordWrap(True)
        box.addWidget(self.msg)
        row = QtWidgets.QHBoxLayout()
        b_del = QtWidgets.QPushButton("Eliminar renglón")
        b_del.clicked.connect(lambda *_a: self._delete_row())
        b_ok = QtWidgets.QPushButton("Aceptar")
        b_cancel = QtWidgets.QPushButton("Cancelar")
        b_ok.clicked.connect(self.accept)
        b_cancel.clicked.connect(self.reject)
        row.addWidget(b_del)
        row.addStretch(1)
        row.addWidget(b_ok)
        row.addWidget(b_cancel)
        box.addLayout(row)
        self._fill()

    # --- tabla

    def _item(self, text, editable=False, bold=False, grey=False):
        item = QtWidgets.QTableWidgetItem(text)
        flags = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable
        if editable:
            flags |= QtCore.Qt.ItemFlag.ItemIsEditable
        item.setFlags(flags)
        if bold:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
        if grey:
            item.setForeground(QtGui.QBrush(QtGui.QColor("#808080")))
        return item

    def _add_row(self, kind, data, cells):
        r = self.table.rowCount()
        self.table.insertRow(r)
        for col, item in enumerate(cells):
            self.table.setItem(r, col, item)
        self.rows.append((kind, data))

    def _fill(self):
        self.filling = True
        self.table.setRowCount(0)
        self.rows = []
        m = self.model
        self._add_row(HEAD, None, [self._item("Variables globales", bold=True)] + [self._item("") for _ in range(3)])
        for vs, prop in m.variables():
            expr = m.expression_of(vs, prop)
            value, _u = m.value(vs, prop)
            shown = "= " + m.sw_expr(vs, expr) if expr else fmt(value)
            self._add_row(VAR, (vs, prop), [
                self._item('"%s"' % m.var_display(vs, prop)), self._item(shown, editable=True),
                self._item(fmt(value)), self._item(vs.getDocumentationOfProperty(prop) or "", editable=True)])
        self._add_row(NEW_VAR, None, [self._item("Agregar variable global", editable=True, grey=True),
                                      self._item("", editable=True), self._item(""), self._item("", editable=True)])
        self._add_row(HEAD, None, [self._item("Ecuaciones", bold=True)] + [self._item("") for _ in range(3)])
        for obj, path, expr in m.expressions():
            name = m.name_of(obj, path) or "%s@%s" % (path.lstrip("."), obj.Label)
            value, unit = m.value(obj, path)
            state = "Error" if "Invalid" in getattr(obj, "State", []) else fmt(value, unit)
            self._add_row(EQ, (obj, path), [self._item('"%s"' % name), self._item("= " + m.sw_expr(obj, expr), editable=True),
                                           self._item(state), self._item("")])
        self._add_row(NEW_EQ, None, [self._item("Agregar ecuación", editable=True, grey=True),
                                     self._item("", editable=True), self._item(""), self._item("")])
        self.filling = False
        self._fill_dims()

    def _fill_dims(self):
        self.dims.clear()
        locked = set((o.Name, p.lstrip(".")) for o, p, _e in self.model.expressions())
        for name, obj, path, value, unit in self.model.all_dims():
            mark = "Σ " if (obj.Name, path.lstrip(".")) in locked or self.model.expression_of(obj, path) else ""
            item = QtWidgets.QListWidgetItem("%s%s = %s" % (mark, name, fmt(value, unit)))
            item.setData(QtCore.Qt.ItemDataRole.UserRole, name)
            self.dims.addItem(item)

    # --- edición

    def _edited(self, item):
        if self.filling:
            return
        r, col = item.row(), item.column()
        kind, data = self.rows[r]
        name_cell = self.table.item(r, 0).text().strip().strip('"')
        value_text = self.table.item(r, 1).text().strip()
        try:
            if kind == VAR and col == 3:
                data[0].setDocumentationOfProperty(data[1], item.text())
                return
            if kind == VAR and col == 1:
                self.model.set_variable(self.model.var_display(*data), value_text)
            elif kind == NEW_VAR:
                if not value_text or name_cell == "Agregar variable global":
                    return
                comment = self.table.item(r, 3).text()
                self.model.set_variable(name_cell, value_text, comment)
            elif kind == EQ and col == 1:
                name = self.model.name_of(*data)
                self.model.set_equation(name, value_text)
            elif kind == NEW_EQ:
                if not value_text or name_cell == "Agregar ecuación":
                    return
                self.model.set_equation(name_cell, value_text)
            else:
                return
        except Exception as exc:
            self.msg.setText("No se aplicó: %s" % exc)
            self.msg.setStyleSheet("color: #c00000;")
            return
        self.msg.setText("Aplicado.")
        self.msg.setStyleSheet("")
        self.doc.recompute()
        QtCore.QTimer.singleShot(0, self._fill)

    def _insert_dim(self, item):
        name = item.data(QtCore.Qt.ItemDataRole.UserRole)
        r = self.table.currentRow()
        kind = self.rows[r][0] if 0 <= r < len(self.rows) else None
        editor_text = '"%s"' % name
        if kind == NEW_EQ and self.table.item(r, 0).text().strip() in ("", "Agregar ecuación"):
            self.table.item(r, 0).setText(editor_text)  # cota a la que se le pone la ecuación
            self.table.setCurrentCell(r, 1)
            self.table.editItem(self.table.item(r, 1))
            return
        if kind in (VAR, NEW_VAR, EQ, NEW_EQ):
            cell = self.table.item(r, 1)
            text = cell.text() or "= "
            if not text.strip().startswith("="):
                text = "= " + text
            cell.setText(text.rstrip() + " " + editor_text)
            return
        # sin renglón elegido: ecuación nueva sobre esa cota
        last = len(self.rows) - 1
        self.filling = True
        self.table.item(last, 0).setText(editor_text)
        self.filling = False
        self.table.setCurrentCell(last, 1)
        self.table.editItem(self.table.item(last, 1))

    def _delete_row(self):
        r = self.table.currentRow()
        if not 0 <= r < len(self.rows):
            return
        kind, data = self.rows[r]
        try:
            if kind == VAR:
                self.model.remove_variable(*data)
            elif kind == EQ:
                data[0].setExpression(data[1], None)
            else:
                return
        except Exception as exc:
            self.msg.setText("No se borró: %s" % exc)
            self.msg.setStyleSheet("color: #c00000;")
            return
        self.doc.recompute()
        self._fill()

    def eventFilter(self, obj, event):
        if (obj is self.table and event.type() == QtCore.QEvent.Type.KeyPress
                and event.key() == QtCore.Qt.Key.Key_Delete and self.table.state() != QtWidgets.QAbstractItemView.State.EditingState):
            self._delete_row()
            return True
        return False

    # --- cerrar

    def accept(self):
        self.doc.commitTransaction()
        self.doc.recompute()
        _changed()
        super().accept()

    def reject(self):
        self.doc.abortTransaction()
        self.doc.recompute()
        _changed()
        super().reject()


_listeners = []


def add_listener(fn):
    if fn not in _listeners:
        _listeners.append(fn)


def _changed():
    for fn in list(_listeners):
        try:
            fn()
        except Exception:
            pass


class _EquationsCommand:
    def GetResources(self):
        from swui import paths

        return {"MenuText": "Ecuaciones...", "ToolTip": "Ecuaciones, variables globales y cotas (como SW)",
                "Pixmap": paths.icon("fork/equations") or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        show_dialog()


def install():
    try:
        FreeCADGui.addCommand(COMMAND, _EquationsCommand())
    except Exception:
        pass  # ya registrado
