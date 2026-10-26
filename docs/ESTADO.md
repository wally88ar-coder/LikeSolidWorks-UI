# Estado del fork

Última actualización: 2026-10-27 (fin de la tercera sesión de trabajo). Todo subido a `origin`.

## Fase actual
- **Fase 0 — Puesta en marcha: terminada y probada por el usuario.**
- **Árbol de operaciones estilo SW (trabajo extra, no estaba en las fases): terminado**
  (etapas A, B y C; la franja Material/Ecuaciones/Sólidos pasó a la fase 3). Detalle y estado
  de pruebas en la sección "Plan: árbol de operaciones" de abajo.
- **Aristas del modelo dentro del croquis (como SW): terminado y probado por el usuario.**
- **Fase 1 (chapa) sigue cajoneada.**
- **Fase 2 — Flujos de pieza: código completo (2026-10-27); falta que la pruebe el usuario**
  salvo el redondeo (probado por él: "anda OK"). Todo lo del plan está hecho: redondeo, chaflán,
  matriz lineal y circular, simetría, asistente para taladro, ángulo de salida, y términos SW en
  barrido, hélice y referencia; además árbol flotante, paneles SW de plano/eje/punto, y planos
  En ángulo / Punto medio que siguen a la pieza. Detalle en "Plan: fase 2" > Avance.
- **Próximo paso:** que el usuario pruebe la fase 2 con una pieza suya (lista sugerida: chaflán,
  matriz lineal con Dirección 2, circular alrededor de un agujero, simetría eligiendo el plano en
  el árbol flotante, taladro refrentado y roscado, ángulo de salida, planos a distancia / en
  ángulo / punto medio cambiando una cota, eje en un cilindro).
- **Fase 3 — Evaluar: analizada con el usuario (2026-10-26), sin código.** Plan y respuestas en
  "Plan: fase 3". Falta su OK para arrancar por el punto 1 (Material).

## Preguntas para el usuario
Respuestas del usuario (2026-10-27) a las dudas de la fase 2: 1) matriz/simetría arrancan vacías
como SW: **hecho**; 2) matriz vieja en Longitud total -> Espaciado: OK; 3) ver el árbol con el panel
abierto: **hecho** (árbol flotante sobre la vista); 4) taladro Posiciones antes de Tipo: OK;
6) plano de referencia con panel como SW: **hecho** (y también eje y punto, por coherencia).
Pendiente:
- 5) Rosca en planos: **sí, la quiere** (representación simplificada: círculo de 3/4 fino de
  frente, líneas finas en lateral/corte). Decidido: va con el trabajo de planos (ver Falta).
- Pedido a FreeCAD (planos en ángulo / punto medio): el usuario lo dejó por ahora.

## Plan: fase 3 — Evaluar (analizado con el usuario el 2026-10-26, sin código)
Verificado en 1.1.4 sin GUI:
- Material: `ShapeMaterial` (Materials::PropertyMaterial) ya existe en Body y en todo Part::Feature;
  biblioteca System de ~200 materiales (nombres en inglés/DIN; varios de "Appearance" y
  "Machining" sin densidad; con densidad p. ej. Steel-Generic 7,9e-6 kg/mm³, Aluminum-6061-T6,
  Copper-Generic). Comandos `Std_SetMaterial` / `Std_SetAppearance` en `lib/MatGui.pyd`.
  **El archivo guarda solo el UUID del material**: si al abrir no está en la biblioteca, FreeCAD
  dice "Material not found" y lo deja en "Default" (densidad 1 g/cm³) sin más aviso (probado).
  Buscado 2026-10-26: FreeCAD lo tiene anotado como pedido abierto #10902 "Embedded materials"
  (del autor del sistema de materiales, 2023, "Still pending" en 2025-01, sin fecha ni PR). No
  está en el roadmap (solo "mejorar materiales" en general) ni en la propuesta FEP-0006 (editor
  de materiales). Si llega algún día, el panel del fork cede a lo nativo.
- Propiedades físicas: `Shape.Volume/Area/CenterOfMass/MatrixOfInertia` y
  `Solid.PrincipalProperties` (momentos, ejes, radios de giro) andan. No hay `Std_MassProperties`
  en 1.1.4 (llega en 26.3).
- Ecuaciones: expresiones (`ExpressionEngine`), `App::VarSet` (`Std_VarSet`) y Spreadsheet.
- Medir: `Std_Measure` (MeasureGui) trae `Measure_es-AR.qm` compilado; aun así el usuario ve el
  panel en inglés (causa sin ver: probar en GUI).

Respuestas del usuario (2026-10-26): los materiales propios **los agrega él después** (la ventana
tiene que dejar crear y editar materiales); asignar material **nunca cambia el color** (no le
gusta eso de SW); masa en **kg**; usa **variables globales y ecuaciones entre cotas**; Medir
**como el de SW** (panel propio, no solo traducir).

Orden propuesto (cada parte termina en una versión que prueba el usuario):
1. Material: ventana estilo SW (categorías a la izquierda, propiedades a la derecha), crear y
   editar materiales propios (biblioteca User de FreeCAD, archivos .FCMat nativos). Asigna con
   `ShapeMaterial` sin tocar la apariencia. Por el problema del UUID: el addon guarda además una
   copia del material en el Body (propiedad oculta, nombre estable a decidir, p. ej.
   `SWUI_MaterialCopy`, JSON con nombre y propiedades) y al abrir un archivo cuyo material no está
   en la biblioteca avisa y ofrece recrearlo (importa al compartir piezas con amigos).
2. Propiedades físicas estilo SW: densidad, masa (kg), volumen, área, CDG, ejes y momentos
   principales, momentos en el CDG y en el origen; pieza entera o sólidos elegidos; en ensamblaje
   suma cada pieza con su material (posición global). Si existe `Std_MassProperties` (26.3+), cede.
3. Franja Material / Ecuaciones / Sólidos (n) arriba del árbol (clic abre 1 y 4).
4. Ecuaciones estilo SW: variables globales, cotas con ecuación, ecuaciones (nombre, valor,
   comentario). Por debajo expresiones + un VarSet de nombre estable. Cotas con nombre tipo SW
   ("D1@Croquis1") a mostrar sobre los nombres de FreeCAD (a definir).
5. Medir estilo SW: panel propio (distancia, mínima/máxima, entre centros, dX/dY/dZ, ángulo,
   radio/diámetro, longitud, área) en pieza y ensamblaje, sobre la medición de Part/Measure.
Límite avisado: no hay configuraciones (ni valor de ecuación por configuración).

## Plan: fase 2 (aprobado por el usuario el 2026-10-26)
Idea: paneles propios estilo PropertyManager de SW, con la lista de aristas/caras/operaciones
SIEMPRE esperando selección (clic agrega, clic sobre una ya elegida la saca; nada de botones
"Seleccionar" / "Agregar"), términos de SW en español y vista previa. Por debajo, siempre la
operación NATIVA de FreeCAD (el archivo guarda un objeto común de Part Design: abre sin el addon
y en versiones nuevas). Motivo: el usuario no supo elegir la arista nueva en el diálogo nativo de
redondeo al reparar una referencia (botón "Seleccionar" que hay que prender).

Orden (cada parte termina en una versión que prueba el usuario):
1. Redondeo: elementos a redondear, radio, propagación tangente, vista previa. Se abre también
   desde "Editar operación" y desde Reparar referencias (reasignar la arista perdida).
2. Chaflán: mismo panel; distancia-distancia y ángulo-distancia.
3. Simetría, matriz lineal y circular (sumadas por el usuario): operaciones a copiar por clic en
   el árbol o el modelo, dirección/eje tocando una arista o eje, plano de simetría tocando una
   cara o plano, espaciado e instancias. Verificado en 1.1.4 sin GUI: `LinearPattern` ya trae
   Dirección 2 nativa (`Direction2`, `Occurrences2`, `Length2`...), `Mode` = Extent/Spacing,
   `Spacings` (espaciado por instancia) y `TransformMode` = Features / Whole shape (= "Sólidos
   a crear una matriz" de SW) en las cuatro (también Mirrored, PolarPattern, MultiTransform).
   No hay "Instancias a saltear": no prometer (sería una operación propia).
4. Asistente para taladro con pestañas Tipo / Posiciones: elegir cara, clic donde van los
   agujeros y acotarlos; el panel arma solo el croquis de centros y el `PartDesign::Hole`.
5. Más livianos (términos SW + selección siempre activa sobre el panel nativo, como Extruir):
   ángulo de salida, barrido, hélice, geometría de referencia.
Límite avisado: redondeos complejos fallan más que en SW; el panel puede decir qué arista falló.

Avance:
- Redondeo: **hecho** (`swui/fork/dress_up_panel.py`). Probado en FreeCAD real con la pieza de
  prueba: nuevo sin selección, dos aristas, radio 5, clic en la cara amarilla saca su arista, OK
  (un solo paso de deshacer), editar y Cancelar (queda igual), nuevo y Cancelar (desaparece),
  Reparar referencias con arista perdida (en rojo, Supr, arista nueva, OK, sin problemas).
  "Propagación tangente" marcada y fija (OpenCASCADE siempre la hace). Sin "Radio variable" ni
  "Retroceso" (FreeCAD no los tiene). El radio con ecuación se muestra bloqueado.
  Probado por el usuario: OK. FreeCAD además dibuja en magenta el borde de las caras
  redondeadas mientras el panel está abierto (es suyo, del modo edición).
- Chaflán: **hecho** (mismo módulo, `ChamferPanel`). Probado en FreeCAD real: arista preelegida,
  segunda arista, distancia 4, Ángulo-distancia 30°, Distancia-distancia 4/2, OK, editar y
  Cancelar, y el redondeo sigue abriendo su panel. FreeCAD muestra flechas rojas de dirección
  (sirven como la flecha de SW). Falta que lo pruebe el usuario.
- Matriz lineal, circular y Simetría: **hechas** (`swui/fork/pattern_panel.py`, base común
  `SwPanel` en `dress_up_panel.py`). Probadas en FreeCAD real: lineal con arista X, 25 x 3,
  dirección 2 (arista Y, 30 x 2), sumar el corte tocando su cara, OK; circular con la cara del
  agujero como eje (se usa su borde circular: FreeCAD pide arista), 4 iguales en 360°, Cancelar;
  simetría con una cara lateral como plano, OK. La "vista previa superpuesta" magenta de FreeCAD
  (con un corte Por todo tapaba la pieza) se apaga mientras el panel está abierto y se devuelve
  la preferencia al cerrar. Falta que lo pruebe el usuario.
- Asistente para taladro: **hecho** (`swui/fork/hole_panel.py`). Sin selección usa el panel de
  elegir cara del original (`pick_plane.FEATURE_COMMANDS` + `PartDesign_Hole`, desde el fork), el
  croquis abre con Punto activo, al salir arranca `PartDesign_Hole` y el panel "Tipo" reemplaza
  al nativo. Taladro nuevo arranca ISO M6 agujero normal (FreeCAD arranca sin norma). Probado en
  FreeCAD real: cara, 2 puntos, Agujero M6 (Ø6,6), Refrentado ISO 4762, M8 Por todo,
  Avellanado ISO 10642, Roscado M8 prof. 8 (Ø6,8), OK, editar, Editar posiciones abre el croquis.
  Falta que lo pruebe el usuario.
- Ángulo de salida: **hecho** como panel propio (`DraftPanel` en `dress_up_panel.py`; es un
  DressUp como el redondeo). Probado en FreeCAD real: cara lateral preelegida, plano neutro =
  cara de abajo (la casilla pasa sola a la lista), 5°, OK.
- Árbol flotante (`swui/fork/flyout_tree.py`): con cualquier panel SW abierto, arriba a la
  izquierda de la vista (Origen plegado, operaciones con su croquis colgado); clic = elegir.
  Probado en FreeCAD real: simetría con "Vista lateral" y la operación elegidas desde ahí.
- Plano de referencia SW (`swui/fork/ref_plane_panel.py`): probado en FreeCAD real: distancia 10
  sobre la cara (z=20) e Invertir (z=0), ángulo 30° por una arista de la cara, punto medio entre
  Planta y la cara (z=5), tres vértices, y editar vuelve a mostrar lo elegido (propiedad oculta
  `SWUI_PlaneSpec`, nombre estable). Ángulo y punto medio: FreeCAD no tiene esos modos (ni hay
  pedido abierto, buscado 2026-10-27); el addon los recalcula después de cada reconstrucción
  (`resync`, observador de documento) y reconstruye una vez más si un plano se movió. Decidido con
  el usuario. Probado: espesor de la placa 10 -> 20 -> 5 y deshacer; el plano en ángulo sigue a la
  arista, el punto medio a la cara, y un croquis apoyado en el plano medio los sigue. Sin addon el
  plano queda donde estaba la última vez. Si una versión futura trae modos nativos
  (`NATIVE_MODES`, nombres supuestos), el panel los usa. "Número de planos" y "Proyectar": no
  (el usuario no los ve críticos). Borrador de pedido para FreeCAD en
  `docs/pedidos/freecad_planos_angulo_punto_medio.md`: guía de puntos para que lo escriba el
  usuario (FreeCAD no acepta pedidos escritos por IA, AI_POLICY.md; Claude no lo publica).
- Eje y punto SW (`swui/fork/ref_axis_point_panel.py`): probados: eje de cara cilíndrica (por su
  borde circular: el modo por inercia salía torcido con la cara cortada), dos planos, eje Y; punto
  en centro de arco y al 25 % de una arista.
- Barrido, hélice, geometría de referencia: **términos SW** sobre el diálogo nativo
  (`swui/fork/native_terms.py`, por objectName y listas por texto). Barrido: el botón del
  trayecto queda prendido si ya hay perfil. Probado en FreeCAD real (textos y botón).
  El plano de referencia sigue con el "Tipo de relación" de FreeCAD (modos de adjunción): no es
  el PropertyManager de SW (primera/segunda/tercera referencia con Paralelo, Perpendicular, A
  distancia...). Ver Preguntas.

## Pruebas del usuario (árbol y croquis)
Probado por él, OK: barra de retroceso arrastrable con gris, mover arriba/abajo, marca de la
operación al tocar una cara, suprimir / desactivar supresión, Ctrl+B / Ctrl+Q, "Guardar también
STEP" (el .step abre en SW 2018 sin errores), aristas del modelo en el croquis (con y sin
herramienta), Reparar referencias (caso croquis).
Probado solo por Claude en FreeCAD real: celeste SW en la selección del árbol y una sola marca
al tocar una cara, cotas con doble clic / un clic en croquis + Modificar, Chequear carpeta.
Cambios pedidos por él en el camino: barra espaciadora = **Medir** (en su SW la tiene así;
nunca la usó para ocultar); marca de la cara en celeste SW (#A6C8E3 / #4288B5) en vez de marco
naranja; un clic en un croquis muestra sus cotas y el doble clic lo abre (como SW 2018).
Pendiente para la fase 3: el panel de Medir de FreeCAD sale en inglés.

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
- C (grande), empezada 2026-10-26. Decisiones del usuario: doble clic como SW (muestra cotas, no
  abre el diálogo); la franja Material/Ecuaciones/Sólidos pasa a la fase 3.
  - Cotas con doble clic: **hecho** (`swui/fork/instant_dims.py`), probado en FreeCAD real con la
    pieza de prueba (árbol y cara, Modificar 100→120, Esc, deshacer). Falta que lo pruebe él.
    Muestra cotas de croquis (Distance/X/Y, Radius, Diameter, Angle) y de Pad/Pocket (Length),
    Fillet, Chamfer, Revolution/Groove. No: arrastrar cotas, Hole.
    Croquis (pedido del usuario, como SW 2018): un clic en el árbol muestra sus cotas (observador
    de selección, sirve también para los croquis de adentro de una operación); doble clic lo abre.
    Probado en FreeCAD real (3 de 3 corridas; en una corrida anterior el clic no las mostró, sin
    causa clara).
  - Reparar referencias: **hecho** (`swui/fork/repair_refs.py`), probado en FreeCAD real (apoyo
    perdido reparado solo; redondeo con arista perdida abre su diálogo). Probado por el usuario
    (2026-10-26): el croquis se reapoya solo, OK. El caso del redondeo no lo pudo terminar: no
    entendió cómo elegir la arista nueva en el diálogo nativo de FreeCAD (botón "Seleccionar"
    que hay que prender). Argumento para adaptar el diálogo de redondeo en la fase 2.
    El usuario dio por cerrada la etapa C así (Chequear carpeta sin probar por él).
    No reconstruye solo las aristas de un redondeo (no se sabe cuáles eran una vez perdidas).
  - Chequear carpeta: **hecho** (`swui/fork/folder_check.py`), probado en FreeCAD real con una
    carpeta de prueba (pieza buena, una con apoyo roto y una abierta; el archivo roto no se
    modifica; informe .txt). Falta que lo pruebe él.
  - Franja Material/Ecuaciones/Sólidos: pasada a la fase 3 (decisión del usuario).
  Con esto la etapa C quedó hecha (salvo la franja).
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
- **Trabajo de planos (TechDraw)**, cuando se encare: rosca simplificada automática para los
  agujeros roscados del asistente para taladro (FreeCAD 1.1.4 trae a mano
  `TechDraw_ExtensionThreadHoleBottom/HoleSide/BoltBottom/BoltSide`, que hacen líneas cosméticas
  que NO siguen a la pieza): el addon las pone solo al crear/actualizar vistas, con el Ø nominal,
  y las rehace si cambia el modelo; además esos 4 botones en la pestaña Dibujo.
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
- `SWUI_PlaneSpec` (texto JSON en los planos hechos con el panel SW): nombre estable (2026-10-27).
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
