"""
Tests for the Granel (Caramelera) system:
- Weighted average cost
- Bulk-to-granel transfers
- FIFO batch management
- Shrinkage audits
- POS integration with decimal quantities
"""
from decimal import Decimal
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from stocks.models import Product, ProductCategory, StockMovement
from stocks.services import StockManagementService
from pos.models import POSSession, POSTransaction, POSTransactionItem
from pos.services import CartService, CheckoutService, POSService
from cashregister.models import PaymentMethod, CashRegister, CashShift
from granel.models import StockBatch, BulkToGranelTransfer, ShrinkageAudit
from granel.services import GranelService, BatchService

User = get_user_model()


class GranelBaseTestCase(TestCase):
    """Base test case with common setup for granel tests."""

    @classmethod
    def setUpTestData(cls):
        # User
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user(
            username='testgranel', password='testpass123',
            first_name='Test', last_name='User'
        )
        cls.user.groups.add(cls.admin_group)

        # Category
        cls.category = ProductCategory.objects.create(name='Gomitas')

        # Payment method
        cls.cash_method = PaymentMethod.objects.create(
            name='Efectivo', code='cash', is_active=True
        )

        # Cash register + shift
        cls.register = CashRegister.objects.create(
            name='Caja Test', code='TEST01', is_active=True
        )
        cls.shift = CashShift.objects.create(
            cash_register=cls.register,
            cashier=cls.user,
            initial_amount=Decimal('10000'),
            status='open'
        )

    def _create_granel_product(self, name='Gomitas Surtidas', sale_price=Decimal('2500'),
                                price_weight=100):
        """Create a granel (wildcard) product."""
        return Product.objects.create(
            name=name,
            sku=f'GRN-{Product.objects.count()+1:04d}',
            sale_price=sale_price,
            is_bulk=True,
            bulk_unit='g',
            is_granel=True,
            granel_price_weight_grams=price_weight,
            current_stock=Decimal('0'),
            weighted_avg_cost_per_gram=Decimal('0'),
            category=self.category,
        )

    def _create_bulk_product(self, name, cost_price, weight_grams, stock=10):
        """Create a bulk (sealed bag) product."""
        return Product.objects.create(
            name=name,
            sku=f'BLK-{Product.objects.count()+1:04d}',
            sale_price=cost_price,  # not sold directly
            cost_price=cost_price,
            purchase_price=cost_price,
            weight_per_unit_grams=Decimal(str(weight_grams)),
            current_stock=Decimal(str(stock)),
            category=self.category,
        )


class WeightedAverageCostTest(GranelBaseTestCase):
    """Test weighted average cost calculation."""

    def test_single_transfer_to_empty_granel(self):
        """First transfer to empty granel: cost = bulk cost/gram."""
        granel = self._create_granel_product()
        bulk = self._create_bulk_product('Ositos 2kg', Decimal('10000'), 2000)

        # Ositos 2kg at $10000 → $5.0000/g
        transfer = GranelService.transfer_bulk_to_granel(
            bulk.pk, granel.pk, self.user
        )

        granel.refresh_from_db()
        self.assertEqual(granel.current_stock, Decimal('2000'))
        self.assertEqual(granel.weighted_avg_cost_per_gram, Decimal('5.0000'))
        self.assertEqual(transfer.grams_transferred, Decimal('2000'))

    def test_two_transfers_weighted_average(self):
        """Two transfers with different costs: proper weighted average."""
        granel = self._create_granel_product()

        bulk1 = self._create_bulk_product('Mogul 1kg', Decimal('5000'), 1000)
        bulk2 = self._create_bulk_product('Haribo 500g', Decimal('4000'), 500)

        # Transfer 1: 1000g at $5/g → avg = $5.0000
        GranelService.transfer_bulk_to_granel(bulk1.pk, granel.pk, self.user)
        granel.refresh_from_db()
        self.assertEqual(granel.weighted_avg_cost_per_gram, Decimal('5.0000'))

        # Transfer 2: 500g at $8/g → avg = (1000*5 + 500*8) / 1500 = 9000/1500 = $6.0000
        GranelService.transfer_bulk_to_granel(bulk2.pk, granel.pk, self.user)
        granel.refresh_from_db()
        self.assertEqual(granel.current_stock, Decimal('1500'))
        self.assertEqual(granel.weighted_avg_cost_per_gram, Decimal('6.0000'))

    def test_cost_price_updated_for_display(self):
        """cost_price should reflect weighted_avg * price_weight_grams."""
        granel = self._create_granel_product(price_weight=100)
        bulk = self._create_bulk_product('Test 1kg', Decimal('5000'), 1000)

        GranelService.transfer_bulk_to_granel(bulk.pk, granel.pk, self.user)
        granel.refresh_from_db()

        # $5.0000/g * 100g = $500.00 cost per 100g
        self.assertEqual(granel.cost_price, Decimal('500.00'))


class TransferValidationTest(GranelBaseTestCase):
    """Test transfer validations."""

    def test_transfer_deducts_bulk_stock(self):
        """Transfer should deduct 1 unit from bulk product."""
        granel = self._create_granel_product()
        bulk = self._create_bulk_product('Test 1kg', Decimal('5000'), 1000, stock=3)

        GranelService.transfer_bulk_to_granel(bulk.pk, granel.pk, self.user)
        bulk.refresh_from_db()
        self.assertEqual(bulk.current_stock, Decimal('2'))

    def test_transfer_no_stock_raises(self):
        """Transfer with no bulk stock should raise ValueError."""
        granel = self._create_granel_product()
        bulk = self._create_bulk_product('Empty', Decimal('5000'), 1000, stock=0)

        with self.assertRaises(ValueError):
            GranelService.transfer_bulk_to_granel(bulk.pk, granel.pk, self.user)

    def test_transfer_creates_stock_movements(self):
        """Transfer should create transfer_out and transfer_in movements."""
        granel = self._create_granel_product()
        bulk = self._create_bulk_product('Test 1kg', Decimal('5000'), 1000)

        GranelService.transfer_bulk_to_granel(bulk.pk, granel.pk, self.user)

        out_movement = StockMovement.objects.filter(
            product=bulk, movement_type='transfer_out'
        ).first()
        in_movement = StockMovement.objects.filter(
            product=granel, movement_type='transfer_in'
        ).first()

        self.assertIsNotNone(out_movement)
        self.assertIsNotNone(in_movement)
        self.assertEqual(out_movement.quantity, Decimal('-1'))
        self.assertEqual(in_movement.quantity, Decimal('1000'))


class FIFOBatchTest(GranelBaseTestCase):
    """Test FIFO batch management."""

    def test_fifo_deduction_order(self):
        """Oldest batch should be deducted first."""
        product = self._create_bulk_product('Test', Decimal('100'), 1000, stock=10)

        # Create 3 batches at different times/costs
        b1 = BatchService.create_batch(product.pk, 5, Decimal('100'),
                                        purchased_at=timezone.now() - timezone.timedelta(days=30),
                                        supplier_name='Proveedor A')
        b2 = BatchService.create_batch(product.pk, 3, Decimal('120'),
                                        purchased_at=timezone.now() - timezone.timedelta(days=15),
                                        supplier_name='Proveedor B')
        b3 = BatchService.create_batch(product.pk, 2, Decimal('150'),
                                        purchased_at=timezone.now(),
                                        supplier_name='Proveedor C')

        # Deduct 6 units → should take 5 from b1 + 1 from b2
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
        product = self._create_bulk_product('Test', Decimal('100'), 1000, stock=10)

        BatchService.create_batch(product.pk, 5, Decimal('100'),
                                   purchased_at=timezone.now() - timezone.timedelta(days=10))
        BatchService.create_batch(product.pk, 5, Decimal('200'),
                                   purchased_at=timezone.now())

        # Cost of 6 units: 5*100 + 1*200 = 700
        cost = BatchService.get_fifo_cost(product.pk, 6)
        self.assertEqual(cost, Decimal('700.00'))

    def test_transfer_uses_fifo_batch(self):
        """Granel transfer should use FIFO batch cost."""
        granel = self._create_granel_product()
        bulk = self._create_bulk_product('Test 1kg', Decimal('5000'), 1000, stock=5)

        # Create cheap old batch and expensive new batch
        b_old = BatchService.create_batch(bulk.pk, 3, Decimal('4000'),
                                           purchased_at=timezone.now() - timezone.timedelta(days=30))
        b_new = BatchService.create_batch(bulk.pk, 2, Decimal('6000'),
                                           purchased_at=timezone.now())

        transfer = GranelService.transfer_bulk_to_granel(bulk.pk, granel.pk, self.user)

        # Should use old batch ($4000/1000g = $4/g)
        self.assertEqual(transfer.source_batch.pk, b_old.pk)
        self.assertEqual(transfer.bulk_cost_per_gram, Decimal('4.0000'))

        b_old.refresh_from_db()
        self.assertEqual(b_old.quantity_remaining, Decimal('2'))


class ShrinkageAuditTest(GranelBaseTestCase):
    """Test shrinkage audit."""

    def test_shrinkage_detection(self):
        """Audit should correctly detect and record shrinkage."""
        granel = self._create_granel_product()
        bulk = self._create_bulk_product('Test 1kg', Decimal('5000'), 1000)
        GranelService.transfer_bulk_to_granel(bulk.pk, granel.pk, self.user)

        granel.refresh_from_db()
        self.assertEqual(granel.current_stock, Decimal('1000'))

        # Actual weight is 980g → 20g shrinkage
        audit = GranelService.perform_shrinkage_audit(
            granel.pk, actual_grams=980, reason='picoteo',
            notes='Control mensual', user=self.user
        )

        self.assertEqual(audit.theoretical_grams, Decimal('1000'))
        self.assertEqual(audit.actual_grams, Decimal('980'))
        self.assertEqual(audit.shrinkage_grams, Decimal('20'))
        self.assertEqual(audit.shrinkage_percent, Decimal('2.00'))
        self.assertTrue(audit.stock_adjusted)

        granel.refresh_from_db()
        self.assertEqual(granel.current_stock, Decimal('980'))

    def test_surplus_detection(self):
        """Audit with more actual weight than theoretical (surplus)."""
        granel = self._create_granel_product()
        granel.current_stock = Decimal('500')
        granel.save()

        audit = GranelService.perform_shrinkage_audit(
            granel.pk, actual_grams=520, reason='pesaje',
            notes='Sobrante', user=self.user
        )

        self.assertEqual(audit.shrinkage_grams, Decimal('-20'))
        granel.refresh_from_db()
        self.assertEqual(granel.current_stock, Decimal('520'))


class POSDecimalQuantityTest(GranelBaseTestCase):
    """Test that POS handles decimal quantities correctly."""

    def test_add_decimal_quantity_to_cart(self):
        """Granel product with decimal quantity in cart."""
        granel = self._create_granel_product(sale_price=Decimal('2500'))
        granel.current_stock = Decimal('5000')
        granel.save()

        session = POSService.get_or_create_session(self.shift)
        txn = POSService.create_transaction(session)

        # Add 150.5 grams
        item, msg = CartService.add_item(txn, granel.pk, quantity=Decimal('150.5'))
        self.assertIsNotNone(item)
        self.assertEqual(item.quantity, Decimal('150.500'))

    def test_checkout_deducts_granel_stock(self):
        """Checkout should deduct grams from granel, not from sealed bags."""
        granel = self._create_granel_product(sale_price=Decimal('2500'))
        granel.current_stock = Decimal('5000')
        granel.weighted_avg_cost_per_gram = Decimal('5.0000')
        granel.cost_price = Decimal('500.00')
        granel.save()

        bulk = self._create_bulk_product('Sealed Bag', Decimal('5000'), 1000, stock=5)

        session = POSService.get_or_create_session(self.shift)
        txn = POSService.create_transaction(session)
        CartService.add_item(txn, granel.pk, quantity=Decimal('200'))
        txn.refresh_from_db()

        success, result = CheckoutService.process_payment(
            txn.pk, [{'method_code': 'cash', 'amount': str(txn.total)}]
        )
        self.assertTrue(success)

        granel.refresh_from_db()
        bulk.refresh_from_db()
        # Granel should be 5000 - 200 = 4800g
        self.assertEqual(granel.current_stock, Decimal('4800'))
        # Sealed bags should be unchanged
        self.assertEqual(bulk.current_stock, Decimal('5'))

    def test_unit_cost_snapshot_at_sale(self):
        """POS item should capture granel weighted_avg cost at time of sale."""
        granel = self._create_granel_product(sale_price=Decimal('2500'))
        granel.current_stock = Decimal('1000')
        granel.weighted_avg_cost_per_gram = Decimal('5.0000')
        granel.cost_price = Decimal('500.00')
        granel.save()

        session = POSService.get_or_create_session(self.shift)
        txn = POSService.create_transaction(session)
        item, _ = CartService.add_item(txn, granel.pk, quantity=Decimal('100'))

        # unit_cost should be the cost_price ($500/100g)
        self.assertEqual(item.unit_cost, Decimal('500.00'))
