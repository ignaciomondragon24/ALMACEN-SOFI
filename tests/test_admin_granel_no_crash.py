"""
Fase 3 del rediseño de venta por peso — Migración B (2026-09-26).

Django admin es la ÚNICA vía que sigue viva hacia los modelos de `granel`
después de sacar `path('granel/', include('granel.urls'))` del urlconf
principal (`/admin/` se registra aparte, en `django.contrib.admin.site.urls`,
y no depende de esa inclusión). `CarameleraAdmin` usa
`filter_horizontal` sobre `productos_autorizados`, que antes tenía
`limit_choices_to={'es_deposito_caramelera': True}` — un campo que ya no
existe en `Product`. Este test confirma que esas pantallas siguen abriendo
sin explotar.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from granel.models import Caramelera

User = get_user_model()


class AdminGranelNoCrashTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            username='admin_granel_check', password='x', is_superuser=True, is_staff=True,
        )
        cls.caramelera = Caramelera.objects.create(
            nombre='Jamón Test Admin', precio_100g=Decimal('1200.00'),
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_caramelera_changelist_abre(self):
        r = self.client.get('/admin/granel/caramelera/')
        self.assertEqual(r.status_code, 200)

    def test_caramelera_add_abre(self):
        r = self.client.get('/admin/granel/caramelera/add/')
        self.assertEqual(r.status_code, 200)

    def test_caramelera_change_abre(self):
        r = self.client.get(f'/admin/granel/caramelera/{self.caramelera.pk}/change/')
        self.assertEqual(r.status_code, 200)

    def test_caramelera_se_guarda_desde_el_admin(self):
        r = self.client.post(f'/admin/granel/caramelera/{self.caramelera.pk}/change/', {
            'nombre': 'Jamón Test Admin Editado',
            'precio_100g': '1300.00',
            'precio_cuarto': '0',
            'stock_gramos_actual': '0',
            'costo_ponderado_gramo': '0',
            'is_active': 'on',
            'productos_autorizados': [],
            '_save': 'Save',
        })
        self.assertEqual(r.status_code, 302, r.content[:500])
        self.caramelera.refresh_from_db()
        self.assertEqual(self.caramelera.nombre, 'Jamón Test Admin Editado')
