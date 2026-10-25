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

## Falta (fase 0)
- [ ] Probar en la interfaz que el addon carga (lo valida el usuario).
- [ ] Traducción al español (`swui/lang/es.py`) + que "Automático" elija español si FreeCAD está
      en español (hoy solo elige alemán o inglés).
- [ ] Pantallas chicas (1366 px): cinta que se compacte o desplace.
- [ ] Extruir / extruir corte sin croquis: elegir cara plana o plano, abrir croquis, lanzar al salir.

## Problemas reportados por el usuario
(ninguno todavía)

## Decisiones
- Pendiente: panel de tareas a la izquierda (como SW) o a la derecha (como el original).

## PR al original
| Rama | Contenido | Estado |
|---|---|---|
| `fix/test-windows-pfade` | Test pasa en Windows | lista, sin proponer (consultar al usuario) |
