"""
Fase 1 del rediseño de venta por peso: `Product.price_for_grams(gramos)`.

Generaliza la regla de tres que ya usaba `Caramelera.calcular_precio` (un solo
tramo a los 250g) a dos tramos independientes (250g y 500g), cada uno con su
propio precio normal y su propio precio de oferta opcional (en pesos, no %).
Estos tests no conectan nada todavía (Fase 1 es aditiva) — solo prueban el
método nuevo en aislamiento, incluida la equivalencia matemática con la
regla vieja para el caso de un solo tramo (la que se usa en la migración de
datos de la Fase 3).
"""
from decimal import Decimal

from django.test import TestCase

from granel.models import Caramelera
from stocks.models import Product


class PriceForGramsTests(TestCase):
    def _producto(self, **kwargs):
        base = dict(name='Jamón', sku='JAM-PFG', sale_price=Decimal('12000'))
        base.update(kwargs)
        return Product(**base)

    def test_sin_tramos_cargados_es_proporcional_al_kilo(self):
        p = self._producto()
        self.assertEqual(p.price_for_grams(100), Decimal('1200'))
        self.assertEqual(p.price_for_grams(250), Decimal('3000'))
        self.assertEqual(p.price_for_grams(333), Decimal('3996.00'))
        self.assertEqual(p.price_for_grams(1000), Decimal('12000'))

    def test_tramo_250_cargado_se_usa_desde_250g(self):
        p = self._producto(sale_price_250g=Decimal('2900'))  # más barato que el proporcional ($3000)
        self.assertEqual(p.price_for_grams(100), Decimal('1200'))   # <250g: sigue el precio por kilo
        self.assertEqual(p.price_for_grams(250), Decimal('2900'))
        self.assertEqual(p.price_for_grams(500), Decimal('5800'))   # 2x el tramo de 250g

    def test_tramo_500_cargado_pisa_al_de_250_desde_500g(self):
        p = self._producto(sale_price_250g=Decimal('2900'), sale_price_500g=Decimal('5500'))
        self.assertEqual(p.price_for_grams(250), Decimal('2900'))
        self.assertEqual(p.price_for_grams(499), Decimal('5788.400'))  # todavía tramo 250
        self.assertEqual(p.price_for_grams(500), Decimal('5500'))     # tramo 500 entra justo acá
        self.assertEqual(p.price_for_grams(750), Decimal('8250.00'))  # 1.5x el tramo de 500g

    def test_oferta_reemplaza_al_precio_normal_del_tramo(self):
        p = self._producto(sale_price_250g=Decimal('3000'), oferta_price_250g=Decimal('2500'))
        self.assertEqual(p.price_for_grams(250), Decimal('2500'))
        self.assertEqual(p.price_for_grams(500), Decimal('5000'))

    def test_oferta_en_cero_significa_sin_oferta(self):
        p = self._producto(sale_price_250g=Decimal('3000'), oferta_price_250g=Decimal('0'))
        self.assertEqual(p.price_for_grams(250), Decimal('3000'))

    def test_oferta_de_500_no_afecta_al_tramo_250(self):
        p = self._producto(sale_price_250g=Decimal('3000'), sale_price_500g=Decimal('5800'),
                           oferta_price_500g=Decimal('5000'))
        self.assertEqual(p.price_for_grams(250), Decimal('3000'))   # sin oferta en este tramo
        self.assertEqual(p.price_for_grams(500), Decimal('5000'))   # con oferta

    def test_equivalencia_matematica_con_la_regla_vieja_de_caramelera(self):
        """Sirve para validar la fórmula de migración de la Fase 3:
        oferta_price_250g = precio_cuarto / 4 da el mismo precio que la
        Caramelera vieja, para cualquier peso >= 250g (mismo tramo único)."""
        precio_100g = Decimal('1200')
        precio_cuarto = Decimal('11000')  # "kilo oferta" viejo
        vieja = Caramelera(nombre='x', precio_100g=precio_100g, precio_cuarto=precio_cuarto)

        nuevo = self._producto(
            sale_price=precio_100g * 10,
            oferta_price_250g=(precio_cuarto / Decimal('4')).quantize(Decimal('0.01')),
        )
        for gramos in (250, 300, 500, 750, 1000, 1500):
            self.assertEqual(nuevo.price_for_grams(gramos), vieja.calcular_precio(gramos),
                            f'diverge en {gramos}g')

    def test_equivalencia_sin_ningun_tramo_cargado(self):
        """Sin oferta ni tramos cargados, coincide con la regla vieja sin precio_cuarto."""
        precio_100g = Decimal('950')
        vieja = Caramelera(nombre='x', precio_100g=precio_100g, precio_cuarto=Decimal('0'))
        nuevo = self._producto(sale_price=precio_100g * 10)
        for gramos in (50, 100, 150, 250, 500, 999):
            self.assertEqual(nuevo.price_for_grams(gramos), vieja.calcular_precio(gramos),
                            f'diverge en {gramos}g')
