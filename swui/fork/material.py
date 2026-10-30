# -*- coding: utf-8 -*-
# SPDX-License-Identifier: LGPL-2.1-or-later
# SPDX-FileCopyrightText: 2026 wally88ar-coder
"""
Material como en SOLIDWORKS (fase 3, pestaña Evaluar).

- Ventana "Material": árbol a la izquierda ("Materiales de FreeCAD" por categoría,
  solo los que tienen densidad, y "Materiales personalizados"), propiedades a la
  derecha. Los personalizados se crean, copian, editan y borran acá; se guardan como
  archivos .FCMat (formato nativo de FreeCAD) en la biblioteca "User" de FreeCAD
  (%APPDATA%/FreeCAD/v1-1/Material), una carpeta por categoría.
- "Aplicar" asigna con la propiedad nativa ShapeMaterial (el archivo abre sin el
  addon) y NUNCA cambia el color de la pieza (pedido del usuario): la apariencia se
  guarda antes y se devuelve.
- El archivo de FreeCAD guarda solo el UUID del material: si al abrirlo el material
  no está en la biblioteca, FreeCAD lo cambia por "Default" sin avisar (pedido
  abierto en FreeCAD, #10902). Por eso cada pieza lleva además una copia del
  material (propiedad SWUI_MaterialCopy, texto JSON, a la vista y de solo lectura:
  sin el addon se puede leer igual). Al abrir un archivo con un material que falta,
  avisa y ofrece recrearlo con el MISMO UUID (después FreeCAD lo encuentra solo).
  La masa (mass_props) usa la copia si el material falta.
- Sin material: densidad 1000 kg/m³, la misma que usa SW.
"""

import json
import os
import re
import uuid as uuidlib

import FreeCAD
import FreeCADGui

from swui.compat import QtCore, QtWidgets

COMMAND = "SWUI_Material"
COPY_PROP = "SWUI_MaterialCopy"  # nombre estable (se guarda en los archivos)
COPY_GROUP = "Material"
DEFAULT_DENSITY = 1e-6  # kg/mm³ = 1000 kg/m³, como SW sin material
DEFAULT_UUID = "7f9fd73b-50c9-41d8-b7b2-575a030c1eeb"  # material "Default" de FreeCAD 1.1.4 (sin material)
SYSTEM = "System"
USER_LIBRARIES = ("User", "Custom")  # dónde se guardan los personalizados (la primera que exista)
DEFAULT_CATEGORY = "Personalizados"

# Propiedades que se muestran y editan: (clave FreeCAD, nombre SW, unidad mostrada, modelo)
PROPS = (
    ("Density", "Densidad de masa", "kg/m^3", "Density"),
    ("YoungsModulus", "Módulo elástico", "MPa", "IsotropicLinearElastic"),
    ("PoissonRatio", "Coeficiente de Poisson", "", "IsotropicLinearElastic"),
    ("ShearModulus", "Módulo cortante", "MPa", "IsotropicLinearElastic"),
    ("YieldStrength", "Límite elástico", "MPa", "LinearElastic"),
    ("UltimateTensileStrength", "Límite de tracción", "MPa", "LinearElastic"),
    ("ThermalExpansionCoefficient", "Coeficiente de expansión térmica", "1/K", "Thermal"),
    ("ThermalConductivity", "Conductividad térmica", "W/m/K", "Thermal"),
    ("SpecificHeat", "Calor específico", "J/kg/K", "Thermal"),
)
UNIT_TEXT = {"kg/m^3": "kg/m³", "MPa": "N/mm² (MPa)", "1/K": "1/K", "W/m/K": "W/(m·K)", "J/kg/K": "J/(kg·K)"}

# UUID de los modelos de FreeCAD (Materials.UUIDs, verificados en 1.1.4)
MODEL_UUIDS = {
    "Density": "454661e5-265b-4320-8e6f-fcf6223ac3af",
    "IsotropicLinearElastic": "f6f9e48c-b116-4e82-ad7f-3659a9219c50",
    "LinearElastic": "7b561d1d-fb9b-44f6-9da9-56a4f74d7536",
    "Thermal": "9959d007-a970-4ea7-bae4-3eb1b8b883c7",
}

# Carpetas de la biblioteca de FreeCAD -> nombre en castellano
CATEGORY_ES = {
    "Metal": "Metales", "Steel": "Acero", "Aluminum": "Aluminio", "Copper": "Cobre",
    "Iron": "Hierro", "Titanium": "Titanio", "Alloys": "Aleaciones", "Thermoplast": "Termoplásticos",
    "Wood": "Madera", "Glass": "Vidrio", "Carbon": "Carbono", "Aggregate": "Áridos y hormigón",
    "Fluid": "Fluidos", "Gas": "Gases", "Liquid": "Líquidos",
}

_open = []  # ventanas abiertas (para que Python no las borre)
_deleted = set()  # UUID borrados en esta sesión (FreeCAD los recuerda hasta reiniciar)


# --- Cuentas y textos (sin Qt, probables en el test) --------------------


def material_matches(wanted, name, parts):
    """¿El texto buscado está en el nombre o en alguna carpeta de la categoría? (sin mayúsculas)"""
    wanted = wanted.lower()
    return wanted in name.lower() or any(wanted in p.lower() for p in parts)


def category_path(directory):
    """'Standard/Metal/Steel' -> ['Metales', 'Acero'] (sin la carpeta 'Standard')."""
    parts = [p for p in (directory or "").replace("\\", "/").split("/") if p]
    if parts and parts[0] == "Standard":
        parts = parts[1:]
    return [CATEGORY_ES.get(p, p) for p in parts]


def parse_number(text):
    """'7850' / '7.850,5' / '0,3' / '2e5' -> float, o None. Coma decimal como en Argentina."""
    t = (text or "").strip().replace(" ", "")
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def fmt_number(value):
    """Número con coma decimal, sin ceros de más ('7850', '0,3', '1,2e-05')."""
    if value is None:
        return ""
    if value != 0 and (abs(value) < 1e-3 or abs(value) >= 1e9):
        return ("%.4g" % value).replace(".", ",")
    text = ("%.6f" % value).rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _yaml_str(text):
    return '"%s"' % str(text).replace("\\", "\\\\").replace('"', '\\"')


def fcmat_text(data):
    """
    Texto .FCMat (YAML, formato de FreeCAD 1.x) de un material personalizado.
    data = {"uuid", "name", "description", "author", "values": {clave: (número, unidad)}}
    """
    lines = ["---", "# Material creado con LikeSolidWorks UI", "General:",
             "  UUID: %s" % _yaml_str(data["uuid"]),
             "  Name: %s" % _yaml_str(data["name"])]
    if data.get("author"):
        lines.append("  Author: %s" % _yaml_str(data["author"]))
    if data.get("description"):
        lines.append("  Description: %s" % _yaml_str(data["description"]))
    values = data.get("values") or {}
    models = []
    for key, _name, _unit, model in PROPS:
        if key in values and model not in models:
            models.append(model)
    # "Límite elástico/tracción" van en LinearElastic, que también pide densidad, E y Poisson
    if "LinearElastic" in models:
        extra = [k for k in ("Density", "YoungsModulus", "PoissonRatio", "ShearModulus") if k in values]
    else:
        extra = []
    if models:
        lines.append("Models:")
    for model in models:
        lines.append("  %s:" % model)
        lines.append("    UUID: '%s'" % MODEL_UUIDS[model])
        for key, _name, _unit, owner in PROPS:
            if key in values and (owner == model or (model == "LinearElastic" and key in extra)):
                number, unit = values[key]
                lines.append("    %s: %s" % (key, _yaml_str(("%r %s" % (number, unit)).strip())))
    return "\n".join(lines) + "\n"


def safe_file_name(name):
    """Nombre de archivo válido en Windows para un material."""
    clean = re.sub(r'[<>:"/\\|?*]+', "_", (name or "").strip()).strip(". ")
    return clean or "Material"


def copy_text(info):
    """Copia del material para guardar en la pieza (JSON). info = {"uuid","name","values"...}."""
    out = {"uuid": info.get("uuid", ""), "name": info.get("name", ""),
           "category": info.get("category", ""), "description": info.get("description", ""),
           "values": {k: [v[0], v[1]] for k, v in (info.get("values") or {}).items()}}
    return json.dumps(out, ensure_ascii=False, sort_keys=True)


def read_copy(text):
    """JSON de la copia -> dict (values como tuplas), o None si no hay o está roto."""
    try:
        data = json.loads(text or "")
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict) or not data.get("uuid"):
        return None
    data["values"] = {k: (float(v[0]), str(v[1])) for k, v in (data.get("values") or {}).items()}
    return data


def density_from(info):
    """Densidad en kg/mm³ de un dict de material (copy/info), o None."""
    try:
        number, unit = info["values"]["Density"]
    except (KeyError, TypeError, ValueError):
        return None
    factor = {"kg/m^3": 1e-9, "g/cm^3": 1e-6, "kg/mm^3": 1.0, "g/mm^3": 1e-3}.get(unit)
    return number * factor if factor else None


def missing_in(copies, known_uuids):
    """De [(objeto, copia, uuid actual)] los que perdieron su material (no está en la biblioteca)."""
    out = []
    for obj, copy, current in copies:
        if copy and copy["uuid"] != current and copy["uuid"] not in known_uuids:
            out.append((obj, copy))
    return out


# --- Biblioteca de FreeCAD --------------------------------------------


def _manager():
    import Materials

    return Materials.MaterialManager()


def libraries():
    """{nombre: carpeta} de las bibliotecas de materiales."""
    out = {}
    for lib in _manager().MaterialLibraries:
        try:
            out[lib[0]] = lib[1]
        except (TypeError, IndexError):
            pass
    return out


def user_library():
    """(nombre, carpeta) donde se guardan los personalizados."""
    libs = libraries()
    for name in USER_LIBRARIES:
        if name in libs:
            return name, libs[name]
    for name, folder in libs.items():
        if name != SYSTEM:
            return name, folder
    return None, None


def info_of(material):
    """Material de FreeCAD -> dict simple {uuid, name, category, description, library, values}."""
    values = {}
    for key, _name, unit, _model in PROPS:
        try:
            if not material.hasPhysicalProperty(key):
                continue
            q = material.getPhysicalValue(key)
        except Exception:
            continue
        if q is None:
            continue
        try:
            number = float(q) if unit == "" or isinstance(q, (int, float)) else q.getValueAs(unit).Value
        except Exception:
            continue
        if number != number:  # nan: propiedad sin valor
            continue
        values[key] = (number, unit)
    return {"uuid": material.UUID, "name": material.Name, "category": material.Directory or "",
            "description": material.Description or "", "library": material.LibraryName, "values": values}


def all_materials():
    """[info] de todos los materiales con densidad (los de "Apariencia"/"Mecanizado" no sirven para masa)."""
    out = []
    for material in _manager().Materials.values():
        try:
            info = info_of(material)
        except Exception:
            continue
        if ("Density" in info["values"] and info["uuid"] != DEFAULT_UUID and info["name"] != "Default"
                and info["uuid"] not in _deleted):
            out.append(info)
    out.sort(key=lambda i: i["name"].lower())
    return out


def known_uuids():
    try:
        return set(_manager().Materials.keys())
    except Exception:
        return set()


def get_material(uid):
    try:
        return _manager().getMaterial(uid)
    except Exception:
        return None


def save_custom(info, old_path=None):
    """
    Guarda (o sobrescribe) un material personalizado como .FCMat en la biblioteca del
    usuario y recarga la biblioteca. Devuelve la ruta del archivo.
    """
    _lib, folder = user_library()
    if not folder:
        raise RuntimeError("FreeCAD no tiene una biblioteca de materiales del usuario.")
    category = (info.get("category") or DEFAULT_CATEGORY).strip("/") or DEFAULT_CATEGORY
    target_dir = os.path.join(folder, *[safe_file_name(p) for p in category.split("/")])
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, safe_file_name(info["name"]) + ".FCMat")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(fcmat_text(info))
    _deleted.discard(info["uuid"])
    if old_path and os.path.normcase(os.path.abspath(old_path)) != os.path.normcase(os.path.abspath(path)):
        try:
            os.remove(old_path)
        except OSError:
            pass
    _refresh()
    return path


def custom_path(info):
    """Archivo .FCMat de un material personalizado (o None)."""
    _lib, folder = user_library()
    if not folder:
        return None
    for root, _dirs, files in os.walk(folder):
        for name in files:
            if not name.lower().endswith(".fcmat"):
                continue
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    if info["uuid"] in fh.read():
                        return path
            except OSError:
                pass
    return None


def remove_custom(info):
    path = custom_path(info)
    if path:
        os.remove(path)
        _deleted.add(info["uuid"])
        _refresh()
    return path


def _refresh():
    try:
        _manager().refresh()
    except Exception:
        pass


# --- Piezas -----------------------------------------------------------


def _is_default(material):
    try:
        return (material is None or material.UUID == DEFAULT_UUID or material.Name == "Default"
                or not material.hasPhysicalProperty("Density"))
    except Exception:
        return True


def material_info(obj):
    """
    (info, origen) del material de una pieza. origen: "material" (de la biblioteca),
    "copia" (falta en la biblioteca: se usa la copia guardada en la pieza) o None (sin material).
    """
    current = getattr(obj, "ShapeMaterial", None)
    if not _is_default(current):
        try:
            return info_of(current), "material"
        except Exception:
            pass
    copy = read_copy(getattr(obj, COPY_PROP, ""))
    if copy:
        return copy, "copia"
    return None, None


def density(obj):
    """Densidad (kg/mm³) y origen ("material", "copia" o None = 1000 kg/m³ como SW)."""
    info, source = material_info(obj)
    value = density_from(info) if info else None
    if value:
        return value, source
    return DEFAULT_DENSITY, None


def _keep_appearance(obj):
    """Apariencia actual (para devolverla después de cambiar el material)."""
    vo = getattr(obj, "ViewObject", None)
    out = {}
    for prop in ("ShapeAppearance", "DiffuseColor", "ShapeColor", "Transparency"):
        try:
            if vo is not None and hasattr(vo, prop):
                out[prop] = getattr(vo, prop)
        except Exception:
            pass
    return out


def _give_back(obj, saved):
    vo = getattr(obj, "ViewObject", None)
    for prop, value in saved.items():
        try:
            if getattr(vo, prop) != value:
                setattr(vo, prop, value)
        except Exception:
            pass


def write_copy(obj, info):
    """Guarda la copia del material en la pieza (propiedad a la vista, solo lectura)."""
    if info is None:
        if COPY_PROP in obj.PropertiesList:
            obj.removeProperty(COPY_PROP)
        return
    if COPY_PROP not in obj.PropertiesList:
        obj.addProperty("App::PropertyString", COPY_PROP, COPY_GROUP,
                        "Copia del material (LikeSolidWorks UI), por si falta en la biblioteca de FreeCAD")
        try:
            obj.setEditorMode(COPY_PROP, 1)  # solo lectura
        except Exception:
            pass
    text = copy_text(info)
    if getattr(obj, COPY_PROP) != text:
        setattr(obj, COPY_PROP, text)


def assign(objs, info):
    """Asigna el material (info) a las piezas sin tocar su color. info None = sin material."""
    material = get_material(info["uuid"]) if info else _default_material()
    if info and material is None:
        raise RuntimeError("El material «%s» no está en la biblioteca." % info["name"])
    for obj in objs:
        saved = _keep_appearance(obj)
        if material is not None:
            obj.ShapeMaterial = material
        _give_back(obj, saved)
        write_copy(obj, info)


def _default_material():
    """El "Default" de FreeCAD (lo que tiene una pieza sin material)."""
    return get_material(DEFAULT_UUID)


def is_part_object(obj):
    """¿Lleva material propio? Cuerpos de Part Design y sólidos sueltos (STEP)."""
    if not hasattr(obj, "ShapeMaterial"):
        return False
    if obj.TypeId == "PartDesign::Body":
        return True
    if obj.isDerivedFrom("PartDesign::Feature"):
        return False  # va el del cuerpo
    try:
        body = obj.getParentGeoFeatureGroup()
        if body is not None and body.TypeId == "PartDesign::Body":
            return False
    except Exception:
        pass
    try:
        return bool(obj.Shape.Solids)
    except Exception:
        return False


def _owner(obj):
    """Objeto que lleva el material para algo elegido (una operación -> su cuerpo)."""
    try:
        body = obj.getParentGeoFeatureGroup()
        if body is not None and body.TypeId == "PartDesign::Body":
            return body
    except Exception:
        pass
    return obj if is_part_object(obj) else None


# Los que usan un sólido sin "comérselo": apoyos de croquis, copias vinculadas de una cara,
# vistas de planos, planillas, contenedores y vínculos de ensamblaje.
NOT_CONSUMERS = ("PartDesign::", "Sketcher::", "TechDraw::", "Spreadsheet::", "App::", "Measure::", "Assembly::")
# Operaciones de Part que COPIAN el sólido (el original sigue existiendo): simetría de sólidos
COPIERS = ("Part::Mirroring",)


def consumes(user, obj):
    """
    ¿user se "come" a obj (obj pasa a ser parte de user y no cuenta aparte)? Como en SW, un
    sólido combinado o dividido deja de existir por su cuenta:
    - Combinar (PartDesign::Boolean): los Cuerpos de su lista (herramientas).
    - Un Cuerpo que arranca de obj (BaseFeature): p. ej. cada pieza de un Dividir.
    - Operaciones de Part (booleanas, Dividir, filtros...): todo lo que usan.
    - Mover sólido (move_bodies, sin "Copiar"): el original pasa al Cuerpo movido.
    - Eliminar sólidos (delete_bodies): el grupo se come lo que tiene adentro.
    """
    kind = getattr(user, "TypeId", "")
    if hasattr(user, "SWUI_MoveBody"):
        from swui.fork import move_bodies

        return move_bodies.is_moved(move_bodies.read_spec(user.SWUI_MoveBody)) and \
            move_bodies.source_of(user) is obj
    if hasattr(user, "SWUI_DeleteBodies"):
        return any(o is obj for o in (getattr(user, "Group", None) or []))
    if kind == "PartDesign::Boolean":
        return any(o is obj for o in (getattr(user, "Group", None) or []))
    if kind == "PartDesign::Body":
        return getattr(user, "BaseFeature", None) is obj
    if kind.startswith(NOT_CONSUMERS) or kind in COPIERS:
        return False
    try:
        return user.isDerivedFrom("Part::Feature")
    except Exception:
        return False


def part_objects(doc):
    """
    Piezas (sólidos de SW: Cuerpos y sólidos sueltos de STEP) que llevan material, sin las que
    se "comió" otra (herramienta de Combinar, base de un Dividir, de una booleana de Part...).
    """
    out = []
    for obj in doc.Objects:
        if not is_part_object(obj):
            continue
        if any(p is not obj and consumes(p, obj) for p in obj.InList):
            continue
        out.append(obj)
    return out


def loose_solids(obj):
    """Cantidad de sólidos sueltos de un Cuerpo (1 si es un solo sólido, como debe ser)."""
    try:
        return len(obj.Shape.Solids)
    except Exception:
        return 0


def targets(doc=None):
    """A qué piezas se aplica: lo elegido (cara -> su cuerpo) o, sin selección, toda la pieza."""
    doc = doc or FreeCAD.ActiveDocument
    if doc is None:
        return []
    out = []
    try:
        for sel in FreeCADGui.Selection.getSelectionEx(doc.Name):
            owner = _owner(sel.Object)
            if owner is not None and owner not in out:
                out.append(owner)
    except Exception:
        pass
    return out or part_objects(doc)


def summary(doc):
    """Texto de la franja: 'Material <sin especificar>', el nombre, o '<varios>'."""
    names = []
    for obj in part_objects(doc):
        info, _src = material_info(obj)
        names.append(info["name"] if info else None)
    if not names or all(n is None for n in names):
        return "Material <sin especificar>"
    if len(set(names)) == 1:
        return names[0]
    return "Material <varios>"


# --- Al abrir y al guardar ----------------------------------------------


def check_document(doc, ask=True):
    """Al abrir: piezas cuyo material falta en la biblioteca. Ofrece recrearlo (mismo UUID)."""
    copies = []
    for obj in doc.Objects:
        if COPY_PROP in getattr(obj, "PropertiesList", []):
            current = getattr(getattr(obj, "ShapeMaterial", None), "UUID", "")
            copies.append((obj, read_copy(getattr(obj, COPY_PROP)), current))
    lost = missing_in(copies, known_uuids())
    if not lost or not ask:
        return lost
    names = sorted(set(c["name"] for _o, c in lost))
    text = ("Esta pieza usa materiales que no están en tu biblioteca de FreeCAD:\n\n  %s\n\n"
            "FreeCAD los cambió por «Default». La pieza guarda una copia de cada uno.\n"
            "¿Recrearlos en Materiales personalizados y volver a asignarlos?") % "\n  ".join(names)
    answer = QtWidgets.QMessageBox.question(FreeCADGui.getMainWindow(), "Material faltante", text)
    if answer != QtWidgets.QMessageBox.StandardButton.Yes:
        FreeCAD.Console.PrintWarning("[SWUI] Materiales faltantes (la masa usa la copia guardada): %s\n"
                                     % ", ".join(names))
        return lost
    restore(lost)
    return lost


def restore(lost):
    """Recrea los materiales faltantes desde la copia y los vuelve a asignar."""
    done = set()
    for _obj, copy in lost:
        if copy["uuid"] not in done:
            save_custom(dict(copy, category=_custom_category(copy)))
            done.add(copy["uuid"])
    for obj, copy in lost:
        material = get_material(copy["uuid"])
        if material is not None:
            saved = _keep_appearance(obj)
            obj.ShapeMaterial = material
            _give_back(obj, saved)


def _custom_category(info):
    """Categoría para un material recreado: la suya si era personalizado, si no 'Recuperados'."""
    cat = info.get("category") or ""
    return cat if cat and not cat.startswith("Standard") else "Recuperados"


def refresh_copies(doc):
    """Al guardar: copia al día en cada pieza con material (también si se asignó con FreeCAD)."""
    for obj in part_objects(doc):
        current = getattr(obj, "ShapeMaterial", None)
        if _is_default(current):
            continue
        try:
            write_copy(obj, info_of(current))
        except Exception:
            pass


class _DocObserver:
    def slotFinishRestoreDocument(self, doc):
        name = doc.Name

        def later():
            d = FreeCAD.listDocuments().get(name)
            if d is not None:
                try:
                    check_document(d)
                except Exception as exc:
                    FreeCAD.Console.PrintError("[SWUI] Material faltante: %s\n" % exc)

        QtCore.QTimer.singleShot(500, later)

    def slotStartSaveDocument(self, doc, _path):
        try:
            refresh_copies(doc)
        except Exception:
            pass


# --- Ventana Material ---------------------------------------------------


def show_dialog(doc=None):
    """Ventana Material (no modal), sobre lo elegido o toda la pieza."""
    doc = doc or FreeCAD.ActiveDocument
    for d in list(_open):
        d.close()
    dialog = _MaterialDialog(doc)
    _open.append(dialog)
    dialog.finished.connect(lambda *_a: _open.remove(dialog) if dialog in _open else None)
    dialog.show()
    dialog.raise_()
    return dialog


class _MaterialDialog(QtWidgets.QDialog):
    ROLE = 256  # Qt.UserRole

    def __init__(self, doc):
        super().__init__(FreeCADGui.getMainWindow())
        self.QtCore, self.Qt = QtCore, QtWidgets
        self.doc = doc
        self.targets = targets(doc) if doc else []
        self.current = None  # info elegida
        self.editable = False
        self.setWindowTitle("Material")
        self.resize(760, 480)
        box = QtWidgets.QVBoxLayout(self)
        split = QtWidgets.QHBoxLayout()
        box.addLayout(split, 1)

        left = QtWidgets.QVBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText("Buscar material")
        self.search.textChanged.connect(self._fill_tree)
        left.addWidget(self.search)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.currentItemChanged.connect(self._chosen)
        self.tree.itemDoubleClicked.connect(lambda *_a: self._apply())
        left.addWidget(self.tree, 1)
        row = QtWidgets.QHBoxLayout()
        self.btn_new = QtWidgets.QPushButton("Nuevo")
        self.btn_new.setToolTip("Material personalizado nuevo (vacío)")
        self.btn_copy = QtWidgets.QPushButton("Copiar")
        self.btn_copy.setToolTip("Material personalizado nuevo a partir del elegido")
        self.btn_delete = QtWidgets.QPushButton("Eliminar")
        self.btn_delete.setToolTip("Borra el material personalizado elegido")
        for b in (self.btn_new, self.btn_copy, self.btn_delete):
            row.addWidget(b)
        left.addLayout(row)
        split.addLayout(left, 2)

        right = QtWidgets.QVBoxLayout()
        form = QtWidgets.QFormLayout()
        self.ed_name = QtWidgets.QLineEdit()
        self.ed_cat = QtWidgets.QLineEdit()
        self.ed_cat.setToolTip("Carpeta dentro de Materiales personalizados (con / para subcarpetas)")
        self.ed_desc = QtWidgets.QLineEdit()
        self.lb_lib = QtWidgets.QLabel()
        form.addRow("Nombre:", self.ed_name)
        form.addRow("Categoría:", self.ed_cat)
        form.addRow("Descripción:", self.ed_desc)
        form.addRow("Biblioteca:", self.lb_lib)
        right.addLayout(form)
        self.table = QtWidgets.QTableWidget(len(PROPS), 3)
        self.table.setHorizontalHeaderLabels(["Propiedad", "Valor", "Unidades"])
        self.table.verticalHeader().setVisible(False)
        for i, (_key, name, unit, _model) in enumerate(PROPS):
            for col, text in ((0, name), (2, UNIT_TEXT.get(unit, unit))):
                item = QtWidgets.QTableWidgetItem(text)
                item.setFlags(QtCore.Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(i, col, item)
            self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(""))
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setDefaultSectionSize(22)
        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(1, 110)
        right.addWidget(self.table, 1)
        self.note = QtWidgets.QLabel()
        self.note.setWordWrap(True)
        right.addWidget(self.note)
        split.addLayout(right, 3)

        bottom = QtWidgets.QHBoxLayout()
        self.lb_targets = QtWidgets.QLabel()
        self.lb_targets.setWordWrap(True)
        bottom.addWidget(self.lb_targets, 1)
        self.btn_save = QtWidgets.QPushButton("Guardar")
        self.btn_save.setToolTip("Guarda los cambios del material personalizado")
        self.btn_apply = QtWidgets.QPushButton("Aplicar")
        self.btn_remove = QtWidgets.QPushButton("Quitar material")
        self.btn_close = QtWidgets.QPushButton("Cerrar")
        for b in (self.btn_save, self.btn_apply, self.btn_remove, self.btn_close):
            bottom.addWidget(b)
        box.addLayout(bottom)

        self.btn_new.clicked.connect(lambda *_a: self._new(None))
        self.btn_copy.clicked.connect(lambda *_a: self._new(self.current))
        self.btn_delete.clicked.connect(lambda *_a: self._delete())
        self.btn_save.clicked.connect(lambda *_a: self._save())
        self.btn_apply.clicked.connect(lambda *_a: self._apply())
        self.btn_remove.clicked.connect(lambda *_a: self._remove())
        self.btn_close.clicked.connect(self.close)

        names = ", ".join(o.Label for o in self.targets) or "(no hay piezas en el documento)"
        self.lb_targets.setText("Aplicar a: " + names)
        self.btn_apply.setEnabled(bool(self.targets))
        self.btn_remove.setEnabled(bool(self.targets))
        self._pending = None  # material nuevo sin guardar
        self._fill_tree()
        self._select_current()

    # --- árbol

    def _fill_tree(self, *_a):
        Qt = QtCore.Qt
        wanted = (self.search.text() or "").strip().lower()
        self.tree.blockSignals(True)
        self.tree.clear()
        roots = {}
        user_name, _folder = user_library()
        for title, key in (("Materiales de FreeCAD", "system"), ("Materiales personalizados", "custom")):
            root = QtWidgets.QTreeWidgetItem([title])
            root.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.tree.addTopLevelItem(root)
            roots[key] = (root, {})
        for info in all_materials():
            custom = info["library"] != SYSTEM
            root, folders = roots["custom" if custom else "system"]
            parts = [p for p in info["category"].replace("\\", "/").split("/") if p] if custom else category_path(info["category"])
            # el nombre o la categoría en castellano: "acero" encuentra los "Steel-..." de Metales / Acero
            if wanted and not material_matches(wanted, info["name"], parts):
                continue
            parent = root
            path = ()
            for p in parts:
                path += (p,)
                if path not in folders:
                    item = QtWidgets.QTreeWidgetItem([p])
                    item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    parent.addChild(item)
                    folders[path] = item
                parent = folders[path]
            leaf = QtWidgets.QTreeWidgetItem([info["name"]])
            leaf.setData(0, self.ROLE, info)
            parent.addChild(leaf)
        for root, _f in roots.values():
            root.setExpanded(True)
            if wanted:
                self.tree.expandAll()
        if user_name is None:
            roots["custom"][0].setText(0, "Materiales personalizados (FreeCAD no tiene biblioteca del usuario)")
        self.tree.blockSignals(False)

    def _items(self):
        out = []

        def walk(item):
            out.append(item)
            for i in range(item.childCount()):
                walk(item.child(i))

        for i in range(self.tree.topLevelItemCount()):
            walk(self.tree.topLevelItem(i))
        return out

    def _select_uuid(self, uid):
        for item in self._items():
            info = item.data(0, self.ROLE)
            if info and info["uuid"] == uid:
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                return True
        return False

    def _select_current(self):
        """Arranca mostrando el material de la pieza (como SW)."""
        for obj in self.targets:
            info, source = material_info(obj)
            if info:
                if not self._select_uuid(info["uuid"]):
                    self._show(info, editable=False)
                    if source == "copia":
                        self.note.setText("Este material falta en tu biblioteca: se muestra la copia guardada "
                                          "en la pieza. Al abrir el archivo se ofrece recrearlo.")
                return
        self._show(None, editable=False)

    def _chosen(self, item, *_a):
        info = item.data(0, self.ROLE) if item is not None else None
        if info is not None:
            self._pending = None
            self._show(info, editable=info["library"] != SYSTEM)

    # --- formulario

    def _show(self, info, editable):
        self.current = info
        self.editable = editable
        values = (info or {}).get("values", {})
        self.ed_name.setText((info or {}).get("name", ""))
        cat = (info or {}).get("category", "")
        self.ed_cat.setText(cat if editable else " / ".join(category_path(cat)))
        self.ed_desc.setText((info or {}).get("description", ""))
        lib = (info or {}).get("library", "")
        self.lb_lib.setText({"": "", SYSTEM: "FreeCAD (solo lectura: usá Copiar para cambiarlo)"}.get(lib, "Personalizados"))
        flags = self.QtCore.Qt.ItemFlag
        for i, (key, _name, _unit, _model) in enumerate(PROPS):
            item = self.table.item(i, 1)
            item.setText(fmt_number(values[key][0]) if key in values else "")
            item.setFlags(flags.ItemIsEnabled | flags.ItemIsSelectable | (flags.ItemIsEditable if editable else flags.NoItemFlags))
        for w in (self.ed_name, self.ed_cat, self.ed_desc):
            w.setReadOnly(not editable)
        self.btn_save.setEnabled(editable)
        self.btn_delete.setEnabled(editable and self._pending is None and info is not None)
        self.btn_copy.setEnabled(info is not None)
        self.btn_apply.setEnabled(bool(self.targets) and info is not None)
        self.note.setText("" if info is None or "Density" in values else "Sin densidad: la masa no se puede calcular.")

    def _read_form(self):
        """Formulario -> info, o (None, problema)."""
        name = self.ed_name.text().strip()
        if not name:
            return None, "Falta el nombre."
        values = {}
        for i, (key, label, unit, _model) in enumerate(PROPS):
            text = self.table.item(i, 1).text().strip()
            if not text:
                continue
            number = parse_number(text)
            if number is None:
                return None, "«%s» no es un número: %s" % (label, text)
            values[key] = (number, unit)
        if "Density" not in values:
            return None, "Falta la densidad (sin ella no hay masa)."
        info = dict(self.current or {})
        info.update(name=name, category=self.ed_cat.text().strip() or DEFAULT_CATEGORY,
                    description=self.ed_desc.text().strip(), values=values)
        info.setdefault("uuid", str(uuidlib.uuid4()))
        return info, ""

    # --- botones

    def _new(self, base):
        info = {"uuid": str(uuidlib.uuid4()), "library": "User",
                "name": (base["name"] + " (copia)") if base else "Material nuevo",
                "category": DEFAULT_CATEGORY, "description": (base or {}).get("description", ""),
                "values": dict((base or {}).get("values", {}))}
        self._pending = info
        self.tree.blockSignals(True)
        self.tree.setCurrentItem(None)
        self.tree.blockSignals(False)
        self._show(info, editable=True)
        self.note.setText("Material nuevo: completá los datos y tocá Guardar.")
        self.ed_name.setFocus()
        self.ed_name.selectAll()

    def _save(self):
        info, problem = self._read_form()
        if info is None:
            self.Qt.QMessageBox.warning(self, "Material", problem)
            return None
        old = None if self._pending is not None else custom_path(self.current or {"uuid": info["uuid"]})
        try:
            save_custom(info, old)
        except Exception as exc:
            self.Qt.QMessageBox.warning(self, "Material", "No se pudo guardar: %s" % exc)
            return None
        self._pending = None
        self._fill_tree()
        self._select_uuid(info["uuid"])
        self.note.setText("Guardado en Materiales personalizados.")
        return info

    def _delete(self):
        info = self.current
        if not info or info.get("library") == SYSTEM:
            return
        used = [o.Label for d in FreeCAD.listDocuments().values() for o in part_objects(d)
                if (material_info(o)[0] or {}).get("uuid") == info["uuid"]]
        text = "¿Borrar el material «%s» de Materiales personalizados?" % info["name"]
        if used:
            text += ("\n\nLo usan piezas abiertas (%s): conservan su copia guardada, y al volver a "
                     "abrirlas se ofrece recrearlo." % ", ".join(used))
        if self.Qt.QMessageBox.question(self, "Material", text) != self.Qt.QMessageBox.StandardButton.Yes:
            return
        remove_custom(info)
        self._fill_tree()
        self._show(None, editable=False)

    def _apply(self):
        if not self.targets:
            return
        info = self.current
        if self.editable and (self._pending is not None or self._form_changed()):
            info = self._save()
            if info is None:
                return
        if info is None:
            return
        self.doc.openTransaction("Asignar material")
        try:
            assign(self.targets, info)
        except Exception as exc:
            self.doc.abortTransaction()
            self.Qt.QMessageBox.warning(self, "Material", str(exc))
            return
        self.doc.commitTransaction()
        _changed()
        self.note.setText("Asignado a: " + ", ".join(o.Label for o in self.targets))

    def _form_changed(self):
        info, _p = self._read_form()
        cur = self.current or {}
        return info is not None and (info["name"] != cur.get("name") or info["values"] != cur.get("values")
                                     or info["description"] != cur.get("description", "")
                                     or info["category"] != (cur.get("category") or DEFAULT_CATEGORY))

    def _remove(self):
        if not self.targets:
            return
        self.doc.openTransaction("Quitar material")
        try:
            assign(self.targets, None)
        except Exception as exc:
            self.doc.abortTransaction()
            self.Qt.QMessageBox.warning(self, "Material", str(exc))
            return
        self.doc.commitTransaction()
        _changed()
        self.note.setText("Sin material: la masa se calcula con 1000 kg/m³ (como SW).")


_listeners = []  # funciones a llamar cuando cambia un material (la franja del árbol)


def add_listener(fn):
    if fn not in _listeners:
        _listeners.append(fn)


def _changed():
    for fn in list(_listeners):
        try:
            fn()
        except Exception:
            pass


# --- Comando ----------------------------------------------------------


class _MaterialCommand:
    def GetResources(self):
        from swui import paths

        return {"MenuText": "Editar material", "ToolTip": "Asignar, crear y editar materiales (como SW). "
                "No cambia el color de la pieza.", "Pixmap": paths.icon("fork/material") or ""}

    def IsActive(self):
        return FreeCAD.ActiveDocument is not None

    def Activated(self):
        show_dialog()


_observer = None


def install():
    global _observer
    try:
        FreeCADGui.addCommand(COMMAND, _MaterialCommand())
    except Exception:
        pass  # ya registrado
    if _observer is None:
        _observer = _DocObserver()
        FreeCAD.addDocumentObserver(_observer)
