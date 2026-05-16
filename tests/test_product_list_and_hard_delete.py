"""Tests de los fixes reportados por el cliente:

1. Listado de productos por defecto solo muestra ACTIVOS (los inactivos
   quedaban "fantasmas" en la lista — caso "-750").
2. Eliminación DEFINITIVA (hard-delete) disponible para Admin sobre
   productos ya desactivados. Si hay historial (POSTransactionItem,
   PurchaseItem) la operación se rechaza con mensaje claro.
3. Backfill de barcodes ausentes en packagings activos (migración 0021),
   cubre los bultos viejos que el POS no encontraba.
"""
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from stocks.models import (
    Product, ProductCategory, UnitOfMeasure, ProductPackaging,
)

User = get_user_model()


def _load_backfill_fn():
    """Carga `backfill_packaging_barcodes` por importlib porque el nombre
    del módulo empieza con dígito (`0021_...`) y `import` lo rechaza."""
    import importlib
    mod = importlib.import_module(
        'stocks.migrations.0021_backfill_active_packaging_barcodes'
    )
    return mod.backfill_packaging_barcodes


class _BaseTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.admin = User.objects.create_user(
            username='hd_admin', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.admin.groups.add(cls.admin_group)
        cls.category = ProductCategory.objects.create(name='HD Cat')
        cls.uom = UnitOfMeasure.objects.create(name='Unidad', abbreviation='un')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)


class ProductListDefaultActiveTests(_BaseTest):
    """Por defecto el listado debe filtrar `is_active=True`. El cliente se
    quejó de que productos viejos desactivados seguían apareciendo."""

    def setUp(self):
        super().setUp()
        self.activo = Product.objects.create(
            name='Activo', sku='ACT-1', barcode='7790000001001',
            category=self.category, unit_of_measure=self.uom,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'),
        )
        self.inactivo = Product.objects.create(
            name='Inactivo Viejo', sku='INA-1', barcode='7790000001002',
            category=self.category, unit_of_measure=self.uom,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'),
            is_active=False,
        )

    def test_default_solo_muestra_activos(self):
        resp = self.client.get(reverse('stocks:product_list'))
        prods = list(resp.context['products'])
        nombres = [p.name for p in prods]
        self.assertIn('Activo', nombres)
        self.assertNotIn('Inactivo Viejo', nombres)

    def test_status_inactive_solo_muestra_inactivos(self):
        resp = self.client.get(
            reverse('stocks:product_list'), {'status': 'inactive'}
        )
        prods = list(resp.context['products'])
        nombres = [p.name for p in prods]
        self.assertNotIn('Activo', nombres)
        self.assertIn('Inactivo Viejo', nombres)

    def test_status_all_muestra_ambos(self):
        resp = self.client.get(
            reverse('stocks:product_list'), {'status': 'all'}
        )
        prods = list(resp.context['products'])
        nombres = [p.name for p in prods]
        self.assertIn('Activo', nombres)
        self.assertIn('Inactivo Viejo', nombres)


class ProductHardDeleteTests(_BaseTest):
    """Hard-delete: solo Admin, solo sobre inactivos, respeta FKs PROTECT."""

    def setUp(self):
        super().setUp()
        self.producto_inactivo = Product.objects.create(
            name='Por borrar', sku='HDL-1', barcode='7790000002001',
            category=self.category, unit_of_measure=self.uom,
            sale_price=Decimal('1'), purchase_price=Decimal('1'),
            cost_price=Decimal('1'),
            is_active=False,
        )
        self.producto_activo = Product.objects.create(
            name='No borrar', sku='HDL-2', barcode='7790000002002',
            category=self.category, unit_of_measure=self.uom,
            sale_price=Decimal('1'), purchase_price=Decimal('1'),
            cost_price=Decimal('1'),
        )

    def test_hard_delete_de_inactivo_borra_completamente(self):
        pk = self.producto_inactivo.pk
        resp = self.client.post(
            reverse('stocks:product_hard_delete', args=[pk]), follow=True
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Product.objects.filter(pk=pk).exists())

    def test_hard_delete_de_activo_se_rechaza(self):
        pk = self.producto_activo.pk
        resp = self.client.post(
            reverse('stocks:product_hard_delete', args=[pk]), follow=True
        )
        self.assertTrue(Product.objects.filter(pk=pk).exists())
        # Mensaje de error claro
        msgs = [m.message for m in resp.context['messages']]
        self.assertTrue(
            any('activo' in m.lower() for m in msgs),
            msg=f'Mensaje esperado sobre estado activo, got: {msgs}'
        )

    def test_get_muestra_pagina_de_confirmacion(self):
        resp = self.client.get(
            reverse('stocks:product_hard_delete', args=[self.producto_inactivo.pk])
        )
        self.assertEqual(resp.status_code, 200)
        # El template muestra el nombre del producto
        self.assertContains(resp, 'Por borrar')


class PackagingBarcodeBackfillTests(_BaseTest):
    """La migración 0021 backfillea packagings activos sin barcode. Acá
    validamos el COMPORTAMIENTO equivalente reproduciendo la lógica del
    runpython sobre datos sintéticos."""

    def test_backfill_genera_codigo_int_para_bulk_sin_barcode(self):
        backfill_packaging_barcodes = _load_backfill_fn()
        from django.apps import apps

        prod = Product.objects.create(
            name='Bulto Huerfano', sku='BHF-1', barcode='7790000003001',
            category=self.category, unit_of_measure=self.uom,
            sale_price=Decimal('500'), purchase_price=Decimal('200'),
            cost_price=Decimal('200'),
        )
        bulk = ProductPackaging.objects.create(
            product=prod, packaging_type='bulk',
            name='Bulto x 12', barcode=None,
            units_per_display=12, displays_per_bulk=1,
            purchase_price=Decimal('200'), sale_price=Decimal('500'),
        )

        backfill_packaging_barcodes(apps, None)
        bulk.refresh_from_db()
        self.assertEqual(bulk.barcode, 'INT-BHF-1-BULK')

    def test_backfill_no_pisa_barcodes_existentes(self):
        backfill_packaging_barcodes = _load_backfill_fn()
        from django.apps import apps

        prod = Product.objects.create(
            name='Con Codigo', sku='CCD-1', barcode='7790000004001',
            category=self.category, unit_of_measure=self.uom,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'),
        )
        bulk = ProductPackaging.objects.create(
            product=prod, packaging_type='bulk',
            name='Bulto', barcode='7790000004999',  # Tiene barcode
            units_per_display=10, displays_per_bulk=1,
            purchase_price=Decimal('400'), sale_price=Decimal('1000'),
        )

        backfill_packaging_barcodes(apps, None)
        bulk.refresh_from_db()
        # NO se modifica
        self.assertEqual(bulk.barcode, '7790000004999')

    def test_backfill_solo_toca_activos(self):
        backfill_packaging_barcodes = _load_backfill_fn()
        from django.apps import apps

        prod = Product.objects.create(
            name='Bulto Inactivo', sku='BIN-1', barcode='7790000005001',
            category=self.category, unit_of_measure=self.uom,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'),
        )
        bulk = ProductPackaging.objects.create(
            product=prod, packaging_type='bulk',
            name='Bulto inactivo', barcode=None,
            units_per_display=10, displays_per_bulk=1,
            purchase_price=Decimal('400'), sale_price=Decimal('1000'),
            is_active=False,  # Inactivo
        )

        backfill_packaging_barcodes(apps, None)
        bulk.refresh_from_db()
        # NO se le asigna barcode (queda como estaba)
        self.assertIsNone(bulk.barcode)


class POSEncuentraBultoTrasBackfillTests(_BaseTest):
    """End-to-end del caso del cliente: un bulto sin barcode no se encuentra
    en el POS. Tras backfill (o tras escribir un código), sí se encuentra."""

    def setUp(self):
        super().setUp()
        self.prod = Product.objects.create(
            name='Galletitas Surtidas', sku='GST-1', barcode='7790000006001',
            category=self.category, unit_of_measure=self.uom,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'), current_stock=Decimal('120'),
        )

    def test_bulto_con_barcode_int_se_encuentra_en_pos(self):
        ProductPackaging.objects.create(
            product=self.prod, packaging_type='bulk',
            name='Bulto x 12', barcode='INT-GST-1-BULK',
            units_per_display=12, displays_per_bulk=1,
            purchase_price=Decimal('400'), sale_price=Decimal('1000'),
        )
        import json
        resp = self.client.get(reverse('pos:api_search'), {'q': 'INT-GST-1-BULK'})
        data = json.loads(resp.content)
        self.assertEqual(len(data['products']), 1)
        self.assertEqual(data['products'][0]['packaging_type'], 'bulk')

    def test_bulto_con_ean_real_se_encuentra_en_pos(self):
        ProductPackaging.objects.create(
            product=self.prod, packaging_type='bulk',
            name='Bulto x 12', barcode='7790000006999',
            units_per_display=12, displays_per_bulk=1,
            purchase_price=Decimal('400'), sale_price=Decimal('1000'),
        )
        import json
        resp = self.client.get(reverse('pos:api_search'), {'q': '7790000006999'})
        data = json.loads(resp.content)
        self.assertEqual(len(data['products']), 1)
        self.assertEqual(data['products'][0]['packaging_type'], 'bulk')
