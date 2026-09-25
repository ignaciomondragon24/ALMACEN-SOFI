"""
Fase 3 del rediseño de venta por peso — Migración A (copia datos, no borra nada).

Dos cosas, sobre datos reales de producción (verificado por SSH el
2026-09-25: 8 Carameleras con producto vinculado, 71 productos marcados
`es_deposito_caramelera=True`, ambos números iguales a los del plan original
— sin drift):

1. Para cada Product con `granel_caramelera` vinculada (las 8 Carameleras
   reales), copia sus datos al Product mismo con las unidades/semántica
   NUEVAS (`current_stock`/`sale_price`/`cost_price` en kilos, no en gramos
   ni "por 100g") y desvincula la FK (`granel_caramelera = None`). Ese
   desvínculo es el corte real: a partir de acá, todo el código de checkout
   y edición (Fase 2) empieza a tratar a estos 8 productos como "nuevos" —
   la Caramelera y sus datos originales quedan intactos en la tabla vieja,
   sin usarse, como respaldo/historial.

   Fórmulas (ver `Product.price_for_grams` y su test de equivalencia
   matemática en `tests/test_weight_price_for_grams.py`):
   - current_stock = stock_gramos_actual / 1000
   - sale_price    = precio_100g * 10        (el viejo sale_price era "por
                                                100g"; el nuevo es "por kilo")
   - cost_price = purchase_price = costo_ponderado_gramo * 1000
   - oferta_price_250g = precio_cuarto / 4   (precio_cuarto es un precio por
     KILO que se aplicaba desde 250g por regla de tres — ver
     `Caramelera.calcular_precio`; dividido por 4 da el precio efectivo en
     el punto de 250g, que es lo que el nuevo `oferta_price_250g` significa)
   - sale_price_250g / sale_price_500g / oferta_price_500g quedan en 0 (no
     existía un precio propio de esos tramos en el sistema viejo — el
     "normal" de cada tramo sigue siendo proporcional al precio por kilo,
     igual que antes)

2. Para los 71 productos `es_deposito_caramelera=True` (decisión confirmada
   por Nacho, sesión 2026-09-25): pasan a ser productos comunes normales
   (`es_deposito_caramelera=False`). Esto los hace vendibles directo desde
   el POS y saca el auto-abrir-hacia-fraccionado al recibir mercadería — en
   los hechos, ya no son "piezas de depósito", son productos comunes. Su
   stock actual se conserva tal cual (ya está en la unidad que corresponde a
   un producto común, no en gramos). Sus nombres quedan impresos en el log
   del deploy para que Nacho/Sofia revisen después cuáles conviene dejar
   activos.

No se borra ninguna columna acá (eso es la Migración B, en un deploy
separado y solo después de verificar esta a mano). Los modelos y datos de
`granel` (incluida la Caramelera original) quedan intactos como historial.
"""
from decimal import Decimal

from django.db import migrations


def migrar_datos(apps, schema_editor):
    Product = apps.get_model('stocks', 'Product')

    # 1) Las 8 Carameleras reales -> datos nativos en el Product, FK suelta.
    productos_granel = Product.objects.filter(
        is_granel=True, granel_caramelera__isnull=False
    ).select_related('granel_caramelera')

    for producto in productos_granel:
        c = producto.granel_caramelera

        producto.current_stock = (c.stock_gramos_actual / Decimal('1000')).quantize(Decimal('0.001'))
        producto.sale_price = (c.precio_100g * Decimal('10')).quantize(Decimal('0.01'))
        costo_kilo = (c.costo_ponderado_gramo * Decimal('1000')).quantize(Decimal('0.01'))
        producto.cost_price = costo_kilo
        producto.purchase_price = costo_kilo

        producto.sale_price_250g = Decimal('0')
        producto.sale_price_500g = Decimal('0')
        producto.oferta_price_500g = Decimal('0')
        if c.precio_cuarto and c.precio_cuarto > 0:
            producto.oferta_price_250g = (c.precio_cuarto / Decimal('4')).quantize(Decimal('0.01'))
        else:
            producto.oferta_price_250g = Decimal('0')

        producto.granel_caramelera = None
        producto.save()

    if productos_granel:
        print(f'  Migrados {len(productos_granel)} productos por peso desde Caramelera:')
        for p in productos_granel:
            print(f'    - {p.name} (sku={p.sku}, pk={p.pk})')

    # 2) Los 71 productos "de depósito" -> productos comunes normales.
    depositos = Product.objects.filter(es_deposito_caramelera=True)
    nombres = list(depositos.values_list('name', 'sku', 'pk'))
    depositos.update(es_deposito_caramelera=False)

    if nombres:
        print(f'  Convertidos {len(nombres)} productos de depósito en productos comunes:')
        for name, sku, pk in nombres:
            print(f'    - {name} (sku={sku}, pk={pk})')


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0024_add_weight_tier_prices'),
        ('granel', '0019_resync_granel_pos_products'),
    ]

    operations = [
        migrations.RunPython(migrar_datos, migrations.RunPython.noop),
    ]
