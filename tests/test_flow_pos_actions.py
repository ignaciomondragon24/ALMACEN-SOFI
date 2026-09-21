"""
Flujo: todo lo que se hace en la caja además de cobrar un producto —
cantidades, descuentos, suspender/reanudar/cancelar, venta al costo, consumo
interno, venta por monto, alta rápida de producto, promociones en el carrito,
y que un ticket no se pueda cobrar dos veces.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from cashregister.models import CashMovement, CashRegister, CashShift, PaymentMethod
from pos.models import POSTransaction, POSTransactionItem
from pos.services import POSService
from promotions.models import Promotion, PromotionProduct
from stocks.models import Product, StockMovement

User = get_user_model()


def jpost(client, name, data=None, args=None):
    return client.post(reverse(name, args=args or []), json.dumps(data or {}), content_type='application/json')


class PosActionsBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        PaymentMethod.get_default_methods()
        reg = CashRegister.objects.create(name='Caja 1', code='C01', is_active=True)
        cls.cajera = User.objects.create_user('cajera_p', password='x')
        cls.cajera.groups.add(Group.objects.get_or_create(name='Cashier')[0])
        cls.encargada = User.objects.create_user('encargada_p', password='x')
        cls.encargada.groups.add(Group.objects.get_or_create(name='Cajero Manager')[0])
        cls.shift = CashShift.objects.create(cash_register=reg, cashier=cls.encargada,
                                             initial_amount=Decimal('1000'), status='open')
        cls.shift2 = None
        cls.aceite = Product.objects.create(name='Aceite', sku='A1', cost_price=Decimal('1000'),
                                            sale_price=Decimal('1500'), current_stock=Decimal('20'))
        cls.fideos = Product.objects.create(name='Fideos', sku='F1', cost_price=Decimal('400'),
                                            sale_price=Decimal('700'), current_stock=Decimal('30'))
        cls.granel = Product.objects.create(name='Caramelos', sku='G1', cost_price=Decimal('100'),
                                            sale_price=Decimal('1000'), current_stock=Decimal('5'),
                                            allow_sell_by_amount=True, is_bulk=True, bulk_unit='kg')

    def setUp(self):
        self.enc = Client()
        self.enc.force_login(self.encargada)
        session = POSService.get_or_create_session(self.shift)
        self.tx = POSService.create_transaction(session)

    def agregar(self, producto, cantidad=1, client=None):
        r = jpost(client or self.enc, 'pos:api_cart_add',
                  {'transaction_id': self.tx.id, 'product_id': producto.pk, 'quantity': cantidad})
        self.assertEqual(r.status_code, 200, r.content)
        self.tx.refresh_from_db()
        return r

    def cobrar(self, pagos=None, client=None):
        self.tx.refresh_from_db()
        pagos = pagos or [{'method_code': 'cash', 'amount': float(self.tx.total)}]
        return jpost(client or self.enc, 'pos:api_checkout', {'transaction_id': self.tx.id, 'payments': pagos})


class CarritoTests(PosActionsBase):
    def test_agregar_el_mismo_producto_suma_la_cantidad(self):
        self.agregar(self.aceite, 1)
        self.agregar(self.aceite, 2)
        item = POSTransactionItem.objects.get(transaction=self.tx)
        self.assertEqual(item.quantity, Decimal('3'))
        self.assertEqual(self.tx.total, Decimal('4500.00'))

    def test_cambiar_cantidad_y_quitar_item(self):
        self.agregar(self.aceite, 1)
        item = POSTransactionItem.objects.get()
        r = jpost(self.enc, 'pos:api_cart_update', {'quantity': 4}, [item.id])
        self.assertEqual(r.status_code, 200)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.total, Decimal('6000.00'))
        r = jpost(self.enc, 'pos:api_cart_remove', args=[item.id])
        self.assertEqual(r.status_code, 200)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.total, Decimal('0.00'))

    def test_cantidad_cero_quita_el_item(self):
        self.agregar(self.aceite, 2)
        item = POSTransactionItem.objects.get()
        jpost(self.enc, 'pos:api_cart_update', {'quantity': 0}, [item.id])
        self.assertFalse(POSTransactionItem.objects.exists())

    def test_vaciar_carrito(self):
        self.agregar(self.aceite, 1)
        self.agregar(self.fideos, 1)
        r = jpost(self.enc, 'pos:api_cart_clear', args=[self.tx.id])
        self.assertEqual(r.status_code, 200)
        self.assertFalse(POSTransactionItem.objects.exists())

    def test_producto_inexistente_o_inactivo_no_se_agrega(self):
        r = jpost(self.enc, 'pos:api_cart_add', {'transaction_id': self.tx.id, 'product_id': 99999, 'quantity': 1})
        self.assertEqual(r.status_code, 400)
        self.fideos.is_active = False
        self.fideos.save()
        r = jpost(self.enc, 'pos:api_cart_add', {'transaction_id': self.tx.id, 'product_id': self.fideos.pk, 'quantity': 1})
        self.assertEqual(r.status_code, 400)

    def test_vender_sin_stock_avisa_pero_deja_vender(self):
        self.aceite.current_stock = Decimal('0')
        self.aceite.save()
        r = self.agregar(self.aceite, 1)
        self.assertIn('sin stock', r.json().get('warning', '').lower())

    def test_detalle_de_la_transaccion(self):
        self.agregar(self.aceite, 2)
        r = self.enc.get(reverse('pos:api_transaction_detail', args=[self.tx.id]))
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(len(data['items']), 1)


class DescuentosTests(PosActionsBase):
    def test_descuento_porcentual_a_un_item(self):
        self.agregar(self.aceite, 2)   # 3000
        item = POSTransactionItem.objects.get()
        r = jpost(self.enc, 'pos:api_cart_item_discount', {'type': 'percent', 'value': 10}, [item.id])
        self.assertEqual(r.status_code, 200)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.total, Decimal('2700.00'))
        self.assertEqual(self.cobrar().status_code, 200)   # y se cobra lo descontado
        self.assertEqual(CashMovement.objects.get().amount, Decimal('2700.00'))

    def test_descuento_fijo_y_quitarlo(self):
        self.agregar(self.aceite, 1)
        item = POSTransactionItem.objects.get()
        jpost(self.enc, 'pos:api_cart_item_discount', {'type': 'fixed', 'value': 200}, [item.id])
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.total, Decimal('1300.00'))
        jpost(self.enc, 'pos:api_cart_item_discount', {'type': 'remove'}, [item.id])
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.total, Decimal('1500.00'))

    def test_descuentos_invalidos_se_rechazan(self):
        self.agregar(self.aceite, 1)
        item = POSTransactionItem.objects.get()
        self.assertEqual(jpost(self.enc, 'pos:api_cart_item_discount', {'type': 'percent', 'value': 150}, [item.id]).status_code, 400)
        self.assertEqual(jpost(self.enc, 'pos:api_cart_item_discount', {'type': 'fixed', 'value': 99999}, [item.id]).status_code, 400)
        self.assertEqual(jpost(self.enc, 'pos:api_cart_item_discount', {'type': 'fixed', 'value': -5}, [item.id]).status_code, 400)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.total, Decimal('1500.00'))

    def test_descuento_a_toda_la_venta(self):
        self.agregar(self.aceite, 1)
        self.agregar(self.fideos, 1)      # 2200
        r = jpost(self.enc, 'pos:api_apply_discount', {'type': 'percent', 'value': 10, 'reason': 'clienta amiga'}, [self.tx.id])
        self.assertEqual(r.status_code, 200)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.total, Decimal('1980.00'))
        self.assertEqual(jpost(self.enc, 'pos:api_apply_discount', {'type': 'percent', 'value': 200}, [self.tx.id]).status_code, 400)

    def test_la_cajera_no_puede_dar_descuentos(self):
        self.agregar(self.aceite, 1)
        cajera = Client()
        cajera.force_login(self.cajera)
        item = POSTransactionItem.objects.get()
        r = jpost(cajera, 'pos:api_cart_item_discount', {'type': 'percent', 'value': 50}, [item.id])
        self.assertEqual(r.status_code, 403)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.total, Decimal('1500.00'))


class CicloDeUnaVentaTests(PosActionsBase):
    def test_suspender_y_reanudar(self):
        self.agregar(self.aceite, 1)
        self.assertEqual(jpost(self.enc, 'pos:api_transaction_suspend', args=[self.tx.id]).status_code, 200)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, 'suspended')
        lista = self.enc.get(reverse('pos:api_suspended_transactions')).json()
        self.assertTrue(lista)
        self.assertEqual(self.enc.get(reverse('pos:suspended')).status_code, 200)
        jpost(self.enc, 'pos:api_transaction_resume', args=[self.tx.id])
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, 'pending')
        self.assertEqual(self.cobrar().status_code, 200)

    def test_cancelar_no_toca_stock_ni_caja(self):
        self.agregar(self.aceite, 3)
        self.assertEqual(jpost(self.enc, 'pos:api_transaction_cancel', args=[self.tx.id]).status_code, 200)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, 'cancelled')
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.current_stock, Decimal('20'))
        self.assertFalse(CashMovement.objects.exists())

    def test_no_se_puede_cobrar_dos_veces_el_mismo_ticket(self):
        self.agregar(self.aceite, 1)
        self.assertEqual(self.cobrar().status_code, 200)
        self.assertEqual(self.cobrar([{'method_code': 'cash', 'amount': 1500}]).status_code, 400)
        self.assertEqual(CashMovement.objects.count(), 1)
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.current_stock, Decimal('19'))

    def test_no_se_cobra_una_venta_cancelada(self):
        self.agregar(self.aceite, 1)
        jpost(self.enc, 'pos:api_transaction_cancel', args=[self.tx.id])
        self.assertEqual(self.cobrar([{'method_code': 'cash', 'amount': 1500}]).status_code, 400)
        self.assertFalse(CashMovement.objects.exists())

    def test_carrito_vacio_o_medio_de_pago_invalido(self):
        self.assertIn(self.cobrar([{'method_code': 'cash', 'amount': 10}]).status_code, (400,))
        self.agregar(self.aceite, 1)
        self.assertEqual(self.cobrar([{'method_code': 'inexistente', 'amount': 1500}]).status_code, 400)
        self.assertEqual(jpost(self.enc, 'pos:api_checkout', {'transaction_id': self.tx.id, 'payments': []}).status_code, 400)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, 'pending')

    def test_ticket_se_puede_imprimir(self):
        self.agregar(self.aceite, 1)
        self.cobrar()
        r = self.enc.get(reverse('pos:print_ticket', args=[self.tx.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Aceite')

    def test_ultima_venta_e_historial(self):
        self.agregar(self.aceite, 1)
        self.cobrar()
        self.assertEqual(self.enc.get(reverse('pos:api_last_transaction')).status_code, 200)
        r = self.enc.get(reverse('pos:api_sales_history'))
        self.assertEqual(r.status_code, 200)

    def test_la_pantalla_de_la_caja_carga_con_turno_abierto(self):
        r = self.enc.get(reverse('pos:main'))
        self.assertEqual(r.status_code, 200)


class CobroEspecialTests(PosActionsBase):
    def test_venta_al_costo(self):
        self.agregar(self.aceite, 2)    # costo 1000 c/u
        r = jpost(self.enc, 'pos:api_checkout_cost_sale', {
            'transaction_id': self.tx.id, 'payments': [{'method_code': 'cash', 'amount': 2000}], 'note': 'empleada'})
        self.assertEqual(r.status_code, 200, r.content)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, 'completed')
        self.assertEqual(CashMovement.objects.get().amount, Decimal('2000.00'))
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.current_stock, Decimal('18'))

    def test_consumo_interno_descuenta_stock_sin_cobrar(self):
        self.agregar(self.fideos, 3)
        r = jpost(self.enc, 'pos:api_checkout_internal_consumption', {'transaction_id': self.tx.id, 'note': 'para la casa'})
        self.assertEqual(r.status_code, 200, r.content)
        self.fideos.refresh_from_db()
        self.assertEqual(self.fideos.current_stock, Decimal('27'))
        self.assertFalse(CashMovement.objects.exists())

    def test_la_cajera_no_puede_vender_al_costo_ni_consumo_interno(self):
        self.agregar(self.aceite, 1)
        cajera = Client()
        cajera.force_login(self.cajera)
        self.assertEqual(jpost(cajera, 'pos:api_checkout_cost_sale', {
            'transaction_id': self.tx.id, 'payments': [{'method_code': 'cash', 'amount': 1000}]}).status_code, 403)
        self.assertEqual(jpost(cajera, 'pos:api_checkout_internal_consumption', {'transaction_id': self.tx.id}).status_code, 403)

    def test_calculo_del_costo_total_de_la_venta(self):
        self.agregar(self.aceite, 2)
        r = self.enc.get(reverse('pos:api_calculate_cost_total', args=[self.tx.id]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['total_cost'], 2000.0)


class VentaPorMontoTests(PosActionsBase):
    def test_calcular_cuanto_lleva_por_un_monto(self):
        r = jpost(self.enc, 'pos:api_calculate_by_amount', {'product_id': self.granel.pk, 'amount': 500})
        self.assertEqual(r.status_code, 200, r.content)
        self.assertAlmostEqual(r.json()['quantity'], 0.5)

    def test_agregar_por_monto(self):
        r = jpost(self.enc, 'pos:api_cart_add_by_amount',
                  {'transaction_id': self.tx.id, 'product_id': self.granel.pk, 'amount': 250})
        self.assertEqual(r.status_code, 200, r.content)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.total, Decimal('250.00'))

    def test_producto_que_no_permite_venta_por_monto(self):
        r = jpost(self.enc, 'pos:api_calculate_by_amount', {'product_id': self.aceite.pk, 'amount': 500})
        self.assertEqual(r.status_code, 400)


class AltaRapidaTests(PosActionsBase):
    def test_crear_producto_desde_la_caja_con_stock(self):
        r = jpost(self.enc, 'pos:api_quick_add_product', {
            'barcode': '7791111111111', 'name': 'Galletitas', 'sale_price': 800,
            'purchase_price': 500, 'initial_stock': 10})
        self.assertEqual(r.status_code, 200, r.content)
        p = Product.objects.get(barcode='7791111111111')
        self.assertEqual(p.current_stock, Decimal('10'))
        self.assertEqual(StockMovement.objects.filter(product=p).count(), 1)
        # y se puede vender enseguida
        self.agregar(p, 2)
        self.assertEqual(self.tx.total, Decimal('1600.00'))

    def test_validaciones(self):
        self.assertEqual(jpost(self.enc, 'pos:api_quick_add_product', {'name': '', 'sale_price': 10}).status_code, 400)
        self.assertEqual(jpost(self.enc, 'pos:api_quick_add_product', {'name': 'X', 'sale_price': 0}).status_code, 400)
        Product.objects.create(name='Ya', sku='Y', barcode='7792222222222', cost_price=1, sale_price=2)
        self.assertEqual(jpost(self.enc, 'pos:api_quick_add_product', {
            'name': 'Repetido', 'sale_price': 10, 'barcode': '7792222222222'}).status_code, 400)


class PromosEnElCarritoTests(PosActionsBase):
    def test_2x1_se_aplica_y_se_cobra(self):
        promo = Promotion.objects.create(name='2x1 fideos', promo_type='nxm', status='active',
                                         quantity_required=2, quantity_charged=1)
        PromotionProduct.objects.create(promotion=promo, product=self.fideos)
        self.agregar(self.fideos, 2)
        self.assertEqual(self.tx.total, Decimal('700.00'))
        self.assertEqual(self.cobrar().status_code, 200)
        self.assertEqual(CashMovement.objects.get().amount, Decimal('700.00'))

    def test_precio_fijo_por_cantidad(self):
        promo = Promotion.objects.create(name='3 x $1800', promo_type='nx_fixed_price', status='active',
                                         quantity_required=3, final_price=Decimal('1800'))
        PromotionProduct.objects.create(promotion=promo, product=self.fideos)
        self.agregar(self.fideos, 3)
        self.assertEqual(self.tx.total, Decimal('1800.00'))

    def test_promo_pausada_no_aplica(self):
        promo = Promotion.objects.create(name='2x1', promo_type='nxm', status='paused',
                                         quantity_required=2, quantity_charged=1)
        PromotionProduct.objects.create(promotion=promo, product=self.fideos)
        self.agregar(self.fideos, 2)
        self.assertEqual(self.tx.total, Decimal('1400.00'))

    def test_al_quitar_un_item_la_promo_se_recalcula(self):
        promo = Promotion.objects.create(name='2x1', promo_type='nxm', status='active',
                                         quantity_required=2, quantity_charged=1)
        PromotionProduct.objects.create(promotion=promo, product=self.fideos)
        self.agregar(self.fideos, 2)
        item = POSTransactionItem.objects.get()
        jpost(self.enc, 'pos:api_cart_update', {'quantity': 1}, [item.id])
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.total, Decimal('700.00'))   # ya no hay 2, sin descuento
