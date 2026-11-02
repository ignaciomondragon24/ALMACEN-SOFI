"""Catálogo de proveedor como checklist: marcar/desmarcar productos y guardar de una."""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from django.urls import reverse

from purchase.models import Supplier, SupplierProduct
from stocks.models import Product, ProductCategory

User = get_user_model()


class SupplierChecklistTests(TestCase):

    def setUp(self):
        group, _ = Group.objects.get_or_create(name='Admin')
        admin = User.objects.create_user(
            username='check_admin', password='pass123', is_superuser=True, is_staff=True)
        admin.groups.add(group)
        self.client = Client()
        self.client.login(username='check_admin', password='pass123')

        cat = ProductCategory.objects.create(name='Almacén')
        self.supplier = Supplier.objects.create(name='Distribuidora X')
        self.arroz = Product.objects.create(
            name='Arroz', category=cat, sale_price=Decimal('1500'), cost_price=Decimal('900'))
        self.fideos = Product.objects.create(
            name='Fideos', category=cat, sale_price=Decimal('1200'), purchase_price=Decimal('700'))
        self.yerba = Product.objects.create(
            name='Yerba', category=cat, sale_price=Decimal('3000'), cost_price=Decimal('2000'))
        self.url = reverse('purchase:supplier_products', args=[self.supplier.pk])

    def test_get_lista_todos_los_productos_activos(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(resp.context['rows']), 3)
        self.assertFalse(any(r['checked'] for r in resp.context['rows']))

    def test_marcar_crea_vinculos_con_costo_por_defecto(self):
        self.client.post(self.url, {'selected': [self.arroz.pk, self.fideos.pk]})
        links = {l.product_id: l for l in self.supplier.supplier_products.all()}
        self.assertEqual(set(links), {self.arroz.pk, self.fideos.pk})
        self.assertEqual(links[self.arroz.pk].cost_price, Decimal('900'))
        self.assertEqual(links[self.fideos.pk].cost_price, Decimal('700'))

    def test_precio_con_coma_y_actualizacion(self):
        self.client.post(self.url, {
            'selected': [self.arroz.pk], f'cost_{self.arroz.pk}': '950,50'})
        self.assertEqual(
            SupplierProduct.objects.get(product=self.arroz).cost_price, Decimal('950.50'))

    def test_desmarcar_quita_y_marcado_se_conserva(self):
        SupplierProduct.objects.create(
            supplier=self.supplier, product=self.arroz, cost_price=Decimal('800'), notes='nota')
        SupplierProduct.objects.create(
            supplier=self.supplier, product=self.yerba, cost_price=Decimal('1900'))
        self.client.post(self.url, {'selected': [self.arroz.pk]})
        self.assertFalse(SupplierProduct.objects.filter(product=self.yerba).exists())
        arroz = SupplierProduct.objects.get(product=self.arroz)
        self.assertEqual(arroz.cost_price, Decimal('800'))  # sin precio en el POST: se conserva
        self.assertEqual(arroz.notes, 'nota')

    def test_no_toca_otros_proveedores(self):
        otro = Supplier.objects.create(name='Otro')
        SupplierProduct.objects.create(supplier=otro, product=self.arroz, cost_price=Decimal('1'))
        self.client.post(self.url, {'selected': []})
        self.assertTrue(SupplierProduct.objects.filter(supplier=otro).exists())

    def test_precio_invalido_no_rompe(self):
        resp = self.client.post(self.url, {
            'selected': [self.arroz.pk], f'cost_{self.arroz.pk}': 'abc'})
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            SupplierProduct.objects.get(product=self.arroz).cost_price, Decimal('900'))
