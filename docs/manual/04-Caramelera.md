# 4. Caramelera (granel)

## Qué es la caramelera

Un **frasco/contenedor** donde se mezclan distintas marcas de golosinas que se venden al mismo precio por gramo. Ejemplo: caramelera de "gomitas surtidas" con Mogul, Beldent y marcas blancas adentro.

Como los costos son distintos pero el precio de venta es único, el sistema usa **costo promedio ponderado** para calcular la ganancia (no FIFO).

---

## Abrir un paquete hacia la caramelera

### Cuándo
Cada vez que vaciás un bulto nuevo en el frasco.

### Paso a paso

1. Ir a **Granel → Abrir Paquete**.
2. Seleccionar:
   - La **caramelera destino** (frasco físico).
   - El **producto de depósito** (el bulto cerrado).
   - **Cantidad de paquetes** a abrir.
3. Confirmar.

### Qué pasa por atrás

1. Calcula los gramos nuevos: `cantidad_paquetes × weight_per_unit_grams`.
2. **Recalcula el costo ponderado** de la caramelera:

   ```
   nuevo_costo_gramo =
     (stock_anterior × costo_anterior + gramos_nuevos × costo_nuevo) / total
   ```

3. Suma los gramos al stock de la caramelera.
4. Descuenta el paquete del stock de depósito.
5. Sincroniza el "producto POS" vinculado a esa caramelera (para que al escanear/buscar aparezcan los gramos actualizados).

---

## Vender por gramos en el POS

1. En el POS, buscá la caramelera (o escaneá su código asociado).
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

1. **Pesar físicamente** la caramelera en la balanza.
2. Ir a **Granel → Auditoría**.
3. Seleccionar la caramelera.
4. Ingresar el **peso real en gramos** medido.
5. (Opcional) Notas: causa probable (humedad, derrame, robo).
6. Confirmar.

### Qué pasa por atrás

1. Calcula `diferencia = stock_sistema - peso_real`.
2. Guarda la auditoría con `% merma` y fecha.
3. **Ajusta automáticamente** el stock de la caramelera al peso real.
4. Queda registrada en el historial — podés ver todas las auditorías en el detalle de la caramelera.

Esto te permite detectar robos o desvíos sistemáticos.
