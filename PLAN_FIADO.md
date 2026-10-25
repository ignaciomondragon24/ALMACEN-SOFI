# Plan: Fiado (cuenta corriente de clientes)

Pedido de Sofia: desde el POS poder "fiar" una venta a un cliente, con clientes
ilimitados. Lo fiado NO es venta facturada del día; cuando el cliente paga (total o
parcial) se descuenta de su cuenta y TAMPOCO cuenta como venta del día.

## Decisiones de diseño

| Tema | Decisión | Por qué |
|---|---|---|
| Dónde vive | App nueva `fiado` (modelos `Customer`, `FiadoEntry`) | Aislado; no toca el flujo de ventas existente |
| Venta fiada | `POSTransaction.status = 'on_credit'` ("Fiado") | Los reportes ya filtran `status='completed'` → quedan afuera solos |
| Stock | Se descuenta al fiar (la mercadería sale) | Se reutiliza el mismo código de descuento (FIFO, granel, packagings) |
| Saldo | Libro de movimientos (cargo / pago); saldo = cargos − pagos (sin anulados) | Auditable, sin campo "saldo" que se desincronice |
| Pago de fiado | `FiadoEntry` pago + `CashMovement` con `is_fiado_payment=True` | La plata entra al cajón (arqueo correcto) pero NO suma a "ventas" |
| Cierre Z | Ventas por método / total ventas excluyen cobros de fiado; línea aparte | Evita la distorsión que describe Sofia |
| Pago parcial | Permitido; no se puede cobrar más que el saldo | Debe 300, paga 250 → queda 50 |
| Deuda previa | "Sumar deuda manual" (cargo sin venta) | Saldos anteriores al sistema |
| Anular | Pagos y cargos manuales; cargos con venta no | Una venta con stock no se "desanula" desde acá |
| Permisos | Cajero/Manager/Admin fían y cobran; anular solo Manager/Admin | Coherente con el POS |
| Push | NO se pushea solo: queda commiteado local | El deploy toca producción de la clienta |

## Pasos

1. App `fiado`: modelos + migración + admin.
2. `CashMovement.is_fiado_payment` + ajustar totales de `CashShift`; Cierre Z (pantalla y TXT).
3. `pos`: status `on_credit` (migración), extraer descuento de stock a helper reutilizable.
4. `FiadoService`: fiar venta, registrar pago, deuda manual, anular.
5. Vistas/URLs/templates: lista, alta/edición, detalle con historial, pago, deuda manual, anular.
6. POS: botón "Fiado" + modal (buscar/crear cliente) + ticket "FIADO".
7. Navbar: "Fiados".
8. Tests (`tests/test_fiado.py`) + suite completa + `smoke_flows` + prueba en navegador.
