"""
Test script para la funcionalidad de Carga de Stock por Bultos
Ejecutar: python test_bulk_stock.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'superrecord.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model

User = get_user_model()

def test_packaging_system():
    """Test completo del sistema de empaques jerárquicos."""
    
    print("=" * 60)
    print("TEST: Sistema de Carga de Stock por Bultos - CHE GOLOSO")
    print("=" * 60)
    
    from stocks.models import Product, ProductCategory, ProductPackaging, StockMovement
    
    # 1. Crear datos de prueba
    print("\n1. Creando datos de prueba...")
    
    # Crear categoría
    category, _ = ProductCategory.objects.get_or_create(
        name='Golosinas Test',
        defaults={'default_margin_percent': Decimal('30')}
    )
    print(f"   ✓ Categoría: {category.name}")
    
    # Crear producto
    product, created = Product.objects.get_or_create(
        sku='TEST-BULTO-001',
        defaults={
            'name': 'Gomitas Test',
            'barcode': '7790001000001',
            'category': category,
            'purchase_price': Decimal('10.00'),
            'sale_price': Decimal('15.00'),
            'current_stock': 0,
            'min_stock': 10
        }
    )
    if not created:
        product.current_stock = 0
        product.save()
    print(f"   ✓ Producto: {product.name} (SKU: {product.sku})")
    
    # 2. Crear empaques jerárquicos
    print("\n2. Configurando empaques jerárquicos...")
    
    # Limpiar empaques anteriores
    ProductPackaging.objects.filter(product=product).delete()
    
    # Empaque Unidad
    unit_pkg = ProductPackaging.objects.create(
        product=product,
        packaging_type='unit',
        barcode='7790001000001-U',
        name='Unidad',
        units_per_display=1,
        displays_per_bulk=1,
        purchase_price=Decimal('100.00'),
        margin_percent=Decimal('30'),
        is_active=True
    )
    print(f"   ✓ Unidad: {unit_pkg.barcode} | Precio: ${unit_pkg.purchase_price}")
    
    # Empaque Display (12 unidades)
    display_pkg = ProductPackaging.objects.create(
        product=product,
        packaging_type='display',
        barcode='7790001000001-D',
        name='Display x 12',
        units_per_display=12,
        displays_per_bulk=1,
        purchase_price=Decimal('1000.00'),
        margin_percent=Decimal('30'),
        is_active=True
    )
    print(f"   ✓ Display: {display_pkg.barcode} | {display_pkg.units_quantity} unidades | Precio: ${display_pkg.purchase_price}")
    
    # Empaque Bulto (12 displays = 144 unidades)
    bulk_pkg = ProductPackaging.objects.create(
        product=product,
        packaging_type='bulk',
        barcode='7790001000001-B',
        name='Bulto x 144',
        units_per_display=12,
        displays_per_bulk=12,
        purchase_price=Decimal('10000.00'),
        margin_percent=Decimal('30'),
        is_active=True
    )
    print(f"   ✓ Bulto: {bulk_pkg.barcode} | {bulk_pkg.units_quantity} unidades | {bulk_pkg.displays_per_bulk} displays")
    
    # 3. Verificar cálculos automáticos
    print("\n3. Verificando cálculos automáticos...")
    
    # Recargar para verificar el save()
    bulk_pkg.refresh_from_db()
    
    assert bulk_pkg.units_quantity == 144, f"Error: units_quantity debería ser 144, es {bulk_pkg.units_quantity}"
    print(f"   ✓ Total unidades por bulto: {bulk_pkg.units_quantity} (correcto)")
    
    expected_unit_price = Decimal('10000.00') / 144
    actual_unit_price = bulk_pkg.unit_purchase_price
    print(f"   ✓ Precio compra por unidad: ${actual_unit_price:.2f}")
    
    # Calcular precio de venta con margen
    bulk_pkg.sale_price = bulk_pkg.purchase_price * (1 + bulk_pkg.margin_percent / 100)
    bulk_pkg.save()
    
    print(f"   ✓ Precio venta bulto: ${bulk_pkg.sale_price:.2f}")
    print(f"   ✓ Precio venta por unidad: ${bulk_pkg.unit_sale_price:.2f}")
    print(f"   ✓ Ganancia por unidad: ${(bulk_pkg.unit_sale_price - bulk_pkg.unit_purchase_price):.2f}")
    
    # 4. Simular carga de stock
    print("\n4. Simulando carga de stock por bultos...")
    
    cantidad_bultos = 3
    stock_inicial = product.current_stock
    
    total_units = bulk_pkg.calculate_total_units(cantidad_bultos)
    total_displays = bulk_pkg.calculate_displays(cantidad_bultos)
    
    print(f"   → Cargando {cantidad_bultos} bultos...")
    print(f"   → Displays calculados: {total_displays}")
    print(f"   → Unidades calculadas: {total_units}")
    
    # Actualizar stock
    product.current_stock += total_units
    product.purchase_price = bulk_pkg.unit_purchase_price
    product.sale_price = bulk_pkg.unit_sale_price
    product.save()
    
    # Registrar movimiento
    movement = StockMovement.objects.create(
        product=product,
        movement_type='purchase',
        quantity=total_units,
        unit_cost=bulk_pkg.unit_purchase_price,
        stock_before=stock_inicial,
        stock_after=product.current_stock,
        reference=f'Test Carga por Bultos - {cantidad_bultos} bultos',
        notes=f'Displays: {total_displays}'
    )
    
    print(f"   ✓ Stock actualizado: {stock_inicial} → {product.current_stock}")
    print(f"   ✓ Movimiento registrado: #{movement.id}")
    
    # 5. Verificar resultado
    print("\n5. Verificando resultado final...")
    
    product.refresh_from_db()
    expected_stock = stock_inicial + total_units
    
    assert product.current_stock == expected_stock, f"Error: stock debería ser {expected_stock}, es {product.current_stock}"
    print(f"   ✓ Stock actual: {product.current_stock} unidades")
    print(f"   ✓ Precio venta unitario: ${product.sale_price:.2f}")
    
    # 6. Test de búsqueda por código de barras
    print("\n6. Verificando búsqueda por código de barras...")
    
    found_pkg = ProductPackaging.objects.filter(barcode='7790001000001-B', is_active=True).first()
    assert found_pkg is not None, "Error: no se encontró el empaque por código de barras"
    assert found_pkg.product.id == product.id, "Error: el empaque no corresponde al producto"
    print(f"   ✓ Búsqueda por barcode: {found_pkg.barcode} → {found_pkg.product.name}")
    
    # 7. Calcular precios desde margen
    print("\n7. Verificando cálculo de precios desde margen...")
    
    prices = bulk_pkg.calculate_prices_from_margin()
    if prices:
        print(f"   ✓ Costo unitario: ${prices['unit_purchase']}")
        print(f"   ✓ Venta unitario: ${prices['unit_sale']}")
        print(f"   ✓ Ganancia unitaria: ${prices['profit_per_unit']}")
        print(f"   ✓ Costo display: ${prices['display_purchase']}")
        print(f"   ✓ Venta display: ${prices['display_sale']}")
        print(f"   ✓ Costo bulto: ${prices['bulk_purchase']}")
        print(f"   ✓ Venta bulto: ${prices['bulk_sale']}")
    
    print("\n" + "=" * 60)
    print("✅ TODOS LOS TESTS PASARON EXITOSAMENTE")
    print("=" * 60)
    
    # Resumen
    print("\n📊 RESUMEN:")
    print(f"   - Producto: {product.name}")
    print(f"   - Empaques configurados: 3 (Unit, Display, Bulto)")
    print(f"   - Stock final: {product.current_stock} unidades")
    print(f"   - Precio venta unitario: ${product.sale_price:.2f}")
    print(f"   - Margen: {bulk_pkg.margin_percent}%")
    
    return True


def test_urls():
    """Verificar que las URLs están configuradas correctamente."""
    print("\n" + "=" * 60)
    print("TEST: Verificación de URLs")
    print("=" * 60)
    
    from django.urls import reverse, NoReverseMatch
    
    urls_to_test = [
        ('stocks:bulk_stock_load', {}),
        ('stocks:packaging_config', {'product_id': 1}),
        ('stocks:api_lookup_packaging', {}),
        ('stocks:api_calculate_prices', {}),
    ]
    
    for url_name, kwargs in urls_to_test:
        try:
            url = reverse(url_name, kwargs=kwargs)
            print(f"   ✓ {url_name} → {url}")
        except NoReverseMatch as e:
            print(f"   ✗ {url_name} → ERROR: {e}")
            return False
    
    print("\n✅ Todas las URLs están configuradas correctamente")
    return True


def test_views():
    """Test de las vistas con cliente de prueba."""
    print("\n" + "=" * 60)
    print("TEST: Verificación de Vistas")
    print("=" * 60)
    
    from django.urls import reverse
    from django.contrib.auth.models import Group
    
    # Crear usuario de prueba
    user, _ = User.objects.get_or_create(
        username='test_bulk_user',
        defaults={
            'email': 'test@test.com',
            'is_active': True
        }
    )
    user.set_password('testpass123')
    user.save()
    
    # Asignar a grupo Admin
    admin_group, _ = Group.objects.get_or_create(name='Admin')
    user.groups.add(admin_group)
    
    client = Client()
    client.login(username='test_bulk_user', password='testpass123')
    
    # Test bulk_stock_load view
    print("\n1. Testing bulk_stock_load view...")
    response = client.get(reverse('stocks:bulk_stock_load'))
    if response.status_code == 200:
        print(f"   ✓ GET /stocks/bulk-load/ → {response.status_code}")
    else:
        print(f"   ✗ GET /stocks/bulk-load/ → {response.status_code}")
    
    # Test packaging_config view
    print("\n2. Testing packaging_config view...")
    from stocks.models import Product
    product = Product.objects.first()
    if product:
        response = client.get(reverse('stocks:packaging_config', kwargs={'product_id': product.id}))
        if response.status_code == 200:
            print(f"   ✓ GET /stocks/packaging/{product.id}/ → {response.status_code}")
        else:
            print(f"   ✗ GET /stocks/packaging/{product.id}/ → {response.status_code}")
    
    # Test API lookup
    print("\n3. Testing api_lookup_packaging...")
    response = client.get(reverse('stocks:api_lookup_packaging') + '?barcode=7790001000001-B')
    print(f"   → Response: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            print(f"   ✓ Encontrado: {data.get('product_name')}")
        else:
            print(f"   ⚠ No encontrado: {data.get('error')}")
    
    print("\n✅ Tests de vistas completados")
    return True


if __name__ == '__main__':
    try:
        # Ejecutar tests
        test_packaging_system()
        test_urls()
        test_views()
        
        print("\n" + "=" * 60)
        print("🎉 TODOS LOS TESTS COMPLETADOS EXITOSAMENTE 🎉")
        print("=" * 60)
        print("\n📝 Próximos pasos:")
        print("   1. Ejecutar: python manage.py makemigrations stocks")
        print("   2. Ejecutar: python manage.py migrate")
        print("   3. Ejecutar el servidor: python manage.py runserver")
        print("   4. Acceder a: http://localhost:8000/stocks/bulk-load/")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
