"""
Venta por peso — validaciones del formulario unificado.

Este archivo cubría originalmente el flujo viejo de "Venta por Peso" (pantalla
aparte, Caramelera) para el pedido de Sofia del 2026-09-20. Con el rediseño
del 2026-09-25 (plan `sharded-honking-quilt.md`) ese flujo se retiró de la UI
— `granel:caramelera_create` y el resto de las URLs de `granel` quedaron
desregistradas (ver `superrecord/urls.py`), así que los tests que las usaban
para armar sus fixtures ya no tienen nada que probar y se sacaron de acá.

La cobertura equivalente para el sistema nuevo (crear producto por peso,
Agregar Mercadería, venta en el POS, compras, conteo físico) vive en
`tests/test_weight_sale_nuevo.py`. Lo que queda acá es la validación del
`ProductForm` unificado (el checkbox "Se vende por peso" + sus 4 campos de
tramo), que no depende de ninguna URL de `granel`.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase

from stocks.forms import ProductForm

User = get_user_model()


class FormularioVentaPorPesoTests(TestCase):
    """Rediseño 2026-09-25: "venta por peso" es un checkbox (`is_granel`) en
    el mismo formulario de producto — ya no hay pieza de depósito ni pantalla
    aparte."""

    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user(
            username='sofia_peso', password='x', is_superuser=True, is_staff=True,
        )
        cls.user.groups.add(group)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def _form(self, **extra):
        data = {
            'name': 'Jamón Cocido', 'sku': 'JC-9', 'cost_price': '12000', 'sale_price': '12000',
            'current_stock': '2.5', 'min_stock': '0', 'is_active': 'on',
            'is_granel': 'on',
        }
        data.update(extra)
        return ProductForm(data)

    def test_producto_por_peso_acepta_stock_con_decimales(self):
        self.assertTrue(self._form().is_valid())

    def test_producto_comun_sigue_exigiendo_stock_entero(self):
        form = self._form(current_stock='2.5')
        form.data = {k: v for k, v in form.data.items() if k != 'is_granel'}
        form = ProductForm(form.data)
        self.assertFalse(form.is_valid())
        self.assertIn('current_stock', form.errors)

    def test_tramos_de_precio_en_blanco_quedan_en_cero(self):
        form = self._form()
        self.assertTrue(form.is_valid())
        producto = form.save(commit=False)
        self.assertEqual(producto.sale_price_250g, Decimal('0'))
        self.assertEqual(producto.sale_price_500g, Decimal('0'))
        self.assertEqual(producto.oferta_price_250g, Decimal('0'))
        self.assertEqual(producto.oferta_price_500g, Decimal('0'))

    def test_tramos_y_oferta_se_guardan_tal_cual_se_cargan(self):
        form = self._form(sale_price_250g='2900', oferta_price_250g='2500')
        self.assertTrue(form.is_valid())
        producto = form.save(commit=False)
        self.assertEqual(producto.sale_price_250g, Decimal('2900'))
        self.assertEqual(producto.oferta_price_250g, Decimal('2500'))

    def test_ya_no_existe_el_paso_de_pieza_de_deposito(self):
        """El campo `es_deposito_caramelera` ya no forma parte del form: si
        llega en el POST (ej. un bookmark viejo), se ignora sin más."""
        form = self._form(es_deposito_caramelera='on', weight_per_unit_grams='')
        self.assertNotIn('es_deposito_caramelera', form.fields)
        self.assertTrue(form.is_valid())
