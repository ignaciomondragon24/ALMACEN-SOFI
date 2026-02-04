"""
MercadoPago Views - Vistas para administración y webhooks
"""
import json
import hmac
import hashlib
import logging
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.utils import timezone
from django.db import transaction, models

from decorators.decorators import group_required
from .models import MPCredentials, PointDevice, PaymentIntent, WebhookLog
from .services import MPPointService, payment_manager

logger = logging.getLogger(__name__)


# ==================== DASHBOARD Y CONFIG ====================

@login_required
@group_required(['Admin'])
def mp_dashboard(request):
    """Dashboard principal de Mercado Pago."""
    credentials = MPCredentials.get_active()
    devices = PointDevice.objects.all()
    
    # Estadísticas recientes
    recent_intents = PaymentIntent.objects.all()[:10]
    
    # Totales del día
    today = timezone.now().date()
    today_intents = PaymentIntent.objects.filter(
        created_at__date=today
    )
    
    stats = {
        'total_devices': devices.count(),
        'active_devices': devices.filter(status='active').count(),
        'today_total': today_intents.filter(status='approved').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0'),
        'today_approved': today_intents.filter(status='approved').count(),
        'today_rejected': today_intents.filter(status='rejected').count(),
        'today_pending': today_intents.filter(status='processing').count(),
    }
    
    return render(request, 'mercadopago/dashboard.html', {
        'credentials': credentials,
        'devices': devices,
        'recent_intents': recent_intents,
        'stats': stats,
    })


@login_required
@group_required(['Admin'])
def credentials_form(request):
    """Formulario para configurar credenciales de MP."""
    credentials = MPCredentials.get_active()
    
    if request.method == 'POST':
        access_token = request.POST.get('access_token', '').strip()
        public_key = request.POST.get('public_key', '').strip()
        is_sandbox = request.POST.get('is_sandbox') == 'on'
        webhook_secret = request.POST.get('webhook_secret', '').strip()
        
        if not access_token:
            messages.error(request, 'El Access Token es requerido')
            return redirect('mercadopago:credentials')
        
        if credentials:
            credentials.access_token = access_token
            credentials.public_key = public_key
            credentials.is_sandbox = is_sandbox
            credentials.webhook_secret = webhook_secret
            credentials.save()
            messages.success(request, 'Credenciales actualizadas correctamente')
        else:
            MPCredentials.objects.create(
                name='Producción' if not is_sandbox else 'Sandbox',
                access_token=access_token,
                public_key=public_key,
                is_sandbox=is_sandbox,
                webhook_secret=webhook_secret,
                is_active=True
            )
            messages.success(request, 'Credenciales guardadas correctamente')
        
        return redirect('mercadopago:dashboard')
    
    return render(request, 'mercadopago/credentials_form.html', {
        'credentials': credentials,
    })


@login_required
@group_required(['Admin'])
def test_connection(request):
    """Prueba la conexión con Mercado Pago."""
    try:
        service = MPPointService()
        success, response = service.get_devices()
        
        if success:
            return JsonResponse({
                'success': True,
                'message': 'Conexión exitosa con Mercado Pago',
                'devices_count': len(response.get('devices', []))
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f"Error: {response.get('message', 'Error desconocido')}"
            })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error de conexión: {str(e)}'
        })


# ==================== DISPOSITIVOS ====================

@login_required
@group_required(['Admin'])
def device_list(request):
    """Lista de dispositivos Point."""
    devices = PointDevice.objects.select_related('cash_register').all()
    return render(request, 'mercadopago/device_list.html', {
        'devices': devices,
    })


@login_required
@group_required(['Admin'])
def sync_devices(request):
    """Sincroniza dispositivos desde Mercado Pago."""
    success, result = payment_manager.sync_devices()
    
    if success:
        messages.success(request, f'Se sincronizaron {len(result)} dispositivos')
    else:
        messages.error(request, f'Error al sincronizar: {result}')
    
    return redirect('mercadopago:device_list')


@login_required
@group_required(['Admin'])
def device_edit(request, device_id):
    """Editar asignación de dispositivo a caja."""
    from cashregister.models import CashRegister
    
    device = get_object_or_404(PointDevice, pk=device_id)
    registers = CashRegister.objects.filter(is_active=True)
    
    if request.method == 'POST':
        register_id = request.POST.get('cash_register')
        device_name = request.POST.get('device_name', '').strip()
        
        if register_id:
            # Verificar que la caja no tenga otro dispositivo asignado
            existing = PointDevice.objects.filter(
                cash_register_id=register_id
            ).exclude(pk=device.pk).first()
            
            if existing:
                messages.error(request, f'La caja ya tiene el dispositivo {existing.device_name} asignado')
                return redirect('mercadopago:device_edit', device_id=device_id)
            
            device.cash_register_id = register_id
        else:
            device.cash_register = None
        
        if device_name:
            device.device_name = device_name
        
        device.save()
        messages.success(request, 'Dispositivo actualizado correctamente')
        return redirect('mercadopago:device_list')
    
    return render(request, 'mercadopago/device_form.html', {
        'device': device,
        'registers': registers,
    })


@login_required
@group_required(['Admin'])
def device_change_mode(request, device_id):
    """Cambia el modo de operación del dispositivo."""
    device = get_object_or_404(PointDevice, pk=device_id)
    mode = request.POST.get('mode', 'PDV')
    
    try:
        service = MPPointService()
        success, response = service.change_device_mode(device.device_id, mode)
        
        if success:
            device.operating_mode = mode
            device.save()
            messages.success(request, f'Modo cambiado a {mode}')
        else:
            messages.error(request, f"Error: {response.get('message', 'Error desconocido')}")
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('mercadopago:device_list')


# ==================== INTENCIONES DE PAGO ====================

@login_required
@group_required(['Admin', 'Manager'])
def payment_intent_list(request):
    """Lista de intenciones de pago."""
    intents = PaymentIntent.objects.select_related(
        'device', 'pos_transaction', 'created_by'
    ).all()[:100]
    
    return render(request, 'mercadopago/payment_intent_list.html', {
        'intents': intents,
    })


@login_required
@group_required(['Admin', 'Manager', 'Cashier'])
def payment_intent_detail(request, intent_id):
    """Detalle de una intención de pago."""
    intent = get_object_or_404(
        PaymentIntent.objects.select_related('device', 'pos_transaction', 'created_by'),
        pk=intent_id
    )
    
    return render(request, 'mercadopago/payment_intent_detail.html', {
        'intent': intent,
    })


@login_required
@group_required(['Admin', 'Manager', 'Cashier'])
def payment_intent_check_status(request, intent_id):
    """Consulta el estado actual de una intención de pago."""
    intent = get_object_or_404(PaymentIntent, pk=intent_id)
    
    success, result = payment_manager.check_status(intent)
    
    if success:
        return JsonResponse({
            'success': True,
            'status': intent.status,
            'mp_status': result.get('state'),
            'data': result
        })
    else:
        return JsonResponse({
            'success': False,
            'error': result
        })


@login_required
@group_required(['Admin', 'Manager', 'Cashier'])
def payment_intent_cancel(request, intent_id):
    """Cancela una intención de pago."""
    intent = get_object_or_404(PaymentIntent, pk=intent_id)
    
    success, message = payment_manager.cancel(intent)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': success, 'message': message})
    
    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)
    
    return redirect('mercadopago:payment_intent_detail', intent_id=intent_id)


# ==================== API PARA POS ====================

@login_required
@require_POST
def api_create_payment_intent(request):
    """
    API para crear una intención de pago desde el POS.
    
    POST /mercadopago/api/create-intent/
    {
        "amount": 1500.00,
        "transaction_id": 123,  // opcional
        "description": "Venta"  // opcional
    }
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    
    amount = data.get('amount')
    transaction_id = data.get('transaction_id')
    description = data.get('description', 'Venta CHE GOLOSO')
    
    if not amount:
        return JsonResponse({'success': False, 'error': 'Monto requerido'}, status=400)
    
    try:
        amount = Decimal(str(amount))
        if amount <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'error': 'Monto inválido'}, status=400)
    
    # Obtener el dispositivo asociado a la caja del usuario
    # Primero buscar el turno activo del usuario
    from cashregister.models import CashShift
    
    active_shift = CashShift.objects.filter(
        cashier=request.user,
        status='open'
    ).select_related('cash_register').first()
    
    if not active_shift:
        return JsonResponse({
            'success': False, 
            'error': 'No hay turno de caja abierto'
        }, status=400)
    
    # Buscar dispositivo Point asociado a la caja
    device = PointDevice.objects.filter(
        cash_register=active_shift.cash_register,
        status='active'
    ).first()
    
    if not device:
        return JsonResponse({
            'success': False, 
            'error': 'No hay dispositivo Point asociado a esta caja'
        }, status=400)
    
    # Obtener transacción POS si se proporcionó
    pos_transaction = None
    if transaction_id:
        from pos.models import POSTransaction
        pos_transaction = POSTransaction.objects.filter(pk=transaction_id).first()
    
    # Crear y enviar la intención de pago
    success, result = payment_manager.create_and_send(
        device=device,
        amount=amount,
        pos_transaction=pos_transaction,
        user=request.user,
        description=description
    )
    
    if success:
        return JsonResponse({
            'success': True,
            'payment_intent': {
                'id': str(result.id),
                'external_reference': result.external_reference,
                'amount': float(result.amount),
                'status': result.status,
                'device_name': device.device_name,
            },
            'message': 'Pago enviado al dispositivo Point. Esperando pago del cliente.'
        })
    else:
        return JsonResponse({
            'success': False,
            'error': result
        }, status=400)


@login_required
@require_GET
def api_check_payment_status(request, intent_id):
    """
    API para consultar el estado de un pago.
    
    GET /mercadopago/api/status/<intent_id>/
    """
    intent = get_object_or_404(PaymentIntent, pk=intent_id)
    
    # Si ya está en estado terminal, devolver sin consultar MP
    if intent.is_terminal_state:
        return JsonResponse({
            'success': True,
            'status': intent.status,
            'is_final': True,
            'payment_intent': {
                'id': str(intent.id),
                'external_reference': intent.external_reference,
                'amount': float(intent.amount),
                'status': intent.status,
                'status_display': intent.get_status_display(),
                'payment_method': intent.payment_method,
                'card_brand': intent.card_brand,
                'card_last_four': intent.card_last_four,
                'authorization_code': intent.authorization_code,
            }
        })
    
    # Consultar estado en MP
    success, result = payment_manager.check_status(intent)
    
    # Actualizar estado local según respuesta
    if success:
        mp_state = result.get('state', '')
        
        if mp_state == 'FINISHED':
            # Verificar si fue aprobado
            payment = result.get('payment', {})
            if payment.get('status') == 'approved':
                intent.mark_approved(payment)
            else:
                intent.mark_rejected(payment.get('status_detail', ''))
        elif mp_state == 'CANCELED':
            intent.mark_cancelled()
        elif mp_state == 'ERROR':
            intent.mark_error(result.get('error_reason', 'Error desconocido'))
    
    return JsonResponse({
        'success': True,
        'status': intent.status,
        'is_final': intent.is_terminal_state,
        'payment_intent': {
            'id': str(intent.id),
            'external_reference': intent.external_reference,
            'amount': float(intent.amount),
            'status': intent.status,
            'status_display': intent.get_status_display(),
            'payment_method': intent.payment_method,
            'card_brand': intent.card_brand,
            'card_last_four': intent.card_last_four,
            'authorization_code': intent.authorization_code,
        }
    })


@login_required
@require_POST  
def api_cancel_payment(request, intent_id):
    """
    API para cancelar un pago pendiente.
    
    POST /mercadopago/api/cancel/<intent_id>/
    """
    intent = get_object_or_404(PaymentIntent, pk=intent_id)
    
    success, message = payment_manager.cancel(intent)
    
    return JsonResponse({
        'success': success,
        'message': message,
        'status': intent.status
    })


# ==================== WEBHOOK ====================

@csrf_exempt
@require_POST
def webhook_receiver(request):
    """
    Endpoint para recibir webhooks de Mercado Pago.
    
    Mercado Pago envía notificaciones cuando:
    - Se completa un pago (approved, rejected)
    - Cambia el estado de una intención de pago
    - Eventos de dispositivos
    
    URL a configurar en MP: https://tudominio.com/mercadopago/webhook/
    """
    # Guardar log del webhook
    webhook_log = WebhookLog(
        event_type='unknown',
        ip_address=get_client_ip(request)
    )
    
    try:
        # Parsear el payload
        try:
            payload = json.loads(request.body)
        except json.JSONDecodeError:
            webhook_log.event_type = 'invalid_json'
            webhook_log.processing_result = 'JSON inválido'
            webhook_log.save()
            return HttpResponse(status=400)
        
        webhook_log.payload = json.dumps(payload, indent=2, default=str)
        webhook_log.headers = json.dumps(dict(request.headers), indent=2, default=str)
        
        # Extraer información del evento
        event_type = payload.get('type', payload.get('action', 'unknown'))
        event_id = payload.get('id', '')
        
        webhook_log.event_type = event_type
        webhook_log.event_id = str(event_id)
        
        # Validar firma si está configurada
        credentials = MPCredentials.get_active()
        if credentials and credentials.webhook_secret:
            signature = request.headers.get('X-Signature')
            if not verify_webhook_signature(request.body, signature, credentials.webhook_secret):
                webhook_log.processing_result = 'Firma inválida'
                webhook_log.save()
                logger.warning(f"Webhook con firma inválida: {event_id}")
                return HttpResponse(status=401)
        
        # Procesar según el tipo de evento
        result = process_webhook_event(event_type, payload)
        
        webhook_log.processed = True
        webhook_log.processing_result = result
        webhook_log.save()
        
        logger.info(f"Webhook procesado: {event_type} - {result}")
        return HttpResponse(status=200)
        
    except Exception as e:
        webhook_log.processing_result = f'Error: {str(e)}'
        webhook_log.save()
        logger.exception(f"Error procesando webhook: {e}")
        return HttpResponse(status=500)


def verify_webhook_signature(body, signature, secret):
    """Verifica la firma del webhook."""
    if not signature or not secret:
        return True  # Si no hay firma configurada, aceptar
    
    try:
        # MP usa HMAC-SHA256
        expected = hmac.new(
            secret.encode(),
            body,
            hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


def process_webhook_event(event_type, payload):
    """
    Procesa un evento de webhook.
    
    Args:
        event_type: Tipo de evento
        payload: Datos del evento
    
    Returns:
        str: Resultado del procesamiento
    """
    # Eventos de Point
    if event_type in ['point_integration_wh', 'point']:
        return process_point_event(payload)
    
    # Eventos de pagos
    elif event_type == 'payment':
        return process_payment_event(payload)
    
    # Otros eventos
    else:
        return f'Evento {event_type} no procesado'


def process_point_event(payload):
    """Procesa eventos del Point."""
    data = payload.get('data', {})
    resource_id = data.get('id')
    
    if not resource_id:
        return 'Sin ID de recurso'
    
    # Buscar la intención de pago
    intent = PaymentIntent.objects.filter(
        mp_payment_intent_id=resource_id
    ).first()
    
    if not intent:
        # Intentar buscar por external_reference en el payload
        external_ref = data.get('external_reference')
        if external_ref:
            intent = PaymentIntent.objects.filter(
                external_reference=external_ref
            ).first()
    
    if not intent:
        return f'Intención de pago no encontrada: {resource_id}'
    
    # Obtener estado actual desde MP
    try:
        service = MPPointService()
        success, response = service.get_payment_intent(
            intent.device.device_id,
            intent.mp_payment_intent_id
        )
        
        if success:
            state = response.get('state', '')
            
            if state == 'FINISHED':
                payment = response.get('payment', {})
                if payment.get('status') == 'approved':
                    intent.mark_approved(payment)
                    # Completar la transacción POS si está asociada
                    complete_pos_transaction(intent)
                    return f'Pago aprobado: {intent.external_reference}'
                else:
                    intent.mark_rejected(payment.get('status_detail', ''))
                    return f'Pago rechazado: {intent.external_reference}'
            
            elif state == 'CANCELED':
                intent.mark_cancelled()
                return f'Pago cancelado: {intent.external_reference}'
            
            elif state == 'ERROR':
                intent.mark_error(response.get('error_reason', ''))
                return f'Error en pago: {intent.external_reference}'
            
            return f'Estado {state}: {intent.external_reference}'
        else:
            return f'Error consultando MP: {response}'
            
    except Exception as e:
        return f'Error: {str(e)}'


def process_payment_event(payload):
    """Procesa eventos de pagos."""
    data = payload.get('data', {})
    payment_id = data.get('id')
    
    if not payment_id:
        return 'Sin ID de pago'
    
    # Buscar por mp_payment_id
    intent = PaymentIntent.objects.filter(
        mp_payment_id=str(payment_id)
    ).first()
    
    if not intent:
        return f'Pago no encontrado en sistema: {payment_id}'
    
    # Obtener detalles del pago
    try:
        service = MPPointService()
        success, payment_data = service.get_payment(payment_id)
        
        if success:
            status = payment_data.get('status')
            
            if status == 'approved' and intent.status != 'approved':
                intent.mark_approved(payment_data)
                complete_pos_transaction(intent)
                return f'Pago confirmado: {intent.external_reference}'
            elif status in ['rejected', 'cancelled']:
                intent.mark_rejected(payment_data.get('status_detail', ''))
                return f'Pago rechazado/cancelado: {intent.external_reference}'
            
            return f'Estado {status}: {intent.external_reference}'
        else:
            return f'Error consultando pago: {payment_data}'
            
    except Exception as e:
        return f'Error: {str(e)}'


def complete_pos_transaction(payment_intent):
    """
    Completa la transacción POS cuando el pago es aprobado.
    """
    if not payment_intent.pos_transaction:
        return
    
    pos_transaction = payment_intent.pos_transaction
    
    if pos_transaction.status != 'pending':
        return
    
    try:
        with transaction.atomic():
            from pos.models import POSPayment
            from cashregister.models import PaymentMethod
            
            # Crear el registro de pago
            mp_method = PaymentMethod.objects.filter(code='mercadopago').first()
            
            if mp_method:
                POSPayment.objects.create(
                    transaction=pos_transaction,
                    payment_method=mp_method,
                    amount=payment_intent.amount,
                    reference=payment_intent.mp_payment_id,
                    details=f"Tarjeta: {payment_intent.card_brand} ****{payment_intent.card_last_four}"
                )
            
            # Actualizar totales
            pos_transaction.amount_paid = payment_intent.amount
            pos_transaction.status = 'completed'
            pos_transaction.completed_at = timezone.now()
            pos_transaction.save()
            
            logger.info(f"Transacción POS completada: {pos_transaction.ticket_number}")
            
    except Exception as e:
        logger.exception(f"Error completando transacción POS: {e}")


def get_client_ip(request):
    """Obtiene la IP del cliente."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


# ==================== LOGS ====================

@login_required
@group_required(['Admin'])
def webhook_logs(request):
    """Lista de logs de webhooks."""
    logs = WebhookLog.objects.all()[:100]
    return render(request, 'mercadopago/webhook_logs.html', {
        'logs': logs,
    })
