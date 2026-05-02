"""Tests de auto-generación de código interno para empaques sin barcode.

Caso de uso real (alfajores Juanino): el display físico no trae código de
barra impreso, pero el dueño quiere asignarle un código para imprimir como
etiqueta y poder buscarlo desde el sistema.

Comportamiento esperado:
- Si el form se guarda con barcode vacío, se autogenera INT-{SKU}-{TIPO}.
- Si el form se guarda con barcode escaneado, se respeta tal cual.
- Re-guardar con barcode vacío sobre un packaging que ya tiene barcode
  (escaneado o INT-) NO lo sobrescribe — preserva el valor existente.
- El POS puede buscar el packaging por su código interno.
- Recepción de OC y cascada de stock siguen funcionando normalmente.
"""
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from stocks.models import (
    Product, ProductCategory, ProductPackaging, StockMovement,
)
from stocks.services import StockManagementService

User = get_user_model()


class _BasePackagingTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.admin = User.objects.create_user(
            username='int_pkg_admin', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.admin.groups.add(cls.admin_group)
        cls.category = ProductCategory.objects.create(name='Cat Int')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)
        self.product = Product.objects.create(
            name='Alfajor Juanino', sku='JUAN-001', barcode='7790000000001',
            category=self.category,
            sale_price=Decimal('500'), purchase_price=Decimal('200'),
            cost_price=Decimal('200'), current_stock=Decimal('48'),
        )

    def _post_save_pkg(self, **extra):
        data = {
            'action': 'save_pkg',
            'pkg_units_per_display': '12',
            'pkg_displays_per_bulk': '6',
            'has_unit': '1',
            'unit_barcode': self.product.barcode,
            'unit_name': 'Unidad',
            'unit_purchase_price': '200',
            'unit_sale_price': '500',
        }
        data.update(extra)
        return self.client.post(
            reverse('stocks:product_packaging', args=[self.product.pk]),
            data, follow=True,
        )


class GeneracionCodigoInternoTests(_BasePackagingTest):

    def test_display_sin_barcode_genera_codigo_interno(self):
        """Display sin código escaneado → INT-{SKU}-DISP."""
        resp = self._post_save_pkg(
            has_display='1',
            display_barcode='',
            display_name='Display x 12',
            display_purchase_price='2400',
            display_sale_price='6000',
        )
        self.assertEqual(resp.status_code, 200)

        display = ProductPackaging.objects.get(
            product=self.product, packaging_type='display'
        )
        self.assertEqual(display.barcode, 'INT-JUAN-001-DISP')
        # Stock cascade: 48 unidades / 12 por display = 4 displays
        self.assertEqual(display.current_stock, Decimal('4.000'))

    def test_bulto_sin_barcode_genera_codigo_interno(self):
        """Bulto sin código escaneado → INT-{SKU}-BULK."""
        self._post_save_pkg(
            has_bulk='1',
            bulk_barcode='',
            bulk_name='Bulto x 72',
            bulk_purchase_price='14400',
            bulk_sale_price='36000',
        )
        bulk = ProductPackaging.objects.get(
            product=self.product, packaging_type='bulk'
        )
        self.assertEqual(bulk.barcode, 'INT-JUAN-001-BULK')

    def test_display_con_barcode_escaneado_no_genera_int(self):
        """Si el usuario escanea EAN-13, se respeta y NO se genera INT-."""
        self._post_save_pkg(
            has_display='1',
            display_barcode='7790000000099',
            display_name='Display x 12',
            display_purchase_price='2400',
            display_sale_price='6000',
        )
        display = ProductPackaging.objects.get(
            product=self.product, packaging_type='display'
        )
        self.assertEqual(display.barcode, '7790000000099')
        # Confirmar que NO arrancó con INT-
        self.assertFalse(display.barcode.startswith('INT-'))

    def test_reguardar_con_vacio_no_borra_barcode_existente(self):
        """Editar packaging dejando vacío el campo barcode NO borra el valor previo.

        Defensa contra el caso: el cliente abre el form, edita el precio, y
        deja el campo barcode vacío sin querer → no debemos perder el EAN
        escaneado original.
        """
        # 1. Crear con EAN escaneado
        self._post_save_pkg(
            has_display='1',
            display_barcode='7790000000099',
            display_name='Display x 12',
            display_purchase_price='2400',
            display_sale_price='6000',
        )
        # 2. Re-guardar con barcode vacío
        self._post_save_pkg(
            has_display='1',
            display_barcode='',  # vacío
            display_name='Display x 12',
            display_purchase_price='2500',
            display_sale_price='6500',
        )
        display = ProductPackaging.objects.get(
            product=self.product, packaging_type='display'
        )
        # El barcode original se conserva
        self.assertEqual(display.barcode, '7790000000099')
        # El precio sí se actualiza
        self.assertEqual(display.purchase_price, Decimal('2500'))

    def test_reemplazar_int_por_ean_real(self):
        """Si tenía INT- y el cliente escanea un EAN real, se reemplaza."""
        # 1. Crear sin barcode → tiene INT-
        self._post_save_pkg(
            has_display='1',
            display_barcode='',
            display_name='Display x 12',
            display_purchase_price='2400',
            display_sale_price='6000',
        )
        # 2. Re-guardar con EAN real
        self._post_save_pkg(
            has_display='1',
            display_barcode='7790000000099',
            display_name='Display x 12',
            display_purchase_price='2400',
            display_sale_price='6000',
        )
        display = ProductPackaging.objects.get(
            product=self.product, packaging_type='display'
        )
        self.assertEqual(display.barcode, '7790000000099')

    def test_dos_productos_distintos_generan_codigos_unicos(self):
        """Dos productos sin barcode generan INT- distintos por su SKU único."""
        otro = Product.objects.create(
            name='Otra galleta', sku='OTRA-001', barcode='7790000000002',
            category=self.category,
            sale_price=Decimal('300'), purchase_price=Decimal('100'),
            cost_price=Decimal('100'), current_stock=Decimal('24'),
        )

        self._post_save_pkg(
            has_display='1', display_barcode='',
            display_name='Display x 12',
            display_purchase_price='2400', display_sale_price='6000',
        )
        self.client.post(
            reverse('stocks:product_packaging', args=[otro.pk]),
            {
                'action': 'save_pkg',
                'pkg_units_per_display': '12',
                'pkg_displays_per_bulk': '1',
                'has_unit': '1',
                'unit_barcode': otro.barcode,
                'unit_name': 'Unidad',
                'unit_purchase_price': '100', 'unit_sale_price': '300',
                'has_display': '1', 'display_barcode': '',
                'display_name': 'Display x 12',
                'display_purchase_price': '1200', 'display_sale_price': '3000',
            }, follow=True,
        )

        d1 = ProductPackaging.objects.get(
            product=self.product, packaging_type='display'
        )
        d2 = ProductPackaging.objects.get(
            product=otro, packaging_type='display'
        )
        self.assertEqual(d1.barcode, 'INT-JUAN-001-DISP')
        self.assertEqual(d2.barcode, 'INT-OTRA-001-DISP')
        self.assertNotEqual(d1.barcode, d2.barcode)


class POSEncuentraPackagingPorCodigoInternoTests(_BasePackagingTest):
    """El POS debe encontrar el packaging cuando el cajero tipea su código interno."""

    def test_api_search_encuentra_display_por_int_code(self):
        # Crear shift abierto y session POS para que el cajero tenga acceso
        self._post_save_pkg(
            has_display='1', display_barcode='',
            display_name='Display x 12',
            display_purchase_price='2400', display_sale_price='6000',
        )
        display = ProductPackaging.objects.get(
            product=self.product, packaging_type='display'
        )
        self.assertEqual(display.barcode, 'INT-JUAN-001-DISP')

        # Login como admin (que es group Admin = puede usar POS)
        resp = self.client.get('/pos/api/search/?q=INT-JUAN-001-DISP')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['products']), 1, msg=data)
        product_data = data['products'][0]
        self.assertEqual(product_data['id'], self.product.pk)
        # El POS debe devolver info del packaging matcheado
        self.assertEqual(product_data['packaging_id'], display.pk)
        self.assertEqual(product_data['packaging_type'], 'display')
        self.assertEqual(product_data['unit_price'], 6000.0)

    def test_api_search_ean_real_sigue_funcionando(self):
        """Garantía: el cambio en api_search no rompe búsquedas por EAN-13."""
        self._post_save_pkg(
            has_display='1',
            display_barcode='7790000000099',
            display_name='Display x 12',
            display_purchase_price='2400', display_sale_price='6000',
        )
        resp = self.client.get('/pos/api/search/?q=7790000000099')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['products']), 1, msg=data)
        self.assertEqual(data['products'][0]['unit_price'], 6000.0)

    def test_api_search_busqueda_por_nombre_no_se_rompe(self):
        """Buscar 'Juanino' por nombre sigue devolviendo el producto."""
        resp = self.client.get('/pos/api/search/?q=Juanino')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        ids = [p['id'] for p in data['products']]
        self.assertIn(self.product.pk, ids)


class CascadaStockNoSeRompeTests(_BasePackagingTest):
    """La recepción y cascada de stock siguen funcionando con código interno."""

    def test_recibir_display_con_int_suma_stock_por_unidades(self):
        """Recibir 5 displays de 12u suma 60 unidades base al producto."""
        self._post_save_pkg(
            has_display='1', display_barcode='',
            display_name='Display x 12',
            display_purchase_price='2400', display_sale_price='6000',
        )
        display = ProductPackaging.objects.get(
            product=self.product, packaging_type='display'
        )
        self.assertEqual(display.barcode, 'INT-JUAN-001-DISP')

        stock_inicial = self.product.current_stock  # 48
        StockManagementService.receive_packaging(
            display, Decimal('5'), cost=Decimal('2400'), user=self.admin,
        )
        self.product.refresh_from_db()
        # 48 + 5*12 = 108
        self.assertEqual(self.product.current_stock, stock_inicial + Decimal('60'))

        display.refresh_from_db()
        # Empezó con 48/12=4, ahora 4+5=9
        self.assertEqual(display.current_stock, Decimal('9.000'))

    def test_recibir_bulto_con_int_cascadea_a_displays_y_unidades(self):
        """Recibir 1 bulto x 72 suma 72 unidades base, 6 displays, 1 bulto."""
        self._post_save_pkg(
            has_bulk='1', bulk_barcode='',
            bulk_name='Bulto x 72',
            bulk_purchase_price='14400', bulk_sale_price='36000',
            has_display='1', display_barcode='',
            display_name='Display x 12',
            display_purchase_price='2400', display_sale_price='6000',
        )
        bulk = ProductPackaging.objects.get(
            product=self.product, packaging_type='bulk'
        )
        self.assertEqual(bulk.barcode, 'INT-JUAN-001-BULK')

        StockManagementService.receive_packaging(
            bulk, Decimal('1'), cost=Decimal('14400'), user=self.admin,
        )
        self.product.refresh_from_db()
        # 48 + 72 = 120 unidades
        self.assertEqual(self.product.current_stock, Decimal('120'))

        # Display arranca con 48/12=4, suma 72/12=6 → 10
        display = ProductPackaging.objects.get(
            product=self.product, packaging_type='display'
        )
        self.assertEqual(display.current_stock, Decimal('10.000'))
