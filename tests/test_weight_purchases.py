"""
Venta por peso + proveedores / órdenes de compra / promociones (2026-09-20).

Antes las compras no sabían nada del peso: la cantidad de la orden era un entero,
y al recibir la mercadería se sumaba al Product (que el POS ya no mira) en vez de
a la caramelera. Resultado: se compraba jamón, se recibía, y en la caja "sin stock".

Ahora, para un producto por peso:
- la orden va en KILOS (con decimales) y el costo es por kilo;
- al recibir, entra a la caramelera (costo ponderado) y deja kardex, lote y gasto;
- el pedido sugerido y el catálogo del proveedor hablan en kilos;
- las promos que cuentan unidades no se aplican (solo el descuento porcentual).
"""
import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from expenses.models import Expense
from granel.models import Caramelera
from granel.services import GranelService
from promotions.engine import PromotionEngine
from promotions.models import Promotion, PromotionProduct
from purchase.models import Purchase, PurchaseItem, Supplier, SupplierProduct
from stocks.models import Product, StockBatch, StockMovement
from stocks.services import StockManagementService

User = get_user_model()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user('compras_peso', password='x', is_superuser=True, is_staff=True)
        cls.user.groups.add(group)
        cls.supplier = Supplier.objects.create(name='Fiambres del Sur')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        # Jamón: 2,5 kg a $8.000/kg, se vende a $12.000/kg
        self.client.post(reverse('granel:caramelera_create'), {
            'nombre': 'Jamón cocido', 'precio_kg': '12000', 'costo_kg': '8000',
            'stock_inicial': '2.5', 'stock_unidad': 'kg',
        })
        self.car = Caramelera.objects.get()
        self.jamon = Product.objects.get(is_granel=True)
        self.gaseosa = Product.objects.create(
            name='Gaseosa', sku='GAS-1', cost_price=Decimal('500'),
            sale_price=Decimal('800'), current_stock=Decimal('10'),
        )

    def crear_oc(self, items):
        r = self.client.post(
            reverse('purchase:purchase_create'),
            data=json.dumps({'supplier_id': self.supplier.pk, 'items': items, 'tax_percent': 0}),
            content_type='application/json',
        )
        return r

    def item_peso(self, kilos='2.5', costo='9000', **extra):
        d = {'product_id': self.jamon.pk, 'quantity': kilos, 'unit_cost': costo}
        d.update(extra)
        return d

    def recibir(self, purchase, **post):
        return self.client.post(reverse('purchase:purchase_receive', args=[purchase.pk]), post)


class OrdenDeCompraTests(Base):
    def test_orden_en_kilos_con_decimales(self):
        r = self.crear_oc([self.item_peso('2.5', '9000')])
        self.assertEqual(r.status_code, 200, r.content)
        item = PurchaseItem.objects.get()
        self.assertEqual(item.quantity, Decimal('2.500'))
        self.assertEqual(item.subtotal, Decimal('22500.00'))
        self.assertEqual(Purchase.objects.get().total, Decimal('22500.00'))
        self.assertEqual(item.cantidad_texto, '2,5 kg')

    def test_producto_comun_sigue_pidiendo_entero(self):
        r = self.crear_oc([{'product_id': self.gaseosa.pk, 'quantity': '2.5', 'unit_cost': '400'}])
        self.assertEqual(r.status_code, 400)
        self.assertIn('número entero', r.json()['error'])
        self.assertFalse(Purchase.objects.exists())

    def test_producto_comun_con_entero_funciona_igual_que_antes(self):
        r = self.crear_oc([{'product_id': self.gaseosa.pk, 'quantity': 6, 'unit_cost': '400'}])
        self.assertEqual(r.status_code, 200)
        item = PurchaseItem.objects.get()
        self.assertEqual(item.subtotal, Decimal('2400.00'))
        self.assertEqual(item.cantidad_texto, '6')

    def test_buscador_de_la_orden_da_costo_y_precio_por_kilo(self):
        r = self.client.get(reverse('purchase:api_search_products'), {'q': 'jamon'})
        prod = r.json()['results'][0]
        self.assertTrue(prod['by_weight'])
        self.assertEqual(Decimal(prod['cost_price']), Decimal('8000.00'))
        self.assertEqual(Decimal(prod['sale_price']), Decimal('12000.00'))
        self.assertEqual(prod['packagings'], [])
        comun = self.client.get(reverse('purchase:api_search_products'), {'q': 'gaseosa'}).json()['results'][0]
        self.assertFalse(comun['by_weight'])

    def test_detalle_recepcion_y_edicion_muestran_kilos(self):
        self.crear_oc([self.item_peso('2.5', '9000')])
        oc = Purchase.objects.get()
        self.assertContains(self.client.get(reverse('purchase:purchase_detail', args=[oc.pk])), '2,5 kg')
        self.assertContains(self.client.get(reverse('purchase:purchase_receive', args=[oc.pk])), '2,5 kg')
        edit = self.client.get(reverse('purchase:purchase_edit', args=[oc.pk]))
        self.assertEqual(edit.status_code, 200)
        self.assertContains(edit, 'value="2.5"')  # no "2.500"


class RecepcionTests(Base):
    def test_recibir_suma_a_la_caramelera_y_promedia_el_costo(self):
        self.crear_oc([self.item_peso('2.5', '9000')])
        oc = Purchase.objects.get()
        r = self.recibir(oc)
        self.assertEqual(r.status_code, 302)
        self.car.refresh_from_db()
        self.assertEqual(self.car.stock_gramos_actual, Decimal('5000.00'))
        # (2500 × 8 + 2500 × 9) / 5000 = 8,5 $/g
        self.assertEqual(self.car.costo_ponderado_gramo, Decimal('8.500000'))
        self.jamon.refresh_from_db()
        self.assertEqual(self.jamon.current_stock, Decimal('5000.000'))
        self.assertEqual(self.jamon.weighted_avg_cost_per_gram, Decimal('8.5000'))

    def test_recibir_deja_kardex_gasto_y_estado(self):
        self.crear_oc([self.item_peso('2.5', '9000')])
        oc = Purchase.objects.get()
        self.recibir(oc)
        oc.refresh_from_db()
        self.assertEqual(oc.status, 'received')
        self.assertEqual(PurchaseItem.objects.get().received_quantity, Decimal('2.500'))
        mov = StockMovement.objects.filter(product=self.jamon, movement_type='purchase').latest('id')
        self.assertEqual(mov.quantity, Decimal('2500.000'))
        self.assertEqual(mov.stock_after, Decimal('5000.00'))
        self.assertEqual(Expense.objects.get().amount, Decimal('22500.00'))

    def test_no_se_duplica_el_stock_en_el_producto(self):
        """El bug de fondo: antes se sumaba al Product y la caramelera quedaba igual."""
        self.crear_oc([self.item_peso('1', '9000')])
        self.recibir(Purchase.objects.get())
        self.car.refresh_from_db()
        self.jamon.refresh_from_db()
        self.assertEqual(self.car.stock_gramos_actual, self.jamon.current_stock)

    def test_precio_de_venta_por_kilo_de_la_orden_actualiza_el_precio(self):
        self.crear_oc([self.item_peso('1', '9000', sale_price='13000')])
        self.recibir(Purchase.objects.get())
        self.car.refresh_from_db()
        self.assertEqual(self.car.precio_kilo, Decimal('13000.00'))
        self.jamon.refresh_from_db()
        self.assertEqual(self.jamon.sale_price, Decimal('1300.00'))  # por 100g

    def test_orden_mixta_peso_y_unidades(self):
        self.crear_oc([self.item_peso('1', '9000'),
                       {'product_id': self.gaseosa.pk, 'quantity': 6, 'unit_cost': '400'}])
        oc = Purchase.objects.get()
        self.recibir(oc)
        self.gaseosa.refresh_from_db()
        self.car.refresh_from_db()
        self.assertEqual(self.gaseosa.current_stock, Decimal('16'))
        self.assertEqual(self.car.stock_gramos_actual, Decimal('3500.00'))

    def test_vencimiento_crea_lote_y_la_venta_lo_descuenta(self):
        self.crear_oc([self.item_peso('2', '9000')])
        oc = Purchase.objects.get()
        item = oc.items.get()
        vence = date.today() + timedelta(days=5)
        self.recibir(oc, **{f'expiration_date_{item.id}': vence.isoformat()})
        lote = StockBatch.objects.get(product=self.jamon)
        self.assertEqual(lote.quantity_remaining, Decimal('2000.000'))
        self.assertEqual(lote.expiration_date, vence)
        GranelService.registrar_venta(self.car.pk, Decimal('500'), Decimal('6000'))
        lote.refresh_from_db()
        self.assertEqual(lote.quantity_remaining, Decimal('1500.000'))

    def test_sin_vencimiento_no_crea_lotes(self):
        self.crear_oc([self.item_peso('2', '9000')])
        self.recibir(Purchase.objects.get())
        self.assertFalse(StockBatch.objects.filter(product=self.jamon).exists())


class OtrosCaminosDeStockTests(Base):
    """Cualquier camino que toque el stock del producto por peso va a la caramelera."""

    def test_add_stock_generico_va_a_la_caramelera(self):
        StockManagementService.add_stock(self.jamon, Decimal('500'), cost=Decimal('9'), reference='X')
        self.car.refresh_from_db()
        self.assertEqual(self.car.stock_gramos_actual, Decimal('3000.00'))
        self.jamon.refresh_from_db()
        self.assertEqual(self.jamon.current_stock, Decimal('3000.000'))

    def test_ajuste_o_conteo_fisico_va_a_la_caramelera(self):
        StockManagementService.adjust_stock(self.jamon, Decimal('1800'), 'Conteo físico', user=self.user)
        self.car.refresh_from_db()
        self.assertEqual(self.car.stock_gramos_actual, Decimal('1800.00'))
        self.jamon.refresh_from_db()
        self.assertEqual(self.jamon.current_stock, Decimal('1800.000'))
        # y se puede seguir vendiendo hasta ese stock
        GranelService.registrar_venta(self.car.pk, Decimal('1800'), Decimal('21600'))

    def test_producto_comun_no_cambia(self):
        StockManagementService.add_stock(self.gaseosa, Decimal('5'), cost=Decimal('400'))
        self.gaseosa.refresh_from_db()
        self.assertEqual(self.gaseosa.current_stock, Decimal('15'))


class PedidoSugeridoTests(Base):
    def setUp(self):
        super().setUp()
        self.supplier.order_day = 'mon'
        self.supplier.save()
        SupplierProduct.objects.create(supplier=self.supplier, product=self.jamon, cost_price=Decimal('9000'))
        SupplierProduct.objects.create(supplier=self.supplier, product=self.gaseosa, cost_price=Decimal('400'))

    def _minimo(self, kg):
        self.client.post(reverse('granel:caramelera_edit', args=[self.car.pk]), {
            'nombre': 'Jamón cocido', 'precio_kg': '12000', 'stock_minimo_kg': kg,
        })

    def test_minimo_en_kilos_se_guarda_en_gramos_y_vuelve_a_mostrarse(self):
        self._minimo('2')
        self.jamon.refresh_from_db()
        self.assertEqual(self.jamon.min_stock, 2000)
        r = self.client.get(reverse('granel:caramelera_edit', args=[self.car.pk]))
        self.assertContains(r, 'value="2.000"')

    def test_sugiere_en_kilos_cuando_queda_poco(self):
        self._minimo('4')       # avisar debajo de 4 kg; hay 2,5 kg → faltan 1,5 kg
        r = self.client.get(reverse('purchase:purchase_suggested') + '?all=1')
        self.assertContains(r, 'Jamón cocido')
        self.assertContains(r, '2,5 kg')      # stock actual
        self.assertContains(r, '4 kg')        # mínimo
        self.assertContains(r, '1,5 kg')      # cantidad sugerida
        self.assertContains(r, '/ kg')

    def test_no_sugiere_si_hay_suficiente(self):
        self._minimo('1')
        r = self.client.get(reverse('purchase:purchase_suggested') + '?all=1')
        self.assertNotContains(r, 'Jamón cocido')

    def test_generar_orden_borrador_en_kilos(self):
        self._minimo('4')
        r = self.client.post(reverse('purchase:purchase_suggested_generate', args=[self.supplier.pk]))
        self.assertEqual(r.status_code, 302)
        item = PurchaseItem.objects.get(product=self.jamon)
        self.assertEqual(item.quantity, Decimal('1.500'))
        self.assertEqual(item.unit_cost, Decimal('9000.00'))
        self.assertEqual(item.subtotal, Decimal('13500.00'))
        # y la orden generada se puede recibir
        oc = Purchase.objects.get()
        self.recibir(oc)
        self.car.refresh_from_db()
        self.assertEqual(self.car.stock_gramos_actual, Decimal('4000.00'))

    def test_catalogo_del_proveedor_muestra_kilos(self):
        r = self.client.get(reverse('purchase:supplier_products', args=[self.supplier.pk]))
        self.assertContains(r, '/ kg')
        self.assertContains(r, '2,5 kg')


class PromocionesTests(Base):
    def _linea_peso(self, gramos=250):
        return {'item_id': 1, 'product_id': self.jamon.pk, 'quantity': gramos,
                'unit_price': 12.0, 'packaging_type': 'unit', 'by_weight': True}

    def test_2x1_no_regala_plata_en_lineas_por_peso(self):
        promo = Promotion.objects.create(
            name='2x1', promo_type='nxm', status='active',
            quantity_required=2, quantity_charged=1)
        PromotionProduct.objects.create(promotion=promo, product=self.jamon)
        r = PromotionEngine.calculate_cart([self._linea_peso(250)])
        self.assertEqual(r['discount_total'], 0)

    def test_precio_fijo_por_cantidad_tampoco(self):
        promo = Promotion.objects.create(
            name='2 x $500', promo_type='nx_fixed_price', status='active',
            quantity_required=2, final_price=Decimal('500'))
        PromotionProduct.objects.create(promotion=promo, product=self.jamon)
        r = PromotionEngine.calculate_cart([self._linea_peso(250)])
        self.assertEqual(r['discount_total'], 0)

    def test_descuento_porcentual_si_aplica_al_peso(self):
        promo = Promotion.objects.create(
            name='Jamón -20%', promo_type='simple_discount', status='active',
            discount_percent=Decimal('20'))
        PromotionProduct.objects.create(promotion=promo, product=self.jamon)
        r = PromotionEngine.calculate_cart([self._linea_peso(250)])
        self.assertAlmostEqual(r['discount_total'], 600.0)  # 20% de $3.000

    def test_promos_por_unidad_siguen_funcionando_en_productos_comunes(self):
        promo = Promotion.objects.create(
            name='2x1 gaseosa', promo_type='nxm', status='active',
            quantity_required=2, quantity_charged=1)
        PromotionProduct.objects.create(promotion=promo, product=self.gaseosa)
        r = PromotionEngine.calculate_cart([
            {'item_id': 2, 'product_id': self.gaseosa.pk, 'quantity': 2, 'unit_price': 800,
             'packaging_type': 'unit', 'by_weight': False}])
        self.assertAlmostEqual(r['discount_total'], 800.0)

    def test_en_el_pos_el_descuento_porcentual_baja_el_total(self):
        from cashregister.models import CashRegister, CashShift
        from pos.services import CartService, POSService
        promo = Promotion.objects.create(
            name='Jamón -20%', promo_type='simple_discount', status='active',
            discount_percent=Decimal('20'))
        PromotionProduct.objects.create(promotion=promo, product=self.jamon)
        reg = CashRegister.objects.create(name='C', code='C9', is_active=True)
        shift = CashShift.objects.create(cash_register=reg, cashier=self.user,
                                         initial_amount=Decimal('0'), status='open')
        tx = POSService.create_transaction(POSService.get_or_create_session(shift))
        item, _ = CartService.add_item(tx, self.jamon.pk, Decimal('250'))
        tx.refresh_from_db()
        self.assertEqual(tx.total, Decimal('2400.00'))  # 250g × $12 = 3000 − 20%
