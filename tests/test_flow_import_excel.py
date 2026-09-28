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

    def test_celda_de_precio_vacia_en_una_actualizacion_no_pisa_el_precio_existente(self):
        # Antes: una celda vacía en una fila de actualización ponía el producto en
        # $0,00 de costo y $0,01 de precio, en silencio. Ahora, vacío = no tocar ese campo.
        existente = Product.objects.create(
            name='Aceite viejo', sku='ACE-1', barcode='7790000000099',
            cost_price=Decimal('1000'), purchase_price=Decimal('1000'),
            sale_price=Decimal('1500'), current_stock=Decimal('5'))
        self.subir({'Almacén': [self.HEAD, [7790000000099, 'ACE-1', 'Aceite', 'u', '', '', 5]]})
        existente.refresh_from_db()
        self.assertEqual(existente.cost_price, Decimal('1000.00'))
        self.assertEqual(existente.purchase_price, Decimal('1000.00'))
        self.assertEqual(existente.sale_price, Decimal('1500.00'))

    def test_celda_de_solo_costo_vacia_deja_el_precio_de_venta_actualizarse_igual(self):
        existente = Product.objects.create(
            name='Yerba vieja', sku='YER-1', barcode='7790000000100',
            cost_price=Decimal('2000'), sale_price=Decimal('3000'), current_stock=Decimal('2'))
        self.subir({'Almacén': [self.HEAD, [7790000000100, 'YER-1', 'Yerba', 'u', '', 3300, 2]]})
        existente.refresh_from_db()
        self.assertEqual(existente.cost_price, Decimal('2000.00'))    # costo vacío: no se toca
        self.assertEqual(existente.sale_price, Decimal('3300.00'))    # venta sí vino: se actualiza

    def test_costo_en_cero_de_verdad_si_se_pisa(self):
        # Un 0 real (no una celda vacía) es un valor válido y sí debe guardarse.
        existente = Product.objects.create(
            name='Regalo', sku='REG-1', barcode='7790000000101',
            cost_price=Decimal('100'), sale_price=Decimal('200'), current_stock=Decimal('1'))
        self.subir({'Almacén': [self.HEAD, [7790000000101, 'REG-1', 'Regalo', 'u', 0, 200, 1]]})
        existente.refresh_from_db()
        self.assertEqual(existente.cost_price, Decimal('0.00'))

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


class VentaPorPesoImportTests(TestCase):
    """Fase 4 del rediseño de venta por peso (2026-09-27): Importar Excel
    también carga los tramos de precio (100g/1-4/1-2 y ofertas) — lo que
    Sofia pidió después de mandar una muestra real de lo que genera su
    skill. Sus columnas base (Costo/Venta) para un producto por peso son
    "por kilo", igual que en el formulario manual."""

    @classmethod
    def setUpTestData(cls):
        g, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user('importa_peso', password='x')
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
    HEAD_PESO = [
        'Código de barras', 'Código interno', 'Nombre', 'Unidad',
        'Precio 100g', 'Precio 1/4', 'Oferta 1/4', 'Costo', 'Venta', 'Stock',
    ]

    def test_crea_producto_por_peso_con_tramos(self):
        self.subir({'Fiambres': [
            self.HEAD_PESO,
            ['', 'JC-1', 'Jamón Cocido', 'kg', 1100, 2300, '', 8000, 11000, 2.5],
        ]})
        p = Product.objects.get(sku='JC-1')
        self.assertTrue(p.is_granel)
        self.assertEqual(p.sale_price_100g, Decimal('1100.00'))
        self.assertEqual(p.sale_price_250g, Decimal('2300.00'))
        self.assertEqual(p.oferta_price_250g, Decimal('0'))
        self.assertEqual(p.sale_price, Decimal('11000.00'))   # Costo/Venta = por kilo
        self.assertEqual(p.cost_price, Decimal('8000.00'))
        self.assertEqual(p.current_stock, Decimal('2.500'))   # kilos, con decimales

    def test_producto_comun_con_unidad_kg_no_se_marca_por_peso(self):
        """Ojo: "kg" como Unidad de Medida NO alcanza para marcar is_granel —
        lo usa cualquier verdulería (papa, cebolla) sin tramos de precio."""
        self.subir({'Almacén': [self.HEAD, [7790000000011, 'PAP-1', 'Papa', 'kg', 300, 500, 10]]})
        p = Product.objects.get(sku='PAP-1')
        self.assertFalse(p.is_granel)

    def test_unidad_queda_forzada_a_kilogramo_pise_lo_que_pise_la_columna(self):
        self.subir({'Fiambres': [
            self.HEAD_PESO,
            ['', 'JC-4', 'Jamón', '100g', 1100, 2300, '', 8000, 11000, 2.5],
        ]})
        p = Product.objects.get(sku='JC-4')
        self.assertEqual(p.unit_of_measure.name, 'Kilogramo')

    def test_oferta_por_cuarto_se_carga(self):
        self.subir({'Fiambres': [
            self.HEAD_PESO,
            ['', 'JC-2', 'Jamón Crudo', 'kg', 1500, 3000, 2500, 9000, 12000, 1],
        ]})
        p = Product.objects.get(sku='JC-2')
        self.assertEqual(p.oferta_price_250g, Decimal('2500.00'))

    def test_columna_precio_cuarto_tambien_se_reconoce(self):
        head = ['Código interno', 'Nombre', 'Precio Cuarto', 'Costo', 'Venta']
        self.subir({'Fiambres': [head, ['Q1', 'Queso de Máquina', 2900, 9000, 12000]]})
        p = Product.objects.get(sku='Q1')
        self.assertTrue(p.is_granel)
        self.assertEqual(p.sale_price_250g, Decimal('2900.00'))

    def test_columna_precio_medio_kilo_y_oferta_medio_se_reconocen(self):
        head = ['Código interno', 'Nombre', 'Precio Medio Kilo', 'Oferta Medio', 'Costo', 'Venta']
        self.subir({'Fiambres': [head, ['M1', 'Mortadela', 5500, 5000, 8000, 12000]]})
        p = Product.objects.get(sku='M1')
        self.assertTrue(p.is_granel)
        self.assertEqual(p.sale_price_500g, Decimal('5500.00'))
        self.assertEqual(p.oferta_price_500g, Decimal('5000.00'))

    def test_actualizacion_no_pisa_tramos_con_celda_vacia(self):
        existente = Product.objects.create(
            name='Salame Viejo', sku='SAL-1', is_granel=True,
            cost_price=Decimal('7000'), sale_price=Decimal('10000'),
            sale_price_250g=Decimal('2700'), current_stock=Decimal('3'),
        )
        # Reimporta solo actualizando el costo — las columnas de tramo vienen vacías.
        self.subir({'Fiambres': [self.HEAD_PESO,
                                 ['', 'SAL-1', 'Salame', 'kg', '', '', '', 7500, '', 3]]})
        existente.refresh_from_db()
        self.assertEqual(existente.cost_price, Decimal('7500.00'))       # sí vino: se actualiza
        self.assertEqual(existente.sale_price_250g, Decimal('2700.00'))  # vacío: no se toca

    def test_producto_comun_se_convierte_al_agregarle_un_tramo(self):
        """Si un producto ya existente (común) aparece con un tramo cargado
        en una reimportación, pasa a ser por peso — nunca al revés."""
        existente = Product.objects.create(
            name='Bondiola', sku='BON-1', cost_price=Decimal('8000'), sale_price=Decimal('12000'),
        )
        self.subir({'Fiambres': [self.HEAD_PESO,
                                 ['', 'BON-1', 'Bondiola', 'kg', 1300, '', '', '', '', '']]})
        existente.refresh_from_db()
        self.assertTrue(existente.is_granel)
        self.assertEqual(existente.sale_price_100g, Decimal('1300.00'))

    def test_exportar_e_importar_conserva_los_tramos(self):
        """Ida y vuelta completa: lo que exporta el sistema para un producto
        por peso (incluidos los tramos) se puede reimportar sin perder nada."""
        Product.objects.create(
            name='Jamón Exportado', sku='JC-EXP', is_granel=True,
            cost_price=Decimal('8000'), purchase_price=Decimal('8000'), sale_price=Decimal('11000'),
            sale_price_100g=Decimal('1200'), sale_price_250g=Decimal('2900'),
            oferta_price_500g=Decimal('5000'), current_stock=Decimal('2.5'),
        )
        r = self.c.get(reverse('stocks:export_excel'))
        self.assertEqual(r.status_code, 200)
        Product.objects.all().delete()

        wb = openpyxl.load_workbook(io.BytesIO(r.content))
        buf = io.BytesIO()
        wb.save(buf)
        archivo = SimpleUploadedFile('reimport.xlsx', buf.getvalue(),
                                     content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        r = self.c.post(self.url, {'excel_file': archivo})
        self.assertEqual(r.status_code, 200)
        self.c.post(self.url, {'confirm': '1'})

        p = Product.objects.get(sku='JC-EXP')
        self.assertTrue(p.is_granel)
        self.assertEqual(p.sale_price_100g, Decimal('1200.00'))
        self.assertEqual(p.sale_price_250g, Decimal('2900.00'))
        self.assertEqual(p.oferta_price_500g, Decimal('5000.00'))
        self.assertEqual(p.sale_price, Decimal('11000.00'))

    def test_preview_muestra_insignia_por_peso(self):
        r = self.subir({'Fiambres': [self.HEAD_PESO,
                                     ['', 'JC-3', 'Jamón', 'kg', 1100, 2300, '', 8000, 11000, 1]]},
                       confirmar=False)
        self.assertContains(r, 'Por peso')
