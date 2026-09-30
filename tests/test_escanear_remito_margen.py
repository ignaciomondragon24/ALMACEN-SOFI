"""
Escanear Remito: recalculo de precio de venta al recibir un costo nuevo.

Hallazgo real (29/9/2026, conversación con Sofia sobre el video de "ComercioCity"
de Tommy): "Escanear Remito" ya actualizaba el costo y el stock, pero dejaba el
PRECIO DE VENTA sin tocar cuando un producto que ya existía subía de costo —
justo el diferencial que Tommy mostró ("actualiza el costo y recalcula el
precio de venta al público en el acto"). Nacho decidió: mantener el margen
PROPIO que ya tenía cada producto (no el de la categoría), y mostrarlo en la
pantalla de revisión para que Sofia lo confirme/edite antes de guardar — nunca
se aplica solo, sin que el JSON `sale_price` venga explícito en la confirmación
(eso lo arma la pantalla de revisión, `templates/assistant/scan_invoice.html`).

Estos tests cubren el endpoint `assistant:api_confirm_invoice` (el backend
nunca recalcula nada por sí solo; solo aplica lo que le llega).
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from purchase.models import Purchase, PurchaseItem
from stocks.models import Product

User = get_user_model()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        g, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user('remito_admin', password='x', is_superuser=True, is_staff=True)
        cls.user.groups.add(g)

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.user)

    def confirmar(self, productos, **extra):
        body = {'productos': productos, 'total': 0, 'subtotal': 0}
        body.update(extra)
        return self.c.post(reverse('assistant:api_confirm_invoice'), json.dumps(body),
                            content_type='application/json')


class RecalculoDeMargenTests(Base):
    def setUp(self):
        super().setUp()
        # Jamón: costo $8000, venta $12000 → margen 50%.
        self.producto = Product.objects.create(
            name='Jamón Cocido', sku='JC-REMITO', cost_price=Decimal('8000'),
            purchase_price=Decimal('8000'), sale_price=Decimal('12000'),
        )

    def test_sube_el_costo_y_el_precio_de_venta_si_la_revision_lo_manda(self):
        """La pantalla de revisión calculó 8800 * 1.5 = 13200 (mismo margen
        50%) y lo manda en `sale_price` — el backend lo aplica."""
        r = self.confirmar([{
            'nombre': 'Jamón Cocido', 'cantidad': 5, 'precio_unitario': 8800,
            'product_id': self.producto.id, 'sale_price': 13200,
        }])
        self.assertEqual(r.status_code, 200, r.content)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.purchase_price, Decimal('8800'))
        self.assertEqual(self.producto.sale_price, Decimal('13200'))

    def test_sin_sale_price_en_el_payload_no_toca_el_precio_de_venta(self):
        """Compatibilidad: si la revisión no manda sale_price (0 o ausente),
        el precio de venta queda exactamente como estaba — comportamiento
        de siempre, nada se rompe para quien no usa la sugerencia."""
        r = self.confirmar([{
            'nombre': 'Jamón Cocido', 'cantidad': 5, 'precio_unitario': 8800,
            'product_id': self.producto.id,
        }])
        self.assertEqual(r.status_code, 200, r.content)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.purchase_price, Decimal('8800'))
        self.assertEqual(self.producto.sale_price, Decimal('12000'))  # sin cambios

    def test_producto_recien_creado_no_usa_sale_price_del_payload(self):
        """Para un producto que NO existía, el precio de venta sale de la
        lógica de auto-creación (30% sobre costo) — el campo `sale_price`
        del payload (pensado para productos EXISTENTES) se ignora ahí,
        para no pisar por accidente un valor que no corresponde a este
        producto nuevo."""
        r = self.confirmar([{
            'nombre': 'Queso Cremoso', 'cantidad': 2, 'precio_unitario': 1000,
            'sale_price': 99999,  # no debería aplicarse: no hay product_id
        }])
        self.assertEqual(r.status_code, 200, r.content)
        nuevo = Product.objects.get(name='Queso Cremoso')
        self.assertEqual(nuevo.sale_price, Decimal('1300.00'))  # 1000 * 1.30
        self.assertNotEqual(nuevo.sale_price, Decimal('99999'))

    def test_crea_el_item_de_compra_y_actualiza_stock_como_antes(self):
        """El recalculo de precio de venta es aditivo: no cambia nada de lo
        que ya funcionaba (compra, stock)."""
        r = self.confirmar([{
            'nombre': 'Jamón Cocido', 'cantidad': 5, 'precio_unitario': 8800,
            'product_id': self.producto.id, 'sale_price': 13200,
        }])
        self.assertEqual(r.status_code, 200, r.content)
        purchase = Purchase.objects.get(pk=r.json()['purchase_id'])
        item = PurchaseItem.objects.get(purchase=purchase, product=self.producto)
        self.assertEqual(item.quantity, 5)
        self.assertEqual(item.unit_cost, Decimal('8800'))


class SerializacionParaLaRevisionTests(Base):
    """`purchase:api_search_products` (usado por la pantalla de revisión
    para "encontrar" cada línea del remito) ahora también manda el margen
    actual del producto — lo que el JS necesita para sugerir el precio de
    venta nuevo."""

    def test_incluye_margin_percent_producto_comun(self):
        Product.objects.create(name='Fideos Matarazzo', sku='FID-M', cost_price=Decimal('1000'),
                                purchase_price=Decimal('1000'), sale_price=Decimal('1500'))
        r = self.c.get(reverse('purchase:api_search_products'), {'q': 'Fideos Matarazzo'})
        self.assertEqual(r.status_code, 200)
        data = r.json()['results'][0]
        self.assertEqual(data['margin_percent'], '50.00')

    def test_incluye_margin_percent_producto_por_peso(self):
        Product.objects.create(name='Salame Por Peso', sku='SAL-P', is_granel=True,
                                cost_price=Decimal('6000'), purchase_price=Decimal('6000'),
                                sale_price=Decimal('9000'))
        r = self.c.get(reverse('purchase:api_search_products'), {'q': 'Salame Por Peso'})
        self.assertEqual(r.status_code, 200)
        data = r.json()['results'][0]
        self.assertEqual(data['margin_percent'], '50.00')
        self.assertTrue(data['by_weight'])
