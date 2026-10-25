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
        from swui.fork import always_swui

        always_swui.install()
        if workbench is not None:
            workbench.appendMenu(MENU, [always_swui.COMMAND])
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Usar siempre LikeSolidWorks UI:\n%s\n" % traceback.format_exc())
