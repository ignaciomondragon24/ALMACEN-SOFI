from datetime import date
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from purchase.forms import SupplierForm
from purchase.models import Supplier


class DiasDePedidoTests(TestCase):
    def test_varios_dias_se_guardan_ordenados(self):
        form = SupplierForm(data={'name': 'Prov', 'order_days': ['thu', 'mon'], 'is_active': True})
        self.assertTrue(form.is_valid(), form.errors)
        s = form.save()
        self.assertEqual(s.order_days, 'thu,mon')
        self.assertEqual(s.order_days_list, ['mon', 'thu'])
        self.assertEqual(s.order_days_display, 'Lunes, Jueves')

    def test_dia_invalido_rechazado_y_sin_dias_ok(self):
        self.assertFalse(SupplierForm(data={'name': 'P', 'order_days': ['xxx']}).is_valid())
        form = SupplierForm(data={'name': 'P', 'is_active': True})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.save().order_days_list, [])

    def test_orders_on_y_proveedores_de_manana(self):
        Supplier.objects.create(name='A', order_days='mon,thu')
        Supplier.objects.create(name='B', order_days='tue')
        Supplier.objects.create(name='C', order_days='mon', is_active=False)
        lunes, martes, jueves = date(2026, 10, 12), date(2026, 10, 13), date(2026, 10, 15)
        self.assertEqual([s.name for s in Supplier.active_ordering_on(lunes)], ['A'])
        self.assertEqual([s.name for s in Supplier.active_ordering_on(martes)], ['B'])
        self.assertEqual([s.name for s in Supplier.active_ordering_on(jueves)], ['A'])

    def test_aviso_de_manana_en_pantallas(self):
        Supplier.objects.create(name='Fiambres del Sur', order_days='mon,thu')
        user = get_user_model().objects.create_superuser('adm', 'a@a.com', 'x')
        self.client.force_login(user)
        domingo = date(2026, 10, 11)
        with mock.patch('django.utils.timezone.localdate', return_value=domingo):
            r = self.client.get(reverse('purchase:supplier_list'))
        self.assertContains(r, 'Mañana hay que hacer el pedido a:')
        self.assertContains(r, 'Fiambres del Sur')
        martes = date(2026, 10, 13)
        with mock.patch('django.utils.timezone.localdate', return_value=martes):
            r = self.client.get(reverse('purchase:supplier_list'))
        self.assertNotContains(r, 'Mañana hay que hacer el pedido')
