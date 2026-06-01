"""Tests del refactor barcode/sku con soft-delete liberador.

Cubre los tres problemas reportados por el usuario:

1. Flexibilidad de identificadores: barcode siempre opcional siempre que
   exista un sku manual o autogenerado.
2. Conflicto de unicidad en borrado lógico: al hacer soft-delete el
   barcode original queda libre vía sufijo `_deleted_{pk}`.
3. Cambio de tipo de empaque (Bulto → Display) sin perder integridad: el
   usuario puede destildar el bulto mal cargado y volver a tildar como
   display con el mismo código sin chocar con el unique=True.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from stocks.forms import ProductForm, ProductPackagingForm
from stocks.models import (
    Product, ProductCategory, ProductPackaging,
    DELETED_BARCODE_MARKER, _release_barcode,
)

User = get_user_model()


class _BaseStocksTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.admin = User.objects.create_user(
            username='softdel_admin', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.admin.groups.add(cls.admin_group)
        cls.category = ProductCategory.objects.create(name='SD Cat')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)


class ProductSoftDeleteTests(_BaseStocksTest):
    """Producto: soft-delete libera el barcode."""

    def test_delete_marca_inactivo_y_libera_barcode(self):
        prod = Product.objects.create(
            name='Caramelo X', sku='CRX-001', barcode='7791111000001',
            category=self.category,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'), current_stock=Decimal('10'),
        )
        original_barcode = prod.barcode
        prod_pk = prod.pk

        prod.delete()

        prod.refresh_from_db()
        self.assertFalse(prod.is_active)
        self.assertEqual(
            prod.barcode,
            f'{original_barcode}{DELETED_BARCODE_MARKER}{prod_pk}',
        )

    def test_recrear_con_mismo_barcode_funciona_post_delete(self):
        """El caso del bug reportado: borrar y volver a cargar con el mismo EAN."""
        original = Product.objects.create(
            name='Galletita Mal Cargada', sku='GAL-001',
            barcode='7792222000001', category=self.category,
            sale_price=Decimal('200'), purchase_price=Decimal('80'),
            cost_price=Decimal('80'), current_stock=Decimal('0'),
        )
        original.delete()

        # Re-crear con el mismo barcode no debe explotar.
        nuevo = Product.objects.create(
            name='Galletita Bien Cargada', sku='GAL-002',
            barcode='7792222000001', category=self.category,
            sale_price=Decimal('250'), purchase_price=Decimal('90'),
            cost_price=Decimal('90'), current_stock=Decimal('5'),
        )
        self.assertEqual(nuevo.barcode, '7792222000001')
        self.assertTrue(nuevo.is_active)

        # El viejo conserva el sufijo
        original.refresh_from_db()
        self.assertIn(DELETED_BARCODE_MARKER, original.barcode)

    def test_delete_sin_barcode_solo_marca_inactivo(self):
        prod = Product.objects.create(
            name='Sin Codigo', sku='SC-001', barcode=None,
            category=self.category,
            sale_price=Decimal('50'), purchase_price=Decimal('20'),
            cost_price=Decimal('20'), current_stock=Decimal('0'),
        )
        prod.delete()
        prod.refresh_from_db()
        self.assertFalse(prod.is_active)
        self.assertIsNone(prod.barcode)

    def test_delete_idempotente_no_duplica_sufijo(self):
        prod = Product.objects.create(
            name='Doble Delete', sku='DD-001', barcode='7793333000001',
            category=self.category,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'),
        )
        prod.delete()
        first_barcode = Product.objects.get(pk=prod.pk).barcode
        # Llamar delete() de nuevo no debe duplicar el sufijo
        prod.delete()
        self.assertEqual(Product.objects.get(pk=prod.pk).barcode, first_barcode)

    def test_hard_delete_cascadea(self):
        prod = Product.objects.create(
            name='Hard Delete', sku='HD-001', barcode='7794444000001',
            category=self.category,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'),
        )
        pk = prod.pk
        prod.delete(hard=True)
        self.assertFalse(Product.objects.filter(pk=pk).exists())


class PackagingSoftDeleteTests(_BaseStocksTest):
    """ProductPackaging: soft-delete libera el barcode."""

    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(
            name='Producto Test', sku='PT-001', barcode='7795555000001',
            category=self.category,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'), current_stock=Decimal('48'),
        )

    def test_packaging_delete_libera_barcode(self):
        pkg = ProductPackaging.objects.create(
            product=self.product, packaging_type='bulk',
            name='Bulto x 144', barcode='7795555000099',
            units_per_display=12, displays_per_bulk=12,
            purchase_price=Decimal('500'), sale_price=Decimal('1500'),
        )
        original = pkg.barcode
        pkg_pk = pkg.pk
        pkg.delete()
        pkg.refresh_from_db()
        self.assertFalse(pkg.is_active)
        self.assertEqual(
            pkg.barcode,
            f'{original}{DELETED_BARCODE_MARKER}{pkg_pk}',
        )

    def test_recrear_packaging_con_mismo_barcode_post_delete(self):
        pkg_a = ProductPackaging.objects.create(
            product=self.product, packaging_type='bulk',
            name='Bulto x 144', barcode='7795555000099',
            units_per_display=12, displays_per_bulk=12,
            purchase_price=Decimal('500'), sale_price=Decimal('1500'),
        )
        pkg_a.delete()

        # Misma EAN, pero ahora como display
        pkg_b = ProductPackaging.objects.create(
            product=self.product, packaging_type='display',
            name='Display x 12', barcode='7795555000099',
            units_per_display=12, displays_per_bulk=1,
            purchase_price=Decimal('400'), sale_price=Decimal('1200'),
        )
        self.assertEqual(pkg_b.barcode, '7795555000099')
        self.assertEqual(pkg_b.packaging_type, 'display')


class CambioDeTipoEnGestorEmpaquesTests(_BaseStocksTest):
    """Caso del usuario: cargó "Bulto" cuando era "Display"."""

    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(
            name='Alfajor Mal', sku='ALM-001', barcode='7796666000001',
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

    def test_destildar_bulto_y_crear_display_con_mismo_barcode(self):
        # 1. Usuario carga (incorrectamente) un bulto con código ABC
        self._post_save_pkg(
            has_bulk='1',
            bulk_barcode='7796666000077',
            bulk_name='Bulto x 72',
            bulk_purchase_price='14400',
            bulk_sale_price='36000',
        )
        bulk = ProductPackaging.objects.get(
            product=self.product, packaging_type='bulk', is_active=True,
        )
        self.assertEqual(bulk.barcode, '7796666000077')

        # 2. Usuario destilda bulto y tilda display con el MISMO código
        resp = self._post_save_pkg(
            has_display='1',
            display_barcode='7796666000077',
            display_name='Display x 12',
            display_purchase_price='2400',
            display_sale_price='6000',
        )
        self.assertEqual(resp.status_code, 200)

        # El bulto quedó soft-deleted con sufijo
        bulk.refresh_from_db()
        self.assertFalse(bulk.is_active)
        self.assertIn(DELETED_BARCODE_MARKER, bulk.barcode or '')

        # El display nuevo tomó el barcode original
        display = ProductPackaging.objects.get(
            product=self.product, packaging_type='display', is_active=True,
        )
        self.assertEqual(display.barcode, '7796666000077')


class ProductCleanValidationTests(_BaseStocksTest):
    """clean() del modelo y del form: barcode-o-sku obligatorio."""

    def test_model_clean_falla_si_no_hay_barcode_ni_sku(self):
        prod = Product(
            name='Sin nada', sku='', barcode=None,
            category=self.category,
            sale_price=Decimal('100'),
        )
        with self.assertRaises(ValidationError):
            prod.full_clean()

    def test_model_clean_pasa_con_solo_sku(self):
        prod = Product(
            name='Con sku', sku='MANUAL-1', barcode=None,
            category=self.category,
            sale_price=Decimal('100'),
        )
        # full_clean valida; queremos que NO levante la ValidationError de
        # barcode/sku — dejamos que valide otros campos normalmente.
        try:
            prod.full_clean(exclude=['unit_of_measure'])
        except ValidationError as exc:
            self.assertNotIn('barcode', exc.message_dict)
            self.assertNotIn('sku', exc.message_dict)

    def test_model_clean_pasa_con_solo_barcode(self):
        prod = Product(
            name='Con barcode', sku='', barcode='7797777000001',
            category=self.category,
            sale_price=Decimal('100'),
        )
        try:
            prod.full_clean(exclude=['unit_of_measure'])
        except ValidationError as exc:
            self.assertNotIn('barcode', exc.message_dict)
            self.assertNotIn('sku', exc.message_dict)

    def test_form_falla_sin_barcode_ni_sku(self):
        form = ProductForm(data={
            'name': 'Form sin id', 'barcode': '', 'sku': '',
            'category': self.category.pk, 'sale_price': '100',
            'cost_price': '50', 'purchase_price': '50',
            'current_stock': '0', 'min_stock': '0',
            'quick_access_color': '#3498db',
            'quick_access_icon': 'fa-box', 'quick_access_position': '0',
            'weight_per_unit_grams': '0',
        })
        self.assertFalse(form.is_valid())

    def test_form_pasa_con_solo_sku(self):
        form = ProductForm(data={
            'name': 'Solo SKU', 'barcode': '', 'sku': 'MAN-X',
            'category': self.category.pk, 'sale_price': '100',
            'cost_price': '50', 'purchase_price': '50',
            'current_stock': '0', 'min_stock': '0',
            'quick_access_color': '#3498db',
            'quick_access_icon': 'fa-box', 'quick_access_position': '0',
            'weight_per_unit_grams': '0',
        })
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_form_detecta_barcode_duplicado_activo(self):
        Product.objects.create(
            name='Existente', sku='EXI-1', barcode='7798888000001',
            category=self.category,
            sale_price=Decimal('100'), cost_price=Decimal('50'),
            purchase_price=Decimal('50'),
        )
        form = ProductForm(data={
            'name': 'Duplicado', 'barcode': '7798888000001', 'sku': 'NEW-1',
            'category': self.category.pk, 'sale_price': '100',
            'cost_price': '50', 'purchase_price': '50',
            'current_stock': '0', 'min_stock': '0',
            'quick_access_color': '#3498db',
            'quick_access_icon': 'fa-box', 'quick_access_position': '0',
            'weight_per_unit_grams': '0',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('barcode', form.errors)

    def test_form_acepta_barcode_de_producto_inactivo(self):
        """Un soft-deleted no bloquea el alta con el mismo barcode."""
        viejo = Product.objects.create(
            name='Viejo', sku='OLD-1', barcode='7799999000001',
            category=self.category,
            sale_price=Decimal('100'), cost_price=Decimal('50'),
            purchase_price=Decimal('50'),
        )
        viejo.delete()  # soft: libera barcode

        form = ProductForm(data={
            'name': 'Nuevo', 'barcode': '7799999000001', 'sku': 'NEW-2',
            'category': self.category.pk, 'sale_price': '100',
            'cost_price': '50', 'purchase_price': '50',
            'current_stock': '0', 'min_stock': '0',
            'quick_access_color': '#3498db',
            'quick_access_icon': 'fa-box', 'quick_access_position': '0',
            'weight_per_unit_grams': '0',
        })
        self.assertTrue(form.is_valid(), msg=form.errors)


class ProductToUnitPackagingSyncTests(_BaseStocksTest):
    """Editar Product propaga al unit packaging automáticamente.

    Resuelve la queja del cliente: editaba el Product, después tenía que
    ir al gestor de empaques y repetir la edición sobre la Unidad. Ahora
    al guardar el Product, el unit_pkg activo refleja los cambios.
    """

    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(
            name='Original', sku='SYNC-001', barcode='7791000000001',
            category=self.category,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'), current_stock=Decimal('10'),
        )
        self.unit_pkg = ProductPackaging.objects.create(
            product=self.product, packaging_type='unit',
            name='Original', barcode='7791000000001',
            units_per_display=1, displays_per_bulk=1,
            purchase_price=Decimal('40'), sale_price=Decimal('100'),
        )

    def test_editar_nombre_propaga_al_unit_pkg(self):
        self.product.name = 'Renombrado'
        self.product.save()
        self.unit_pkg.refresh_from_db()
        self.assertEqual(self.unit_pkg.name, 'Renombrado')

    def test_editar_sale_price_propaga_al_unit_pkg(self):
        self.product.sale_price = Decimal('150')
        self.product.save()
        self.unit_pkg.refresh_from_db()
        self.assertEqual(self.unit_pkg.sale_price, Decimal('150'))

    def test_editar_cost_price_propaga_a_purchase_price_del_unit_pkg(self):
        self.product.cost_price = Decimal('55')
        self.product.save()
        self.unit_pkg.refresh_from_db()
        self.assertEqual(self.unit_pkg.purchase_price, Decimal('55'))

    def test_update_solo_de_stock_no_dispara_sync(self):
        """Cascadas de stock NO deben tocar el unit_pkg vía sync.

        Caso real: receive_packaging hace product.save(update_fields=['current_stock']).
        Si esto disparara sync, sería un query extra inútil cada cascada.
        Verificamos cambiando el unit_pkg.name "a mano" y comprobando que
        un save de stock no lo revierte.
        """
        self.unit_pkg.name = 'Custom Manual'
        self.unit_pkg.save(update_fields=['name'])

        self.product.current_stock = Decimal('99')
        self.product.save(update_fields=['current_stock'])

        self.unit_pkg.refresh_from_db()
        # El unit_pkg conserva el nombre custom porque update_fields=current_stock
        # no entra en _UNIT_PKG_SYNC_FIELDS.
        self.assertEqual(self.unit_pkg.name, 'Custom Manual')

    def test_sync_no_pisa_barcode_propio_del_unit_pkg(self):
        """El unit_pkg puede tener un EAN distinto (display vendido como
        unidad por separado, etc.). El sync sólo rellena si está vacío."""
        # unit_pkg ya tiene su barcode '7791000000001'. Cambio el del Product.
        self.product.barcode = '7791000000099'
        self.product.save()
        self.unit_pkg.refresh_from_db()
        # No fue pisado: sigue con el original.
        self.assertEqual(self.unit_pkg.barcode, '7791000000001')

    def test_sync_rellena_barcode_vacio_del_unit_pkg(self):
        # Vaciamos el unit_pkg
        self.unit_pkg.barcode = None
        self.unit_pkg.save(update_fields=['barcode'])

        # Re-guardamos el product (sin cambiar barcode pero forzando el ciclo)
        self.product.name = 'Forzar sync'
        self.product.save()

        self.unit_pkg.refresh_from_db()
        self.assertEqual(self.unit_pkg.barcode, '7791000000001')

    def test_sync_ignora_unit_pkg_inactivo(self):
        """Un unit_pkg soft-deleted no debe ser revivido por el sync."""
        self.unit_pkg.delete()  # soft-delete
        self.unit_pkg.refresh_from_db()
        self.assertFalse(self.unit_pkg.is_active)

        self.product.name = 'Cambio post-delete'
        self.product.save()

        self.unit_pkg.refresh_from_db()
        self.assertFalse(self.unit_pkg.is_active)
        # El nombre del unit inactivo no se actualizó (sigue 'Original')
        self.assertEqual(self.unit_pkg.name, 'Original')

    def test_sync_funciona_via_form_edit(self):
        """End-to-end por el flujo real del usuario: ProductForm.save()."""
        from stocks.forms import ProductForm
        form = ProductForm(
            data={
                'name': 'Editado por form', 'barcode': '7791000000001',
                'sku': 'SYNC-001', 'category': self.category.pk,
                'sale_price': '200', 'cost_price': '80',
                'purchase_price': '80', 'current_stock': '10',
                'min_stock': '0', 'quick_access_color': '#3498db',
                'quick_access_icon': 'fa-box', 'quick_access_position': '0',
                'weight_per_unit_grams': '0',
            },
            instance=self.product,
        )
        self.assertTrue(form.is_valid(), msg=form.errors)
        form.save()

        self.unit_pkg.refresh_from_db()
        self.assertEqual(self.unit_pkg.name, 'Editado por form')
        self.assertEqual(self.unit_pkg.sale_price, Decimal('200'))
        self.assertEqual(self.unit_pkg.purchase_price, Decimal('80'))


class ProductDeleteCascadesPackagingsTests(_BaseStocksTest):
    """Product.delete() debe cascadear soft-delete a sus packagings activos."""

    def setUp(self):
        super().setUp()
        self.product = Product.objects.create(
            name='Prod Con Empaques', sku='PCE-001', barcode='7796000000001',
            category=self.category,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'), current_stock=Decimal('60'),
        )
        self.unit_pkg = ProductPackaging.objects.create(
            product=self.product, packaging_type='unit',
            name='Unidad', barcode='7796000000001',
            units_per_display=1, displays_per_bulk=1,
            purchase_price=Decimal('40'), sale_price=Decimal('100'),
        )
        self.display_pkg = ProductPackaging.objects.create(
            product=self.product, packaging_type='display',
            name='Display x 12', barcode='7796000000099',
            units_per_display=12, displays_per_bulk=1,
            purchase_price=Decimal('480'), sale_price=Decimal('1100'),
        )

    def test_soft_delete_producto_cascadea_packagings(self):
        self.product.delete()

        self.unit_pkg.refresh_from_db()
        self.display_pkg.refresh_from_db()

        self.assertFalse(self.unit_pkg.is_active)
        self.assertFalse(self.display_pkg.is_active)
        self.assertIn(DELETED_BARCODE_MARKER, self.unit_pkg.barcode)
        self.assertIn(DELETED_BARCODE_MARKER, self.display_pkg.barcode)

    def test_barcode_reutilizable_tras_cascade_delete(self):
        """Después de borrar el producto, el barcode del display queda libre."""
        barcode_display = self.display_pkg.barcode
        self.product.delete()

        otro_prod = Product.objects.create(
            name='Otro Producto', sku='OTR-001', barcode='7796111000001',
            category=self.category,
            sale_price=Decimal('50'), purchase_price=Decimal('20'),
            cost_price=Decimal('20'), current_stock=Decimal('0'),
        )
        # No debe lanzar IntegrityError: el barcode fue liberado por la cascada
        pkg_nuevo = ProductPackaging.objects.create(
            product=otro_prod, packaging_type='display',
            name='Display nuevo', barcode=barcode_display,
            units_per_display=12, displays_per_bulk=1,
            purchase_price=Decimal('200'), sale_price=Decimal('500'),
        )
        self.assertTrue(pkg_nuevo.is_active)
        self.assertEqual(pkg_nuevo.barcode, barcode_display)


class OrphanedPackagingAutoReleaseTests(_BaseStocksTest):
    """_check_barcode libera automáticamente packagings de productos inactivos."""

    def setUp(self):
        super().setUp()
        self.parent = Product.objects.create(
            name='Producto Padre', sku='PP-900', barcode='7797000000001',
            category=self.category,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'), current_stock=Decimal('0'),
        )

    def test_check_barcode_libera_packaging_huerfano(self):
        """Si un packaging activo pertenece a un producto inactivo,
        _check_barcode lo debe liberar en vez de bloquear al usuario."""
        # Simular el estado huérfano: producto inactivo, packaging activo
        inactive_prod = Product.objects.create(
            name='Producto Inactivo', sku='PI-900', barcode=None,
            category=self.category,
            sale_price=Decimal('50'), purchase_price=Decimal('20'),
            cost_price=Decimal('20'), current_stock=Decimal('0'),
            is_active=False,
        )
        orphaned_pkg = ProductPackaging.objects.create(
            product=inactive_prod, packaging_type='bulk',
            name='Bulto Huerfano', barcode='7797000000099',
            units_per_display=6, displays_per_bulk=4,
            purchase_price=Decimal('200'), sale_price=Decimal('500'),
            is_active=True,
        )

        # Intentar registrar ese barcode en el producto padre debe funcionar.
        # No usamos follow=True para evitar el render del template (bug de
        # compatibilidad Python 3.14 / Django 4.2 en context.__copy__).
        resp = self.client.post(
            reverse('stocks:product_packaging', args=[self.parent.pk]),
            {
                'action': 'save_pkg',
                'pkg_units_per_display': '6',
                'pkg_displays_per_bulk': '4',
                'has_unit': '1',
                'unit_barcode': '7797000000001',
                'unit_name': 'Unidad',
                'unit_purchase_price': '40',
                'unit_sale_price': '100',
                'has_bulk': '1',
                'bulk_barcode': '7797000000099',
                'bulk_name': 'Bulto x 24',
                'bulk_purchase_price': '200',
                'bulk_sale_price': '500',
            },
        )
        # Debe redirigir (302) — sin error 500
        self.assertEqual(resp.status_code, 302)
        # El packaging huérfano debe haber sido soft-deleted
        orphaned_pkg.refresh_from_db()
        self.assertFalse(orphaned_pkg.is_active)
        self.assertIn(DELETED_BARCODE_MARKER, orphaned_pkg.barcode)
        # El nuevo bulk del padre debe existir con ese barcode
        new_bulk = ProductPackaging.objects.filter(
            product=self.parent, packaging_type='bulk', is_active=True
        ).first()
        self.assertIsNotNone(new_bulk)
        self.assertEqual(new_bulk.barcode, '7797000000099')

class ReleaseBarcodeHelperTests(TestCase):
    """Sanity check del helper directamente."""

    def test_genera_sufijo(self):
        self.assertEqual(_release_barcode('123', 5), f'123{DELETED_BARCODE_MARKER}5')

    def test_idempotente(self):
        already = f'123{DELETED_BARCODE_MARKER}5'
        self.assertEqual(_release_barcode(already, 9), already)

    def test_none_se_devuelve_intacto(self):
        self.assertIsNone(_release_barcode(None, 1))

    def test_empty_se_devuelve_intacto(self):
        self.assertEqual(_release_barcode('', 1), '')
