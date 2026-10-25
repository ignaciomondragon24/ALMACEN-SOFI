"""
Fiado (cuenta corriente de clientes).

Lo importante que se verifica acá:
  * fiar una venta saca el stock pero NO es venta del día, ni entra plata a la caja;
  * el pago de un fiado (total o parcial) baja la deuda, entra al efectivo del
    cajón (el arqueo cierra) pero NO suma a las ventas del día;
  * no se puede cobrar de más, ni fiar un carrito vacío / ya procesado.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from cashregister.models import CashMovement, CashRegister, CashShift, PaymentMethod
from fiado.models import Customer, FiadoEntry
from fiado.services import FiadoService, parse_amount
from pos.models import POSTransaction
from pos.services import POSService
from stocks.models import Product

User = get_user_model()


def jpost(client, name, data=None, args=None):
    return client.post(reverse(name, args=args or []), json.dumps(data or {}), content_type='application/json')


class FiadoBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        PaymentMethod.get_default_methods()
        cls.cash = PaymentMethod.objects.get(code='cash')
        cls.transfer = PaymentMethod.objects.get(code='transfer')
        reg = CashRegister.objects.create(name='Caja 1', code='C01', is_active=True)
        cls.admin = User.objects.create_user('admin_f', password='x')
        cls.admin.groups.add(Group.objects.get_or_create(name='Admin')[0])
        cls.encargada = User.objects.create_user('encargada_f', password='x')
        cls.encargada.groups.add(Group.objects.get_or_create(name='Cajero Manager')[0])
        cls.cajera = User.objects.create_user('cajera_f', password='x')
        cls.cajera.groups.add(Group.objects.get_or_create(name='Cashier')[0])
        cls.shift = CashShift.objects.create(cash_register=reg, cashier=cls.encargada,
                                             initial_amount=Decimal('1000'), status='open')
        cls.aceite = Product.objects.create(name='Aceite', sku='A1', cost_price=Decimal('1000'),
                                            sale_price=Decimal('1500'), current_stock=Decimal('20'))
        cls.fideos = Product.objects.create(name='Fideos', sku='F1', cost_price=Decimal('400'),
                                            sale_price=Decimal('700'), current_stock=Decimal('30'))
        cls.juan = Customer.objects.create(name='Juan Pérez', phone='221555')

    def setUp(self):
        self.enc = Client()
        self.enc.force_login(self.encargada)
        self.nueva_venta()

    def nueva_venta(self):
        session = POSService.get_or_create_session(self.shift)
        self.tx = POSService.create_transaction(session)
        return self.tx

    def agregar(self, producto, cantidad=1):
        r = jpost(self.enc, 'pos:api_cart_add',
                  {'transaction_id': self.tx.id, 'product_id': producto.pk, 'quantity': cantidad})
        self.assertEqual(r.status_code, 200, r.content)
        self.tx.refresh_from_db()

    def fiar(self, customer=None, client=None, tx=None):
        tx = tx or self.tx
        return jpost(client or self.enc, 'fiado:api_charge_sale',
                     {'transaction_id': tx.id, 'customer_id': (customer or self.juan).id})

    def cobrar_normal(self):
        self.tx.refresh_from_db()
        return jpost(self.enc, 'pos:api_checkout', {
            'transaction_id': self.tx.id,
            'payments': [{'method_code': 'cash', 'amount': float(self.tx.total)}],
        })


class FiarVentaTests(FiadoBase):
    def test_fiar_descuenta_stock_y_anota_la_deuda(self):
        self.agregar(self.aceite, 2)   # 3000
        r = self.fiar()
        self.assertEqual(r.status_code, 200, r.content)
        data = r.json()
        self.assertEqual(data['total'], 3000.0)
        self.assertEqual(data['balance'], 3000.0)

        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.current_stock, Decimal('18'))
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, 'on_credit')
        self.assertEqual(self.juan.balance, Decimal('3000.00'))
        entry = FiadoEntry.objects.get()
        self.assertEqual(entry.entry_type, FiadoEntry.CHARGE)
        self.assertEqual(entry.pos_transaction_id, self.tx.id)

    def test_fiar_no_mueve_la_caja(self):
        self.agregar(self.aceite, 1)
        self.assertEqual(self.fiar().status_code, 200)
        self.assertFalse(CashMovement.objects.exists())
        self.assertEqual(self.shift.get_cash_total(), Decimal('0'))
        self.assertEqual(self.shift.calculate_expected(), Decimal('1000'))

    def test_fiar_no_cuenta_como_venta_del_dia(self):
        # una venta normal de 700 y una fiada de 3000: ventas del día = 700
        self.agregar(self.fideos, 1)
        self.assertEqual(self.cobrar_normal().status_code, 200)
        self.nueva_venta()
        self.agregar(self.aceite, 2)
        self.assertEqual(self.fiar().status_code, 200)

        admin = Client()
        admin.force_login(self.admin)
        ctx = admin.get(reverse('sales:dashboard')).context
        self.assertEqual(ctx['today_sales'], Decimal('700.00'))
        self.assertEqual(ctx['today_count'], 1)
        self.assertEqual(self.shift.get_cash_total(), Decimal('700.00'))

    def test_no_se_puede_fiar_un_carrito_vacio(self):
        r = self.fiar()
        self.assertEqual(r.status_code, 400)
        self.assertIn('vacío', r.json()['error'])
        self.assertFalse(FiadoEntry.objects.exists())

    def test_no_se_puede_fiar_dos_veces_la_misma_venta(self):
        self.agregar(self.aceite, 1)
        self.assertEqual(self.fiar().status_code, 200)
        r = self.fiar()
        self.assertEqual(r.status_code, 400)
        self.assertEqual(FiadoEntry.objects.count(), 1)
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.current_stock, Decimal('19'))   # descontó una sola vez

    def test_no_se_puede_fiar_una_venta_ya_cobrada(self):
        self.agregar(self.aceite, 1)
        self.assertEqual(self.cobrar_normal().status_code, 200)
        self.assertEqual(self.fiar().status_code, 400)
        self.assertFalse(FiadoEntry.objects.exists())

    def test_cliente_inactivo_o_inexistente_no_recibe_fiado(self):
        self.agregar(self.aceite, 1)
        inactivo = Customer.objects.create(name='Viejo', is_active=False)
        self.assertEqual(self.fiar(customer=inactivo).status_code, 400)
        r = jpost(self.enc, 'fiado:api_charge_sale', {'transaction_id': self.tx.id, 'customer_id': 99999})
        self.assertEqual(r.status_code, 400)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, 'pending')
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.current_stock, Decimal('20'))

    def test_fiar_con_datos_incompletos(self):
        r = jpost(self.enc, 'fiado:api_charge_sale', {'transaction_id': self.tx.id})
        self.assertEqual(r.status_code, 400)

    def test_dos_fiados_suman_a_la_misma_cuenta(self):
        self.agregar(self.aceite, 1)
        self.fiar()
        self.nueva_venta()
        self.agregar(self.fideos, 2)   # 1400
        self.fiar()
        self.assertEqual(self.juan.balance, Decimal('2900.00'))

    def test_el_cajero_tambien_puede_fiar(self):
        cajera = Client()
        cajera.force_login(self.cajera)
        self.agregar(self.aceite, 1)
        self.assertEqual(self.fiar(client=cajera).status_code, 200)

    def test_el_ticket_dice_fiado(self):
        self.agregar(self.aceite, 1)
        self.fiar()
        r = self.enc.get(reverse('pos:print_ticket', args=[self.tx.id]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'FIADO')
        self.assertContains(r, 'Juan Pérez')


class PagoFiadoTests(FiadoBase):
    def fiar_monto(self, producto, cantidad):
        self.agregar(producto, cantidad)
        self.assertEqual(self.fiar().status_code, 200)

    def pagar(self, monto, method=None, user=None):
        return FiadoService.register_payment(
            self.juan.pk, monto, (method or self.cash).pk, user or self.encargada)

    def test_pago_parcial_baja_la_deuda(self):
        self.fiar_monto(self.aceite, 2)   # 3000
        ok, res = self.pagar('2500')
        self.assertTrue(ok, res)
        self.assertEqual(res['balance'], Decimal('500.00'))
        self.assertEqual(self.juan.balance, Decimal('500.00'))

    def test_pago_total_deja_la_cuenta_en_cero(self):
        self.fiar_monto(self.aceite, 1)
        ok, res = self.pagar('1500')
        self.assertTrue(ok, res)
        self.assertEqual(self.juan.balance, Decimal('0.00'))

    def test_no_se_puede_cobrar_mas_de_lo_que_debe(self):
        self.fiar_monto(self.aceite, 1)   # 1500
        ok, res = self.pagar('1500.01')
        self.assertFalse(ok)
        self.assertIn('mayor a la deuda', res['error'])
        self.assertEqual(self.juan.balance, Decimal('1500.00'))

    def test_monto_invalido_o_cero_se_rechaza(self):
        self.fiar_monto(self.aceite, 1)
        for monto in ('', '0', '-5', 'abc', None):
            ok, _ = self.pagar(monto)
            self.assertFalse(ok, monto)
        self.assertEqual(FiadoEntry.objects.filter(entry_type=FiadoEntry.PAYMENT).count(), 0)

    def test_cliente_sin_deuda_no_puede_pagar(self):
        ok, res = self.pagar('100')
        self.assertFalse(ok)
        self.assertIn('no tiene deuda', res['error'])

    def test_pago_en_efectivo_entra_al_cajon_pero_no_es_venta(self):
        self.fiar_monto(self.aceite, 2)   # 3000
        self.nueva_venta()
        self.agregar(self.fideos, 1)      # venta normal 700 en efectivo
        self.assertEqual(self.cobrar_normal().status_code, 200)

        ok, _ = self.pagar('250')
        self.assertTrue(ok)

        mov = CashMovement.objects.get(is_fiado_payment=True)
        self.assertEqual(mov.amount, Decimal('250.00'))
        self.assertEqual(mov.movement_type, 'income')
        # ventas del turno: solo los 700 de la venta normal
        self.assertEqual(self.shift.get_cash_total(), Decimal('700.00'))
        self.assertEqual(self.shift.total_income, Decimal('700.00'))
        self.assertEqual(self.shift.total_sales, Decimal('700.00'))
        self.assertEqual([m['payment_method__code'] for m in self.shift.get_totals_by_payment_method()], ['cash'])
        self.assertEqual(self.shift.get_totals_by_payment_method()[0]['total'], Decimal('700.00'))
        # pero la plata sí está en el cajón: 1000 inicial + 700 + 250
        self.assertEqual(self.shift.calculate_expected(), Decimal('1950.00'))
        self.assertEqual(self.shift.get_fiado_cash_total(), Decimal('250.00'))
        self.assertEqual(self.shift.get_fiado_total(), Decimal('250.00'))

    def test_pago_por_transferencia_no_toca_el_efectivo_esperado(self):
        self.fiar_monto(self.aceite, 1)
        ok, _ = self.pagar('500', method=self.transfer)
        self.assertTrue(ok)
        self.assertEqual(self.shift.calculate_expected(), Decimal('1000.00'))
        self.assertEqual(self.shift.get_fiado_cash_total(), Decimal('0'))
        self.assertEqual(self.shift.get_fiado_total(), Decimal('500.00'))
        self.assertEqual(self.shift.get_non_cash_total(), Decimal('0'))   # no es venta digital

    def test_el_pago_no_aparece_en_los_reportes_de_ventas(self):
        self.fiar_monto(self.aceite, 1)
        self.pagar('1000')
        admin = Client()
        admin.force_login(self.admin)
        ctx = admin.get(reverse('sales:dashboard')).context
        self.assertEqual(ctx['today_sales'], Decimal('0'))
        self.assertEqual(ctx['today_count'], 0)
        self.assertEqual(list(ctx['payment_stats']), [])

    def test_pago_sin_turno_abierto_se_registra_pero_no_toca_la_caja(self):
        self.fiar_monto(self.aceite, 1)
        ok, res = self.pagar('300', user=self.admin)   # el admin no tiene turno abierto
        self.assertTrue(ok)
        self.assertFalse(res['in_cash_register'])
        self.assertFalse(CashMovement.objects.exists())
        self.assertEqual(self.juan.balance, Decimal('1200.00'))

    def test_deuda_manual_suma_al_saldo(self):
        ok, res = FiadoService.add_manual_charge(self.juan.pk, '1.234,50', self.encargada, 'Saldo anterior')
        self.assertTrue(ok)
        self.assertEqual(res['balance'], Decimal('1234.50'))
        ok, _ = FiadoService.add_manual_charge(self.juan.pk, '0', self.encargada)
        self.assertFalse(ok)


class AnularTests(FiadoBase):
    def setUp(self):
        super().setUp()
        self.agregar(self.aceite, 2)   # 3000
        self.fiar()

    def test_anular_un_pago_restituye_la_deuda_y_saca_el_movimiento_de_caja(self):
        ok, res = FiadoService.register_payment(self.juan.pk, '1000', self.cash.pk, self.encargada)
        self.assertEqual(self.juan.balance, Decimal('2000.00'))
        ok, res = FiadoService.void_entry(res['entry'].pk, self.encargada, 'me equivoqué')
        self.assertTrue(ok, res)
        self.assertEqual(self.juan.balance, Decimal('3000.00'))
        self.assertFalse(CashMovement.objects.exists())
        self.assertEqual(self.shift.calculate_expected(), Decimal('1000.00'))

    def test_no_se_puede_anular_dos_veces(self):
        _, res = FiadoService.register_payment(self.juan.pk, '1000', self.cash.pk, self.encargada)
        FiadoService.void_entry(res['entry'].pk, self.encargada)
        ok, _ = FiadoService.void_entry(res['entry'].pk, self.encargada)
        self.assertFalse(ok)

    def test_no_se_puede_anular_un_pago_de_un_turno_cerrado(self):
        _, res = FiadoService.register_payment(self.juan.pk, '1000', self.cash.pk, self.encargada)
        self.shift.close(Decimal('2000'))
        ok, out = FiadoService.void_entry(res['entry'].pk, self.encargada)
        self.assertFalse(ok)
        self.assertIn('cerrado', out['error'])
        self.assertEqual(self.juan.balance, Decimal('2000.00'))
        self.assertTrue(CashMovement.objects.filter(is_fiado_payment=True).exists())

    def test_no_se_puede_anular_una_venta_con_productos(self):
        entry = FiadoEntry.objects.get(entry_type=FiadoEntry.CHARGE)
        ok, out = FiadoService.void_entry(entry.pk, self.encargada)
        self.assertFalse(ok)
        self.assertIn('stock', out['error'])
        self.assertEqual(self.juan.balance, Decimal('3000.00'))

    def test_anular_deuda_manual(self):
        _, res = FiadoService.add_manual_charge(self.juan.pk, '500', self.encargada)
        ok, _ = FiadoService.void_entry(res['entry'].pk, self.encargada)
        self.assertTrue(ok)
        self.assertEqual(self.juan.balance, Decimal('3000.00'))

    def test_no_se_anula_una_deuda_que_ya_se_pago_en_parte(self):
        _, res = FiadoService.add_manual_charge(self.juan.pk, '500', self.encargada)
        FiadoService.register_payment(self.juan.pk, '3500', self.cash.pk, self.encargada)   # deja saldo 0
        ok, out = FiadoService.void_entry(res['entry'].pk, self.encargada)
        self.assertFalse(ok)
        self.assertEqual(self.juan.balance, Decimal('0.00'))

    def test_el_cajero_no_puede_anular(self):
        _, res = FiadoService.register_payment(self.juan.pk, '1000', self.cash.pk, self.encargada)
        cajera = Client()
        cajera.force_login(self.cajera)
        r = cajera.post(reverse('fiado:entry_void', args=[res['entry'].pk]))
        self.assertEqual(r.status_code, 403)
        self.assertEqual(self.juan.balance, Decimal('2000.00'))

    def test_el_encargado_anula_desde_la_pantalla(self):
        _, res = FiadoService.register_payment(self.juan.pk, '1000', self.cash.pk, self.encargada)
        r = self.enc.post(reverse('fiado:entry_void', args=[res['entry'].pk]), {'reason': 'error'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.juan.balance, Decimal('3000.00'))


class ClientesTests(FiadoBase):
    def test_crear_cliente_por_api_desde_el_pos(self):
        r = jpost(self.enc, 'fiado:api_customer_create', {'name': '  María  ', 'phone': '123'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['customer']['name'], 'María')
        self.assertTrue(Customer.objects.filter(name='María').exists())

    def test_nombre_vacio_o_repetido_se_rechaza(self):
        self.assertEqual(jpost(self.enc, 'fiado:api_customer_create', {'name': '   '}).status_code, 400)
        r = jpost(self.enc, 'fiado:api_customer_create', {'name': 'juan pérez'})
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Customer.objects.count(), 1)

    def test_clientes_ilimitados(self):
        for i in range(60):
            ok, _ = FiadoService.create_customer(f'Cliente {i}')
            self.assertTrue(ok)
        self.assertEqual(Customer.objects.count(), 61)

    def test_buscar_clientes(self):
        FiadoService.create_customer('Ana Gómez')
        r = self.enc.get(reverse('fiado:api_customers'), {'q': 'gómez'})
        names = [c['name'] for c in r.json()['customers']]
        self.assertEqual(names, ['Ana Gómez'])
        r = self.enc.get(reverse('fiado:api_customers'))
        self.assertEqual(len(r.json()['customers']), 2)

    def test_la_busqueda_trae_el_saldo(self):
        self.agregar(self.aceite, 1)
        self.fiar()
        r = self.enc.get(reverse('fiado:api_customers'), {'q': 'juan'})
        self.assertEqual(r.json()['customers'][0]['balance'], 1500.0)

    def test_pantallas_renderizan(self):
        self.agregar(self.aceite, 1)
        self.fiar()
        for name, args in [('fiado:customer_list', []), ('fiado:customer_create', []),
                           ('fiado:customer_detail', [self.juan.pk]), ('fiado:customer_edit', [self.juan.pk])]:
            r = self.enc.get(reverse(name, args=args))
            self.assertEqual(r.status_code, 200, name)
        r = self.enc.get(reverse('fiado:customer_list'))
        self.assertContains(r, 'Juan Pérez')
        self.assertEqual(r.context['total_owed'], Decimal('1500.00'))
        r = self.enc.get(reverse('fiado:customer_list'), {'deuda': '1'})
        self.assertContains(r, 'Juan Pérez')

    def test_alta_con_deuda_anterior(self):
        r = self.enc.post(reverse('fiado:customer_create'), {
            'name': 'Pedro', 'phone': '', 'notes': '', 'opening_balance': '300'})
        self.assertEqual(r.status_code, 302)
        pedro = Customer.objects.get(name='Pedro')
        self.assertEqual(pedro.balance, Decimal('300.00'))

    def test_registrar_pago_desde_la_pantalla(self):
        self.agregar(self.aceite, 2)   # 3000
        self.fiar()
        r = self.enc.post(reverse('fiado:payment_create', args=[self.juan.pk]),
                          {'amount': '2500', 'method_id': self.cash.pk, 'note': ''}, follow=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.juan.balance, Decimal('500.00'))
        self.assertContains(r, 'Saldo')

    def test_no_se_desactiva_un_cliente_con_deuda(self):
        self.agregar(self.aceite, 1)
        self.fiar()
        self.enc.post(reverse('fiado:customer_toggle_active', args=[self.juan.pk]))
        self.juan.refresh_from_db()
        self.assertTrue(self.juan.is_active)

    def test_requiere_login(self):
        anon = Client()
        self.assertEqual(anon.get(reverse('fiado:customer_list')).status_code, 302)
        self.assertIn(anon.get(reverse('fiado:api_customers')).status_code, (302, 401))
        self.assertIn(jpost(anon, 'fiado:api_charge_sale', {'transaction_id': 1, 'customer_id': 1}).status_code, (302, 401))

    def test_parse_amount(self):
        self.assertEqual(parse_amount('250'), Decimal('250.00'))
        self.assertEqual(parse_amount('250.50'), Decimal('250.50'))
        self.assertEqual(parse_amount('1.234,56'), Decimal('1234.56'))
        self.assertEqual(parse_amount('$ 300'), Decimal('300.00'))
        self.assertIsNone(parse_amount('abc'))
        self.assertIsNone(parse_amount(''))
        self.assertIsNone(parse_amount('NaN'))


class PosYCierreTests(FiadoBase):
    def test_el_pos_tiene_el_boton_y_el_modal_de_fiado(self):
        r = self.enc.get(reverse('pos:pos_main'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'id="btn-fiado"')
        self.assertContains(r, 'id="fiadoModal"')
        self.assertContains(r, 'js/pos-fiado')   # el nombre puede llevar hash del manifiesto

    def test_historial_y_reimpresion_incluyen_la_venta_fiada(self):
        self.agregar(self.aceite, 1)
        self.fiar()
        r = self.enc.get(reverse('pos:api_sales_history'))
        self.assertEqual(r.status_code, 200)
        txs = r.json()['transactions']
        self.assertEqual(len(txs), 1)
        self.assertEqual(txs[0]['payments'], ['FIADO a Juan Pérez'])
        r = self.enc.get(reverse('pos:api_last_transaction'))
        self.assertEqual(r.json()['transaction_id'], self.tx.id)

    def test_cierre_z_separa_los_cobros_de_fiado(self):
        self.agregar(self.aceite, 2)   # 3000 fiados
        self.fiar()
        self.nueva_venta()
        self.agregar(self.fideos, 1)   # 700 venta
        self.cobrar_normal()
        FiadoService.register_payment(self.juan.pk, '250', self.cash.pk, self.encargada)

        r = self.enc.get(reverse('cashregister:close_shift', args=[self.shift.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['total_sales'], Decimal('700.00'))      # sin los 250 cobrados
        self.assertEqual(r.context['expected'], Decimal('1950.00'))        # 1000 + 700 + 250
        self.assertEqual(r.context['fiado_cash'], Decimal('250.00'))
        self.assertContains(r, 'Cobros de fiado')

        # y el cierre queda cuadrado con el efectivo contado
        r = self.enc.post(reverse('cashregister:close_shift', args=[self.shift.pk]),
                          {'actual_amount': '1950', 'notes': ''})
        self.assertEqual(r.status_code, 302)
        self.shift.refresh_from_db()
        self.assertEqual(self.shift.status, 'closed')
        self.assertEqual(self.shift.difference, Decimal('0.00'))

    def test_reporte_txt_del_cierre_incluye_el_fiado(self):
        self.agregar(self.aceite, 1)
        self.fiar()
        FiadoService.register_payment(self.juan.pk, '500', self.cash.pk, self.encargada)
        r = self.enc.get(reverse('cashregister:shift_report_pdf', args=[self.shift.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn('Cobros Fiado', r.content.decode())

    def test_el_detalle_del_turno_renderiza_con_cobros_de_fiado(self):
        self.agregar(self.aceite, 1)
        self.fiar()
        FiadoService.register_payment(self.juan.pk, '500', self.cash.pk, self.encargada)
        r = self.enc.get(reverse('cashregister:shift_detail', args=[self.shift.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Cobro fiado')
