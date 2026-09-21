"""
Venta por peso — flujo simple (pedido de Sofia, 2026-09-20).

Sofia no entendía cómo cargar un producto por peso (precio, margen y stock) y
en el POS "no la dejaba vender". Causas encontradas y cubiertas acá:

1. Crear el producto por peso autorizando una pieza de depósito que ya tenía
   stock dejaba el producto del POS con stock 0 y costo 0 (copia vieja en
   memoria) aunque la caramelera sí tuviera mercadería.
2. Piezas de depósito sin "gramos por unidad" nunca se abrían: stock 0 sin
   ningún aviso, y recién al cobrar salía "Stock insuficiente".
3. El precio por gramo se guardaba con 2 decimales: con precio por kilo el
   total salía desfasado ($3.085 en vez de $3.086,25).
4. "Margen" significaba cosas distintas en Productos (sobre el costo) y en
   Venta por Peso (sobre el precio de venta).

Ahora se carga todo en una pantalla, por kilo, con stock inicial y costo.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase
from django.urls import reverse

from cashregister.models import CashRegister, CashShift, PaymentMethod
from granel.models import AperturaBulto, Caramelera, VentaGranel
from granel.services import GranelService
from pos.models import POSTransactionItem
from pos.services import CartService, POSService
from stocks.forms import ProductForm
from stocks.models import Product

User = get_user_model()


class WeightSaleBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        group, _ = Group.objects.get_or_create(name='Admin')
        cls.user = User.objects.create_user(
            username='sofia_peso', password='x', is_superuser=True, is_staff=True,
        )
        cls.user.groups.add(group)
        PaymentMethod.objects.create(name='Efectivo Peso', code='cash_peso', is_active=True)
        cls.register = CashRegister.objects.create(name='Caja Peso', code='PSO1', is_active=True)

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    def crear_por_peso(self, **extra):
        data = {
            'nombre': 'Jamón cocido',
            'precio_kg': '12000',
            'costo_kg': '8000',
            'stock_inicial': '2.5',
            'stock_unidad': 'kg',
        }
        data.update(extra)
        return self.client.post(reverse('granel:caramelera_create'), data)

    def nueva_transaccion(self):
        shift = CashShift.objects.create(
            cash_register=self.register, cashier=self.user,
            initial_amount=Decimal('1000'), status='open',
        )
        return POSService.create_transaction(POSService.get_or_create_session(shift))


class CargaSimpleTests(WeightSaleBase):
    def test_form_de_alta_se_muestra_por_kilo(self):
        r = self.client.get(reverse('granel:caramelera_create'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Costo por kilo')
        self.assertContains(r, 'Precio de venta por kilo')
        self.assertContains(r, '¿Cuánta mercadería tenés ahora?')

    def test_crea_producto_con_stock_costo_y_precio(self):
        r = self.crear_por_peso()
        self.assertEqual(r.status_code, 302, getattr(r, 'context', None) and r.context['errors'])
        c = Caramelera.objects.get()
        self.assertEqual(c.precio_100g, Decimal('1200.00'))          # 12000/kg → 1200 cada 100g
        self.assertEqual(c.stock_gramos_actual, Decimal('2500.00'))  # 2,5 kg
        self.assertEqual(c.costo_ponderado_gramo, Decimal('8.000000'))
        self.assertEqual(c.precio_cuarto, Decimal('0'))              # sin oferta automática

    def test_producto_del_pos_queda_con_stock_y_costo(self):
        self.crear_por_peso()
        p = Product.objects.get(is_granel=True)
        self.assertEqual(p.current_stock, Decimal('2500.000'))
        self.assertEqual(p.weighted_avg_cost_per_gram, Decimal('8.0000'))
        self.assertEqual(p.sale_price, Decimal('1200.00'))

    def test_stock_en_gramos(self):
        self.crear_por_peso(stock_inicial='750', stock_unidad='g')
        self.assertEqual(Caramelera.objects.get().stock_gramos_actual, Decimal('750.00'))

    def test_se_puede_crear_sin_stock_y_sin_costo(self):
        r = self.crear_por_peso(stock_inicial='', costo_kg='')
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Caramelera.objects.get().stock_gramos_actual, Decimal('0'))

    def test_stock_sin_costo_pide_el_costo(self):
        r = self.crear_por_peso(costo_kg='')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'cuánto te costó el kilo')
        self.assertFalse(Caramelera.objects.exists())

    def test_error_conserva_lo_que_escribio(self):
        r = self.crear_por_peso(costo_kg='', nombre='Queso rallado')
        self.assertContains(r, 'value="Queso rallado"')

    def test_margen_es_sobre_el_costo_como_en_productos(self):
        self.crear_por_peso()
        c = Caramelera.objects.get()
        # costo 8000, venta 12000 → 50% sobre el costo (no 33% sobre la venta)
        self.assertEqual(c.margen_sobre_costo, Decimal('50.0'))
        self.assertEqual(c.ganancia_kilo, Decimal('4000.00'))
        self.assertEqual(c.costo_kilo, Decimal('8000.00'))
        self.assertEqual(c.precio_kilo, Decimal('12000.00'))

    def test_detalle_y_lista_muestran_kilos_y_ganancia(self):
        self.crear_por_peso()
        c = Caramelera.objects.get()
        lista = self.client.get(reverse('granel:caramelera_list'))
        self.assertContains(lista, 'Precio por kilo')
        detalle = self.client.get(reverse('granel:caramelera_detail', args=[c.pk]))
        self.assertContains(detalle, 'Agregar mercadería')
        self.assertContains(detalle, '50,0% sobre el costo')
        self.assertContains(detalle, 'Stock inicial')


class DetalleProlijoTests(WeightSaleBase):
    def test_detalle_de_un_producto_cargado_directo_no_muestra_ruido(self):
        self.crear_por_peso()
        c = Caramelera.objects.get()
        html = self.client.get(reverse('granel:caramelera_detail', args=[c.pk])).content.decode()
        self.assertNotIn('>None<', html)                       # ranking de rotación con "None"
        self.assertNotIn('Sin productos autorizados', html)    # panel que no aplica a este producto
        self.assertIn('$8.000', html)                          # costo por kilo con separador de miles


class NumerosAbsurdosNoRompenTests(WeightSaleBase):
    """Un cero de más al tipear no puede terminar en un error 500."""

    def test_precio_gigante_avisa(self):
        r = self.crear_por_peso(precio_kg='95003078000')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'demasiado alto')
        self.assertFalse(Caramelera.objects.exists())

    def test_costo_y_oferta_gigantes_avisan(self):
        r = self.crear_por_peso(costo_kg='99999999999')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'demasiado alto')
        r = self.crear_por_peso(precio_cuarto='99999999999')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Caramelera.objects.exists())

    def test_stock_gigante_avisa(self):
        r = self.crear_por_peso(stock_inicial='99999999999')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'demasiado grande')

    def test_agregar_mercaderia_con_numeros_absurdos(self):
        self.crear_por_peso()
        c = Caramelera.objects.get()
        r = self.client.post(reverse('granel:api_ingresar_stock', args=[c.pk]),
                             data=json.dumps({'cantidad': 99999999999, 'unidad': 'kg', 'costo_kg': 8000}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)


class AgregarMercaderiaTests(WeightSaleBase):
    def _ingresar(self, **body):
        c = Caramelera.objects.get()
        return self.client.post(
            reverse('granel:api_ingresar_stock', args=[c.pk]),
            data=json.dumps(body), content_type='application/json',
        )

    def test_suma_stock_y_promedia_el_costo(self):
        self.crear_por_peso()  # 2500g a $8/g
        r = self._ingresar(cantidad=2.5, unidad='kg', costo_kg=10000)
        self.assertEqual(r.status_code, 200, r.content)
        c = Caramelera.objects.get()
        self.assertEqual(c.stock_gramos_actual, Decimal('5000.00'))
        # (2500×8 + 2500×10) / 5000 = $9/g
        self.assertEqual(c.costo_ponderado_gramo, Decimal('9.000000'))
        p = Product.objects.get(is_granel=True)
        self.assertEqual(p.current_stock, Decimal('5000.000'))
        self.assertEqual(p.weighted_avg_cost_per_gram, Decimal('9.0000'))

    def test_deja_registro_en_el_historial(self):
        self.crear_por_peso()
        self._ingresar(cantidad=500, unidad='g', costo_kg=9000)
        ap = AperturaBulto.objects.filter(caramelera=Caramelera.objects.get()).first()
        self.assertIsNone(ap.producto)
        self.assertIn('Ingreso directo', str(ap))

    def test_producto_vacio_recibe_su_primer_costo(self):
        self.crear_por_peso(stock_inicial='', costo_kg='')
        r = self._ingresar(cantidad=1, unidad='kg', costo_kg=7000)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Caramelera.objects.get().costo_ponderado_gramo, Decimal('7.000000'))

    def test_valida_cantidad_y_costo(self):
        self.crear_por_peso()
        self.assertEqual(self._ingresar(cantidad=0, unidad='kg', costo_kg=100).status_code, 400)
        self.assertEqual(self._ingresar(cantidad=1, unidad='kg', costo_kg=0).status_code, 400)
        self.assertEqual(self._ingresar(cantidad='x', unidad='kg', costo_kg=100).status_code, 400)


class DepositoSincronizaPosTests(WeightSaleBase):
    """Bug raíz: el producto del POS quedaba con stock 0 y costo 0."""

    def test_autorizar_pieza_con_stock_deja_el_pos_con_stock_y_costo(self):
        pieza = Product.objects.create(
            name='Jamón pieza', sku='PZ-1', es_deposito_caramelera=True,
            weight_per_unit_grams=Decimal('500'), cost_price=Decimal('5000'),
            sale_price=Decimal('5000'), current_stock=Decimal('3'),
        )
        r = self.client.post(reverse('granel:caramelera_create'), {
            'nombre': 'Jamón fraccionado', 'precio_100g': '2500',
            'productos_autorizados': [str(pieza.pk)],
        })
        self.assertEqual(r.status_code, 302)
        c = Caramelera.objects.get()
        self.assertEqual(c.stock_gramos_actual, Decimal('1500.00'))
        p = Product.objects.get(is_granel=True)
        self.assertEqual(p.current_stock, Decimal('1500.000'))
        self.assertEqual(p.weighted_avg_cost_per_gram, Decimal('10.0000'))


class FormularioDepositoTests(WeightSaleBase):
    def _form(self, **extra):
        data = {
            'name': 'Pieza', 'sku': 'PZ-9', 'cost_price': '100', 'sale_price': '100',
            'current_stock': '1', 'min_stock': '0', 'is_active': 'on',
            'es_deposito_caramelera': 'on',
        }
        data.update(extra)
        return ProductForm(data)

    def test_pieza_de_deposito_sin_gramos_no_se_puede_guardar(self):
        form = self._form(weight_per_unit_grams='')
        self.assertFalse(form.is_valid())
        self.assertIn('weight_per_unit_grams', form.errors)

    def test_pieza_de_deposito_con_gramos_se_guarda(self):
        self.assertTrue(self._form(weight_per_unit_grams='500').is_valid())

    def test_producto_comun_sigue_sin_pedir_gramos(self):
        form = self._form(weight_per_unit_grams='')
        form.data = {k: v for k, v in form.data.items() if k != 'es_deposito_caramelera'}
        self.assertTrue(ProductForm(form.data).is_valid())


class VentaEnPosTests(WeightSaleBase):
    def setUp(self):
        super().setUp()
        self.crear_por_peso()  # 2,5 kg a $12.000/kg, costo $8.000/kg
        self.pos_product = Product.objects.get(is_granel=True)

    def _agregar(self, tx, gramos, unit_price=None):
        body = {'transaction_id': tx.id, 'product_id': self.pos_product.id, 'quantity': gramos}
        if unit_price is not None:
            body['unit_price'] = unit_price
        return self.client.post(reverse('pos:api_cart_add'), json.dumps(body),
                                content_type='application/json')

    def _cobrar(self, tx):
        tx.refresh_from_db()
        return self.client.post(reverse('pos:api_checkout'), json.dumps({
            'transaction_id': tx.id,
            'payments': [{'method_code': 'cash_peso', 'amount': float(tx.total)}],
        }), content_type='application/json')

    def test_venta_completa_descuenta_stock_y_registra_ganancia(self):
        tx = self.nueva_transaccion()
        self.assertEqual(self._agregar(tx, 250).status_code, 200)
        tx.refresh_from_db()
        self.assertEqual(tx.total, Decimal('3000.00'))  # 250g × $12/g
        r = self._cobrar(tx)
        self.assertEqual(r.status_code, 200, r.content)
        c = Caramelera.objects.get()
        self.assertEqual(c.stock_gramos_actual, Decimal('2250.00'))
        venta = VentaGranel.objects.get()
        self.assertEqual(venta.costo_total, Decimal('2000.00'))
        self.assertEqual(venta.ganancia, Decimal('1000.00'))
        self.pos_product.refresh_from_db()
        self.assertEqual(self.pos_product.current_stock, Decimal('2250.000'))

    def test_precio_kilo_oferta_no_pierde_centavos(self):
        c = Caramelera.objects.get()
        c.precio_cuarto = Decimal('12345.00')
        c.save()
        tx = self.nueva_transaccion()
        # el navegador redondea distinto: el servidor manda
        self.assertEqual(self._agregar(tx, 250, unit_price=12.34).status_code, 200)
        tx.refresh_from_db()
        self.assertEqual(tx.total, Decimal('3086.25'))  # 250g × 12345/kg
        self.assertEqual(self._cobrar(tx).status_code, 200)

    def test_precio_manipulado_desde_el_navegador_se_ignora(self):
        tx = self.nueva_transaccion()
        self._agregar(tx, 100, unit_price=0.01)
        tx.refresh_from_db()
        self.assertEqual(tx.total, Decimal('1200.00'))

    def test_sin_stock_avisa_claro_al_agregar(self):
        Caramelera.objects.update(stock_gramos_actual=Decimal('0'))
        tx = self.nueva_transaccion()
        r = self._agregar(tx, 100)
        self.assertEqual(r.status_code, 400)
        self.assertIn('Agregar mercadería', r.json()['error'])
        self.assertFalse(POSTransactionItem.objects.exists())

    def test_no_deja_pasarse_del_stock_ni_sumando_lineas(self):
        tx = self.nueva_transaccion()
        self.assertEqual(self._agregar(tx, 2000).status_code, 200)
        r = self._agregar(tx, 600)  # 2000 + 600 > 2500
        self.assertEqual(r.status_code, 400)
        self.assertIn('quedan 2500g', r.json()['error'])
        self.assertEqual(self._agregar(tx, 500).status_code, 200)  # justo lo que queda

    def test_producto_comun_no_cambia(self):
        normal = Product.objects.create(
            name='Gaseosa', sku='G-1', cost_price=Decimal('500'),
            sale_price=Decimal('800'), current_stock=Decimal('10'),
        )
        tx = self.nueva_transaccion()
        item, _ = CartService.add_item(tx, normal.pk, Decimal('2'))
        self.assertEqual(item.unit_price, Decimal('800'))
        tx.refresh_from_db()
        self.assertEqual(tx.total, Decimal('1600.00'))

    def test_buscador_del_pos_trae_stock_real(self):
        r = self.client.get(reverse('pos:api_search'), {'q': 'jamon'})
        prod = r.json()['products'][0]
        self.assertTrue(prod['is_granel'])
        self.assertEqual(prod['stock'], 2500.0)
