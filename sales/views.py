"""
Sales Views - Reports and Analytics
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Avg, F
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal

from .models import Sale
from pos.models import POSTransaction, POSTransactionItem, POSSession, POSPayment
from cashregister.models import CashShift, PaymentMethod
from stocks.models import Product, ProductCategory
from decorators.decorators import group_required


@login_required
@group_required(['Admin', 'Manager'])
def reports_dashboard(request):
    """Reports dashboard with overview."""
    today = timezone.localdate()
    month_start = today.replace(day=1)
    
    # Today stats
    today_transactions = POSTransaction.objects.filter(
        created_at__date=today,
        status='completed'
    )
    today_sales = today_transactions.aggregate(total=Sum('total'))['total'] or Decimal('0')
    today_count = today_transactions.count()
    
    # Month stats
    month_transactions = POSTransaction.objects.filter(
        created_at__date__gte=month_start,
        status='completed'
    )
    month_sales = month_transactions.aggregate(total=Sum('total'))['total'] or Decimal('0')
    month_count = month_transactions.count()
    
    # Top products today - using subtotal instead of total
    top_products = POSTransactionItem.objects.filter(
        transaction__created_at__date=today,
        transaction__status='completed'
    ).values('product__name').annotate(
        total_qty=Sum('quantity'),
        total_amount=Sum('subtotal')
    ).order_by('-total_amount')[:5]
    
    # Recent transactions - using cashier instead of opened_by
    recent_transactions = POSTransaction.objects.filter(
        status='completed'
    ).select_related('session__cash_shift__cash_register', 'session__cash_shift__cashier').order_by('-created_at')[:10]
    
    # Sales by payment method today - AHORA FUNCIONAL
    payment_stats = POSPayment.objects.filter(
        transaction__created_at__date=today,
        transaction__status='completed'
    ).values(
        'payment_method__name',
        'payment_method__icon',
        'payment_method__color'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    context = {
        'today_sales': today_sales,
        'today_count': today_count,
        'month_sales': month_sales,
        'month_count': month_count,
        'top_products': top_products,
        'recent_transactions': recent_transactions,
        'payment_stats': payment_stats,
        'today': today,
    }
    return render(request, 'sales/reports_dashboard.html', context)


@login_required
def sale_list(request):
    """List sales/transactions."""
    transactions = POSTransaction.objects.filter(
        status='completed'
    ).select_related('session__cash_shift__cash_register', 'session__cash_shift__cashier').order_by('-created_at')
    
    # Filters
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from:
        transactions = transactions.filter(created_at__date__gte=date_from)
    if date_to:
        transactions = transactions.filter(created_at__date__lte=date_to)
    
    total = transactions.aggregate(total=Sum('total'))['total'] or Decimal('0')
    
    context = {
        'transactions': transactions[:100],
        'total': total,
        'count': transactions.count(),
        'date_from': date_from,
        'date_to': date_to,
    }
    return render(request, 'sales/sale_list.html', context)


@login_required
@group_required(['Admin', 'Manager'])
def daily_report(request):
    """Daily sales report."""
    date = request.GET.get('date', '')
    if date:
        report_date = datetime.strptime(date, '%Y-%m-%d').date()
    else:
        report_date = timezone.localdate()
    
    transactions = POSTransaction.objects.filter(
        created_at__date=report_date,
        status='completed'
    ).select_related('session__cash_shift__cash_register', 'session__cash_shift__cashier')
    
    # Stats
    stats = transactions.aggregate(
        total=Sum('total'),
        count=Count('id'),
        avg=Avg('total'),
        discount=Sum('discount_total')
    )
    
    # By cashier (through session)
    by_cashier = transactions.values(
        'session__cash_shift__cashier__username',
        'session__cash_shift__cashier__first_name',
        'session__cash_shift__cashier__last_name'
    ).annotate(
        total=Sum('total'),
        count=Count('id')
    )
    
    # By hour
    by_hour = transactions.extra(
        select={'hour': "strftime('%%H', created_at)"}
    ).values('hour').annotate(
        total=Sum('total'),
        count=Count('id')
    ).order_by('hour')
    
    # By payment method
    by_payment = POSPayment.objects.filter(
        transaction__created_at__date=report_date,
        transaction__status='completed'
    ).values(
        'payment_method__name',
        'payment_method__icon',
        'payment_method__color'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    context = {
        'report_date': report_date,
        'transactions': transactions,
        'stats': stats,
        'by_cashier': by_cashier,
        'by_hour': by_hour,
        'by_payment': by_payment,
    }
    return render(request, 'sales/daily_report.html', context)


@login_required
@group_required(['Admin', 'Manager'])
def period_report(request):
    """Period sales report."""
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from:
        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
    else:
        start_date = timezone.localdate() - timedelta(days=30)
    
    if date_to:
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    else:
        end_date = timezone.localdate()
    
    transactions = POSTransaction.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        status='completed'
    )
    
    # Stats
    stats = transactions.aggregate(
        total=Sum('total'),
        count=Count('id'),
        avg=Avg('total'),
        discount=Sum('discount_total')
    )
    
    # Daily breakdown
    daily_sales = transactions.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        total=Sum('total'),
        count=Count('id')
    ).order_by('date')
    
    # By payment method
    by_payment = POSPayment.objects.filter(
        transaction__created_at__date__gte=start_date,
        transaction__created_at__date__lte=end_date,
        transaction__status='completed'
    ).values(
        'payment_method__name',
        'payment_method__icon',
        'payment_method__color'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'stats': stats,
        'daily_sales': list(daily_sales),
        'by_payment': by_payment,
    }
    return render(request, 'sales/period_report.html', context)


@login_required
@group_required(['Admin', 'Manager'])
def products_report(request):
    """Products sales report."""
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from:
        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
    else:
        start_date = timezone.localdate() - timedelta(days=30)
    
    if date_to:
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    else:
        end_date = timezone.localdate()
    
    items = POSTransactionItem.objects.filter(
        transaction__created_at__date__gte=start_date,
        transaction__created_at__date__lte=end_date,
        transaction__status='completed'
    ).values(
        'product__id',
        'product__name',
        'product__category__name'
    ).annotate(
        total_qty=Sum('quantity'),
        total_amount=Sum('subtotal'),
        avg_price=Avg('unit_price')
    ).order_by('-total_amount')
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'items': items[:50],
    }
    return render(request, 'sales/products_report.html', context)


@login_required
@group_required(['Admin', 'Manager'])
def categories_report(request):
    """Categories sales report."""
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from:
        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
    else:
        start_date = timezone.localdate() - timedelta(days=30)
    
    if date_to:
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    else:
        end_date = timezone.localdate()
    
    items = POSTransactionItem.objects.filter(
        transaction__created_at__date__gte=start_date,
        transaction__created_at__date__lte=end_date,
        transaction__status='completed'
    ).values(
        'product__category__id',
        'product__category__name',
        'product__category__color'
    ).annotate(
        total_qty=Sum('quantity'),
        total_amount=Sum('subtotal'),
        product_count=Count('product', distinct=True)
    ).order_by('-total_amount')
    
    total = sum(item['total_amount'] or 0 for item in items)
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'items': items,
        'total': total,
    }
    return render(request, 'sales/categories_report.html', context)


@login_required
@group_required(['Admin', 'Manager'])
def cashiers_report(request):
    """Cashiers performance report."""
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from:
        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
    else:
        start_date = timezone.localdate() - timedelta(days=30)
    
    if date_to:
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    else:
        end_date = timezone.localdate()
    
    transactions = POSTransaction.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        status='completed'
    ).values(
        'session__cash_shift__cashier__id',
        'session__cash_shift__cashier__username',
        'session__cash_shift__cashier__first_name',
        'session__cash_shift__cashier__last_name'
    ).annotate(
        total_sales=Sum('total'),
        count=Count('id')
    ).order_by('-total_sales')
    
    # Calculate average per cashier
    for t in transactions:
        if t['count'] > 0:
            t['avg'] = t['total_sales'] / t['count']
        else:
            t['avg'] = Decimal('0')
    
    context = {
        'start_date': start_date,
        'end_date': end_date,
        'cashiers': transactions,
    }
    return render(request, 'sales/cashiers_report.html', context)


@login_required
@group_required(['Admin', 'Manager'])
def export_excel(request):
    """Export sales to Excel."""
    # Simple CSV export
    import csv
    
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if date_from:
        start_date = datetime.strptime(date_from, '%Y-%m-%d').date()
    else:
        start_date = timezone.localdate() - timedelta(days=30)
    
    if date_to:
        end_date = datetime.strptime(date_to, '%Y-%m-%d').date()
    else:
        end_date = timezone.localdate()
    
    transactions = POSTransaction.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=end_date,
        status='completed'
    ).select_related('session__cash_shift__cashier')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="ventas_{start_date}_{end_date}.csv"'
    response.write('\ufeff')  # BOM for Excel UTF-8
    
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Ticket', 'Fecha', 'Cajero', 'Subtotal', 'Descuento', 'Total'])
    
    for t in transactions:
        cashier = t.session.cash_shift.cashier if t.session and t.session.cash_shift else None
        writer.writerow([
            t.ticket_number,
            t.created_at.strftime('%d/%m/%Y %H:%M'),
            cashier.get_full_name() if cashier else '-',
            str(t.subtotal).replace('.', ','),
            str(t.discount_total).replace('.', ','),
            str(t.total).replace('.', ','),
        ])
    
    return response


@login_required
@group_required(['Admin', 'Manager'])
def export_pdf(request):
    """Export sales report to PDF."""
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="reporte_ventas.txt"'
    
    response.write("REPORTE DE VENTAS\n")
    response.write("=" * 50 + "\n")
    response.write("Para generar PDFs, se requiere instalar reportlab.\n")
    response.write("pip install reportlab\n")
    
    return response


# API for real-time stats
@login_required
def api_today_stats(request):
    """API endpoint for real-time today stats."""
    today = timezone.localdate()
    
    transactions = POSTransaction.objects.filter(
        created_at__date=today,
        status='completed'
    )
    
    stats = transactions.aggregate(
        total=Sum('total'),
        count=Count('id')
    )
    
    # By payment method
    payments = POSPayment.objects.filter(
        transaction__created_at__date=today,
        transaction__status='completed'
    ).values('payment_method__name', 'payment_method__color').annotate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    # Convert Decimals to floats for JSON serialization
    payments_list = [
        {
            'payment_method__name': p['payment_method__name'],
            'payment_method__color': p['payment_method__color'],
            'total': float(p['total'] or 0),
            'count': p['count']
        }
        for p in payments
    ]
    
    return JsonResponse({
        'success': True,
        'total': float(stats['total'] or 0),
        'count': stats['count'] or 0,
        'by_payment': payments_list,
        'timestamp': timezone.now().isoformat()
    })
