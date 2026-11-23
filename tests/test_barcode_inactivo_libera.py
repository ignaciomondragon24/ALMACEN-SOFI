"""Un producto/empaque inactivo no puede retener su código de barras."""
from django.test import TestCase

from stocks.models import Product, ProductPackaging


class BarcodeInactivoTests(TestCase):
    def _producto(self, barcode='7790000000011'):
        return Product.objects.create(
            name='Mermelada', barcode=barcode, sale_price=100, is_active=True
        )

    def test_destildar_activo_libera_el_codigo(self):
        p = self._producto()
        p.is_active = False
        p.save()  # como hace el formulario de edición
        p.refresh_from_db()
        self.assertIn('_deleted_', p.barcode)
        # Ahora se puede crear otro producto con el mismo código.
        Product.objects.create(
            name='Mermelada nueva', barcode='7790000000011', sale_price=100
        )

    def test_save_con_update_fields_tambien_libera(self):
        p = self._producto('7790000000028')
        p.is_active = False
        p.save(update_fields=['is_active'])
        p.refresh_from_db()
        self.assertIn('_deleted_', p.barcode)

    def test_desactivar_producto_desactiva_y_libera_sus_empaques(self):
        p = self._producto('7790000000035')
        pkg = ProductPackaging.objects.create(
            product=p, packaging_type='display', name='Display',
            barcode='7790000000042', units_per_display=6, sale_price=500,
        )
        p.is_active = False
        p.save()
        pkg.refresh_from_db()
        self.assertFalse(pkg.is_active)
        self.assertIn('_deleted_', pkg.barcode)

    def test_empaque_inactivo_libera_el_codigo(self):
        p = self._producto('7790000000059')
        pkg = ProductPackaging.objects.create(
            product=p, packaging_type='display', name='Display',
            barcode='7790000000066', units_per_display=6, sale_price=500,
        )
        pkg.is_active = False
        pkg.save()
        pkg.refresh_from_db()
        self.assertIn('_deleted_', pkg.barcode)

    def test_producto_activo_conserva_su_codigo(self):
        p = self._producto('7790000000073')
        p.name = 'Otro nombre'
        p.save()
        p.refresh_from_db()
        self.assertEqual(p.barcode, '7790000000073')


class CrearConCodigoRetenidoPorInactivoTests(TestCase):
    """Reproduce lo de Sofia: el código 'no existe' pero al crear 'ya existe'."""
    CODE = '7790580148973'

    def _inactivo_retenido(self):
        # Como quedó en producción: inactivo y con el código sin liberar.
        p = Product.objects.create(name='Mermelada vieja', barcode=self.CODE,
                                   sale_price=100, is_active=True)
        Product.objects.filter(pk=p.pk).update(is_active=False)
        return p

    def test_formulario_de_alta_libera_y_deja_crear(self):
        from stocks.forms import ProductForm
        viejo = self._inactivo_retenido()
        form = ProductForm(data={
            'name': 'Mermelada nueva', 'barcode': self.CODE, 'sku': '',
            'sale_price': '100', 'cost_price': '50', 'purchase_price': '50',
            'current_stock': '1', 'min_stock': '0', 'is_active': 'on',
            'quick_access_color': '#3498db', 'quick_access_icon': 'fa-box',
            'quick_access_position': '0', 'weight_per_unit_grams': '0',
        })
        self.assertTrue(form.is_valid(), msg=form.errors)
        nuevo = form.save()
        self.assertEqual(nuevo.barcode, self.CODE)
        viejo.refresh_from_db()
        self.assertIn('_deleted_', viejo.barcode)
        self.assertFalse(viejo.is_active)

    def test_no_toca_productos_activos(self):
        from stocks.models import liberar_barcode_de_inactivos
        activo = Product.objects.create(name='A', barcode=self.CODE,
                                        sale_price=10, is_active=True)
        self.assertEqual(liberar_barcode_de_inactivos(self.CODE), 0)
        activo.refresh_from_db()
        self.assertEqual(activo.barcode, self.CODE)

    def test_empaque_activo_de_producto_inactivo_tambien_se_libera(self):
        from stocks.models import liberar_barcode_de_inactivos
        p = Product.objects.create(name='P', barcode='7790000000999',
                                   sale_price=10, is_active=True)
        pkg = ProductPackaging.objects.create(
            product=p, packaging_type='display', name='D', barcode=self.CODE,
            units_per_display=6, sale_price=50)
        Product.objects.filter(pk=p.pk).update(is_active=False)  # huérfano
        self.assertEqual(liberar_barcode_de_inactivos(self.CODE), 1)
        pkg.refresh_from_db()
        self.assertFalse(pkg.is_active)
        self.assertIn('_deleted_', pkg.barcode)

    def test_alta_rapida_del_pos_con_codigo_retenido(self):
        from django.contrib.auth import get_user_model
        from django.urls import reverse
        import json
        self._inactivo_retenido()
        u = get_user_model().objects.create_superuser('adm', 'a@a.com', 'x')
        self.client.force_login(u)
        r = self.client.post(reverse('pos:api_quick_add_product'), data=json.dumps({
            'name': 'Mermelada POS', 'barcode': self.CODE, 'sale_price': 100}),
            content_type='application/json')
        self.assertIn(r.status_code, (200, 201), r.content)
        self.assertEqual(Product.objects.filter(barcode=self.CODE, is_active=True).count(), 1)
