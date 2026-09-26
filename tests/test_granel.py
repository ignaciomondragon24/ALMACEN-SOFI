"""
Tests for the Granel (Caramelera) system — historia, sistema VIEJO.

Fase 3 del rediseño de venta por peso (Migración B, 2026-09-26): se borraron
las 4 columnas que vinculaban un `stocks.Product` a una `Caramelera`
(`granel_caramelera`, `es_deposito_caramelera`, `granel_price_weight_grams`,
`weighted_avg_cost_per_gram`). Ya no existe forma de crear ese vínculo — el
mecanismo completo (piezas de depósito, "abrir paquete" hacia una caramelera,
sync automático al Product del POS) quedó retirado, no solo desconectado del
menú. Por eso este archivo quedó reducido a lo que sigue siendo real: la
lógica de `Caramelera`/`GranelService` que NO toca `Product` en absoluto
(precio, venta, auditoría) y el FIFO genérico de `StockBatch` (que nunca
dependió de esa vinculación). Los tests que armaban un Product vinculado
(`WeightedAverageCostTest`, `TransferValidationTest`, `AutoAperturaTest`,
`POSDecimalQuantityTest`, `OtrosCaminosDeStockTests`) se sacaron de acá —
la funcionalidad que probaban ya no es alcanzable ni construible.
"""
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from stocks.models import Product, ProductCategory
from cashregister.models import PaymentMethod, CashRegister, CashShift
from granel.models import Caramelera
from granel.services import GranelService, BatchService

User = get_user_model()


class GranelBaseTestCase(TestCase):
    """Base test case with common setup for granel tests."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user(
            username='testgranel', password='testpass123',
            first_name='Test', last_name='User'
        )
        cls.user.groups.add(cls.admin_group)

        cls.category = ProductCategory.objects.create(name='Gomitas Test')

        cls.cash_method = PaymentMethod.objects.create(
            name='Efectivo Test', code='cash_test', is_active=True
        )
        cls.register = CashRegister.objects.create(
            name='Caja Granel Test', code='GRN01', is_active=True
        )
        cls.shift = CashShift.objects.create(
            cash_register=cls.register,
            cashier=cls.user,
            initial_amount=Decimal('10000'),
            status='open'
        )

    def _create_caramelera(self, nombre='Gomitas Surtidas',
                            precio_100g=Decimal('2500'),
                            precio_cuarto=Decimal('5500')):
        return Caramelera.objects.create(
            nombre=nombre,
            precio_100g=precio_100g,
            precio_cuarto=precio_cuarto,
        )


class AuditoriaTest(GranelBaseTestCase):
    """Test auditoría de caramelera."""

    def test_auditoria_merma(self):
        """Auditoría con peso real menor que sistema: merma positiva."""
        caramelera = self._create_caramelera()
        caramelera.stock_gramos_actual = Decimal('1000')
        caramelera.save()

        auditoria = GranelService.realizar_auditoria(
            caramelera.pk, Decimal('980'), self.user, motivo='picoteo'
        )

        self.assertEqual(auditoria.stock_sistema_gramos, Decimal('1000'))
        self.assertEqual(auditoria.peso_real_balanza_gramos, Decimal('980'))
        self.assertEqual(auditoria.diferencia_gramos, Decimal('20'))
        self.assertEqual(auditoria.porcentaje_merma, Decimal('2.00'))
        self.assertTrue(auditoria.ajuste_aplicado)

        caramelera.refresh_from_db()
        self.assertEqual(caramelera.stock_gramos_actual, Decimal('980'))

    def test_auditoria_sobrante(self):
        """Auditoría con peso real mayor que sistema: diferencia negativa."""
        caramelera = self._create_caramelera()
        caramelera.stock_gramos_actual = Decimal('500')
        caramelera.save()

        auditoria = GranelService.realizar_auditoria(
            caramelera.pk, Decimal('520'), self.user
        )

        self.assertEqual(auditoria.diferencia_gramos, Decimal('-20'))
        caramelera.refresh_from_db()
        self.assertEqual(caramelera.stock_gramos_actual, Decimal('520'))


class VentaGranelTest(GranelBaseTestCase):
    """Test registrar_venta."""

    def test_registrar_venta_descuenta_stock(self):
        """registrar_venta debería descontar gramos de la caramelera."""
        caramelera = self._create_caramelera()
        caramelera.stock_gramos_actual = Decimal('1000')
        caramelera.costo_ponderado_gramo = Decimal('5.000000')
        caramelera.save()

        venta = GranelService.registrar_venta(
            caramelera.pk, Decimal('200'), Decimal('5000')
        )

        caramelera.refresh_from_db()
        self.assertEqual(caramelera.stock_gramos_actual, Decimal('800'))
        self.assertEqual(venta.gramos_vendidos, Decimal('200'))
        self.assertEqual(venta.precio_cobrado, Decimal('5000'))
        self.assertEqual(venta.costo_total, Decimal('1000.00'))
        self.assertEqual(venta.ganancia, Decimal('4000.00'))

    def test_registrar_venta_sin_stock_raises(self):
        """registrar_venta con stock insuficiente debe lanzar ValueError."""
        caramelera = self._create_caramelera()
        caramelera.stock_gramos_actual = Decimal('100')
        caramelera.save()

        with self.assertRaises(ValueError):
            GranelService.registrar_venta(caramelera.pk, Decimal('500'), Decimal('5000'))

    def test_calcular_precio_libre(self):
        """calcular_precio para < 250g es proporcional a precio/100g."""
        caramelera = self._create_caramelera(precio_100g=Decimal('2500'))
        # 150g → (150/100) * 2500 = 3750
        self.assertEqual(caramelera.calcular_precio(150), Decimal('3750.0'))
        # 200g → (200/100) * 2500 = 5000
        self.assertEqual(caramelera.calcular_precio(200), Decimal('5000.0'))

    def test_calcular_precio_kilo_oferta(self):
        """calcular_precio para >= 250g usa precio por kilo (regla de tres)."""
        # precio_cuarto ahora almacena el precio por kilo oferta
        caramelera = self._create_caramelera(precio_100g=Decimal('2500'),
                                              precio_cuarto=Decimal('20000'))
        # 250g → (250/1000) * 20000 = 5000
        self.assertEqual(caramelera.calcular_precio(250), Decimal('5000.0'))
        # 300g → (300/1000) * 20000 = 6000
        self.assertEqual(caramelera.calcular_precio(300), Decimal('6000.0'))
        # 500g → (500/1000) * 20000 = 10000
        self.assertEqual(caramelera.calcular_precio(500), Decimal('10000.0'))
        # 1000g → (1000/1000) * 20000 = 20000
        self.assertEqual(caramelera.calcular_precio(1000), Decimal('20000.0'))

    def test_calcular_precio_bajo_250_ignora_kilo(self):
        """calcular_precio para < 250g siempre usa precio/100g, incluso con kilo oferta."""
        caramelera = self._create_caramelera(precio_100g=Decimal('2500'),
                                              precio_cuarto=Decimal('20000'))
        # 100g → (100/100) * 2500 = 2500 (NO usa kilo)
        self.assertEqual(caramelera.calcular_precio(100), Decimal('2500.0'))
        # 200g → (200/100) * 2500 = 5000 (NO usa kilo)
        self.assertEqual(caramelera.calcular_precio(200), Decimal('5000.0'))


class FIFOBatchTest(GranelBaseTestCase):
    """Test FIFO batch management (BatchService) — genérico, nunca dependió
    de la vinculación Product↔Caramelera."""

    def test_fifo_deduction_order(self):
        """Oldest batch should be deducted first."""
        from django.utils import timezone
        product = Product.objects.create(
            name='Batch Test',
            sku='BTEST001',
            sale_price=Decimal('100'),
            current_stock=Decimal('10'),
            category=self.category,
        )

        b1 = BatchService.create_batch(product.pk, 5, Decimal('100'),
                                        purchased_at=timezone.now() - timezone.timedelta(days=30))
        b2 = BatchService.create_batch(product.pk, 3, Decimal('120'),
                                        purchased_at=timezone.now() - timezone.timedelta(days=15))
        b3 = BatchService.create_batch(product.pk, 2, Decimal('150'),
                                        purchased_at=timezone.now())

        deductions = BatchService.deduct_fifo(product.pk, 6)

        self.assertEqual(len(deductions), 2)
        self.assertEqual(deductions[0][0].pk, b1.pk)
        self.assertEqual(deductions[0][1], Decimal('5'))
        self.assertEqual(deductions[1][0].pk, b2.pk)
        self.assertEqual(deductions[1][1], Decimal('1'))

        b1.refresh_from_db()
        b2.refresh_from_db()
        b3.refresh_from_db()
        self.assertEqual(b1.quantity_remaining, Decimal('0'))
        self.assertEqual(b2.quantity_remaining, Decimal('2'))
        self.assertEqual(b3.quantity_remaining, Decimal('2'))

    def test_fifo_cost_calculation(self):
        """FIFO cost should use batch-specific costs."""
        from django.utils import timezone
        product = Product.objects.create(
            name='Batch Cost Test',
            sku='BCTEST001',
            sale_price=Decimal('100'),
            current_stock=Decimal('10'),
            category=self.category,
        )

        BatchService.create_batch(product.pk, 5, Decimal('100'),
                                   purchased_at=timezone.now() - timezone.timedelta(days=10))
        BatchService.create_batch(product.pk, 5, Decimal('200'),
                                   purchased_at=timezone.now())

        cost = BatchService.get_fifo_cost(product.pk, 6)
        self.assertEqual(cost, Decimal('700.00'))
