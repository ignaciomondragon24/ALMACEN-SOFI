# 4. Venta por Peso (granel)

![Depósito: las piezas/bultos cerrados que todavía no se abrieron hacia ningún fraccionado.](images/04-deposito-lista.jpg)

## Qué es un producto fraccionado

Un **contenedor** (fiambre en la fiambrera, queso, dietética a granel, etc) donde se van agregando bultos que se venden todos al mismo precio por gramo. Ejemplo: "Jamón Cocido Fraccionado", donde vas abriendo distintas piezas/paquetes comprados a distintos proveedores o a distinto precio.

Como los costos son distintos pero el precio de venta es único, el sistema usa **costo promedio ponderado** para calcular la ganancia (no FIFO).

![Listado de productos a venta por peso, con stock y margen de cada uno.](images/04-venta-por-peso-lista.jpg)

---

## Cargar un producto por peso (1 sola pantalla)

En **Venta por Peso → Nuevo producto por peso** completás 3 pasos. Todo va **por kilo**:

1. **Nombre** — ej: "Jamón cocido", "Queso de máquina", "Almendras".
2. **Costo y precio por kilo**
   - **Costo por kilo**: lo que te cuesta a vos el kilo.
   - **Ganancia %** y **Precio de venta por kilo**: son lo mismo dicho de dos maneras. Si escribís la ganancia, el sistema calcula el precio; si escribís el precio, calcula la ganancia. La ganancia es **sobre el costo**, igual que en Productos (costo $100 y venta $130 = 30%).
   - Abajo ves al instante cuánto ganás por kilo y a cuánto queda el ¼, el ½ y los 100g.
3. **Cuánta mercadería tenés ahora** — el peso en kg (o g). Si todavía no tenés, lo dejás vacío.

Con **Guardar y dejar listo para vender** ya aparece en la caja. No hay que hacer nada más.

### Sumar mercadería cuando comprás más

En el producto, botón verde **Agregar mercadería**: ponés cuántos kilos entraron y a cuánto te salió el kilo. El sistema suma el peso al stock y recalcula el **costo por kilo** (promedio entre lo que tenías y lo nuevo), así la ganancia siempre sale bien aunque cambie el precio del proveedor.

### Opciones avanzadas (no hace falta tocarlas)

- **Precio especial por kilo (oferta)**: si lo completás, desde 250g en adelante se cobra a ese precio por kilo en vez del normal. Si lo dejás vacío no hay ninguna oferta.
- **Piezas cerradas en Depósito**: solo si querés cargar piezas enteras (ej: una pata de jamón de 500g) desde Inventario y que se abran solas hacia el producto. Ver la sección de abajo. Si cargás una pieza de depósito hay que indicar sus **gramos** (sin eso el sistema no puede abrirla).

---

## Depósito de piezas cerradas (opcional)

Si preferís manejar piezas enteras:

1. **Inventario → Nuevo Producto**, tildando **"Producto para Venta por Peso (pieza/bulto de depósito)"**: marca, **gramos por unidad** (obligatorio) y **precio de costo** de la pieza.
2. Cargale stock como a cualquier producto (por **Compras** o ajuste manual). La cantidad es de **piezas**, no gramos.
3. En el producto por peso, en **Opciones avanzadas**, marcá esa pieza como autorizada.

## La apertura hacia el producto fraccionado es automática

**Ya no hace falta clickear "abrir" cada vez que empezás una pieza nueva.** En cuanto el depósito (Paso 1) tiene piezas en stock (Paso 2) y está autorizado en un producto fraccionado (Paso 3), el sistema las abre solo, apenas se cumplen las dos condiciones — no importa el orden en que hiciste los pasos:

- Si cargás stock nuevo al depósito (por una compra o con el ajuste manual +/-) y ya estaba autorizado → se abre al toque.
- Si autorizás un depósito que ya tenía piezas esperando → se abren en el momento de guardar esa autorización.

![Ficha del producto fraccionado: stock actual, precios, depósito autorizado e historial de aperturas.](images/04-venta-por-peso-detalle.jpg)

### Qué pasa por atrás, automáticamente

1. Calcula los gramos nuevos: cantidad de piezas × gramos que trae cada una.
2. **Recalcula el costo ponderado** del producto fraccionado (ver sección siguiente).
3. Suma los gramos al stock del producto fraccionado.
4. Descuenta las piezas del stock de depósito (queda en 0 — ya están "puestas en el mostrador").
5. Sincroniza el "producto POS" vinculado (para que al escanear/buscar aparezcan los gramos actualizados).
6. Igual que antes, queda registrada en el historial de aperturas para auditoría.

### Cuándo SÍ hace falta abrir a mano

Solo en un caso poco común: si el mismo depósito está autorizado en **más de un** producto fraccionado a la vez, el sistema no puede adivinar hacia cuál abrir — ahí sí tenés que ir al detalle del producto fraccionado y usar el botón **"Abrir Manualmente"**, eligiendo la pieza y la cantidad.

---

## Cómo se calcula el costo ponderado

El sistema **no promedia por cantidad de productos distintos**. Promedia **por gramos**: cada gramo dentro del frasco hereda un costo promedio que refleja de dónde vinieron los gramos que ya había y los que acabás de agregar.

### Fórmula

```
costo_nuevo =  (stock_antes × costo_antes) + (gramos_nuevos × costo_nuevo_pieza)
               ────────────────────────────────────────────────────────────────
                                stock_antes + gramos_nuevos
```

Es decir: **total de plata invertida ÷ gramos totales**.

### Costo por gramo de la pieza que abrís

Se calcula a partir del precio de costo del producto de depósito:

```
costo por gramo de la pieza = costo de la pieza ÷ gramos que trae
```

Ejemplo: pieza de jamón cocido de 500 g que costó $5.000 → $10 por gramo.

### Ejemplo con dos piezas distintas

El producto fraccionado arranca vacío (stock = 0, costo = 0).

**Paso 1 — abrís una pieza de 500 g que costó $5.000:**

- Costo por gramo de la pieza: `5.000 / 500 = $10/g`
- Como no hay gramos previos, el costo ponderado queda directo en **$10/g**.
- Stock: **500 g a $10/g**.

**Paso 2 — abrís una pieza de 900 g que costó $13.500 (otro proveedor, otro precio):**

- Costo por gramo de la pieza: `13.500 / 900 = $15/g`
- Aplicamos la fórmula ponderada:

  ```
  costo =  (500 × 10) + (900 × 15)   =   5.000 + 13.500   =   18.500
           ─────────────────────         ────────────────       ──────
                500 + 900                       1.400            1.400
  ```

- Costo ponderado final: **≈ $13,2143/g**.
- Stock: **1.400 g a $13,21/g**.

### Cosas clave a entender

- **Pondera por gramos, no por unidades**: una pieza de 900 g "pesa" más en el promedio que una de 500 g, aunque sea una sola pieza.
- **Cada apertura recalcula el promedio completo**: los gramos viejos se mezclan con los nuevos y todos pasan a compartir el nuevo costo. No se guardan lotes individuales dentro del producto fraccionado (sí se guarda cada apertura en el historial para auditoría).
- **El POS usa este costo ponderado** para calcular la ganancia de cada venta por peso.
- **Las auditorías de peso no tocan el costo ponderado** — solo ajustan gramos (merma/sobrante). Si vendés 200 g después del paso 2, los 1.200 g restantes siguen a $13,21/g; cuando abras otra pieza, se promedia contra esos 1.200 g × $13,21.

---

## Vender por gramos en el POS

1. En el POS, buscá el producto por peso (o escaneá su código asociado).
2. Se abre el modal: ingresá los **gramos** a vender (o tocá 100g / ¼ kg / ½ kg). Si no hay stock cargado, el modal te lo avisa y no deja agregar.
3. El sistema calcula el precio:
   - < 250g → proporcional al precio cada 100g.
   - ≥ 250g con **precio kilo oferta** activo → se aplica la regla de tres sobre el precio del kilo.
   - Sin oferta, siempre es proporcional al precio del kilo. El precio lo calcula el sistema, no la pantalla.
4. Seguí con el cobro normal.

---

## Auditoría de merma

### Cuándo
Periódicamente (una vez por semana recomendado) o cuando sospéches diferencias.

### Paso a paso

1. **Pesar físicamente** el producto en la balanza.
2. Entrar al detalle del producto fraccionado → botón **Auditoría**.
3. Ingresar el **peso real en gramos** medido.
4. (Opcional) Notas: causa probable (humedad, derrame, robo).
5. Confirmar.

### Qué pasa por atrás

1. Calcula la diferencia entre el stock del sistema y el peso real.
2. Guarda la auditoría con el % de merma y la fecha.
3. **Ajusta automáticamente** el stock del producto fraccionado al peso real.
4. Queda registrada en el historial — podés ver todas las auditorías en el detalle del producto.

Esto te permite detectar robos o desvíos sistemáticos.
