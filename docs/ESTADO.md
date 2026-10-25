# Estado del fork

Última actualización: 2026-10-25 (fin de la primera sesión de trabajo)

## Fase actual
**Fase 0 — Puesta en marcha: terminada y probada por el usuario** ("ahora sí se parece más a SW").
Después se hicieron retoques de interfaz pedidos por el usuario (ver "Hecho").
**Fase 1 (chapa) cajoneada por un tiempo** a pedido del usuario. Próximo trabajo: lo que él pida.

## Entorno del usuario
- FreeCAD 1.1.4 en `D:\Freecad` (Python: `D:\Freecad\bin\python.exe`). Hay además un FreeCAD
  1.0.0 en `C:\Program Files\FreeCAD 1.0` que NO se usa.
- Addons: `%APPDATA%\FreeCAD\v1-1\Mod`. SheetMetal instalado ahí (Addon Manager).
- Este repo: `%APPDATA%\FreeCAD\v1-1\Mod\LikeSolidWorks-UI` (FreeCAD lo carga directo).
- Preferencias propias del usuario: estilo de navegación SolidWorks, "Modo de rotación: Centro
  del objeto", FreeCAD en "Spanish (Argentina)", pantalla 1366x768.
- Cómo probar (test y FreeCAD real con capturas): ver `docs/NOTAS_TECNICAS.md`.

## Hecho
Generales (en ramas limpias, candidatas a PR al original; ver tabla al final):
- Test `tools/test_load.py` en verde en Windows (comparaba rutas con `/`).
- Español: `swui/lang/es.py` con términos de SW en español; "Automático" elige el idioma de
  FreeCAD si hay archivo (detecta "Spanish (Argentina)").
- Cinta para pantallas chicas: pestañas desplazables; si no entra, botones solo con ícono; si
  aun así no entra, flechas. Ancho mínimo de ventana 418 px (antes 1614).
- Diálogos de operación ya no saltan a Part Design (Part Design lo pide desde C++ con
  `Gui.activateWorkbench`; se bloquea en `swui/sketch_edit.py`); términos SW en los diálogos
  también en Windows (objectName `PartDesignGui__...` en vez de `::`).
- Croquis / Extruir / Extruir corte / Revolución sin selección: panel propio para elegir plano
  o cara plana; al salir del croquis se lanza la operación (`swui/pick_plane.py`).

Propios del fork (en `swui/fork/`, enganchados en `swui/fork/__init__.py`, una línea en
`InitGui.Initialize`):
- `panel_sw.py`: panel izquierdo como FeatureManager/PropertyManager: **Modelo y Tareas en
  pestañas** (arriba), pasa solo a Tareas al abrir una operación y vuelve al árbol al cerrarla;
  sin títulos repetidos. Vista de informe abajo y **oculta**, y no se abre sola ante avisos
  (preferencias OutputWindow, se devuelven al salir).
- `look_sw.py`: **aspecto claro SW 2018** (colores medidos en capturas del usuario): cinta y
  paneles #F7F7F7, pestañas #D4D4D4, fondo degradado #E1E4ED/#D7DCE7/#FEFEFE, croquis azul puro
  2 px, constructivas 1 px trazo y punto, resaltado naranja, aristas negras 1 px. Árbol en panel
  fijo (sin superposición). Sin barras Archivo/Editar.
- `quick_access.py`: íconos Nuevo/Abrir/Guardar/Deshacer/Recalcular a la derecha de la barra
  de menú (área "MenuBarRightArea" de FreeCAD 1.1).
- `orbit_speed.py`: velocidad de giro con la ruedita (menú "Velocidad de giro...", x1,5 de
  fábrica). FreeCAD no tiene ese ajuste: se agranda el arrastre en la vista 3D.
- `always_swui.py`: **usar siempre LikeSolidWorks UI** (arranque, vuelta automática si algo
  cambia de banco, selector oculto); se apaga en el menú "Usar siempre LikeSolidWorks UI".

## Falta / ideas pendientes
- Fase 1: chapa metálica + DXF (cajoneada). Pedir al usuario piezas STEP de chapa cuando se retome.
- Simulación FEM como pestaña "Simulación" con flujo SW (estudio, material, sujeciones, cargas,
  malla, ejecutar, resultados): conversada, sin empezar; es grande.
- Panel Ver/Datos (propiedades de FreeCAD): se deja por ahora; el usuario va a ver si le sirve.
  Opción hablada: separarlo y dejarlo oculto como la Vista de informe.
- Ejes rojo/verde del croquis (SW no los muestra): sin ajuste simple en FreeCAD.
- Plantillas de rótulo en español; decimales con coma en "Formato de línea".
- Color de las piezas (gris de SW): no se tocó; pedir captura si el usuario lo quiere.

## Problemas reportados por el usuario (todos resueltos)
- 2026-10-25: cinta cortaba la ventana a 1366 px (pedía 1614 px). Resuelto.
- 2026-10-25: al extruir un croquis saltaba a Part Design y el diálogo quedaba nativo. Resuelto.
- 2026-10-25: Croquis sin selección caía en "Seleccione un plano" (solo planos base, nombres de
  FreeCAD, no acepta caras). Resuelto con el panel propio.

## Decisiones
- Similitud total con SW: panel de tareas solo a la izquierda (sin opción a la derecha),
  LikeSolidWorks UI como único banco, todo módulo nuevo (chapa, FEM) como pestaña de la cinta
  sobre las herramientas nativas.
- Código propio del fork: en `swui/fork/`, comentarios en español, mensajes sin tr(); cambia
  tablas/funciones del original desde afuera (sin editar sus archivos) para no generar
  conflictos al traer novedades de upstream.
- Lo que sirve a todos va en ramas limpias para PR; antes de abrir PR/issue, consultar al usuario.

## Git
- `origin` = fork del usuario (todo subido al 2026-10-25), `upstream` = Schlauminik/LikeSolidWorks-UI.
- `master` = versión que usa el usuario (ramas generales unidas + código del fork).

## PR al original
| Rama | Contenido | Estado |
|---|---|---|
| `fix/test-windows-pfade` | Test pasa en Windows | lista, sin proponer |
| `feat/sprache-es` | Idioma español + Automático según FreeCAD | lista, sin proponer (en Windows su test necesita también la rama anterior) |
| `feat/ribbon-schmal` | Cinta para pantallas chicas (incluye `fix/test-windows-pfade`) | lista, sin proponer |
| `fix/feature-dialog-bleibt` | Diálogos no saltan a Part Design; términos SW en Windows (incluye `fix/test-windows-pfade`) | lista, sin proponer |
| `feat/skizze-ohne-auswahl` | Croquis/extruir sin selección (incluye `fix/feature-dialog-bleibt`); sus textos en español están solo en master | lista, sin proponer |
