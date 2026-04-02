"""
Tests for caramelera create/edit views and API.
Covers:
- GET caramelera_list returns 200
- GET caramelera_create returns 200
- POST api_caramelera_save with valid data creates caramelera + components
- POST with missing name returns 400
- POST with no rows returns 400
- Weighted average cost calculation
- Edit (pk) updates existing caramelera
"""
import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from stocks.models import Product, ProductCategory
from granel.models import CarameleraComponent

User = get_user_model()


class CarameleraFormTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        # stock_manager_required checks for 'Admin' or 'Cajero Manager'
        cls.sm_group, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user(
            username='stockmgr', password='pass123',
            first_name='Stock', last_name='Mgr'
        )
        cls.user.groups.add(cls.sm_group)

        cls.category = ProductCategory.objects.create(name='Gomitas Test')

        # Two bulk products (they have weight_per_unit_grams > 0)
        cls.bulk1 = Product.objects.create(
            sku='BULK-001',
            name='Gomitas Ositos 1kg',
            sale_price=Decimal('5000'),
            cost_price=Decimal('3000'),
            weight_per_unit_grams=Decimal('1000'),
            current_stock=Decimal('5'),
            category=cls.category,
        )
        cls.bulk2 = Product.objects.create(
            sku='BULK-002',
            name='Caramelos Acidos 500g',
            sale_price=Decimal('2000'),
            cost_price=Decimal('1000'),
            weight_per_unit_grams=Decimal('500'),
            current_stock=Decimal('10'),
            category=cls.category,
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='stockmgr', password='pass123')

    # ------ GET views ------

    def test_caramelera_list_returns_200(self):
        url = reverse('granel:caramelera_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

    def test_caramelera_create_returns_200(self):
        url = reverse('granel:caramelera_create')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Nueva Caramelera')

    # ------ POST api_caramelera_save ------

    def _post_save(self, payload, pk=None):
        if pk:
            url = reverse('granel:api_caramelera_save_edit', args=[pk])
        else:
            url = reverse('granel:api_caramelera_save')
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
        )

    def _valid_payload(self):
        return {
            'name': 'Gomitas Surtidas',
            'sale_price_100g': '2500',
            'sale_price_250g': '6250',
            'rows': [
                {'product_id': self.bulk1.pk, 'proportion_grams': '500'},
                {'product_id': self.bulk2.pk, 'proportion_grams': '300'},
            ],
        }

    def test_create_caramelera_success(self):
        resp = self._post_save(self._valid_payload())
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get('success'))
        self.assertIn('pk', data)

        # Product was created
        caramelera = Product.objects.get(pk=data['pk'])
        self.assertTrue(caramelera.is_granel)
        self.assertEqual(caramelera.name, 'Gomitas Surtidas')
        self.assertEqual(caramelera.sale_price, Decimal('2500'))
        self.assertEqual(caramelera.sale_price_250g, Decimal('6250'))

        # Components created
        components = CarameleraComponent.objects.filter(caramelera=caramelera)
        self.assertEqual(components.count(), 2)

    def test_weighted_average_cost_calculation(self):
        """
        bulk1: 3000/1000 = 3.0 $/g, 500g  -> cost = 1500
        bulk2: 1000/500  = 2.0 $/g, 300g  -> cost = 600
        total_grams = 800, total_cost = 2100
        weighted_cpg = 2100/800 = 2.625
        """
        resp = self._post_save(self._valid_payload())
        data = resp.json()
        caramelera = Product.objects.get(pk=data['pk'])

        expected_cpg = Decimal('2.625').quantize(Decimal('0.0001'))
        # Allow small rounding difference (stored as 4 decimal places)
        self.assertAlmostEqual(
            float(caramelera.weighted_avg_cost_per_gram),
            float(expected_cpg),
            places=3,
        )
        # cost_price should be cpg * 100
        expected_cost100 = (expected_cpg * 100).quantize(Decimal('0.01'))
        self.assertEqual(caramelera.cost_price, expected_cost100)

    def test_missing_name_returns_400(self):
        payload = self._valid_payload()
        payload['name'] = ''
        resp = self._post_save(payload)
        self.assertEqual(resp.status_code, 400)
        self.assertIn('error', resp.json())

    def test_zero_price_returns_400(self):
        payload = self._valid_payload()
        payload['sale_price_100g'] = '0'
        resp = self._post_save(payload)
        self.assertEqual(resp.status_code, 400)

    def test_no_rows_returns_400(self):
        payload = self._valid_payload()
        payload['rows'] = []
        resp = self._post_save(payload)
        self.assertEqual(resp.status_code, 400)

    def test_invalid_product_id_returns_400(self):
        payload = self._valid_payload()
        payload['rows'] = [{'product_id': 999999, 'proportion_grams': '100'}]
        resp = self._post_save(payload)
        self.assertEqual(resp.status_code, 400)

    def test_zero_grams_row_returns_400(self):
        payload = self._valid_payload()
        payload['rows'][0]['proportion_grams'] = '0'
        resp = self._post_save(payload)
        self.assertEqual(resp.status_code, 400)

    def test_edit_caramelera_updates_existing(self):
        # First create
        resp = self._post_save(self._valid_payload())
        pk = resp.json()['pk']

        # Now edit: change name and price
        edited = self._valid_payload()
        edited['name'] = 'Gomitas Surtidas Editadas'
        edited['sale_price_100g'] = '3000'
        resp2 = self._post_save(edited, pk=pk)
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json()['success'])

        caramelera = Product.objects.get(pk=pk)
        self.assertEqual(caramelera.name, 'Gomitas Surtidas Editadas')
        self.assertEqual(caramelera.sale_price, Decimal('3000'))
        # Components replaced: still 2 rows
        self.assertEqual(
            CarameleraComponent.objects.filter(caramelera=caramelera).count(), 2
        )

    def test_caramelera_edit_get_returns_200(self):
        # Create one first
        resp = self._post_save(self._valid_payload())
        pk = resp.json()['pk']
        url = reverse('granel:caramelera_edit', args=[pk])
        resp2 = self.client.get(url)
        self.assertEqual(resp2.status_code, 200)

    def test_sku_uniqueness_on_create(self):
        """Creating two carameleras with the same name should not crash."""
        self._post_save(self._valid_payload())
        resp2 = self._post_save(self._valid_payload())
        self.assertEqual(resp2.status_code, 200)
        self.assertTrue(resp2.json()['success'])
        # Both should exist with different SKUs
        qs = Product.objects.filter(is_granel=True, name='Gomitas Surtidas')
        self.assertEqual(qs.count(), 2)
        skus = list(qs.values_list('sku', flat=True))
        self.assertNotEqual(skus[0], skus[1])

    def test_unauthenticated_redirects(self):
        self.client.logout()
        url = reverse('granel:caramelera_list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)
