"""
Flujo: un día de caja completo (abrir turno → vender → movimientos → cierre de caja).

Lo que importa para Sofia: el cierre separa EFECTIVO de transferencias/tarjetas
(el efectivo esperado no incluye lo que entró por transferencia) y la diferencia
sale bien.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from cashregister.models import (
    BillCount, CashMovement, CashRegister, CashShift, PaymentMethod, ShiftPaymentSummary,
)
from pos.models import POSTransaction
from pos.services import CartService, CheckoutService, POSService
from stocks.models import Product

User = get_user_model()


class CashDayTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        PaymentMethod.get_default_methods()
        cls.cash = PaymentMethod.objects.get(code='cash')
        cls.transfer = PaymentMethod.objects.get(code='transfer')
        cls.register = CashRegister.objects.create(name='Caja 1', code='C01', is_active=True)
        cls.register2 = CashRegister.objects.create(name='Caja 2', code='C02', is_active=True)
        cajero_g, _ = Group.objects.get_or_create(name='Cashier')
        admin_g, _ = Group.objects.get_or_create(name='Admin')
        cls.cajera = User.objects.create_user('cajera', password='x')
        cls.cajera.groups.add(cajero_g)
        cls.otra = User.objects.create_user('otra_cajera', password='x')
        cls.otra.groups.add(cajero_g)
        cls.duena = User.objects.create_user('duena', password='x')
        cls.duena.groups.add(admin_g)
        cls.aceite = Product.objects.create(name='Aceite', sku='A1', cost_price=Decimal('1000'),
                                            sale_price=Decimal('1500'), current_stock=Decimal('50'))

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.cajera)

    # ---------- helpers
    def abrir_turno(self, monto='5000', client=None):
        return (client or self.c).post(reverse('cashregister:open_shift'), {
            'cash_register': self.register.pk, 'initial_amount': monto})

    def vender(self, shift, unidades, pagos):
        """Venta por la API real de la caja: agrega producto y cobra."""
        session = POSService.get_or_create_session(shift)
        tx = POSService.create_transaction(session)
        r = self.c.post(reverse('pos:api_cart_add'), json.dumps(
            {'transaction_id': tx.id, 'product_id': self.aceite.pk, 'quantity': unidades}),
            content_type='application/json')
        self.assertEqual(r.status_code, 200, r.content)
        tx.refresh_from_db()
        r = self.c.post(reverse('pos:api_checkout'), json.dumps(
            {'transaction_id': tx.id, 'payments': pagos}), content_type='application/json')
        return tx, r

    # ---------- abrir turno
    def test_abrir_turno(self):
        r = self.abrir_turno('5000')
        self.assertEqual(r.status_code, 302)
        shift = CashShift.objects.get()
        self.assertEqual(shift.cashier, self.cajera)
        self.assertEqual(shift.status, 'open')
        self.assertEqual(shift.initial_amount, Decimal('5000'))

    def test_no_se_pueden_abrir_dos_turnos_del_mismo_cajero(self):
        self.abrir_turno()
        self.abrir_turno()
        self.assertEqual(CashShift.objects.count(), 1)

    def test_una_caja_ocupada_no_se_abre_dos_veces(self):
        self.abrir_turno()
        otra = Client()
        otra.force_login(self.otra)
        self.abrir_turno(client=otra)
        self.assertEqual(CashShift.objects.count(), 1)

    def test_monto_inicial_invalido_no_abre(self):
        self.c.post(reverse('cashregister:open_shift'), {'cash_register': self.register.pk, 'initial_amount': ''})
        self.assertFalse(CashShift.objects.exists())

    # ---------- ventas y su registro en caja
    def test_venta_en_efectivo_entra_a_la_caja(self):
        self.abrir_turno()
        shift = CashShift.objects.get()
        tx, r = self.vender(shift, 2, [{'method_code': 'cash', 'amount': 3000}])
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(shift.get_cash_total(), Decimal('3000.00'))
        self.assertEqual(shift.get_non_cash_total(), Decimal('0.00'))

    def test_venta_por_transferencia_no_es_efectivo(self):
        self.abrir_turno()
        shift = CashShift.objects.get()
        self.vender(shift, 1, [{'method_code': 'transfer', 'amount': 1500}])
        self.assertEqual(shift.get_cash_total(), Decimal('0.00'))
        self.assertEqual(shift.get_non_cash_total(), Decimal('1500.00'))

    def test_pago_mixto_efectivo_y_transferencia(self):
        self.abrir_turno()
        shift = CashShift.objects.get()
        self.vender(shift, 2, [{'method_code': 'cash', 'amount': 1000},
                               {'method_code': 'transfer', 'amount': 2000}])
        self.assertEqual(shift.get_cash_total(), Decimal('1000.00'))
        self.assertEqual(shift.get_non_cash_total(), Decimal('2000.00'))

    def test_el_vuelto_no_se_cuenta_como_ingreso(self):
        self.abrir_turno()
        shift = CashShift.objects.get()
        tx, r = self.vender(shift, 1, [{'method_code': 'cash', 'amount': 2000}])  # cuesta 1500
        self.assertEqual(r.json()['change'], 500.0)
        self.assertEqual(shift.get_cash_total(), Decimal('1500.00'))

    def test_pago_insuficiente_no_deja_rastros(self):
        self.abrir_turno()
        shift = CashShift.objects.get()
        tx, r = self.vender(shift, 2, [{'method_code': 'cash', 'amount': 1000}])   # cuesta 3000
        self.assertEqual(r.status_code, 400)
        self.assertEqual(CashMovement.objects.count(), 0)
        tx.refresh_from_db()
        self.assertEqual(tx.status, 'pending')
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.current_stock, Decimal('50'))

    def test_venta_descuenta_stock(self):
        self.abrir_turno()
        self.vender(CashShift.objects.get(), 3, [{'method_code': 'cash', 'amount': 4500}])
        self.aceite.refresh_from_db()
        self.assertEqual(self.aceite.current_stock, Decimal('47'))

    # ---------- movimientos manuales
    def test_retiro_de_efectivo(self):
        self.abrir_turno()
        shift = CashShift.objects.get()
        r = self.c.post(reverse('cashregister:add_movement', args=[shift.pk]), {
            'movement_type': 'expense', 'amount': '500', 'payment_method': self.cash.pk,
            'description': 'Compra de bolsas', 'reference': ''})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(shift.movements.get().amount, Decimal('500'))

    # ---------- cierre de caja
    def _dia_completo(self):
        self.abrir_turno('5000')
        shift = CashShift.objects.get()
        self.vender(shift, 2, [{'method_code': 'cash', 'amount': 3000}])           # +3000 efectivo
        self.vender(shift, 1, [{'method_code': 'transfer', 'amount': 1500}])       # +1500 transferencia
        self.vender(shift, 2, [{'method_code': 'cash', 'amount': 1000},
                               {'method_code': 'transfer', 'amount': 2000}])       # +1000 ef, +2000 transf
        self.c.post(reverse('cashregister:add_movement', args=[shift.pk]), {
            'movement_type': 'expense', 'amount': '500', 'payment_method': self.cash.pk,
            'description': 'Bolsas', 'reference': ''})                             # -500 efectivo
        return shift

    def test_efectivo_esperado_no_incluye_transferencias(self):
        shift = self._dia_completo()
        # 5000 inicial + 3000 + 1000 − 500 = 8500 (las transferencias no van al cajón)
        self.assertEqual(shift.calculate_expected(), Decimal('8500.00'))

    def test_pantalla_de_cierre_muestra_efectivo_y_otros_medios_por_separado(self):
        shift = self._dia_completo()
        r = self.c.get(reverse('cashregister:close_shift', args=[shift.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['cash_total'], Decimal('4000.00'))
        self.assertEqual(r.context['non_cash_total'], Decimal('3500.00'))
        self.assertEqual(r.context['expected'], Decimal('8500.00'))
        self.assertEqual(r.context['total_sales'], Decimal('7500.00'))

    def test_cierre_sin_diferencia(self):
        shift = self._dia_completo()
        r = self.c.post(reverse('cashregister:close_shift', args=[shift.pk]),
                        {'actual_amount': '8500', 'notes': 'Todo ok', 'bill_5000': 1, 'bill_2000': 1, 'bill_1000': 1, 'bill_500': 1})
        self.assertEqual(r.status_code, 302)
        shift.refresh_from_db()
        self.assertEqual(shift.status, 'closed')
        self.assertEqual(shift.expected_amount, Decimal('8500.00'))
        self.assertEqual(shift.actual_amount, Decimal('8500'))
        self.assertEqual(shift.difference, Decimal('0.00'))
        self.assertIsNotNone(shift.closed_at)
        self.assertEqual(shift.get_bill_count_total(), Decimal('8500'))

    def test_cierre_con_faltante_y_con_sobrante(self):
        shift = self._dia_completo()
        self.c.post(reverse('cashregister:close_shift', args=[shift.pk]), {'actual_amount': '8300', 'notes': ''})
        shift.refresh_from_db()
        self.assertEqual(shift.difference, Decimal('-200.00'))      # faltante
        # otro turno con sobrante
        self.abrir_turno('1000')
        s2 = CashShift.objects.get(status='open')
        self.c.post(reverse('cashregister:close_shift', args=[s2.pk]), {'actual_amount': '1100', 'notes': ''})
        s2.refresh_from_db()
        self.assertEqual(s2.difference, Decimal('100.00'))          # sobrante

    def test_el_cierre_guarda_resumen_por_medio_de_pago(self):
        shift = self._dia_completo()
        self.c.post(reverse('cashregister:close_shift', args=[shift.pk]), {'actual_amount': '8500', 'notes': ''})
        resumen = {s.payment_method.code: s.total_amount for s in ShiftPaymentSummary.objects.filter(cash_shift=shift)}
        self.assertEqual(resumen, {'cash': Decimal('4000.00'), 'transfer': Decimal('3500.00')})

    def test_un_turno_cerrado_no_se_cierra_ni_modifica(self):
        shift = self._dia_completo()
        self.c.post(reverse('cashregister:close_shift', args=[shift.pk]), {'actual_amount': '8500', 'notes': ''})
        self.c.post(reverse('cashregister:close_shift', args=[shift.pk]), {'actual_amount': '1', 'notes': 'x'})
        shift.refresh_from_db()
        self.assertEqual(shift.actual_amount, Decimal('8500'))
        r = self.c.post(reverse('cashregister:add_movement', args=[shift.pk]), {
            'movement_type': 'expense', 'amount': '10', 'payment_method': self.cash.pk, 'description': 'x', 'reference': ''})
        self.assertEqual(shift.movements.filter(description='x').count(), 0)

    def test_no_se_puede_vender_en_un_turno_cerrado(self):
        shift = self._dia_completo()
        self.c.post(reverse('cashregister:close_shift', args=[shift.pk]), {'actual_amount': '8500', 'notes': ''})
        # el POS ya no tiene turno abierto para esta cajera
        r = self.c.get(reverse('pos:main'))
        self.assertIn(r.status_code, (302, 200))
        if r.status_code == 200:
            self.assertContains(r, 'turno', status_code=200)

    def test_otra_cajera_no_puede_cerrar_mi_turno(self):
        shift = self._dia_completo()
        otra = Client()
        otra.force_login(self.otra)
        otra.post(reverse('cashregister:close_shift', args=[shift.pk]), {'actual_amount': '1', 'notes': ''})
        shift.refresh_from_db()
        self.assertEqual(shift.status, 'open')

    def test_la_duena_si_puede_cerrar_el_turno_de_una_cajera(self):
        shift = self._dia_completo()
        due = Client()
        due.force_login(self.duena)
        due.post(reverse('cashregister:close_shift', args=[shift.pk]), {'actual_amount': '8500', 'notes': ''})
        shift.refresh_from_db()
        self.assertEqual(shift.status, 'closed')

    def test_reporte_de_cierre_z_descargable_con_los_totales_por_medio(self):
        shift = self._dia_completo()
        self.c.post(reverse('cashregister:close_shift', args=[shift.pk]), {'actual_amount': '8500', 'notes': ''})
        r = self.c.get(reverse('cashregister:shift_report_pdf', args=[shift.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn('attachment', r['Content-Disposition'])
        texto = r.content.decode('utf-8')
        self.assertIn('Efectivo', texto)
        self.assertIn('Transferencia', texto)
        self.assertIn('4.000,00', texto)      # efectivo
        self.assertIn('3.500,00', texto)      # transferencias

    def test_detalle_y_listado_de_turnos(self):
        shift = self._dia_completo()
        self.assertContains(self.c.get(reverse('cashregister:shift_detail', args=[shift.pk])), 'Bolsas')
        self.assertEqual(self.c.get(reverse('cashregister:shift_list')).status_code, 200)
        self.assertEqual(self.c.get(reverse('cashregister:shift_data_api', args=[shift.pk])).status_code, 200)
