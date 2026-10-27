# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Pestaña Chapa de la cinta (fase 1), como la de SW: Brida base, Brida de arista, Dobladillo,
Extruir corte, Convertir en chapa, Aplanar y Exportar DXF. Se suma a la tabla del original (ribbon_layout.TABS) desde afuera, después de
Croquis; el test (tools/test_load.py, parte "fork") lee esta tabla.
"""

TITLE = "Chapa"

GROUPS = [
    [
        ("SWUI_SMBaseFlange", "Brida\nbase", {"svg": "fork/sm_base_flange"}),
        ("SWUI_SMEdgeFlange", "Brida de\narista", {"svg": "fork/sm_edge_flange"}),
        ("SWUI_SMHem", "Dobladillo", {"svg": "fork/sm_hem"}),
    ],
    [
        ("SWUI_SMCut", "Extruir\ncorte", {"svg": "sketch/f_pocket"}),
        ("SWUI_SMConvert", "Convertir\nen chapa", {"svg": "fork/sm_convert"}),
    ],
    [
        ("SWUI_SMFlatten", "Aplanar", {"svg": "fork/sm_flatten"}),
        ("SWUI_SMExportDXF", "Exportar\nDXF", {"svg": "fork/sm_dxf"}),
    ],
]


def install():
    from swui import ribbon_layout

    if any(title == TITLE for title, _g in ribbon_layout.TABS):
        return
    after = next((i for i, (title, _g) in enumerate(ribbon_layout.TABS)
                  if title == ribbon_layout.SKIZZE[0]), len(ribbon_layout.TABS) - 1)
    ribbon_layout.TABS.insert(after + 1, (TITLE, [list(g) for g in GROUPS]))
