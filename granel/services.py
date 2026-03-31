"""
Granel Services - Transfer, FIFO, weighted cost, shrinkage.
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone

from stocks.models import Product, StockMovement
from .models import StockBatch, BulkToGranelTransfer, ShrinkageAudit


class GranelService:
    """Service for bulk-to-granel operations and weighted average cost."""

    @staticmethod
    @transaction.atomic
    def transfer_bulk_to_granel(bulk_product_id, granel_product_id, user, notes=''):
        """
        Abre un bulto y transfiere su contenido al producto granel.
        - Resta 1 unidad del bulto (FIFO: del lote más antiguo)
        - Suma los gramos al producto granel
        - Recalcula el costo ponderado del granel
        """
        bulk = Product.objects.select_for_update().get(pk=bulk_product_id)
        granel = Product.objects.select_for_update().get(pk=granel_product_id)

        if not granel.is_granel:
            raise ValueError(f'{granel.name} no es un producto granel')
        if bulk.weight_per_unit_grams <= 0:
            raise ValueError(f'{bulk.name} no tiene peso por unidad configurado')
        if bulk.current_stock < 1:
            raise ValueError(f'No hay stock de {bulk.name} para transferir')

        grams = bulk.weight_per_unit_grams

        # FIFO: consume from oldest batch with remaining stock
        batch = (
            StockBatch.objects.select_for_update()
            .filter(product=bulk, quantity_remaining__gt=0)
            .order_by('purchased_at', 'created_at')
            .first()
        )

        if batch:
            cost_per_gram = batch.unit_cost / grams
            batch.quantity_remaining -= 1
            batch.save()
        else:
            # Fallback: use product cost_price if no batches exist
            cost_per_gram = bulk.cost_price / grams if grams > 0 else Decimal('0')

        # Snapshot before
        stock_before = granel.current_stock
        cost_before = granel.weighted_avg_cost_per_gram

        # Weighted average cost recalculation
        if stock_before > 0:
            total_value = (stock_before * cost_before) + (grams * cost_per_gram)
            new_avg = total_value / (stock_before + grams)
        else:
            new_avg = cost_per_gram

        # Update granel product
        granel.current_stock += grams
        granel.weighted_avg_cost_per_gram = new_avg
        # Update cost_price for display (cost per price_weight unit, e.g. per 100g)
        granel.cost_price = (new_avg * granel.granel_price_weight_grams).quantize(Decimal('0.01'))
        granel.save()

        # Deduct 1 unit from bulk
        bulk_stock_before = bulk.current_stock
        bulk.current_stock -= 1
        bulk.save()

        # Stock movements
        StockMovement.objects.create(
            product=bulk,
            movement_type='transfer_out',
            quantity=Decimal('-1'),
            unit_cost=batch.unit_cost if batch else bulk.cost_price,
            stock_before=bulk_stock_before,
            stock_after=bulk.current_stock,
            reference=f'Apertura bulto -> {granel.name}',
            notes=notes,
            created_by=user,
        )
        StockMovement.objects.create(
            product=granel,
            movement_type='transfer_in',
            quantity=grams,
            unit_cost=cost_per_gram,
            stock_before=stock_before,
            stock_after=granel.current_stock,
            reference=f'Recibe {grams}g de {bulk.name}',
            notes=notes,
            created_by=user,
        )

        # Transfer log
        transfer = BulkToGranelTransfer.objects.create(
            bulk_product=bulk,
            granel_product=granel,
            source_batch=batch,
            grams_transferred=grams,
            bulk_cost_per_gram=cost_per_gram,
            granel_stock_before=stock_before,
            granel_weighted_cost_before=cost_before,
            granel_stock_after=granel.current_stock,
            granel_weighted_cost_after=new_avg,
            transferred_by=user,
            notes=notes,
        )

        return transfer

    @staticmethod
    @transaction.atomic
    def perform_shrinkage_audit(granel_product_id, actual_grams, reason, notes, user, apply_adjustment=True):
        """
        Compara stock teórico vs peso real y registra la merma.
        """
        granel = Product.objects.select_for_update().get(pk=granel_product_id)
        actual_grams = Decimal(str(actual_grams))
        theoretical = granel.current_stock
        shrinkage = theoretical - actual_grams

        if theoretical > 0:
            shrinkage_pct = (shrinkage / theoretical * 100).quantize(Decimal('0.01'))
        else:
            shrinkage_pct = Decimal('0.00')

        audit = ShrinkageAudit.objects.create(
            granel_product=granel,
            theoretical_grams=theoretical,
            actual_grams=actual_grams,
            shrinkage_grams=shrinkage,
            shrinkage_percent=shrinkage_pct,
            reason=reason,
            notes=notes,
            audited_by=user,
            stock_adjusted=apply_adjustment,
        )

        if apply_adjustment and shrinkage != 0:
            movement_type = 'adjustment_out' if shrinkage > 0 else 'adjustment_in'
            StockMovement.objects.create(
                product=granel,
                movement_type=movement_type,
                quantity=-shrinkage,  # negative shrinkage = reduce stock
                unit_cost=granel.weighted_avg_cost_per_gram,
                stock_before=theoretical,
                stock_after=actual_grams,
                reference=f'Auditoría merma #{audit.pk}',
                notes=f'{audit.get_reason_display()}: {notes}',
                created_by=user,
            )
            granel.current_stock = actual_grams
            granel.save()

        return audit


class BatchService:
    """Service for FIFO stock batch management."""

    @staticmethod
    @transaction.atomic
    def create_batch(product_id, quantity, unit_cost, purchased_at=None,
                     supplier_name='', purchase=None, notes='', user=None):
        """Create a new stock batch (called when receiving merchandise)."""
        product = Product.objects.select_for_update().get(pk=product_id)
        if purchased_at is None:
            purchased_at = timezone.now()

        batch = StockBatch.objects.create(
            product=product,
            purchase=purchase,
            supplier_name=supplier_name,
            quantity_purchased=Decimal(str(quantity)),
            quantity_remaining=Decimal(str(quantity)),
            purchase_price=Decimal(str(unit_cost)),
            purchased_at=purchased_at,
            created_by=user,
            notes=notes,
        )
        return batch

    @staticmethod
    @transaction.atomic
    def deduct_fifo(product_id, quantity):
        """
        Deduct quantity using FIFO from available batches.
        Returns list of (batch, qty_deducted) tuples for margin reporting.
        """
        quantity = Decimal(str(quantity))
        remaining = quantity
        deductions = []

        batches = (
            StockBatch.objects.select_for_update()
            .filter(product_id=product_id, quantity_remaining__gt=0)
            .order_by('purchased_at', 'created_at')
        )

        for batch in batches:
            if remaining <= 0:
                break
            take = min(batch.quantity_remaining, remaining)
            batch.quantity_remaining -= take
            batch.save()
            deductions.append((batch, take))
            remaining -= take

        return deductions

    @staticmethod
    def get_fifo_cost(product_id, quantity):
        """
        Calculate the exact cost of selling `quantity` units using FIFO,
        without actually deducting. Useful for margin preview.
        """
        quantity = Decimal(str(quantity))
        remaining = quantity
        total_cost = Decimal('0.00')

        batches = (
            StockBatch.objects
            .filter(product_id=product_id, quantity_remaining__gt=0)
            .order_by('purchased_at', 'created_at')
        )

        for batch in batches:
            if remaining <= 0:
                break
            take = min(batch.quantity_remaining, remaining)
            total_cost += take * batch.unit_cost
            remaining -= take

        return total_cost

    @staticmethod
    def get_batch_summary(product_id):
        """Get summary of all active batches for a product."""
        batches = (
            StockBatch.objects
            .filter(product_id=product_id, quantity_remaining__gt=0)
            .order_by('purchased_at', 'created_at')
        )
        return batches
