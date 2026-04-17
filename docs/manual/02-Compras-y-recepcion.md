# 2. Compras y recepción de mercadería

## Cargar una orden de compra

### Cuándo usarla
Cada vez que le comprás mercadería a un proveedor. La OC te sirve para:
- Dejar registrado qué pediste y a qué precio.
- Al recibir, sumar stock automáticamente y generar el gasto.

### Paso a paso

1. Ir a **Compras → Nueva Orden de Compra**.
2. Seleccionar **proveedor**. Si no existe, crearlo (nombre, CUIT, teléfono).
3. Agregar items, uno por fila:
   - Producto (buscándolo por nombre o escaneando).
   - **Cantidad en UNIDADES BASE**. Si el proveedor te manda 10 bultos de 144 unidades = cargá `1440`, no `10`.
   - **Costo unitario** (lo que te cuesta cada unidad).
   - **Precio de venta** (opcional — si lo completás, al recibir actualiza el precio del producto).
4. Revisar el **IVA** (por defecto 21%).
5. **Crear Orden**. Queda con estado `pending` (pendiente de recibir).

---

## Recepcionar la mercadería

### Cuándo hacerlo
Cuando la mercadería llegó físicamente al local. **Hasta que no la recibás, no suma al stock.**

### Paso a paso

1. Ir a **Compras → [Tu OC pendiente] → Recibir**.
2. Confirmar.

Eso es todo. El sistema hace el resto.

### Qué pasa por atrás

Cuando confirmás la recepción, por cada ítem de la OC el sistema:

1. **Suma el stock** al producto base y **cascadea a los empaques** (unidad, display, bulto) automáticamente.
2. **Recalcula el costo promedio** del producto con la nueva compra.
3. **Crea un lote (StockBatch)** con la fecha y el precio de esa compra. Este lote es el que se va a consumir FIFO al vender.
4. Si pusiste precio de venta en la OC, **actualiza el precio del producto**.
5. **Genera un gasto automático** en categoría "Proveedores" por el total de la OC.
6. Marca la OC como `received`.

---

## Comprar el mismo producto a varios proveedores

Si comprás Coca-Cola al proveedor A a $100 y después al proveedor B a $150, el sistema:

- Crea **dos lotes distintos**, cada uno con su precio y fecha.
- El **costo promedio** del producto se recalcula (pasa a ser algo entre $100 y $150, ponderado por cantidad).
- Al vender, se consume **primero el lote más antiguo** (el de $100). La ganancia se calcula con ese costo real — no con el promedio. Esto refleja ganancia verdadera y trazabilidad.

---

## Errores comunes

- **Cargar cantidad en bultos en vez de unidades.** Si comprás 2 bultos de 144 y ponés `2`, el sistema suma 2 unidades al stock (no 288). Corregilo antes de recibir, o ajustá manualmente después.
- **Olvidarse de recepcionar.** Mientras esté `pending`, el stock no se actualiza y no se genera el gasto.
