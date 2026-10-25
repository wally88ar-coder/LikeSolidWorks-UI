# Estado del fork

Última actualización: 2026-10-25

## Fase actual
**Fase 0 — Puesta en marcha**: todo implementado, falta que el usuario lo pruebe.

## Entorno del usuario
- FreeCAD 1.1.4 instalado en `D:\Freecad` (Python: `D:\Freecad\bin\python.exe`).
  También hay un FreeCAD 1.0.0 en `C:\Program Files\FreeCAD 1.0` (no se usa).
- Carpeta de addons: `%APPDATA%\FreeCAD\v1-1\Mod`. SheetMetal ya instalado ahí (Addon Manager).
- Este repo: `%APPDATA%\FreeCAD\v1-1\Mod\LikeSolidWorks-UI` (FreeCAD lo carga directo).
- Test: `D:\Freecad\bin\python.exe tools/test_load.py .`

## Hecho
- Clonado el fork; remotos `origin` (fork) y `upstream` (Schlauminik/LikeSolidWorks-UI).
  Base: upstream 0.10.0 (commit b3f64eb).
- `tools/test_load.py` fallaba en Windows (comparaba rutas con `/` fijas). Arreglado en la rama
  `fix/test-windows-pfade` (limpia, sobre upstream/master) y unida a `master`. Test en verde.
- Traducción al español: `swui/lang/es.py` (661 textos, términos de SW en español: Croquis,
  Extruir saliente/base, Relaciones de posición, Planta/Alzado/Vista lateral...). "Automático"
  ahora elige el idioma de FreeCAD si hay archivo para él (detecta "Spanish (Argentina)").
  Rama `feat/sprache-es`, unida a `master`. Probado por el usuario el 2026-10-25: carga bien y
  se ve en español.

- Cinta para pantallas chicas: cada pestaña se puede desplazar; si no entra, los botones grandes
  quedan solo con ícono (nombre en el tooltip); si aun así no entra, flechas ‹ ›. Probado en
  FreeCAD real a 1366 px: ancho mínimo de ventana 418 px (antes 1614). Rama `feat/ribbon-schmal`.
- Panel de tareas a la izquierda, solo con operación abierta; Vista de informe abajo (110 px).
  Propio del fork: `swui/fork/panel_sw.py`, enganchado desde `swui/fork/__init__.py`
  (una línea en `InitGui.Initialize`). Probado en FreeCAD real con un croquis.
  El test del original se adaptó en `master` para verificar este comportamiento.

- Arreglado (reporte del usuario): al extruir, FreeCAD saltaba al banco Part Design (Part Design
  lo hace solo al abrir cualquier diálogo de operación). Ahora se queda en LikeSolidWorks UI.
  Además los términos SW de los diálogos no andaban en Windows (nombre `PartDesignGui__...`).
  Rama `fix/feature-dialog-bleibt`. Probado en FreeCAD real.

- Croquis / Extruir / Extruir corte / Revolución sin selección: panel propio "Croquis:
  seleccionar un plano" (lista + clic en pantalla o árbol, acepta caras planas); se abre el
  croquis ahí y, para operaciones, al salir del croquis se lanza la operación. El cuerpo se crea
  antes y ya con Planta/Alzado/Vista lateral. `swui/pick_plane.py`, rama
  `feat/skizze-ohne-auswahl`. Probado en FreeCAD real (extruir en Planta + corte en cara).

- Navegación (pedido del usuario, 2026-10-25): el usuario puso en Preferencias "Modo de
  rotación: Centro del objeto" (antes "Centro de la ventana") y mejoró. Para la velocidad,
  FreeCAD no tiene ajuste: `swui/fork/orbit_speed.py` agranda el arrastre con la ruedita (solo
  estilo de navegación SolidWorks, sin teclas, solo vistas 3D, solo en LikeSolidWorks UI).
  Menú "Velocidad de giro...", de fábrica x1,5. Medido en FreeCAD real.

- Vista de informe oculta por defecto (pedido del usuario, 2026-10-25): se abre a mano con
  Ver → Paneles → Vista de informe cuando haga falta mirar errores. Mientras está en
  LikeSolidWorks UI tampoco se abre sola (preferencias OutputWindow, se devuelven al salir).
  Probado en FreeCAD real.
- Usar siempre LikeSolidWorks UI (pedido del usuario, 2026-10-25): arranque en el banco
  (AutoloadModule, el anterior queda guardado), vuelta automática si algo cambia de banco
  (señal workbenchActivated; la página de Inicio cambia desde C++), selector oculto. Escape:
  menú "Usar siempre LikeSolidWorks UI". `swui/fork/always_swui.py`. Probado en FreeCAD real.
- Aspecto SW 2018 claro (pedido del usuario, 2026-10-25, con capturas de su SW):
  `swui/fork/look_sw.py` cambia las tablas del original (theme.COLORS, view_background,
  overlay_panels) y agrega preferencias del croquis (Mod/Sketcher/View, con copia propia).
  Panel izquierdo: Modelo y Tareas en pestañas (panel_sw.py), sin títulos repetidos.
  Probado en FreeCAD real. Pendiente de decidir: la mitad de abajo del panel Modelo (Ver/Datos,
  propiedades de FreeCAD) no existe en SW; los ejes rojo/verde del croquis tampoco.
- Barras Archivo y Editar ocultas en LikeSolidWorks UI (pedido del usuario, 2026-10-25).
  En su lugar, íconos Nuevo/Abrir/Guardar/Deshacer/Recalcular a la derecha de la barra de menú
  (`swui/fork/quick_access.py`, área "MenuBarRightArea" de FreeCAD 1.1). Probado en FreeCAD real.
  Panel Ver/Datos: se deja por ahora, el usuario va a ver si le sirve.
- Estrategia acordada: todo módulo nuevo (chapa, simulación FEM) como pestaña de la cinta dentro
  de LikeSolidWorks UI, con flujo y nombres SW sobre las herramientas nativas.

## Falta (fase 0)
- [x] Prueba del usuario (2026-10-25): conforme, "ahora sí se parece más a SW".

## Problemas reportados por el usuario
- 2026-10-25: al extruir un croquis saltaba a Part Design y el diálogo quedaba nativo. **Arreglado.**
- 2026-10-25: Croquis sin selección caía en "Seleccione un plano" (solo planos base con nombres
  de FreeCAD, no acepta caras). **Reemplazado por el panel propio.**
- 2026-10-25: con la cinta en español Windows avisa "Unable to set geometry 1614x705": la
  ventana no entra en 1366 px y se corta el borde derecho (Tareas y Vista de informe).

## Decisiones
- Fase 1 (chapa) **cajoneada por un tiempo** a pedido del usuario (2026-10-25).
- Pendiente para más adelante: plantillas de rótulo en español (hoy un dibujo nuevo en español
  usa la plantilla en inglés). Decimales con coma en "Formato de línea" (hoy solo en alemán).
- Panel de tareas: **solo a la izquierda, sin opción a la derecha**: se busca similitud total
  con SW (usuario, 2026-10-25). Es propio del fork, no se propone al original.
- Código propio del fork: en `swui/fork/`, comentarios en español, mensajes sin tr().

## PR al original
| Rama | Contenido | Estado |
|---|---|---|
| `fix/test-windows-pfade` | Test pasa en Windows | lista, sin proponer (consultar al usuario) |
| `feat/ribbon-schmal` | Cinta para pantallas chicas (incluye `fix/test-windows-pfade`) | lista, sin proponer |
| `fix/feature-dialog-bleibt` | Diálogos no saltan a Part Design; términos SW en Windows (incluye `fix/test-windows-pfade`) | lista, sin proponer |
| `feat/skizze-ohne-auswahl` | Croquis/extruir sin selección (incluye `fix/feature-dialog-bleibt`); textos es se agregan en master | lista, sin proponer |
| `feat/sprache-es` | Idioma español + Automático según FreeCAD | lista, sin proponer; el test de esa rama sola necesita también `fix/test-windows-pfade` en Windows |
