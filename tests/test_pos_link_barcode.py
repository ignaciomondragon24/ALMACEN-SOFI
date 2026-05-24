"""Tests del flujo "vincular código escaneado a producto existente" en el POS.

Caso real reportado por el cliente:
- Cargó un bulto en el sistema; la migración 0021 le asignó `INT-{SKU}-BULK`
  porque el barcode quedó vacío al crear.
- Al escanear el EAN-13 físico impreso en la caja, `api_search` no lo encuentra
  porque el barcode en DB es `INT-...`, no el EAN.
- Sin este fix la única salida era ir al Gestor de Empaques y editar el bulto
  manualmente; lento y poco descubrible desde el POS.

Con el nuevo endpoint el cajero, desde el mismo modal "código no encontrado",
busca el producto, elige el nivel (unidad/display/bulto) y vincula el código en
un solo paso, agregándolo al carrito acto seguido.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from stocks.models import Product, ProductCategory, ProductPackaging

User = get_user_model()


class _BaseLinkBarcodeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cashier_group, _ = Group.objects.get_or_create(name='Cashier')
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user(
            username='link_cashier', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.user.groups.add(cls.admin_group)
        cls.category = ProductCategory.objects.create(name='Cat Link')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        # Producto bulto-only con código interno tipo migración 0021
        self.product = Product.objects.create(
            name='pic nic nevares x40', sku='PICNIC40',
            category=self.category,
            sale_price=Decimal('417.50'), purchase_price=Decimal('278.63'),
            cost_price=Decimal('278.63'), current_stock=Decimal('0'),
        )
        self.bulk = ProductPackaging.objects.create(
            product=self.product, packaging_type='bulk',
            name='pic nic x 40', barcode='INT-PICNIC40-BULK',
            units_per_display=1, displays_per_bulk=40,
            purchase_price=Decimal('11145'), sale_price=Decimal('16700'),
            is_active=True,
        )

    def _link(self, **kwargs):
        return self.client.post(
            reverse('pos:api_link_barcode'),
            data=json.dumps(kwargs),
            content_type='application/json',
        )


class LinkBarcodeEndpointTests(_BaseLinkBarcodeTest):

    def test_vincula_ean_real_a_bulto_con_codigo_interno(self):
        """Caso bandera: EAN físico se asigna al bulto que tenía INT-{SKU}-BULK."""
        resp = self._link(
            barcode='7799999000077',
            target_type='packaging',
            target_id=self.bulk.pk,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertTrue(data['success'])

        self.bulk.refresh_from_db()
        self.assertEqual(self.bulk.barcode, '7799999000077')

        # El response trae el shape esperado por el frontend (similar a api_search).
        prod = data['product']
        self.assertEqual(prod['id'], self.product.pk)
        self.assertEqual(prod['packaging_id'], self.bulk.pk)
        self.assertEqual(prod['packaging_type'], 'bulk')
        self.assertEqual(prod['unit_price'], 16700.0)
        self.assertEqual(prod['packaging_units'], 40)

    def test_despues_de_vincular_api_search_lo_encuentra_por_ean(self):
        """Garantía: el cambio se ve reflejado en `api_search` (sin caches stale)."""
        self._link(
            barcode='7799999000077', target_type='packaging', target_id=self.bulk.pk,
        )
        resp = self.client.get('/pos/api/search/?q=7799999000077')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['products']), 1)
        self.assertEqual(data['products'][0]['packaging_id'], self.bulk.pk)

    def test_no_permite_vincular_codigo_ya_tomado_por_otro_packaging(self):
        """Choque de barcode con otro packaging activo → 409, sin pisar."""
        otro_prod = Product.objects.create(
            name='Otro', sku='OTRO-1', sale_price=Decimal('100'),
            purchase_price=Decimal('50'), cost_price=Decimal('50'),
        )
        ProductPackaging.objects.create(
            product=otro_prod, packaging_type='unit', name='u',
            barcode='7799999000077', is_active=True,
        )
        resp = self._link(
            barcode='7799999000077', target_type='packaging', target_id=self.bulk.pk,
        )
        self.assertEqual(resp.status_code, 409)
        self.bulk.refresh_from_db()
        self.assertEqual(self.bulk.barcode, 'INT-PICNIC40-BULK')  # sin cambiar

    def test_no_permite_vincular_codigo_ya_tomado_por_un_product(self):
        """Choque con un Product activo → 409. Evita sobrescribir un EAN ajeno."""
        Product.objects.create(
            name='Conflict', sku='CONFLICT-1', barcode='7799999000077',
            sale_price=Decimal('1'), purchase_price=Decimal('1'),
            cost_price=Decimal('1'),
        )
        resp = self._link(
            barcode='7799999000077', target_type='packaging', target_id=self.bulk.pk,
        )
        self.assertEqual(resp.status_code, 409)

    def test_vincula_a_product_cuando_no_hay_packagings(self):
        """Productos sin empaques: el código va directo a Product.barcode."""
        prod = Product.objects.create(
            name='Galleta Suelta', sku='GAL-1',
            sale_price=Decimal('500'), purchase_price=Decimal('200'),
            cost_price=Decimal('200'),
        )
        resp = self._link(
            barcode='7790000001234', target_type='product', target_id=prod.pk,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        prod.refresh_from_db()
        self.assertEqual(prod.barcode, '7790000001234')
        # Y el POS lo encuentra por EAN
        resp2 = self.client.get('/pos/api/search/?q=7790000001234')
        self.assertEqual(resp2.json()['products'][0]['id'], prod.pk)

    def test_barcode_vacio_rechaza(self):
        resp = self._link(barcode='', target_type='packaging', target_id=self.bulk.pk)
        self.assertEqual(resp.status_code, 400)

    def test_target_type_invalido_rechaza(self):
        resp = self._link(
            barcode='7799999000077', target_type='garbage', target_id=self.bulk.pk,
        )
        self.assertEqual(resp.status_code, 400)

    def test_target_id_inexistente_rechaza(self):
        resp = self._link(
            barcode='7799999000077', target_type='packaging', target_id=999999,
        )
        self.assertEqual(resp.status_code, 404)

    def test_no_autenticado_rechaza(self):
        self.client.logout()
        resp = self._link(
            barcode='7799999000077', target_type='packaging', target_id=self.bulk.pk,
        )
        self.assertIn(resp.status_code, (302, 401, 403))  # redirect login, ajax 401, o 403

    def test_reemplazar_el_mismo_barcode_es_idempotente(self):
        """Vincular el mismo código que ya estaba: no rompe, devuelve OK."""
        self.bulk.barcode = '7790000000001'
        self.bulk.save(update_fields=['barcode'])
        resp = self._link(
            barcode='7790000000001', target_type='packaging', target_id=self.bulk.pk,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.bulk.refresh_from_db()
        self.assertEqual(self.bulk.barcode, '7790000000001')


class SearchForLinkEndpointTests(_BaseLinkBarcodeTest):

    def test_busca_por_nombre_y_devuelve_niveles(self):
        resp = self.client.get('/pos/api/search-for-link/?q=pic')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['results']), 1)
        r = data['results'][0]
        self.assertEqual(r['product_id'], self.product.pk)
        self.assertEqual(len(r['levels']), 1)
        lvl = r['levels'][0]
        self.assertEqual(lvl['target_type'], 'packaging')
        self.assertEqual(lvl['target_id'], self.bulk.pk)
        self.assertEqual(lvl['packaging_type'], 'bulk')
        self.assertEqual(lvl['barcode'], 'INT-PICNIC40-BULK')
        self.assertEqual(lvl['sale_price'], 16700.0)

    def test_busca_por_sku(self):
        resp = self.client.get('/pos/api/search-for-link/?q=PICNIC40')
        data = resp.json()
        self.assertEqual(len(data['results']), 1)

    def test_query_corto_devuelve_vacio(self):
        """Evita resultados ruidosos al primer caracter (UX)."""
        resp = self.client.get('/pos/api/search-for-link/?q=p')
        self.assertEqual(resp.json()['results'], [])

    def test_producto_sin_packagings_se_lista_como_unit_product(self):
        """Si un Product no tiene empaques, se ofrece vincular a Product directo."""
        Product.objects.create(
            name='Cosa suelta xyz', sku='SUELT-1',
            sale_price=Decimal('100'), purchase_price=Decimal('50'),
            cost_price=Decimal('50'),
        )
        resp = self.client.get('/pos/api/search-for-link/?q=suelta')
        data = resp.json()
        self.assertEqual(len(data['results']), 1)
        lvl = data['results'][0]['levels'][0]
        self.assertEqual(lvl['target_type'], 'product')
        self.assertEqual(lvl['packaging_type'], 'unit')

    def test_no_lista_productos_inactivos(self):
        """Productos desactivados no aparecen en el buscador."""
        Product.objects.create(
            name='picnic viejo', sku='VIEJO-1', is_active=False,
            sale_price=Decimal('1'), purchase_price=Decimal('1'),
            cost_price=Decimal('1'),
        )
        resp = self.client.get('/pos/api/search-for-link/?q=picnic viejo')
        # Solo aparece el actual ('pic nic nevares x40'), no el inactivo.
        for r in resp.json()['results']:
            self.assertNotEqual(r['sku'], 'VIEJO-1')


class APISearchAcepta14DigitosTests(TestCase):
    """Regresión: el POS debe encontrar bultos con barcode de 14 dígitos.

    Caso reportado por el cliente (alfajor Genio Triple Chocolate):
    el bulto trae impreso un ITF-14 / GS1-14 (EAN-13 con un dígito de embalaje
    delante, ej. 17798094220953). El api_search debe matchear tanto:
    - via packaging_match (cuando el bulto está cargado como ProductPackaging),
    - como via Product.barcode (fallback para productos sin empaques).

    El bug original en el frontend era el regex `/^\\d{8,13}$/` en
    handleSearchKeydown — no aceptaba 14 dígitos y el scan caía en una rama
    inútil. El test de frontend no lo cubre acá; este test cierra el lado del
    backend para que cualquier cliente del API pueda buscar por 14 dígitos.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user(
            username='itf14_admin', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.user.groups.add(cls.admin_group)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def test_api_search_encuentra_packaging_por_barcode_de_14_digitos(self):
        product = Product.objects.create(
            name='Genio Triple Chocolate', sku='GENIO-TCH',
            barcode='7798094220956',  # EAN-13 unidad
            sale_price=Decimal('600'), purchase_price=Decimal('300'),
            cost_price=Decimal('300'),
        )
        bulk = ProductPackaging.objects.create(
            product=product, packaging_type='bulk',
            name='Bulto x 24', barcode='17798094220953',  # ITF-14 bulto
            units_per_display=1, displays_per_bulk=24,
            purchase_price=Decimal('7200'), sale_price=Decimal('14400'),
            is_active=True,
        )

        resp = self.client.get('/pos/api/search/?q=17798094220953')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['products']), 1, msg=data)
        prod = data['products'][0]
        self.assertEqual(prod['id'], product.pk)
        self.assertEqual(prod['packaging_id'], bulk.pk)
        self.assertEqual(prod['packaging_type'], 'bulk')
        self.assertEqual(prod['packaging_units'], 24)
        self.assertEqual(prod['unit_price'], 14400.0)

    def test_api_search_encuentra_product_por_barcode_de_14_digitos(self):
        """Fallback: Product.barcode de 14 dígitos también matchea."""
        product = Product.objects.create(
            name='Bulto suelto', sku='BS-1',
            barcode='12345678901234',  # 14 dígitos
            sale_price=Decimal('1000'), purchase_price=Decimal('500'),
            cost_price=Decimal('500'),
        )
        resp = self.client.get('/pos/api/search/?q=12345678901234')
        data = resp.json()
        self.assertEqual(len(data['products']), 1)
        self.assertEqual(data['products'][0]['id'], product.pk)

    def test_api_search_packaging_gana_sobre_product_legacy_con_14d(self):
        """Defensa: si un Product legacy comparte ITF-14 con un Packaging
        activo, el Packaging tiene prioridad (devuelve precio del bulto)."""
        product_a = Product.objects.create(
            name='Producto A', sku='A-1',
            sale_price=Decimal('100'), purchase_price=Decimal('50'),
            cost_price=Decimal('50'),
        )
        bulk = ProductPackaging.objects.create(
            product=product_a, packaging_type='bulk',
            name='Bulto x 24', barcode='17798094220953',
            units_per_display=1, displays_per_bulk=24,
            purchase_price=Decimal('1000'), sale_price=Decimal('9999'),
            is_active=True,
        )
        # El Product legacy queda sin barcode (la unicidad lo impediría).
        resp = self.client.get('/pos/api/search/?q=17798094220953')
        data = resp.json()
        self.assertEqual(data['products'][0]['unit_price'], 9999.0)
        self.assertEqual(data['products'][0]['packaging_id'], bulk.pk)
