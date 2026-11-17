import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from assistant.models import AssistantSettings
from assistant.services import (
    InvoiceScanService, SCAN_SIN_PRODUCTOS, _fecha_remito, _numero_remito, normalizar_datos_remito,
)


class NumeroRemitoTests(SimpleTestCase):
    def test_numeros_ya_numericos_quedan_igual(self):
        self.assertEqual(_numero_remito(12), 12)
        self.assertEqual(_numero_remito(1250.5), 1250.5)

    def test_texto_formato_argentino(self):
        self.assertEqual(_numero_remito('1.250,50'), 1250.5)
        self.assertEqual(_numero_remito('$ 180.749,75'), 180749.75)
        self.assertEqual(_numero_remito('1250,5'), 1250.5)

    def test_texto_formato_ingles_y_miles(self):
        self.assertEqual(_numero_remito('1,250.50'), 1250.5)
        self.assertEqual(_numero_remito('1250.5'), 1250.5)
        self.assertEqual(_numero_remito('1.250'), 1250)
        self.assertEqual(_numero_remito('1.250.500'), 1250500)

    def test_con_unidades_y_vacios(self):
        self.assertEqual(_numero_remito('12 unidades'), 12)
        self.assertIsNone(_numero_remito(None))
        self.assertIsNone(_numero_remito(''))
        self.assertIsNone(_numero_remito('s/d'))
        self.assertIsNone(_numero_remito(True))


class FechaRemitoTests(SimpleTestCase):
    def test_formatos_comunes_a_dd_mm_yyyy(self):
        for entrada in ('12/11/2026', '12-11-2026', '2026-11-12', '2026-11-12T10:00:00', '12/11/26', '12.11.2026'):
            self.assertEqual(_fecha_remito(entrada), '12/11/2026', entrada)

    def test_no_entendible_da_none(self):
        self.assertIsNone(_fecha_remito('ayer'))
        self.assertIsNone(_fecha_remito(None))
        self.assertIsNone(_fecha_remito('31/02/2026'))


class NormalizarDatosRemitoTests(SimpleTestCase):
    def test_tipos_correctos_aunque_el_modelo_mande_texto(self):
        data = normalizar_datos_remito({
            'proveedor': '  La Espiga  ',
            'fecha': '2026-11-12',
            'total': '$ 1.500,00',
            'iva': None,
            'productos': [
                {'nombre': 'Fideos', 'cantidad': '12', 'precio_unitario': '1.250,50',
                 'precio_total': '15.006,00', 'codigo_barras': 7790895000126.0},
                'basura',
                {'nombre': '', 'cantidad': 1},
                {'nombre': 'Aceite', 'cantidad': 6, 'codigo_barras': 'EAN 7790895000127'},
            ],
        })
        self.assertEqual(data['proveedor'], 'La Espiga')
        self.assertEqual(data['fecha'], '12/11/2026')
        self.assertEqual(data['total'], 1500)
        self.assertIsNone(data['iva'])
        self.assertEqual(len(data['productos']), 2)
        fideos, aceite = data['productos']
        self.assertEqual((fideos['cantidad'], fideos['precio_unitario'], fideos['precio_total']), (12, 1250.5, 15006))
        self.assertEqual(fideos['codigo_barras'], '7790895000126')
        self.assertEqual(aceite['codigo_barras'], '7790895000127')
        self.assertIsNone(aceite['precio_unitario'])

    def test_estructuras_raras_no_rompen(self):
        for raro in (None, [], 'texto', {'productos': None}, {'productos': 'x'}):
            self.assertEqual(normalizar_datos_remito(raro)['productos'], [])


class ScanDevuelveDatosNormalizadosTests(TestCase):
    def setUp(self):
        s = AssistantSettings.get_settings()
        s.anthropic_api_key = ''
        s.openai_api_key = 'AQ.clave-de-google'
        s.save()

    @patch('google.genai.Client')
    def test_numeros_como_texto_llegan_como_numeros(self, MockGenai):
        payload = {'proveedor': 'X', 'fecha': '2026-11-12', 'total': '3.000,00',
                   'productos': [{'nombre': 'Jamón', 'cantidad': '2', 'precio_unitario': '1.500,00',
                                  'precio_total': '3.000,00'}]}
        MockGenai.return_value.models.generate_content.return_value = MagicMock(text=json.dumps(payload))
        r = InvoiceScanService().scan_invoice(b'x', 'image/jpeg')
        self.assertTrue(r['success'], r)
        p = r['data']['productos'][0]
        self.assertEqual((p['cantidad'], p['precio_unitario'], p['precio_total']), (2, 1500, 3000))
        self.assertEqual(r['data']['fecha'], '12/11/2026')

    @patch('google.genai.Client')
    def test_sin_productos_da_error_claro(self, MockGenai):
        MockGenai.return_value.models.generate_content.return_value = MagicMock(
            text=json.dumps({'proveedor': 'X', 'productos': []}))
        r = InvoiceScanService().scan_invoice(b'x', 'image/jpeg')
        self.assertFalse(r['success'])
        self.assertEqual(r['error'], SCAN_SIN_PRODUCTOS)
