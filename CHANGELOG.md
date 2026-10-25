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
- Feature-Dialoge (Linear austragen, Verrundung …) wechselten in FreeCAD
  1.1.4 selbst zur Workbench Part Design – Ribbon weg, Dialog ohne
  SW-Begriffe. Sie bleiben jetzt in LikeSolidWorks UI.
- SW-Begriffe in den Dialogen auch unter Windows (Objektname dort
  `PartDesignGui__…` statt `PartDesignGui::…`).
- **Skizze / Linear austragen / Linearer Schnitt ohne Auswahl** wie in
  SOLIDWORKS: Ebene oder ebene Fläche im Grafikbereich, im Baum oder in
  der Liste wählen, die Skizze öffnet sich darauf; bei Austragen/Schnitt
  startet das Feature nach „Skizze beenden“. Bisher: FreeCADs Dialog mit
  nur den Ursprungsebenen (Flächen nicht wählbar), beim automatisch
  angelegten Körper noch mit FreeCADs Ebenennamen.
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
- Feature dialogs (Extruded Boss/Base, Fillet …) switched to the Part Design
  workbench by themselves in FreeCAD 1.1.4 – ribbon gone, no SW terms. They
  now stay in LikeSolidWorks UI.
- SW terms in the dialogs also on Windows (object name `PartDesignGui__…`
  there instead of `PartDesignGui::…`).
- **Sketch / Extruded Boss / Extruded Cut without a selection** as in
  SOLIDWORKS: pick a plane or planar face in the graphics area, the tree or
  the list, the sketch opens on it; for boss/cut the feature starts after
  "Exit Sketch". Before: FreeCAD's dialog with only the origin planes (faces
  not selectable).
- `tools/test_load.py` also runs on Windows (path comparisons).

**Fork (wally88ar-coder, español)**
- **Aspecto claro de SOLIDWORKS 2018** (colores medidos en capturas): cinta y paneles
  #F7F7F7, pestañas #D4D4D4, fondo degradado gris-celeste a blanco; croquis en azul puro
  (líneas 2 px, constructivas 1 px trazo y punto), resaltado naranja, aristas negras 1 px.
- Panel izquierdo como en SOLIDWORKS: **Modelo y Tareas en pestañas** sobre fondo gris
  claro (el árbol ya no flota sobre la vista 3D); al abrir una operación pasa solo a Tareas
  y al cerrarla vuelve al árbol.
  Vista de informe abajo y **oculta** (se abre con Ver → Paneles → Vista de
  informe); dentro de LikeSolidWorks UI no se abre sola ante avisos/errores.
  Código propio del fork en `swui/fork/`.
- **Usar siempre LikeSolidWorks UI** (menú *LikeSolidWorks UI*, con tilde): FreeCAD
  arranca en LikeSolidWorks UI, vuelve a él si algo cambia de banco (por ejemplo
  "Cuerpo paramétrico" o "Ensamblaje" en la página de Inicio) y oculta el selector de
  bancos. Desmarcado, todo vuelve a ser como en FreeCAD.
- **Velocidad de giro** con la ruedita del mouse (menú *LikeSolidWorks UI →
  Velocidad de giro…*): x1 (como FreeCAD), x1,5 (de fábrica), x2, x2,5. Medido a
  1366 px: x1 = 16°, x1,5 = 25°, x2 = 35° por cada 100 px de arrastre.

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
