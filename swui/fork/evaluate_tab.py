# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Lo que el fork agrega a la cinta. Pestaña Evaluar con las herramientas de la fase 3 (como el
CommandManager de SW): Medir (el del fork en lugar de Std_Measure), Propiedades físicas,
Ecuaciones y Editar material. Pestaña Operaciones: Combinar (multicuerpo). Cambia las tablas
del original (ribbon_layout.EVALUIEREN / FEATURES) desde afuera, antes de que se arme la cinta;
el test (tools/test_load.py, parte "fork") lee esta tabla.
"""

# Reemplazos en la cinta del original: comando del original -> (comando, texto, opciones)
REPLACE = {
    "Std_Measure": ("SWUI_Measure", "Messen", {"svg": "fork/measure"}),
}

# Grupo nuevo, después de Medir (textos en castellano, sin tr(): convención del fork)
GROUP = [
    ("SWUI_MassProperties", "Propiedades\nfísicas", {"svg": "fork/mass"}),
    ("SWUI_Equations", "Ecuaciones", {"svg": "fork/equations"}),
    ("SWUI_Material", "Editar\nmaterial", {"svg": "fork/material"}),
]


# Pestaña Operaciones: multicuerpo (combinar.py / dividir), en la columna chica de "Cuerpo"
FEATURES_ADD = [
    ("SWUI_Combine", "Combinar", {"svg": "fork/combine"}),
]


def install_features():
    from swui import ribbon_layout

    for group in ribbon_layout.FEATURES[1]:
        for entry in group:
            if isinstance(entry, dict) and any(isinstance(e, tuple) and e[0] == "PartDesign_Body"
                                               for e in entry.get("stack", ())):
                for add in FEATURES_ADD:
                    if add not in entry["stack"]:
                        entry["stack"].append(add)
                return
    ribbon_layout.FEATURES[1].append(list(FEATURES_ADD))


def install():
    install_features()
    from swui import ribbon_layout

    groups = ribbon_layout.EVALUIEREN[1]
    if any(GROUP[0] in g for g in groups):
        return  # ya está
    for gi, group in enumerate(groups):
        for ei, entry in enumerate(group):
            if isinstance(entry, tuple) and entry[0] in REPLACE:
                group[ei] = REPLACE[entry[0]]
                if GROUP not in groups:
                    groups.insert(gi + 1, list(GROUP))
                return
    groups.insert(0, list(GROUP))  # sin Medir en la tabla: al principio
