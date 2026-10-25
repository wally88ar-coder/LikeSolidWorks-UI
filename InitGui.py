# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 Dominik Ladewig
"""
InitGui.py - Einstiegspunkt fuer die LikeSolidWorks-UI-Workbench.

Diese Datei wird von FreeCAD beim Start automatisch ausgefuehrt,
sobald der Ordner unter Mod/ liegt. Sie darf nichts Schweres tun:
nur die Workbench anmelden. Alles andere passiert erst in
Initialize(), also wenn der Benutzer die Workbench anklickt.


ZWEI FALLSTRICKE - bitte beim Bearbeiten beachten
=================================================

FreeCAD importiert diese Datei nicht als Modul, sondern wertet ihren
Quelltext mit exec() aus. Daraus folgen zwei Regeln, die hier anders
sind als in jeder anderen Python-Datei des Projekts:

1. __file__ GIBT ES NICHT.
   Der eigene Pfad kommt deshalb aus swui.paths - das ist ein echtes
   Modul und hat sein __file__.

2. exec() laeuft mit GETRENNTEN Namensraeumen.
   Namen auf Modulebene landen in den Locals der exec-Umgebung.
   Funktionen finden sie dort noch, KLASSENRUEMPFE NICHT - die
   schauen nur in ihren eigenen Namensraum und danach direkt in die
   Globals. Eine Zeile wie

       class Foo:
           Icon = os.path.join(_HERE, "x.svg")

   scheitert deshalb mit "name '_HERE' is not defined" - und je nach
   FreeCAD-Version sogar schon bei 'os'.

   REGEL: Im Klassenrumpf stehen nur Literale. Alles Berechnete wird
   nach der Klassendefinition zugewiesen. Methoden importieren, was
   sie brauchen, selbst - ein lokaler Import ist billig und immun.

tools/test_load.py prueft beide Punkte. Vor jeder Auslieferung laufen
lassen.
"""

import os
import sys
import traceback

import FreeCAD
import FreeCADGui

# Schluessel, unter dem FreeCAD die Workbench fuehrt.
_WB_KEY = "LikeSolidWorksUIWorkbench"


class LikeSolidWorksUIWorkbench(FreeCADGui.Workbench):
    """Die Workbench, die in FreeCADs Auswahlliste erscheint."""

    # Nur Literale - siehe Fallstrick 2 im Kopf dieser Datei.
    MenuText = "LikeSolidWorks UI"
    ToolTip = "SOLIDWORKS-aehnliche Oberflaeche und Werkzeuge"
    Icon = ""  # wird unten nach der Klassendefinition gesetzt

    def Initialize(self):
        """Wird einmal aufgerufen, wenn die Workbench zuerst aktiviert wird."""
        # Lokale Imports: unabhaengig davon, was die exec-Umgebung sieht.
        import traceback as tb

        import FreeCAD as App

        try:
            from swui import commands, compat

            compat.report_environment_to_console()
            commands.register_all()

            # Skizzen in LikeSolidWorks UI bearbeiten statt im Sketcher.
            from swui import sketch_edit

            sketch_edit.install()

            # Neue Features bekommen SOLIDWORKS-Namen (Skizze1, ...).
            from swui import naming

            naming.install()

            # Schnitt-/Detailansichten nach Norm benennen (A-A / Z), Benennung als Textfeld.
            from swui import view_labels

            view_labels.install()

            # Projizierte Ansichten: nach dem Verteilen von Hand verschiebbar (Achse bleibt).
            from swui import proj_views

            proj_views.install()

            # Beim Hineinzoomen ins Blatt duennere Linien/kleinere Punkte (nur Bildschirm).
            from swui import zoom_lines

            zoom_lines.install()

            # Harmlose Qt-Meldungen beim starken Zoomen ("render glyph failed")
            # ausblenden - wirksam nur, solange diese Werkbank aktiv ist
            # (set_active in Activated/Deactivated). Abschaltbar ueber den
            # Parameter Mod/SWUI/QtMessageFilter.
            from swui import qt_messages

            qt_messages.install()

            # Schweisssymbol: Pfeil folgt beim Verschieben des Symbols.
            from swui import weld_symbol

            weld_symbol.install()

            # Agregados propios del fork (swui/fork/), enganchados en un solo lugar.
            from swui import fork

            fork.install()

            # Keine eigene Toolbar: Alles Sichtbare lebt im Ribbon.
            # Die Diagnose bleibt im Menue "LikeSolidWorks UI" erreichbar.
            self.appendMenu("LikeSolidWorks UI", ["SWUI_Diagnostics"])

            App.Console.PrintMessage("[SWUI] Workbench initialisiert.\n")
        except Exception:
            App.Console.PrintError(
                "[SWUI] Initialize() fehlgeschlagen:\n%s\n" % tb.format_exc()
            )

    def Activated(self):
        """Workbench betreten: SOLIDWORKS-Layout anwenden, Ribbon zeigen."""
        import traceback as tb

        import FreeCAD as App

        # Getrennt abgesichert: Scheitert das Layout, kommt das Ribbon
        # trotzdem - und umgekehrt.
        # Reihenfolge wichtig: Layout merkt sich den Fensterzustand
        # BEVOR das Ribbon erscheint.
        try:
            from swui import layout

            layout.enter()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Layout konnte nicht angewendet werden:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import ribbon

            ribbon.show()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Ribbon konnte nicht angezeigt werden:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import sketch_relations

            sketch_relations.install()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Beziehungs-Panel nicht gestartet:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import assembly_mates

            assembly_mates.install()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Verknüpfungs-Panel nicht gestartet:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import feature_terms

            feature_terms.install()
        except Exception:
            App.Console.PrintError(
                "[SWUI] SW-Begriffe in Dialogen nicht gestartet:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import assembly_drop

            assembly_drop.install()
            assembly_drop.keep_workbench()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Drag & Drop in Baugruppen nicht gestartet:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import context_sketch

            context_sketch.install()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Symbol Skizze erstellen nicht gestartet:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import qt_messages

            qt_messages.set_active(True)
        except Exception:
            App.Console.PrintError(
                "[SWUI] Qt-Meldungsfilter nicht eingeschaltet:\n%s\n" % tb.format_exc()
            )

    def Deactivated(self):
        """Workbench verlassen: Originalzustand herstellen, Ribbon weg."""
        import traceback as tb

        import FreeCAD as App

        try:
            from swui import layout

            layout.leave()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Layout konnte nicht zurueckgesetzt werden:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import ribbon

            ribbon.hide()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Ribbon konnte nicht ausgeblendet werden:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import sketch_relations

            sketch_relations.uninstall()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Beziehungs-Panel nicht beendet:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import assembly_mates

            assembly_mates.uninstall()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Verknüpfungs-Panel nicht beendet:\n%s\n" % tb.format_exc()
            )
        try:
            from swui.commands import free_rotate

            free_rotate.stop()  # laufende freie Drehung beenden
        except Exception:
            App.Console.PrintError(
                "[SWUI] Freie Drehung nicht beendet:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import feature_terms

            feature_terms.uninstall()
        except Exception:
            App.Console.PrintError(
                "[SWUI] SW-Begriffe in Dialogen nicht beendet:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import assembly_drop

            # Ausserhalb dieser Werkbank verhaelt sich FreeCAD wieder wie
            # gewohnt: Drop-Faenger ab, Baugruppen-Einstellung zurueck.
            assembly_drop.uninstall()
            assembly_drop.restore_workbench_setting()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Drag & Drop in Baugruppen nicht beendet:\n%s\n" % tb.format_exc()
            )
        try:
            # laufende "Klick aufs Blatt"-Modi beenden (Text, Schweisssymbol, projizierte Ansicht)
            from swui import proj_views, text_note, weld_symbol

            for mod in (text_note, weld_symbol, proj_views):
                mod.stop_picking()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Auswahl auf dem Blatt nicht beendet:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import context_sketch

            context_sketch.uninstall()
        except Exception:
            App.Console.PrintError(
                "[SWUI] Symbol Skizze erstellen nicht beendet:\n%s\n" % tb.format_exc()
            )
        try:
            from swui import qt_messages

            qt_messages.set_active(False)  # Meldungen wieder ungefiltert
        except Exception:
            App.Console.PrintError(
                "[SWUI] Qt-Meldungsfilter nicht ausgeschaltet:\n%s\n" % tb.format_exc()
            )

    def GetClassName(self):
        # Pflicht-Methode. Dieser Wert bedeutet: reine Python-Workbench.
        return "Gui::PythonWorkbench"


# --- Ab hier wieder Modulebene: Namen sind normal sichtbar -----------


def _find_addon_dir():
    """
    Wurzelverzeichnis des Add-ons - ohne __file__.

    Weg 1: swui.paths importieren. FreeCAD legt den Mod-Unterordner
           vor dem Ausfuehren in sys.path ab, der Import gelingt also.
    Weg 2: Notnagel - sys.path nach einem Ordner durchsuchen, der
           wie unser Add-on aussieht.
    """
    try:
        from swui import paths

        return paths.ADDON_DIR
    except Exception:
        for entry in sys.path:
            try:
                if os.path.isfile(os.path.join(entry, "InitGui.py")) and os.path.isdir(
                    os.path.join(entry, "swui")
                ):
                    return entry
            except Exception:
                continue
        return ""


_HERE = _find_addon_dir()

if _HERE:
    LikeSolidWorksUIWorkbench.Icon = os.path.join(
        _HERE, "resources", "icons", "swui_workbench.svg"
    )


# --- Anmeldung -------------------------------------------------------
# Die Meldung hier erscheint beim FreeCAD-START und beweist, dass der
# Mod-Ordner gefunden wurde.
#
# Die Doppel-Pruefung ist noetig, weil das Add-on waehrend der
# Entwicklung zweimal unter Mod/ liegen kann (echter Ordner und
# zusaetzlich ein Symlink). Ohne sie wuerde FreeCAD beim zweiten
# Versuch einen Fehler werfen.

try:
    if _WB_KEY in FreeCADGui.listWorkbenches():
        FreeCAD.Console.PrintWarning(
            "[SWUI] Bereits registriert - dieser Pfad wird uebersprungen: %s\n" % _HERE
        )
    else:
        FreeCADGui.addWorkbench(LikeSolidWorksUIWorkbench())
        FreeCAD.Console.PrintMessage(
            "[SWUI] Workbench angemeldet - geladen aus: %s\n" % (_HERE or "PFAD UNBEKANNT")
        )
except Exception:
    FreeCAD.Console.PrintError(
        "[SWUI] Anmeldung fehlgeschlagen:\n%s\n" % traceback.format_exc()
    )


# --- Aufraeumen nach Absturz -----------------------------------------
# Ist FreeCAD zuletzt im SOLIDWORKS-Layout abgestuerzt, stehen die
# 3D-Hintergrund-Einstellungen noch auf unserem Verlauf. Hier beim Start
# zuruecksetzen, damit andere Workbenches wieder normal aussehen.

try:
    from swui import view_background as _vb

    _vb.recover()
    # Ebenso die Panel-Ueberlagerung (Baum links, Aufgaben rechts).
    from swui import overlay_panels as _op

    _op.recover()
    # Ebenso FreeCADs Baugruppen-Einstellung "in Werkbank wechseln".
    from swui import assembly_drop as _ad

    _ad.restore_workbench_setting()
except Exception:
    FreeCAD.Console.PrintWarning(
        "[SWUI] Aufräumen beim Start fehlgeschlagen:\n%s\n" % traceback.format_exc()
    )
