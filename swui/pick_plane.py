# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 Dominik Ladewig
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Skizze / Linear austragen / Linearer Schnitt OHNE Auswahl - wie in SOLIDWORKS.

Ohne Auswahl zeigt FreeCAD (PartDesign_NewSketch) den Dialog "Ebene
auswaehlen": nur die drei Ursprungsebenen in einer Liste, Flaechen des
Koerpers lassen sich dort nicht waehlen. Linear austragen ohne Skizze
landet im selben Dialog. In SOLIDWORKS dagegen:

  1. Knopf druecken (Skizze, Linear austragen, Linearer Schnitt ...)
  2. "Ebene oder ebene Flaeche waehlen" - Klick in den Grafikbereich,
     in den Baum oder in die Liste
  3. die Skizze oeffnet sich darauf
  4. bei einem Feature-Knopf: "Skizze beenden" startet das Feature mit
     dieser Skizze

So macht es dieses Modul (Einstieg ribbon._run -> handle()). Darunter
arbeitet weiter FreeCADs PartDesign_NewSketch mit Vorauswahl.

Nebenbei: Legt PartDesign_NewSketch selbst einen Koerper an, steht die
Ebenenliste schon da, bevor naming.py die Ebenen umbenennen kann - die
Liste zeigte "XY_Plane" statt "Ebene oben" (unter Windows gemeldet,
25.10.). Hier wird der Koerper vorher angelegt und gleich benannt.
Kommt der Koerper von anderswo (Startseite "Parametrischer Koerper" legt
ihn in Part Design an, aeltere Datei), heissen die Ebenen noch "Plano XY"
o. ae.: rename_default_planes() benennt sie beim Oeffnen des Panels um.
"""

import re
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets
from swui.i18n import N_, tr  # noqa: F401

SKETCH_COMMAND = "PartDesign_NewSketch"
# Features, die nach "Skizze beenden" mit der neuen Skizze starten
FEATURE_COMMANDS = (
    "PartDesign_Pad",
    "PartDesign_Pocket",
    "PartDesign_Revolution",
    "PartDesign_Groove",
)
PLANE_TYPES = ("App::Plane", "PartDesign::Plane")
BODY_TYPE = "PartDesign::Body"
ASSEMBLY_TYPE = "Assembly::AssemblyObject"
POLL_MS = 300
DELAY_MS = 50
SHOW_ORIGIN_MS = 300

_panel = None
_armed = None  # {"command", "sketch"}: Feature nach "Skizze beenden"
_timer = None


# --- Logik (ohne Qt pruefbar) ----------------------------------------


def handle(command):
    """
    True, wenn der Knopf hier uebernommen wurde (keine passende Auswahl).
    False: FreeCAD fuehrt den Befehl wie gewohnt aus (z. B. Skizze gewaehlt).
    """
    if command != SKETCH_COMMAND and command not in FEATURE_COMMANDS:
        return False
    doc = FreeCAD.ActiveDocument
    if doc is None or _dialog_open() or _is_assembly_doc(doc):
        return False
    sel = _selection()
    target = picked_target(sel)
    if sel and target is None:
        return False  # etwas anderes gewaehlt (z. B. eine Skizze): FreeCAD entscheidet
    if command == SKETCH_COMMAND and target is not None:
        return False  # Ebene/Flaeche schon gewaehlt: FreeCAD legt die Skizze direkt an
    _disarm()
    if target is not None:
        start_sketch(command)  # Feature-Knopf mit gewaehlter Ebene/Flaeche
    else:
        open_panel(command)
    return True


def picked_target(sel):
    """
    Genau eine Ebene oder ebene Flaeche gewaehlt? -> (Objekt, Unterelement)
    sonst None. sel = [(Objekt, [Unterelemente])] wie getSelectionEx.
    """
    if len(sel) != 1:
        return None
    obj, subs = sel[0]
    if not subs:
        return (obj, "") if getattr(obj, "TypeId", "") in PLANE_TYPES else None
    if len(subs) != 1:
        return None
    sub = subs[0]
    if getattr(obj, "TypeId", "") in PLANE_TYPES:
        return obj, sub
    from swui import context_sketch

    face = context_sketch.face_of(obj, sub)
    if face is not None and context_sketch.is_planar(face):
        return obj, sub
    return None


def body_planes(body):
    """Ebenen fuer die Liste: Ursprungsebenen des Koerpers, dann Bezugsebenen."""
    out = []
    try:
        out += [f for f in body.Origin.OriginFeatures if getattr(f, "TypeId", "") in PLANE_TYPES]
    except Exception:
        pass
    try:
        out += [o for o in body.Group if getattr(o, "TypeId", "") == "PartDesign::Plane"]
    except Exception:
        pass
    return out


def is_default_plane_label(label, role):
    """
    Von FreeCAD vergebener Name einer Ursprungsebene? "XY_Plane", "Plano XY",
    "XY-Ebene", "Plan XY001" ... (die Achsen der Rolle, dazu hoechstens ein Wort).
    """
    axes = (role or "").split("_")[0]
    if len(axes) != 2:
        return False
    word = r"[^\W\d_]*"
    return re.match(r"^%s[\s_-]*%s[\s_-]*%s\d*$" % (word, axes, word), label or "") is not None


def rename_default_planes(planes):
    """Ursprungsebenen mit FreeCAD-Namen wie in SW benennen ("Planta" ...)."""
    from swui import naming

    for p in planes:
        try:
            if getattr(p, "TypeId", "") != "App::Plane":
                continue
            if not is_default_plane_label(p.Label, getattr(p, "Role", "")):
                continue  # schon SW-Name oder vom Benutzer benannt
            label = naming.sw_label_for(p)
            if label:
                p.Label = label
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI] Ebene umbenennen: %s" % traceback.format_exc())


def _selection():
    try:
        return [(s.Object, list(s.SubElementNames or [])) for s in FreeCADGui.Selection.getSelectionEx()]
    except Exception:
        return []


def _dialog_open():
    try:
        return bool(FreeCADGui.Control.activeDialog())
    except Exception:
        return False


def _is_assembly_doc(doc):
    return any(getattr(o, "TypeId", "") == ASSEMBLY_TYPE for o in doc.Objects)


def active_body(create=True):
    """Aktiver Koerper; gibt es genau einen, wird er aktiv; keinen -> neu (SW-benannt)."""
    try:
        view = FreeCADGui.ActiveDocument.ActiveView
        body = view.getActiveObject("pdbody")
    except Exception:
        view, body = None, None
    if body is not None:
        return body
    doc = FreeCAD.ActiveDocument
    bodies = [o for o in doc.Objects if getattr(o, "TypeId", "") == BODY_TYPE]
    if len(bodies) == 1:
        body = bodies[0]
    elif not bodies and create:
        FreeCADGui.runCommand("PartDesign_Body")
        body = view.getActiveObject("pdbody") if view is not None else None
        try:
            from swui import naming

            naming._flush()  # Ebenen sofort "Ebene oben" ... nennen, nicht erst spaeter
        except Exception:
            pass
        return body
    if body is not None and view is not None:
        view.setActiveObject("pdbody", body)
    return body


# --- Ablauf ----------------------------------------------------------


def start_sketch(command):
    """Skizze auf der gewaehlten Ebene/Flaeche; bei Feature-Knopf das Feature vormerken."""
    before = set(o.Name for o in FreeCAD.ActiveDocument.Objects)
    FreeCADGui.runCommand(SKETCH_COMMAND)
    if command == SKETCH_COMMAND:
        return
    new = [o for o in FreeCAD.ActiveDocument.Objects
           if o.Name not in before and o.TypeId == "Sketcher::SketchObject"]
    if new:
        arm(command, new[-1])


def arm(command, sketch):
    """Nach "Skizze beenden" command mit sketch starten."""
    global _armed, _timer
    _armed = {"command": command, "sketch": sketch, "seen_edit": False}
    if _timer is None:
        _timer = QtCore.QTimer()
        _timer.setInterval(POLL_MS)
        _timer.timeout.connect(tick)
    _timer.start()


def _disarm():
    global _armed
    _armed = None
    if _timer is not None:
        _timer.stop()


def armed():
    return dict(_armed) if _armed else None


def tick():
    """Laeuft, solange ein Feature vorgemerkt ist: Skizze beendet? -> Feature starten."""
    if not _armed:
        _disarm()
        return
    sketch = _armed["sketch"]
    try:
        editing = _editing() is sketch
        alive = sketch.Document is not None and sketch.Name in [o.Name for o in sketch.Document.Objects]
    except Exception:
        alive = False
    if not alive:
        _disarm()  # Skizze geloescht / Rueckgaengig
        return
    if editing:
        _armed["seen_edit"] = True
        return
    if not _armed["seen_edit"] or _dialog_open():
        return
    command = _armed["command"]
    _disarm()
    if _used_by_feature(sketch) or not _has_geometry(sketch):
        return  # schon per Ribbon aus der Skizze ausgetragen (from_sketch) oder leer
    try:
        sel = FreeCADGui.Selection
        sel.clearSelection()
        sel.addSelection(sketch)
        FreeCADGui.runCommand(command)
    except Exception as exc:
        FreeCAD.Console.PrintError(tr("[SWUI] Befehl %s fehlgeschlagen: %s\n") % (command, exc))


def _editing():
    try:
        vp = FreeCADGui.ActiveDocument.getInEdit()
        return vp.Object if vp is not None else None
    except Exception:
        return None


def _used_by_feature(sketch):
    try:
        return any(getattr(o, "Profile", None) and o.Profile[0] is sketch for o in sketch.InList)
    except Exception:
        return False


def _is_empty(body):
    try:
        return body.Shape.isNull() or not body.Shape.Solids
    except Exception:
        return True


def _has_geometry(sketch):
    try:
        return len(sketch.Geometry) > 0
    except Exception:
        return True


# --- Panel "Ebene waehlen" -------------------------------------------


def open_panel(command):
    global _panel
    try:
        body = active_body()
        _panel = _TaskPanel(command, body)
        FreeCADGui.Control.showDialog(_panel)
        _panel.start()
    except Exception:
        FreeCAD.Console.PrintError(tr("[SWUI] Ebene wählen: %s\n") % traceback.format_exc())


def picked(target, command):
    """Ebene/Flaeche gewaehlt: Panel schliessen, Auswahl setzen, Skizze anlegen."""
    obj, sub = target
    try:
        FreeCADGui.Control.closeDialog()
    except Exception:
        pass

    def go():
        try:
            sel = FreeCADGui.Selection
            sel.clearSelection()
            if sub:
                sel.addSelection(obj, sub)
            else:
                sel.addSelection(obj)
            start_sketch(command)
        except Exception:
            FreeCAD.Console.PrintError(tr("[SWUI] Ebene wählen: %s\n") % traceback.format_exc())

    QtCore.QTimer.singleShot(DELAY_MS, go)


class _SelectionWatcher:
    """FreeCAD-Auswahlbeobachter: jede neue Auswahl an das Panel melden."""

    def __init__(self, panel):
        self.panel = panel

    def addSelection(self, *_args):
        QtCore.QTimer.singleShot(0, self.panel.check_selection)


class _TaskPanel:
    """Wie SOLIDWORKS: Ebene oder ebene Flaeche waehlen (Grafikbereich, Baum oder Liste)."""

    def __init__(self, command, body):
        self.command = command
        self.body = body
        self.done = False
        self.shown = []  # (ViewObject, alte Sichtbarkeit) - Ursprung zum Waehlen eingeblendet
        self.form = QtWidgets.QWidget()
        self.form.setObjectName("SWUI_PickPlane")
        self.form.setWindowTitle(tr("Skizze: Ebene wählen"))
        lay = QtWidgets.QVBoxLayout(self.form)
        hint = QtWidgets.QLabel(tr("Eine Ebene oder ebene Fläche im Grafikbereich, im Baum oder in der Liste wählen."))
        hint.setWordWrap(True)
        lay.addWidget(hint)
        self.list = QtWidgets.QListWidget(self.form)
        self.planes = body_planes(body) if body is not None else []
        rename_default_planes(self.planes)
        for p in self.planes:
            self.list.addItem(p.Label)
        self.list.itemClicked.connect(self._list_clicked)
        lay.addWidget(self.list)
        self.message = QtWidgets.QLabel("")
        self.message.setWordWrap(True)
        lay.addWidget(self.message)
        self.watcher = _SelectionWatcher(self)

    def start(self):
        FreeCADGui.Selection.clearSelection()
        FreeCADGui.Selection.addObserver(self.watcher)
        # Ein neuer Koerper blendet seinen Ursprung kurz danach selbst aus - deshalb verzoegert
        QtCore.QTimer.singleShot(SHOW_ORIGIN_MS, self._show_origin)

    def _show_origin(self):
        if self.done:
            return
        try:
            origin = self.body.Origin
            for o in [origin] + [p for p in self.planes if p in origin.OriginFeatures]:
                self.shown.append((o.ViewObject, o.ViewObject.Visibility))
                o.ViewObject.Visibility = True
            if _is_empty(self.body):
                view = FreeCADGui.ActiveDocument.ActiveView
                view.viewIsometric()  # alle drei Ebenen sichtbar (leeres Teil)
                view.fitAll()
        except Exception:
            FreeCAD.Console.PrintLog("[SWUI] Ursprung zeigen: %s" % traceback.format_exc())

    def _cleanup(self):
        try:
            FreeCADGui.Selection.removeObserver(self.watcher)
        except Exception:
            pass
        for vo, vis in reversed(self.shown):
            try:
                vo.Visibility = vis
            except Exception:
                pass
        self.shown = []

    def _list_clicked(self, item):
        row = self.list.row(item)
        if 0 <= row < len(self.planes):
            # Erst nach dem Klick schliessen: closeDialog loescht die Liste, deren
            # Mausereignis noch laeuft -> "Access violation" (unter Windows gemeldet, 25.10.)
            plane = self.planes[row]
            QtCore.QTimer.singleShot(0, lambda: self._take((plane, "")))

    def check_selection(self):
        if self.done:
            return
        sel = _selection()
        if not sel:
            return
        target = picked_target(sel)
        if target is None:
            self.message.setText(tr("Das ist keine Ebene und keine ebene Fläche."))
            FreeCADGui.Selection.clearSelection()
            return
        self._take(target)

    def _take(self, target):
        if self.done:
            return
        self.done = True
        self._cleanup()
        picked(target, self.command)

    def getStandardButtons(self):
        cancel = QtWidgets.QDialogButtonBox.StandardButton.Cancel
        return int(getattr(cancel, "value", cancel))  # nur "Abbrechen" (Qt6-Enum / Qt5-int)

    def reject(self):
        if self.done:
            return True
        self.done = True
        self._cleanup()
        FreeCADGui.Control.closeDialog()
        return True

    def accept(self):
        return self.reject()
