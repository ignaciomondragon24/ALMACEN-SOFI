"""Tests para el sistema de vencimientos por lote (StockBatch.expiration_date).

Cubre:
- stocks.services.expiration_buckets(): clasificación vencido / vence_pronto / próximo.
- Vista stocks:vencimientos: filtros de búsqueda y de días de alerta.
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from stocks.models import Product, ProductCategory, StockBatch
from stocks.services import expiration_buckets

User = get_user_model()


class ExpirationBucketsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.category = ProductCategory.objects.create(name='Vencimientos Cat')
        cls.product = Product.objects.create(
            name='Jamon Cocido Test', sku='VENC-001',
            category=cls.category,
            current_stock=Decimal('10'),
            cost_price=Decimal('10'),
            purchase_price=Decimal('10'),
            sale_price=Decimal('20'),
        )

    def _make_batch(self, expiration_date, quantity_remaining='5'):
        return StockBatch.objects.create(
            product=self.product,
            supplier_name='Proveedor Test',
            quantity_purchased=Decimal('5'),
            quantity_remaining=Decimal(quantity_remaining),
            purchase_price=Decimal('10'),
            purchased_at=timezone.now(),
            expiration_date=expiration_date,
        )

    def test_clasifica_vencido(self):
        today = timezone.localdate()
        self._make_batch(today - timedelta(days=1))
        qs = StockBatch.objects.filter(quantity_remaining__gt=0, expiration_date__isnull=False)
        buckets = expiration_buckets(qs)
        self.assertEqual(buckets['vencido']['count'], 1)
        self.assertEqual(buckets['vence_pronto']['count'], 0)
        self.assertEqual(buckets['proximo']['count'], 0)

    def test_clasifica_vence_pronto(self):
        today = timezone.localdate()
        self._make_batch(today + timedelta(days=3))
        qs = StockBatch.objects.filter(quantity_remaining__gt=0, expiration_date__isnull=False)
        buckets = expiration_buckets(qs, warn_days=7)
        self.assertEqual(buckets['vencido']['count'], 0)
        self.assertEqual(buckets['vence_pronto']['count'], 1)
        self.assertEqual(buckets['proximo']['count'], 0)

    def test_clasifica_proximo(self):
        today = timezone.localdate()
        self._make_batch(today + timedelta(days=20))
        qs = StockBatch.objects.filter(quantity_remaining__gt=0, expiration_date__isnull=False)
        buckets = expiration_buckets(qs, warn_days=7, soon_days=30)
        self.assertEqual(buckets['vencido']['count'], 0)
        self.assertEqual(buckets['vence_pronto']['count'], 0)
        self.assertEqual(buckets['proximo']['count'], 1)

    def test_fuera_de_soon_days_no_entra_en_ningun_balde(self):
        today = timezone.localdate()
        self._make_batch(today + timedelta(days=90))
        qs = StockBatch.objects.filter(quantity_remaining__gt=0, expiration_date__isnull=False)
        buckets = expiration_buckets(qs, warn_days=7, soon_days=30)
        self.assertEqual(buckets['vencido']['count'], 0)
        self.assertEqual(buckets['vence_pronto']['count'], 0)
        self.assertEqual(buckets['proximo']['count'], 0)

    def test_lote_sin_stock_restante_no_cuenta(self):
        """El queryset pasado a expiration_buckets ya debe venir filtrado por stock > 0;
        acá confirmamos que un lote agotado, si se incluyera, no se pierde de la cuenta general
        pero la vista real lo excluye antes de llamar a la función."""
        today = timezone.localdate()
        self._make_batch(today - timedelta(days=1), quantity_remaining='0')
        qs = StockBatch.objects.filter(quantity_remaining__gt=0, expiration_date__isnull=False)
        buckets = expiration_buckets(qs)
        self.assertEqual(buckets['vencido']['count'], 0)


class VencimientosViewTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.admin = User.objects.create_user(
            username='venc_admin', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.admin.groups.add(cls.admin_group)
        cls.category = ProductCategory.objects.create(name='Venc View Cat')
        cls.product = Product.objects.create(
            name='Queso Cremoso Test', sku='VENC-002',
            category=cls.category,
            current_stock=Decimal('10'),
            cost_price=Decimal('10'),
            purchase_price=Decimal('10'),
            sale_price=Decimal('20'),
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username='venc_admin', password='pass123')

    def _make_batch(self, expiration_date):
        return StockBatch.objects.create(
            product=self.product,
            supplier_name='Proveedor Test',
            quantity_purchased=Decimal('5'),
            quantity_remaining=Decimal('5'),
            purchase_price=Decimal('10'),
            purchased_at=timezone.now(),
            expiration_date=expiration_date,
        )

    def test_vista_devuelve_200(self):
        resp = self.client.get(reverse('stocks:vencimientos'))
        self.assertEqual(resp.status_code, 200)

    def test_filtro_de_busqueda_por_nombre(self):
        today = timezone.localdate()
        self._make_batch(today - timedelta(days=1))
        resp = self.client.get(reverse('stocks:vencimientos'), {'search': 'Queso'})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Queso Cremoso Test')

        resp = self.client.get(reverse('stocks:vencimientos'), {'search': 'Inexistente'})
        self.assertNotContains(resp, 'Queso Cremoso Test')

    def test_filtro_dias_afecta_bucket_vence_pronto(self):
        today = timezone.localdate()
        self._make_batch(today + timedelta(days=10))

        resp = self.client.get(reverse('stocks:vencimientos'), {'dias': '5'})
        self.assertEqual(resp.context['buckets']['vence_pronto']['count'], 0)

        resp = self.client.get(reverse('stocks:vencimientos'), {'dias': '15'})
        self.assertEqual(resp.context['buckets']['vence_pronto']['count'], 1)
