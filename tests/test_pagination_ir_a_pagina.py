from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.core.paginator import Paginator


class IrAPaginaTests(SimpleTestCase):
    def _render(self, query='?q=arroz&page=3'):
        request = RequestFactory().get('/stocks/products/' + query)
        page = Paginator(list(range(200)), 20).get_page(3)
        return render_to_string('includes/pagination.html', {'page_obj': page, 'request': request})

    def test_tiene_campo_para_elegir_pagina(self):
        html = self._render()
        self.assertIn('Ir a la página', html)
        self.assertIn('name="page"', html)
        self.assertIn('max="10"', html)

    def test_conserva_filtros_sin_duplicar_page(self):
        html = self._render()
        self.assertIn('<input type="hidden" name="q" value="arroz">', html)
        self.assertNotIn('<input type="hidden" name="page"', html)
