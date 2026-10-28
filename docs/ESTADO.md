# Estado del fork

Última actualización: 2026-10-27 (fase 5, ensamblaje: código completo de las etapas 1 a 5).

**Checklists compartidos con el usuario** (se tildan ahí; al cerrar algo, tildarlo también):
- Todas las fases: "Checklists del fork: qué falta en cada fase"
  (https://claude.ai/artifact/URHdbLtcw8n3aXAYoYt6U1).
- Fase 5 en detalle: "Fase 5 — Ensamblaje estilo SW 2018: plan y checklist"
  (https://claude.ai/artifact/YNSyZA5W3hnRB9McFjJGyf).
Al empezar una sesión, leerlos (docs tools, `read`) para ver qué tildó o comentó el usuario.

## Fase actual
- **Fase 0 — Puesta en marcha: terminada y probada por el usuario.**
- **Árbol de operaciones estilo SW (trabajo extra, no estaba en las fases): terminado**
  (etapas A, B y C; la franja Material/Ecuaciones/Sólidos pasó a la fase 3). Detalle y estado
  de pruebas en la sección "Plan: árbol de operaciones" de abajo.
- **Aristas del modelo dentro del croquis (como SW): terminado y probado por el usuario.**
- **Fase 1 — Chapa: versiones 1 a 3 hechas (2026-10-27/28); falta que las pruebe el usuario.**
  Pestaña Chapa con Brida base, Brida de arista, Dobladillo, Extruir corte, Convertir en chapa
  (STEP), Aplanar, Desdoblar/Doblar y Exportar DXF (también por lotes desde un ensamblaje). Las
  tres versiones del plan están hechas (ver "Plan: fase 1").
- **Fase 2 — Flujos de pieza: código completo (2026-10-27); falta que la pruebe el usuario**
  salvo el redondeo (probado por él: "anda OK"). Todo lo del plan está hecho: redondeo, chaflán,
  matriz lineal y circular, simetría, asistente para taladro, ángulo de salida, y términos SW en
  barrido, hélice y referencia; además árbol flotante, paneles SW de plano/eje/punto, y planos
  En ángulo / Punto medio que siguen a la pieza. Detalle en "Plan: fase 2" > Avance.
- **Fase 4 — Mover cara: terminada (2026-10-27)**, con operaciones nativas (Pad / Pocket /
  Draft), sin FeaturePython (aprobado por el usuario). Probado por él: girar cara ("muy bueno");
  falta que pruebe equidistanciar y trasladar.
- **Mover/Copiar sólido y Eliminar/Conservar sólidos: terminados (2026-10-27); falta que los
  pruebe el usuario.** Incluye "de un vértice a otro" y Supr que devuelve los sólidos.
  Restricciones: descartado por el usuario (ecuaciones a mano si hiciera falta).
  Con esto (y la chapa de la fase 1) está completo el "Alcance" del menú Insertar.
  Detalle de las tres en "Análisis: Mover/Copiar sólido..." > Hecho.
- **Próximo paso:** todas las fases tienen el código completo (la 0 está terminada). Falta que
  el usuario pruebe con piezas y conjuntos suyos: fase 1 (chapa, versiones 1 a 3), fase 2 (lista
  sugerida: chaflán, matriz lineal con Dirección 2, circular alrededor de un agujero, simetría
  eligiendo el plano en el árbol flotante, taladro refrentado y roscado, ángulo de salida, planos a
  distancia / en ángulo / punto medio cambiando una cota, eje en un cilindro), fase 3 (y sus
  decisiones), fase 4 (equidistanciar / trasladar cara), Mover/Copiar y Eliminar/Conservar
  sólidos, y fase 5 (etapas 2 a 5, checklist en el documento compartido). Después: planos
  (TechDraw, ver "Falta") o lo que elija el usuario.
- **Fase 3 — Evaluar: código completo (2026-10-26), hecha sola a pedido del usuario ("dale con
  toda la fase 3, yo estoy ocupado"); falta que la pruebe él y que revise las decisiones** de
  "Plan: fase 3" > Decisiones para revisar. Probada por Claude sin GUI y en FreeCAD real.
- **Fase 5 — Ensamblaje: código completo (etapas 1 a 5, 2026-10-27); falta que el usuario la
  pruebe con conjuntos suyos y que responda las casillas "Vos" del documento compartido** "Fase 5
  — Ensamblaje estilo SW 2018: plan y checklist" (https://claude.ai/artifact/YNSyZA5W3hnRB9McFjJGyf),
  donde se tilda etapa por etapa. Alcance (lo que el usuario usa de la pestaña Ensamblaje de SW):
  insertar, relaciones de posición, matriz de componentes lineal y circular, simetría de
  componentes, taladro y extruir corte de ensamblaje, geometría de referencia. Commits 3d61268,
  bc35bf6, 258df65, c6b3deb. Hallazgos técnicos en `docs/NOTAS_TECNICAS.md` > "Ensamblaje (fase 5)".
  - Etapa 1 — pruebas sin GUI (FreeCADCmd): todo anda con matices.
  - Etapa 2 — relaciones de posición (`swui/fork/mates_sw.py`): panel SW que queda abierto,
    tangente, Alineada/Antialineada, límites en la concéntrica, editar con doble clic,
    Fijar/Flotar y Ver relaciones en el clic derecho. Probada en FreeCAD real.
  - Etapa 3 — matriz y simetría de componentes (`swui/fork/component_patterns.py`): lineal (una o
    dos direcciones), circular, simetría misma pieza o versión opuesta. Probada en FreeCAD real.
  - Etapa 4 — taladro y corte de ensamblaje (`swui/fork/assembly_features.py`): el agujero queda
    dentro de cada pieza, sigue al croquis y se realinea si la pieza se mueve. Probada en FreeCAD real.
  - Etapa 5 — plano/eje/punto en el ensamblaje (`swui/fork/asm_reference.py`). Probada en FreeCAD real.
  - Decisiones del usuario (2026-10-27): 1) el addon avisa a las copias de una matriz cuando el
    motor mueve la semilla (observador, lógica propia aceptada); 2) la versión opuesta se
    reconstruye sola al abrirla; 3) el taladro de ensamblaje sigue solo a la pieza al moverla, como
    SW (observador que pone el binder en `vinculo.Placement.inverse() * croquis.Placement`);
    4) distancia a una cara = elegir la cara directo, sin plano apoyado.
  - Decidido por Claude sin consultar (revisar con el usuario):
    - Árbol: las relaciones NO cuelgan de cada componente (FreeCAD no deja agregar hijos a un
      vínculo); clic derecho "Ver relaciones de posición" las selecciona en la carpeta.
    - Límites solo en la concéntrica (FreeCAD los tiene solo en uniones cilíndricas, de giro y lineales).
    - Matriz: un vínculo con copias por semilla ("MatrizLineal1 Tornillo"), datos en un VarSet.
    - Versión opuesta: archivo "<pieza>-opuesta" en la carpeta de la original, sin preguntar.
    - Taladro: cada punto de posición lleva un círculo de 0,5 mm atado (el taladro solo toma
      círculos de la copia del croquis).
    - Plano/eje/punto hecho solo sobre el origen: queda fijo al aceptar (el motor ignora uno apoyado).
    - Matrices, simetrías, operaciones de ensamblaje y referencias se editan con clic derecho
      "Editar operación" (el doble clic sobre esos objetos es de FreeCAD o no hace nada en 1.1.4).
  - Pendiente que decida el usuario: pieza repetida en el ensamblaje con taladro (hoy sigue a la
    primera instancia y el panel avisa); nombre automático de la versión opuesta.
  - Falta (menor): aviso visible al abrir sola una pieza con agujeros del ensamblaje (hoy, vista
    de informes y nombre en el árbol); borrar una matriz entera de un golpe (borrar el VarSet deja
    las copias); un eje/punto fijo pierde sus selecciones al editarlo; la cinta no pasa sola a la
    pestaña Ensamblaje; doble clic en el taladro dentro de la pieza abre el diálogo de FreeCAD.

## Preguntas para el usuario
Respuestas del usuario (2026-10-27) a las dudas de la fase 2: 1) matriz/simetría arrancan vacías
como SW: **hecho**; 2) matriz vieja en Longitud total -> Espaciado: OK; 3) ver el árbol con el panel
abierto: **hecho** (árbol flotante sobre la vista); 4) taladro Posiciones antes de Tipo: OK;
6) plano de referencia con panel como SW: **hecho** (y también eje y punto, por coherencia).
Pendiente:
- 5) Rosca en planos: **sí, la quiere** (representación simplificada: círculo de 3/4 fino de
  frente, líneas finas en lateral/corte). Decidido: va con el trabajo de planos (ver Falta).
- Pedido a FreeCAD (planos en ángulo / punto medio): el usuario lo dejó por ahora.

## Plan: fase 1 — Chapa (aprobado por el usuario el 2026-10-27)
Por debajo el addon SheetMetal (0.8.26 instalado; usa networkx de
`%APPDATA%/FreeCAD/v1-1/AdditionalPythonPackages`), arriba paneles y nombres SW.
Respuestas del usuario: radio de plegado = espesor ("me funciona muy bien"); factor K no lo dijo
(Claude usó 0,5, el de fábrica de SW; se cambia en la Brida base); DXF bien simple, solo contorno y
líneas de plegado de trazos; nombre "pieza_espesor_material" con coma decimal; lotes, por ahora lo
más simple. No hace falta que mande piezas: Claude arma las de prueba y compara con la cuenta.
Versiones:
1. **HECHA (2026-10-27)**: pestaña Chapa (después de Croquis), Brida base, Brida de arista,
   Aplanar, Exportar DXF de una pieza.
2. Dobladillo, Convertir en chapa (piezas STEP de SW), cortes sobre la chapa, DXF por lotes desde
   un ensamblaje (un DXF por pieza, lo más simple).
3. **HECHA (2026-10-28)**: Desdoblar/Doblar (cortar sobre el plano y volver a plegar), sobre el
   "Wrap Cutout" de SheetMetal (`SMSketchOnSheet`). Desdoblar muestra el desarrollo (que SheetMetal
   deja en su lugar, apoyado en la cara fija), oculta la chapa plegada y abre un croquis en el
   Cuerpo sobre la cara fija ("Croquis-Desdoblar1", marca `SWUI_UnfoldCut`, **nombre estable**;
   al croquis se le apagan ShowSupport y HideDependent para que se vea el desarrollo). Doblar (o
   salir del croquis, con `pick_plane.arm`) arma "Corte-Desdoblado1" con el K atado a la Brida base
   y vuelve a plegar; sin dibujar nada, borra el croquis y solo vuelve a plegar. Probado en FreeCAD
   real: ranura 10x20 que cruza el pliegue (saca 400 mm³, saliendo del croquis), 6x12 cruzando el
   pliegue con Doblar con el croquis abierto (144 mm³), vacío, y el DXF con los dos huecos.
   **Límite de SheetMetal** (probado): un corte que queda entero sobre una brida (no toca la cara
   fija ni cruza un pliegue) no corta nada; el fork lo detecta, no deja la operación, avisa (usar
   Extruir corte sobre la cara de la brida) y el croquis queda para corregirlo con Desdoblar.
   Editar un Corte-Desdoblado (clic derecho > Editar operación) abre un panel del fork en lugar
   del de SheetMetal (pedido del usuario, 2026-10-28: "interfaz homogénea"): factor K ("Usar el
   factor K de la chapa" o propio) y "Editar croquis sobre el desarrollo", que despliega la chapa
   como estaba antes del corte (el desarrollo apunta al apoyo del corte; Aplanar/DXF lo vuelven a
   la punta), abre el croquis y al salir (o con Doblar) vuelve a plegar; si el corte quedó con
   error o entero sobre una brida, avisa. Probado en FreeCAD real (K 0,4 propio y de vuelta a la
   chapa, ranura movida de 45-55 a 65-75 sacando lo mismo, aviso). Queda un paso de deshacer vacío
   de SheetMetal ("WrappedCutout") al editar, como en las bridas.
   SW permite elegir qué pliegues desdoblar: acá se despliega todo.

Versión 2: **HECHA (2026-10-27/28**, el usuario se fue a dormir: "seguí trabajando"; falta que la
pruebe él). Botones nuevos en la pestaña Chapa: Dobladillo, Extruir corte, Convertir en chapa;
Exportar DXF en un ensamblaje exporta todas las chapas (un DXF por pieza, en la carpeta del
ensamblaje, aviso con la lista). Probado en FreeCAD real: dobladillo abierto con el panel SW;
corte desde la cara (pick_plane -> croquis -> Pocket nativo) y el DXF con el círculo; pieza
"importada" corrida y girada convertida (espesor 2 medido solo) + brida de arista sobre ella + su
DXF; ensamblaje con 3 vínculos a 2 piezas -> 2 DXF. Test en verde.
Decisiones (Claude, para revisar):
1. Convertir en chapa = solo chapas que ya vienen plegadas (STEP de SW). Convertir un sólido
   macizo como en SW (cara fija + aristas de pliegue) queda sin hacer.
2. En la pieza convertida, el radio de las bridas nuevas sale del pliegue más chico de la pieza
   (si no tiene pliegues, = espesor); el K, 0,5. Se cambian con "Convertir en chapa" otra vez.
3. Dobladillo nuevo: cerrado, longitud la última usada (10 la primera vez), radio y separación =
   espesor, Material interior.
4. Lotes: los Desarrollos se agregan a los archivos de cada pieza (quedan modificados sin guardar).
5. "Extruir corte" de la pestaña Chapa es el mismo Extruir corte de Operaciones (Pocket nativo).
Lo que se verificó antes de escribir el código (sin GUI):
- **Cortes**: el Extruir corte nativo (Pocket "Por todo") sobre la chapa anda; el desarrollo sale
  con el agujero y una brida de arista puesta después del corte también anda (U con brida de 20
  después del corte: desarrollo 93,42 = 42 + 26 + 16 + 2 × 4,712). Plan: botón "Extruir corte" en
  la pestaña Chapa que llame a `ribbon._run("PartDesign_Pocket")` (con un comando SWUI propio,
  para no repetir PartDesign_Pocket en la cinta: el test cuenta botones).
- **Convertir en chapa (STEP de SW)**: el Unfold despliega un sólido sin historia (76,712, bien) y
  `SheetMetalNewUnfolder.EstimateThickness.using_best_method(forma, i_cara)` da el espesor (2).
  Cuerpo con `BaseFeature` = sólido y `Body.Placement` = el del sólido (como `move_face._body_for`):
  FreeCAD 1.1.4 arma adentro un `PartDesign::FeatureBase` (es la punta). **Las bridas van apoyadas
  en ese FeatureBase**, no en el sólido importado: con el sólido de base la brida no sale y el
  Placement se aplica dos veces (probado con el sólido corrido y girado 30°). Plan: propiedad
  `SWUI_Sheet` en el Cuerpo (JSON: espesor detectado, radio, K, cara fija como punto + normal en
  coordenadas del Cuerpo; **nombre estable**); `sheet_metal` tiene que aceptar Cuerpos sin Brida
  base (espesor, K, radio y cara fija desde `SWUI_Sheet`; las bridas con radio por valor). El
  "Convertir en chapa" de SW sobre un sólido macizo (cara fija + aristas de pliegue) sería
  `SheetMetal_FromSolid` (caras a sacar + aristas a rasgar): queda para después.
- **Dobladillo** = `SMHem` (HemType Flat / Open / Teardrop / Rolled = Cerrado / Abierto / Lágrima /
  Laminado de SW; `width` = longitud, `opening` = separación, `radius` y `RollAngle` para lágrima y
  laminado). Placa 100x50x2, arista de arriba en y=50, longitud 10: "Material Inside" = no pasa
  la arista (y máx 50, = Material interior de SW); "Material Outside" = sale 2 (y 52, = Pliegue
  exterior); "Thickness Outside" da error (no ofrecerlo). En Cerrado el radio y IncludeBend no
  cambian la forma; `invert` lo pasa para abajo. Desarrollo de los cuatro: válido.
- Hecho así: `SWUI_Sheet` en el Cuerpo convertido con la cara fija como punto + normal
  (`sheet_metal.face_key` / `face_at`); `sheet_metal` acepta Cuerpos sin Brida base.

Hecho en la versión 1 (`swui/fork/sheet_metal.py` sin interfaz, `sheet_panels.py` paneles y
comandos, `sheet_tab.py` la pestaña; íconos `sm_*` en `make_icons_fork.py`):
- Brida base = `SMBaseBend` de SheetMetal (PartDesign::FeaturePython en el Cuerpo). Se llega como
  a Extruir: con el croquis abierto (from_sketch) o sin nada elegido (pick_plane: plano/cara ->
  croquis -> al salir se arma). Panel: Dirección 1 (profundidad, invertir, plano medio; solo perfil
  abierto), Parámetros de chapa (espesor, invertir = lado del espesor, "Radio = espesor" prendido
  de fábrica con la ecuación `Radius = Thickness`), Margen de pliegue (factor K en `SWUI_KFactor`,
  propiedad de la Brida base, **nombre estable**). Perfil abierto: de fábrica el croquis da las
  medidas de afuera (BendSide "Inside").
- Brida de arista = `SMBendWall`. Panel: aristas con clics (sin elegir nada antes también),
  "Usar radio predeterminado" (ecuación `radius = BaseBend.Radius`), ángulo, longitud, "Medida
  hasta" Exterior virtual / Interior virtual / Tangente al pliegue y Posición de brida. Equivalencias
  verificadas sin GUI (placa de 50, brida de 30, espesor 2, radio 2): Material interior = "Material
  Inside" (cara de afuera de la brida en la arista), Material exterior = "Thickness Outside",
  Pliegue exterior = "Material Outside"; exterior virtual = "Outer Sharp" (alto total 30).
- Editar una brida (clic derecho > Editar operación) abre el panel SW en lugar del de SheetMetal.
- Aplanar: Unfold de SheetMetal (raíz del documento, Label "Desarrollo", marca `SWUI_FlatOf` =
  Name del Cuerpo, **nombre estable**), K atado a la Brida base, cara fija = la cara grande de la
  Brida base del lado del croquis (buscada en la punta del Cuerpo cada vez que se usa). Desarrollo
  al 60 % de transparencia: SheetMetal dibuja el croquis de plegado en la cara de abajo.
- Exportar DXF: R12 escrito por el fork (capas CONTORNO continua y PLEGADO DASHED, mm, arranca en
  0,0, rectas seguidas unidas), al lado del .FCStd; sin guardar, pregunta dónde. Si existe, lo pisa
  (decidido por Claude: "un clic"; avisa en la barra de estado y en la Vista de informe).
- Probado sin GUI (desarrollo 76,712 = cuenta a mano con K 0,5; con espesor 3 y K 0,4, 74,597 =
  cuenta; reabierto en otro proceso se recalcula) y en FreeCAD real (Brida base por los dos
  caminos, placa y perfil en L, brida de arista elegida antes y con clic, Cancelar sin rastros,
  Aplanar y volver, DXF con 4 rectas de contorno + 1 de plegado a 28,356 / 48,356 = mitad del
  pliegue, editar espesor 2 -> 3 y el radio y la brida lo siguen, un Ctrl+Z).

Decisiones para revisar con el usuario (las tomó Claude):
1. Factor K 0,5 de fábrica (SW). Si él usa otro, se cambia en la Brida base y queda para la pieza.
2. Espesor de fábrica: el último usado (la primera vez 2 mm); largo de brida: el último (20 mm).
3. Una segunda Brida base en una pieza que ya tiene sólido: no se deja (avisa: pieza nueva).
4. El DXF se pisa sin preguntar.
5. Nombres "Brida-Base1", "Brida-Arista1", "Desarrollo" (los de SW en castellano, a confirmar).
6. "Ángulo" va dentro de "Parámetros de brida" y las opciones de longitud/posición en listas
   desplegables (en SW son recuadros y botones con ícono): si no, el panel no entraba en 768 px.

Límites / sin hacer en la versión 1: desahogo de pliegue (quedan los valores de SheetMetal; solo
importa con bridas más cortas que la arista), alivio de esquinas, bridas con perfil editado, la
etiqueta "90°" del plegado se ve al aplanar (no va al DXF). Al editar una brida queda un paso de
deshacer vacío de SheetMetal ("BaseBend"). Sin GUI SheetMetal no arma los croquis del desarrollo
(DXF solo con la interfaz; la geometría sí se recalcula con `GenerateSketch` apagado).

Para que pruebe el usuario: una pieza en U con Brida base desde la Planta y dos bridas de arista,
Aplanar y volver, Exportar DXF y abrirlo en su programa de corte (capas y trazos), editar el
espesor y volver a exportar; un perfil en L abierto.

## Alcance: menú Insertar de SW que usa el usuario (audio + capturas, 2026-10-26)
Lo que no está en esta lista no se hace (salvo pedido). "Por ahora no" = quizás más adelante.
- Saliente/Base: Extruir, Revolución, Barrer. No: Recubrir, Límite, Dar espesor.
- Cortar: Extruir, Revolución. No: Barrer ("corte barrido nunca usé"), Recubrir, Límite, Con superficie.
- Operaciones: Redondeo, Chaflán, Asistente para taladro, Ángulo de salida, Vaciado, Combinar,
  **Mover/Copiar sólido**, **Eliminar/Conservar sólido** (hechos 2026-10-27). Vaciado hoy es el
  `PartDesign_Thickness` nativo con nombre en castellano, sin panel SW (el usuario lo da por hecho).
- Matriz/Simetría: Matriz lineal, Matriz circular, Simetría.
- Cara: Mover/rotar cara (fase 4, hecha 2026-10-27). Curva: Hélice/Espiral. Geometría de referencia: hecha.
- Chapa (fase 1): Brida base, Convertir en chapa metálica, Brida de arista, Dobladillo,
  Desdoblar/Doblar (abrir el desarrollo, operar en plano y volver a plegar).
- Por ahora no: Operación Cierre, Superficie.

## Análisis: Mover/Copiar sólido, Eliminar/Conservar sólido, Mover/rotar cara (analizado 2026-10-26, hecho 2026-10-27)
Verificado en 1.1.4 sin GUI (todo nativo, en la línea "asistente, no motor"):
- Copiar sólido: Cuerpo nuevo con BaseFeature = copia vinculada (SubShapeBinder) del original y
  el desplazamiento/giro en **Body.Placement** (admite ecuaciones; sigue los cambios del original;
  admite operaciones encima). Ojo: el Placement de la copia vinculada (o de un Clon de Draft) usada
  como BaseFeature se IGNORA (FeatureBase lo descarta): hay que mover el Cuerpo.
- Mover sólido: o bien Body.Placement del mismo Cuerpo (simple; mueve todo, también lo que se
  agregue después), o bien como Copiar + el original "consumido" (queda como paso del historial:
  lo de antes en A, lo de después en el Cuerpo nuevo). El usuario eligió la segunda (b).
- Conservar sólido (corte que parte la pieza en sueltos): `CompoundTools.CompoundFilter`
  (Part::FeaturePython de FreeCAD) + Cuerpo nuevo con BaseFeature = filtro: correcto. Elegir la
  pieza por número es frágil (orden); idea a probar: modo "collision-pass" con un punto dentro de
  la pieza elegida. El Body no tiene `Suppressed` (las operaciones sí).
- Mover cara (desfase según la normal): **Pad / Pocket nativos con la cara del sólido como perfil**
  (también sobre un sólido importado, Cuerpo con BaseFeature): volumen exacto con caras vecinas
  perpendiculares (+5: 125000, -5: 75000 mm³). Con vecinas inclinadas da un escalón en vez de
  prolongarlas (110000 vs 109375 de SW); TaperAngle del Pad podría cubrir paredes de igual
  inclinación (sin afinar). Dirección elegida: usar su componente normal (Pad con dirección
  oblicua corre el prisma inclinado, no sirve).
- Rotar cara alrededor de una arista: **PartDesign::Draft nativo** (cara de arriba, plano neutro =
  cara lateral que contiene la arista, 10°: vértices y volumen exactos, 55918 mm³).
- Consecuencia: la fase 4 se puede hacer sin FeaturePython propio (el CLAUDE.md lo preveía);
  cambio de arquitectura aprobado por el usuario (2026-10-26).
- El Cuerpo y la copia vinculada NO tienen apoyo (Attachment) en 1.1.4. (Después se verificó que
  Restricciones y "de un vértice a otro" sí salen con puntos / sistemas de coordenadas de Part y
  ecuaciones: ver más abajo.)

Respuestas del usuario (2026-10-26, con capturas de los paneles de SW 2018):
- Mover/Copiar: usa Trasladar/Girar con números **y** Restricciones. Mover = **(b)**, paso en el
  historial (lo de antes en el Cuerpo original, lo de después en el nuevo). Panel SW: "Sólidos para
  mover/copiar", Copiar + cantidad de copias, Trasladar (referencia + ΔX ΔY ΔZ), Girar (referencia
  o centro X Y Z + ángulos X Y Z), botón Restricciones.
- Eliminar/Conservar: usa los dos casos (pedazos de un corte y sólidos enteros). Panel SW: Tipo
  Eliminar / Conservar sólidos + "Sólidos para eliminar/conservar".
- Mover cara: en piezas propias y en importadas. **Aprobado hacer la fase 4 con objetos nativos**
  (Pad/Pocket/Draft), sin FeaturePython. Panel SW: Equidistanciar / Trasladar / Girar, caras,
  Copiar, condición final (Hasta profundidad especificada...), dirección, distancia, ΔX ΔY ΔZ.

Hecho: **Mover cara** (2026-10-27, `swui/fork/move_face.py`, botón en Operaciones bajo
Combinar). Panel SW: Equidistanciar / Trasladar / Girar, Caras, y en Parámetros Dirección
(Trasladar; vacía = ΔX ΔY ΔZ), Eje de giro (Girar), Invertir dirección, Distancia, Ángulo.
- Por debajo: Pad (sale) / Pocket (entra) con la cara como perfil; Girar = PartDesign::Draft con
  plano neutro = cara plana que contiene la arista y tiro = arista recta (o cara) perpendicular a
  ella dentro de la cara (prolonga también vecinas inclinadas, verificado). Varias caras: tienen que
  mirar para el mismo lado (girar: mismo plano). Si cambia el sentido o el tipo, la operación se
  cambia por la otra (bloqueado si otra operación usa sus caras). Marca `SWUI_MoveFace` (texto JSON,
  oculta, **nombre estable**). Editar abre el panel (sin modo edición de FreeCAD: así se puede
  cambiar Pad <-> Pocket). Sólido suelto (STEP): Cuerpo nuevo con BaseFeature = el sólido y
  `Body.Placement` = el del sólido (el Cuerpo descarta la ubicación del sólido de arranque).
- Probado sin GUI (cuentas, caras, eje) y en FreeCAD real: +5 (125000 mm³), editar e Invertir
  -> Pocket (75000), un deshacer vuelve al Pad; girar 10° (119082, igual al cálculo; hacia abajo
  no entra y avisa "probá con Invertir dirección o un ángulo menor"); importado corrido en Y
  queda en su lugar; Cancelar no deja nada. Reabierto en otro proceso sin el addon: recalcula.
- Sin hacer (decidir con el usuario si hace falta): Copiar (la casilla), condición final
  distinta de "Hasta profundidad especificada", girar alrededor de un eje que no esté en la cara,
  Equidistanciar caras curvas (p. ej. agrandar un agujero), ícono propio en el árbol (se ve el de
  Extruir/Cortar/Ángulo de salida), y la distancia de Trasladar con dirección inclinada no se ata
  a ecuaciones (se guarda la componente normal como número). Una ecuación que cambie de signo no
  pasa de Extruir a Cortar.

Hecho: **Mover/Copiar sólido** (2026-10-27, `swui/fork/move_bodies.py`) y **Eliminar/Conservar
sólidos** (`swui/fork/delete_bodies.py`). En la cinta: botón grande "Mover/Copiar sólido" con menú
(Eliminar/Conservar adentro), al lado de la columna Cuerpo/Combinar/Mover cara (una columna más
con texto no entraba en 1366 px y los botones grandes perdían el texto).
- Mover/Copiar: por sólido y copia, copia vinculada (SubShapeBinder, raíz, marca `SWUI_MoveBody`
  con JSON y "op" que agrupa; **nombre estable**) + Cuerpo nuevo (BaseFeature) con el
  desplazamiento en `Body.Placement` (copia i = desplazamiento^i; girar y después trasladar).
  Mover = sin Copiar: el original queda oculto y `material.consumes` lo descuenta. Editar: clic
  derecho -> Editar operación sobre el Cuerpo nuevo o la copia vinculada (`dress_up_panel.OPENERS`,
  `feature_tree`). Cuerpos nuevos "Cuerpo2"... (decidido por Claude: el original conserva su
  nombre; avisar al usuario). No se puede sacar de la lista un sólido cuya copia ya tiene
  operaciones propias (avisa).
- Eliminar/Conservar: grupo (App::DocumentObjectGroup, marca `SWUI_DeleteBodies`, **nombre
  estable**) con los Cuerpos eliminados (ocultos, descontados); pedazos: Part::Vertex adentro del
  pedazo + CompoundFilter "collision-pass" + Cuerpo nuevo por pedazo que queda; el Cuerpo partido
  queda oculto. Conservar = se elimina todo lo demás (como SW). Editar desarma y vuelve a armar;
  lista vacía borra la operación. Pedazo con operaciones propias: no se desarma (avisa).
- Probado sin GUI (cuentas, plan de eliminar/conservar, reabierto sin el addon cambiando cotas:
  la copia y el pedazo siguen) y en FreeCAD real: mover +50 en Z (Sólidos sin el original),
  editar a Copiar ×3 con ΔX 120 (el original vuelve a verse), deshacer/rehacer, eliminar el
  pedazo 2 de un Cuerpo partido (queda el 1 como Cuerpo nuevo), editar a Conservar (queda solo el
  pedazo), lista vacía (todo vuelve), Cancelar sin rastros, segunda operación sin pisar la primera
  (error encontrado en la prueba y corregido: las dos se llamaban igual y la segunda borraba las
  copias de la primera).
- Hecho después (2026-10-27, pedido del usuario; los nombres "Cuerpo2"... le dan igual por ahora):
  - **Supr sobre Eliminar/Conservar devuelve los sólidos** como SW: con solo operaciones de ese
    tipo elegidas, el addon toma la tecla (acepta ShortcutOverride, así Std_Delete no corre) y en
    un paso de deshacer ("Borrar Eliminar/Conservar sólido1") muestra los Cuerpos eliminados y el
    partido y borra pedazos, filtros y puntos. Respaldo por otro camino (menú, Python): observador
    de documento, paso aparte. Un pedazo con operaciones propias: con Supr avisa y no borra; por
    otro camino se queda y avisa. Probado en real con la tecla de verdad, deshacer/rehacer, y
    borrado por Python (sin restos).
  - **De un vértice a otro** en Trasladar: dos vértices en Dirección (clic derecho -> Borrar
    selecciones vuelve a ΔX ΔY ΔZ). Probado en real: la copia de un taco queda con su esquina en
    la esquina de la placa y la sigue al alargar la placa de 100 a 150.
- **Restricciones: NO hacer** (decisión del usuario, 2026-10-27: "llegado el caso puede hacerse
  con alguna ecuación ad-hoc"). Lo verificado queda como referencia:
  - De un vértice a otro: `Part::DatumPoint` (raíz del documento, MapMode "Vertex", apoyado a
    través del Cuerpo: `(Cuerpo, "Box.Vertex3")`) en cada vértice y la ecuación
    `Placement.Base = Destino.Placement.Base - Origen.Placement.Base` en el Cuerpo copia: sigue
    al cambiar la pieza.
  - Restricciones como marcos: `Part::LocalCoordinateSystem` apoyado en lo elegido de cada pieza
    (cara plana, arista, vértice; modos del motor de apoyo) y
    `Placement = Destino.Placement * minvert(Origen.Placement)` en el Cuerpo copia (funciona).
    Falta resolver cómo traducir combinaciones de relaciones de SW a modos de apoyo y qué hacer
    con los grados de libertad que quedan libres (dejarlos como están al aceptar, en
    AttachmentOffset). El Body y la SubShapeBinder no tienen apoyo propio.

## Plan: fase 3 — Evaluar (analizado con el usuario el 2026-10-26; hecho el mismo día)
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

Avance (todo hecho, en `swui/fork/`; cinta en `evaluate_tab.py`, íconos con
`tools/fork/make_icons_fork.py`):
- Material (`material.py`): ventana, personalizados (.FCMat en la biblioteca "User", carpeta por
  categoría), aplicar sin tocar el color, quitar, copia `SWUI_MaterialCopy` (nombre estable) que
  se pone al aplicar y se pone al día al guardar, aviso al abrir con material faltante y
  recreación con el mismo UUID. Probado sin GUI (guardar, abrir en otro proceso sin el material:
  queda "Default", se recrea y vuelve el mismo UUID) y en FreeCAD real (acero, color igual antes y
  después, material nuevo "Chapa SAE 1010", aviso de faltante con Sí).
- Propiedades físicas (`mass_props.py`): informe SW, decimales, ocultos sí/no, centro de masa
  marcado en la vista, selección (cara -> cuerpo, en ensamblaje el componente). Probado: placa
  100x50x10 de acero (0,395 kg, Lxx = 85,583 a mano), pieza en L (producto de inercia), ensamblaje
  con dos instancias (0,790 kg, CDG z = 55) y elegir un componente.
- Ecuaciones (`equations.py`): probado sin GUI y en FreeCAD real ("Largo" = 120, D1@Croquis1 =
  "Largo", D1@Saliente-Extruir1 = "Largo" / 10 -> 12 mm; insertar cota con doble clic; Cancelar
  deja cota, ecuación y nombre de la cota como estaban). El addon renombra las extrusiones como
  SW ("Saliente-Extruir1"), así que los nombres quedan iguales a los de SW en castellano.
- Medir (`measure_sw.py`): probado sin GUI (vértice, arista, círculo, cara con agujeros, dos caras
  paralelas, cilindros centro a centro / mínima, ángulo, totales) y en FreeCAD real (dos caras de
  una pieza; ensamblaje: 90 mm entre piezas; clic en el vacío borra; barra espaciadora abre y
  cierra). Hallazgo: el observador de selección recibe la cara RESUELTA (objeto interno, sin la
  posición en el ensamblaje); se toma la ruta completa de `getSelectionEx("", 0)`.
- Franja (`tree_strip.py`): Ecuaciones (si hay) / Sólidos(n) con lista desplegable / Material
  con clic derecho Editar/Quitar. Probada en FreeCAD real.

Decisiones para revisar con el usuario (las tomó Claude trabajando solo; ver también memoria
"decidir y anotar"):
1. **Productos de inercia con el signo de SW** (+∫xy dm), al revés que OpenCASCADE. Creo que SW
   los muestra así, pero no lo verifiqué en SW: comparar Lxy de una pieza en L en SW 2018.
2. Sin material: 1000 kg/m³, igual que SW, con una nota en el informe.
3. Masa con 3 decimales de fábrica (en SW se elige); Medir con 2 (como SW). Se cambian en cada
   ventana y quedan guardados.
4. Materiales de FreeCAD con su nombre original (en inglés / normas DIN: "Steel-C22E"...),
   categorías en castellano; solo los que tienen densidad. Ver si prefiere nombres en castellano.
5. "Aplicar" va a lo elegido; sin selección, a todos los sólidos de la pieza (como SW a nivel
   pieza).
6. La copia del material queda **a la vista** (solo lectura) en Datos > Material >
   SWUI_MaterialCopy, para que se lea aun sin el addon.
7. Material recuperado: si era personalizado vuelve a su categoría; si era de FreeCAD, a
   "Recuperados". Al recrearlo el documento queda modificado (hay que guardar).
8. Ecuaciones es **modal** (mientras está abierta no se toca el modelo) para que Aceptar sea un
   solo deshacer y Cancelar deshaga todo. Las cotas se eligen de la lista de la derecha, no
   tocándolas en la vista como en SW.
9. Comentarios solo en variables globales (FreeCAD no guarda comentarios en las expresiones).
10. Variables globales sin unidades (como SW): "Largo" = 120 se usa como 120 mm o 120°.
11. Nombres de cotas: D1, D2... en el orden de las cotas del croquis; al usar una en una ecuación
    se le pone ese nombre en el croquis (así no se corre). Cotas de operaciones con tabla propia
    (`FEATURE_DIMS`: D1 = profundidad, D2 = segunda profundidad...): puede no coincidir con la
    numeración de SW en todos los casos.
12. "Ecuaciones" en la franja aparece solo si hay ecuaciones (como SW). El objeto "Variables
    globales" (VarSet, nombre interno `VariablesGlobales`, estable) se ve en el árbol: es de
    FreeCAD.
13. La franja va arriba del árbol (no dentro: FreeCAD no deja) y solo en piezas.
14. Propiedades físicas incluye sólidos ocultos de fábrica (casilla), como la opción de SW.
15. En 26.3+ el botón Propiedades físicas abre la herramienta nueva de FreeCAD (regla de ceder a
    lo nativo): pierde el informe SW y no usa la copia del material. Revisar al actualizar.
16. Medir reemplaza al de FreeCAD en la cinta y la barra espaciadora; sin "proyectado en" (el
    usuario puede pedirlo). Un clic sobre algo ya elegido lo saca.
    **Distancia máxima: hecha a pedido del usuario (2026-10-26)**, tercera opción del Medir
    (`max_distance.py`). Él eligió "general + casos sencillos": reducir (rectas y caras planas ->
    vértices), barrido de lo curvo, afinado de 8 candidatos sobre la geometría exacta; fórmulas
    exactas para solo vértices, punto-círculo y círculos coplanares (el test compara general
    contra fórmulas). Qué es "máxima": entre bordes de agujeros (círculos) como SW; entre
    cualquier otra cosa, la máxima real (en dos caras cilíndricas incluye el largo). Probado sin
    GUI: exacto en círculos, cajas, cilindros, esfera, medio arco (contra fuerza bruta) y
    caras de redondeo (≥ malla fina, dif. 2e-5 mm); en FreeCAD real: dos agujeros 59 mm
    (centro a centro 50, mínima 41).
    Reportado por el usuario (2026-10-26, captura): centro a centro entre un agujero y una cara
    plana daba la mínima. Corregido: como SW, desde el centro/eje de lo circular (círculo,
    cilindro, esfera) hasta una cara plana, arista recta o vértice ("Distancia desde el centro");
    si el eje corta el plano o ninguno es circular, la mínima. Probado en FreeCAD real (agujero
    con redondeo y cara lateral: 45 mm).
    Pedido del usuario (2026-10-26, captura de SW): dibujar las proyecciones como SW. Hecho:
    línea de la distancia negra con recuadro "Dist." y escalera dX roja -> dY verde -> dZ azul
    desde el primer punto, cada tramo con su recuadro (rótulo de color + valor); los recuadros
    siguen a la cámara (como las cotas con doble clic), no tapan los clics y bajan un renglón si
    se pisan. Casilla "Mostrar dX, dY, dZ en la vista" (prendida de fábrica, se recuerda).
    Probado en FreeCAD real: isométrica y de frente.
17. FreeCAD recuerda un material borrado hasta reiniciar: el addon lo oculta de la lista.

Para que pruebe el usuario (fase 3): asignar un material de FreeCAD y uno propio nuevo (ver que
no cambie el color), Propiedades físicas de una pieza suya comparando con SW (masa, CDG, Lxy),
Ecuaciones con una variable global y dos cotas, Medir con la barra espaciadora (dos caras, dos
agujeros centro a centro, en un ensamblaje), la franja arriba del árbol, y mandarle una pieza
con material propio a otra PC (o borrar el .FCMat) para ver el aviso.

## Multicuerpo (piezas con varios sólidos): analizado y decidido el 2026-10-26, sin código
Surgió en la prueba de la fase 3 (paso 1.3: "Sólidos(1)" con dos sólidos sueltos en un Cuerpo).
Usos del usuario en SW: piezas soldadas, partir una pieza, y armar partes por separado y
unirlas al final. Deja los sólidos en la misma pieza; no comparte estos archivos (por ahora).
Usa mucho **Fusionar resultado** (apagado) y **Alcance de la operación**.

Cómo es FreeCAD 1.1.4 (verificado sin GUI):
- Un Cuerpo admite varios sólidos sueltos (`AllowCompound`, prendido de fábrica). No hay
  "Fusionar resultado": lo que toca se fusiona; y una operación nativa fusiona TODO lo que se
  toca en el Cuerpo, aunque la operación no lo toque. No hay "Alcance": un corte pasante corta
  todos los sólidos del Cuerpo. Material: uno por Cuerpo (al usuario le parece razonable).
- "Combinar" de SW = `PartDesign::Boolean` (Fuse/Cut/Common) entre Cuerpos: el Cuerpo activo
  (entero) con otros Cuerpos como herramientas.
- FreeCAD no tiene nada de esto pedido ni en camino (relacionados abiertos: #14510 fusión
  inesperada con varios sólidos, #18469 separar sólidos en Cuerpos, #9748 concepto de Cuerpo).

Caminos analizados:
1. Un Cuerpo por sólido de SW, todo nativo.
2. Un Cuerpo con varios sólidos y operaciones propias (FeaturePython) antes/después de cada
   operación nativa. Prototipo: funcionó (bloque apoyado sin fusionar; corte solo en un sólido),
   pero una operación nativa posterior fusiona todo, y sin el addon el archivo abre y NO se
   recalcula (queda viejo sin avisar). **Descartado por el usuario**: es lógica nuestra, sin años
   de prueba, corriendo en cada recálculo.
3. **ELEGIDO: camino 1 con el addon como asistente** (memoria "addon asistente, no motor"): el
   addon arma objetos nativos al crear la operación; después recalcula FreeCAD solo. Se acepta
   que cada sólido (Cuerpo) tenga su propio historial ("me acoplo a lo de FreeCAD").

Verificado en 1.1.4 para el camino 3 (sin GUI):
- **Trampa**: un croquis de un Cuerpo B apoyado DIRECTO en una cara de A no da error, pero la
  extrusión de B se trae la placa de A adentro (68000 en vez de 18000 mm³). El asistente tiene
  que apoyar el croquis en una **copia vinculada** de la cara (`PartDesign::SubShapeBinder` dentro
  de B): así da bien y sigue los cambios de A.
- Alcance: un solo croquis; corte en A (el croquis) y en otro Cuerpo con una copia vinculada
  del croquis: correcto, y el Cuerpo no elegido queda intacto.
- Combinar con la Booleana: correcto.
- Dividir: `BOPTools.SplitFeatures.makeSlice` (Mode "Split") con un plano + un
  `CompoundTools.CompoundFilter` por pieza + Cuerpo nuevo con `BaseFeature` = esa pieza: correcto
  y paramétrico; son herramientas que trae FreeCAD (Mod/Part), así que reabierto en otro proceso
  sin el addon se recalcula bien al cambiar una cota. Ojo: el filtro elige la pieza por número
  de orden (si un cambio invierte el orden, se cruzan): probar con casos reales.

Plan aprobado por el usuario (2026-10-26), por etapas:
- **A. HECHA (2026-10-26)**: `material.consumes` / `part_objects`: no cuentan como pieza los
  Cuerpos que se "comió" otro (herramienta de Combinar, base de un Dividir, cualquier operación de
  Part que use el sólido); sí cuentan aunque haya un croquis o una copia vinculada apoyada en
  ellos. Corrige el doble conteo de Propiedades físicas (encontrado al analizar). Franja:
  "Sólidos(n)" = Cuerpos, con ⚠ y explicación si un Cuerpo tiene sólidos sueltos; en la lista,
  "C (2 sólidos sueltos · material)". El informe de masa avisa los sólidos sueltos. Probado sin
  GUI (Combinar + Dividir + copia vinculada + Cuerpo con 2 sólidos: 78000 mm³, correcto) y en
  FreeCAD real. Falta que lo pruebe el usuario.
- **B. HECHA (2026-10-26)** (`swui/fork/multibody.py`): en los diálogos nativos de Extruir /
  Revolución, adentro del cuadro de parámetros:
  - Saliente: casilla **Fusionar resultado** debajo de "Invertir dirección" (solo si el Cuerpo ya
    tiene sólido, o si la operación ya está aparte). Apagada, al Aceptar la operación pasa a un
    Cuerpo nuevo ("Cuerpo2"...): el croquis queda en su Cuerpo (con sus referencias a aristas) y
    el nuevo usa una copia vinculada del croquis (SubShapeBinder). Revolución: eje del origen ->
    el del Cuerpo nuevo; eje del croquis (V/H) -> recta de referencia apoyada en el croquis; otro
    eje -> no se separa y avisa. Prenderla al editar la devuelve a su Cuerpo (si el sólido no tiene
    otras operaciones; si tiene, avisa: usar Combinar).
  - Corte: cuadro **Alcance de la operación** (solo si hay más de un sólido): Todos los sólidos /
    Sólidos seleccionados, Selección automática (de fábrica, como SW: los que el corte atraviesa,
    calculado con la herramienta del corte contra cada sólido antes del corte) y la lista con
    tildes (el sólido del corte va siempre). Al Aceptar se crean/borran copias del corte en los
    otros sólidos: copia vinculada del croquis + ecuaciones a las cotas del original (también
    Tipo, Invertir, SideType...), propiedad `SWUI_ScopeOf` (LinkGlobal, nombre estable). Al editar
    una copia, el panel avisa que se edita el original. Las ecuaciones de las copias no se
    muestran en Ecuaciones ni en la franja.
  Probado sin GUI (separar/volver, revoluciones con los dos ejes, copias que siguen al original
  hasta en el tipo, "Hasta la cara" no se copia, y **reabierto sin el addon se recalcula bien**) y
  en FreeCAD real (separar, cortar "Por todo" los dos sólidos con copia, editar y sacar un sólido:
  copia y vínculo borrados; revolución separada; Cancelar no deja nada). Falta que lo pruebe el
  usuario.
  Decisiones / límites, con el porqué explicado al usuario (2026-10-26):
  - Cuerpos nuevos "Cuerpo2"... (FreeCAD no repite nombres).
  - Vista previa con el diálogo abierto: fusionada. El usuario mostró que en SW es igual (la
    casilla no cambia la vista previa): no se hace nada.
  - Deshacer: dos pasos ("Fusionar resultado" y "Make Pad"). Probado separar en el `pressed` de
    Aceptar (un solo paso): FreeCAD, al terminar su Aceptar, vuelve a escribir
    `ReferenceAxis = (croquis, N_Axis)` y la extrusión arrastra el otro sólido (los dos Cuerpos
    con el mismo volumen; al rehacer queda con error). **Descartado: quedan dos pasos**, que se
    deshacen y rehacen limpios (probado en FreeCAD real).
  - Hecho después (2026-10-26, pedido del usuario):
    - Borrar el corte original borra sus copias y lo que el asistente armó para ellas: con Supr
      (filtro de la aplicación) se suman a la selección y Std_Delete borra todo en un paso, sin
      aviso de vínculos rotos. Probado en real con el atajo de verdad (QTest a la ventana, con
      Std_Delete ya habilitado): un solo paso "Delete", sin aviso, y un Ctrl+Z devuelve todo. La
      primera versión escuchaba solo KeyPress y llegaba tarde (salía el aviso nativo y las copias
      se borraban en un segundo paso): corregido escuchando ShortcutOverride. Por otro camino
      (menú, Python): respaldo que borra las copias enseguida (paso aparte).
    - "Hasta la cara" se lleva a los otros sólidos con una copia vinculada de la cara (probado
      sin GUI). "Hasta el sólido" (UpToShape) sigue sin llevarse.
    - Selección automática: el modo queda en el original (`SWUI_ScopeMode`, oculta, nombre
      estable). Después de cada recálculo, si un corte "automático" pasa a atravesar otros
      sólidos (o deja de atravesarlos), el addon pregunta "¿Actualizar el alcance?"; no cambia
      nada solo y no vuelve a preguntar lo mismo si se respondió No (en esa sesión). Probado en
      real (croquis alargado: avisa y con Sí suma la copia).
    - Las copias siguen el nombre del original al aceptar una edición.
  Hecho después (2026-10-26, el usuario usa simetría de sólidos y alcance en taladro; alcance en
  matrices/simetrías de operaciones "eventualmente": queda para después):
    - **Simetría de sólidos** (`mirror_bodies.py` + `pattern_panel.MirrorPanel`): en el panel de
      Simetría, "Sólidos para simetría" (lista; clic en la lista y después en el sólido) y
      "Fusionar sólidos". Prendida y solo el sólido de la operación: simetría nativa de Part Design
      (Whole shape, como antes). Apagada: por cada sólido, Simetría de Part (Part::Mirroring) +
      Cuerpo nuevo con BaseFeature = esa simetría (sigue al original y admite operaciones propias).
      Vista previa propia en amarillo; un solo deshacer ("Simetría de sólidos"). Prendida con otros
      sólidos: avisa (solo el propio). Plano: origen y caras apuntados a través del Cuerpo; plano de
      referencia por ecuaciones (Part::Mirroring ignora PartDesign::Plane). `material.consumes`:
      Part::Mirroring copia, no consume (si no, el original desaparecía de Sólidos(n)). Probado sin
      GUI (los tres tipos de plano, siguen los cambios, reabierto sin el addon) y en real.
      Límite: para cambiar el plano de una simetría ya hecha como sólido aparte hay que editar la
      Simetría de Part (diálogo nativo) o rehacerla.
    - **Alcance en el Asistente para taladro** (`hole_panel` + `multibody`): cuadro "Alcance de la
      operación" debajo de las pestañas Tipo/Posiciones (solo con más de un sólido); copias con
      copia vinculada del croquis de posiciones, medidas por ecuación y opciones de lista (tipo y
      tamaño de rosca, refrentado...) copiadas por valor al aceptar (`ENUM_PROPS`; con ecuación la
      copia mostraba M7 en vez de M8). Se aplica dentro de la transacción del taladro: un solo
      deshacer. Supr / aviso automático: igual que los cortes. Probado sin GUI (M6->M8,
      refrentado) y en real (dos placas, Por todo: copia en la de abajo, mismo volumen).
  Para más adelante: alcance en matrices y simetrías de operaciones, barridos.
- C. Combinar (Agregar / Restar / Común) y Dividir con paneles SW.
  - **Combinar: HECHO (2026-10-26)** (`swui/fork/combine_panel.py`, botón en Operaciones, columna
    de "Cuerpo"). Panel como el de SW (capturas del usuario): Tipo de operación Agregar /
    Eliminar / Común; "Sólidos para combinar" o, en Eliminar, "Sólido principal" + "Sólidos para
    substraer"; clic en una cara o en el árbol elige el sólido, otro clic lo saca. Por debajo la
    Booleana nativa (Fuse/Cut/Common) en el Cuerpo principal (en Agregar/Común, el primero de la
    lista; si cambia, la operación se muda), herramientas ocultas y descontadas de Sólidos(n).
    Editar una existente abre el mismo panel (registrado en `dress_up_panel.PANELS`). Probado en
    FreeCAD real: A con B y C superpuestos, Eliminar -> 43500 mm³ (correcto), un solo deshacer,
    editar y Cancelar sin cambios. Falta que lo pruebe el usuario.
  - Dividir: el usuario aclaró (2026-10-26) que con "Dividir" quería decir el Eliminar de
    Combinar: **etapa C completa**. Probado por él: "quedó muy bien Combinar". El "Dividir" de SW
    (partir un sólido con un plano en varios Cuerpos) queda sin hacer; está verificado que se
    puede con herramientas nativas (ver arriba, BOPTools Slice + CompoundFilter) si algún día lo pide.
- D. Soldadas, después de la chapa.

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
El panel de Medir de FreeCAD salía en inglés: resuelto en la fase 3 con Medir propio estilo SW.

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
- Fase 1: chapa hecha; pendientes chicos: desahogos de pliegue, Convertir en chapa de un sólido
  macizo, elegir qué pliegues desdoblar.
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
- 2026-10-26 (archivo "fallo multiples solidos.FCStd" en Documentos\FreeCAD pruebas, captura):
  placa + cilindro extruido contra la placa con "Fusionar resultado" destildado: la placa
  "desapareció". La geometría estaba bien (dos Cuerpos válidos): al crear la extrusión FreeCAD
  oculta la punta anterior (la placa) y, al pasar la extrusión al Cuerpo nuevo, la punta volvía a
  la placa pero oculta. Corregido (`multibody._set_tip`: se ve la punta, se oculta la anterior solo
  si sigue en el Cuerpo; también al volver a fusionar y al borrar copias). Reproducido en FreeCAD
  real con su caso (plano sobre la cara, croquis en el plano, extrusión invertida). En su archivo
  basta con prender el ojo de "Saliente-Extruir1". Probado por el usuario después del arreglo: "ahora sí, funciona".
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
