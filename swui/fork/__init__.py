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


def install():
    """Enganchar los agregados del fork. Cada uno protegido por separado."""
    try:
        from swui.fork import panel_sw

        panel_sw.install()
    except Exception:
        FreeCAD.Console.PrintError("[SWUI fork] Panel de tareas a la izquierda:\n%s\n" % traceback.format_exc())
