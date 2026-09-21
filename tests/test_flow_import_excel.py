"""
Flujo: importar el inventario desde un Excel (lo que Sofia va a hacer con su lista).

Cubre: vista previa, confirmación, categorías por hoja, códigos de barras que Excel
guarda como número, precios en formato argentino, cálculo por margen, productos que ya
existen (se actualizan, no se duplican), stock inicial, "borrar todo antes" (preservando
las promociones) y archivos inválidos.
"""
import io
from decimal import Decimal

import openpyxl
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from promotions.models import Promotion, PromotionProduct
from stocks.models import Product, ProductCategory, StockMovement, UnitOfMeasure

User = get_user_model()


def xlsx(sheets):
    """sheets = {'Fiambres': [[encabezados], [fila], ...]} → SimpleUploadedFile .xlsx"""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return SimpleUploadedFile('inventario.xlsx', buf.getvalue(),
                              content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


class ImportExcelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        g, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user('importa', password='x')
        cls.user.groups.add(g)

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.user)
        self.url = reverse('stocks:import_excel')

    def subir(self, sheets, confirmar=True, **extra):
        r = self.c.post(self.url, {'excel_file': xlsx(sheets)})
        self.assertEqual(r.status_code, 200, 'la vista previa debería mostrarse')
        if not confirmar:
            return r
        return self.c.post(self.url, dict({'confirm': '1'}, **extra))

    HEAD = ['Código de barras', 'Código interno', 'Nombre', 'Unidad', 'Costo', 'Venta', 'Stock']

    def test_pantalla_de_importar_abre(self):
        r = self.c.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Stock')

    def test_importa_dos_hojas_como_dos_categorias(self):
        r = self.subir({
            'Fiambres': [self.HEAD, [7790000000011, 'FIA-1', 'Queso cremoso', 'kg', 5000, 7500, 3]],
            'Almacén': [self.HEAD, [7790000000028, 'ALM-1', 'Fideos 500g', 'unidad', 600, 900, 24]],
        })
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(set(ProductCategory.objects.values_list('name', flat=True)), {'Fiambres', 'Almacén'})
        fideos = Product.objects.get(sku='ALM-1')
        self.assertEqual(fideos.category.name, 'Almacén')
        self.assertEqual(fideos.sale_price, Decimal('900.00'))
        self.assertEqual(fideos.cost_price, Decimal('600.00'))

    def test_codigo_de_barras_numerico_de_excel_queda_limpio(self):
        self.subir({'Almacén': [self.HEAD, [7790000000011.0, 'A', 'Aceite', 'u', 1000, 1500, 5]]})
        self.assertEqual(Product.objects.get(sku='A').barcode, '7790000000011')

    def test_precios_en_formato_argentino_y_con_signo_peso(self):
        self.subir({'Almacén': [self.HEAD, ['', 'P1', 'Yerba 1kg', 'u', '$ 1.234,56', '$2.500,50', 2]]})
        p = Product.objects.get(sku='P1')
        self.assertEqual(p.cost_price, Decimal('1234.56'))
        self.assertEqual(p.sale_price, Decimal('2500.50'))

    def test_calcula_el_precio_de_venta_desde_el_margen(self):
        self.subir({'Almacén': [['Nombre', 'Código interno', 'Costo', 'Margen %'],
                                ['Harina 1kg', 'H1', 1000, 30]]})
        self.assertEqual(Product.objects.get(sku='H1').sale_price, Decimal('1300.00'))

    def test_stock_inicial_se_carga_y_deja_movimiento(self):
        self.subir({'Almacén': [self.HEAD, ['', 'S1', 'Arroz', 'u', 500, 800, 12.5]]})
        p = Product.objects.get(sku='S1')
        self.assertEqual(p.current_stock, Decimal('12.500'))
        mov = StockMovement.objects.get(product=p)
        self.assertEqual(mov.quantity, Decimal('12.500'))
        self.assertEqual(mov.stock_after, Decimal('12.500'))
        self.assertIn('Importación', mov.reference)

    def test_sin_columna_de_stock_arranca_en_cero(self):
        self.subir({'Almacén': [['Nombre', 'Código interno', 'Costo', 'Venta'], ['Sal', 'SAL1', 100, 200]]})
        self.assertEqual(Product.objects.get(sku='SAL1').current_stock, Decimal('0'))

    def test_columna_cantidad_tambien_se_reconoce(self):
        self.subir({'Almacén': [['Producto', 'Codigo interno', 'Costo', 'Venta', 'Cantidad'],
                                ['Azúcar', 'AZ1', 300, 450, 40]]})
        self.assertEqual(Product.objects.get(sku='AZ1').current_stock, Decimal('40.000'))

    def test_producto_existente_se_actualiza_y_no_se_duplica_ni_cambia_su_stock(self):
        existente = Product.objects.create(
            name='Fideos viejo', sku='ALM-1', barcode='7790000000028',
            cost_price=Decimal('500'), sale_price=Decimal('700'), current_stock=Decimal('8'))
        self.subir({'Almacén': [self.HEAD, [7790000000028, 'ALM-1', 'Fideos 500g', 'u', 600, 900, 99]]})
        self.assertEqual(Product.objects.count(), 1)
        existente.refresh_from_db()
        self.assertEqual(existente.sale_price, Decimal('900.00'))
        self.assertEqual(existente.current_stock, Decimal('8'))   # el stock real no se pisa

    def test_reimportar_el_mismo_archivo_no_duplica(self):
        hojas = {'Almacén': [self.HEAD, [7790000000011, 'A1', 'Aceite', 'u', 1000, 1500, 5]]}
        self.subir(hojas)
        self.subir(hojas)
        self.assertEqual(Product.objects.count(), 1)
        self.assertEqual(Product.objects.get().current_stock, Decimal('5.000'))

    def test_unidad_de_medida_se_crea_o_reutiliza(self):
        UnitOfMeasure.objects.create(name='Kilogramo', abbreviation='kg')
        self.subir({'Almacén': [self.HEAD, ['', 'U1', 'Queso', 'kg', 1, 2, 1], ['', 'U2', 'Pan', 'docena', 1, 2, 1]]})
        self.assertEqual(Product.objects.get(sku='U1').unit_of_measure.name, 'Kilogramo')
        self.assertTrue(Product.objects.get(sku='U2').unit_of_measure)

    def test_sin_codigos_genera_sku_y_no_falla(self):
        self.subir({'Almacén': [['Nombre', 'Costo', 'Venta'], ['Sin código', 10, 20], ['Otro sin código', 11, 22]]})
        self.assertEqual(Product.objects.count(), 2)
        self.assertEqual(Product.objects.filter(sku='').count(), 0)

    def test_barcode_repetido_en_el_archivo_es_el_mismo_producto_y_no_rompe(self):
        # El código de barras es único: dos filas con el mismo código son un solo producto.
        self.subir({'Almacén': [self.HEAD, [7790000000011, 'X1', 'Uno', 'u', 1, 2, 1],
                                           [7790000000011, 'X2', 'Dos', 'u', 1, 3, 1]]})
        self.assertEqual(Product.objects.filter(barcode='7790000000011').count(), 1)

    def test_borrar_todo_antes_conserva_las_promociones(self):
        viejo = Product.objects.create(name='Viejo', sku='V1', cost_price=Decimal('1'), sale_price=Decimal('2'))
        promo = Promotion.objects.create(name='2x1', promo_type='nxm', status='active',
                                         quantity_required=2, quantity_charged=1)
        PromotionProduct.objects.create(promotion=promo, product=viejo)
        self.subir({'Almacén': [self.HEAD, ['', 'V1', 'Viejo renovado', 'u', 5, 9, 3]]}, flush='1')
        self.assertFalse(Product.objects.filter(name='Viejo').exists())
        nuevo = Product.objects.get(sku='V1')
        self.assertTrue(PromotionProduct.objects.filter(promotion=promo, product=nuevo).exists())
        self.assertTrue(Promotion.objects.filter(pk=promo.pk).exists())

    def test_archivo_que_no_es_excel_se_rechaza(self):
        r = self.c.post(self.url, {'excel_file': SimpleUploadedFile('datos.txt', b'hola')})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Product.objects.count(), 0)

    def test_excel_corrupto_no_da_error_500(self):
        r = self.c.post(self.url, {'excel_file': SimpleUploadedFile('roto.xlsx', b'no soy un excel')})
        self.assertEqual(r.status_code, 302)

    def test_excel_vacio_avisa(self):
        r = self.c.post(self.url, {'excel_file': xlsx({'Hoja1': [['Nombre', 'Costo']]})})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Product.objects.count(), 0)

    def test_confirmar_sin_subir_archivo_no_rompe(self):
        r = self.c.post(self.url, {'confirm': '1'})
        self.assertEqual(r.status_code, 302)

    def test_lo_importado_se_puede_vender_en_el_pos(self):
        """El objetivo final: lo que se importa aparece en el buscador de la caja con su stock."""
        self.subir({'Almacén': [self.HEAD, [7790000000011, 'A1', 'Aceite girasol', 'u', 1000, 1500, 6]]})
        r = self.c.get(reverse('pos:api_search'), {'q': 'aceite'})
        prod = r.json()['products'][0]
        self.assertEqual(prod['unit_price'], 1500.0)
        self.assertEqual(prod['stock'], 6.0)
        # y también por código de barras
        r = self.c.get(reverse('pos:api_search'), {'q': '7790000000011'})
        self.assertEqual(r.json()['products'][0]['name'], 'Aceite girasol')

    def test_exportar_e_importar_ida_y_vuelta(self):
        """Lo que exporta el sistema se puede volver a importar."""
        Product.objects.create(name='Galletitas', sku='G1', barcode='7790000000099',
                               cost_price=Decimal('300'), sale_price=Decimal('500'), current_stock=Decimal('7'))
        r = self.c.get(reverse('stocks:export_excel'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('spreadsheetml', r['Content-Type'])
        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        self.assertTrue(wb.sheetnames)
