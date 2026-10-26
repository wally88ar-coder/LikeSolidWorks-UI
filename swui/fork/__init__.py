# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Agregados propios de este fork (no van al original de Dominik).

Todo lo del fork vive en este paquete y se engancha desde un solo lugar
(install(), llamado en InitGui.Initialize), así los cambios del original
se pueden incorporar sin conflictos.
"""

import traceback

import FreeCAD


MENU = "LikeSolidWorks UI"


def install(workbench=None):
    """Enganchar los agregados del fork. Cada uno protegido por separado."""
    try:
        from swui.fork import look_sw

        look_sw.install()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Aspecto SW 2018:\n%s\n" % traceback.format_exc())
    try:
        from swui.fork import quick_access

        quick_access.install()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Acceso rápido:\n%s\n" % traceback.format_exc())
    try:
        from swui.fork import panel_sw

        panel_sw.install()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Panel de tareas a la izquierda:\n%s\n" % traceback.format_exc())
    try:
        from swui.fork import orbit_speed

        orbit_speed.install()
        if workbench is not None:
            workbench.appendMenu(MENU, [orbit_speed.COMMAND])
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Velocidad de giro:\n%s\n" % traceback.format_exc())
    try:
        from swui.fork import view_keys

        view_keys.install()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Teclas N y F:\n%s\n" % traceback.format_exc())
    try:
        from swui.fork import feature_tree, folder_check, rebuild_keys, repair_refs, step_copy, tree_overlay

        feature_tree.install()
        rebuild_keys.install()
        tree_overlay.install()
        step_copy.install()
        repair_refs.install()
        folder_check.install()
        if workbench is not None:
            workbench.appendMenu(MENU, [rebuild_keys.REBUILD, rebuild_keys.FORCE_REBUILD,
                                        rebuild_keys.WHATS_WRONG, repair_refs.COMMAND, step_copy.COMMAND,
                                        folder_check.COMMAND])
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Árbol de operaciones:\n%s\n" % traceback.format_exc())
    try:
        from swui.fork import instant_dims

        instant_dims.install()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Cotas con doble clic:\n%s\n" % traceback.format_exc())
    try:
        from swui.fork import dress_up_panel, hole_panel, pattern_panel

        dress_up_panel.install()
        pattern_panel.install()
        hole_panel.install()
        from swui.fork import ref_plane_panel

        ref_plane_panel.install()
        from swui.fork import ref_axis_point_panel

        ref_axis_point_panel.install()
        from swui.fork import native_terms

        native_terms.install()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Paneles de operación SW:\n%s\n" % traceback.format_exc())
    try:
        from swui.fork import sketch_model_edges

        sketch_model_edges.install()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Aristas del modelo en el croquis:\n%s\n" % traceback.format_exc())
    try:
        from swui.fork import equations, evaluate_tab, mass_props, material, measure_sw, tree_strip

        material.install()
        mass_props.install()
        equations.install()
        measure_sw.install()
        evaluate_tab.install()
        tree_strip.install()
        if workbench is not None:
            workbench.appendMenu(MENU, [measure_sw.COMMAND, mass_props.COMMAND, equations.COMMAND,
                                        material.COMMAND])
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Evaluar (material, propiedades físicas, ecuaciones, "
                                   "medir):\n%s\n" % traceback.format_exc())
    try:
        from swui.fork import multibody

        multibody.install()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Multicuerpo (fusionar resultado, alcance):\n%s\n"
                                   % traceback.format_exc())
    try:
        from swui.fork import always_swui

        always_swui.install()
        if workbench is not None:
            workbench.appendMenu(MENU, [always_swui.COMMAND])
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Usar siempre LikeSolidWorks UI:\n%s\n" % traceback.format_exc())
