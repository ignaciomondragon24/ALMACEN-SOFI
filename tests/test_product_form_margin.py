"""Test del bug reportado por Sofia: el campo "Margen %" del formulario de
producto siempre mostraba 30.00 al abrir CUALQUIER producto para editar,
sin importar su margen real (cost_price/sale_price) — porque el campo no
estaba atado a ningún dato real, solo era un helper de cálculo en JS con un
fallback fijo en el template. Si el usuario tocaba el precio de costo, el JS
recalculaba el precio de venta usando ese 30% falso y le pisaba precios
reales con márgenes distintos (ej: 46%).

Fix: el campo arranca con `product.margin_percent` real al editar, y con el
`default_margin_percent` de la categoría elegida al crear un producto nuevo
(vía JS al cambiar de categoría), en vez de un 30% fijo.
"""
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from stocks.models import Product, ProductCategory

User = get_user_model()


class ProductFormMarginTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.admin = User.objects.create_user(
            username='margin_admin', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.admin.groups.add(cls.admin_group)
        cls.category = ProductCategory.objects.create(
            name='Fiambres', default_margin_percent=Decimal('46.00'),
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)

    def test_edit_form_shows_real_margin_not_hardcoded_30(self):
        """Producto con margen real del 46% no debe mostrar 30% al editar."""
        product = Product.objects.create(
            name='Jamon Cocido Fraccionado', sku='MARGIN-001',
            category=self.category,
            cost_price=Decimal('100.00'), purchase_price=Decimal('100.00'),
            sale_price=Decimal('146.00'),  # margen real = 46%
        )
        self.assertEqual(product.margin_percent, Decimal('46.00'))

        response = self.client.get(reverse('stocks:product_edit', args=[product.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('value="46.00"', content)
        self.assertNotIn('value="30.00"', content)

    def test_category_option_carries_its_default_margin(self):
        """El <option> de categoría debe exponer su margen por defecto para
        que el JS lo use al crear un producto nuevo (en vez de 30% fijo)."""
        response = self.client.get(reverse('stocks:product_create'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(f'data-margin="46.00"', content)
