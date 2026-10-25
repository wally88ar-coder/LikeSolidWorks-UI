# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 Dominik Ladewig
"""
Sprache der Oberflaeche - Deutsch / English, erweiterbar (Dominik, 18.10.).

Warum nicht FreeCADs Uebersetzung (Qt, .ts-Dateien)? Die haengt an
FreeCADs eigener Sprache und wirkt erst nach einem Neustart. Gewuenscht
ist eine eigene Umschaltung im Reiter "Evaluieren", die SOFORT wirkt.

So funktioniert es:
  - Die Quelltexte im Code sind deutsch (wie bisher). Sie sind zugleich
    die Schluessel: tr("Fase") -> "Chamfer", wenn Englisch aktiv ist.
  - Jede Sprache ist eine Datei in swui/lang/ mit CODE, NAME und TEXTS
    (dict deutsch -> Uebersetzung). NEUE SPRACHE = NEUE DATEI - sie
    erscheint automatisch im Menue des Knopfes "Language".
  - Fehlt ein Text, wird Englisch genommen, dann der deutsche Text.
  - Einstellung: Parameter BaseApp/Preferences/Mod/SWUI/Language
    ("auto", "de", "en", ...). "auto" = wie FreeCAD: gibt es eine
    Sprachdatei fuer FreeCADs Sprache, wird sie genommen, sonst Englisch.
  - Wer auf Umschaltungen reagieren muss (Ribbon), meldet sich mit
    add_listener() an.
"""

import importlib
import os
import pkgutil
import traceback

import FreeCAD

PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI"
KEY = "Language"
AUTO = "auto"
SOURCE = "de"  # Sprache der Quelltexte (= Schluessel)
FALLBACK = "en"  # wenn eine Sprache einen Text nicht kennt

# Knopf heisst in jeder Sprache gleich (Dominiks Vorgabe) - damit man ihn
# auch in einer fremden Sprache findet.
BUTTON_TEXT = "Language"
BUTTON_TIP = "Sprache der Oberfläche / User interface language"

_languages = None  # Code -> Modul, einmal eingelesen
_listeners = []

# FreeCADs Sprachnamen (Gui.getLocale, Translator::supportedLocales) -> Code
_FREECAD_NAMES = {"german": "de", "deutsch": "de", "english": "en", "spanish": "es", "español": "es"}


# --- Sprachen --------------------------------------------------------


def languages():
    """{Code: Modul} aller Sprachdateien in swui/lang/ (Deutsch immer dabei)."""
    global _languages
    if _languages is None:
        found = {}
        from swui import lang as pkg

        for info in pkgutil.iter_modules([os.path.dirname(pkg.__file__)]):
            if info.name.startswith("_"):
                continue
            try:
                mod = importlib.import_module("swui.lang." + info.name)
                code = getattr(mod, "CODE", info.name)
                if isinstance(getattr(mod, "TEXTS", None), dict) and getattr(mod, "NAME", ""):
                    found[code] = mod
            except Exception:
                FreeCAD.Console.PrintWarning(
                    "[SWUI] Sprachdatei %s fehlerhaft:\n%s\n" % (info.name, traceback.format_exc()))
        _languages = found
    return _languages


def choices():
    """[(Code, Name)] fuer das Menue: Deutsch und Englisch zuerst, dann der Rest."""
    langs = languages()
    order = [c for c in (SOURCE, FALLBACK) if c in langs] + sorted(c for c in langs if c not in (SOURCE, FALLBACK))
    return [(c, langs[c].NAME) for c in order]


# --- Einstellung -----------------------------------------------------


def setting():
    """Gespeicherte Auswahl: "auto" oder ein Sprachcode."""
    try:
        value = FreeCAD.ParamGet(PARAMS).GetString(KEY, AUTO) or AUTO
    except Exception:
        value = AUTO
    return value if value == AUTO or value in languages() else AUTO


def freecad_language():
    """FreeCADs eigene Sprache als Code ("de", "en", ...)."""
    name = ""
    try:
        import FreeCADGui

        name = FreeCADGui.getLocale() or ""
    except Exception:
        pass
    if not name:
        try:
            name = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/General").GetString("Language", "")
        except Exception:
            name = ""
    if not name:
        try:
            from swui.compat import QtCore

            name = QtCore.QLocale.system().name()  # z. B. "de_DE"
        except Exception:
            name = ""
    low = name.strip().lower()
    # FreeCAD speichert z. B. "Spanish (Argentina)" -> "spanish"
    low = low.split(" (")[0].strip()
    if low in _FREECAD_NAMES:
        return _FREECAD_NAMES[low]
    return low.replace("-", "_").split("_")[0][:2]


def resolve(value):
    """Auswahl -> tatsaechlich verwendete Sprache."""
    if value != AUTO:
        return value if value in languages() else FALLBACK
    fc = freecad_language()
    # FreeCAD deutsch -> Deutsch; weitere Sprache mit eigener Datei -> diese; sonst Englisch
    return fc if fc in languages() else FALLBACK


def current():
    return resolve(setting())


def set_setting(value):
    """Neue Auswahl speichern und alle Angemeldeten benachrichtigen (wirkt sofort)."""
    if value != AUTO and value not in languages():
        raise ValueError("Unbekannte Sprache: %s" % value)
    before = current()
    try:
        FreeCAD.ParamGet(PARAMS).SetString(KEY, value)
    except Exception:
        FreeCAD.Console.PrintWarning("[SWUI] Sprache nicht speicherbar: %s\n" % traceback.format_exc())
    after = current()
    for fn in list(_listeners):
        try:
            fn(before, after)
        except Exception:
            FreeCAD.Console.PrintError("[SWUI] Sprachwechsel: %s\n" % traceback.format_exc())
    return after


def add_listener(fn):
    if fn not in _listeners:
        _listeners.append(fn)


def remove_listener(fn):
    if fn in _listeners:
        _listeners.remove(fn)


# --- Uebersetzen -----------------------------------------------------


def N_(text):
    """
    Markierung ohne Wirkung fuer Texte, die schon beim Laden feststehen
    (Listen wie die Nahtarten) und erst bei der Anzeige mit tr() uebersetzt
    werden. Der Test findet alle tr("...") und N_("...") und prueft, dass
    jede Sprache sie kennt.
    """
    return text


def tr(text, lang=None):
    """Deutschen Quelltext in die aktive (oder angegebene) Sprache uebersetzen."""
    if not text:
        return text
    code = lang or current()
    if code == SOURCE:
        return text
    langs = languages()
    for c in (code, FALLBACK):
        mod = langs.get(c)
        if mod is not None and text in mod.TEXTS:
            return mod.TEXTS[text]
    return text


TREE = "Baum|"  # Vorsatz fuer Baumnamen in den Sprachdateien ("Baum|Rotieren": "Revolve")


def tree(text, lang=None):
    """
    Name im Baum (Sprache, Schritt 4). Eigene Schluessel "Baum|<deutsch>",
    weil der Baum oft anders heisst als der Ribbon-Knopf: Knopf "Rotieren"
    = "Revolved Boss/Base", im Baum aber "Revolve1" (wie in SOLIDWORKS).
    Rueckfall: Sprache -> Englisch -> deutscher Name.
    """
    if not text:
        return text
    code = lang or current()
    if code == SOURCE:
        return text
    langs = languages()
    for c in (code, FALLBACK):
        mod = langs.get(c)
        if mod is not None and TREE + text in mod.TEXTS:
            return mod.TEXTS[TREE + text]
    return text


def tree_variants(text):
    """Ein Baumname in allen Sprachen - zum Wiedererkennen vorhandener Namen."""
    out = [text]
    for code, _name in choices():
        t = tree(text, code)
        if t not in out:
            out.append(t)
    return out


def tree_like(text, existing):
    """
    Baumname in der Sprache, in der 'existing' schon heisst. So bleibt z. B.
    "Detailansicht Z (2:1)" beim Aendern des Massstabs deutsch, auch wenn
    inzwischen Englisch eingestellt ist (vorhandene Namen bleiben).
    """
    existing = existing or ""
    for t in sorted(tree_variants(text), key=len, reverse=True):
        if existing.startswith(t):
            return t
    return tree(text)


def missing(keys, lang):
    """Welche der Schluessel fehlen in einer Sprache? (fuer den Test)"""
    if lang == SOURCE:
        return []
    mod = languages().get(lang)
    table = mod.TEXTS if mod is not None else {}
    return [k for k in keys if k not in table]
