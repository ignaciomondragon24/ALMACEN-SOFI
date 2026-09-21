"""
Granel Views — CRUD de depósito y carameleras, APIs para aperturas,
auditorías y registro de ventas desde el POS.
"""
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Sum, Count
from decimal import Decimal, InvalidOperation
import json

from decorators.decorators import stock_manager_required
from stocks.models import Product
from .models import (
    Caramelera,
    AperturaBulto,
    VentaGranel,
    AuditoriaCaramelera,
)
from .services import GranelService


# ============================================================
# ProductoDeposito — CRUD
# ============================================================

@login_required
@stock_manager_required
def deposito_list(request):
    """Lista de productos del inventario marcados como 'para caramelera'."""
    qs = Product.objects.filter(es_deposito_caramelera=True, is_active=True).order_by('name')
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(name__icontains=q) | Product.objects.filter(
            es_deposito_caramelera=True, is_active=True, marca__icontains=q
        )
        qs = qs.distinct()

    return render(request, 'granel/deposito_list.html', {
        'productos': qs,
        'q': q,
    })


@login_required
@stock_manager_required
def deposito_edit(request, pk):
    """Redirige al formulario estándar del inventario para editar el producto."""
    return redirect('stocks:product_edit', pk=pk)


@login_required
@stock_manager_required
@require_POST
def api_deposito_ajustar_stock(request, pk):
    """POST: ajusta el current_stock de un Product (depósito caramelera)."""
    producto = get_object_or_404(Product, pk=pk, es_deposito_caramelera=True)
    try:
        data = json.loads(request.body)
        delta = int(data.get('delta', 0))
        nuevo = int(producto.current_stock) + delta
        if nuevo < 0:
            return JsonResponse({'error': 'El stock no puede quedar negativo.'}, status=400)
        producto.current_stock = nuevo
        producto.save(update_fields=['current_stock', 'updated_at'])
        if delta > 0:
            GranelService.auto_abrir_disponible(producto, user=request.user)
        return JsonResponse({
            'success': True,
            'stock_unidades': int(producto.current_stock),
        })
    except (ValueError, json.JSONDecodeError) as e:
        return JsonResponse({'error': str(e)}, status=400)


# ============================================================
# Caramelera — CRUD + detalle
# ============================================================

@login_required
@stock_manager_required
def caramelera_list(request):
    """Lista de carameleras activas con stock, precios y margen estimado."""
    carameleras = (
        Caramelera.objects.filter(is_active=True)
        .order_by('nombre')
    )
    return render(request, 'granel/caramelera_list.html', {'carameleras': carameleras})


def _fmt_dec(value, places='0.01'):
    """Decimal → texto con punto decimal para value="" de inputs type=number ('' si es 0/None)."""
    if value is None or Decimal(value) == 0:
        return ''
    return str(Decimal(value).quantize(Decimal(places)))


def _caramelera_form_context(request, caramelera, valores=None, errors=None):
    """Contexto compartido del formulario de producto por peso."""
    productos = Product.objects.filter(es_deposito_caramelera=True, is_active=True).order_by('name')
    if valores is None:
        valores = {}
        if caramelera is not None:
            valores = {
                'nombre': caramelera.nombre,
                'precio_100g': _fmt_dec(caramelera.precio_100g),
                'precio_kg': _fmt_dec(caramelera.precio_kilo),
                'precio_cuarto': _fmt_dec(caramelera.precio_cuarto),
            }
            pos_product = caramelera.producto_pos.filter(is_granel=True).first()
            if pos_product is not None and pos_product.min_stock:
                valores['stock_minimo_kg'] = _fmt_dec(Decimal(pos_product.min_stock) / 1000, '0.001')
    if caramelera is not None:
        autorizados_ids = list(caramelera.productos_autorizados.values_list('pk', flat=True))
    else:
        autorizados_ids = []
    if request.method == 'POST':
        autorizados_ids = [int(x) for x in request.POST.getlist('productos_autorizados') if x.isdigit()]
    return {
        'title': f'Editar {caramelera.nombre}' if caramelera else 'Nuevo producto por peso',
        'caramelera': caramelera,
        'productos_deposito': productos,
        'autorizados_ids': autorizados_ids,
        'valores': valores,
        'errors': errors or [],
        'costo_kg_actual': _fmt_dec(caramelera.costo_kilo) if caramelera else '',
    }


@login_required
@stock_manager_required
def caramelera_create(request):
    """Formulario para crear un nuevo producto por peso."""
    if request.method == 'POST':
        return _caramelera_save(request, None)
    return render(request, 'granel/caramelera_form.html',
                  _caramelera_form_context(request, None))


@login_required
@stock_manager_required
def caramelera_edit(request, pk):
    """Formulario para editar un producto por peso."""
    caramelera = get_object_or_404(Caramelera, pk=pk)
    if request.method == 'POST':
        return _caramelera_save(request, caramelera)
    return render(request, 'granel/caramelera_form.html',
                  _caramelera_form_context(request, caramelera))


# Topes que entran en las columnas de la base (evita un error 500 si alguien tipea un cero de más).
MAX_PRECIO = Decimal('9999999.99')     # precio por 100g / por kilo de oferta / costo por kilo
MAX_GRAMOS = Decimal('999999999')      # ~1.000 toneladas


def _parse_decimal(raw, default=None):
    raw = (raw or '').strip().replace(',', '.')
    if raw == '':
        return default
    return Decimal(raw)  # InvalidOperation lo maneja quien llama


def _caramelera_save(request, caramelera):
    """Lógica compartida de creación/edición de un producto por peso.

    El precio se puede cargar por kilo (`precio_kg`, lo natural para quien
    vende por peso) o por 100g (`precio_100g`); internamente se guarda por
    100g. Al crear también se puede cargar la mercadería que ya hay
    (`stock_inicial` + `stock_unidad` + `costo_kg`), sin pasar por depósito.
    """
    nombre = request.POST.get('nombre', '').strip()
    autorizados_ids = request.POST.getlist('productos_autorizados')

    errors = []
    if not nombre:
        errors.append('El nombre es obligatorio.')

    # Precio de venta (por 100g, derivado del precio por kilo si hace falta)
    precio_100g = Decimal('0')
    try:
        p100 = _parse_decimal(request.POST.get('precio_100g'))
        pkg = _parse_decimal(request.POST.get('precio_kg'))
        # El precio por kilo es el que ve y edita la persona: si viene, manda.
        if pkg is not None:
            p100 = (pkg / Decimal('10')).quantize(Decimal('0.01'))
        if p100 is None:
            errors.append('Ingresá el precio de venta por kilo.')
        elif p100 <= 0:
            errors.append('El precio de venta debe ser mayor a 0.')
        elif p100 > MAX_PRECIO:
            errors.append('El precio de venta es demasiado alto. Revisá los ceros.')
        else:
            precio_100g = p100
    except InvalidOperation:
        errors.append('El precio de venta es inválido.')

    try:
        precio_cuarto = _parse_decimal(request.POST.get('precio_cuarto'), Decimal('0'))
        if precio_cuarto < 0:
            precio_cuarto = Decimal('0')
        if precio_cuarto > MAX_PRECIO:
            errors.append('El precio especial por kilo es demasiado alto. Revisá los ceros.')
            precio_cuarto = Decimal('0')
    except InvalidOperation:
        precio_cuarto = Decimal('0')

    # Mercadería que ya hay (solo al crear)
    gramos_iniciales = Decimal('0')
    costo_kg = None
    if caramelera is None:
        try:
            stock_ini = _parse_decimal(request.POST.get('stock_inicial'), Decimal('0'))
            costo_kg = _parse_decimal(request.POST.get('costo_kg'))
            if stock_ini < 0:
                errors.append('El stock inicial no puede ser negativo.')
            elif stock_ini > 0:
                unidad = request.POST.get('stock_unidad', 'kg')
                gramos_iniciales = stock_ini * (Decimal('1000') if unidad == 'kg' else Decimal('1'))
                if gramos_iniciales > MAX_GRAMOS:
                    errors.append('El stock inicial es demasiado grande. Revisá la cantidad y la unidad.')
                    gramos_iniciales = Decimal('0')
                if costo_kg is None or costo_kg <= 0:
                    errors.append(
                        'Ingresá cuánto te costó el kilo, así el sistema calcula tu ganancia.'
                    )
                elif costo_kg > MAX_PRECIO:
                    errors.append('El costo por kilo es demasiado alto. Revisá los ceros.')
        except InvalidOperation:
            errors.append('El stock inicial o el costo son inválidos.')

    # Aviso de stock bajo (para el pedido sugerido a proveedores), en kilos.
    minimo_gramos = 0
    try:
        minimo_kg = _parse_decimal(request.POST.get('stock_minimo_kg'), Decimal('0'))
        if minimo_kg < 0:
            errors.append('El aviso de stock bajo no puede ser negativo.')
        else:
            minimo_gramos = int(minimo_kg * 1000)
    except InvalidOperation:
        errors.append('El aviso de stock bajo es inválido.')

    valores = {
        'nombre': nombre,
        'stock_minimo_kg': request.POST.get('stock_minimo_kg', ''),
        'precio_100g': request.POST.get('precio_100g', ''),
        'precio_kg': request.POST.get('precio_kg', ''),
        'precio_cuarto': request.POST.get('precio_cuarto', ''),
        'stock_inicial': request.POST.get('stock_inicial', ''),
        'stock_unidad': request.POST.get('stock_unidad', 'kg'),
        'costo_kg': request.POST.get('costo_kg', ''),
    }

    if errors:
        return render(request, 'granel/caramelera_form.html',
                      _caramelera_form_context(request, caramelera, valores, errors))

    if caramelera is None:
        caramelera = Caramelera()

    caramelera.nombre = nombre
    caramelera.precio_100g = precio_100g
    caramelera.precio_cuarto = precio_cuarto
    caramelera.save()

    # Mercadería inicial cargada en el mismo formulario
    if gramos_iniciales > 0:
        GranelService.ingresar_stock(
            caramelera.pk, gramos_iniciales, costo_kg, user=request.user,
            notas='Stock inicial',
        )

    # Sincronizar productos autorizados
    autorizados = Product.objects.filter(
        pk__in=[int(x) for x in autorizados_ids if x.isdigit()],
        es_deposito_caramelera=True,
        is_active=True,
    )
    caramelera.productos_autorizados.set(autorizados)

    # Si algún producto recién autorizado ya tenía stock esperando (se
    # cargó antes de autorizarlo), abrirlo automáticamente ahora que la
    # autorización ya es inequívoca (ver GranelService.auto_abrir_disponible).
    for producto in autorizados:
        GranelService.auto_abrir_disponible(producto, user=request.user)

    # Crear/actualizar el producto POS vinculado (is_granel=True)
    pos_product = _sync_caramelera_pos_product(caramelera)
    if pos_product.min_stock != minimo_gramos:
        pos_product.min_stock = minimo_gramos
        pos_product.save(update_fields=['min_stock', 'updated_at'])

    return redirect('granel:caramelera_detail', pk=caramelera.pk)


def _sync_caramelera_pos_product(caramelera):
    """Crea o actualiza el producto is_granel de stocks vinculado a esta caramelera.

    El producto POS es el que aparece en el buscador del POS y dispara el modal de peso.
    Relee la caramelera de la base antes de copiar (ver
    GranelService.sincronizar_producto_pos).
    """
    return GranelService.sincronizar_producto_pos(caramelera)


@login_required
@stock_manager_required
def caramelera_detail(request, pk):
    """
    Vista principal de una caramelera:
    - Stock actual, precios, costo ponderado, margen
    - Historial de aperturas recientes
    - Ranking de rotación por producto
    - Ventas recientes con margen real
    - Card de resumen de margen acumulado
    - Modal Abrir Paquete
    - Modal Auditoría
    """
    caramelera = get_object_or_404(Caramelera, pk=pk)

    # Productos autorizados con stock en depósito (stocks.Product)
    autorizados = caramelera.productos_autorizados.filter(is_active=True).order_by('name')

    # Historial de aperturas (últimas 20)
    aperturas = (
        AperturaBulto.objects.filter(caramelera=caramelera)
        .select_related('producto', 'abierto_por')
        .order_by('-abierto_en')[:20]
    )

    # Ranking de rotación — agrupado por producto
    ranking = (
        AperturaBulto.objects.filter(caramelera=caramelera, producto__isnull=False)
        .values('producto__id', 'producto__name', 'producto__marca')
        .annotate(
            bolsas=Count('id'),
            gramos_total=Sum('gramos_agregados'),
        )
        .order_by('-bolsas')[:10]
    )

    # Ventas recientes
    ventas = (
        VentaGranel.objects.filter(caramelera=caramelera)
        .order_by('-vendido_en')[:20]
    )

    # Resumen de margen real total
    resumen_ventas = VentaGranel.objects.filter(caramelera=caramelera).aggregate(
        total_recaudado=Sum('precio_cobrado'),
        total_costo=Sum('costo_total'),
        total_ganancia=Sum('ganancia'),
    )

    # Historial de auditorías (últimas 20)
    auditorias = (
        AuditoriaCaramelera.objects.filter(caramelera=caramelera)
        .select_related('auditado_por')
        .order_by('-auditado_en')[:20]
    )

    return render(request, 'granel/caramelera_detail.html', {
        'caramelera': caramelera,
        'autorizados': autorizados,
        'aperturas': aperturas,
        'ranking': ranking,
        'ventas': ventas,
        'resumen_ventas': resumen_ventas,
        'auditorias': auditorias,
    })


# ============================================================
# APIs JSON
# ============================================================

@login_required
@stock_manager_required
@require_POST
def api_abrir_paquete(request, pk):
    """POST {producto_id, cantidad?, notas?} — Abre paquetes del depósito hacia la caramelera."""
    try:
        data = json.loads(request.body)
        producto_id = data.get('producto_id')
        notas = data.get('notas', '')
        cantidad = int(data.get('cantidad', 1))

        if not producto_id:
            return JsonResponse({'error': 'Falta producto_id'}, status=400)
        if cantidad < 1:
            return JsonResponse({'error': 'La cantidad debe ser al menos 1'}, status=400)

        apertura = GranelService.abrir_paquete(
            caramelera_id=pk,
            producto_deposito_id=int(producto_id),
            user=request.user,
            notas=notas,
            cantidad=cantidad,
        )

        return JsonResponse({
            'success': True,
            'cantidad': cantidad,
            'gramos_agregados': float(apertura.gramos_agregados),
            'nuevo_stock': float(apertura.stock_gramos_despues),
            'nuevo_costo_ponderado': float(apertura.costo_ponderado_despues),
            'unidades_restantes_deposito': apertura.unidades_restantes_deposito,
            'producto_nombre': apertura.producto.name,
        })
    except (Caramelera.DoesNotExist, Product.DoesNotExist):
        return JsonResponse({'error': 'No encontrado'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@stock_manager_required
@require_POST
def api_ingresar_stock(request, pk):
    """POST {cantidad, unidad ('kg'|'g'), costo_kg, notas?} — Suma mercadería a granel."""
    try:
        data = json.loads(request.body)
        cantidad = Decimal(str(data.get('cantidad', '')).replace(',', '.'))
        costo_kg = Decimal(str(data.get('costo_kg', '')).replace(',', '.'))
    except (json.JSONDecodeError, InvalidOperation):
        return JsonResponse({'error': 'Completá la cantidad y el costo por kilo con números.'}, status=400)

    gramos = cantidad * (Decimal('1000') if data.get('unidad', 'kg') == 'kg' else Decimal('1'))
    if costo_kg <= 0:
        return JsonResponse({'error': 'Ingresá cuánto te costó el kilo.'}, status=400)
    if costo_kg > MAX_PRECIO or gramos > MAX_GRAMOS:
        return JsonResponse({'error': 'La cantidad o el costo son demasiado altos. Revisá los números.'}, status=400)
    from django.utils.dateparse import parse_date
    vencimiento = parse_date(str(data.get('vencimiento') or '').strip()) or None
    try:
        apertura = GranelService.ingresar_stock(
            pk, gramos, costo_kg, user=request.user, notas=data.get('notas', ''),
            vencimiento=vencimiento,
        )
    except Caramelera.DoesNotExist:
        return JsonResponse({'error': 'No encontrado'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({
        'success': True,
        'gramos_agregados': float(apertura.gramos_agregados),
        'nuevo_stock': float(apertura.stock_gramos_despues),
        'nuevo_costo_ponderado': float(apertura.costo_ponderado_despues),
    })


@login_required
@stock_manager_required
@require_POST
def api_auditoria(request, pk):
    """POST {peso_real, motivo?} — Registra una auditoría y ajusta el stock."""
    try:
        data = json.loads(request.body)
        peso_real = data.get('peso_real')
        motivo = data.get('motivo', '')

        if peso_real is None:
            return JsonResponse({'error': 'Falta peso_real'}, status=400)
        peso_real = Decimal(str(peso_real))
        if peso_real < 0:
            return JsonResponse({'error': 'El peso real no puede ser negativo'}, status=400)

        auditoria = GranelService.realizar_auditoria(
            caramelera_id=pk,
            peso_real_balanza=peso_real,
            user=request.user,
            motivo=motivo,
        )

        return JsonResponse({
            'success': True,
            'stock_sistema': float(auditoria.stock_sistema_gramos),
            'peso_real': float(auditoria.peso_real_balanza_gramos),
            'diferencia': float(auditoria.diferencia_gramos),
            'porcentaje_merma': float(auditoria.porcentaje_merma),
            'nuevo_stock': float(auditoria.peso_real_balanza_gramos),
        })
    except Caramelera.DoesNotExist:
        return JsonResponse({'error': 'No encontrado'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
def api_venta_granel(request, pk):
    """
    POST {gramos, precio_cobrado, pos_transaction_id?}
    Registra una VentaGranel y descuenta el stock.
    Puede ser llamado sin @stock_manager_required porque también lo llama el POS.
    Requiere login.
    """
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'No autenticado'}, status=401)

    caramelera = get_object_or_404(Caramelera, pk=pk)
    try:
        data = json.loads(request.body)
        gramos = data.get('gramos')
        precio_cobrado = data.get('precio_cobrado')
        pos_transaction_id = data.get('pos_transaction_id')

        if gramos is None or precio_cobrado is None:
            return JsonResponse({'error': 'Faltan gramos o precio_cobrado'}, status=400)

        venta = GranelService.registrar_venta(
            caramelera_id=caramelera.pk,
            gramos_vendidos=gramos,
            precio_cobrado=precio_cobrado,
            pos_transaction_id=pos_transaction_id,
        )
        caramelera.refresh_from_db()

        return JsonResponse({
            'success': True,
            'venta_id': venta.pk,
            'ganancia': float(venta.ganancia),
            'nuevo_stock': float(caramelera.stock_gramos_actual),
        })
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_GET
def api_caramelera_info(request, pk):
    """GET — Devuelve datos actuales de la caramelera para el POS."""
    caramelera = get_object_or_404(Caramelera, pk=pk, is_active=True)
    return JsonResponse({
        'id': caramelera.pk,
        'nombre': caramelera.nombre,
        'stock_gramos': float(caramelera.stock_gramos_actual),
        'precio_100g': float(caramelera.precio_100g),
        'precio_cuarto': float(caramelera.precio_cuarto),
        'costo_ponderado_gramo': float(caramelera.costo_ponderado_gramo),
        'margen_100g': float(caramelera.margen_100g),
    })
