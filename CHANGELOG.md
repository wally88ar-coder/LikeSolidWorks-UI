# Änderungen / Changelog

Neueste Version oben. / Newest version first.

## Unveröffentlicht / Unreleased

**Deutsch**
- Oberfläche auch auf **Spanisch** (`swui/lang/es.py`), Begriffe wie im
  spanischen SOLIDWORKS (Croquis, Extruir saliente/base, Relaciones de
  posición, Planta/Alzado/Vista lateral …).
- *Automatisch* nimmt FreeCADs Sprache, wenn es dafür eine Sprachdatei gibt
  (bisher nur Deutsch, sonst Englisch); erkennt auch „Spanish (Argentina)“.
- **Kleine Bildschirme:** Das Ribbon erzwingt keine Mindestbreite des
  Fensters mehr (bisher ~1460 px – bei 1366 px ragte das Fenster rechts
  über den Rand). Passt ein Reiter nicht, zeigen die großen Knöpfe nur das
  Symbol (Name im Tooltip, wie in SOLIDWORKS ohne „große Knöpfe mit
  Text“); reicht das nicht, erscheinen Pfeile zum Verschieben.
- Feature-Dialoge (Linear austragen, Verrundung …) wechselten in FreeCAD
  1.1.4 selbst zur Workbench Part Design – Ribbon weg, Dialog ohne
  SW-Begriffe. Sie bleiben jetzt in LikeSolidWorks UI.
- SW-Begriffe in den Dialogen auch unter Windows (Objektname dort
  `PartDesignGui__…` statt `PartDesignGui::…`).
- **Skizze / Linear austragen / Linearer Schnitt ohne Auswahl** wie in
  SOLIDWORKS: Ebene oder ebene Fläche im Grafikbereich, im Baum oder in
  der Liste wählen, die Skizze öffnet sich darauf; bei Austragen/Schnitt
  startet das Feature nach „Skizze beenden“. Bisher: FreeCADs Dialog mit
  nur den Ursprungsebenen (Flächen nicht wählbar), beim automatisch
  angelegten Körper noch mit FreeCADs Ebenennamen.
  Auch ein Körper von der Startseite („Plano XY“ …) bekommt beim Öffnen
  des Panels die SW-Ebenennamen; ein Klick in die Liste brach unter
  Windows mit „Access violation“ ab.
- `tools/test_load.py` läuft auch unter Windows (Pfadvergleiche).

**English**
- Interface also in **Spanish** (`swui/lang/es.py`), terms as in the
  Spanish SOLIDWORKS.
- *Automatic* uses FreeCAD's language whenever there is a language file for
  it (before: German, otherwise English); also recognises "Spanish (Argentina)".
- **Small screens:** the ribbon no longer forces a minimum window width
  (before ~1460 px – on 1366 px screens the window was cut off on the
  right). If a tab does not fit, the large buttons show only their icon
  (name in the tooltip); if that is still too wide, arrows appear to scroll.
- Feature dialogs (Extruded Boss/Base, Fillet …) switched to the Part Design
  workbench by themselves in FreeCAD 1.1.4 – ribbon gone, no SW terms. They
  now stay in LikeSolidWorks UI.
- SW terms in the dialogs also on Windows (object name `PartDesignGui__…`
  there instead of `PartDesignGui::…`).
- **Sketch / Extruded Boss / Extruded Cut without a selection** as in
  SOLIDWORKS: pick a plane or planar face in the graphics area, the tree or
  the list, the sketch opens on it; for boss/cut the feature starts after
  "Exit Sketch". Before: FreeCAD's dialog with only the origin planes (faces
  not selectable).
- `tools/test_load.py` also runs on Windows (path comparisons).

**Fork (wally88ar-coder, español)**
- **Aspecto claro de SOLIDWORKS 2018** (colores medidos en capturas): cinta y paneles
  #F7F7F7, pestañas #D4D4D4, fondo degradado gris-celeste a blanco; croquis en azul puro
  (líneas 2 px, constructivas 1 px trazo y punto), resaltado naranja, aristas negras 1 px.
- Sin las barras Archivo y Editar (nuevo/abrir/guardar, deshacer/rehacer/recalcular):
  quedan los menús y los atajos de teclado. En su lugar, **íconos de acceso rápido** en la
  barra de menú (Nuevo, Abrir, Guardar, Deshacer, Recalcular), como en la barra de título
  de SW 2018.
- Panel izquierdo como en SOLIDWORKS: **Modelo y Tareas en pestañas** sobre fondo gris
  claro (el árbol ya no flota sobre la vista 3D); al abrir una operación pasa solo a Tareas
  y al cerrarla vuelve al árbol.
  Vista de informe abajo y **oculta** (se abre con Ver → Paneles → Vista de
  informe); dentro de LikeSolidWorks UI no se abre sola ante avisos/errores.
  Código propio del fork en `swui/fork/`.
- **Usar siempre LikeSolidWorks UI** (menú *LikeSolidWorks UI*, con tilde): FreeCAD
  arranca en LikeSolidWorks UI, vuelve a él si algo cambia de banco (por ejemplo
  "Cuerpo paramétrico" o "Ensamblaje" en la página de Inicio) y oculta el selector de
  bancos. Desmarcado, todo vuelve a ser como en FreeCAD.
- **Velocidad de giro** con la ruedita del mouse (menú *LikeSolidWorks UI →
  Velocidad de giro…*): x1 (como FreeCAD), x1,5 (de fábrica), x2, x2,5. Medido a
  1366 px: x1 = 16°, x1,5 = 25°, x2 = 35° por cada 100 px de arrastre.
- **Teclas N y F** como en SOLIDWORKS: **F** ajusta y centra todo, al instante (sin la
  animación de FreeCAD ni la espera por el atajo "F, S" del filtro de caras, que se quita
  dentro de LikeSolidWorks UI); **N** = *Normal a*, con animación:
  con una cara plana o un plano seleccionado lo mira de frente (otra vez N: del otro
  lado), editando un croquis mira el croquis de frente, y sin selección gira a la vista
  estándar más cercana. El "arriba" queda derecho. En un campo de texto la letra se
  escribe normalmente. Solo dentro de LikeSolidWorks UI (`swui/fork/view_keys.py`).
- Panel para elegir plano: los planos de un cuerpo creado desde la página de Inicio
  también se llaman Planta / Alzado / Vista lateral.
- **Árbol de operaciones como el FeatureManager de SW (etapa A)**. Clic derecho sobre una
  operación (en el árbol o sobre una cara), arriba de todo: *Editar operación*, *Editar
  croquis*, *Suprimir* (también lo que depende de ella, como en SW), *Desactivar supresión*
  (con o sin dependientes), *Retroceder* (la barra queda justo antes de la operación),
  *Avanzar*, *Avanzar hasta el final* y *Padre/Hijo…*. Por debajo, la "punta" del cuerpo y
  la supresión nativas de FreeCAD; se puede deshacer. "Toggle Freeze" se oculta del menú:
  en 1.1.4 cuelga FreeCAD al guardar.
- **Ctrl+B** reconstruye y **Ctrl+Q** fuerza la reconstrucción de todo; si quedan errores
  se abre **¿Qué es incorrecto?** (también en el menú *LikeSolidWorks UI*), con el
  mensaje de FreeCAD explicado en palabras simples. Dentro de LikeSolidWorks UI, Ctrl+B
  deja de ser el zoom de ventana de FreeCAD.
- **Barra espaciadora = Medir** (como la tiene el usuario en su SW). Dentro de LikeSolidWorks
  UI deja de ser "Alternar visibilidad" de FreeCAD (ocultar sigue en el clic derecho).
- Al crear un cuerpo, el árbol muestra abiertos el cuerpo y su Origen (Planta, Alzado,
  Vista lateral a la vista). Al guardar una pieza retrocedida, aviso con *Avanzar hasta el
  final y guardar*. Código en `swui/fork/feature_tree.py`, `rebuild_keys.py` y
  `tree_dialogs.py`.
- **Árbol, etapa B**: **barra de retroceso** amarilla debajo de la última operación, que
  se arrastra con el mouse (manito) como en SW; lo que queda debajo se ve **en gris**, y lo
  suprimido también. Clic derecho *Mover arriba* / *Mover abajo* (con su croquis); si
  rompería una dependencia, avisa por qué no se puede. Al elegir una cara en la vista, la
  operación que la creó se marca en el árbol **como en SW 2018: fondo celeste con borde
  azul** sobre ícono y nombre, y la última operación (que FreeCAD selecciona porque es la
  que se ve) ya no aparece resaltada: queda una sola marca, como en SW. Elegir en el árbol
  también se ve en celeste con borde y texto oscuro (antes azul fuerte con letra blanca). Menú *LikeSolidWorks UI → Guardar también STEP* (apagado de fábrica):
  al guardar deja al lado un `.step` con el mismo nombre, como resguardo sin historial.
  Código en `swui/fork/tree_overlay.py` y `step_copy.py`.
- **Aristas y vértices del modelo dentro del croquis, como en SW**: con una herramienta
  activa (cota inteligente, relaciones, línea, círculo…), al pasar el mouse a menos de 10 px
  de una arista o vértice de la pieza se **resalta en naranja** (primero vértices); al hacer
  clic se trae sola como referencia (lo mismo que *Convertir entidades*) y el clic cae justo
  sobre ella: la cota o la línea quedan enganchadas aunque no se apunte exacto. También una
  arista que coincide con un eje del croquis (gana la arista, como en SW). **Sin herramienta**
  (seleccionando) también: elegir un punto del croquis y después una arista del sólido la
  suma a la selección, y el panel *Agregar relaciones* ofrece *Sobre entidad*. Antes había que
  traerla a mano; FreeCAD 1.1.4 no deja tocar el modelo desde el croquis. No trae aristas de
  operaciones posteriores al croquis. Desde FreeCAD 26.3, que ya lo hace, queda lo nativo
  (`swui/fork/sketch_model_edges.py`).
- Árbol: un croquis suelto debajo de la última operación ya no aparece en gris (solo lo que
  queda debajo de la barra).
- **Mover arriba / abajo con redondeos y chaflanes en el medio**: FreeCAD los apoya en el
  sólido anterior por número de arista, y al cambiar el orden esos números cambian (el
  redondeo quedaba en otra arista sin avisar, o con error). Ahora se vuelven a buscar las
  mismas aristas por su forma, como en SW. El padre de un redondeo es la operación que creó
  sus aristas (no la de justo arriba): ya se puede mover un redondeo por encima de un corte
  que no lo afecta. Si después de mover algo queda con error, avisa y ofrece deshacer.
- **Cotas con doble clic (estilo Instant3D)**: doble clic en una operación o croquis del
  árbol, o en una cara de la pieza (la operación que la creó), muestra sobre el modelo sus
  cotas con líneas y flechas: las del croquis (distancias, Ø, R, ángulos) y las de la
  operación (profundidad, radio de redondeo, distancia de chaflán, ángulo de revolución).
  Clic en un valor abre **Modificar** (✓, ✗, ↻ reconstruir; acepta "12,5"); se puede
  deshacer. Las cotas atadas a una ecuación se marcan con Σ. Esc o un clic en otro lado las
  esconde. Como en SW, el doble clic ya no abre el diálogo: para eso, clic derecho → *Editar
  operación* (`swui/fork/instant_dims.py`). **Croquis, como en SW 2018: un clic** en el árbol
  (también en los que están adentro de una operación) muestra sus cotas y se pueden cambiar;
  el doble clic abre el croquis.
- **Reparar referencias…** (menú *LikeSolidWorks UI*, botón en "¿Qué es incorrecto?" y clic
  derecho de una operación con error): lista los croquis/planos que perdieron la cara donde
  se apoyaban, los redondeos/chaflanes que perdieron aristas y los croquis con referencias
  del modelo perdidas. Si hay una sola cara plana donde estaba el croquis, lo reapoya solo;
  si no, abre el editor de apoyo de FreeCAD o el diálogo de la operación para volver a
  elegir (`swui/fork/repair_refs.py`).
- **Chequear carpeta…** (menú *LikeSolidWorks UI*), para el día que se cambia de versión de
  FreeCAD: abre sin mostrar cada pieza de una carpeta (y subcarpetas), la recalcula entera,
  junta errores y referencias perdidas y la cierra **sin guardar**; las piezas abiertas no se
  tocan. Lista con doble clic para abrir y *Guardar informe* (.txt en la carpeta)
  (`swui/fork/folder_check.py`).
- *Desactivar supresión con dependientes* también devuelve los redondeos/chaflanes de la
  operación (antes quedaban suprimidos). "¿Qué es incorrecto?" explica el error de una
  operación sin sólido antes (por ejemplo, un corte con la base suprimida).
- **Panel de Redondeo como el PropertyManager de SW** (fase 2): la lista *Elementos a
  redondear* siempre espera selección (clic en una arista o cara la agrega, otro clic o Supr la
  saca; clic en la cara amarilla de la vista previa también), radio, vista previa con las caras
  nuevas en amarillo y aviso claro si FreeCAD no puede hacer el redondeo. Reemplaza al diálogo
  de FreeCAD desde la cinta, el menú, *Editar operación* y *Reparar referencias* (las
  referencias perdidas salen en rojo). Por debajo sigue siendo el redondeo de FreeCAD
  (`swui/fork/dress_up_panel.py`).
- **Panel de Chaflán** igual al de redondeo, con los tipos de SW: *Ángulo-distancia* o
  *Distancia-distancia* (con *Distancia igual*) e *Invertir dirección*.
- **Paneles de Matriz lineal, Matriz circular y Simetría** estilo SW: casillas de selección
  (la activa en rosado; arista, eje o cara plana; en la circular también una cara cilíndrica
  como eje), *Dirección 2*, *Espaciado* e *Instancias*, *Separación igual*, *Operaciones y caras*
  (clic en una cara suma la operación que la creó), *Sólidos* (toda la pieza) y vista previa con
  las copias en amarillo. Se apaga la vista previa magenta de FreeCAD mientras el panel está
  abierto (`swui/fork/pattern_panel.py`).
- **Asistente para taladro con flujo SW**: sin nada elegido, se toca la cara plana, se abre el
  croquis con la herramienta Punto lista (Posiciones), y al salir del croquis aparece el panel
  *Tipo*: Refrentado / Avellanado / Agujero / Agujero roscado, estándar ISO (también rosca fina,
  UNC, UNF o sin norma), tipo de tornillo (ISO 4762, DIN 7984, ISO 10642...), tamaño (M6...),
  ajuste (Ajustado / Normal / Holgado), condición final, fondo, rosca; *Editar posiciones* vuelve
  al croquis. Todo sobre el taladro y las tablas de FreeCAD (`swui/fork/hole_panel.py`).
- **Árbol flotante** sobre la vista mientras un panel SW está abierto (como el FeatureManager
  desplegable de SW): un clic en una operación, plano o eje lo elige para el panel; el título lo
  pliega (`swui/fork/flyout_tree.py`). Matriz y Simetría nuevas arrancan con la lista de
  operaciones vacía, como SW (antes: toda la pieza).
- **Geometría de referencia como SW**: *Plano* con Primera/Segunda/Tercera referencia y sus
  relaciones (Coincidente, Paralelo, Perpendicular, Distancia con Invertir, Ángulo, Punto medio,
  Tangente) y el estado *Totalmente definido*; *Eje* (Una línea/arista/eje, Dos planos, Dos
  puntos, Superficie cilíndrica, Punto y cara) y *Punto* (Centro de arco, Centro de cara,
  Intersección, Proyección, A lo largo de la curva) con la lista *Selecciones*. Por debajo, los
  planos/ejes/puntos de referencia de FreeCAD (`swui/fork/ref_plane_panel.py`,
  `ref_axis_point_panel.py`). Los planos *En ángulo* y *Punto medio* (FreeCAD no los tiene) los
  recalcula el addon en cada reconstrucción: siguen a la pieza y a lo que se apoya en ellos.
- **Panel de Ángulo de salida** estilo SW: ángulo, *Plano neutro* (casilla rosada que espera una
  cara plana o un plano) y *Caras de salida*, con vista previa.
- **Términos de SW** en los diálogos que siguen siendo de FreeCAD: barrido (Perfil, Trayecto,
  Esquinas, Tipo de orientación/torsión: Seguir trayecto…), hélice (Definido por: Altura y paso,
  Paso y revolución…; Paso, Revoluciones, Sentido antihorario) y plano/eje/punto de referencia
  (textos que quedaban en inglés). En el barrido, con el perfil ya elegido, queda esperando el
  trayecto sin apretar nada (`swui/fork/native_terms.py`).
- **Pestaña Evaluar como en SW** (fase 3): *Medir*, *Propiedades físicas*, *Ecuaciones* y
  *Editar material*, con íconos propios (`tools/fork/make_icons_fork.py`).
- **Material**: ventana con *Materiales de FreeCAD* (por categoría, en castellano, solo los que
  tienen densidad) y *Materiales personalizados* que uno crea, copia, edita y borra (archivos
  .FCMat nativos en la biblioteca del usuario). Se asigna a lo elegido o a toda la pieza **sin
  cambiar el color**. Cada pieza guarda una copia del material: si se abre el archivo en una PC
  que no lo tiene (FreeCAD lo cambiaría por "Default" sin avisar), el addon avisa y lo recrea
  igual (`swui/fork/material.py`).
- **Propiedades físicas** con el informe de SW: densidad, masa en kg, volumen, área, centro de
  masa (marcado en la vista), ejes y momentos principales, momentos en el centro de masa y en el
  origen. Pieza entera, sólidos elegidos o ensamblaje (cada pieza con su material y en su
  lugar). Sin material: 1000 kg/m³, como SW (`swui/fork/mass_props.py`).
- **Ecuaciones, variables globales y cotas**: tabla como la de SW ("Largo" = 120,
  "D1@Croquis1" = "Largo" / 2...), lista de cotas para insertar con doble clic, funciones de SW
  (sqr, iif...), coma decimal; Aceptar es un solo paso de deshacer y Cancelar deja todo igual.
  Por debajo, expresiones y un VarSet de FreeCAD (abre sin el addon). Doble clic en una cota con
  ecuación abre la ventana (`swui/fork/equations.py`).
- **Medir** estilo SW (también con la barra espaciadora): cada clic suma un elemento, clic en el
  vacío borra; distancia con dX/dY/dZ, centro a centro en círculos y cilindros, distancia
  normal, ángulo, longitud, diámetro, área y perímetro; dibuja la distancia en la vista y mide
  bien en ensamblajes (`swui/fork/measure_sw.py`). Reemplaza al Medir de FreeCAD, en inglés.
  Tercera opción **Distancia máxima** (FreeCAD no la trae): entre bordes de agujeros como SW y
  entre cualquier otra geometría, con cálculo propio exacto (`swui/fork/max_distance.py`).
  *Centro a centro* también entre un agujero y una cara plana, arista recta o vértice (desde el
  eje del agujero, como SW).
  En la vista, como SW: línea de la distancia con su recuadro y la escalera de proyecciones
  dX (roja), dY (verde) y dZ (azul) con sus valores; siguen al girar el modelo (casilla para
  apagarlas).
- **Franja Ecuaciones / Sólidos(n) / Material** arriba del árbol, como las carpetas del
  FeatureManager (`swui/fork/tree_strip.py`).
- **Multicuerpo, etapa A** (cada sólido de SW = un Cuerpo de FreeCAD): Propiedades físicas y la
  franja ya no cuentan dos veces un Cuerpo usado en una Booleana (Combinar) o en un Dividir;
  *Sólidos(n)* marca con ⚠ un Cuerpo que tiene varios sólidos sueltos adentro.
- **Multicuerpo, etapa B**: en Extruir y Revolución, casilla **Fusionar resultado** (apagada, la
  operación queda como un sólido aparte en un Cuerpo nuevo) y, en los cortes, **Alcance de la
  operación** (Todos los sólidos / Sólidos seleccionados / Selección automática, como SW): el corte
  se copia en cada sólido elegido y las copias siguen las medidas del original. Todo con objetos
  nativos de FreeCAD: el archivo se abre y se recalcula bien sin el addon (`swui/fork/multibody.py`).
  Borrar el corte original (Supr) borra también sus copias en un solo paso; "Hasta la cara" se
  lleva a los otros sólidos; con selección automática, si el corte cambia y pasa a atravesar otro
  sólido, el addon pregunta si actualizar el alcance.
- **Simetría de sólidos** como SW: "Sólidos para simetría" y "Fusionar sólidos"; apagado, cada
  sólido espejado queda como sólido aparte que sigue al original (`swui/fork/mirror_bodies.py`).
- **Alcance de la operación en el Asistente para taladro**, igual que en los cortes.
- **Combinar** (pestaña Operaciones) con el panel de SW: Agregar / Eliminar / Común, sólidos
  elegidos con clics; por debajo la Booleana nativa de FreeCAD (`swui/fork/combine_panel.py`).
- **Mover cara** (pestaña Operaciones, fase 4) con el panel de SW: Equidistanciar / Trasladar
  (dirección o ΔX ΔY ΔZ) / Girar alrededor de una arista, solo caras planas, también en sólidos
  importados. Por debajo Extruir o Cortar desde la cara y el Ángulo de salida nativos: el archivo
  abre y se recalcula sin el addon (`swui/fork/move_face.py`). Límite: con caras vecinas
  inclinadas, mover (no girar) deja un escalón en vez de prolongarlas.
- **Mover/Copiar sólido** (pestaña Operaciones, botón con menú) con el panel de SW: sólidos,
  Copiar + cantidad, Trasladar (arista + distancia o ΔX ΔY ΔZ), Girar (arista + ángulo o centro +
  ángulos), también **de un vértice a otro** (sigue a los vértices si la pieza cambia). Cada copia
  (o el sólido movido) es un Cuerpo nuevo que sigue al original; al mover, lo de antes queda en el
  original oculto (`swui/fork/move_bodies.py`). Sin Restricciones (decisión del usuario).
- **Eliminar/Conservar sólidos** (mismo botón) para Cuerpos enteros y para los pedazos que deja un
  corte; cada pedazo que queda es un Cuerpo nuevo, elegido por un punto adentro (sigue siendo el
  mismo aunque cambien las cotas). Borrar la operación con Supr (o editarla con la lista vacía)
  devuelve los sólidos, como SW (`swui/fork/delete_bodies.py`).

## 0.10.0 — 2026-10-18

**Deutsch**
- Oberfläche auf **Deutsch und Englisch** – Knopf *Language* im Reiter
  Evaluieren (Automatisch wie FreeCAD / Deutsch / English), wirkt sofort.
  Englische SOLIDWORKS-Begriffe im Ribbon, in den Dialogen und im Baum
  (Sketch1, Boss-Extrude1, Top Plane, Mates, Sheet1 …).
- Reiter *Evaluieren* ganz links, damit man die Sprache sofort findet.
- **„Skizze erstellen“ unter dem Mauspfeil** nach einem Klick auf eine
  ebene Fläche (blasst beim Wegbewegen aus).
- Zeichnungen:
  - englische Vorlagen A4 hoch / A3 quer (ISO 7200, Feld „Unit“)
  - **Projektionsmethode je Zeichnung wählbar** (Methode 1 / Methode 3),
    Symbol im Schriftfeld wechselt mit
  - **Linieneigenschaften**: Linienart, Strichstärke (ISO 128), Farbe
  - **Formen** auf dem Blatt (Linie, Rechteck, Kreis, Bogen, Vieleck) in
    einer Blatt-Skizze mit allen Abhängigkeiten, frei verschiebbar
  - **Text** per Klick aufs Blatt, Schriftgröße in mm oder pt
  - Export: zwei Blätter konnten denselben Dateinamen bekommen – behoben
- Kompatibilität: Fenster öffnen auch unter Qt5/PySide2; laufende
  Platzier-Modi enden beim Werkbankwechsel; geprüft gegen FreeCAD 1.0.2,
  1.1.4 und den Entwicklungsstand.
- Erste Freigabe über den Zweig `release`.

**English**
- Interface in **German and English** — *Language* button in the Evaluate
  tab (automatic like FreeCAD / German / English), switches immediately.
  English SOLIDWORKS terms in the ribbon, dialogs and tree.
- Evaluate tab moved to the far left so the language is easy to find.
- **"Sketch" context symbol** next to the pointer after clicking a planar
  face (fades out when moving away).
- Drawings: English title block templates (ISO 7200, "Unit" field);
  **projection method per drawing** (first/third angle) with matching
  symbol; **Line Format** (style, ISO 128 thickness, colour); **shapes** on
  the sheet in a sheet sketch with all relations, movable; **text** by
  clicking on the sheet, font size in mm or pt; fixed duplicate file names
  when exporting several sheets.
- Compatibility: dialogs also open with Qt5/PySide2; placement modes end
  when switching workbenches; checked against FreeCAD 1.0.2, 1.1.4 and the
  development version.
- First release through the `release` branch.

## 0.9.0 — 2026-10-18

**Deutsch** – Erste Veröffentlichung: Ribbon im Stil des
SOLIDWORKS-CommandManagers, dunkles Farbschema, SOLIDWORKS-Namen und
-Begriffe für Teile, Skizzen, Baugruppen und Zeichnungen, Beziehungs- und
Verknüpfungs-Panel, Drag & Drop in Baugruppen, Zeichnung erstellen mit
ISO-7200-Schriftfeld, Blatteigenschaften, Oberflächenangabe (ISO 1302),
Schweißsymbol (ISO 2553), PDF/DXF-Export, eigene Symbole.

**English** – First public version: CommandManager-style ribbon, dark
theme, SOLIDWORKS names and terms for parts, sketches, assemblies and
drawings, relations and mates panels, drag & drop into assemblies, drawing
creation with ISO 7200 title block, sheet properties, surface finish
(ISO 1302), weld symbol (ISO 2553), PDF/DXF export, own icons.
