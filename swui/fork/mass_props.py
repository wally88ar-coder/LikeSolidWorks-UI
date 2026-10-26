# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Propiedades físicas como en SOLIDWORKS (fase 3, pestaña Evaluar).

Ventana no modal con el mismo informe que SW: densidad, masa (kg), volumen, área,
centro de masa, ejes y momentos principales (en el centro de masa), momentos de
inercia en el centro de masa (Lxx...) y en el origen (Ixx...). Pieza entera, o
lo elegido (cara/operación -> su cuerpo; en ensamblaje, el componente). En un
ensamblaje suma cada pieza con su material, en su posición real.

Cuentas: OpenCASCADE da por sólido volumen, área, centro y matriz de inercia en el
centro con densidad 1 (forma de tensor: fuera de la diagonal, -∫xy). SW muestra los
productos de inercia como +∫xy dm: acá se muestran igual que SW (decisión anotada en
docs/ESTADO.md para verificar con una pieza en L). La densidad sale de material.py
(material de la biblioteca, la copia guardada en la pieza, o 1000 kg/m³ como SW).

FreeCAD 1.1.4 no trae esta herramienta; la 26.3 trae Std_MassProperties: si existe,
el comando la usa (decisión del proyecto: ceder a lo nativo).
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

COMMAND = "SWUI_MassProperties"
NATIVE = "Std_MassProperties"  # FreeCAD 26.3+
PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI/MassProperties"
DEFAULT_DECIMALS = 3
MAX_DEPTH = 12

_open = []


# --- Cuentas (sin FreeCAD, probables en el test) -----------------------


def _zeros():
    return [[0.0] * 3 for _ in range(3)]


def shift(inertia_cm, mass, d):
    """Steiner: tensor en el centro de masa -> tensor en un punto a distancia d del centro."""
    dd = d[0] ** 2 + d[1] ** 2 + d[2] ** 2
    out = _zeros()
    for i in range(3):
        for j in range(3):
            out[i][j] = inertia_cm[i][j] + mass * ((dd if i == j else 0.0) - d[i] * d[j])
    return out


def combine(items):
    """
    items = [(volumen mm³, área mm², centro (x,y,z) mm, tensor 3x3 en su centro con densidad 1,
    densidad kg/mm³)]. Devuelve dict: mass, volume, area, center, inertia_cm (tensor kg·mm²
    en el centro de masa del total), inertia_origin (tensor en el origen).
    """
    mass = volume = area = 0.0
    moment = [0.0, 0.0, 0.0]
    for vol, ar, c, _t, rho in items:
        m = vol * rho
        mass += m
        volume += vol
        area += ar
        for k in range(3):
            moment[k] += m * c[k]
    if mass <= 0:
        return None
    center = [moment[k] / mass for k in range(3)]
    total = _zeros()
    for vol, _ar, c, tensor, rho in items:
        m = vol * rho
        own = [[tensor[i][j] * rho for j in range(3)] for i in range(3)]
        moved = shift(own, m, [c[k] - center[k] for k in range(3)])
        for i in range(3):
            for j in range(3):
                total[i][j] += moved[i][j]
    origin = shift(total, mass, [-center[0], -center[1], -center[2]])
    return {"mass": mass, "volume": volume, "area": area, "center": center,
            "inertia_cm": total, "inertia_origin": origin}


def sw_matrix(tensor):
    """Tensor (fuera de la diagonal -∫xy) -> como lo muestra SW (+∫xy)."""
    return [[tensor[i][j] if i == j else -tensor[i][j] for j in range(3)] for i in range(3)]


def principal(tensor):
    """Momentos principales (de menor a mayor) y sus ejes, como SW (Ix <= Iy <= Iz)."""
    try:
        import numpy

        values, vectors = numpy.linalg.eigh(numpy.array(tensor, dtype=float))
        axes = [list(vectors[:, k]) for k in range(3)]
        values = list(values)
    except ImportError:  # sin numpy (no pasa en FreeCAD): solo la diagonal
        values = [tensor[k][k] for k in range(3)]
        axes = [[1.0 if i == k else 0.0 for i in range(3)] for k in range(3)]
    out = []
    for value, axis in sorted(zip(values, axes), key=lambda p: p[0]):
        # sentido como SW: la componente más grande positiva
        big = max(range(3), key=lambda i: abs(axis[i]))
        if axis[big] < 0:
            axis = [-a for a in axis]
        out.append((value, [a if abs(a) > 1e-12 else 0.0 for a in axis]))
    return out


def fmt(value, decimals=DEFAULT_DECIMALS):
    """Número con coma decimal y punto de miles como en Argentina ('1.234,567')."""
    if value is None:
        return "-"
    if abs(value) < 0.5 * 10 ** -decimals:
        value = 0.0
    text = "{:,.{d}f}".format(value, d=decimals)
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def density_text(rhos, decimals=DEFAULT_DECIMALS):
    """Densidad en kg/m³ (una sola, o 'varias')."""
    values = sorted(set(round(r * 1e9, 6) for r in rhos))
    if not values:
        return "-"
    if len(values) > 1:
        return "varias (%s kg/m³)" % " / ".join(fmt(v, 2) for v in values)
    return "%s kilogramos por metro cúbico" % fmt(values[0], 2)


def report(result, rhos, names, notes, decimals=DEFAULT_DECIMALS):
    """Informe con el mismo orden y textos que el de SW."""
    f = lambda v: fmt(v, decimals)
    if result is None:
        return "No hay sólidos para calcular."
    c = result["center"]
    lines = ["Propiedades físicas de: %s" % ", ".join(names), "",
             "Sistema de coordenadas de salida: -- predeterminado --", "",
             "Densidad = %s" % density_text(rhos, decimals), "",
             "Masa = %s kilogramos" % f(result["mass"]), "",
             "Volumen = %s milímetros^3" % f(result["volume"]), "",
             "Área de superficie = %s milímetros^2" % f(result["area"]), "",
             "Centro de masa: ( milímetros )",
             "\tX = %s" % f(c[0]), "\tY = %s" % f(c[1]), "\tZ = %s" % f(c[2]), "",
             "Ejes principales de inercia y momentos principales de inercia: ( kilogramos * milímetros^2 )",
             "Medido desde el centro de masa."]
    for (value, axis), axis_name, moment_name in zip(principal(result["inertia_cm"]), "xyz", ("Px", "Py", "Pz")):
        lines.append("\t I%s = (%s, %s, %s)   \t%s = %s" % (axis_name, fmt(axis[0], 4), fmt(axis[1], 4),
                                                         fmt(axis[2], 4), moment_name, f(value)))
    lines += ["", "Momentos de inercia: ( kilogramos * milímetros^2 )",
              "Obtenidos en el centro de masa y alineados con el sistema de coordenadas de salida."]
    lines += _matrix_lines("L", sw_matrix(result["inertia_cm"]), f)
    lines += ["", "Momentos de inercia: ( kilogramos * milímetros^2 )",
              "Medido desde el sistema de coordenadas de salida."]
    lines += _matrix_lines("I", sw_matrix(result["inertia_origin"]), f)
    if notes:
        lines += ["", "Notas:"] + ["\t" + n for n in notes]
    return "\n".join(lines)


def _matrix_lines(letter, m, f):
    axes = "xyz"
    return ["\t" + "\t".join("%s%s%s = %s" % (letter, axes[i], axes[j], f(m[i][j])) for j in range(3))
            for i in range(3)]


# --- Piezas y ensamblajes -------------------------------------------------


def _solid_items(shape, rho):
    out = []
    for solid in shape.Solids:
        if solid.Volume <= 0:
            continue
        c = solid.CenterOfMass
        m = solid.MatrixOfInertia
        tensor = [[m.A11, m.A12, m.A13], [m.A21, m.A22, m.A23], [m.A31, m.A32, m.A33]]
        out.append((solid.Volume, solid.Area, (c.x, c.y, c.z), tensor, rho))
    return out


def _is_assembly(obj):
    return getattr(obj, "TypeId", "") == "Assembly::AssemblyObject"


def _visible(parent, sub, obj):
    try:
        state = parent.isElementVisible(sub.rstrip("."))
        if state in (0, 1):
            return bool(state)
    except Exception:
        pass
    return bool(getattr(obj, "Visibility", True))


def _walk(root, path, obj, hidden, out, depth=0):
    """Piezas (objeto con material, ruta desde root) dentro de un ensamblaje o App::Part."""
    from swui.fork import material

    if depth > MAX_DEPTH:
        return
    linked = obj.getLinkedObject(True) if hasattr(obj, "getLinkedObject") else obj
    if material.is_part_object(linked):
        out.append((linked, root, path))
        return
    try:
        subs = obj.getSubObjects()
    except Exception:
        subs = []
    for sub in subs:
        try:
            child = obj.getSubObject(sub, retType=1)
        except Exception:
            child = None
        if child is None:
            continue
        if not hidden and not _visible(obj, sub, child):
            continue
        _walk(root, path + sub, child, hidden, out, depth + 1)


def components(doc, hidden=True):
    """[(pieza, raíz, ruta)] de todo el documento (pieza suelta: raíz = ella, ruta '')."""
    from swui.fork import material

    out = []
    roots = [o for o in doc.Objects if not o.InList]
    asm = [o for o in roots if _is_assembly(o) or o.TypeId == "App::Part"]
    if asm:
        for root in asm:
            _walk(root, "", root, hidden, out)
        return out
    for obj in material.part_objects(doc):
        if hidden or getattr(obj, "Visibility", True):
            out.append((obj, obj, ""))
    return out


def selected_components(doc):
    """Lo elegido -> [(pieza, raíz, ruta)]: cara u operación -> su cuerpo; en ensamblaje, el componente."""
    from swui.fork import material

    out = []
    try:
        sels = FreeCADGui.Selection.getSelectionEx(doc.Name, 0)
    except Exception:
        return out
    for sel in sels:
        root = sel.Object
        for full in (sel.SubElementNames or [""]):
            tokens = [t + "." for t in full.split(".")[:-1]]
            found = None
            path = ""
            for tok in [""] + tokens:
                path += tok
                try:
                    obj = root.getSubObject(path, retType=1) if path else root
                except Exception:
                    obj = None
                if obj is None:
                    break
                linked = obj.getLinkedObject(True) if hasattr(obj, "getLinkedObject") else obj
                if material.is_part_object(linked):
                    found = (linked, root, path)
                    break
                owner = material._owner(linked)
                if owner is not None and not path:  # una operación elegida sola: su cuerpo
                    found = (owner, owner, "")
                    break
            if found and all(found[0] is not f[0] or found[2] != f[2] for f in out):
                out.append(found)
    return out


def _global_shape(obj, root, path):
    import Part

    if not path:
        return Part.getShape(obj)
    return Part.getShape(root, path, needSubElement=False)


def _component_label(obj, root, path):
    """Nombre como en SW: en un ensamblaje el del componente (Pieza1), si no el del sólido."""
    if path:
        try:
            return root.getSubObject(path, retType=1).Label
        except Exception:
            pass
    return obj.Label


def compute(parts):
    """parts = [(pieza, raíz, ruta)] -> (resultado, densidades, nombres, notas)."""
    from swui.fork import material

    items, rhos, names, notes = [], [], [], []
    for obj, root, path in parts:
        rho, source = material.density(obj)
        shape = _global_shape(obj, root, path)
        found = _solid_items(shape, rho)
        if not found:
            notes.append("%s: no tiene sólidos (no se cuenta)." % _component_label(obj, root, path))
            continue
        items += found
        rhos.append(rho)
        name = _component_label(obj, root, path)
        names.append(name)
        if source is None:
            notes.append("%s: sin material, se usó 1000 kg/m³ (como SW)." % name)
        elif source == "copia":
            notes.append("%s: su material falta en la biblioteca; se usó la copia guardada en la pieza." % name)
    return combine(items), rhos, names, notes


# --- Ventana -----------------------------------------------------------


def decimals():
    return FreeCAD.ParamGet(PARAMS).GetInt("Decimals", DEFAULT_DECIMALS)


def show_dialog(doc=None):
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return None
    for d in list(_open):
        d.close()
    dialog = _MassDialog(doc)
    _open.append(dialog)
    dialog.finished.connect(lambda *_a: dialog._cleanup())
    dialog.show()
    dialog.raise_()
    return dialog


class _SelObserver:
    def __init__(self, dialog):
        self.dialog = dialog

    def _later(self, *_a):
        QtCore.QTimer.singleShot(150, self.dialog.recompute)

    addSelection = removeSelection = setSelection = clearSelection = _later


class _MassDialog(QtWidgets.QDialog):
    def __init__(self, doc):
        super().__init__(FreeCADGui.getMainWindow())
        self.doc = doc
        self.marker = None
        self.setWindowTitle("Propiedades físicas")
        self.resize(620, 560)
        box = QtWidgets.QVBoxLayout(self)
        self.lb_sel = QtWidgets.QLabel()
        self.lb_sel.setWordWrap(True)
        box.addWidget(self.lb_sel)
        row = QtWidgets.QHBoxLayout()
        self.cb_hidden = QtWidgets.QCheckBox("Incluir sólidos/componentes ocultos")
        self.cb_hidden.setChecked(True)
        self.cb_hidden.toggled.connect(lambda *_a: self.recompute())
        self.cb_marker = QtWidgets.QCheckBox("Mostrar centro de masa")
        self.cb_marker.setChecked(True)
        self.cb_marker.toggled.connect(lambda *_a: self.recompute())
        row.addWidget(self.cb_hidden)
        row.addWidget(self.cb_marker)
        row.addStretch(1)
        row.addWidget(QtWidgets.QLabel("Decimales:"))
        self.sp_dec = QtWidgets.QSpinBox()
        self.sp_dec.setRange(0, 8)
        self.sp_dec.setValue(decimals())
        self.sp_dec.valueChanged.connect(self._decimals)
        row.addWidget(self.sp_dec)
        box.addLayout(row)
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QtWidgets.QPlainTextEdit.LineWrapMode.NoWrap)
        box.addWidget(self.text, 1)
        buttons = QtWidgets.QHBoxLayout()
        b_copy = QtWidgets.QPushButton("Copiar al portapapeles")
        b_calc = QtWidgets.QPushButton("Recalcular")
        b_close = QtWidgets.QPushButton("Cerrar")
        b_copy.clicked.connect(lambda *_a: QtWidgets.QApplication.clipboard().setText(self.text.toPlainText()))
        b_calc.clicked.connect(lambda *_a: self.recompute())
        b_close.clicked.connect(self.close)
        buttons.addWidget(b_copy)
        buttons.addStretch(1)
        buttons.addWidget(b_calc)
        buttons.addWidget(b_close)
        box.addLayout(buttons)
        self.observer = _SelObserver(self)
        FreeCADGui.Selection.addObserver(self.observer)
        self.recompute()

    def _decimals(self, value):
        FreeCAD.ParamGet(PARAMS).SetInt("Decimals", int(value))
        self.recompute()

    def recompute(self):
        if self.doc is None or self.doc.Name not in FreeCAD.listDocuments():
            return
        parts = selected_components(self.doc)
        if parts:
            self.lb_sel.setText("Elementos seleccionados: " + ", ".join(_component_label(*p) for p in parts)
                                + "   (sin selección: todo el documento)")
        else:
            parts = components(self.doc, self.cb_hidden.isChecked())
            self.lb_sel.setText("Todo el documento (%s). Elegí sólidos o componentes para ver solo esos."
                                % self.doc.Label)
        try:
            result, rhos, names, notes = compute(parts)
        except Exception as exc:
            self.text.setPlainText("No se pudo calcular: %s" % exc)
            return
        self.text.setPlainText(report(result, rhos, names, notes, self.sp_dec.value()))
        self._show_marker(result["center"] if result and self.cb_marker.isChecked() else None)

    def _show_marker(self, center):
        """Símbolo del centro de masa en la vista (como SW), mientras la ventana está abierta."""
        self._hide_marker()
        if center is None:
            return
        try:
            from pivy import coin

            view = FreeCADGui.getDocument(self.doc.Name).ActiveView
            node = coin.SoAnnotation()
            color = coin.SoBaseColor()
            color.rgb = (0.0, 0.35, 0.85)
            style = coin.SoMarkerSet()
            coords = coin.SoCoordinate3()
            coords.point.setValues(0, 1, [tuple(center)])
            style.markerIndex = coin.SoMarkerSet.CIRCLE_FILLED_9_9
            node.addChild(color)
            node.addChild(coords)
            node.addChild(style)
            view.getSceneGraph().addChild(node)
            self.marker = (view, node)
        except Exception:
            self.marker = None

    def _hide_marker(self):
        if self.marker is not None:
            view, node = self.marker
            try:
                view.getSceneGraph().removeChild(node)
            except Exception:
                pass
        self.marker = None

    def _cleanup(self):
        self._hide_marker()
        try:
            FreeCADGui.Selection.removeObserver(self.observer)
        except Exception:
            pass
        if self in _open:
            _open.remove(self)


# --- Comando ----------------------------------------------------------


def has_native():
    try:
        return NATIVE in FreeCADGui.listCommands()
    except Exception:
        return False


class _MassCommand:
    def GetResources(self):
        from swui import paths

        return {"MenuText": "Propiedades físicas", "ToolTip": "Masa, volumen, área, centro de masa e inercia "
                "(como SW), con la densidad del material", "Pixmap": paths.icon("fork/mass") or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        if has_native():
            FreeCADGui.runCommand(NATIVE)
            return
        show_dialog()


def install():
    try:
        FreeCADGui.addCommand(COMMAND, _MassCommand())
    except Exception:
        pass  # ya registrado
