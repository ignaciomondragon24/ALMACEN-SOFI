"""
Flujo: crear y administrar promociones desde la pantalla, y que después descuenten
bien en la caja. Cubre los tipos que Sofia pidió: 2x1, descuento por segunda unidad,
combos fijos, más precio fijo por cantidad, descuento porcentual y descuento por cantidad.
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
from pos.services import CartService, POSService
from promotions.models import Promotion, PromotionProduct, PromotionSubgroup
from stocks.models import Product

User = get_user_model()


class PromoBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        PaymentMethod.get_default_methods()
        cls.dueña = User.objects.create_user('dueña_promo', password='x')
        cls.dueña.groups.add(Group.objects.get_or_create(name='Admin')[0])
        cls.encargada = User.objects.create_user('enc_promo', password='x')
        cls.encargada.groups.add(Group.objects.get_or_create(name='Cajero Manager')[0])
        cls.cajera = User.objects.create_user('caj_promo', password='x')
        cls.cajera.groups.add(Group.objects.get_or_create(name='Cashier')[0])
        reg = CashRegister.objects.create(name='C', code='C1', is_active=True)
        cls.shift = CashShift.objects.create(cash_register=reg, cashier=cls.encargada,
                                             initial_amount=Decimal('0'), status='open')
        mk = lambda n, s, p: Product.objects.create(name=n, sku=s, cost_price=p / 2, sale_price=p, current_stock=Decimal('100'))
        cls.galle = mk('Galletitas', 'GA', Decimal('1000'))
        cls.jugo = mk('Jugo', 'JU', Decimal('500'))
        cls.pan = mk('Pan lactal', 'PL', Decimal('2000'))
        cls.hamb = mk('Pan hamburguesa', 'PH', Decimal('1500'))

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.dueña)
        self.tx = POSService.create_transaction(POSService.get_or_create_session(self.shift))

    def crear(self, **datos):
        base = {'name': 'Promo', 'status': 'active'}
        base.update(datos)
        return self.c.post(reverse('promotions:promotion_create'), base)

    def total_con(self, *lineas):
        for prod, cant in lineas:
            CartService.add_item(self.tx, prod.pk, Decimal(str(cant)))
        self.tx.refresh_from_db()
        return self.tx.total


class CrearPromocionesTests(PromoBase):
    def test_2x1(self):
        r = self.crear(name='2x1 galletitas', promo_type='nxm', buy_quantity='2', pay_quantity='1',
                       products=str(self.galle.pk))
        self.assertEqual(r.status_code, 302, r.content[:300])
        p = Promotion.objects.get()
        self.assertEqual((p.quantity_required, p.quantity_charged), (2, 1))
        self.assertEqual(self.total_con((self.galle, 2)), Decimal('1000.00'))

    def test_3x2(self):
        self.crear(name='3x2', promo_type='nxm', buy_quantity='3', pay_quantity='2', products=str(self.galle.pk))
        self.assertEqual(self.total_con((self.galle, 3)), Decimal('2000.00'))

    def test_precio_fijo_por_cantidad(self):
        self.crear(name='3 jugos x $1200', promo_type='nx_fixed_price', nx_quantity='3',
                   nx_fixed_price='1200', products=str(self.jugo.pk))
        self.assertEqual(self.total_con((self.jugo, 3)), Decimal('1200.00'))

    def test_segunda_unidad_con_descuento(self):
        r = self.crear(name='2da al 50%', promo_type='second_unit', second_unit_discount='50',
                       products=str(self.galle.pk))
        self.assertEqual(r.status_code, 302)
        # 2 galletitas: la segunda con 50% → 1000 + 500
        self.assertEqual(self.total_con((self.galle, 2)), Decimal('1500.00'))

    def test_descuento_porcentual(self):
        self.crear(name='Jugo -20%', promo_type='simple_discount', discount_percent_simple='20',
                   products=str(self.jugo.pk))
        self.assertEqual(self.total_con((self.jugo, 2)), Decimal('800.00'))

    def test_descuento_por_cantidad(self):
        self.crear(name='Docena -10%', promo_type='quantity_discount', discount_percent='10',
                   min_quantity='6', products=str(self.jugo.pk))
        self.assertEqual(self.total_con((self.jugo, 6)), Decimal('2700.00'))

    def test_combo_de_productos_a_precio_fijo(self):
        self.crear(name='Combo merienda', promo_type='combo', combo_price='1200',
                   products=f'{self.galle.pk},{self.jugo.pk}')
        self.assertEqual(self.total_con((self.galle, 1), (self.jugo, 1)), Decimal('1200.00'))

    def test_combo_por_subgrupos(self):
        r = self.crear(name='2 lactal + 1 hamburguesa', promo_type='subgroup_combo',
                       subgroup_combo_price='4500', products_a=str(self.pan.pk), products_b=str(self.hamb.pk),
                       group_a_quantity='2', group_b_quantity='1')
        self.assertEqual(r.status_code, 302, r.content[:300])
        sg = {s.slot: s for s in PromotionSubgroup.objects.all()}
        self.assertEqual(sg['a'].quantity_required, 2)
        self.assertEqual(self.total_con((self.pan, 2), (self.hamb, 1)), Decimal('4500.00'))

    def test_validaciones_no_crean_promociones_incompletas(self):
        casos = [
            dict(promo_type='nx_fixed_price', nx_quantity='3', nx_fixed_price='0', products=str(self.jugo.pk)),
            dict(promo_type='second_unit', second_unit_discount='0', products=str(self.jugo.pk)),
            dict(promo_type='simple_discount', discount_percent_simple='0', products=str(self.jugo.pk)),
            dict(promo_type='nxm', buy_quantity='2', pay_quantity='1', products=''),
            dict(promo_type='subgroup_combo', subgroup_combo_price='100', products_a='', products_b=str(self.pan.pk)),
        ]
        for datos in casos:
            r = self.crear(**datos)
            self.assertEqual(r.status_code, 200, datos)           # vuelve al formulario con el error
        self.assertFalse(Promotion.objects.exists())

    def test_la_cajera_no_puede_crear_promociones(self):
        c = Client()
        c.force_login(self.cajera)
        r = c.post(reverse('promotions:promotion_create'), {
            'name': 'x', 'promo_type': 'nxm', 'buy_quantity': '2', 'pay_quantity': '1', 'products': str(self.galle.pk)})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Promotion.objects.exists())

    def test_formulario_de_alta_abre(self):
        self.assertEqual(self.c.get(reverse('promotions:promotion_create')).status_code, 200)


class VigenciaTests(PromoBase):
    def test_promo_vencida_no_aplica(self):
        ayer = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.crear(name='Vencida', promo_type='nxm', buy_quantity='2', pay_quantity='1',
                   products=str(self.galle.pk), end_date=ayer)
        self.assertEqual(self.total_con((self.galle, 2)), Decimal('2000.00'))

    def test_promo_futura_no_aplica_todavia(self):
        manana = (timezone.localdate() + timedelta(days=1)).isoformat()
        self.crear(name='Futura', promo_type='nxm', buy_quantity='2', pay_quantity='1',
                   products=str(self.galle.pk), start_date=manana)
        self.assertEqual(self.total_con((self.galle, 2)), Decimal('2000.00'))

    def test_promo_vigente_hoy_aplica(self):
        hoy = timezone.localdate()
        self.crear(name='Vigente', promo_type='nxm', buy_quantity='2', pay_quantity='1',
                   products=str(self.galle.pk), start_date=(hoy - timedelta(days=2)).isoformat(),
                   end_date=(hoy + timedelta(days=2)).isoformat())
        self.assertEqual(self.total_con((self.galle, 2)), Decimal('1000.00'))

    def test_dia_de_la_semana(self):
        hoy = timezone.localdate()
        dias = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        otro = dias[(hoy.weekday() + 3) % 7]
        self.crear(name='Solo otro día', promo_type='nxm', buy_quantity='2', pay_quantity='1',
                   products=str(self.galle.pk), **{otro: 'on'})
        self.assertEqual(self.total_con((self.galle, 2)), Decimal('2000.00'))


class AdministrarPromocionesTests(PromoBase):
    def setUp(self):
        super().setUp()
        self.crear(name='2x1 galletitas', promo_type='nxm', buy_quantity='2', pay_quantity='1',
                   products=str(self.galle.pk))
        self.promo = Promotion.objects.get()

    def test_listado_y_detalle(self):
        self.assertContains(self.c.get(reverse('promotions:promotion_list')), '2x1 galletitas')
        self.assertContains(self.c.get(reverse('promotions:promotion_detail', args=[self.promo.pk])), 'Galletitas')
        self.assertEqual(self.c.get(reverse('promotions:promotion_list'), {'status': 'active', 'search': 'galle'}).status_code, 200)

    def test_editar_cambia_la_regla_y_los_productos(self):
        r = self.c.post(reverse('promotions:promotion_edit', args=[self.promo.pk]), {
            'name': '3x2 jugos', 'promo_type': 'nxm', 'status': 'active', 'buy_quantity': '3',
            'pay_quantity': '2', 'products': str(self.jugo.pk)})
        self.assertEqual(r.status_code, 302, r.content[:300])
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.name, '3x2 jugos')
        self.assertEqual(list(self.promo.products.values_list('pk', flat=True)), [self.jugo.pk])
        self.assertEqual(self.total_con((self.jugo, 3)), Decimal('1000.00'))

    def test_pausar_y_activar(self):
        self.c.post(reverse('promotions:promotion_pause', args=[self.promo.pk]))
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.status, 'paused')
        self.assertEqual(self.total_con((self.galle, 2)), Decimal('2000.00'))
        self.c.post(reverse('promotions:promotion_activate', args=[self.promo.pk]))
        self.promo.refresh_from_db()
        self.assertEqual(self.promo.status, 'active')

    def test_borrar_pide_escribir_el_nombre(self):
        url = reverse('promotions:promotion_delete', args=[self.promo.pk])
        self.c.post(url, {'confirm_name': 'otro nombre'})
        self.assertTrue(Promotion.objects.filter(pk=self.promo.pk).exists())
        self.c.post(url, {'confirm_name': '2x1 galletitas'})
        self.assertFalse(Promotion.objects.filter(pk=self.promo.pk).exists())

    def test_la_encargada_puede_editar_pero_no_borrar(self):
        e = Client()
        e.force_login(self.encargada)
        self.assertEqual(e.get(reverse('promotions:promotion_edit', args=[self.promo.pk])).status_code, 200)
        e.post(reverse('promotions:promotion_delete', args=[self.promo.pk]), {'confirm_name': '2x1 galletitas'})
        self.assertTrue(Promotion.objects.filter(pk=self.promo.pk).exists())

    def test_calculadora_de_promociones_de_la_pantalla(self):
        r = self.c.post(reverse('promotions:api_calculate'), json.dumps({
            'items': [{'product_id': self.galle.pk, 'quantity': 2, 'unit_price': 1000}]}),
            content_type='application/json')
        self.assertEqual(r.status_code, 200)

    def test_promo_con_productos_borrados_no_rompe_la_caja(self):
        self.galle.delete()      # baja lógica
        self.assertEqual(self.total_con((self.jugo, 1)), Decimal('500.00'))
