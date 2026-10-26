# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 Dominik Ladewig
"""
Simuliert, wie FreeCAD eine Workbench laedt.

Zwei Fallstricke, die FreeCAD hat und ein normaler Python-Import nicht:

1. __file__ ist NICHT definiert. FreeCAD wertet den Quelltext aus,
   statt die Datei als Modul zu importieren.

2. exec() laeuft mit GETRENNTEN Namensraeumen fuer Globals und Locals.
   Folge: Funktionen finden Namen auf Modulebene noch, KLASSENRUEMPFE
   aber nicht. Eine Zeile wie

       class Foo:
           Icon = os.path.join(_HERE, "x.svg")

   bricht dann mit "name '_HERE' is not defined" ab, obwohl _HERE
   drei Zeilen darueber zugewiesen wurde.

Deshalb wird hier in BEIDEN Varianten geladen. Faellt eine davon
durch, ist der Test rot.

Aufruf:
    python3 tools/test_load.py /pfad/zum/addon
"""

import math
import os
import sys
import types
from unittest import mock

ADDON = os.path.abspath(sys.argv[1])
SCRATCH_TMP = __import__("tempfile").mkdtemp(prefix="swui_test_")

log = []

# Diese Befehle gibt es in der Attrappe absichtlich nicht - prueft,
# dass das Ribbon fehlende Befehle sauber auslaesst.
VIEW = "User parameter:BaseApp/Preferences/View"
ORIGINAL_VIEW = {"Simple": True, "BackgroundColor2": 123456}
ORIGINAL_OVERLAY_RIGHT = {"Widgets": "Tasks,", "Transparent": True}

MISSING = {
    "PartDesign_SubtractiveLoft",
    "Sketcher_Projection",  # prueft den Ersatzbefehl
    "Sketcher_CreateArcSlot",  # prueft Ausklappknopf mit fehlender Variante
}

# Ersatzbefehle, die es in der Attrappe gibt (fuer "fallback" im Layout).
# Befehle, die nicht im Ribbon stehen, aber in FreeCAD 1.1.4 sicher
# existieren (geprueft in CommandConstraints.cpp, CreateSketcherCommandsConstraints):
# Sketcher_ConstrainCoincident nutzt das Beziehungs-Panel.
EXTRA_AVAILABLE = {"Sketcher_External", "Sketcher_ConstrainCoincident"}


def _all_layout_commands(filename="ribbon_layout.py"):
    """Alle Befehls-IDs aus einer Layout-Datei, ohne swui zu importieren."""
    import ast

    path = os.path.join(ADDON, "swui", filename)
    if not os.path.isfile(path):
        return []
    tree = ast.parse(open(path, encoding="utf-8").read())
    names = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Tuple) and len(node.elts) in (2, 3):
            first, second = node.elts[0], node.elts[1]
            if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
                continue
            if not (isinstance(second, ast.Constant) and isinstance(second.value, str)):
                continue
            if "_" in first.value and first.value.split("_")[0] in (
                "PartDesign",
                "Sketcher",
                "Std",
                "Part",
                "SWUI",
                "Assembly",
                "TechDraw",
            ):
                name = first.value
                if len(node.elts) == 3:
                    opts = ast.literal_eval(node.elts[2])
                    if opts.get("index") is not None:
                        name = "%s#%d" % (name, opts["index"])
                    if opts.get("fallback"):
                        _FALLBACKS[name] = list(opts["fallback"])
                names.append(name)
    return names


_FALLBACKS = {}


# fork: la pestaña Evaluar cambia la tabla del original desde swui/fork/evaluate_tab.py
FORK_REPLACED = {"Std_Measure": "SWUI_Measure"}


def _fork_layout_commands():
    return _all_layout_commands(os.path.join("fork", "evaluate_tab.py"))


def _expected_buttons():
    """Welche Knopf-IDs gebaut und welche Befehle ausgelassen werden muessen."""
    available = ({c.split("#")[0] for c in _all_layout_commands() + _fork_layout_commands()}
                 | EXTRA_AVAILABLE) - MISSING
    built, skipped = [], []
    layout_ids = [FORK_REPLACED.get(c, c) for c in _all_layout_commands()]  # fork
    layout_ids += [c for c in _fork_layout_commands() if c not in layout_ids]  # fork
    for cid in layout_ids:
        cmd = cid.split("#")[0]
        if cmd in available:
            built.append(cid)
            continue
        alt = next((f for f in _FALLBACKS.get(cid, []) if f in available), None)
        if alt:
            built.append(alt)
        else:
            skipped.append(cmd)
    return built, skipped


# --- Attrappen -------------------------------------------------------


class _FakeTree:
    """Baum im Modell-Panel: nur das eigene Stylesheet."""

    def __init__(self):
        self.qss = "/* FreeCAD-Baum */"

    def styleSheet(self):
        return self.qss

    def setStyleSheet(self, qss):
        self.qss = qss


class _FakeBar:
    """Toolbar oder Dock: Name, Sichtbarkeit, Bereich."""

    def __init__(self, name, area="top", visible=True):
        self.name = name
        self.area = area
        self.visible = visible
        self.trees = [_FakeTree()] if name == "Model" else []
        # Wie bei Dominik nach dem Werkbank-Wechsel: Ausgabefenster schwebt.
        self.floating = name == "Report view"

    def isFloating(self):
        return self.floating

    def setFloating(self, value):
        self.floating = bool(value)

    def findChildren(self, cls, name=None):
        return list(self.trees)

    def objectName(self):
        return self.name

    def isVisible(self):
        return self.visible

    def hide(self):
        self.visible = False

    def show(self):
        self.visible = True

    def raise_(self):
        _FakeMainWindow.current.raised.append(self.name)


class _FakeMainWindow:
    """Hauptfenster mit FreeCAD-typischen Leisten und Panels."""

    current = None

    def __init__(self):
        _FakeMainWindow.current = self
        self.toolbars = [
            _FakeBar(n)
            for n in ("File", "Edit", "Workbench", "View", "Structure", "Macro", "Help")
        ]
        # Leiste innerhalb eines Panels: darf NICHT angefasst werden.
        self.toolbars.append(_FakeBar("InnerPanelBar", area=None))
        # Echte Namen aus FreeCAD 1.1 (Ausgabefenster vom 15.10.)
        self.docks = [
            _FakeBar("Model", area="left"),
            _FakeBar("Tasks", area="right"),
            _FakeBar("Report view", area="right"),
            _FakeBar("Python console", area="bottom"),
            _FakeBar("Selection view", area="right"),
        ]
        self.raised = []
        self.tabified = []
        self.split = []
        # So tut, als haette FreeCAD bereits ein eigenes Stylesheet.
        self.ORIGINAL_QSS = "/* FreeCAD-Theme */\nQWidget { color: #ff0000; }"
        self.qss = self.ORIGINAL_QSS
        self.restore_count = 0
        self.filters = 0
        self.dialog_open = False
        self.actions = []  # fork: teclas N y F (view_keys.py)

    def addAction(self, action):
        self.actions.append(action)

    def removeAction(self, action):
        if action in self.actions:
            self.actions.remove(action)

    def findChildren(self, cls, name=None):
        qtw = sys.modules["PySide"].QtWidgets
        if name is not None:  # Suche nach Objektname (Feature-Dialoge)
            return list(getattr(self, "dialog_roots", {}).get(name, []))
        if cls is qtw.QToolBar:
            return list(self.toolbars)
        if cls is qtw.QDockWidget:
            return list(self.docks)
        return []

    def toolBarArea(self, tb):
        return tb.area if tb.area else sys.modules["PySide"].QtCore.Qt.ToolBarArea.NoToolBarArea

    def saveState(self):
        return {
            "bars": {b.name: b.visible for b in self.toolbars + self.docks},
            "areas": {d.name: d.area for d in self.docks},
        }

    def restoreState(self, state):
        self.restore_count += 1
        for b in self.toolbars + self.docks:
            if b.name in state["bars"]:
                b.visible = state["bars"][b.name]
        for d in self.docks:
            d.area = state["areas"].get(d.name, d.area)
        self.tabified = []

    def addDockWidget(self, area, dock):
        if isinstance(dock, _FakeBar):
            dock.area = area

    def splitDockWidget(self, first, second, orientation):
        self.split.append((first.name, second.name, orientation))

    def tabifyDockWidget(self, first, second):
        self.tabified.append((first.name, second.name))

    def installEventFilter(self, _obj):
        self.filters += 1

    def isVisible(self):
        return True

    def styleSheet(self):
        return self.qss

    def setStyleSheet(self, qss):
        self.qss = qss

    def visible_bars(self):
        return sorted(b.name for b in self.toolbars if b.visible)


def _make_stubs():
    """Baut frische FreeCAD-/Qt-Attrappen und haengt sie in sys.modules."""
    registered = {}
    commands = {}

    class _Console:
        @staticmethod
        def PrintMessage(t):
            log.append(("MSG", t.rstrip()))

        @staticmethod
        def PrintWarning(t):
            log.append(("WARN", t.rstrip()))

        @staticmethod
        def PrintError(t):
            log.append(("ERR", t.rstrip()))

        @staticmethod
        def PrintLog(t):
            log.append(("LOG", t.rstrip()))

    freecad = types.ModuleType("FreeCAD")
    freecad.Console = _Console
    freecad.Version = lambda: ["1", "1", "4", "FreeCAD-Attrappe"]
    freecad.getUserAppDataDir = lambda: "/fake/appdata/"

    # FreeCADs Einstellungsspeicher (ParamGet) als einfaches dict.
    params = {}

    class _Group:
        def __init__(self, path):
            self.d = params.setdefault(path, {})

        def GetString(self, key, default=""):
            return self.d.get(key, default)

        def SetString(self, key, value):
            self.d[key] = value

        # Bool/Unsigned wie FreeCAD: Get mit Standard, Set, Remove.
        def GetBool(self, key, default=False):
            return self.d.get(key, default)

        def SetBool(self, key, value):
            self.d[key] = bool(value)

        # Namen wie in FreeCAD (src/Base/ParameterPy.cpp): Rem..., nicht Remove...
        def RemBool(self, key):
            self.d.pop(key, None)

        def RemString(self, key):
            self.d.pop(key, None)

        def GetUnsigned(self, key, default=0):
            return self.d.get(key, default)

        def SetUnsigned(self, key, value):
            self.d[key] = int(value)

        def RemUnsigned(self, key):
            self.d.pop(key, None)

        def GetFloat(self, key, default=0.0):
            return self.d.get(key, default)

        def SetFloat(self, key, value):
            self.d[key] = float(value)

        def RemFloat(self, key):
            self.d.pop(key, None)

        def GetInt(self, key, default=0):
            return self.d.get(key, default)

        def SetInt(self, key, value):
            self.d[key] = int(value)

        def RemInt(self, key):
            self.d.pop(key, None)

        def GetContents(self):
            return [("?", k, v) for k, v in self.d.items()]

    class Vector:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            self.x, self.y, self.z = float(x), float(y), float(z)

        def __repr__(self):
            return "V(%g,%g,%g)" % (self.x, self.y, self.z)

    class _Rot:
        def multVec(self, v):
            return v

    class Placement:  # Skizze liegt im Ursprung (Identitaet)
        Rotation = _Rot()

        def inverse(self):
            return self

        def multVec(self, v):
            return v

    freecad.Vector = Vector
    freecad.Placement = Placement
    part = types.ModuleType("Part")
    part.LineSegment = lambda a, b: ("Line", (a.x, a.y), (b.x, b.y))
    sys.modules["Part"] = part
    sketcher = types.ModuleType("Sketcher")
    sketcher.Constraint = lambda *a: a
    sys.modules["Sketcher"] = sketcher
    sys.modules["pivy"] = mock.MagicMock(name="pivy")
    sys.modules["pivy.coin"] = sys.modules["pivy"].coin

    freecad._observers = []
    freecad.addDocumentObserver = lambda o: freecad._observers.append(o)
    freecad.ParamGet = _Group
    freecad._params = params
    # Ausgangszustand von Dominiks Ansichts-Einstellungen (ausgedacht):
    # zwei Schluessel existieren, alle anderen nicht.
    params["User parameter:BaseApp/Preferences/View"] = dict(ORIGINAL_VIEW)
    # FreeCAD 1.1-Standard: Aufgaben rechts ueberlagert; links nie benutzt.
    params["User parameter:BaseApp/MainWindow/DockWindows/OverlayRight"] = dict(ORIGINAL_OVERLAY_RIGHT)

    gui = types.ModuleType("FreeCADGui")
    gui.Workbench = type("Workbench", (), {})
    gui.listWorkbenches = lambda: dict(registered)
    gui.addWorkbench = lambda obj: registered.setdefault(type(obj).__name__, obj)
    gui.addCommand = lambda name, obj: commands.setdefault(name, obj)
    gui._doc_observers = []  # fork: panel de redondeo (slotInEdit)
    gui.addDocumentObserver = lambda o: gui._doc_observers.append(o)

    # Ribbon und Layout brauchen: Hauptfenster, Befehlsliste, Befehle.
    # Das Hauptfenster ist eine echte kleine Attrappe mit Zustand, damit
    # pruefbar ist, was ein- und ausgeblendet und wiederhergestellt wird.
    mw = _FakeMainWindow()
    gui.getMainWindow = lambda: mw
    gui._mw = mw
    gui.Control = types.SimpleNamespace(activeDialog=lambda: mw.dialog_open)
    gui._active_wb = "LikeSolidWorksUIWorkbench"
    gui.getLocale = lambda: "German"  # FreeCAD auf Deutsch (wie bei Dominik)
    gui.activeWorkbench = lambda: types.SimpleNamespace(name=lambda: gui._active_wb)

    # FreeCADs Show-Modul: TempoVis wechselt beim Skizzieren die Workbench.
    switched = []

    class TempoVis:
        def activateWorkbench(self, wb_name):
            switched.append(wb_name)

    show = types.ModuleType("Show")
    show.mTempoVis = types.ModuleType("Show.mTempoVis")
    show.mTempoVis.TempoVis = TempoVis
    show.TempoVis = TempoVis
    show._switched = switched
    sys.modules["Show"] = show
    sys.modules["Show.mTempoVis"] = show.mTempoVis
    gui.ActiveDocument = None
    gui.listCommands = lambda: sorted(
        (
            {c.split("#")[0] for c in _all_layout_commands() + _fork_layout_commands()}
            | EXTRA_AVAILABLE
        )
        - MISSING
    )
    ran = []
    gui.runCommand = lambda name, *idx: ran.append((name,) + idx)

    # Auswahl (fuer das Beziehungs-Panel)
    gui._sel = []
    gui._sel_observers = []
    gui.Selection = types.SimpleNamespace(
        addObserver=lambda o: gui._sel_observers.append(o),
        removeObserver=lambda o: gui._sel_observers.remove(o),
        getSelectionEx=lambda *_a: list(gui._sel),
    )
    gui._ran = ran

    class _Cmd:
        def __init__(self, name):
            self.name = name

        def getInfo(self):
            return {
                "menuText": self.name,
                "toolTip": "<b>%s</b> Tooltip" % self.name,
                "pixmap": self.name,
            }

        def getAction(self):
            return []

        def isActive(self):
            return not self.name.startswith("Sketcher_")

    gui.Command = types.SimpleNamespace(get=_Cmd)

    sys.modules["FreeCAD"] = freecad
    sys.modules["FreeCADGui"] = gui

    # Qt als MagicMock: nimmt jeden Aufruf an. Findet keine Qt-Fehl-
    # bedienung, aber jeden Python-Fehler (Tippfehler, Namensraeume,
    # falsche Argumente an eigene Funktionen).
    pyside = mock.MagicMock(name="PySide")
    pyside.QtCore.qVersion = lambda: "6.0.0-Attrappe"
    sys.modules["PySide"] = pyside
    for sub in ("QtCore", "QtGui", "QtWidgets"):
        sys.modules["PySide." + sub] = getattr(pyside, sub)

    # draftutils absichtlich NICHT bereitstellen: compat.py muss fehlende
    # optionale Module sauber abfangen. (Sketcher und pivy sind oben als
    # Attrappen angelegt - die Mittelpunktlinie braucht sie.)
    sys.modules.pop("draftutils", None)

    return registered, commands


def _clear_addon_modules():
    """swui-Module zwischen den Durchlaeufen entfernen."""
    for name in [n for n in sys.modules if n == "swui" or n.startswith("swui.")]:
        del sys.modules[name]


def _check_qss(qss):
    """Grobe Syntaxpruefung fuer Qt-Stylesheets."""
    import re

    if "%(" in qss:
        return False, "nicht ersetzter Platzhalter"
    depth = 0
    for ch in qss:
        depth += ch == "{"
        depth -= ch == "}"
        if depth < 0 or depth > 1:
            return False, "Klammern verschachtelt/unausgeglichen"
    if depth:
        return False, "Klammern unausgeglichen"
    body = re.sub(r"/\*.*?\*/", "", qss, flags=re.S)
    for block in re.findall(r"\{([^}]*)\}", body):
        for decl in [d.strip() for d in block.split(";") if d.strip()]:
            if ":" not in decl:
                return False, "Deklaration ohne Doppelpunkt: %r" % decl
            key, val = [x.strip() for x in decl.split(":", 1)]
            if not key or not val:
                return False, "leere Eigenschaft: %r" % decl
            for col in re.findall(r"#[0-9a-fA-F]+\b", val):
                if len(col) not in (4, 7, 9):
                    return False, "Farbe ungueltig: %s" % col
    return True, ""


# --- Ein Durchlauf ---------------------------------------------------


def _check_feature_tree(commands, mw, layout, hooked):
    """Fork: árbol de operaciones como el FeatureManager de SW (lógica con objetos falsos)."""
    ft = sys.modules["swui.fork.feature_tree"]
    rk = sys.modules["swui.fork.rebuild_keys"]
    import importlib

    td = importlib.import_module("swui.fork.tree_dialogs")  # se carga recién al abrir un diálogo

    class _Obj:
        """Objeto de Part Design falso: kind = feat / sketch / body; vínculos como propiedades."""

        def __init__(self, name, kind, **links):
            self.Name = self.Label = name
            self.kind = kind
            self.TypeId = "PartDesign::Body" if kind == "body" else "x"
            self.props = dict(links)
            self.extra = {}
            self.Suppressed = False
            self.MapMode = "FlatFace"
            self.InList = []
            self.body = None

        def __getattr__(self, name):
            props = self.__dict__.get("props", {})
            if name in props:
                return props[name]
            if name in self.__dict__.get("extra", {}):
                return self.__dict__["extra"][name]
            raise AttributeError(name)

        @property
        def PropertiesList(self):
            return list(self.props) + list(self.extra) + (["MapMode"] if self.kind == "sketch" else [])

        def getTypeIdOfProperty(self, name):
            return "App::PropertyLink" if name in self.props else "App::PropertyString"

        def isDerivedFrom(self, t):
            return {"PartDesign::Feature": self.kind == "feat", "Sketcher::SketchObject": self.kind == "sketch"}.get(t, False)

        def getParentGeoFeatureGroup(self):
            return self.body

        def addProperty(self, _type, name, *_a):
            self.extra[name] = ""

        def setPropertyStatus(self, *_a):
            pass

        def removeProperty(self, name):
            self.extra.pop(name, None)

        def __setattr__(self, name, value):
            if "extra" in self.__dict__ and name in self.__dict__["extra"]:
                self.__dict__["extra"][name] = value
            else:
                object.__setattr__(self, name, value)

    body = _Obj("Body", "body")
    sk1 = _Obj("Croquis1", "sketch")
    pad = _Obj("Extruir1", "feat", Profile=(sk1, []), BaseFeature=None, _Body=body)
    sk2 = _Obj("Croquis2", "sketch", AttachmentSupport=[(pad, ("Face3",))])
    pocket = _Obj("Corte1", "feat", Profile=(sk2, []), BaseFeature=pad, _Body=body)
    fillet = _Obj("Redondeo1", "feat", Base=(pocket, ["Edge1"]), BaseFeature=pocket, _Body=body)
    group = [sk1, pad, sk2, pocket, fillet]
    for o in group:
        o.body = body
        o.InList = [p for p in group if o in ft.links(p) or getattr(p, "BaseFeature", None) is o] + [body]
    body.Group, body.Tip = group, fillet
    feats = ft.features(body)
    if (feats != [pad, pocket, fillet] or ft.rollback_target(feats, pocket) is not pad
            or ft.rollback_target(feats, pad) is not None or ft.forward_target(feats, None) is not pad
            or ft.forward_target(feats, pad) is not pocket or ft.forward_target(feats, fillet) is not None
            or ft.rolled_back(feats, fillet) or not ft.rolled_back(feats, pad)):
        print("  FEHLER: fork: árbol: retroceder/avanzar (punta del cuerpo)")
        return False
    # Padres/hijos sin contar el "sólido anterior" (BaseFeature)
    if (ft.parents(pocket) != [sk2] or ft.children(pad) != [sk2] or ft.dependents(pad) != [sk2, pocket, fillet]
            or ft.parents(fillet) != [pocket] or ft.children(sk1) != [pad]):
        print("  FEHLER: fork: árbol: padre/hijo", [o.Name for o in ft.dependents(pad)])
        return False
    # Suprimir como SW: también los dependientes; el croquis apoyado en la cara suprimida se suelta
    done = ft.suppress(pad)
    if (done != [pad, pocket, fillet] or sk2.MapMode != ft.OFF or getattr(sk2, ft.MAPMODE_PROP) != "FlatFace"
            or ft.menu_commands([pad])[2:4] != [ft.UNSUPPRESS, ft.UNSUPPRESS_ALL]):
        print("  FEHLER: fork: árbol: suprimir con dependientes", [o.Name for o in done], sk2.MapMode)
        return False
    ft.unsuppress(pad)  # sin dependientes: el apoyo vuelve, el corte sigue suprimido
    if pad.Suppressed or not pocket.Suppressed or sk2.MapMode != "FlatFace" or ft.MAPMODE_PROP in sk2.PropertiesList:
        print("  FEHLER: fork: árbol: desactivar supresión (apoyo del croquis devuelto)")
        return False
    ft.unsuppress(pad, with_children=True)
    if pocket.Suppressed or fillet.Suppressed:
        print("  FEHLER: fork: árbol: desactivar supresión con dependientes")
        return False
    menu = ft.menu_commands([pocket])
    body.Tip = pad
    menu_back = ft.menu_commands([sk2])
    if (menu != [ft.EDIT, ft.EDIT_SKETCH, ft.SUPPRESS, ft.ROLLBACK, ft.MOVE_UP, ft.MOVE_DOWN, ft.PARENT_CHILD]
            or menu_back != [ft.EDIT_SKETCH, ft.ROLL_FORWARD, ft.ROLL_END, ft.PARENT_CHILD]
            or ft.menu_commands([body]) != []):
        print("  FEHLER: fork: árbol: comandos del clic derecho", menu, menu_back)
        return False
    missing = [n for n, _c in ft.COMMANDS if n not in commands] + [
        n for n in (rk.REBUILD, rk.FORCE_REBUILD, rk.WHATS_WRONG) if n not in commands]
    if missing:
        print("  FEHLER: fork: árbol: comandos sin registrar", missing)
        return False
    # Teclas: Ctrl+B, Ctrl+Q y barra espaciadora = Medir (como en el SW del usuario)
    if (rk.keys() != [("Ctrl+B", rk.REBUILD), ("Ctrl+Q", rk.FORCE_REBUILD), ("Space", "SWUI_Measure")]
            or len(rk._actions) != 3 or not hooked(layout.enter, "_swui_rebuild")
            or not hooked(layout.leave, "_swui_rebuild")):
        print("  FEHLER: fork: teclas Ctrl+B / Ctrl+Q / barra espaciadora (Medir)", len(mw.actions))
        return False
    if (td.explain("AttachEngine3D: subshape not found Pad.Face3").startswith("Perdió") is False
            or td.explain("Cannot create a pad with a total length of zero.") != "La profundidad es cero."
            or td.explain("Pocket: does not intersect") != "La operación no toca el sólido."
            or not td.explain("Base feature's TopoShape is invalid").startswith("No hay sólido")
            or td.explain("algo raro") != td.UNKNOWN_TEXT):
        print("  FEHLER: fork: ¿Qué es incorrecto? (mensajes en palabras simples)")
        return False
    class _Act:
        def __init__(self, name):
            self.name, self.visible = name, True

        def objectName(self):
            return self.name

        def isSeparator(self):
            return self.name == "Separator"

        def isVisible(self):
            return self.visible

        def setVisible(self, on):
            self.visible = on

    class _Menu:
        def __init__(self, names):
            self.acts = [_Act(n) for n in names]

        def actions(self):
            return list(self.acts)

        def insertActions(self, before, moved):
            rest = [a for a in self.acts if a not in moved]
            i = rest.index(before)
            self.acts = rest[:i] + list(moved) + rest[i:]

    menu_q = _Menu(["", "Std_ToggleFreeze", ft.EDIT, ft.SUPPRESS, "Separator", "Std_Placement"])
    if (not ft.arrange_menu(menu_q) or [a.name for a in menu_q.acts] != [ft.EDIT, ft.SUPPRESS, "Separator", "",
                                                                       "Std_ToggleFreeze", "Std_Placement"]
            or menu_q.acts[4].visible):
        print("  FEHLER: fork: lo nuestro arriba del clic derecho y sin 'Toggle Freeze'")
        return False
    # Etapa B: mover con chequeo, barra arrastrable, STEP al lado
    if (ft.move_blocker(pocket, "up") is None or ft.move_blocker(pad, "down") is None
            or ft.move_blocker(pad, "up") is None or ft.move_blocker(fillet, "down") is None):
        print("  FEHLER: fork: árbol: mover arriba/abajo sin romper dependencias")
        return False
    to = importlib.import_module("swui.fork.tree_overlay")
    rows_g = [(sk1, 10, 30, False), (pad, 30, 50, True), (sk2, 50, 60, False), (pocket, 60, 80, True)]
    g = to.gaps(rows_g)
    # el croquis suelto de arriba no cambia la punta: la barra "antes de todo" queda debajo de él
    if (g != [(30, None), (60, pad), (80, pocket)] or to.nearest(g, 57) != (60, pad)
            or to.bar_y(g, pocket) != 80 or to.bar_y(g, None) != 30 or to.gaps([]) != []):
        print("  FEHLER: fork: barra de retroceso (lugares donde puede quedar)", g)
        return False
    class _Pick:
        def __init__(self, obj, subs):
            self.Object, self.SubElementNames, self.SubObjects = obj, subs, [None] * len(subs)

    # Tocado en la vista -> marcar la operación (y apagar el resaltado del árbol); desde el árbol -> nada
    if (to.view_marks([_Pick(pocket, ["Edge1"]), _Pick(pocket, ["Vertex2"])]) != [pocket]
            or to.view_marks([_Pick(pocket, [])]) is not None or to.view_marks([]) is not None
            or to.view_marks([_Pick(pocket, ["Edge1"]), _Pick(pad, [])]) is not None
            or to.view_marks([_Pick(sk2, ["Edge1"])]) is not None):
        print("  FEHLER: fork: árbol: marca de lo tocado en la vista")
        return False
    sc = sys.modules["swui.fork.step_copy"]

    class _Shape:
        def __init__(self, kind, part=False, two_d=False):
            self.TypeId, self.part, self.two_d = kind, part, two_d

        def isDerivedFrom(self, t):
            return {"Part::Feature": self.part, "Part::Part2DObject": self.two_d}.get(t, False)

    shapes = [_Shape("PartDesign::Body"), _Shape("Sketcher::SketchObject", True, True), _Shape("Part::Feature", True),
              _Shape("TechDraw::DrawPage"), _Shape("App::Part")]
    if (sc.step_path("C:/x/pieza.FCStd") != "C:/x/pieza.step" or [s.TypeId for s in sc.exportable(shapes)]
            != ["PartDesign::Body", "Part::Feature", "App::Part"] or sc.enabled() or sc.COMMAND not in commands):
        print("  FEHLER: fork: guardar también STEP (nombre, qué se exporta, apagado de fábrica)")
        return False
    # Aristas del modelo en el croquis (se traen solas al tocarlas con una herramienta)
    me = sys.modules["swui.fork.sketch_model_edges"]
    class _Sk:
        ExternalGeometry = [(pad, ("Edge10",))]

    verts = [(("Pad", "Vertex1"), (100, 100), 0.0)]
    # dos aristas superpuestas en pantalla: gana la que está sobre el plano del croquis (lejanía 0)
    edges_s = [(("Pad", "Edge3"), [(0, 50), (200, 50)], 10.0), (("Pad", "Edge4"), [(0, 50), (200, 50)], 0.0),
               (("Pad", "Edge5"), [(0, 80), (200, 80)], 0.0)]
    if (me.choose((105, 96), verts, edges_s) != (("Pad", "Vertex1"), (100, 100))
            or me.choose((60, 57), verts, edges_s) != (("Pad", "Edge4"), (60.0, 50.0))
            or me.choose((60, 65), verts, edges_s) is not None
            or me.choose((60, 75), verts, edges_s) != (("Pad", "Edge5"), (60.0, 80.0))
            or me.closest_on_segment((5, 5), (0, 0), (0, 0))[0] != math.hypot(5, 5)
            or me.qt_point(500, 352, 491) != (500.0, 139.0)
            or me.external_index(_Sk(), "Extruir1", "Edge10") != 1 or me.external_index(_Sk(), "Extruir1", "Edge2")            or me.coin_point(500, 139, 491) != (500, 352) or me.coin_point(10, 0, 100, 1.5) != (15, 150)
            or not me.already(_Sk(), "Extruir1", "Edge10") or me.already(_Sk(), "Extruir1", "Edge2")
            or me._filter is None):
        print("  FEHLER: fork: aristas del modelo en el croquis (qué se toma bajo el mouse)")
        return False
    rr = sys.modules["swui.fork.repair_refs"]
    if rr.COMMAND not in commands or ft.REPAIR != rr.COMMAND:
        print("  FEHLER: fork: reparar referencias (comando)")
        return False
    fck = sys.modules["swui.fork.folder_check"]
    report = fck.summarize([("C:/p/a.FCStd", "ok", []), ("C:/p/sub/b.FCStd", "error", ["Croquis2: perdió su cara"])],
                           "C:/p")
    if (fck.COMMAND not in commands or "2 piezas, 1 con problemas" not in report
            or "b.FCStd: CON ERRORES" not in report or "    Croquis2: perdió su cara" not in report):
        print("  FEHLER: fork: chequear carpeta (comando / informe)", report)
        return False
    # Cotas con doble clic (instant_dims): formato y lectura de valores como SW en castellano
    idm = sys.modules["swui.fork.instant_dims"]
    if (idm.fmt(100.0) != "100" or idm.fmt(12.5) != "12,5" or idm.fmt(0.1234) != "0,123"
            or idm.fmt(90.0, "angle") != "90°" or idm.parse("12,5") != 12.5 or idm.parse(" 7 ") != 7.0
            or idm.parse("") is not None or idm.perpendicular_away((0, 0), (10, 0), (5, 5)) != (-0.0, -1.0)
            or idm.perpendicular_away((0, 0), (10, 0), (5, -5)) != (-0.0, 1.0)):
        print("  FEHLER: fork: cotas con doble clic (formato, lectura, ubicación)",
              idm.fmt(12.5), idm.perpendicular_away((0, 0), (10, 0), (5, 5)))
        return False
    # Croquis: un clic (elegido entero, desde el árbol) muestra sus cotas
    if (idm.sketch_to_show([_Pick(sk2, [])]) is not sk2 or idm.sketch_to_show([_Pick(sk2, ["Edge1"])])
            or idm.sketch_to_show([_Pick(pad, [])]) or idm.sketch_to_show([_Pick(sk2, []), _Pick(sk1, [])])
            or idm.sketch_to_show([])):
        print("  FEHLER: fork: cotas de un croquis con un clic")
        return False
    # Panel de redondeo (dress_up_panel): nombres como SW, clic agrega / saca, enganchado a la edición
    dup = sys.modules["swui.fork.dress_up_panel"]
    gui_ = sys.modules["FreeCADGui"]
    if (dup.sw_names(["Edge3", "Face1", "Edge7"]) != ["Arista<1>", "Cara<1>", "Arista<2>"]
            or dup.toggle(["Edge1"], "Edge2") != ["Edge1", "Edge2"] or dup.toggle(["Edge1", "Edge2"], "Edge1") != ["Edge2"]
            or not any(isinstance(o, dup._EditObserver) for o in gui_._doc_observers)
            or dup.chamfer_type(True, True) != "Distance and Angle" or dup.chamfer_type(False, True) != "Equal distance"
            or dup.chamfer_type(False, False) != "Two distances"):
        print("  FEHLER: fork: panel de redondeo/chaflán (nombres, selección, enganche, tipos)")
        return False
    # Paneles de matriz y simetría (pattern_panel): espaciado SW desde la longitud total, nombres
    pp = sys.modules["swui.fork.pattern_panel"]
    if (pp.spacing_from_extent(100.0, 5) != 25.0 or pp.spacing_from_extent(30.0, 1) != 30.0
            or pp.sub_name("Edge4") != "Arista" or pp.sub_name("H_Axis") != "eje H"
            or "PartDesign::LinearPattern" not in dup.PANELS or "PartDesign::Mirrored" not in dup.PANELS):
        print("  FEHLER: fork: paneles de matriz y simetría")
        return False
    # Asistente para taladro (hole_panel): nombres SW, tipo desde FreeCAD, tornillos, y el taladro
    # sin selección pasa por "elegir cara" (pick_plane)
    hp = sys.modules["swui.fork.hole_panel"]
    pk = sys.modules["swui.pick_plane"]
    if (hp.size_text("ISOMetricProfile", "M6x1.0") != "M6" or hp.size_text("ISOMetricFineProfile", "M8x1.0") != "M8x1.0"
            or hp.kind_of(True, "None") != hp.TAPPED or hp.kind_of(False, "ISO 10642") != hp.COUNTERSINK
            or hp.kind_of(False, "Counterbore") != hp.COUNTERBORE or hp.kind_of(False, "None") != hp.PLAIN
            or hp.screws_for(hp.COUNTERBORE, ["None", "Counterbore", "DIN 7984", "ISO 10642", "ISO 4762"])
            != ["ISO 4762", "DIN 7984", "Counterbore"]
            or hp.nearest_size(["M5x0.8", "M6x0.75", "M6x1.0"], "M6x1.0") != "M6x0.75"
            or hp.fit_index("Loose") != 2 or "PartDesign_Hole" not in pk.FEATURE_COMMANDS
            or "PartDesign::Hole" not in dup.PANELS):
        print("  FEHLER: fork: asistente para taladro")
        return False
    # Ángulo de salida (panel SW) y términos SW en barrido / hélice / referencia (native_terms)
    nt = sys.modules["swui.fork.native_terms"]
    if ("PartDesign::Draft" not in dup.PANELS
            or nt.translate_items(["Estándar", "Algo nuevo"], nt.DIALOGS["PartDesignGui::TaskPipeOrientation"]["combos"]["comboBoxMode"])
            != ["Seguir trayecto", "Algo nuevo"]
            or nt.root_names("PartGui::TaskAttacher") != ("PartGui::TaskAttacher", "PartGui__TaskAttacher")):
        print("  FEHLER: fork: ángulo de salida / términos SW en diálogos nativos")
        return False
    importlib.import_module("swui.fork.flyout_tree")  # árbol flotante: que al menos cargue
    # Plano de referencia SW: referencias + relaciones -> modo de adjunción de FreeCAD
    rp = sys.modules["swui.fork.ref_plane_panel"]
    if (rp.resolve([("plane", "distance")]) != ("FlatFace", [0], "offset")
            or rp.resolve([("vertex", "coincident"), ("plane", "parallel")]) != ("ParallelPlane", [1, 0], None)
            or rp.resolve([("plane", "angle"), ("edge", "coincident")]) != ("FlatFace", [0, 1], "angle")
            or rp.resolve([("plane", "midplane"), ("plane", "midplane")]) != ("FlatFace", [0, 1], "mid")
            or rp.resolve([("vertex", "coincident")] * 3) != ("ThreePointsPlane", [0, 1, 2], None)
            or rp.resolve([("edge", "coincident")]) is not None
            or rp.pick_mode("ParallelPlane", ["TangentPlane"]) != "TangentPlane"
            or rp.offer("plane", ["midplane"])[1] != "midplane" or "PartDesign::Plane" not in dup.PANELS
            or not any(isinstance(o, rp._RecomputeObserver) for o in sys.modules["FreeCAD"]._observers)):
        print("  FEHLER: fork: panel de plano de referencia")
        return False
    ra = sys.modules["swui.fork.ref_axis_point_panel"]
    if (ra.guess_axis(["plane", "plane"]) != "planes" or ra.resolve_axis("planes", ["plane", "plane"]) != ("IntersectionLine", [0, 1])
            or ra.resolve_axis("point_face", ["vertex", "plane"]) != ("FaceNormal", [1, 0])
            or ra.resolve_axis("line", ["edge"], True) != ("ObjectX", [0])
            or ra.guess_point(["arc"]) != "arc_center" or ra.resolve_point("along", ["edge"]) != ("OnEdge", [0])
            or ra.resolve_point("projection", ["vertex", "plane"]) != ("ProximityPoint1", [1, 0])
            or "PartDesign::Line" not in dup.PANELS or "PartDesign::Point" not in dup.PANELS):
        print("  FEHLER: fork: paneles de eje y punto de referencia")
        return False
    # Fase 3 (Evaluar): material, propiedades físicas, ecuaciones, medir, franja y cinta
    mat = sys.modules["swui.fork.material"]
    mp = sys.modules["swui.fork.mass_props"]
    eq = sys.modules["swui.fork.equations"]
    ms = sys.modules["swui.fork.measure_sw"]
    et = sys.modules["swui.fork.evaluate_tab"]
    tsp = sys.modules["swui.fork.tree_strip"]
    lay_ = sys.modules["swui.ribbon_layout"]
    copy_ = mat.read_copy(mat.copy_text({"uuid": "u1", "name": "Chapa", "values": {"Density": (7870.0, "kg/m^3")}}))
    if (mat.category_path("Standard/Metal/Steel") != ["Metales", "Acero"] or mat.parse_number("7.850,5") != 7850.5
            or mat.parse_number("0,3") != 0.3 or mat.parse_number("x") is not None or mat.fmt_number(0.3) != "0,3"
            or abs(mat.density_from(copy_) - 7.87e-6) > 1e-12 or mat.read_copy("roto") is not None
            or mat.missing_in([("o", copy_, "otro")], set()) != [("o", copy_)]
            or mat.missing_in([("o", copy_, "otro")], {"u1"}) or mat.missing_in([("o", copy_, "u1")], set())
            or 'UUID: "u1"' not in mat.fcmat_text(copy_) or "Density: \"7870.0 kg/m^3\"" not in mat.fcmat_text(copy_)
            or mat.safe_file_name('Acero "A/B"') != "Acero _A_B_"):
        print("  FEHLER: fork: material (categorías, números, copia en la pieza, archivo .FCMat)")
        return False
    res_ = mp.combine([(1000.0, 600.0, (5.0, 5.0, 5.0), [[16666.67, 0, 0], [0, 16666.67, 0], [0, 0, 16666.67]], 1e-6)])
    two_ = mp.combine([(1000.0, 600.0, (0.0, 0.0, 0.0), [[0.0] * 3] * 3, 1e-6),
                       (1000.0, 600.0, (10.0, 0.0, 0.0), [[0.0] * 3] * 3, 1e-6)])
    if (abs(res_["mass"] - 0.001) > 1e-12 or abs(res_["inertia_origin"][0][1] + 0.025) > 1e-9
            or abs(res_["inertia_origin"][0][0] - (0.01666667 + 0.05)) > 1e-6 or mp.combine([]) is not None
            or two_["center"] != [5.0, 0.0, 0.0] or abs(two_["inertia_cm"][1][1] - 0.05) > 1e-12
            or mp.sw_matrix([[1, -2, 0], [-2, 1, 0], [0, 0, 1]])[0][1] != 2 or mp.fmt(1234.5678, 2) != "1.234,57"
            or mp.fmt(-0.0001, 2) != "0,00" or "kilogramos por metro cúbico" not in mp.density_text([7.85e-6])
            or "Masa = 0,001 kilogramos" not in mp.report(res_, [1e-6], ["Body"], [])):
        print("  FEHLER: fork: propiedades físicas (masa, centro, inercia como SW, informe)")
        return False
    res_eq = eq.to_freecad('= "Largo" * 2,5 + sqr(16) + iif("Largo" > 5; 1; 2)',
                           lambda n: {"Largo": "VariablesGlobales.Largo"}.get(n))
    if (eq.sketch_dim_names([("Distance", ""), ("Coincident", ""), ("Radius", "D1"), ("Angle", "")])
            != {0: "D2", 2: "D1", 3: "D3"}
            or eq.feature_dim_names("PartDesign::Pad", ["Length", "Length2", "Type"]) != {"Length": "D1", "Length2": "D2"}
            or res_eq != ("VariablesGlobales.Largo * 2.5 + sqrt(16) + ((VariablesGlobales.Largo > 5) ? (1) : (2))", [])
            or eq.to_freecad('= "Nada"', lambda n: None)[1] != ["Nada"]
            or eq.to_sw("VariablesGlobales.Largo * 2.5", lambda t, p: "Largo" if t == "VariablesGlobales" else None)
            != '"Largo" * 2,5'
            or eq.to_sw("Largo / 4", lambda t, p: None, {"Largo": "Largo"}) != '"Largo" / 4'
            or eq.fmt(30.5, "mm") != "30,5 mm"):
        print("  FEHLER: fork: ecuaciones (nombres D1@Croquis1, funciones y coma como SW)")
        return False
    groups_ = lay_.EVALUIEREN[1]
    flat_ = [e[0] for g in groups_ for e in g if isinstance(e, tuple)]
    if (ms.toggle_pick([1, 2], 2) != [1] or ms.toggle_pick([1], 2) != [1, 2] or "Std_Measure" in flat_
            or ms.projections((0.0, 0.0, 0.0), (70.0, 30.0, 10.0))
            != [("x", (0.0, 0.0, 0.0), (70.0, 0.0, 0.0)), ("y", (70.0, 0.0, 0.0), (70.0, 30.0, 0.0)),
                ("z", (70.0, 30.0, 0.0), (70.0, 30.0, 10.0))]
            or [k for k, _a, _b in ms.projections((0.0, 0.0, 0.0), (0.0, 5.0, 0.0))] != ["y"]
            or flat_[:4] != ["SWUI_Measure", "SWUI_MassProperties", "SWUI_Equations", "SWUI_Material"]
            or tsp.rows_for(None) != [] or ms.COMMAND != rk.MEASURE):
        print("  FEHLER: fork: medir / pestaña Evaluar / franja del árbol", flat_)
        return False
    # Distancia máxima (max_distance): el método general tiene que dar lo mismo que las fórmulas
    import math as math_
    mx = importlib.import_module("swui.fork.max_distance")

    def circle_(c, r, n_dir):
        u_ = mx._any_perp(n_dir)
        w_ = (n_dir[1] * u_[2] - n_dir[2] * u_[1], n_dir[2] * u_[0] - n_dir[0] * u_[2], n_dir[0] * u_[1] - n_dir[1] * u_[0])
        return mx.Item(lambda p: tuple(c[k] + r * (math_.cos(p[0]) * u_[k] + math_.sin(p[0]) * w_[k]) for k in range(3)),
                       (0.0,), (2 * math_.pi,))

    z_ = (0.0, 0.0, 1.0)
    gen_cc = mx.max_between([circle_((20.0, 20.0, 0.0), 5.0, z_)], [circle_((70.0, 20.0, 0.0), 4.0, z_)])[0]
    exa_cc = mx.max_coplanar_circles((20.0, 20.0, 0.0), 5.0, (70.0, 20.0, 0.0), 4.0, z_)[0]
    gen_pc = mx.max_between([mx.Item.point((0.0, 0.0, 30.0))], [circle_((5.0, 0.0, 0.0), 10.0, z_)])[0]
    exa_pc = mx.max_point_circle((0.0, 0.0, 30.0), (5.0, 0.0, 0.0), z_, 10.0)[0]
    tilted_ = circle_((30.0, 5.0, 10.0), 6.0, (math_.sqrt(0.5), math_.sqrt(0.5), 0.0))
    flat_c = circle_((0.0, 0.0, 0.0), 8.0, z_)
    brute_ = max(mx.dist(flat_c.pos((2 * math_.pi * i / 720,)), tilted_.pos((2 * math_.pi * j / 720,)))
                 for i in range(720) for j in range(720))
    gen_tc = mx.max_between([flat_c], [tilted_])[0]
    box_a = [mx.Item.point((x, y, z)) for x in (0.0, 10.0) for y in (0.0, 10.0) for z in (0.0, 10.0)]
    box_b = [mx.Item.point((x, y, z)) for x in (30.0, 35.0) for y in (0.0, 5.0) for z in (0.0, 5.0)]
    if (abs(gen_cc - 59.0) > 1e-6 or abs(exa_cc - 59.0) > 1e-12
            or abs(gen_pc - exa_pc) > 1e-6 or abs(exa_pc - math_.sqrt(30 ** 2 + 15 ** 2)) > 1e-9
            or gen_tc < brute_ - 1e-9 or gen_tc - brute_ > 1e-3
            or abs(mx.max_between(box_a, box_b)[0] - math_.sqrt(35 ** 2 + 10 ** 2 + 10 ** 2)) > 1e-12):
        print("  FEHLER: fork: distancia máxima (general contra fórmulas)", gen_cc, gen_pc, exa_pc, gen_tc, brute_)
        return False
    print("  Evaluar  : fork: material (copia en la pieza), propiedades físicas, ecuaciones SW, medir SW, franja")
    print("  Medir    : fork: distancia máxima general (barrido + afinado) = fórmulas exactas")
    print("  Árbol    : fork: retroceder, suprimir con dependientes, padre/hijo, Ctrl+B/Q, barra espaciadora = Medir")
    print("  Árbol    : fork: mover arriba/abajo, barra de retroceso arrastrable, guardar también STEP")
    print("  Croquis  : fork: aristas y vértices del modelo se traen solos al tocarlos con una herramienta")
    print("  Redondeo : fork: paneles SW de redondeo y chaflán (Arista<1>, clic agrega/saca, tipos de chaflán)")
    print("  Matrices : fork: paneles SW de matriz lineal/circular y simetría (espaciado, sólidos)")
    print("  Taladro  : fork: asistente SW (cara -> croquis de posiciones -> tipo, tamaño, tornillo)")
    print("  Diálogos : fork: ángulo de salida SW; términos SW en barrido, hélice y referencia")
    print("  Plano    : fork: panel SW (primera/segunda/tercera referencia y relaciones); eje y punto SW")
    return True


def run(split_namespace):
    """
    Laedt InitGui.py einmal.

    split_namespace=True  -> getrennte Globals/Locals (wie FreeCAD)
    split_namespace=False -> ein gemeinsames Dictionary
    """
    mode = "getrennte Namensraeume (wie FreeCAD)" if split_namespace else "ein Namensraum"
    print("\n" + "=" * 62)
    print("DURCHLAUF:", mode)
    print("=" * 62)

    log.clear()
    _clear_addon_modules()
    registered, commands = _make_stubs()

    if ADDON in sys.path:
        sys.path.remove(ADDON)
    sys.path.insert(0, ADDON)

    with open(os.path.join(ADDON, "InitGui.py"), encoding="utf-8") as fh:
        source = fh.read()

    code = compile(source, "InitGui.py", "exec")

    # Entscheidend: __file__ wird NICHT gesetzt.
    g = {"__name__": "__main__", "__builtins__": __builtins__}

    try:
        if split_namespace:
            exec(code, g, {})
        else:
            exec(code, g)
    except Exception:
        import traceback

        print("FEHLGESCHLAGEN beim Ausfuehren von InitGui.py:")
        traceback.print_exc()
        return False

    for level, text in log:
        print("  [%s] %s" % (level, text))
    log.clear()

    if not registered:
        print("  FEHLER: keine Workbench registriert")
        return False

    wb = list(registered.values())[0]
    icon_ok = bool(wb.Icon) and os.path.isfile(wb.Icon)
    print("  Workbench:", list(registered)[0])
    print("  MenuText :", wb.MenuText)
    print("  Icon     :", wb.Icon or "(leer)")
    print("  Icon da? :", icon_ok)

    type(wb).appendToolbar = lambda self, n, c: print("  Toolbar  :", n, c)
    type(wb).appendMenu = lambda self, n, c: print("  Menue    :", n, c)

    try:
        wb.Initialize()
    except Exception:
        import traceback

        print("FEHLGESCHLAGEN in Initialize():")
        traceback.print_exc()
        return False

    for level, text in log:
        for line in text.splitlines():
            print("  [%s] %s" % (level, line))
        if level == "ERR":
            return False

    print("  Befehle  :", list(commands) or "KEINE")

    # --- Skizze bleibt in LikeSolidWorks UI -------------------------------
    show = sys.modules["Show"]
    gui = sys.modules["FreeCADGui"]
    tv = show.TempoVis()
    tv.activateWorkbench("SketcherWorkbench")
    if show._switched:
        print("  FEHLER: In LikeSolidWorks UI wurde trotzdem zum Sketcher gewechselt")
        return False
    gui._active_wb = "PartDesignWorkbench"
    tv.activateWorkbench("SketcherWorkbench")
    gui._active_wb = "LikeSolidWorksUIWorkbench"
    if show._switched != ["SketcherWorkbench"]:
        print("  FEHLER: Part Design wechselt nicht mehr in den Sketcher", show._switched)
        return False
    sys.modules["swui.sketch_edit"].install()  # zweites Einhaken
    orig = show.mTempoVis.TempoVis.activateWorkbench._swui_original
    if getattr(orig, "_swui_original", None) is not None:
        print("  FEHLER: doppelt eingehakt")
        return False
    print("  Skizze   : bleibt in LikeSolidWorks UI; Part Design wechselt weiter zum Sketcher")

    # Feature-Dialoge: FreeCADs eigenes "Gui.activateWorkbench('PartDesignWorkbench')" (doCommand,
    # Dateiname "<string>") wird in LikeSolidWorks UI uebersprungen, Auswahl/Makros nicht
    se = sys.modules["swui.sketch_edit"]
    old_act = getattr(gui, "activateWorkbench", None)
    switched_wb = []
    gui.activateWorkbench = lambda name_, *a_: switched_wb.append(name_) or True
    try:
        se._hook_feature_dialogs()
        se._hook_feature_dialogs()  # zweites Einhaken: nichts doppelt
        exec(compile("Gui.activateWorkbench('PartDesignWorkbench')", "<string>", "exec"), {"Gui": gui})
        from_cpp = list(switched_wb)
        gui.activateWorkbench("PartDesignWorkbench")  # Makro / Add-on
        gui._active_wb = "PartDesignWorkbench"
        exec(compile("Gui.activateWorkbench('PartDesignWorkbench')", "<string>", "exec"), {"Gui": gui})
        gui._active_wb = "LikeSolidWorksUIWorkbench"
        se.uninstall()
        restored = not hasattr(gui.activateWorkbench, "_swui_original")
    finally:
        gui._active_wb = "LikeSolidWorksUIWorkbench"
        if old_act is None:
            del gui.activateWorkbench
        else:
            gui.activateWorkbench = old_act
        se.install()
    if from_cpp or switched_wb != ["PartDesignWorkbench", "PartDesignWorkbench"] or not restored:
        print("  FEHLER: Feature-Dialog wechselt zu Part Design / Makro blockiert", from_cpp, switched_wb, restored)
        return False
    print("  Dialog   : Feature-Dialoge bleiben in LikeSolidWorks UI; Workbench-Auswahl und Makros wechseln weiter")

    # --- Skizze / Feature ohne Auswahl: Ebene oder ebene Flaeche waehlen ---
    __import__("swui.pick_plane")
    pp = sys.modules["swui.pick_plane"]
    cs = sys.modules["swui.context_sketch"] if "swui.context_sketch" in sys.modules else __import__(
        "swui.context_sketch", fromlist=["x"])
    plane = types.SimpleNamespace(TypeId="App::Plane", Label="Ebene oben")
    flat = types.SimpleNamespace(isPlanar=lambda: True)
    round_ = types.SimpleNamespace(isPlanar=lambda: False)
    solid = types.SimpleNamespace(TypeId="PartDesign::Pad",
                                  getSubObject=lambda s_: {"Face1": flat, "Face2": round_}.get(s_.split(".")[-1]))
    sketch_o = types.SimpleNamespace(TypeId="Sketcher::SketchObject")
    if (pp.picked_target([(plane, [])]) != (plane, "") or pp.picked_target([(solid, ["Face1"])]) != (solid, "Face1")
            or pp.picked_target([(solid, ["Face2"])]) is not None or pp.picked_target([(solid, ["Edge1"])]) is not None
            or pp.picked_target([(sketch_o, [])]) is not None or pp.picked_target([]) is not None):
        print("  FEHLER: Ebene/ebene Fläche nicht richtig erkannt")
        return False
    calls_pp = []
    saved_pp = (pp._selection, pp._dialog_open, pp.start_sketch, pp.open_panel)
    fc_pp = sys.modules["FreeCAD"]
    old_doc_pp = getattr(fc_pp, "ActiveDocument", None)
    fc_pp.ActiveDocument = types.SimpleNamespace(Objects=[])
    try:
        pp._dialog_open = lambda: False
        pp.start_sketch = lambda c_: calls_pp.append(("skizze", c_))
        pp.open_panel = lambda c_: calls_pp.append(("panel", c_))
        results_pp = []
        for sel_, cmd_ in (([], "PartDesign_NewSketch"), ([], "PartDesign_Pad"), ([(solid, ["Face1"])], "PartDesign_Pocket"),
                           ([(solid, ["Face1"])], "PartDesign_NewSketch"), ([(sketch_o, [])], "PartDesign_Pad"),
                           ([], "PartDesign_Fillet")):
            pp._selection = lambda s_=sel_: s_
            results_pp.append(pp.handle(cmd_))
    finally:
        pp._selection, pp._dialog_open, pp.start_sketch, pp.open_panel = saved_pp
        fc_pp.ActiveDocument = old_doc_pp
    if results_pp != [True, True, True, False, False, False] or calls_pp != [
            ("panel", "PartDesign_NewSketch"), ("panel", "PartDesign_Pad"), ("skizze", "PartDesign_Pocket")]:
        print("  FEHLER: Ohne Auswahl -> Panel, mit Fläche -> Skizze, sonst FreeCAD", results_pp, calls_pp)
        return False
    # Vorgemerktes Feature startet erst nach "Skizze beenden", nur mit Geometrie
    ran_pp, editing_pp = [], [None]
    sk_doc = types.SimpleNamespace(Objects=[])
    sk_pp = types.SimpleNamespace(Name="Sketch", Document=sk_doc, Geometry=[1], InList=[])
    sk_doc.Objects.append(sk_pp)
    saved_t = (pp._editing, pp._dialog_open, pp.QtCore)
    gui_pp = sys.modules["FreeCADGui"]
    old_run_pp, old_sel_pp = gui_pp.runCommand, getattr(gui_pp, "Selection", None)
    try:
        pp._editing = lambda: editing_pp[0]
        pp._dialog_open = lambda: False
        gui_pp.runCommand = lambda c_, *a_: ran_pp.append(c_)
        gui_pp.Selection = types.SimpleNamespace(clearSelection=lambda: None, addSelection=lambda *a_: None)
        pp.arm("PartDesign_Pad", sk_pp)
        pp.tick()  # Skizze noch nicht geoeffnet
        editing_pp[0] = sk_pp
        pp.tick()
        pp.tick()  # in Bearbeitung
        during = list(ran_pp)
        editing_pp[0] = None
        pp.tick()  # beendet -> Feature
        after = list(ran_pp)
        pp.arm("PartDesign_Pad", sk_pp)
        editing_pp[0] = sk_pp
        pp.tick()
        sk_pp.Geometry = []
        editing_pp[0] = None
        pp.tick()  # leer beendet -> nichts
    finally:
        pp._editing, pp._dialog_open, pp.QtCore = saved_t
        gui_pp.runCommand = old_run_pp
        if old_sel_pp is not None:
            gui_pp.Selection = old_sel_pp
        pp._disarm()
    if during or after != ["PartDesign_Pad"] or ran_pp != ["PartDesign_Pad"] or pp.armed():
        print("  FEHLER: Feature nach Skizze beenden", during, after, ran_pp)
        return False
    # FreeCAD-Ebenennamen (Koerper von der Startseite) werden erkannt, SW- und eigene Namen nicht
    defaults_pp = [("XY_Plane", "XY_Plane"), ("Plano XY", "XY_Plane"), ("XZ-Ebene", "XZ_Plane"), ("Plan YZ001", "YZ_Plane")]
    others_pp = [("Planta", "XY_Plane"), ("Ebene oben", "XY_Plane"), ("Plano XY", "XZ_Plane"), ("Mi plano XY", "XY_Plane")]
    if (not all(pp.is_default_plane_label(l_, r_) for l_, r_ in defaults_pp)
            or any(pp.is_default_plane_label(l_, r_) for l_, r_ in others_pp)):
        print("  FEHLER: FreeCAD-Ebenennamen nicht richtig erkannt")
        return False
    print("  Ohne Ausw:Skizze/Austragen ohne Auswahl -> Ebene oder ebene Fläche wählen, Feature nach Skizze beenden")

    # --- SOLIDWORKS-Namen fuer neue Features ----------------------------
    fc = sys.modules["FreeCAD"]
    naming = sys.modules["swui.naming"]
    naming.install()  # zweites Mal: darf nicht doppelt anmelden
    nobs = [o for o in fc._observers if isinstance(o, naming._Observer)]
    if len(nobs) != 1:
        print("  FEHLER: Beobachter %d-mal angemeldet" % len(nobs))
        return False
    obs = nobs[0]

    class Doc:
        Restoring = False
        Transacting = False

        def __init__(self):
            self.Objects = []

    class Obj:
        def __init__(self, doc, type_id, label, role=None):
            self.Document, self.TypeId, self.Label = doc, type_id, label
            if role is not None:
                self.Role = role
            doc.Objects.append(self)

    doc = Doc()
    for lbl in ("Skizze1", "Skizze4", "Linear austragen1"):  # schon vorhanden
        Obj(doc, "Sketcher::SketchObject" if lbl.startswith("Skizze") else "PartDesign::Pad", lbl)

    def create(type_id, label, **kw):
        o = Obj(doc, type_id, label, **kw)
        obs.slotCreatedObject(o)
        return o

    sk = create("Sketcher::SketchObject", "Sketch")
    pad = create("PartDesign::Pad", "Pad")
    body = create("PartDesign::Body", "Körper")
    plane = create("App::Plane", "XZ-Ebene")
    plane.Role = "XZ_Plane"  # FreeCAD setzt die Rolle erst NACH der Meldung
    naming._flush()
    got = (sk.Label, pad.Label, body.Label, plane.Label)
    if got != ("Skizze5", "Linear austragen2", "Körper", "Ebene vorne"):
        print("  FEHLER: Namen", got)
        return False

    doc.Restoring = True
    loaded = create("Sketcher::SketchObject", "Sketch001")
    doc.Restoring = False
    doc.Transacting = True
    redone = create("PartDesign::Pad", "Pad001")
    doc.Transacting = False
    gui._active_wb = "PartDesignWorkbench"
    other = create("PartDesign::Fillet", "Fillet")
    gui._active_wb = "LikeSolidWorksUIWorkbench"
    naming._flush()
    if (loaded.Label, redone.Label, other.Label) != ("Sketch001", "Pad001", "Fillet"):
        print("  FEHLER: umbenannt beim Laden/Rückgängig/anderer Workbench",
              (loaded.Label, redone.Label, other.Label))
        return False

    class Gone:  # Objekt, das vor dem Umbenennen geloescht wurde
        TypeId = "Sketcher::SketchObject"

        @property
        def Document(self):
            raise RuntimeError("Objekt geloescht")

    naming._pending.append(Gone())
    try:
        naming._flush()
    except Exception as exc:
        print("  FEHLER: gelöschtes Objekt bricht das Umbenennen:", exc)
        return False
    print("  Namen    : Skizze5, Linear austragen2, Ebene vorne; Laden/Rückgängig/Part Design unberührt")

    # Baugruppen-Baum wie in SW (8d)
    doc = Doc()

    def acreate(type_id, label, name, inlist=(), **attrs):
        o = Obj(doc, type_id, label)
        o.Name, o.InList = name, list(inlist)
        for k, v in attrs.items():
            setattr(o, k, v)
        obs.slotCreatedObject(o)
        return o

    asm = acreate("Assembly::AssemblyObject", "Assembly", "Assembly")
    jg = acreate("Assembly::JointGroup", "Joints", "Joints", [asm])
    welle_doc = types.SimpleNamespace(Label="Welle", Name="Welle")
    welle = types.SimpleNamespace(Document=welle_doc, Label="Body", Name="Body")
    platte = types.SimpleNamespace(Document=doc, Label="Platte", Name="Part")
    l1 = acreate("App::Link", "Body", "Link", [asm], LinkedObject=welle)
    l2 = acreate("App::Link", "Body", "Link001", [asm], LinkedObject=welle)
    l3 = acreate("App::Link", "Platte", "Link002", [asm], LinkedObject=platte)
    loose = acreate("App::Link", "Body", "Link003", [], LinkedObject=welle)
    naming._flush()
    got = (asm.Label, jg.Label, l1.Label, l2.Label, l3.Label, loose.Label)
    if got != ("Baugruppe1", "Verknüpfungen", "Welle<1>", "Welle<2>", "Platte<1>", "Body"):
        print("  FEHLER: Baugruppen-Namen", got)
        return False
    ground = acreate("App::FeaturePython", "GroundedJoint", "GroundedJoint", [jg], ObjectToGround=l1)
    naming._flush()
    if l1.Label != "(f) Welle<1>" or l2.Label != "Welle<2>":
        print("  FEHLER: fixiertes Teil nicht mit (f) markiert", l1.Label, l2.Label)
        return False
    doc.Objects.remove(ground)
    obs.slotDeletedObject(ground)
    naming._flush()
    if l1.Label != "Welle<1>":
        print("  FEHLER: (f) nach dem Lösen nicht entfernt", l1.Label)
        return False
    doc.Transacting = True  # Rueckgaengig stellt die Fixierung wieder her
    ground = acreate("App::FeaturePython", "GroundedJoint", "GroundedJoint", [jg], ObjectToGround=l1)
    doc.Transacting = False
    naming._flush()
    l4 = acreate("App::Link", "Body", "Link004", [asm], LinkedObject=welle)
    naming._flush()
    if l1.Label != "(f) Welle<1>" or ground.Label != "GroundedJoint" or l4.Label != "Welle<3>":
        print("  FEHLER: (f) bei Rückgängig / Nummer nach (f)", l1.Label, ground.Label, l4.Label)
        return False
    print("  Baum     : Baugruppe1, (f) Welle<1>, Welle<2>, Verknüpfungen; (f) folgt Fixieren/Lösen/Rückgängig")

    # Verknuepfungen (Gelenke) mit SW-Namen (8f)
    def joint(label, jtype, name, dist=0.0):
        o = acreate("App::FeaturePython", label, name, [jg])
        o.JointType, o.Distance = jtype, types.SimpleNamespace(Value=dist)
        obs.slotChangedObject(o, "JointType")
        return o

    sys.modules["JointObject"] = types.SimpleNamespace(TranslatedJointTypes=[
        "Fest", "Drehgelenk", "Zylindrisch", "Schieber", "Kugel", "Abstand", "Parallel",
        "Senkrecht", "Winkel", "Zahnstange", "Schraube", "Zahnräder", "Riemen"])
    j1 = joint("Abstand", "Distance", "Joint")
    j2 = joint("Zylindrisch", "Cylindrical", "Joint001")
    j3 = joint("Abstand001", "Distance", "Joint002", dist=5.0)
    j4 = joint("Lager vorne", "Cylindrical", "Joint003")  # vom Benutzer benannt
    naming._flush()
    got = (j1.Label, j2.Label, j3.Label, j4.Label)
    if got != ("Deckungsgleich1", "Konzentrisch1", "Abstand1", "Lager vorne"):
        print("  FEHLER: Verknüpfungs-Namen", got)
        return False
    j1.JointType = "Parallel"  # im Dialog umgestellt
    obs.slotChangedObject(j1, "JointType")
    j3.Distance = types.SimpleNamespace(Value=0.0)
    obs.slotChangedObject(j3, "Distance")
    obs.slotChangedObject(j2, "Label")  # andere Eigenschaft: nichts tun
    naming._flush()
    if (j1.Label, j3.Label, j2.Label) != ("Parallel1", "Deckungsgleich1", "Konzentrisch1"):
        print("  FEHLER: Name folgt der Verknüpfungsart nicht", j1.Label, j3.Label)
        return False
    del sys.modules["JointObject"]
    print("  Verkn.Nm : Deckungsgleich1, Konzentrisch1, Abstand1; folgt Art/Abstand; eigene Namen bleiben")
    if not (bool(commands) and icon_ok):
        return False

    # --- Ribbon: Activated / Klick / Aktiv-Status / Deactivated -------
    log.clear()
    wb.Activated()
    for level, text in log:
        for line in text.splitlines():
            print("  [%s] %s" % (level, line))
        if level == "ERR":
            return False

    ribbon = sys.modules.get("swui.ribbon")
    if ribbon is None:
        print("  FEHLER: Activated() hat swui.ribbon nicht geladen")
        return False

    expected, expected_skipped = _expected_buttons()
    built = ribbon.button_names()
    skipped = ribbon.skipped_commands()
    print("  Ribbon   : %d Knöpfe, %d ausgelassen %s" % (len(built), len(skipped), sorted(skipped)))

    if sorted(built) != sorted(expected):
        print("  FEHLER: Knöpfe stimmen nicht mit ribbon_layout.py überein")
        return False
    if sorted(skipped) != sorted(expected_skipped):
        print("  FEHLER: Fehlende Befehle wurden nicht korrekt ausgelassen")
        return False

    # Klick simulieren: _run muss den FreeCAD-Befehl ausloesen.
    ran = sys.modules["FreeCADGui"]._ran
    # Qt haengt beim Klick 'checked' an - genau so aufrufen.
    ribbon._run("PartDesign_Pad", None, False)
    if ran[-1:] != [("PartDesign_Pad",)]:
        print("  FEHLER: Klick hat keinen FreeCAD-Befehl ausgelöst", ran[-1:])
        return False
    ribbon._run("Std_DrawStyle", 5, False)
    if ran[-1:] != [("Std_DrawStyle", 5)]:
        print("  FEHLER: Gruppenbefehl ohne Index ausgeführt", ran[-1:])
        return False
    print("  Klick    : runCommand OK, Gruppenbefehl mit Index OK")

    ribbon._refresh_enabled()
    print("  Aktiv    : Status-Abfrage OK")

    # --- Ausklappknoepfe ----------------------------------------------
    flys = {f["id"]: f for f in ribbon.flyouts()}
    rect = flys.get("Sketcher_CreateRectangle")
    slot = flys.get("Sketcher_CreateSlot")
    if rect is None or slot is None:
        print("  FEHLER: Ausklappknöpfe fehlen", sorted(flys))
        return False
    if [v["key"] for v in slot["variants"]] != ["Sketcher_CreateSlot"]:
        print("  FEHLER: fehlende Variante nicht ausgelassen", slot["variants"])
        return False
    ribbon._run_flyout(rect, False)
    if ran[-1:] != [("Sketcher_CreateRectangle",)]:
        print("  FEHLER: Hauptklick führt nicht die Standard-Variante aus", ran[-1:])
        return False
    ribbon._choose_variant(rect, 1, False)
    if ran[-1:] != [("Sketcher_CreateRectangle_Center",)] or rect["current"] != 1:
        print("  FEHLER: Menüauswahl nicht ausgeführt/übernommen", ran[-1:])
        return False
    ribbon._run_flyout(rect, False)
    if ran[-1:] != [("Sketcher_CreateRectangle_Center",)]:
        print("  FEHLER: Knopf hat sich die Variante nicht gemerkt")
        return False
    if ribbon._remembered_variant(rect) != 1:
        print("  FEHLER: Variante nicht für den nächsten Start gespeichert")
        return False
    if ribbon._menu_text("3-Punkt-\nKreis") != "3-Punkt-Kreis":
        print("  FEHLER: Menütext", ribbon._menu_text("3-Punkt-\nKreis"))
        return False
    print("  Ausklapp : %d Knöpfe; Auswahl wird ausgeführt, gemerkt und gespeichert" % len(flys))

    # --- Eigene Skizzen-Symbole ----------------------------------------
    import xml.etree.ElementTree as ET
    import tempfile

    paths_mod = sys.modules["swui.paths"]
    layout_mod = sys.modules["swui.ribbon_layout"]
    svgs = []

    def _walk(entries):
        for e in entries:
            if isinstance(e, dict):
                _walk(e.get("flyout") or e.get("stack") or e.get("toggle") or [])
            elif len(e) > 2 and e[2].get("svg"):
                svgs.append((e[0], e[2]))

    for _title, groups in layout_mod.TABS:
        for g in groups:
            _walk(g)
    if len(svgs) < 92:
        print("  FEHLER: zu wenige eigene Symbole im Ribbon", len(svgs))
        return False
    for cmd, opts in svgs:
        path = paths_mod.icon(opts["svg"])
        if not path:
            print("  FEHLER: Symbol fehlt:", opts["svg"])
            return False
        try:
            ET.parse(path)
        except Exception as exc:
            print("  FEHLER: Symbol kein gültiges SVG:", path, exc)
            return False
    qicon = sys.modules["PySide.QtGui"].QIcon
    qicon.reset_mock()
    qicon.return_value.isNull.return_value = False
    cmd0, opts0 = svgs[0]
    got_icon = ribbon._command_icon(cmd0, {"pixmap": cmd0}, opts0)
    qicon.return_value.isNull.return_value = mock.DEFAULT
    first = qicon.call_args_list[0][0] if qicon.call_args_list else ()
    if first != (paths_mod.icon(opts0["svg"]),) or got_icon is not qicon.return_value:
        print("  FEHLER: eigenes Symbol hat im Ribbon keinen Vorrang", qicon.call_args_list[:2])
        return False
    gen_path = os.path.join(ADDON, "tools", "make_icons.py")
    if os.path.exists(gen_path):  # nur im Repo, nicht in der Installation
        import importlib.util

        spec = importlib.util.spec_from_file_location("_make_icons", gen_path)
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        with tempfile.TemporaryDirectory() as tmp:
            for f in gen.build(tmp):
                mine = os.path.join(paths_mod.ICONS_DIR, "sketch", os.path.basename(f))
                # Vergleich nur des Bildinhalts: Beim Uebertragen koennen
                # Metadaten (C2PA) dazukommen - die sind harmlos.
                body = open(f, encoding="utf-8").read().split("<title>", 1)[1].split("</svg>")[0]
                if not os.path.exists(mine) or body not in open(mine, encoding="utf-8").read():
                    print("  FEHLER: Symbol veraltet - make_icons.py neu laufen lassen:", os.path.basename(f))
                    return False
    print("  Symbole  : %d eigene Skizzen-Symbole vorhanden, gültig, im Ribbon mit Vorrang" % len(svgs))

    # --- Aufteilung wie im SW-CommandManager ----------------------------
    if "Sketcher_Offset" not in built:
        print("  FEHLER: Offset-Elemente fehlt im Ribbon")
        return False
    qtw = sys.modules["PySide.QtWidgets"]
    small_calls = [c for c in qtw.QGridLayout.return_value.addWidget.call_args_list]
    cells = {(c[0][1], c[0][2]) for c in small_calls}
    if max((r for r, _c in cells), default=-1) != 2 or (0, 3) not in cells:
        print("  FEHLER: Zeichenwerkzeuge nicht als 3-Zeilen-Stapel angeordnet", sorted(cells))
        return False
    togs = ribbon.toggles()
    if len(togs) != 1 or [v["command"] for v in togs[0]["variants"]] != ["PartDesign_NewSketch", "Sketcher_LeaveSketch"]:
        print("  FEHLER: Umschaltknopf Skizze/Skizze beenden fehlt", togs)
        return False
    tog = togs[0]
    gui_ = sys.modules["FreeCADGui"]
    gui_.ActiveDocument = types.SimpleNamespace(
        getInEdit=lambda: types.SimpleNamespace(Object=types.SimpleNamespace(TypeId="Sketcher::SketchObject")))
    ribbon._refresh_enabled()
    in_sketch = tog["current"]
    ribbon._run_toggle(tog)
    ran_leave = ran[-1:]
    gui_.ActiveDocument = None
    ribbon._refresh_enabled()
    ribbon._run_toggle(tog)
    if in_sketch != 1 or ran_leave != [("Sketcher_LeaveSketch",)] or ran[-1:] != [("PartDesign_NewSketch",)]:
        print("  FEHLER: Umschaltknopf wechselt nicht mit der Skizze", in_sketch, ran_leave, ran[-1:])
        return False
    print("  Aufteil. : Zeichenwerkzeuge im 3-Zeilen-Stapel, Skizze/Skizze beenden umschaltend, Offset da")

    # --- Kleine Bildschirme: Reiter verschiebbar, erst nur Symbole, dann Pfeile ---
    if len(ribbon._scrollers) != len(layout_mod.TABS):
        print("  FEHLER: nicht jeder Reiter im verschiebbaren Rahmen", len(ribbon._scrollers))
        return False
    under = sys.modules["PySide.QtCore"].Qt.ToolButtonStyle.ToolButtonTextUnderIcon
    icon_only = sys.modules["PySide.QtCore"].Qt.ToolButtonStyle.ToolButtonIconOnly

    class FitBtn:
        def __init__(self):
            self.style, self.tip = under, "Tooltip"
        def toolButtonStyle(self):
            return self.style
        def setToolButtonStyle(self, s_):
            self.style = s_
        def text(self):
            return "Linear\naustragen"
        def toolTip(self):
            return self.tip
        def setToolTip(self, t_):
            self.tip = t_

    fit_btn = FitBtn()
    widths = {under: 1600, icon_only: 900}
    fit_lay = types.SimpleNamespace(invalidate=lambda: None, activate=lambda: None,
                                    minimumSize=lambda: types.SimpleNamespace(width=lambda: widths[fit_btn.style]))
    fit_page = types.SimpleNamespace(layout=lambda: fit_lay, findChildren=lambda cls_: [fit_btn],
                                     minimumSizeHint=lambda: types.SimpleNamespace(height=lambda: 70))
    shown = {}

    def arrow_(side):
        return types.SimpleNamespace(setVisible=lambda v_: shown.__setitem__(side, v_))

    avail = [1700]
    sc_t = {"box": types.SimpleNamespace(width=lambda: avail[0]), "area": types.SimpleNamespace(setFixedHeight=lambda h_: None),
            "page": fit_page, "large": None, "compact": False, "full_w": None, "compact_w": None, "avail": None,
            "left": arrow_("l"), "right": arrow_("r")}
    steps = []
    for a_ in (1700, 1366, 800, 1700):
        avail[0] = a_
        ribbon._fit(sc_t)
        steps.append((sc_t["compact"], shown.get("l"), shown.get("r")))
    if steps != [(False, False, False), (True, False, False), (True, True, True), (False, False, False)]:
        print("  FEHLER: Anpassung an die Breite (Text / nur Symbol / Pfeile)", steps)
        return False
    if fit_btn.style != under or fit_btn.tip != "Tooltip":
        print("  FEHLER: Knopf nach dem Vergroessern nicht wieder mit Text", fit_btn.style, fit_btn.tip)
        return False
    avail[0] = 1000
    ribbon._fit(sc_t)
    if fit_btn.tip != "Linear austragen\nTooltip":
        print("  FEHLER: Name fehlt im Tooltip des kompakten Knopfes", repr(fit_btn.tip))
        return False
    print("  Schmal   : jeder Reiter verschiebbar; zu schmal -> nur Symbole (Name im Tooltip), noch schmaler -> Pfeile")

    # --- Direkt aus Skizze austragen -----------------------------------
    fs = sys.modules.get("swui.from_sketch")
    import importlib
    fs = fs or importlib.import_module("swui.from_sketch")
    pending = []
    fs._later = lambda fn: pending.append(fn)  # Timer in der Attrappe von Hand ausloesen
    selected = []
    gui_.Selection.clearSelection = lambda *a: selected.clear()
    gui_.Selection.addSelection = lambda obj, *a: selected.append(obj)
    skobj = types.SimpleNamespace(TypeId="Sketcher::SketchObject", Name="Sketch")
    gui_.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: types.SimpleNamespace(Object=skobj))
    n0 = len(ran)
    ribbon._run("PartDesign_Pad", None, False)
    if ran[n0:] != [("Sketcher_LeaveSketch",)] or len(pending) != 1:
        print("  FEHLER: offene Skizze wird nicht zuerst beendet", ran[n0:])
        return False
    gui_.ActiveDocument = None  # FreeCAD hat die Skizze inzwischen geschlossen
    pending.pop()()
    if ran[n0:] != [("Sketcher_LeaveSketch",), ("PartDesign_Pad",)] or selected != [skobj]:
        print("  FEHLER: Feature nicht mit der Skizze gestartet", ran[n0:], selected)
        return False
    n0 = len(ran)
    ribbon._run("PartDesign_Pocket", None, False)  # ohne offene Skizze: ganz normal
    gui_.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: types.SimpleNamespace(Object=skobj))
    ribbon._run("PartDesign_Fillet", None, False)  # kein Profil-Feature: unveraendert
    gui_.ActiveDocument = None
    if ran[n0:] != [("PartDesign_Pocket",), ("PartDesign_Fillet",)] or pending:
        print("  FEHLER: normale Befehle werden umgeleitet", ran[n0:])
        return False
    print("  Aus Skizze: Linear austragen beendet Skizze, wählt sie und startet das Feature")

    # --- Reiter Baugruppe -------------------------------------------------
    titles = list(ribbon._tab_titles)
    # Evaluieren ganz links (Knopf "Language" sofort sichtbar), Start trotzdem auf Features
    if titles[:2] != ["Evaluieren", "Features"]:
        print("  FEHLER: Evaluieren steht nicht ganz links vor Features", titles)
        return False
    start_calls = [c_[0][0] for c_ in ribbon._tabs.setCurrentIndex.call_args_list]
    if not start_calls or start_calls[0] != titles.index("Features"):
        print("  FEHLER: beim Start ist nicht Features aufgeschlagen", start_calls[:3])
        return False
    if titles[-3:] != ["Ansicht", "Baugruppe", "Zeichnungen"]:
        print("  FEHLER: Reiter Baugruppe/Zeichnungen nicht rechts neben Ansicht", titles)
        return False
    lay_mod = sys.modules["swui.ribbon_layout"]

    def tab_cmds(tab):
        out = []

        def walk(e):
            if isinstance(e, tuple):
                out.append(e[0])
            elif isinstance(e, dict):
                for k in ("flyout", "stack", "toggle"):
                    for x in e.get(k, []):
                        walk(x)
        for g in tab[1]:
            for e in g:
                walk(e)
        return out

    if "SWUI_NewDrawing" in tab_cmds(lay_mod.FEATURES) or "SWUI_NewDrawing" not in tab_cmds(lay_mod.ZEICHNUNGEN):
        print("  FEHLER: Zeichnung erstellen nicht vom Reiter Features in Zeichnungen verschoben")
        return False
    zcmds = tab_cmds(lay_mod.ZEICHNUNGEN)
    for need in ("TechDraw_View", "TechDraw_SectionView", "TechDraw_DetailView", "TechDraw_Dimension",
                 "TechDraw_Balloon", "SWUI_ExportPDF", "SWUI_ExportDXF"):
        if need not in zcmds:
            print("  FEHLER: Zeichnungs-Werkzeug fehlt im Reiter:", need)
            return False
    if "TechDrawGui" not in lay_mod.REQUIRED_GUI_MODULES:
        print("  FEHLER: TechDraw-Befehle werden nicht geladen")
        return False
    # Blatt wird aktiv -> Reiter Zeichnungen (nur beim Übergang)
    real_da = ribbon._drawing_active
    try:
        ribbon._tabs.setCurrentIndex.reset_mock()
        ribbon._on_drawing = False
        ribbon._drawing_active = lambda: True
        ribbon._check_drawing()
        first = ribbon._tabs.setCurrentIndex.call_args
        ribbon._tabs.setCurrentIndex.reset_mock()
        ribbon._check_drawing()  # weiterhin Blatt: Benutzer darf Reiter wechseln
        again = ribbon._tabs.setCurrentIndex.called
        ribbon._drawing_active = lambda: False
        ribbon._check_drawing()
    finally:
        ribbon._drawing_active = real_da
        ribbon._on_drawing = False
    if first is None or first[0][0] != ribbon._tab_titles.index("Zeichnungen") or again:
        print("  FEHLER: Reiterwechsel beim Zeichenblatt", first, again)
        return False
    for big in ("Assembly_CreateJointDistance", "Assembly_CreateJointParallel", "Assembly_CreateJointCylindrical",
                "Assembly_CreateView", "Assembly_CreateBom", "Assembly_InsertLink"):
        if big not in ribbon._buttons:
            print("  FEHLER: Baugruppen-Knopf fehlt oder steckt im Ausklappmenü:", big)
            return False
    import builtins
    tried = []
    real_import = builtins.__import__

    def spy(name, *a, **k):
        if name in ribbon_layout_mod.ASSEMBLY_COMMAND_MODULES:
            tried.append(name)
            raise ImportError("Attrappe: keine Assembly-Werkbank")
        return real_import(name, *a, **k)

    ribbon_layout_mod = sys.modules["swui.ribbon_layout"]
    builtins.__import__ = spy
    try:
        ribbon._load_gui_modules()
    finally:
        builtins.__import__ = real_import
    if tried != list(ribbon_layout_mod.ASSEMBLY_COMMAND_MODULES):
        print("  FEHLER: Baugruppen-Befehlsmodule werden nicht geladen", tried)
        return False
    # Symbolname wie in FreeCAD 1.1.4 (CommandCreateAssembly.py: "Geoassembly")
    if commands["SWUI_NewAssembly"].GetResources()["Pixmap"] != "Geoassembly":
        print("  FEHLER: Neue Baugruppe zeigt auf ein nicht vorhandenes Symbol")
        return False
    # Neue Baugruppe = neues Dokument, erst darin Assembly_CreateAssembly
    na = sys.modules["swui.commands.new_assembly"]
    if "SWUI_NewAssembly" not in ribbon._buttons or "Assembly_CreateAssembly" in ribbon._buttons:
        print("  FEHLER: Ribbon nutzt nicht den eigenen Befehl Neue Baugruppe")
        return False
    fcm0 = sys.modules["FreeCAD"]
    made, active = [], []
    teil = types.SimpleNamespace(Name="Teil", Label="Teil")
    alt = types.SimpleNamespace(Name="Baugruppe1", Label="Baugruppe1")
    fcm0.listDocuments = lambda: {"Teil": teil, "Baugruppe1": alt}

    def new_doc(name):
        d = types.SimpleNamespace(Name=name, Label="")
        made.append(d)
        return d

    fcm0.newDocument = new_doc
    fcm0.setActiveDocument = lambda n: active.append(n)
    later = []
    na._later = lambda fn: later.append(fn)
    n0 = len(ran)
    commands["SWUI_NewAssembly"].Activated()
    if [d.Name for d in made] != ["Baugruppe2"] or made[0].Label != "Baugruppe2" or ran[n0:]:
        print("  FEHLER: neues Dokument nicht (zuerst) angelegt", [d.Name for d in made], ran[n0:])
        return False
    later.pop()()
    if ran[n0:] != [("Assembly_CreateAssembly",)] or active[-1] != "Baugruppe2":
        print("  FEHLER: Baugruppe nicht im neuen Dokument erstellt", ran[n0:], active)
        return False
    print("  Baugruppe: Reiter rechts von Ansicht, Deckungsgleich/Parallel/Konzentrisch groß, Module werden geladen")

    # --- Drag & Drop in die Baugruppe ------------------------------------
    ad = sys.modules["swui.assembly_drop"]
    if not ad.is_installed():
        print("  FEHLER: Workbench-Activated hat Drag & Drop nicht eingeschaltet")
        return False
    fcm = sys.modules["FreeCAD"]

    class U:
        def __init__(self, p):
            self.p = p

        def toLocalFile(self):
            return self.p

    if ad.fcstd_paths([U("/h/a/Welle.FCStd"), U("/h/a/Bild.png"), "/h/a/lager.fcstd"]) != ["/h/a/Welle.FCStd", "/h/a/lager.fcstd"]:
        print("  FEHLER: Dateifilter für .FCStd")
        return False

    class Box:
        def __init__(self, xmin, xmax):
            self.XMin, self.XMax = xmin, xmax

        def isValid(self):
            return True

    class Obj:
        def __init__(self, type_id, label, inlist=(), box=(0.0, 20.0)):
            self.TypeId, self.Label, self.InList = type_id, label, list(inlist)
            self.box = box
            self.Placement = types.SimpleNamespace(Base=fcm.Vector(0, 0, 0))

        def isDerivedFrom(self, t):
            return self.TypeId == t

        def recompute(self):
            pass

    part = Obj("App::Part", "Welle")
    body = Obj("PartDesign::Body", "Body", inlist=[part])
    sketch = Obj("Sketcher::SketchObject", "Skizze", inlist=[body])
    welle_doc = types.SimpleNamespace(Objects=[part, body, sketch], FileName="/h/a/Welle.FCStd", Name="Welle")
    sub = Obj("Assembly::AssemblyObject", "Lagerbock")
    sub_doc = types.SimpleNamespace(Objects=[sub, Obj("App::Part", "Teil", inlist=[sub])], FileName="/h/a/Lagerbock.FCStd", Name="Lagerbock")
    lonely_body = Obj("PartDesign::Body", "Body")
    if ad.pick_objects(welle_doc) != [part] or ad.pick_objects(sub_doc) != [sub] or ad.pick_objects(
            types.SimpleNamespace(Objects=[lonely_body])) != [lonely_body]:
        print("  FEHLER: Auswahl des einzufügenden Objekts (Unterbaugruppe > Teil > Körper)")
        return False

    class AsmDoc:
        Name = "Baugruppe"

        def __init__(self):
            self.opened = self.committed = 0

        def openTransaction(self, _n):
            self.opened += 1

        def commitTransaction(self):
            self.committed += 1

        def recompute(self):
            pass

    asm_doc = AsmDoc()
    grounded = []

    class Asm:
        TypeId = "Assembly::AssemblyObject"
        Document = asm_doc

        def __init__(self):
            self.Group, self.OutListRecursive = [], []
            self.editing = False  # Bearbeitungsmodus (nur dann lassen sich Teile ziehen)
            self.ViewObject = types.SimpleNamespace(isInEditMode=lambda: self.editing)

        def newObject(self, type_id, label):
            o = Obj(type_id, label, box=(0.0, 15.0))
            self.Group.append(o)
            return o

    asm = Asm()
    opened = []
    fcm.listDocuments = lambda: {"Welle": welle_doc}

    def fake_open(path, hidden=False):
        opened.append((path, hidden))
        asm.editing = False  # schlimmster Fall: Oeffnen beendet den Bearbeitungsmodus
        return sub_doc

    fcm.openDocument = fake_open
    fcm.setActiveDocument = lambda name: None
    guim_d = sys.modules["FreeCADGui"]
    set_edit = []

    def fake_set_edit(obj):
        set_edit.append(asm_doc.opened - asm_doc.committed)  # 0 = ausserhalb der Transaktion
        obj.editing = True

    real_getdoc = getattr(guim_d, "getDocument", None)
    real_ctl_d = getattr(guim_d, "Control", None)
    guim_d.getDocument = lambda name: types.SimpleNamespace(setEdit=fake_set_edit)
    guim_d.Control = types.SimpleNamespace(activeDialog=lambda: False)

    def fake_ground(obj):
        grounded.append(obj)
        asm.OutListRecursive.append(types.SimpleNamespace(ObjectToGround=obj))

    sys.modules["CommandCreateJoint"] = types.SimpleNamespace(createGroundedJoint=fake_ground)
    sys.modules["Part"].getShape = lambda o: types.SimpleNamespace(
        BoundBox=Box(o.Placement.Base.x + o.box[0], o.Placement.Base.x + o.box[1]))
    try:
        added = ad.insert_files(asm, ["/h/a/Welle.FCStd", "/h/a/Lagerbock.FCStd"])
        edit_after = asm.editing
        n_set_edit = len(set_edit)
        # Offener Dialog: nicht aktivieren (wuerde ihn schliessen), nur Hinweis
        asm.editing = False
        guim_d.Control = types.SimpleNamespace(activeDialog=lambda: True)
        dlg_res = ad._ensure_active(asm)
        dlg_calls = len(set_edit) - n_set_edit
    finally:
        del sys.modules["CommandCreateJoint"]
        if real_getdoc is not None:
            guim_d.getDocument = real_getdoc
        else:
            del guim_d.getDocument
        guim_d.Control = real_ctl_d
        asm.editing = True
    if not edit_after:
        print("  FEHLER: Baugruppe nach dem Einfügen nicht im Bearbeitungsmodus - Teile ließen sich nicht ziehen")
        return False
    if n_set_edit != 2 or set_edit[:2] != [0, 0] or dlg_res or dlg_calls:
        print("  FEHLER: Aktivieren vor/nach dem Einfügen (außerhalb des Rückgängig-Schritts) bzw. bei offenem Dialog falsch", n_set_edit, set_edit, dlg_res, dlg_calls)
        return False
    if [a.TypeId for a in added] != ["App::Link", "Assembly::AssemblyLink"] or added[0].LinkedObject is not part:
        print("  FEHLER: falsche Verknüpfungsart / falsches Ziel", [a.TypeId for a in added])
        return False
    if opened != [("/h/a/Lagerbock.FCStd", True)]:
        print("  FEHLER: Datei nicht (versteckt) geöffnet oder schon offene doppelt geöffnet", opened)
        return False
    if grounded != [added[0]]:
        print("  FEHLER: erste Komponente nicht (allein) fixiert", grounded)
        return False
    if added[0].Placement.Base.x != 0 or added[1].Placement.Base.x != 15 + ad.GAP_MM:
        print("  FEHLER: Platzierung (erste im Ursprung, zweite daneben)", added[1].Placement.Base.x)
        return False
    if (asm_doc.opened, asm_doc.committed) != (1, 1):
        print("  FEHLER: nicht genau ein Rückgängig-Schritt", asm_doc.opened, asm_doc.committed)
        return False

    # Ungespeicherte Baugruppe: erst speichern, sonst nichts einfuegen
    asks, ins = [], []
    real_ask, real_ins = ad.ask_save, ad.insert_files
    try:
        ad.insert_files = lambda a, p: (ins.append(p), [])[1]
        unsaved = types.SimpleNamespace(Document=types.SimpleNamespace(FileName="", Label="Baugruppe1", Name="Baugruppe1"))
        ad.ask_save = lambda d, p: (asks.append(p), False)[1]
        ad._safe_insert(unsaved, ["/h/a/Welle.FCStd"])
        declined = list(ins)

        def do_save(d, p):
            asks.append(p)
            d.FileName = "/h/a/Baugruppe1.FCStd"
            return True

        ad.ask_save = do_save
        ad._safe_insert(unsaved, ["/h/a/Welle.FCStd"])
        ad._safe_insert(unsaved, ["/h/a/Welle.FCStd"])  # jetzt gespeichert: keine Frage mehr
    finally:
        ad.ask_save, ad.insert_files = real_ask, real_ins
    if declined or len(asks) != 2 or len(ins) != 2:
        print("  FEHLER: ungespeicherte Baugruppe nicht erst gespeichert", declined, asks, ins)
        return False
    # normpath: unter Windows setzt os.path.join einen Rueckstrich ein
    vorschlag = ad.suggested_path(types.SimpleNamespace(Label="Baugruppe1"), "/h/a/Welle.FCStd")
    if os.path.normpath(vorschlag) != os.path.normpath("/h/a/Baugruppe1.FCStd"):
        print("  FEHLER: Speicher-Vorschlag")
        return False

    # Ereignis-Filter: nur bei Baugruppe abfangen
    T = sys.modules["PySide.QtCore"].QEvent.Type

    class Ev:
        def __init__(self, kind, urls):
            self.kind, self.urls_, self.accepted = kind, urls, False

        def type(self):
            return self.kind

        def mimeData(self):
            return types.SimpleNamespace(hasUrls=lambda: True, urls=lambda: self.urls_)

        def acceptProposedAction(self):
            self.accepted = True

    real_target = ad.target_assembly
    try:
        ad.target_assembly = lambda: None
        e0 = Ev(T.Drop, [U("/h/a/Welle.FCStd")])
        r0 = ad.handle_drag_event(e0)
        ad.target_assembly = lambda: asm
        e1 = Ev(T.DragEnter, [U("/h/a/Welle.FCStd")])
        r1 = ad.handle_drag_event(e1)
        e2 = Ev(T.DragEnter, [U("/h/a/Bild.png")])
        r2 = ad.handle_drag_event(e2)
    finally:
        ad.target_assembly = real_target
    if r0 or e0.accepted or not (r1 and e1.accepted) or r2:
        print("  FEHLER: Drop-Filter greift falsch", r0, r1, r2)
        return False
    # Werkbank-Wechsel beim Doppelklick auf die Baugruppe ist in SW UI aus
    ap = fcm.ParamGet(ad.ASSEMBLY_PARAMS)
    op = fcm.ParamGet(ad.OWN_PARAMS)
    if ap.GetBool(ad.SWITCH_KEY, True) is not False or op.GetString(ad.BACKUP_KEY, "") != "1":
        print("  FEHLER: FreeCADs Wechsel in die Baugruppen-Werkbank nicht (mit Sicherung) abgeschaltet")
        return False
    ad.keep_workbench()  # zweimal betreten darf die Sicherung nicht überschreiben
    if op.GetString(ad.BACKUP_KEY, "") != "1":
        print("  FEHLER: Sicherung beim zweiten Betreten überschrieben")
        return False
    ad.restore_workbench_setting()
    if ap.GetBool(ad.SWITCH_KEY, False) is not True or op.GetString(ad.BACKUP_KEY, ""):
        print("  FEHLER: Originalwert nicht wiederhergestellt")
        return False
    ad.keep_workbench()  # Zustand wie vorher (Workbench ist noch aktiv)
    # Baugruppe auch ohne Aktivierung finden, verschachtelte zählen nicht
    top_asm = Obj("Assembly::AssemblyObject", "Baugruppe1")
    nested = Obj("Assembly::AssemblyObject", "Unter", inlist=[top_asm])
    old_doc = getattr(fcm, "ActiveDocument", None)
    fcm.ActiveDocument = types.SimpleNamespace(Objects=[top_asm, nested])
    try:
        found = ad.target_assembly()
        fcm.ActiveDocument = types.SimpleNamespace(Objects=[part])
        none_found = ad.target_assembly()
    finally:
        fcm.ActiveDocument = old_doc
    if found is not top_asm or none_found is not None:
        print("  FEHLER: Ziel-Baugruppe falsch ermittelt", found, none_found)
        return False
    print("  Drop     : .FCStd in Baugruppe -> Link/Unterbaugruppe, erste fixiert, weitere daneben, 1 Rückgängig-Schritt, vorher speichern, danach aktiv (Teile ziehbar)")

    # --- SW-Begriffe in Feature-Dialogen --------------------------------
    ft = sys.modules["swui.feature_terms"]
    if not ft.is_installed():
        print("  FEHLER: Workbench-Activated hat die SW-Begriffe nicht eingeschaltet")
        return False

    class FLabel:
        def __init__(self, t):
            self.t = t

        def text(self):
            return self.t

        def setText(self, t):
            self.t = t

    class FGroup:
        def __init__(self, t):
            self.t = t

        def title(self):
            return self.t

        def setTitle(self, t):
            self.t = t

    class FCombo:
        def __init__(self, items):
            self.items = list(items)

        def count(self):
            return len(self.items)

        def itemText(self, i):
            return self.items[i]

        def setItemText(self, i, t):
            self.items[i] = t

    class FRoot:
        def __init__(self, kids):
            self.kids = kids

        def findChild(self, _cls, name):
            return self.kids.get(name)

    pad = FRoot({
        "side1Label": FLabel("Seite 1"), "textLabel1": FLabel("Typ"), "labelLength": FLabel("Länge"),
        "checkBoxReversed": FLabel("Umgekehrt"), "groupBox": FGroup("Richtung"),
        "changeMode": FCombo(["Bemaßung", "Bis zum letzten", "Bis zum ersten", "Bis zur Fläche", "Bis zur Form"]),
        "sidesMode": FCombo(["Einseitig", "Zweiseitig", "Symmetrisch"]),
        "changeMode2": FCombo(["A", "B", "C", "D", "E", "F"]),  # andere Version: 6 Eintraege
    })
    ft.apply(pad, ft.PAD_POCKET)
    k = pad.kids
    if (k["side1Label"].t, k["textLabel1"].t, k["labelLength"].t, k["checkBoxReversed"].t, k["groupBox"].t) != (
            "Richtung 1", "Endbedingung", "Tiefe", "Richtung umkehren", "Austragungsrichtung"):
        print("  FEHLER: Beschriftungen nicht auf SW-Begriffe umgestellt")
        return False
    if k["changeMode"].items[0] != "Blind" or k["changeMode"].items[3] != "Bis Fläche" or k["sidesMode"].items[2] != "Mittelebene":
        print("  FEHLER: Endbedingungen nicht umbenannt", k["changeMode"].items, k["sidesMode"].items)
        return False
    if k["changeMode2"].items[0] != "A":
        print("  FEHLER: Liste mit unerwarteter Länge wurde trotzdem umbenannt")
        return False
    if ft.apply(pad, ft.PAD_POCKET) != 0:
        print("  FEHLER: zweiter Durchlauf ändert erneut (unnötiges Neuzeichnen)")
        return False
    # Englische Oberflaeche: dieselben Felder bekommen die englischen SW-Begriffe
    i18_ft = sys.modules["swui.i18n"]
    par_ft = sys.modules["FreeCAD"].ParamGet(i18_ft.PARAMS)
    par_ft.SetString(i18_ft.KEY, "en")
    try:
        pad_en = FRoot({
            "side1Label": FLabel("Seite 1"), "textLabel1": FLabel("Typ"), "labelLength": FLabel("Länge"),
            "groupBox": FGroup("Richtung"),
            "changeMode": FCombo(["Bemaßung", "Bis zum letzten", "Bis zum ersten", "Bis zur Fläche", "Bis zur Form"]),
            "sidesMode": FCombo(["Einseitig", "Zweiseitig", "Symmetrisch"]),
        })
        ft.apply(pad_en, ft.PAD_POCKET)
        en_again = ft.apply(pad_en, ft.PAD_POCKET)
    finally:
        par_ft.RemString(i18_ft.KEY)
    ke = pad_en.kids
    if ((ke["side1Label"].t, ke["textLabel1"].t, ke["labelLength"].t, ke["groupBox"].t)
            != ("Direction 1", "End Condition", "Depth", "Direction of Extrusion")
            or ke["changeMode"].items[:2] != ["Blind", "Through All"] or ke["sidesMode"].items[2] != "Mid Plane"):
        print("  FEHLER: SW-Begriffe in englischer Oberfläche", ke["side1Label"].t, ke["changeMode"].items)
        return False
    if en_again != 0:
        print("  FEHLER: englischer zweiter Durchlauf ändert erneut")
        return False
    rev = FRoot({"checkBoxMidplane": FLabel("Symmetrisch zur Ebene"),
                 "changeMode": FCombo(["Winkel", "Durch alles", "Bis zum ersten", "Bis zur Fläche", "Zwei Winkel"])})
    ft.apply(rev, ft.REVOLUTION)
    if rev.kids["checkBoxMidplane"].t != "Mittelebene" or rev.kids["changeMode"].items[4] != "Zwei Richtungen":
        print("  FEHLER: Rotieren-Dialog nicht umgestellt")
        return False
    mwf = sys.modules["FreeCADGui"]._mw
    pad2 = FRoot({"side1Label": FLabel("Seite 1")})
    mwf.dialog_roots = {ft.PAD_POCKET["root"]: [pad2]}
    mwf.dialog_open = False
    ft.tick()
    closed_text = pad2.kids["side1Label"].t
    mwf.dialog_open = True
    ft.tick()
    mwf.dialog_open = False
    mwf.dialog_roots = {}
    if closed_text != "Seite 1" or pad2.kids["side1Label"].t != "Richtung 1":
        print("  FEHLER: Takt findet offenen Dialog nicht / arbeitet ohne Dialog", closed_text, pad2.kids["side1Label"].t)
        return False
    # Windows (FreeCAD 1.1.4): Objektname mit "__" statt "::"
    pad_win = FRoot({"side1Label": FLabel("Seite 1")})
    mwf.dialog_roots = {"PartDesignGui__TaskPadPocketParameters": [pad_win]}
    mwf.dialog_open = True
    ft.tick()
    mwf.dialog_open = False
    mwf.dialog_roots = {}
    if pad_win.kids["side1Label"].t != "Richtung 1":
        print("  FEHLER: Dialog mit Windows-Objektnamen (PartDesignGui__...) nicht erkannt")
        return False
    jroot = FRoot({
        "jointType": FCombo(["Fest", "Drehgelenk", "Zylindrisch", "Schieber", "Kugel", "Abstand", "Parallel",
                             "Senkrecht", "Winkel", "Zahnstange", "Schraube", "Zahnräder", "Riemen"]),
        "groupBox_limits": FGroup("Begrenzungen"), "PushButtonReverse": FLabel("Umkehren"),
        "distanceLabel": FLabel("Radius 1"),  # wechselt je nach Art - muss FreeCADs bleiben
    })
    ft.apply(jroot, ft.JOINT)
    jk = jroot.kids
    if (jk["jointType"].items[2], jk["jointType"].items[5], jk["groupBox_limits"].t, jk["PushButtonReverse"].t,
            jk["distanceLabel"].t) != ("Konzentrisch", "Deckungsgleich / Abstand", "Grenzwerte",
                                       "Ausrichtung umkehren", "Radius 1"):
        print("  FEHLER: Verknüpfungs-Dialog", jk["jointType"].items, jk["groupBox_limits"].t)
        return False
    if ft.JOINT not in ft.SPECS or ft.INSERT not in ft.SPECS:
        print("  FEHLER: Baugruppen-Dialoge nicht im Takt")
        return False
    print("  Dialoge : Linear austragen/Schnitt/Rotieren/Verknüpfung mit SW-Begriffen; fremde Listenlängen bleiben unberührt")
    # Zeichnungs-Dialoge (9e1): Beschriftungen, Listen, Tooltips, Massstabsfeld bei "Benutzerdefiniert"
    class FTip:
        def __init__(self, t):
            self.tip = t

        def toolTip(self):
            return self.tip

        def setToolTip(self, t):
            self.tip = t

    class FScaleCombo(FCombo):
        def __init__(self, items, idx):
            super().__init__(items)
            self.idx = idx

        def currentIndex(self):
            return self.idx

        def isEnabled(self):
            return True

    class FSpin:
        def __init__(self):
            self.on = False

        def isEnabled(self):
            return self.on

        def setEnabled(self, v):
            self.on = bool(v)

    pg = FRoot({"label_7": FLabel("Projektion"), "chkView1": FTip("Top"), "chkView8": FTip("Bottom"),
                "projection": FCombo(["Erster Winkel", "Dritter Winkel", "Seite"]),
                "cmbScaleType": FCombo(["Seite", "Automatisch", "Benutzerdefiniert"])})
    ft.apply(pg, ft.PROJ_GROUP)
    pk = pg.kids
    if (pk["label_7"].t, pk["projection"].items[0], pk["cmbScaleType"].items[0], pk["chkView1"].tip,
            pk["chkView8"].tip) != ("Projektionsmethode", "Methode 1 (DIN/ISO)", "Blattmaßstab", "Draufsicht", "Unteransicht"):
        print("  FEHLER: Dialog Standard-Dreiansicht", pk["projection"].items, pk["chkView1"].tip)
        return False
    spin = FSpin()
    sec = FRoot({"label_7": FLabel("Basisansicht"), "gbPlane": FGroup("Schnittebene"),
                 "cmbScaleType": FScaleCombo(["Seite", "Automatisch", "Benutzerdefiniert"], 2), "sbScale": spin})
    ft.apply(sec, ft.SECTION_VIEW)
    if (sec.kids["label_7"].t, sec.kids["gbPlane"].t, sec.kids["cmbScaleType"].items[2], spin.on) != (
            "Ausgangsansicht", "Lage der Schnittebene", "Benutzerdefiniert", True):
        print("  FEHLER: Dialog Schnittansicht / Maßstabsfeld bei Benutzerdefiniert gesperrt", spin.on)
        return False
    spin2 = FSpin()
    sec2 = FRoot({"cmbScaleType": FScaleCombo(["a", "b", "c"], 0), "sbScale": spin2})
    ft.apply(sec2, ft.SECTION_VIEW)
    if spin2.on:
        print("  FEHLER: Maßstabsfeld bei Blattmaßstab freigegeben")
        return False
    det = FRoot({"label_6": FLabel("Radius"), "cbScaleType": FCombo(["x", "y", "z"])})
    cs = FRoot({"cmbStrategy": FCombo(["Versatz", "Ausgerichtet", "Keine Parallele"]), "label_9": FLabel("Profil")})
    ft.apply(det, ft.DETAIL_VIEW)
    ft.apply(cs, ft.COMPLEX_SECTION)
    if (det.kids["label_6"].t, det.kids["cbScaleType"].items[1], cs.kids["cmbStrategy"].items[0], cs.kids["label_9"].t) != (
            "Kreisradius", "Automatisch", "Abgesetzter Schnitt", "Schnittverlauf (Skizze)"):
        print("  FEHLER: Dialoge Detail / ausgerichteter Schnitt")
        return False
    if any(sp_ not in ft.SPECS for sp_ in (ft.PROJ_GROUP, ft.SECTION_VIEW, ft.DETAIL_VIEW, ft.COMPLEX_SECTION)):
        print("  FEHLER: Zeichnungs-Dialoge nicht im Takt")
        return False
    print("  Dialoge : Standard-Dreiansicht/Schnitt/Detail/ausgerichteter Schnitt mit SW-Begriffen")
    bal = FRoot({"label": FLabel("Text"), "comboLineVisible": FCombo(["Falsch", "Wahr"]),
                 "comboBubbleShape": FCombo(["a", "b", "c", "d", "e", "f", "g", "h"])})
    dimr = FRoot({"cbReference": FLabel("Referenz"), "comboDrawingStyle": FCombo(["1", "2", "3", "4"])})
    weld = FRoot({"cbAllAround": FLabel("Umlaufend"), "pbArrowSymbol": FLabel("Kehlnaht")})
    ft.apply(bal, ft.BALLOON)
    ft.apply(dimr, ft.DIMENSION)
    ft.apply(weld, ft.WELD)
    if (bal.kids["label"].t, bal.kids["comboLineVisible"].items[1], bal.kids["comboBubbleShape"].items[0],
            dimr.kids["cbReference"].t, dimr.kids["comboDrawingStyle"].items[0], weld.kids["cbAllAround"].t,
            weld.kids["pbArrowSymbol"].t) != ("Positionsnummer", "Anzeigen", "Kreis", "Hilfsmaß (in Klammern)",
                                               "ISO ausgerichtet", "Ringsum-Naht", "Kehlnaht"):
        print("  FEHLER: Beschriftungs-Dialoge (Positionsnummer/Bemaßung/Schweißen)")
        return False
    if any(sp_ not in ft.SPECS for sp_ in (ft.DIMENSION, ft.BALLOON, ft.NOTE, ft.LEADER, ft.HATCH, ft.CENTER_LINE, ft.WELD, ft.SURFACE)):
        print("  FEHLER: Beschriftungs-Dialoge nicht im Takt")
        return False
    print("  Dialoge : Bemaßung/Positionsnummer/Notiz/Hinweislinie/Schraffur/Mittellinie/Schweißen/Oberfläche mit SW-Begriffen")

    # --- Reiter wechselt beim Skizzieren --------------------------------
    gui = sys.modules["FreeCADGui"]
    tabs = ribbon._tabs
    sketch_idx = ribbon._tab_titles.index("Skizze")

    def editing(type_id):
        vp = None if type_id is None else types.SimpleNamespace(
            Object=types.SimpleNamespace(TypeId=type_id)
        )
        gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: vp)

    editing("PartDesign::Pad")  # Feature bearbeiten: KEIN Wechsel
    n0 = tabs.setCurrentIndex.call_count
    ribbon._refresh_enabled()
    if tabs.setCurrentIndex.call_count != n0:
        print("  FEHLER: Reiter gewechselt, obwohl keine Skizze bearbeitet wird")
        return False
    editing("Sketcher::SketchObject")
    ribbon._refresh_enabled()
    if tabs.setCurrentIndex.call_args[0][0] != sketch_idx:
        print("  FEHLER: beim Skizzieren nicht auf Reiter Skizze gewechselt")
        return False
    n = tabs.setCurrentIndex.call_count
    ribbon._refresh_enabled()
    if tabs.setCurrentIndex.call_count != n:
        print("  FEHLER: Reiter wird bei jedem Takt neu gesetzt (Benutzer kann nicht wechseln)")
        return False
    editing(None)
    ribbon._refresh_enabled()
    if tabs.setCurrentIndex.call_args[0][0] is not tabs.currentIndex.return_value:
        print("  FEHLER: nach der Skizze nicht zum vorherigen Reiter zurück")
        return False
    gui.ActiveDocument = None
    print("  Kontext  : Skizze -> Reiter Skizze, danach zurück; Benutzerwahl bleibt")

    # --- Mittellinie --------------------------------------------------
    cl = sys.modules["swui.commands.centerline"]
    LINE, CIRCLE = "Part::GeomLineSegment", "Part::GeomCircle"

    class Geo:
        def __init__(self, t):
            self.TypeId = t

    class Doc:
        HasPendingTransaction = False

        def __init__(self):
            self.opened = self.committed = 0

        def openTransaction(self, _name):
            self.opened += 1

        def commitTransaction(self):
            self.committed += 1

    class Sk:
        TypeId = "Sketcher::SketchObject"

        def __init__(self):
            self.Document = Doc()
            self.Geometry = [Geo(LINE)]  # schon vorhandene normale Linie
            self.constr = set()

        def getConstruction(self, i):
            return i in self.constr

        def setConstruction(self, i, state):
            (self.constr.add if state else self.constr.discard)(i)

    sk = Sk()
    vp = types.SimpleNamespace(Object=sk)
    gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: vp)

    if "SWUI_Centerline" not in commands or not commands["SWUI_Centerline"].IsActive():
        print("  FEHLER: Befehl Mittellinie fehlt oder ist in der Skizze nicht aktiv")
        return False
    commands["SWUI_Centerline"].Activated()
    if ran[-1:] != [("Sketcher_CreateLine",)] or not cl.is_running():
        print("  FEHLER: Mittellinie startet das Linienwerkzeug nicht", ran[-1:])
        return False
    sk.Geometry += [Geo(LINE), Geo(CIRCLE)]  # neue Linie + Kreis gezeichnet
    cl._tick()
    if sk.constr != {1} or sk.Document.committed != 1:
        print("  FEHLER: nur die neue Linie hätte umgewandelt werden dürfen", sk.constr)
        return False
    sk.Document.HasPendingTransaction = True  # FreeCAD hat Transaktion offen
    sk.Geometry.append(Geo(LINE))
    opened_before = sk.Document.opened
    cl._tick()
    sk.Document.HasPendingTransaction = False
    if 3 not in sk.constr:
        print("  FEHLER: bei offener FreeCAD-Transaktion nicht sofort umgewandelt (Fehler vom 16.10.)")
        return False
    if sk.Document.opened != opened_before:
        print("  FEHLER: eigene Transaktion in eine offene hinein geöffnet")
        return False
    sk.constr.discard(3)  # Abbrechen nimmt die Umwandlung zurück ...
    cl._tick()
    if 3 not in sk.constr:  # ... der nächste Takt holt sie nach
        print("  FEHLER: zurückgenommene Umwandlung wird nicht nachgeholt")
        return False
    ribbon._run("Sketcher_CreateCircle", None, False)  # anderes Werkzeug
    if cl.is_running() or sk.constr != {1, 3}:
        print("  FEHLER: Werkzeugwechsel beendet die Mittellinie nicht sauber", sk.constr)
        return False
    sk.Geometry.append(Geo(LINE))  # danach: normale Linie bleibt normal
    cl._tick()
    if 4 in sk.constr:
        print("  FEHLER: nach dem Beenden wird weiter umgewandelt")
        return False
    cl.start()
    gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: None)  # Skizze verlassen
    sk.Geometry.append(Geo(LINE))
    cl._tick()
    if cl.is_running() or 5 in sk.constr:
        print("  FEHLER: Verlassen der Skizze beendet die Mittellinie nicht")
        return False
    # --- Mittellinie (symmetrisch, gespiegelte Gegenseite) -------------
    ml = sys.modules["swui.commands.midpoint_line"]
    fc = sys.modules["FreeCAD"]
    V = fc.Vector

    class MlSketch:
        TypeId = "Sketcher::SketchObject"

        def __init__(self):
            self.Document = Doc()
            self.Geometry, self.pts, self.constraints = [], {}, []
            self.constr = set()

        def draw(self, a, b, constr=False, kind=LINE):
            """So legt FreeCADs Linienwerkzeug eine Linie an."""
            gid = len(self.Geometry)
            self.Geometry.append(Geo(kind))
            self.pts[(gid, 1)], self.pts[(gid, 2)] = a, b
            if constr:
                self.constr.add(gid)
            return gid

        def getPoint(self, gid, pos):
            return V(*self.pts[(gid, pos)])

        def getConstruction(self, i):
            return i in self.constr

        def addGeometry(self, line, constr=False):
            _kind, a, b = line
            return self.draw(a, b, constr)

        def addConstraint(self, c):
            self.constraints.append(c)

        def solve(self):
            return 0

    msk = MlSketch()
    msk.draw((0.0, 0.0), (5.0, 5.0))  # schon vorhanden: bleibt unberuehrt
    vp2 = types.SimpleNamespace(Object=msk)
    gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: vp2)

    if "SWUI_MidpointLine" not in commands or not commands["SWUI_MidpointLine"].IsActive():
        print("  FEHLER: Befehl Mittellinie fehlt oder nicht aktiv")
        return False
    commands["SWUI_MidpointLine"].Activated()
    if ran[-1:] != [("Sketcher_CreateLine",)] or not ml.is_running():
        print("  FEHLER: Mittellinie startet das Linienwerkzeug nicht", ran[-1:])
        return False
    msk.draw((10.0, 5.0), (40.0, 25.0))  # Index 1: vom Mittelpunkt gezogen
    msk.draw((0.0, 0.0), (1.0, 0.0), kind=CIRCLE)  # Index 2: Kreis
    ml._tick()
    if len(msk.Geometry) != 4 or msk.pts.get((3, 1)) != (10.0, 5.0) or msk.pts.get((3, 2)) != (-20.0, -15.0):
        print("  FEHLER: Gegenseite fehlt oder nicht gespiegelt", msk.pts)
        return False
    if msk.constraints != [("Coincident", 3, 1, 1, 1), ("Symmetric", 1, 2, 3, 2, 1, 1)]:
        print("  FEHLER: Beziehungen der Gegenseite", msk.constraints)
        return False
    if msk.constr:
        print("  FEHLER: Mittellinie ist gestrichelt", msk.constr)
        return False
    ml._tick()
    if len(msk.Geometry) != 4:
        print("  FEHLER: Gegenseite wurde selbst nochmal gespiegelt")
        return False
    msk.Document.HasPendingTransaction = True
    opened_before = msk.Document.opened
    msk.draw((0.0, 0.0), (0.0, 7.0), constr=True)  # Index 4, Konstruktionsmodus
    ml._tick()
    msk.Document.HasPendingTransaction = False
    if len(msk.Geometry) != 6 or 5 not in msk.constr or msk.pts.get((5, 2)) != (0.0, -7.0):
        print("  FEHLER: Gegenseite im Konstruktionsmodus/offener Transaktion", msk.pts.get((5, 2)))
        return False
    if msk.Document.opened != opened_before:
        print("  FEHLER: eigene Transaktion in eine offene hinein geöffnet")
        return False
    msk.draw((3.0, 3.0), (3.0, 3.0))  # Null-Linie (Doppelklick)
    ml._tick()
    if len(msk.Geometry) != 7:
        print("  FEHLER: Null-Linie gespiegelt")
        return False
    del msk.Geometry[4:]  # Rueckgaengig
    ml._tick()
    msk.draw((1.0, 1.0), (2.0, 1.0))  # Index 4 neu
    ml._tick()
    if len(msk.Geometry) != 6 or msk.pts.get((5, 2)) != (0.0, 1.0):
        print("  FEHLER: nach Rückgängig keine Gegenseite", len(msk.Geometry))
        return False
    msk.draw((0.0, 0.0), (9.0, 0.0))  # letzte Linie direkt vor Werkzeugwechsel
    ribbon._run("Sketcher_CreateCircle", None, False)
    if ml.is_running() or len(msk.Geometry) != 8:
        print("  FEHLER: Werkzeugwechsel beendet nicht sauber / letzte Linie nicht gespiegelt")
        return False
    msk.draw((0.0, 0.0), (4.0, 0.0))  # danach: normale Linie bleibt einseitig
    ml._tick()
    if len(msk.Geometry) != 9:
        print("  FEHLER: nach dem Beenden wird weiter gespiegelt")
        return False
    commands["SWUI_MidpointLine"].Activated()
    gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: None)  # Skizze verlassen
    ml._tick()
    if ml.is_running():
        print("  FEHLER: Verlassen der Skizze beendet die Mittellinie nicht")
        return False
    print("  Mittellin: Gegenseite gespiegelt (Deckungsgleich+Symmetrisch), nicht gestrichelt, Ende bei Wechsel/Skizzenende")

    # --- Beziehungs-Panel (SW "Beziehungen hinzufuegen") ---------------
    rel = sys.modules["swui.sketch_relations"]
    if not rel.is_installed():
        print("  FEHLER: Workbench-Activated hat das Beziehungs-Panel nicht angemeldet")
        return False
    T = lambda t: Geo("Part::Geom" + t)

    class RelSketch:
        TypeId = "Sketcher::SketchObject"

        def __init__(self):
            self.Document = Doc()
            # 0,1 Linie  2 Kreis  3 Bogen  4 Ellipse  5 Punkt  6 Spline
            self.Geometry = [T("LineSegment"), T("LineSegment"), T("Circle"),
                             T("ArcOfCircle"), T("Ellipse"), T("Point"), T("BSplineCurve")]
            self.ExternalGeo = [T("LineSegment"), T("LineSegment"), T("LineSegment")]
            self.vertices = {0: (0, 1), 1: (0, 2), 2: (1, 1), 3: (1, 2), 4: (5, 1)}
            self.Constraints = [
                types.SimpleNamespace(Type="Horizontal", First=0, FirstPos=0, Second=-2000, SecondPos=0, Third=-2000, ThirdPos=0),
                types.SimpleNamespace(Type="Coincident", First=0, FirstPos=2, Second=1, SecondPos=1, Third=-2000, ThirdPos=0),
                types.SimpleNamespace(Type="Distance", First=0, FirstPos=0, Second=-2000, SecondPos=0, Third=-2000, ThirdPos=0),
                types.SimpleNamespace(Type="Tangent", First=2, FirstPos=0, Second=3, SecondPos=0, Third=-2000, ThirdPos=0),
            ]
            self.deleted = []

        def getGeoVertexIndex(self, v):
            return self.vertices[v]

        def delConstraint(self, idx):
            self.deleted.append(idx)

        def solve(self):
            return 0

    rsk = RelSketch()

    def offer(*names):
        return rel.suggest(rel.classify(rsk, list(names)))

    cases = [
        (("Edge1",), ["horizontal", "vertical", "block"]),
        (("Edge1", "Edge2"), ["horizontal", "vertical", "collinear", "parallel", "perpendicular", "equal", "block"]),
        (("Edge1", "H_Axis"), ["collinear", "parallel", "perpendicular"]),
        (("Edge3", "Edge4"), ["tangent", "concentric", "equal", "block"]),
        (("Edge1", "Edge3"), ["tangent", "block"]),
        (("Edge3", "Edge5"), ["tangent", "concentric", "block"]),
        (("Edge7",), ["block"]),
        (("ExternalEdge1", "Edge1"), ["collinear", "parallel", "perpendicular", "equal"]),
        (("Vertex1", "Vertex3"), ["horizontal", "vertical", "coincident", "lock"]),
        (("Vertex1", "RootPoint"), ["horizontal", "vertical", "coincident"]),
        (("Vertex1", "Vertex3", "Vertex5"), ["coincident", "symmetric", "lock"]),
        (("Vertex3", "Edge1"), ["on_object", "midpoint"]),
        (("Vertex1", "Edge1"), []),  # eigener Endpunkt: FreeCAD lehnt ab
        (("Vertex3", "Vertex4", "Edge1"), ["on_object", "symmetric"]),
        (("RootPoint", "Edge1"), ["on_object", "midpoint"]),
        (("Vertex3", "Edge3"), ["on_object"]),
        (("Constraint3",), []),
    ]
    for names, want in cases:
        got = offer(*names)
        if got != want:
            print("  FEHLER: Beziehungen für", names, "->", got, "erwartet", want)
            return False
    for key, (command, _text) in rel.RELATIONS.items():
        if command not in sys.modules["FreeCADGui"].listCommands():
            print("  FEHLER: Beziehungsbefehl existiert nicht in FreeCAD 1.1.4:", command)
            return False
    pmod = sys.modules["swui.paths"]
    missing_icons = [k for k in rel.RELATIONS if not pmod.icon(rel.RELATION_ICONS.get(k) or "-")]
    if missing_icons:
        print("  FEHLER: Beziehungen ohne eigenes Symbol:", missing_icons)
        return False
    labels = [e.label for e in rel.classify(rsk, ["Edge1", "Edge3", "Vertex4", "RootPoint", "H_Axis", "ExternalEdge1"])]
    if labels != ["Linie1", "Kreis3", "Punkt4", "Ursprung", "Horizontale Achse", "Übernommen1"]:
        print("  FEHLER: Elementnamen", labels)
        return False
    ex = rel.existing(rsk, rel.classify(rsk, ["Edge1"]))
    if ex != [(0, "Horizontal"), (1, "Deckungsgleich")]:
        print("  FEHLER: vorhandene Beziehungen der Linie (ohne Bemaßung)", ex)
        return False
    # Dieselben Namen auf Englisch (Sprache Schritt 2b)
    fcp = sys.modules["FreeCAD"].ParamGet("User parameter:BaseApp/Preferences/Mod/SWUI")
    fcp.SetString("Language", "en")
    try:
        labels_en = [e.label for e in rel.classify(rsk, ["Edge1", "Edge3", "Vertex4", "RootPoint", "H_Axis", "ExternalEdge1"])]
        ex_en = rel.existing(rsk, rel.classify(rsk, ["Edge1"]))
    finally:
        fcp.RemString("Language")
    if labels_en != ["Line1", "Circle3", "Point4", "Origin", "Horizontal axis", "Converted1"] or ex_en != [(0, "Horizontal"), (1, "Coincident")]:
        print("  FEHLER: Elementnamen/Beziehungen auf Englisch", labels_en, ex_en)
        return False
    if rel.existing(rsk, rel.classify(rsk, ["Vertex2"])) != [(1, "Deckungsgleich")] or rel.existing(
        rsk, rel.classify(rsk, ["Vertex1"])
    ):
        print("  FEHLER: vorhandene Beziehungen eines Punkts")
        return False

    # Ablauf mit Auswahl-Beobachter
    rel.uninstall()
    rel.install()
    if not rel.is_installed() or len([o for o in gui._sel_observers if isinstance(o, rel._SelectionObserver)]) != 1:
        print("  FEHLER: Auswahl-Beobachter nicht (genau einmal) angemeldet", gui._sel_observers)
        return False
    vp3 = types.SimpleNamespace(Object=rsk)
    gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: vp3)
    gui._sel = [types.SimpleNamespace(Object=rsk, SubElementNames=("Edge1", "Edge2"))]
    log.clear()
    rel.refresh()
    if any(level in ("ERR", "WARN") for level, _t in log):
        print("  FEHLER: Panel-Aufbau meldet Fehler:", log)
        return False
    if rel._panel is None or rel._panel.offered != cases[1][1]:
        print("  FEHLER: Panel zeigt nicht die passenden Beziehungen")
        return False
    if rel._panel.existing_ids != [0, 1]:
        print("  FEHLER: Panel zeigt vorhandene Beziehungen nicht", rel._panel.existing_ids)
        return False
    rel.run_relation("parallel")
    if ran[-1:] != [("Sketcher_ConstrainParallel",)]:
        print("  FEHLER: Knopf startet die Beziehung nicht", ran[-1:])
        return False
    rel.delete_relations(rsk, [0, 1])
    if rsk.deleted != [1, 0] or rsk.Document.opened != rsk.Document.committed:
        print("  FEHLER: Löschen nicht von hinten / ohne Rückgängig-Schritt", rsk.deleted)
        return False
    w = rel._panel.widget
    w.hide.reset_mock()
    gui._sel = []
    rel.refresh()
    if not w.hide.called:
        print("  FEHLER: Panel bleibt ohne Auswahl sichtbar")
        return False
    gui._sel = [types.SimpleNamespace(Object=rsk, SubElementNames=("Edge1",))]
    w.hide.reset_mock()
    gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: None)  # Skizze zu
    rel.refresh()
    if not w.hide.called:
        print("  FEHLER: Panel bleibt nach Skizzenende sichtbar")
        return False
    # Einhaengen OBEN in FreeCADs Aufgaben-Panel (TaskPanel in QScrollArea)
    lay = sys.modules["swui.layout"]
    host = mock.MagicMock(name="TaskPanel")
    host.metaObject.return_value.className.return_value = "Gui::TaskView::TaskPanel"
    other = mock.MagicMock(name="AndereScrollArea")
    other.widget.return_value.metaObject.return_value.className.return_value = "QWidget"
    area = mock.MagicMock(name="TaskScrollArea")
    area.widget.return_value = host
    tasks = mock.MagicMock(name="TasksDock")
    tasks.findChildren.return_value = [other, area]
    real_find = lay._find_dock
    lay._find_dock = lambda _mw, _keys: tasks
    try:
        gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: vp3)
        gui._sel = [types.SimpleNamespace(Object=rsk, SubElementNames=("Vertex3", "Edge1"))]
        rel.refresh()
    finally:
        lay._find_dock = real_find
    ins = host.layout.return_value.insertWidget
    if not ins.called or ins.call_args[0][0] != 0 or ins.call_args[0][1] is not rel._panel.widget:
        print("  FEHLER: Panel nicht oben ins Aufgaben-Panel eingehängt", ins.call_args)
        return False
    if not tasks.raise_.called or rel._panel.offered != ["on_object", "midpoint"]:
        print("  FEHLER: Aufgaben-Panel nicht nach vorn / falsche Beziehungen")
        return False
    rel.uninstall()
    if rel.is_installed() or any(isinstance(o, rel._SelectionObserver) for o in gui._sel_observers):
        print("  FEHLER: Beobachter nach dem Verlassen noch aktiv")
        return False
    gui._sel = []
    print("  Bezieh.  : %d Auswahl-Fälle passend; vorhandene ohne Maße; Knopf, Löschen, Ein-/Ausblenden OK" % len(cases))

    # --- Kontext-Symbol "Skizze erstellen" (Wunschliste 1) ---------------
    cs = sys.modules.get("swui.context_sketch")
    if cs is None or not cs.is_installed() or not any(isinstance(o, cs._SelectionObserver) for o in gui._sel_observers):
        print("  FEHLER: Workbench-Activated hat das Symbol Skizze erstellen nicht eingeschaltet")
        return False
    if (cs.opacity_for(0), cs.opacity_for(cs.FADE_START), round(cs.opacity_for(100), 2), cs.opacity_for(cs.FADE_END)) != (1.0, 1.0, 0.5, 0.0):
        print("  FEHLER: Ausblenden nach Abstand", cs.opacity_for(100))
        return False

    class CFace:
        def __init__(self, planar):
            self.planar = planar

        def isPlanar(self):
            return self.planar

    class CObj:
        def __init__(self, name, type_id="PartDesign::Pad", parents=()):
            self.Name, self.TypeId, self.InListRecursive = name, type_id, list(parents)

        def getSubObject(self, sub):
            return {"Face1": CFace(True), "Face2": CFace(False), "Pad.Face1": CFace(True)}.get(sub)

    asm_c = CObj("Assembly", "Assembly::AssemblyObject")
    cobjs = {"Pad": CObj("Pad"), "Body": CObj("Body", "PartDesign::Body"), "Teil": CObj("Teil", parents=[asm_c]),
             "Assembly": asm_c}
    fc_c = sys.modules["FreeCAD"]
    old_getdoc = getattr(fc_c, "getDocument", None)
    fc_c.getDocument = lambda _n: types.SimpleNamespace(getObject=lambda n: cobjs.get(n))
    one = [types.SimpleNamespace(SubElementNames=["Face1"])]
    two = [types.SimpleNamespace(SubElementNames=["Face1", "Face3"])]
    cases_c = [  # (Objekt, Element, Auswahl, Dialog offen, Parameter) -> erwartet
        (("Pad", "Face1", one, False, True), True),
        (("Body", "Pad.Face1", one, False, True), True),
        (("Pad", "Face2", one, False, True), False),   # nicht eben
        (("Pad", "Edge3", one, False, True), False),   # keine Flaeche
        (("Pad", "Face1", two, False, True), False),   # zwei Elemente gewaehlt
        (("Pad", "Face1", one, True, True), False),    # Dialog offen (Feature waehlt Flaechen)
        (("Teil", "Face1", one, False, True), False),  # in einer Baugruppe
        (("Assembly", "Face1", one, False, True), False),
        (("Pad", "Face1", one, False, False), False),  # per Parameter abgeschaltet
    ]
    par_c = fc_c.ParamGet(cs.PARAMS)
    bad_c = []
    try:
        for (o_, s_, sel_, dlg_, on_), want_ in cases_c:
            gui._sel = sel_
            gui._mw.dialog_open = dlg_
            par_c.SetBool(cs.PARAM_KEY, on_)
            if cs.should_show("Doc", o_, s_) != want_:
                bad_c.append((o_, s_, dlg_, on_))
    finally:
        gui._mw.dialog_open = False
        par_c.RemBool(cs.PARAM_KEY)
        gui._sel = []
    if bad_c:
        print("  FEHLER: Symbol Skizze erstellen – falsche Fälle", bad_c)
        return False
    # Klick auf Flaeche -> Symbol rechts oberhalb des Mauspfeils; weit weg -> verschwindet; Klick -> Skizze
    qtc_c = sys.modules["PySide.QtCore"]
    qtg_c = sys.modules["PySide.QtGui"]
    old_single_c = qtc_c.QTimer.singleShot
    old_cursor_c = qtg_c.QCursor
    cur_c = [(500, 400)]
    qtg_c.QCursor = types.SimpleNamespace(pos=lambda: types.SimpleNamespace(x=lambda: cur_c[0][0], y=lambda: cur_c[0][1]))
    qtc_c.QTimer.singleShot = lambda _ms, fn: fn()
    try:
        gui._sel = one
        obs_c = [o for o in gui._sel_observers if isinstance(o, cs._SelectionObserver)][0]
        obs_c.addSelection("Doc", "Pad", "Face1", (0, 0, 0))
        pop_c = cs._popup
        moved_c = pop_c.move.call_args[0] if pop_c is not None and pop_c.move.called else None
        shown_c = pop_c is not None and pop_c.show.called
        g_c = types.SimpleNamespace(x=lambda: 514, y=lambda: 356, width=lambda: 38, height=lambda: 38)
        pop_c.geometry = lambda: g_c
        pop_c.isVisible = lambda: True
        pop_c.hide.reset_mock()
        cur_c[0] = (533, 375)
        cs._poll()
        near_hidden = pop_c.hide.called
        cur_c[0] = (900, 800)
        cs._poll()
        far_hidden = pop_c.hide.called
        gui._ran.clear()
        cs._clicked()
        ran_c = list(gui._ran)
        obs_c.clearSelection("Doc")
    finally:
        qtc_c.QTimer.singleShot = old_single_c
        qtg_c.QCursor = old_cursor_c
        gui._sel = []
        if old_getdoc is None:
            del fc_c.getDocument
        else:
            fc_c.getDocument = old_getdoc
    if moved_c != (514, 356) or not shown_c or near_hidden or not far_hidden or ran_c != [("PartDesign_NewSketch",)]:
        print("  FEHLER: Symbol Skizze erstellen – Zeigen/Ausblenden/Klick", moved_c, shown_c, near_hidden, far_hidden, ran_c)
        return False
    print("  Skizz-Sym: „Skizze erstellen“ nur bei einer ebenen Fläche im Teil, blasst weg, Klick legt Skizze an")

    # --- Linieneigenschaften (Wunschliste 3) -----------------------------
    lf = sys.modules.get("swui.line_format")
    lf_cmd = commands.get("SWUI_LineFormat")
    if lf is None or lf_cmd is None:
        print("  FEHLER: Befehl SWUI_LineFormat nicht angemeldet")
        return False
    view_l = types.SimpleNamespace(TypeId="TechDraw::DrawProjGroupItem")
    page_l = types.SimpleNamespace(TypeId="TechDraw::DrawPage")
    sel_ok = [types.SimpleNamespace(Object=view_l, SubElementNames=["Edge3", "Vertex1", "Edge7"])]
    sel_bad = [types.SimpleNamespace(Object=view_l, SubElementNames=["Vertex1"]),
               types.SimpleNamespace(Object=page_l, SubElementNames=["Edge1"])]
    if lf.selected_edges(sel_ok) != [(view_l, ["Edge3", "Edge7"])] or lf.selected_edges(sel_bad) != []:
        print("  FEHLER: Linien-Auswahl erkannt", lf.selected_edges(sel_ok), lf.selected_edges(sel_bad))
        return False
    gui._ran.clear()
    gui._sel = sel_bad
    lf_cmd.Activated()
    ran_none = list(gui._ran)
    gui._sel = sel_ok
    lf_cmd.Activated()
    ran_some = list(gui._ran)
    gui._sel = []
    if ran_none or ran_some != [("TechDraw_DecorateLine",)]:
        print("  FEHLER: Linieneigenschaften – Dialog ohne/mit Auswahl", ran_none, ran_some)
        return False
    i18_lf = sys.modules["swui.i18n"]
    par_lf = sys.modules["FreeCAD"].ParamGet(i18_lf.PARAMS)
    w_de = (lf.width_text(0.35), lf.width_text(1.0), lf.width_text(0.13))
    par_lf.SetString(i18_lf.KEY, "en")
    try:
        w_en = lf.width_text(0.35)
    finally:
        par_lf.RemString(i18_lf.KEY)
    if w_de != ("0,35 mm", "1 mm", "0,13 mm") or w_en != "0.35 mm" or (lf.nearest_index(0.5), lf.nearest_index(0.42)) != (5, 0):
        print("  FEHLER: Normstärken-Texte", w_de, w_en, lf.nearest_index(0.5))
        return False

    class LSpin:
        def __init__(self):
            self.props = {"rawValue": 0.25}

        def setProperty(self, k, v):
            self.props[k] = v

        def property(self, k):
            return self.props.get(k)

    spin_l = LSpin()
    lf._apply_preset(spin_l, 4)
    after_4 = spin_l.props["rawValue"]
    lf._apply_preset(spin_l, 0)  # Eintrag "–" aendert nichts
    if after_4 != 0.35 or spin_l.props["rawValue"] != 0.35:
        print("  FEHLER: Normstärke setzt das Zahlenfeld nicht", after_4, spin_l.props)
        return False

    class LRoot:
        def __init__(self):
            self.inserted = []
            lay = types.SimpleNamespace(insertWidget=lambda i, w: self.inserted.append((i, w)))
            self.layout = lambda: lay

        def findChild(self, _cls, name):
            if name == lf.WEIGHT_SPIN:
                return spin_l
            if name == lf.PRESET_NAME and self.inserted:
                return types.SimpleNamespace(findChild=lambda _c: types.SimpleNamespace(
                    text=lambda: sys.modules["swui.i18n"].tr(lf.PRESET_LABEL), setText=lambda _t: None))
            return None

    root_l = LRoot()
    first_l = lf.add_presets(root_l)
    second_l = lf.add_presets(root_l)
    if first_l != 1 or second_l != 0 or len(root_l.inserted) != 1 or root_l.inserted[0][0] != 1:
        print("  FEHLER: Schnellauswahl Normstärke im Dialog (genau einmal, unter den Feldern)", first_l, second_l, root_l.inserted)
        return False
    ft_l = sys.modules["swui.feature_terms"]
    if ft_l.LINE_DECOR not in ft_l.SPECS or ft_l.LINE_DECOR["root"] != "TechDrawGui::TaskLineDecor":
        print("  FEHLER: SW-Begriffe für den Liniendialog fehlen")
        return False
    print("  Linien   : Linieneigenschaften nur mit gewählten Linien, SW-Begriffe, Normstärken ISO 128 setzen den Wert")

    # --- Blatt-Skizze: Feld "Formen" (Wunschliste 2, Z1a) -----------------
    ss = sys.modules.get("swui.sheet_sketch")
    shape_cmds = ["SWUI_SheetShape_" + k for k, _t, _x in (ss.SHAPES if ss else [])]
    if ss is None or not shape_cmds or any(c not in commands for c in shape_cmds):
        print("  FEHLER: Befehle für Formen auf dem Blatt nicht angemeldet")
        return False
    if ss.frame_lines(297, 210) != [((0, 0), (297.0, 0)), ((297.0, 0), (297.0, 210.0)), ((297.0, 210.0), (0, 210.0)), ((0, 210.0), (0, 0))]:
        print("  FEHLER: Blattrand der Blatt-Skizze", ss.frame_lines(297, 210))
        return False

    class SObj:
        def __init__(self, doc, type_id, name):
            self.Document, self.TypeId, self.Name, self.Label = doc, type_id, name, name
            self.geo, self.cons, self.views = [], [], []
            self.X = self.Y = 0.0
            self.ViewObject = types.SimpleNamespace(clicked=[], doubleClicked=lambda: self.ViewObject.clicked.append(1))

        def addProperty(self, _t, name, *_a):
            setattr(self, name, None)

        def addGeometry(self, g, construction=False):
            self.geo.append((g, construction))
            return len(self.geo) - 1

        def addConstraint(self, c):
            self.cons.append(c)

        @property
        def Geometry(self):
            pt = lambda xy: types.SimpleNamespace(x=xy[0], y=xy[1])
            return [types.SimpleNamespace(StartPoint=pt(g[1]), EndPoint=pt(g[2])) for g, _c in self.geo]

        def delGeometries(self, ids):
            # wie FreeCAD: Linien weg, Bedingungen daran weg, hoehere Indizes ruecken nach
            keep = [i for i in range(len(self.geo)) if i not in ids]
            self.geo = [self.geo[i] for i in keep]
            self.cons = [("Block", keep.index(c[1])) for c in self.cons if c[1] in keep]

        def addView(self, v):
            self.views.append(v)

    class SDoc:
        Name = "Zeichnung"

        def __init__(self):
            self.Objects, self.tx = [], []

        def addObject(self, t_, n_):
            o = SObj(self, t_, n_)
            self.Objects.append(o)
            return o

        def openTransaction(self, n_):
            self.tx.append(n_)

        def commitTransaction(self):
            self.tx.append("commit")

        def recompute(self):
            pass

        def getObject(self, n_):
            return next((o for o in self.Objects if o.Name == n_), None)

    sdoc = SDoc()
    spage = sdoc.addObject("TechDraw::DrawPage", "Page")
    spage.Template = types.SimpleNamespace(Width=420.0, Height=297.0)
    had_td2 = "TechDraw" in sys.modules
    sys.modules.setdefault("TechDraw", types.ModuleType("TechDraw"))
    edits_s, ran_s = [], []
    in_edit_s = [False]

    def set_edit_s(n_):
        edits_s.append(n_)
        in_edit_s[0] = True

    gdoc_s = types.SimpleNamespace(
        mdiViewsOfType=lambda _c: [],  # Zeichnungsdatei ohne 3D-Fenster
        setEdit=set_edit_s,
        getInEdit=lambda: types.SimpleNamespace(Object=sdoc.getObject("SheetSketch")) if in_edit_s[0] else None)
    fc_s = sys.modules["FreeCAD"]
    old_gd_s, old_fgd_s = getattr(gui, "getDocument", None), getattr(fc_s, "getDocument", None)
    gui.getDocument = lambda _n: gdoc_s
    fc_s.getDocument = lambda _n: sdoc
    old_run_s = gui.runCommand
    gui.runCommand = lambda c_, *a_: ran_s.append(c_)
    qtc_s = sys.modules["PySide.QtCore"]
    old_single_s = qtc_s.QTimer.singleShot
    qtc_s.QTimer.singleShot = lambda _ms, fn: fn()
    msgs_s = []
    old_msg_s = getattr(gui, "SendMsgToActiveView", None)
    gui.SendMsgToActiveView = lambda m_: msgs_s.append(m_)
    try:
        sk = ss.edit(spage, "Sketcher_CreateCircle")
        view_s = ss.find_sheet_view(sk)
        frame_init = [(g[1], g[2]) for g, c in sk.geo if c]
        blocks_init = [c for c in sk.cons if c[0] == "Block"]
        again_s = ss.edit(spage, "Sketcher_ConstrainEqual")  # schon offen: nur Werkzeug, nicht neu oeffnen
        n_objs = len(sdoc.Objects)
        # Kreis bei (100, 50) r=10 gezeichnet -> Huelle 90..110 / 40..60
        sk.Shape = types.SimpleNamespace(BoundBox=types.SimpleNamespace(
            isValid=lambda: True, XMin=90.0, XMax=110.0, YMin=40.0, YMax=60.0))
        ss.tick()  # noch in Bearbeitung: nichts
        still = (view_s.X, view_s.Y)
        in_edit_s[0] = False
        ss.tick()  # "Skizze beenden"
        after_s = (view_s.X, view_s.Y, len(spage.ViewObject.clicked))
        frame_before = [g[1] for g, c in sk.geo if c][:1]
        # Benutzer zieht die Zeichnung auf dem Blatt um (+50, +30) -> beim naechsten Bearbeiten
        # wandert der Blattrand um (-50, -30), nach "Skizze beenden" bleibt die Ansicht, wo sie ist
        view_s.X, view_s.Y = 150.0, 80.0
        ss.edit(spage, "Sketcher_CreateLine")
        frame_moved = [(g[1], g[2]) for g, c in sk.geo if c]
        blocks_moved = sorted(c[1] for c in sk.cons)
        in_edit_s[0] = False
        ss.tick()
        dragged_s = (view_s.X, view_s.Y)
    finally:
        if old_msg_s is None:
            del gui.SendMsgToActiveView
        else:
            gui.SendMsgToActiveView = old_msg_s
        qtc_s.QTimer.singleShot = old_single_s
        gui.runCommand = old_run_s
        if old_gd_s is None:
            del gui.getDocument
        else:
            gui.getDocument = old_gd_s
        if old_fgd_s is None:
            del fc_s.getDocument
        else:
            fc_s.getDocument = old_fgd_s
        if not had_td2:
            del sys.modules["TechDraw"]
    frame_s, blocks_s = frame_init, blocks_init
    if (getattr(sk, ss.SKETCH_PROP) is not spage or len(frame_s) != 4 or len(blocks_s) != 4
            or frame_s[1] != ((420.0, 0.0), (420.0, 297.0))):
        print("  FEHLER: Blatt-Skizze mit Blattrand (Konstruktion, blockiert)", frame_s, blocks_s)
        return False
    if (view_s is None or view_s.Source != [sk] or view_s.Scale != 1.0 or view_s.ScaleType != "Custom"
            or (view_s.Direction.z, view_s.XDirection.x) != (1.0, 1.0) or spage.views != [view_s]
            or getattr(view_s, "LockPosition", False)):
        print("  FEHLER: Ansicht der Blatt-Skizze (1:1, von oben, auf dem Blatt)")
        return False
    if again_s is not sk or n_objs != 3 or edits_s != ["SheetSketch", "SheetSketch"]:
        print("  FEHLER: Blatt-Skizze wird doppelt angelegt / nicht bearbeitet", n_objs, edits_s)
        return False
    if ran_s[:3] != ["Std_ViewCreate", "Sketcher_CreateCircle", "Sketcher_ConstrainEqual"]:
        print("  FEHLER: 3D-Fenster/Werkzeug beim Zeichnen", ran_s)
        return False
    if still != (210.0, 148.5) or after_s != (100.0, 50.0, 1):
        print("  FEHLER: Ansicht nach Skizze beenden nicht 1:1 aufs Blatt gelegt / Blatt nicht vorn", still, after_s)
        return False
    if (frame_before != [(0.0, 0.0)] or len(frame_moved) != 4 or frame_moved[0] != ((-50.0, -30.0), (370.0, -30.0))
            or blocks_moved != [0, 1, 2, 3] or dragged_s != (150.0, 80.0)):
        print("  FEHLER: Zeichnung auf dem Blatt verschoben – Blattrand/Ansicht", frame_moved[:1], blocks_moved, dragged_s)
        return False
    old_sk = SObj(sdoc, "Sketcher::SketchObject", "Alt")
    old_sk.geo = [(("Line", (5.0, 5.0), (20.0, 5.0)), False)] + [
        (("Line", s_, e_), True) for s_, e_ in ss.frame_lines(420.0, 297.0)]
    if ss.detect_frame(old_sk, 420.0, 297.0) != 1 or ss.detect_frame(old_sk, 297.0, 210.0) is not None:
        print("  FEHLER: Blattrand älterer Blatt-Skizzen nicht erkannt", ss.detect_frame(old_sk, 420.0, 297.0))
        return False
    if msgs_s.count("ViewFit") < 2:
        print("  FEHLER: beim Platzieren nicht aufs ganze Blatt gezoomt", msgs_s)
        return False
    nm_s = sys.modules["swui.naming"]
    if (nm_s.sw_label_for(sk), nm_s.sw_label_for(view_s)) != ("Blatt-Skizze1", "Blatt-Skizzen-Ansicht1"):
        print("  FEHLER: Baumnamen der Blatt-Skizze", nm_s.sw_label_for(sk), nm_s.sw_label_for(view_s))
        return False
    fly_f = [f for f in sys.modules["swui.ribbon"]._flyouts if f.get("title") == "Formen"]
    if not fly_f or [v["command"] for v in fly_f[0]["variants"]] != shape_cmds:
        print("  FEHLER: Feld Formen im Ribbon (feste Beschriftung, alle Formen)")
        return False
    print("  Blatt-Sk.: Formen öffnen Blatt-Skizze (Rand blockiert, aufs Blatt gezoomt), 1:1 aufs Blatt, frei verschiebbar – Rand wandert mit")

    # --- Feld "Text" (Z2) --------------------------------------------------
    tn = sys.modules.get("swui.text_note")
    if tn is None or "SWUI_Text" not in commands:
        print("  FEHLER: Befehl SWUI_Text nicht angemeldet")
        return False
    if tn.lines_of("Allgemeintoleranz ISO 2768-m") != ["Allgemeintoleranz ISO 2768-m"] or tn.lines_of("   ") != [] \
            or tn.lines_of("Zeile 1\\nZeile 2") != ["Zeile 1", "Zeile 2"]:
        print("  FEHLER: Text in Zeilen", tn.lines_of("Zeile 1\\nZeile 2"))
        return False
    tdoc = SDoc()
    tpage = tdoc.addObject("TechDraw::DrawPage", "Page")
    qtw_t = sys.modules["PySide.QtWidgets"]
    qtc_t = sys.modules["PySide.QtCore"]
    # Fenster: (Text, Wert, Einheit); beim Aendern 10 pt
    answers_t = [("Bohrungen entgratet", 5.0, "mm"), ("", 3.5, "mm"), ("geändert", 10.0, "pt")]
    seen_t = []

    def dialog_t(text_, size_, unit_):
        seen_t.append((text_, round(size_, 4), unit_))
        return answers_t.pop(0)

    old_dialog_t = tn._run_dialog
    tn._run_dialog = dialog_t
    par_t2 = sys.modules["FreeCAD"].ParamGet(tn.PARAMS)
    old_single_t = qtc_t.QTimer.singleShot
    qtc_t.QTimer.singleShot = lambda _ms, fn: fn()
    had_td3 = "TechDraw" in sys.modules
    sys.modules.setdefault("TechDraw", types.ModuleType("TechDraw"))
    try:
        # Klick bei Szene (1200, -800) -> Blatt (120, 80) mm (Rez 10, y nach oben)
        T_ = qtc_t.QEvent.Type
        gview_t = types.SimpleNamespace(mapToScene=lambda _p: types.SimpleNamespace(x=lambda: 1200.0, y=lambda: -800.0))
        picker_t = types.SimpleNamespace(page=tpage, gview=gview_t)
        click_t = types.SimpleNamespace(type=lambda: T_.MouseButtonPress, button=lambda: qtc_t.Qt.MouseButton.LeftButton,
                                        position=lambda: types.SimpleNamespace(toPoint=lambda: (0, 0)))
        took_t = tn.handle_pick_event(picker_t, click_t)
        made_t = [o for o in tdoc.Objects if o.TypeId == tn.ANNOTATION_TYPE]
        tn.handle_pick_event(picker_t, click_t)  # leere Eingabe -> nichts
        made_t2 = [o for o in tdoc.Objects if o.TypeId == tn.ANNOTATION_TYPE]
        esc_t = types.SimpleNamespace(type=lambda: T_.KeyPress, key=lambda: qtc_t.Qt.Key.Key_Escape)
        esc_took = tn.handle_pick_event(picker_t, esc_t)
        size_first = getattr(made_t[0], "TextSize", None) if made_t else None
        if made_t:
            tn.edit_text(made_t[0])
        remembered_t = tn.last_size()
    finally:
        tn._run_dialog = old_dialog_t
        par_t2.RemFloat("TextSize")
        par_t2.RemString("TextUnit")
        qtc_t.QTimer.singleShot = old_single_t
        if not had_td3:
            del sys.modules["TechDraw"]
    if not took_t or len(made_t) != 1 or len(made_t2) != 1 or not esc_took:
        print("  FEHLER: Text per Klick aufs Blatt (genau ein Text, leere Eingabe/Esc ohne Text)", took_t, len(made_t), len(made_t2))
        return False
    tx = made_t[0]
    pt10 = 10.0 * 25.4 / 72.0
    if (round(tn.to_mm(72, "pt"), 6) != 25.4 or round(tn.from_mm(25.4, "pt"), 6) != 72.0 or tn.to_mm(3.5, "mm") != 3.5
            or size_first != 5.0 or seen_t[-1] != ("Bohrungen entgratet", 5.0, "mm") or seen_t[1] != ("", 5.0, "mm")
            or abs(remembered_t[0] - pt10) > 1e-9 or remembered_t[1] != "pt"):
        print("  FEHLER: Schriftgröße mm/pt (Umrechnung, Vorbelegung beim Ändern, gemerkt)", size_first, seen_t, remembered_t)
        return False
    if ((round(tx.X, 6), round(tx.Y, 6)) != (120.0, 80.0) or tx.Text != ["geändert"]
            or abs(getattr(tx, "TextSize", 0) - pt10) > 1e-9
            or tpage.views != [tx] or not tn.is_text(tx) or tdoc.tx.count("commit") != 2):
        print("  FEHLER: Text – Lage, Inhalt, Schrifthöhe, Rückgängig", tx.X, tx.Y, tx.Text, tdoc.tx)
        return False
    if sys.modules["swui.naming"].sw_label_for(tx) != "Text1":
        print("  FEHLER: Baumname des Texts", sys.modules["swui.naming"].sw_label_for(tx))
        return False
    cpt = sys.modules["swui.compat"]
    calls_c = []
    old_style = types.SimpleNamespace(exec_=lambda: calls_c.append("exec_") or 1)
    new_style = types.SimpleNamespace(exec=lambda: calls_c.append("exec") or 1, exec_=lambda: calls_c.append("falsch"))
    if cpt.exec_dialog(old_style) != 1 or cpt.exec_dialog(new_style) != 1 or calls_c != ["exec_", "exec"]:
        print("  FEHLER: Fenster öffnen unter PySide2 (exec_) / PySide6 (exec)", calls_c)
        return False
    print("  Text     : Klick aufs Blatt, Text + Schriftgröße in mm/pt, gewählten Text ändern, Esc bricht ab, Baum Text1")

    # --- Verknuepfungs-Panel (Baugruppe, 8e) -----------------------------
    mt = sys.modules.get("swui.assembly_mates")
    if mt is None or not mt.is_installed():
        print("  FEHLER: Workbench-Activated hat das Verknüpfungs-Panel nicht eingeschaltet")
        return False
    if len([o for o in gui._sel_observers if isinstance(o, mt._SelectionObserver)]) != 1:
        print("  FEHLER: Verknüpfungs-Beobachter nicht genau einmal angemeldet")
        return False
    for cmd, _t, svg in mt.MATES.values():
        if not os.path.isfile(os.path.join(ADDON, "resources", "icons", svg + ".svg")):
            print("  FEHLER: Symbol fehlt", svg)
            return False

    class Plane: pass
    class Cylinder: pass
    class Cone: pass
    class Sphere: pass
    class Line: pass
    class Circle: pass
    class BSplineSurface: pass

    def face(cls):
        return types.SimpleNamespace(ShapeType="Face", Surface=cls())

    def edge(cls):
        return types.SimpleNamespace(ShapeType="Edge", Curve=cls())

    kinds = [mt.kind_of_shape(x) for x in (face(Plane), face(Cylinder), face(Sphere), face(BSplineSurface),
                                           edge(Line), edge(Circle), types.SimpleNamespace(ShapeType="Vertex"), None)]
    if kinds != ["plane", "cylinder", "sphere", "face", "line", "circle", "point", "part"]:
        print("  FEHLER: Geometrie-Art", kinds)
        return False
    E = mt.Element
    mcases = [
        (("plane", "plane"), ["coincident", "parallel", "perpendicular", "distance", "angle"]),
        (("cylinder", "circle"), ["concentric", "coincident", "revolute", "parallel", "perpendicular", "distance"]),
        (("cylinder", "plane"), ["parallel", "perpendicular", "distance"]),
        (("line", "cylinder"), ["concentric", "coincident", "parallel", "perpendicular", "slider", "distance"]),
        (("point", "plane"), ["coincident", "distance"]),
        (("sphere", "sphere"), ["ball", "coincident", "distance"]),
        (("plane",), []),
        (("part", "plane"), []),
    ]
    for ks, want in mcases:
        got = mt.suggest([E(k, "T%d" % i) for i, k in enumerate(ks)])
        if got != want:
            print("  FEHLER: Verknüpfungen für", ks, "->", got, "erwartet", want)
            return False
    if not mt.same_component([E("plane", "Welle<1>"), E("plane", "Welle<1>")]):
        print("  FEHLER: gleiches Bauteil nicht erkannt")
        return False

    # Ablauf: aktive Baugruppe, zwei Flaechen an zwei Teilen gewaehlt
    masm = types.SimpleNamespace(Name="Assembly")
    parts = {"Link": types.SimpleNamespace(Label="Welle<1>"), "Link001": types.SimpleNamespace(Label="Platte<1>")}

    def comp_ref(_asm, _root, sub):
        first = sub.split(".")[1] if sub.startswith("Assembly.") else None
        return (parts[first], "x") if first in parts else (None, "")

    shapes = {"Assembly.Link.Body.Face1": face(Cylinder), "Assembly.Link001.Body.Face3": face(Cylinder),
              "Assembly.Link.Body.Face2": face(Plane)}
    root = types.SimpleNamespace(Name="Baugruppe", getSubObject=lambda sub: shapes.get(sub))
    fake_ua = types.SimpleNamespace(activeAssembly=lambda: masm, getComponentReference=comp_ref)
    sys.modules["UtilsAssembly"] = fake_ua
    lay._find_dock = lambda _mw, _keys: tasks
    ran_mates = []
    real_run = gui.runCommand
    try:
        gui.ActiveDocument = types.SimpleNamespace(getInEdit=lambda: None)
        gui._sel = [types.SimpleNamespace(Object=root, SubElementNames=(
            "Assembly.Link.Body.Face1", "Assembly.Link001.Body.Face3", "Fremd.Face9"))]
        host.layout.return_value.insertWidget.reset_mock()
        mt.refresh()
        mins = host.layout.return_value.insertWidget
        first = mt._panel.offered if mt._panel else None
        gui._sel = [types.SimpleNamespace(Object=root, SubElementNames=(
            "Assembly.Link.Body.Face1", "Assembly.Link.Body.Face2"))]
        mt.refresh()
        same = list(mt._panel.offered)
        same_hint = mt.hint_for(mt.current()[1], same)
        gui._mw.dialog_open = True
        dialog_cur = mt.current()
        gui._mw.dialog_open = False
        gui.runCommand = lambda c, *a: ran_mates.append(c)
        mt.run_mate("concentric")
    finally:
        gui.runCommand = real_run
        lay._find_dock = real_find
        del sys.modules["UtilsAssembly"]
        gui._sel = []
    if first != ["concentric", "coincident", "revolute", "parallel", "perpendicular", "distance"]:
        print("  FEHLER: Panel bietet für zwei Zylinder an zwei Teilen", first)
        return False
    if not mins.called or mins.call_args[0][0] != 0 or mins.call_args[0][1] is not mt._panel.widget:
        print("  FEHLER: Verknüpfungs-Panel nicht oben ins Aufgaben-Panel eingehängt")
        return False
    if same or "selben Bauteil" not in same_hint:
        print("  FEHLER: zwei Elemente am selben Teil", same, same_hint)
        return False
    if dialog_cur != (None, []) or ran_mates != ["Assembly_CreateJointCylindrical"]:
        print("  FEHLER: Dialog offen / Knopf startet falschen Befehl", dialog_cur, ran_mates)
        return False
    print("  Verknüpf.: %d Auswahl-Fälle; Panel nur bei aktiver Baugruppe ohne Dialog; gleiches Teil abgelehnt" % len(mcases))

    # --- Freie Drehung (8g) ---------------------------------------------
    fr = sys.modules.get("swui.commands.free_rotate")
    if fr is None or "SWUI_FreeRotate" not in commands:
        print("  FEHLER: Befehl SWUI_FreeRotate nicht angemeldet")
        return False
    fc_ = sys.modules["FreeCAD"]

    class V:
        def __init__(self, x=0.0, y=0.0, z=0.0):
            self.x, self.y, self.z = x, y, z

        def __add__(self, o):
            return V(self.x + o.x, self.y + o.y, self.z + o.z)

        def __sub__(self, o):
            return V(self.x - o.x, self.y - o.y, self.z - o.z)

    class Rot:  # Drehung um z (Winkel in Grad) - reicht fuer den Test
        def __init__(self, angle=0.0):
            self.angle = angle

        def multVec(self, v):
            a = math.radians(self.angle)
            return V(v.x * math.cos(a) - v.y * math.sin(a), v.x * math.sin(a) + v.y * math.cos(a), v.z)

        def multiply(self, o):
            return Rot(self.angle + o.angle)

    class Pl:
        def __init__(self, base=None, rot=None):
            self.Base, self.Rotation = base or V(), rot or Rot()

    rdoc = types.SimpleNamespace(Objects=[], opened=0, committed=0, recomputed=0)
    rdoc.openTransaction = lambda _n: setattr(rdoc, "opened", rdoc.opened + 1)
    rdoc.commitTransaction = lambda: setattr(rdoc, "committed", rdoc.committed + 1)
    rdoc.recompute = lambda: setattr(rdoc, "recomputed", rdoc.recomputed + 1)
    ca = types.SimpleNamespace(TypeId="App::Link", Name="Link", Label="Welle<1>", Document=rdoc, Placement=Pl(V(10, 0, 0)))
    cb = types.SimpleNamespace(TypeId="App::Link", Name="Link001", Label="Platte<1>", Document=rdoc, Placement=Pl())
    rasm = types.SimpleNamespace(Name="Assembly", Group=[ca, cb], Document=rdoc)
    rdoc.Objects = [rasm, ca, cb]

    def cref(_asm, _root, sub):
        part = {"Link": ca, "Link001": cb}.get(sub.split(".")[1] if "." in sub else "")
        return (part, "x") if part else (None, "")

    sys.modules["UtilsAssembly"] = types.SimpleNamespace(activeAssembly=lambda: rasm, getComponentReference=cref)
    root = types.SimpleNamespace(Name="Assembly")
    try:
        one = fr.selected_component(rasm, [types.SimpleNamespace(Object=root, SubElementNames=("Assembly.Link.Body.Face1", "Assembly.Link.Body.Edge3"))])
        tree = fr.selected_component(rasm, [types.SimpleNamespace(Object=cb, SubElementNames=())])
        two = fr.selected_component(rasm, [types.SimpleNamespace(Object=root, SubElementNames=("Assembly.Link.Body.Face1", "Assembly.Link001.Body.Face2"))])
        free = fr.blocking_reason(rasm, ca)
        jnt = types.SimpleNamespace(Name="Joint", Label="Konzentrisch1", JointType="Cylindrical",
                                    Reference1=(root, ["Assembly.Link001.Body.Face2", "Assembly.Link001.Body.Face2"]),
                                    Reference2=(root, ["Assembly.Link002.Body.Face1"]))
        gnd = types.SimpleNamespace(Name="GroundedJoint", Label="GroundedJoint", ObjectToGround=ca)
        rdoc.Objects += [jnt]
        joined = fr.blocking_reason(rasm, cb)
        still_free = fr.blocking_reason(rasm, ca)
        rdoc.Objects += [gnd]
        grounded_ = fr.blocking_reason(rasm, ca)
        # Sprache: Gruende und Verknuepfungs-Hinweise auf Englisch
        fcp_r = sys.modules["FreeCAD"].ParamGet("User parameter:BaseApp/Preferences/Mod/SWUI")
        fcp_r.SetString("Language", "en")
        try:
            grounded_en = fr.blocking_reason(rasm, ca)
            none_en = fr.blocking_reason(rasm, None)
            mt_en = sys.modules["swui.assembly_mates"]
            hint_en = mt_en.hint_for([mt_en.Element("plane", "Welle")], [])
            label_en = mt_en.Element("cylinder", "Welle").label
        finally:
            fcp_r.RemString("Language")
        if (not grounded_en.endswith("is fixed – free rotation only for floating parts.")
                or none_en != "Please select exactly one part of the active assembly."
                or hint_en != "Select a second entity on another component."
                or label_en != "Cylindrical face – Welle"):
            print("  FEHLER: Freie Drehung/Verknüpfungen auf Englisch", grounded_en, none_en, hint_en, label_en)
            return False
        rdoc.Objects.remove(jnt)
        rdoc.Objects.remove(gnd)
        # Knopf grau/aktiv je nach Auswahl
        gui._sel = [types.SimpleNamespace(Object=root, SubElementNames=("Assembly.Link.Body.Face1",))]
        act_free = commands["SWUI_FreeRotate"].IsActive()
        rdoc.Objects.append(gnd)
        act_gnd = commands["SWUI_FreeRotate"].IsActive()
        rdoc.Objects.remove(gnd)
    finally:
        del sys.modules["UtilsAssembly"]
        gui._sel = []
    if one is not ca or tree is not cb or two is not None:
        print("  FEHLER: gewähltes Teil falsch erkannt", one, tree, two)
        return False
    if free is not None or still_free is not None or "Konzentrisch1" not in (joined or "") or "fixiert" not in (grounded_ or ""):
        print("  FEHLER: Sperre (Verknüpfung/Fixierung)", free, joined, still_free, grounded_)
        return False
    if not act_free or act_gnd:
        print("  FEHLER: Knopf nicht grau bei fixiertem Teil / grau bei freiem", act_free, act_gnd)
        return False
    ax, ang = fr.drag_rotation(10, 0)
    ay, _ = fr.drag_rotation(0, -4)
    if ax != (0.0, 1.0, 0.0) or abs(ang - 10 * fr.DEG_PER_PIXEL) > 1e-9 or ay != (1.0, 0.0, 0.0) or fr.drag_rotation(0, 0)[0] is not None:
        print("  FEHLER: Mausweg -> Drehachse", ax, ang, ay)
        return False

    # Werkzeug: Ereignisse aus der 3D-Ansicht
    class Btn:
        BUTTON1, BUTTON2 = 1, 2

        @staticmethod
        def getClassTypeId():
            return "btn"

    coin_ = mock.MagicMock(name="coin")  # Szenengraph-Knoten (Drehkreuz) als Attrappe
    coin_.SoMouseButtonEvent = Btn
    coin_.SoButtonEvent = types.SimpleNamespace(DOWN=1, UP=0)
    coin_.SoLocation2Event = types.SimpleNamespace(getClassTypeId=lambda: "move")
    coin_.SoKeyboardEvent = types.SimpleNamespace(getClassTypeId=lambda: "key", ESCAPE=27,
                                                  isKeyPressEvent=lambda ev, k: getattr(ev, "key", None) == k)
    sg = mock.MagicMock(name="SceneGraph")
    cbs = {}
    rview = types.SimpleNamespace(
        addEventCallbackPivy=lambda t, f: cbs.__setitem__(t, f),
        removeEventCallbackPivy=lambda t, f: cbs.pop(t, None),
        getCameraOrientation=lambda: types.SimpleNamespace(multVec=lambda v: v),
        getSceneGraph=lambda: sg)
    rasm.ViewObject = types.SimpleNamespace(EnableMovement=True)

    class Node:
        def __init__(self, ev):
            self.ev, self.handled = ev, False

        def getEvent(self):
            return self.ev

        def setHandled(self):
            self.handled = True

    def mouse(button, state, x=0, y=0):
        pos = types.SimpleNamespace(getValue=lambda: (x, y))
        return Node(types.SimpleNamespace(getButton=lambda: button, getState=lambda: state, getPosition=lambda: pos))

    def move(x, y):
        pos = types.SimpleNamespace(getValue=lambda: (x, y))
        return Node(types.SimpleNamespace(getPosition=lambda: pos))

    old_pivy_coin = getattr(sys.modules["pivy"], "coin", None)
    sys.modules["pivy"].coin = coin_
    old_pl, old_rot, old_vec = fc_.Placement, getattr(fc_, "Rotation", None), fc_.Vector
    fc_.Placement, fc_.Vector = Pl, V
    fc_.Rotation = lambda axis, angle: Rot(angle if axis.y >= 0 else -angle)
    gui.ActiveDocument = types.SimpleNamespace(ActiveView=rview, getInEdit=lambda: None)
    try:
        sys.modules["UtilsAssembly"] = types.SimpleNamespace(activeAssembly=lambda: rasm)
        fr.start(ca)
        del sys.modules["UtilsAssembly"]
        running = fr.is_running() and set(cbs) == {"btn", "move", "key"}
        blocked = rasm.ViewObject.EnableMovement is False
        marker_added = sg.addChild.called
        idle = move(5, 5)
        cbs["move"](idle)  # ohne Ziehen: FreeCAD darf vorwählen
        down = mouse(1, 1, 0, 0)
        cbs["btn"](down)
        cbs["move"](move(30, 0))  # 30 px nach rechts -> 15 Grad
        up = mouse(1, 0, 30, 0)
        cbs["btn"](up)
        after = (round(ca.Placement.Rotation.angle, 6), round(ca.Placement.Base.x, 6), round(ca.Placement.Base.y, 6))
        trans = (rdoc.opened, rdoc.committed)
        fr.stop()
        stopped = not fr.is_running() and not cbs
        restored = rasm.ViewObject.EnableMovement is True and sg.removeChild.called
        orbit = fr.rotated_placement(Pl(V(10, 0, 0)), V(0, 0, 0), Rot(90))
        orbit = (round(orbit.Base.x, 6), round(orbit.Base.y, 6), orbit.Rotation.angle)
    finally:
        fc_.Placement, fc_.Vector = old_pl, old_vec
        if old_rot is None:
            del fc_.Rotation
        else:
            fc_.Rotation = old_rot
        sys.modules["pivy"].coin = old_pivy_coin
        gui.ActiveDocument = None
    if not (blocked and marker_added and restored):
        print("  FEHLER: FreeCADs Verschieben nicht gesperrt / Drehkreuz fehlt / nicht zurückgesetzt",
              blocked, marker_added, restored)
        return False
    if not running or idle.handled or not (down.handled and up.handled):
        print("  FEHLER: Werkzeug hängt sich nicht (richtig) an die 3D-Ansicht", running, idle.handled, down.handled)
        return False
    # Drehpunkt = Ursprung des Teils (Placement-Basis 10,0,0): Lage bleibt, Winkel 15 Grad
    if after != (15.0, 10.0, 0.0) or trans != (1, 1) or not stopped or orbit != (0.0, 10.0, 90):
        print("  FEHLER: Drehung/Rückgängig-Schritt/Beenden", after, trans, stopped)
        return False
    print("  Drehung : nur lose Teile (Verknüpfung/Fixierung -> grau); Ziehen dreht um den Teil-Ursprung mit Drehkreuz, FreeCAD-Verschieben gesperrt")

    # --- Zeichnung erstellen (9a) ----------------------------------------
    nd = sys.modules.get("swui.commands.new_drawing")
    if nd is None or "SWUI_NewDrawing" not in commands:
        print("  FEHLER: Befehl SWUI_NewDrawing nicht angemeldet")
        return False

    def solid(x, y, z):
        return types.SimpleNamespace(Shape=types.SimpleNamespace(BoundBox=types.SimpleNamespace(XLength=x, YLength=y, ZLength=z)))

    if nd.suggest_format([solid(40, 30, 20)]) != "A4 hoch" or nd.suggest_format([solid(40, 220, 20)]) != "A3 quer":
        print("  FEHLER: Vorschlag Blattformat nach Teilgröße")
        return False
    vorschlag = nd.suggested_path(types.SimpleNamespace(FileName="/h/a/Welle.FCStd", Label="Welle"))
    if os.path.normpath(vorschlag) != os.path.normpath("/h/a/Welle_Zeichnung.FCStd"):
        print("  FEHLER: Vorschlag Speicherort der Zeichnung")
        return False
    fcz = sys.modules["FreeCAD"]
    old_res = getattr(fcz, "getResourceDir", None)
    fcz.getResourceDir = lambda: os.path.join(ADDON, "nicht_da")  # Vorlage fehlt -> Rueckfall
    old_own = nd.own_templates_dir
    own = nd.template_path("A3 quer")  # eigene deutsche Vorlage zuerst
    nd.own_templates_dir = lambda: os.path.join(ADDON, "nicht_da")
    fallback = nd.template_path("A3 quer")
    nd.own_templates_dir = old_own
    if os.path.basename(own) != "A3_quer_ISO7200_DE.svg" or not os.path.isfile(own):
        print("  FEHLER: eigene deutsche Vorlage wird nicht bevorzugt", own)
        return False
    # Englische Oberflaeche: englische Vorlage (Feld Unit), sonst deutsche als Rueckfall
    i18_t = sys.modules["swui.i18n"]
    par_t = fcz.ParamGet(i18_t.PARAMS)
    par_t.SetString(i18_t.KEY, "en")
    try:
        own_en = nd.template_path("A3 quer")
        own_en4 = nd.template_path("A4 hoch")
    finally:
        par_t.RemString(i18_t.KEY)
    if (os.path.basename(own_en), os.path.basename(own_en4)) != ("A3_Landscape_ISO7200_EN.svg", "A4_Portrait_ISO7200_EN.svg"):
        print("  FEHLER: englische Vorlage bei englischer Oberfläche", own_en, own_en4)
        return False

    class TDObj:
        def __init__(self, type_id, name):
            self.TypeId, self.Name, self.Label = type_id, name, name
            self.views, self.projections = [], []

        def addView(self, v):
            self.views.append(v)

        def addProjection(self, d):
            self.projections.append(d)

    class TDDoc:
        def __init__(self, name):
            self.Name, self.Label, self.Objects, self.FileName = name, name, [], ""
            self.saved_as, self.saves, self.xsource_saved = None, 0, None

        def addObject(self, t, n):
            o = TDObj(t, n)
            if t == "TechDraw::DrawProjGroup":
                doc_ref = self

                class G(TDObj):
                    @property
                    def XSource(self):
                        return self._xs

                    @XSource.setter
                    def XSource(self, v):
                        doc_ref.xsource_saved = bool(doc_ref.FileName)  # schon gespeichert?
                        self._xs = v
                o = G(t, n)
            self.Objects.append(o)
            return o

        def saveAs(self, p):
            self.saved_as, self.FileName = p, p

        def save(self):
            self.saves += 1

        def recompute(self):
            pass

    made_docs = []
    body = types.SimpleNamespace(Label="Körper")
    src_doc = types.SimpleNamespace(Name="Welle", Label="Welle", FileName="/h/a/Welle.FCStd", Objects=[body])
    qtw = sys.modules["PySide.QtWidgets"] if "PySide.QtWidgets" in sys.modules else sys.modules["PySide"].QtWidgets
    real_src, real_new = nd.source_objects, getattr(fcz, "newDocument", None)
    old_active = getattr(fcz, "ActiveDocument", None)
    sys.modules["TechDraw"] = types.ModuleType("TechDraw")
    try:
        nd.source_objects = lambda d: [body] if d is src_doc else []
        fcz.newDocument = lambda n: (made_docs.append(TDDoc(n)), made_docs[-1])[1]
        fcz.ActiveDocument = src_doc
        qtw.QInputDialog.getItem.return_value = ("A3 quer", True)
        qtw.QFileDialog.getSaveFileName.return_value = ("/h/a/Welle Zeichnung", "")
        result = nd.create()
        qtw.QInputDialog.getItem.return_value = ("", False)  # Abbruch beim Format
        cancelled = nd.create()
    finally:
        nd.source_objects = real_src
        if real_new is None:
            del fcz.newDocument
        else:
            fcz.newDocument = real_new
        fcz.ActiveDocument = old_active
        if old_res is None:
            del fcz.getResourceDir
        else:
            fcz.getResourceDir = old_res
        del sys.modules["TechDraw"]
    if not fallback.endswith("Default_Template_A4_Landscape.svg"):
        print("  FEHLER: kein Rückfall auf FreeCADs Standardvorlage", fallback)
        return False
    if result is None or len(made_docs) != 1 or cancelled is not None:
        print("  FEHLER: Zeichnung nicht (genau einmal) erstellt", result, made_docs, cancelled)
        return False
    zdoc = made_docs[0]
    types_ = [o.TypeId for o in zdoc.Objects]
    page = [o for o in zdoc.Objects if o.TypeId == "TechDraw::DrawPage"][0]
    group = [o for o in zdoc.Objects if o.TypeId == "TechDraw::DrawProjGroup"][0]
    if (zdoc.saved_as != "/h/a/Welle Zeichnung.FCStd" or zdoc.Label != "Welle Zeichnung" or zdoc.Name != "Welle_Zeichnung"
            or types_ != ["TechDraw::DrawSVGTemplate", "TechDraw::DrawPage", "TechDraw::DrawProjGroup"]):
        print("  FEHLER: Zeichnungsdatei/Objekte", zdoc.saved_as, zdoc.Label, zdoc.Name, types_)
        return False
    if (group.XSource != [body] or not zdoc.xsource_saved or group.ProjectionType != "First angle"
            or group.projections != ["Front", "Top", "Left"] or page.views != [group] or page.Label != "Blatt1"):
        print("  FEHLER: Dreiansicht (Quelle, vorher gespeichert, Methode 1, Ansichten)",
              group.XSource, zdoc.xsource_saved, group.ProjectionType, group.projections)
        return False
    print("  Zeichnung: eigene Datei, vor dem Verknüpfen gespeichert, Methode 1 Vorne/Oben/Links, A4/A3-Vorlage")

    # --- Blatteigenschaften (9b) -----------------------------------------
    sp = sys.modules.get("swui.sheet_properties")
    if sp is None or "SWUI_SheetProperties" not in commands:
        print("  FEHLER: Befehl SWUI_SheetProperties nicht angemeldet")
        return False
    if (sp.display_name("/x/A3_Landscape_ISO5457_advanced.svg") != "A3 quer – Schriftfeld ISO 7200 (englisch, FreeCAD)"
            or sp.display_name("/x/A4_hoch_ISO7200_DE.svg") != "A4 hoch – Schriftfeld ISO 7200 (deutsch, mit Maßeinheit)"
            or sp.display_name("/x/A4_Portrait_blank.svg") != "A4 hoch – leer"
            or sp.display_name("/x/Firma.svg") != "Firma"):
        print("  FEHLER: Anzeigenamen der Vorlagen", sp.display_name("/x/A3_Landscape_ISO5457_advanced.svg"))
        return False
    tmpdir = os.path.join(SCRATCH_TMP, "iso_tpl")
    os.makedirs(tmpdir, exist_ok=True)
    for n in ("A0_Landscape_blank.svg", "A3_Landscape_ISO5457_advanced.svg", "A4_Portrait_ISO5457_advanced.svg"):
        open(os.path.join(tmpdir, n), "w").close()
    cat = [os.path.basename(p_) for _n, p_ in sp.template_catalog(tmpdir)]
    if cat[:2] != ["A4_Portrait_ISO5457_advanced.svg", "A3_Landscape_ISO5457_advanced.svg"] or len(cat) != 3:
        print("  FEHLER: Vorlagenliste (A4 hoch, A3 quer zuerst)", cat)
        return False
    # Eigene Vorlagen: deutsch, Feld "unit" (Maßeinheit) mit Vorgabe mm, gueltiges XML
    import xml.dom.minidom as _md
    for n_ in ("A4_hoch_ISO7200_DE.svg", "A3_quer_ISO7200_DE.svg"):
        f_ = os.path.join(sp.own_templates_dir(), n_)
        if not os.path.isfile(f_):
            print("  FEHLER: eigene Vorlage fehlt", f_)
            return False
        txt_ = open(f_, encoding="utf-8").read()
        _md.parseString(txt_.encode("utf-8"))
        if ('freecad:editable="unit"' not in txt_ or "<tspan>mm</tspan>" not in txt_
                or "Maßeinheit:" not in txt_ or "Werkstoff:" not in txt_ or "Part Material" in txt_):
            print("  FEHLER: Vorlage ohne Maßeinheit bzw. nicht deutsch", n_)
            return False
    for n_ in ("A4_Portrait_ISO7200_EN.svg", "A3_Landscape_ISO7200_EN.svg"):
        f_ = os.path.join(sp.own_templates_dir(), n_)
        if not os.path.isfile(f_):
            print("  FEHLER: englische Vorlage fehlt", f_)
            return False
        txt_ = open(f_, encoding="utf-8").read()
        _md.parseString(txt_.encode("utf-8"))
        if ('freecad:editable="unit"' not in txt_ or "<tspan>mm</tspan>" not in txt_ or "Unit:" not in txt_
                or "Material:" not in txt_ or "<tspan>EN</tspan>" not in txt_ or "Werkstoff" in txt_ or "Maßeinheit" in txt_):
            print("  FEHLER: englische Vorlage ohne Unit bzw. nicht englisch", n_)
            return False
    if sp.display_name("/x/A4_Portrait_ISO7200_EN.svg") != "A4 hoch – Schriftfeld ISO 7200 (englisch, mit Maßeinheit)":
        print("  FEHLER: Anzeigename englische Vorlage", sp.display_name("/x/A4_Portrait_ISO7200_EN.svg"))
        return False
    fc_ = sys.modules["FreeCAD"]
    had_ = hasattr(fc_, "getResourceDir")
    old_ = getattr(fc_, "getResourceDir", None)
    fc_.getResourceDir = lambda: tmpdir  # FreeCADs Vorlagen: hier nicht vorhanden
    try:
        full = [os.path.basename(p_) for _n, p_ in sp.template_catalog()]
    finally:
        if had_:
            fc_.getResourceDir = old_
        else:
            del fc_.getResourceDir
    if full[:2] != ["A4_hoch_ISO7200_DE.svg", "A3_quer_ISO7200_DE.svg"]:
        print("  FEHLER: deutsche Vorlagen nicht zuerst in der Liste", full[:3])
        return False
    if sp.field_label("unit") != "Maßeinheit" or sp.ordered_fields(["unit", "scale", "part_material"]) != ["part_material", "scale", "unit"]:
        print("  FEHLER: Feld Maßeinheit im Panel")
        return False
    if sp.fill_empty({"unit": ""}, {"unit": "mm"}) != {"unit": "mm"}:
        print("  FEHLER: Maßeinheit nicht vorbelegt")
        return False
    if sp.ordered_fields(["scale", "zzz", "title", "creator"]) != ["title", "scale", "creator", "zzz"]:
        print("  FEHLER: Reihenfolge der Schriftfeld-Felder")
        return False
    if (sp.scale_text(0.5), sp.scale_text(2), sp.scale_text(1), sp.scale_text(0.4)) != ("1:2", "2:1", "1:1", "1:2.5"):
        print("  FEHLER: Maßstab als Text", sp.scale_text(0.5), sp.scale_text(0.4))
        return False

    class Tpl:
        def __init__(self):
            self._t, self.Width, self.Height = "/t/A4_Portrait_ISO5457_advanced.svg", 210.0, 297.0
            self.EditableTexts = {"title": "", "scale": "", "creator": "", "general_tolerances": ""}

        @property
        def Template(self):
            return self._t

        @Template.setter
        def Template(self, v):  # wie FreeCAD: neue Felder, Eingaben weg, neues Format
            self._t, self.Width, self.Height = v, 420.0, 297.0
            self.EditableTexts = {"title": "", "scale": "", "drawing_number": ""}

    welle_doc = types.SimpleNamespace(Label="Welle")
    welle_body = types.SimpleNamespace(Document=welle_doc, Label="Körper", ShapeMaterial=types.SimpleNamespace(Name="S235JR"))
    view = types.SimpleNamespace(X=105.0, Y=150.0, Scale=0.5, XSource=[welle_body])
    zdoc2 = types.SimpleNamespace(Label="Welle_Zeichnung", recomputed=0)
    zdoc2.recompute = lambda: setattr(zdoc2, "recomputed", zdoc2.recomputed + 1)
    pg = types.SimpleNamespace(TypeId="TechDraw::DrawPage", Template=Tpl(), Views=[view], Document=zdoc2, InList=[])
    zdoc2.Objects = [pg, view]
    auto = sp.auto_values(pg, today=__import__("datetime").date(2026, 10, 17))
    if (auto.get("title"), auto.get("part_material"), auto.get("scale"), auto.get("drawing_number"), auto.get("date_of_issue")) != (
            "Welle", "S235JR", "1:2", "Welle_Zeichnung", "17.10.2026") or auto.get("unit") != "mm":
        print("  FEHLER: Schriftfeld-Vorbelegung aus dem Teil", auto)
        return False
    filled = sp.fill_empty({"title": "Eigene Benennung", "scale": ""}, auto)
    if filled != {"title": "Eigene Benennung", "scale": "1:2"}:
        print("  FEHLER: Vorbelegung überschreibt Eingaben", filled)
        return False
    sp.apply_sheet(pg, pg.Template.Template, {"title": "Welle", "scale": "1:2", "creator": "Dominik", "general_tolerances": "ISO 2768-m"})
    same = dict(pg.Template.EditableTexts)
    sp.apply_sheet(pg, "/t/A3_Landscape_ISO5457_advanced.svg", {"title": "Welle", "scale": "1:2", "creator": "Dominik"})
    switched = dict(pg.Template.EditableTexts)
    if same.get("general_tolerances") != "ISO 2768-m" or switched != {"title": "Welle", "scale": "1:2", "drawing_number": ""}:
        print("  FEHLER: Schriftfeld beim Vorlagenwechsel nicht übernommen", same, switched)
        return False
    if (round(view.X, 3), round(view.Y, 3)) != (210.0, 150.0) or pg.Template.Template != "/t/A3_Landscape_ISO5457_advanced.svg":
        print("  FEHLER: Ansichten nicht aufs neue Blatt umgerechnet", view.X, view.Y)
        return False
    if sp.find_page(zdoc2, [view]) is not pg or sp.find_page(zdoc2) is not pg or sp.find_page(types.SimpleNamespace(Objects=[])) is not None:
        print("  FEHLER: Blatt wird nicht gefunden")
        return False
    print("  Blatt    : Vorlagen A4 hoch/A3 quer zuerst, Wechsel behält Schriftfeld + Ansichten, Vorbelegung aus Teil")

    # --- Projektionsmethode (Sprache, Schritt 4b2) ---
    import re
    import xml.dom.minidom as _md2
    own_dir = sp.own_templates_dir()
    for n_ in ("A4_hoch_ISO7200_DE", "A3_quer_ISO7200_DE", "A4_Portrait_ISO7200_EN", "A3_Landscape_ISO7200_EN"):
        f3 = os.path.join(own_dir, n_ + "_M3.svg")
        if not os.path.isfile(f3):
            print("  FEHLER: Vorlage für Methode 3 fehlt", f3)
            return False
        t3 = open(f3, encoding="utf-8").read()
        _md2.parseString(t3.encode("utf-8"))
        m_tr = re.search(r'id="third_angle_trapezoid" d="m ([\d.]+),', t3)
        m_ci = re.search(r'id="third_angle_outer circle" cx="([\d.]+)"', t3)
        # Methode 3: Kreise links (rechter Rand cx+5 vor der schmalen Seite wide-10), Kegelstumpf rechts
        if "first_angle" in t3 or not (m_tr and m_ci) or not float(m_ci.group(1)) + 5 < float(m_tr.group(1)) - 10:
            print("  FEHLER: Symbol Methode 3 falsch", n_)
            return False
    cat_own = [os.path.basename(p_) for _n, p_ in sp.template_catalog(own_dir)]
    if any("_M3" in c_ for c_ in cat_own) or len(cat_own) != 4:
        print("  FEHLER: Methode-3-Vorlagen erscheinen in der Vorlagenliste", cat_own)
        return False
    de_own = os.path.join(own_dir, "A4_hoch_ISO7200_DE.svg")

    class PGroup2:
        TypeId = "TechDraw::DrawProjGroup"

        def __init__(self):
            self.ProjectionType, self.X, self.Y = "First angle", 100.0, 150.0

    tpl_m = Tpl()
    tpl_m._t, tpl_m.Width, tpl_m.Height = de_own, 210.0, 297.0
    grp_m = PGroup2()
    pg_m = types.SimpleNamespace(TypeId="TechDraw::DrawPage", Template=tpl_m, Views=[grp_m], Document=zdoc2,
                                 InList=[], ProjectionType="First angle")
    sp.apply_sheet(pg_m, de_own, {"title": "Welle"}, sp.THIRD)
    to3 = (os.path.basename(tpl_m.Template), grp_m.ProjectionType, pg_m.ProjectionType, sp.page_method(pg_m))
    sp.apply_sheet(pg_m, sp.base_template(tpl_m.Template), {"title": "Welle"}, sp.FIRST)
    to1 = (os.path.basename(tpl_m.Template), grp_m.ProjectionType, pg_m.ProjectionType, sp.page_method(pg_m))
    foreign = sp.template_for_method("/t/A3_Landscape_ISO5457_advanced.svg", sp.THIRD)
    if (to3 != ("A4_hoch_ISO7200_DE_M3.svg", "Third angle", "Third angle", "Third angle")
            or to1 != ("A4_hoch_ISO7200_DE.svg", "First angle", "First angle", "First angle")
            or foreign != "/t/A3_Landscape_ISO5457_advanced.svg"):
        print("  FEHLER: Projektionsmethode umstellen (Vorlage/Ansichten)", to3, to1, foreign)
        return False
    # Englische Oberflaeche: Vorgabe Methode 3, neue Zeichnung mit Draufsicht oben + Seitenansicht rechts
    i18_m = sys.modules["swui.i18n"]
    par_m = sys.modules["FreeCAD"].ParamGet(i18_m.PARAMS)
    par_m.SetString(i18_m.KEY, "en")
    had_td = "TechDraw" in sys.modules
    sys.modules.setdefault("TechDraw", types.ModuleType("TechDraw"))
    try:
        dflt_en = sp.default_projection()
        auto_en = sp.auto_values(pg, today=__import__("datetime").date(2026, 10, 17))
        mdoc = TDDoc("M")
        page_en, grp_en = nd.build(mdoc, [welle_body], "A4 hoch")
        tpl_en = [o for o in mdoc.Objects if o.TypeId == "TechDraw::DrawSVGTemplate"][0].Template
    finally:
        par_m.RemString(i18_m.KEY)
        if not had_td:
            del sys.modules["TechDraw"]
    dflt_de = sp.default_projection()
    if dflt_en != "Third angle" or dflt_de != "First angle":
        print("  FEHLER: Vorgabe der Projektionsmethode nach Sprache", dflt_en, dflt_de)
        return False
    if (grp_en.ProjectionType, page_en.ProjectionType, grp_en.projections, os.path.basename(tpl_en)) != (
            "Third angle", "Third angle", ["Front", "Top", "Right"], "A4_Portrait_ISO7200_EN_M3.svg"):
        print("  FEHLER: neue englische Zeichnung (Methode 3)", grp_en.ProjectionType, grp_en.projections, tpl_en)
        return False
    if (auto_en.get("language_code"), auto_en.get("date_of_issue")) != ("EN", "2026-10-17"):
        print("  FEHLER: englisches Schriftfeld (Sprache EN, Datum ISO)", auto_en.get("language_code"), auto_en.get("date_of_issue"))
        return False
    print("  Methode  : wählbar in Blatteigenschaften, Vorlage mit passendem Symbol, Englisch = Methode 3 (Vorne/Oben/Rechts)")

    # --- Bild einfuegen ---------------------------------------------------
    ii = sys.modules.get("swui.insert_image")
    if ii is None or "SWUI_InsertImage" not in commands:
        print("  FEHLER: Befehl SWUI_InsertImage nicht angemeldet")
        return False
    mm_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="50mm" height="20mm" viewBox="0 0 50 20"><rect/></svg>'
    px_svg = '<svg width="300" height="150"><rect/></svg>'
    vb_svg = '<svg viewBox="0 0 400 100"></svg>'
    sizes = (ii.svg_natural_size(mm_svg, 10.0), ii.svg_natural_size(px_svg, 10.0), ii.svg_natural_size(vb_svg, 10.0),
             ii.svg_natural_size("kein svg", 10.0), ii.bitmap_natural_size(800, 600, 10.0))
    if sizes != ((50.0, 20.0), (30.0, 15.0), (40.0, 10.0), None, (80.0, 60.0)):
        print("  FEHLER: natürliche Bildgröße", sizes)
        return False
    if (ii.initial_scale((200.0, 100.0), 420.0), ii.initial_scale((50.0, 20.0), 420.0), ii.width_to_scale(25.0, (50.0, 20.0))) != (0.63, 1.0, 0.5):
        print("  FEHLER: Startgröße / Breite -> Maßstab",
              ii.initial_scale((200.0, 100.0), 420.0), ii.width_to_scale(25.0, (50.0, 20.0)))
        return False
    svg_path = os.path.join(SCRATCH_TMP, "logo.svg")
    open(svg_path, "w", encoding="utf-8").write(mm_svg)

    class ImgDoc:
        def __init__(self):
            self.Objects = []

        def addObject(self, t, n):
            o = types.SimpleNamespace(TypeId=t, Name=n, Label=n, X=0.0, Y=0.0, Scale=1.0, Rotation=0.0, Document=self)
            self.Objects.append(o)
            return o

    idoc = ImgDoc()
    ipage = types.SimpleNamespace(Document=idoc, Template=types.SimpleNamespace(Width=420.0, Height=297.0), views=[])
    ipage.addView = lambda v: ipage.views.append(v)
    real_px = ii.image_pixels
    sys.modules["TechDraw"] = types.ModuleType("TechDraw")
    try:
        sym = ii.add_image(ipage, svg_path)
        ii.image_pixels = lambda p_: (2000, 1000)
        bmp = ii.add_image(ipage, "/h/a/foto.JPG")
        try:
            ii.add_image(ipage, "/h/a/text.pdf")
            wrong_ok = True
        except ValueError:
            wrong_ok = False
    finally:
        ii.image_pixels = real_px
        del sys.modules["TechDraw"]
    if (sym.TypeId, sym.Scale, sym.X, sym.Y, sym.ScaleType) != ("TechDraw::DrawViewSymbol", 1.0, 210.0, 148.5, "Custom") or "<rect/>" not in sym.Symbol:
        print("  FEHLER: SVG nicht als Symbol in Blattmitte eingefügt", sym)
        return False
    if bmp.TypeId != "TechDraw::DrawViewImage" or bmp.ImageFile != "/h/a/foto.JPG" or abs(bmp.Scale - 0.63) > 1e-9 or wrong_ok:
        print("  FEHLER: PNG/JPG nicht als Bild eingefügt (oder falsches Format angenommen)", bmp.TypeId, bmp.Scale)
        return False
    if ipage.views != [sym, bmp]:
        print("  FEHLER: Bilder nicht aufs Blatt gelegt")
        return False
    ii.set_geometry(sym, x=30, y=40, width=100, rotation=90, natural=(50.0, 20.0))
    if (sym.X, sym.Y, sym.Scale, sym.Rotation) != (30.0, 40.0, 2.0, 90.0):
        print("  FEHLER: Position/Breite/Drehung nicht gesetzt", sym.X, sym.Y, sym.Scale, sym.Rotation)
        return False
    if ii.selected_image([types.SimpleNamespace(TypeId="TechDraw::DrawPage"), sym]) is not sym:
        print("  FEHLER: gewähltes Bild nicht erkannt")
        return False
    if ii.geometry_of(sym, (50.0, 20.0)) != (30.0, 40.0, 100.0, 90.0):
        print("  FEHLER: Geometrie des Bildes", ii.geometry_of(sym, (50.0, 20.0)))
        return False
    sym.X, sym.Y = 120.0, 80.0  # mit der Maus verschoben
    if ii.changed_fields([30.0, 40.0, 100.0, 90.0], ii.geometry_of(sym, (50.0, 20.0)), tol=0.05) != [0, 1]:
        print("  FEHLER: Mausverschiebung nicht erkannt")
        return False
    # Panel: Abgleich und OK schreiben die alten Feldwerte NICHT aufs Bild zurück
    class Spin:
        def __init__(self, v):
            self.v, self.blocked = v, False

        def value(self):
            return self.v

        def setValue(self, v):
            self.v = v

        def blockSignals(self, b):
            self.blocked = b

    commits = []
    sym.Document.commitTransaction = lambda: commits.append(1)
    pnl = ii._TaskPanel.__new__(ii._TaskPanel)
    pnl.obj, pnl.natural = sym, (50.0, 20.0)
    pnl.x, pnl.y, pnl.width, pnl.rot = Spin(30.0), Spin(40.0), Spin(100.0), Spin(90.0)
    pnl.height, pnl.timer = mock.MagicMock(), mock.MagicMock()
    real_close = gui.Control.closeDialog if hasattr(gui.Control, "closeDialog") else None
    gui.Control.closeDialog = lambda: None
    try:
        pnl.accept()
    finally:
        if real_close is None:
            del gui.Control.closeDialog
        else:
            gui.Control.closeDialog = real_close
    if (sym.X, sym.Y) != (120.0, 80.0) or (pnl.x.v, pnl.y.v) != (120.0, 80.0) or commits != [1]:
        print("  FEHLER: OK setzt das Bild auf die alte Position zurück", sym.X, sym.Y, pnl.x.v)
        return False
    print("  Bild     : SVG als Vektor, PNG/JPG eingebettet, Breite in mm -> Maßstab; Felder folgen der Maus, OK behält Position")

    # --- Benennung Schnitt/Detail nach Norm --------------------------------
    vl = sys.modules.get("swui.view_labels")
    if vl is None or vl._observer is None:
        print("  FEHLER: Benennung von Schnitt-/Detailansichten nicht eingeschaltet")
        return False

    class LDoc:
        Restoring = False
        Transacting = False

        def __init__(self):
            self.Objects = []

        def addObject(self, t, n):
            o = LObj(t, n, self)
            self.Objects.append(o)
            return o

    class LObj:
        def __init__(self, t, n, d, **kw):
            self.TypeId, self.Name, self.Label, self.Document = t, n, n, d
            self.X = self.Y = 0.0
            self.Scale, self.InList = 1.0, []
            self.__dict__.update(kw)

        def addProperty(self, _t, name, *_a):
            setattr(self, name, None)

    ld = LDoc()
    lpage = LObj("TechDraw::DrawPage", "Page", ld)
    lpage.views = []
    lpage.addView = lambda v: lpage.views.append(v)
    ld.Objects.append(lpage)

    def view(t, name, **kw):
        o = LObj(t, name, ld, InList=[lpage], **kw)
        ld.Objects.append(o)
        return o

    s1 = view("TechDraw::DrawViewSection", "Section", SectionSymbol="", X=100.0, Y=200.0)
    d1 = view("TechDraw::DrawViewDetail", "Detail", Reference="1", Radius=10.0, Scale=2.0, X=300.0, Y=150.0)
    s2 = view("TechDraw::DrawComplexSection", "Section001", SectionSymbol="-")
    d2 = view("TechDraw::DrawViewDetail", "Detail001", Reference="K", Radius=5.0, Scale=0.5)  # selbst eingetragen
    gui._mw.dialog_open = True
    waited = vl.process(s1)
    gui._mw.dialog_open = False
    for v_ in (s1, d1, s2, d2):
        vl.process(v_)
    if waited or (s1.SectionSymbol, s2.SectionSymbol, d1.Reference, d2.Reference) != ("A", "B", "Z", "K"):
        print("  FEHLER: Buchstaben nach Norm (A-A..., Z...)", waited, s1.SectionSymbol, s2.SectionSymbol, d1.Reference, d2.Reference)
        return False
    if (s1.Label, d1.Label) != ("Schnittansicht A-A", "Detailansicht Z (2:1)"):
        print("  FEHLER: Namen im Baum", s1.Label, d1.Label)
        return False
    la = vl.find_label(s1, ld.Objects)
    lz = vl.find_label(d1, ld.Objects)
    if la is None or lz is None or la.Text != ["A-A"] or lz.Text != ["Z (2:1)"] or la not in lpage.views or la.Owner is not s1:
        print("  FEHLER: Benennung als Textfeld fehlt", la and la.Text, lz and lz.Text)
        return False
    if (lz.X, lz.Y) != (300.0, 150.0 - (10.0 * 2.0 + vl.GAP)):
        print("  FEHLER: Benennung nicht unter der Detailansicht", lz.X, lz.Y)
        return False
    if vl.next_letter(s1, [s1, s2] + [view("TechDraw::DrawViewSection", "S%d" % k, SectionSymbol=c) for k, c in enumerate("CDEFGH")]) != "J":
        print("  FEHLER: I/O/Q werden nicht ausgelassen")
        return False
    # Benennung von Hand umschreiben -> Buchstabe wandert in die Ansicht
    lz.Text = ["Y (5:1)"]
    vl.on_label_text_changed(lz)
    # Ansicht verschoben -> Benennung wandert mit
    d1.X, d1.Y = 320.0, 160.0
    vl.on_view_changed(d1, "X")
    # Massstab der Ansicht geaendert -> Benennung folgt (Text entspricht noch dem Schema)
    d1.Scale = 4.0
    vl.on_view_changed(d1, "Scale")
    if d1.Reference != "Y" or d1.Label != "Detailansicht Y (4:1)" or (lz.X, lz.Y) != (320.0, 130.0) or lz.Text != ["Y (4:1)"]:
        print("  FEHLER: Umbenennen/Mitwandern/Nachführen", d1.Reference, lz.X, lz.Y, lz.Text)
        return False
    lz.Text = ["Einzelheit Y, gedreht"]  # freier Text bleibt stehen
    vl.on_label_text_changed(lz)
    d1.Scale = 2.0
    vl.on_view_changed(d1, "Scale")
    if lz.Text != ["Einzelheit Y, gedreht"] or d1.Reference != "Y":
        print("  FEHLER: freier Text wurde überschrieben", lz.Text)
        return False
    print("  Benenn.  : Schnitt A-A, B-B …, Detail Z, Y … mit Maßstab; Textfeld frei verschiebbar, wandert mit, umbenennbar")

    # --- Projizierte Ansichten ---------------------------------------------
    pv = sys.modules.get("swui.proj_views")
    if pv is None or "SWUI_ProjectedView" not in commands:
        print("  FEHLER: Projizierte Ansicht nicht angemeldet")
        return False

    class PItem:
        def __init__(self, t, x=0.0, y=0.0, grp=None):
            self.TypeId, self.Type, self.X, self.Y, self.Label = "TechDraw::DrawProjGroupItem", t, x, y, t
            self.InList = [grp] if grp else []

    class PGroup:
        TypeId = "TechDraw::DrawProjGroup"

        def __init__(self, method="First angle"):
            self.ProjectionType, self.AutoDistribute, self.Scale = method, True, 0.5
            self.X, self.Y = 150.0, 180.0
            self.XSource = [types.SimpleNamespace(Shape=types.SimpleNamespace(
                BoundBox=types.SimpleNamespace(XLength=200, YLength=80, ZLength=60)))]
            self.Views = [PItem("Front", grp=self)]
            self.Document = types.SimpleNamespace(opened=0, committed=0)
            self.Document.openTransaction = lambda _n: None
            self.Document.commitTransaction = lambda: None
            self.Document.recompute = lambda: None

        def addProjection(self, t):
            it = PItem(t, grp=self)
            self.Views.append(it)
            return it

    if (pv.direction_from(50, 3), pv.direction_from(-2, -40), pv.direction_from(30, 25), pv.direction_from(0, 0)) != ((1, 0), (0, -1), (1, 1), None):
        print("  FEHLER: Mausrichtung -> Richtung")
        return False
    g1 = PGroup()
    if (pv.target_type(g1, "Front", (1, 0)), pv.target_type(g1, "Front", (0, -1)), pv.target_type(g1, "Left", (1, 0)),
            pv.target_type(g1, "Top", (1, 0)), pv.target_type(g1, "Top", (0, -1))) != ("Left", "Top", "Rear", "FrontTopLeft", None):
        print("  FEHLER: Methode-1-Raster relativ zur angeklickten Ansicht")
        return False
    g1.addProjection("Top"); g1.addProjection("Left")
    pv.setup_group(g1)
    dx, dy = pv.default_steps(g1)
    top, left = pv.item_of_type(g1, "Top"), pv.item_of_type(g1, "Left")
    if g1.AutoDistribute is not False or (top.X, top.Y) != (0.0, -dy) or (left.X, left.Y) != (dx, 0.0) or abs(dx - (140 * 0.5 + pv.SPACING)) > 1e-9:
        print("  FEHLER: Startlage / sofort verschiebbar", g1.AutoDistribute, top.Y, left.X)
        return False
    # Klick rechts neben der Seitenansicht (von links) -> Rückansicht, Höhe wie Vorderansicht
    left.X = 120.0  # vorher verschoben
    page_click = (150.0 + 260.0, 180.0 + 7.0)
    rear, created = pv.create_at(left, page_click)
    # Klick unten links neben der Vorderansicht -> Isometrie (Methode 1: FrontTopRight)
    iso, c_iso = pv.create_at(g1.Views[0], (150.0 - 100.0, 180.0 - 90.0))
    # Klick unter der Draufsicht -> dort gibt es keine Projektion
    none_, c_none = pv.create_at(top, (150.0, 180.0 - dy - 100.0))
    # Klick über der Vorderansicht -> Untersicht, senkrecht über Vorne, Höhe = Klick
    bottom, c_b = pv.create_at(g1.Views[0], (152.0, 180.0 + 95.0))
    if (rear.Type, rear.X, rear.Y, created) != ("Rear", 260.0, 0.0, True):
        print("  FEHLER: Rückansicht neben Seitenansicht", rear.Type, rear.X, rear.Y)
        return False
    if (iso.Type, iso.X, iso.Y, iso.Label) != ("FrontTopRight", -100.0, -90.0, "Isometrie") or none_ is not None or c_none:
        print("  FEHLER: Isometrie/keine Projektion", iso.Type, iso.X, iso.Y, none_)
        return False
    if (bottom.Type, bottom.X, bottom.Y) != ("Bottom", 0.0, 95.0):
        print("  FEHLER: Untersicht nicht auf der Achse", bottom.Type, bottom.X, bottom.Y)
        return False
    g3 = PGroup("Third angle")
    if pv.target_type(g3, "Front", (1, 0)) != "Right" or pv.place_for(g3, "Right") != (pv.default_steps(g3)[0], 0.0):
        print("  FEHLER: Methode 3")
        return False
    # Bestehende Zeichnung: verteilte Gruppen werden verschiebbar, unverteilte nicht
    g5, g6 = PGroup(), PGroup()
    g5.Views.append(PItem("Top", 0.0, -80.0, g5))
    g6.Views.append(PItem("Top", 0.0, 0.0, g6))
    n = pv.freeze_doc(types.SimpleNamespace(Objects=[g5, g6]))
    if n != 1 or g5.AutoDistribute is not False or g6.AutoDistribute is not True:
        print("  FEHLER: bestehende Gruppen verschiebbar machen", n)
        return False
    if pv.scene_to_page(1500.0, -900.0, 10.0) != (150.0, 90.0):
        print("  FEHLER: Szene -> Blatt")
        return False
    print("  Projiz.  : Klick neben die Ansicht -> Projektion nach Methode 1 relativ zur Ansicht, auf der Achse; Gruppen verschiebbar")

    # --- Ansichten mit einem Linksklick ziehen ------------------------------
    pd = sys.modules.get("swui.page_drag")
    if pd is None:
        import importlib
        pd = importlib.import_module("swui.page_drag")
    g7 = PGroup()
    t7, l7, i7 = g7.addProjection("Top"), g7.addProjection("Left"), g7.addProjection("FrontTopLeft")
    f7 = g7.Views[0]
    flags = [pd.axis_flags(v) for v in (t7, l7, i7)]
    if flags != [(False, True), (True, False), (True, True)] or pd.drag_target(f7)[0] is not g7:
        print("  FEHLER: Achsbindung beim Ziehen", flags)
        return False
    pd.apply_delta(t7, 5.0, -7.0)
    pd.apply_delta(l7, 4.0, 9.0)
    pd.apply_delta(f7, 10.0, 2.0)
    if (t7.X, t7.Y, l7.X, l7.Y, g7.X, g7.Y) != (0.0, -7.0, 4.0, 0.0, 160.0, 182.0):
        print("  FEHLER: Verschieben mit Achsbindung", t7.X, t7.Y, l7.X, l7.Y, g7.X, g7.Y)
        return False
    if pd.movable_view(types.SimpleNamespace(TypeId="TechDraw::DrawViewDimension")) is not None:
        print("  FEHLER: Bemaßung wird als Ansicht gezogen")
        return False
    # Ereignisablauf: Druecken (TechDraw waehlt Kante) -> Ziehen -> Loslassen
    QE = sys.modules["PySide.QtCore"].QEvent.Type
    LB = sys.modules["PySide.QtCore"].Qt.MouseButton.LeftButton

    class Pt:
        def __init__(self, x, y):
            self._x, self._y = x, y

        def x(self):
            return self._x

        def y(self):
            return self._y

        def toPoint(self):
            return self

    class Ev:
        def __init__(self, kind, x, y):
            self.kind, self.p = kind, Pt(x, y)

        def type(self):
            return self.kind

        def button(self):
            return LB

        def position(self):
            return self.p

    trans = []
    t7.Document = types.SimpleNamespace(openTransaction=lambda n: trans.append("open"),
                                        commitTransaction=lambda: trans.append("commit"),
                                        recompute=lambda: trans.append("recompute"))
    gview = mock.MagicMock(name="QGraphicsView")
    gview.mapToScene.side_effect = lambda p_: p_
    gview.transform.return_value.m11.return_value = 1.0
    gview.scene.return_value.mouseGrabberItem.return_value = None  # Kante: TechDraw zieht nicht
    gview.viewport.return_value.cursor.return_value.shape.return_value = (
        sys.modules["swui.compat"].QtCore.Qt.CursorShape.ArrowCursor)  # kein TechDraw-Werkzeug aktiv
    gui._sel = [types.SimpleNamespace(Object=t7, SubElementNames=("Edge3",))]
    st = pd.DragState()
    y0 = t7.Y
    try:
        r_press = pd.handle_event(st, gview, Ev(QE.MouseButtonPress, 100.0, 100.0))
        r_small = pd.handle_event(st, gview, Ev(QE.MouseMove, 102.0, 101.0))
        r_move = pd.handle_event(st, gview, Ev(QE.MouseMove, 130.0, 150.0))  # 50 Einheiten nach unten
        r_rel = pd.handle_event(st, gview, Ev(QE.MouseButtonRelease, 130.0, 150.0))
    finally:
        gui._sel = []
    if r_press or r_small or not r_move or not r_rel or trans != ["open", "commit", "recompute"]:
        print("  FEHLER: Ziehen-Ablauf", r_press, r_small, r_move, r_rel, trans)
        return False
    if t7.X != 0.0 or abs(t7.Y - (y0 - 50.0 / 10.0)) > 1e-9:
        print("  FEHLER: Draufsicht beim Ziehen nicht senkrecht verschoben", t7.X, t7.Y)
        return False
    print("  Ziehen   : ein Linksklick genügt (auch auf Kanten), Achse bleibt, 1 Rückgängig-Schritt je Zug")

    # --- Maßstab der Ansicht --------------------------------------------------
    vs = sys.modules.get("swui.view_scale")
    if vs is None or "SWUI_ViewScale" not in commands:
        print("  FEHLER: Befehl SWUI_ViewScale nicht angemeldet")
        return False
    if (vs.parse_scale("1:5"), vs.parse_scale("2:1"), vs.parse_scale("0,5"), vs.parse_scale("1:0"), vs.parse_scale("abc")) != (0.2, 2.0, 0.5, None, None):
        print("  FEHLER: Maßstab lesen")
        return False
    g8 = PGroup()
    g8.AutoDistribute, g8.ScaleType = False, "Automatic"
    t8, l8 = g8.addProjection("Top"), g8.addProjection("Left")
    t8.Y, l8.X = -100.0, 120.0
    tpl8 = types.SimpleNamespace(EditableTexts={"scale": "1:2", "title": "Tisch"})
    page8 = types.SimpleNamespace(TypeId="TechDraw::DrawPage", Template=tpl8)
    g8.InList = [page8]
    if vs.scale_target(t8) is not g8 or vs.scale_target(types.SimpleNamespace(TypeId="TechDraw::DrawViewDimension", Scale=1)) is not None:
        print("  FEHLER: Maßstab-Ziel (Gruppe statt Einzelprojektion)")
        return False
    new = vs.apply_scale(g8, 0.25, "Custom")
    if (new, g8.ScaleType, t8.Y, l8.X, tpl8.EditableTexts["scale"]) != (0.25, "Custom", -50.0, 60.0, "1:4"):
        print("  FEHLER: Maßstab setzen / Abstände / Schriftfeld", new, g8.ScaleType, t8.Y, l8.X, tpl8.EditableTexts)
        return False
    tpl8.EditableTexts = {"scale": "M 1:4 (Hauptansicht)"}  # eigener Text bleibt
    vs.apply_scale(g8, 0.5, "Custom")
    det = types.SimpleNamespace(TypeId="TechDraw::DrawViewDetail", Scale=2.0, ScaleType="Custom", InList=[page8],
                                Document=types.SimpleNamespace(recompute=lambda: None), Label="Detail Z")
    vs.apply_scale(det, None, "Page")
    if tpl8.EditableTexts["scale"] != "M 1:4 (Hauptansicht)" or det.ScaleType != "Page" or vs.current_label(det) != "Blattmaßstab":
        print("  FEHLER: eigener Schriftfeldtext / Blattmaßstab", tpl8.EditableTexts, det.ScaleType)
        return False
    print("  Maßstab  : Normmaßstäbe/Blatt/automatisch/eigener; Gruppe gemeinsam, Abstände + Schriftfeld folgen")

    # --- Duennere Linien beim Hineinzoomen (nur Bildschirm) ---
    zl = sys.modules.get("swui.zoom_lines")
    if zl is None:
        print("  FEHLER: zoom_lines nicht geladen (InitGui.Initialize)")
        return False
    if (zl.step_for(4), zl.step_for(6), zl.step_for(13), zl.step_for(48), zl.step_for(1e9)) != (0, 0, 2, 3, zl.MAX_STEP):
        print("  FEHLER: Zoomstufen der Strichstärke", zl.step_for(13), zl.step_for(48))
        return False

    class ZVO:
        def __init__(self, **kw):
            self.__dict__.update(kw)
            self.PropertiesList = list(kw)

    class ZObj:
        def __init__(self, name, type_id, vo, views=()):
            self.Name, self.TypeId, self.ViewObject, self.Views = name, type_id, vo, list(views)
            self.Document = zdoc

    zdoc = types.SimpleNamespace(Name="ZDoc")
    front = ZObj("Front", "TechDraw::DrawProjGroupItem", ZVO(LineWidth=0.5, HiddenWidth=0.25, IsoWidth=0.25, ExtraWidth=0.25))
    grp = ZObj("Grp", "TechDraw::DrawProjGroup", ZVO(LineWidth=0.5, HiddenWidth=0.25, IsoWidth=0.25, ExtraWidth=0.25), [front])
    dim = ZObj("Dim", "TechDraw::DrawViewDimension", ZVO(LineWidth=0.35, Arrowsize=3.5))
    page_z = types.SimpleNamespace(Views=[grp, dim])
    objs_z = zl.page_objects(page_z)
    if [o.Name for o in objs_z] != ["Grp", "Dim", "Front"]:
        print("  FEHLER: Ansichten des Blatts (auch in Gruppen)", [o.Name for o in objs_z])
        return False
    zl._orig.clear()
    zl._step = 0
    zl.apply_step(objs_z, 2)
    zl._step = 2
    if (front.ViewObject.LineWidth, front.ViewObject.HiddenWidth, dim.ViewObject.LineWidth, dim.ViewObject.Arrowsize) != (0.125, 0.0625, 0.0875, 3.5):
        print("  FEHLER: Strichstärken beim Zoomen", front.ViewObject.LineWidth, dim.ViewObject.LineWidth)
        return False
    front.ViewObject.LineWidth = 0.175  # von Hand geaendert (0,7 mm bei Stufe 2)
    zl.apply_step(objs_z, 1)
    zl._step = 1
    if abs(front.ViewObject.LineWidth - 0.35) > 1e-9:
        print("  FEHLER: Handänderung beim Zoomen verloren", front.ViewObject.LineWidth)
        return False
    fcz2 = sys.modules["FreeCAD"]
    old_gd = getattr(fcz2, "getDocument", None)
    by_name = {o.Name: o for o in objs_z}
    fcz2.getDocument = lambda n: types.SimpleNamespace(getObject=lambda on: by_name[on])
    try:
        zl._SaveObserver().slotStartSaveDocument(zdoc, "/tmp/x.FCStd")
    finally:
        if old_gd is not None:
            fcz2.getDocument = old_gd
    if (front.ViewObject.LineWidth, front.ViewObject.HiddenWidth, grp.ViewObject.LineWidth, dim.ViewObject.LineWidth) != (0.7, 0.25, 0.5, 0.35) or zl._orig or zl._step:
        print("  FEHLER: Norm-Strichstärken vor dem Speichern nicht zurück", front.ViewObject.LineWidth, dim.ViewObject.LineWidth)
        return False
    print("  Zoom     : Linien/Punkte beim Hineinzoomen dünner (Stufen), Original vor Speichern/Dialog/Ausgabe")
    # Absturz beim Bemassen (17.10.): waehrend eines TechDraw-Werkzeugs nichts neu zeichnen / nicht ziehen
    pd_ = sys.modules["swui.page_drag"]
    qtc = sys.modules["swui.compat"].QtCore
    arrow_ = qtc.Qt.CursorShape.ArrowCursor
    tool_cursor = object()

    def gview_with(shape):
        return types.SimpleNamespace(viewport=lambda: types.SimpleNamespace(
            cursor=lambda: types.SimpleNamespace(shape=lambda: shape)),
            transform=lambda: types.SimpleNamespace(m11=lambda: 50.0),  # stark gezoomt
            mapToScene=lambda p_: p_, scene=lambda: None)

    g_idle, g_tool = gview_with(arrow_), gview_with(tool_cursor)
    if pd_.tool_active(g_idle) or not pd_.tool_active(g_tool):
        print("  FEHLER: aktives TechDraw-Werkzeug wird nicht erkannt")
        return False
    if not zl._busy(g_tool, types.SimpleNamespace(Document=types.SimpleNamespace(HasPendingTransaction=False))):
        print("  FEHLER: Strichstärken würden während des Bemaßens geändert (Absturz)")
        return False
    if not zl._busy(g_idle, types.SimpleNamespace(Document=types.SimpleNamespace(HasPendingTransaction=True))):
        print("  FEHLER: Strichstärken würden während einer offenen Transaktion geändert")
        return False
    old_tick_page = zl._active_page
    zl._active_page = lambda: (page_z, g_tool)
    old_wb = zl._active_workbench
    zl._active_workbench = lambda: True
    old_dlg = zl._dialog_open
    zl._dialog_open = lambda: False
    zl._orig.clear()
    zl._step = 0
    before_lw = front.ViewObject.LineWidth
    try:
        zl.tick()
        zl.tick()
    finally:
        zl._active_page, zl._active_workbench, zl._dialog_open = old_tick_page, old_wb, old_dlg
    if front.ViewObject.LineWidth != before_lw or zl._orig:
        print("  FEHLER: Zoom-Takt ändert Linien trotz aktivem Werkzeug")
        return False
    press = types.SimpleNamespace(type=lambda: qtc.QEvent.Type.MouseButtonPress,
                                  button=lambda: qtc.Qt.MouseButton.LeftButton,
                                  position=lambda: types.SimpleNamespace(
                                      toPoint=lambda: types.SimpleNamespace(x=lambda: 1.0, y=lambda: 2.0)))
    st_ = pd_.DragState()
    old_wb2 = pd_._is_active_workbench
    pd_._is_active_workbench = lambda: True
    guim = sys.modules["FreeCADGui"]
    old_ctl = getattr(guim, "Control", None)
    guim.Control = types.SimpleNamespace(activeDialog=lambda: False)
    st_idle = pd_.DragState()
    try:
        pd_.handle_event(st_, g_tool, press)
        pd_.handle_event(st_idle, g_idle, press)  # Gegenprobe: ohne Werkzeug wird der Klick gemerkt
    finally:
        pd_._is_active_workbench = old_wb2
        guim.Control = old_ctl
    if st_idle.press is None:
        print("  FEHLER: Prüfaufbau Ziehen (ohne Werkzeug kein Klick erkannt)")
        return False
    if st_.press is not None:
        print("  FEHLER: Ziehen greift während eines TechDraw-Werkzeugs ein")
        return False
    print("  Werkzeug : während Bemaßen & Co. kein Neuzeichnen und kein Ziehen (Absturz behoben)")

    # --- Oberflaechenangabe (9e2c): editierbare Texte, Rz-Schnellauswahl, Doppelklick ---
    sf = sys.modules.get("swui.surface_finish")
    if sf is None:
        print("  FEHLER: surface_finish nicht geladen (Befehl SWUI_SurfaceFinish)")
        return False
    import re as _re
    import re
    import xml.dom.minidom as _md2
    svg_s = sf.build_svg("required", True, {"a": "Rz 16", "b": "Ra 0,8", "c": "geschliffen", "d": "⊥", "e": "0,5"})
    dom_s = _md2.parseString(svg_s.encode("utf-8"))
    ns_ok = dom_s.documentElement.getAttribute("xmlns:freecad") == "https://www.freecad.org/wiki/index.php?title=Svg_Namespace"
    keys_s = _re.findall(r"freecad:editable='(\w)'", svg_s)
    vals_s = [t_.firstChild.firstChild.nodeValue if t_.firstChild.firstChild else "" for t_ in dom_s.getElementsByTagName("text")]
    if not ns_ok or keys_s != list(sf.FIELDS) or vals_s != ["Rz 16", "Ra 0,8", "geschliffen", "⊥", "0,5"]:
        print("  FEHLER: Oberflächensymbol – editierbare Felder/Reihenfolge/Namensraum", keys_s, vals_s, ns_ok)
        return False
    if "M0,44 L24,44" not in svg_s or "r='6'" not in svg_s or "r='9'" in svg_s:
        print("  FEHLER: Oberflächensymbol – Grundsymbol/rundum")
        return False
    if "M0,44 L24,44" in sf.build_svg("any") or "r='9'" not in sf.build_svg("prohibited"):
        print("  FEHLER: Oberflächensymbol – Sinnbilder beliebig/unzulässig")
        return False
    if not all(p_ in sf.PRESETS for p_ in ("Rz 4", "Rz 16", "Rz 63")):
        print("  FEHLER: Schnellauswahl Rz 4/16/63 fehlt")
        return False
    sym_o = types.SimpleNamespace(SWUI_Kind="surface", SWUI_SurfaceType="prohibited", SWUI_SurfaceAllAround=False,
                                  EditableTexts=["Rz 63", "", "gedreht", "C"], Rotation=90.0)
    st_s = sf.read_state(sym_o)
    if st_s["texts"] != {"a": "Rz 63", "b": "", "c": "gedreht", "d": "C", "e": ""} or st_s["type"] != "prohibited" or st_s["rotation"] != 90.0:
        print("  FEHLER: Oberflächensymbol – Werte nicht zurückgelesen", st_s)
        return False
    ii_ = sys.modules["swui.insert_image"]
    if ii_.selected_image([types.SimpleNamespace(TypeId="TechDraw::DrawViewSymbol", SWUI_Kind="surface")]) is not None:
        print("  FEHLER: Oberflächensymbol wird als Bild behandelt")
        return False
    opened = []
    old_open = sf.open_panel
    sf.open_panel = lambda o, created: opened.append((o, created)) or True
    old_sel = getattr(gui.Selection, "getSelection", None)
    gui.Selection.getSelection = lambda: [sym_o]
    old_ctl2 = getattr(gui, "Control", None)
    gui.Control = types.SimpleNamespace(activeDialog=lambda: False)
    old_wb3 = pd_._is_active_workbench
    pd_._is_active_workbench = lambda: True
    dbl = types.SimpleNamespace(type=lambda: qtc.QEvent.Type.MouseButtonDblClick)
    try:
        r_dbl = pd_.handle_event(pd_.DragState(), g_idle, dbl)
        r_dbl_tool = pd_.handle_event(pd_.DragState(), g_tool, dbl)
    finally:
        sf.open_panel = old_open
        if old_sel is None:
            del gui.Selection.getSelection
        else:
            gui.Selection.getSelection = old_sel
        gui.Control = old_ctl2
        pd_._is_active_workbench = old_wb3
    if not r_dbl or opened != [(sym_o, False)] or r_dbl_tool:
        print("  FEHLER: Doppelklick öffnet die Oberflächenangabe nicht", r_dbl, opened, r_dbl_tool)
        return False
    print("  Oberfl.  : Symbol nach ISO 1302, Texte editierbar, Rz 4/16/63, Doppelklick öffnet wieder")

    # --- Schweisssymbol wie SW (9e2d) ---
    ws = sys.modules.get("swui.weld_symbol")
    if ws is None:
        print("  FEHLER: weld_symbol nicht geladen (Befehl SWUI_WeldSymbol)")
        return False
    data_w = {"arrow": {"seam": "fillet", "size": "a5", "len": "2×20 (10)"}, "other": {"seam": ""},
              "all_around": True, "field": True, "tail": "111"}
    svg_w = ws.build_svg(data_w, (-14.0, 12.0))
    dom_w = _md2.parseString(svg_w.encode("utf-8"))
    root_w = dom_w.documentElement
    vb = [float(v) for v in root_w.getAttribute("viewBox").split()]
    keys_w = _re.findall(r"freecad:editable='(\w+)'", svg_w)
    if (keys_w != list(ws.TEXT_FIELDS) or not root_w.getAttribute("width").endswith("mm")
            or abs(vb[0] + vb[2] / 2) > 1e-6 or abs(vb[1] + vb[3] / 2) > 1e-6):
        print("  FEHLER: Schweißsymbol – Textfelder/mm/um den Knick zentriert", keys_w, vb)
        return False
    if "r='1.5'" not in svg_w or "M0,0 L0,-7" not in svg_w or "111" not in svg_w:
        print("  FEHLER: Schweißsymbol – Ringsum/Baustelle/Gabel")
        return False
    if "stroke-dasharray" in svg_w or "stroke-dasharray" not in ws.build_svg(dict(data_w, dashed=True)):
        print("  FEHLER: Schweißsymbol – gestrichelte Linie nur auf Wunsch")
        return False
    # Pfeilseite unter der Linie (vereinfacht), ueber der Linie mit gestrichelter Linie (DIN EN 22553)
    plain = ws.build_svg({"arrow": {"seam": "fillet"}}, (-10, 8))
    dashed = ws.build_svg({"arrow": {"seam": "fillet"}, "dashed": True}, (-10, 8))
    fil_plain = _re.search(r"d='M([\d.]+),0\.00 L[\d.]+,(-?[\d.]+)", plain)
    fil_dash = _re.search(r"d='M([\d.]+),0\.00 L[\d.]+,(-?[\d.]+)", dashed)
    if not fil_plain or not fil_dash or float(fil_plain.group(2)) <= 0 or float(fil_dash.group(2)) >= 0:
        print("  FEHLER: Schweißsymbol – Pfeilseite unten (vereinfacht) / oben (mit Strichlinie)")
        return False
    if ws.tip_vector((100.0, 50.0), (90.0, 40.0)) != (-10.0, 10.0):
        print("  FEHLER: Schweißsymbol – Pfeilrichtung (Blatt y nach oben, SVG nach unten)")
        return False

    class WObj:
        def __init__(self):
            self.X, self.Y, self.SWUI_TipX, self.SWUI_TipY = 0.0, 0.0, 0.0, 0.0
            self.SWUI_Kind, self.SWUI_WeldData, self.EditableTexts, self.Symbol = "weld", "", [], ""
            self.Document = types.SimpleNamespace(Name="D", recompute=lambda: None)
            self.Name = "Schweissen"

    wo = WObj()
    nxt = ws.apply_pick(wo, 0, (80.0, 60.0))
    if nxt != 1 or (wo.SWUI_TipX, wo.SWUI_TipY) != (80.0, 60.0) or (wo.X, wo.Y) != (80.0 + ws.DEFAULT_OFFSET[0], 60.0 + ws.DEFAULT_OFFSET[1]):
        print("  FEHLER: Schweißsymbol – 1. Klick setzt Pfeilspitze", wo.X, wo.Y)
        return False
    if ws.apply_pick(wo, 1, (100.0, 75.0)) is not None or (wo.X, wo.Y) != (100.0, 75.0) or "freecad:editable" not in wo.Symbol:
        print("  FEHLER: Schweißsymbol – 2. Klick setzt Symbol")
        return False
    wo.EditableTexts = ["a7", "", "", "", "141"]  # im Eigenschaften-Fenster umgeschrieben
    dw = ws.read_data(wo)
    if dw["arrow"]["size"] != "a7" or dw["tail"] != "141":
        print("  FEHLER: Schweißsymbol – geänderte Texte nicht übernommen", dw)
        return False
    # Verschieben: Beobachter baut neu (Pfeil folgt), Spitze bleibt
    old_single = qtc.QTimer.singleShot
    qtc.QTimer.singleShot = lambda _ms, fn: fn()
    old_sym = wo.Symbol
    wo.X = 130.0
    try:
        ws._Observer().slotChangedObject(wo, "X")
    finally:
        qtc.QTimer.singleShot = old_single
    if wo.Symbol == old_sym or (wo.SWUI_TipX, wo.SWUI_TipY) != (80.0, 60.0) or ws._rebuilding:
        print("  FEHLER: Schweißsymbol – Pfeil folgt beim Verschieben nicht")
        return False
    # Doppelklick oeffnet, Klick-Modus sperrt das Ziehen
    opened_w = []
    old_open_w = ws.open_panel
    ws.open_panel = lambda o, created: opened_w.append((o, created)) or True
    gui.Selection.getSelection = lambda: [wo]
    gui_ctl = getattr(gui, "Control", None)
    gui.Control = types.SimpleNamespace(activeDialog=lambda: False)
    pd_._is_active_workbench = lambda: True
    try:
        r_w = pd_.handle_event(pd_.DragState(), g_idle, dbl)
        ws._picker = object()
        st_pick = pd_.DragState()
        pd_.handle_event(st_pick, g_idle, press)
    finally:
        ws._picker = None
        ws.open_panel = old_open_w
        del gui.Selection.getSelection
        gui.Control = gui_ctl
        pd_._is_active_workbench = old_wb3
    if not r_w or opened_w != [(wo, False)] or st_pick.press is not None:
        print("  FEHLER: Schweißsymbol – Doppelklick / Klick-Modus", r_w, opened_w, st_pick.press)
        return False
    print("  Schweißen: Symbol nach ISO 2553 wie SW – Pfeil anklicken, Symbol setzen, Pfeil folgt, Doppelklick")

    # --- Namen im Zeichnungsbaum (9f) ---
    nm = sys.modules["swui.naming"]

    class NObj:
        def __init__(self, type_id, label, **kw):
            self.TypeId, self.Label = type_id, label
            self.__dict__.update(kw)

    ndoc = types.SimpleNamespace(Objects=[])

    def nadd(o):
        o.Document = ndoc
        ndoc.Objects.append(o)
        return o

    grp1 = nadd(NObj("TechDraw::DrawProjGroup", "ProjGroup"))
    lab_g1 = nm.sw_label_for(grp1)
    grp1.Label = lab_g1
    grp2 = nadd(NObj("TechDraw::DrawProjGroup", "ProjGroup001"))
    lab_g2 = nm.sw_label_for(grp2)
    vp1 = nadd(NObj("TechDraw::DrawViewPart", "View"))
    dim1 = nadd(NObj("TechDraw::DrawViewDimension", "Maß001"))
    bal1 = nadd(NObj("TechDraw::DrawViewBalloon", "Balloon"))
    weld1 = nadd(NObj("TechDraw::DrawViewSymbol", "Schweißsymbol", SWUI_Kind="weld"))
    surf1 = nadd(NObj("TechDraw::DrawViewSymbol", "Oberflächenangabe", SWUI_Kind="surface"))
    img1 = nadd(NObj("TechDraw::DrawViewSymbol", "Symbol"))
    left1 = nadd(NObj("TechDraw::DrawProjGroupItem", "Links", Type="Left"))
    ann1 = nadd(NObj("TechDraw::DrawViewAnnotation", "Benennung A-A"))
    got_n = (lab_g1, lab_g2, nm.sw_label_for(vp1), nm.sw_label_for(dim1), nm.sw_label_for(bal1),
             nm.sw_label_for(weld1), nm.sw_label_for(surf1), nm.sw_label_for(img1), nm.sw_label_for(left1),
             nm.sw_label_for(ann1))
    want_n = ("Standard-Dreiansicht", "Standard-Dreiansicht2", "Zeichenansicht1", "Bemaßung1", "Positionsnummer1",
              "Schweißsymbol1", "Oberflächenangabe1", "Bild1", "Seitenansicht von links", None)
    if got_n != want_n:
        print("  FEHLER: SW-Namen im Zeichnungsbaum", got_n)
        return False
    # bestehende Zeichnung: nur FreeCAD-Namen ersetzen
    old_doc = types.SimpleNamespace(Objects=[])
    for o in (NObj("TechDraw::DrawProjGroupItem", "Links", Type="Left"),
              NObj("TechDraw::DrawProjGroupItem", "Vorderansicht", Type="Front"),
              NObj("TechDraw::DrawProjGroupItem", "Meine Ansicht", Type="Top"),
              NObj("TechDraw::DrawProjGroupItem", "Isometrie001", Type="FrontTopRight"),
              NObj("TechDraw::DrawSVGTemplate", "Template")):
        o.Document = old_doc
        old_doc.Objects.append(o)
    n_ren = nm.refresh_drawing(old_doc)
    labels_old = [o.Label for o in old_doc.Objects]
    if labels_old != ["Seitenansicht von links", "Vorderansicht", "Meine Ansicht", "Isometrie001", "Blattformat1"] or n_ren != 2:
        print("  FEHLER: Namen in bestehender Zeichnung", labels_old, n_ren)
        return False
    if nm.refresh_drawing(old_doc) != 0:
        print("  FEHLER: Umbenennen in bestehender Zeichnung wiederholt sich")
        return False

    # --- Baumnamen auf Englisch (Sprache, Schritt 4a) ---
    i18_n = sys.modules["swui.i18n"]
    vl_n = sys.modules["swui.view_labels"]
    de_n = sys.modules["swui.drawing_export"]
    na_n = sys.modules["swui.commands.new_assembly"]
    par_n = sys.modules["FreeCAD"].ParamGet(i18_n.PARAMS)
    par_n.SetString(i18_n.KEY, "en")
    try:
        edoc = types.SimpleNamespace(Objects=[])

        def eadd(o):
            o.Document = edoc
            edoc.Objects.append(o)
            return o

        eadd(NObj("Sketcher::SketchObject", "Skizze1"))  # vorhanden, noch deutsch
        e_sk = eadd(NObj("Sketcher::SketchObject", "Sketch"))
        e_pad = eadd(NObj("PartDesign::Pad", "Pad"))
        e_pl = eadd(NObj("App::Plane", "XY_Plane", Role="XY_Plane"))
        e_grp = eadd(NObj("TechDraw::DrawProjGroup", "ProjGroup"))
        e_left = eadd(NObj("TechDraw::DrawProjGroupItem", "Left", Type="Left"))
        e_weld = eadd(NObj("TechDraw::DrawViewSymbol", "Weld", SWUI_Kind="weld"))
        e_jg = eadd(NObj("Assembly::JointGroup", "Joints"))
        got_e = tuple(nm.sw_label_for(o) for o in (e_sk, e_pad, e_pl, e_grp, e_left, e_weld, e_jg))
        # Verknuepfungen: vorhandenes "Deckungsgleich1" bleibt, neues heisst "Coincident1"
        j_old = eadd(NObj("App::FeaturePython", "Deckungsgleich1", JointType="Distance", Distance=0.0, InList=[e_jg]))
        j_new = eadd(NObj("App::FeaturePython", "Joint", JointType="Distance", Distance=0.0, InList=[e_jg]))
        j_dis = eadd(NObj("App::FeaturePython", "Joint001", JointType="Distance", Distance=5.0, InList=[e_jg]))
        nm.refresh_joints(edoc)
        joints_e = (j_old.Label, j_new.Label, j_dis.Label)
        # bestehende Zeichnung: deutsche SW-Namen bleiben, FreeCAD-Namen werden englisch
        odoc = types.SimpleNamespace(Objects=[])
        for o in (NObj("TechDraw::DrawProjGroupItem", "Vorderansicht", Type="Front"),
                  NObj("TechDraw::DrawProjGroupItem", "Links", Type="Left"),
                  NObj("TechDraw::DrawSVGTemplate", "Template")):
            o.Document = odoc
            odoc.Objects.append(o)
        nm.refresh_drawing(odoc)
        drawing_e = [o.Label for o in odoc.Objects]
        again_e = nm.refresh_drawing(odoc)
        # Schnittansicht: neu englisch, vorhandene deutsche bleibt deutsch
        sec_t = sorted(vl_n.SECTION_TYPES)[0]
        s_new = NObj(sec_t, "Section", SectionSymbol="")
        vl_n.set_letter(s_new, "A")
        s_old = NObj(sec_t, "Schnittansicht B-B", SectionSymbol="B")
        vl_n.set_letter(s_old, "C")
        secs_e = (s_new.Label, s_old.Label)
        pg_a, pg_b = NObj("TechDraw::DrawPage", "Sheet1"), NObj("TechDraw::DrawPage", "Sheet2")
        pg_c = NObj("TechDraw::DrawPage", "Mein Blatt")
        paths_e = de_n.sheet_paths("/o/T.pdf", [pg_a, pg_b], ".pdf") + de_n.sheet_paths("/o/T.dxf", [pg_c, pg_a], ".dxf")
        asm_e = na_n.next_name(["Assembly1"])
    finally:
        par_n.RemString(i18_n.KEY)
    if got_e != ("Sketch1", "Boss-Extrude1", "Top Plane", "Standard 3 View", "Left View", "Weld Symbol1", "Mates"):
        print("  FEHLER: englische Baumnamen", got_e)
        return False
    if joints_e != ("Deckungsgleich1", "Coincident1", "Distance1"):
        print("  FEHLER: englische Verknüpfungsnamen / vorhandene bleiben", joints_e)
        return False
    if drawing_e != ["Vorderansicht", "Left View", "Sheet Format1"] or again_e != 0:
        print("  FEHLER: bestehende Zeichnung auf Englisch", drawing_e, again_e)
        return False
    if secs_e != ("Section View A-A", "Schnittansicht C-C"):
        print("  FEHLER: Schnittansicht englisch / vorhandene deutsch", secs_e)
        return False
    if paths_e != ["/o/T_Sheet1.pdf", "/o/T_Sheet2.pdf", "/o/T_Sheet1.dxf", "/o/T_Sheet2.dxf"] or asm_e != "Assembly2":
        print("  FEHLER: englische Dateinamen je Blatt / Baugruppe", paths_e, asm_e)
        return False
    print("  Baum EN  : Sketch1, Boss-Extrude1, Top Plane, Standard 3 View, Coincident1, Section View A-A, _Sheet2.pdf; vorhandene deutsche Namen bleiben")
    # geloeschtes Objekt in der Warteschlange (Vorschau-Bemassung) darf _flush nicht abbrechen
    class Gone:
        @property
        def TypeId(self):
            raise ReferenceError("Cannot access attribute 'TypeId' of deleted object")

    keep_n = NObj("TechDraw::DrawViewBalloon", "Balloon")
    keep_n.Document = ndoc
    nm._pending[:] = [Gone(), keep_n]
    try:
        nm._flush()
    except Exception as exc_:
        print("  FEHLER: Umbenennen bricht bei gelöschtem Objekt ab", exc_)
        return False
    if nm._pending or keep_n.Label != "Positionsnummer1":
        print("  FEHLER: nach gelöschtem Objekt nicht weiter umbenannt", nm._pending, keep_n.Label)
        return False
    print("  Baum     : Blatt/Blattformat/Zeichenansicht/Bemaßung/Positionsnummer/Schnitt-/Detailansicht wie SW")

    # --- Qt-Meldungen beim starken Zoomen (render glyph failed) ausblenden ---
    qm = sys.modules.get("swui.qt_messages")
    if qm is None or not qm._installed:
        print("  FEHLER: Qt-Meldungsfilter nicht installiert (InitGui.Initialize)")
        return False
    if not qm._active:
        print("  FEHLER: Qt-Meldungsfilter nach Activated nicht aktiv")
        return False
    got_q = []
    old_prev, old_act = qm._previous, qm._active
    qm._previous = lambda m_, c_, t_: got_q.append(t_)
    glyph = "render glyph failed err=62 face=0x1, glyph=72"
    try:
        qm.set_active(True)  # in der Werkbank
        qm.handler(1, types.SimpleNamespace(category="default"), glyph)
        qm.handler(1, types.SimpleNamespace(category="default"), "QWidget: andere Warnung")
        in_wb = list(got_q)
        del got_q[:]
        qm.set_active(False)  # ausserhalb: voellig durchlaessig
        qm.handler(1, types.SimpleNamespace(category="default"), glyph)
        out_wb = list(got_q)
    finally:
        qm._previous, qm._active = old_prev, old_act
    if in_wb != ["QWidget: andere Warnung"] or qm.format_message("qt.svg", "x") != "(qt.svg) x" or qm.format_message("default", "x") != "x":
        print("  FEHLER: Qt-Meldungsfilter filtert falsch", in_wb)
        return False
    if out_wb != [glyph]:
        print("  FEHLER: Qt-Meldungsfilter wirkt auch außerhalb der Werkbank", out_wb)
        return False
    # Parameter Mod/SWUI/QtMessageFilter = false -> gar nicht anmelden
    fc_q = sys.modules["FreeCAD"]
    saved_inst = qm._installed
    fc_q.ParamGet(qm.OWN_PARAMS).SetBool(qm.ENABLE_KEY, False)
    try:
        qm._installed = False
        off_res = qm.install()
        off_state = qm._installed
        qm.set_active(True)
        off_act = qm._active
    finally:
        fc_q.ParamGet(qm.OWN_PARAMS).RemBool(qm.ENABLE_KEY)
        qm._installed, qm._active = saved_inst, old_act
    if off_res or off_state or off_act:
        print("  FEHLER: Qt-Meldungsfilter trotz QtMessageFilter=false angemeldet/aktiv")
        return False
    print("  Meldungen: 'render glyph failed' nur in der Werkbank ausgeblendet, sonst alles durchgelassen; abschaltbar")

    # --- Sprache: Knopf "Language", swui/i18n.py, swui/lang/ ----------
    __import__("swui.i18n")
    i18 = sys.modules["swui.i18n"]
    rb_l = sys.modules["swui.ribbon"]
    lay_l = sys.modules["swui.ribbon_layout"]
    gui_l = sys.modules["FreeCADGui"]
    qtc_l = sys.modules["PySide.QtCore"]
    if [c for c, _n in i18.choices()] != ["de", "en", "es"] or i18.setting() != "auto":
        print("  FEHLER: Sprachen/Vorgabe", i18.choices(), i18.setting())
        return False
    # "Automatisch" = wie FreeCAD: Sprache mit eigener Datei -> diese, sonst Englisch
    res_auto = []
    for loc in ("German", "English", "French", "Spanish (Argentina)", "es-AR", ""):
        gui_l.getLocale = (lambda l_=loc: l_)
        res_auto.append(i18.resolve("auto"))
    gui_l.getLocale = lambda: "German"
    if res_auto[:5] != ["de", "en", "en", "es", "es"]:
        print("  FEHLER: Automatisch folgt FreeCADs Sprache nicht", res_auto)
        return False
    # Alle Ribbon-Texte muessen in jeder Sprache vorhanden sein
    keys_l = ["\n(Pfeil rechts: weitere Varianten)", "Automatisch"]
    def walk_l(entry):
        if isinstance(entry, dict) and entry.get("title"):
            keys_l.append(entry["title"])  # feste Beschriftung eines Ausklappknopfs
        if isinstance(entry, dict):
            for k_ in ("stack", "flyout", "toggle"):
                for sub_ in entry.get(k_, ()):
                    walk_l(sub_)
        elif isinstance(entry, tuple):
            if entry[0] in _fork_layout_commands():
                return  # fork: textos en castellano sin tr() (convención del fork)
            keys_l.append(entry[1])
            cmd_ = commands.get(entry[0])
            if cmd_ is not None:
                tip_ = cmd_.GetResources().get("ToolTip")
                if tip_:
                    keys_l.append(tip_)
    for title_, groups_ in lay_l.TABS:
        keys_l.append(title_)
        for g_ in groups_:
            for e_ in g_:
                walk_l(e_)
    # Alle tr("...") / N_("...") im Code (eigene Fenster, Meldungen) - statisch gesucht
    import ast as ast_l
    swui_dir = os.path.join(ADDON, "swui")
    for base_, dirs_, files_ in os.walk(swui_dir):
        dirs_[:] = [d_ for d_ in dirs_ if d_ not in ("__pycache__", "lang")]
        for f_ in files_:
            if not f_.endswith(".py"):
                continue
            with open(os.path.join(base_, f_), encoding="utf-8") as fh_:
                tree_ = ast_l.parse(fh_.read())
            for n_ in ast_l.walk(tree_):
                if (isinstance(n_, ast_l.Call) and getattr(n_.func, "id", None) in ("tr", "N_") and n_.args
                        and isinstance(n_.args[0], ast_l.Constant) and isinstance(n_.args[0].value, str)):
                    keys_l.append(n_.args[0].value)
                # Baumnamen: tree("...") / tree_like("...") -> Schluessel "Baum|..."
                if (isinstance(n_, ast_l.Call) and getattr(n_.func, "id", None) in ("tree", "tree_like", "tree_variants")
                        and n_.args and isinstance(n_.args[0], ast_l.Constant) and isinstance(n_.args[0].value, str)):
                    keys_l.append(i18.TREE + n_.args[0].value)
    # SW-Begriffe in FreeCAD-Dialogen (feature_terms.SPECS): alle Beschriftungen,
    # Listeneintraege und Tooltips
    __import__("swui.feature_terms")
    for spec_ in sys.modules["swui.feature_terms"].SPECS:
        keys_l.extend(spec_["labels"].values())
        for items_ in spec_["combos"].values():
            keys_l.extend(items_)
        keys_l.extend(spec_.get("tooltips", {}).values())
    # Baumnamen aus den Listen von naming.py und proj_views.TYPE_NAMES
    keys_l.extend(i18.TREE + n_ for n_ in sys.modules["swui.naming"].tree_terms())
    keys_l.extend(i18.TREE + n_ for n_ in sys.modules["swui.proj_views"].TYPE_NAMES.values())
    # Sprachdateien: kein Schluessel doppelt (Python wuerde still ueberschreiben)
    lang_dir = os.path.join(swui_dir, "lang")
    for f_ in sorted(os.listdir(lang_dir)):
        if f_.endswith(".py") and not f_.startswith("_"):
            with open(os.path.join(lang_dir, f_), encoding="utf-8") as fh_:
                tree_ = ast_l.parse(fh_.read())
            for n_ in ast_l.walk(tree_):
                if isinstance(n_, ast_l.Dict):
                    seen_, dup_ = set(), []
                    for k_ in n_.keys:
                        if isinstance(k_, ast_l.Constant):
                            (dup_.append(k_.value) if k_.value in seen_ else seen_.add(k_.value))
                    if dup_:
                        print("  FEHLER: %s - Schlüssel doppelt: %s" % (f_, dup_[:3]))
                        return False
    for code_, _name in i18.choices():
        miss_ = i18.missing(sorted(set(keys_l)), code_)
        if miss_:
            print("  FEHLER: Sprache %s - %d Text(e) ohne Übersetzung: %s" % (code_, len(miss_), miss_[:5]))
            return False
    # Platzhalter (%s, %d, %.1f ...) muessen in jeder Uebersetzung gleich sein,
    # sonst stuerzt die Meldung zur Laufzeit ab ("not all arguments converted")
    import re as re_l
    ph_re = re_l.compile(r"%[-+ #0]*\d*(?:\.\d+)?[sdifgrx%]")
    for code_, _name in i18.choices():
        table_ = getattr(i18.languages().get(code_), "TEXTS", {})
        for k_, v_ in table_.items():
            if ph_re.findall(k_) != ph_re.findall(v_):
                print("  FEHLER: Sprache %s - Platzhalter verschieden: %r -> %r" % (code_, k_, v_))
                return False
    if i18.tr("Fase", "en") != "Chamfer" or i18.tr("Fase", "de") != "Fase" or i18.tr("Gibt es nicht", "en") != "Gibt es nicht":
        print("  FEHLER: tr() übersetzt falsch")
        return False
    # Sprache fehlt ein Text -> Englisch, dann Deutsch (dritte Sprache simuliert)
    langs_l = i18.languages()
    langs_l["fr"] = types.SimpleNamespace(CODE="fr", NAME="Français", TEXTS={"Fase": "Chanfrein"})
    try:
        fr_ok = (i18.tr("Fase", "fr") == "Chanfrein" and i18.tr("Verrundung", "fr") == "Fillet"
                 and i18.tr("Gibt es nicht", "fr") == "Gibt es nicht"
                 and [c for c, _n in i18.choices()] == ["de", "en", "es", "fr"])
    finally:
        del langs_l["fr"]
    if not fr_ok:
        print("  FEHLER: Rückfall Englisch/Deutsch oder Menü-Reihenfolge bei weiterer Sprache")
        return False
    # Knopf im Reiter Evaluieren
    if {"language": True} not in [e_ for g_ in dict(lay_l.TABS)["Evaluieren"] for e_ in g_]:
        print("  FEHLER: Knopf Language nicht im Reiter Evaluieren")
        return False
    if [(c, x) for c, x, _k in rb_l.language_menu()] != [("auto", "Automatisch (Deutsch)"), ("de", "Deutsch"), ("en", "English"),
                                                         ("es", "Español")] \
            or [k for _c, _x, k in rb_l.language_menu()] != [True, False, False, False]:
        print("  FEHLER: Language-Menü (deutsch)", rb_l.language_menu())
        return False
    # Umschalten auf Englisch: wirkt sofort (Ribbon neu aufgebaut)
    old_single_l = qtc_l.QTimer.singleShot
    qtc_l.QTimer.singleShot = lambda _ms, fn: fn()
    old_dock_l = rb_l._dock
    qtw_l = sys.modules["PySide.QtWidgets"]
    btn_mock = qtw_l.QToolButton.return_value  # Attrappe: alle Knoepfe sind dasselbe Objekt
    tab_mock = qtw_l.QTabWidget.return_value
    try:
        btn_mock.reset_mock()
        tab_mock.reset_mock()
        old_dock_l.deleteLater.reset_mock()
        i18.set_setting("en")
        texts_en = [c_[0][0] for c_ in btn_mock.setText.call_args_list]
        tips_en = [c_[0][0] for c_ in btn_mock.setToolTip.call_args_list]
        tabs_en = [c_[0][1] for c_ in tab_mock.addTab.call_args_list]
        titles_en = list(rb_l._tab_titles)
        menu_en = rb_l.language_menu()
        removed = old_dock_l.deleteLater.called
        try:
            i18.set_setting("xx")
            bad_ok = False
        except ValueError:
            bad_ok = True
        btn_mock.reset_mock()
        i18.set_setting("auto")
        texts_de = [c_[0][0] for c_ in btn_mock.setText.call_args_list]
    finally:
        qtc_l.QTimer.singleShot = old_single_l
        sys.modules["FreeCAD"].ParamGet(i18.PARAMS).RemString(i18.KEY)
    if ("Extruded\nBoss/Base" not in texts_en or "Linear\naustragen" in texts_en
            or "Linear\naustragen" not in texts_de or "Extruded\nBoss/Base" in texts_de):
        print("  FEHLER: Ribbon-Beschriftung nach Umschalten", texts_en[:4], texts_de[:4])
        return False
    lang_btn = "Language" if "Language" in texts_en and "Language" in texts_de else texts_en[:3]
    fly_tip = next((x_ for x_ in tips_en if "variants" in x_), "")
    if tabs_en[:6] != ["Evaluate", "Features", "Sketch", "View", "Assembly", "Drawing"] or titles_en[2] != "Skizze":
        print("  FEHLER: Reiter auf Englisch / interne Namen", tabs_en, titles_en)
        return False
    if [k for _c, _x, k in menu_en] != [False, False, True, False] or menu_en[0][1] != "Automatic (Deutsch)" or lang_btn != "Language":
        print("  FEHLER: Language-Menü (englisch)", menu_en, lang_btn)
        return False
    if not fly_tip.endswith("(Arrow on the right: more variants)") or not removed or not bad_ok:
        print("  FEHLER: Tooltip/Neuaufbau/unbekannte Sprache", fly_tip, removed, bad_ok)
        return False
    # Eigene Fenster zeigen die eingestellte Sprache (Oberflaechenangabe, Schweisssymbol)
    qtw_f = sys.modules["PySide.QtWidgets"]

    def panel_texts(code):
        sys.modules["FreeCAD"].ParamGet(i18.PARAMS).SetString(i18.KEY, code)
        n0 = len(qtw_f.mock_calls)
        sys.modules["swui.surface_finish"]._TaskPanel(types.SimpleNamespace(
            EditableTexts=["Rz 16", "", "", "", ""], SWUI_SurfaceType="any", SWUI_SurfaceAllAround=False, Rotation=0.0))
        __import__("swui.weld_symbol")
        sys.modules["swui.weld_symbol"]._TaskPanel(types.SimpleNamespace(EditableTexts=[]))
        out = set()
        for c_ in qtw_f.mock_calls[n0:]:
            for a_ in list(c_[1]):
                if isinstance(a_, str):
                    out.add(a_)
        return out

    combo_f = qtw_f.QComboBox.return_value
    old_find = combo_f.findData.return_value
    combo_f.findData.return_value = 0  # Attrappe: Index statt MagicMock
    try:
        txt_en = panel_texts("en")
        txt_de = panel_texts("de")
    finally:
        combo_f.findData.return_value = old_find
        sys.modules["FreeCAD"].ParamGet(i18.PARAMS).RemString(i18.KEY)
    want_en = {"Symbol", "Parameter and value (a)", "Arrow side", "Weld type", "Fillet weld", "None", "Weld all around (circle)"}
    want_de = {"Sinnbild", "Kenngröße und Wert (a)", "Pfeilseite", "Nahtart", "Kehlnaht", "Ohne", "Ringsum-Naht (Kreis)"}
    if not want_en <= txt_en or txt_en & want_de or not want_de <= txt_de:
        print("  FEHLER: Fenster nicht in der eingestellten Sprache", sorted(want_en - txt_en), sorted(txt_en & want_de))
        return False
    print("  Sprache  : Knopf Language (Automatisch/Deutsch/English), Ribbon sofort umgeschaltet, %d Texte in allen Sprachen, Fenster übersetzt, Rückfall Englisch" % len(set(keys_l)))

    # --- Ausgabe PDF (alle Blaetter) / DXF (9g) ---
    de = sys.modules.get("swui.drawing_export")
    pm = sys.modules.get("swui.pdf_merge")
    if de is None or pm is None:
        print("  FEHLER: drawing_export/pdf_merge nicht geladen")
        return False
    tplx = types.SimpleNamespace(EditableTexts={"drawing_number": "TZ-001/A"})
    pg1 = types.SimpleNamespace(TypeId="TechDraw::DrawPage", Label="Blatt1", Name="Page", Template=tplx)
    pg2 = types.SimpleNamespace(TypeId="TechDraw::DrawPage", Label="Blatt2", Name="Page001", Template=None)
    xdoc = types.SimpleNamespace(Objects=[pg1, types.SimpleNamespace(TypeId="TechDraw::DrawViewPart"), pg2],
                                 FileName="/h/z/Tisch_Zeichnung.FCStd", Label="Tisch_Zeichnung", Name="Tisch")
    pgs = de.pages_of(xdoc)
    if pgs != [pg1, pg2] or os.path.normpath(de.suggested_path(xdoc, pgs, ".pdf")) != os.path.normpath("/h/z/TZ-001_A.pdf"):
        print("  FEHLER: Blätter/Dateiname aus Zeichnungsnummer", de.suggested_path(xdoc, pgs, ".pdf"))
        return False
    tplx.EditableTexts = {"drawing_number": ""}
    if os.path.normpath(de.suggested_path(xdoc, pgs, ".dxf")) != os.path.normpath("/h/z/Tisch_Zeichnung.dxf"):
        print("  FEHLER: Dateiname ohne Zeichnungsnummer")
        return False
    if de.sheet_paths("/o/T.dxf", pgs, ".dxf") != ["/o/T_Blatt1.dxf", "/o/T_Blatt2.dxf"] or de.sheet_paths("/o/T.dxf", [pg1], ".dxf") != ["/o/T.dxf"]:
        print("  FEHLER: DXF je Blatt", de.sheet_paths("/o/T.dxf", pgs, ".dxf"))
        return False
    # PDF: echte Mini-PDFs (klassische xref-Tabelle wie Qt) zusammenfuegen
    def mini_pdf(path, w, h, text):
        objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
                b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
                b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Contents 4 0 R /Resources << >> >>" % (w, h)]
        stream = b"BT /F1 12 Tf 20 20 Td (" + text + b") Tj ET"
        objs.append(b"<< /Length 5 0 R >>\nstream\n" + stream + b"\nendstream")
        objs.append(b"%d" % len(stream))
        out = bytearray(b"%PDF-1.4\n")
        offs = []
        for i_, o_ in enumerate(objs, 1):
            offs.append(len(out))
            out += b"%d 0 obj\n" % i_ + o_ + b"\nendobj\n"
        xr = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
        for o_ in offs:
            out += b"%010d 00000 n \n" % o_
        out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, xr)
        with open(path, "wb") as fh_:
            fh_.write(bytes(out))

    pdir = os.path.join(SCRATCH_TMP, "pdf9g")
    os.makedirs(pdir, exist_ok=True)
    texts_pdf = {pg1.Name: (595, 842, b"Blatt eins"), pg2.Name: (1191, 842, b"Blatt zwei")}
    outp = os.path.join(pdir, "TZ.pdf")
    files_p, merged_p = de.export_pdf(pgs, outp, lambda p_, f_: mini_pdf(f_, *texts_pdf[p_.Name]), pm.merge)
    data_p = open(outp, "rb").read()
    objs_p = pm.read_objects(data_p)
    pages_p = [o_ for o_ in objs_p.values() if b"/Type /Page " in o_ or b"/Type /Page\n" in o_]
    if (not merged_p or files_p != [outp] or b"/Count 2" not in data_p or len(pages_p) != 2
            or b"Blatt eins" not in data_p or b"Blatt zwei" not in data_p or b"/Parent 2 0 R" not in pages_p[0]
            or data_p.index(b"Blatt eins") > data_p.index(b"Blatt zwei")):
        print("  FEHLER: PDF – alle Blätter in einer Datei", merged_p, files_p, len(pages_p))
        return False
    # Zusammenfuegen klappt nicht -> einzelne Dateien
    def broken(_files, _out):
        raise pm.UnsupportedPdf("Test")
    files_b, merged_b = de.export_pdf(pgs, os.path.join(pdir, "B.pdf"), lambda p_, f_: mini_pdf(f_, *texts_pdf[p_.Name]), broken)
    if merged_b or [os.path.basename(f_) for f_ in files_b] != ["B_Blatt1.pdf", "B_Blatt2.pdf"] or not all(os.path.isfile(f_) for f_ in files_b):
        print("  FEHLER: PDF-Rückfall auf einzelne Dateien", files_b)
        return False
    print("  Ausgabe  : PDF alle Blätter in einer Datei (sonst einzeln), DXF je Blatt, Name aus Zeichnungsnummer")

    gui.ActiveDocument = None
    print("  Konstrukt: nur neue Linien gestrichelt, Kreise/alte Linien bleiben; Ende bei Werkzeugwechsel/Skizzenende")

    # Zweites Activated darf nicht neu bauen (sonst doppelte Knoepfe).
    wb.Activated()
    if len(ribbon.button_names()) != len(built):
        print("  FEHLER: Ribbon wurde beim zweiten Aktivieren neu aufgebaut")
        return False

    # --- Layout pruefen (nach dem ersten Activated) --------------------
    mw = sys.modules["FreeCADGui"]._mw
    layout = sys.modules.get("swui.layout")
    if layout is None:
        print("  FEHLER: Activated() hat swui.layout nicht geladen")
        return False

    keep = ["InnerPanelBar"]  # fork: sin Archivo/Editar (look_sw), selector oculto (always_swui)
    if mw.visible_bars() != keep:
        print("  FEHLER: sichtbare Leisten", mw.visible_bars(), "erwartet", keep)
        return False
    print("  Layout   : sichtbar bleiben", mw.visible_bars())
    # Fork: íconos de acceso rápido en la barra de menú (quick_access.py)
    qa = sys.modules["swui.fork.quick_access"]

    def hooked(fn_, flag_):
        """¿Algún enganche de la cadena (cada uno guarda el anterior en _original) tiene la marca?"""
        while fn_ is not None:
            if getattr(fn_, flag_, False):
                return True
            fn_ = (fn_.__defaults__ or (None,))[0] if callable(fn_) else None
            fn_ = fn_ if callable(fn_) else None
        return False

    if (qa.COMMANDS != ("Std_New", "Std_Open", "Std_Save", "Std_Undo", "Std_Refresh")
            or not hooked(layout.enter, "_swui_quick") or not hooked(layout.leave, "_swui_quick")):
        print("  FEHLER: fork: acceso rápido (comandos / enganche a entrar y salir)")
        return False
    # Fork: usar siempre LikeSolidWorks UI
    asw = sys.modules["swui.fork.always_swui"]
    gen_p = sys.modules["FreeCAD"]._params.get("User parameter:BaseApp/Preferences/General", {})
    if (gen_p.get("AutoloadModule") != "LikeSolidWorksUIWorkbench" or not asw.should_return("PartDesignWorkbench")
            or asw.should_return("LikeSolidWorksUIWorkbench") or "SWUI_AlwaysSWUI" not in commands):
        print("  FEHLER: fork: usar siempre LikeSolidWorks UI (arranque / volver / comando)", gen_p.get("AutoloadModule"))
        return False
    commands["SWUI_AlwaysSWUI"].Activated(False)  # apagado: arranque anterior, selector visible
    off_ok = (gen_p.get("AutoloadModule") != "LikeSolidWorksUIWorkbench" and not asw.should_return("PartDesignWorkbench")
              and "Workbench" in mw.visible_bars())
    commands["SWUI_AlwaysSWUI"].Activated(True)
    if not off_ok or "Workbench" in mw.visible_bars() or gen_p.get("AutoloadModule") != "LikeSolidWorksUIWorkbench":
        print("  FEHLER: fork: apagar/prender 'usar siempre' desde el menú", off_ok, mw.visible_bars())
        return False

    op = sys.modules.get("swui.overlay_panels")
    fcp = sys.modules["FreeCAD"]._params
    left, right = fcp.get(op.DOCK_PARAMS + "OverlayLeft", {}), fcp.get(op.DOCK_PARAMS + "OverlayRight", {})
    others = [fcp.get(op.DOCK_PARAMS + g, {}).get("Widgets") for g in ("OverlayTop", "OverlayBottom")]
    # Fork (look_sw.py): nada superpuesto; el árbol va en un panel fijo con Tareas
    if (left.get("Widgets") != "" or left.get("Transparent") is not False or right.get("Widgets") != ""
            or others != ["", ""]):
        print("  FEHLER: fork: nada superpuesto (árbol en panel fijo)", left, right)
        return False
    qt = sys.modules["PySide.QtCore"].Qt
    by = {d.name: d for d in mw.docks}
    # Fork (swui/fork/panel_sw.py): árbol y Tareas en pestañas a la izquierda; informe abajo y oculto
    pnl_sw = sys.modules["swui.fork.panel_sw"]
    if (by["Tasks"].area is not qt.DockWidgetArea.LeftDockWidgetArea
            or by["Model"].area is not qt.DockWidgetArea.LeftDockWidgetArea
            or ("Model", "Tasks") not in mw.tabified
            or by["Report view"].area is not qt.DockWidgetArea.BottomDockWidgetArea
            or by["Report view"].visible or by["Report view"].floating or by["Tasks"].floating):
        print("  FEHLER: fork: árbol + Tareas en pestañas a la izquierda / informe abajo y oculto", mw.tabified)
        return False
    sk_view = fcp.get("User parameter:BaseApp/Preferences/Mod/Sketcher/View", {})
    if (sk_view.get("EdgeWidth"), sk_view.get("ConstructionWidth")) != (2, 1):
        print("  FEHLER: fork: líneas de croquis como SW (2 px / constructivas 1 px)", sk_view)
        return False
    out_params = fcp.get("User parameter:BaseApp/Preferences/OutputWindow", {})
    if [out_params.get(k_) for k_ in ("checkShowReportViewOnWarning", "checkShowReportViewOnError")] != [False, False]:
        print("  FEHLER: la Vista de informe se sigue abriendo sola", out_params)
        return False
    del mw.raised[:]
    mw.dialog_open = True
    pnl_sw._update(by["Tasks"], by["Model"])
    pnl_sw._update(by["Tasks"], by["Model"])  # sigue abierta: no vuelve a cambiar de pestaña
    mw.dialog_open = False
    pnl_sw._update(by["Tasks"], by["Model"])
    if mw.raised != ["Tasks", "Model"]:
        print("  FEHLER: fork: pestaña Tareas al abrir una operación, árbol al cerrarla", mw.raised)
        return False
    # Fork: velocidad de giro (swui/fork/orbit_speed.py)
    osp = sys.modules["swui.fork.orbit_speed"]
    if (osp.factor() != 1.5 or osp.scaled((100, 100), (110, 96), 1.5) != (115.0, 94.0)
            or osp.choice_text(1.5) != "x1,5" or osp.choice_text(1.0) != "x1 (como FreeCAD)"
            or "SWUI_OrbitSpeed" not in commands):
        print("  FEHLER: velocidad de giro (x1,5 de fábrica, movimiento agrandado, comando)")
        return False
    # Fork: teclas N y F (swui/fork/view_keys.py)
    vk = sys.modules["swui.fork.view_keys"]
    c30 = (0.0, -math.sin(math.radians(30)), -math.cos(math.radians(30)))  # mirando casi desde arriba
    near = vk.nearest_axis(c30)
    up_top = vk.straight_up((0, 0, -1), (0.2, 0.98, 0))  # vista superior, pantalla algo torcida
    flip = vk.face_direction((0, 0, 1), (0, 0, -1))  # ya de frente a la cara -> del otro lado
    front = vk.face_direction((0, -1, 0), c30)
    if vk.face_direction((0, 0, 1), (0, 0, -1), again=False) != (0.0, 0.0, -1.0):  # otra cara paralela: no dar vuelta
        print("  FEHLER: fork: N sobre otra cara ya de frente no debe darla vuelta")
        return False
    # F: ajuste de FreeCAD con la animación apagada solo mientras dura
    gui_vk = sys.modules["FreeCADGui"]
    view_p = sys.modules["FreeCAD"].ParamGet(vk.VIEW_PARAMS)
    seen_vk, old_msg_vk = [], getattr(gui_vk, "SendMsgToActiveView", None)
    view_d = sys.modules["FreeCAD"]._params.setdefault(vk.VIEW_PARAMS, {})
    view_saved = dict(view_d)
    try:
        gui_vk.SendMsgToActiveView = lambda m_: seen_vk.append((m_, view_p.GetBool(vk.ANIMATIONS, True)))
        view_p.SetBool(vk.ANIMATIONS, True)
        vk.fit_all()
        on_after = view_p.GetBool(vk.ANIMATIONS, False)
        view_p.SetBool(vk.ANIMATIONS, False)
        vk.fit_all()
        off_after = view_p.GetBool(vk.ANIMATIONS, True)
    finally:
        if old_msg_vk is None:
            del gui_vk.SendMsgToActiveView
        else:
            gui_vk.SendMsgToActiveView = old_msg_vk
        view_d.clear()
        view_d.update(view_saved)  # sin rastros: el test de salir del banco compara las preferencias
    if (seen_vk != [("ViewFit", False), ("ViewFit", False)] or not on_after or off_after
            or "SWUI_FitAll" not in commands or dict(vk.KEYS).get("F") != "SWUI_FitAll"):
        print("  FEHLER: fork: F sin animación (y preferencia devuelta)", seen_vk, on_after, off_after)
        return False
    # Atajos de FreeCAD que empiezan con F o N demoran la tecla suelta ~0,3 s
    if (not vk.clashes("F, S") or not vk.clashes("N, X") or vk.clashes("F") or vk.clashes("F3")
            or vk.clashes("V, F") or vk.clashes("Ctrl+F")):
        print("  FEHLER: fork: atajos que empiezan con F/N mal detectados")
        return False
    right_, up_, back_ = vk.camera_axes((0, 1, 0), (0, 0, 1))
    if (near != (0, 0, -1) or up_top != (0.0, 1.0, 0.0) or flip != (0.0, 0.0, 1.0) or front != (0.0, 1.0, 0.0)
            or vk.straight_up((0, 1, 0), (0, 0, 1)) != (0.0, 0.0, 1.0)
            or tuple(round(x, 9) for x in right_) != (1.0, 0.0, 0.0) or back_ != (0, -1, 0)
            or "SWUI_NormalTo" not in commands or len(vk._actions) != 2
            or not hooked(layout.enter, "_swui_keys") or not hooked(layout.leave, "_swui_keys")):
        print("  FEHLER: fork: teclas N y F (vista más cercana, arriba derecho, dar vuelta, comando)",
              near, up_top, flip, front, right_)
        return False
    # Fork: árbol de operaciones como SW (swui/fork/feature_tree.py, rebuild_keys.py, tree_dialogs.py)
    if not _check_feature_tree(commands, mw, layout, hooked):
        return False
    if not fcp[op.OWN_PARAMS].get(op.BACKUP_KEY):
        print("  FEHLER: keine Sicherung der Panel-Einstellungen")
        return False
    model_tree = [d for d in mw.docks if d.name == "Model"][0].trees[0]
    if op.TREE_TEXT not in model_tree.qss or "#f7f7f7" not in model_tree.qss:
        print("  FEHLER: fork: árbol sobre panel gris claro", model_tree.qss)
        return False
    print("  Layout   : fork: árbol y Tareas en pestañas a la izquierda (gris claro), informe abajo oculto")

    # --- Farbschema ---------------------------------------------------
    if not mw.qss.startswith(mw.ORIGINAL_QSS) or "SWUI_RibbonTabs" not in mw.qss:
        print("  FEHLER: Farbschema nicht angehängt")
        return False
    theme = sys.modules["swui.theme"]
    ok, why = _check_qss(theme.build_qss())
    if not ok:
        print("  FEHLER: Stylesheet fehlerhaft:", why)
        return False
    print("  Farben   : Stylesheet angehängt, Syntax OK (%d Regeln)" % theme.build_qss().count("{"))

    # --- 3D-Hintergrund ----------------------------------------------
    fc = sys.modules["FreeCAD"]
    vb = sys.modules["swui.view_background"]
    view = fc._params[VIEW]
    want_top = vb._packed(theme.COLORS["view_top"])
    if not (view.get("Gradient") is True and view.get("RadialGradient") is False
            and view.get("BackgroundColor2") == want_top
            and "BackgroundColor3" in view):
        print("  FEHLER: Verlauf nicht gesetzt", view)
        return False
    if not fc._params[vb.OWN_PARAMS].get(vb.BACKUP_KEY):
        print("  FEHLER: keine Absturz-Sicherung angelegt")
        return False
    sketch_keys = {
        "EditedEdgeColor": "sketch_open",
        "FullyConstraintElementColor": "sketch_defined",
        "ConstrainedDimColor": "sketch_dim",
        "ConstructionColor": "sketch_construction",
    }
    for key, color in sketch_keys.items():
        if view.get(key) != vb._packed(theme.COLORS[color]):
            print("  FEHLER: Skizzenfarbe %s nicht gesetzt" % key, view.get(key))
            return False
    print("  3D-Hgrd  : Verlauf gesetzt (oben %s), Sicherung angelegt" % theme.COLORS["view_top"])
    print("  Skizze   : unterbestimmt %s, bestimmt %s" % (theme.COLORS["sketch_open"], theme.COLORS["sketch_defined"]))

    # laufender "Text aufs Blatt"-Modus beim Verlassen beenden (sonst faengt das Blatt weiter Klicks ab)
    tn_d = sys.modules["swui.text_note"]
    closed_d = []
    tn_d._picker = types.SimpleNamespace(close=lambda: closed_d.append(1))
    log.clear()
    wb.Deactivated()
    if any(level == "ERR" for level, _ in log):
        print("  FEHLER in Deactivated():", log)
        return False
    if tn_d.picking() or closed_d != [1]:
        print("  FEHLER: Text-Platzierung nach Verlassen der Werkbank noch aktiv")
        return False
    all_bars = sorted(b.name for b in mw.toolbars)
    if mw.visible_bars() != all_bars or layout.is_active():
        print("  FEHLER: nach Verlassen nicht wiederhergestellt", mw.visible_bars())
        return False
    if any(k_ in fcp.get("User parameter:BaseApp/Preferences/OutputWindow", {})
           for k_ in ("checkShowReportViewOnWarning", "checkShowReportViewOnError")):
        print("  FEHLER: fork: preferencias de la Vista de informe no devueltas al salir")
        return False
    if fcp.get("User parameter:BaseApp/Preferences/Mod/Sketcher/View", {}):
        print("  FEHLER: fork: preferencias del croquis no devueltas al salir",
              fcp.get("User parameter:BaseApp/Preferences/Mod/Sketcher/View"))
        return False
    task = [d for d in mw.docks if d.name == "Tasks"][0]
    if task.area != "right":
        print("  FEHLER: Aufgaben-Panel nicht an alten Platz zurück:", task.area)
        return False
    if mw.qss != mw.ORIGINAL_QSS:
        print("  FEHLER: Stylesheet nach Verlassen nicht exakt zurück")
        return False
    if fc._params[VIEW] != ORIGINAL_VIEW or fc._params[vb.OWN_PARAMS].get(vb.BACKUP_KEY):
        print("  FEHLER: Ansichts-Einstellungen nicht exakt zurück", fc._params[VIEW])
        return False
    op = sys.modules["swui.overlay_panels"]
    if (fc._params[op.DOCK_PARAMS + "OverlayRight"] != ORIGINAL_OVERLAY_RIGHT
            or fc._params[op.DOCK_PARAMS + "OverlayLeft"] or fc._params[op.OWN_PARAMS].get(op.BACKUP_KEY)
            or fc._params[op.DOCK_PARAMS + "OverlayBottom"] or fc._params[op.DOCK_PARAMS + "OverlayTop"]):
        print("  FEHLER: Panel-Überlagerung nicht exakt zurück", fc._params[op.DOCK_PARAMS + "OverlayLeft"])
        return False
    if [d for d in mw.docks if d.name == "Model"][0].trees[0].qss != "/* FreeCAD-Baum */":
        print("  FEHLER: Baum-Schrift nicht zurück")
        return False
    if sys.modules["swui.assembly_mates"].is_installed():
        print("  FEHLER: Verknüpfungs-Panel nach Verlassen noch aktiv")
        return False
    if sys.modules["swui.context_sketch"].is_installed():
        print("  FEHLER: Symbol Skizze erstellen nach Verlassen noch aktiv")
        return False
    rb = sys.modules["swui.ribbon"]
    if rb.is_wanted():
        print("  FEHLER: Ribbon nach Verlassen noch gewünscht")
        return False
    rb._dock.hide.reset_mock()
    layout._restore_state_again()  # FreeCAD stellt verzögert wieder her ...
    if not rb._dock.hide.called:
        print("  FEHLER: Ribbon nach verzögertem Wiederherstellen nicht wieder ausgeblendet")
        return False
    rb._dock.hide.reset_mock()
    rb._wanted = True
    rb._hide_if_unwanted()  # in LikeSolidWorks UI: nichts ausblenden
    rb._wanted = False
    if rb._dock.hide.called:
        print("  FEHLER: Ribbon-Wächter blendet in LikeSolidWorks UI aus")
        return False
    print("  Verlassen: alle Leisten, Panels, Farben und 3D-Einstellungen wiederhergestellt")

    # Beenden von FreeCAD im SOLIDWORKS-Layout
    wb.Activated()
    layout._on_close()
    if mw.visible_bars() != all_bars:
        print("  FEHLER: beim Schliessen nicht wiederhergestellt", mw.visible_bars())
        return False
    if mw.qss != mw.ORIGINAL_QSS:
        print("  FEHLER: Stylesheet beim Schließen nicht zurück")
        return False
    if fc._params[VIEW] != ORIGINAL_VIEW:
        print("  FEHLER: 3D-Einstellungen beim Schließen nicht zurück")
        return False
    print("  Schließen: Originalzustand vor dem Speichern hergestellt")

    # ...und Schliessen abgebrochen: Layout muss wiederkommen
    layout._reenter_if_still_open()
    if mw.visible_bars() != keep:
        print("  FEHLER: nach abgebrochenem Schließen kein Layout", mw.visible_bars())
        return False
    if mw.qss.count("SWUI-THEME-BEGIN") != 1:
        print("  FEHLER: Farbschema nach Abbruch nicht genau einmal aktiv")
        return False
    print("  Abbruch  : Layout und Farben wieder angewendet")

    if mw.filters != 1:
        print("  FEHLER: Ereignisfilter %d-mal installiert" % mw.filters)
        return False

    wb.Deactivated()

    # Absturz im SOLIDWORKS-Layout: naechster Start muss aufraeumen.
    wb.Activated()
    vb._applied = False  # "neuer Prozess"
    vb.recover()
    if fc._params[VIEW] != ORIGINAL_VIEW:
        print("  FEHLER: nach Absturz nicht aufgeräumt", fc._params[VIEW])
        return False
    op._applied = False  # "neuer Prozess"
    op._tree_saved.clear()
    op.recover()
    if fc._params[op.DOCK_PARAMS + "OverlayRight"] != ORIGINAL_OVERLAY_RIGHT or fc._params[op.DOCK_PARAMS + "OverlayLeft"]:
        print("  FEHLER: Panel-Überlagerung nach Absturz nicht aufgeräumt")
        return False
    wb.Deactivated()
    if fc._params[VIEW] != ORIGINAL_VIEW:
        print("  FEHLER: Verlassen nach Wiederherstellung verändert Einstellungen")
        return False
    print("  Absturz  : Einstellungen beim nächsten Start zurückgesetzt")
    _ad = sys.modules.get("swui.assembly_drop")
    if _ad is not None:
        if _ad.is_installed():
            print("  FEHLER: Drop-Fänger nach Verlassen der Workbench noch angemeldet")
            return False
        # Abgemeldet greift er nie ein - auch nicht bei .FCStd auf eine Baugruppe
        _T = sys.modules["PySide.QtCore"].QEvent.Type
        _ev = types.SimpleNamespace(
            type=lambda: _T.DragEnter, acceptProposedAction=lambda: None,
            mimeData=lambda: types.SimpleNamespace(
                hasUrls=lambda: True, urls=lambda: ["/h/a/Welle.FCStd"]))
        _real_t = _ad.target_assembly
        _ad.target_assembly = lambda: types.SimpleNamespace(Label="Baugruppe1")
        try:
            _grab = _ad.handle_drag_event(_ev)
        finally:
            _ad.target_assembly = _real_t
        if _grab:
            print("  FEHLER: abgemeldeter Drop-Fänger übernimmt trotzdem ein Ereignis")
            return False
        _ad.install()  # Gegenprobe: angemeldet würde er übernehmen
        _ad.target_assembly = lambda: types.SimpleNamespace(Label="Baugruppe1")
        try:
            _grab_on = _ad.handle_drag_event(_ev)
        finally:
            _ad.target_assembly = _real_t
            _ad.uninstall()
        if not _grab_on:
            print("  FEHLER: Testereignis ungültig (angemeldet würde es auch nicht übernommen)")
            return False
    _qm2 = sys.modules.get("swui.qt_messages")
    if _qm2 is not None and _qm2._active:
        print("  FEHLER: Qt-Meldungsfilter nach Verlassen der Workbench noch aktiv")
        return False
        if sys.modules["FreeCAD"].ParamGet(_ad.OWN_PARAMS).GetString(_ad.BACKUP_KEY, ""):
            print("  FEHLER: Baugruppen-Einstellung nach Verlassen nicht zurückgesetzt")
            return False
    print("  Wechsel  : Activated/Deactivated OK")
    return True


def check_manifest():
    """package.xml passt zu InitGui.py und zu den Lizenzdateien (Addon-Manager prueft das auch)."""
    import re
    import xml.etree.ElementTree as ET

    ns = "{https://wiki.freecad.org/Package_Metadata}"
    try:
        root = ET.parse(os.path.join(ADDON, "package.xml")).getroot()
    except Exception as exc:
        print("  FEHLER: package.xml nicht lesbar: %s" % exc)
        return False
    ok = True
    cls = root.findtext("%scontent/%sworkbench/%sclassname" % (ns, ns, ns)) or ""
    with open(os.path.join(ADDON, "InitGui.py"), encoding="utf-8") as fh:
        src = fh.read()
    if not re.search(r"^class %s\(" % re.escape(cls), src, re.M) or not cls:
        print("  FEHLER: <classname> '%s' ist keine Klasse in InitGui.py" % cls)
        ok = False
    if '_WB_KEY = "%s"' % cls not in src:
        print("  FEHLER: _WB_KEY in InitGui.py passt nicht zu <classname> '%s'" % cls)
        ok = False
    # Werkbank-Name = MenuText in InitGui.py, und die Suche im Addon-Manager
    # (Name, Beschreibung, <tag>; Gross/klein egal) muss ihn finden.
    wb_name = (root.findtext("%scontent/%sworkbench/%sname" % (ns, ns, ns)) or "").strip()
    m = re.search(r'^\s*MenuText\s*=\s*"([^"]*)"', src, re.M)
    if not m or m.group(1) != wb_name:
        print("  FEHLER: Werkbank-Name '%s' passt nicht zu MenuText in InitGui.py" % wb_name)
        ok = False
    shown = (root.findtext(ns + "name") or "").strip()
    haystack = [shown, root.findtext(ns + "description") or ""] + [t.text or "" for t in root.findall(ns + "tag")]
    if not any(wb_name.lower() in h.lower() for h in haystack):
        print("  FEHLER: Suche nach '%s' findet das Paket '%s' im Addon-Manager nicht" % (wb_name, shown))
        ok = False
    # Version: package.xml und swui/version.py gleich, Datum im Format JJJJ-MM-TT
    vtxt = open(os.path.join(ADDON, "swui", "version.py"), encoding="utf-8").read()
    mv = re.search(r'^__version__\s*=\s*"([^"]+)"', vtxt, re.M)
    pkg_ver = (root.findtext(ns + "version") or "").strip()
    pkg_date = (root.findtext(ns + "date") or "").strip()
    if not mv or mv.group(1) != pkg_ver:
        print("  FEHLER: Version in package.xml (%s) und swui/version.py (%s) verschieden"
              % (pkg_ver, mv.group(1) if mv else "?"))
        ok = False
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", pkg_date):
        print("  FEHLER: <date> '%s' nicht im Format JJJJ-MM-TT" % pkg_date)
        ok = False
    repo = [u for u in root.findall(ns + "url") if u.get("type") == "repository"]
    if not repo or not (repo[0].text or "").startswith("https://") or not repo[0].get("branch"):
        print("  FEHLER: <url type=\"repository\" branch=\"…\"> fehlt oder unvollständig")
        ok = False
    # Freigabe ueber den Zweig "release" (tools/freigabe.sh); README-Link zeigt auf denselben Zweig
    readme_u = [u for u in root.findall(ns + "url") if u.get("type") == "readme"]
    if repo and (repo[0].get("branch") != "release" or not readme_u or "/blob/release/" not in (readme_u[0].text or "")):
        print("  FEHLER: Nutzer sollen den Zweig release bekommen (repository branch / readme-Link)")
        ok = False
    changelog = os.path.join(ADDON, "CHANGELOG.md")
    log_txt = open(changelog, encoding="utf-8").read() if os.path.isfile(changelog) else ""
    if not re.search(r"^## %s [—-] %s$" % (re.escape(pkg_ver), re.escape(pkg_date)), log_txt, re.M):
        print("  FEHLER: CHANGELOG.md ohne Eintrag '## %s — %s'" % (pkg_ver, pkg_date))
        ok = False
    script = os.path.join(ADDON, "tools", "freigabe.sh")
    sh = open(script, encoding="utf-8").read() if os.path.isfile(script) else ""
    order = [sh.find(s) for s in ('= "master" ]', "git status --porcelain", 'grep -q "^## $version " CHANGELOG.md',
                                  "refs/tags/v$version", "python3 tools/test_load.py", "git push -u origin release")]
    if not sh.startswith("#!/usr/bin/env bash") or "set -euo pipefail" not in sh or -1 in order or order != sorted(order):
        print("  FEHLER: tools/freigabe.sh fehlt oder prüft nicht alles vor dem Hochladen", order)
        ok = False
    for lic in root.findall(ns + "license"):
        f = lic.get("file")
        if not f or not os.path.isfile(os.path.join(ADDON, f)):
            print("  FEHLER: Lizenzdatei '%s' fehlt (%s)" % (f, lic.text))
            ok = False
    # Jede Quelldatei traegt die Code-Lizenz aus package.xml als SPDX-Kopfzeile
    code_lic = [l.text for l in root.findall(ns + "license") if l.get("file") == "LICENSE-Code"]
    want = "# SPDX-License-Identifier: %s" % (code_lic[0] if code_lic else "?")
    missing = []
    for base, dirs, files in os.walk(ADDON):
        dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
        for f in files:
            if f.endswith(".py"):
                p = os.path.join(base, f)
                with open(p, encoding="utf-8") as fh:
                    head = [fh.readline().rstrip("\n") for _ in range(5)]
                if want not in head:
                    missing.append(os.path.relpath(p, ADDON))
    if missing:
        print("  FEHLER: SPDX-Kopfzeile '%s' fehlt in: %s" % (want, ", ".join(sorted(missing))))
        ok = False
    # README deutsch + englisch: verweisen aufeinander, Markenhinweis in beiden
    for name_, other_, mark_ in (("README.md", "README_EN.md", "eingetragene Marke von Dassault"),
                                 ("README_EN.md", "README.md", "registered trademark of Dassault")):
        path_ = os.path.join(ADDON, name_)
        txt_ = open(path_, encoding="utf-8").read() if os.path.isfile(path_) else ""
        if "(%s)" % other_ not in txt_ or mark_ not in txt_:
            print("  FEHLER: %s fehlt, verweist nicht auf %s oder ohne Markenhinweis" % (name_, other_))
            ok = False
    if ok:
        print("  README   : deutsch und englisch, verweisen aufeinander, Markenhinweis")
        print("  Manifest : <classname> %s passt, Lizenzdateien vorhanden" % cls)
        print("  Lizenz   : SPDX-Kopfzeile in allen Quelldateien")
        print("  Version  : %s vom %s (package.xml = version.py)" % (pkg_ver, pkg_date))
        print("  Freigabe : Zweig release, CHANGELOG %s, freigabe.sh prüft master/gesichert/CHANGELOG/Tag/Test" % pkg_ver)
        print("  Manifest : Addon-Manager zeigt '%s', Suche nach '%s' findet es" % (shown, wb_name))
    return ok


# --- Hauptteil -------------------------------------------------------

print("Add-on:", ADDON)

results = {
    "getrennte Namensraeume": run(split_namespace=True),
    "ein Namensraum": run(split_namespace=False),
    "package.xml": check_manifest(),
}

print("\n" + "=" * 62)
for name, ok in results.items():
    print("  %-26s %s" % (name, "OK" if ok else "FEHLGESCHLAGEN"))

allok = all(results.values())
print("\nERGEBNIS:", "OK" if allok else "FEHLGESCHLAGEN")
sys.exit(0 if allok else 1)
