"""
Fiado - vistas (pantallas de clientes/cuenta corriente y API para el POS).
"""
import json
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import DecimalField, F, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from cashregister.models import PaymentMethod
from decorators.decorators import group_required

from .models import Customer, FiadoEntry
from .services import FiadoService

ALL_ROLES = ['Admin', 'Cajero Manager', 'Cashier']
MANAGER_ROLES = ['Admin', 'Cajero Manager']

ZERO = Value(Decimal('0.00'), output_field=DecimalField(max_digits=12, decimal_places=2))


def _with_balance(queryset):
    """Anota cada cliente con su saldo (cargos - pagos, sin anulados)."""
    money = DecimalField(max_digits=12, decimal_places=2)
    live = Q(entries__voided_at__isnull=True)
    return queryset.annotate(
        _charges=Coalesce(
            Sum('entries__amount', filter=live & Q(entries__entry_type=FiadoEntry.CHARGE)),
            ZERO, output_field=money),
        _payments=Coalesce(
            Sum('entries__amount', filter=live & Q(entries__entry_type=FiadoEntry.PAYMENT)),
            ZERO, output_field=money),
    ).annotate(balance_db=F('_charges') - F('_payments'))


# ─────────────────────────────────────────────────────────────
#  Pantallas
# ─────────────────────────────────────────────────────────────

@login_required
@group_required(ALL_ROLES)
def customer_list(request):
    q = request.GET.get('q', '').strip()
    only_debt = request.GET.get('deuda') == '1'
    show_inactive = request.GET.get('inactivos') == '1'

    customers = _with_balance(Customer.objects.all())
    if not show_inactive:
        customers = customers.filter(is_active=True)
    if q:
        customers = customers.filter(Q(name__icontains=q) | Q(phone__icontains=q))
    if only_debt:
        customers = customers.filter(balance_db__gt=0)
    customers = customers.order_by('-balance_db', 'name')

    total_owed = _with_balance(Customer.objects.filter(is_active=True)).filter(
        balance_db__gt=0
    ).aggregate(t=Sum('balance_db'))['t'] or Decimal('0.00')

    today = timezone.localdate()
    collected_today = FiadoEntry.objects.filter(
        entry_type=FiadoEntry.PAYMENT,
        voided_at__isnull=True,
        created_at__date=today,
    ).aggregate(t=Sum('amount'))['t'] or Decimal('0.00')

    return render(request, 'fiado/customer_list.html', {
        'customers': customers,
        'q': q,
        'only_debt': only_debt,
        'show_inactive': show_inactive,
        'total_owed': total_owed,
        'collected_today': collected_today,
        'can_manage': _is_manager(request.user),
    })


@login_required
@group_required(ALL_ROLES)
def customer_create(request):
    if request.method == 'POST':
        ok, result = FiadoService.create_customer(
            request.POST.get('name'), request.POST.get('phone'), request.POST.get('notes')
        )
        if ok:
            customer = result['customer']
            opening = request.POST.get('opening_balance', '').strip()
            if opening:
                ok2, res2 = FiadoService.add_manual_charge(
                    customer.pk, opening, request.user, 'Saldo anterior'
                )
                if not ok2:
                    messages.warning(request, f'Cliente creado, pero el saldo anterior no se cargó: {res2["error"]}')
            messages.success(request, f'Cliente "{customer.name}" creado.')
            return redirect('fiado:customer_detail', pk=customer.pk)
        messages.error(request, result['error'])
    return render(request, 'fiado/customer_form.html', {
        'customer': None,
        'form_data': request.POST if request.method == 'POST' else {},
    })


@login_required
@group_required(ALL_ROLES)
def customer_edit(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        if not name:
            messages.error(request, 'El nombre es obligatorio.')
        elif Customer.objects.filter(name__iexact=name, is_active=True).exclude(pk=pk).exists():
            messages.error(request, 'Ya existe otro cliente con ese nombre.')
        else:
            customer.name = name
            customer.phone = request.POST.get('phone', '').strip()
            customer.notes = request.POST.get('notes', '').strip()
            customer.save()
            messages.success(request, 'Datos del cliente actualizados.')
            return redirect('fiado:customer_detail', pk=pk)
    return render(request, 'fiado/customer_form.html', {
        'customer': customer,
        'form_data': request.POST if request.method == 'POST' else {},
    })


@login_required
@group_required(ALL_ROLES)
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    entries = customer.entries.select_related(
        'payment_method', 'created_by', 'voided_by', 'pos_transaction'
    ).all()
    return render(request, 'fiado/customer_detail.html', {
        'customer': customer,
        'balance': customer.balance,
        'entries': entries,
        'payment_methods': PaymentMethod.objects.filter(is_active=True),
        'can_manage': _is_manager(request.user),
    })


@login_required
@group_required(ALL_ROLES)
@require_POST
def payment_create(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    ok, result = FiadoService.register_payment(
        customer.pk,
        request.POST.get('amount'),
        request.POST.get('method_id'),
        request.user,
        request.POST.get('note', ''),
    )
    if ok:
        msg = f'Pago de ${result["entry"].amount} registrado. Saldo: ${result["balance"]}.'
        if not result['in_cash_register']:
            msg += ' (No tenés un turno de caja abierto: no se sumó a la caja.)'
        messages.success(request, msg)
    else:
        messages.error(request, result['error'])
    return redirect('fiado:customer_detail', pk=pk)


@login_required
@group_required(ALL_ROLES)
@require_POST
def charge_create(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    ok, result = FiadoService.add_manual_charge(
        customer.pk, request.POST.get('amount'), request.user, request.POST.get('note', '')
    )
    if ok:
        messages.success(request, f'Deuda de ${result["entry"].amount} sumada. Saldo: ${result["balance"]}.')
    else:
        messages.error(request, result['error'])
    return redirect('fiado:customer_detail', pk=pk)


@login_required
@group_required(MANAGER_ROLES)
@require_POST
def entry_void(request, pk):
    entry = get_object_or_404(FiadoEntry, pk=pk)
    ok, result = FiadoService.void_entry(entry.pk, request.user, request.POST.get('reason', ''))
    if ok:
        messages.success(request, f'Movimiento anulado. Saldo: ${result["balance"]}.')
    else:
        messages.error(request, result['error'])
    return redirect('fiado:customer_detail', pk=entry.customer_id)


@login_required
@group_required(MANAGER_ROLES)
@require_POST
def customer_toggle_active(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if customer.is_active and customer.balance > 0:
        messages.error(request, 'No se puede desactivar un cliente que todavía debe plata.')
    else:
        customer.is_active = not customer.is_active
        customer.save(update_fields=['is_active'])
        messages.success(
            request,
            f'Cliente {"activado" if customer.is_active else "desactivado"}.'
        )
    return redirect('fiado:customer_detail', pk=pk)


def _is_manager(user):
    return (
        user.is_superuser
        or user.groups.filter(name__in=['Admin', 'Cajero Manager', 'Manager',
                                        'Stock Manager', 'General Manager']).exists()
    )


# ─────────────────────────────────────────────────────────────
#  API para el POS
# ─────────────────────────────────────────────────────────────

def _json_body(request):
    try:
        return json.loads(request.body or b'{}')
    except json.JSONDecodeError:
        return None


@login_required
@group_required(ALL_ROLES)
@require_GET
def api_customers(request):
    q = request.GET.get('q', '').strip()
    customers = _with_balance(Customer.objects.filter(is_active=True))
    if q:
        customers = customers.filter(Q(name__icontains=q) | Q(phone__icontains=q))
    customers = customers.order_by('name')[:30]
    return JsonResponse({
        'success': True,
        'customers': [
            {'id': c.id, 'name': c.name, 'phone': c.phone, 'balance': float(c.balance_db)}
            for c in customers
        ],
    })


@login_required
@group_required(ALL_ROLES)
@require_POST
def api_customer_create(request):
    data = _json_body(request)
    if data is None:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    ok, result = FiadoService.create_customer(data.get('name'), data.get('phone', ''))
    if not ok:
        return JsonResponse({'success': False, **result}, status=400)
    c = result['customer']
    return JsonResponse({
        'success': True,
        'customer': {'id': c.id, 'name': c.name, 'phone': c.phone, 'balance': 0.0},
    })


@login_required
@group_required(ALL_ROLES)
@require_POST
def api_charge_sale(request):
    """Pasa el carrito actual a la cuenta de un cliente (fiado)."""
    data = _json_body(request)
    if data is None:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    transaction_id = data.get('transaction_id')
    customer_id = data.get('customer_id')
    if not transaction_id or not customer_id:
        return JsonResponse({'success': False, 'error': 'Datos incompletos'}, status=400)
    ok, result = FiadoService.charge_sale(
        transaction_id, customer_id, request.user, data.get('note', '')
    )
    if ok:
        return JsonResponse(result)
    return JsonResponse({'success': False, **result}, status=400)
