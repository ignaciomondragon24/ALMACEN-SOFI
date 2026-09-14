"""
Bug reportado por Sofia (2026-09-14): al buscar un producto por peso en el
POS no le aparecía el modal pidiendo los gramos. Causa real: los productos
de depósito (es_deposito_caramelera=True) — piezas cerradas de uso interno,
sin sentido para vender sueltas — aparecían mezclados en el buscador y el
panel de productos del POS junto al producto fraccionado real. Si tocaba
por error el de depósito, se agregaba como 1 unidad normal (sin is_granel),
sin el modal de gramos.

Fix: excluir productos de depósito de las vistas de venta del POS
(api_search, api_all_products) y rechazarlos explícitamente si de todos
modos se intenta agregarlos al carrito (CartService.add_item).
"""
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from stocks.models import Product, ProductCategory
from pos.models import POSSession, POSTransaction
from pos.services import CartService, POSService
from cashregister.models import PaymentMethod, CashRegister, CashShift

User = get_user_model()


class DepositoNotSellableTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user(
            username='dep_admin', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.user.groups.add(cls.admin_group)
        cls.category = ProductCategory.objects.create(name='Fiambres Dep Test')

        cls.deposito = Product.objects.create(
            name='Jamon Cocido - Pieza', sku='DEP-NS-001',
            category=cls.category, es_deposito_caramelera=True,
            weight_per_unit_grams=Decimal('500'),
            cost_price=Decimal('5000'), sale_price=Decimal('0.01'),
            current_stock=Decimal('3'),
        )
        cls.normal = Product.objects.create(
            name='Gaseosa Normal', sku='NORM-001',
            category=cls.category,
            cost_price=Decimal('500'), sale_price=Decimal('800'),
            current_stock=Decimal('10'),
        )

        cls.cash_method = PaymentMethod.objects.create(
            name='Efectivo Dep Test', code='cash_dep_test', is_active=True
        )
        cls.register = CashRegister.objects.create(
            name='Caja Dep Test', code='DEP01', is_active=True
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_api_search_excluye_deposito(self):
        r = self.client.get(reverse('pos:api_search'), {'q': 'jamon'})
        self.assertEqual(r.status_code, 200)
        names = [p['name'] for p in r.json()['products']]
        self.assertNotIn('Jamon Cocido - Pieza', names)

    def test_api_search_sigue_encontrando_productos_normales(self):
        r = self.client.get(reverse('pos:api_search'), {'q': 'gaseosa'})
        self.assertEqual(r.status_code, 200)
        names = [p['name'] for p in r.json()['products']]
        self.assertIn('Gaseosa Normal', names)

    def test_api_all_products_excluye_deposito(self):
        r = self.client.get(reverse('pos:api_all_products'))
        self.assertEqual(r.status_code, 200)
        names = [p['name'] for p in r.json()['products']]
        self.assertNotIn('Jamon Cocido - Pieza', names)
        self.assertIn('Gaseosa Normal', names)

    def test_cart_add_rechaza_producto_deposito(self):
        shift = CashShift.objects.create(
            cash_register=self.register, cashier=self.user,
            initial_amount=Decimal('1000'), status='open',
        )
        session = POSService.get_or_create_session(shift)
        pos_transaction = POSService.create_transaction(session)

        item, message = CartService.add_item(pos_transaction, self.deposito.pk, Decimal('1'))
        self.assertIsNone(item)
        self.assertIn('depósito', message)

    def test_cart_add_sigue_permitiendo_producto_normal(self):
        shift = CashShift.objects.create(
            cash_register=self.register, cashier=self.user,
            initial_amount=Decimal('1000'), status='open',
        )
        session = POSService.get_or_create_session(shift)
        pos_transaction = POSService.create_transaction(session)

        item, message = CartService.add_item(pos_transaction, self.normal.pk, Decimal('1'))
        self.assertIsNotNone(item)
