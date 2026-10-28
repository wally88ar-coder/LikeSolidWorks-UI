# Proyecto: fork de LikeSolidWorks UI para FreeCAD (flujo e interfaz estilo SolidWorks 2018)

## Contexto
- Usuario: ~20 años de experiencia en SolidWorks (referencia: SW 2018). Habla español rioplatense.
  Trabaja en Windows, pantalla de 1366x768 al 100 % de escala.
- Uso: personal y, más adelante, para compartir con amigos y conocidos.
- Objetivo: que FreeCAD se sienta lo más parecido posible a SW 2018, limitado a las funciones
  que el usuario realmente usa (ver Alcance).

## Base: fork de LikeSolidWorks UI
- Original: https://github.com/Schlauminik/LikeSolidWorks-UI (autor: Dominik Ladewig, LGPL-2.1+,
  íconos CC-BY-SA-4.0). Comentarios y README del original en alemán.
- Este repositorio es el fork del usuario. Configurar el remoto `upstream` apuntando al original
  y revisar sus novedades con regularidad.
- Respetar SIEMPRE las convenciones del original (ver su README): Qt solo vía `swui.compat`,
  IDs de comandos con prefijo `SWUI_`, rutas vía `swui.paths`, imports pesados en `Initialize()`,
  cabecera SPDX en cada archivo, contenido de la cinta solo en `swui/ribbon_layout.py`,
  íconos generados con `tools/make_icons.py` (no editar SVG a mano), test `tools/test_load.py`
  en verde antes de cada entrega, entrada en CHANGELOG.md.
- Lo que sirve a todos (traducciones, correcciones, mejoras de flujo generales) se prepara en
  ramas separadas y limpias para proponerlo al original con un pull request. Consultar al usuario
  antes de abrir cualquier PR o issue en el repositorio original.
- Lo propio del usuario (chapa, mover/rotar cara, etc.) va en módulos separados nuevos, tocando lo
  mínimo los archivos existentes, para que incorporar cambios del original no genere conflictos.
- Pendiente de decidir más adelante: si el fork se distribuye con otro nombre de paquete para que
  no choque con el original en el Addon Manager.

## Decisiones de arquitectura (no cambiar sin consultar)
- Addon en Python encima de FreeCAD oficial; nada de modificar el código de FreeCAD.
- Versión objetivo: FreeCAD 1.1.4 (último mantenimiento de la rama 1.1). La "1.2" pasó a llamarse
  **26.3** (FreeCAD numera ahora año.N: 26.3, 27.1, 27.2...; tres por año). El usuario actualiza
  cada ~2 años: desarrollar para 1.1.4 aunque una versión nueva ya traiga la función, y que cada
  función ceda a lo nativo si la versión lo trae. Evitar detalles internos frágiles.
- Nombres internos de lo que el fork guarda en los archivos (propiedades, clases): estables para
  siempre (ver `docs/ESTADO.md`, Decisiones).
- Dependencia: addon SheetMetal para chapa. No reimplementarlo: construir la interfaz encima.
- Nada de íconos, nombres comerciales ni recursos de Dassault.
- Preferir siempre la herramienta nativa de FreeCAD por debajo, con interfaz y flujo estilo SW.
- Similitud total con SW (decidido por el usuario, 2026-10-25): LikeSolidWorks UI es el ÚNICO
  banco (arranca ahí, vuelve solo, selector oculto; se apaga en el menú); todo módulo nuevo
  (chapa, simulación FEM...) va como pestaña de la cinta dentro de él; aspecto claro SW 2018;
  panel izquierdo con Modelo y Tareas en pestañas.
- Código propio del fork en `swui/fork/` (comentarios en español): cambia tablas y funciones del
  original desde afuera, sin editar sus archivos. Detalle en `docs/NOTAS_TECNICAS.md`.

## Lo que el original ya resuelve (no rehacer)
Cinta tipo CommandManager; croquis (colores azul/negro, panel de relaciones aplicables, línea
constructiva, línea por punto medio, ícono contextual de croquis sobre cara plana); extruir desde
un croquis abierto (`swui/from_sketch.py`); términos SW en diálogos de extruir/cortar/revolución
(`swui/feature_terms.py`, solo cambia textos); panel de relaciones de posición
(`swui/assembly_mates.py`); planos muy completos (TechDraw, exportación PDF/DXF de hojas).

## Lo que falta y es el trabajo de este fork
**Rápidos / generales (candidatos a PR al original):**
- Traducción al español (`swui/lang/es.py`, copiando `en.py`). Hoy la cinta queda en inglés y los
  diálogos nativos en español: mezcla de idiomas.
- Pantallas chicas: con 1366 px la cinta fuerza un ancho mínimo de ventana de 1458 px y se corta el
  borde derecho (panel de Tareas incluido). La cinta debe compactarse o desplazarse.
- Extruir / extruir corte sin croquis: hoy cae en el panel nativo "Seleccione un plano", que no
  acepta caras del sólido. Debe aceptar cara plana o plano, abrir el croquis ahí y lanzar la
  operación al salir del croquis (como SW). Extender el mecanismo de `from_sketch.py`.
- (Hecho en la fase 2, en `swui/fork/`: paneles SW de redondeo, chaflán, simetría, matriz lineal y
  circular, ángulo de salida, plano/eje/punto de referencia; asistente para taladro con flujo SW;
  términos SW en barrido y hélice. Son propios del fork, no candidatos a PR tal cual.)
- (Hecho en la fase 5, `swui/fork/mates_sw.py`: tangente y panel que queda abierto para encadenar
  relaciones; propio del fork, no candidato a PR tal cual.)
- (Hecho en el fork: panel de tareas a la izquierda, sin opción a la derecha, por decisión del
  usuario.)

**Propios del usuario:**
- (Hecho en la fase 1, versiones 1 a 3, en `swui/fork/`; falta que lo pruebe el usuario.)
  Chapa metálica (trabaja con plegadora, no punzonadora): pestaña nueva con brida base, brida de
  arista, propiedades de chapa, desplegar/plegar, sobre SheetMetal. **Exportar DXF del desarrollo
  con un clic**: contorno y líneas de plegado en capas separadas, nombre de archivo automático
  (pieza + espesor + material), y exportación por lotes desde un ensamblaje.
- (Hecho en la fase 3, en `swui/fork/`; falta que lo pruebe el usuario.) Pestaña Evaluar: propiedades físicas (masa, volumen, área, CDG, inercia) con Shape.Volume, Area,
  CenterOfMass, MatrixOfInertia y la densidad del material; FreeCAD 1.1 no las trae (llegan en
  26.3 como Std_MassProperties): diseñar para migrar fácil a la herramienta oficial. Asignar
  material. Diálogo de Ecuaciones estilo SW sobre expresiones + Spreadsheet/VarSet. Mediciones en
  pieza y ensamblaje (el panel de Medir de FreeCAD sale en inglés). Franja Material / Ecuaciones /
  Sólidos arriba del árbol (pasada acá desde el plan del árbol).
- (Hecho en la fase 4, 2026-10-27, `swui/fork/move_face.py`.) Mover/rotar cara: solo caras
  **planas**, con operaciones nativas (no FeaturePython: aprobado por el usuario). Equidistanciar /
  Trasladar = Extruir o Cortar con la cara como perfil (componente normal); Girar alrededor de una
  arista de la cara = Ángulo de salida nativo. Límite: con vecinas inclinadas, mover deja escalón.

Operaciones de pieza que usa (menú Insertar de SW, lista completa en `docs/ESTADO.md` > Alcance):
todas hechas (Mover/Copiar y Eliminar/Conservar sólido: 2026-10-27, sin
Restricciones por decisión del usuario); Superficie y Operación Cierre, por ahora no.

El usuario NO usa en planos: tablas/notas de plegado, listas de materiales con globos,
tolerancias geométricas.

## Fases (orden propuesto; el usuario puede reordenar)
Estado al 2026-10-27: fase 0 terminada; fases 1 a 5 con código completo, falta que las pruebe
el usuario (de la 2 solo probó el redondeo, de la 4 girar cara), que revise las decisiones de la
fase 3 y que responda las casillas de la fase 5 (documento compartido, enlace en `docs/ESTADO.md`).
Hecho además fuera de las fases: árbol de operaciones estilo SW (barra de retroceso, suprimir,
mover, cotas con doble clic, reparar referencias...), aristas del modelo dentro del croquis,
multicuerpo (Fusionar resultado, Alcance, Combinar, simetría de sólidos) y Mover/Copiar /
Eliminar/Conservar sólidos. Próximo: lo que elija el usuario después de probar. Ver `docs/ESTADO.md`.
Trabajo de planos (TechDraw, sin número de fase): rosca simplificada automática, rótulo en
castellano, coma decimal; ver "Falta" en `docs/ESTADO.md`.
0. Puesta en marcha: remotos (origin = fork, upstream = original), verificar que carga y que el
   test pasa en Windows, traducción al español, arreglo de pantallas chicas, extruir/cortar sin
   croquis.
1. Chapa metálica + exportación DXF (es lo que más usa el usuario y no existe).
2. Flujos de pieza: diálogos restantes adaptados y asistente para taladro.
3. Evaluar: propiedades físicas, material, ecuaciones.
4. Mover/rotar cara (hecha 2026-10-27).
5. Ensamblaje (código completo 2026-10-27, falta que la pruebe el usuario): relaciones SW, matriz y
   simetría de componentes, taladro/corte de ensamblaje, geometría de referencia. Plan y checklist
   en el documento compartido (enlace en `docs/ESTADO.md`).

## Forma de trabajo
- Antes de tocar algo grande, explicar el plan al usuario en lenguaje simple (no es programador).
- Cada fase termina en una versión que el usuario prueba en su FreeCAD. La interfaz gráfica la
  valida el usuario; la geometría probarla también con FreeCADCmd (sin GUI) cuando se pueda.
- Para Python fuera de FreeCAD, usar el intérprete incluido en FreeCAD si no hay otro instalado.
- Piezas de prueba reales del usuario (exportadas de SW en STEP): pedir la carpeta y usarlas.
- Commits pequeños y descriptivos. Nunca forzar push ni reescribir historia publicada.
- Mantener actualizado `docs/ESTADO.md`: fase actual, qué está hecho, qué falta, problemas
  reportados por el usuario, decisiones nuevas y estado de los PR al original. Leerlo al inicio
  de cada sesión, junto con `docs/NOTAS_TECNICAS.md` (cómo probar en FreeCAD real con
  `tools/fork/gui_probe.py`, hallazgos de FreeCAD 1.1.4 en Windows).
- Antes de entregar cambios de interfaz, probarlos en FreeCAD real con la plantilla de prueba
  (copia de la configuración, nunca la del usuario) y mirar las capturas; después la valida él.
- Ser honesto sobre límites que el addon no puede resolver.

## Límites conocidos (comunicar, no prometer)
Motor OpenCASCADE menos robusto que Parasolid en redondeos complejos; rendimiento con ensamblajes
grandes; los .SLDPRT/.SLDASM solo se pueden traer como sólidos sin historial (STEP o el addon de
importación de SolidWorks); TechDraw requiere más clics para acotar; no hay configuraciones
equivalentes a SW; archivos de 1.1 pueden no abrir en versiones anteriores.
