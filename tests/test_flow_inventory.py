"""
Flujo: inventario del día a día — crear/editar/dar de baja productos, categorías,
conteo físico, empaques (unidad / display / bulto) con su venta en la caja, movimientos,
lista de precios, stock bajo, vencimientos, y que los productos por peso no se puedan
desincronizar desde Inventario.
"""
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from cashregister.models import CashRegister, CashShift, PaymentMethod
from granel.models import Caramelera
from pos.services import CartService, POSService
from stocks.models import (
    Product, ProductCategory, ProductPackaging, StockBatch, StockMovement,
)

User = get_user_model()


class InvBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        PaymentMethod.get_default_methods()
        cls.dueña = User.objects.create_user('dueña_inv', password='x')
        cls.dueña.groups.add(Group.objects.get_or_create(name='Admin')[0])
        cls.encargada = User.objects.create_user('enc_inv', password='x')
        cls.encargada.groups.add(Group.objects.get_or_create(name='Cajero Manager')[0])
        cls.cajera = User.objects.create_user('caj_inv', password='x')
        cls.cajera.groups.add(Group.objects.get_or_create(name='Cashier')[0])

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.dueña)

    def alta(self, **extra):
        data = {'name': 'Yerba 1kg', 'sku': '', 'barcode': '7790000000123', 'cost_price': '2000',
                'sale_price': '3000', 'current_stock': '10', 'min_stock': '3', 'is_active': 'true',
                'weight_per_unit_grams': ''}
        data.update(extra)
        return self.c.post(reverse('stocks:product_create'), data)


class ProductosTests(InvBase):
    def test_crear_producto_con_stock_y_empaque_unidad(self):
        r = self.alta()
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['form'].errors)
        p = Product.objects.get(barcode='7790000000123')
        self.assertEqual(p.current_stock, Decimal('10'))
        self.assertEqual(p.sale_price, Decimal('3000'))
        unit = p.packagings.get(packaging_type='unit')
        self.assertEqual(unit.sale_price, Decimal('3000'))
        self.assertEqual(unit.barcode, '7790000000123')

    def test_codigo_de_barras_repetido_se_rechaza(self):
        self.alta()
        r = self.alta(name='Otra yerba', sku='OTRA-1')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Product.objects.count(), 1)

    def test_hay_que_indicar_codigo_o_sku(self):
        r = self.alta(barcode='', sku='')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Product.objects.exists())

    def test_solo_con_sku_tambien_se_puede(self):
        r = self.alta(barcode='', sku='YER-01')
        self.assertEqual(r.status_code, 302)
        self.assertTrue(Product.objects.filter(sku='YER-01').exists())

    def test_editar_precio_se_refleja_en_la_caja(self):
        self.alta()
        p = Product.objects.get()
        self.c.post(reverse('stocks:product_edit', args=[p.pk]), {
            'name': 'Yerba 1kg', 'sku': p.sku, 'barcode': p.barcode, 'cost_price': '2200',
            'sale_price': '3300', 'current_stock': '10', 'min_stock': '3', 'is_active': 'true',
            'weight_per_unit_grams': ''})
        p.refresh_from_db()
        self.assertEqual(p.sale_price, Decimal('3300'))
        self.assertEqual(p.packagings.get(packaging_type='unit').sale_price, Decimal('3300'))
        pos = self.c.get(reverse('pos:api_search'), {'q': 'yerba'}).json()['products'][0]
        self.assertEqual(pos['unit_price'], 3300.0)

    def test_editar_no_pisa_el_stock_aunque_el_navegador_mande_uno_viejo(self):
        """Escenario real: abro la edición (stock 10), la cajera vende 3, guardo la edición."""
        self.alta()
        p = Product.objects.get()
        Product.objects.filter(pk=p.pk).update(current_stock=Decimal('7'))     # venta mientras se editaba
        r = self.c.post(reverse('stocks:product_edit', args=[p.pk]), {
            'name': 'Yerba', 'sku': p.sku, 'barcode': p.barcode, 'cost_price': '2000', 'sale_price': '3100',
            'current_stock': '10', 'min_stock': '3', 'is_active': 'true', 'weight_per_unit_grams': ''})
        self.assertEqual(r.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.sale_price, Decimal('3100'))          # el resto sí se guarda
        self.assertEqual(p.current_stock, Decimal('7'))          # y el stock real no se pisa

    def test_dar_de_baja_lo_saca_de_la_caja_y_libera_el_codigo(self):
        self.alta()
        p = Product.objects.get()
        self.c.post(reverse('stocks:product_delete', args=[p.pk]))
        p.refresh_from_db()
        self.assertFalse(p.is_active)
        self.assertEqual(self.c.get(reverse('pos:api_search'), {'q': 'yerba'}).json()['products'], [])
        # el mismo código se puede volver a usar
        self.assertEqual(self.alta(name='Yerba nueva', sku='').status_code, 302)

    def test_borrado_definitivo_solo_de_lo_inactivo(self):
        self.alta()
        p = Product.objects.get()
        self.c.post(reverse('stocks:product_hard_delete', args=[p.pk]))
        self.assertTrue(Product.objects.filter(pk=p.pk).exists())        # activo: no se borra
        self.c.post(reverse('stocks:product_delete', args=[p.pk]))
        self.c.post(reverse('stocks:product_hard_delete', args=[p.pk]))
        self.assertFalse(Product.objects.filter(pk=p.pk).exists())

    def test_no_se_borra_definitivamente_lo_que_ya_se_vendio(self):
        self.alta()
        p = Product.objects.get()
        reg = CashRegister.objects.create(name='C', code='C1', is_active=True)
        shift = CashShift.objects.create(cash_register=reg, cashier=self.dueña, initial_amount=0, status='open')
        tx = POSService.create_transaction(POSService.get_or_create_session(shift))
        CartService.add_item(tx, p.pk, Decimal('1'))
        self.c.post(reverse('stocks:product_delete', args=[p.pk]))
        self.c.post(reverse('stocks:product_hard_delete', args=[p.pk]))
        self.assertTrue(Product.objects.filter(pk=p.pk).exists())

    def test_listado_busqueda_y_detalle(self):
        self.alta()
        p = Product.objects.get()
        self.assertContains(self.c.get(reverse('stocks:product_list')), 'Yerba 1kg')
        self.assertContains(self.c.get(reverse('stocks:product_list'), {'search': 'yerba'}), 'Yerba 1kg')
        self.assertContains(self.c.get(reverse('stocks:product_detail', args=[p.pk])), 'Yerba 1kg')
        self.assertEqual(self.c.get(reverse('stocks:api_search'), {'q': 'yer'}).status_code, 200)

    def test_generador_de_codigos_de_barras(self):
        r = self.c.get(reverse('stocks:generate_barcode'))
        self.assertEqual(len(r.json()['barcode']), 13)

    def test_la_cajera_no_puede_crear_ni_editar(self):
        cj = Client()
        cj.force_login(self.cajera)
        self.assertIn(cj.get(reverse('stocks:product_create')).status_code, (302, 403))
        self.assertEqual(Product.objects.count(), 0)


class CategoriasTests(InvBase):
    def test_crear_editar_y_listar(self):
        r = self.c.post(reverse('stocks:category_create'), {'name': 'Fiambres', 'description': '', 'default_margin_percent': '35', 'color': '#ff0000', 'is_active': 'on'})
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['form'].errors)
        cat = ProductCategory.objects.get(name='Fiambres')
        self.c.post(reverse('stocks:category_edit', args=[cat.pk]), {'name': 'Fiambres y quesos', 'description': '', 'default_margin_percent': '40', 'color': '#ff0000', 'is_active': 'on'})
        cat.refresh_from_db()
        self.assertEqual(cat.name, 'Fiambres y quesos')
        self.assertContains(self.c.get(reverse('stocks:category_list')), 'Fiambres y quesos')

    def test_producto_dentro_de_una_categoria(self):
        cat = ProductCategory.objects.create(name='Almacén')
        self.alta(category=cat.pk)
        self.assertEqual(Product.objects.get().category, cat)


class StockTests(InvBase):
    def setUp(self):
        super().setUp()
        self.alta()
        self.p = Product.objects.get()

    def test_conteo_fisico_corrige_el_stock_y_deja_registro(self):
        r = self.c.post(reverse('stocks:inventory_count', args=[self.p.pk]), {
            'new_quantity': '7', 'reason': 'conteo_fisico', 'notes': 'faltaban 3'})
        self.assertEqual(r.status_code, 302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('7'))
        mov = StockMovement.objects.filter(product=self.p).latest('id')
        self.assertEqual(mov.movement_type, 'adjustment_out')
        self.assertEqual(mov.quantity, Decimal('-3'))
        self.assertIn('Conteo', mov.reference)
        self.assertEqual(mov.notes, 'faltaban 3')

    def test_conteo_hacia_arriba(self):
        self.c.post(reverse('stocks:inventory_count', args=[self.p.pk]), {'new_quantity': '25', 'reason': 'correccion_error'})
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('25'))
        self.assertEqual(StockMovement.objects.filter(product=self.p).latest('id').movement_type, 'adjustment_in')

    def test_conteo_invalido_no_cambia_nada(self):
        self.c.post(reverse('stocks:inventory_count', args=[self.p.pk]), {'new_quantity': 'abc', 'reason': 'otro'})
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('10'))

    def test_historial_de_movimientos(self):
        self.c.post(reverse('stocks:inventory_count', args=[self.p.pk]), {'new_quantity': '8', 'reason': 'otro'})
        self.assertEqual(self.c.get(reverse('stocks:movement_list')).status_code, 200)
        self.assertEqual(self.c.get(reverse('stocks:product_movements', args=[self.p.pk])).status_code, 200)

    def test_stock_bajo(self):
        self.c.post(reverse('stocks:inventory_count', args=[self.p.pk]), {'new_quantity': '2', 'reason': 'otro'})
        self.assertContains(self.c.get(reverse('stocks:low_stock')), 'Yerba 1kg')

    def test_lista_de_precios_y_costos(self):
        self.assertContains(self.c.get(reverse('stocks:price_list')), 'Yerba 1kg')
        self.assertEqual(self.c.get(reverse('stocks:cost_history')).status_code, 200)
        self.assertEqual(self.c.get(reverse('stocks:product_costs', args=[self.p.pk])).status_code, 200)

    def test_vencimientos_muestra_lotes_proximos(self):
        StockBatch.objects.create(
            product=self.p, quantity_purchased=Decimal('5'), quantity_remaining=Decimal('5'),
            purchase_price=Decimal('2000'), purchased_at=timezone.now(),
            expiration_date=timezone.localdate() + timedelta(days=3))
        r = self.c.get(reverse('stocks:vencimientos'))
        self.assertContains(r, 'Yerba 1kg')


class EmpaquesTests(InvBase):
    """Unidad + display x12 + bulto x4 displays; se compra por bulto y se vende por unidad o display."""

    def setUp(self):
        super().setUp()
        self.alta(name='Alfajor', barcode='7790000000999', cost_price='100', sale_price='200', current_stock='0')
        self.p = Product.objects.get()
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'save_pkg',
            'has_unit': '1', 'unit_purchase_price': '100', 'unit_sale_price': '200',
            'has_display': '1', 'display_barcode': '7790000001000', 'display_purchase_price': '1100',
            'display_sale_price': '2200', 'has_bulk': '1', 'bulk_barcode': '7790000002000',
            'bulk_purchase_price': '4200', 'bulk_sale_price': '8400',
            'pkg_units_per_display': '12', 'pkg_displays_per_bulk': '4'})

    def test_se_crean_los_tres_niveles_con_su_equivalencia(self):
        pk = {x.packaging_type: x for x in self.p.packagings.filter(is_active=True)}
        self.assertEqual(set(pk), {'unit', 'display', 'bulk'})
        self.assertEqual(pk['display'].units_quantity, 12)
        self.assertEqual(pk['bulk'].units_quantity, 48)

    def test_recibir_bultos_suma_unidades(self):
        bulk = self.p.packagings.get(packaging_type='bulk', is_active=True)
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'receive', 'packaging_id': bulk.pk, 'quantity': '2', 'cost': '4200'})
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('96'))       # 2 bultos × 48

    def test_abrir_un_bulto_lo_pasa_a_displays(self):
        bulk = self.p.packagings.get(packaging_type='bulk', is_active=True)
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'receive', 'packaging_id': bulk.pk, 'quantity': '2', 'cost': '4200'})
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'open', 'packaging_id': bulk.pk, 'quantity': '1'})
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('96'))       # abrir no cambia el total en unidades

    def test_el_display_se_vende_por_su_codigo_y_descuenta_12_unidades(self):
        bulk = self.p.packagings.get(packaging_type='bulk', is_active=True)
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'receive', 'packaging_id': bulk.pk, 'quantity': '1', 'cost': '4200'})
        r = self.c.get(reverse('pos:api_search'), {'q': '7790000001000'})
        prod = r.json()['products'][0]
        self.assertEqual(prod['unit_price'], 2200.0)
        self.assertEqual(prod['packaging_type'], 'display')
        # venderlo
        reg = CashRegister.objects.create(name='C', code='C1', is_active=True)
        shift = CashShift.objects.create(cash_register=reg, cashier=self.dueña, initial_amount=0, status='open')
        tx = POSService.create_transaction(POSService.get_or_create_session(shift))
        r = self.c.post(reverse('pos:api_cart_add'), json.dumps({
            'transaction_id': tx.id, 'product_id': self.p.pk, 'quantity': 1, 'packaging_id': prod['packaging_id']}),
            content_type='application/json')
        self.assertEqual(r.status_code, 200, r.content)
        tx.refresh_from_db()
        self.assertEqual(tx.total, Decimal('2200.00'))
        r = self.c.post(reverse('pos:api_checkout'), json.dumps({
            'transaction_id': tx.id, 'payments': [{'method_code': 'cash', 'amount': 2200}]}),
            content_type='application/json')
        self.assertEqual(r.status_code, 200, r.content)
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('36'))       # 48 − 12

    def test_ajuste_por_empaque(self):
        unit = self.p.packagings.get(packaging_type='unit', is_active=True)
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'adjust', 'packaging_id': unit.pk, 'new_stock': '30', 'reason': 'conteo'})
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('30'))

    def test_inventario_de_empaques(self):
        self.assertEqual(self.c.get(reverse('stocks:packaging_inventory')).status_code, 200)


class ProductosPorPesoEnInventarioTests(InvBase):
    def setUp(self):
        super().setUp()
        self.c.post(reverse('granel:caramelera_create'), {
            'nombre': 'Jamón cocido', 'precio_kg': '12000', 'costo_kg': '8000',
            'stock_inicial': '2', 'stock_unidad': 'kg'})
        self.car = Caramelera.objects.get()
        self.p = Product.objects.get(is_granel=True)

    def test_editarlo_desde_inventario_lleva_a_venta_por_peso(self):
        r = self.c.get(reverse('stocks:product_edit', args=[self.p.pk]))
        self.assertRedirects(r, reverse('granel:caramelera_edit', args=[self.car.pk]), fetch_redirect_response=False)
        # y un POST tampoco cambia nada
        self.c.post(reverse('stocks:product_edit', args=[self.p.pk]), {'name': 'Otro', 'sale_price': '1', 'sku': self.p.sku})
        self.p.refresh_from_db()
        self.assertEqual(self.p.name, 'Jamón cocido')
        self.assertEqual(self.p.sale_price, Decimal('1200.00'))

    def test_empaques_no_aplica_a_productos_por_peso(self):
        r = self.c.get(reverse('stocks:product_packaging', args=[self.p.pk]))
        self.assertRedirects(r, reverse('granel:caramelera_detail', args=[self.car.pk]), fetch_redirect_response=False)

    def test_conteo_fisico_si_funciona_y_actualiza_la_caramelera(self):
        self.c.post(reverse('stocks:inventory_count', args=[self.p.pk]), {'new_quantity': '1500', 'reason': 'conteo_fisico'})
        self.car.refresh_from_db()
        self.assertEqual(self.car.stock_gramos_actual, Decimal('1500.00'))

    def test_darlo_de_baja_lo_saca_de_venta_por_peso_tambien(self):
        self.c.post(reverse('stocks:product_delete', args=[self.p.pk]))
        self.car.refresh_from_db()
        self.assertFalse(self.car.is_active)
        self.assertEqual(list(self.c.get(reverse('granel:caramelera_list')).context['carameleras']), [])
        self.assertEqual(self.c.get(reverse('pos:api_search'), {'q': 'jamon'}).json()['products'], [])
