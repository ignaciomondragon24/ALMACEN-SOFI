"""
Rediseño de venta por peso — sistema NUEVO (2026-09-25, plan
`sharded-honking-quilt.md`).

Un producto por peso "nuevo" es un `Product` con `is_granel=True` y SIN
`granel_caramelera` vinculada — se carga, se edita y se vende todo desde las
mismas pantallas que cualquier producto, sin pasar por la app `granel` ni por
el concepto de "pieza de depósito" (eliminado). Los productos por peso VIEJOS
(con Caramelera vinculada) siguen su propio camino sin cambios — ver
`tests/test_weight_sale_simple.py` y `tests/test_granel.py`.

Convenciones de unidades del sistema nuevo:
- `Product.current_stock`, `cost_price`, `sale_price`: en KILOS (con
  decimales) — no en gramos, a diferencia del sistema viejo.
- El carrito del POS sigue viajando en GRAMOS (mismo frontend que el sistema
  viejo): los servicios de checkout convierten gramos↔kilos donde hace falta.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from cashregister.models import CashRegister, CashShift, PaymentMethod
from pos.services import POSService
from purchase.models import Purchase, PurchaseItem, Supplier
from stocks.forms import ProductForm
from stocks.models import Product, ProductPackaging, StockMovement
from stocks.services import StockManagementService

User = get_user_model()


class NuevoPesoBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user(
            username='nacho_peso_nuevo', password='x', is_superuser=True, is_staff=True,
        )
        cls.user.groups.add(group)
        PaymentMethod.objects.create(name='Efectivo', code='cash', is_active=True)
        cls.register = CashRegister.objects.create(name='Caja', code='PN1', is_active=True)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def crear_producto_por_peso(self, **extra):
        data = {
            'name': 'Jamón Cocido', 'sku': 'JC-NUEVO', 'cost_price': '8000', 'sale_price': '12000',
            'current_stock': '2.5', 'min_stock': '0', 'is_active': 'on', 'is_granel': 'on',
        }
        data.update(extra)
        return self.client.post(reverse('stocks:product_create'), data)

    def nueva_transaccion(self):
        shift = CashShift.objects.create(
            cash_register=self.register, cashier=self.user,
            initial_amount=Decimal('1000'), status='open',
        )
        return POSService.create_transaction(POSService.get_or_create_session(shift))


class CreacionTests(NuevoPesoBase):
    def test_crear_producto_por_peso_no_crea_empaque_unidad(self):
        """A diferencia de un producto común, uno por peso no usa el sistema
        de Unidad/Display/Bulto — no tiene sentido para algo que se vende
        fraccionado en gramos."""
        r = self.crear_producto_por_peso()
        self.assertEqual(r.status_code, 302)
        producto = Product.objects.get(sku='JC-NUEVO')
        self.assertTrue(producto.is_granel)
        self.assertIsNone(producto.granel_caramelera_id)
        self.assertFalse(ProductPackaging.objects.filter(product=producto).exists())

    def test_crear_producto_por_peso_redirige_al_detalle_no_a_empaques(self):
        r = self.crear_producto_por_peso()
        producto = Product.objects.get(sku='JC-NUEVO')
        self.assertRedirects(r, reverse('stocks:product_detail', kwargs={'pk': producto.pk}))

    def test_stock_y_precios_quedan_en_kilos(self):
        self.crear_producto_por_peso(sale_price_250g='2900', oferta_price_500g='5000')
        producto = Product.objects.get(sku='JC-NUEVO')
        self.assertEqual(producto.current_stock, Decimal('2.5'))
        self.assertEqual(producto.sale_price, Decimal('12000.00'))
        self.assertEqual(producto.sale_price_250g, Decimal('2900'))
        self.assertEqual(producto.oferta_price_500g, Decimal('5000'))

    def test_producto_comun_sigue_creando_su_empaque_unidad(self):
        """No regresión: el flujo de siempre para productos que NO son por
        peso sigue intacto (crea Unidad, redirige a Gestionar Empaques)."""
        r = self.client.post(reverse('stocks:product_create'), {
            'name': 'Gaseosa', 'sku': 'GAS-1', 'cost_price': '500', 'sale_price': '800',
            'current_stock': '10', 'min_stock': '0', 'is_active': 'on',
        })
        producto = Product.objects.get(sku='GAS-1')
        self.assertRedirects(r, reverse('stocks:product_packaging', kwargs={'pk': producto.pk}))
        self.assertTrue(ProductPackaging.objects.filter(product=producto, packaging_type='unit').exists())


class EdicionYEmpaquesTests(NuevoPesoBase):
    def setUp(self):
        super().setUp()
        self.crear_producto_por_peso()
        self.producto = Product.objects.get(sku='JC-NUEVO')

    def test_editar_producto_por_peso_nuevo_no_redirige_a_granel(self):
        """A diferencia de una Caramelera vieja, un producto por peso nuevo
        se edita en la misma pantalla que cualquier producto."""
        r = self.client.get(reverse('stocks:product_edit', kwargs={'pk': self.producto.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertTemplateUsed(r, 'stocks/product_form.html')

    def test_gestionar_empaques_redirige_al_detalle(self):
        r = self.client.get(reverse('stocks:product_packaging', kwargs={'pk': self.producto.pk}))
        self.assertRedirects(r, reverse('stocks:product_detail', kwargs={'pk': self.producto.pk}))

    def test_detalle_muestra_precios_por_tramo_con_oferta_aplicada(self):
        self.producto.sale_price_250g = Decimal('2900')
        self.producto.oferta_price_500g = Decimal('5000')
        self.producto.save()
        r = self.client.get(reverse('stocks:product_detail', kwargs={'pk': self.producto.pk}))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['precio_250g'], Decimal('2900'))
        self.assertEqual(r.context['precio_500g'], Decimal('5000'))


class AgregarMercaderiaTests(NuevoPesoBase):
    def setUp(self):
        super().setUp()
        self.crear_producto_por_peso()
        self.producto = Product.objects.get(sku='JC-NUEVO')

    def _agregar(self, kilos, costo_kilo=None, notas=''):
        data = {'kilos': kilos, 'notas': notas}
        if costo_kilo is not None:
            data['costo_kilo'] = costo_kilo
        return self.client.post(
            reverse('stocks:product_add_stock', kwargs={'pk': self.producto.pk}), data
        )

    def test_suma_stock_y_promedia_el_costo(self):
        # 2.5kg a $8000 + 2.5kg a $10000 → promedio $9000
        self._agregar('2.5', '10000')
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.current_stock, Decimal('5.0'))
        self.assertEqual(self.producto.cost_price, Decimal('9000.00'))

    def test_el_costo_promedio_puede_bajar_a_diferencia_de_productos_comunes(self):
        """A diferencia de un producto común (que nunca promedia el costo
        hacia abajo), uno por peso sí lo hace — promedio ponderado real."""
        self._agregar('2.5', '4000')  # más barato que el costo actual ($8000)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.current_stock, Decimal('5.0'))
        self.assertEqual(self.producto.cost_price, Decimal('6000.00'))

    def test_sin_costo_nuevo_mantiene_el_costo_actual(self):
        self._agregar('1.0')
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.current_stock, Decimal('3.5'))
        self.assertEqual(self.producto.cost_price, Decimal('8000.00'))

    def test_deja_registro_en_el_historial(self):
        self._agregar('2.5', '10000', notas='Compra proveedor X')
        mov = StockMovement.objects.filter(product=self.producto).latest('created_at')
        self.assertEqual(mov.quantity, Decimal('2.5'))
        self.assertEqual(mov.notes, 'Compra proveedor X')

    def test_no_aplica_a_producto_comun(self):
        comun = Product.objects.create(
            name='Gaseosa', sku='GAS-2', cost_price=Decimal('500'), sale_price=Decimal('800'),
            current_stock=Decimal('10'),
        )
        r = self.client.post(reverse('stocks:product_add_stock', kwargs={'pk': comun.pk}), {'kilos': '1'})
        self.assertRedirects(r, reverse('stocks:product_detail', kwargs={'pk': comun.pk}))
        comun.refresh_from_db()
        self.assertEqual(comun.current_stock, Decimal('10'))

    def test_cantidad_invalida_no_rompe(self):
        r = self._agregar('no-es-un-numero')
        self.assertEqual(r.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.current_stock, Decimal('2.5'))  # sin cambios


class VentaEnPosTests(NuevoPesoBase):
    def setUp(self):
        super().setUp()
        self.crear_producto_por_peso()  # 2.5kg a $12000/kg, costo $8000/kg
        self.producto = Product.objects.get(sku='JC-NUEVO')

    def _agregar(self, tx, gramos):
        body = {'transaction_id': tx.id, 'product_id': self.producto.id, 'quantity': gramos}
        return self.client.post(reverse('pos:api_cart_add'), json.dumps(body),
                                 content_type='application/json')

    def _cobrar(self, tx):
        tx.refresh_from_db()
        return self.client.post(reverse('pos:api_checkout'), json.dumps({
            'transaction_id': tx.id,
            'payments': [{'method_code': 'cash', 'amount': float(tx.total)}],
        }), content_type='application/json')

    def test_venta_completa_descuenta_stock_en_kilos(self):
        tx = self.nueva_transaccion()
        self.assertEqual(self._agregar(tx, 250).status_code, 200)
        tx.refresh_from_db()
        self.assertEqual(tx.total, Decimal('3000.00'))  # 250g proporcional a $12000/kg
        r = self._cobrar(tx)
        self.assertEqual(r.status_code, 200, r.content)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.current_stock, Decimal('2.250'))

    def test_usa_precio_de_tramo_con_oferta(self):
        self.producto.oferta_price_250g = Decimal('2500')
        self.producto.save()
        tx = self.nueva_transaccion()
        self.assertEqual(self._agregar(tx, 250).status_code, 200)
        tx.refresh_from_db()
        self.assertEqual(tx.total, Decimal('2500.00'))

    def test_sin_stock_avisa_claro_al_agregar(self):
        self.producto.current_stock = Decimal('0')
        self.producto.save()
        tx = self.nueva_transaccion()
        r = self._agregar(tx, 100)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Agregar Mercadería', r.json()['error'])

    def test_no_deja_pasarse_del_stock(self):
        tx = self.nueva_transaccion()
        r = self._agregar(tx, 3000)  # solo hay 2.5kg = 2500g
        self.assertEqual(r.status_code, 400)

    def test_venta_al_costo_descuenta_stock_correctamente(self):
        from pos.services import CartService, CheckoutService
        tx = self.nueva_transaccion()
        CartService.add_item(tx, self.producto.id, quantity=250)
        # 250g al costo de $8000/kg = $2000 (costo por gramo * gramos)
        ok, result = CheckoutService.process_cost_sale(tx.id, payments=[
            {'method_code': 'cash', 'amount': 2000},
        ], employee_note='consumo')
        self.assertTrue(ok, result)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.current_stock, Decimal('2.250'))


class OrdenDeCompraTests(NuevoPesoBase):
    """Encontrados y arreglados al escribir esta clase (`purchase/models.py`
    y `purchase/views.py` solo reconocían "por peso" al viejo estilo, con
    Caramelera vinculada — bloqueaban la orden con "se compra por unidad" y
    el buscador no mostraba costo/precio para un producto por peso nuevo)."""

    def setUp(self):
        super().setUp()
        self.crear_producto_por_peso()  # 2.5kg a $12000/kg, costo $8000/kg
        self.producto = Product.objects.get(sku='JC-NUEVO')
        self.supplier = Supplier.objects.create(name='Fiambres del Sur')

    def _crear_oc(self, items):
        return self.client.post(
            reverse('purchase:purchase_create'),
            data=json.dumps({'supplier_id': self.supplier.pk, 'items': items, 'tax_percent': 0}),
            content_type='application/json',
        )

    def test_orden_en_kilos_con_decimales_no_pide_entero(self):
        r = self._crear_oc([{'product_id': self.producto.pk, 'quantity': '1.5', 'unit_cost': '9000'}])
        self.assertEqual(r.status_code, 200, r.content)
        item = PurchaseItem.objects.get()
        self.assertEqual(item.quantity, Decimal('1.500'))
        self.assertEqual(item.subtotal, Decimal('13500.00'))

    def test_recibir_suma_al_stock_y_promedia_el_costo(self):
        self._crear_oc([{'product_id': self.producto.pk, 'quantity': '2.5', 'unit_cost': '10000'}])
        oc = Purchase.objects.get()
        r = self.client.post(reverse('purchase:purchase_receive', args=[oc.pk]))
        self.assertEqual(r.status_code, 302)
        self.producto.refresh_from_db()
        # 2.5kg@8000 + 2.5kg@10000 -> 5kg promedio $9000
        self.assertEqual(self.producto.current_stock, Decimal('5.000'))
        self.assertEqual(self.producto.cost_price, Decimal('9000.00'))

    def test_buscador_de_la_orden_da_costo_y_precio_por_kilo_directo_del_producto(self):
        r = self.client.get(reverse('purchase:api_search_products'), {'q': 'jamón'})
        prod = r.json()['results'][0]
        self.assertTrue(prod['by_weight'])
        self.assertEqual(Decimal(prod['cost_price']), Decimal('8000.00'))
        self.assertEqual(Decimal(prod['sale_price']), Decimal('12000.00'))
        self.assertEqual(prod['packagings'], [])


class PromocionesTests(NuevoPesoBase):
    """Portado de `tests/test_weight_purchases.py` (retirado junto con las
    URLs de `granel`): el motor de promociones solo aplica `simple_discount`
    a líneas por peso — 2x1/combos/precio fijo regalarían plata contando
    gramos como si fueran unidades. La lógica en sí (`promotions/engine.py`)
    no cambió con el rediseño, esto solo prueba que sigue enganchada bien al
    producto por peso nuevo."""

    def setUp(self):
        super().setUp()
        self.crear_producto_por_peso()  # 2.5kg a $12000/kg
        self.producto = Product.objects.get(sku='JC-NUEVO')
        self.gaseosa = Product.objects.create(
            name='Gaseosa', sku='GAS-PROMO', cost_price=Decimal('500'),
            sale_price=Decimal('800'), current_stock=Decimal('10'),
        )

    def _linea_peso(self, gramos=250):
        return {'item_id': 1, 'product_id': self.producto.pk, 'quantity': gramos,
                'unit_price': 12.0, 'packaging_type': 'unit', 'by_weight': True}

    def test_2x1_no_regala_plata_en_lineas_por_peso(self):
        from promotions.engine import PromotionEngine
        from promotions.models import Promotion, PromotionProduct
        promo = Promotion.objects.create(
            name='2x1', promo_type='nxm', status='active',
            quantity_required=2, quantity_charged=1)
        PromotionProduct.objects.create(promotion=promo, product=self.producto)
        r = PromotionEngine.calculate_cart([self._linea_peso(250)])
        self.assertEqual(r['discount_total'], 0)

    def test_precio_fijo_por_cantidad_tampoco(self):
        from promotions.engine import PromotionEngine
        from promotions.models import Promotion, PromotionProduct
        promo = Promotion.objects.create(
            name='2 x $500', promo_type='nx_fixed_price', status='active',
            quantity_required=2, final_price=Decimal('500'))
        PromotionProduct.objects.create(promotion=promo, product=self.producto)
        r = PromotionEngine.calculate_cart([self._linea_peso(250)])
        self.assertEqual(r['discount_total'], 0)

    def test_descuento_porcentual_si_aplica_al_peso(self):
        from promotions.engine import PromotionEngine
        from promotions.models import Promotion, PromotionProduct
        promo = Promotion.objects.create(
            name='Jamón -20%', promo_type='simple_discount', status='active',
            discount_percent=Decimal('20'))
        PromotionProduct.objects.create(promotion=promo, product=self.producto)
        r = PromotionEngine.calculate_cart([self._linea_peso(250)])
        self.assertAlmostEqual(r['discount_total'], 600.0)  # 20% de $3.000

    def test_promos_por_unidad_siguen_funcionando_en_productos_comunes(self):
        from promotions.engine import PromotionEngine
        from promotions.models import Promotion, PromotionProduct
        promo = Promotion.objects.create(
            name='2x1 gaseosa', promo_type='nxm', status='active',
            quantity_required=2, quantity_charged=1)
        PromotionProduct.objects.create(promotion=promo, product=self.gaseosa)
        r = PromotionEngine.calculate_cart([
            {'item_id': 2, 'product_id': self.gaseosa.pk, 'quantity': 2, 'unit_price': 800,
             'packaging_type': 'unit', 'by_weight': False}])
        self.assertAlmostEqual(r['discount_total'], 800.0)

    def test_en_el_pos_el_descuento_porcentual_baja_el_total(self):
        from promotions.models import Promotion, PromotionProduct
        from pos.services import CartService
        promo = Promotion.objects.create(
            name='Jamón -20%', promo_type='simple_discount', status='active',
            discount_percent=Decimal('20'))
        PromotionProduct.objects.create(promotion=promo, product=self.producto)
        tx = self.nueva_transaccion()
        CartService.add_item(tx, self.producto.pk, Decimal('250'))
        tx.refresh_from_db()
        self.assertEqual(tx.total, Decimal('2400.00'))  # 250g × $12 = 3000 − 20%


class PedidoSugeridoTests(NuevoPesoBase):
    """Portado de `tests/test_weight_purchases.py`. Encontrado y arreglado al
    escribir esto: `_low_stock_suggestions_for_supplier` (purchase/views.py)
    asumía que el stock/mínimo de CUALQUIER producto por peso estaban en
    gramos (cierto solo para el sistema viejo) — para un producto nuevo ya
    están en kilos, sin convertir."""

    def setUp(self):
        super().setUp()
        self.crear_producto_por_peso(current_stock='2.5', min_stock='4')
        self.producto = Product.objects.get(sku='JC-NUEVO')
        self.supplier = Supplier.objects.create(name='Fiambres del Sur', order_day='mon')
        from purchase.models import SupplierProduct
        SupplierProduct.objects.create(supplier=self.supplier, product=self.producto, cost_price=Decimal('9000'))

    def test_sugiere_en_kilos_cuando_queda_poco(self):
        # mínimo 4kg, hay 2,5kg -> faltan 1,5kg
        r = self.client.get(reverse('purchase:purchase_suggested') + '?all=1')
        self.assertContains(r, 'Jamón Cocido')
        self.assertContains(r, '2,5 kg')   # stock actual
        self.assertContains(r, '4 kg')     # mínimo
        self.assertContains(r, '1,5 kg')   # cantidad sugerida
        self.assertContains(r, '/ kg')

    def test_generar_orden_borrador_en_kilos(self):
        r = self.client.post(reverse('purchase:purchase_suggested_generate', args=[self.supplier.pk]))
        self.assertEqual(r.status_code, 302)
        item = PurchaseItem.objects.get(product=self.producto)
        self.assertEqual(item.quantity, Decimal('1.500'))
        self.assertEqual(item.unit_cost, Decimal('9000.00'))
        oc = Purchase.objects.get()
        r = self.client.post(reverse('purchase:purchase_receive', args=[oc.pk]))
        self.assertEqual(r.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.current_stock, Decimal('4.000'))


class InventarioTests(NuevoPesoBase):
    def setUp(self):
        super().setUp()
        self.crear_producto_por_peso()
        self.producto = Product.objects.get(sku='JC-NUEVO')

    def test_conteo_fisico_acepta_decimales(self):
        r = self.client.post(reverse('stocks:inventory_count', kwargs={'pk': self.producto.pk}), {
            'new_quantity': '2.750', 'reason': 'conteo_fisico', 'notes': '',
        })
        self.assertEqual(r.status_code, 302)
        self.producto.refresh_from_db()
        self.assertEqual(self.producto.current_stock, Decimal('2.750'))
