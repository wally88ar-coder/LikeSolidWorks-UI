# Notas técnicas (para quien siga el trabajo)

## Probar
- Test sin GUI (antes de cada entrega): `D:\Freecad\bin\python.exe tools/test_load.py .`
  Debe terminar en `ERGEBNIS: OK`. Simula FreeCAD con objetos falsos (Qt = MagicMock).
- Prueba en FreeCAD REAL, sin tocar la configuración del usuario:
  `tools/fork/gui_probe.py` es una plantilla. Copiarla al scratchpad, completar los pasos y correr
  ```
  cp %APPDATA%/FreeCAD/v1-1/user.cfg <scratch>/user.cfg
  timeout 90 D:/Freecad/bin/freecad.exe -u <scratch>/user.cfg <scratch>/probe.py
  ```
  `-u` usa una copia de la configuración (FreeCAD la guarda al cerrar). El script escribe un
  JSON y capturas PNG; leerlas con la herramienta de imágenes.
  - Capturas: `mw.grab()` sirve para la interfaz; la vista 3D puede salir atrasada si hay
    animación (esperar o usar `view.saveImage(...)`).
  - Si FreeCAD queda colgado (diálogo modal, excepción sin cerrar), `timeout` lo mata. Cerrar
    siempre los documentos antes de `mw.close()` (si no, pregunta "¿guardar?" y se cuelga).
  - Envolver cada paso en try/except y volcar el JSON después de CADA paso.
  - Simular el mouse: `QApplication.sendEvent(viewport, QMouseEvent(...))` sobre
    `QGraphicsView.viewport()` de la vista `Gui::View3DInventor`.
- El usuario puede tener su FreeCAD abierto (proceso sin argumentos): no tocarlo.
- Medir colores de capturas del usuario: `QImage(...).pixelColor(x, y)` con el Python de FreeCAD.

## FreeCAD 1.1.4 en Windows: hallazgos
- Los nombres de objeto de formularios usan `__` en vez de `::` (`PartDesignGui__TaskPadPocketParameters`).
- Part Design cambia de banco al abrir cualquier diálogo de operación vía
  `Gui.activateWorkbench('PartDesignWorkbench')` ejecutado desde C++ (archivo `"<string>"`).
- La página de Inicio ("Cuerpo paramétrico", "Ensamblaje") cambia de banco desde C++ sin pasar por
  Python: solo se puede reaccionar después con la señal `MainWindow.workbenchActivated(nombre)`.
- `ParamGet(...).GetBools()` devuelve solo los NOMBRES (no pares nombre-valor).
- Barra de menú: FreeCAD 1.1 trae `MenuBarLeftArea` / `MenuBarRightArea` como cornerWidgets.
- Al tabificar paneles, Qt deja barras de pestañas vacías encima de la buena: ocultarlas.
  FreeCAD repone la barra de título del panel Tareas al abrir operaciones: volver a quitarla.
- Preferencias útiles: `View/RotationMode`, `View/OrbitStyle`, `General/AutoloadModule`,
  `OutputWindow/checkShowReportViewOn*`, `Mod/Sketcher/View/EdgeWidth|ConstructionWidth|ConstructionPattern`,
  `View/HighlightColor|SelectionColor|DefaultShapeLineWidth|BackgroundColor2/3/4`.

## Herramientas (entorno de Claude Code)
- En la consola Bash, un `\n` dentro de un heredoc puede llegar convertido en salto de línea real
  al archivo: para textos con `\n` en código Python, editar con la herramienta Edit/Write.
- `git config core.autocrlf=true`: los avisos "LF will be replaced by CRLF" son normales.

## Arquitectura del fork
- `swui/fork/__init__.py` instala todo (cada parte en su try). Se llama desde `InitGui.Initialize`.
- Patrón: cambiar tablas/funciones del original desde afuera (`layout._dock_right`, `layout.enter`,
  `layout.leave`, `theme.COLORS`, `theme.build_qss`, `view_background._target_values`,
  `overlay_panels.TARGET`), marcando cada envoltura con un atributo `_swui_*` para no envolver dos
  veces. Toda preferencia que se cambie se guarda antes y se devuelve al salir del banco.
- `tools/test_load.py` (del original) tiene chequeos agregados del fork, marcados "fork".
- Selección: `getSelectionEx()` (resuelta) da las formas en coordenadas LOCALES del objeto;
  para la posición real (cuerpo girado, ensamblaje) usar `getSelectionEx("", 0)` y
  `raiz.getSubObject(sub)`; un `App::Plane` no tiene forma: `getSubObject(sub, retType=3)`
  da su Placement global.
- Cámara: `view.getCameraOrientation()` / `setCameraOrientation(Rotation)` (anima). Una
  animación en curso (p. ej. `viewIsometric()`) pisa un giro pedido enseguida: en pruebas,
  esperar ~1,5 s entre pasos.
- Atajos: `QTest.keyClick` dispara atajos de verdad (sendEvent no). Editando un croquis la
  vista 3D se queda con las teclas sueltas: los atajos de la ventana no llegan.
- `Std_ViewFitAll` SÍ anima (con "UseNavigationAnimations"): `animatedViewAll(10, 20)` corre
  los pasos DENTRO de la llamada (~0,35 s bloqueando) y recién después vuelve; por eso leer la
  cámara justo después la da final y parece instantáneo (error mío del 25/10, lo destapó un
  video del usuario). Medir el TIEMPO de la llamada, no la cámara. Sin animación: apagar la
  preferencia, `SendMsgToActiveView("ViewFit")`, prenderla (FreeCAD la aplica en el acto).
- `runCommand` desde dentro de otro comando queda para después (no correr un comando de
  FreeCAD desde el Activated de otro si importa el momento).
- Un atajo de varias teclas que empieza con la tecla suelta ("F, S" de Part_SelectFilter,
  acción [2] del grupo, invisible para `Command.get(...).getShortcut()`) hace esperar ~0,3 s
  a la tecla suelta. Buscar con `mw.findChildren(QAction)` y `shortcuts()`.
- Menú de clic derecho: `FreeCADGui.addWorkbenchManipulator(obj)` con
  `modifyContextMenu(recipient)` (recipient "Tree" o "View") que devuelve
  `[{"insert": cmd, "menuItem": "Std_Placement"}]` inserta ANTES de ese comando ("Separator" vale).
  El manipulador es global: revisar el banco activo. En el árbol FreeCAD igual pone arriba las
  opciones del objeto ("Editar vaciado", "Suprimido", "Toggle Freeze"): `feature_tree.arrange_menu`
  las reordena al mostrarse el menú (filtro de eventos de la aplicación, solo dentro del banco).
  Las acciones de comandos tienen objectName = nombre del comando.
- **No usar Std_ToggleFreeze**: con un croquis congelado, guardar el documento cuelga FreeCAD 1.1.4
  (probado dos veces). Para suprimir sin errores, apagar el apoyo del croquis (MapMode "Deactivated").
- Part Design: las operaciones de sólido son `isDerivedFrom("PartDesign::Feature")` (croquis, planos
  de referencia y binders no). `Suppressed` existe en 1.1.4. Los vínculos de una operación incluyen
  `BaseFeature` (el sólido anterior: no es "padre" en sentido SW) y `_Body`.
- `PySide.QtTest` no existe en el envoltorio de FreeCAD: `from PySide6.QtTest import QTest`.
  Los íconos del árbol y la vista 3D se refrescan después: capturar ~1 s más tarde.
- Videos: medir cuadro a cuadro con ffmpeg a 30 fps en gris crudo + numpy (caja de píxeles
  oscuros de la pieza por cuadro); las hojas de miniaturas no alcanzan para ver animaciones.
- Videos del usuario: ffmpeg 9.0.2 instalado con winget (Gyan.FFmpeg, solo su usuario) en
  `%LOCALAPPDATA%/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.2-full_build/bin/`
  (alias `ffmpeg` en consolas nuevas). Sacar cuadros: `ffmpeg -i video.mp4 -vf fps=2 <scratch>/c_%03d.png`.
