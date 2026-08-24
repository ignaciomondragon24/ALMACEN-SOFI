# 4. Venta por Peso (granel)

![Depósito: las piezas/bultos cerrados que todavía no se abrieron hacia ningún fraccionado.](images/04-deposito-lista.jpg)

## Qué es un producto fraccionado

Un **contenedor** (fiambre en la fiambrera, queso, dietética a granel, etc) donde se van agregando bultos que se venden todos al mismo precio por gramo. Ejemplo: "Jamón Cocido Fraccionado", donde vas abriendo distintas piezas/paquetes comprados a distintos proveedores o a distinto precio.

Como los costos son distintos pero el precio de venta es único, el sistema usa **costo promedio ponderado** para calcular la ganancia (no FIFO).

![Listado de productos a venta por peso, con stock y margen de cada uno.](images/04-venta-por-peso-lista.jpg)

---

## Abrir un paquete hacia el producto fraccionado

### Cuándo
Cada vez que abrís una pieza/bulto nuevo (ej: una nueva pata de jamón, una nueva horma de queso).

### Paso a paso

1. Ir a **Inventario → Venta por Peso**, entrar al producto.
2. Seleccionar:
   - El **producto de depósito** (el bulto/pieza cerrada).
   - **Cantidad de paquetes** a abrir.
3. Confirmar.

![Ficha del producto fraccionado: stock actual, precios, depósito autorizado e historial de aperturas.](images/04-venta-por-peso-detalle.jpg)

### Qué pasa por atrás

1. Calcula los gramos nuevos: cantidad de paquetes × gramos que trae cada uno.
2. **Recalcula el costo ponderado** del producto fraccionado (ver sección siguiente).
3. Suma los gramos al stock del producto fraccionado.
4. Descuenta el paquete del stock de depósito.
5. Sincroniza el "producto POS" vinculado (para que al escanear/buscar aparezcan los gramos actualizados).

---

## Cómo se calcula el costo ponderado

El sistema **no promedia por cantidad de productos distintos**. Promedia **por gramos**: cada gramo dentro del frasco hereda un costo promedio que refleja de dónde vinieron los gramos que ya había y los que acabás de agregar.

### Fórmula

```
costo_nuevo =  (stock_antes × costo_antes) + (gramos_nuevos × costo_nuevo_bolsa)
               ────────────────────────────────────────────────────────────────
                                stock_antes + gramos_nuevos
```

Es decir: **total de plata invertida ÷ gramos totales**.

### Costo por gramo de la bolsa que abrís

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

1. En el POS, buscá el producto fraccionado (o escaneá su código asociado).
2. Se abre el modal: ingresá los **gramos** a vender.
3. El sistema calcula el precio:
   - < 250g → proporcional al precio cada 100g.
   - ≥ 250g con **precio kilo oferta** activo → se aplica la regla de tres sobre el precio del kilo.
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
