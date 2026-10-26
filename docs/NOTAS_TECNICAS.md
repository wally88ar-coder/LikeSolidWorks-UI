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
- Árbol (`Gui::TreeWidget`): **no guardar QTreeWidgetItem** para usarlos después; PySide los da
  por borrados ("Internal C++ object already deleted"). Medir rectángulos en el momento. Los
  renglones se relacionan con objetos por Label (`doc.getObjectsByLabel`); el renglón de primer
  nivel es el documento. Dibujar encima: widget hermano del viewport (hijo del árbol, no del
  viewport, así no se corre al desplazar), transparente al mouse; arrastre con filtro en el viewport.
- Estilo de los renglones del árbol: FreeCAD 1.1 los pinta con el estilo de una vista interna
  `QTreeView#DocumentTreeItems` (hija de `Gui::TreeWidget`): un estilo cambiado solo en el
  TreeWidget no se ve. Una regla `::item:selected` agregada al final no le gana a la primera:
  sacar la vieja (regex) y poner la nueva. Estilar `::branch` borra la flechita de abrir/cerrar;
  la zona de la flechita se pinta con el fondo de `::item:selected`.
- Part Design: `Body.removeObject(f)` + `Body.insertObject(f, otro, after)` reordena y reengancha
  BaseFeature solo; si se saca la punta, la punta pasa a la anterior (volver a ponerla).
  `Shape.getElementHistory` no devuelve nada útil en 1.1.4: para "qué operación creó esta cara"
  se compara geometría (misma superficie en la operación anterior).
- Redondeo/chaflán (`PartDesign::DressUp`): `Base` = (sólido anterior, ["EdgeN"...]) y FreeCAD
  lo sigue al cambiar BaseFeature, pero con los MISMOS números de arista: al reordenar quedan en
  otra arista o con error. `feature_tree.move` guarda la forma de cada arista antes y las vuelve a
  buscar por forma (misma recta/circunferencia y superpuestas) en el sólido nuevo.
- Croquis en edición: el modelo no se puede preseleccionar, pero `view.getObjectsInfo((x, y))`
  (coordenadas Coin: y desde abajo, píxeles reales = Qt * devicePixelRatio) devuelve también las
  aristas cercanas del sólido. Con una herramienta del croquis activa el cursor del viewport es
  `BitmapCursor`. `sketch.addExternal("Pad", "Edge10")` + `sketch.recompute()` y un MouseMove
  sintético en el mismo punto: el croquis la preselecciona y el clic la toma. No usar
  `view.getCursorPos()` (es el cursor real, no el del evento). Dos Esc seguidos cierran el croquis.
  `view.getPointOnViewport` da puntos fuera de la ventana si la cámara no los muestra (ajustar antes).
  Es rápido (~0,05 ms por punto): proyectar aristas discretizadas una vez por posición de cámara.
  Resaltar en la vista: pivy `SoAnnotation` (encima de todo) con SoLineSet/SoMarkerSet agregado a
  `view.getSceneGraph()`. Forma global con los mismos índices: `Part.getShape(raíz, "Pad.")` usando
  `obj.getParents()`. Una referencia externa encima de un eje del croquis le gana al eje en la
  preselección.
- Sin herramienta (cursor flecha) la preselección del croquis (`Selection.getPreselection()`)
  no se actualiza con movimientos sintéticos y puede quedar vieja: medir en pantalla si hay
  geometría del croquis cerca (`View/PickRadius`). En ese modo el croquis elige al SOLTAR el
  botón: para sumar una referencia a la selección usar
  `Selection.addSelection(doc, sketch, "ExternalEdgeN")` (N desde 1, orden de ExternalGeometry)
  y no dejar pasar ese soltar.
- `PySide.QtTest` no existe en el envoltorio de FreeCAD: `from PySide6.QtTest import QTest`.
  Los íconos del árbol y la vista 3D se refrescan después: capturar ~1 s más tarde.
- Videos: medir cuadro a cuadro con ffmpeg a 30 fps en gris crudo + numpy (caja de píxeles
  oscuros de la pieza por cuadro); las hojas de miniaturas no alcanzan para ver animaciones.
- Videos del usuario: ffmpeg 9.0.2 instalado con winget (Gyan.FFmpeg, solo su usuario) en
  `%LOCALAPPDATA%/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-9.0.2-full_build/bin/`
  (alias `ffmpeg` en consolas nuevas). Sacar cuadros: `ffmpeg -i video.mp4 -vf fps=2 <scratch>/c_%03d.png`.
- Reemplazar un diálogo de operación por uno propio: observador de documento de Gui
  (`FreeCADGui.addDocumentObserver`) con `slotInEdit(vp)`; fuera del slot (QTimer 0)
  `Control.closeDialog()` cierra el diálogo nativo SIN cancelarlo: la operación, el modo edición
  y la transacción del comando ("Make Fillet") quedan abiertos. Editar una existente no abre
  transacción (abrir una propia). **`resetEdit()` confirma la transacción pendiente**: para
  cancelar, `abortTransaction()` primero y después `resetEdit()`. Sin selección,
  `PartDesign_Fillet` crea igual el redondeo (vacío, con error) sobre la punta y lo pone en edición.
- En el envoltorio de PySide de FreeCAD 1.1 (Qt6), `QAction` está en `QtGui`, no en `QtWidgets`.
- Paneles SW sobre operaciones nativas (`swui/fork/dress_up_panel.py`): base `SwPanel` +
  registro `PANELS` {TypeId: clase}; `pattern_panel.py` y `hole_panel.py` suman los suyos en su
  `install()`. Para un tipo nuevo: subclase con `_build` (self.form), `_apply` (valores al objeto,
  devuelve un problema o ""), `_pick(obj, sub)` y registrarla.
- La "vista previa superpuesta" magenta de Part Design es la preferencia
  `Mod/PartDesign/Preview/ShowTransparentPreview`; se apaga con la casilla
  `showTransparentPreviewCheckBox` del diálogo nativo antes de cerrarlo y se devuelve al cerrar.
- `PartDesign_LinearPattern/PolarPattern/Mirrored/Draft/Hole` crean el objeto y lo ponen en edición
  igual que el redondeo (sin selección: matriz/simetría arrancan en "Whole shape"). La matriz
  circular pide una ARISTA como eje ("Axis reference must be an edge"): una cara cilíndrica se
  cambia por un borde circular suyo. `ThreadSize` del taladro: "M6x1.0" (no "M6"); con
  `ThreadType` "None" el tamaño es "---". Las tablas de tornillos están en
  `<recursos>/Mod/PartDesign/Resources/Hole/*.json` (`cut_type` counterbore/countersink).
- Taladro sin selección: `pick_plane.FEATURE_COMMANDS` (del original) se extiende desde el fork
  con `PartDesign_Hole`, y `pick_plane.arm` se envuelve para prender `Sketcher_CreatePoint`.
- En las pruebas: no llamar `dump` a una función propia (la plantilla ya tiene `dump()`); una lista
  guardada en el log se vuelca al final (guardar copias: `list(...)`).

## Fase 3 (Evaluar): hallazgos en FreeCAD 1.1.4
- Materiales: `Materials.MaterialManager()`; `MaterialLibraries` da tuplas (nombre, carpeta,
  ícono): "System" (`D:/Freecad/data/Mod/Material/Resources/Materials`) y "User"
  (`%APPDATA%/FreeCAD/v1-1/Material`, no existe hasta que se guarda algo). Con las preferencias
  `Mod/Material/Resources` UseMaterialsFromConfigDir=False, UseMaterialsFromCustomDir=True y
  CustomMaterialsDir=<carpeta> aparece una biblioteca "Custom": así se prueba sin tocar la del
  usuario (en una copia de user.cfg). No hay `defaultMaterial()`: el "Default" tiene UUID
  `7f9fd73b-50c9-41d8-b7b2-575a030c1eeb` (está en System y tiene densidad: filtrarlo).
- `ShapeMaterial` se guarda en el archivo SOLO como UUID (`<PropertyMaterial uuid=.../>`). Material
  que falta al abrir: "Material not found" en la consola y queda "Default". Un .FCMat escrito a
  mano (YAML, ver `material.fcmat_text`) con el mismo UUID + `refresh()` lo vuelve a encontrar.
  `refresh()` NO olvida un material cuyo archivo se borró (sigue hasta reiniciar): las pruebas de
  "material faltante" van en otro proceso.
- Asignar `ShapeMaterial` desde Python no cambió `ShapeAppearance` en la prueba, pero igual se
  guarda y se devuelve la apariencia (versiones nuevas podrían cambiarla).
- `getPhysicalValue` da Quantity (`getValueAs("kg/m^3")`), float (Poisson, en float32: 0,29 ->
  0,28999999) o None; propiedad del modelo sin valor = nan.
- Inercia: `Solid.MatrixOfInertia` es el tensor en el centro de masa con densidad 1 (fuera de la
  diagonal -∫xy). Un compuesto no tiene MatrixOfInertia ni CenterOfMass: sumar sólido por sólido
  (Steiner, `mass_props.combine`).
- Expresiones: aceptan coma decimal (FreeCAD la guarda como punto), trigonometría en grados,
  `a ? b : c`, `trunc`, `sqrt`. En un VarSet FreeCAD guarda las referencias a sí mismo SIN el
  nombre del objeto ("Largo / 4"). Una PropertyFloat acepta un resultado con mm (lo guarda sin
  unidad). Ruta de una cota de croquis: `.Constraints.D1` o `.Constraints[3]`; de una operación,
  `Length` (sin punto). `renameConstraint(i, "D1")` deja la ecuación atada aunque se borren cotas.
  `setDocumentationOfProperty` cambia el comentario de una propiedad dinámica.
- `doc.openTransaction` al abrir la ventana + varios cambios + `abortTransaction` deshace todo
  (también un VarSet creado y un renombre de cota). Por eso Ecuaciones es modal.
- Selección en ensamblajes: el observador (`addSelection(doc, obj, sub, pnt)`) recibe el objeto
  RESUELTO (p. ej. "Box", "Face6"), sin la ruta del componente. La ruta completa sale de
  `Selection.getSelectionEx("", 0)` (raíz "Ensamblaje", sub "Pieza1.Box.Face6");
  `raíz.getSubObject(sub)` da la forma en su posición real y `Part.getShape(raíz, "Pieza1.",
  needSubElement=False)` el sólido entero ubicado. Los vínculos del original se llaman "Body<1>".
- Un clic del usuario en la vista llega como clearSelection + addSelection; un clic en el vacío,
  solo clearSelection: Medir espera 60 ms para distinguirlos.
- Las ventanas sueltas (QDialog) no salen en `mw.grab()`: capturarlas con `dialogo.grab()`.
- El test arma la cinta esperada desde `ribbon_layout.py` por AST; el fork suma
  `swui/fork/evaluate_tab.py` (`_fork_layout_commands`, `FORK_REPLACED`) y sus textos en castellano
  no se exigen en de/en.
- Distancia máxima (`max_distance.py`): OpenCASCADE no la trae (BRepExtrema/distToShape es solo la
  mínima). `Edge.valueAt(t)` / `Face.valueAt(u, v)` dan el punto en posición real (con la
  ubicación de la forma); `Face.ParameterRange` y `Face.isInside(p, tol, True)` para caras
  recortadas. Las esferas tienen aristas degeneradas (polos, `Edge.Degenerated`) cuyo `.Curve`
  da "undefined curve type": saltearlas. La primera llamada tarda ~1,5 s más (carga de numpy).
