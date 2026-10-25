# LikeSolidWorks UI — FreeCAD Add-on

*A SOLIDWORKS-like user interface for FreeCAD. Not affiliated with Dassault Systèmes.*

[Deutsche Fassung: README.md](README.md)

In the FreeCAD Addon Manager the package is listed as **LikeSolid**; the
workbench itself is called **LikeSolidWorks UI**. The search finds it
under both names.

LikeSolidWorks UI gives FreeCAD a user interface and workflow modelled
on SOLIDWORKS: a CommandManager-style ribbon, SOLIDWORKS names in the
tree and SOLIDWORKS terms in the dialogs — for parts, assemblies and
drawings. Everything only applies while the workbench is active;
leaving it restores FreeCAD exactly as it was.

Developed and tested on **Linux Mint** with **FreeCAD 1.1.4** (Flatpak).
Version 0.9.0 — other platforms have not been tested yet.

## Language

The interface is available in **German, English and Spanish**. Switch it in the
*Evaluate* tab (the leftmost tab) with the **Language** button:

- *Automatic* — like FreeCAD: FreeCAD's language if there is a
  language file for it (German, Spanish), English otherwise
- *Deutsch* / *English* / *Español*

The change takes effect immediately. New objects get tree names in the
chosen language (Sketch1, Boss-Extrude1, Top Plane, Mates, Coincident1,
Sheet1 …); existing names are never changed. New drawings use the
matching title block template.

## Features

**Ribbon and layout**
- Ribbon like the SOLIDWORKS CommandManager with the tabs Evaluate,
  Features, Sketch, View, Assembly and Drawing; flyout buttons remember
  the last variant
- Over 120 icons of its own design (white, grey, red and blue)
- Dark colour scheme, grey-blue 3D background, the tree as a
  transparent overlay, task panel and report view docked on the right
- The Sketch and Drawing tabs come to the front automatically

**Parts**
- SOLIDWORKS names in the tree: Sketch1, Boss-Extrude1, Cut-Extrude1,
  Fillet1, Top/Front/Right Plane …
- SOLIDWORKS terms in FreeCAD's feature dialogs: Direction 1, End
  Condition, Blind, Through All, Up To Next, Mid Plane …
- Extrude straight from an open sketch: the sketch is closed, selected
  and the feature started in one click
- Context symbol *Sketch*: click a planar face and a small sketch
  symbol appears next to the pointer; one click starts a sketch on that
  face. It fades out as you move the mouse away

**Sketches**
- SOLIDWORKS colours (blue = under defined, black = fully defined)
- *Add Relations* panel: only the relations that fit the selection,
  existing relations listed and removable
- Symmetric centre line with mirrored opposite side, dashed
  construction line

**Assemblies**
- Every assembly is its own file, like parts and drawings
- Drag .FCStd parts and sub-assemblies from the file manager into the
  active assembly
- Tree like SOLIDWORKS: Assembly1, Shaft<1>, Shaft<2>, "(f)" in front
  of fixed parts, a *Mates* folder with Coincident1, Concentric1 …
- *Add Mate* panel: pick two faces or edges and get only the mates
  that fit
- Free rotation of unconstrained parts around their origin

**Drawings**
- *Make Drawing from Part/Assembly* as a separate file with a
  standard 3 view
- Own title block templates after ISO 7200 (A4 portrait, A3 landscape)
  with a *Unit* field, in German and English
- *Sheet Properties*: switch format or template (views are kept), fill
  in the title block, take values from the part
- Projection method per drawing: first angle (ISO) or third angle; the
  symbol in the title block changes with it. English drawings start
  with third angle, German drawings with first angle
- Projected views by mouse click, views draggable with linked axes,
  view scale menu with standard scales
- Section and detail view labels after the standard: A-A, B-B …,
  Z, Y … with scale
- Surface finish symbol after ISO 1302 and weld symbol after ISO 2553
  (SOLIDWORKS-style: click the arrow tip, place the symbol, the arrow
  follows)
- Insert images (SVG, PNG, JPG)
- *Shapes* on the sheet (line, rectangle, circle, arc, polygon): drawn in
  a sheet sketch with all sketch relations and dimensions, shown 1:1 in
  place on the sheet and freely movable there
- *Text*: click the button, click on the sheet and type — plain text,
  font size in mm or pt; select a text and click again to edit it
- *Line Format*: change line style (e.g. dashed), thickness and colour of
  the selected lines, with a quick choice of ISO 128 line thicknesses
- *Save as PDF* writes all sheets into one PDF; *Export DXF* writes
  one file per sheet
- Lines get thinner on screen when zooming in; saved files, PDF,
  print and export keep the standard line widths

## Compatibility

| | Status |
|---|---|
| FreeCAD 1.1.x | tested (1.1.4, Linux Mint, Flatpak) |
| FreeCAD 1.0.x | source checked: everything available except three assembly buttons (activate assembly, insert new part, motion study) and "Intersection" — these buttons are simply left out of the ribbon |
| FreeCAD development version | source checked (2026-10-18): everything available |
| Qt6/PySide6 and Qt5/PySide2 | both supported (imports via FreeCAD's `PySide` layer) |
| Python | 3.8 or newer |
| Windows, macOS, other Linux packages | not tested; no hard-coded paths, should work — feedback welcome |

## Installation

**Addon Manager.** Inclusion in the official FreeCAD add-on index is
planned. Until then, add the repository by hand: *Edit → Preferences
→ Addon Manager → Custom repositories*, URL
`https://github.com/Schlauminik/LikeSolidWorks-UI`, branch `release`.
Then search for **LikeSolid** in the Addon Manager and install it.

**By hand.** Clone the repository into the `Mod` folder of FreeCAD's
user data directory and restart FreeCAD:

```bash
git clone -b release https://github.com/Schlauminik/LikeSolidWorks-UI.git <user data directory>/Mod/LikeSolidWorks-UI
```

FreeCAD 1.1 uses a separate user data directory per version. The
FreeCAD Python console shows the right one:
`FreeCAD.getUserAppDataDir()`. With the Flatpak on Linux it is
`~/.var/app/org.freecad.FreeCAD/data/FreeCAD/v1-1/`.

Do not install it both ways at the same time — FreeCAD would load two
copies.

## Settings

**Qt message filter.** When zooming far into a drawing sheet, Qt
reports "render glyph failed" for every character (harmless, also
happens without this add-on). The add-on hides exactly this message —
**only while LikeSolidWorks UI is active**. To switch it off
completely: *Tools → Edit parameters →* `BaseApp/Preferences/Mod/SWUI`
→ new Boolean `QtMessageFilter` = `false`, then restart FreeCAD.

**Drag & drop into assemblies** only works in LikeSolidWorks UI.
Elsewhere FreeCAD opens dropped files as usual.

**Context symbol "Sketch".** To switch it off: parameter
`BaseApp/Preferences/Mod/SWUI` → new Boolean `ContextSketch` = `false`
(takes effect immediately).

**Language** is stored in the parameter
`BaseApp/Preferences/Mod/SWUI/Language` (`auto`, `de`, `en`).
More languages: copy `swui/lang/en.py` (e.g. as `fr.py`), adjust
`CODE`, `NAME` and the texts — the language then appears in the menu
automatically. `tools/test_load.py` reports missing texts.

## Troubleshooting

Workbench **LikeSolidWorks UI** → toolbar *SW Diagnose* → button
*Diagnose*: shows all version details with a copy button. For error
messages switch on the report view (*View → Panels → Report view*).

## For developers

```bash
python3 tools/test_load.py .
```

Simulates the way FreeCAD loads the add-on and checks the workbench,
commands, ribbon, translations and much more with mock objects. Source
comments are in German.

## License

| Part | License | File |
|---|---|---|
| Source code (`*.py`) | LGPL-2.1-or-later | `LICENSE-Code` |
| Icons (`resources/icons/`) | CC-BY-SA-4.0 | `LICENSE-Assets` |
| Drawing templates (`resources/templates/`, `tools/template_sources/`) | CC0-1.0 (public domain) | stated in the SVG files |

The drawing templates are derived from FreeCAD's ISO templates (from
FreeCAD 1.1.4), which FreeCAD released as CC0. Every source file
carries an `SPDX-License-Identifier` header.

## Trademarks and legal notes

**SOLIDWORKS is a registered trademark of Dassault Systèmes.** This
project is not affiliated with, endorsed, reviewed or approved by
Dassault Systèmes. The name "LikeSolidWorks UI" only describes what the
interface is modelled on; it is not a product name or trademark of
Dassault Systèmes.

**All icons are original designs**, drawn from scratch
(`tools/make_icons.py`); they are not copies or edits of anyone else's
icons. The drawing templates are edits of FreeCAD's public-domain ISO
templates.

**Standards.** The add-on implements the technical content of ISO 7200
(title block), ISO 1302 (surface finish), ISO 2553 (weld symbols) and
ISO 5456-2 (projection symbol). The texts of the standards are
copyrighted and are neither included nor quoted.

**Font.** The templates refer to `osifont` by name. The font file
belongs to FreeCAD and is not part of this project.

## Disclaimer

This add-on is provided without any warranty. It changes FreeCAD's
interface while the workbench is active and restores the original
state when you leave it. No liability is accepted for data loss or
incorrect drawings — always check technical drawings yourself before
passing them on.
