# Pedido para el GitHub de FreeCAD: plano "en ángulo" y "punto medio"

**Importante (2026-10-27):** FreeCAD no acepta pedidos escritos por una IA. Su política
(https://github.com/FreeCAD/FreeCAD/blob/main/AI_POLICY.md) pide que toda la comunicación la haga
la persona misma; el formulario de pedidos lo repite ("Using LLMs to communicate is not allowed").
Por eso Claude **no** lo publica: este texto es solo una guía de los puntos para que el usuario
lo escriba con sus palabras (puede ser en inglés simple; si usa un traductor, la política pide
agregar también el texto original).

Dónde: https://github.com/FreeCAD/FreeCAD/issues/new/choose -> "Report a Problem" (no hay
formulario aparte para funciones nuevas; el mismo dice "missing altogether"). Banco: Part Design.
Antes de publicar, buscar de nuevo por si alguien ya lo pidió (al 2026-10-27 no había nada).

## Puntos del pedido (solo el pedido, sin proponer cómo hacerlo)

1. Plano de referencia **en ángulo**: un plano que pase por una arista recta y forme un ángulo
   dado con una cara plana o un plano. Que siga a la pieza cuando cambian las cotas.
2. Plano de referencia en el **punto medio**: un plano a mitad de camino entre dos caras planas
   (o planos) paralelas. Que siga a la pieza cuando cambia la distancia entre ellas.
3. Para qué se usan: croquis de cortes o salientes inclinados que arrancan en una arista; plano
   de simetría de una pieza cuyo espesor depende de una cota; plano para un nervio centrado.
4. En FreeCAD 1.1.4 ninguno de los dos se puede armar con los modos de adjunción del plano de
   referencia de forma que siga a la pieza.
5. Otros programas de CAD los traen como opciones comunes del plano de referencia.
6. Versión: FreeCAD 1.1.4, Windows.
