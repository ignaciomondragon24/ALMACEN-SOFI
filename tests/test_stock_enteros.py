"""
El stock de productos comunes se cuenta en unidades enteras, sin decimales
(pedido de Nacho, 2026-09-23). Los productos por peso siguen en gramos, que
pueden tener decimales (precisión de balanza) — no se tocan acá.

Cubre: alta de producto, conteo físico, empaques (recepción/apertura/ajuste),
alta rápida desde el POS, y que las pantallas muestren "24" y no "24.000".
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from stocks.models import Product, ProductCategory, ProductPackaging, StockMovement

User = get_user_model()


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        g, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user('entero_admin', password='x', is_superuser=True, is_staff=True)
        cls.user.groups.add(g)
        cls.cat = ProductCategory.objects.create(name='Almacén Entero Test')

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.user)


class AltaDeProductoTests(Base):
    def _alta(self, **extra):
        data = {'name': 'Aceite', 'sku': '', 'barcode': '7790000009001', 'cost_price': '1000',
                'sale_price': '1500', 'current_stock': '10', 'min_stock': '3', 'is_active': 'true',
                'weight_per_unit_grams': ''}
        data.update(extra)
        return self.c.post(reverse('stocks:product_create'), data)

    def test_stock_entero_se_guarda_bien(self):
        r = self._alta()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Product.objects.get().current_stock, Decimal('10'))

    def test_stock_con_decimales_se_rechaza(self):
        r = self._alta(current_stock='10.5')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'unidades enteras')
        self.assertFalse(Product.objects.exists())

    def test_stock_cero_o_vacio_no_rompe(self):
        r = self._alta(current_stock='0')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Product.objects.get().current_stock, Decimal('0'))

    def test_producto_de_deposito_tambien_exige_entero(self):
        """La pieza cerrada (deposito para venta por peso) se cuenta por pieza, entera."""
        r = self._alta(barcode='7790000009002', current_stock='2.5',
                       es_deposito_caramelera='true', weight_per_unit_grams='500')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'unidades enteras')

    def test_pantalla_de_alta_pide_paso_de_a_uno(self):
        r = self.c.get(reverse('stocks:product_create'))
        self.assertContains(r, 'step="1"')
        self.assertContains(r, 'unidades enteras')


class EdicionNoRompeStockViejoTests(Base):
    def test_editar_un_producto_con_stock_fraccionario_viejo_sigue_funcionando(self):
        """Si por lo que sea quedó un resto decimal de antes de este cambio, la
        edición (que no toca el stock) no debe bloquearse por eso."""
        p = Product.objects.create(name='Legado', sku='LEG-1', cost_price=Decimal('100'),
                                   sale_price=Decimal('150'), current_stock=Decimal('9.500'))
        r = self.c.post(reverse('stocks:product_edit', args=[p.pk]), {
            'name': 'Legado', 'sku': 'LEG-1', 'barcode': '', 'cost_price': '100', 'sale_price': '160',
            'current_stock': '9.500', 'min_stock': '0', 'is_active': 'true', 'weight_per_unit_grams': ''})
        self.assertEqual(r.status_code, 302)
        p.refresh_from_db()
        self.assertEqual(p.sale_price, Decimal('160'))
        self.assertEqual(p.current_stock, Decimal('9.500'))   # no se tocó ni se bloqueó


class ConteoFisicoTests(Base):
    def setUp(self):
        super().setUp()
        self.p = Product.objects.create(name='Fideos', sku='FID-E', cost_price=Decimal('400'),
                                        sale_price=Decimal('700'), current_stock=Decimal('20'), category=self.cat)

    def test_conteo_con_decimales_se_rechaza(self):
        r = self.c.post(reverse('stocks:inventory_count', args=[self.p.pk]),
                        {'new_quantity': '18.5', 'reason': 'conteo_fisico'})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'número entero')
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('20'))

    def test_conteo_entero_funciona(self):
        r = self.c.post(reverse('stocks:inventory_count', args=[self.p.pk]),
                        {'new_quantity': '18', 'reason': 'conteo_fisico'})
        self.assertEqual(r.status_code, 302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('18'))

    def test_pantalla_de_conteo_muestra_el_stock_sin_decimales(self):
        r = self.c.get(reverse('stocks:inventory_count', args=[self.p.pk]))
        self.assertContains(r, '20')
        self.assertNotContains(r, '20.000')
        self.assertNotContains(r, '20.00<')

    def test_producto_por_peso_conserva_decimales_en_el_conteo(self):
        self.c.post(reverse('granel:caramelera_create'), {
            'nombre': 'Jamón entero test', 'precio_kg': '12000', 'costo_kg': '8000',
            'stock_inicial': '2.5', 'stock_unidad': 'kg'})
        peso = Product.objects.get(is_granel=True)
        r = self.c.post(reverse('stocks:inventory_count', args=[peso.pk]),
                        {'new_quantity': '1850.5', 'reason': 'conteo_fisico'})
        self.assertEqual(r.status_code, 302, getattr(r, 'content', b'')[:200])
        peso.refresh_from_db()
        self.assertEqual(peso.current_stock, Decimal('1850.500'))


class ProductoDetalleYListaTests(Base):
    def setUp(self):
        super().setUp()
        self.p = Product.objects.create(name='Yerba Entera', sku='YER-E', cost_price=Decimal('2000'),
                                        sale_price=Decimal('3000'), current_stock=Decimal('24'),
                                        min_stock=5, category=self.cat)

    def test_lista_muestra_24_no_24_000(self):
        r = self.c.get(reverse('stocks:product_list'))
        self.assertContains(r, '24')
        self.assertNotContains(r, '24.000')

    def test_detalle_muestra_24_no_24_000(self):
        r = self.c.get(reverse('stocks:product_detail', args=[self.p.pk]))
        self.assertContains(r, '24')
        self.assertNotContains(r, '24.000')

    def test_bajo_minimo_tambien_se_ve_entero(self):
        # low_stock.html ya usaba floatformat:0 para el stock antes de este cambio;
        # este test es solo para no perder esa cobertura. Ojo: sale_price=$3.000
        # también aparece en la página (con separador de miles), así que hay que
        # buscar el stock puntualmente, no cualquier "3.000" en toda la respuesta.
        self.p.current_stock = Decimal('3')
        self.p.save()
        r = self.c.get(reverse('stocks:low_stock'))
        self.assertContains(r, 'Yerba Entera')
        self.assertContains(r, '>3<')


class EmpaquesTests(Base):
    def setUp(self):
        super().setUp()
        self.p = Product.objects.create(name='Alfajor Entero', sku='ALF-E', cost_price=Decimal('100'),
                                        sale_price=Decimal('200'), current_stock=Decimal('0'), category=self.cat)
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'save_pkg', 'has_unit': '1', 'unit_purchase_price': '100', 'unit_sale_price': '200',
            'has_display': '1', 'display_barcode': '7790000009101', 'display_purchase_price': '1100',
            'display_sale_price': '2200', 'has_bulk': '1', 'bulk_barcode': '7790000009102',
            'bulk_purchase_price': '4200', 'bulk_sale_price': '8400',
            'pkg_units_per_display': '12', 'pkg_displays_per_bulk': '4'})
        self.bulk = self.p.packagings.get(packaging_type='bulk')
        self.unit = self.p.packagings.get(packaging_type='unit')

    def test_recibir_con_decimales_se_rechaza(self):
        r = self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'receive', 'packaging_id': self.bulk.pk, 'quantity': '1.5', 'cost': '4200'})
        self.assertEqual(r.status_code, 302)
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('0'))

    def test_recibir_entero_funciona(self):
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'receive', 'packaging_id': self.bulk.pk, 'quantity': '2', 'cost': '4200'})
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('96'))

    def test_abrir_paquete_con_decimales_se_rechaza(self):
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'receive', 'packaging_id': self.bulk.pk, 'quantity': '1', 'cost': '4200'})
        r = self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'open', 'packaging_id': self.bulk.pk, 'quantity': '0.5'})
        self.bulk.refresh_from_db()
        self.assertEqual(self.bulk.current_stock, Decimal('1'))   # no se abrió nada

    def test_ajustar_unidades_con_decimales_se_rechaza(self):
        r = self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'adjust', 'packaging_id': self.unit.pk, 'new_stock': '5.5', 'reason': 'test'})
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('0'))

    def test_ajustar_unidades_entero_funciona(self):
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'adjust', 'packaging_id': self.unit.pk, 'new_stock': '30', 'reason': 'test'})
        self.p.refresh_from_db()
        self.assertEqual(self.p.current_stock, Decimal('30'))

    def test_ajustar_display_con_decimales_SI_se_permite(self):
        """Media caja abierta es una fracción legítima a nivel display/bulto."""
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'receive', 'packaging_id': self.bulk.pk, 'quantity': '1', 'cost': '4200'})
        self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'open', 'packaging_id': self.bulk.pk, 'quantity': '1'})
        display = self.p.packagings.get(packaging_type='display')
        r = self.c.post(reverse('stocks:product_packaging', args=[self.p.pk]), {
            'action': 'adjust', 'packaging_id': display.pk, 'new_stock': '2.5', 'reason': 'media caja'})
        self.assertEqual(r.status_code, 302)
        display.refresh_from_db()
        self.assertEqual(display.current_stock, Decimal('2.5'))


class AltaRapidaDesdeElPosTests(Base):
    def test_stock_inicial_entero(self):
        r = self.c.post(reverse('pos:api_quick_add_product'),
                        data='{"name":"Galletitas","sale_price":800,"purchase_price":500,"initial_stock":10}',
                        content_type='application/json')
        self.assertEqual(r.status_code, 200, r.content)
        p = Product.objects.get(name='Galletitas')
        self.assertEqual(p.current_stock, Decimal('10'))
        self.assertEqual(StockMovement.objects.filter(product=p).count(), 1)

    def test_stock_inicial_decimal_se_rechaza_con_mensaje_claro(self):
        r = self.c.post(reverse('pos:api_quick_add_product'),
                        data='{"name":"Galletitas2","sale_price":800,"initial_stock":10.5}',
                        content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('entero', r.json()['error'])
        self.assertFalse(Product.objects.filter(name='Galletitas2').exists())

    def test_sin_stock_inicial_no_rompe(self):
        r = self.c.post(reverse('pos:api_quick_add_product'),
                        data='{"name":"Galletitas3","sale_price":800}', content_type='application/json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(Product.objects.get(name='Galletitas3').current_stock, Decimal('0'))
