# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 Dominik Ladewig
"""
ribbon.py - Das Ribbon im Stil des SOLIDWORKS-CommandManagers.

Aufbau
------
Ein QDockWidget oben im FreeCAD-Hauptfenster. Darin ein QTabWidget mit
einem Reiter pro Eintrag in ribbon_layout.TABS. Jeder Reiter enthaelt
Gruppen, getrennt durch Trennstriche. Wie im SOLIDWORKS-CommandManager
gibt es drei Knopfarten:
  - grosse Knoepfe mit Text darunter (Hauptfunktionen)
  - Stapel kleiner Symbol-Knoepfe, 3 Zeilen hoch (Zeichenwerkzeuge)
  - Stapel kleiner Knoepfe mit Text daneben (Spiegeln, Muster ...)

Warum ein Dock und keine Toolbar: FreeCAD blendet beim Workbench-
Wechsel alle Toolbars aus, die es nicht selbst verwaltet. Ein Dock
mit eigenem Namen laesst es in Ruhe - wir steuern die Sichtbarkeit
selbst ueber show() und hide().

Die Knoepfe fuehren vorhandene FreeCAD-Befehle aus. Ob ein Knopf
anklickbar ist, fragt ein Timer regelmaessig bei FreeCAD nach - so
werden z.B. die Skizzen-Werkzeuge nur im Skizziermodus aktiv.

Absichtlich ohne Unterklassen von Qt-Klassen: Komposition statt
Vererbung haelt den Code testbar und robust gegen Qt5/Qt6-Unterschiede.
"""

import functools
import traceback

import FreeCAD
import FreeCADGui

from swui import ribbon_layout
from swui.compat import QtCore, QtGui, QtWidgets
from swui.i18n import N_, tr  # noqa: F401

DOCK_NAME = "SWUI_Ribbon"
ICON_SIZE = 32  # grosse Knoepfe (Text darunter)
SMALL_ICON_SIZE = 20  # kleine Knoepfe in Stapeln (wie im SW-CommandManager)
STACK_ROWS = 3  # Zeilen je Stapel-Spalte
REFRESH_MS = 500
SCROLL_STEP = 120  # Pixel je Klick auf die Pfeile eines zu breiten Reiters

# Modulzustand. Das Ribbon wird einmal gebaut und danach nur noch
# ein- und ausgeblendet.
_dock = None
_timer = None
_wanted = False  # soll das Ribbon gerade sichtbar sein? (nur in LikeSolidWorks UI)
_buttons = {}  # Knopf-ID -> QToolButton. ID = Befehl oder "Befehl#Index"
_flyouts = []  # Ausklappknoepfe: {"button", "variants", "current", "id"}
_toggles = []  # Umschaltknoepfe: {"button", "variants", "current"}
_skipped = []  # Befehle, die es nicht gibt
_tabs = None  # das QTabWidget des Ribbons
_tab_titles = []  # Reiternamen in Reihenfolge
_in_sketch = False  # wird gerade eine Skizze bearbeitet?
_tab_before_sketch = None  # Reiter vor dem Betreten der Skizze
_on_drawing = False  # ist gerade ein Zeichenblatt das aktive Fenster?
_scrollers = []  # je Reiter: Rahmen mit Pfeilen, siehe _scroller()

START_TAB = "Features"  # beim Start aufgeschlagen, auch wenn links davon Evaluieren steht
SKETCH_TAB = "Skizze"
DRAWING_TAB = "Zeichnungen"
DRAWING_VIEW_CLASS = "TechDrawGui::MDIViewPage"  # Fenster eines Zeichenblatts (1.1.4)
SKETCH_TYPES = ("Sketcher::SketchObject",)

# Hier merkt sich FreeCAD die zuletzt gewaehlte Variante je Ausklappknopf
# (bleibt ueber Neustarts erhalten).
PARAM_PATH = "User parameter:BaseApp/Preferences/Mod/SWUI/Ribbon"
_icon_index = None  # Symbolname -> Ressourcenpfad, einmal aufgebaut


def _tr(text):
    """Text in der eingestellten Sprache (swui/i18n.py) - Deutsch bleibt Deutsch."""
    try:
        from swui import i18n

        return i18n.tr(text)
    except Exception:
        return text


# --- Oeffentliche Schnittstelle --------------------------------------


def show():
    """Ribbon einblenden. Baut es beim ersten Aufruf."""
    global _dock, _wanted
    _wanted = True
    if _dock is None:
        _dock = _build()
    _dock.show()
    _timer.start()
    _refresh_enabled()


def hide():
    """Ribbon ausblenden. Der Inhalt bleibt erhalten."""
    global _wanted
    _wanted = False
    if _dock is not None:
        _dock.hide()
    if _timer is not None:
        _timer.stop()


def _on_visibility(visible):
    """
    Waechter: Taucht das Ribbon ausserhalb von LikeSolidWorks UI wieder auf,
    sofort wieder ausblenden. Das passiert, wenn FreeCAD beim Werkbank-
    Wechsel Fenster- und Panel-Zustaende zeitversetzt wiederherstellt
    (Dominiks Hinweis vom 17.10.).
    """
    if visible and not _wanted:
        QtCore.QTimer.singleShot(0, _hide_if_unwanted)


def _hide_if_unwanted():
    if _wanted or _dock is None:
        return
    try:
        if _dock.isVisible():
            _dock.hide()
    except Exception:
        pass


def is_wanted():
    return _wanted


def button_names():
    """IDs aller Knoepfe inkl. aller Varianten in Ausklappknoepfen (fuer Tests)."""
    names = list(_buttons)
    for fly in _flyouts:
        names.extend(v["key"] for v in fly["variants"])
    for tog in _toggles:
        names.extend(v["key"] for v in tog["variants"])
    return names


def toggles():
    """Die Umschaltknoepfe (fuer Tests)."""
    return list(_toggles)


def flyouts():
    """Die Ausklappknoepfe (fuer Tests)."""
    return list(_flyouts)


def skipped_commands():
    """Liste der Befehle, die mangels FreeCAD-Befehl fehlen."""
    return list(_skipped)


# --- Aufbau ----------------------------------------------------------


def _build():
    """Baut das Dock samt allen Reitern. Wird genau einmal aufgerufen."""
    global _timer

    _load_gui_modules()
    available = set(FreeCADGui.listCommands())

    main_window = FreeCADGui.getMainWindow()

    dock = QtWidgets.QDockWidget(main_window)
    dock.setObjectName(DOCK_NAME)
    dock.setWindowTitle(tr("SolidWorks Ribbon"))
    # Leeres Widget als Titelleiste = keine sichtbare Titelleiste.
    dock.setTitleBarWidget(QtWidgets.QWidget(dock))
    dock.setFeatures(QtWidgets.QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)

    tabs = QtWidgets.QTabWidget(dock)
    tabs.setObjectName("SWUI_RibbonTabs")
    tabs.setDocumentMode(True)
    # Wie im SOLIDWORKS-CommandManager: Reiter UNTER den Knoepfen.
    tabs.setTabPosition(QtWidgets.QTabWidget.TabPosition.South)

    global _tabs
    _tabs = tabs
    for tab_title, groups in ribbon_layout.TABS:
        page = _build_page(tabs, groups, available)
        tabs.addTab(page, _tr(tab_title))
        _tab_titles.append(tab_title)  # intern immer der deutsche Name (Logik)
    if START_TAB in _tab_titles:
        tabs.setCurrentIndex(_tab_titles.index(START_TAB))
    try:
        tabs.currentChanged.connect(lambda *_a: _fit_current())
    except Exception:
        pass

    dock.setWidget(tabs)
    main_window.addDockWidget(QtCore.Qt.DockWidgetArea.TopDockWidgetArea, dock)
    try:
        dock.visibilityChanged.connect(_on_visibility)
    except Exception:
        pass

    try:
        from swui import i18n

        i18n.add_listener(_on_language)
    except Exception:
        pass

    _timer = QtCore.QTimer(dock)
    _timer.setInterval(REFRESH_MS)
    _timer.timeout.connect(_refresh_enabled)

    if _skipped:
        FreeCAD.Console.PrintWarning(
            tr("[SWUI] Ribbon: %d Befehl(e) in dieser FreeCAD-Version nicht "
            "gefunden und ausgelassen: %s\n") % (len(_skipped), ", ".join(_skipped))
        )
    FreeCAD.Console.PrintMessage(
        tr("[SWUI] Ribbon aufgebaut: %d Knöpfe und %d Ausklappknöpfe in %d Reitern.\n")
        % (len(_buttons), len(_flyouts), len(ribbon_layout.TABS))
    )
    return dock


def _build_page(parent, groups, available):
    """Ein Reiter: Knopfgruppen nebeneinander, getrennt durch Striche."""
    page = QtWidgets.QWidget(parent)
    row = QtWidgets.QHBoxLayout(page)
    row.setContentsMargins(4, 2, 4, 2)
    row.setSpacing(2)

    first_group = True
    for group in groups:
        widgets = []
        for entry in group:
            w = _build_entry(page, entry, available)
            if w is not None:
                widgets.append(w)

        # Leere Gruppen (alle Befehle fehlen) erzeugen keinen Strich.
        if not widgets:
            continue
        if not first_group:
            row.addWidget(_make_separator(page))
        first_group = False
        for w in widgets:
            row.addWidget(w)

    row.addStretch(1)
    return _scroller(parent, page)


# --- Kleine Bildschirme ----------------------------------------------
#
# Ohne Rahmen bestimmt der BREITESTE Reiter die Mindestbreite des ganzen
# FreeCAD-Fensters (QTabWidget nimmt das Maximum aller Seiten): bei
# 1366 px Bildschirmbreite und spanischen/deutschen Beschriftungen ragt
# das Fenster rechts ueber den Rand (Aufgaben-Panel abgeschnitten).
# Deshalb steckt jeder Reiter in einem waagerecht verschiebbaren Rahmen.
# Passt er nicht, zuerst wie in SOLIDWORKS ohne "grosse Knoepfe mit
# Text" (nur Symbol, Name im Tooltip); passt er dann noch nicht, Pfeile
# links/rechts zum Verschieben.


def _scroller(parent, page):
    """Reiterseite -> Rahmen (Pfeil links, verschiebbarer Bereich, Pfeil rechts)."""
    box = QtWidgets.QWidget(parent)
    box.setObjectName("SWUI_RibbonPage")
    row = QtWidgets.QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(0)
    area = QtWidgets.QScrollArea(box)
    area.setObjectName("SWUI_RibbonScroll")
    area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidgetResizable(True)
    area.setWidget(page)
    sc = {"box": box, "area": area, "page": page, "large": None, "compact": False,
          "full_w": None, "compact_w": None, "avail": None}
    sc["left"] = _make_arrow(box, sc, -1)
    sc["right"] = _make_arrow(box, sc, 1)
    row.addWidget(sc["left"])
    row.addWidget(area, 1)
    row.addWidget(sc["right"])
    try:
        area.horizontalScrollBar().rangeChanged.connect(lambda *_a: _fit(sc))
    except Exception:
        pass
    _scrollers.append(sc)
    return box


def _make_arrow(parent, sc, direction):
    arrow = QtWidgets.QToolButton(parent)
    arrow.setObjectName("SWUI_RibbonArrow")
    arrow.setArrowType(QtCore.Qt.ArrowType.LeftArrow if direction < 0 else QtCore.Qt.ArrowType.RightArrow)
    arrow.setAutoRaise(True)
    arrow.setAutoRepeat(True)
    arrow.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Expanding)
    arrow.clicked.connect(functools.partial(_scroll, sc, direction))
    arrow.hide()
    return arrow


def _scroll(sc, direction, *_args):
    bar = sc["area"].horizontalScrollBar()
    bar.setValue(bar.value() + direction * SCROLL_STEP)


def _min_width(page):
    """Mindestbreite der Seite in der aktuellen Knopfart (Layout neu berechnet)."""
    lay = page.layout()
    lay.invalidate()
    lay.activate()
    return lay.minimumSize().width()


def _large_buttons(page):
    """Grosse Knoepfe (Text unter dem Symbol) einer Seite mit ihrem Tooltip."""
    under = QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon
    return [(b, b.toolTip()) for b in page.findChildren(QtWidgets.QToolButton) if b.toolButtonStyle() == under]


def _set_compact(sc, compact):
    """Grosse Knoepfe nur mit Symbol (compact) oder wieder mit Text darunter."""
    if sc["large"] is None:
        sc["large"] = _large_buttons(sc["page"])
    style = (QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly if compact
             else QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    for button, tip in sc["large"]:
        button.setToolButtonStyle(style)
        name = _menu_text(button.text())
        button.setToolTip(name + ("\n" + tip if tip and tip != name else "") if compact else tip)
    sc["compact"] = compact


def _fit(sc):
    """Knopfart und Pfeile der verfuegbaren Breite anpassen (bei Groessenaenderung)."""
    try:
        avail = sc["box"].width()
        if avail <= 0 or avail == sc["avail"]:
            return
        sc["avail"] = avail
        if sc["full_w"] is None:
            sc["full_w"] = _min_width(sc["page"])
        compact = sc["full_w"] > avail
        if compact != sc["compact"]:
            _set_compact(sc, compact)
        if compact and sc["compact_w"] is None:
            sc["compact_w"] = _min_width(sc["page"])
        need = sc["compact_w"] if compact else sc["full_w"]
        over = need > avail
        sc["left"].setVisible(over)
        sc["right"].setVisible(over)
        sc["area"].setFixedHeight(sc["page"].minimumSizeHint().height())
    except Exception:
        pass


def _fit_current():
    try:
        index = _tabs.currentIndex()
        if 0 <= index < len(_scrollers):
            _fit(_scrollers[index])
    except Exception:
        pass


def _build_entry(parent, entry, available, small=False, beside=False):
    """
    Ein Layout-Eintrag -> Widget (oder None, wenn kein Befehl existiert).

    small/beside: innerhalb eines Stapels - kleines Symbol, ohne Text
    (beside=False) oder mit Text daneben (beside=True).
    """
    size = SMALL_ICON_SIZE if small else ICON_SIZE
    show_text = beside or not small
    if isinstance(entry, dict) and "language" in entry:
        return _make_language_button(parent)
    if isinstance(entry, dict) and "stack" in entry:
        return _make_stack(parent, entry, available)
    if isinstance(entry, dict) and "flyout" in entry:
        variants = [_resolve(e, available) for e in entry["flyout"]]
        variants = [v for v in variants if v is not None]
        if not variants:
            return None
        return _make_flyout(parent, variants, icon_size=size, show_text=show_text, beside=beside,
                            title=entry.get("title"))
    if isinstance(entry, dict) and "toggle" in entry:
        variants = [_resolve(e, available) for e in entry["toggle"]]
        if any(v is None for v in variants):
            variants = [v for v in variants if v is not None]
            if not variants:
                return None
            return _make_button(parent, *variants[0])
        return _make_toggle(parent, variants)
    resolved = _resolve(entry, available)
    if resolved is None:
        return None
    return _make_button(parent, *resolved, icon_size=size, show_text=show_text, beside=beside)


def _make_stack(parent, entry, available):
    """
    Stapel wie im SW-CommandManager: kleine Knoepfe spaltenweise,
    STACK_ROWS Zeilen hoch. style "icon" = nur Symbol, "text" = Symbol
    mit Text daneben.
    """
    beside = entry.get("style") == "text"
    box = QtWidgets.QWidget(parent)
    box.setObjectName("SWUI_RibbonStack")
    grid = QtWidgets.QGridLayout(box)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(1)
    grid.setVerticalSpacing(1)
    n = 0
    for sub in entry["stack"]:
        w = _build_entry(box, sub, available, small=True, beside=beside)
        if w is None:
            continue
        grid.addWidget(w, n % STACK_ROWS, n // STACK_ROWS)
        n += 1
    return box if n else None


def _resolve(entry, available):
    """
    (Befehl, Beschriftung, opts) fuer einen Layout-Eintrag - oder None,
    wenn weder der Befehl noch einer seiner Ersatzbefehle existiert.
    """
    command, label = entry[0], entry[1]
    opts = entry[2] if len(entry) > 2 else {}
    if command in available:
        return command, label, opts
    alt = next((c for c in opts.get("fallback", ()) if c in available), None)
    if alt is None:
        _skipped.append(command)
        return None
    FreeCAD.Console.PrintLog("[SWUI] Ribbon: %s nicht vorhanden, nutze %s\n" % (command, alt))
    return alt, label, opts


def button_id(command, opts):
    """Eindeutige ID eines Knopfes - Gruppenbefehle haben mehrere."""
    index = opts.get("index")
    return command if index is None else "%s#%d" % (command, index)


def _style_button(button, icon_size, show_text, beside=False):
    """Gemeinsame Optik: gross mit Text darunter, klein ohne Text oder klein mit Text daneben."""
    if show_text and beside:
        button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
    elif show_text:
        button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
    else:
        button.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonIconOnly)
    button.setIconSize(QtCore.QSize(icon_size, icon_size))
    button.setAutoRaise(True)


def _make_button(parent, command, label, opts, icon_size=ICON_SIZE, show_text=True, register=True,
                 beside=False):
    """
    Ein Knopf fuer einen FreeCAD-Befehl.

    icon_size / show_text: Ribbon = gross mit Text, Heads-up = klein ohne.
    register: nur Ribbon-Knoepfe werden angemeldet (Aktiv-Status, Tests).
    """
    key = button_id(command, opts)
    index = opts.get("index")

    button = QtWidgets.QToolButton(parent)
    button.setObjectName("SWUI_Btn_" + key.replace("#", "_"))
    _style_button(button, icon_size, show_text, beside)
    text = _tr(label)
    button.setText(_menu_text(text) if beside else text)

    info = _command_info(command)
    button.setIcon(_command_icon(command, info, opts))
    tooltip = _tr(_strip_html(info.get("toolTip") or info.get("menuText") or command))
    if index is not None or not show_text:
        tooltip = _menu_text(text)
    button.setToolTip(tooltip)

    button.clicked.connect(functools.partial(_run, command, index))
    if register:
        _buttons[key] = button
    return button


def _make_flyout(parent, variants, icon_size=ICON_SIZE, show_text=True, register=True, param_prefix="",
                 beside=False, title=None):
    """
    Ausklappknopf wie in SOLIDWORKS: Klick auf das Symbol startet die
    aktuelle Variante, der Pfeil daneben oeffnet das Menue mit allen.
    Eine im Menue gewaehlte Variante wird ausgefuehrt UND zur neuen
    aktuellen - auch ueber einen Neustart hinweg.

    param_prefix trennt die gemerkten Varianten verschiedener Leisten
    (z.B. Heads-up vs. Ribbon), auch wenn sie mit demselben Befehl beginnen.
    """
    button = QtWidgets.QToolButton(parent)
    _style_button(button, icon_size, show_text, beside)
    button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.MenuButtonPopup)

    # title: feste Beschriftung (z. B. "Formen"), das Symbol zeigt die zuletzt gewaehlte Variante
    fly = {"button": button, "variants": [], "current": 0, "show_text": show_text, "beside": beside, "title": title}
    menu = QtWidgets.QMenu(button)
    for i, (command, label, opts) in enumerate(variants):
        info = _command_info(command)
        icon = _command_icon(command, info, opts)
        tip = _tr(_strip_html(info.get("toolTip") or info.get("menuText") or command))
        fly["variants"].append(
            {
                "command": command,
                "label": label,
                "index": opts.get("index"),
                "icon": icon,
                "tooltip": tip,
                "key": button_id(command, opts),
            }
        )
        action = menu.addAction(icon, _menu_text(_tr(label)))
        action.triggered.connect(functools.partial(_choose_variant, fly, i))
    fly["id"] = param_prefix + fly["variants"][0]["key"]
    button.setMenu(menu)
    button.clicked.connect(functools.partial(_run_flyout, fly))

    _set_variant(fly, _remembered_variant(fly))
    if register:
        _flyouts.append(fly)
    return button


def _make_toggle(parent, variants):
    """
    Umschaltknopf wie "Skizze" in SOLIDWORKS: ausserhalb einer Skizze
    Variante 0 (Skizze anlegen), beim Bearbeiten einer Skizze Variante 1
    (Skizze beenden). Gleicher Platz, anderer Befehl.
    """
    button = QtWidgets.QToolButton(parent)
    _style_button(button, ICON_SIZE, True)
    tog = {"button": button, "variants": [], "current": -1}
    for command, label, opts in variants:
        info = _command_info(command)
        tog["variants"].append(
            {
                "command": command,
                "label": label,
                "index": opts.get("index"),
                "icon": _command_icon(command, info, opts),
                "tooltip": _tr(_strip_html(info.get("toolTip") or info.get("menuText") or command)),
                "key": button_id(command, opts),
            }
        )
    button.clicked.connect(functools.partial(_run_toggle, tog))
    _toggles.append(tog)
    _set_toggle(tog, 0)
    return button


def _set_toggle(tog, i):
    if tog["current"] == i:
        return
    tog["current"] = i
    v = tog["variants"][i]
    b = tog["button"]
    b.setObjectName("SWUI_Tog_" + v["key"].replace("#", "_"))
    b.setText(_tr(v["label"]))
    b.setIcon(v["icon"])
    b.setToolTip(v["tooltip"])


def _run_toggle(tog, *_args):
    v = tog["variants"][tog["current"]]
    _run(v["command"], v["index"])


def _menu_text(label):
    """
    Knopf-Beschriftung einzeilig fuers Menue:
      'Mittelpunkt-\\nrechteck' -> 'Mittelpunktrechteck'  (Silbentrennung)
      '3-Punkt-\\nKreis'        -> '3-Punkt-Kreis'        (echter Bindestrich)
      'Abgerundetes\\nRechteck' -> 'Abgerundetes Rechteck'
    """
    import re

    label = re.sub(r"-\n(?=[a-zäöüß])", "", label)
    label = label.replace("-\n", "-")
    return label.replace("\n", " ")


def _set_variant(fly, i):
    """Macht Variante i zur angezeigten und per Klick ausgefuehrten."""
    v = fly["variants"][i]
    fly["current"] = i
    button = fly["button"]
    button.setObjectName("SWUI_Fly_" + v["key"].replace("#", "_"))
    text = _tr(v["label"])
    shown = _tr(fly["title"]) if fly.get("title") else text
    button.setText(_menu_text(shown) if fly.get("beside") else shown)
    button.setIcon(v["icon"])
    name = v["tooltip"] if fly.get("show_text", True) else _menu_text(text)
    if fly.get("title"):
        name = "%s: %s" % (_menu_text(_tr(fly["title"])), _menu_text(text))
    button.setToolTip(name + _tr("\n(Pfeil rechts: weitere Varianten)"))


def _choose_variant(fly, i, *_args):
    """Variante aus dem Menue gewaehlt: merken und ausfuehren."""
    _set_variant(fly, i)
    _remember_variant(fly)
    v = fly["variants"][i]
    _run(v["command"], v["index"])


def _run_flyout(fly, *_args):
    """Klick auf den Ausklappknopf selbst: aktuelle Variante ausfuehren."""
    v = fly["variants"][fly["current"]]
    _run(v["command"], v["index"])


def _remembered_variant(fly):
    """Index der zuletzt gewaehlten Variante, sonst 0."""
    try:
        saved = FreeCAD.ParamGet(PARAM_PATH).GetString(fly["id"], "")
    except Exception:
        return 0
    for i, v in enumerate(fly["variants"]):
        if v["key"] == saved:
            return i
    return 0


def _remember_variant(fly):
    try:
        key = fly["variants"][fly["current"]]["key"]
        FreeCAD.ParamGet(PARAM_PATH).SetString(fly["id"], key)
    except Exception:
        pass


# --- Sprache (Knopf "Language" im Reiter Evaluieren) -----------------


LANGUAGE_ICON = "sketch/e_language"
_language_button = None
_language_entries = []  # [(Code, Text, angehakt)] - wie im Menue (fuer Tests)


def _make_language_button(parent):
    """
    Knopf "Language" mit Ausklappmenue (Dominik, 18.10.): Automatisch (wie
    FreeCAD) und alle Sprachen aus swui/lang/. Der Knopf heisst in jeder
    Sprache gleich, damit man ihn auch in einer fremden Sprache findet.
    """
    global _language_button
    from swui import i18n

    button = QtWidgets.QToolButton(parent)
    button.setObjectName("SWUI_Btn_Language")
    _style_button(button, ICON_SIZE, True)
    button.setText(i18n.BUTTON_TEXT)
    button.setToolTip(i18n.BUTTON_TIP)
    button.setIcon(_command_icon(None, {}, {"svg": LANGUAGE_ICON}))
    button.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
    menu = QtWidgets.QMenu(button)
    # Qt6: QActionGroup in QtGui, Qt5: in QtWidgets
    group_cls = getattr(QtGui, "QActionGroup", None) or getattr(QtWidgets, "QActionGroup")
    group = group_cls(menu)
    group.setExclusive(True)
    chosen = i18n.setting()
    names = dict(i18n.choices())
    del _language_entries[:]
    auto_text = "%s (%s)" % (_tr("Automatisch"), names.get(i18n.resolve(i18n.AUTO), i18n.resolve(i18n.AUTO)))
    for code, text in [(i18n.AUTO, auto_text)] + i18n.choices():
        action = menu.addAction(text)
        action.setCheckable(True)
        action.setChecked(code == chosen)
        action.setData(code)
        group.addAction(action)
        action.triggered.connect(functools.partial(_pick_language, code))
        _language_entries.append((code, text, code == chosen))
    button.setMenu(menu)
    _language_button = button
    return button


def language_menu():
    """[(Code, Text, angehakt)] des Language-Menues (fuer Tests)."""
    return list(_language_entries)


def _pick_language(code, *_args):
    try:
        from swui import i18n

        i18n.set_setting(code)
    except Exception:
        FreeCAD.Console.PrintError(tr("[SWUI] Sprache: %s\n") % traceback.format_exc())


def _on_language(_before, _after):
    """Sprache gewechselt: Ribbon neu aufbauen - erst nach dem Menue-Klick
    (der Knopf, der das ausloest, wird dabei ersetzt)."""
    QtCore.QTimer.singleShot(0, rebuild)


def rebuild():
    """Ribbon in der aktuellen Sprache neu aufbauen; Reiter und Sichtbarkeit bleiben."""
    global _dock, _tabs
    if _dock is None:
        return
    current = _tabs.currentIndex() if _tabs is not None else 0
    old = _dock
    try:
        if _timer is not None:
            _timer.stop()
    except Exception:
        pass
    _buttons.clear()
    del _flyouts[:]
    del _toggles[:]
    del _skipped[:]
    del _tab_titles[:]
    del _scrollers[:]
    # Einzeln abgesichert: Scheitert ein Schritt, wird das alte Dock trotzdem entsorgt
    for step in (lambda: old.hide(),
                 lambda: FreeCADGui.getMainWindow().removeDockWidget(old),
                 lambda: old.setParent(None),
                 lambda: old.deleteLater()):
        try:
            step()
        except Exception:
            pass
    _dock = _build()
    try:
        _tabs.setCurrentIndex(max(0, min(current, _tabs.count() - 1)))
    except Exception:
        pass
    try:
        from swui.commands import free_rotate

        free_rotate._last_tip = None  # Grund-Tooltip am neuen Knopf wieder setzen
    except Exception:
        pass
    if _wanted:
        _dock.show()
        _timer.start()
        _refresh_enabled()
    else:
        _dock.hide()


def _make_separator(parent):
    """Senkrechter Trennstrich zwischen zwei Gruppen."""
    line = QtWidgets.QFrame(parent)
    line.setObjectName("SWUI_RibbonSeparator")
    line.setFrameShape(QtWidgets.QFrame.Shape.VLine)
    line.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
    return line


# --- Anbindung an FreeCAD-Befehle ------------------------------------


def _load_gui_modules():
    """
    Laedt die GUI-Module von Sketcher und PartDesign.

    Ohne das existieren deren Befehle nicht, solange der Benutzer die
    jeweilige Workbench noch nie aktiviert hat.
    """
    for name in ribbon_layout.REQUIRED_GUI_MODULES:
        try:
            __import__(name)
        except Exception as exc:
            FreeCAD.Console.PrintWarning(
                tr("[SWUI] Modul %s nicht ladbar: %s\n") % (name, exc)
            )
    # Baugruppen-Befehle (Python-Module der Assembly-Werkbank). Fehlt die
    # Werkbank, fehlen nur diese Knoepfe - Meldung im Ausgabefenster.
    missing = []
    for name in getattr(ribbon_layout, "ASSEMBLY_COMMAND_MODULES", ()):
        try:
            __import__(name)
        except Exception:
            missing.append(name)
    if missing:
        FreeCAD.Console.PrintLog(
            "[SWUI] Baugruppen-Module nicht ladbar: %s\n" % ", ".join(missing)
        )


def _command_info(command):
    """getInfo() eines FreeCAD-Befehls, oder leeres dict bei Fehlern."""
    try:
        return FreeCADGui.Command.get(command).getInfo() or {}
    except Exception:
        return {}


def _command_icon(command, info, opts):
    """
    Symbol eines Befehls. Vier Wege, der erste Treffer gewinnt:

    1. Die QAction, die FreeCAD fuer den Befehl angelegt hat (bei
       Gruppenbefehlen die des Unterpunkts). Existiert nur, wenn der
       Befehl schon einmal in einer Leiste/einem Menue stand.
    2. Suche nach Dateinamen in FreeCADs eingebauten Ressourcen -
       REKURSIV. Noetig, weil z.B. die Sketcher-Symbole in
       Unterordnern liegen (:/icons/geometry/...), die PartDesign-
       Symbole aber direkt unter :/icons/.
    3. FreeCADGui.getIcon() - zuletzt, weil es bei unbekannten Namen
       ein rotes Platzhalter-Kreuz statt "nichts" liefern kann.
    """
    # 0. Eigenes Add-on-Symbol (resources/icons/<svg>.svg) hat Vorrang -
    #    nur im Ribbon; FreeCADs eigene Leisten bleiben unveraendert.
    if opts.get("svg"):
        try:
            from swui import paths

            path = paths.icon(opts["svg"])
            if path:
                icon = QtGui.QIcon(path)
                if not icon.isNull():
                    return icon
        except Exception:
            pass

    index = opts.get("index")
    try:
        actions = FreeCADGui.Command.get(command).getAction() or []
        if index is not None and len(actions) > index:
            candidates = [actions[index]]
        elif index is None and actions:
            candidates = [actions[0]]
        else:
            candidates = []
        for action in candidates:
            icon = action.icon()
            if not icon.isNull():
                return icon
    except Exception:
        pass

    names = [n for n in (opts.get("icon"), info.get("pixmap")) if n]

    # Eigene Befehle geben einen Dateipfad als Symbol an.
    import os

    for name in names:
        if os.path.isabs(name) and os.path.isfile(name):
            icon = QtGui.QIcon(name)
            if not icon.isNull():
                return icon

    index_map = _resource_icons()
    for name in names:
        path = index_map.get(name) or index_map.get(name.lower())
        if path:
            icon = QtGui.QIcon(path)
            if not icon.isNull():
                return icon

    get_icon = getattr(FreeCADGui, "getIcon", None)
    if get_icon is not None:
        for name in names:
            try:
                icon = get_icon(name)
                if icon is not None and not icon.isNull():
                    return QtGui.QIcon(icon)
            except Exception:
                continue
    return QtGui.QIcon()


def _resource_icons():
    """
    Verzeichnis aller Symbole in FreeCADs Qt-Ressourcen.

    Schluessel: Dateiname ohne Endung (zusaetzlich kleingeschrieben).
    Wird einmal aufgebaut. Begrenzt auf MAX Eintraege, damit eine
    fehlerhafte Umgebung nie in eine Endlosschleife laeuft.
    """
    global _icon_index
    if _icon_index is not None:
        return _icon_index

    _icon_index = {}
    max_entries = 50000
    try:
        flags = QtCore.QDirIterator.IteratorFlag.Subdirectories
        it = QtCore.QDirIterator(":/icons", flags)
        count = 0
        while it.hasNext() and count < max_entries:
            count += 1
            path = it.next()
            if not isinstance(path, str):
                break
            base = path.rsplit("/", 1)[-1]
            stem = base.rsplit(".", 1)[0]
            if stem and stem not in _icon_index:
                _icon_index[stem] = path
                _icon_index.setdefault(stem.lower(), path)
    except Exception as exc:
        FreeCAD.Console.PrintLog("[SWUI] Symbolsuche nicht moeglich: %s\n" % exc)
    return _icon_index


def _run(command, index=None, *_args):
    """
    Knopfdruck: FreeCAD-Befehl ausfuehren.

    index: Unterpunkt eines Gruppenbefehls oder None.
    *_args faengt das 'checked'-Argument von Qt ab.
    """
    # Ein anderer Ribbon-Befehl beendet laufende eigene Werkzeuge.
    if command != "SWUI_Centerline":
        try:
            from swui.commands import centerline

            centerline.stop()
        except Exception:
            pass
    if command != "SWUI_MidpointLine":
        try:
            from swui.commands import midpoint_line

            midpoint_line.stop()
        except Exception:
            pass
    # Feature-Knopf bei offener Skizze: erst Skizze beenden, dann
    # Feature mit dieser Skizze starten (wie SOLIDWORKS).
    if index is None:
        try:
            from swui import from_sketch

            if from_sketch.handle(command):
                _pick_plane_call("_disarm")  # Feature laeuft schon mit dieser Skizze
                return
        except Exception as exc:
            FreeCAD.Console.PrintWarning(tr("[SWUI] Austragen aus Skizze: %s\n") % exc)
        # Skizze / Feature ohne Auswahl: erst Ebene oder ebene Flaeche waehlen (wie SOLIDWORKS)
        if _pick_plane_call("handle", command):
            return
    try:
        if index is None:
            FreeCADGui.runCommand(command)
        else:
            FreeCADGui.runCommand(command, index)
    except Exception as exc:
        FreeCAD.Console.PrintError(
            tr("[SWUI] Befehl %s fehlgeschlagen: %s\n") % (command, exc)
        )


def _pick_plane_call(name, *args):
    try:
        from swui import pick_plane

        return getattr(pick_plane, name)(*args)
    except Exception:
        FreeCAD.Console.PrintWarning(tr("[SWUI] Ebene wählen: %s\n") % traceback.format_exc())
        return False


def _check_context():
    """
    Wie in SOLIDWORKS: Beim Betreten einer Skizze springt das Ribbon auf
    den Reiter "Skizze", beim Verlassen zurueck auf den vorherigen.

    Gewechselt wird nur beim UEBERGANG. Klickt der Benutzer waehrend der
    Skizze selbst einen anderen Reiter an, bleibt der stehen.
    """
    global _in_sketch, _tab_before_sketch
    if _tabs is None or SKETCH_TAB not in _tab_titles:
        return
    _check_drawing()

    now = _editing_sketch()
    if now == _in_sketch:
        return
    _in_sketch = now

    if now:
        _tab_before_sketch = _tabs.currentIndex()
        _tabs.setCurrentIndex(_tab_titles.index(SKETCH_TAB))
    elif _tab_before_sketch is not None:
        _tabs.setCurrentIndex(_tab_before_sketch)
        _tab_before_sketch = None


def _check_drawing():
    """Zeichenblatt wird aktives Fenster -> Reiter "Zeichnungen" (nur beim Uebergang)."""
    global _on_drawing
    if DRAWING_TAB not in _tab_titles:
        return
    now = _drawing_active()
    if now:
        # Ansichten mit einem Linksklick ziehen (auch auf Kanten) - jedes Blatt-Fenster
        try:
            from swui import page_drag

            page_drag.attach_active()
        except Exception:
            pass
    if now == _on_drawing:
        return
    _on_drawing = now
    if now:
        _tabs.setCurrentIndex(_tab_titles.index(DRAWING_TAB))
        # Bestehende Zeichnungen: Ansichten verschiebbar machen (Achse bleibt verbunden)
        try:
            from swui import proj_views

            proj_views.freeze_doc(FreeCAD.ActiveDocument)
        except Exception:
            pass
        # Bestehende Zeichnungen: FreeCAD-Namen im Baum durch SW-Namen ersetzen (9f)
        try:
            from swui import naming

            naming.refresh_drawing(FreeCAD.ActiveDocument)
        except Exception:
            pass



def _drawing_active():
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        sub = mdi.activeSubWindow() if mdi is not None else None
        widget = sub.widget() if sub is not None else None
        return widget is not None and widget.metaObject().className() == DRAWING_VIEW_CLASS
    except Exception:
        return False


def _editing_sketch():
    """True, wenn im aktiven Dokument gerade eine Skizze bearbeitet wird."""
    try:
        gui_doc = FreeCADGui.ActiveDocument
        if gui_doc is None:
            return False
        vp = gui_doc.getInEdit()
        if vp is None:
            return False
        return vp.Object.TypeId in SKETCH_TYPES
    except Exception:
        return False


def _refresh_enabled():
    """
    Laeuft alle REFRESH_MS: Reiter dem Kontext anpassen und fuer jeden
    Knopf bei FreeCAD nachfragen, ob er gerade anwendbar ist.
    """
    _check_context()
    _fit_current()
    for key, button in _buttons.items():
        button.setEnabled(_is_active(key.split("#", 1)[0]))
    for fly in _flyouts:
        v = fly["variants"][fly["current"]]
        fly["button"].setEnabled(_is_active(v["command"]))
    editing = _editing_sketch()
    for tog in _toggles:
        _set_toggle(tog, 1 if (editing and len(tog["variants"]) > 1) else 0)
        v = tog["variants"][tog["current"]]
        tog["button"].setEnabled(_is_active(v["command"]))


def _is_active(command):
    try:
        return bool(FreeCADGui.Command.get(command).isActive())
    except Exception:
        return True  # im Zweifel anklickbar lassen


def _strip_html(text):
    """FreeCAD-Tooltips enthalten manchmal HTML - fuer Tooltips entfernen."""
    import re

    return re.sub(r"<[^>]+>", "", text).strip()
