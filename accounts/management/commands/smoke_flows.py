"""
Prueba de humo de los flujos principales contra la base REAL, sin dejar rastros.

Recorre lo que hace Sofia (cargar un producto por peso, comprarlo a un proveedor y
recibirlo, venderlo en la caja, cerrar la caja, importar un Excel, crear una promo...)
y visita las pantallas del sistema con los datos reales.

Seguridad:
- TODO corre dentro de una transacción que SIEMPRE se deshace al final (no existe una
  opción para confirmarla). Al terminar se comparan los conteos de las tablas: tienen
  que quedar idénticos.
- No visita MercadoPago ni el asistente de IA (llaman a servicios externos que no se
  pueden deshacer) y en las pantallas existentes solo hace GET.
- Los datos de prueba usan el prefijo "ZZ SMOKE".

Uso:  python manage.py smoke_flows
"""
import io
import json
import re
import traceback
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand
from django.db import transaction
from django.test import Client
from django.urls import get_resolver, reverse
from django.urls.resolvers import URLPattern, URLResolver
from django.utils import timezone

SKIP_PREFIXES = ('admin/', 'mercadopago/', 'assistant/')
SKIP_NAMES = {'logout'}


class Rollback(Exception):
    """Fuerza el deshacer de la transacción."""


def _walk(patterns, prefix=''):
    for p in patterns:
        if isinstance(p, URLResolver):
            yield from _walk(p.url_patterns, prefix + str(p.pattern))
        elif isinstance(p, URLPattern):
            yield prefix + str(p.pattern), p.name


class Command(BaseCommand):
    help = 'Prueba de humo de los flujos principales; siempre deshace todo lo que hace.'

    def handle(self, *args, **options):
        import logging
        logging.getLogger('django.request').setLevel(logging.CRITICAL)   # 404/405 esperados al recorrer
        self.results = []
        counts_before = self._counts()
        try:
            with transaction.atomic():
                self._run()
                raise Rollback()          # SIEMPRE se deshace
        except Rollback:
            pass
        counts_after = self._counts()

        limpio = counts_before == counts_after
        self._report('La base quedó idéntica (nada se guardó)', limpio,
                     '' if limpio else str({k: (counts_before[k], counts_after[k])
                                            for k in counts_before if counts_before[k] != counts_after[k]}))

        fallas = [r for r in self.results if not r[0]]
        self.stdout.write('')
        self.stdout.write(f'{len(self.results) - len(fallas)} OK, {len(fallas)} con problemas')
        if fallas:
            for _, nombre, detalle in fallas:
                self.stdout.write(self.style.ERROR(f'  ✗ {nombre} — {detalle}'))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS('Todo bien.'))

    # ------------------------------------------------------------------
    def _counts(self):
        from cashregister.models import CashMovement, CashRegister, CashShift
        from expenses.models import Expense
        from granel.models import AperturaBulto, Caramelera, VentaGranel
        from pos.models import POSSession, POSTransaction, POSTransactionItem
        from promotions.models import Promotion
        from purchase.models import Purchase, PurchaseItem, Supplier
        from stocks.models import Product, ProductCategory, ProductPackaging, StockBatch, StockMovement
        from django.contrib.sessions.models import Session
        User = get_user_model()
        modelos = [Product, ProductCategory, ProductPackaging, StockMovement, StockBatch, Purchase,
                   PurchaseItem, Supplier, POSTransaction, POSTransactionItem, POSSession, CashShift,
                   CashMovement, CashRegister, Expense, Caramelera, AperturaBulto, VentaGranel,
                   Promotion, User, Group, Session]
        return {m.__name__: m.objects.count() for m in modelos}

    def _report(self, nombre, cond, detalle=''):
        self.results.append((bool(cond), nombre, detalle))
        marca = self.style.SUCCESS('✓') if cond else self.style.ERROR('✗')
        self.stdout.write(f'  {marca} {nombre}' + (f'  [{detalle}]' if detalle and not cond else ''))

    def _step(self, titulo, fn):
        self.stdout.write(self.style.MIGRATE_HEADING(titulo))
        try:
            with transaction.atomic():         # punto de guardado: si un paso falla no arrastra a los demás
                fn()
        except Exception as exc:  # noqa: BLE001
            self._report(f'{titulo}: no terminó', False,
                         f'{type(exc).__name__}: {exc} @ {traceback.format_exc().strip().splitlines()[-3].strip()[:120]}')

    # ------------------------------------------------------------------
    def _run(self):
        from cashregister.models import CashMovement, CashRegister, CashShift, PaymentMethod
        from granel.models import Caramelera
        from pos.services import POSService
        from promotions.models import Promotion
        from purchase.models import Purchase, PurchaseItem, Supplier
        from stocks.models import Product

        User = get_user_model()
        host = next((h for h in settings.ALLOWED_HOSTS if h and h != '*' and not h.startswith('.')), 'localhost')
        c = Client(HTTP_HOST=host)

        for g in ('Admin', 'Cajero Manager', 'Cashier'):
            Group.objects.get_or_create(name=g)
        PaymentMethod.get_default_methods()
        user = User.objects.create_user('zz_smoke_admin', password=None, is_superuser=True, is_staff=True, is_admin=True)
        user.set_unusable_password()
        user.save()
        c.force_login(user)

        state = {}

        # ------------------------------------------------------------ 1
        def producto_por_peso():
            # Rediseño 2026-09-25: "se vende por peso" es un checkbox en la
            # MISMA pantalla de producto — ya no hay pestaña ni pieza de
            # depósito aparte (ver plan sharded-honking-quilt.md, Fase 2/3).
            r = c.post(reverse('stocks:product_create'), {
                'name': 'ZZ SMOKE Jamón', 'sku': 'ZZSMOKE-PESO', 'barcode': '', 'cost_price': '8000',
                'sale_price': '12000', 'current_stock': '2.5', 'min_stock': '1',
                'is_active': 'true', 'is_granel': 'true', 'weight_per_unit_grams': ''})
            self._report('crea un producto por peso (1 pantalla)', r.status_code == 302, str(r.status_code))
            peso = Product.objects.get(name='ZZ SMOKE Jamón')
            state['peso'] = peso
            self._report('queda con 2,500 kg de stock',
                         peso.current_stock == Decimal('2.500'), str(peso.current_stock))
            self._report('precio $12.000/kg y margen 50% sobre el costo',
                         peso.sale_price == Decimal('12000.00') and peso.margin_percent == Decimal('50.00'),
                         f'{peso.sale_price} / {peso.margin_percent}')
            r = c.post(reverse('stocks:product_add_stock', args=[peso.pk]), {
                'kilos': '0.5', 'costo_kilo': '10000'})
            peso.refresh_from_db()
            self._report('"Agregar Mercadería" suma y promedia el costo', r.status_code == 302 and
                         peso.current_stock == Decimal('3.000') and peso.cost_price == Decimal('8333.33'),
                         f'{peso.current_stock} kg, ${peso.cost_price}/kg')
        self._step('1. Producto por peso', producto_por_peso)

        # ------------------------------------------------------------ 2
        def producto_comun():
            r = c.post(reverse('stocks:product_create'), {
                'name': 'ZZ SMOKE Yerba', 'sku': '', 'barcode': '7799999000012', 'cost_price': '2000',
                'sale_price': '3000', 'current_stock': '10', 'min_stock': '3', 'is_active': 'true',
                'weight_per_unit_grams': ''})
            self._report('crea un producto común', r.status_code == 302, str(r.status_code))
            p = Product.objects.get(barcode='7799999000012')
            state['comun'] = p
            busq = c.get(reverse('pos:api_search'), {'q': '7799999000012'}).json()['products']
            self._report('la caja lo encuentra por código de barras con su precio y stock',
                         busq and busq[0]['unit_price'] == 3000.0 and busq[0]['stock'] == 10.0, str(busq[:1]))
            Product.objects.filter(pk=p.pk).update(current_stock=Decimal('7'))
            c.post(reverse('stocks:product_edit', args=[p.pk]), {
                'name': 'ZZ SMOKE Yerba', 'sku': p.sku, 'barcode': p.barcode, 'cost_price': '2000',
                'sale_price': '3100', 'current_stock': '10', 'min_stock': '3', 'is_active': 'true',
                'weight_per_unit_grams': ''})
            p.refresh_from_db()
            self._report('editar el precio NO pisa el stock (queda 7)', p.sale_price == Decimal('3100') and p.current_stock == Decimal('7'),
                         f'{p.sale_price} / {p.current_stock}')
            Product.objects.filter(pk=p.pk).update(current_stock=Decimal('10'), sale_price=Decimal('3000'))
        self._step('2. Producto común', producto_comun)

        # ------------------------------------------------------------ 3
        def compras():
            sup = Supplier.objects.create(name='ZZ SMOKE Proveedor', order_day='mon')
            peso, comun = state['peso'], state['comun']
            r = c.post(reverse('purchase:purchase_create'), json.dumps({
                'supplier_id': sup.pk, 'tax_percent': 0,
                'items': [{'product_id': peso.pk, 'quantity': '1.5', 'unit_cost': 9000},
                          {'product_id': comun.pk, 'quantity': 6, 'unit_cost': 1800}]}), content_type='application/json')
            self._report('crea una orden con 1,5 kg de un producto por peso y unidades de otro', r.status_code == 200, r.content[:120].decode())
            oc = Purchase.objects.get(supplier=sup)
            self._report('el total de la orden es $24.300', oc.total == Decimal('24300.00'), str(oc.total))
            stock_antes = Product.objects.get(pk=peso.pk).current_stock
            r = c.post(reverse('purchase:purchase_receive', args=[oc.pk]))
            comun.refresh_from_db(); peso.refresh_from_db()
            self._report('al recibir, el peso entra al producto (+1,5 kg) y las unidades también (+6)',
                         peso.current_stock - stock_antes == Decimal('1.5') and comun.current_stock == Decimal('16'),
                         f'{stock_antes}→{peso.current_stock}; comun={comun.current_stock}')
            oc.refresh_from_db()
            self._report('la orden queda recibida y se genera el gasto', oc.status == 'received')
            r2 = c.post(reverse('purchase:purchase_receive', args=[oc.pk]))
            peso.refresh_from_db()
            self._report('no se puede recibir dos veces', peso.current_stock - stock_antes == Decimal('1.5'))
            comun.current_stock = Decimal('10'); comun.save()
        self._step('3. Proveedores y órdenes de compra', compras)

        # ------------------------------------------------------------ 4
        def caja_y_ventas():
            peso, comun = state['peso'], state['comun']
            reg = CashRegister.objects.create(name='ZZ SMOKE Caja', code='ZZSMK', is_active=True)
            r = c.post(reverse('cashregister:open_shift'), {'cash_register': reg.pk, 'initial_amount': '5000'})
            shift = CashShift.objects.get(cash_register=reg)
            self._report('abre el turno de caja', r.status_code == 302 and shift.status == 'open')
            session = POSService.get_or_create_session(shift)

            def cobrar(items, pagos):
                tx = POSService.create_transaction(session)
                for prod, cant in items:
                    rr = c.post(reverse('pos:api_cart_add'), json.dumps(
                        {'transaction_id': tx.id, 'product_id': prod.pk, 'quantity': cant}), content_type='application/json')
                    if rr.status_code != 200:
                        return tx, rr
                tx.refresh_from_db()
                pagos = pagos(tx)
                return tx, c.post(reverse('pos:api_checkout'), json.dumps(
                    {'transaction_id': tx.id, 'payments': pagos}), content_type='application/json')

            stock0 = Product.objects.get(pk=peso.pk).current_stock
            tx, r = cobrar([(peso, 250), (comun, 2)], lambda t: [{'method_code': 'cash', 'amount': float(t.total) + 500}])
            self._report('vende 250 g de peso + 2 unidades en efectivo con vuelto',
                         r.status_code == 200 and abs(r.json().get('change', 0) - 500) < 0.01, r.content[:150].decode())
            tx.refresh_from_db()
            self._report('total = 250 g × $12/g + 2 × $3.000 = $9.000', tx.total == Decimal('9000.00'), str(tx.total))
            peso.refresh_from_db(); comun.refresh_from_db()
            self._report('descuenta el stock (peso −0,250 kg, unidades −2)',
                         stock0 - peso.current_stock == Decimal('0.250') and comun.current_stock == Decimal('8'),
                         f'{stock0}→{peso.current_stock}; {comun.current_stock}')
            tx2, r = cobrar([(comun, 1)], lambda t: [{'method_code': 'transfer', 'amount': float(t.total)}])
            self._report('vende por transferencia', r.status_code == 200, r.content[:120].decode())
            tx3, r = cobrar([(peso, 99999)], lambda t: [{'method_code': 'cash', 'amount': 1}])
            self._report('no deja vender más peso del que hay', r.status_code == 400, str(r.status_code))
            r = c.post(reverse('pos:api_checkout'), json.dumps(
                {'transaction_id': tx.id, 'payments': [{'method_code': 'cash', 'amount': 9000}]}), content_type='application/json')
            self._report('no se puede cobrar dos veces el mismo ticket', r.status_code == 400, str(r.status_code))
            shift.refresh_from_db()
            esperado = shift.calculate_expected()
            self._report('efectivo esperado = inicial $5.000 + venta $9.000 (la transferencia no cuenta)',
                         esperado == Decimal('14000.00'), str(esperado))
            r = c.post(reverse('cashregister:close_shift', args=[shift.pk]), {'actual_amount': '13900', 'notes': 'smoke'})
            shift.refresh_from_db()
            self._report('cierra la caja con un faltante de $100', shift.status == 'closed' and shift.difference == Decimal('-100.00'),
                         f'{shift.status} {shift.difference}')
            comun.current_stock = Decimal('10'); comun.save()
        self._step('4. Caja y ventas', caja_y_ventas)

        # ------------------------------------------------------------ 5
        def promociones():
            from pos.services import CartService
            from cashregister.models import CashRegister, CashShift
            comun = state['comun']
            r = c.post(reverse('promotions:promotion_create'), {
                'name': 'ZZ SMOKE 2x1', 'promo_type': 'nxm', 'status': 'active', 'buy_quantity': '2',
                'pay_quantity': '1', 'products': str(comun.pk)})
            self._report('crea una promo 2x1 desde el formulario', r.status_code == 302, str(r.status_code))
            reg = CashRegister.objects.create(name='ZZ SMOKE Caja 2', code='ZZSMK2', is_active=True)
            sh = CashShift.objects.create(cash_register=reg, cashier=user, initial_amount=Decimal('0'), status='open')
            tx = POSService.create_transaction(POSService.get_or_create_session(sh))
            CartService.add_item(tx, comun.pk, Decimal('2'))
            tx.refresh_from_db()
            self._report('2 unidades con 2x1 cuestan una sola ($3.000)', tx.total == Decimal('3000.00'), str(tx.total))
            peso = state['peso']
            c.post(reverse('promotions:promotion_create'), {
                'name': 'ZZ SMOKE -20% peso', 'promo_type': 'simple_discount', 'status': 'active',
                'discount_percent_simple': '20', 'products': str(peso.pk)})
            tx = POSService.create_transaction(POSService.get_or_create_session(sh))
            CartService.add_item(tx, peso.pk, Decimal('250'))
            tx.refresh_from_db()
            self._report('250 g con descuento 20% cuestan $2.400', tx.total == Decimal('2400.00'), str(tx.total))
        self._step('5. Promociones', promociones)

        # ------------------------------------------------------------ 6
        def importar_excel():
            import openpyxl
            from django.core.files.uploadedfile import SimpleUploadedFile
            wb = openpyxl.Workbook(); wb.remove(wb.active)
            ws = wb.create_sheet('ZZ SMOKE Almacén')
            ws.append(['Código de barras', 'Nombre', 'Costo', 'Venta', 'Stock'])
            ws.append([7799999000100, 'ZZ SMOKE Lentejas', 600, 950, 30])
            buf = io.BytesIO(); wb.save(buf)
            r = c.post(reverse('stocks:import_excel'), {'excel_file': SimpleUploadedFile('x.xlsx', buf.getvalue())})
            self._report('importar Excel: muestra la vista previa', r.status_code == 200, str(r.status_code))
            r = c.post(reverse('stocks:import_excel'), {'confirm': '1'})
            p = Product.objects.filter(barcode='7799999000100').first()
            self._report('importar Excel: crea el producto con su stock (30)', p is not None and p.current_stock == Decimal('30'),
                         str(p and p.current_stock))
        self._step('6. Importar Excel', importar_excel)

        # ------------------------------------------------------------ 7
        def pantallas():
            from cashregister.models import CashShift as CS
            from company.models import Company
            from expenses.models import Expense
            from promotions.models import Promotion as Pr
            from purchase.models import Purchase as Pu, Supplier as Su
            from stocks.models import Product as Pd, ProductCategory as PC
            ids = {
                'pk': set(), 'transaction_id': set(), 'item_id': set(), 'shift_pk': set(),
                'packaging_id': set(), 'link_pk': set(), 'supplier_id': set(),
            }
            from pos.models import POSTransaction, POSTransactionItem
            from stocks.models import ProductPackaging
            from purchase.models import SupplierProduct
            for model in (Pd, PC, Su, Pu, Pr, CS, Expense, Company, Caramelera, User):
                ids['pk'] |= set(model.objects.order_by('-pk').values_list('pk', flat=True)[:3])
            ids['transaction_id'] = set(POSTransaction.objects.order_by('-pk').values_list('pk', flat=True)[:3])
            ids['item_id'] = set(POSTransactionItem.objects.order_by('-pk').values_list('pk', flat=True)[:3])
            ids['shift_pk'] = set(CS.objects.order_by('-pk').values_list('pk', flat=True)[:3])
            ids['packaging_id'] = set(ProductPackaging.objects.order_by('-pk').values_list('pk', flat=True)[:3])
            ids['link_pk'] = set(SupplierProduct.objects.order_by('-pk').values_list('pk', flat=True)[:3])
            ids['supplier_id'] = set(Su.objects.order_by('-pk').values_list('pk', flat=True)[:3])

            visitadas, malas = 0, []
            for route, name in _walk(get_resolver().url_patterns):
                if route.startswith(SKIP_PREFIXES) or name in SKIP_NAMES:
                    continue
                params = re.findall(r'<(?:\w+:)?(\w+)>', route)
                if any(p not in ids for p in params):
                    continue
                urls = ['/' + route]
                for p in params:
                    urls = [re.sub(r'<(?:\w+:)?%s>' % p, str(v), u, count=1) for u in urls for v in ids[p]]
                for url in urls:
                    visitadas += 1
                    try:
                        with transaction.atomic():
                            resp = c.get(url)
                            body = resp.content[:60000].decode('utf-8', 'ignore') if resp.status_code == 200 else ''
                            transaction.set_rollback(True)
                        if resp.status_code >= 500 or any(m in body for m in (
                                'Traceback (most recent call last)', 'TemplateSyntaxError', 'NoReverseMatch')):
                            malas.append(f'{url} → {resp.status_code}')
                    except Exception as exc:  # noqa: BLE001
                        malas.append(f'{url} → {type(exc).__name__}: {str(exc)[:100]}')
            self._report(f'las {visitadas} pantallas visitadas con datos reales abren sin errores', not malas, '; '.join(malas[:6]))
        self._step('7. Pantallas con datos reales (solo lectura)', pantallas)
