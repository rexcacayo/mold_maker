# Mold Maker 1.0.0

Complemento para Blender 4.2 a 5.x (probado en 5.2). Crea **moldes imprimibles de cualquier pieza**.
Todo en modo Objeto; la pieza original no se toca. Licencia GPL-3.0-or-later.

## Uso (Vista 3D → N → pestaña Mold Maker)

1. **Selecciona la pieza** (cerrada; si no lo está, pásala antes por Mesh Doctor).
2. **Elige el tipo de molde**:
   - **Silicona** (lo más usado para figuras): crea una **caja** (paredes) y una **base con soporte**.
     Pegas la pieza sobre el soporte, encajas la caja en la ranura de la base, sellas con silicona
     caliente o plastilina y viertes. El soporte deja el agujero para verter en el molde de silicona.
     Te dice **cuántos ml y gramos de silicona** necesitas.
   - **Rígido**: un bloque con la pieza vaciada dentro, partido en **2 mitades** por su parte más ancha.
     Lleva **llaves de centrado** (cono en una mitad, hueco en la otra), **bebedero** para verter y
     **respiraderos** donde se queda el aire. Para resina o escayola directamente en el molde impreso.
     Te dice cuántos ml de resina/escayola hacen falta.
3. **Crear molde**. Si no te gusta, Ctrl+Z y cambia los ajustes.
4. **Exportar STL** en mm.

## Ajustes

- Rígido: eje de partición (Auto/X/Y/Z), subir/bajar la partición, pared, bebedero, respiraderos, llaves, holgura.
- Silicona: silicona alrededor de la pieza, pared de la caja, altura y grosor del soporte, holgura de la ranura.

## Consejos

- Molde rígido: usa desmoldeante (vaselina, cera o spray) y lija las caras de partición si no cierran bien.
  Sujeta las mitades con gomas o pinzas al verter.
- Molde de silicona: deja al menos 8 mm de silicona alrededor; si la pieza tiene muchos huecos, mejor
  cortar el molde de silicona con un cúter en zigzag para sacarla.

## Límites

- El molde rígido de 2 mitades sirve para piezas que salen sin quedarse enganchadas (sin retenciones).
  Las figuras con brazos o huecos complicados: mejor molde de silicona.
- La partición automática elige la cara más ancha; en piezas raras, prueba otro eje o súbela/bájala.
