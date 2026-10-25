"""
Fiado - lógica de negocio.

Todas las operaciones devuelven (ok, dict). En caso de error el dict trae
'error' con un mensaje listo para mostrar.
"""
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from .models import Customer, FiadoEntry

CENT = Decimal('0.01')


def parse_amount(value):
    """Convierte lo que llega del formulario a Decimal con 2 decimales, o None."""
    if value is None:
        return None
    text = str(value).strip().replace('$', '').replace(' ', '')
    if not text:
        return None
    # "1.234,56" (formato AR) -> "1234.56"; "250.50" se respeta tal cual.
    if ',' in text:
        text = text.replace('.', '').replace(',', '.')
    try:
        amount = Decimal(text)
    except InvalidOperation:
        return None
    if not amount.is_finite():
        return None
    return amount.quantize(CENT)


class FiadoService:

    # ── Clientes ────────────────────────────────────────────────────────
    @staticmethod
    def create_customer(name, phone='', notes=''):
        name = (name or '').strip()
        if not name:
            return False, {'error': 'El nombre es obligatorio'}
        if Customer.objects.filter(name__iexact=name, is_active=True).exists():
            return False, {
                'error': 'Ya existe un cliente con ese nombre. '
                         'Agregale un apellido o un dato para distinguirlos.'
            }
        customer = Customer.objects.create(
            name=name, phone=(phone or '').strip(), notes=(notes or '').strip()
        )
        return True, {'customer': customer}

    # ── Fiar una venta del POS ──────────────────────────────────────────
    @staticmethod
    def charge_sale(transaction_id, customer_id, user, note=''):
        """Pasa el carrito pendiente a la cuenta del cliente.

        La mercadería sale (se descuenta stock) pero la venta queda en estado
        'on_credit': no es 'completed', así que no suma a ventas del día ni a
        ningún reporte, y no entra plata a la caja.
        """
        from pos.models import POSTransaction
        from pos.services import CheckoutService

        try:
            with transaction.atomic():
                try:
                    pos_tx = POSTransaction.objects.select_for_update().get(
                        id=transaction_id, status='pending'
                    )
                except POSTransaction.DoesNotExist:
                    return False, {'error': 'Venta no encontrada o ya procesada'}

                try:
                    customer = Customer.objects.select_for_update().get(
                        id=customer_id, is_active=True
                    )
                except (Customer.DoesNotExist, ValueError, TypeError):
                    return False, {'error': 'Cliente no encontrado'}

                if not pos_tx.items.exists() or pos_tx.total <= 0:
                    return False, {'error': 'El carrito está vacío'}

                CheckoutService.deduct_stock_for_transaction(pos_tx, label='Fiado')

                pos_tx.status = 'on_credit'
                pos_tx.completed_at = timezone.now()
                pos_tx.amount_paid = Decimal('0.00')
                pos_tx.change_given = Decimal('0.00')
                extra = f'Fiado a {customer.name}'
                pos_tx.notes = f'{pos_tx.notes}\n{extra}'.strip() if pos_tx.notes else extra
                pos_tx.save()

                FiadoEntry.objects.create(
                    customer=customer,
                    entry_type=FiadoEntry.CHARGE,
                    amount=pos_tx.total,
                    note=(note or '').strip()[:200],
                    pos_transaction=pos_tx,
                    ticket_number=pos_tx.ticket_number,
                    created_by=user,
                )
                balance = customer.balance
        except ValueError as e:
            # Stock insuficiente u otro error de negocio: la transacción
            # atómica ya revirtió todo, incluido el stock descontado.
            return False, {'error': str(e)}

        return True, {
            'success': True,
            'transaction_id': pos_tx.id,
            'ticket_number': pos_tx.ticket_number,
            'total': float(pos_tx.total),
            'customer_id': customer.id,
            'customer_name': customer.name,
            'balance': float(balance),
        }

    # ── Deuda cargada a mano (saldo anterior) ───────────────────────────
    @staticmethod
    def add_manual_charge(customer_id, amount, user, note=''):
        amount = parse_amount(amount)
        if amount is None or amount <= 0:
            return False, {'error': 'Ingresá un monto válido mayor a cero'}
        with transaction.atomic():
            try:
                customer = Customer.objects.select_for_update().get(id=customer_id)
            except Customer.DoesNotExist:
                return False, {'error': 'Cliente no encontrado'}
            entry = FiadoEntry.objects.create(
                customer=customer,
                entry_type=FiadoEntry.CHARGE,
                amount=amount,
                note=(note or '').strip()[:200] or 'Deuda cargada manualmente',
                created_by=user,
            )
            return True, {'entry': entry, 'balance': customer.balance}

    # ── Pago del cliente ────────────────────────────────────────────────
    @staticmethod
    def register_payment(customer_id, amount, method_id, user, note=''):
        """Descuenta un pago (total o parcial) de la cuenta.

        Si el usuario tiene un turno abierto, la plata entra a la caja como
        CashMovement marcado is_fiado_payment: suma al efectivo del cajón (el
        arqueo cierra bien) pero NO cuenta como venta del día.
        """
        from cashregister.models import CashMovement, CashShift, PaymentMethod

        amount = parse_amount(amount)
        if amount is None or amount <= 0:
            return False, {'error': 'Ingresá un monto válido mayor a cero'}

        with transaction.atomic():
            try:
                customer = Customer.objects.select_for_update().get(id=customer_id)
            except Customer.DoesNotExist:
                return False, {'error': 'Cliente no encontrado'}

            try:
                method = PaymentMethod.objects.get(id=method_id, is_active=True)
            except (PaymentMethod.DoesNotExist, ValueError, TypeError):
                return False, {'error': 'Elegí cómo pagó el cliente'}

            balance = customer.balance
            if balance <= 0:
                return False, {'error': 'Este cliente no tiene deuda'}
            if amount > balance:
                return False, {
                    'error': f'El pago (${amount}) es mayor a la deuda (${balance}). '
                             f'Cobrá como máximo ${balance}.'
                }

            shift = CashShift.objects.filter(cashier=user, status='open').first()

            entry = FiadoEntry.objects.create(
                customer=customer,
                entry_type=FiadoEntry.PAYMENT,
                amount=amount,
                note=(note or '').strip()[:200],
                payment_method=method,
                cash_shift=shift,
                created_by=user,
            )
            if shift:
                movement = CashMovement.objects.create(
                    cash_shift=shift,
                    movement_type='income',
                    amount=amount,
                    payment_method=method,
                    description=f'Cobro fiado - {customer.name}',
                    reference=f'FIADO-{entry.pk}',
                    created_by=user,
                    is_fiado_payment=True,
                )
                entry.cash_movement = movement
                entry.save(update_fields=['cash_movement'])

            return True, {
                'entry': entry,
                'balance': customer.balance,
                'in_cash_register': shift is not None,
            }

    # ── Anular ──────────────────────────────────────────────────────────
    @staticmethod
    def void_entry(entry_id, user, reason=''):
        """Anula un pago o una deuda manual (no una venta con productos)."""
        with transaction.atomic():
            try:
                entry = FiadoEntry.objects.select_for_update().select_related(
                    'cash_movement', 'cash_shift', 'customer'
                ).get(id=entry_id)
            except FiadoEntry.DoesNotExist:
                return False, {'error': 'Movimiento no encontrado'}

            if entry.is_voided:
                return False, {'error': 'Este movimiento ya está anulado'}
            if not entry.can_void:
                return False, {
                    'error': 'Una venta con productos no se puede anular desde acá '
                             '(el stock ya salió).'
                }

            customer = Customer.objects.select_for_update().get(pk=entry.customer_id)

            if entry.entry_type == FiadoEntry.PAYMENT:
                shift = entry.cash_shift
                if entry.cash_movement_id and shift and shift.status == 'closed':
                    return False, {
                        'error': 'El turno donde se cobró ya está cerrado. Para corregirlo '
                                 'sumá una deuda manual por el mismo monto.'
                    }
                if entry.cash_movement_id:
                    movement = entry.cash_movement
                    entry.cash_movement = None
                    entry.save(update_fields=['cash_movement'])
                    movement.delete()
            else:
                # Anular una deuda no puede dejar la cuenta con saldo a favor
                if customer.balance - entry.amount < 0:
                    return False, {
                        'error': 'No se puede anular: el cliente ya pagó parte de esta '
                                 'deuda. Anulá primero los pagos.'
                    }

            entry.voided_at = timezone.now()
            entry.voided_by = user
            entry.void_reason = (reason or '').strip()[:200]
            entry.save(update_fields=['voided_at', 'voided_by', 'void_reason'])
            return True, {'entry': entry, 'balance': customer.balance}
