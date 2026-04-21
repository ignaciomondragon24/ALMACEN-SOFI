"""Tests del form de empaques: resolución de colisiones de barcode."""
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from stocks.models import Product, ProductCategory, ProductPackaging

User = get_user_model()


class PackagingBarcodeCollisionTests(TestCase):
    """Cuando el barcode que el usuario quiere usar para un packaging ya
    pertenece a un Product legacy, el sistema debe permitir la creación
    y liberar el barcode del Product viejo (ponerlo a NULL) en vez de
    fallar. El POS prioriza ProductPackaging al escanear, así que la
    coexistencia no rompe las ventas, pero tener dos dueños del mismo
    EAN en el listado es confuso."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.admin = User.objects.create_user(
            username='pkg_admin', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.admin.groups.add(cls.admin_group)
        cls.category = ProductCategory.objects.create(name='Test Cat')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)
        self.product = Product.objects.create(
            name='Producto Padre', sku='PP-001', barcode='7791234000001',
            category=self.category,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'), current_stock=Decimal('24'),
        )

    def _post_save_pkg(self, **extra):
        data = {
            'action': 'save_pkg',
            'pkg_units_per_display': '6',
            'pkg_displays_per_bulk': '4',
            'has_unit': '1',
            'unit_barcode': self.product.barcode,
            'unit_name': 'Unidad',
            'unit_purchase_price': '40',
            'unit_sale_price': '100',
        }
        data.update(extra)
        return self.client.post(
            reverse('stocks:product_packaging', args=[self.product.pk]),
            data,
            follow=True,
        )

    def test_colision_con_product_legacy_permite_y_libera_barcode(self):
        """Si existe otro Product con el mismo barcode, se permite la creación
        y se libera (NULL) el barcode del Product viejo."""
        legacy = Product.objects.create(
            name='Producto Viejo', sku='LEG-001',
            barcode='7791234000077',
            category=self.category,
            sale_price=Decimal('300'), purchase_price=Decimal('150'),
            cost_price=Decimal('150'), current_stock=Decimal('5'),
        )

        resp = self._post_save_pkg(
            has_display='1',
            display_barcode='7791234000077',
            display_name='Display x 6',
            display_purchase_price='240',
            display_sale_price='600',
        )
        self.assertEqual(resp.status_code, 200)

        # El packaging se creó con el barcode
        display = ProductPackaging.objects.get(
            product=self.product, packaging_type='display'
        )
        self.assertEqual(display.barcode, '7791234000077')

        # El Product viejo sigue activo pero sin barcode
        legacy.refresh_from_db()
        self.assertIsNone(legacy.barcode)
        self.assertTrue(legacy.is_active)
        # Stock e historial del Product viejo intactos
        self.assertEqual(legacy.current_stock, Decimal('5'))
        self.assertEqual(legacy.sale_price, Decimal('300'))

    def test_colision_con_otro_packaging_sigue_bloqueando(self):
        """Si el barcode ya lo usa otro packaging de otro producto,
        seguimos rechazando (es un conflicto real a nivel DB)."""
        otro = Product.objects.create(
            name='Otro Padre', sku='OP-001',
            category=self.category,
            sale_price=Decimal('50'), purchase_price=Decimal('20'),
            cost_price=Decimal('20'), current_stock=Decimal('10'),
        )
        ProductPackaging.objects.create(
            product=otro, packaging_type='display',
            barcode='7791234000099', name='Display otro',
            units_per_display=6, displays_per_bulk=1,
            purchase_price=Decimal('120'), sale_price=Decimal('300'),
        )

        resp = self._post_save_pkg(
            has_display='1',
            display_barcode='7791234000099',
            display_name='Display colide',
            display_purchase_price='240',
            display_sale_price='600',
        )
        # No se creó el packaging display del producto padre
        self.assertFalse(
            ProductPackaging.objects.filter(
                product=self.product, packaging_type='display'
            ).exists()
        )
        # Mensaje de error en la respuesta
        msgs = [str(m) for m in list(resp.context['messages'])]
        self.assertTrue(
            any('ya está en uso' in m for m in msgs),
            f'Se esperaba error de barcode en uso, mensajes: {msgs}',
        )

    def test_sin_colision_crea_packaging_normal(self):
        """El flujo feliz no debe cambiar."""
        resp = self._post_save_pkg(
            has_display='1',
            display_barcode='7791234000055',
            display_name='Display libre',
            display_purchase_price='240',
            display_sale_price='600',
        )
        self.assertEqual(resp.status_code, 200)

        display = ProductPackaging.objects.get(
            product=self.product, packaging_type='display'
        )
        self.assertEqual(display.barcode, '7791234000055')

    def test_barcode_del_propio_producto_no_genera_conflicto(self):
        """Usar el barcode del Product padre para el packaging unit no
        debe disparar la liberación (es el caso natural)."""
        # _save_inline_packaging con has_unit=1 y unit_barcode = barcode
        # del padre. No debe tocar al Product padre.
        original_barcode = self.product.barcode
        resp = self._post_save_pkg()  # solo unit, barcode = del padre
        self.assertEqual(resp.status_code, 200)

        self.product.refresh_from_db()
        self.assertEqual(self.product.barcode, original_barcode)

        unit = ProductPackaging.objects.get(
            product=self.product, packaging_type='unit'
        )
        self.assertEqual(unit.barcode, original_barcode)
