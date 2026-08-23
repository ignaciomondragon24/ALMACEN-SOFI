"""Auditoría de purchase_receive con packagings.

Verifica que al recibir una OC con items que usan packaging (display/bulk),
toda la información queda correctamente registrada y nada se sobreescribe
como pasó con el bug del precio unitario:

- StockBatch: cantidad y costo siempre en unidades base (FIFO real).
- product.cost_price: promedio ponderado correcto (no sobreescribe).
- product.current_stock: suma la cantidad en unidades base.
- product.sale_price: solo cambia si el item es sin packaging o es
  packaging unit. NUNCA cuando el packaging es display/bulk.
- packaging.sale_price: solo se actualiza el nivel comprado.
- packaging.current_stock: cascada coherente con Product.
- StockMovement: registra el ingreso en unidades base.
"""
from decimal import Decimal

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from stocks.models import (
    Product, ProductCategory, ProductPackaging, StockBatch, StockMovement,
)
from purchase.models import Supplier, Purchase, PurchaseItem

User = get_user_model()


class PurchaseReceiveAuditWithPackagingTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.admin = User.objects.create_user(
            username='audit_purch', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.admin.groups.add(cls.admin_group)
        cls.category = ProductCategory.objects.create(name='Audit Cat')
        cls.supplier = Supplier.objects.create(name='Proveedor Audit')

    def setUp(self):
        self.client = Client()
        self.client.login(username='audit_purch', password='pass123')

    def _make_product_with_pkgs(self, initial_stock='0', initial_cost='40',
                                initial_sale='100'):
        product = Product.objects.create(
            name='Gomitas Audit', sku='AUD-001',
            category=self.category,
            current_stock=Decimal(initial_stock),
            cost_price=Decimal(initial_cost),
            purchase_price=Decimal(initial_cost),
            sale_price=Decimal(initial_sale),
        )
        unit = ProductPackaging.objects.create(
            product=product, packaging_type='unit', name='Unidad',
            units_per_display=1, displays_per_bulk=1,
            purchase_price=Decimal(initial_cost),
            sale_price=Decimal(initial_sale),
            current_stock=Decimal(initial_stock),
        )
        display = ProductPackaging.objects.create(
            product=product, packaging_type='display', name='Display x 6',
            units_per_display=6, displays_per_bulk=1,
            purchase_price=Decimal('240'),
            sale_price=Decimal('500'),
            current_stock=Decimal('0'),
        )
        bulk = ProductPackaging.objects.create(
            product=product, packaging_type='bulk', name='Bulto x 24',
            units_per_display=6, displays_per_bulk=4,
            purchase_price=Decimal('960'),
            sale_price=Decimal('2000'),
            current_stock=Decimal('0'),
        )
        return product, unit, display, bulk

    def _create_oc(self, items):
        """items = lista de dicts con product, packaging, quantity, unit_cost, sale_price."""
        purchase = Purchase.objects.create(
            supplier=self.supplier, order_number='OC-AUDIT-001',
            status='draft', created_by=self.admin,
        )
        for it in items:
            PurchaseItem.objects.create(
                purchase=purchase,
                product=it['product'],
                packaging=it.get('packaging'),
                quantity=it['quantity'],
                unit_cost=it['unit_cost'],
                sale_price=it.get('sale_price'),
            )
        return purchase

    def _receive(self, purchase, data=None):
        return self.client.post(
            reverse('purchase:purchase_receive', args=[purchase.pk]),
            data=data or {},
        )

    # ---------- DISPLAY ----------

    def test_recibir_display_actualiza_todo_correctamente(self):
        """Recibiendo 10 displays de 6u a $300/display con sale_price=$600:
        - Stock base: +60 u.
        - cost_price: $300/6 = $50 (promedio con stock previo 0).
        - product.sale_price: NO CAMBIA (sigue en $100).
        - unit_pkg.sale_price: NO CAMBIA ($100).
        - display_pkg.sale_price: pasa a $600.
        - StockBatch: quantity_purchased=60, purchase_price=$50.
        - StockMovement: qty=60, unit_cost=$50.
        """
        product, unit, display, bulk = self._make_product_with_pkgs()
        purchase = self._create_oc([{
            'product': product, 'packaging': display,
            'quantity': 10, 'unit_cost': Decimal('300'),
            'sale_price': Decimal('600'),
        }])

        self._receive(purchase)
        product.refresh_from_db()
        unit.refresh_from_db()
        display.refresh_from_db()
        bulk.refresh_from_db()

        # Stock y costo
        self.assertEqual(product.current_stock, Decimal('60'))
        self.assertEqual(product.cost_price, Decimal('50'))

        # Precios de venta: solo cambió el display
        self.assertEqual(product.sale_price, Decimal('100'))
        self.assertEqual(unit.sale_price, Decimal('100'))
        self.assertEqual(display.sale_price, Decimal('600'))
        self.assertEqual(bulk.sale_price, Decimal('2000'))  # intacto

        # Cascada de stock
        self.assertEqual(unit.current_stock, Decimal('60'))
        self.assertEqual(display.current_stock, Decimal('10'))
        self.assertEqual(bulk.current_stock, Decimal('2.5'))  # 60/24

        # Batch
        batch = StockBatch.objects.get(product=product, purchase=purchase)
        self.assertEqual(batch.quantity_purchased, Decimal('60'))
        self.assertEqual(batch.quantity_remaining, Decimal('60'))
        self.assertEqual(batch.purchase_price, Decimal('50'))
        self.assertEqual(batch.supplier_name, self.supplier.name)

        # Movimiento de stock
        mov = StockMovement.objects.filter(
            product=product, movement_type='purchase'
        ).first()
        self.assertEqual(mov.quantity, Decimal('60'))
        self.assertEqual(mov.unit_cost, Decimal('50'))

    # ---------- VENCIMIENTO (opcional) ----------

    def test_recibir_sin_vencimiento_no_rompe_nada(self):
        """Si no se carga fecha de vencimiento, el batch se crea igual con expiration_date=None."""
        product, unit, display, bulk = self._make_product_with_pkgs()
        purchase = self._create_oc([{
            'product': product, 'packaging': display,
            'quantity': 5, 'unit_cost': Decimal('300'),
        }])
        self._receive(purchase)
        batch = StockBatch.objects.get(product=product, purchase=purchase)
        self.assertIsNone(batch.expiration_date)

    def test_recibir_con_vencimiento_lo_guarda_en_el_batch(self):
        """La fecha de vencimiento cargada en el form de recepción queda en el StockBatch."""
        product, unit, display, bulk = self._make_product_with_pkgs()
        purchase = self._create_oc([{
            'product': product, 'packaging': display,
            'quantity': 5, 'unit_cost': Decimal('300'),
        }])
        item = purchase.items.first()
        self._receive(purchase, data={f'expiration_date_{item.id}': '2026-12-31'})
        batch = StockBatch.objects.get(product=product, purchase=purchase)
        self.assertEqual(str(batch.expiration_date), '2026-12-31')

    # ---------- BULK ----------

    def test_recibir_bulto_actualiza_todo_correctamente(self):
        """Recibiendo 2 bultos (24u cada) a $1200/bulto con sale_price=$2500:
        - Stock base: +48.
        - cost_price: $1200/24 = $50.
        - product/unit/display sale_price: intactos.
        - bulk.sale_price: pasa a $2500.
        """
        product, unit, display, bulk = self._make_product_with_pkgs()
        purchase = self._create_oc([{
            'product': product, 'packaging': bulk,
            'quantity': 2, 'unit_cost': Decimal('1200'),
            'sale_price': Decimal('2500'),
        }])

        self._receive(purchase)
        product.refresh_from_db()
        unit.refresh_from_db()
        display.refresh_from_db()
        bulk.refresh_from_db()

        self.assertEqual(product.current_stock, Decimal('48'))
        self.assertEqual(product.cost_price, Decimal('50'))

        # Solo el bulto se modificó
        self.assertEqual(product.sale_price, Decimal('100'))
        self.assertEqual(unit.sale_price, Decimal('100'))
        self.assertEqual(display.sale_price, Decimal('500'))
        self.assertEqual(bulk.sale_price, Decimal('2500'))

        # Cascada
        self.assertEqual(unit.current_stock, Decimal('48'))
        self.assertEqual(display.current_stock, Decimal('8'))   # 48/6
        self.assertEqual(bulk.current_stock, Decimal('2'))

        batch = StockBatch.objects.get(product=product, purchase=purchase)
        self.assertEqual(batch.quantity_purchased, Decimal('48'))
        self.assertEqual(batch.purchase_price, Decimal('50'))

    # ---------- PROMEDIO PONDERADO CON STOCK PREVIO ----------

    def test_promedio_ponderado_con_stock_previo_y_packaging(self):
        """Stock previo a $40 + compra de displays a $50 unitario base.
        cost_price final debe ser el promedio ponderado, no sobreescribir."""
        product, unit, display, bulk = self._make_product_with_pkgs(
            initial_stock='30', initial_cost='40'
        )
        # Ajustar stocks de packagings al inicial
        unit.current_stock = Decimal('30')
        unit.save(update_fields=['current_stock'])
        display.current_stock = Decimal('5')
        display.save(update_fields=['current_stock'])

        # OC: 10 displays a $300/display → base_qty=60, unit_cost_base=$50
        purchase = self._create_oc([{
            'product': product, 'packaging': display,
            'quantity': 10, 'unit_cost': Decimal('300'),
        }])
        self._receive(purchase)

        product.refresh_from_db()
        # Promedio: (40*30 + 50*60) / 90 = (1200+3000)/90 = 4200/90 ≈ 46.67
        expected = (Decimal('40') * 30 + Decimal('50') * 60) / 90
        self.assertAlmostEqual(
            float(product.cost_price), float(expected), places=2,
            msg='cost_price debe ser promedio ponderado, no sobreescribir',
        )
        self.assertEqual(product.current_stock, Decimal('90'))

    # ---------- FIFO CON MÚLTIPLES RECEPCIONES ----------

    def test_multiples_recepciones_generan_batches_fifo_con_precios_propios(self):
        """Dos OCs sucesivas crean dos StockBatch independientes, cada uno
        con su purchase_price — requerido para FIFO correcto."""
        product, unit, display, bulk = self._make_product_with_pkgs()

        oc1 = self._create_oc([{
            'product': product, 'packaging': display,
            'quantity': 5, 'unit_cost': Decimal('240'),  # base $40
        }])
        self._receive(oc1)

        oc2 = Purchase.objects.create(
            supplier=self.supplier, order_number='OC-AUDIT-002',
            status='draft', created_by=self.admin,
        )
        PurchaseItem.objects.create(
            purchase=oc2, product=product, packaging=display,
            quantity=5, unit_cost=Decimal('360'),  # base $60
        )
        self.client.post(reverse('purchase:purchase_receive', args=[oc2.pk]))

        batches = StockBatch.objects.filter(product=product).order_by('purchased_at')
        self.assertEqual(batches.count(), 2)
        self.assertEqual(batches[0].purchase_price, Decimal('40'))
        self.assertEqual(batches[0].quantity_purchased, Decimal('30'))
        self.assertEqual(batches[1].purchase_price, Decimal('60'))
        self.assertEqual(batches[1].quantity_purchased, Decimal('30'))

    # ---------- RECEPCIÓN SIN PACKAGING ----------

    def test_recibir_sin_packaging_es_unidades_base(self):
        """Retrocompatibilidad: item sin packaging se trata como unidades base."""
        product = Product.objects.create(
            name='Simple', sku='SIMP-001', category=self.category,
            current_stock=Decimal('0'), cost_price=Decimal('0'),
            purchase_price=Decimal('0'), sale_price=Decimal('100'),
        )
        purchase = self._create_oc([{
            'product': product, 'packaging': None,
            'quantity': 20, 'unit_cost': Decimal('55'),
            'sale_price': Decimal('110'),
        }])
        self._receive(purchase)

        product.refresh_from_db()
        self.assertEqual(product.current_stock, Decimal('20'))
        self.assertEqual(product.cost_price, Decimal('55'))
        self.assertEqual(product.sale_price, Decimal('110'))

        batch = StockBatch.objects.get(product=product, purchase=purchase)
        self.assertEqual(batch.quantity_purchased, Decimal('20'))
        self.assertEqual(batch.purchase_price, Decimal('55'))

    # ---------- MIXTO: DISPLAY + SIN PACKAGING EN LA MISMA OC ----------

    def test_oc_mixta_con_display_y_unidades_sueltas_registra_dos_batches(self):
        """Una OC puede tener un item por display y otro por unidad suelta.
        Cada uno debe generar su StockBatch con la conversión correcta."""
        product, unit, display, bulk = self._make_product_with_pkgs()

        purchase = Purchase.objects.create(
            supplier=self.supplier, order_number='OC-AUDIT-MIX',
            status='draft', created_by=self.admin,
        )
        PurchaseItem.objects.create(
            purchase=purchase, product=product, packaging=display,
            quantity=5, unit_cost=Decimal('300'),  # base $50
        )
        # Segundo item: unidades sueltas a costo distinto (el mismo producto)
        PurchaseItem.objects.create(
            purchase=purchase, product=product, packaging=unit,
            quantity=10, unit_cost=Decimal('45'),
        )
        self._receive(purchase)

        product.refresh_from_db()
        # Stock total: 5*6 + 10 = 40
        self.assertEqual(product.current_stock, Decimal('40'))

        # Dos batches, cada uno con su cantidad y costo
        batches = StockBatch.objects.filter(product=product).order_by('id')
        self.assertEqual(batches.count(), 2)

        display_batch = next(b for b in batches if b.quantity_purchased == Decimal('30'))
        unit_batch = next(b for b in batches if b.quantity_purchased == Decimal('10'))
        self.assertEqual(display_batch.purchase_price, Decimal('50'))
        self.assertEqual(unit_batch.purchase_price, Decimal('45'))


class PurchaseApiSearchEan14Tests(TestCase):
    """api_search_products: escanear un EAN-14 de display debe encontrar
    el producto usando los 13 dígitos internos (EAN-13)."""

    @classmethod
    def setUpTestData(cls):
        cls.admin_group, _ = Group.objects.get_or_create(name='Admin')
        cls.admin = User.objects.create_user(
            username='ean14_admin', password='pass123',
            is_superuser=True, is_staff=True,
        )
        cls.admin.groups.add(cls.admin_group)
        cls.category = ProductCategory.objects.create(name='EAN14 Cat')

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.admin)
        self.product = Product.objects.create(
            name='Producto EAN14', sku='E14-001', barcode='7790001000001',
            category=self.category,
            sale_price=Decimal('100'), purchase_price=Decimal('40'),
            cost_price=Decimal('40'), current_stock=Decimal('0'),
        )
        self.display_pkg = ProductPackaging.objects.create(
            product=self.product, packaging_type='display',
            name='Display x 12', barcode='7790001000099',
            units_per_display=12, displays_per_bulk=1,
            purchase_price=Decimal('480'), sale_price=Decimal('1100'),
            is_active=True,
        )

    def _search(self, code, barcode=True):
        url = reverse('purchase:api_search_products')
        params = f'?q={code}&barcode={"1" if barcode else "0"}'
        return self.client.get(url + params)

    def test_ean13_exacto_encuentra_packaging(self):
        """Escanear el EAN-13 exacto del display lo devuelve con matched_packaging_id."""
        resp = self._search('7790001000099')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['matched_packaging_id'], self.display_pkg.id)

    def test_ean14_con_indicador_0_encuentra_packaging(self):
        """Escanear 0 + EAN-13 del display debe encontrar el packaging."""
        resp = self._search('07790001000099')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['matched_packaging_id'], self.display_pkg.id)

    def test_ean14_con_indicador_1_encuentra_packaging(self):
        """Escanear 1 + EAN-13 del display también debe encontrar el packaging."""
        resp = self._search('17790001000099')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['matched_packaging_id'], self.display_pkg.id)

    def test_ean14_producto_base(self):
        """Escanear 0 + EAN-13 del producto base lo devuelve correctamente."""
        resp = self._search('07790001000001')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(data['results'][0]['id'], self.product.id)

    def test_ean14_no_numerico_no_intenta_stripping(self):
        """Un código de 14 caracteres no numérico no debe intentar stripping."""
        resp = self._search('ABCD1234567890')
        self.assertEqual(resp.status_code, 200)
        # Ningún resultado esperado para un código inventado
        data = resp.json()
        self.assertEqual(len(data['results']), 0)
