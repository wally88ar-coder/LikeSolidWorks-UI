# Estado del fork

Última actualización: 2026-10-25 (fin de la primera sesión de trabajo)

## Fase actual
**Fase 0 — Puesta en marcha: terminada y probada por el usuario** ("ahora sí se parece más a SW").
Después se hicieron retoques de interfaz pedidos por el usuario (ver "Hecho").
**Fase 1 (chapa) cajoneada por un tiempo** a pedido del usuario. Próximo trabajo: lo que él pida.
Árbol de operaciones estilo SW (sección "Plan" abajo): **etapas A y B hechas (2026-10-25)**.
El usuario probó la barra de retroceso arrastrable con gris debajo ("quedó muy bien", capturas
del 2026-10-25); el resto de A y B, probado con la plantilla, sin confirmación suya todavía.
Pieza de prueba para mover operaciones (pedida por el usuario), armada por Claude en
`C:\Users\Windows\Documents\FreeCAD pruebas\Prueba mover operaciones.FCStd`: base 100x60x10,
tetón Ø20x15 sobre su cara, corte Ø30 Por todo desde Planta que pisa el tetón, redondeo R2 en
la arista de arriba del tetón. Al prepararla apareció que mover rompía/cambiaba los redondeos:
corregido (ver CHANGELOG). **Mover arriba/abajo probado por el usuario con esa pieza: "anduvo
OK" (2026-10-25).** Marco naranja (cara → operación) también probado por él: OK; después
pidió el estilo SW: ahora fondo celeste #A6C8E3 con borde #4288B5 sobre ícono y nombre (colores
medidos en su captura de SW 2018), pintado en modo "multiplicar" para que el texto siga negro.
Probando suprimir con esa pieza (sin GUI) apareció que "Desactivar supresión con dependientes"
dejaba el redondeo suprimido (mientras el tetón está suprimido no se sabe qué arista usa):
corregido, ahora va por tandas recalculando. El usuario probó suprimir (pasos 1-6 con esa pieza):
anduvo, el tetón vuelve a su lugar. Salía un aviso rojo "subshape not found Pad.Face6" al
desactivar la supresión de la base (el apoyo del croquis se devolvía antes de recalcular la
base): corregido.
Ctrl+B / Ctrl+Q probados por el usuario: OK. "Guardar también STEP" probado: el .step abrió en
SW 2018 sin errores (Diagnóstico de importación). Barra espaciadora: andaba, pero el usuario
la tiene en SW para **Medir** (nunca la usó para ocultar): cambiada a Std_Measure (probado en
FreeCAD real). El panel de Medir de FreeCAD sale en inglés (Measurement, Mode, Result):
pendiente para la fase 3 (Evaluar).
Etapa C sin empezar.

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
- `view_keys.py`: **teclas N (normal a) y F (ajustar)** como SW. N: cara plana/plano
  seleccionado (repetida sobre la misma cara: del otro lado), croquis en edición, o vista
  estándar más cercana sin selección; "arriba" derecho. Acciones propias en la ventana +
  filtro en la vista 3D (en croquis la vista se queda con las teclas). Probado en FreeCAD
  real y probado por el usuario (2026-10-25, "quedó OK"). Confirmado por él en SW 2018: N sin
  selección va a la vista estándar más cercana. F sin animación (pedido del usuario; la N sí
  anima, a propósito) y sin la espera de ~0,3 s del atajo "F, S" (filtro de caras de Part,
  quitado dentro de LikeSolidWorks UI y devuelto al salir).

## Plan: árbol de operaciones como el FeatureManager de SW (analizado, sin empezar)
Analizado con el usuario el 2026-10-25, sin código todavía. Se hace para FreeCAD 1.1.4, porque el
usuario se va a quedar unos 2 años en esa versión. Cada función revisa si FreeCAD ya lo hace y, si
lo hace, usa lo nativo (así no choca con la 26.3 ni con las que vengan). Verificado en la 1.1.4 sin
GUI: ya trae `Suppressed` en las operaciones, `Tip` y `AllowCompound` en el Body, y
`Shape.getElementHistory` (registro de caras).

Puntos (qué hace el addon / qué pasa con la 26.3):
1. Estructura: franja propia arriba de la pestaña Modelo con Material / Ecuaciones / Sólidos (n)
   (va con la fase 3; el árbol de FreeCAD no acepta renglones inventados); Origen abierto al crear
   la pieza. Propiedades físicas: propias en 1.1.4; en 26.3+ usar `Std_MassProperties` nativo.
2. Barra de retroceso: menú "Retroceder / Avanzar uno / Avanzar hasta el final" sobre la `Tip`
   nativa y aviso al guardar con la pieza retrocedida; después, barra arrastrable dibujada sobre el
   árbol (lo más frágil del plan, siempre con el menú como respaldo). La 26.3 no trae nada de esto.
3. Reconstrucción y errores: Ctrl+B / Ctrl+Q; diálogo "¿Qué es incorrecto?" (sumar la info nueva de
   la 26.3: referencias rotas marcadas en el árbol, notificaciones de redondeos); "Reparar
   referencias" sobre el registro de caras. Seguir reconstruyendo tras un error: imposible (límite
   de FreeCAD).
4. Editar: menú "Editar operación / Editar croquis"; clic en una cara que marque en el árbol la
   operación que la creó (registro de caras); cotas con doble clic tipo Instant3D en versión
   liviana (cajita "Modificar"; sin arrastre).
5. Reordenar / suprimir / padre-hijo: suprimir con menú SW sobre lo nativo, gris propio solo en
   1.1.4 (la 26.3 tacha sola); mover arriba/abajo revisando dependencias; diálogo Padre/Hijo con
   InList/OutList. Carpetas: descartado (el Body no admite grupos). Configuraciones: mucho después,
   sobre la tabla de configuraciones de Spreadsheet.
6. Mostrar/ocultar: barra espaciadora sobre una cara oculta el Body entero, solo en 1.1.4 (la 26.3
   ya lo hace).
7. Ensamblajes: nombres ya hechos por el original; "Fijar / Flotar" en el clic derecho (con la
   fase 5). La 26.3 ya no exige pieza fija para arrastrar.
8. Archivos a futuro: regla de nombres internos estables (ver Decisiones); opción "Guardar también
   STEP" al guardar; herramienta "Chequear carpeta" (abre y recalcula todas las piezas de una carpeta
   y lista las que dan error), para el día que el usuario salte de versión.

Etapas:
- A (rápida) — **HECHA** (`swui/fork/feature_tree.py`, `rebuild_keys.py`, `tree_dialogs.py`):
  menú contextual SW (editar, retroceder/avanzar, suprimir, Padre/Hijo), Ctrl+B / Ctrl+Q,
  "¿Qué es incorrecto?", Origen abierto, aviso de pieza retrocedida, barra espaciadora (al
  final: Medir, a pedido del usuario), regla de nombres estables. Suprimir también suprime los dependientes (como SW) y
  suelta el apoyo de los croquis/planos sobre caras suprimidas (MapMode "Deactivated", modo
  guardado en `SWUI_SuppressedMapMode`).
- B (media) — **HECHA** (`swui/fork/tree_overlay.py`, `step_copy.py`, más en `feature_tree.py`):
  barra arrastrable, gris en lo suprimido y lo retrocedido, mover arriba/abajo (clic derecho, con
  chequeo de dependencias y moviendo también su croquis), cara → operación en el árbol (marco
  naranja; la operación se busca por geometría: la más vieja que ya tenía una cara sobre la misma
  superficie), "Guardar también STEP" (apagado de fábrica). Quedó para más adelante: reordenar
  arrastrando operaciones con el mouse. Límite: FreeCAD sigue marcando en azul la última operación
  al elegir una cara (no se puede cambiar sin tocar FreeCAD).
- C (grande): cotas con doble clic, "Reparar referencias", franja (con fase 3), "Chequear carpeta".
- Descartado: carpetas, reconstruir tras un error. Configuraciones: mucho después.

## FreeCAD 26.3 (la que antes se iba a llamar 1.2)
- FreeCAD pasó a numerar por calendario (año.número): 26.3, 27.1 (rama 31/1/2027), 27.2, 27.3...
  Tres versiones por año.
- Al 2026-10-25: versión de prueba RC2 (18/10), 4 errores que frenan la salida y varios errores
  nuevos abiertos (STEP que no importa, cierre con redondeos imposibles, cotas en croquis). Final
  esperada para alrededor de noviembre. No se usa todavía.
- Archivos: las versiones nuevas abren los de la 1.1.4. El riesgo es que alguna operación se
  recalcule distinto (cambio de nombres de caras en 1.0, OpenCASCADE 8 en 26.3), y que los objetos
  de addons (SheetMetal, los del fork) necesitan su addon instalado.
- Revisar al actualizar (no antes): "Nuevo croquis" sin selección abre un diálogo nativo de
  ubicación (puede chocar con `pick_plane.py`); Ctrl+0 / botón para los paneles de abajo (el fork
  oculta la Vista de informe); varios documentos editándose a la vez (cambio Modelo/Tareas de
  `panel_sw.py`). Roadmap oficial: menciona una "barra de cinta" propia (podría competir con la
  cinta del addon; sin fecha).

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
- 2026-10-25 (video): en un croquis sobre una cara no se podían enganchar ni acotar las aristas
  del sólido. No era un error: FreeCAD 1.1.4 no deja tocar el modelo desde el croquis (hay que
  usar Convertir entidades; 26.3 sí lo permite). Hecho en el fork (`sketch_model_edges.py`): con
  una herramienta activa, un clic en una arista/vértice del modelo la trae sola como referencia.
  El usuario lo probó ("anduvo") y pidió que sea como SW: resaltar al pasar y con distancia de
  enganche. Hecho: resaltado naranja a menos de 10 px (vértices primero), el clic se manda sobre
  la arista; una arista sobre un eje del croquis gana al eje. Probado en FreeCAD real (cota a
  7 px, vértice, arista sobre eje). El usuario lo probó con línea y rectángulo ("funciona muy
  bien") y pidió lo mismo sin herramienta (punto del croquis + arista para relacionar). Hecho:
  sin herramienta la arista se suma a la selección y el panel de relaciones ofrece "Sobre
  entidad" (probado: queda PointOnObject). Falta que lo pruebe el usuario.
- 2026-10-25: panel "Croquis: seleccionar un plano" mostraba "Plano XY/XZ/YZ" (cuerpo creado
  desde la página de Inicio, en Part Design) y al hacer clic en la lista daba "Access violation"
  (el panel se cerraba durante el propio clic). Resuelto en `feat/skizze-ohne-auswahl` (+ master);
  en el fork, `always_swui` renombra los planos al volver de otro banco. Probado por él (2026-10-25): Planta/Alzado/Vista lateral y sin "Access violation".
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
- **Nombres internos estables (2026-10-25):** el nombre de clase/módulo con que se guarda en el
  archivo cada objeto propio del fork (p. ej. mover/rotar cara, FeaturePython) no cambia nunca. Si
  algún día hay que cambiarlo, dejar un alias y convertir los objetos viejos al abrir el archivo.
  Motivo: el usuario actualiza poco (~2 años por versión) y sus archivos tienen que abrir siempre.
- Desarrollar para la 1.1.4 aunque una versión nueva ya traiga la función (el usuario no la va a
  tener); cada función cede a lo nativo si la versión de FreeCAD lo trae.

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
