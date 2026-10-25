# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Velocidad de giro con la ruedita del mouse, como en SOLIDWORKS.

FreeCAD 1.1.4 no tiene un ajuste de velocidad de órbita para el mouse (los
de "sensibilidad" son del ratón 3D). Con "Arcball redondeado" gira unos 16°
por cada 100 px; en SW se siente bastante más rápido.

Cómo se logra: un filtro de eventos en la vista 3D. Mientras se arrastra con
la ruedita SIN teclas (en el estilo de navegación SolidWorks eso es girar),
cada movimiento se agranda FACTOR veces respecto del punto donde se apretó la
ruedita, y FreeCAD gira en proporción (medido: x1,5 -> 25°, x2 -> 35° por
cada 100 px). El centro de giro, Ctrl+ruedita (desplazar), el zoom y las
hojas de dibujo (TechDraw) no se tocan. Solo actúa dentro de LikeSolidWorks UI.

Ajuste: menú "LikeSolidWorks UI" -> "Velocidad de giro...", guardado en el
parámetro BaseApp/Preferences/Mod/SWUI/OrbitSpeed.
"""

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtGui, QtWidgets

PARAMS = "User parameter:BaseApp/Preferences/Mod/SWUI"
KEY = "OrbitSpeed"
DEFAULT = 1.5
CHOICES = (1.0, 1.5, 2.0, 2.5)
NAV_STYLES = ("Gui::SolidWorksNavigationStyle",)  # estilos donde ruedita sin teclas = girar
VIEW_CLASS = "Gui::View3DInventor"
WB_NAME = "LikeSolidWorksUIWorkbench"
COMMAND = "SWUI_OrbitSpeed"

_filter = None


def factor():
    try:
        value = FreeCAD.ParamGet(PARAMS).GetFloat(KEY, DEFAULT)
    except Exception:
        value = DEFAULT
    return value if value > 0 else DEFAULT


def set_factor(value):
    FreeCAD.ParamGet(PARAMS).SetFloat(KEY, float(value))


def choice_text(value):
    """1.5 -> 'x1,5'; 1.0 -> 'x1 (como FreeCAD)'."""
    text = ("x%g" % value).replace(".", ",")
    return text + " (como FreeCAD)" if value == 1.0 else text


def scaled(start, pos, k):
    """Punto agrandado k veces desde start (x, y)."""
    return (start[0] + (pos[0] - start[0]) * k, start[1] + (pos[1] - start[1]) * k)


def _wanted():
    try:
        if FreeCADGui.activeWorkbench().name() != WB_NAME:
            return False
        style = FreeCAD.ParamGet("User parameter:BaseApp/Preferences/View").GetString("NavigationStyle", "")
        return style in NAV_STYLES
    except Exception:
        return False


def _xy(event):
    p = event.position() if hasattr(event, "position") else event.localPos()  # Qt6 / Qt5
    return p.x(), p.y()


class _OrbitFilter(QtCore.QObject):
    """Filtro de eventos en el área de dibujo de cada vista 3D."""

    def __init__(self):
        super().__init__()
        self.start = None
        self.busy = False

    def eventFilter(self, obj, event):
        if self.busy:
            return False
        try:
            t = event.type()
            if t == QtCore.QEvent.Type.MouseButtonPress:
                middle = event.button() == QtCore.Qt.MouseButton.MiddleButton
                plain = event.modifiers() == QtCore.Qt.KeyboardModifier.NoModifier
                self.start = _xy(event) if middle and plain and _wanted() else None
                return False
            if t == QtCore.QEvent.Type.MouseButtonRelease:
                self.start = None
                return False
            if t != QtCore.QEvent.Type.MouseMove or self.start is None:
                return False
            k = factor()
            if k == 1.0 or not (event.buttons() & QtCore.Qt.MouseButton.MiddleButton):
                return False
            x, y = scaled(self.start, _xy(event), k)
            point = QtCore.QPointF(x, y)
            moved = QtGui.QMouseEvent(event.type(), point, QtCore.QPointF(obj.mapToGlobal(point)),
                                      event.button(), event.buttons(), event.modifiers())
            self.busy = True
            try:
                QtWidgets.QApplication.sendEvent(obj, moved)
            finally:
                self.busy = False
            return True  # el movimiento original no llega a FreeCAD
        except Exception:
            self.start = None
            return False


def install():
    """Comando del menú y filtro en las vistas 3D (las abiertas y las que se abran)."""
    global _filter
    try:
        FreeCADGui.addCommand(COMMAND, _OrbitSpeedCommand())
    except Exception:
        pass  # ya registrado
    if _filter is not None:
        return
    _filter = _OrbitFilter()
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        mdi.subWindowActivated.connect(lambda *_a: _attach_all())
    except Exception:
        FreeCAD.Console.PrintLog("[SWUI fork] Velocidad de giro: no se encontró el área de ventanas.\n")
    _attach_all()


def _attach_all():
    """Poner el filtro en el área de dibujo de cada vista 3D abierta (una sola vez por vista)."""
    try:
        mdi = FreeCADGui.getMainWindow().findChild(QtWidgets.QMdiArea)
        for sub in mdi.subWindowList():
            view = sub.widget()
            if view is None or view.metaObject().className() != VIEW_CLASS:
                continue
            for gv in view.findChildren(QtWidgets.QGraphicsView):
                vp = gv.viewport()
                if not vp.property("swui_orbit"):
                    vp.setProperty("swui_orbit", True)
                    vp.installEventFilter(_filter)
    except Exception:
        pass


class _OrbitSpeedCommand:
    """Menú LikeSolidWorks UI -> Velocidad de giro..."""

    def GetResources(self):
        return {
            "MenuText": "Velocidad de giro...",
            "ToolTip": "Qué tan rápido gira el modelo al arrastrar con la ruedita del mouse",
        }

    def IsActive(self):
        return True

    def Activated(self):
        items = [choice_text(v) for v in CHOICES]
        current = min(range(len(CHOICES)), key=lambda i: abs(CHOICES[i] - factor()))
        text, ok = QtWidgets.QInputDialog.getItem(
            FreeCADGui.getMainWindow(), "Velocidad de giro",
            "Giro con la ruedita del mouse\n(x1 = como FreeCAD; SW se siente parecido a x1,5 - x2):",
            items, current, False)
        if ok and text in items:
            set_factor(CHOICES[items.index(text)])
