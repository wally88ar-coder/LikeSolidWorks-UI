# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 Dominik Ladewig
"""
SOLIDWORKS-Begriffe in FreeCADs Feature-Dialogen.

Die Dialoge selbst bleiben FreeCADs - samt aller Logik. Ausgetauscht
werden NUR die angezeigten Texte (Beschriftungen und Eintraege von
Auswahllisten), z.B. "Bemaßung" -> "Blind", "Seite 1" -> "Richtung 1".

Woran die Felder erkannt werden: an ihren festen Objektnamen aus FreeCADs
.ui-Dateien (FreeCAD 1.1.4, src/Mod/PartDesign/Gui/TaskPadPocketParameters.ui
und TaskRevolutionParameters.ui). Das ist unabhaengig von der Sprache.

Sprache (Schritt 3, 18.10.): Die Texte unten sind deutsch und zugleich die
Schluessel fuer swui/lang/*.py - apply() setzt sie mit tr() in der
eingestellten Sprache ein (englisch: Begriffe wie im englischen SOLIDWORKS,
Direction 1, End Condition, Blind, Through All ...). Ein Sprachwechsel wirkt
beim naechsten Takt auch in einem schon offenen Dialog.

Sicherheitsregel: Eine Auswahlliste wird nur umbenannt, wenn sie GENAU so
viele Eintraege hat wie in 1.1.4. Aendert eine kuenftige FreeCAD-Version
die Liste, bleiben FreeCADs eigene Texte stehen - lieber unveraendert als
falsch beschriftet.
"""

import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets
from swui.i18n import tr

POLL_MS = 400

# Linear austragen + Linearer Schnitt (gemeinsames Formular)
PAD_POCKET = {
    "root": "PartDesignGui::TaskPadPocketParameters",
    "labels": {
        "sidesLabel": "Richtungen",
        "side1Label": "Richtung 1",
        "side2Label": "Richtung 2",
        "textLabel1": "Endbedingung",
        "typeLabel2": "Endbedingung",
        "labelLength": "Tiefe",
        "labelLength2": "Tiefe",
        "labelOffset": "Abstand von Fläche",
        "labelOffset2": "Abstand von Fläche",
        "labelTaperAngle": "Formschräge",
        "labelTaperAngle2": "Formschräge",
        "checkBoxReversed": "Richtung umkehren",
        "groupBox": "Austragungsrichtung",
        "checkBoxAlongDirection": "Tiefe entlang Skizzennormale",
        "labelEdge": "Richtung / Kante",
    },
    "combos": {
        # Reihenfolge in 1.1.4: Pad = Dimension, To last, To first, Up to face, Up to shape
        #                       Pocket = Dimension, Through all, To first, Up to face, Up to shape
        "changeMode": ["Blind", "Durch alles", "Bis nächste", "Bis Fläche", "Bis Körper"],
        "changeMode2": ["Blind", "Durch alles", "Bis nächste", "Bis Fläche", "Bis Körper"],
        # One sided, Two sided, Symmetric
        "sidesMode": ["Eine Richtung", "Zwei Richtungen", "Mittelebene"],
    },
}

# Rotieren + Rotierter Schnitt
REVOLUTION = {
    "root": "PartDesignGui::TaskRevolutionParameters",
    "labels": {
        "textLabelMode": "Endbedingung",
        "textLabel1": "Rotationsachse",
        "labelAngle": "Winkel",
        "labelAngle2": "Winkel Richtung 2",
        "checkBoxMidplane": "Mittelebene",
        "checkBoxReversed": "Richtung umkehren",
    },
    "combos": {
        # Angle, To last/Through all, To first, Up to face, Two angles
        "changeMode": ["Blind", "Durch alles", "Bis nächste", "Bis Fläche", "Zwei Richtungen"],
    },
}

# Verknuepfung (FreeCAD: Gelenk) - src/Mod/Assembly/Gui/Resources/panels/
# TaskAssemblyCreateJoint.ui. "distanceLabel" bleibt FreeCADs: es wechselt
# je nach Art zwischen Abstand, Radius, Steigung (JointObject.adaptUi).
JOINT = {
    "root": "TaskAssemblyCreateJoint",
    "labels": {
        "offsetLabel": "Versatz",
        "rotationLabel": "Drehung",
        "advancedOffsetCheckbox": "Erweiterte Versätze anzeigen",
        "PushButtonReverse": "Ausrichtung umkehren",
        "groupBox_limits": "Grenzwerte",
        "limitCheckbox1": "Min. Abstand",
        "limitCheckbox2": "Max. Abstand",
        "limitCheckbox3": "Min. Winkel",
        "limitCheckbox4": "Max. Winkel",
        "reverseRotCheckbox": "Drehrichtung umkehren",
    },
    "combos": {
        # Reihenfolge wie JointObject.JointTypes in 1.1.4: Fixed, Revolute,
        # Cylindrical, Slider, Ball, Distance, Parallel, Perpendicular,
        # Angle, RackPinion, Screw, Gears, Belt
        "jointType": [
            "Starr", "Drehgelenk", "Konzentrisch", "Linear", "Kugelgelenk",
            "Deckungsgleich / Abstand", "Parallel", "Senkrecht", "Winkel",
            "Zahnstange", "Schraube", "Zahnrad", "Riemen",
        ],
    },
}

# Komponente einfuegen - TaskAssemblyInsertLink.ui
INSERT = {
    "root": "TaskAssemblyInsertLink",
    "labels": {
        "label1": "Teil nicht in der Liste?",
        "openFileButton": "Datei öffnen …",
    },
    "combos": {},
}

# --- Zeichnungen (9e1): TechDraw-Dialoge des Ansichtslayouts ----------------
# Formulare aus src/Mod/TechDraw/Gui/Task*.ui (1.1.4). TechDraw vergleicht bei
# der Massstabsart an zwei Stellen den ANGEZEIGTEN Text mit "Custom"
# (TaskSectionView.cpp/TaskComplexSection.cpp, enableAll) - das passt schon
# bei deutscher Oberflaeche nicht. _scale_fix gibt das Massstabsfeld bei
# "Benutzerdefiniert" (Index 2) deshalb selbst frei.

SCALE_TYPES = ["Blattmaßstab", "Automatisch", "Benutzerdefiniert"]


def _scale_fix(combo_name, spin_name):
    def fix(root):
        box = root.findChild(QtWidgets.QComboBox, combo_name)
        spin = root.findChild(QtWidgets.QWidget, spin_name)
        if box is None or spin is None:
            return 0
        if box.currentIndex() == 2 and box.isEnabled() and not spin.isEnabled():
            spin.setEnabled(True)
            return 1
        return 0
    return fix


# Standard-Dreiansicht / Projektionsgruppe
PROJ_GROUP = {
    "root": "TechDrawGui::TaskProjGroup",
    "labels": {
        "label": "Maßstab",
        "directionGroupbox": "Ausrichtung der Vorderansicht",
        "secondaryProjGroupbox": "Projizierte Ansichten",
        "label_7": "Projektionsmethode",
        "cbAutoDistribute": "Automatisch anordnen",
        "label_10": "Abstand X",
        "label_11": "Abstand Y",
    },
    "combos": {
        "cmbScaleType": SCALE_TYPES,
        # First angle, Third angle, Page
        "projection": ["Methode 1 (DIN/ISO)", "Methode 3 (amerikanisch)", "Wie Blatt"],
    },
    "tooltips": {
        # Kaestchen der Projektionen (Namen wie im Baum, naming.py)
        "chkView0": "Isometrie links oben",
        "chkView1": "Draufsicht",
        "chkView2": "Isometrie rechts oben",
        "chkView3": "Ansicht von links",
        "chkView4": "Vorderansicht",
        "chkView5": "Ansicht von rechts",
        "chkView6": "Rückansicht",
        "chkView7": "Isometrie links unten",
        "chkView8": "Unteransicht",
        "chkView9": "Isometrie rechts unten",
    },
}

# Schnittansicht
SECTION_VIEW = {
    "root": "TechDrawGui::TaskSectionView",
    "labels": {
        "label_7": "Ausgangsansicht",
        "label_2": "Bezeichnung",
        "label_3": "Maßstabsart",
        "label": "Maßstab",
        "gbOrientation": "Blickrichtung des Schnitts",
        "gbPlane": "Lage der Schnittebene",
        "gbUpdate": "Vorschau",
        "pbUpdateNow": "Jetzt aktualisieren",
        "cbLiveUpdate": "Vorschau sofort aktualisieren",
    },
    "combos": {"cmbScaleType": SCALE_TYPES},
    "after": _scale_fix("cmbScaleType", "sbScale"),
}

# Detailansicht
DETAIL_VIEW = {
    "root": "TechDrawGui::TaskDetail",
    "labels": {
        "label_4": "Ausgangsansicht",
        "label": "Detailansicht",
        "pbDragger": "Detailkreis verschieben",
        "label_9": "Maßstabsart",
        "label_8": "Maßstab",
        "label_7": "Bezeichnung",
        "label_6": "Kreisradius",
        "label_2": "Mittelpunkt X",
        "label_3": "Mittelpunkt Y",
    },
    "combos": {"cbScaleType": SCALE_TYPES},
}

# Ausgerichteter / abgesetzter Schnitt
COMPLEX_SECTION = {
    "root": "TechDrawGui::TaskComplexSection",
    "labels": {
        "groupBox": "Auswahl",
        "label_8": "Zu schneidende Körper",
        "pbSectionObjects": "Auswahl übernehmen",
        "label_9": "Schnittverlauf (Skizze)",
        "pbProfileObject": "Auswahl übernehmen",
        "groupBox_2": "Schnittparameter",
        "label": "Maßstab",
        "label_3": "Maßstabsart",
        "label_7": "Schnittart",
        "label_2": "Bezeichnung",
        "label_5": "Ausgangsansicht",
        "gbOrientation": "Blickrichtung des Schnitts",
        "groupBox_3": "Vorschau",
        "cbLiveUpdate": "Vorschau sofort aktualisieren",
        "pbUpdateNow": "Jetzt aktualisieren",
    },
    "combos": {
        "cmbScaleType": SCALE_TYPES,
        # Offset, Aligned, No parallel
        "cmbStrategy": ["Abgesetzter Schnitt", "Ausgerichteter Schnitt", "Ohne parallele Abschnitte"],
    },
    "after": _scale_fix("cmbScaleType", "sbScale"),
}

# --- Zeichnungen (9e2a): Beschriftungs-Dialoge ---------------------------
# Nicht angefasst werden Knoepfe, deren Text TechDraw je nach Zustand selbst
# umschreibt (Hinweislinie "pbTracker", Schweisssymbol "pbArrowSymbol"/
# "pbOtherSymbol") - sonst waere der Zustand nicht mehr erkennbar.

LINE_STYLES = ["Durchgezogen", "Gestrichelt", "Gepunktet", "Strichpunkt", "Strich-Zweipunkt"]

DIMENSION = {
    "root": "TechDrawGui::TaskDimension",
    "labels": {
        "gbTolerancing": "Maßwert",
        "label_11": "Formatvorgabe",
        "cbArbitrary": "Maßtext überschreiben",
        "label_9": "Nachkommastellen",
        "cbReference": "Hilfsmaß (in Klammern)",
        "gbFormatting": "Toleranz",
        "cbEqualTolerance": "Symmetrische Toleranz (±)",
        "cbArbitraryTolerances": "Toleranztext frei eingeben",
        "label": "Format oberes Abmaß",
        "label_12": "Format unteres Abmaß",
        "cbTheoreticallyExact": "Theoretisch genaues Maß (Rahmen)",
        "label_2": "Oberes Abmaß",
        "label_8": "Unteres Abmaß",
        "gbDisplayStyle": "Darstellung",
        "cbArrowheads": "Pfeile umkehren",
        "label_5": "Farbe",
        "label_7": "Schriftgröße",
        "label_4": "Bemaßungsstil",
        "gbLines": "Maß- und Hilfslinien",
        "rbOverride": "Winkel vorgeben",
        "label_3": "Winkel der Maßlinie",
        "label_6": "Winkel der Maßhilfslinien",
        "pbDimUseDefault": "Standard",
        "pbExtUseDefault": "Standard",
        "pbDimUseSelection": "Aus Auswahl",
        "pbExtUseSelection": "Aus Auswahl",
    },
    "combos": {
        # ISO oriented, ISO referencing, ASME inlined, ASME referencing
        "comboDrawingStyle": ["ISO ausgerichtet", "ISO mit Bezugslinie", "ASME waagerecht", "ASME mit Bezugslinie"],
    },
}

BALLOON = {
    "root": "TechDrawGui::TaskBalloon",
    "labels": {
        "label": "Positionsnummer",
        "label_5": "Textfarbe",
        "label_7": "Schriftgröße",
        "label_3": "Form",
        "label_2": "Größe der Form",
        "label_4": "Endsymbol",
        "label_10": "Größe Endsymbol",
        "label_9": "Hinweislinie",
        "label_8": "Linienstärke",
        "label_6": "Knicklänge",
    },
    "combos": {
        # Circular, None, Triangle, Inspection, Hexagon, Square, Rectangle, Line
        "comboBubbleShape": ["Kreis", "Ohne", "Dreieck", "Prüfmaß", "Sechseck", "Quadrat", "Rechteck", "Unterstrichen"],
        "comboLineVisible": ["Ausblenden", "Anzeigen"],
    },
}

NOTE = {
    "root": "TechDrawGui::TaskRichAnno",
    "labels": {
        "label": "Bezug",
        "label_2": "Max. Breite",
        "pbEditor": "Text bearbeiten …",
        "label_3": "Rahmen",
        "label_4": "Farbe",
        "label_5": "Linienstärke",
        "label_6": "Linienart",
    },
    "combos": {"cFrameStyle": ["Ohne Rahmen"] + LINE_STYLES},
}

LEADER = {
    "root": "TechDrawGui::TaskLeaderLine",
    "labels": {
        "label_4": "Ausgangsansicht",
        "pbCancelEdit": "Änderungen verwerfen",
        "label_2": "Startsymbol",
        "label_3": "Endsymbol",
        "label": "Farbe",
        "label_5": "Linienstärke",
        "label_6": "Linienart",
    },
    "combos": {"cboxStyle": ["Keine Linie"] + LINE_STYLES},
}

HATCH = {
    "root": "TechDrawGui::TaskHatch",
    "labels": {
        "groupBox": "Schraffurmuster",
        "label": "Musterdatei",
        "label_3": "Linienfarbe",
        "label_2": "Musterabstand (Skalierung)",
        "label_4": "Winkel",
        "label_5": "Versatz X",
        "label_6": "Versatz Y",
    },
    "combos": {},
}

CENTER_LINE = {
    "root": "TechDrawGui::TaskCenterLine",
    "labels": {
        "label_4": "Ausgangsansicht",
        "label_2": "Elemente",
        "gbOrientation": "Ausrichtung",
        # eindeutig: "Senkrecht" heisst bei Beziehungen "rechtwinklig"
        "rbVertical": "Vertikal",
        "rbHorizontal": "Horizontal",
        "rbAligned": "Ausgerichtet",
        "label": "Farbe",
        "label_5": "Linienstärke",
        "label_6": "Linienart",
        "label_7": "Versatz waagerecht",
        "label_8": "Versatz senkrecht",
        "label_9": "Drehen",
        "label_3": "Überstand",
    },
    "combos": {},
}

WELD = {
    "root": "TaskWeldingSymbol",
    "labels": {
        "pbOtherErase": "Löschen",
        "pbFlipSides": "Seiten tauschen",
        "cbFieldWeld": "Baustellennaht",
        "cbAllAround": "Ringsum-Naht",
        "cbAltWeld": "Unterbrochen, versetzt",
        "label_5": "Angabe an der Gabel (z. B. Verfahren)",
        "label": "Symbolordner",
    },
    "combos": {},
}

SURFACE = {
    "root": "TechDrawGui::TaskSurfaceFinishSymbols",
    "labels": {"lbAngle": "Drehwinkel"},
    "combos": {},
}

# Linieneigenschaften (TechDraw_DecorateLine, ueber SWUI_LineFormat) - line_format.py
def _line_presets(root):
    from swui import line_format

    return line_format.add_presets(root)


LINE_DECOR = {
    "root": "TechDrawGui::TaskLineDecor",
    "labels": {
        "label_4": "Ansicht",
        "label_10": "Linien",
        "label_6": "Linienart",
        "label_15": "Strichstärke",
        "label_14": "Farbe",
        "label": "Sichtbar",
    },
    "combos": {"cb_Visible": ["Nein", "Ja"]},
    "after": _line_presets,
}

SPECS = (PAD_POCKET, REVOLUTION, JOINT, INSERT, PROJ_GROUP, SECTION_VIEW, DETAIL_VIEW, COMPLEX_SECTION,
         DIMENSION, BALLOON, NOTE, LEADER, HATCH, CENTER_LINE, WELD, SURFACE, LINE_DECOR)

_timer = None
_installed = False


def install():
    """Beim Betreten der Workbench: offene Feature-Dialoge beobachten."""
    global _timer, _installed
    if _installed:
        return
    try:
        if _timer is None:
            _timer = QtCore.QTimer()
            _timer.setInterval(POLL_MS)
            _timer.timeout.connect(tick)
        _timer.start()
        _installed = True
    except Exception:
        FreeCAD.Console.PrintWarning(
            tr("[SWUI] SW-Begriffe in Dialogen nicht verfügbar:\n%s\n") % traceback.format_exc()
        )


def uninstall():
    """Beim Verlassen der Workbench abschalten (FreeCAD-Texte bleiben dann ab dem naechsten Dialog)."""
    global _installed
    if _timer is not None:
        _timer.stop()
    _installed = False


def is_installed():
    return _installed


def root_names(name):
    """
    Objektname des Formulars in beiden Schreibweisen: unter Linux heisst es
    "PartDesignGui::TaskPadPocketParameters", unter Windows (FreeCAD 1.1.4,
    gemeldet 25.10.) "PartDesignGui__TaskPadPocketParameters".
    """
    other = name.replace("::", "__")
    return (name, other) if other != name else (name,)


def tick():
    """Laeuft regelmaessig: nur wenn ein Aufgaben-Dialog offen ist."""
    try:
        if not FreeCADGui.Control.activeDialog():
            return
        mw = FreeCADGui.getMainWindow()
        for spec in SPECS:
            for name in root_names(spec["root"]):
                for root in mw.findChildren(QtWidgets.QWidget, name):
                    apply(root, spec)
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI] Dialog-Begriffe: %s\n" % traceback.format_exc())


def apply(root, spec):
    """
    Texte in einem Dialog-Formular austauschen. Gibt die Zahl der
    geaenderten Felder zurueck (fuer Tests).
    """
    changed = 0
    for name, text in spec["labels"].items():
        text = tr(text)
        w = root.findChild(QtWidgets.QWidget, name)
        if w is None:
            continue
        try:
            if hasattr(w, "setTitle") and hasattr(w, "title"):  # QGroupBox
                if w.title() != text:
                    w.setTitle(text)
                    changed += 1
            elif w.text() != text:
                w.setText(text)
                changed += 1
        except Exception:
            continue
    for name, items in spec["combos"].items():
        box = root.findChild(QtWidgets.QComboBox, name)
        if box is None:
            continue
        try:
            if box.count() != len(items):
                continue  # andere FreeCAD-Version: nicht anfassen
            for i, text in enumerate(items):
                text = tr(text)
                if box.itemText(i) != text:
                    box.setItemText(i, text)
                    changed += 1
        except Exception:
            continue
    for name, tip in spec.get("tooltips", {}).items():
        tip = tr(tip)
        w = root.findChild(QtWidgets.QWidget, name)
        try:
            if w is not None and w.toolTip() != tip:
                w.setToolTip(tip)
                changed += 1
        except Exception:
            continue
    fix = spec.get("after")
    if fix is not None:
        try:
            changed += fix(root) or 0
        except Exception:
            pass
    return changed
