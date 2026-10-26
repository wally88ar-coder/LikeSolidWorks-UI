# Pedido para el GitHub de FreeCAD: plano "en ángulo" y "punto medio"

**Para el usuario (en castellano):** borrador de un pedido de función ("feature request") para
https://github.com/FreeCAD/FreeCAD/issues/new/choose (plantilla "Feature request"). Va en inglés
porque así se escriben ahí. Pide dos modos nuevos para los planos de referencia, para que no haga
falta el addon para que sigan a la pieza. **No está publicado:** lo publicás vos, o lo publico yo
cuando me des el OK. Antes de publicarlo conviene buscar de nuevo por si alguien ya lo pidió
(al 2026-10-27 no había nada).

---

**Title:** Attacher: add "plane at angle through an edge" and "mid plane between two planes" modes for datum planes

**Problem**

Two of the most common ways to define a reference plane in mechanical design cannot be built
parametrically with the current attachment modes of PartDesign/Part datum planes (checked on
1.1.4; no matching mode in `AttachEnginePlane.suggestModes()`):

1. **A plane through a straight edge at a given angle to a face or plane.** Typical uses: a sketch
   for an inclined cut or boss that starts at an edge of the part, a bend line, a chamfer-like
   pocket. Today one has to attach to the face and type a rotation and position into
   `AttachmentOffset` by hand. The offset is expressed in the face's attachment frame, so when the
   part changes (the edge moves inside the face, the face is resized) the plane no longer passes
   through the edge.

2. **A mid plane between two parallel planes or planar faces.** Typical uses: symmetry plane of a
   part whose thickness is driven by a dimension, mirror plane, sketch plane for a centered rib.
   Today the half distance has to be typed into `AttachmentOffset` and does not update when the
   distance changes. Expressions can cover simple cases (e.g. `Pad.Length / 2`) but not the
   general case of two arbitrary faces.

Other parametric CAD systems offer both as standard reference-plane options ("At angle" with a
face/plane and an edge; "Mid plane" with two faces/planes), and users coming from them expect them.

**Proposed solution**

Add two modes to the plane attacher (`Attacher::AttachEnginePlane`):

- **At angle** — references: a planar face or plane, and a straight edge or line parallel to it;
  plus an angle (e.g. reuse the attachment offset rotation, or a dedicated `MapAngle`-like
  property). Result: the plane contains the edge and makes the given angle with the reference
  plane. Error if the edge is not parallel to the plane.
- **Mid plane** — references: two parallel planar faces or planes. Result: the plane parallel to
  both, halfway between them (normal taken from the first reference). Error if not parallel.

Both should recompute like the other modes, so dependent sketches and features follow the model.

**Workaround in use**

The LikeSolidWorks UI addon (fork) computes the offset itself and re-applies it after every
recompute. It works, but only with the addon installed: without it the plane stays at the last
computed position. A native mode would remove the need for that.

**Version**

FreeCAD 1.1.4 (Windows). No open issue or pull request about these modes was found
(searched 2026-10-27).
