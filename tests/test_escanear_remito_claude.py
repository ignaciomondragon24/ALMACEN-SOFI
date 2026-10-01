"""
Escanear Remito: migración de Gemini a Claude (1/10/2026, pedido de Nacho).

Cada negocio usa su PROPIA API key de Anthropic (console.anthropic.com,
facturación aparte de una suscripción de Claude.ai) — campo separado del de
Gemini en `AssistantSettings`, que sigue usándose solo para el chat del
asistente (sin tocar).

Estos tests mockean el cliente de Anthropic (nunca pegan a la red real) y
cubren: construcción correcta del pedido, parseo de la respuesta, y cada
rama de manejo de errores.
"""
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import httpx2
import anthropic
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from assistant.models import AssistantSettings
from assistant.services import InvoiceScanService

User = get_user_model()


def _fake_response(status_code):
    req = httpx2.Request('POST', 'https://api.anthropic.com/v1/messages')
    return httpx2.Response(status_code, request=req)


def _text_block(text):
    block = MagicMock()
    block.type = 'text'
    block.text = text
    return block


class ScanInvoiceConClaudeTests(TestCase):
    def setUp(self):
        self.settings_obj = AssistantSettings.get_settings()
        self.settings_obj.anthropic_api_key = 'sk-ant-test-key'
        self.settings_obj.anthropic_model = 'claude-sonnet-5'
        self.settings_obj.save()
        self.service = InvoiceScanService()

    def test_sin_api_key_da_error_claro(self):
        self.settings_obj.anthropic_api_key = ''
        self.settings_obj.save()
        result = self.service.scan_invoice(b'fake-image-bytes', 'image/jpeg')
        self.assertFalse(result['success'])
        self.assertIn('Claude', result['error'])

    @patch('anthropic.Anthropic')
    def test_escaneo_exitoso_parsea_json_y_usa_el_modelo_configurado(self, MockAnthropic):
        payload = {
            'proveedor': 'Fiambres del Sur', 'numero_comprobante': '0001-0001234',
            'fecha': '30/09/2026',
            'productos': [{'nombre': 'Jamón Cocido', 'cantidad': 5, 'tipo_cantidad': 'unidad',
                           'precio_unitario': 8800.0, 'precio_total': 44000.0, 'codigo_barras': None}],
            'subtotal': 44000.0, 'iva': 0, 'total': 44000.0, 'metodo_pago': 'efectivo', 'notas': '',
        }
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(content=[_text_block(json.dumps(payload))])
        MockAnthropic.return_value = mock_client

        result = self.service.scan_invoice(b'fake-image-bytes', 'image/jpeg')

        self.assertTrue(result['success'], result)
        self.assertEqual(result['data']['proveedor'], 'Fiambres del Sur')
        self.assertEqual(result['data']['productos'][0]['nombre'], 'Jamón Cocido')

        # Se usó el modelo configurado en AssistantSettings, no uno hardcodeado.
        _, kwargs = mock_client.messages.create.call_args
        self.assertEqual(kwargs['model'], 'claude-sonnet-5')
        # La imagen viaja como bloque 'image' en base64, con el mime type correcto.
        content_blocks = kwargs['messages'][0]['content']
        image_block = next(b for b in content_blocks if b['type'] == 'image')
        self.assertEqual(image_block['source']['media_type'], 'image/jpeg')

    @patch('anthropic.Anthropic')
    def test_respeta_el_modelo_haiku_si_esta_configurado(self, MockAnthropic):
        self.settings_obj.anthropic_model = 'claude-haiku-4-5-20251001'
        self.settings_obj.save()
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[_text_block('{"productos": [], "proveedor": null}')]
        )
        MockAnthropic.return_value = mock_client

        self.service.scan_invoice(b'fake-image-bytes', 'image/jpeg')

        _, kwargs = mock_client.messages.create.call_args
        self.assertEqual(kwargs['model'], 'claude-haiku-4-5-20251001')

    @patch('anthropic.Anthropic')
    def test_respuesta_con_markdown_code_fence_se_limpia_igual(self, MockAnthropic):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[_text_block('```json\n{"productos": [], "proveedor": "X"}\n```')]
        )
        MockAnthropic.return_value = mock_client

        result = self.service.scan_invoice(b'fake-image-bytes', 'image/jpeg')
        self.assertTrue(result['success'], result)
        self.assertEqual(result['data']['proveedor'], 'X')

    @patch('anthropic.Anthropic')
    def test_json_invalido_da_error_amigable(self, MockAnthropic):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(content=[_text_block('esto no es json')])
        MockAnthropic.return_value = mock_client

        result = self.service.scan_invoice(b'fake-image-bytes', 'image/jpeg')
        self.assertFalse(result['success'])
        self.assertIn('foto más clara', result['error'])

    @patch('anthropic.Anthropic')
    def test_api_key_invalida(self, MockAnthropic):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.AuthenticationError(
            'invalid x-api-key', response=_fake_response(401), body=None)
        MockAnthropic.return_value = mock_client

        result = self.service.scan_invoice(b'fake-image-bytes', 'image/jpeg')
        self.assertFalse(result['success'])
        self.assertIn('API key', result['error'])

    @patch('anthropic.Anthropic')
    def test_rate_limit(self, MockAnthropic):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.RateLimitError(
            'rate limited', response=_fake_response(429), body=None)
        MockAnthropic.return_value = mock_client

        result = self.service.scan_invoice(b'fake-image-bytes', 'image/jpeg')
        self.assertFalse(result['success'])
        self.assertIn('límite', result['error'])

    @patch('anthropic.Anthropic')
    def test_imagen_demasiado_grande(self, MockAnthropic):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = anthropic.BadRequestError(
            'image exceeds max size', response=_fake_response(400), body=None)
        MockAnthropic.return_value = mock_client

        result = self.service.scan_invoice(b'fake-image-bytes', 'image/jpeg')
        self.assertFalse(result['success'])
        self.assertIn('grande', result['error'])

    @patch('anthropic.Anthropic')
    def test_error_de_conexion(self, MockAnthropic):
        mock_client = MagicMock()
        req = httpx2.Request('POST', 'https://api.anthropic.com/v1/messages')
        mock_client.messages.create.side_effect = anthropic.APIConnectionError(request=req)
        MockAnthropic.return_value = mock_client

        result = self.service.scan_invoice(b'fake-image-bytes', 'image/jpeg')
        self.assertFalse(result['success'])
        self.assertIn('conectar', result['error'])


class ConfiguracionEnPantallaTests(TestCase):
    """La pantalla de 'Asistente IA → Configuración' ahora tiene los dos
    proveedores (Gemini para el chat, Claude para Escanear Remito) como
    campos independientes — ninguno bloquea al otro."""

    @classmethod
    def setUpTestData(cls):
        g, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user('ia_admin', password='x', is_superuser=True, is_staff=True)
        cls.user.groups.add(g)

    def setUp(self):
        self.c = Client()
        self.c.force_login(self.user)

    def test_guardar_solo_la_key_de_claude_sin_gemini_no_rompe(self):
        r = self.c.post(reverse('assistant:settings'), {
            'openai_api_key': '', 'model': 'gemini-2.5-flash',
            'anthropic_api_key': 'sk-ant-nueva', 'anthropic_model': 'claude-sonnet-5',
            'max_tokens': '2000', 'temperature': '0.7',
        })
        self.assertEqual(r.status_code, 302)
        settings_obj = AssistantSettings.get_settings()
        self.assertEqual(settings_obj.anthropic_api_key, 'sk-ant-nueva')
        self.assertEqual(settings_obj.openai_api_key, '')

    def test_pantalla_de_escanear_remito_avisa_si_falta_la_key(self):
        r = self.c.get(reverse('assistant:scan_invoice'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Falta configurar la API Key de Claude')

    def test_pantalla_de_escanear_remito_no_avisa_si_ya_esta_configurada(self):
        settings_obj = AssistantSettings.get_settings()
        settings_obj.anthropic_api_key = 'sk-ant-ya-configurada'
        settings_obj.save()
        r = self.c.get(reverse('assistant:scan_invoice'))
        self.assertNotContains(r, 'Falta configurar la API Key de Claude')
