# LikeSolidWorks UI — FreeCAD Add-on

*Eine SOLIDWORKS-ähnliche Oberfläche für FreeCAD. Nicht verbunden mit Dassault Systèmes.*

[English version: README_EN.md](README_EN.md)

Im FreeCAD-Addon-Manager erscheint das Paket als **LikeSolid**; die Werkbank selbst heißt **LikeSolidWorks UI**. Die Suche findet es unter beiden Namen.

SOLIDWORKS-ähnliche Benutzeroberfläche und Werkzeuge für FreeCAD.
Entwickelt für **Linux Mint** mit **FreeCAD 1.1** (Flatpak).

## Status

| Schritt | Inhalt | Stand |
|---|---|---|
| 1 | Projektgerüst, Workbench-Registrierung, Diagnose | **fertig** |
| 2a | Ribbon-Gerüst: Reiter Features und Skizze | **fertig** |
| 2b | SW-Layout: Leisten aus, Aufgaben links, Reiter Ansicht/Evaluieren | **fertig** |
| 2c | Dunkles Farbschema im SW-Look (`swui/theme.py`) | **fertig** |
| 2c+ | Ausklappknöpfe im Ribbon, Skizzen-Varianten | **fertig** |
| 2d | 3D-Hintergrund grau-blau, Reiter Skizze automatisch | **fertig** |
| 2e | Schwebende Ansichtsleiste (Heads-up) | verworfen – Reiter *Ansicht* deckt es ab |
| 3 | Baum: SOLIDWORKS-Namen für neue Features und Ebenen (`swui/naming.py`) | **fertig** |
| 4 | Skizzen: SW-Farben (blau/schwarz), Beziehungen im Ribbon | **fertig** |
| 5 | Mittellinie symmetrisch mit gespiegelter Gegenseite (`midpoint_line.py`), Konstruktionslinie gestrichelt (`centerline.py`) | **fertig** |
| 6a | Panel „Beziehungen hinzufügen“: nur passende Beziehungen zur Auswahl, vorhandene anzeigen/löschen (`swui/sketch_relations.py`) | **fertig** |
| 6b | Eigene Skizzen-Symbole (SW-Klarheit + FreeCAD-Stil), Paket 1: Zeichenwerkzeuge (`tools/make_icons.py`) | **fertig** |
| 6b+ | Reiter Skizze aufgeteilt wie SW-CommandManager: große Hauptknöpfe, 3-Zeilen-Stapel, Zeilen mit Text; Skizze/Skizze beenden umschaltend; Offset-Elemente | **fertig** |
| 6c | Symbole Paket 2: Bearbeiten-Werkzeuge (Skizze, Bemaßung, Trimmen, Offset, Spiegeln, Muster …) | **fertig** |
| 6d | Symbole Paket 3: Beziehungen (Ribbon und Panel), Farben nur Weiß/Grau/Rot/Blau | **fertig** |
| 7a | Reiter Features aufgeteilt wie SW, eigene 3D-Symbole (grau = Körper, blau = Ergebnis) | **fertig** |
| 7b | Direkt aus offener Skizze austragen: Skizze beenden, auswählen, Feature starten (`swui/from_sketch.py`) | **fertig** |
| 7c | Feature-Dialoge mit SW-Begriffen: Richtung 1/2, Endbedingung, Blind, Durch alles, Mittelebene … (`swui/feature_terms.py`) | **fertig** |
| 8a | Reiter Baugruppe (rechts von Ansicht): Einfügen, Deckungsgleich/Parallel/Konzentrisch groß, weitere Verknüpfungen, Explosionsansicht, Stückliste | **fertig** |
| 8b | Drag & Drop von .FCStd-Teilen/Unterbaugruppen aus dem Datei-Explorer in die aktive Baugruppe (`swui/assembly_drop.py`) | **fertig** |
| 8b+ | Neue Baugruppe immer als eigene Datei (`swui/commands/new_assembly.py`); Teile, Baugruppen, Zeichnungen = getrennte Dateien wie in SW | **fertig** |
| 8c | Eigene Symbole für den Reiter Baugruppe (22 Stück) | **fertig** |
| 8c+ | Drop in ungespeicherte Baugruppe: erst Speichern-Dialog, dann einfügen; fehlgeschlagene Teile nicht im Baum lassen | **fertig** |
| 8c++ | Baum links als durchsichtige Überlagerung (Schrift grau); Aufgaben oben + Ausgabefenster unten rechts fest angedockt (`swui/overlay_panels.py`); 3D-Hintergrund wird beim Verlassen wieder korrekt zurückgesetzt | **fertig** |
| 8d | Baum wie in SW: Baugruppe1, Welle<1>/Welle<2> (Name = Teil-Datei), „(f)“ vor fixierten Teilen, Ordner „Verknüpfungen“ (`swui/naming.py`) | **fertig** |
| 8e | Panel „Verknüpfung hinzufügen“: zwei Flächen/Kanten wählen → nur passende Verknüpfungen, Klick startet FreeCADs Gelenk mit der Auswahl (`swui/assembly_mates.py`) | **fertig** |
| 8f | SW-Begriffe im Verknüpfungs-Dialog (Verknüpfungsart, Grenzwerte …) und Verknüpfungen im Baum als Deckungsgleich1, Konzentrisch1, Abstand1 … (`feature_terms.py`, `naming.py`) | **fertig** |
| 8g | Freie Drehung (wie Inventor) um den Teil-Ursprung mit Drehkreuz, nur für Teile ohne Verknüpfung/Fixierung, sonst Knopf grau mit Grund im Tooltip (`swui/commands/free_rotate.py`) | **fertig** |
| 9a | Zeichnung erstellen (eigener Reiter „Zeichnungen“ rechts neben Baugruppe, zusätzlich im Reiter Baugruppe): eigene Datei, A4 hoch/A3 quer mit ISO-7200-Schriftfeld, Standard-Dreiansicht Methode 1 (`swui/commands/new_drawing.py`) | **fertig** |
| 9b | Blatteigenschaften: Blattformat/Vorlage per Liste wechseln (Ansichten bleiben), Schriftfeld als Eingabefelder mit deutschen Namen, Vorbelegung aus dem Teil (`swui/sheet_properties.py`) | **fertig** |
| 9b+ | Bild einfügen: SVG (Vektor), PNG/JPG (eingebettet), Position X/Y, Breite in mm, Drehung von Hand; gewähltes Bild nachträglich bearbeiten (`swui/insert_image.py`) | **fertig** |
| 9c | Reiter Zeichnungen: Ansichtslayout (Modell-, Schnitt-, Detailansicht …), Beschriftung (Intelligente Bemaßung, Positionsnummer, Notiz, Mittellinie …), PDF/DXF; springt bei aktivem Blatt nach vorn | **fertig** (Symbole folgen) |
| 9c+ | Benennung nach Norm: Schnitte A-A, B-B …, Details Z, Y … mit Maßstab; eigenes Textfeld, frei verschiebbar, wandert mit, umbenennbar (`swui/view_labels.py`) | **fertig** |
| 9c++ | Projizierte Ansicht (wie SW): Lage wählen, Projektion nach Methode 1 ausgerichtet; Ansichten verschiebbar mit verbundener Mittelachse (`swui/proj_views.py`) | **fertig** |
| 9c+++ | Ansichten mit einem Linksklick ziehen (auch auf Kanten), Achsbindung bleibt; Projizierte Ansicht per Mausklick relativ zur gewählten Ansicht (`swui/page_drag.py`, `swui/proj_views.py`) | **fertig** |
| 9c4 | Maßstab der gewählten Ansicht per Menü: Normmaßstäbe, Blattmaßstab, automatisch, eigener; Abstände und Schriftfeld folgen (`swui/view_scale.py`) | **fertig** |
| 9c5 | Schriftfeld mit Feld „Maßeinheit“ (Vorgabe mm): eigene deutsche Vorlagen A4 hoch/A3 quer nach DIN EN ISO 7200 (`resources/templates/`, erzeugt von `tools/make_templates.py`) | **fertig** |
| 9d1 | Eigene Symbole für den Reiter Zeichnungen: Modell-, projizierte, Schnitt-, Detailansicht, Standard-Dreiansicht, Maßstab, Bemaßung, Positionsnummer, Notiz, PDF, DXF (`tools/make_icons.py`) | **fertig** |
| 9d2 | Eigene Symbole für die kleinen Zeichnungs-Einträge: Bemaßungsarten, ausgerichteter Schnitt, unterbrochene Ansicht, Ausschnitt, Mittellinie, Mittelpunktmarke, Schraffur, Oberfläche, Schweißen, Hinweislinie | **fertig** |
| 9d3 | Beim Hineinzoomen ins Blatt werden Linien und Eckpunkte stufenweise dünner – nur am Bildschirm; Speichern, PDF, Druck und Export behalten die Norm-Strichstärken (`swui/zoom_lines.py`) | **fertig** |
| 9e1 | SW-Begriffe in den TechDraw-Dialogen des Ansichtslayouts: Standard-Dreiansicht, Schnitt-, Detailansicht, ausgerichteter Schnitt (`swui/feature_terms.py`) | **fertig** |
| 9e2a | SW-Begriffe in den Beschriftungs-Dialogen: Bemaßung, Positionsnummer, Notiz, Hinweislinie, Schraffur, Mittellinie, Schweiß- und Oberflächensymbol (`swui/feature_terms.py`) | **fertig** |
| Fix | Absturz beim Bemaßen behoben: Während ein TechDraw-Werkzeug läuft, ändern Zoom-Linien und Ziehen nichts mehr (`zoom_lines.py`, `page_drag.py`) | **fertig** |
| 9e2c | Eigene Oberflächenangabe nach DIN EN ISO 1302: Sinnbild, rundum, Felder a–e als editierbare Texte, Schnellauswahl Rz 4/16/63, Doppelklick öffnet wieder (`swui/surface_finish.py`) | **fertig** |
| 9e2d | Eigenes Schweißsymbol nach DIN EN ISO 2553 wie in SOLIDWORKS: Pfeilspitze anklicken, Symbol setzen, Pfeil folgt beim Verschieben; Pfeil-/Gegenseite, Nahtdicke, Länge, Oberfläche, G/C/M/F, ringsum, Baustelle, Gabel, wahlweise Strichlinie; Doppelklick (`swui/weld_symbol.py`) | **fertig** |
| 9f | Namen im Zeichnungsbaum wie SW: Blatt1, Blattformat1, Standard-Dreiansicht, Vorderansicht/Draufsicht/Seitenansicht von links, Zeichenansicht1, Schnittansicht A-A, Detailansicht Z (2:1), Bemaßung1, Positionsnummer1, Notiz1, Schraffur1, Schweißsymbol1, Oberflächenangabe1; bestehende Zeichnungen werden beim Öffnen nachgezogen (`naming.py`, `view_labels.py`) | **fertig** |
| Fix | Harmlose Qt-Meldungen „render glyph failed“ beim starken Hineinzoomen werden ausgeblendet (`swui/qt_messages.py`) | **fertig** |
| 9g | Ausgabe: „Als PDF speichern“ schreibt alle Blätter in eine PDF (eigenes Zusammenfügen, sonst einzelne Dateien), „Als DXF exportieren“ je Blatt eine Datei; Dateiname aus der Zeichnungsnummer (`drawing_export.py`, `pdf_merge.py`) | **fertig** |
| V1 | Veröffentlichung vorbereitet: Name **LikeSolidWorks UI**, Lizenzdateien (LGPL-2.1+/CC-BY-SA-4.0), Rechtshinweise, Manifest-Prüfung im Test | **fertig** |
| V2 | Nur in der Werkbank: Drag & Drop in Baugruppen wird beim Verlassen abgemeldet; Qt-Meldungsfilter wirkt nur, solange LikeSolidWorks UI aktiv ist, und ist per Parameter abschaltbar | **fertig** |
| Fix | Nach dem Reinziehen ließen sich die Teile manchmal nicht bewegen: Die Baugruppe war nur als aktiv markiert, nicht im Bearbeitungsmodus. Drag & Drop aktiviert sie jetzt vor und nach dem Einfügen (`swui/assembly_drop.py`) | **fertig** |
| L1 | Sprache: Knopf **Language** mit Ausklappmenü im Reiter Evaluieren (Automatisch wie FreeCAD / Deutsch / English), Ribbon schaltet sofort um; neue Sprache = neue Datei in `swui/lang/` (`swui/i18n.py`) | **fertig** |
| L2a | Sprache: Fenster der Zeichnungswerkzeuge zweisprachig (Oberflächenangabe, Schweißsymbol, Blatteigenschaften, Bild einfügen, Maßstab, Export, Zeichnung erstellen, projizierte Ansicht), auch Rückgängig-Einträge; Hilfswerkzeug `tools/wrap_tr.py` | **fertig** |
| L2b | Sprache: Beziehungs- und Verknüpfungs-Panel, freie Drehung (auch Sperrgründe im Tooltip), Diagnose, Drag & Drop und alle Meldungen im Ausgabefenster zweisprachig; Test prüft Platzhalter (%s, %d) jeder Übersetzung | **fertig** |
| L3 | Sprache: SW-Begriffe in FreeCADs eigenen Dialogen auch auf Englisch (Direction 1, End Condition, Blind, Through All, Mid Plane, Projected Views, Balloon …) | **fertig** |
| L4a | Sprache: Namen im Baum für neue Objekte auf Englisch wie in SW (Sketch1, Boss-Extrude1, Top Plane, Mates, Coincident1, Sheet1, Standard 3 View, Section View A-A …), vorhandene Namen bleiben; Export je Blatt `…_Sheet2.pdf`; Reiter Evaluieren ganz links (Knopf Language sofort sichtbar), Start weiter auf Features | **fertig** |
| L4b1 | Sprache: englische Zeichnungsvorlagen A4 hoch / A3 quer (ISO 7200, Feld „Unit“, Sprache EN); neue Zeichnung nimmt die Vorlage der eingestellten Sprache | **fertig** |
| L4b2 | Projektionsmethode je Zeichnung wählbar (Blatteigenschaften): Methode 1 (DIN/ISO) oder 3, Symbol im Schriftfeld wechselt mit (ISO 5456-2); neue Zeichnung auf Englisch mit Methode 3 (Vorder-, Draufsicht oben, Seitenansicht rechts), sonst Methode 1; englisches Schriftfeld mit Sprache EN und Datum JJJJ-MM-TT | **fertig** |
| L5 | Englische README (`README_EN.md`) mit Funktionsübersicht und Installationsanleitung für andere Nutzer; Beschreibung im Addon-Manager zweisprachig | **fertig** |
| W1 | Kontext-Symbol „Skizze erstellen“ wie in SW: Klick auf eine ebene Fläche im Teil → Symbol rechts oberhalb des Mauspfeils, Klick legt die Skizze auf der Fläche an; wird beim Wegbewegen der Maus blasser und verschwindet; nicht in Baugruppen und nicht bei offenem Dialog (`swui/context_sketch.py`) | **fertig** |
| W3 | Knopf „Linieneigenschaften“ im Reiter Zeichnungen (wie SW-Linienformat): gewählte Linien einer Ansicht → Linienart, Strichstärke, Farbe, Sichtbar; wirkt sofort; Schnellauswahl Normstärke nach ISO 128 (0,13–1 mm); ohne Auswahl Hinweis statt Fehlerfenster (`swui/line_format.py`, nutzt FreeCADs Dialog TechDraw_DecorateLine) | **fertig** |
| W2a | Zeichnen auf dem Blatt, Feld **Formen** (Linie, Rechteck, Kreis, Bogen, Vieleck) im Reiter Zeichnungen: öffnet die Blatt-Skizze (Blattrand als blockierte Hilfslinien) mit allen Skizzen-Abhängigkeiten und Maßen; beim Platzieren wird aufs ganze Blatt gezoomt; nach „Skizze beenden“ erscheint sie 1:1 an der richtigen Stelle auf dem Blatt und lässt sich dort frei verschieben – der Blattrand in der Skizze wandert mit (`swui/sheet_sketch.py`) | **fertig** |
| W2c | Feld **Text** im Reiter Zeichnungen: Knopf, aufs Blatt klicken, Text tippen – einfacher Text ohne Notiz-Formatierung, Schriftgröße in mm oder pt (Schnellwahl Normhöhen ISO 3098, letzte Größe wird gemerkt), verschiebbar; ist ein Text gewählt, öffnet der Knopf ihn zum Ändern; Esc/Rechtsklick bricht ab (`swui/text_note.py`) | **fertig** |

Später: 3D-Skizzen.

## Kompatibilität

| | Stand |
|---|---|
| FreeCAD 1.1.x | getestet (1.1.4, Linux Mint, Flatpak) |
| FreeCAD 1.0.x | Quelltext geprüft: alle Funktionen vorhanden außer drei Baugruppen-Knöpfen (Baugruppe aktivieren, Neues Teil einfügen, Bewegungsstudie) und „Schnittkurve“ – diese Knöpfe fehlen dann einfach im Ribbon |
| FreeCAD-Entwicklungsstand | Quelltext geprüft (18.10.2026): alles vorhanden |
| Qt6/PySide6 und Qt5/PySide2 | beide berücksichtigt (Import über FreeCADs `PySide`-Schicht) |
| Python | ab 3.8 |
| Windows, macOS, andere Linux-Pakete | nicht getestet; keine festen Pfade, sollte laufen – Rückmeldungen willkommen |

## Installation

**Addon-Manager.** Die Aufnahme in den offiziellen FreeCAD-Index ist
geplant. Bis dahin das Repository von Hand eintragen: *Bearbeiten →
Einstellungen → Addon-Manager → Benutzerdefinierte Repositories*, URL
`https://github.com/Schlauminik/LikeSolidWorks-UI`, Zweig `release`.
Danach im Addon-Manager nach **LikeSolid** suchen und installieren.

**Von Hand.** In den Ordner `Mod` des FreeCAD-Benutzerordners klonen und
FreeCAD neu starten (den richtigen Ordner zeigt die Python-Konsole mit
`FreeCAD.getUserAppDataDir()`):

```bash
git clone -b release https://github.com/Schlauminik/LikeSolidWorks-UI.git <Benutzerordner>/Mod/LikeSolidWorks-UI
```

Nicht beide Wege gleichzeitig nutzen – FreeCAD würde zwei Kopien laden.
Was sich je Version geändert hat, steht in `CHANGELOG.md`.

## Entwicklungs-Setup

FreeCAD 1.1 liegt hier als Flatpak und nutzt **versionierte**
Benutzerordner. Der richtige Mod-Ordner ist:

`~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/Mod/SWUI/`

(Nicht `…/data/FreeCAD/Mod/` – der stammt aus einer älteren Version
und wird von 1.1 ignoriert.) Die Dateien liegen dort als Kopie, kein
Symlink. Danach FreeCAD neu starten.

## Freigabe einer neuen Version

Entwickelt wird auf `master`, Nutzer bekommen den Zweig `release`.
Für eine Freigabe: Version in `package.xml` und `swui/version.py`
hochzählen, Datum setzen, Eintrag in `CHANGELOG.md`, committen, dann

```bash
bash tools/freigabe.sh
```

Das Skript prüft (auf `master`, nichts ungesichert, Version im
CHANGELOG, noch nicht freigegeben, Test grün) und bringt den Stand nach
`release` mit Tag `vX.Y.Z`. Der Addon-Manager meldet den Nutzern dann ein
Update.

## Test vor jeder Auslieferung

```bash
python3 tools/test_load.py .
```

Simuliert FreeCADs Ladeweise (ohne `__file__`, getrennte
Namensräume) und prüft Workbench, Befehle und Ribbon.

## Aufbau

```
InitGui.py           Workbench-Registrierung (nur GUI-Start)
Init.py              Konsolen-Modus, absichtlich leer
package.xml          Metadaten für den FreeCAD Addon-Manager
swui/
  compat.py          Qt-Import über FreeCADs PySide-Shim
  paths.py           Pfade zu Icons und .ui-Dateien
  version.py         Versionsnummer
  i18n.py            Sprache der Oberfläche (tr(), Language-Knopf)
  lang/              je Sprache eine Datei (de.py, en.py, ...)
  commands/          Ein Modul je Themenbereich
resources/
  icons/             SVG-Icons
    sketch/          eigene Skizzen-Symbole - NICHT von Hand aendern,
                     sondern tools/make_icons.py anpassen und laufen lassen
  ui/                Qt-Designer-Dateien
```

### Konventionen

- Qt immer über `from swui.compat import QtWidgets` — nie direkt `PySide6`.
  Einzige dokumentierte Ausnahme: `swui/qt_messages.py` versucht zuerst
  `PySide6.QtCore.qInstallMessageHandler`, weil die Schicht diese
  Funktion nicht immer hat, und fällt danach auf `compat` zurück.
- Befehls-IDs beginnen mit `SWUI_`
- Pfade nur über `swui.paths`, nie zusammengestückelt
- Schwere Imports in `Initialize()`, nicht auf Modulebene

## Fehlersuche

Workbench → **LikeSolidWorks UI** → Toolbar **SW Diagnose** → Knopf *Diagnose*.
Das Fenster zeigt alle Versionsangaben mit Kopier-Knopf.

Python-Konsole einschalten: Ansicht → Panels → Python-Konsole.
Report-Ansicht einschalten: Ansicht → Panels → Report-Ansicht.

## Einstellungen

**Qt-Meldungsfilter.** Beim starken Hineinzoomen ins Zeichenblatt meldet
Qt für jedes Zeichen „render glyph failed“ (harmlos, tritt auch ohne
das Add-on auf). Das Add-on blendet genau diese Meldung aus — **nur,
solange LikeSolidWorks UI aktiv ist**. In anderen Werkbänken gehen alle
Meldungen unverändert durch.

Technischer Hinweis: FreeCADs eigener Meldungsweiterleiter ist C++-Code
und lässt sich aus Python nicht wieder einsetzen, wenn er einmal
ersetzt wurde. Der Filter bleibt deshalb angemeldet, ist außerhalb der
Werkbank aber völlig durchlässig und leitet alles so weiter wie
FreeCAD selbst. Wer ihn gar nicht möchte:

*Werkzeuge → Bearbeiten → Parameter →*
`BaseApp/Preferences/Mod/SWUI` → neuen Bool-Eintrag `QtMessageFilter`
mit Wert `false` anlegen, FreeCAD neu starten. Dann wird nichts
angemeldet.

**Drag & Drop in Baugruppen** (.FCStd-Dateien aus dem Datei-Explorer
auf eine aktive Baugruppe ziehen) wirkt nur in LikeSolidWorks UI.
Außerhalb öffnet FreeCAD gezogene Dateien wie gewohnt.

**Symbol „Skizze erstellen“.** Nach einem Klick auf eine ebene Fläche
erscheint neben dem Mauspfeil ein kleines Skizzen-Symbol. Wer das nicht
möchte: Parameter `BaseApp/Preferences/Mod/SWUI` → neuer Bool-Eintrag
`ContextSketch` mit Wert `false` (wirkt sofort).

**Sprache.** Reiter *Evaluieren* → Knopf **Language**: *Automatisch*
(wie FreeCAD — gibt es eine Sprachdatei für FreeCADs Sprache, wird sie
genommen, sonst Englisch), *Deutsch*, *English* oder *Español*. Die Umschaltung wirkt sofort. Gespeichert
wird sie im Parameter `BaseApp/Preferences/Mod/SWUI/Language`.
Weitere Sprachen: `swui/lang/en.py` kopieren (z. B. als `fr.py`),
`CODE`, `NAME` und die Texte anpassen — die Sprache erscheint danach
automatisch im Menü. Fehlende Texte meldet `tools/test_load.py`.

## Lizenz

Zwei Lizenzen, wie bei FreeCAD-Add-ons üblich, dazu gemeinfreie Vorlagen:

| Teil | Lizenz | Datei |
|---|---|---|
| Quelltext (`*.py`) | LGPL-2.1-or-later | `LICENSE-Code` |
| Symbole (`resources/icons/`) | CC-BY-SA-4.0 | `LICENSE-Assets` |
| Zeichnungsvorlagen (`resources/templates/`, `tools/template_sources/`) | CC0-1.0 (gemeinfrei) | Angabe in den SVG-Dateien |

LGPL für den Code, weil FreeCAD selbst unter dieser Lizenz steht und
der Code damit notfalls auch in FreeCAD einfließen könnte. CC-BY-SA
für die Grafiken, weil die LGPL auf Nicht-Quelltext schlecht passt.
Beides erlaubt Weitergabe und Änderung, verlangt aber, dass
Änderungen unter derselben Lizenz bleiben.

Die Zeichnungsvorlagen sind aus FreeCADs ISO-Vorlagen abgeleitet
(`tools/template_sources/`, aus FreeCAD 1.1.4), die FreeCAD als CC0
freigegeben hat. Sie bleiben ebenfalls CC0 — so steht es auch in den
Metadaten der Dateien. Jede Quelldatei trägt eine
`SPDX-License-Identifier`-Kopfzeile; der Test prüft das.

## Marken und Rechtliches

**SOLIDWORKS ist eine eingetragene Marke von Dassault Systèmes.**
Dieses Projekt steht in keiner Verbindung zu Dassault Systèmes und
wird von dort weder unterstützt, geprüft noch genehmigt. Der Name
„LikeSolidWorks UI“ soll nur ausdrücken, woran sich die Bedienung
anlehnt; er ist kein Produkt- oder Markenname von Dassault Systèmes.

**Alle Symbole sind Eigenentwürfe.** Alle SVG-Dateien unter
`resources/icons/` wurden von Grund auf neu gezeichnet
(`tools/make_icons.py`) und sind keine Kopien oder Bearbeitungen
fremder Symbole. Die Zeichnungsvorlagen sind dagegen Bearbeitungen
von FreeCADs gemeinfreien ISO-Vorlagen (deutsche Beschriftung, Feld
„Maßeinheit“) — siehe Abschnitt Lizenz.

**Normen.** Das Add-on setzt den technischen Inhalt von DIN EN ISO
7200 (Schriftfeld), 1302 (Oberflächenangaben), 2553
(Schweißsymbole) und ISO 5456-2 (Symbol der Projektionsmethode) um. Die Normtexte selbst sind urheberrechtlich
geschützt und werden hier weder mitgeliefert noch zitiert — verwendet
wird nur das Fachwissen, so wie es jedes CAD-Programm tut.

**Schriftart.** Die Vorlagen verweisen über den Namen auf `osifont`.
Die Schriftdatei selbst gehört zu FreeCAD und liegt nicht in diesem
Projekt.

## Haftungsausschluss

Dieses Add-on wird ohne jede Gewährleistung bereitgestellt. Es
verändert die Oberfläche von FreeCAD, solange die Werkbank aktiv ist,
und stellt den Ursprungszustand beim Verlassen wieder her. Für
Datenverlust oder fehlerhafte Zeichnungen wird keine Haftung
übernommen — technische Zeichnungen vor der Weitergabe immer selbst
prüfen.
