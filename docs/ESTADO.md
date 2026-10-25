# Estado del fork

Última actualización: 2026-10-25

## Fase actual
**Fase 0 — Puesta en marcha** (en curso)

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

## Falta (fase 0)
- [ ] Pantallas chicas (1366 px): cinta que se compacte o desplace. En español la cinta pide
      1614 px de ancho mínimo (en inglés 1458): la ventana queda cortada a la derecha.
- [ ] Panel de tareas a la izquierda (decidido), como opción.
- [ ] Extruir / extruir corte sin croquis: elegir cara plana o plano, abrir croquis, lanzar al salir.

## Problemas reportados por el usuario
- 2026-10-25: con la cinta en español Windows avisa "Unable to set geometry 1614x705": la
  ventana no entra en 1366 px y se corta el borde derecho (Tareas y Vista de informe).

## Decisiones
- Pendiente para más adelante: plantillas de rótulo en español (hoy un dibujo nuevo en español
  usa la plantilla en inglés). Decimales con coma en "Formato de línea" (hoy solo en alemán).
- Panel de tareas: **a la izquierda**, como el PropertyManager de SW (usuario, 2026-10-25).
  Hacerlo como opción para poder proponerlo al original sin cambiar su comportamiento.

## PR al original
| Rama | Contenido | Estado |
|---|---|---|
| `fix/test-windows-pfade` | Test pasa en Windows | lista, sin proponer (consultar al usuario) |
| `feat/sprache-es` | Idioma español + Automático según FreeCAD | lista, sin proponer; el test de esa rama sola necesita también `fix/test-windows-pfade` en Windows |
