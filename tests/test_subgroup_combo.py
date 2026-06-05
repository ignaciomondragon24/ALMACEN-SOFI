"""
Tests para el tipo de promoción subgroup_combo.

Verifica:
- Detección correcta del combo en el POS
- Cálculo del descuento y distribución proporcional
- Múltiples sets
- Combos incompletos (sin descuento)
- Productos ajenos no afectados
- Precio combo mayor al original (sin descuento negativo)
- Promo pausada ignorada
- Retrocompatibilidad: nx_fixed_price no se rompe
"""
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'superrecord.settings')

import django
django.setup()

from django.test import TestCase
from decimal import Decimal

from promotions.models import Promotion, PromotionSubgroup
from promotions.engine import PromotionEngine
from stocks.models import Product


def _make_product(name, price):
    return Product.objects.create(
        name=name,
        sale_price=Decimal(str(price)),
        cost_price=Decimal('100'),
        is_active=True,
    )


def _cart(*items):
    """items: list of (product, quantity)"""
    return [
        {
            'item_id': i + 1,
            'product_id': prod.id,
            'quantity': qty,
            'unit_price': float(prod.sale_price),
            'packaging_type': 'unit',
        }
        for i, (prod, qty) in enumerate(items)
    ]


class SubgroupComboEngineTest(TestCase):

    def setUp(self):
        self.blanco = _make_product('Pan Nevares Blanco 550g', 2000)
        self.salvado = _make_product('Pan De Salvado Nevares 550g', 2200)
        self.hamburguesa = _make_product('Pan de Hamburguesa Nevares', 1800)
        self.pancho = _make_product('Pan de Pancho Nevares 210g', 1700)
        self.ajeno = _make_product('Producto Ajeno', 1000)

        self.promo = Promotion.objects.create(
            name='2 Lactal + 1 Hamb/Pancho x $5000',
            promo_type='subgroup_combo',
            status='active',
            final_price=Decimal('5000.00'),
            priority=50,
        )
        sg_a = PromotionSubgroup.objects.create(promotion=self.promo, slot='a', quantity_required=2)
        sg_a.products.set([self.blanco, self.salvado])

        sg_b = PromotionSubgroup.objects.create(promotion=self.promo, slot='b', quantity_required=1)
        sg_b.products.set([self.hamburguesa, self.pancho])

    # ── casos que SÍ aplican ──────────────────────────────────────────────────

    def test_2_blanco_1_hamburguesa(self):
        """Combo exacto: 2 blanco + 1 hamburguesa."""
        cart = _cart((self.blanco, 2), (self.hamburguesa, 1))
        r = PromotionEngine.calculate_cart(cart)
        self.assertEqual(len(r['applied_promotions']), 1)
        original = 2 * 2000 + 1800  # 5800
        self.assertAlmostEqual(r['discount_total'], original - 5000, places=2)
        self.assertAlmostEqual(r['final_total'], 5000.0, places=2)

    def test_2_blanco_1_pancho(self):
        """Combo con pancho en lugar de hamburguesa."""
        cart = _cart((self.blanco, 2), (self.pancho, 1))
        r = PromotionEngine.calculate_cart(cart)
        self.assertEqual(len(r['applied_promotions']), 1)
        original = 2 * 2000 + 1700  # 5700
        self.assertAlmostEqual(r['discount_total'], original - 5000, places=2)

    def test_1_blanco_1_salvado_1_hamburguesa(self):
        """Combo con mezcla de lactal: 1 blanco + 1 salvado + 1 hamburguesa."""
        cart = _cart((self.blanco, 1), (self.salvado, 1), (self.hamburguesa, 1))
        r = PromotionEngine.calculate_cart(cart)
        self.assertEqual(len(r['applied_promotions']), 1)
        original = 2000 + 2200 + 1800  # 6000
        self.assertAlmostEqual(r['discount_total'], original - 5000, places=2)

    def test_2_salvado_1_pancho(self):
        """Combo: 2 salvado + 1 pancho."""
        cart = _cart((self.salvado, 2), (self.pancho, 1))
        r = PromotionEngine.calculate_cart(cart)
        self.assertEqual(len(r['applied_promotions']), 1)
        original = 2 * 2200 + 1700  # 6100
        self.assertAlmostEqual(r['discount_total'], original - 5000, places=2)

    def test_dos_sets(self):
        """4 lactal + 2 hamburguesa → 2 sets."""
        cart = _cart((self.blanco, 2), (self.salvado, 2), (self.hamburguesa, 2))
        r = PromotionEngine.calculate_cart(cart)
        self.assertEqual(len(r['applied_promotions']), 1)
        original = 2 * 2000 + 2 * 2200 + 2 * 1800  # 12000
        self.assertAlmostEqual(r['discount_total'], original - 2 * 5000, places=2)  # 2000

    # ── casos que NO aplican ─────────────────────────────────────────────────

    def test_solo_1_lactal_no_aplica(self):
        """1 lactal + 1 hamburguesa → grupo A insuficiente."""
        cart = _cart((self.blanco, 1), (self.hamburguesa, 1))
        r = PromotionEngine.calculate_cart(cart)
        self.assertAlmostEqual(r['discount_total'], 0)

    def test_solo_2_lactal_sin_hamburguesa_no_aplica(self):
        """2 lactal sin hamburguesa → grupo B ausente."""
        cart = _cart((self.blanco, 2),)
        r = PromotionEngine.calculate_cart(cart)
        self.assertAlmostEqual(r['discount_total'], 0)

    def test_solo_hamburguesa_no_aplica(self):
        """Solo hamburguesa sin lactal."""
        cart = _cart((self.hamburguesa, 1),)
        r = PromotionEngine.calculate_cart(cart)
        self.assertAlmostEqual(r['discount_total'], 0)

    # ── productos ajenos no se afectan ──────────────────────────────────────

    def test_producto_ajeno_no_descontado(self):
        """Producto fuera de la promo no recibe descuento."""
        cart = _cart((self.blanco, 2), (self.hamburguesa, 1), (self.ajeno, 3))
        r = PromotionEngine.calculate_cart(cart)
        # Descuento solo sobre los 3 productos del combo
        combo_original = 2 * 2000 + 1800  # 5800
        self.assertAlmostEqual(r['discount_total'], combo_original - 5000, places=2)
        # Total final = combo_promo + ajeno
        self.assertAlmostEqual(r['final_total'], 5000 + 3 * 1000, places=2)

    # ── sin descuento negativo ────────────────────────────────────────────────

    def test_sin_descuento_cuando_combo_mas_barato_que_precio_fijo(self):
        """Si los productos suman menos que el precio combo, no hay descuento."""
        barato_a = _make_product('Pan Barato A', 1000)
        barato_b = _make_product('Pan Barato B', 500)
        promo2 = Promotion.objects.create(
            name='Promo cara', promo_type='subgroup_combo', status='active',
            final_price=Decimal('5000.00'),
        )
        sg2a = PromotionSubgroup.objects.create(promotion=promo2, slot='a', quantity_required=2)
        sg2a.products.set([barato_a])
        sg2b = PromotionSubgroup.objects.create(promotion=promo2, slot='b', quantity_required=1)
        sg2b.products.set([barato_b])

        cart = _cart((barato_a, 2), (barato_b, 1))  # original = 2500 < 5000
        r = PromotionEngine.calculate_cart(cart)
        self.assertAlmostEqual(r['discount_total'], 0)
        self.assertGreater(r['final_total'], 0)

    # ── promo pausada ─────────────────────────────────────────────────────────

    def test_promo_pausada_no_aplica(self):
        """Promo pausada no genera descuento."""
        self.promo.status = 'paused'
        self.promo.save()
        cart = _cart((self.blanco, 2), (self.hamburguesa, 1))
        r = PromotionEngine.calculate_cart(cart)
        self.assertAlmostEqual(r['discount_total'], 0)
        # Restore
        self.promo.status = 'active'
        self.promo.save()

    # ── retrocompatibilidad ──────────────────────────────────────────────────

    def test_nx_fixed_price_no_se_rompe(self):
        """El tipo nx_fixed_price existente sigue funcionando."""
        gaseosa = _make_product('Gaseosa', 500)
        promo_gas = Promotion.objects.create(
            name='2 Gaseosas $800',
            promo_type='nx_fixed_price',
            status='active',
            quantity_required=2,
            final_price=Decimal('800.00'),
        )
        promo_gas.products.add(gaseosa)

        cart = [{'item_id': 99, 'product_id': gaseosa.id, 'quantity': 2,
                 'unit_price': 500, 'packaging_type': 'unit'}]
        r = PromotionEngine.calculate_cart(cart)
        self.assertAlmostEqual(r['discount_total'], 200.0, places=2)  # 2*500 - 800 = 200

    def test_subgroup_no_interfiere_con_nx_fixed_en_mismo_carrito(self):
        """subgroup_combo y nx_fixed_price en el mismo carrito se aplican independientemente."""
        gaseosa = _make_product('Gaseosa', 500)
        promo_gas = Promotion.objects.create(
            name='2 Gaseosas $800',
            promo_type='nx_fixed_price',
            status='active',
            quantity_required=2,
            final_price=Decimal('800.00'),
        )
        promo_gas.products.add(gaseosa)

        cart = _cart((self.blanco, 2), (self.hamburguesa, 1), (gaseosa, 2))
        r = PromotionEngine.calculate_cart(cart)
        self.assertEqual(len(r['applied_promotions']), 2)
        pan_original = 2 * 2000 + 1800  # 5800
        gas_original = 2 * 500  # 1000
        expected_discount = (pan_original - 5000) + (gas_original - 800)
        self.assertAlmostEqual(r['discount_total'], expected_discount, places=2)

    # ── distribución del descuento ────────────────────────────────────────────

    def test_item_discounts_suman_al_total(self):
        """La suma de item_discounts debe igualar el discount_amount total."""
        cart = _cart((self.blanco, 2), (self.hamburguesa, 1))
        r = PromotionEngine.calculate_cart(cart)
        promo_result = r['applied_promotions'][0]
        sum_items = sum(d['discount'] for d in promo_result['item_discounts'])
        self.assertAlmostEqual(sum_items, promo_result['discount_amount'], places=5)


if __name__ == '__main__':
    import unittest
    unittest.main()
