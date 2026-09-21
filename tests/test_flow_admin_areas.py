"""
Flujo: gastos (y su efecto en la caja), usuarios y roles, cambio de contraseña, login,
empresa/sucursales, y edición/cancelación de órdenes de compra.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from cashregister.models import CashMovement, CashRegister, CashShift, PaymentMethod
from company.models import Branch, Company
from expenses.models import Expense, ExpenseCategory
from purchase.models import Purchase, PurchaseItem, Supplier
from stocks.models import Product

User = get_user_model()


def usuario(username, rol=None, **extra):
    u = User.objects.create_user(username, password='clave-larga-1', **extra)
    if rol:
        u.groups.add(Group.objects.get_or_create(name=rol)[0])
    return u


class GastosTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        PaymentMethod.get_default_methods()
        cls.dueña = usuario('dueña_g', 'Admin')
        cls.cat = ExpenseCategory.objects.create(name='Servicios')
        cls.reg = CashRegister.objects.create(name='C', code='C1', is_active=True)

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.dueña)

    def gasto(self, **extra):
        data = {'category': self.cat.pk, 'description': 'Luz', 'amount': '12000',
                'expense_date': timezone.localdate().isoformat(), 'payment_method': 'transfer',
                'receipt_number': '', 'notes': ''}
        data.update(extra)
        return self.c.post(reverse('expenses:expense_create'), data)

    def test_gasto_por_transferencia_no_toca_la_caja(self):
        r = self.gasto()
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['form'].errors)
        self.assertEqual(Expense.objects.get().amount, Decimal('12000'))
        self.assertFalse(CashMovement.objects.exists())

    def test_gasto_en_efectivo_que_sale_del_cajon_se_descuenta_en_el_turno(self):
        shift = CashShift.objects.create(cash_register=self.reg, cashier=self.dueña,
                                         initial_amount=Decimal('5000'), status='open')
        self.gasto(payment_method='cash', affects_cash_drawer='on', amount='800', description='Bolsas')
        mov = CashMovement.objects.get()
        self.assertEqual((mov.movement_type, mov.amount), ('expense', Decimal('800')))
        self.assertEqual(shift.calculate_expected(), Decimal('4200.00'))

    def test_gasto_del_cajon_sin_turno_abierto_se_rechaza(self):
        r = self.gasto(payment_method='cash', affects_cash_drawer='on')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Expense.objects.exists())

    def test_editar_el_monto_actualiza_el_movimiento_de_caja(self):
        shift = CashShift.objects.create(cash_register=self.reg, cashier=self.dueña,
                                         initial_amount=Decimal('5000'), status='open')
        self.gasto(payment_method='cash', affects_cash_drawer='on', amount='800')
        exp = Expense.objects.get()
        self.c.post(reverse('expenses:expense_edit', args=[exp.pk]), {
            'category': self.cat.pk, 'description': 'Bolsas', 'amount': '1000', 'expense_date': exp.expense_date.isoformat(),
            'payment_method': 'cash', 'affects_cash_drawer': 'on', 'receipt_number': '', 'notes': ''})
        self.assertEqual(CashMovement.objects.get().amount, Decimal('1000'))
        self.assertEqual(shift.calculate_expected(), Decimal('4000.00'))

    def test_si_deja_de_salir_del_cajon_se_quita_el_movimiento(self):
        CashShift.objects.create(cash_register=self.reg, cashier=self.dueña, initial_amount=Decimal('5000'), status='open')
        self.gasto(payment_method='cash', affects_cash_drawer='on', amount='800')
        exp = Expense.objects.get()
        self.c.post(reverse('expenses:expense_edit', args=[exp.pk]), {
            'category': self.cat.pk, 'description': 'Bolsas', 'amount': '800', 'expense_date': exp.expense_date.isoformat(),
            'payment_method': 'transfer', 'receipt_number': '', 'notes': ''})
        self.assertFalse(CashMovement.objects.exists())

    def test_borrar_el_gasto_borra_su_movimiento_de_caja(self):
        CashShift.objects.create(cash_register=self.reg, cashier=self.dueña, initial_amount=Decimal('5000'), status='open')
        self.gasto(payment_method='cash', affects_cash_drawer='on', amount='800')
        exp = Expense.objects.get()
        self.c.post(reverse('expenses:expense_delete', args=[exp.pk]))
        self.assertFalse(Expense.objects.exists())
        self.assertFalse(CashMovement.objects.exists())

    def test_categorias_recurrentes_y_reporte(self):
        self.gasto()
        r = self.c.post(reverse('expenses:category_create'), {'name': 'Sueldos', 'description': '', 'color': '#123456', 'is_active': 'on'})
        self.assertEqual(r.status_code, 302)
        for name in ('expenses:expense_list', 'expenses:category_list', 'expenses:recurring_list', 'expenses:expense_report'):
            self.assertEqual(self.c.get(reverse(name)).status_code, 200, name)
        self.assertEqual(self.c.get(reverse('expenses:api_expenses_by_category')).status_code, 200)

    def test_solo_la_dueña_ve_gastos(self):
        cj = Client()
        cj.force_login(usuario('caj_g', 'Cashier'))
        self.assertEqual(cj.get(reverse('expenses:expense_list')).status_code, 403)


class UsuariosYAccesoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dueña = usuario('dueña_u', 'Admin')

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.dueña)

    def alta(self, **extra):
        d = {'username': 'lucia', 'email': 'l@x.com', 'first_name': 'Lucía', 'last_name': 'P',
             'is_active': 'on', 'password': 'clave-larga-1', 'password_confirm': 'clave-larga-1', 'role': 'Cashier'}
        d.update(extra)
        return self.c.post(reverse('accounts:user_create'), d)

    def test_crear_cajera_y_que_pueda_entrar(self):
        r = self.alta()
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['form'].errors)
        u = User.objects.get(username='lucia')
        self.assertTrue(u.groups.filter(name='Cashier').exists())
        nueva = Client()
        r = nueva.post(reverse('accounts:login'), {'username': 'lucia', 'password': 'clave-larga-1'})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(nueva.get(reverse('accounts:dashboard')).status_code, 200)

    def test_validaciones_de_alta(self):
        self.assertEqual(self.alta(password_confirm='otra-cosa').status_code, 200)     # no coinciden
        self.assertEqual(self.alta(password='corta', password_confirm='corta').status_code, 200)
        self.assertEqual(self.alta(role='').status_code, 200)                          # sin rol
        self.alta()
        self.assertEqual(self.alta().status_code, 200)                                  # usuario repetido
        self.assertEqual(User.objects.filter(username='lucia').count(), 1)

    def test_login_incorrecto_no_entra(self):
        self.alta()
        nuevo = Client()
        r = nuevo.post(reverse('accounts:login'), {'username': 'lucia', 'password': 'mal'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(nuevo.get(reverse('accounts:dashboard')).status_code, 302)

    def test_usuario_desactivado_no_puede_entrar(self):
        self.alta()
        u = User.objects.get(username='lucia')
        self.c.post(reverse('accounts:user_toggle', args=[u.pk]))
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        r = Client().post(reverse('accounts:login'), {'username': 'lucia', 'password': 'clave-larga-1'})
        self.assertEqual(r.status_code, 200)

    def test_login_no_redirige_a_sitios_externos(self):
        self.alta()
        r = Client().post(reverse('accounts:login') + '?next=https://sitio-malo.example/robo',
                          {'username': 'lucia', 'password': 'clave-larga-1'})
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('sitio-malo', r['Location'])

    def test_editar_usuario_cambia_su_rol(self):
        self.alta()
        u = User.objects.get(username='lucia')
        self.c.post(reverse('accounts:user_edit', args=[u.pk]), {
            'username': 'lucia', 'email': 'l@x.com', 'first_name': 'Lucía', 'last_name': 'P',
            'is_active': 'on', 'role': 'Cajero Manager'})
        self.assertEqual(list(u.groups.values_list('name', flat=True)), ['Cajero Manager'])

    def test_un_admin_creado_desde_la_pantalla_es_admin_de_verdad(self):
        """Antes solo el grupo Admin daba acceso a algunas pantallas y no a otras."""
        self.alta(username='otra_admin', role='Admin')
        adm = Client()
        adm.force_login(User.objects.get(username='otra_admin'))
        for name in ('accounts:user_list', 'expenses:expense_list', 'purchase:purchase_list',
                     'promotions:promotion_list', 'stocks:import_excel', 'company:settings'):
            self.assertEqual(adm.get(reverse(name)).status_code, 200, name)

    def test_no_se_puede_desactivar_a_si_mismo(self):
        self.c.post(reverse('accounts:user_toggle', args=[self.dueña.pk]))
        self.dueña.refresh_from_db()
        self.assertTrue(self.dueña.is_active)
        self.c.post(reverse('accounts:user_delete', args=[self.dueña.pk]))
        self.dueña.refresh_from_db()
        self.assertTrue(self.dueña.is_active)

    def test_cambiar_contraseña(self):
        u = usuario('cambia', 'Cashier')
        c = Client()
        c.force_login(u)
        c.post(reverse('accounts:change_password'), {'current_password': 'mala', 'new_password': 'nueva-clave-99', 'confirm_password': 'nueva-clave-99'})
        u.refresh_from_db()
        self.assertTrue(u.check_password('clave-larga-1'))                  # contraseña actual mal → no cambia
        c.post(reverse('accounts:change_password'), {'current_password': 'clave-larga-1', 'new_password': 'corta', 'confirm_password': 'corta'})
        u.refresh_from_db()
        self.assertTrue(u.check_password('clave-larga-1'))                  # muy corta → no cambia
        c.post(reverse('accounts:change_password'), {'current_password': 'clave-larga-1', 'new_password': 'nueva-clave-99', 'confirm_password': 'nueva-clave-99'})
        u.refresh_from_db()
        self.assertTrue(u.check_password('nueva-clave-99'))

    def test_perfil(self):
        self.assertEqual(self.c.get(reverse('accounts:profile')).status_code, 200)

    def test_cada_rol_ve_solo_lo_suyo(self):
        cajera = Client(); cajera.force_login(usuario('caj_r', 'Cashier'))
        for name in ('accounts:user_list', 'purchase:purchase_list', 'expenses:expense_list',
                     'promotions:promotion_list', 'stocks:import_excel'):
            self.assertEqual(cajera.get(reverse(name)).status_code, 403, name)
        for name in ('cashregister:dashboard', 'accounts:dashboard'):
            self.assertIn(cajera.get(reverse(name)).status_code, (200, 302), name)


class EmpresaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dueña = usuario('dueña_e', 'Admin')

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.dueña)

    def test_datos_de_la_empresa_y_sucursales(self):
        self.assertEqual(self.c.get(reverse('company:settings')).status_code, 200)
        r = self.c.post(reverse('company:settings'), {
            'name': 'Almacén de Sofia', 'legal_name': 'Sofia SRL', 'cuit': '', 'phone': '', 'email': '',
            'address': 'Calle 1', 'tax_condition': 'monotributo', 'currency_symbol': '$',
            'decimal_separator': ',', 'thousands_separator': '.'})
        self.assertIn(r.status_code, (200, 302))
        r = self.c.post(reverse('company:branch_create'), {'name': 'Sucursal 2', 'code': 'S2', 'address': 'x', 'phone': '', 'is_active': 'on'})
        self.assertIn(r.status_code, (200, 302))
        for name in ('company:branch_list',):
            self.assertEqual(self.c.get(reverse(name)).status_code, 200)


class OrdenesDeCompraEdicionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dueña = usuario('dueña_oc', 'Admin')
        cls.prov = Supplier.objects.create(name='Prov')
        cls.a = Product.objects.create(name='Aceite', sku='A', cost_price=Decimal('900'), sale_price=Decimal('1500'), current_stock=Decimal('10'))
        cls.b = Product.objects.create(name='Fideos', sku='B', cost_price=Decimal('300'), sale_price=Decimal('700'), current_stock=Decimal('10'))

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.dueña)
        r = self.c.post(reverse('purchase:purchase_create'), json.dumps({
            'supplier_id': self.prov.pk, 'tax_percent': 0,
            'items': [{'product_id': self.a.pk, 'quantity': 10, 'unit_cost': 900},
                      {'product_id': self.b.pk, 'quantity': 5, 'unit_cost': 300}]}), content_type='application/json')
        self.oc = Purchase.objects.get()
        self.items = list(self.oc.items.order_by('id'))

    def _form(self, filas, tax='21', proveedor=None):
        d = {'supplier': (proveedor or self.prov).pk, 'order_date': '', 'tax_percent': tax, 'notes': '',
             'items-TOTAL_FORMS': str(len(filas)), 'items-INITIAL_FORMS': str(sum(1 for f in filas if f.get('id'))),
             'items-MIN_NUM_FORMS': '0', 'items-MAX_NUM_FORMS': '1000'}
        for i, f in enumerate(filas):
            for k, v in f.items():
                d[f'items-{i}-{k}'] = v
            d[f'items-{i}-purchase'] = self.oc.pk
        return d

    def test_editar_cantidades_recalcula_el_total(self):
        r = self.c.post(reverse('purchase:purchase_edit', args=[self.oc.pk]), self._form([
            {'id': self.items[0].pk, 'product': self.a.pk, 'quantity': '20', 'unit_cost': '900'},
            {'id': self.items[1].pk, 'product': self.b.pk, 'quantity': '5', 'unit_cost': '300'}], tax='0'))
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['formset'].errors)
        self.oc.refresh_from_db()
        self.assertEqual(self.oc.subtotal, Decimal('19500.00'))
        self.assertEqual(self.oc.total, Decimal('19500.00'))

    def test_quitar_un_item_y_aplicar_iva(self):
        self.c.post(reverse('purchase:purchase_edit', args=[self.oc.pk]), self._form([
            {'id': self.items[0].pk, 'product': self.a.pk, 'quantity': '10', 'unit_cost': '900'},
            {'id': self.items[1].pk, 'product': self.b.pk, 'quantity': '5', 'unit_cost': '300', 'DELETE': 'on'}], tax='21'))
        self.oc.refresh_from_db()
        self.assertEqual(self.oc.items.count(), 1)
        self.assertEqual(self.oc.subtotal, Decimal('9000.00'))
        self.assertEqual(self.oc.total, Decimal('10890.00'))

    def test_cantidad_con_decimales_en_producto_comun_se_rechaza(self):
        r = self.c.post(reverse('purchase:purchase_edit', args=[self.oc.pk]), self._form([
            {'id': self.items[0].pk, 'product': self.a.pk, 'quantity': '2.5', 'unit_cost': '900'},
            {'id': self.items[1].pk, 'product': self.b.pk, 'quantity': '5', 'unit_cost': '300'}]))
        self.assertEqual(r.status_code, 200)
        self.items[0].refresh_from_db()
        self.assertEqual(self.items[0].quantity, Decimal('10'))

    def test_cancelar_orden_no_toca_stock_ni_genera_gasto(self):
        self.c.post(reverse('purchase:purchase_cancel', args=[self.oc.pk]))
        self.oc.refresh_from_db()
        self.assertEqual(self.oc.status, 'cancelled')
        self.a.refresh_from_db()
        self.assertEqual(self.a.current_stock, Decimal('10'))
        self.assertFalse(Expense.objects.exists())

    def test_no_se_puede_recibir_dos_veces(self):
        self.c.post(reverse('purchase:purchase_receive', args=[self.oc.pk]))
        self.c.post(reverse('purchase:purchase_receive', args=[self.oc.pk]))
        self.a.refresh_from_db()
        self.assertEqual(self.a.current_stock, Decimal('20'))          # 10 + 10, una sola vez
        self.assertEqual(Expense.objects.count(), 1)

    def test_no_se_puede_cancelar_una_orden_recibida(self):
        self.c.post(reverse('purchase:purchase_receive', args=[self.oc.pk]))
        self.c.post(reverse('purchase:purchase_cancel', args=[self.oc.pk]))
        self.oc.refresh_from_db()
        self.assertEqual(self.oc.status, 'received')

    def test_recibir_con_precio_de_venta_actualiza_el_producto(self):
        PurchaseItem.objects.filter(pk=self.items[0].pk).update(sale_price=Decimal('1800'))
        self.c.post(reverse('purchase:purchase_receive', args=[self.oc.pk]))
        self.a.refresh_from_db()
        self.assertEqual(self.a.sale_price, Decimal('1800'))

    def test_listado_filtros_y_detalle(self):
        self.assertContains(self.c.get(reverse('purchase:purchase_list')), self.oc.order_number)
        for q in ({'status': 'draft'}, {'search': 'OC-'}, {'supplier': self.prov.pk}):
            self.assertEqual(self.c.get(reverse('purchase:purchase_list'), q).status_code, 200)
        self.assertEqual(self.c.get(reverse('purchase:purchase_detail', args=[self.oc.pk])).status_code, 200)
