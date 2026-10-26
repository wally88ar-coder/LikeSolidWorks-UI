# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
"Chequear carpeta": para el día que se cambia de versión de FreeCAD.

Abre una por una las piezas (.FCStd) de una carpeta (y sus subcarpetas), sin
mostrarlas, recalcula TODO (como Ctrl+Q), junta los errores ("¿Qué es
incorrecto?") y las referencias perdidas ("Reparar referencias") y las cierra
SIN GUARDAR. Las que ya están abiertas no se tocan (se avisa). Al final, una
lista: doble clic abre la pieza; "Guardar informe" deja un .txt en la carpeta.
"""

import os
import traceback

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

COMMAND = "SWUI_CheckFolder"
REPORT = "Chequeo FreeCAD %s.txt"

_open = []


def find_files(folder):
    """Piezas .FCStd de la carpeta y subcarpetas, ordenadas (sin copias .FCBak)."""
    out = []
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if name.lower().endswith(".fcstd"):
                out.append(os.path.join(root, name))
    return sorted(out, key=lambda p: p.lower())


def summarize(results, folder):
    """Texto del informe. results = [(ruta, estado, [renglones])], estado: ok / error / abierto / no_abre."""
    head = {"ok": "OK", "error": "CON ERRORES", "abierto": "SIN CHEQUEAR (estaba abierto)",
            "no_abre": "NO SE PUDO ABRIR"}
    bad = sum(1 for _p, st, _l in results if st != "ok")
    lines = ["Chequeo de piezas - FreeCAD %s" % ".".join(FreeCAD.Version()[:3]),
             "Carpeta: %s" % folder,
             "%d piezas, %d con problemas" % (len(results), bad), ""]
    for path, state, detail in results:
        lines.append("%s: %s" % (os.path.relpath(path, folder), head.get(state, state)))
        lines += ["    " + d for d in detail]
    return "\n".join(lines) + "\n"


def check_file(path):
    """(estado, [renglones]) de una pieza."""
    from swui.fork import repair_refs, tree_dialogs

    norm = os.path.normcase(os.path.abspath(path))
    for doc in FreeCAD.listDocuments().values():
        if os.path.normcase(os.path.abspath(doc.FileName or "")) == norm:
            return "abierto", ["Cerrala y volvé a chequear para incluirla."]
    before = set(FreeCAD.listDocuments())
    try:
        doc = FreeCAD.openDocument(path, True)  # oculta
    except Exception as exc:
        return "no_abre", [str(exc)]
    try:
        for obj in doc.Objects:
            try:
                obj.touch()
            except Exception:
                pass
        doc.recompute()
        # Primero lo de "Reparar referencias" (dice qué cara/arista se perdió); los demás errores,
        # solo de lo que no esté ya en esa lista
        refs = repair_refs.problems(doc)
        lines = ["%s: %s" % (obj.Label, text) for obj, _kind, text in refs]
        named = {obj.Name for obj, _k, _t in refs}
        for obj, kind, message in tree_dialogs.problems(doc):
            if kind == tree_dialogs.ERROR and obj.Name not in named:
                lines.append("%s: %s" % (obj.Label, tree_dialogs.explain(message)))
        return ("error" if lines else "ok"), lines
    except Exception:
        return "error", [traceback.format_exc().splitlines()[-1]]
    finally:
        for name in set(FreeCAD.listDocuments()) - before:  # la pieza y lo que abrió con ella
            try:
                FreeCAD.closeDocument(name)
            except Exception:
                pass


def run(folder):
    """Chequear la carpeta con barra de progreso; devuelve los resultados."""
    files = find_files(folder)
    mw = FreeCADGui.getMainWindow()
    progress = QtWidgets.QProgressDialog("Chequeando piezas...", "Cancelar", 0, max(len(files), 1), mw)
    progress.setWindowTitle("Chequear carpeta")
    progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    results = []
    for i, path in enumerate(files):
        if progress.wasCanceled():
            break
        progress.setLabelText("Chequeando %s (%d de %d)..." % (os.path.basename(path), i + 1, len(files)))
        progress.setValue(i)
        QtWidgets.QApplication.processEvents()
        state, lines = check_file(path)
        results.append((path, state, lines))
    progress.setValue(progress.maximum())
    progress.close()
    return results


def show_results(results, folder):
    from swui.fork import tree_dialogs as td

    dialog = QtWidgets.QDialog(FreeCADGui.getMainWindow())
    dialog.setWindowTitle("Chequear carpeta")
    dialog.resize(640, 420)
    box = QtWidgets.QVBoxLayout(dialog)
    bad = [r for r in results if r[1] != "ok"]
    box.addWidget(QtWidgets.QLabel("%d piezas chequeadas, %d con problemas." % (len(results), len(bad))))
    lst = QtWidgets.QListWidget()
    lst.setWordWrap(True)
    marks = {"ok": "✓", "error": "✗", "abierto": "•", "no_abre": "✗"}
    for path, state, lines in sorted(results, key=lambda r: r[1] == "ok"):
        item = QtWidgets.QListWidgetItem("\n".join(["%s  %s" % (marks.get(state, "?"), os.path.relpath(path, folder))]
                                                   + ["      " + line for line in lines]))
        item.setData(QtCore.Qt.ItemDataRole.UserRole, path)
        lst.addItem(item)
    box.addWidget(lst)
    row = QtWidgets.QHBoxLayout()
    save = QtWidgets.QPushButton("Guardar informe")
    close = QtWidgets.QPushButton("Cerrar")
    row.addWidget(save)
    row.addStretch(1)
    row.addWidget(close)
    box.addLayout(row)

    def do_save(*_a):
        path = os.path.join(folder, REPORT % ".".join(FreeCAD.Version()[:3]))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(summarize(results, folder))
        save.setText("Informe guardado ✓")
        save.setToolTip(path)

    lst.itemDoubleClicked.connect(lambda item: FreeCAD.openDocument(item.data(QtCore.Qt.ItemDataRole.UserRole)))
    save.clicked.connect(do_save)
    close.clicked.connect(dialog.close)
    td._keep(dialog)
    return dialog


class _CheckFolder:
    def GetResources(self):
        return {"MenuText": "Chequear carpeta...",
                "ToolTip": "Abre, recalcula y revisa todas las piezas de una carpeta (sin guardar nada)"}

    def IsActive(self):
        return True

    def Activated(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(FreeCADGui.getMainWindow(), "Carpeta a chequear")
        if folder:
            show_results(run(folder), folder)


def install():
    try:
        FreeCADGui.addCommand(COMMAND, _CheckFolder())
    except Exception:
        pass  # ya registrado
