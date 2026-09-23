"""Test del bug reportado por Sofia (19/09/2026): al cargar un producto nuevo
escaneando el código de barras y completando todos los campos, "Guardar" no
hacía nada ("se tilda la página") y no llegaba ningún POST al servidor.

Causas (ambas del lado del navegador, por eso el servidor no logueaba error):
1. "Gramos por unidad" (dentro de la sección oculta de venta por peso) llegaba
   con "0.00" en un producto sin peso y tenía min="1": campo inválido y no
   enfocable -> Chrome cancelaba el submit sin mostrar ningún mensaje.
2. Costo y precio de venta tenían step="1" pero el JS los rellena con 2
   decimales (costo x margen), así que cualquier precio con centavos era
   rechazado por el navegador. Stock tenía step="1" con el modelo en 3 decimales.
"""
import re

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

User = get_user_model()


def _input_tag(html, field_id):
    m = re.search(r'<input[^>]*\bid="%s"[^>]*>' % field_id, html, re.S)
    assert m, f'no se encontró el input #{field_id}'
    return m.group(0)


class ProductFormSaveBlockersTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name='Admin')
        cls.admin = User.objects.create_user(
            username='blockers_admin', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.admin.groups.add(group)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)

    def _new_product_html(self):
        return self.client.get(reverse('stocks:product_create')).content.decode()

    def test_weight_field_is_blank_and_never_forces_min_1(self):
        tag = _input_tag(self._new_product_html(), 'id_weight_per_unit_grams')
        self.assertIn('value=""', tag)
        # min="1" + campo oculto era lo que bloqueaba el envío en silencio
        self.assertNotIn('min="1"', tag)

    def test_prices_accept_cents(self):
        html = self._new_product_html()
        for field_id in ('id_cost_price', 'id_sale_price'):
            self.assertIn('step="0.01"', _input_tag(html, field_id))

    def test_stock_is_whole_units_only(self):
        # 2026-09-23: el stock de productos comunes pasó a contarse en unidades
        # enteras (pedido de Nacho) — reemplaza al viejo "test_stock_accepts_decimals",
        # que verificaba justo lo contrario.
        self.assertIn('step="1"', _input_tag(self._new_product_html(), 'id_current_stock'))

    def test_create_product_with_cents_price(self):
        response = self.client.post(reverse('stocks:product_create'), {
            'name': 'Queso Sofia Test', 'barcode': '7791234500001',
            'cost_price': '850', 'sale_price': '1147.50',
            'current_stock': '3', 'min_stock': '0',
            'weight_per_unit_grams': '', 'is_active': 'on',
        })
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and response.context['form'].errors)
