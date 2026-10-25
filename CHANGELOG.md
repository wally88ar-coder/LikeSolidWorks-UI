# Änderungen / Changelog

Neueste Version oben. / Newest version first.

## Unveröffentlicht / Unreleased

**Deutsch**
- Oberfläche auch auf **Spanisch** (`swui/lang/es.py`), Begriffe wie im
  spanischen SOLIDWORKS (Croquis, Extruir saliente/base, Relaciones de
  posición, Planta/Alzado/Vista lateral …).
- *Automatisch* nimmt FreeCADs Sprache, wenn es dafür eine Sprachdatei gibt
  (bisher nur Deutsch, sonst Englisch); erkennt auch „Spanish (Argentina)“.
- **Kleine Bildschirme:** Das Ribbon erzwingt keine Mindestbreite des
  Fensters mehr (bisher ~1460 px – bei 1366 px ragte das Fenster rechts
  über den Rand). Passt ein Reiter nicht, zeigen die großen Knöpfe nur das
  Symbol (Name im Tooltip, wie in SOLIDWORKS ohne „große Knöpfe mit
  Text“); reicht das nicht, erscheinen Pfeile zum Verschieben.
- `tools/test_load.py` läuft auch unter Windows (Pfadvergleiche).

**English**
- Interface also in **Spanish** (`swui/lang/es.py`), terms as in the
  Spanish SOLIDWORKS.
- *Automatic* uses FreeCAD's language whenever there is a language file for
  it (before: German, otherwise English); also recognises "Spanish (Argentina)".
- **Small screens:** the ribbon no longer forces a minimum window width
  (before ~1460 px – on 1366 px screens the window was cut off on the
  right). If a tab does not fit, the large buttons show only their icon
  (name in the tooltip); if that is still too wide, arrows appear to scroll.
- `tools/test_load.py` also runs on Windows (path comparisons).

**Fork (wally88ar-coder, español)**
- Panel de tareas (PropertyManager) **a la izquierda**, visible solo mientras hay
  una operación abierta; sin operación queda el árbol, como en SOLIDWORKS.
  Vista de informe abajo. Código propio del fork en `swui/fork/`.

## 0.10.0 — 2026-10-18

**Deutsch**
- Oberfläche auf **Deutsch und Englisch** – Knopf *Language* im Reiter
  Evaluieren (Automatisch wie FreeCAD / Deutsch / English), wirkt sofort.
  Englische SOLIDWORKS-Begriffe im Ribbon, in den Dialogen und im Baum
  (Sketch1, Boss-Extrude1, Top Plane, Mates, Sheet1 …).
- Reiter *Evaluieren* ganz links, damit man die Sprache sofort findet.
- **„Skizze erstellen“ unter dem Mauspfeil** nach einem Klick auf eine
  ebene Fläche (blasst beim Wegbewegen aus).
- Zeichnungen:
  - englische Vorlagen A4 hoch / A3 quer (ISO 7200, Feld „Unit“)
  - **Projektionsmethode je Zeichnung wählbar** (Methode 1 / Methode 3),
    Symbol im Schriftfeld wechselt mit
  - **Linieneigenschaften**: Linienart, Strichstärke (ISO 128), Farbe
  - **Formen** auf dem Blatt (Linie, Rechteck, Kreis, Bogen, Vieleck) in
    einer Blatt-Skizze mit allen Abhängigkeiten, frei verschiebbar
  - **Text** per Klick aufs Blatt, Schriftgröße in mm oder pt
  - Export: zwei Blätter konnten denselben Dateinamen bekommen – behoben
- Kompatibilität: Fenster öffnen auch unter Qt5/PySide2; laufende
  Platzier-Modi enden beim Werkbankwechsel; geprüft gegen FreeCAD 1.0.2,
  1.1.4 und den Entwicklungsstand.
- Erste Freigabe über den Zweig `release`.

**English**
- Interface in **German and English** — *Language* button in the Evaluate
  tab (automatic like FreeCAD / German / English), switches immediately.
  English SOLIDWORKS terms in the ribbon, dialogs and tree.
- Evaluate tab moved to the far left so the language is easy to find.
- **"Sketch" context symbol** next to the pointer after clicking a planar
  face (fades out when moving away).
- Drawings: English title block templates (ISO 7200, "Unit" field);
  **projection method per drawing** (first/third angle) with matching
  symbol; **Line Format** (style, ISO 128 thickness, colour); **shapes** on
  the sheet in a sheet sketch with all relations, movable; **text** by
  clicking on the sheet, font size in mm or pt; fixed duplicate file names
  when exporting several sheets.
- Compatibility: dialogs also open with Qt5/PySide2; placement modes end
  when switching workbenches; checked against FreeCAD 1.0.2, 1.1.4 and the
  development version.
- First release through the `release` branch.

## 0.9.0 — 2026-10-18

**Deutsch** – Erste Veröffentlichung: Ribbon im Stil des
SOLIDWORKS-CommandManagers, dunkles Farbschema, SOLIDWORKS-Namen und
-Begriffe für Teile, Skizzen, Baugruppen und Zeichnungen, Beziehungs- und
Verknüpfungs-Panel, Drag & Drop in Baugruppen, Zeichnung erstellen mit
ISO-7200-Schriftfeld, Blatteigenschaften, Oberflächenangabe (ISO 1302),
Schweißsymbol (ISO 2553), PDF/DXF-Export, eigene Symbole.

**English** – First public version: CommandManager-style ribbon, dark
theme, SOLIDWORKS names and terms for parts, sketches, assemblies and
drawings, relations and mates panels, drag & drop into assemblies, drawing
creation with ISO 7200 title block, sheet properties, surface finish
(ISO 1302), weld symbol (ISO 2553), PDF/DXF export, own icons.
