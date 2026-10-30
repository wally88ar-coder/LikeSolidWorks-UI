# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Términos de SOLIDWORKS 2018 en los diálogos de FreeCAD que quedan nativos:
Saliente/Corte barrido, Hélice, Plano / Eje / Punto de referencia, y la caja
"vista previa" que FreeCAD agrega a varios diálogos.

Como swui/feature_terms.py del original (que hace lo mismo con Extruir y
Revolución), solo cambia textos: los diálogos y su lógica siguen siendo de
FreeCAD. Diferencias: los textos de acá ya están en castellano (el fork es en
castellano) y las listas se traducen por texto, no por posición, porque varias
cambian de largo según el croquis (ejes del croquis, referencias agregadas).
Un texto que no está en la tabla queda como lo puso FreeCAD.

Además, "selección siempre activa" donde FreeCAD la deja apagada: en el
barrido con el perfil ya elegido, el botón del trayecto queda prendido para
que el próximo clic en el croquis del trayecto lo tome (como SW, que pasa solo
a la casilla Trayecto).
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

WB_NAME = "LikeSolidWorksUIWorkbench"
POLL_MS = 400

# root (objectName en Windows usa "__"): {"title", "labels": {objectName: texto}, "combos": {objectName: {texto: texto}}}
DIALOGS = {
    "PartDesignGui::TaskPipeParameters": {
        "labels": {
            "groupprofile": "Perfil",
            "buttonProfileBase": "Elegir perfil",
            "label_2": "Esquinas:",
            "groupBox": "Trayecto",
            "buttonSpineBase": "Elegir trayecto",
            "buttonRefAdd": "Agregar aristas",
            "buttonRefRemove": "Quitar aristas",
        },
        "combos": {
            "comboBoxTransition": {"Transformado": "Transformadas", "Transformed": "Transformadas",
                                   "Right corner": "En ángulo recto", "Round corner": "Redondeadas"},
        },
    },
    "PartDesignGui::TaskPipeOrientation": {
        "labels": {"label_2": "Tipo de orientación/torsión:"},
        "combos": {
            "comboBoxMode": {"Estándar": "Seguir trayecto", "Standard": "Seguir trayecto",
                             "Fijo": "Mantener normal constante", "Fixed": "Mantener normal constante",
                             "Ángulo fijo": "Frenet", "Frenet": "Frenet",
                             "Auxiliar": "Curva guía auxiliar", "Auxiliary": "Curva guía auxiliar",
                             "Binormal": "Binormal"},
        },
    },
    "PartDesignGui::TaskPipeScaling": {
        "labels": {"label_2": "Secciones:"},
        "combos": {
            "comboBoxScaling": {"Constante": "Una sola sección", "Constant": "Una sola sección",
                                "Multisección": "Varias secciones", "Multisection": "Varias secciones"},
        },
    },
    "PartDesignGui::TaskHelixParameters": {
        "labels": {
            "labelAxis": "Eje:",
            "labelInputMode": "Definido por:",
            "labelPitch": "Paso:",
            "labelHeight": "Altura:",
            "labelTurns": "Revoluciones:",
            "labelConeAngle": "Ángulo de cono:",
            "labelGrowth": "Incremento por vuelta:",
            "checkBoxLeftHanded": "Sentido antihorario (rosca izquierda)",
            "checkBoxReversed": "Invertir dirección",
        },
        "combos": {
            "axis": {"Normal al  boceto": "Normal al croquis", "Normal al boceto": "Normal al croquis",
                     "Normal sketch axis": "Normal al croquis",
                     "Eje vertical del croquis": "Eje vertical del croquis",
                     "Eje horizontal del croquis": "Eje horizontal del croquis",
                     "Eje X base": "Eje X", "Eje Y base": "Eje Y", "Eje Z base": "Eje Z",
                     "Seleccionar referencia…": "Elegir arista o eje…",
                     "Select reference…": "Elegir arista o eje…"},
            "inputMode": {"Paso-Altura-Ángulo": "Altura y paso",
                          "Paso-Vueltas-Ángulo": "Paso y revolución",
                          "Altura-Vueltas-Ángulo": "Altura y revolución",
                          "Paso-Altura-Incremento": "Altura y paso variable"},
        },
    },
    "PartGui::TaskAttacher": {
        "labels": {
            "label": "Tipo de relación:",
            "labelOffsetX": "En X:",
            "labelOffsetY": "En Y:",
            "labelOffsetZ": "En Z (desfase):",
            "labelRoll": "Giro en X:",
            "labelPitch": "Giro en Y:",
            "labelYaw": "Giro en Z:",
            "checkBoxFlip": "Invertir lado",
        },
        "combos": {},
    },
    "PartDesignGui::TaskPreviewParameters": {
        "labels": {
            "showFinalCheckBox": "Mostrar el resultado final",
            "showTransparentPreviewCheckBox": "Mostrar la vista previa superpuesta",
        },
        "combos": {},
    },
}


# Encabezados de las cajas del panel de tareas que FreeCAD 1.1.4 deja en inglés (vistos con el
# mouse en el barrido, 2026-10-30). Textos de SW 2018 donde los hay.
HEADERS = {
    "Pipe Parameters": "Perfil y trayecto",
    "Pipe parameters": "Perfil y trayecto",
    "Section Orientation": "Opciones",
    "Section orientation": "Opciones",
    "Section Transformation": "Transformación de la sección",
    "Helix parameters": "Parámetros de hélice",
    "Helix Parameters": "Parámetros de hélice",
}


def translate_headers(mw):
    """
    Encabezados del panel de tareas en castellano (solo los de la tabla). El encabezado de
    cada caja es un botón (QSint::ActionLabel), no una etiqueta: se miran los dos.
    """
    for kind in (QtWidgets.QLabel, QtWidgets.QAbstractButton):
        for widget in mw.findChildren(kind):
            text = widget.text()
            if text in HEADERS:
                widget.setText(HEADERS[text])


def root_names(name):
    """FreeCAD en Windows usa '__' en vez de '::' en los objectName."""
    return (name, name.replace("::", "__"))


def translate_items(items, table):
    """Textos de una lista -> los de SW; los que no están en la tabla quedan igual."""
    return [table.get(t, t) for t in items]


def _apply_root(root, spec):
    for name, text in spec["labels"].items():
        for w in root.findChildren(QtWidgets.QWidget, name):
            if isinstance(w, QtWidgets.QGroupBox):
                if w.title() != text:
                    w.setTitle(text)
            elif hasattr(w, "setText") and hasattr(w, "text"):
                # el botón de una referencia cambia su texto mientras elige ("Selecting…"): no pisar eso
                busy = isinstance(w, (QtWidgets.QPushButton, QtWidgets.QToolButton)) and w.isChecked()
                if w.text() != text and not busy:
                    w.setText(text)
    for name, table in spec["combos"].items():
        for combo in root.findChildren(QtWidgets.QComboBox, name):
            for i in range(combo.count()):
                old = combo.itemText(i)
                new = table.get(old, old)
                if new != old:
                    combo.setItemText(i, new)


def _path_active(root):
    """Barrido: si el perfil ya está y el trayecto no, dejar prendido "Elegir trayecto"."""
    if root.property("swui_path_armed"):
        return
    try:
        vp = FreeCADGui.ActiveDocument.getInEdit()
        obj = vp.Object if vp is not None else None
    except Exception:
        obj = None
    if obj is None or not hasattr(obj, "Spine") or obj.Spine or not obj.Profile:
        return
    for button in root.findChildren(QtWidgets.QAbstractButton, "buttonSpineBase"):
        if not button.isEnabled() or not button.isVisible():
            return  # todavía armándose: probar en el próximo tick (antes se daba por hecho)
        if button.isCheckable() and not button.isChecked():
            button.click()
        root.setProperty("swui_path_armed", True)


def tick():
    try:
        if FreeCADGui.activeWorkbench().name() != WB_NAME or not FreeCADGui.Control.activeDialog():
            return
    except Exception:
        return
    try:
        mw = FreeCADGui.getMainWindow()
        translate_headers(mw)
        for name, spec in DIALOGS.items():
            for root_name in root_names(name):
                for root in mw.findChildren(QtWidgets.QWidget, root_name):
                    _apply_root(root, spec)
                    if name == "PartDesignGui::TaskPipeParameters":
                        _path_active(root)
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Términos SW en diálogos:\n%s\n" % traceback.format_exc())
        _timer.stop()


_timer = None


# Nombres en el árbol que la tabla del original no trae (quedaba "AdditiveHelix"). SW arma la
# hélice como curva + barrido; acá es una operación sola, con el nombre del botón.
# Clave alemana como las del original (i18n.tree busca "Baum|<clave>" en cada idioma).
TREE_NAMES = {
    "PartDesign::AdditiveHelix": ("Helix", {"en": "Helix", "es": "Hélice"}),
    "PartDesign::SubtractiveHelix": ("Helix-Schnitt", {"en": "Cut-Helix", "es": "Cortar-Hélice"}),
}


def add_tree_names():
    from swui import i18n, naming
    langs = i18n.languages()
    for type_id, (key, names) in TREE_NAMES.items():
        naming.FEATURE_NAMES.setdefault(type_id, key)
        for code, mod in langs.items():
            mod.TEXTS.setdefault(i18n.TREE + key, names.get(code, names["en"]))


def install():
    global _timer
    add_tree_names()
    if _timer is None:
        _timer = QtCore.QTimer()
        _timer.setInterval(POLL_MS)
        _timer.timeout.connect(tick)
        _timer.start()
