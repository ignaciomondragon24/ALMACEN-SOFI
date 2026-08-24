# 8. Vencimientos

## Qué es

Un control automático de fechas de vencimiento por lote, pensado para fiambrería, lácteos y dietética. El sistema avisa antes de que un producto se venza para que puedas venderlo con descuento, devolverlo o descartarlo a tiempo — en vez de enterarte cuando ya es tarde.

---

## Cargar la fecha de vencimiento

### Cuándo
Al **recibir una compra** (capítulo 2), no antes. Es en ese momento donde el sistema crea el lote de stock, y ahí es donde se le asocia el vencimiento.

### Paso a paso
1. Ir a **Compras → [Tu OC pendiente] → Recibir**.
2. En la fila de cada producto vas a ver una columna **Vencimiento** con un campo de fecha.
3. Cargala si ese producto vence. Si no vence (por ejemplo, productos de limpieza), dejala vacía — es opcional.
4. Confirmar la recepción como siempre.

No hay forma de cargar o corregir la fecha después de recibida la compra desde la pantalla normal — si te equivocaste, pedile a Ignacio que la corrija desde el panel de administración.

---

## Ver los vencimientos

### Dónde
**Inventario → Vencimientos**.

### Qué muestra
Todos los lotes que **todavía tienen stock** y tienen fecha de vencimiento cargada, ordenados por fecha más próxima, con tres colores:

- **Rojo — Vencido:** la fecha ya pasó. Hay que sacarlo de la venta o descartarlo.
- **Amarillo — Vence pronto:** vence dentro de los próximos 7 días (podés cambiar ese umbral desde un filtro en la misma pantalla).
- **Azul — Próximo:** vence dentro de los próximos 30 días. Sirve para planificar.

Podés buscar por nombre de producto y ajustar cuántos días de anticipación considerar "vence pronto".

---

## Alertas

Cada vez que entrás al sistema (Admin o Cajero Manager), el **dashboard** muestra un cartel con la cantidad de lotes vencidos y por vencer, con un link directo a la pantalla de Vencimientos. También hay un número en rojo al lado de "Vencimientos" en el menú de Inventario, así se nota sin tener que entrar a buscarlo.

Estas alertas son **solo dentro del sistema** — no se manda nada por WhatsApp ni email todavía. Hay que entrar a mirar (o fijarse en el cartel del dashboard cuando iniciás sesión).

---

## Qué hacer con un producto por vencer

El sistema **no automatiza** ninguna acción sobre el producto vencido (no lo baja de precio ni lo saca de la venta solo). Es una decisión de negocio: podés

- Venderlo con descuento manual antes de que venza (capítulo 3, "descuento manual").
- Si se venció y no se puede vender, hacer un **ajuste de stock** con motivo "Mercadería Vencida" (capítulo 5) para sacarlo del inventario y que quede registrado como pérdida.
