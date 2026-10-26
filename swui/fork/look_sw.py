# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Aspecto claro de SOLIDWORKS 2018 (colores medidos en capturas del usuario, 25.10.).

El original (swui/theme.py, view_background.py, overlay_panels.py) usa un
tema oscuro y el árbol transparente sobre la vista 3D. Acá, sin tocar esos
archivos, se cambian sus tablas antes de que se apliquen:

  - Interfaz: cinta, menú, panel izquierdo y barras #F7F7F7, barra de
    pestañas #D4D4D4, texto oscuro, azul de selección #368EC4.
  - Árbol sobre panel opaco gris claro (no superpuesto): panel_sw.py lo pone
    en pestañas con Tareas, como FeatureManager / PropertyManager. Renglón
    elegido como en SW: celeste #A6C8E3 con borde #4288B5 y texto oscuro.
  - Fondo 3D: degradado #E1E4ED (arriba) -> #D7DCE7 (medio) -> #FEFEFE (abajo).
  - Croquis: azul puro #0000FF (insuficientemente definido), negro (definido),
    líneas de 2 px; constructivas 1 px trazo y punto; resaltado naranja
    #FF8000; aristas de sólidos nuevos 1 px negras.

Todas son preferencias de FreeCAD: se guardan antes y se devuelven al salir
de LikeSolidWorks UI (mismo mecanismo que view_background.py del original;
las del croquis con una copia propia, SKETCH_BACKUP_KEY).
"""

import json

import FreeCAD

COLORS = {
    "window": "#f7f7f7",
    "panel": "#f7f7f7",
    "ribbon": "#f7f7f7",
    "ribbon_tabbar": "#d4d4d4",
    "border": "#c4c4c4",
    "text": "#1e1e1e",
    "text_dim": "#3e3e3e",
    "text_disabled": "#a5a5a5",
    "accent": "#368ec4",
    "hover": "#d9e8f5",
    "pressed": "#b7d4ee",
    "selection": "#368ec4",
    "tree_text": "#1e1e1e",
    "tree_selection": "#a6c8e3",  # renglón elegido en el FeatureManager de SW 2018
    "tree_selection_line": "#4288b5",
    "view_top": "#e1e4ed",
    "view_mid": "#d7dce7",
    "view_bottom": "#fefefe",
    "sketch_open": "#0000ff",
    "sketch_defined": "#000000",
    "sketch_construction": "#0000ff",
    "sketch_construction_defined": "#000000",
    "sketch_dim": "#000000",
    "sketch_dim_driven": "#7a7a7a",
    "sketch_relation": "#1e7d32",
    "preselect": "#ff8000",
    "edge": "#000000",
}

# Además de lo que ya pone view_background.py (grupo View)
EXTRA_VIEW = [
    ("Bool", "UseBackgroundColorMid", True),
    ("Unsigned", "BackgroundColor4", "view_mid"),  # color del medio del degradado
    ("Unsigned", "EditedVertexColor", "sketch_open"),
    ("Unsigned", "HighlightColor", "preselect"),  # al pasar el mouse
    ("Unsigned", "SelectionColor", "selection"),
    ("Unsigned", "DefaultShapeLineColor", "edge"),
    ("Int", "DefaultShapeLineWidth", 1),
]

KEEP_TOOLBARS = ("Workbench",)  # el original deja también "File" y "Edit"

SKETCH_PARAMS ="User parameter:BaseApp/Preferences/Mod/Sketcher/View"
SKETCH_BACKUP_KEY = "SketcherViewBackup"
DASH_DOT = 0xFFC6  # trazo largo, hueco, punto, hueco (16 bits)
SKETCH_VALUES = [
    ("Int", "EdgeWidth", 2),
    ("Int", "ConstructionWidth", 1),
    ("Int", "ConstructionPattern", DASH_DOT),
    ("Int", "InternalWidth", 1),
]

TREE_QSS = (
    "QTreeView { background: %(panel)s; color: %(tree_text)s; border: none; }"
    "QTreeView::item { color: %(tree_text)s; }"
    "QTreeView::item:selected { background: %(tree_selection)s; color: %(tree_text)s;"
    " border: 1px solid %(tree_selection_line)s; }"
)

# Se agrega al final del estilo del original (theme.build_qss)
EXTRA_QSS = """
/* ---------- fork: aspecto claro SW 2018 ---------- */
QDockWidget#Model, QDockWidget#Tasks {
    background: %(panel)s;
}
QDockWidget#Model QTreeView {
    background: %(panel)s;
    color: %(tree_text)s;
}
QMainWindow > QTabBar {
    background: %(ribbon_tabbar)s;
}
QMainWindow > QTabBar::tab {
    background: %(ribbon_tabbar)s;
    color: %(text)s;
    min-width: 70px;
}
QMainWindow > QTabBar::tab:selected {
    background: %(panel)s;
    color: %(text)s;
}
QTabWidget#SWUI_RibbonTabs QTabBar::tab {
    color: %(text)s;
}
QTabWidget#SWUI_RibbonTabs QTabBar::tab:selected {
    font-weight: bold;
}
QStatusBar {
    background: %(window)s;
}
"""


def install():
    """Cambiar las tablas del original antes de que layout.enter() las aplique."""
    from swui import layout, overlay_panels, theme, view_background

    # Sin las barras Archivo (nuevo/abrir/guardar) y Editar (deshacer/rehacer/recalcular):
    # quedan los menús y los atajos (Ctrl+N/O/S/Z/Y, F5... ). Solo el selector de bancos se
    # conserva como salida (always_swui.py lo oculta mientras está activo).
    layout.KEEP_TOOLBARS = KEEP_TOOLBARS
    theme.COLORS.update(COLORS)
    if not getattr(theme.build_qss, "_swui_look", False):
        original_qss = theme.build_qss

        def build_qss(c=None, _original=original_qss):
            colors = dict(theme.COLORS, **(c or {}))
            return _original(c) + "\n" + EXTRA_QSS % colors

        build_qss._swui_look = True
        theme.build_qss = build_qss

    # Árbol: panel fijo, opaco (nada superpuesto sobre la vista 3D)
    overlay_panels.TARGET = tuple(
        (g, k, n, ("" if (g, n) == ("OverlayLeft", "Widgets") else
                   False if (g, n) == ("OverlayLeft", "Transparent") else v))
        for g, k, n, v in overlay_panels.TARGET)
    overlay_panels.TREE_TEXT = COLORS["tree_text"]
    overlay_panels.TREE_QSS = TREE_QSS % COLORS

    if not getattr(view_background._target_values, "_swui_look", False):
        original_targets = view_background._target_values

        def _target_values(_original=original_targets):
            out = {name: (kind, name, value) for kind, name, value in _original()}
            for kind, name, value in EXTRA_VIEW:
                if isinstance(value, str):
                    value = view_background._packed(COLORS[value])
                out[name] = (kind, name, value)
            return list(out.values())

        _target_values._swui_look = True
        view_background._target_values = _target_values

        original_apply, original_restore = view_background.apply, view_background.restore

        def apply(_original=original_apply):
            _original()
            apply_sketch()

        def restore(_original=original_restore):
            restore_sketch()
            _original()

        view_background.apply, view_background.restore = apply, restore
    restore_sketch()  # copia vieja de un cierre inesperado


def apply_sketch():
    grp, own = FreeCAD.ParamGet(SKETCH_PARAMS), FreeCAD.ParamGet(view_params_own())
    if not own.GetString(SKETCH_BACKUP_KEY, ""):
        existing = {name: value for _t, name, value in (grp.GetContents() or [])}
        own.SetString(SKETCH_BACKUP_KEY, json.dumps(
            {name: [kind, name in existing, existing.get(name)] for kind, name, _v in SKETCH_VALUES}))
    for kind, name, value in SKETCH_VALUES:
        getattr(grp, "Set" + kind)(name, value)


def restore_sketch():
    own = FreeCAD.ParamGet(view_params_own())
    raw = own.GetString(SKETCH_BACKUP_KEY, "")
    if not raw:
        return
    grp = FreeCAD.ParamGet(SKETCH_PARAMS)
    for name, (kind, existed, value) in json.loads(raw).items():
        if existed:
            getattr(grp, "Set" + kind)(name, value)
        else:
            getattr(grp, "Rem" + kind)(name)
    own.SetString(SKETCH_BACKUP_KEY, "")


def view_params_own():
    from swui import view_background

    return view_background.OWN_PARAMS
