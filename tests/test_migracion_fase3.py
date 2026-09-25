"""
Fase 3 del rediseño de venta por peso — Migración A
(`stocks/migrations/0025_migrar_carameleras_y_depositos.py`).

Prueba la función `migrar_datos` directamente (mismo código que corre en el
deploy real) contra datos armados a mano que imitan los reales de
producción, sin depender del framework de test de migraciones de Django
(no hace falta: esta migración no cambia el esquema, solo copia datos).
"""
import importlib
from decimal import Decimal

from django.apps import apps
from django.test import TestCase

from granel.models import Caramelera
from stocks.models import Product

migracion = importlib.import_module('stocks.migrations.0025_migrar_carameleras_y_depositos')


class MigrarCarameleraTests(TestCase):
    def _crear_caramelera_con_producto(self, **extra):
        base = dict(
            nombre='Jamón Cocido', precio_100g=Decimal('1200.00'),
            precio_cuarto=Decimal('11000.00'), stock_gramos_actual=Decimal('2500.00'),
            costo_ponderado_gramo=Decimal('0.800000'),
        )
        base.update(extra)
        c = Caramelera.objects.create(**base)
        # Igual que hace GranelService al crear: producto POS vinculado por FK.
        p = Product.objects.create(
            name=c.nombre, sku='JC-MIG', is_granel=True, granel_caramelera=c,
            sale_price=c.precio_100g, sale_price_250g=c.precio_cuarto,
            current_stock=c.stock_gramos_actual,
        )
        return c, p

    def test_copia_stock_en_kilos(self):
        c, p = self._crear_caramelera_con_producto(stock_gramos_actual=Decimal('2500.00'))
        migracion.migrar_datos(apps, None)
        p.refresh_from_db()
        self.assertEqual(p.current_stock, Decimal('2.500'))

    def test_copia_precio_por_kilo_no_por_100g(self):
        c, p = self._crear_caramelera_con_producto(precio_100g=Decimal('1200.00'))
        migracion.migrar_datos(apps, None)
        p.refresh_from_db()
        self.assertEqual(p.sale_price, Decimal('12000.00'))

    def test_copia_costo_ponderado_a_costo_por_kilo(self):
        c, p = self._crear_caramelera_con_producto(costo_ponderado_gramo=Decimal('0.800000'))
        migracion.migrar_datos(apps, None)
        p.refresh_from_db()
        self.assertEqual(p.cost_price, Decimal('800.00'))
        self.assertEqual(p.purchase_price, Decimal('800.00'))

    def test_precio_cuarto_se_convierte_en_oferta_250g(self):
        c, p = self._crear_caramelera_con_producto(precio_cuarto=Decimal('11000.00'))
        migracion.migrar_datos(apps, None)
        p.refresh_from_db()
        self.assertEqual(p.oferta_price_250g, Decimal('2750.00'))
        self.assertEqual(p.sale_price_250g, Decimal('0'))

    def test_sin_precio_cuarto_oferta_queda_en_cero(self):
        c, p = self._crear_caramelera_con_producto(precio_cuarto=Decimal('0'))
        migracion.migrar_datos(apps, None)
        p.refresh_from_db()
        self.assertEqual(p.oferta_price_250g, Decimal('0'))

    def test_desvincula_la_caramelera(self):
        c, p = self._crear_caramelera_con_producto()
        migracion.migrar_datos(apps, None)
        p.refresh_from_db()
        self.assertIsNone(p.granel_caramelera_id)
        # La Caramelera original queda intacta, sin usarse.
        c.refresh_from_db()
        self.assertEqual(c.stock_gramos_actual, Decimal('2500.00'))

    def test_precio_migrado_da_lo_mismo_que_la_regla_vieja(self):
        """El caso central: después de migrar, price_for_grams(nuevo) tiene
        que dar exactamente lo mismo que calcular_precio(viejo) para
        cualquier peso — ya probado en abstracto en
        tests/test_weight_price_for_grams.py, acá se confirma sobre el
        camino real de la migración."""
        c, p = self._crear_caramelera_con_producto(
            precio_100g=Decimal('1200.00'), precio_cuarto=Decimal('11000.00'),
        )
        migracion.migrar_datos(apps, None)
        p.refresh_from_db()
        for gramos in (50, 100, 150, 250, 300, 500, 750, 1000, 1500):
            self.assertEqual(
                p.price_for_grams(gramos), c.calcular_precio(gramos),
                f'diverge en {gramos}g',
            )

    def test_producto_sin_caramelera_no_se_toca(self):
        comun = Product.objects.create(
            name='Gaseosa', sku='GAS-MIG', current_stock=Decimal('10'),
            sale_price=Decimal('800'), cost_price=Decimal('500'),
        )
        migracion.migrar_datos(apps, None)
        comun.refresh_from_db()
        self.assertEqual(comun.current_stock, Decimal('10'))
        self.assertEqual(comun.sale_price, Decimal('800.00'))


class ConvertirDepositosTests(TestCase):
    def test_deposito_pasa_a_ser_producto_comun(self):
        p = Product.objects.create(
            name='Bolsa Fiambre x3kg', sku='DEP-1', es_deposito_caramelera=True,
            weight_per_unit_grams=Decimal('3000'), current_stock=Decimal('4'),
            sale_price=Decimal('100'),
        )
        migracion.migrar_datos(apps, None)
        p.refresh_from_db()
        self.assertFalse(p.es_deposito_caramelera)
        # El stock no se toca — ya está en la unidad de un producto común.
        self.assertEqual(p.current_stock, Decimal('4'))

    def test_deposito_ahora_es_vendible_directo_en_el_pos(self):
        from pos.models import POSTransaction, POSSession
        from pos.services import CartService, POSService
        from cashregister.models import CashRegister, CashShift, PaymentMethod
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(username='u1', password='x')
        register = CashRegister.objects.create(name='Caja', code='DEP1', is_active=True)
        shift = CashShift.objects.create(
            cash_register=register, cashier=user, initial_amount=Decimal('0'), status='open',
        )
        tx = POSService.create_transaction(POSService.get_or_create_session(shift))

        p = Product.objects.create(
            name='Bolsa Fiambre x3kg', sku='DEP-2', es_deposito_caramelera=True,
            weight_per_unit_grams=Decimal('3000'), current_stock=Decimal('4'),
            sale_price=Decimal('100'), is_active=True,
        )
        # Antes de migrar: bloqueado.
        item, msg = CartService.add_item(tx, p.id, quantity=1)
        self.assertIsNone(item)
        self.assertIn('pieza de depósito', msg)

        migracion.migrar_datos(apps, None)
        p.refresh_from_db()

        item, msg = CartService.add_item(tx, p.id, quantity=1)
        self.assertIsNotNone(item, msg)

    def test_no_afecta_productos_que_no_son_de_deposito(self):
        p = Product.objects.create(
            name='Gaseosa', sku='GAS-DEP', current_stock=Decimal('10'), sale_price=Decimal('800'),
        )
        migracion.migrar_datos(apps, None)
        p.refresh_from_db()
        self.assertFalse(p.es_deposito_caramelera)
