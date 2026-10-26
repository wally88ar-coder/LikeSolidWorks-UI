# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Asistente para taladro con el flujo de SOLIDWORKS 2018.

FreeCAD pide un croquis previo con los centros. Acá, como en SW:
1. "Asistente para taladro" sin nada elegido: se elige la cara plana (el panel
   "elegir plano o cara" del original, pick_plane.py, ahora también para el
   taladro); se abre el croquis ahí con la herramienta Punto ya puesta
   ("Posiciones"): se marcan los centros y se acotan con lo de siempre.
2. "Salir del croquis": arranca el taladro nativo (PartDesign::Hole) con ese
   croquis y este panel reemplaza a su diálogo ("Tipo"): Refrentado,
   Avellanado, Agujero, Agujero roscado; estándar, tipo de tornillo, tamaño,
   ajuste, condición final, punta... con vista previa.
   "Editar posiciones" vuelve al croquis de los centros.

Por debajo todo es el taladro de FreeCAD (tablas ISO de FreeCAD: diámetros de
paso, refrentados ISO 4762, etc.). Mismo enganche que el redondeo
(dress_up_panel.py): Aceptar confirma, Cancelar deshace.
"""

import json
import os

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets
from swui.fork import dress_up_panel as dp

HOLE = "PartDesign::Hole"
HOLE_COMMAND = "PartDesign_Hole"
POINT_TOOL = "Sketcher_CreatePoint"
POINT_TOOL_DELAY_MS = 700

# Tipos de agujero de SW (orden de SW 2018) -> qué cambia en el Hole de FreeCAD
COUNTERBORE, COUNTERSINK, PLAIN, TAPPED = "cbore", "csink", "hole", "tap"
KINDS = [(COUNTERBORE, "Refrentado"), (COUNTERSINK, "Avellanado"), (PLAIN, "Agujero"), (TAPPED, "Agujero roscado")]

# Estándar de SW -> ThreadType de FreeCAD ("" = sin norma: diámetro a mano)
STANDARDS = [("ISOMetricProfile", "ISO"), ("ISOMetricFineProfile", "ISO rosca fina"),
             ("UNC", "ANSI pulgadas (UNC)"), ("UNF", "ANSI pulgadas (UNF)"), ("None", "Sin norma (diámetro a mano)")]

# Ajuste de SW -> ThreadFit de FreeCAD (métrico / pulgadas)
FITS = [("Ajustado", ("Fine", "Close")), ("Normal", ("Medium", "Normal")), ("Holgado", ("Coarse", "Loose"))]

# Tornillos de las tablas de FreeCAD, con nombre como en SW
SCREWS = {
    "ISO 4762": "Cabeza cilíndrica allen (ISO 4762)",
    "ISO 4762 + 7089": "Cabeza cilíndrica allen + arandela (ISO 4762 + 7089)",
    "DIN 7984": "Cabeza cilíndrica baja allen (DIN 7984)",
    "ISO 12474": "Cabeza cilíndrica allen fina (ISO 12474)",
    "ISO 14583": "Cabeza alomada torx (ISO 14583)",
    "ISO 14583 (partial)": "Cabeza alomada torx, parcial (ISO 14583)",
    "ISO 10642": "Cabeza avellanada allen (ISO 10642)",
    "ISO 2009": "Cabeza avellanada ranurada (ISO 2009)",
    "ISO 7046": "Cabeza avellanada Phillips (ISO 7046)",
}
# Si no se pueden leer las tablas de FreeCAD (lo leído en 1.1.4)
CUT_TYPES = {"ISO 4762": COUNTERBORE, "ISO 4762 + 7089": COUNTERBORE, "DIN 7984": COUNTERBORE,
             "ISO 12474": COUNTERBORE, "ISO 14583": COUNTERBORE, "ISO 14583 (partial)": COUNTERBORE,
             "ISO 10642": COUNTERSINK, "ISO 2009": COUNTERSINK, "ISO 7046": COUNTERSINK}
GENERIC = {COUNTERBORE: "Counterbore", COUNTERSINK: "Countersink"}
GENERIC_TEXT = "Genérico (medidas a mano)"


# --- Sin FreeCAD (probables en el test) ---------------------------------


def size_text(thread_type, size):
    """'M6x1.0' -> 'M6' en ISO de paso normal (como SW); el resto igual."""
    if thread_type == "ISOMetricProfile" and size.startswith("M") and "x" in size:
        return size.split("x")[0]
    return size


def kind_of(threaded, cut_type, cut_kinds=None):
    """Tipo SW a partir del Hole de FreeCAD."""
    if cut_type in ("Counterbore", "Counterdrill"):
        return COUNTERBORE
    if cut_type == "Countersink":
        return COUNTERSINK
    kinds = cut_kinds or CUT_TYPES
    if cut_type in kinds:
        return kinds[cut_type]
    return TAPPED if threaded else PLAIN


def screws_for(kind, cut_list, cut_kinds=None):
    """Cabezas de tornillo de la lista de FreeCAD que van con este tipo, más la genérica."""
    kinds = cut_kinds or CUT_TYPES
    order = list(SCREWS)  # primero los de uso común (ISO 4762, como el de SW por defecto)
    out = sorted((c for c in cut_list if kinds.get(c) == kind),
                 key=lambda c: order.index(c) if c in order else len(order))
    if kind in GENERIC:
        out.append(GENERIC[kind])
    return out


def fit_index(fit):
    for i, (_text, values) in enumerate(FITS):
        if fit in values:
            return i
    return 1


def nearest_size(sizes, old):
    """Al cambiar de estándar, quedarse con un tamaño parecido (M6 -> M6x0.75...)."""
    head = old.split("x")[0] if old else ""
    for s in sizes:
        if s.split("x")[0] == head:
            return s
    return sizes[0] if sizes else ""


def read_cut_kinds():
    """Tablas de tornillos de FreeCAD: {'ISO 4762': COUNTERBORE, ...}."""
    folder = os.path.join(FreeCAD.getResourceDir(), "Mod", "PartDesign", "Resources", "Hole")
    out = dict(CUT_TYPES)
    try:
        names = os.listdir(folder)
    except Exception:
        return out
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(folder, name), encoding="utf-8") as fh:
                data = json.load(fh)
            out[data["name"]] = COUNTERSINK if data.get("cut_type") == "countersink" else COUNTERBORE
        except Exception:
            pass
    return out


# --- Panel -------------------------------------------------------------


def _narrow(combo):
    """Lista que no ensancha el panel (los nombres de tornillo son largos; 1366 px)."""
    combo.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(12)
    return combo


class HolePanel(dp.SwPanel):
    TRANSACTION = "Editar taladro"
    FAIL = "FreeCAD no puede hacer el taladro así: revisá la profundidad y los centros del croquis."
    NOTHING = "El croquis de posiciones no tiene centros (puntos o círculos)."

    def __init__(self, obj):
        self.cut_kinds = read_cut_kinds()
        self.filling = False
        if obj.Document.HasPendingTransaction and obj.ThreadType == "None":
            _defaults(obj)  # taladro nuevo: como SW (ISO, M6, agujero pasante normal)
        super().__init__(obj)

    def _sketch(self):
        try:
            return self.obj.Profile[0]
        except Exception:
            return None

    def centers(self):
        sk = self._sketch()
        if sk is None:
            return 0
        n = 0
        for i, g in enumerate(sk.Geometry):
            try:
                if sk.getConstruction(i):
                    continue
            except Exception:
                pass
            if type(g).__name__ in ("Point", "Circle"):
                n += 1
        return n

    # --- interfaz

    def _combo(self, form, label, handler):
        box = _narrow(QtWidgets.QComboBox())
        box.currentIndexChanged.connect(handler)
        lab = QtWidgets.QLabel(label)
        form.addRow(lab, box)
        return box, lab

    def _build(self):
        obj = self.obj
        self.filling = True  # las listas se llenan: que no toquen el objeto todavía
        tabs = QtWidgets.QTabWidget()
        tabs.setWindowTitle("Asistente para taladro")

        # Pestaña Tipo
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        self.kind = _narrow(QtWidgets.QComboBox())
        for key, text in KINDS:
            self.kind.addItem(text, key)
        form.addRow("Tipo de agujero:", self.kind)
        self.standard, _l = self._combo(form, "Estándar:", self._standard_changed)
        for key, text in STANDARDS:
            self.standard.addItem(text, key)
        self.screw, self.screw_label = self._combo(form, "Tipo:", self._changed)
        self.size, self.size_label = self._combo(form, "Tamaño:", self._changed)
        self.fit, self.fit_label = self._combo(form, "Ajuste:", self._changed)
        for text, _values in FITS:
            self.fit.addItem(text)
        self.diameter = self._value_box("Diameter", " mm", 0.1, 10000.0)
        self.diameter_label = QtWidgets.QLabel("Diámetro:")
        form.addRow(self.diameter_label, self.diameter)
        self.info = QtWidgets.QLabel()
        form.addRow(self.info)

        self.custom = QtWidgets.QCheckBox("Mostrar tamaño personalizado")
        self.custom.setChecked(bool(obj.HoleCutCustomValues))
        self.custom.toggled.connect(self._changed)
        form.addRow(self.custom)
        self.cut_diameter = self._value_box("HoleCutDiameter", " mm", 0.1, 10000.0)
        self.cut_depth = self._value_box("HoleCutDepth", " mm", 0.0, 10000.0)
        self.cut_angle = self._value_box("HoleCutCountersinkAngle", "°", 1.0, 179.0)
        self.cut_diameter_label = QtWidgets.QLabel("Ø refrentado:")
        self.cut_depth_label = QtWidgets.QLabel("Prof. refrentado:")
        self.cut_angle_label = QtWidgets.QLabel("Ángulo avellanado:")
        form.addRow(self.cut_diameter_label, self.cut_diameter)
        form.addRow(self.cut_depth_label, self.cut_depth)
        form.addRow(self.cut_angle_label, self.cut_angle)

        self.end = _narrow(QtWidgets.QComboBox())
        self.end.addItem("Hasta profundidad especificada", "Dimension")
        self.end.addItem("Por todo", "ThroughAll")
        self.end.currentIndexChanged.connect(self._changed)
        form.addRow("Condición final:", self.end)
        self.depth = self._value_box("Depth", " mm", 0.01, 100000.0)
        self.depth_label = QtWidgets.QLabel("Profundidad:")
        form.addRow(self.depth_label, self.depth)
        self.point = _narrow(QtWidgets.QComboBox())
        self.point.addItem("Plana", "Flat")
        self.point.addItem("Ángulo de broca", "Angled")
        self.point.currentIndexChanged.connect(self._changed)
        self.point_label = QtWidgets.QLabel("Fondo:")
        form.addRow(self.point_label, self.point)

        self.thread_depth = _narrow(QtWidgets.QComboBox())
        self.thread_depth.addItem("Igual al agujero", "Hole Depth")
        self.thread_depth.addItem("Profundidad dada", "Dimension")
        self.thread_depth.addItem("Según DIN 76", "Tapped (DIN76)")
        self.thread_depth.currentIndexChanged.connect(self._changed)
        self.thread_depth_label = QtWidgets.QLabel("Rosca:")
        form.addRow(self.thread_depth_label, self.thread_depth)
        self.thread_len = self._value_box("ThreadDepth", " mm", 0.01, 100000.0)
        self.thread_len_label = QtWidgets.QLabel("Prof. de rosca:")
        form.addRow(self.thread_len_label, self.thread_len)
        self.modeled = QtWidgets.QCheckBox("Rosca modelada (más pesada; si no, cosmética)")
        self.modeled.setChecked(bool(obj.ModelThread))
        self.modeled.toggled.connect(self._changed)
        form.addRow(self.modeled)
        self.left = QtWidgets.QCheckBox("Rosca izquierda")
        self.left.setChecked(obj.ThreadDirection == "Left")
        self.left.toggled.connect(self._changed)
        form.addRow(self.left)
        self.flip = QtWidgets.QCheckBox("Invertir dirección")
        self.flip.setChecked(bool(obj.Reversed))
        self.flip.toggled.connect(self._changed)
        form.addRow(self.flip)
        tabs.addTab(page, "Tipo")

        # Pestaña Posiciones
        page2 = QtWidgets.QWidget()
        lay2 = QtWidgets.QVBoxLayout(page2)
        self.where = QtWidgets.QLabel()
        self.where.setWordWrap(True)
        lay2.addWidget(self.where)
        edit = QtWidgets.QPushButton("Editar posiciones (croquis)")
        edit.clicked.connect(self.edit_positions)
        lay2.addWidget(edit)
        lay2.addStretch(1)
        tabs.addTab(page2, "Posiciones")

        box = QtWidgets.QWidget()
        box.setWindowTitle("Asistente para taladro")
        outer = QtWidgets.QVBoxLayout(box)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(tabs)
        outer.addWidget(self._message_label())
        self.form = box
        self._load()
        self.kind.currentIndexChanged.connect(self._kind_changed)
        self.filling = False

    def _set_combo(self, combo, data):
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                return True
        return False

    def _load(self):
        """Del Hole de FreeCAD al panel."""
        obj = self.obj
        before, self.filling = self.filling, True
        try:
            self._set_combo(self.kind, kind_of(obj.Threaded, obj.HoleCutType, self.cut_kinds))
            self._set_combo(self.standard, obj.ThreadType)
            self._fill_sizes()
            self._fill_screws()
            self.fit.setCurrentIndex(fit_index(obj.ThreadFit))
            self._set_combo(self.end, obj.DepthType)
            self._set_combo(self.point, obj.DrillPoint)
            self._set_combo(self.thread_depth, obj.ThreadDepthType)
        finally:
            self.filling = before
        self._update_rows()

    def _fill_sizes(self):
        obj = self.obj
        self.size.blockSignals(True)
        self.size.clear()
        kind = self.standard.currentData()
        sizes = [s for s in obj.getEnumerationsOfProperty("ThreadSize") if s != "---"] if kind != "None" else []
        for s in sizes:
            self.size.addItem(size_text(kind, s), s)
        self._set_combo(self.size, obj.ThreadSize)
        self.size.blockSignals(False)

    def _fill_screws(self):
        obj = self.obj
        self.screw.blockSignals(True)
        self.screw.clear()
        kind = self.kind.currentData()
        for cut in screws_for(kind, obj.getEnumerationsOfProperty("HoleCutType"), self.cut_kinds):
            self.screw.addItem(GENERIC_TEXT if cut in GENERIC.values() else SCREWS.get(cut, cut), cut)
        if not self._set_combo(self.screw, obj.HoleCutType) and self.screw.count():
            self.screw.setCurrentIndex(0)
        self.screw.blockSignals(False)

    def _update_rows(self):
        kind = self.kind.currentData()
        norm = self.standard.currentData() != "None"
        cut = kind in (COUNTERBORE, COUNTERSINK)
        generic = cut and self.screw.currentData() in GENERIC.values()
        custom = cut and (generic or self.custom.isChecked())
        tapped = kind == TAPPED
        through = self.end.currentData() == "ThroughAll"
        for w in (self.screw, self.screw_label):
            w.setVisible(cut)
        for w in (self.size, self.size_label):
            w.setVisible(norm)
        for w in (self.fit, self.fit_label):
            w.setVisible(norm and not tapped)
        for w in (self.diameter, self.diameter_label):
            w.setVisible(not norm)
        self.custom.setVisible(cut and not generic)
        for w in (self.cut_diameter, self.cut_diameter_label):
            w.setVisible(custom)
        for w in (self.cut_depth, self.cut_depth_label):
            w.setVisible(custom and kind == COUNTERBORE)
        for w in (self.cut_angle, self.cut_angle_label):
            w.setVisible(custom and kind == COUNTERSINK)
        self.cut_diameter_label.setText("Ø refrentado:" if kind == COUNTERBORE else "Ø avellanado:")
        for w in (self.depth, self.depth_label, self.point, self.point_label):
            w.setVisible(not through)
        for w in (self.thread_depth, self.thread_depth_label, self.modeled, self.left):
            w.setVisible(tapped)
        for w in (self.thread_len, self.thread_len_label):
            w.setVisible(tapped and self.thread_depth.currentData() == "Dimension")
        self.where.setText(self._where_text())

    def _where_text(self):
        sk = self._sketch()
        if sk is None:
            return "Sin croquis de posiciones."
        n = self.centers()
        return ("%d centro%s en %s. Para mover o agregar agujeros: Editar posiciones "
                "(puntos del croquis, acotados como siempre)." % (n, "" if n == 1 else "s", sk.Label))

    # --- cambios

    def _standard_changed(self, *_a):
        if self.filling:
            return
        old = self.obj.ThreadSize
        self._set("ThreadType", self.standard.currentData())
        if self.standard.currentData() != "None":
            sizes = [s for s in self.obj.getEnumerationsOfProperty("ThreadSize") if s != "---"]
            new = nearest_size(sizes, old)
            if new:
                self._set("ThreadSize", new)
        self._fill_sizes()
        self._fill_screws()
        self._changed()

    def _kind_changed(self, *_a):
        if self.filling:
            return
        self._fill_screws()
        self._custom_defaults()
        self._changed()

    def _custom_defaults(self):
        """Refrentado/avellanado a mano sin medidas todavía: unas razonables según el Ø."""
        d = self.obj.Diameter.Value
        if self.cut_diameter.value() <= d:
            self.cut_diameter.setValue(round(d * 1.8, 1))
        if self.cut_depth.value() <= 0.0:
            self.cut_depth.setValue(round(d, 1))

    def _changed(self, *_a):
        if self.filling:
            return
        self._update_rows()
        super()._changed()

    # --- vista previa

    def _apply(self):
        kind = self.kind.currentData()
        self._set("ThreadType", self.standard.currentData())
        if self.standard.currentData() != "None" and self.size.currentData():
            self._set("ThreadSize", self.size.currentData())
            fit = FITS[self.fit.currentIndex()][1]
            fits = self.obj.getEnumerationsOfProperty("ThreadFit")
            self._set("ThreadFit", fit[0] if fit[0] in fits else fit[1])
        else:
            self._set("Diameter", self.diameter.value())
        self._set("Threaded", kind == TAPPED)
        if kind == TAPPED:
            self._set("ModelThread", self.modeled.isChecked())
            self._set("ThreadDirection", "Left" if self.left.isChecked() else "Right")
            self._set("ThreadDepthType", self.thread_depth.currentData())
            if self.thread_depth.currentData() == "Dimension":
                self._set("ThreadDepth", self.thread_len.value())
        cut = self.screw.currentData() if kind in (COUNTERBORE, COUNTERSINK) else "None"
        self._set("HoleCutType", cut or "None")
        if kind in (COUNTERBORE, COUNTERSINK):
            custom = cut in GENERIC.values() or self.custom.isChecked()
            self._set("HoleCutCustomValues", custom)
            if custom:
                self._set("HoleCutDiameter", self.cut_diameter.value())
                if kind == COUNTERBORE:
                    self._set("HoleCutDepth", self.cut_depth.value())
                else:
                    self._set("HoleCutCountersinkAngle", self.cut_angle.value())
        self._set("DepthType", self.end.currentData())
        if self.end.currentData() == "Dimension":
            self._set("Depth", self.depth.value())
            self._set("DrillPoint", self.point.currentData())
        self._set("Reversed", self.flip.isChecked())
        self.info.setText(self._info_text())
        if not self.centers():
            return self.NOTHING
        return ""

    def _info_text(self):
        obj = self.obj
        try:
            text = "Ø del agujero: %s" % dp_fmt(obj.Diameter.Value)
            if obj.HoleCutType not in ("None", ""):
                text += "   Ø cabeza: %s" % dp_fmt(obj.HoleCutDiameter.Value)
            return text
        except Exception:
            return ""

    def _nothing(self):
        return not self.centers()

    def _pick(self, obj, sub):
        return False  # las posiciones van en el croquis

    # --- posiciones

    def edit_positions(self, *_a):
        """Aceptar lo de ahora y abrir el croquis de los centros (como la pestaña Posiciones)."""
        sk = self._sketch()
        if sk is None:
            return
        self.preview()
        if self.valid:
            if not self.accept():
                return
            FreeCADGui.Control.closeDialog()
        else:
            self.reject()
            FreeCADGui.Control.closeDialog()
        QtCore.QTimer.singleShot(100, lambda: _edit_sketch(sk))


DEFAULT_SIZE = "M6x1.0"


def _defaults(obj):
    """Valores de arranque de un taladro nuevo (FreeCAD arranca sin norma)."""
    try:
        obj.ThreadType = "ISOMetricProfile"
        sizes = obj.getEnumerationsOfProperty("ThreadSize")
        obj.ThreadSize = DEFAULT_SIZE if DEFAULT_SIZE in sizes else nearest_size(sizes, "M6")
        obj.ThreadFit = "Medium"
        obj.Threaded = False
        obj.HoleCutType = "None"
    except Exception:
        FreeCAD.Console.PrintWarning("[SWUI fork] Taladro: no se pudieron poner los valores de arranque.\n")


def dp_fmt(value):
    from swui.fork import instant_dims

    return instant_dims.fmt(value) + " mm"


def _edit_sketch(sketch):
    try:
        if sketch.Document is not None:
            FreeCADGui.getDocument(sketch.Document.Name).setEdit(sketch)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Editar posiciones del taladro: no se pudo abrir el croquis.\n")


# --- Enganche: taladro sin nada elegido ----------------------------------


def _point_tool(sketch):
    """En el croquis nuevo del taladro, la herramienta Punto lista (Posiciones de SW)."""
    try:
        vp = FreeCADGui.ActiveDocument.getInEdit()
        if vp is not None and vp.Object == sketch and not sketch.Geometry:
            FreeCADGui.runCommand(POINT_TOOL)
    except Exception:
        pass


def install():
    from swui import pick_plane

    dp.PANELS[HOLE] = HolePanel
    if HOLE_COMMAND not in pick_plane.FEATURE_COMMANDS:
        pick_plane.FEATURE_COMMANDS = tuple(pick_plane.FEATURE_COMMANDS) + (HOLE_COMMAND,)
    arm = pick_plane.arm
    if not getattr(arm, "_swui_hole", False):
        def wrapped(command, sketch):
            arm(command, sketch)
            if command == HOLE_COMMAND:
                QtCore.QTimer.singleShot(POINT_TOOL_DELAY_MS, lambda: _point_tool(sketch))
        wrapped._swui_hole = True
        pick_plane.arm = wrapped
