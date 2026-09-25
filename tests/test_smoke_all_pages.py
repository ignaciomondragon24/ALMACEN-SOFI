"""
Recorrido de TODO el sistema: visita cada ruta (páginas y APIs, ~190) con datos
reales de un día de trabajo y con cada rol, y falla si alguna da error 500, tira
una excepción o muestra una plantilla rota.

Cada visita corre dentro de un savepoint que se deshace, así ninguna página que
haga algo al abrirla (o un "eliminar") arruina los datos del resto del recorrido.

Es la red de seguridad contra "se rompió una pantalla y nadie se enteró".
"""
import re
import traceback
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.test import Client, TestCase
from django.urls import get_resolver
from django.urls.resolvers import URLPattern, URLResolver
from django.utils import timezone

from cashregister.models import CashRegister, CashShift, PaymentMethod
from company.models import Company
from expenses.models import Expense, ExpenseCategory
from pos.models import POSTransaction, POSTransactionItem
from pos.services import CartService, CheckoutService, POSService
from promotions.models import Promotion, PromotionProduct
from purchase.models import Purchase, PurchaseItem, Supplier, SupplierProduct
from stocks.models import Product, ProductCategory, ProductPackaging, StockBatch, UnitOfMeasure

User = get_user_model()

# Rutas que no se visitan: cierran sesión, o son el admin de Django.
SKIP_PREFIXES = ('admin/',)
SKIP_NAMES = {'logout'}
# Códigos aceptables: OK, redirección, pedido inválido/incompleto (APIs sin parámetros),
# sin permiso, no encontrado (id que no corresponde a ese modelo), método no permitido.
OK_CODES = {200, 201, 204, 301, 302, 400, 401, 403, 404, 405, 409, 422}


def _walk(patterns, prefix=''):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p.name


def _all_routes():
    routes = []
    for route, name in _walk(get_resolver().url_patterns):
        if route.startswith(SKIP_PREFIXES) or name in SKIP_NAMES:
            continue
        routes.append((route, name))
    return routes


class SmokeAllPages(TestCase):
    @classmethod
    def setUpTestData(cls):
        # ---- usuarios por rol
        cls.users = {}
        for role in ('Admin', 'Cajero Manager', 'Cashier', 'Stock Manager'):
            g, _ = Group.objects.get_or_create(name=role)
            u = User.objects.create_user(f'u_{role.split()[0].lower()}', password='x')
            u.groups.add(g)
            cls.users[role] = u
        cls.users['superuser'] = User.objects.create_user(
            'u_super', password='x', is_superuser=True, is_staff=True)

        # ---- catálogo
        Company.objects.create(name='Almacén Sofia')
        cat = ProductCategory.objects.create(name='Almacén')
        unit, _ = UnitOfMeasure.objects.get_or_create(name='Unidad', abbreviation='u')
        cls.cat = cat
        cls.product = Product.objects.create(
            name='Aceite 900ml', sku='ACE-1', barcode='7790000000011', category=cat,
            unit_of_measure=unit, cost_price=Decimal('1000'), sale_price=Decimal('1500'),
            current_stock=Decimal('24'), min_stock=5)
        cls.pkg = ProductPackaging.objects.create(
            product=cls.product, packaging_type='unit', name='Aceite 900ml',
            barcode='7790000000011', purchase_price=Decimal('1000'), sale_price=Decimal('1500'),
            current_stock=Decimal('24'))
        cls.product2 = Product.objects.create(
            name='Fideos 500g', sku='FID-1', category=cat, cost_price=Decimal('400'),
            sale_price=Decimal('700'), current_stock=Decimal('40'), min_stock=10)
        StockBatch.objects.create(
            product=cls.product2, quantity_purchased=Decimal('40'), quantity_remaining=Decimal('40'),
            purchase_price=Decimal('400'), purchased_at=timezone.now(),
            expiration_date=timezone.localdate() + timezone.timedelta(days=10))

        # ---- venta por peso (rediseño 2026-09-25: checkbox en el mismo
        # formulario de producto, igual que lo carga Sofia ahora)
        c = Client()
        c.force_login(cls.users['superuser'])
        c.post('/stocks/add/', {
            'name': 'Jamón cocido', 'sku': 'JC-SMOKE', 'cost_price': '8000',
            'sale_price': '12000', 'current_stock': '5', 'min_stock': '1',
            'is_active': 'true', 'is_granel': 'true'})
        cls.weight_product = Product.objects.get(is_granel=True)

        # ---- proveedores y compras
        cls.supplier = Supplier.objects.create(name='Distribuidora Sur', order_day='mon')
        cls.link = SupplierProduct.objects.create(
            supplier=cls.supplier, product=cls.product, cost_price=Decimal('950'))
        SupplierProduct.objects.create(
            supplier=cls.supplier, product=cls.weight_product, cost_price=Decimal('9000'))
        cls.purchase = Purchase.objects.create(supplier=cls.supplier, order_number='OC-SMOKE-1')
        PurchaseItem.objects.create(purchase=cls.purchase, product=cls.product,
                                    quantity=12, unit_cost=Decimal('950'))
        PurchaseItem.objects.create(purchase=cls.purchase, product=cls.weight_product,
                                    quantity=Decimal('2.5'), unit_cost=Decimal('9000'))

        # ---- promoción
        promo = Promotion.objects.create(name='2x1 fideos', promo_type='nxm', status='active',
                                         quantity_required=2, quantity_charged=1)
        PromotionProduct.objects.create(promotion=promo, product=cls.product2)
        cls.promo = promo

        # ---- caja, turno, ventas
        cash = PaymentMethod.objects.create(name='Efectivo', code='cash', is_active=True)
        PaymentMethod.objects.create(name='Transferencia', code='transfer', is_active=True)
        reg = CashRegister.objects.create(name='Caja 1', code='C01', is_active=True)
        cls.shift = CashShift.objects.create(
            cash_register=reg, cashier=cls.users['Cashier'],
            initial_amount=Decimal('5000'), status='open')
        session = POSService.get_or_create_session(cls.shift)
        done = POSService.create_transaction(session)
        CartService.add_item(done, cls.product.pk, Decimal('2'))
        CartService.add_item(done, cls.weight_product.pk, Decimal('300'))
        done.refresh_from_db()
        CheckoutService.process_payment(
            done.pk, [{'method_code': 'cash', 'amount': str(done.total)}])
        cls.pending = POSService.create_transaction(session)
        CartService.add_item(cls.pending, cls.product2.pk, Decimal('2'))

        # ---- gastos
        ecat = ExpenseCategory.objects.create(name='Servicios')
        cls.expense = Expense.objects.create(
            category=ecat, description='Luz', amount=Decimal('12000'),
            expense_date=timezone.localdate(), payment_method='transfer',
            created_by=cls.users['superuser'])

    # ------------------------------------------------------------------
    def _candidate_ids(self):
        """Ids que existen en el recorrido, agrupados por nombre de parámetro."""
        pending_item = POSTransactionItem.objects.filter(transaction=self.pending).first()
        pks = {
            self.product.pk, self.product2.pk, self.cat.pk, self.supplier.pk, self.purchase.pk,
            self.promo.pk, self.shift.pk, self.expense.pk,
            self.weight_product.pk, self.pending.pk, self.users['superuser'].pk,
            self.users['Cashier'].pk, Company.objects.first().pk,
        }
        pks |= set(UnitOfMeasure.objects.values_list('pk', flat=True))
        pks |= set(PaymentMethod.objects.values_list('pk', flat=True))
        pks |= set(ExpenseCategory.objects.values_list('pk', flat=True))
        pks |= set(CashRegister.objects.values_list('pk', flat=True))
        return {
            'pk': sorted(pks),
            'transaction_id': [self.pending.pk, POSTransaction.objects.exclude(pk=self.pending.pk).first().pk],
            'item_id': [pending_item.pk],
            'shift_pk': [self.shift.pk],
            'packaging_id': [self.pkg.pk],
            'link_pk': [self.link.pk],
            'supplier_id': [self.supplier.pk],
        }

    def _urls_for(self, route, ids):
        """Todas las URLs concretas de una ruta (una por cada id candidato)."""
        params = re.findall(r'<(?:\w+:)?(\w+)>', route)
        if not params:
            return ['/' + route]
        if any(p not in ids for p in params):
            return []                      # ids de MercadoPago/asistente/archivos: se cubren aparte
        urls = ['/' + route]
        for p in params:
            nxt = []
            for u in urls:
                for val in ids[p]:
                    nxt.append(re.sub(r'<(?:\w+:)?%s>' % p, str(val), u, count=1))
            urls = nxt
        return urls

    def _visit(self, client, url, method='get'):
        """Devuelve (status, problema|None). Deshace todo lo que la visita haya hecho."""
        try:
            with transaction.atomic():
                if method == 'post':
                    resp = client.post(url, data='{}', content_type='application/json')
                else:
                    resp = client.get(url, follow=False)
                body = b''
                if resp.status_code == 200 and 'text/html' in resp.get('Content-Type', ''):
                    body = resp.content
                transaction.set_rollback(True)
        except Exception as exc:  # noqa: BLE001 — queremos ver CUALQUIER falla
            tb = traceback.format_exc().strip().splitlines()
            return 'EXC', f'{type(exc).__name__}: {exc} @ {tb[-3].strip()[:120]}'
        if resp.status_code >= 500:
            return resp.status_code, 'error 500'
        if resp.status_code not in OK_CODES:
            return resp.status_code, f'código inesperado {resp.status_code}'
        text = body.decode('utf-8', 'ignore')
        for marker in ('Traceback (most recent call last)', 'TemplateDoesNotExist',
                       'TemplateSyntaxError', 'NoReverseMatch'):
            if marker in text:
                return resp.status_code, f'la página muestra "{marker}"'
        return resp.status_code, None

    def _crawl(self, user_key, method='get'):
        client = Client(raise_request_exception=True)
        if user_key != 'anonymous':
            client.force_login(self.users[user_key])
        ids = self._candidate_ids()
        problems, visited, ok200 = [], 0, 0
        for route, name in _all_routes():
            for url in self._urls_for(route, ids):
                status, problem = self._visit(client, url, method)
                visited += 1
                if status == 200:
                    ok200 += 1
                if problem:
                    problems.append(f'[{user_key}] {method.upper()} {url} ({name}) → {problem}')
        return visited, ok200, problems

    # ------------------------------------------------------------------
    def _assert_clean(self, user_key, min_pages_ok=0, method='get'):
        visited, ok200, problems = self._crawl(user_key, method)
        self.assertFalse(problems, f'{len(problems)} problemas:\n' + '\n'.join(problems[:40]))
        self.assertGreaterEqual(ok200, min_pages_ok,
                                f'{user_key}: solo {ok200} páginas respondieron 200 de {visited}')

    def test_get_superusuario(self):
        # el dueño tiene que poder abrir la gran mayoría de las pantallas
        self._assert_clean('superuser', min_pages_ok=60)

    def test_get_admin(self):
        self._assert_clean('Admin', min_pages_ok=40)

    def test_get_cajero_manager(self):
        self._assert_clean('Cajero Manager', min_pages_ok=15)

    def test_get_cajero(self):
        self._assert_clean('Cashier', min_pages_ok=5)

    def test_get_stock_manager(self):
        self._assert_clean('Stock Manager', min_pages_ok=5)

    def test_get_sin_sesion_no_abre_nada_privado(self):
        client = Client()
        abiertas = []
        for route, name in _all_routes():
            for url in self._urls_for(route, self._candidate_ids()):
                status, problem = self._visit(client, url)
                self.assertIsNone(problem, f'{url}: {problem}')
                if status == 200:
                    abiertas.append(url)
        permitidas = ('/login/', '/health/', '/register/', '/password')
        privadas = [u for u in abiertas if not u.startswith(permitidas)]
        self.assertEqual(privadas, [], f'Páginas abiertas sin iniciar sesión: {privadas}')

    def test_post_vacio_no_rompe_ninguna_api(self):
        """Un POST sin datos a cada ruta (todas las APIs) tiene que dar un error prolijo, no un 500."""
        self._assert_clean('superuser', method='post')
